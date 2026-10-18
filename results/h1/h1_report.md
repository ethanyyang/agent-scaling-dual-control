# H1 results (ANALYSIS.md section 1)

Primary fit: 12 cells, WLS with family and domain fixed effects, inverse task-cluster variance weights, dof 7.

- slope b = -0.413, 95% CI [-1.505, +0.679] (t); bootstrap CI [-0.713, -0.055]
- permutation p (within family, 10000): two-sided 0.4311; one-sided (negative) 0.2103
- H1 supported (slope < 0, CI excludes 0, permutation p < 0.05): False
- crossing x0 = -0.012, task-cluster bootstrap 95% CI [-2.423, 0.307]; reading: no crossing (slope CI covers zero)
- intercept at the mean fixed effect -0.005; coefficients {"intercept": 0.2744, "x": -0.4128, "family_Google": -0.2641, "domain_retail": -0.2442, "domain_telecom": -0.1979}

Family-by-x interaction (x*family_Google): -0.744, 95% CI [-3.069, +1.582], dof 6; slope OpenAI -0.129, Google -0.873

Robustness forms:

- split_seed_12 (n=12, dof 7): slope -0.443, 95% CI [-0.954, +0.069]
- split_seed_13 (n=13, dof 7): slope -0.443, 95% CI [-0.954, +0.069]
- logit_gain (n=12, dof 7): slope -1.606, 95% CI [-4.965, +1.753]  (slope in logit units per unit of x)
- relative_gain (n=12, dof 7): slope -0.347, 95% CI [-1.396, +0.702]  (slope in relative-gain units per unit of x)
- naive_12 (n=12, dof 7): slope -0.547, 95% CI [-1.157, +0.063]  (descriptive only: x shares episodes with gain (19 to 28% false-positive rate in power_sim.py))
- naive_13 (n=13, dof 7): slope -0.547, 95% CI [-1.157, +0.063]  (descriptive only: x shares episodes with gain (19 to 28% false-positive rate in power_sim.py))

Cells (pass^1 as fractions):

| family | model | domain | S1 | M1 | gain | SE | LODO x | primary |
|---|---|---|---:|---:|---:|---:|---:|---|
| Google | gemini-3.1-flash-lite | airline | 0.787 | 0.627 | -0.160 | 0.042 | 0.557 | True |
| Google | gemini-3.1-flash-lite | retail | 0.773 | 0.413 | -0.360 | 0.061 | 0.563 | True |
| Google | gemini-3.1-flash-lite | telecom | 0.340 | 0.120 | -0.220 | 0.048 | 0.780 | True |
| Google | gemini-3-flash | airline | 0.807 | 0.553 | -0.253 | 0.060 | 0.857 | True |
| Google | gemini-3-flash | retail | 0.800 | 0.253 | -0.547 | 0.059 | 0.860 | True |
| Google | gemini-3-flash | telecom | 0.913 | 0.107 | -0.807 | 0.036 | 0.803 | True |
| OpenAI | gpt-5-nano | airline | 0.427 | 0.453 | +0.027 | 0.051 | 0.503 | True |
| OpenAI | gpt-5-nano | retail | 0.680 | 0.447 | -0.233 | 0.051 | 0.377 | True |
| OpenAI | gpt-5-nano | telecom | 0.327 | 0.193 | -0.133 | 0.036 | 0.553 | True |
| OpenAI | gpt-5-mini | airline | 0.747 | 0.580 | -0.167 | 0.053 | 0.767 | True |
| OpenAI | gpt-5-mini | retail | 0.760 | 0.480 | -0.280 | 0.057 | 0.760 | True |
| OpenAI | gpt-5-mini | telecom | 0.773 | 0.660 | -0.113 | 0.038 | 0.753 | True |
| Qwen | qwen3.5-4b | telecom | 0.947 | 0.233 | -0.713 | 0.046 | nan | False |
