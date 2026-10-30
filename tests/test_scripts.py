import importlib.util
from pathlib import Path

from generator.anomalies import check_expected_failures
from generator.detect import detect, score_detection
from generator.export import export_dataset
from generator.report import build_report
from generator.validate import validate_all

ROOT = Path(__file__).resolve().parent.parent
RUN = {"seed": 20261022, "policies": 2000, "claims": 1000}


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def export(dataset, folder):
    clean, final, gt = dataset
    clean_results, final_results = validate_all(clean), validate_all(final)
    problems = check_expected_failures(final_results, gt)
    scores, mismatches = score_detection(gt, detect(final))
    text = build_report(RUN, final, gt, clean_results, final_results, problems, scores, mismatches)
    export_dataset(folder, final, gt, RUN, (text, clean_results, final_results))


def test_demo_runs_on_an_exported_dataset(dataset, tmp_path, capsys):
    export(dataset, tmp_path)
    load_script("demo").main(tmp_path)
    out = capsys.readouterr().out
    assert "CLAIM_PAID_TWICE" in out
    assert "checks passed" in out


def test_manifest_verification_passes_then_detects_tampering(dataset, tmp_path):
    export(dataset, tmp_path)
    verify = load_script("verify_manifest").verify
    assert verify(tmp_path) == []
    with open(tmp_path / "csv" / "claims.csv", "a", encoding="utf-8") as f:
        f.write("x\n")
    assert verify(tmp_path) == ["changed: csv/claims.csv"]