import argparse
import sys
from pathlib import Path

from generator.anomalies import check_expected_failures
from generator.config import (
    DEFAULT_CLAIMS, DEFAULT_POLICIES, DEFAULT_SEED, REFERENCE_DATE,
)
from generator.detect import detect, score_detection
from generator.export import write_ground_truth, write_tables
from generator.pipeline import build_dataset
from generator.report import build_report, write_report
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
    clean_results = validate_all(clean)
    failed_clean = print_report(clean_results, args.verbose)

    print("\nValidation of the FINAL dataset (failures must match the injected defects):")
    final_results = validate_all(final)
    for res in final_results:
        if not res["passed"]:
            print(f"  [DEFECT] {res['check']} ({res['bad_rows']} bad rows)")
    problems = check_expected_failures(final_results, gt)
    if problems:
        print("  PROBLEMS:")
        for p in problems:
            print(f"    {p}")
    else:
        print("  Every failing check is explained by the ground truth.")

    print("\nDetection run (detector sees only the tables, scored against ground_truth.csv):")
    scores, mismatches = score_detection(gt, detect(final))
    shown = scores[["issue_type", "support", "tp", "fp", "fn", "precision", "recall"]].round(3)
    print(shown.to_string(index=False))
    print(f"  Misclassified claims: {len(mismatches)}")

    write_tables(final, args.out)
    write_ground_truth(gt, args.out)
    run = {"seed": args.seed, "policies": args.policies, "claims": args.claims}
    text = build_report(run, final, gt, clean_results, final_results, problems, scores, mismatches)
    write_report(args.out, text, clean_results, final_results)
    print(f"\nFiles written to {args.out.resolve()} (tables, ground_truth.csv, "
          "validation_summary.md, validation_results.csv)")
    sys.exit(1 if failed_clean or problems or len(mismatches) else 0)


if __name__ == "__main__":
    main()