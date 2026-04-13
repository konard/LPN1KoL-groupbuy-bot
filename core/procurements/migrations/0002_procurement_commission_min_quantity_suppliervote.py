# Generated migration for issue #74: update procurement processes

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procurements', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        # Add commission_percent field to Procurement
        migrations.AddField(
            model_name='procurement',
            name='commission_percent',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Organizer commission percentage (1–4%)',
                max_digits=4,
            ),
        ),
        # Add min_quantity field to Procurement
        migrations.AddField(
            model_name='procurement',
            name='min_quantity',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Minimum total quantity to launch the procurement',
                max_digits=10,
                null=True,
            ),
        ),
        # Create SupplierVote model
        migrations.CreateModel(
            name='SupplierVote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('procurement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='supplier_votes',
                    to='procurements.procurement',
                )),
                ('supplier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='supplier_votes_received',
                    to='users.user',
                )),
                ('voter', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='supplier_votes_cast',
                    to='users.user',
                )),
            ],
            options={
                'db_table': 'supplier_votes',
                'unique_together': {('procurement', 'voter')},
            },
        ),
        migrations.AddIndex(
            model_name='suppliervote',
            index=models.Index(fields=['procurement', 'supplier'], name='supplier_vo_procure_idx'),
        ),
    ]
