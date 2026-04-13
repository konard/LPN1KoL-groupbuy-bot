# Migration for issue #116: add VoteCloseRequest model and close_vote/vote_close_status endpoints

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procurements', '0002_procurement_commission_min_quantity_suppliervote'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='VoteCloseRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('procurement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='vote_close_requests',
                    to='procurements.procurement',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='vote_close_requests',
                    to='users.user',
                )),
            ],
            options={
                'db_table': 'vote_close_requests',
                'unique_together': {('procurement', 'user')},
            },
        ),
        migrations.AddIndex(
            model_name='votecloserequest',
            index=models.Index(fields=['procurement'], name='vote_close_procure_idx'),
        ),
    ]
