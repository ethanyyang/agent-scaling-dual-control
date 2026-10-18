"""Power of the H1 primary test for the 12 cells held: observed LODO x, observed per-cell SEs, family + domain FE,
inverse-variance WLS with scaled covariance and t CI (as in h1_analysis.py). Adds between-cell heterogeneity tau,
which power_sim.py (section 1.1) set to zero. tau is estimated from the primary fit's overdispersion."""
import os as _os, sys as _sys
_REPO = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_HERE = _os.path.dirname(_os.path.abspath(__file__))
import csv, numpy as np, os, json
T975 = {7: 2.365}
P = _REPO + "/results/h1/h1_cells.csv"
C = [r for r in csv.DictReader(open(P)) if r["in_primary"] == "True"]
x = np.array([float(r["lodo_x"]) for r in C]); se = np.array([float(r["se"]) for r in C])
X = np.column_stack([np.ones(len(C)), x, [r["family"] == "Google" for r in C], [r["domain"] == "retail" for r in C], [r["domain"] == "telecom" for r in C]]).astype(float)
w = 1 / se ** 2; A = (X.T * w) @ X; Ainv = np.linalg.inv(A); H = Ainv @ (X.T * w); dof = len(C) - X.shape[1]
y = np.array([float(r["gain"]) for r in C]); b = H @ y; res = y - X @ b; s2 = (w * res ** 2).sum() / dof
# method-of-moments tau^2 for WLS: E[sum w r^2] = dof + tau^2 * tr(W (I - X H))
M = np.eye(len(C)) - X @ H; tau2 = max(0.0, ((w * res ** 2).sum() - dof) / np.trace(np.diag(w) @ M))
print(f"observed slope {b[1]:+.3f}, sigma2 {s2:.1f}, tau (between-cell SD) {np.sqrt(tau2):.3f}, median SE {np.median(se):.3f}, x range {x.min():.2f}-{x.max():.2f}")
rng = np.random.default_rng(300); R = 4000; out = {}
for tau in (0.0, 0.10, round(float(np.sqrt(tau2)), 3)):
    row = {}
    for slope in (0.0, -0.2, -0.3, -0.5, -1.0):
        hit = 0
        for _ in range(R):
            g = b[0] + slope * x + rng.normal(0, tau, len(C)) + rng.normal(0, se)
            bb = H @ g; rr = g - X @ bb; ss = (w * rr ** 2).sum() / dof
            if bb[1] + T975[dof] * np.sqrt(ss * Ainv[1, 1]) < 0: hit += 1
        row[slope] = hit / R
    out[tau] = row; print(f"tau {tau:.3f}: " + "  ".join(f"b={k:+.1f}: {v:.2f}" for k, v in row.items()))
json.dump({str(k): v for k, v in out.items()}, open(_REPO + "/results/secondary-2026-09-26/power12.json", "w"), indent=1)
