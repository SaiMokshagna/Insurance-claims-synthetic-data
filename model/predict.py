"""Prediction module – load a trained model and classify claims.

Mirrors the interface of :func:`generator.detect.detect` but uses the
trained ML model instead of hand-crafted rules.

Usage::

    from model.predict import load_model, predict

    model, label_encoder = load_model()
    predictions = predict(tables, model, label_encoder)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import LabelEncoder

from model.features import extract_features

logger = logging.getLogger(__name__)

# Default artefact locations (sibling to this file).
_MODEL_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = _MODEL_DIR / "trained_model.joblib"
DEFAULT_ENCODER_PATH = _MODEL_DIR / "label_encoder.joblib"


def load_model(
    model_path: str | Path = DEFAULT_MODEL_PATH,
    encoder_path: str | Path = DEFAULT_ENCODER_PATH,
) -> tuple[BaseEstimator, LabelEncoder]:
    """Deserialise the trained model and its label encoder.

    Parameters
    ----------
    model_path : str | Path
        Path to the joblib-serialised classifier.
    encoder_path : str | Path
        Path to the joblib-serialised :class:`LabelEncoder`.

    Returns
    -------
    tuple[BaseEstimator, LabelEncoder]
        The fitted model and the label encoder used during training.

    Raises
    ------
    FileNotFoundError
        If either artefact file is missing.
    """
    model_path = Path(model_path)
    encoder_path = Path(encoder_path)

    if not model_path.exists():
        raise FileNotFoundError(
            f"Trained model not found at {model_path}.  "
            "Run `python -m model.train` first."
        )
    if not encoder_path.exists():
        raise FileNotFoundError(
            f"Label encoder not found at {encoder_path}.  "
            "Run `python -m model.train` first."
        )

    model: BaseEstimator = joblib.load(model_path)
    label_encoder: LabelEncoder = joblib.load(encoder_path)
    logger.info(
        "Loaded model from %s  (%d classes)",
        model_path,
        len(label_encoder.classes_),
    )
    return model, label_encoder


def predict(
    tables: dict[str, pd.DataFrame],
    model: BaseEstimator,
    label_encoder: LabelEncoder,
) -> pd.DataFrame:
    """Predict the issue type for every claim in *tables*.

    The returned DataFrame has the same shape and semantics as
    :func:`generator.detect.detect`: two columns ``claim_id`` and
    ``predicted_issue``.

    Parameters
    ----------
    tables : dict[str, pd.DataFrame]
        The full set of dataset tables (same format as
        :func:`generator.pipeline.build_dataset` output).
    model : BaseEstimator
        A fitted scikit-learn classifier.
    label_encoder : LabelEncoder
        The encoder that maps integer labels back to issue-type strings.

    Returns
    -------
    pd.DataFrame
        Columns: ``claim_id``, ``predicted_issue``.
    """
    X = extract_features(tables)
    logger.info("Predicting on %d claims …", len(X))

    y_pred_encoded = model.predict(X)
    y_pred_labels = label_encoder.inverse_transform(y_pred_encoded)

    result = pd.DataFrame({
        "claim_id": X.index,
        "predicted_issue": y_pred_labels,
    }).reset_index(drop=True)

    logger.info(
        "Prediction distribution:\n%s",
        result["predicted_issue"].value_counts().to_string(),
    )
    return result


def main() -> None:
    """Quick smoke-test: load model, generate data, predict, print summary."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-28s  %(levelname)-8s  %(message)s",
    )
    from generator.config import DEFAULT_CLAIMS, DEFAULT_POLICIES, DEFAULT_SEED
    from generator.pipeline import build_dataset

    logger.info("Building dataset for prediction demo …")
    _clean, final, _gt = build_dataset(DEFAULT_SEED, DEFAULT_POLICIES, DEFAULT_CLAIMS)

    model, le = load_model()
    preds = predict(final, model, le)

    print("\n===  ML Predictions  ===")
    print(preds["predicted_issue"].value_counts().to_string())
    print(f"\nTotal claims: {len(preds)}")


if __name__ == "__main__":
    main()
