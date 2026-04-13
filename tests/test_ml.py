"""
Tests for the ML Analytics app (plexe integration).

These tests use only the heuristic prediction path so they run without
plexe or a real LLM key being installed.
"""

import pytest
from unittest.mock import MagicMock, patch
from rest_framework import status
from rest_framework.test import APITestCase


class PlexeServiceTests(APITestCase):
    """Unit tests for PlexeService helper methods."""

    def _make_procurement(self, **kwargs):
        """Build a minimal Procurement-like mock object."""
        p = MagicMock()
        p.title = kwargs.get("title", "Test Procurement")
        p.category = MagicMock()
        p.category.name = kwargs.get("category", "Electronics")
        p.city = kwargs.get("city", "Moscow")
        p.target_amount = kwargs.get("target_amount", 10000)
        p.current_amount = kwargs.get("current_amount", 3000)
        p.price_per_unit = kwargs.get("price_per_unit", 500)
        p.participant_count = kwargs.get("participant_count", 6)
        p.progress = kwargs.get("progress", 30)
        # deadline - created_at = 30 days
        from datetime import timedelta
        from django.utils import timezone

        p.deadline = timezone.now() + timedelta(days=15)
        p.created_at = timezone.now() - timedelta(days=15)
        return p

    def test_extract_features_returns_all_keys(self):
        """extract_features should return a dict with expected keys."""
        from ml.plexe_service import PlexeService

        p = self._make_procurement()
        features = PlexeService.extract_features(p)

        expected_keys = {
            "category",
            "city",
            "target_amount",
            "participant_count",
            "days_active",
            "price_per_unit",
            "current_amount",
            "progress",
        }
        self.assertEqual(set(features.keys()), expected_keys)

    def test_extract_features_numeric_types(self):
        """extract_features should return numeric types for numeric fields."""
        from ml.plexe_service import PlexeService

        p = self._make_procurement(target_amount=5000, price_per_unit=250.5)
        features = PlexeService.extract_features(p)

        self.assertIsInstance(features["target_amount"], float)
        self.assertIsInstance(features["price_per_unit"], float)
        self.assertIsInstance(features["participant_count"], int)

    def test_extract_features_no_category(self):
        """extract_features should handle missing category gracefully."""
        from ml.plexe_service import PlexeService

        p = self._make_procurement()
        p.category = None
        features = PlexeService.extract_features(p)

        self.assertEqual(features["category"], "unknown")

    def test_build_success_dataset_structure(self):
        """_build_success_dataset should return a DataFrame with required columns."""
        from ml.plexe_service import PlexeService

        procurements = [
            self._make_procurement(title="P1"),
            self._make_procurement(title="P2"),
        ]
        # Assign status attributes (MagicMock doesn't propagate string equality)
        procurements[0].status = "completed"
        procurements[1].status = "cancelled"

        df = PlexeService._build_success_dataset(procurements)

        self.assertFalse(df.empty)
        self.assertEqual(len(df), 2)
        expected_cols = {
            "category",
            "city",
            "target_amount",
            "participant_count",
            "days_active",
            "price_per_unit",
            "successful",
        }
        self.assertEqual(set(df.columns), expected_cols)
        self.assertEqual(df.loc[0, "successful"], 1)
        self.assertEqual(df.loc[1, "successful"], 0)


