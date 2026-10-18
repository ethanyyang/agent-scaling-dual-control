# Local Qwen S1 calibration — ANALYSIS.md §4.2

Interim rows are labelled `running`; freeze budget values only after 150/150 attempts. Infrastructure failures are retried once, then excluded and reported as required by ANALYSIS.md §3.

| Domain × model | Status | valid/attempted | infra excluded | SHA-256 | S1 mean | P75 B_1x | 0.5× | 2× | call P95 c | pass^1 | pass above B_1x | pass ≤ B_1x | recoveries |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| airline × qwen3.5:4b | complete | 144/150 | 6 | 9a82a8ed5fc8 | 5357.28 | 6832.25 | 3416.12 | 13664.50 | 1405.40 | 0.396 | 0.389 | 0.398 | 56 |
| retail × qwen3.5:4b | complete | 142/150 | 8 | 1bcf769e8288 | 3146.17 | 4256.00 | 2128.00 | 8512.00 | 944.10 | 0.359 | 0.472 | 0.321 | 26 |
| telecom × qwen3.5:4b | complete | 0/150 | 150 | 19ab750af9aa | — | — | — | — | — | — | — | — | — |

Completion-token totals include every agent-side call. A thinking-only primary generation and its materialization call are already summed in the logged call usage.
Percentiles use NumPy's linear/type-7 definition; unrounded values are retained in `summary.json`.
