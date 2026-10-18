Received from Ethan in chat on 2026-10-18 as `qwen-local-s1.zip` (the teammate's results/qwen-local-s1-calibration folder,
files dated 2026-09-19 to 2026-10-07; `__MACOSX` entries dropped; `runner.log` was empty and is not kept).

What it is: the teammate's September S1 calibration of qwen3.5:4b on a different stack from the registered cell:
`ollama_chat/qwen3.5:4b` (unpinned tag, no digest), `num_ctx` 32768, temperature 0.0, `think` on, a custom
"thinking-only recovery" that adds a second call when the model returns thinking without content (56 recoveries
on airline). Registered stack: `openai/tt-qwen3.5-4b:q4` (pinned digest), `num_ctx` 131072, the model's shipped
sampling defaults, no recovery call. The airline row gives B_1x 6832.25 (144 evaluated episodes, 6 infrastructure
errors, pass^1 39.6%), which is the budget the received airline x 4b M1 run used (B 27329, c 6832).

What it is not: the S1 results.json (only a one-episode pre-recovery file from 2026-09-20 and a per-episode CSV),
the M1 done manifest, the build digest of the model the M1 ran on, or the tau2 commit of the M1 run (the S1 log
shows c339866).

Consequence (ANALYSIS.md CHANGELOG 2026-10-18): the airline x qwen3.5-4b M1 file cannot be used as a cell. Its
budget was calibrated on another stack and the only S1 it could pair with ran on that other stack.