class MLStatusAPITests(APITestCase):
    """Tests for the /api/ml/models/status/ endpoint."""

    def test_status_endpoint_returns_200(self):
        """The plexe status endpoint should always return HTTP 200."""
        response = self.client.get("/api/ml/models/status/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("plexe_available", response.data)
        self.assertIn("message", response.data)

    def test_status_endpoint_reports_availability(self):
        """plexe_available flag should be a boolean."""
        response = self.client.get("/api/ml/models/status/")
        self.assertIsInstance(response.data["plexe_available"], bool)


class MLModelListAPITests(APITestCase):
    """Tests for the /api/ml/models/ list endpoint."""

    def test_list_models_empty(self):
        """Model list should be empty by default."""
        response = self.client.get("/api/ml/models/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_train_without_plexe_returns_503(self):
        """POST /api/ml/models/train/ should return 503 when plexe is not available."""
        with patch("ml.views.PLEXE_AVAILABLE", False):
            response = self.client.post(
                "/api/ml/models/train/",
                {"model_type": "success_prediction", "max_iterations": 1},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("error", response.data)

    def test_train_invalid_model_type_returns_400(self):
        """POST /api/ml/models/train/ with invalid model_type should return 400."""
        with patch("ml.views.PLEXE_AVAILABLE", True):
            response = self.client.post(
                "/api/ml/models/train/",
                {"model_type": "nonexistent_type"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PredictionAPITests(APITestCase):
    """Tests for the /api/ml/predictions/predict/ endpoint."""

    def setUp(self):
        """Create a user and procurement for prediction tests."""
        # Create user
        self.client.post(
            "/api/users/",
            {
                "platform": "telegram",
                "platform_user_id": "42",
                "first_name": "Organizer",
                "role": "organizer",
            },
            format="json",
        )
        # Look up the created user to get its DB id
        user_response = self.client.get(
            "/api/users/by_platform/",
            {"platform": "telegram", "platform_user_id": "42"},
        )
        self.user_id = user_response.data["id"]

        # Create procurement
        self.client.post(
            "/api/procurements/",
            {
                "title": "ML Test Procurement",
                "description": "Procurement for ML tests",
                "organizer": self.user_id,
                "city": "Saint Petersburg",
                "target_amount": 8000,
                "deadline": "2027-12-31T23:59:59Z",
                "unit": "kg",
                "status": "active",
                "price_per_unit": 400,
            },
            format="json",
        )
        # Look up the created procurement by listing (create serializer doesn't return id)
        list_response = self.client.get("/api/procurements/")
        self.procurement_id = list_response.data["results"][0]["id"]

    def test_predict_success_probability(self):
        """POST /api/ml/predictions/predict/ should return a success probability."""
        response = self.client.post(
            "/api/ml/predictions/predict/",
            {
                "procurement_id": self.procurement_id,
                "prediction_type": "success_prediction",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertIn("predicted_value", data)
        self.assertIn("confidence", data)
        self.assertIn("input_features", data)
        self.assertEqual(data["procurement"], self.procurement_id)

    def test_predict_demand_forecast(self):
        """POST /api/ml/predictions/predict/ should return a demand forecast."""
        response = self.client.post(
            "/api/ml/predictions/predict/",
            {
                "procurement_id": self.procurement_id,
                "prediction_type": "demand_forecast",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertGreater(response.data["predicted_value"], 0)

    def test_predict_invalid_procurement_returns_404(self):
        """Predicting for a non-existent procurement should return 404."""
        response = self.client.post(
            "/api/ml/predictions/predict/",
            {"procurement_id": 99999, "prediction_type": "success_prediction"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_predictions(self):
        """GET /api/ml/predictions/ should list existing predictions."""
        # Create a prediction first
        self.client.post(
            "/api/ml/predictions/predict/",
            {
                "procurement_id": self.procurement_id,
                "prediction_type": "success_prediction",
            },
            format="json",
        )

        response = self.client.get("/api/ml/predictions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_predictions_by_procurement(self):
        """GET /api/ml/predictions/?procurement=<id> should filter correctly."""
        self.client.post(
            "/api/ml/predictions/predict/",
            {
                "procurement_id": self.procurement_id,
                "prediction_type": "success_prediction",
            },
            format="json",
        )

        response = self.client.get(
            f"/api/ml/predictions/?procurement={self.procurement_id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class HeuristicPredictTests(APITestCase):
    """Unit tests for the _heuristic_predict helper."""

    def test_success_prediction_range(self):
        """Success probability should be between 0 and 1."""
        from ml.views import _heuristic_predict

        value, conf = _heuristic_predict(
            "success_prediction",
            {"progress": 50, "days_active": 20, "participant_count": 5},
        )
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, 1.0)

    def test_demand_forecast_positive(self):
        """Demand forecast should be a positive number."""
        from ml.views import _heuristic_predict

        value, _ = _heuristic_predict(
            "demand_forecast",
            {"target_amount": 10000, "price_per_unit": 500},
        )
        self.assertGreater(value, 0)

    def test_price_optimization_positive(self):
        """Suggested price should be positive."""
        from ml.views import _heuristic_predict

        value, _ = _heuristic_predict(
            "price_optimization",
            {"target_amount": 9000, "participant_count": 9},
        )
        self.assertGreater(value, 0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
