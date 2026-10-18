#!/usr/bin/env python3
"""Figures for the draft. Reads cells.csv (every number traced to ANALYSIS.md or the project log).

    python3 make_figures.py      # writes fig_rulemap.pdf next to this file
"""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
rows = list(csv.DictReader(open(HERE / "cells.csv")))

MARK = {"OpenAI": "o", "Google": "s", "Qwen": "D"}
COL = {"below": "#c0392b", "straddles": "#7f8c8d", "above": "#2c3e50"}

fig, ax = plt.subplots(figsize=(6.4, 3.6))
ax.axhline(0, color="black", lw=0.8)
ax.axvline(45, color="black", lw=0.8, ls="--")
ax.axvspan(0, 45, color="#f4f6f7", zorder=0)

for r in rows:
    s1 = float(r["s1"])
    m = MARK[r["family"]]
    if r["g1"] != "valid":
        gain = float(r["gain"]) if r["gain"] else float(r["m1"]) - s1
        ax.plot(s1, gain, marker="x", color="#95a5a6", ms=6, mew=1.2, ls="none", zorder=3)
        continue
    gain, lo, hi = float(r["gain"]), float(r["gain_lo"]), float(r["gain_hi"])
    informative = lo > 0 or hi < 0
    c = COL[r["class"]]
    ax.errorbar(s1, gain, yerr=[[gain - lo], [hi - gain]], fmt="none", ecolor=c, elinewidth=0.9, capsize=2, zorder=2)
    ax.plot(s1, gain, marker=m, ms=6.5, ls="none", color=c, mfc=c if informative else "white", mew=1.2, zorder=4)

ax.set_xlim(20, 100)
ax.set_ylim(-95, 25)
ax.set_xlabel("single-agent pass$^1$ of the cell (S1), %")
ax.set_ylabel("gain = M1 $-$ S1, points (95% CI)")
ax.text(22, 18, "rule predicts M1 > S1", fontsize=8, color="#555555")
ax.text(47, 18, "rule predicts M1 < S1", fontsize=8, color="#555555")
ax.text(45.8, -55, "45%", fontsize=8, rotation=90, va="center")

from matplotlib.lines import Line2D
handles = [
    Line2D([], [], marker="o", color="#2c3e50", ls="none", label="OpenAI GPT-5"),
    Line2D([], [], marker="s", color="#2c3e50", ls="none", label="Google Gemini"),
    Line2D([], [], marker="D", color="#2c3e50", ls="none", label="Qwen3.5"),
    Line2D([], [], marker="o", color="#c0392b", ls="none", label="S1 clearly below 45%"),
    Line2D([], [], marker="o", color="#7f8c8d", mfc="white", ls="none", label="S1 CI straddles 45% (hollow: gain CI covers 0)"),
    Line2D([], [], marker="x", color="#95a5a6", ls="none", label="qwen3.5-9b cells failing G1 (point only)"),
]
ax.legend(handles=handles, fontsize=7, loc="lower left", frameon=False)
fig.tight_layout()
fig.savefig(HERE / "fig_rulemap.pdf")
print("wrote", HERE / "fig_rulemap.pdf")
