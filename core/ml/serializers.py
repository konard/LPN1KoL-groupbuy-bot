"""
Serializers for the ML Analytics API.
"""

from rest_framework import serializers

from .models import MLModel, ProcurementPrediction


class MLModelSerializer(serializers.ModelSerializer):
    """Serializer for MLModel instances."""

    class Meta:
        model = MLModel
        fields = [
            "id",
            "name",
            "model_type",
            "status",
            "intent",
            "performance",
            "artifact_path",
            "training_metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProcurementPredictionSerializer(serializers.ModelSerializer):
    """Serializer for ProcurementPrediction instances."""

    procurement_title = serializers.CharField(
        source="procurement.title", read_only=True
    )

    class Meta:
        model = ProcurementPrediction
        fields = [
            "id",
            "procurement",
            "procurement_title",
            "ml_model",
            "prediction_type",
            "predicted_value",
            "confidence",
            "input_features",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TrainModelSerializer(serializers.Serializer):
    """Input serializer for the train-model action."""

    model_type = serializers.ChoiceField(
        choices=MLModel.ModelType.choices,
        help_text="Type of model to train.",
    )
    max_iterations = serializers.IntegerField(
        default=3,
        min_value=1,
        max_value=20,
        help_text="Number of plexe search iterations.",
    )
    work_dir = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Directory for plexe artifacts (optional).",
    )


class PredictSerializer(serializers.Serializer):
    """Input serializer for the predict action."""

    procurement_id = serializers.IntegerField(
        help_text="ID of the procurement to predict for."
    )
    prediction_type = serializers.ChoiceField(
        choices=MLModel.ModelType.choices,
        default=MLModel.ModelType.SUCCESS_PREDICTION,
    )
