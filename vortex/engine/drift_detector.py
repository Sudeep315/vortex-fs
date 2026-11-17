from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy import stats


class FeatureDriftDetector:
    """
    Statistical engine for monitoring feature quality, distribution shifts,
    and alerting on production data drift between training baseline and live inference.
    """

    @staticmethod
    def calculate_psi(baseline: np.ndarray, target: np.ndarray, num_bins: int = 10) -> float:
        """
        Calculates Population Stability Index (PSI).
        PSI < 0.1: Stable / No drift
        0.1 <= PSI < 0.25: Moderate drift
        PSI >= 0.25: Significant drift (Action needed)
        """
        baseline = baseline[~np.isnan(baseline)]
        target = target[~np.isnan(target)]

        if len(baseline) == 0 or len(target) == 0:
            return 0.0

        # Create quantile-based bins from baseline
        quantiles = np.linspace(0, 100, num_bins + 1)
        bins = np.percentile(baseline, quantiles)
        bins = np.unique(bins)

        if len(bins) < 2:
            return 0.0

        # Frequency in baseline and target
        base_counts, _ = np.histogram(baseline, bins=bins)
        target_counts, _ = np.histogram(target, bins=bins)

        # Convert to percentages with epsilon smoothing to prevent div by zero
        eps = 1e-4
        base_pct = (base_counts + eps) / (len(baseline) + eps * len(base_counts))
        target_pct = (target_counts + eps) / (len(target) + eps * len(target_counts))

        # PSI formula = sum((target% - base%) * ln(target% / base%))
        psi_value = np.sum((target_pct - base_pct) * np.log(target_pct / base_pct))
        return float(psi_value)

    @staticmethod
    def calculate_ks_test(baseline: np.ndarray, target: np.ndarray) -> Dict[str, float]:
        """
        Two-sample Kolmogorov-Smirnov test to detect whether two underlying
        one-dimensional distributions differ significantly.
        """
        baseline = baseline[~np.isnan(baseline)]
        target = target[~np.isnan(target)]

        if len(baseline) < 5 or len(target) < 5:
            return {"ks_statistic": 0.0, "p_value": 1.0, "is_drift": False}

        ks_res = stats.ks_2samp(baseline, target)
        # p_value < 0.05 indicates statistically significant distribution shift
        return {
            "ks_statistic": round(float(ks_res.statistic), 4),
            "p_value": round(float(ks_res.pvalue), 6),
            "is_drift": bool(ks_res.pvalue < 0.05),
        }

    @classmethod
    def profile_feature_series(cls, series: pd.Series) -> Dict[str, Any]:
        """Calculates rich statistical summary metrics for a feature."""
        clean = series.dropna()
        n_total = len(series)
        n_missing = series.isna().sum()

        if len(clean) == 0:
            return {
                "count": 0,
                "missing_count": int(n_missing),
                "missing_pct": 100.0,
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "p25": 0.0,
                "median": 0.0,
                "p75": 0.0,
                "max": 0.0,
            }

        return {
            "count": int(len(clean)),
            "missing_count": int(n_missing),
            "missing_pct": round(float(n_missing / n_total * 100.0), 2) if n_total > 0 else 0.0,
            "mean": round(float(clean.mean()), 4),
            "std": round(float(clean.std()), 4) if len(clean) > 1 else 0.0,
            "min": round(float(clean.min()), 4),
            "p25": round(float(clean.quantile(0.25)), 4),
            "median": round(float(clean.median()), 4),
            "p75": round(float(clean.quantile(0.75)), 4),
            "max": round(float(clean.max()), 4),
        }

    @classmethod
    def compare_distributions(
        cls,
        baseline_df: pd.DataFrame,
        current_df: pd.DataFrame,
        feature_cols: List[str],
    ) -> Dict[str, Any]:
        """
        Runs comprehensive drift analysis across multiple features.
        """
        report: Dict[str, Any] = {}

        for col in feature_cols:
            if col not in baseline_df.columns or col not in current_df.columns:
                continue

            base_vals = pd.to_numeric(baseline_df[col], errors="coerce").values
            curr_vals = pd.to_numeric(current_df[col], errors="coerce").values

            psi = cls.calculate_psi(base_vals, curr_vals)
            ks_info = cls.calculate_ks_test(base_vals, curr_vals)
            base_profile = cls.profile_feature_series(baseline_df[col])
            curr_profile = cls.profile_feature_series(current_df[col])

            severity = "STABLE"
            if psi >= 0.25 or (ks_info["is_drift"] and psi > 0.15):
                severity = "DRIFT_CRITICAL"
            elif psi >= 0.10:
                severity = "DRIFT_MODERATE"

            report[col] = {
                "feature": col,
                "psi": round(psi, 4),
                "ks_statistic": ks_info["ks_statistic"],
                "ks_p_value": ks_info["p_value"],
                "severity": severity,
                "baseline_profile": base_profile,
                "current_profile": curr_profile,
            }

        return report
