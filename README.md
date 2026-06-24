# Relative-Value Forward-P/E Dashboard

[![Build, gate & deploy](https://github.com/vhung-1/PEhistory/actions/workflows/pages.yml/badge.svg)](https://github.com/vhung-1/PEhistory/actions/workflows/pages.yml)

**Live:** https://vhung-1.github.io/PEhistory/

Self-contained interactive dashboard for L/S diversified-financials: relative NTM
forward-P/E across 85 names in 7 sub-sectors, mean-reversion pair backtests,
per-pair quarterly consistency, single-name P/E history, a sub-sector grid, a
click-to-measure share-price-return tool, and a Software reference tab for JKHY.

**Read `CLAUDE.md` for the full operating manual** (build, validation gate,
data-refresh procedure, constraints, licensing). Claude Code reads it automatically.

## Quick start
```bash
python build.py        # template.html + 5 JSON -> Relative_PE_Dashboard.html
# validation gate (both must pass before shipping):
python3 -c "import re;h=open('Relative_PE_Dashboard.html',encoding='utf-8').read();open('/tmp/app.js','w',encoding='utf-8').write(max(re.findall(r'<script>([\s\S]*?)</script>',h),key=len))"
node --check /tmp/app.js
node bt_verify.js      # must print: ALL CHECKS PASSED (39 passed)
```
Open `Relative_PE_Dashboard.html` in a browser to view (no server needed).

## Refresh (summary — see CLAUDE.md §7)
1. Drop the new coverage workbook as `Coverage_PE_multiples.xlsx`; set `ASOF` in
   `mkdata.py` to the latest *settled* close (exclude today's intraday row, weekends,
   and US market holidays). `python mkdata.py` -> `data.json`.
2. `python q_pairs.py` && `python bt_export.py` (regenerate references).
3. `python mksw.py` (realign/refresh the Software panel; needs `bbg_software_mults.xlsx`).
4. Pull daily prices from S&P Global (resolution map in CLAUDE.md §7c) and
   `python build_dpx3.py` -> `daily_px.json` (scale-factor splice). If nothing
   advanced past the asof, just re-run build_dpx3.py to realign (no pull needed).
5. `python build.py` then the gate above.

## Tokens (build.py order)
`__QDATA__` `__BTDATA__` `__DATA__` `__DPX__` `__SWDATA__`  (long *DATA tokens before `__DATA__`).

## Licensing
Embeds Bloomberg/S&P-derived data. The data owner has **confirmed distribution
rights**, so this dashboard is published publicly via GitHub Pages. Absent that
permission, the default is private + access-controlled — see CLAUDE.md §11.
