"""Transaction tables: incidents, claims, claim_items, documents.

Pipeline: (1) list every (policy, coverage) a claim could be made against,
(2) draw clean claims weighted by exposure, (3) add Layer A scenarios
(duplicates, fraud pattern) as extra INPUTS, (4) sort by submission date,
(5) only then assign IDs and build the tables.
"""
import copy
from datetime import timedelta

import numpy as np
import pandas as pd

from generator import ids
from generator.config import (
    CLAIM_AMOUNT_MEDIAN_FRACTION, CLAIM_AMOUNT_SIGMA, CLAIM_PERIOD_START,
    EARLY_CLAIM_DAYS, P_EXCLUSION_TRIGGERED, P_EXTRA_DOCUMENT,
    P_INCOMPLETE_EVIDENCE, P_LATE_RECEIVED, REFERENCE_DATE,
)
from generator.master import pick
from generator.reference_data import (
    CITIES, CLAIM_TYPE_WEIGHTS, INCIDENT_DESCRIPTIONS, ITEM_CATEGORIES,
    ITEM_DESCRIPTIONS, OPTIONAL_DOCUMENTS, REQUIRED_DOCUMENTS,
)
from generator.rules import derive_prior_claims

RECEIVED_STATUSES = ("RECEIVED", "VERIFIED", "REJECTED")


def _clamp(d):
    """Dates can never be later than the reference date."""
    return min(d, REFERENCE_DATE)


def _coverage_window_end(pol):
    ends = [pol["expiry_date"], REFERENCE_DATE]
    for key in ("cancellation_date", "lapse_date"):
        if pd.notna(pol[key]):
            ends.append(pol[key])
    return min(ends)


def _build_candidates(policies, policy_coverages, coverages, risk_of):
    pol = policies.set_index("policy_id").to_dict("index")
    cov_type = coverages.set_index("coverage_id")["coverage_type"].to_dict()
    candidates = []
    for pc in policy_coverages.itertuples(index=False):
        p = pol[pc.policy_id]
        start = max(p["effective_date"], CLAIM_PERIOD_START)
        exposure = (_coverage_window_end(p) - start).days + 1
        if exposure <= 0:
            continue                      # no covered days in 2026
        ctype = cov_type[pc.coverage_id]
        candidates.append({
            "policy_id": pc.policy_id,
            "customer_id": p["customer_id"],
            "risk_tier": risk_of[p["customer_id"]],
            "coverage_id": pc.coverage_id,
            "claim_type": ctype,
            "coverage_limit": pc.coverage_limit,
            "exclusions": pc.exclusions.split("|"),
            "effective": p["effective_date"],
            "start": start,
            "exposure": exposure,
            "weight": CLAIM_TYPE_WEIGHTS[ctype] * exposure,
        })
    return candidates


def _received_doc(rng, dtype, mandatory, received, requested):
    return {
        "document_type": dtype,
        "is_mandatory": mandatory,
        "status": "VERIFIED" if rng.random() < 0.7 else "RECEIVED",
        "requested_date": requested,
        "received_date": received,
        "file_ext": "jpg" if dtype == "PHOTOS" else "pdf",
        "file_size_kb": int(rng.integers(50, 6001)),
    }


def _draw_documents(rng, ctype, submitted, force_complete=False):
    mandatory = REQUIRED_DOCUMENTS[ctype]
    incomplete = rng.random() < P_INCOMPLETE_EVIDENCE
    if force_complete:
        incomplete = False
    late_idx, arrives_late = -1, False
    if incomplete:
        late_idx = int(rng.integers(len(mandatory)))
        arrives_late = rng.random() < P_LATE_RECEIVED

    docs = []
    for i, dtype in enumerate(mandatory):
        if i == late_idx:
            requested = _clamp(submitted + timedelta(days=int(rng.integers(1, 4))))
            received = submitted + timedelta(days=int(rng.integers(5, 21)))
            if arrives_late and received <= REFERENCE_DATE:
                docs.append(_received_doc(rng, dtype, True, received, requested))
            else:   # still outstanding as of the reference date
                docs.append({"document_type": dtype, "is_mandatory": True,
                             "status": "REQUESTED", "requested_date": requested,
                             "received_date": None, "file_ext": None,
                             "file_size_kb": None})
        else:
            received = _clamp(submitted + timedelta(days=int(rng.integers(0, 4))))
            docs.append(_received_doc(rng, dtype, True, received, None))

    if rng.random() < P_EXTRA_DOCUMENT and OPTIONAL_DOCUMENTS[ctype]:
        dtype = pick(rng, OPTIONAL_DOCUMENTS[ctype])
        received = _clamp(submitted + timedelta(days=int(rng.integers(0, 6))))
        docs.append(_received_doc(rng, dtype, False, received, None))
    return docs


