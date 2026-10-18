# H1 diagnostics and sensitivity

Primary fit overdispersion sigma^2 = 18.6 (1 = cells scatter only as much as task sampling allows).
Unweighted residual SD 0.183 against a median per-cell sampling SE of 0.051.

Residuals (gain minus fitted, pass^1 fraction):

- airline x gemini-3.1-flash-lite: +0.060
- retail x gemini-3.1-flash-lite: +0.106
- telecom x gemini-3.1-flash-lite: +0.290
- airline x gemini-3-flash: +0.090
- retail x gemini-3-flash: +0.042
- telecom x gemini-3-flash: -0.287
- airline x gpt-5-nano: -0.040
- retail x gpt-5-nano: -0.108
- telecom x gpt-5-nano: +0.019
- airline x gpt-5-mini: -0.125
- retail x gpt-5-mini: +0.004
- telecom x gpt-5-mini: +0.121

Leave-one-cell-out slope [95% CI]:

- without airline x gemini-3.1-flash-lite: -0.280 [-1.653, +1.093]
- without retail x gemini-3.1-flash-lite: -0.353 [-1.593, +0.888]
- without telecom x gemini-3.1-flash-lite: -0.415 [-1.382, +0.552]
- without airline x gemini-3-flash: -0.478 [-1.751, +0.795]
- without retail x gemini-3-flash: -0.454 [-1.768, +0.861]
- without telecom x gemini-3-flash: -0.294 [-0.607, +0.018]
- without airline x gpt-5-nano: -0.433 [-1.673, +0.807]
- without retail x gpt-5-nano: -0.613 [-1.980, +0.754]
- without telecom x gpt-5-nano: -0.376 [-1.718, +0.967]
- without airline x gpt-5-mini: -0.245 [-1.559, +1.069]
- without retail x gpt-5-mini: -0.417 [-1.763, +0.930]
- without telecom x gpt-5-mini: -0.573 [-1.772, +0.625]

Sensitivity adding the three qwen3.5-9b cells (n = 15, dof 9): slope -0.281, 95% CI [-1.255, +0.693], permutation p two-sided 0.5939, one-sided 0.3041
9b cells used: airline: x 0.857, gain -0.180, SE 0.056; retail: x 0.873, gain -0.267, SE 0.062; telecom: x 0.776, gain -0.620, SE 0.052
