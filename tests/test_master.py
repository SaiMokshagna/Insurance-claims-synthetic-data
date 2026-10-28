import numpy as np

from generator.master import generate_master
from generator.validate import validate_master


def make(seed=20261022, policies=200, claims=100):
    return generate_master(np.random.default_rng(seed), policies, claims)


def test_row_counts():
    t = make()
    assert len(t["policies"]) == 200
    assert len(t["customers"]) == 120      # 60% of 200
    assert len(t["adjusters"]) == 20       # minimum of 20


def test_same_seed_gives_identical_tables():
    a, b = make(), make()
    for name in a:
        assert a[name].equals(b[name]), name


def test_different_seed_gives_different_tables():
    assert not make(seed=1)["policies"].equals(make(seed=2)["policies"])


def test_validation_passes():
    failed = [r for r in validate_master(make()) if not r["passed"]]
    assert failed == []