def _draw_items(rng, ctype, limit, total=None):
    """Claim items: amounts split a total; the claim total is later SUMMED from them."""
    n_items = int(rng.integers(1, 5))
    if total is None:
        total = max(100.0, limit * CLAIM_AMOUNT_MEDIAN_FRACTION
                    * float(rng.lognormal(0, CLAIM_AMOUNT_SIGMA)))
    shares = 0.5 / n_items + 0.5 * rng.dirichlet(np.ones(n_items))   # every item >= 12.5%
    amounts = [round(total * float(s), 2) for s in shares]
    amounts[-1] = round(total - sum(amounts[:-1]), 2)
    items = []
    for amount in amounts:
        category = pick(rng, ITEM_CATEGORIES[ctype])
        items.append({"item_category": category,
                      "description": pick(rng, ITEM_DESCRIPTIONS[category]),
                      "claimed_amount": amount})
    return items


def _draw_claim_spec(rng, cand, city_of, order):
    ctype = cand["claim_type"]
    incident_date = cand["start"] + timedelta(days=int(rng.integers(0, cand["exposure"])))
    delay = int(min(rng.exponential(5), 60))
    submitted = min(incident_date + timedelta(days=delay), REFERENCE_DATE)

    home_city = city_of[cand["customer_id"]]
    city = home_city if rng.random() < 0.85 else pick(rng, CITIES)[0]
    description = pick(rng, INCIDENT_DESCRIPTIONS[ctype])
    exclusion = pick(rng, cand["exclusions"]) if rng.random() < P_EXCLUSION_TRIGGERED else None
    items = _draw_items(rng, ctype, cand["coverage_limit"])
    return {
        "order": order, "policy_id": cand["policy_id"], "coverage_id": cand["coverage_id"],
        "claim_type": ctype, "incident_date": incident_date, "submitted_date": submitted,
        "city": city, "description": description, "exclusion": exclusion,
        "items": items, "docs": _draw_documents(rng, ctype, submitted),
        "issue_type": None, "incident_of": None,
    }


def _new_base_spec(rng, candidates, probs, city_of, used, order):
    """A clean claim whose (policy, type, date) is not already taken."""
    cand = candidates[int(rng.choice(len(candidates), p=probs))]
    for attempt in range(50):
        spec = _draw_claim_spec(rng, cand, city_of, order)
        key = (spec["policy_id"], spec["claim_type"], spec["incident_date"])
        if key not in used:
            break
        if attempt % 10 == 9:       # this coverage keeps colliding: try another one
            cand = candidates[int(rng.choice(len(candidates), p=probs))]
    used.add(key)
    return spec


# ---------------------------------------------------------------------------
# Layer A: scenarios built as inputs
# ---------------------------------------------------------------------------
def _make_duplicate(rng, original, kind, order):
    """Same policy, type, date and amount, filed again 1-15 days later."""
    dup = copy.deepcopy(original)
    dup["order"] = order
    dup["issue_type"] = kind
    dup["submitted_date"] = original["submitted_date"] + timedelta(days=int(rng.integers(1, 16)))
    dup["docs"] = _draw_documents(rng, original["claim_type"], dup["submitted_date"])
    if kind == "DUPLICATE_CLAIM":
        dup["incident_of"] = original["order"]     # shares the original's incident row
    return dup                                     # DUPLICATE_INCIDENT gets its own incident row


def _fraud_max_offset(cand):
    """Latest day after the window start that still allows an early AND late-reported claim."""
    days_after_start = (cand["start"] - cand["effective"]).days
    return min(EARLY_CLAIM_DAYS - days_after_start, cand["exposure"] - 1,
               (REFERENCE_DATE - cand["start"]).days - 45)


def _draw_fraud_spec(rng, cand, city_of, order):
    """Engineered to trip the fraud score: incident within 30 days of policy start,
    reported 31-45 days late, amount 85-130% of the limit, high-risk customer.
    (20 + 15 + 10 + 10 = 55, above the referral threshold of 50.)"""
    ctype, limit = cand["claim_type"], cand["coverage_limit"]
    incident_date = cand["start"] + timedelta(days=int(rng.integers(0, _fraud_max_offset(cand) + 1)))
    submitted = incident_date + timedelta(days=31 + int(rng.integers(0, 15)))
    total = round(limit * (0.85 + 0.45 * float(rng.random())), 2)
    return {
        "order": order, "policy_id": cand["policy_id"], "coverage_id": cand["coverage_id"],
        "claim_type": ctype, "incident_date": incident_date, "submitted_date": submitted,
        "city": city_of[cand["customer_id"]],
        "description": pick(rng, INCIDENT_DESCRIPTIONS[ctype]), "exclusion": None,
        "items": _draw_items(rng, ctype, limit, total=total),
        "docs": _draw_documents(rng, ctype, submitted, force_complete=True),
        "issue_type": "FRAUD_SUSPECTED", "incident_of": None,
    }


