"""
Procurement models for GroupBuy Bot
Supports group purchases with organizers, participants, and suppliers
"""
from django.db import models
from django.utils import timezone
from users.models import User


class Category(models.Model):
    """Product category for procurements"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='children'
    )
    icon = models.CharField(max_length=50, blank=True, help_text='Emoji or icon name')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'categories'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Procurement(models.Model):
    """Main procurement model"""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        STOPPED = 'stopped', 'Stopped'
        PAYMENT = 'payment', 'Payment in Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    # Basic info
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='procurements')

    # Organizer and supplier
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_procurements')
    supplier = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='supplied_procurements'
    )

    # Location
    city = models.CharField(max_length=100)
    delivery_address = models.TextField(blank=True)

    # Financial
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    current_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stop_at_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Stop accepting when this amount is reached'
    )
    unit = models.CharField(max_length=20, default='units', help_text='e.g., kg, pieces, liters')
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    commission_percent = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text='Organizer commission percentage (1–4%)'
    )
    min_quantity = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Minimum total quantity to launch the procurement'
    )

    # Status and timing
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    deadline = models.DateTimeField()
    payment_deadline = models.DateTimeField(null=True, blank=True)

    # Metadata
    image_url = models.URLField(blank=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'procurements'
        indexes = [
            models.Index(fields=['status'], name='procurement_status_a1b2c3_idx'),
            models.Index(fields=['organizer'], name='procurement_organiz_d4e5f6_idx'),
            models.Index(fields=['category'], name='procurement_categor_g7h8i9_idx'),
            models.Index(fields=['city'], name='procurement_city_j0k1l2_idx'),
            models.Index(fields=['deadline'], name='procurement_deadlin_m3n4o5_idx'),
            models.Index(fields=['created_at'], name='procurement_created_p6q7r8_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.status})"

    @property
    def progress(self):
        """Calculate progress percentage"""
        if self.target_amount == 0:
            return 0
        return min(100, int((self.current_amount / self.target_amount) * 100))

    @property
    def participant_count(self):
        """Get number of participants"""
        return self.participants.count()

    @property
    def days_left(self):
        """Calculate days until deadline"""
        delta = self.deadline - timezone.now()
        return max(0, delta.days)

    @property
    def status_display(self):
        return dict(self.Status.choices).get(self.status, self.status)

    @property
    def can_join(self):
        """Check if new participants can join"""
        if self.status != self.Status.ACTIVE:
            return False
        if self.deadline < timezone.now():
            return False
        if self.stop_at_amount and self.current_amount >= self.stop_at_amount:
            return False
        return True

    def update_current_amount(self):
        """Recalculate current amount from participants"""
        total = self.participants.filter(is_active=True).aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        self.current_amount = total
        self.save(update_fields=['current_amount', 'updated_at'])

        # Check if stop amount is reached
        if self.stop_at_amount and self.current_amount >= self.stop_at_amount:
            self.status = self.Status.STOPPED
            self.save(update_fields=['status', 'updated_at'])


class Participant(models.Model):
    """Participant in a procurement"""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        PAID = 'paid', 'Paid'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'

    procurement = models.ForeignKey(Procurement, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='participations')

    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    notes = models.TextField(blank=True, help_text='Special requests or notes')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'participants'
        unique_together = ['procurement', 'user']
        indexes = [
            models.Index(fields=['procurement', 'status'], name='participant_procure_s9t0u1_idx'),
            models.Index(fields=['user'], name='participant_user_id_v2w3x4_idx'),
        ]

    def __str__(self):
        return f"{self.user} in {self.procurement.title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update procurement totals
        self.procurement.update_current_amount()


class SupplierVote(models.Model):
    """Participant vote for a supplier in a procurement.

    Each participant may cast exactly one vote per procurement (enforced by
    the unique_together constraint).  The winning supplier is determined by
    simple majority; ties trigger a second round.
    """

    procurement = models.ForeignKey(
        Procurement, on_delete=models.CASCADE, related_name='supplier_votes'
    )
    voter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='supplier_votes_cast'
    )
    # The supplier being voted for (a User with role='supplier')
    supplier = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='supplier_votes_received'
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'supplier_votes'
        # One vote per participant per procurement
        unique_together = ['procurement', 'voter']
        indexes = [
            models.Index(fields=['procurement', 'supplier'], name='supplier_vo_procure_idx'),
        ]

    def __str__(self):
        return f"{self.voter} voted for {self.supplier} in {self.procurement.title}"


class VoteCloseRequest(models.Model):
    """Tracks which participants have confirmed closing the supplier vote.

    The vote is considered closed when all active participants have submitted
    a close request for the procurement.
    """

    procurement = models.ForeignKey(
        Procurement, on_delete=models.CASCADE, related_name='vote_close_requests'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='vote_close_requests'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vote_close_requests'
        unique_together = ['procurement', 'user']
        indexes = [
            models.Index(fields=['procurement'], name='vote_close_procure_idx'),
        ]

    def __str__(self):
        return f"{self.user} requested close vote in {self.procurement.title}"


class SupplierDocumentJob(models.Model):
    """Tracks document export jobs sent to suppliers.

    Status machine: pending → processing → sent | failed_retry | fatal_error
    Idempotency: unique (procurement, job_type, idempotency_key) prevents duplicate sends.
    Full request/response payloads are stored in JSONB for audit and debugging.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        SENT = 'sent', 'Sent'
        FAILED_RETRY = 'failed_retry', 'Failed – will retry'
        FATAL_ERROR = 'fatal_error', 'Fatal error – no retry'

    procurement = models.ForeignKey(
        Procurement, on_delete=models.CASCADE, related_name='supplier_document_jobs'
    )
    organizer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='initiated_supplier_jobs'
    )
    job_type = models.CharField(max_length=50, default='receipt_table')
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    idempotency_key = models.CharField(max_length=255)
    retry_count = models.PositiveSmallIntegerField(default=0)
    max_retries = models.PositiveSmallIntegerField(default=3)
    supplier_api_url = models.TextField(blank=True, default='')
    # Full request dump (for audit / retry)
    request_payload = models.JSONField(default=dict)
    # Full response from supplier API (for audit / debugging)
    response_payload = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, default='')
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'supplier_document_jobs'
        unique_together = ['procurement', 'job_type', 'idempotency_key']
        indexes = [
            models.Index(fields=['status'], name='sdj_status_idx'),
            models.Index(fields=['procurement'], name='sdj_procurement_idx'),
        ]

    def __str__(self):
        return f"SupplierDocumentJob {self.id} [{self.status}] for {self.procurement.title}"
