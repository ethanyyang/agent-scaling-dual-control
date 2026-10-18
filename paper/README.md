# Paper draft: Does Multi-Agent Collaboration Pay When Agents Serve Users? Testing Agent Scaling in Dual-Control Settings

Full version (18 Oct 2026). Plain `article` layout, 11pt, 1in margins, Times; APA reference list through `apacite`
(`natbibapa` option). Authors: Ethan Yang, Xiangcheng Shi (University of Pennsylvania). No conference style files.

## Build

```
latexmk -pdf main.tex          # TeX Live with apacite (texlive-bibtex-extra), tikz, booktabs, seqsplit, microtype
python3 figures/make_figures.py   # regenerates figures/fig_rulemap.pdf from figures/cells.csv
cd figures && python3 make_fig_main.py ../../results/h1   # regenerates figures/fig_main.pdf
```

Builds with 0 errors and no undefined references (26 pages).

## Structure

Main text: abstract; 1 Introduction; 2 Background and related work (with the position table); 3 Experimental design
(3.1 setting, models, notation, the two systems, why centralized, control flow; 3.2 budget protocol with the
prior-protocol table, implementation, meter checks and the calibration table; 3.3 outcome measures with the failure
taxonomy and the judge; 3.4 hypotheses, the coupling lemma with its proof, validity bars, robustness and the power
table); 4 Results (4.1 the grid as run with the validity table and its notes; 4.2 the grid and the loss decomposition;
4.3 the principle's sign test and the uncapped arm; 4.4 H1; 4.5 H2 with the taxonomy table; 4.6 robustness and cost;
4.7 the strong SAS extension; 4.8 compute and cost); 5 Discussion and limitations (main and further limitations in one
place); 6 Conclusion. Appendix A: tests and results card. Appendix B: the local 4-billion model (builds, per-trial
results, seed replay, airline x 4b sensitivity), kept outside the main text because every item in it sits outside the
registered fits by decision (ANALYSIS.md CHANGELOG 2026-10-17 and 2026-10-18).

## Sources

Every number is taken from the files in `../results/` and the run manifests; `figures/cells.csv` lists the source of each grid row. `figures/make_fig_main.py ../../results/h1` regenerates Figure 2 from the H1 outputs.
