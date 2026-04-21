"""ML module base interface for TokenLens.

All ML modules (forecaster, anomaly detector, efficiency engine, profiler)
implement this ABC for consistent training, prediction, and persistence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path  # noqa: TC003
from typing import Any


def _check_ml_deps() -> None:
    """Verify that optional [ml] dependencies are installed."""
    try:
        import pandas  # noqa: F401
        import sklearn  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Install tokenlens[ml] for ML features: "
            "pip install 'tokenlens[ml]' or uv pip install 'tokenlens[ml]'"
        ) from exc


# Perform the check at import time so callers get a clear error early.
_check_ml_deps()

import pandas as pd  # noqa: E402, TC002


class MLModule(ABC):
    """Base class for all ML modules."""

    @abstractmethod
    def train(self, data: pd.DataFrame) -> Any:
        """Train the model on historical data. Returns the trained model object."""
        ...

    @abstractmethod
    def predict(self, model: Any, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate predictions from a trained model."""
        ...

    @abstractmethod
    def evaluate(self, model: Any, test_data: pd.DataFrame) -> dict[str, float]:
        """Evaluate model performance. Returns metric dict (e.g., MAE, RMSE)."""
        ...

    @abstractmethod
    def save(self, model: Any, path: Path) -> None:
        """Persist trained model to disk (joblib)."""
        ...

    @abstractmethod
    def load(self, path: Path) -> Any:
        """Load a trained model from disk."""
        ...
