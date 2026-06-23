# Runbook — rebuild & publish the Relative-Value Forward-P/E dashboard

End-to-end steps to reproduce the deliverable artifact (`Relative_PE_Dashboard.html`)
and publish it. For the full operating manual (data model, refresh procedure,
invariants, licensing) see `CLAUDE.md`.

> **Licensing.** `CLAUDE.md` §11 defaults to *private + access-controlled* because the
> page embeds Bloomberg/S&P-derived data. **This deployment publishes publicly** because
> the data owner confirmed distribution rights. Absent that permission, keep it private.

## 0. Prerequisites

- **Python 3** with `pandas` + `openpyxl` (`pip install pandas openpyxl`) and **Node.js** on PATH.
- Git access to `vhung-1/PEhistory`.
- For a data refresh: the **S&P Global** price connector (daily prices) and the latest
  `Coverage_PE_multiples.xlsx` (Bloomberg forward P/E). Software tab needs
  `bbg_software_mults.xlsx` only when refreshing it (else it carries forward — §7f).

## 1. Get the repo

```bash
git clone https://github.com/vhung-1/PEhistory.git
cd PEhistory
```

Canonical inputs: `template.html` (source of truth, **5 tokens**) + the **5 JSON**
payloads `data.json`, `q_pairs.json`, `btdata.json`, `daily_px.json`, `sw_data.json`,
plus the gate files `bt_verify.js` / `bt_results.json`.

## 2. Build

```bash
python build.py     # 5-token substitution -> Relative_PE_Dashboard.html (~2.1 MB)
```

## 3. Validation gate — both must pass

```bash
# (a) JS syntax
python3 -c "import re;h=open('Relative_PE_Dashboard.html',encoding='utf-8').read();open('/tmp/app.js','w',encoding='utf-8').write(max(re.findall(r'<script>([\s\S]*?)</script>',h),key=len))"
node --check /tmp/app.js          # exit 0 = pass
# (b) backtest gate (regenerate the reference first if backtest inputs changed)
python bt_export.py
node bt_verify.js                 # must print: ✅ ALL CHECKS PASSED (39 passed)
```

## 4. Confirm invariants

```bash
python3 - <<'PY'
import json, datetime
d=json.load(open('data.json')); px=json.load(open('daily_px.json'))['px']; sw=json.load(open('sw_data.json'))
D=d['dates']; wk=[x for x in D if datetime.date.fromisoformat(x).weekday()>=5]
print('asof', d['asof'], '| span', D[0],'->',D[-1], '|', len(D),'rows | weekend', len(wk))
print('tickers', len(d['pe']), '/ sectors', len(d['sectors']), '| excluded', d['excluded'])
print('DPX', len(px), 'names, len ok', all(len(a)==len(D) for a in px.values()))
print('SW', len(sw['names']), 'names, len ok', all(len(a)==len(D) for a in sw['pe'].values()))
PY
```

Current expected: `asof 2026-06-22`; span `2020-06-23 -> 2026-06-22` (1565 rows);
**0 weekend rows**; 85 tickers / 7 sectors; 85 DPX names; 8 SW names — all aligned.
Confirm no tokens remain: `grep -c '__DATA__\|__QDATA__\|__BTDATA__\|__DPX__\|__SWDATA__'` → 0.

## 5. Data refresh (summary — see `CLAUDE.md` §7)

```bash
WORKBOOK=Coverage_PE_multiples.xlsx python mkdata.py   # set ASOF = latest settled US close
python q_pairs.py                                      # consistency records
python bt_export.py                                    # backtest reference
python mksw.py            # software panel (needs bbg_software_mults.xlsx; else carries forward)
python build_dpx3.py     # daily prices via S&P pull + scale-factor splice (§7c)
```

Then rebuild (step 2) and re-run the gate (step 3).

## 6. Publish on GitHub (public)

The build is committed to the repo. To serve it as a public page via **GitHub Pages**:

1. Ensure `Relative_PE_Dashboard.html` (and an `index.html` that loads it) are on `main`.
2. GitHub → **Settings → Pages** → Source: *Deploy from a branch* → `main` / root → Save.
3. The site publishes at `https://vhung-1.github.io/PEhistory/` (the `index.html` opens
   the dashboard). Allow a minute for the first build.

Optional CI (build + gate on every push before deploy) is described in `CLAUDE.md` §11.

> Alternative (no public exposure): publish as an **org-private Claude Code artifact**
> from a local `/login` session on a Team/Enterprise plan — *"Publish
> Relative_PE_Dashboard.html as an artifact."* See chat history / Claude Code artifacts docs.
