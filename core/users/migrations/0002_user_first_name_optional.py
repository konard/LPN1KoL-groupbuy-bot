# Migration: make first_name optional so users control what personal data they share.
# The name is taken from the messenger profile automatically; users are not forced
# to provide it during registration.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='first_name',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
