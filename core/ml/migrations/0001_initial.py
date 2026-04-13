"""
Initial migration for the ml app.
Creates MLModel and ProcurementPrediction tables.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("procurements", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MLModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                (
                    "model_type",
                    models.CharField(
                        choices=[
                            ("success_prediction", "Procurement Success Prediction"),
                            ("demand_forecast", "Demand Forecast"),
                            ("price_optimization", "Price Optimization"),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("training", "Training"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                        ],
                        default="training",
                        max_length=20,
                    ),
                ),
                (
                    "intent",
                    models.TextField(
                        help_text="Natural language description used with plexe"
                    ),
                ),
                (
                    "performance",
                    models.FloatField(
                        blank=True, null=True, help_text="Model performance score"
                    ),
                ),
                (
                    "artifact_path",
                    models.CharField(
                        blank=True,
                        help_text="Path to the saved plexe model artifacts",
                        max_length=500,
                    ),
                ),
                (
                    "training_metadata",
                    models.JSONField(
                        default=dict, help_text="Extra info from plexe training run"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "ml_models",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ProcurementPrediction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("prediction_type", models.CharField(max_length=50)),
                ("predicted_value", models.FloatField()),
                ("confidence", models.FloatField(blank=True, null=True)),
                ("input_features", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "ml_model",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="predictions",
                        to="ml.mlmodel",
                    ),
                ),
                (
                    "procurement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ml_predictions",
                        to="procurements.procurement",
                    ),
                ),
            ],
            options={
                "db_table": "procurement_predictions",
                "ordering": ["-created_at"],
            },
        ),
    ]
