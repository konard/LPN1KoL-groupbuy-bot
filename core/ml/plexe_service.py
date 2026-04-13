"""
Plexe integration service for GroupBuy Bot.

Uses plexe (https://github.com/plexe-ai/plexe) to build ML models from
natural language descriptions of procurement analytics tasks.

Example usage:
    from ml.plexe_service import PlexeService

    service = PlexeService()
    result = service.train_success_model(work_dir="./workdir/success_model")
    prediction = service.predict_success(procurement)
"""

import logging
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Plexe is an optional dependency; the app still runs without it.
try:
    import pandas as pd
    import plexe  # noqa: F401 — imported for availability check

    PLEXE_AVAILABLE = True
except ImportError:
    PLEXE_AVAILABLE = False
    logger.warning(
        "plexe is not installed. ML analytics features will be unavailable. "
        "Install it with: pip install plexe"
    )


def _require_plexe() -> None:
    if not PLEXE_AVAILABLE:
        raise RuntimeError("plexe is not installed. Install it with: pip install plexe")


class PlexeService:
    """
    Service that wraps the plexe library for procurement analytics.

    Three analytics modes are supported:

    1. **Success prediction** – predicts whether a procurement will reach its
       target amount given its current state.
    2. **Demand forecasting** – estimates total demand (in units) for new
       procurements based on category and city.
    3. **Price optimisation** – suggests an optimal price-per-unit that
       maximises participation while covering the target amount.
    """

    # -------------------------------------------------------------------
    # Training
    # -------------------------------------------------------------------

    def train_success_model(
        self,
        procurements_qs=None,
        work_dir: str | None = None,
        max_iterations: int = 3,
    ) -> dict[str, Any]:
        """
        Train a procurement success prediction model using plexe.

        Args:
            procurements_qs: Django queryset of Procurement objects used as
                training data.  When *None* all procurements in terminal
                states (completed / cancelled) are used.
            work_dir: Directory where plexe stores artifacts.  A temporary
                directory is used when not provided.
            max_iterations: Number of plexe search iterations.

        Returns:
            dict with keys ``performance``, ``artifact_path``, and
            ``metadata``.
        """
        _require_plexe()
        from plexe.main import main as plexe_main  # local import to keep startup fast

        if procurements_qs is None:
            from procurements.models import Procurement

            procurements_qs = Procurement.objects.filter(
                status__in=["completed", "cancelled"]
            )

        df = self._build_success_dataset(procurements_qs)
        if df.empty:
            raise ValueError(
                "Not enough training data. Need completed/cancelled procurements."
            )

        tmp_dir = tempfile.mkdtemp(prefix="plexe_success_")
        artifact_dir = Path(work_dir or tmp_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        dataset_path = artifact_dir / "success_dataset.parquet"
        df.to_parquet(dataset_path, index=False)

        logger.info("Starting plexe training for success prediction …")
        best_solution, metrics, _ = plexe_main(
            intent=(
                "Predict whether a group procurement will be successful "
                "(reach its target amount) based on category, city, target_amount, "
                "participant_count, days_active, and price_per_unit."
            ),
            data_refs=[str(dataset_path)],
            max_iterations=max_iterations,
            work_dir=artifact_dir,
        )

        performance = best_solution.performance if best_solution else 0.0
        logger.info("plexe training complete. Performance: %.4f", performance)

        return {
            "performance": performance,
            "artifact_path": str(artifact_dir),
            "metadata": {"metrics": metrics, "dataset_rows": len(df)},
        }

    def train_demand_forecast_model(
        self,
        procurements_qs=None,
        work_dir: str | None = None,
        max_iterations: int = 3,
    ) -> dict[str, Any]:
        """Train a demand forecast model using plexe."""
        _require_plexe()
        from plexe.main import main as plexe_main

        if procurements_qs is None:
            from procurements.models import Procurement

            procurements_qs = Procurement.objects.filter(status="completed")

        df = self._build_demand_dataset(procurements_qs)
        if df.empty:
            raise ValueError("Not enough training data. Need completed procurements.")

        tmp_dir = tempfile.mkdtemp(prefix="plexe_demand_")
        artifact_dir = Path(work_dir or tmp_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        dataset_path = artifact_dir / "demand_dataset.parquet"
        df.to_parquet(dataset_path, index=False)

        logger.info("Starting plexe training for demand forecasting …")
        best_solution, metrics, _ = plexe_main(
            intent=(
                "Predict the total number of participants that will join a procurement "
                "based on category, city, target_amount, and price_per_unit."
            ),
            data_refs=[str(dataset_path)],
            max_iterations=max_iterations,
            work_dir=artifact_dir,
        )

        performance = best_solution.performance if best_solution else 0.0
        logger.info("plexe training complete. Performance: %.4f", performance)

        return {
            "performance": performance,
            "artifact_path": str(artifact_dir),
            "metadata": {"metrics": metrics, "dataset_rows": len(df)},
        }

    # -------------------------------------------------------------------
    # Feature extraction helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _build_success_dataset(procurements_qs) -> "pd.DataFrame":
        """Build a pandas DataFrame for success prediction training."""
        import pandas as pd

        rows = []
        for p in procurements_qs:
            rows.append(
                {
                    "category": p.category.name if p.category else "unknown",
                    "city": p.city or "unknown",
                    "target_amount": float(p.target_amount),
                    "participant_count": p.participant_count,
                    "days_active": max(
                        0,
                        (p.deadline - p.created_at).days,
                    ),
                    "price_per_unit": float(p.price_per_unit)
                    if p.price_per_unit
                    else 0.0,
                    "successful": 1 if p.status == "completed" else 0,
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _build_demand_dataset(procurements_qs) -> "pd.DataFrame":
        """Build a pandas DataFrame for demand forecast training."""
        import pandas as pd

        rows = []
        for p in procurements_qs:
            rows.append(
                {
                    "category": p.category.name if p.category else "unknown",
                    "city": p.city or "unknown",
                    "target_amount": float(p.target_amount),
                    "price_per_unit": float(p.price_per_unit)
                    if p.price_per_unit
                    else 0.0,
                    "participant_count": p.participant_count,
                }
            )
        return pd.DataFrame(rows)

    # -------------------------------------------------------------------
    # Feature extraction for a single procurement
    # -------------------------------------------------------------------

    @staticmethod
    def extract_features(procurement) -> dict[str, Any]:
        """Extract prediction features from a Procurement instance."""
        return {
            "category": procurement.category.name
            if procurement.category
            else "unknown",
            "city": procurement.city or "unknown",
            "target_amount": float(procurement.target_amount),
            "participant_count": procurement.participant_count,
            "days_active": max(
                0,
                (procurement.deadline - procurement.created_at).days,
            ),
            "price_per_unit": (
                float(procurement.price_per_unit) if procurement.price_per_unit else 0.0
            ),
            "current_amount": float(procurement.current_amount),
            "progress": procurement.progress,
        }
