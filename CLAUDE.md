# overview-figures

Figure folders follow [FIGURE_TEMPLATE.md](FIGURE_TEMPLATE.md).

## Workflow for figure changes

- Split a request into data/config work and plotting work.
  - Data/config work (inputs, analysis, YAML, caches, CSVs) goes to a
    **Sonnet:medium** subagent.
  - Plotting work (layout, annotations, styling) goes to a **Haiku:medium** subagent.
  - The main session reviews both: read the diff and view the PNG.
- When both touch the same file, run them **one after the other**, not in
  parallel.
- Run scripts from the repo root:
  `MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python figures/<folder>/plot_<NAME>.py`.