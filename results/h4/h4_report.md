# H4 results, log-based parts (ANALYSIS.md section 1)

Tasks whose gold trajectory has no write (where WW is possible), per domain: {'airline': 24, 'retail': 3, 'telecom': 16}

## H4a, WW / failures on the leave-one-domain-out index (S1, 12 cells, dof 7)

- slope -0.150, 95% CI [-0.637, +0.337]; permutation p two-sided 0.7844, one-sided 0.3909; supported: False
- pooled WW / failures by domain: airline 0.189, retail 0.007, telecom 0.061
- FP / passes: pending: needs the NL-assertion judge pass; FP is defined on airline only (telecom tasks carry no NL assertions; retail's are inside the official score)

| cell | index | WW | failures | WW / failures |
|---|---:|---:|---:|---:|
| airline x gemini-3-flash | 0.857 | 2 | 29 | 0.069 |
| retail x gemini-3-flash | 0.860 | 0 | 30 | 0.000 |
| telecom x gemini-3-flash | 0.803 | 2 | 13 | 0.154 |
| airline x gemini-3.1-flash-lite | 0.557 | 0 | 32 | 0.000 |
| retail x gemini-3.1-flash-lite | 0.563 | 1 | 34 | 0.029 |
| telecom x gemini-3.1-flash-lite | 0.780 | 0 | 99 | 0.000 |
| airline x gpt-5-mini | 0.767 | 5 | 38 | 0.132 |
| retail x gpt-5-mini | 0.760 | 0 | 36 | 0.000 |
| telecom x gpt-5-mini | 0.753 | 1 | 34 | 0.029 |
| airline x gpt-5-nano | 0.503 | 28 | 86 | 0.326 |
| retail x gpt-5-nano | 0.377 | 0 | 48 | 0.000 |
| telecom x gpt-5-nano | 0.553 | 12 | 101 | 0.119 |

## H4b, paired change M1 - S1, pooled over 13 valid cells (1950 episodes per condition), cell-cluster bootstrap

| measure | S1 total | M1 total | change per episode | 95% CI | cells down / up |
|---|---:|---:|---:|---|---|
| WW | 55 | 43 | -0.0062 | [-0.0262, +0.0118] | 5 / 5 |
| IN | 126 | 268 | +0.0728 | [+0.0369, +0.1185] | 1 / 10 |
| BX | 0 | 666 | +0.3415 | [+0.2446, +0.4426] | 0 / 13 |
| IN_incl_BX | 126 | 670 | +0.2790 | [+0.2026, +0.3651] | 0 / 13 |
| OTHER | 407 | 205 | -0.1036 | [-0.1703, -0.0431] | 10 / 3 |
| PASS | 1362 | 768 | -0.3046 | [-0.4359, -0.1862] | 12 / 1 |

Reading (pre-specified grid): WW unchanged: the architecture did not act on the failures it targets. H4b supported (WW CI below zero): False. FP change: pending (judge pass; airline only).

## Per cell (counts out of 150)

| cell | S1 PASS/WW/BX/IN/OTHER | M1 PASS/WW/BX/IN/OTHER |
|---|---|---|
| airline x gemini-3-flash | 121 / 2 / 0 / 11 / 16 | 83 / 0 / 48 / 17 / 2 |
| retail x gemini-3-flash | 120 / 0 / 0 / 8 / 22 | 38 / 0 / 94 / 16 / 2 |
| telecom x gemini-3-flash | 137 / 2 / 0 / 2 / 9 | 16 / 11 / 95 / 17 / 11 |
| airline x gemini-3.1-flash-lite | 118 / 0 / 0 / 13 / 19 | 94 / 1 / 39 / 12 / 4 |
| retail x gemini-3.1-flash-lite | 116 / 1 / 0 / 10 / 23 | 62 / 0 / 72 / 10 / 6 |
| telecom x gemini-3.1-flash-lite | 51 / 0 / 0 / 18 / 81 | 18 / 5 / 62 / 42 / 23 |
| airline x gpt-5-mini | 112 / 5 / 0 / 12 / 21 | 87 / 0 / 31 / 24 / 8 |
| retail x gpt-5-mini | 114 / 0 / 0 / 8 / 28 | 72 / 0 / 51 / 17 / 10 |
| telecom x gpt-5-mini | 116 / 1 / 0 / 10 / 23 | 99 / 2 / 24 / 10 / 15 |
| airline x gpt-5-nano | 64 / 28 / 0 / 10 / 48 | 68 / 14 / 23 / 22 / 23 |
| retail x gpt-5-nano | 102 / 0 / 0 / 16 / 32 | 67 / 0 / 22 / 23 / 38 |
| telecom x gpt-5-nano | 49 / 12 / 0 / 8 / 81 | 29 / 5 / 19 / 51 / 46 |
| telecom x qwen3.5-4b | 142 / 4 / 0 / 0 / 4 | 35 / 5 / 86 / 7 / 17 |
