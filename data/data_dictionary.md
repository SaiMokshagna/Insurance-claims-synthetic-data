# Data Dictionary: Insurance Claims Synthetic Dataset

Version 1.0 · Seed 20261022 · Reference date 2026-10-22

## 1. Global conventions

| Item | Convention |
|---|---|
| Dates | ISO `YYYY-MM-DD` (no time). |
| Timestamps | ISO 8601 UTC `YYYY-MM-DDTHH:MM:SSZ`, used only in `status_event`. |
| Money | Single currency **USD**, rounded to 2 decimals. Reconciliation tolerance 0.005. |
| IDs | Immutable, zero-padded, case-sensitive strings. Counters are **global per entity** (not per product). |
| Policy ID year | The `2026` in `POL-<product>-2026-NNNNNN` is the dataset year, not the policy start year. |
| Reference date | `2026-10-22` is the fixed "today" for status derivation. Never use the system clock. |
| Nulls | Empty cell in CSV, `null` in JSON. "Req = N" means null is allowed. |
| Products | `AUTO`, `HOME`, `HLTH`, `LIAB` |
| Claim types | `AUTO_COLLISION`, `PROPERTY_DAMAGE`, `THEFT`, `MEDICAL`, `LIABILITY` |

## 2. Entity overview and cardinality

| Relationship | Cardinality | Notes |
|---|---|---|
| Customer → Policy | 1:N | A customer may hold several policies. |
| Policy ↔ Coverage | N:M via `PolicyCoverage` | Bridge carries limit, deductible, exclusions, effective dates. |
| Policy → Incident | 1:N | Incident belongs to the policy it affected. |
| Incident → Claim | 1:N | More than one claim on one incident is a duplicate-claim case. |
| Policy → Claim | 1:N | |
| Claim → ClaimItem | 1:N | Items are immutable once submitted. |
| Claim → Document | 1:N | Includes REQUESTED rows for missing documents. |
| Claim ↔ Adjuster | N:M via `ClaimAssignment` | Optional until assigned. |
| Claim → Assessment | 1:N | A re-assessment adds a new row; it never overwrites. |
| Claim → Reserve | 1:N | Versioned through `supersedes_reserve_id`. |
| Claim → Settlement | 1:N (normally 1) | More than one PAID settlement is the "paid twice" anomaly. |
| Any entity → status_event | 1:N | Generic audit log of state changes. |

## 3. Entities

### 3.1 Customer (`customers`)

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| customer_id | string (PK) | Y | `CUS-NNNNNN` | Y | Matches regex `^CUS-\d{6}$` |
| full_name | string | Y | 2–80 chars | N | Non-empty |
| date_of_birth | date | Y | Age 18–85 at reference date | N | Not in future |
| email | string | Y | Valid email format | Y | Contains one `@` |
| phone | string | N | Digits, spaces, `+` | N | |
| city | string | Y | From city list | N | |
| region | string | Y | From region list | N | |
| customer_since | date | Y | | N | ≤ reference date |
| risk_tier | enum | Y | `LOW`, `MEDIUM`, `HIGH` | N | |

### 3.2 Coverage (`coverages`): master catalogue

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| coverage_id | string (PK) | Y | `COV-<product>-NN`, e.g. `COV-AUTO-01` | Y | Matches regex |
| product_code | enum | Y | `AUTO`, `HOME`, `HLTH`, `LIAB` | N | |
| coverage_type | enum | Y | A claim type value | N | Must be valid for the product |
| description | string | Y | | N | |
| default_limit | decimal | Y | USD, > 0 | N | |
| default_deductible | decimal | Y | USD, ≥ 0 | N | Less than default_limit |

Planned catalogue: AUTO has `AUTO_COLLISION` and `THEFT`; HOME has `PROPERTY_DAMAGE` and `THEFT`; HLTH has `MEDICAL`; LIAB has `LIABILITY`.

