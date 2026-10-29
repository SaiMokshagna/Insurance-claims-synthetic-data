import argparse
import sys
from pathlib import Path

import numpy as np

from generator.config import (
    DEFAULT_CLAIMS, DEFAULT_POLICIES, DEFAULT_SEED, REFERENCE_DATE,
)
from generator.export import write_tables
from generator.master import generate_master
from generator.transactions import generate_transactions
from generator.validate import (
    print_report, validate_master, validate_transactions, validate_workflow,
)
from generator.workflow import generate_workflow


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
    master = generate_master(rng, args.policies, args.claims)
    tables = {**master, **generate_transactions(rng, master, args.claims)}
    tables.update(generate_workflow(rng, tables))     # replaces claims with the updated status

    print("\nRow counts:")
    for name, df in tables.items():
        print(f"  {name}: {len(df)}")
    for title, col, table in [("Policy status mix", "status", "policies"),
                              ("Claim status mix", "current_status", "claims"),
                              ("Settlement status mix", "settlement_status", "settlements"),
                              ("Event counts by entity", "entity_type", "status_events")]:
        print(f"\n{title}:")
        print(tables[table][col].value_counts().to_string())

    print("\nValidation:")
    results = validate_master(tables) + validate_transactions(tables) + validate_workflow(tables)
    failed = print_report(results)

    write_tables(tables, args.out)
    print(f"\nCSV files written to {args.out.resolve()}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()