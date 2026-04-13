"""
Migration: 0004_supplierdocumentjob
Adds the SupplierDocumentJob model for tracked document export to suppliers.
"""
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('procurements', '0003_votecloserequest'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupplierDocumentJob',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_type', models.CharField(default='receipt_table', max_length=50)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('processing', 'Processing'),
                        ('sent', 'Sent'),
                        ('failed_retry', 'Failed – will retry'),
                        ('fatal_error', 'Fatal error – no retry'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20,
                )),
                ('idempotency_key', models.CharField(max_length=255)),
                ('retry_count', models.PositiveSmallIntegerField(default=0)),
                ('max_retries', models.PositiveSmallIntegerField(default=3)),
                ('supplier_api_url', models.TextField(blank=True, default='')),
                ('request_payload', models.JSONField(default=dict)),
                ('response_payload', models.JSONField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True, default='')),
                ('last_attempt_at', models.DateTimeField(blank=True, null=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('procurement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='supplier_document_jobs',
                    to='procurements.procurement',
                )),
                ('organizer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='initiated_supplier_jobs',
                    to='users.user',
                )),
            ],
            options={
                'db_table': 'supplier_document_jobs',
                'indexes': [
                    models.Index(fields=['status'], name='sdj_status_idx'),
                    models.Index(fields=['procurement'], name='sdj_procurement_idx'),
                ],
                'unique_together': {('procurement', 'job_type', 'idempotency_key')},
            },
        ),
    ]
