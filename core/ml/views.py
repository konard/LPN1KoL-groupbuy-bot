"""
Views for ML Analytics API.

Provides endpoints for training plexe models and retrieving predictions.
"""

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from procurements.models import Procurement

from .models import MLModel, ProcurementPrediction
from .plexe_service import PLEXE_AVAILABLE, PlexeService
from .serializers import (
    MLModelSerializer,
    PredictSerializer,
    ProcurementPredictionSerializer,
    TrainModelSerializer,
)

logger = logging.getLogger(__name__)


class MLModelViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving trained ML models.

    Endpoints:
    - GET  /api/ml/models/               – list all models
    - GET  /api/ml/models/{id}/          – retrieve a single model
    - POST /api/ml/models/train/         – trigger plexe training
    - GET  /api/ml/models/status/        – plexe availability check
    """

    queryset = MLModel.objects.all()
    serializer_class = MLModelSerializer

    @action(detail=False, methods=["get"], url_path="status")
    def plexe_status(self, request):
        """Check whether plexe is installed and available."""
        return Response(
            {
                "plexe_available": PLEXE_AVAILABLE,
                "message": (
                    "plexe is installed and ready."
                    if PLEXE_AVAILABLE
                    else "plexe is not installed. Run: pip install plexe"
                ),
            }
        )

    @action(detail=False, methods=["post"], url_path="train")
    def train(self, request):
        """
        Trigger plexe model training.

        Requires plexe to be installed and an LLM API key to be configured
        (OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable).

        Request body:
            model_type (str): One of 'success_prediction', 'demand_forecast'.
            max_iterations (int): Number of plexe search iterations (default 3).
            work_dir (str, optional): Path for storing model artifacts.
        """
        if not PLEXE_AVAILABLE:
            return Response(
                {
                    "error": "plexe is not installed.",
                    "hint": "pip install plexe",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = TrainModelSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        model_type = serializer.validated_data["model_type"]
        max_iterations = serializer.validated_data["max_iterations"]
        work_dir = serializer.validated_data.get("work_dir") or None

        # Create a DB record so callers can track the run.
        ml_model = MLModel.objects.create(
            name=f"plexe-{model_type}",
            model_type=model_type,
            status=MLModel.Status.TRAINING,
            intent=f"Automated plexe training for {model_type}",
        )

        try:
            service = PlexeService()
            if model_type == MLModel.ModelType.SUCCESS_PREDICTION:
                result = service.train_success_model(
                    work_dir=work_dir, max_iterations=max_iterations
                )
            elif model_type == MLModel.ModelType.DEMAND_FORECAST:
                result = service.train_demand_forecast_model(
                    work_dir=work_dir, max_iterations=max_iterations
                )
            else:
                ml_model.status = MLModel.Status.FAILED
                ml_model.save(update_fields=["status", "updated_at"])
                return Response(
                    {"error": f"Unsupported model_type: {model_type}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            ml_model.performance = result["performance"]
            ml_model.artifact_path = result["artifact_path"]
            ml_model.training_metadata = result.get("metadata", {})
            ml_model.status = MLModel.Status.READY
            ml_model.save()

            return Response(
                MLModelSerializer(ml_model).data, status=status.HTTP_201_CREATED
            )

        except Exception as exc:
            logger.exception("plexe training failed: %s", exc)
            ml_model.status = MLModel.Status.FAILED
            ml_model.training_metadata = {"error": str(exc)}
            ml_model.save(update_fields=["status", "training_metadata", "updated_at"])
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProcurementPredictionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing procurement ML predictions.

    Endpoints:
    - GET  /api/ml/predictions/          – list all predictions
    - GET  /api/ml/predictions/{id}/     – retrieve a single prediction
    - POST /api/ml/predictions/predict/  – create a rule-based prediction
    """

    queryset = ProcurementPrediction.objects.select_related("procurement", "ml_model")
    serializer_class = ProcurementPredictionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        procurement_id = self.request.query_params.get("procurement")
        if procurement_id:
            qs = qs.filter(procurement_id=procurement_id)
        return qs

    @action(detail=False, methods=["post"], url_path="predict")
    def predict(self, request):
        """
        Generate a rule-based procurement analytics prediction.

        This endpoint provides instant analytics without requiring a trained
        plexe model.  It uses heuristics derived from the procurement's
        current state:

        - **success_probability** – probability that the procurement will
          reach its funding target, derived from current progress and
          time-remaining ratios.
        - **demand_forecast** – estimated total participant count based on
          historical category averages (falls back to a simple heuristic).
        - **price_suggestion** – whether the current price-per-unit appears
          competitive given the target amount and participant count.

        Request body:
            procurement_id (int): ID of the procurement.
            prediction_type (str): Type of prediction (default: success_prediction).
        """
        serializer = PredictSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        procurement_id = serializer.validated_data["procurement_id"]
        prediction_type = serializer.validated_data["prediction_type"]

        procurement = get_object_or_404(Procurement, pk=procurement_id)
        features = PlexeService.extract_features(procurement)

        predicted_value, confidence = _heuristic_predict(prediction_type, features)

        prediction = ProcurementPrediction.objects.create(
            procurement=procurement,
            prediction_type=prediction_type,
            predicted_value=predicted_value,
            confidence=confidence,
            input_features=features,
        )

        return Response(
            ProcurementPredictionSerializer(prediction).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Heuristic fallback (no plexe model required)
# ---------------------------------------------------------------------------


def _heuristic_predict(prediction_type: str, features: dict) -> tuple[float, float]:
    """
    Return (predicted_value, confidence) using simple heuristics.

    These heuristics serve two purposes:
    1. They provide instant value without a trained ML model.
    2. They demonstrate the feature schema that plexe models will consume.
    """
    if prediction_type == MLModel.ModelType.SUCCESS_PREDICTION:
        progress = features.get("progress", 0) / 100.0
        days_active = max(1, features.get("days_active", 1))
        participant_count = features.get("participant_count", 0)

        # Simple weighted score: progress matters most, then participants.
        score = (
            0.6 * progress
            + 0.3 * min(1.0, participant_count / 10)
            + 0.1 * min(1.0, days_active / 30)
        )
        return round(min(1.0, score), 4), 0.5

    if prediction_type == MLModel.ModelType.DEMAND_FORECAST:
        target = features.get("target_amount", 1000)
        price = features.get("price_per_unit", 0) or 1
        estimated_units = target / price
        estimated_participants = max(1, int(estimated_units / 5))
        return float(estimated_participants), 0.4

    # price_optimization
    target = features.get("target_amount", 1000)
    participants = max(1, features.get("participant_count", 1))
    suggested_price = target / participants
    return round(suggested_price, 2), 0.35