### 3.3 Policy (`policies`)

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| policy_id | string (PK) | Y | `POL-<product>-2026-NNNNNN` | Y | Product segment equals `product_code` |
| customer_id | string (FK → customers) | Y | | N | Must exist |
| product_code | enum | Y | `AUTO`, `HOME`, `HLTH`, `LIAB` | N | |
| effective_date | date | Y | | N | < expiry_date |
| expiry_date | date | Y | Term 12 months | N | |
| status | enum | Y | `IN_FORCE`, `EXPIRED`, `LAPSED`, `CANCELLED` | N | Derived from dates and cancellation (see 5.1) |
| cancellation_date | date | N | | N | Required iff status = `CANCELLED`; within the policy term |
| lapse_date | date | N | | N | Required iff status = `LAPSED` |
| annual_premium | decimal | Y | USD, > 0 | N | |

### 3.4 PolicyCoverage (`policy_coverages`): bridge

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| policy_coverage_id | string (PK) | Y | `PCV-<policy-id>-NN` | Y | |
| policy_id | string (FK) | Y | | N | Must exist |
| coverage_id | string (FK) | Y | | N | Product must match the policy's product |
| coverage_limit | decimal | Y | USD, > 0 | N | |
| deductible | decimal | Y | USD, ≥ 0 | N | < coverage_limit |
| exclusions | string | N | Pipe-separated codes: `WAR`, `INTENTIONAL_ACT`, `RACING`, `WEAR_AND_TEAR`, `PRE_EXISTING`, `UNLICENSED_DRIVER` | N | Every code in the allowed list |
| effective_date | date | Y | | N | Within the policy term |
| expiry_date | date | Y | | N | > effective_date |

Unique pair: (`policy_id`, `coverage_id`).

### 3.5 Incident (`incidents`)

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| incident_id | string (PK) | Y | `INC-2026-NNNNNN` | Y | |
| policy_id | string (FK) | Y | | N | Must exist |
| incident_type | enum | Y | One of the 5 claim types | N | |
| incident_date | date | Y | | N | ≤ reference date |
| location_city | string | Y | | N | |
| description | string | Y | Template text | N | |
| exclusion_triggered | string | N | One exclusion code | N | Used by the rules engine for excluded perils |

Duplicate claims (`DUPLICATE_CLAIM`) share an existing incident row, so there are fewer incident rows than claims.

### 3.6 Claim (`claims`)

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| claim_id | string (PK) | Y | `CLM-2026-NNNNNN` | Y | |
| policy_id | string (FK) | Y | | N | Must exist |
| incident_id | string (FK) | Y | | N | Must exist; incident's policy equals claim's policy |
| coverage_id | string (FK) | Y | | N | Must be attached to the policy via `policy_coverages` |
| claim_type | enum | Y | One of the 5 claim types | N | Equals the incident type |
| submitted_date | date | Y | | N | ≥ incident_date |
| claimed_amount | decimal | Y | USD, > 0 | N | **Derived**: equals sum of `claim_items.claimed_amount` |
| current_status | enum | Y | See lifecycle 5.2 | N | **Derived**: equals the last `status_event` for the claim |
| reporting_delay_days | int | Y | ≥ 0 | N | **Derived**: submitted_date − incident_date |
| prior_claims_12m | int | Y | ≥ 0 | N | **Derived**: count of the same customer's earlier claims in the prior 12 months |

### 3.7 ClaimItem (`claim_items`)

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| claim_item_id | string (PK) | Y | `ITM-<claim-id>-NNN` | Y | |
| claim_id | string (FK) | Y | | N | Must exist |
| item_category | enum | Y | Per claim type, e.g. `REPAIR`, `REPLACEMENT`, `HOSPITAL`, `MEDICATION`, `THIRD_PARTY_DAMAGE` | N | |
| description | string | Y | | N | |
| claimed_amount | decimal | Y | USD, > 0 | N | |

