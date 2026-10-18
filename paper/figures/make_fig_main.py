#!/usr/bin/env python3
"""Main results figure: (a) rule map on the cell's own S1, (b) gain against the leave-one-domain-out index with
the H1 fit (the slope forms are in Table 3 of the paper). Reads h1_cells.csv, h1_results.json, h1_sensitivity.json from argv[1]
(default ../../results/h1) and cells.csv (for the qwen3.5-9b points and CIs) next to this file.
Writes fig_main.pdf next to this file.
"""
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from scipy import stats

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent.parent / "results" / "h1"
h1cells = list(csv.DictReader(open(SRC / "h1_cells.csv")))
res = json.load(open(SRC / "h1_results.json"))
sens = json.load(open(SRC / "h1_sensitivity.json"))
tab = list(csv.DictReader(open(HERE / "cells.csv")))

DOM_COL = {"airline": "#2a78d6", "retail": "#eb6834", "telecom": "#1baf7a"}   # validated categorical slots 1-3
FAM_MARK = {"OpenAI": "o", "Google": "s", "Qwen": "D"}
INK, MUTED, GRID = "#222222", "#6b6b6b", "#e4e4e0"
plt.rcParams.update({"font.size": 7, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})
fig, (ax0, ax) = plt.subplots(1, 2, figsize=(7.2, 2.05))


def dot(axis, x, g, lo, hi, dom, fam, hollow=False):
    c = DOM_COL[dom]
    axis.plot([x, x], [lo, hi], color=c, lw=1.0, zorder=3)
    axis.plot(x, g, marker=FAM_MARK[fam], ms=5.2, color=c, mfc="white" if hollow else c, mec=c if hollow else "white",
              mew=1.0, ls="none", zorder=4)


# ---- (a) rule map on the cell's own S1
ax0.axvspan(20, 45, color="#f2f2ef", lw=0, zorder=0)
ax0.axhline(0, color=MUTED, lw=0.8); ax0.axvline(45, color=MUTED, lw=0.8, ls="--")
for r in tab:
    s1 = float(r["s1"])
    if r["g1"] != "valid":
        g = float(r["gain"]) if r["gain"] else float(r["m1"]) - s1
        ax0.plot(s1, g, marker="x", color="#9a9a96", ms=4.5, mew=1.0, ls="none", zorder=3)
        continue
    g, lo, hi = float(r["gain"]), float(r["gain_lo"]), float(r["gain_hi"])
    dot(ax0, s1, g, lo, hi, r["domain"], r["family"], hollow=lo <= 0 <= hi)
ax0.set_xlim(20, 100); ax0.set_ylim(-95, 22)
ax0.set_xlabel("cell's own SAS pass$^1$ (%)"); ax0.set_ylabel("gain = MAS $-$ SAS (points, 95% CI)")
ax0.text(21.5, 15, "principle: gain", color=MUTED, fontsize=6); ax0.text(46.5, 15, "principle: loss", color=MUTED, fontsize=6)
ax0.set_title("(a) principle map", fontsize=7.5, color=INK, loc="left")
ax0.grid(axis="y", color=GRID, lw=0.6); ax0.set_axisbelow(True)

# ---- (b) gain against the leave-one-domain-out index, with the H1 fit
P = res["primary"]
prim = [c for c in h1cells if c["in_primary"] == "True"]
x = np.array([float(c["lodo_x"]) for c in prim]); y = np.array([float(c["gain"]) for c in prim])
v = np.array([float(c["se"]) ** 2 for c in prim])
fam = np.array([c["family"] for c in prim]); dom = np.array([c["domain"] for c in prim])
X = np.column_stack([np.ones_like(x), x, (fam == "Google").astype(float), (dom == "retail").astype(float), (dom == "telecom").astype(float)])
w = 1 / v; A = (X.T * w) @ X; beta = np.linalg.solve(A, (X.T * w) @ y)
dof = len(y) - X.shape[1]; s2 = (w * (y - X @ beta) ** 2).sum() / dof; cov = s2 * np.linalg.inv(A)
assert abs(beta[1] - P["slope"]) < 1e-9
t = stats.t.ppf(0.975, dof)
grid = np.linspace(0.33, 0.90, 60)
C = np.column_stack([np.ones_like(grid), grid, np.full_like(grid, 0.5), np.full_like(grid, 1 / 3), np.full_like(grid, 1 / 3)])
fitv = C @ beta; half = t * np.sqrt(np.einsum("ij,jk,ik->i", C, cov, C))
ax.fill_between(grid * 100, (fitv - half) * 100, (fitv + half) * 100, color="#bdbdb8", alpha=0.35, lw=0, zorder=1)
ax.plot(grid * 100, fitv * 100, color=INK, lw=1.4, zorder=2)
ax.axhline(0, color=MUTED, lw=0.8); ax.axvline(45, color=MUTED, lw=0.8, ls="--")
for c in prim:
    g, se = float(c["gain"]) * 100, float(c["se"]) * 100
    dot(ax, float(c["lodo_x"]) * 100, g, g - 1.96 * se, g + 1.96 * se, c["domain"], c["family"])
ax.set_xlim(33, 90); ax.set_ylim(-95, 22)
ax.set_xlabel("capability index: SAS on the other domains (%)")
ax.set_title(f"(b) H1: slope {P['slope']:+.2f} [{P['ci'][0]:+.2f}, {P['ci'][1]:+.2f}]", fontsize=7.5, color=INK, loc="left")
ax.grid(axis="y", color=GRID, lw=0.6); ax.set_axisbelow(True)
handles = [Line2D([], [], marker=FAM_MARK[f], color=MUTED, ls="none", ms=4.5, label=l) for f, l in
           (("OpenAI", "GPT-5"), ("Google", "Gemini"), ("Qwen", "Qwen3.5-4b"))] + \
          [Line2D([], [], marker="x", color="#9a9a96", ls="none", ms=4.5, label="9b, fails G1")] + \
          [Line2D([], [], marker="o", color=DOM_COL[d], ls="none", ms=4.5, label=d) for d in DOM_COL]
ax0.legend(handles=handles, fontsize=5.8, frameon=False, loc="lower left", ncol=2, handletextpad=0.2, columnspacing=0.6)

fig.tight_layout(w_pad=0.8)
fig.savefig(HERE / "fig_main.pdf")
print("wrote", HERE / "fig_main.pdf")
