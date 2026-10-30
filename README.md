# Insurance Claims Anomaly Detection System

A synthetic insurance claims data generator with **ML-based anomaly detection** and a **REST API** for serving predictions. Built as an end-to-end AI pipeline: data generation → feature engineering → model training → API deployment.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Data Generation Pipeline                      │
│  generator/                                                          │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────────┐  │
│  │  Master   │→│ Transactions │→│ Workflow  │→│  Anomaly       │  │
│  │  Data     │  │ (incidents,  │  │ (assess, │  │  Injection     │  │
│  │ (2000     │  │  claims,     │  │  settle, │  │  (Layer A + B) │  │
│  │  policies)│  │  documents)  │  │  events) │  │  + Ground Truth│  │
│  └──────────┘  └──────────────┘  └──────────┘  └────────────────┘  │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
        ┌───────────────────┐          ┌───────────────────┐
        │  Rules-Based      │          │  ML Model         │
        │  Detector         │          │  (RandomForest     │
        │  (generator/      │          │   Classifier)     │
        │   detect.py)      │          │  (model/)         │
        └────────┬──────────┘          └────────┬──────────┘
                 │                               │
                 └──────────┬────────────────────┘
                            ▼
                 ┌───────────────────┐
                 │  FastAPI Server   │
                 │  (api/serve.py)   │
                 │  POST /predict    │
                 │  GET /health      │
                 └───────────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate the synthetic dataset (14 tables, 1000 claims, ~17K events)
python -m generator --seed 20261022 --policies 2000 --claims 1000

# 3. Train the ML anomaly detection model
python -m model.train

# 4. Start the API server
uvicorn api.serve:app --reload

# 5. Run the full test suite (30+ tests)
pytest
```

## Docker

```bash
docker build -t claims-detector .
docker run -p 8000:8000 claims-detector
# API docs at http://localhost:8000/docs
```

## Project Structure

```
claims-data-generator/
├── generator/              # Synthetic data generation engine
│   ├── config.py           # All parameters: seeds, rates, thresholds
│   ├── master.py           # Customers, policies, coverages, adjusters
│   ├── transactions.py     # Incidents, claims, items, documents
│   ├── workflow.py         # Assignments, assessments, reserves, settlements
│   ├── anomalies.py        # Defect injection (Layer A + B) and ground truth
│   ├── rules.py            # Business rules engine (coverage, fraud, routing)
│   ├── detect.py           # Rules-based anomaly detector (baseline)
│   ├── validate.py         # 90+ validation checks across all tables
│   ├── export.py           # CSV, JSON, SQL, manifest with SHA-256 checksums
│   └── report.py           # Validation summary report generation
│
├── model/                  # ML anomaly detection
│   ├── features.py         # Feature engineering from 14 joined tables
│   ├── train.py            # Model training + evaluation + comparison
│   └── predict.py          # Model loading + inference
│
├── api/                    # REST API
│   └── serve.py            # FastAPI server with /predict and /health
│
├── tests/                  # Test suite (30+ tests)
│   ├── test_rules.py       # Business rules boundary testing
│   ├── test_anomalies.py   # Defect injection verification
│   ├── test_detection.py   # Detector accuracy testing
│   ├── test_export.py      # SQL FK enforcement, JSON/CSV fidelity
│   ├── test_api.py         # API endpoint testing
│   └── ...
│
├── docs/
│   ├── data_dictionary.md  # 300+ line schema specification
│   └── reproducibility_report.md
│
├── Dockerfile              # Container for deployment
├── pyproject.toml          # Package metadata and entry points
└── requirements.txt        # Pinned dependencies
```

## Dataset

The generator creates **14 interrelated tables** modeling an insurance claims workflow:

| Table | Description | Rows |
|---|---|---|
| customers | Policyholders | 1,200 |
| policies | Insurance policies | 2,000 |
| policy_coverages | Coverage terms per policy | ~3,300 |
| incidents | Reported incidents | ~985 |
| claims | Filed claims | 1,000 |
| claim_items | Line items per claim | ~2,500 |
| documents | Required/optional documents | ~3,200 |
| claim_assignments | Adjuster assignments | ~1,600 |
| assessments | Eligibility assessments | ~970 |
| reserves | Financial reserves (versioned) | ~1,750 |
| settlements | Payment decisions | ~975 |
| status_events | Full audit trail | ~16,700 |
| adjusters | Claims adjusters | 40 |
| coverages | Coverage catalogue | 6 |

## Anomaly Detection

### Two-Layer Injection Strategy

- **Layer A (Input Anomalies):** Duplicates and fraud patterns are created as *inputs* — the workflow handles them through the documented business rules.
- **Layer B (Data Defects):** Records are *mutated after processing* — the data now violates the rules, and each violation is labelled in `ground_truth.csv`.

### Anomaly Types (12 categories)

| Type | Layer | Count per 1K |
|---|---|---|
| DUPLICATE_CLAIM | A | 15 |
| DUPLICATE_INCIDENT | A | 15 |
| FRAUD_SUSPECTED | A | 30 |
| CLAIM_BEFORE_POLICY_START | B | 12 |
| POLICY_CANCELLED_BEFORE_INCIDENT | B | 12 |
| INCIDENT_OUTSIDE_COVERAGE | B | 16 |
| SETTLEMENT_EXCEEDS_LIMIT | B | 15 |
| MISSING_MANDATORY_DOCUMENT | B | 15 |
| CLAIM_PAID_TWICE | B | 12 |
| AMOUNT_OVER_LIMIT | Natural | — |
| INCOMPLETE_EVIDENCE | Natural | — |
| NONE | — | — |

### ML vs Rules Comparison

The rules-based detector (`generator/detect.py`) achieves perfect F1 by construction. The ML model (`model/`) is trained to match or approach this performance using only numeric/categorical features — demonstrating that the injected anomalies are detectable from the data without hand-coded rules.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check — model and dataset status |
| `POST` | `/predict` | Generate dataset + return predictions from both detectors |
| `GET` | `/detect/{seed}` | Shortcut: predict with default params and given seed |
| `GET` | `/docs` | Auto-generated OpenAPI documentation |

### Example

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"seed": 20261022, "policies": 200, "claims": 100}'
```

## Validation

90+ automated checks cover:
- Primary key uniqueness and ID format matching
- Foreign key integrity across all 14 tables
- Enum value constraints
- Date ordering and coverage period boundaries
- Arithmetic reconciliation (amounts, deductibles, limits)
- Lifecycle state machine compliance (claim, settlement, document, policy)
- Business rule consistency

## Reproducibility

The generator uses a single seeded `numpy.random.Generator` for the entire run. Two runs with the same seed produce **byte-identical output**, verified by SHA-256 checksums. See [`docs/reproducibility_report.md`](docs/reproducibility_report.md).

## Provenance

All data is synthetic. No external datasets, no scraping, no personal data. Names come from short fictional lists, email addresses use the reserved `example.com` domain, and all amounts are in USD.