### 3.8 Document (`documents`)

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| document_id | string (PK) | Y | `DOC-<claim-id>-NNN` | Y | |
| claim_id | string (FK) | Y | | N | Must exist |
| document_type | enum | Y | `CLAIM_FORM`, `POLICE_REPORT`, `PHOTOS`, `REPAIR_ESTIMATE`, `MEDICAL_REPORT`, `PROOF_OF_OWNERSHIP`, `INVOICE` | N | |
| is_mandatory | bool | Y | | N | **Derived** from the required-documents rule for the claim type |
| status | enum | Y | `REQUESTED`, `RECEIVED`, `VERIFIED`, `REJECTED` | N | |
| requested_date | date | N | | N | Set when status ≠ received on submission |
| received_date | date | N | | N | Required iff status in `RECEIVED`, `VERIFIED`, `REJECTED`; ≥ submitted_date |
| file_name | string | N | Synthetic name, `.pdf` or `.jpg` | N | Present iff received |
| file_size_kb | int | N | 10–8000 | N | Present iff received |

### 3.9 Adjuster (`adjusters`)

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| adjuster_id | string (PK) | Y | `ADJ-NNNN` | Y | |
| full_name | string | Y | | N | |
| seniority | enum | Y | `JUNIOR`, `SENIOR`, `MANAGER` | N | |
| specialty | enum | Y | One of the 5 claim types | N | |
| region | string | Y | | N | |
| approval_authority | decimal | Y | USD, > 0 | N | JUNIOR < SENIOR < MANAGER |
| hire_date | date | Y | | N | ≤ reference date |
| is_active | bool | Y | | N | |

### 3.10 ClaimAssignment (`claim_assignments`): bridge, `ASN-` IDs

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| assignment_id | string (PK) | Y | `ASN-<claim-id>-NNN` | Y | |
| claim_id | string (FK) | Y | | N | Must exist |
| adjuster_id | string (FK) | Y | | N | Must exist and be active |
| assignment_role | enum | Y | `PRIMARY`, `REVIEWER` | N | Exactly one active `PRIMARY` per claim |
| assigned_date | date | Y | | N | ≥ submitted_date |
| unassigned_date | date | N | | N | > assigned_date |

### 3.11 Assessment (`assessments`): versioned

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| assessment_id | string (PK) | Y | `ASM-<claim-id>-NNN` | Y | |
| claim_id | string (FK) | Y | | N | Must exist |
| adjuster_id | string (FK) | Y | | N | Must be assigned to the claim |
| assessed_date | date | Y | | N | ≥ submitted_date |
| incident_in_coverage_period | bool | Y | | N | **Derived** from dates (see 5.1) |
| documents_complete | bool | Y | | N | **Derived** from `documents` |
| duplicate_suspected | bool | Y | | N | **Derived** from the duplicate rule |
| fraud_risk_score | int | Y | 0–100 | N | **Derived** by a documented weighted formula |
| eligible_amount | decimal | Y | USD, ≥ 0 | N | ≤ claimed_amount |
| eligibility_decision | enum | Y | `ELIGIBLE`, `PARTIALLY_ELIGIBLE`, `INELIGIBLE`, `PENDING_DOCUMENTS`, `REFER_INVESTIGATION` | N | |
| reason_code | enum | Y | See section 6 | N | Required for every decision |
| reason_text | string | Y | | N | Human-readable explanation |
| rule_version | string | Y | e.g. `RULES-1.0` | N | |

### 3.12 Reserve (`reserves`): versioned

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| reserve_id | string (PK) | Y | `RSV-<claim-id>-NNN` | Y | |
| claim_id | string (FK) | Y | | N | Must exist |
| assessment_id | string (FK) | Y | | N | Must belong to the same claim |
| reserve_type | enum | Y | `INITIAL`, `REVISED` | N | |
| reserve_amount | decimal | Y | USD, ≥ 0 | N | ≤ coverage_limit; **derived** = min(eligible − deductible, limit), floored at 0 |
| effective_date | date | Y | | N | ≥ assessed_date |
| supersedes_reserve_id | string (FK, self) | N | | N | Required iff `REVISED` |

