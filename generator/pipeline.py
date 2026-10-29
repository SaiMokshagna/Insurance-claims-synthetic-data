"""The whole generation pipeline in one place (used by the CLI and by the tests)."""
import numpy as np

from generator.anomalies import build_ground_truth, inject_defects, scale_plan
from generator.master import generate_master
from generator.transactions import generate_transactions
from generator.workflow import generate_workflow


def build_dataset(seed, n_policies, n_claims):
    """Return (clean tables, final tables with defects, ground truth)."""
    rng = np.random.default_rng(seed)           # the ONE RNG for the whole run
    plan = scale_plan(n_claims)
    labels_a = {}
    master = generate_master(rng, n_policies, n_claims)
    tables = {**master, **generate_transactions(rng, master, n_claims, plan=plan, labels=labels_a)}
    tables.update(generate_workflow(rng, tables))
    final, labels_b = inject_defects(rng, tables, plan)
    return tables, final, build_ground_truth(final, labels_a, labels_b)