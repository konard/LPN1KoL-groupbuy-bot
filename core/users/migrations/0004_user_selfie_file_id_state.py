# Migration: record selfie_file_id in Django's migration state.
#
# Migration 0003_user_selfie_file_id added the selfie_file_id column to the
# database using RunPython (idempotent SQL so it works whether or not the Rust
# core already created the column).  However, RunPython does not update
# Django's internal migration state, so makemigrations still sees selfie_file_id
# as a new field and regenerates an AddField migration on every container
# restart — exactly what triggered the ProgrammingError reported in issue #206.
#
# This migration fixes that by registering the field in Django's state via
# SeparateDatabaseAndState: the state_operations side records the AddField so
# Django stops regenerating it, while database_operations is empty because
# 0003 already performed the actual ALTER TABLE.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_user_selfie_file_id'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # The column already exists in the DB from migration 0003; nothing
            # to do at the database level.
            database_operations=[],
            # Record the field in Django's migration state so makemigrations
            # does not regenerate it as a pending change.
            state_operations=[
                migrations.AddField(
                    model_name='user',
                    name='selfie_file_id',
                    field=models.CharField(blank=True, default='', max_length=255),
                    preserve_default=False,
                ),
            ],
        ),
    ]
