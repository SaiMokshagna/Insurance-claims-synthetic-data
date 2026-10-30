"""Check that every file in a dataset folder matches the checksums in its manifest.json.
Usage:  python scripts/verify_manifest.py [data_folder]      (default: data)
"""
import hashlib
import json
import sys
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(root):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    problems = []
    for entry in manifest["files"]:
        path = root / entry["path"]
        if not path.exists():
            problems.append(f"missing: {entry['path']}")
        elif sha256_file(path) != entry["sha256"]:
            problems.append(f"changed: {entry['path']}")
    return problems


def main(root="data"):
    problems = verify(root)
    manifest = json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))
    print(f"Checked {len(manifest['files'])} files against {Path(root) / 'manifest.json'}")
    if problems:
        for p in problems:
            print("  PROBLEM", p)
        sys.exit(1)
    print("All checksums match.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data")