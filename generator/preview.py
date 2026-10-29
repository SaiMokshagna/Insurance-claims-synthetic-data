"""Dry run: apply the rules engine to every baseline claim. Writes nothing.
Run with:  python -m generator.preview"""
import numpy as np
import pandas as pd

from generator.config import (
    DEFAULT_CLAIMS, DEFAULT_POLICIES, DEFAULT_SEED,
    FRAUD_REFERRAL_SCORE, REVIEW_SCORE,
)
from generator.context import build_claim_contexts
from generator.master import generate_master
from generator.rules import evaluate_claim
from generator.transactions import generate_transactions


def main():
    rng = np.random.default_rng(DEFAULT_SEED)
    master = generate_master(rng, DEFAULT_POLICIES, DEFAULT_CLAIMS)
    tables = {**master, **generate_transactions(rng, master, DEFAULT_CLAIMS)}

    results = {cid: evaluate_claim(ctx) for cid, ctx in build_claim_contexts(tables).items()}
    df = pd.DataFrame.from_dict(results, orient="index")

    print("Eligibility decisions:")
    print(df["eligibility_decision"].value_counts().to_string())
    print("\nReason codes:")
    print(df["reason_code"].value_counts().to_string())
    print("\nRouting:")
    print(df["routing_decision"].fillna("NONE (pending documents)").value_counts().to_string())
    print("\nFraud risk score:")
    print(df["fraud_risk_score"].describe().round(1).to_string())
    print(f"  claims with score >= {REVIEW_SCORE}: {(df['fraud_risk_score'] >= REVIEW_SCORE).sum()}")
    print(f"  claims with score >= {FRAUD_REFERRAL_SCORE}: {(df['fraud_risk_score'] >= FRAUD_REFERRAL_SCORE).sum()}")
    print(f"\nTotal reserve: {df['reserve_amount'].sum():,.2f}")
    print(f"Duplicates found in baseline: {int(df['duplicate_suspected'].sum())}")


if __name__ == "__main__":
    main()