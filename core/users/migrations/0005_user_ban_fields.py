"""
Migration: 0005_user_ban_fields
Adds ban-related fields to the User model:
  - is_banned: boolean flag (cached in Redis for 10 s to avoid DB hits)
  - banned_at: timestamp when the ban was applied
  - ban_reason: human-readable reason for the ban
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_user_selfie_file_id_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_banned',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='user',
            name='banned_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='ban_reason',
            field=models.TextField(blank=True, default=''),
        ),
    ]
