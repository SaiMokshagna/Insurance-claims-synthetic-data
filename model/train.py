"""Train an ML classifier to predict claim issue_type.

Builds the synthetic dataset, extracts features, trains a
``RandomForestClassifier`` via scikit-learn, evaluates against a
stratified hold-out set, and persists the fitted artefacts to disk.

Run as::

    python -m model.train
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from generator.config import DEFAULT_CLAIMS, DEFAULT_POLICIES, DEFAULT_SEED
from generator.detect import detect, score_detection
from generator.pipeline import build_dataset
from model.features import extract_features

logger = logging.getLogger(__name__)

# Paths for persisted artefacts (relative to project root).
MODEL_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = MODEL_DIR / "trained_model.joblib"
DEFAULT_ENCODER_PATH = MODEL_DIR / "label_encoder.joblib"


def _build_label_series(
    ground_truth: pd.DataFrame,
    feature_index: pd.Index,
) -> pd.Series:
    """Align ground-truth issue_type to the feature matrix index.

    Parameters
    ----------
    ground_truth : pd.DataFrame
        Must contain ``claim_id`` and ``issue_type`` columns.
    feature_index : pd.Index
        The ``claim_id`` index of the feature matrix.

    Returns
    -------
    pd.Series
        ``issue_type`` values aligned to *feature_index*.
    """
    gt = ground_truth.drop_duplicates(subset="claim_id").set_index("claim_id")
    labels = gt["issue_type"].reindex(feature_index)
    # If a claim is missing from ground truth, label it as NONE.
    labels = labels.fillna("NONE")
    return labels


def train(
    seed: int = DEFAULT_SEED,
    n_policies: int = DEFAULT_POLICIES,
    n_claims: int = DEFAULT_CLAIMS,
    model_path: Path = DEFAULT_MODEL_PATH,
    encoder_path: Path = DEFAULT_ENCODER_PATH,
) -> None:
    """End-to-end training pipeline.

    Parameters
    ----------
    seed : int
        Random seed for dataset generation and train/test split.
    n_policies, n_claims : int
        Size parameters forwarded to :func:`build_dataset`.
    model_path : Path
        Destination for the serialised model (joblib).
    encoder_path : Path
        Destination for the serialised label encoder (joblib).
    """
    # ---------------------------------------------------------------- data
    logger.info(
        "Building dataset  (seed=%d, policies=%d, claims=%d) …",
        seed, n_policies, n_claims,
    )
    _clean, final, ground_truth = build_dataset(seed, n_policies, n_claims)

    logger.info("Extracting features …")
    X = extract_features(final)

    y_raw = _build_label_series(ground_truth, X.index)
    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    logger.info(
        "Label distribution:\n%s",
        pd.Series(y_raw.values).value_counts().to_string(),
    )

    # ---------------------------------------------------------- split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.20,
        random_state=seed,
        stratify=y,
    )
    logger.info(
        "Train size: %d | Test size: %d", len(X_train), len(X_test),
    )

    # ---------------------------------------------------------- model
    clf = RandomForestClassifier(
        n_estimators=150,
        max_depth=15,
        min_samples_split=4,
        min_samples_leaf=1,
        class_weight="balanced",
        random_state=seed,
        n_jobs=-1,
    )
    logger.info("Training RandomForestClassifier …")
    clf.fit(X_train, y_train)

    # ---------------------------------------------------------- evaluate
    y_pred = clf.predict(X_test)
    target_names = list(le.classes_)

    report = classification_report(
        y_test, y_pred, target_names=target_names, zero_division=0,
    )
    print("\n===  ML Model – Classification Report (test set)  ===")
    print(report)

    ml_f1_macro = f1_score(y_test, y_pred, average="macro", zero_division=0)
    ml_f1_weighted = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    # --------------------------------------------- rules-based comparison
    print("===  Rules-Based Detector  ===")
    rules_preds = detect(final)
    rules_scores, _ = score_detection(ground_truth, rules_preds)
    rules_f1_values = rules_scores["f1"].dropna()
    rules_f1_macro = float(rules_f1_values.mean()) if len(rules_f1_values) else 0.0

    print(
        rules_scores[
            ["issue_type", "support", "tp", "fp", "fn", "precision", "recall", "f1"]
        ]
        .round(3)
        .to_string(index=False)
    )

    print("\n===  Comparison  ===")
    print(f"  Rules-based detector  –  macro-F1: {rules_f1_macro:.4f}")
    print(f"  ML model (test set)   –  macro-F1: {ml_f1_macro:.4f}")
    print(f"  ML model (test set)   –  weighted-F1: {ml_f1_weighted:.4f}")

    # ---------------------------------------------------------- persist
    joblib.dump(clf, model_path)
    joblib.dump(le, encoder_path)
    logger.info("Model saved to %s", model_path)
    logger.info("Label encoder saved to %s", encoder_path)
    print(f"\nArtefacts written to:\n  {model_path}\n  {encoder_path}")


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-28s  %(levelname)-8s  %(message)s",
    )
    train()


if __name__ == "__main__":
    main()
