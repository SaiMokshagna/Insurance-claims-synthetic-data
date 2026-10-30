"""Prove reproducibility.

Runs the generator twice with the same seed, each in its own process, and compares row
counts and SHA-256 checksums. A third run with a different seed is a control: it must
differ, which shows the comparison can fail. Writes docs/reproducibility_report.md.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261022


def run(seed, out_dir):
    cmd = [sys.executable, "-m", "generator", "--seed", str(seed), "--out", str(out_dir)]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    manifest_path = Path(out_dir) / "manifest.json"
    if not manifest_path.exists():
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])
        sys.exit(f"The generator did not finish for seed {seed}.")
    return json.loads(manifest_path.read_text(encoding="utf-8")), result.returncode


def compare(a, b):
    fa = {f["path"]: f["sha256"] for f in a["files"]}
    fb = {f["path"]: f["sha256"] for f in b["files"]}
    return [(p, fa.get(p, "missing"), fb.get(p, "missing")) for p in sorted(set(fa) | set(fb))]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        print("Run 1 (seed %d) ..." % SEED)
        a, code_a = run(SEED, tmp / "run1")
        print("Run 2 (seed %d) ..." % SEED)
        b, code_b = run(SEED, tmp / "run2")
        print("Control run (seed %d) ..." % (SEED + 1))
        c, code_c = run(SEED + 1, tmp / "control")

    rows = compare(a, b)
    identical_files = all(x == y for _, x, y in rows)
    identical_counts = a["tables"] == b["tables"]
    control_differs = sum(1 for _, x, y in compare(a, c) if x != y)
    ok = identical_files and identical_counts and code_a == 0 and code_b == 0 and control_differs > 0

    print(f"\nFiles compared: {len(rows)}")
    print(f"Identical checksums (run 1 vs run 2): {sum(x == y for _, x, y in rows)}/{len(rows)}")
    print(f"Row counts identical: {identical_counts}")
    print(f"Control (different seed): {control_differs}/{len(rows)} files differ")
    if code_c != 0:
        print("  (the control run reported validation problems; informational only)")
    print("RESULT:", "REPRODUCIBLE" if ok else "NOT REPRODUCIBLE")

    lines = [
        "# Reproducibility report", "",
        f"Command: `{a['command']}`", "",
        f"Environment: Python {a['environment']['python']}, pandas {a['environment']['pandas']}, "
        f"numpy {a['environment']['numpy']}.", "",
        "The generator was run twice with the same seed, each time in a separate process. "
        "A third run with a different seed is a control.", "",
        "## Result", "",
        f"- Run 1 vs run 2: **{sum(x == y for _, x, y in rows)} of {len(rows)} files identical**, "
        f"row counts identical: **{identical_counts}**.",
        f"- Control (seed {SEED + 1}): {control_differs} of {len(rows)} files differ, "
        "so the comparison does detect changes.", "",
        "## Row counts", "", "| Table | Run 1 | Run 2 |", "|---|---|---|",
    ]
    for name in a["tables"]:
        lines.append(f"| {name} | {a['tables'][name]['rows']} | {b['tables'][name]['rows']} |")
    lines += ["", "## Checksums (first 16 characters of SHA-256; the manifest has the full values)", "",
              "| File | Run 1 | Run 2 | Match |", "|---|---|---|---|"]
    for path, x, y in rows:
        lines.append(f"| {path} | {x[:16]} | {y[:16]} | {'yes' if x == y else 'NO'} |")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "reproducibility_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("Wrote docs/reproducibility_report.md")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()