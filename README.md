# Relative-Value Forward-P/E Dashboard

Self-contained interactive dashboard for L/S diversified-financials: relative NTM
forward-P/E across 85 names in 7 sub-sectors, mean-reversion pair backtests,
per-pair quarterly consistency, single-name P/E history, a sub-sector grid, and a
click-to-measure share-price-return tool on the pair chart.

**Read `CLAUDE.md` for the full operating manual** (build, validation gate,
data-refresh procedure, constraints, licensing). Claude Code reads it automatically.

## Quick start
```bash
python build.py        # template.html + 4 JSON -> Relative_PE_Dashboard.html
# validation gate (must both pass before shipping):
python3 -c "import re;h=open('Relative_PE_Dashboard.html',encoding='utf-8').read();open('/tmp/app.js','w',encoding='utf-8').write(max(re.findall(r'<script>([\s\S]*?)</script>',h),key=len))"
node --check /tmp/app.js
node bt_verify.js      # must print: ALL CHECKS PASSED (39 passed)
```
Open `Relative_PE_Dashboard.html` in a browser to view (no server needed).

## Refresh (summary — see CLAUDE.md §7)
1. Drop the new Bloomberg workbook as `Coverage_PE_multiples.xlsx`; set `ASOF` in
   `mkdata.py` to the latest *real* trading day (today's row is forward-filled).
   `python mkdata.py` -> `data.json`.
2. `python q_pairs.py` && `python bt_export.py` (regenerate references).
3. Pull daily prices from S&P Global (see resolution map in CLAUDE.md §7c) and
   `python build_dpx3.py` -> `daily_px.json` (scale-factor splice).
4. `python build.py` then the gate above.

## ⚠️ Licensing
Embeds licensed Bloomberg/S&P-derived data. **Do not host on a public site.**
Private repo + access control only — see CLAUDE.md §11.
