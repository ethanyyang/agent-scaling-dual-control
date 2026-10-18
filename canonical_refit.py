#!/usr/bin/env python3
"""Refit the canonical 260-configuration agent-scaling regression.

This wrapper leaves the pinned ``agent-scaling`` clone untouched. It reuses
the authors' released feature engineering and model formula, removes the later
Gemini 3 addition, and reproduces the paper's 260-row analysis plus its 15-of-16
threshold sign check.

No model API calls, Docker containers, or benchmark downloads are required.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import binomtest
from statsmodels.stats.multitest import multipletests


PROJECT_ROOT = Path(__file__).resolve().parent
UPSTREAM_ROOT = PROJECT_ROOT / "agent-scaling"
UPSTREAM_SCRIPT = (
    UPSTREAM_ROOT / "scripts" / "extended_mixed_effects_6benchmarks.py"
)
UPSTREAM_RESULTS = (
    UPSTREAM_ROOT / "scripts" / "per_instance_results_swe_tb.csv"
)

EXCLUDED_MODEL = "gemini-3-flash-preview"
PUBLISHED_RAW_CUTOFF = 0.45

EXPECTED_ORIGINAL_CONFIGS = 180
EXPECTED_RELEASED_NEW_CONFIGS = 90
EXPECTED_CANONICAL_NEW_CONFIGS = 80
EXPECTED_TOTAL_CONFIGS = 260
EXPECTED_SIGN_MATCHES = 15


def load_upstream_analysis() -> ModuleType:
    """Import the pinned authors' analysis module directly from its file."""
    if not UPSTREAM_SCRIPT.is_file() or not UPSTREAM_RESULTS.is_file():
        raise FileNotFoundError(
            "The pinned agent-scaling clone is missing. Expected:\n"
            f"  {UPSTREAM_SCRIPT}\n"
            f"  {UPSTREAM_RESULTS}\n\n"
            "Clone tag v2.1.3 into the project root before running this script."
        )

    sys.path.insert(0, str(UPSTREAM_SCRIPT.parent))
    spec = importlib.util.spec_from_file_location(
        "agent_scaling_released_analysis", UPSTREAM_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not create an import specification for {UPSTREAM_SCRIPT}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_value(*args: str) -> str:
    """Return a Git provenance value for the upstream clone."""
    completed = subprocess.run(
        ["git", "-C", str(UPSTREAM_ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def package_versions() -> dict[str, str]:
    """Record statistical package versions that can affect the fit."""
    return {
        package: importlib.metadata.version(package)
        for package in (
            "numpy",
            "pandas",
            "scikit-learn",
            "scipy",
            "statsmodels",
        )
    }


def robust_p_value(model: Any, scaled: pd.DataFrame, parameter: str) -> float:
    """Calculate the dataset-clustered p-value for one fitted parameter."""
    robust = model.get_robustcov_results(
        cov_type="cluster",
        groups=scaled["dataset"],
        use_t=True,
    )
    parameter_names = list(model.params.index)
    return float(robust.pvalues[parameter_names.index(parameter)])


def holm_p_value(model: Any, parameter: str) -> float:
    """Return the Holm-Bonferroni-adjusted p-value across 19 predictors."""
    raw_p_values = model.pvalues.drop("Intercept")
    adjusted = multipletests(raw_p_values.to_numpy(), method="holm")[1]
    return float(adjusted[list(raw_p_values.index).index(parameter)])


def build_sign_validation(canonical_new_rows: list[list[Any]]) -> pd.DataFrame:
    """Reproduce the published 15-of-16 threshold sign validation."""
    new_results = pd.DataFrame(
        canonical_new_rows,
        columns=[
            "dataset",
            "architecture",
            "provider",
            "model",
            "performance",
        ],
    )
    pivot = new_results.pivot(
        index=["dataset", "model"],
        columns="architecture",
        values="performance",
    )

    sas = pivot["single-agent"]
    best_mas = pivot.drop(columns="single-agent").max(axis=1)
    validation = pd.DataFrame(
        {
            "sas": sas,
            "best_mas": best_mas,
            "delta": best_mas - sas,
            # At the cutoff, the rule predicts that MAS gains have saturated.
            "predicted_gain": sas < PUBLISHED_RAW_CUTOFF,
            "observed_gain": best_mas > sas,
        }
    ).reset_index()
    validation["match"] = (
        validation["predicted_gain"] == validation["observed_gain"]
    )
    return validation.sort_values(["dataset", "model"]).reset_index(drop=True)


def check_close(
    name: str,
    actual: float,
    expected: float,
    tolerance: float,
) -> None:
    """Fail loudly when the pinned reproduction drifts unexpectedly."""
    if not np.isclose(actual, expected, atol=tolerance, rtol=0.0):
        raise RuntimeError(
            f"Reproduction check failed for {name}: "
            f"expected {expected:.6f} ± {tolerance:.6f}, "
            f"got {actual:.6f}"
        )


def refit() -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """Return the fit summary, 260-row regression data, and validation table."""
    analysis = load_upstream_analysis()

    original_rows = list(analysis.ORIGINAL_DATA)
    released_new_rows = analysis.load_new_data(str(UPSTREAM_RESULTS))
    canonical_new_rows = [
        row for row in released_new_rows if row[3] != EXCLUDED_MODEL
    ]

    expected_counts = (
        ("embedded", len(original_rows), EXPECTED_ORIGINAL_CONFIGS),
        ("released SWE/Terminal", len(released_new_rows), EXPECTED_RELEASED_NEW_CONFIGS),
        ("canonical SWE/Terminal", len(canonical_new_rows), EXPECTED_CANONICAL_NEW_CONFIGS),
    )
    for label, actual, expected in expected_counts:
        if actual != expected:
            raise RuntimeError(
                f"Expected {expected} {label} configurations, found {actual}"
            )

    canonical_rows = original_rows + canonical_new_rows
    raw, _ = analysis.build_dataframe(canonical_rows)
    scaled, scaler = analysis.standardize(raw, analysis.FEATURE_COLS)
    model = analysis.smf.ols(analysis.FORMULA, data=scaled).fit()
    cv_scores = analysis.run_5fold_cv(
        scaled,
        analysis.FORMULA,
        analysis.FEATURE_COLS,
    )

    beta_agents = float(model.params["log_agents"])
    beta_interaction = float(model.params["baseline_x_agents"])
    beta_baseline = float(model.params["single_agent_baseline"])
    standardized_ratio = -beta_agents / beta_interaction

    baseline_index = analysis.FEATURE_COLS.index("single_agent_baseline")
    baseline_mean = float(scaler.mean_[baseline_index])
    baseline_std = float(scaler.scale_[baseline_index])
    naive_inverse_threshold = baseline_mean + standardized_ratio * baseline_std

    sign_validation = build_sign_validation(canonical_new_rows)
    sign_matches = int(sign_validation["match"].sum())
    sign_cells = int(len(sign_validation))

    summary: dict[str, Any] = {
        "provenance": {
            "upstream_repository": "https://github.com/ybkim95/agent-scaling",
            "upstream_tag": git_value("describe", "--tags", "--exact-match"),
            "upstream_commit": git_value("rev-parse", "HEAD"),
            "excluded_later_model": EXCLUDED_MODEL,
            "package_versions": package_versions(),
        },
        "data": {
            "embedded_original_configurations": len(original_rows),
            "released_swe_terminal_configurations": len(released_new_rows),
            "canonical_swe_terminal_configurations": len(canonical_new_rows),
            "canonical_total_configurations": len(canonical_rows),
        },
        "fit": {
            "training_r_squared": float(model.rsquared),
            "adjusted_r_squared": float(model.rsquared_adj),
            "cross_validated_r_squared_mean": float(np.mean(cv_scores)),
            "cross_validated_r_squared_std": float(np.std(cv_scores)),
            "observations": int(model.nobs),
            "parameters_including_intercept": int(len(model.params)),
        },
        "key_coefficients": {
            "log_agents": beta_agents,
            "baseline_x_agents": beta_interaction,
            "single_agent_baseline": beta_baseline,
            "single_agent_baseline_naive_p": float(
                model.pvalues["single_agent_baseline"]
            ),
            "single_agent_baseline_cluster_robust_p": robust_p_value(
                model,
                scaled,
                "single_agent_baseline",
            ),
            "single_agent_baseline_holm_p": holm_p_value(
                model,
                "single_agent_baseline",
            ),
            "baseline_x_agents_naive_p": float(
                model.pvalues["baseline_x_agents"]
            ),
            "baseline_x_agents_cluster_robust_p": robust_p_value(
                model,
                scaled,
                "baseline_x_agents",
            ),
        },
        "threshold": {
            "published_operational_raw_cutoff": PUBLISHED_RAW_CUTOFF,
            "coefficient_ratio": standardized_ratio,
            "baseline_mean": baseline_mean,
            "baseline_population_std": baseline_std,
            "naive_inverse_z_threshold": naive_inverse_threshold,
            "caveat": (
                "The coefficient ratio is the authors' selection-rule quantity. "
                "Because log_agents and baseline_x_agents are standardized "
                "separately, treating that ratio as a baseline z-score is an "
                "interpretation, not an algebraically exact raw-scale "
                "marginal-effect conversion."
            ),
        },
        "sign_validation": {
            "cutoff_rule": "predict MAS gain only when SAS < 0.45",
            "matches": sign_matches,
            "cells": sign_cells,
            "accuracy": sign_matches / sign_cells,
            "binomial_one_sided_p_vs_half": float(
                binomtest(
                    sign_matches,
                    sign_cells,
                    0.5,
                    alternative="greater",
                ).pvalue
            ),
            "binomial_two_sided_p_vs_half": float(
                binomtest(
                    sign_matches,
                    sign_cells,
                    0.5,
                    alternative="two-sided",
                ).pvalue
            ),
        },
    }

    if len(canonical_rows) != EXPECTED_TOTAL_CONFIGS:
        raise RuntimeError(
            f"Expected {EXPECTED_TOTAL_CONFIGS} total configurations, "
            f"found {len(canonical_rows)}"
        )
    check_close(
        "cross-validated R²",
        summary["fit"]["cross_validated_r_squared_mean"],
        0.372804,
        0.000005,
    )
    check_close(
        "log_agents coefficient",
        beta_agents,
        0.040422,
        0.000005,
    )
    check_close(
        "baseline_x_agents coefficient",
        beta_interaction,
        -0.235929,
        0.000005,
    )
    check_close(
        "coefficient ratio",
        standardized_ratio,
        0.171333,
        0.000005,
    )
    if sign_matches != EXPECTED_SIGN_MATCHES or sign_cells != 16:
        raise RuntimeError(
            f"Expected {EXPECTED_SIGN_MATCHES}/16 sign matches, "
            f"got {sign_matches}/{sign_cells}"
        )

    return summary, raw, sign_validation


def write_outputs(
    output_dir: Path,
    summary: dict[str, Any],
    regression_data: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:
    """Write the full regression dataset and reproduction artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    regression_data.to_csv(output_dir / "regression_data.csv", index=False)
    validation.to_csv(output_dir / "sign_validation.csv", index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Optionally write summary.json, regression_data.csv, and "
            "sign_validation.csv to this directory."
        ),
    )
    args = parser.parse_args()

    summary, regression_data, validation = refit()
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("\nSign-validation cells:\n")
    print(validation.to_string(index=False))

    if args.output_dir is not None:
        write_outputs(args.output_dir, summary, regression_data, validation)
        print(f"\nWrote reproduction artifacts to {args.output_dir.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
