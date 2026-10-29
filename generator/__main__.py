import argparse
import sys
from pathlib import Path

from generator.anomalies import check_expected_failures
from generator.config import (
    DEFAULT_CLAIMS, DEFAULT_POLICIES, DEFAULT_SEED, REFERENCE_DATE,
)
from generator.export import write_ground_truth, write_tables
from generator.pipeline import build_dataset
from generator.validate import print_report, validate_all


def parse_args():
    parser = argparse.ArgumentParser(description="Synthetic insurance claims data generator")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--policies", type=int, default=DEFAULT_POLICIES)
    parser.add_argument("--claims", type=int, default=DEFAULT_CLAIMS)
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--verbose", action="store_true", help="print every validation check")
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"Seed: {args.seed} | Reference date: {REFERENCE_DATE}")
    clean, final, gt = build_dataset(args.seed, args.policies, args.claims)

    print("\nRow counts (final dataset):")
    for name, df in final.items():
        print(f"  {name}: {len(df)}")
    print(f"  ground_truth: {len(gt)}")

    print("\nGround truth labels:")
    print(gt.groupby(["origin", "issue_type"]).size().to_string())

    print("\nValidation of the CLEAN dataset (before Layer B defects):")
    failed_clean = print_report(validate_all(clean), args.verbose)

    print("\nValidation of the FINAL dataset (failures must match the injected defects):")
    results = validate_all(final)
    for res in results:
        if not res["passed"]:
            print(f"  [DEFECT] {res['check']} ({res['bad_rows']} bad rows)")
    problems = check_expected_failures(results, gt)
    if problems:
        print("  PROBLEMS:")
        for p in problems:
            print(f"    {p}")
    else:
        print("  Every failing check is explained by the ground truth.")

    write_tables(final, args.out)
    write_ground_truth(gt, args.out)
    print(f"\nCSV files written to {args.out.resolve()}")
    sys.exit(1 if failed_clean or problems else 0)


if __name__ == "__main__":
    main()