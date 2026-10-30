"""Tests for the FastAPI anomaly detection API."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from api.serve import app
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["dataset_loaded"] is True
    assert data["model_loaded"] is True


def test_predict_returns_all_claims(client):
    resp = client.post("/predict", json={"seed": 20261022, "policies": 100, "claims": 50})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_claims"] == 50
    assert len(data["predictions"]) == 50
    assert 0.0 <= data["rules_f1_macro"] <= 1.0
    assert 0.0 <= data["ml_f1_macro"] <= 1.0


def test_detect_seed_shortcut(client):
    resp = client.get("/detect/20261022")
    assert resp.status_code == 200
    data = resp.json()
    assert data["seed"] == 20261022
    assert data["total_claims"] > 0
