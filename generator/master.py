"""Master (parent) tables.

IMPORTANT: the ORDER of random draws defines the dataset. If you reorder the
build_* calls, or add a draw in the middle, every later row changes.
"""
import math
from datetime import timedelta

import numpy as np
import pandas as pd

from generator import ids
from generator.config import (
    CLAIM_TYPES, CUSTOMER_RATIO, P_CANCELLED, P_LAPSED, POLICY_WINDOW_END,
    POLICY_WINDOW_START, REFERENCE_DATE, TERM_DAYS,
)
from generator.reference_data import (
    APPROVAL_AUTHORITY, BASE_PREMIUM, CITIES, COVERAGE_CATALOGUE,
    EXCLUSIONS_BY_COVERAGE_TYPE, FIRST_NAMES, LAST_NAMES, PRODUCT_WEIGHTS,
)
from generator.rules import derive_policy_status


def pick(rng, options):
    """Pick one item from a list using the shared RNG."""
    return options[int(rng.integers(len(options)))]


def build_customers(rng, n_customers):
    rows = []
    for n in range(1, n_customers + 1):
        first, last = pick(rng, FIRST_NAMES), pick(rng, LAST_NAMES)
        age_years = float(np.clip(rng.normal(42, 13), 18.1, 85))
        dob = REFERENCE_DATE - timedelta(days=int(age_years * 365.25))
        # Tenure: mostly short, never before the 18th birthday, max 15 years.
        max_tenure = int((age_years - 18) * 365.25)
        tenure = int(min(rng.exponential(4 * 365), max_tenure, 15 * 365))
        city, region = pick(rng, CITIES)
        rows.append({
            "customer_id": ids.customer_id(n),
            "full_name": f"{first} {last}",
            "date_of_birth": dob,
            "email": f"{first.lower()}.{last.lower()}{n}@example.com",
            "phone": f"+1-555-{int(rng.integers(100, 1000))}-{int(rng.integers(1000, 10000))}",
            "city": city,
            "region": region,
            "customer_since": REFERENCE_DATE - timedelta(days=tenure),
            "risk_tier": str(rng.choice(["LOW", "MEDIUM", "HIGH"], p=[0.6, 0.3, 0.1])),
        })
    return pd.DataFrame(rows)


def build_coverages():
    """The coverage catalogue is fixed reference data: no randomness."""
    rows = []
    for product, num, ctype, desc, limit, deductible in COVERAGE_CATALOGUE:
        rows.append({
            "coverage_id": ids.coverage_id(product, num),
            "product_code": product,
            "coverage_type": ctype,
            "description": desc,
            "default_limit": float(limit),
            "default_deductible": float(deductible),
        })
    return pd.DataFrame(rows)


def build_adjusters(rng, n_adjusters):
    """Specialty cycles through claim types; each specialty gets one manager,
    two seniors and the rest juniors, so every claim type can be routed."""
    regions = sorted({region for _, region in CITIES})
    rows = []
    for i in range(n_adjusters):
        specialty = CLAIM_TYPES[i % len(CLAIM_TYPES)]
        rank = i // len(CLAIM_TYPES)
        seniority = "MANAGER" if rank == 0 else "SENIOR" if rank <= 2 else "JUNIOR"
        rows.append({
            "adjuster_id": ids.adjuster_id(i + 1),
            "full_name": f"{pick(rng, FIRST_NAMES)} {pick(rng, LAST_NAMES)}",
            "seniority": seniority,
            "specialty": specialty,
            "region": pick(rng, regions),
            "approval_authority": APPROVAL_AUTHORITY[seniority],
            "hire_date": REFERENCE_DATE - timedelta(days=int(rng.integers(180, 3650))),
            "is_active": True if rank <= 2 else bool(rng.random() < 0.9),
        })
    return pd.DataFrame(rows)


