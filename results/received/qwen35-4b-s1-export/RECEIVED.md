Received from Ethan in chat on 2026-10-18 as `qwen35-4b-s1-export.zip` (zip SHA-256 8f5f5f92f951cbbf...), the teammate's
export of their qwen3.5-4b S1 runs, byte-for-byte copies of their results.json files with per-run manifests
(their README and top-level manifest are kept unchanged).

Contents:
- airline/, retail/, telecom/: the September S1 runs on the teammate's own stack (`ollama_chat/qwen3.5:4b`, unpinned
  tag, 32k context, temperature 0, think on; tau2 c339866). Airline 150 attempted, 144 evaluated, 57 passed, 69
  agent_error endings; retail 150 / 142; telecom 22 of 150 (partial). The airline file's SHA-256 (9a82a8ed5fc8...)
  matches the calibration summary that gave B_1x 6832.25, the budget used by the received airline x 4b M1 run.
- airline-october-partial/: `calib-airline-s1-qwen35-4b-q4-ollama-...`, an S1 on the registered interface and
  configuration (`openai/tt-qwen3.5-4b:q4`, reasoning high, max_tokens 32768), run 2026-10-07 15:44 to 18:00 local,
  10 of 150 episodes (8 evaluated, 7 passed, 2 infrastructure errors), stopped before the received M1 run started
  at 18:58 the same day. Not a calibration (10 of 150) and no build digest.

Still absent: the M1 done manifest, the digest of the model the M1 ran on, the M1 run's tau2 commit.

Consequence (ANALYSIS.md CHANGELOG 2026-10-18): the airline x qwen3.5-4b M1 stays dropped as a cell. Its budget came
from the other-stack S1; the registered-stack S1 was stopped at 10 episodes.
