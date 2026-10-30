"""Feature engineering for insurance claims anomaly detection.

Joins the 14 interrelated tables and extracts numeric / categorical features
per claim, returning a DataFrame indexed by ``claim_id`` that can be fed
straight into a scikit-learn estimator.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Canonical claim types for one-hot encoding.
CLAIM_TYPES = [
    "AUTO_COLLISION",
    "PROPERTY_DAMAGE",
    "THEFT",
    "MEDICAL",
    "LIABILITY",
]

# Ordinal encoding for customer risk tier.
RISK_TIER_MAP: dict[str, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def _safe_to_datetime(series: pd.Series) -> pd.Series:
    """Convert a column to datetime, coercing errors to NaT."""
    return pd.to_datetime(series, errors="coerce")


def _days_between(a: pd.Series, b: pd.Series) -> pd.Series:
    """Return (a - b) as fractional days, NaN where either side is NaT."""
    return (
        _safe_to_datetime(a) - _safe_to_datetime(b)
    ).dt.total_seconds() / 86_400


def extract_features(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build a feature matrix with one row per claim.

    Parameters
    ----------
    tables : dict[str, pd.DataFrame]
        The full set of dataset tables keyed by table name (e.g.
        ``"claims"``, ``"policies"``, ``"incidents"``, …).

    Returns
    -------
    pd.DataFrame
        A DataFrame indexed by ``claim_id`` containing all engineered
        features as columns.  Missing numeric values are filled with
        safe defaults (0 or NaN) documented inline.
    """
    # ------------------------------------------------------------------ base
    clm = tables["claims"].copy()
    pol = tables["policies"][
        ["policy_id", "customer_id", "effective_date", "expiry_date",
         "status", "cancellation_date", "lapse_date"]
    ].copy()
    inc = tables["incidents"][
        ["incident_id", "incident_date", "exclusion_triggered"]
    ].copy()
    pc = tables["policy_coverages"][
        ["policy_id", "coverage_id", "coverage_limit", "deductible"]
    ].copy()
    cust = tables["customers"][["customer_id", "risk_tier"]].copy()

    # Merge into one row per claim
    df = (
        clm.merge(inc, on="incident_id", how="left")
           .merge(pol, on="policy_id", how="left")
           .merge(pc, on=["policy_id", "coverage_id"], how="left")
           .merge(cust, on="customer_id", how="left")
    )
    logger.info("Base join produced %d rows for %d claims", len(df), clm["claim_id"].nunique())

    # ----------------------------------------------------------- date features
    df["days_since_policy_start"] = _days_between(
        df["incident_date"], df["effective_date"]
    )
    df["days_until_expiry"] = _days_between(
        df["expiry_date"], df["incident_date"]
    )

    # ----------------------------------------------------------- ratio features
    coverage_limit = pd.to_numeric(df["coverage_limit"], errors="coerce")
    deductible = pd.to_numeric(df["deductible"], errors="coerce")
    claimed_amount = pd.to_numeric(df["claimed_amount"], errors="coerce")

    df["amount_to_limit_ratio"] = claimed_amount / coverage_limit.replace(0, np.nan)
    df["amount_to_deductible_ratio"] = claimed_amount / deductible.replace(0, np.nan)

    # ----------------------------------------------------------- boolean flags
    df["is_cancelled"] = (df["status"] == "CANCELLED").astype(int)
    df["is_lapsed"] = (df["status"] == "LAPSED").astype(int)
    df["has_exclusion"] = df["exclusion_triggered"].notna().astype(int)

    # ----------------------------------------------------------- document stats
    docs = tables["documents"]
    doc_agg = docs.groupby("claim_id").agg(
        num_documents=("document_id", "count"),
        num_mandatory_docs=("is_mandatory", lambda s: s.astype(bool).sum()),
        num_received_docs=(
            "status",
            lambda s: s.isin(["RECEIVED", "VERIFIED"]).sum(),
        ),
        num_requested_docs=(
            "status",
            lambda s: (s == "REQUESTED").sum(),
        ),
    )
    df = df.merge(doc_agg, on="claim_id", how="left")
    for col in ["num_documents", "num_mandatory_docs", "num_received_docs",
                "num_requested_docs"]:
        df[col] = df[col].fillna(0).astype(int)

    # ----------------------------------------------------------- claim items
    items = tables["claim_items"]
    item_counts = items.groupby("claim_id").size().rename("num_claim_items")
    df = df.merge(item_counts, on="claim_id", how="left")
    df["num_claim_items"] = df["num_claim_items"].fillna(0).astype(int)

    # ----------------------------------------------------------- settlements
    stl = tables["settlements"]
    stl_agg = stl.groupby("claim_id").agg(
        num_settlements=("settlement_id", "count"),
        max_approved_amount=("approved_amount", "max"),
    )
    df = df.merge(stl_agg, on="claim_id", how="left")
    df["num_settlements"] = df["num_settlements"].fillna(0).astype(int)
    df["max_approved_amount"] = df["max_approved_amount"].fillna(0.0)
    df["has_multiple_settlements"] = (df["num_settlements"] > 1).astype(int)

    # -------------------------------------------------- one-hot: claim_type
    for ct in CLAIM_TYPES:
        df[f"claim_type_{ct}"] = (df["claim_type"] == ct).astype(int)

    # -------------------------------------------------- ordinal: risk_tier
    df["risk_tier_encoded"] = (
        df["risk_tier"].map(RISK_TIER_MAP).fillna(1).astype(int)
    )

    # -------------------------------------------------------- select features
    feature_cols: list[str] = [
        # numeric from claims table
        "claimed_amount",
        "reporting_delay_days",
        "prior_claims_12m",
        # from policy_coverages
        "coverage_limit",
        "deductible",
        # date-derived
        "days_since_policy_start",
        "days_until_expiry",
        # ratios
        "amount_to_limit_ratio",
        "amount_to_deductible_ratio",
        # boolean
        "is_cancelled",
        "is_lapsed",
        "has_exclusion",
        # document stats
        "num_documents",
        "num_mandatory_docs",
        "num_received_docs",
        "num_requested_docs",
        # items
        "num_claim_items",
        # settlements
        "num_settlements",
        "has_multiple_settlements",
        "max_approved_amount",
        # one-hot claim type
        *(f"claim_type_{ct}" for ct in CLAIM_TYPES),
        # ordinal
        "risk_tier_encoded",
    ]

    result = df.set_index("claim_id")[feature_cols].copy()

    # Ensure numeric columns are truly numeric
    for col in result.columns:
        result[col] = pd.to_numeric(result[col], errors="coerce")

    # Fill remaining NaN with 0 (safe default for tree-based models)
    result = result.fillna(0)

    logger.info(
        "Feature matrix: %d claims × %d features", *result.shape
    )
    return result
