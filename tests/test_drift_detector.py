import numpy as np
import pandas as pd
from vortex.engine.drift_detector import FeatureDriftDetector


def test_psi_identical_distributions():
    np.random.seed(42)
    base = np.random.normal(loc=100, scale=15, size=1000)
    target = np.random.normal(loc=100, scale=15, size=1000)

    psi = FeatureDriftDetector.calculate_psi(base, target)
    assert psi < 0.10, f"Expected stable PSI < 0.10, got {psi}"


def test_psi_drifted_distribution():
    np.random.seed(42)
    base = np.random.normal(loc=100, scale=15, size=1000)
    # Significant mean shift from 100 to 140
    drifted = np.random.normal(loc=140, scale=25, size=1000)

    psi = FeatureDriftDetector.calculate_psi(base, target=drifted)
    assert psi >= 0.25, f"Expected critical drift PSI >= 0.25, got {psi}"


def test_ks_test():
    np.random.seed(42)
    base = np.random.exponential(scale=50, size=500)
    shifted = np.random.exponential(scale=120, size=500)

    res = FeatureDriftDetector.calculate_ks_test(base, shifted)
    assert res["is_drift"] is True
    assert res["p_value"] < 0.05
