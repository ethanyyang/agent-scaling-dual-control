# Stage 1: Canonical Regression Reproduction

This directory records the Stage 1 reproduction of Kim et al.'s canonical
agent-scaling analysis. The source data are the freely released results in the
pinned `agent-scaling` v2.1.3 clone at commit
`358d67e24c616073127ce1a8b78d4b632162848c`.

Run from the project root:

```bash
agent-scaling/.venv/bin/python canonical_refit.py \
  --output-dir results/canonical-refit
```

## Reproduced results

- Canonical configurations: 260
- Training R-squared: 0.463295
- Adjusted R-squared: 0.427957
- Five-fold cross-validated R-squared: 0.372804 (SD 0.170166)
- `log_agents` coefficient: 0.040422
- `baseline_x_agents` coefficient: -0.235929
- Published 45% cutoff sign matches: 15/16 (93.75%)
- One-sided binomial p-value against chance: 0.000259

`regression_data.csv` contains one row per configuration. `sign_validation.csv`
is a separate model-by-benchmark aggregation for the published sign test.

## Threshold interpretation

The primary transfer test will use 0.45 because it is the authors' published
operational selection rule. The coefficient ratio reproduced here is 0.171333.
A direct inverse-standardization using the released feature scaler gives
0.476566, not exactly 0.45. Because `log_agents` and `baseline_x_agents` were
standardized as separate columns, treating their coefficient ratio as a
baseline z-score is not an algebraically exact raw-scale conversion.

We therefore preserve 0.45 as the pre-specified primary cutoff and record
0.476566 as a sensitivity cutoff. This distinction must not be changed after
the confirmatory tau2-bench data are collected.

