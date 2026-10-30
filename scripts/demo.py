"""A short tour of the dataset.
Usage:  python scripts/demo.py [data_folder]      (default: data)
"""
import json
import sys
from pathlib import Path

import pandas as pd


def main(root="data"):
    root = Path(root)

    def read(name):
        return pd.read_csv(root / "csv" / f"{name}.csv")

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    gt = pd.read_csv(root / "ground_truth" / "ground_truth.csv")
    claims, settlements = read("claims"), read("settlements")
    assessments, items, events = read("assessments"), read("claim_items"), read("status_events")

    print("1. THE DATASET")
    print(f"   Command: {manifest['command']}")
    for name, info in manifest["tables"].items():
        print(f"   {name:<20} {info['rows']:>7}")

    print("\n2. ONE NORMAL CLAIM, FROM SUBMISSION TO PAYMENT")
    paid = set(settlements.loc[settlements["settlement_status"] == "PAID", "claim_id"])
    normal = gt[gt["issue_type"] == "NONE"].merge(claims[["claim_id", "current_status"]], on="claim_id")
    normal = normal[(normal["current_status"] == "CLOSED") & normal["claim_id"].isin(paid)]
    cid = normal.iloc[0]["claim_id"]
    claim = claims[claims["claim_id"] == cid].iloc[0]
    claim_items = items[items["claim_id"] == cid]
    assessment = assessments[assessments["claim_id"] == cid].iloc[0]
    settlement = settlements[settlements["claim_id"] == cid].iloc[0]
    print(f"   {cid}: {claim['claim_type']}, submitted {claim['submitted_date']}, "
          f"claimed {claim['claimed_amount']:,.2f} from {len(claim_items)} item(s)")
    print(f"   Decision: {assessment['eligibility_decision']} ({assessment['reason_code']})")
    print(f"   Settlement {settlement['settlement_id']}: routing {settlement['routing_decision']}, "
          f"recommended {settlement['recommended_amount']:,.2f}, "
          f"deductible {settlement['deductible_applied']:,.2f}, paid on {settlement['paid_date']}")
    story = events[events["entity_id"].isin([cid, settlement["settlement_id"]])].sort_values("event_id")
    print(story[["event_ts", "entity_type", "event_type", "from_status", "to_status"]].to_string(index=False))

    print("\n3. INJECTED EDGE CASES (one example of each, from the ground truth)")
    injected = gt[gt["origin"] == "INJECTED"].groupby("issue_type").head(1).sort_values("issue_type")
    for r in injected.itertuples():
        print(f"   {r.issue_type:<34} {r.claim_id}  {r.notes}")
    twice = gt[gt["issue_type"] == "CLAIM_PAID_TWICE"].iloc[0]["claim_id"]
    print(f"\n   Evidence for {twice} (paid twice):")
    cols = ["settlement_id", "settlement_status", "approved_amount", "approved_date", "paid_date"]
    print(settlements[settlements["claim_id"] == twice][cols].to_string(index=False))
    over = gt[gt["issue_type"] == "SETTLEMENT_EXCEEDS_LIMIT"].iloc[0]["claim_id"]
    row = settlements[settlements["claim_id"] == over].iloc[0]
    print(f"\n   Evidence for {over}: approved {row['approved_amount']:,.2f} "
          f"against a coverage limit of {row['limit_applied']:,.2f}")

    print("\n4. VALIDATION")
    v = pd.read_csv(root / "reports" / "validation_results.csv")
    clean = v[v["dataset"] == "CLEAN"]
    print(f"   Clean dataset: {int(clean['passed'].sum())}/{len(clean)} checks passed")
    print("   After defects are injected, these checks fail, and each is explained by the labels:")
    failing = v[(v["dataset"] == "FINAL") & (~v["passed"])]
    for r in failing.itertuples():
        print(f"   [DEFECT] {r.check} ({r.bad_rows} bad rows)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data")