# ---------------------------------------------------------------------------
def _build_tables(specs, master):
    claim_of, incident_of_order, counter = {}, {}, 0
    for n, s in enumerate(specs, start=1):          # IDs are assigned only now
        claim_of[s["order"]] = ids.claim_id(n)
        if s["incident_of"] is None:
            counter += 1
            incident_of_order[s["order"]] = ids.incident_id(counter)

    inc_rows, clm_rows, item_rows, doc_rows, labels = [], [], [], [], {}
    for s in specs:
        clm = claim_of[s["order"]]
        inc = incident_of_order[s["order"] if s["incident_of"] is None else s["incident_of"]]
        if s["incident_of"] is None:
            inc_rows.append({
                "incident_id": inc, "policy_id": s["policy_id"],
                "incident_type": s["claim_type"], "incident_date": s["incident_date"],
                "location_city": s["city"], "description": s["description"],
                "exclusion_triggered": s["exclusion"],
            })
        clm_rows.append({
            "claim_id": clm, "policy_id": s["policy_id"], "incident_id": inc,
            "coverage_id": s["coverage_id"], "claim_type": s["claim_type"],
            "submitted_date": s["submitted_date"],
            "claimed_amount": round(sum(i["claimed_amount"] for i in s["items"]), 2),
            "current_status": "SUBMITTED",           # the workflow recomputes this from events
            "reporting_delay_days": (s["submitted_date"] - s["incident_date"]).days,
        })
        for k, item in enumerate(s["items"], start=1):
            item_rows.append({"claim_item_id": ids.claim_item_id(clm, k),
                              "claim_id": clm, **item})
        for k, d in enumerate(s["docs"], start=1):
            received = d["status"] in RECEIVED_STATUSES
            doc_rows.append({
                "document_id": ids.document_id(clm, k), "claim_id": clm,
                "document_type": d["document_type"], "is_mandatory": d["is_mandatory"],
                "status": d["status"], "requested_date": d["requested_date"],
                "received_date": d["received_date"],
                "file_name": f"{clm}_{d['document_type'].lower()}.{d['file_ext']}" if received else None,
                "file_size_kb": d["file_size_kb"],
            })
        if s["issue_type"]:
            labels[clm] = s["issue_type"]

    claims = pd.DataFrame(clm_rows)
    claims["prior_claims_12m"] = derive_prior_claims(claims, master["policies"])
    documents = pd.DataFrame(doc_rows)
    documents["file_size_kb"] = documents["file_size_kb"].astype("Int64")   # blanks, not 123.00
    tables = {
        "incidents": pd.DataFrame(inc_rows), "claims": claims,
        "claim_items": pd.DataFrame(item_rows), "documents": documents,
    }
    return tables, labels


def generate_transactions(rng, master, n_claims, plan=None, labels=None):
    """Build the transaction tables. `plan` adds Layer A scenarios; if `labels`
    (a dict) is passed it is filled with {claim_id: issue_type} for them."""
    plan = plan or {}
    n_dup_claim = plan.get("DUPLICATE_CLAIM", 0)
    n_dup_inc = plan.get("DUPLICATE_INCIDENT", 0)
    n_fraud = plan.get("FRAUD_SUSPECTED", 0)

    risk_of = master["customers"].set_index("customer_id")["risk_tier"].to_dict()
    candidates = _build_candidates(master["policies"], master["policy_coverages"],
                                   master["coverages"], risk_of)
    weights = np.array([c["weight"] for c in candidates], dtype=float)
    probs = weights / weights.sum()
    city_of = master["customers"].set_index("customer_id")["city"].to_dict()

    # 1. Clean claims first
    used, specs = set(), []
    for _ in range(n_claims - (n_dup_claim + n_dup_inc + n_fraud)):
        specs.append(_new_base_spec(rng, candidates, probs, city_of, used, len(specs)))

    # 2. Layer A: duplicates of clean, on-time, non-excluded claims
    pool = [s for s in specs
            if s["exclusion"] is None
            and all(d["requested_date"] is None for d in s["docs"])
            and s["submitted_date"] <= REFERENCE_DATE - timedelta(days=16)]
    k = min(n_dup_claim + n_dup_inc, len(pool))
    originals = [pool[int(i)] for i in rng.choice(len(pool), size=k, replace=False)] if k else []
    for j, original in enumerate(originals):
        kind = "DUPLICATE_CLAIM" if j < n_dup_claim else "DUPLICATE_INCIDENT"
        specs.append(_make_duplicate(rng, original, kind, len(specs)))

    # 3. Layer A: fraud pattern, on high-risk customers
    fraud_pool = [c for c in candidates if c["risk_tier"] == "HIGH" and _fraud_max_offset(c) >= 0]
    made = tries = 0
    while made < n_fraud and fraud_pool and tries < 20 * n_fraud:
        tries += 1
        spec = _draw_fraud_spec(rng, fraud_pool[int(rng.integers(len(fraud_pool)))],
                                city_of, len(specs))
        key = (spec["policy_id"], spec["claim_type"], spec["incident_date"])
        if key in used:
            continue
        used.add(key)
        specs.append(spec)
        made += 1

    # 4. Top up with clean claims if any scenario could not be built (keeps the total exact)
    while len(specs) < n_claims:
        specs.append(_new_base_spec(rng, candidates, probs, city_of, used, len(specs)))

    specs.sort(key=lambda s: (s["submitted_date"], s["order"]))
    tables, claim_labels = _build_tables(specs, master)
    if labels is not None:
        labels.update(claim_labels)
    return tables