### 3.13 Settlement (`settlements`)

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| settlement_id | string (PK) | Y | `SET-<claim-id>-NNN` | Y | |
| claim_id | string (FK) | Y | | N | Must exist |
| assessment_id | string (FK) | Y | | N | Must belong to the same claim |
| routing_decision | enum | Y | `AUTO_APPROVE`, `SENIOR_REVIEW`, `INVESTIGATION`, `REJECT` | N | Follows the routing rules |
| recommended_amount | decimal | Y | USD, ≥ 0 | N | **Derived** from the assessment, deductible, and limit |
| deductible_applied | decimal | Y | USD, ≥ 0 | N | |
| limit_applied | decimal | Y | USD, > 0 | N | |
| approved_amount | decimal | N | USD, ≥ 0 | N | ≤ limit_applied (violations are the injected anomaly) |
| settlement_status | enum | Y | `RECOMMENDED`, `APPROVED`, `REJECTED`, `PAID`, `CANCELLED` | N | |
| approver_id | string (FK → adjusters) | N | | N | Authority ≥ approved_amount |
| approved_date | date | N | | N | |
| paid_date | date | N | | N | Required iff `PAID`; ≥ approved_date |

## 4. Supporting tables

### 4.1 status_event (`status_events`): audit trail

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| event_id | string (PK) | Y | `EVT-NNNNNNNN` | Y | |
| entity_type | enum | Y | `POLICY`, `CLAIM`, `DOCUMENT`, `SETTLEMENT` | N | |
| entity_id | string | Y | | N | Must exist in the table named by `entity_type` |
| event_type | string | Y | e.g. `CLAIM_SUBMITTED`, `DOCS_REQUESTED`, `ASSESSED`, `PAID` | N | |
| from_status | string | N | | N | Null only for the first event of an entity |
| to_status | string | Y | | N | Transition must be legal (see 5.2) |
| event_ts | timestamp | Y | | N | Non-decreasing per entity |
| actor_type | enum | Y | `SYSTEM`, `ADJUSTER`, `CUSTOMER` | N | |
| actor_id | string | N | | N | Adjuster ID when `ADJUSTER` |
| reason_code | string | N | | N | |

### 4.2 ground_truth (`ground_truth.csv`): kept OUT of the model-input files

One row per claim (including claims with no issue). Never read by any generator step and never merged into the input tables.

| Field | Type | Req | Allowed values / format | Unique | Validation rule |
|---|---|---|---|---|---|
| gt_id | string (PK) | Y | `GT-NNNNNN` | Y | One row per claim |
| claim_id | string (FK → claims) | Y | | Y | Exactly one row per claim |
| issue_type | enum | Y | `CLAIM_BEFORE_POLICY_START`, `POLICY_CANCELLED_BEFORE_INCIDENT`, `INCIDENT_OUTSIDE_COVERAGE`, `DUPLICATE_INCIDENT`, `DUPLICATE_CLAIM`, `SETTLEMENT_EXCEEDS_LIMIT`, `MISSING_MANDATORY_DOCUMENT`, `CLAIM_PAID_TWICE`, `AMOUNT_OVER_LIMIT`, `FRAUD_SUSPECTED`, `INCOMPLETE_EVIDENCE`, `NONE` | N | |
| origin | enum | Y | `INJECTED`, `NATURAL`, `NONE` | N | NATURAL = arose in the baseline and was handled correctly |
| injected_table | string | N | | N | Table that was modified (injected rows only) |
| injected_field | string | N | | N | Field that was modified (injected rows only) |
| expected_decision | enum | Y | Eligibility decision values | N | Produced by the rules engine on the final data |
| expected_reason_code | string | Y | Reason codes (section 6) | N | Produced by the rules engine |
| expected_payable_amount | decimal | Y | USD, >= 0 | N | What the rules say should be paid |
| notes | string | N | | N | Plain-language description |

