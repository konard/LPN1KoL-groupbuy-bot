"""
Migration to add Tochka Bank support to Payment model
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add order_id field and update provider choices for Tochka Bank support"""

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='order_id',
            field=models.CharField(
                blank=True,
                help_text='Order ID for Tochka Cyclops',
                max_length=100
            ),
        ),
        migrations.AlterField(
            model_name='payment',
            name='provider',
            field=models.CharField(
                choices=[
                    ('tochka', 'Tochka Bank (Cyclops)'),
                    ('yookassa', 'YooKassa (Legacy)')
                ],
                default='tochka',
                max_length=50
            ),
        ),
    ]
