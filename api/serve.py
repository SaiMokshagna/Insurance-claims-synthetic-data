"""REST API for insurance claims anomaly detection.

Serves predictions from both the rules-based detector and the trained ML model,
allowing side-by-side comparison of the two approaches.

Start with:  uvicorn api.serve:app --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from generator.config import DEFAULT_CLAIMS, DEFAULT_POLICIES, DEFAULT_SEED
from generator.detect import detect as rules_detect
from generator.detect import score_detection
from generator.pipeline import build_dataset
from model.predict import load_model, predict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"

# --- State: loaded once at startup ---
_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Loading ML model...")
    model_path = MODEL_DIR / "trained_model.joblib"
    encoder_path = MODEL_DIR / "label_encoder.joblib"
    if model_path.exists() and encoder_path.exists():
        _state["model"], _state["encoder"] = load_model(model_path, encoder_path)
        logger.info("ML model loaded.")
    else:
        logger.warning("Trained model not found at %s — run 'python -m model.train' first.", model_path)

    logger.info("Building default dataset (seed=%d)...", DEFAULT_SEED)
    clean, final, gt = build_dataset(DEFAULT_SEED, DEFAULT_POLICIES, DEFAULT_CLAIMS)
    _state["final"] = final
    _state["gt"] = gt
    logger.info("Default dataset ready (%d claims).", len(gt))
    yield
    _state.clear()


app = FastAPI(
    title="Claims Anomaly Detection API",
    description=(
        "Serves anomaly predictions for synthetic insurance claims data. "
        "Compares a rules-based baseline detector against a trained ML model."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


class GenerateRequest(BaseModel):
    seed: int = Field(default=DEFAULT_SEED, description="RNG seed for reproducible generation")
    policies: int = Field(default=DEFAULT_POLICIES, ge=10, le=50000)
    claims: int = Field(default=DEFAULT_CLAIMS, ge=10, le=50000)


class PredictionRow(BaseModel):
    claim_id: str
    rules_prediction: str
    ml_prediction: str
    ground_truth: str


class PredictionResponse(BaseModel):
    seed: int
    total_claims: int
    rules_f1_macro: float
    ml_f1_macro: float
    predictions: list[PredictionRow]
    mismatches: int


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    dataset_loaded: bool


def _macro_f1(scores: pd.DataFrame) -> float:
    """Compute macro-average F1 from the per-issue scores table."""
    valid = scores["f1"].dropna()
    return round(float(valid.mean()), 4) if len(valid) else 0.0


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model_loaded="model" in _state,
        dataset_loaded="final" in _state,
    )


@app.post("/predict", response_model=PredictionResponse)
def predict_endpoint(req: GenerateRequest) -> PredictionResponse:
    """Generate a dataset with the given parameters and return predictions from both detectors."""
    if "model" not in _state:
        raise HTTPException(status_code=503, detail="ML model not loaded. Run 'python -m model.train' first.")

    logger.info("Generating dataset (seed=%d, policies=%d, claims=%d)...", req.seed, req.policies, req.claims)
    _, final, gt = build_dataset(req.seed, req.policies, req.claims)

    # Rules-based predictions
    rules_pred = rules_detect(final)
    rules_scores, _ = score_detection(gt, rules_pred)

    # ML predictions
    ml_pred = predict(final, _state["model"], _state["encoder"])
    ml_scores, _ = score_detection(gt, ml_pred)

    # Merge everything
    merged = (
        gt[["claim_id", "issue_type"]]
        .merge(rules_pred.rename(columns={"predicted_issue": "rules_prediction"}), on="claim_id")
        .merge(ml_pred.rename(columns={"predicted_issue": "ml_prediction"}), on="claim_id")
    )

    predictions = [
        PredictionRow(
            claim_id=row.claim_id,
            rules_prediction=row.rules_prediction,
            ml_prediction=row.ml_prediction,
            ground_truth=row.issue_type,
        )
        for row in merged.itertuples(index=False)
    ]

    mismatches = int((merged["issue_type"] != merged["ml_prediction"]).sum())

    return PredictionResponse(
        seed=req.seed,
        total_claims=len(gt),
        rules_f1_macro=_macro_f1(rules_scores),
        ml_f1_macro=_macro_f1(ml_scores),
        predictions=predictions,
        mismatches=mismatches,
    )


@app.get("/detect/{seed}", response_model=PredictionResponse)
def detect_with_seed(seed: int) -> PredictionResponse:
    """Shortcut: generate with the given seed using default policy/claim counts."""
    return predict_endpoint(GenerateRequest(seed=seed))


def main() -> None:
    import uvicorn
    uvicorn.run("api.serve:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