def build_policies(rng, customers, n_policies):
    cust_ids = customers["customer_id"].tolist()
    cust_since = customers["customer_since"].tolist()
    n_customers = len(cust_ids)

    # Every customer gets at least one policy; the rest are spread randomly.
    base = np.arange(n_customers)
    extra = rng.integers(0, n_customers, size=n_policies - n_customers)
    customer_idx = rng.permutation(np.concatenate([base, extra]))

    products = list(PRODUCT_WEIGHTS)
    weights = list(PRODUCT_WEIGHTS.values())
    window_days = (POLICY_WINDOW_END - POLICY_WINDOW_START).days

    rows = []
    for n, ci in enumerate(customer_idx, start=1):
        ci = int(ci)
        product = str(rng.choice(products, p=weights))
        candidate = POLICY_WINDOW_START + timedelta(days=int(rng.integers(0, window_days + 1)))
        effective = max(candidate, cust_since[ci])   # never before customer_since
        expiry = effective + timedelta(days=TERM_DAYS)

        # Mid-term cancellation or lapse (never both), in the past, 30+ days in.
        cancellation = lapse = None
        roll = float(rng.random())
        earliest = effective + timedelta(days=30)
        latest = min(expiry - timedelta(days=1), REFERENCE_DATE)
        if earliest <= latest:
            event_date = earliest + timedelta(days=int(rng.integers(0, (latest - earliest).days + 1)))
            if roll < P_CANCELLED:
                cancellation = event_date
            elif roll < P_CANCELLED + P_LAPSED:
                lapse = event_date

        rows.append({
            "policy_id": ids.policy_id(product, n),
            "customer_id": cust_ids[ci],
            "product_code": product,
            "effective_date": effective,
            "expiry_date": expiry,
            "status": derive_policy_status(cancellation, lapse, expiry, REFERENCE_DATE),
            "cancellation_date": cancellation,
            "lapse_date": lapse,
            "annual_premium": round(BASE_PREMIUM[product] * float(rng.lognormal(0, 0.25)), 2),
        })
    return pd.DataFrame(rows)


def build_policy_coverages(rng, policies, coverages):
    cov_by_product = {}
    for cov in coverages.itertuples(index=False):
        cov_by_product.setdefault(cov.product_code, []).append(cov)

    rows = []
    for pol in policies.itertuples(index=False):
        for k, cov in enumerate(cov_by_product[pol.product_code], start=1):
            limit_mult = float(rng.choice([0.5, 1.0, 1.5, 2.0], p=[0.2, 0.5, 0.2, 0.1]))
            ded_mult = float(rng.choice([0.5, 1.0, 2.0], p=[0.25, 0.5, 0.25]))
            options = EXCLUSIONS_BY_COVERAGE_TYPE[cov.coverage_type]
            n_excl = int(rng.integers(1, min(2, len(options)) + 1))
            chosen = sorted(str(x) for x in rng.choice(options, size=n_excl, replace=False))
            rows.append({
                "policy_coverage_id": ids.policy_coverage_id(pol.policy_id, k),
                "policy_id": pol.policy_id,
                "coverage_id": cov.coverage_id,
                "coverage_limit": round(cov.default_limit * limit_mult, 2),
                "deductible": round(cov.default_deductible * ded_mult, 2),
                "exclusions": "|".join(chosen),
                "effective_date": pol.effective_date,
                "expiry_date": pol.expiry_date,
            })
    return pd.DataFrame(rows)


def generate_master(rng, n_policies, n_claims):
    n_customers = max(1, min(n_policies, round(n_policies * CUSTOMER_RATIO)))
    n_adjusters = max(20, math.ceil(n_claims / 25))

    customers = build_customers(rng, n_customers)
    adjusters = build_adjusters(rng, n_adjusters)
    coverages = build_coverages()
    policies = build_policies(rng, customers, n_policies)
    policy_coverages = build_policy_coverages(rng, policies, coverages)

    return {  # parent tables first
        "customers": customers,
        "coverages": coverages,
        "adjusters": adjusters,
        "policies": policies,
        "policy_coverages": policy_coverages,
    }