Injection layers:

- **Layer A (inputs, handled correctly by the workflow):** `DUPLICATE_CLAIM`, `DUPLICATE_INCIDENT`, `FRAUD_SUSPECTED`.
- **Layer B (defects: the recorded data breaks a rule):** `CLAIM_BEFORE_POLICY_START`, `POLICY_CANCELLED_BEFORE_INCIDENT`, `INCIDENT_OUTSIDE_COVERAGE`, `SETTLEMENT_EXCEEDS_LIMIT`, `MISSING_MANDATORY_DOCUMENT`, `CLAIM_PAID_TWICE`.
- **Natural (baseline cases, handled correctly):** `AMOUNT_OVER_LIMIT`, `INCOMPLETE_EVIDENCE`, and any naturally arising `FRAUD_SUSPECTED`.

## 5. Lifecycles and derivation rules

### 5.1 Policy status (derived at the reference date)

1. `CANCELLED` if `cancellation_date` is set and ≤ reference date.
2. `LAPSED` if `lapse_date` is set and ≤ reference date.
3. `EXPIRED` if `expiry_date` < reference date.
4. Otherwise `IN_FORCE`.

An incident is **in coverage period** if `effective_date ≤ incident_date ≤ min(expiry_date, cancellation_date, lapse_date)` (ignoring null dates).

### 5.2 Claim status transitions

```
SUBMITTED → UNDER_REVIEW
UNDER_REVIEW → DOCS_REQUESTED | ASSESSED
DOCS_REQUESTED → UNDER_REVIEW
ASSESSED → APPROVED | REJECTED | REFERRED
APPROVED → PAID
PAID → CLOSED
REJECTED → CLOSED
REFERRED → APPROVED | REJECTED
```

Any other transition is invalid and must be flagged by the validator (except where deliberately injected and labelled in `ground_truth`).

### 5.3 Settlement status transitions

```
RECOMMENDED → APPROVED | REJECTED
APPROVED → PAID | CANCELLED
```

## 6. Reason codes

| Code | Meaning |
|---|---|
| COVERED_OK | Claim is covered and eligible |
| COVERED_LIMIT_CAPPED | Eligible, but payout capped at the coverage limit |
| INCIDENT_BEFORE_POLICY_START | Incident predates the effective date |
| INCIDENT_AFTER_COVERAGE_END | Incident after expiry, lapse, or cancellation |
| POLICY_CANCELLED_BEFORE_INCIDENT | Policy cancelled before the incident date |
| CLAIM_BEFORE_POLICY_START | Claim submitted before the policy start |
| EXCLUDED_PERIL | An exclusion applies |
| MISSING_MANDATORY_DOCUMENT | Mandatory document not received yet (within the 30-day deadline) |
| DOCUMENTS_OVERDUE | Requested mandatory document not received within 30 days |
| DUPLICATE_CLAIM | Same incident already claimed |
| DUPLICATE_INCIDENT | Same policy, type, and date already recorded (location is ignored) |
| BELOW_DEDUCTIBLE | Claimed amount does not exceed the deductible; nothing payable |
| FRAUD_REFERRAL | Fraud risk score above the threshold |
| PAID_TWICE | More than one PAID settlement on the claim |

## 7. Required documents by claim type (rule table)

| Claim type | Mandatory documents |
|---|---|
| AUTO_COLLISION | `CLAIM_FORM`, `PHOTOS`, `REPAIR_ESTIMATE` |
| PROPERTY_DAMAGE | `CLAIM_FORM`, `PHOTOS`, `REPAIR_ESTIMATE` |
| THEFT | `CLAIM_FORM`, `POLICE_REPORT`, `PROOF_OF_OWNERSHIP` |
| MEDICAL | `CLAIM_FORM`, `MEDICAL_REPORT`, `INVOICE` |
| LIABILITY | `CLAIM_FORM`, `POLICE_REPORT`, `INVOICE` |
