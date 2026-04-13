"""
Models for ML Analytics app.
Stores training runs, model metadata, and prediction logs.
"""

from django.db import models
from procurements.models import Procurement


class MLModel(models.Model):
    """Stores metadata about trained plexe models."""

    class ModelType(models.TextChoices):
        SUCCESS_PREDICTION = "success_prediction", "Procurement Success Prediction"
        DEMAND_FORECAST = "demand_forecast", "Demand Forecast"
        PRICE_OPTIMIZATION = "price_optimization", "Price Optimization"

    class Status(models.TextChoices):
        TRAINING = "training", "Training"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    name = models.CharField(max_length=200)
    model_type = models.CharField(max_length=50, choices=ModelType.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TRAINING
    )
    intent = models.TextField(help_text="Natural language description used with plexe")
    performance = models.FloatField(
        null=True, blank=True, help_text="Model performance score"
    )
    artifact_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to the saved plexe model artifacts",
    )
    training_metadata = models.JSONField(
        default=dict, help_text="Extra info from plexe training run"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ml_models"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.model_type}) - {self.status}"


class ProcurementPrediction(models.Model):
    """Prediction result for a specific procurement."""

    procurement = models.ForeignKey(
        Procurement,
        on_delete=models.CASCADE,
        related_name="ml_predictions",
    )
    ml_model = models.ForeignKey(
        MLModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="predictions",
    )
    prediction_type = models.CharField(max_length=50)
    # success_probability or predicted_demand or suggested_price_per_unit
    predicted_value = models.FloatField()
    confidence = models.FloatField(null=True, blank=True)
    input_features = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "procurement_predictions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.prediction_type} for {self.procurement.title}: {self.predicted_value:.3f}"
