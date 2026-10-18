# H4, FP half (airline only)

Commission rule: `^(Check that )?Agent (does not|should not|must not|should never|never|should refuse)\b`

| model | index | S1 FP commission / passes | S1 FP all / passes | M1 FP commission / passes | M1 FP all / passes |
|---|---:|---|---|---|---|
| gpt-5-nano | 0.503 | 10 / 64 = 0.156 | 20 / 64 = 0.312 | 9 / 68 = 0.132 | 22 / 68 = 0.324 |
| gemini-3.1-flash-lite | 0.557 | 6 / 118 = 0.051 | 12 / 118 = 0.102 | 1 / 94 = 0.011 | 10 / 94 = 0.106 |
| gpt-5-mini | 0.767 | 8 / 112 = 0.071 | 14 / 112 = 0.125 | 6 / 87 = 0.069 | 17 / 87 = 0.195 |
| gemini-3-flash | 0.857 | 3 / 121 = 0.025 | 12 / 121 = 0.099 | 1 / 83 = 0.012 | 8 / 83 = 0.096 |

Pooled fp_commission change per episode (M1 - S1): -0.0167, cell-cluster 95% CI [-0.0283, -0.0083] over 4 cells

Pooled fp_all change per episode (M1 - S1): -0.0017, cell-cluster 95% CI [-0.0200, +0.0167] over 4 cells
