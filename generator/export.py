from pathlib import Path


def write_tables(tables, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False,
                  float_format="%.2f", lineterminator="\n")