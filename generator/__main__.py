import argparse
import sys
from pathlib import Path

import numpy as np

from generator.config import (
    DEFAULT_CLAIMS, DEFAULT_POLICIES, DEFAULT_SEED, REFERENCE_DATE,
)
from generator.export import write_tables
from generator.master import generate_master
from generator.validate import print_report, validate_master


def parse_args():
    parser = argparse.ArgumentParser(description="Synthetic insurance claims data generator")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--policies", type=int, default=DEFAULT_POLICIES)
    parser.add_argument("--claims", type=int, default=DEFAULT_CLAIMS)
    parser.add_argument("--out", type=Path, default=Path("output"))
    return parser.parse_args()


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)  # the ONE RNG for the whole run

    print(f"Seed: {args.seed} | Reference date: {REFERENCE_DATE}")
    tables = generate_master(rng, args.policies, args.claims)

    print("\nRow counts:")
    for name, df in tables.items():
        print(f"  {name}: {len(df)}")
    print("\nPolicy status mix:")
    print(tables["policies"]["status"].value_counts().to_string())

    print("\nValidation:")
    failed = print_report(validate_master(tables))

    write_tables(tables, args.out)
    print(f"\nCSV files written to {args.out.resolve()}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()