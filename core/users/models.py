"""
User models for GroupBuy Bot
Supports three roles: buyer, organizer, supplier
"""
from django.db import models
from django.core.validators import RegexValidator


class User(models.Model):
    """User model with support for multiple messenger platforms"""

    class Role(models.TextChoices):
        BUYER = 'buyer', 'Buyer'
        ORGANIZER = 'organizer', 'Organizer'
        SUPPLIER = 'supplier', 'Supplier'

    class Platform(models.TextChoices):
        TELEGRAM = 'telegram', 'Telegram'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        WEBSOCKET = 'websocket', 'WebSocket'
        VK = 'vk', 'VKontakte'

    # Platform identification
    platform = models.CharField(max_length=20, choices=Platform.choices, default=Platform.TELEGRAM)
    platform_user_id = models.CharField(max_length=100, db_index=True)

    # User info — taken from the messenger profile, all optional so users
    # control what personal data they share.
    username = models.CharField(max_length=100, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)

    # Contact info
    phone_regex = RegexValidator(
        regex=r'^\+?[1-9]\d{10,14}$',
        message="Phone number must be in format: '+79991234567'"
    )
    phone = models.CharField(validators=[phone_regex], max_length=20, blank=True)
    email = models.EmailField(blank=True)

    # Identity verification — selfie taken during registration.
    # Stored as a Telegram file_id; visible only to admins, never exposed in
    # regular API responses.
    selfie_file_id = models.CharField(max_length=255, blank=True)

    # Role and balance
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.BUYER)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Metadata
    language_code = models.CharField(max_length=10, default='ru')
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    # Ban fields — cached in Redis (10 s TTL) to protect DB from DDoS/scraping
    is_banned = models.BooleanField(default=False, db_index=True)
    banned_at = models.DateTimeField(null=True, blank=True)
    ban_reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        unique_together = ['platform', 'platform_user_id']
        indexes = [
            models.Index(fields=['platform', 'platform_user_id'], name='users_platfor_c3e4f9_idx'),
            models.Index(fields=['role'], name='users_role_7f85d1_idx'),
            models.Index(fields=['created_at'], name='users_created_d5e9f8_idx'),
        ]
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.platform}:{self.platform_user_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def role_display(self):
        return dict(self.Role.choices).get(self.role, self.role)

    def update_balance(self, amount):
        """Update user balance (positive for credit, negative for debit)"""
        self.balance += amount
        self.save(update_fields=['balance', 'updated_at'])
        return self.balance


class UserSession(models.Model):
    """User session for tracking dialog states"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    dialog_type = models.CharField(max_length=50, blank=True)
    dialog_state = models.CharField(max_length=50, blank=True)
    dialog_data = models.JSONField(default=dict)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_sessions'
        indexes = [
            models.Index(fields=['user', 'dialog_type'], name='user_sessio_user_id_1a2b3c_idx'),
        ]

    def __str__(self):
        return f"Session for {self.user} - {self.dialog_type}"
