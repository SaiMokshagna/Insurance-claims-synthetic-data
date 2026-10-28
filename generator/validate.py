"""Validation checks. Each check returns {check, passed, bad_rows}."""
import numpy as np
import pandas as pd

from generator.config import CLAIM_TYPES, PRODUCTS, REFERENCE_DATE
from generator.ids import ID_PATTERNS
from generator.reference_data import ALL_EXCLUSIONS

POLICY_STATUSES = ["IN_FORCE", "EXPIRED", "LAPSED", "CANCELLED"]
RISK_TIERS = ["LOW", "MEDIUM", "HIGH"]
SENIORITIES = ["JUNIOR", "SENIOR", "MANAGER"]


def _result(name, bad_count):
    return {"check": name, "passed": int(bad_count) == 0, "bad_rows": int(bad_count)}


def _unique(df, col, table):
    return _result(f"{table}.{col} is unique", df[col].duplicated().sum())


def _pattern(df, col, key, table):
    bad = ~df[col].astype(str).str.match(ID_PATTERNS[key])
    return _result(f"{table}.{col} matches ID format", bad.sum())


def _fk(child, col, parent, pcol, label):
    return _result(f"FK {label}", (~child[col].isin(parent[pcol])).sum())


def _enum(df, col, allowed, table):
    return _result(f"{table}.{col} has allowed values", (~df[col].isin(allowed)).sum())


def validate_master(t):
    c, cov, a = t["customers"], t["coverages"], t["adjusters"]
    p, pc = t["policies"], t["policy_coverages"]
    ref = pd.Timestamp(REFERENCE_DATE)
    r = []

    # --- customers ---
    r += [_unique(c, "customer_id", "customers"), _pattern(c, "customer_id", "customer", "customers"),
          _unique(c, "email", "customers"), _enum(c, "risk_tier", RISK_TIERS, "customers")]
    dob, since = pd.to_datetime(c["date_of_birth"]), pd.to_datetime(c["customer_since"])
    age = (ref - dob).dt.days / 365.25
    r.append(_result("customers: age between 18 and 85", ((age < 18) | (age > 85)).sum()))
    r.append(_result("customers: customer_since after 18th birthday and not in future",
                     (((since - dob).dt.days < 18 * 365) | (since > ref)).sum()))

    # --- coverages ---
    r += [_unique(cov, "coverage_id", "coverages"), _pattern(cov, "coverage_id", "coverage", "coverages"),
          _enum(cov, "product_code", PRODUCTS, "coverages"), _enum(cov, "coverage_type", CLAIM_TYPES, "coverages")]
    r.append(_result("coverages: default_deductible < default_limit",
                     (cov["default_deductible"] >= cov["default_limit"]).sum()))

    # --- adjusters ---
    r += [_unique(a, "adjuster_id", "adjusters"), _pattern(a, "adjuster_id", "adjuster", "adjusters"),
          _enum(a, "seniority", SENIORITIES, "adjusters"), _enum(a, "specialty", CLAIM_TYPES, "adjusters")]
    auth = a.groupby("seniority")["approval_authority"].agg(["min", "max"])
    ordered = (auth.loc["JUNIOR", "max"] < auth.loc["SENIOR", "min"]
               and auth.loc["SENIOR", "max"] < auth.loc["MANAGER", "min"])
    r.append(_result("adjusters: authority JUNIOR < SENIOR < MANAGER", 0 if ordered else 1))
    managers = set(a[(a["seniority"] == "MANAGER") & a["is_active"]]["specialty"])
    r.append(_result("adjusters: active manager exists for every claim type", len(set(CLAIM_TYPES) - managers)))

    # --- policies ---
    r += [_unique(p, "policy_id", "policies"), _pattern(p, "policy_id", "policy", "policies"),
          _fk(p, "customer_id", c, "customer_id", "policies.customer_id -> customers"),
          _enum(p, "product_code", PRODUCTS, "policies"), _enum(p, "status", POLICY_STATUSES, "policies")]
    r.append(_result("policies: product in policy_id equals product_code",
                     (p["policy_id"].str.split("-").str[1] != p["product_code"]).sum()))
    eff, exp = pd.to_datetime(p["effective_date"]), pd.to_datetime(p["expiry_date"])
    can, lap = pd.to_datetime(p["cancellation_date"]), pd.to_datetime(p["lapse_date"])
    r.append(_result("policies: effective_date < expiry_date", (eff >= exp).sum()))
    r.append(_result("policies: cancellation_date set iff CANCELLED",
                     ((p["status"] == "CANCELLED") != can.notna()).sum()))
    r.append(_result("policies: lapse_date set iff LAPSED",
                     ((p["status"] == "LAPSED") != lap.notna()).sum()))
    r.append(_result("policies: cancellation/lapse inside policy term",
                     ((can.notna() & ((can < eff) | (can > exp))) | (lap.notna() & ((lap < eff) | (lap > exp)))).sum()))
    expected = np.where(can.notna(), "CANCELLED", np.where(lap.notna(), "LAPSED",
                        np.where(exp < ref, "EXPIRED", "IN_FORCE")))
    r.append(_result("policies: status matches independent re-derivation", (p["status"].values != expected).sum()))
    m = p.merge(c[["customer_id", "customer_since"]], on="customer_id")
    r.append(_result("policies: effective_date not before customer_since",
                     (pd.to_datetime(m["effective_date"]) < pd.to_datetime(m["customer_since"])).sum()))

    # --- policy_coverages (bridge) ---
    r += [_unique(pc, "policy_coverage_id", "policy_coverages"),
          _pattern(pc, "policy_coverage_id", "policy_coverage", "policy_coverages"),
          _fk(pc, "policy_id", p, "policy_id", "policy_coverages.policy_id -> policies"),
          _fk(pc, "coverage_id", cov, "coverage_id", "policy_coverages.coverage_id -> coverages")]
    r.append(_result("policy_coverages: (policy_id, coverage_id) pair is unique",
                     pc.duplicated(["policy_id", "coverage_id"]).sum()))
    r.append(_result("policy_coverages: deductible < coverage_limit", (pc["deductible"] >= pc["coverage_limit"]).sum()))
    bad_excl = pc["exclusions"].fillna("").apply(
        lambda s: any(code not in ALL_EXCLUSIONS for code in s.split("|") if code))
    r.append(_result("policy_coverages: exclusion codes are allowed", bad_excl.sum()))
    pm = (pc.merge(p[["policy_id", "product_code", "effective_date", "expiry_date"]],
                   on="policy_id", suffixes=("", "_policy"))
            .merge(cov[["coverage_id", "product_code"]], on="coverage_id",
                   suffixes=("_policy", "_coverage")))
    r.append(_result("policy_coverages: coverage product matches policy product",
                     (pm["product_code_policy"] != pm["product_code_coverage"]).sum()))
    r.append(_result("policy_coverages: dates inside policy term",
                     ((pd.to_datetime(pm["effective_date"]) < pd.to_datetime(pm["effective_date_policy"])) |
                      (pd.to_datetime(pm["expiry_date"]) > pd.to_datetime(pm["expiry_date_policy"]))).sum()))
    return r


def print_report(results):
    for res in results:
        tag = "PASS" if res["passed"] else "FAIL"
        extra = "" if res["passed"] else f"  ({res['bad_rows']} bad rows)"
        print(f"[{tag}] {res['check']}{extra}")
    failed = sum(not res["passed"] for res in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return failed