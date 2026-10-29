import pytest

from generator.pipeline import build_dataset


@pytest.fixture(scope="session")
def dataset():
    return build_dataset(20261022, 2000, 1000)     # (clean, final, ground_truth)