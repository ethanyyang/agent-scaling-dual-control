# Received file: M1 (as built), airline x qwen3.5-4b, local Ollama

Received from Ethan in chat on 2026-10-16 as `results1.json`; saved here unchanged.
SHA-256 153f9b2dcf645967e3a103127368392601f764e42d707c98128066b80f9f1232 (23.8 MB).

What the file says about itself: agent `m1_qwen35_4b_q4_ollama_airline_b4x_capb1x`
(the registered qwen3.5-4b name, not the oct26 name), model `openai/tt-qwen3.5-4b:q4`,
reasoning_effort high, max_tokens 32768; user simulator gpt-5.2 low; seed 300, 3 trials
(626729, 373753, 361454), 50 airline tasks, 150 episodes; tau2 commit c339866;
budget B = 27329, c = 6832 (so B_1x = 6832, cap rule b1x), w 4099, a_min 162;
episodes from 2026-10-07 18:58 to 2026-10-12 18:04 local time, with one 26 hour pause
(2026-10-10 06:37 to 2026-10-11 08:40).

Not in this folder, and still needed before the cell can enter any table as a result:
- which machine ran it (the Ollama server in this folder was idle from 2026-10-01 to
  2026-10-08 and restarted on 2026-10-10, so it was not this Mac's server);
- the build of tt-qwen3.5-4b:q4 on that machine (registered 2a654d98e6fb / 668eab7d518c,
  or the October build d8b0f5e9760c / c0535b43ca6b), with its check-q4.json or
  provenance file;
- the done manifest written by run_m1.py (results_sha256, started and finished times);
- the S1 calibration run for airline x qwen3.5-4b that gave B_1x 6832: its results.json
  and manifest. Without it there is no paired gain and the S1 rows in ANALYSIS.md
  sections 4.2 and 5 stay blank.

Reading (2026-10-16, fixed order: infrastructure errors, mechanical G1 bars, write orders,
reward last) is in the ANALYSIS.md CHANGELOG entry of 2026-10-16.

Update 2026-10-18: the teammate's S1 calibration behind B_1x 6832 arrived (`teammate-s1-calibration-2026-10-07/`). It
ran on a different stack (`ollama_chat/qwen3.5:4b`, 32k context, temperature 0, recovery call), so the M1 run above was
budgeted from another stack and cannot be paired. Dropped as a cell; kept for the record (ANALYSIS.md CHANGELOG 2026-10-18).
