# Exploratory tau2 airline SAS baseline

This prerelease publishes the raw trajectories behind the exploratory
single-agent baseline in `transfer-testing`.

## Run

- Domain: airline
- Tasks: 50
- Trials per task: 3
- Episodes: 150
- Agent: `gpt-4.1-mini-2025-04-14`, temperature 0
- User simulator: `gpt-4.1-mini-2025-04-14`, temperature 0
- Root seed: 300
- tau2-bench commit: `c3398666e6559e3a063da3fc04b5acf7f941464e`

## Result

- pass^1: 40.0%
- pass^2: 26.0%
- pass^3: 18.0%
- Recorded trajectory cost: $1.646436

These pass^k values match tau2-bench's official combinatorial estimator. This
is an exploratory pilot, not evidence by itself that the 45% capability rule
transfers to conversational tool use.

## Asset integrity

Asset: `tau2-airline-sas-gpt41mini-3trials-seed300-results.json.gz`

- Compressed SHA-256:
  `8c1d1afc480a446983e8273cc59c44fdae7d8a6a98b6549e98bf4f51a2059761`
- Decompressed JSON SHA-256:
  `0e6a9bb1c33951e3ae51e0d1f32996d8f4d9adf18d9631119f244ba873ac3bd7`

The asset contains full prompts, trajectories, token usage, rewards, costs,
and provider response metadata. A credential-pattern scan found no API keys,
bearer tokens, private keys, or secret-valued fields. The tau2 scenarios and
customer records are synthetic.

See the result directory in the repository for the analysis report,
per-episode CSV, exact reproduction command, and interpretation cautions.
