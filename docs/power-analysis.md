# Pre-registered power analysis — output of `power_sim.py --reps 400 --seed 1` (2026-09-02)

Inputs: task heterogeneity fitted to the pilot and gate per_episode.csv (beta-binomial); planned design; assumed cell baselines in the script (x-axis placement only). No API calls.

```
Task-heterogeneity fit (beta-binomial):
  pilot: mean=0.400 kappa=1.39
  gate: mean=0.807 kappa=0.42
  using kappa=0.91 (smaller = more task heterogeneity)

H1 slope test, x-axis = naive: power (fraction of worlds where slope CI excludes 0, negative side)
  scenario                                           b=+0.00 b=-0.10 b=-0.20 b=-0.30 b=-0.40   sign-acc@b=-0.3  informative-cells@b=-0.3
  27 cells, 50 tasks, 3 seeds (pre-registered)         0.19    0.78    1.00    1.00    1.00        0.84             0.39
  27 cells, 50 tasks, 5 seeds                          0.23    0.91    1.00    1.00    1.00        0.86             0.47
  18 cells (drop qwen), 50 tasks, 3 seeds              0.20    0.67    0.99    1.00    1.00        0.87             0.49
  27 cells, 114-task full splits, 3 seeds              0.28    0.98    1.00    1.00    1.00        0.88             0.52
  (column b=+0.00 is the false-positive rate; target <= 0.05)

H1 slope test, x-axis = split: power (fraction of worlds where slope CI excludes 0, negative side)
  scenario                                           b=+0.00 b=-0.10 b=-0.20 b=-0.30 b=-0.40   sign-acc@b=-0.3  informative-cells@b=-0.3
  27 cells, 50 tasks, 3 seeds (pre-registered)         0.07    0.48    0.87    0.99    1.00        0.82             0.32
  27 cells, 50 tasks, 5 seeds                          0.11    0.70    0.99    1.00    1.00        0.85             0.44
  18 cells (drop qwen), 50 tasks, 3 seeds              0.07    0.35    0.80    0.97    1.00        0.86             0.42
  27 cells, 114-task full splits, 3 seeds              0.12    0.81    0.99    1.00    1.00        0.86             0.46
  (column b=+0.00 is the false-positive rate; target <= 0.05)

H1 slope test, x-axis = loo: power (fraction of worlds where slope CI excludes 0, negative side)
  scenario                                           b=+0.00 b=-0.10 b=-0.20 b=-0.30 b=-0.40   sign-acc@b=-0.3  informative-cells@b=-0.3
  27 cells, 50 tasks, 3 seeds (pre-registered)         0.07    0.40    0.77    0.95    1.00        0.84             0.38
  27 cells, 50 tasks, 5 seeds                          0.10    0.51    0.93    0.99    1.00        0.86             0.47
  18 cells (drop qwen), 50 tasks, 3 seeds              0.07    0.37    0.74    0.94    0.98        0.88             0.50
  27 cells, 114-task full splits, 3 seeds              0.09    0.70    0.98    1.00    1.00        0.88             0.51
  (column b=+0.00 is the false-positive rate; target <= 0.05)

Replica of Kim et al. validation (16 cells, 20 tasks, 1 run), true b=-0.30:
  expected sign-match accuracy = 0.74; P(accuracy >= 15/16) = 0.04
  under NULL (b=0): expected accuracy = 0.60; P(>= 15/16) = 0.01

H4a wrongful-write-rate test (WW/failures vs baseline; 27 cells, 50 tasks, 3 seeds):
  power (effect as in §0 anchors) = 1.00; false-positive rate = 0.03
```
