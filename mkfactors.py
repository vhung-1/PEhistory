"""mkfactors.py - inputs for the private "Coverage Factor Exposures" page (not part of the public dashboard).

Usage:  python3 -I mkfactors.py <GS factor workbook .xlsx> <output dir> [repo dir]

Reads the workbook's "GS FACTORS" sheet (one Bloomberg BQL formula, px_last of every GS basket and factor
index), plus this repo's daily_px.json (S&P adjusted closes), data.json (FY+1 P/E) and q_pairs.json (the
curated pairs), and writes three JSON files for the page:

  factor_weekly.json  {columns, data, meta}: one row per week (Friday close to Friday close), weekly log
                      returns in % for the 91 names and every GS series, and the weekly change in each
                      name's log FY+1 P/E (columns "pe:<ticker>").
  factor_series.json  {rows, meta}: one row per series: id, label, kind (name | market | style | theme), group.
  factor_pairs.json   {rows, meta}: the curated pairs (pair, a, b, sector).

Labels come from the BQL output's own security-ID row (Excel row 4), never the sheet's Theme/Ticker rows
above it: BQL returns the series in its own order, so in the 2026-11-21 workbook those rows sat over the
wrong data in 138 of 160 columns. The ticker -> theme name map is still read from the Theme/Ticker rows.

GS data is licensed: these outputs must never be committed to this (public) repository.
"""
import json, math, os, sys
import numpy as np
import pandas as pd

wb, out = sys.argv[1], sys.argv[2]
repo = sys.argv[3] if len(sys.argv) > 3 else os.path.dirname(os.path.abspath(__file__))
os.makedirs(out, exist_ok=True)

MARKET = 'X7'   # S&P 500 ex Magnificent 7 (Bloomberg index in the workbook)
STYLES = [      # GS "indexified Barra" long/short factor pairs; a positive exposure moves with the first-named side
    ('GSP1SIZE', 'Size', 'Large minus small caps'),
    ('GSP1VALU', 'Value', 'Cheap minus expensive'),
    ('GSP1MOMO', 'Momentum', 'High minus low momentum'),
    ('GSP1QUAL', 'Quality', 'High minus low quality'),
    ('GSP1GRWT', 'Growth', 'High minus low growth'),
    ('GSP1BETA', 'Beta', 'High minus low beta'),
    ('GSP1RSVL', 'Residual vol', 'High minus low residual volatility'),
    ('GSP1LEVG', 'Leverage', 'High minus low leverage'),
    ('GSPU10YR', 'Rate sensitivity', 'High minus low 10-yr rate sensitivity (Wolfe)'),
    ('GSPUCRWD', 'Crowding', 'Most minus least crowded'),
    ('GSPUWSHI', 'Short interest', 'High minus low short interest'),
]

# --- GS series, labelled by the BQL security-ID row -------------------------------------------------------
raw = pd.read_excel(wb, sheet_name='GS FACTORS', header=None)
theme, group, cat = {}, {}, str(raw.iloc[0, 1]).strip()   # the first category's name sits above the date column
for j in range(2, raw.shape[1]):
    k, t = raw.iloc[1, j], raw.iloc[0, j]
    if pd.isna(k) or not str(k).strip():
        if pd.notna(t): cat = str(t).strip()
        continue
    k = str(k).strip()
    theme.setdefault(k, str(t).strip())
    group.setdefault(k, (cat or '').split('(')[0].replace('*Indexified Barra Indices*', '').strip())
dates = pd.to_datetime(raw.iloc[5:, 1], errors='coerce')
cols = {}
for j in range(2, raw.shape[1]):
    sid = raw.iloc[3, j]
    if pd.isna(sid) or not str(sid).strip() or str(sid).strip().lower() == 'index': continue
    k = str(sid).strip().rsplit(' ', 1)[0]
    s = pd.to_numeric(raw.iloc[5:, j], errors='coerce'); s.index = dates
    s = s[s.index.notna()]
    if s.notna().sum() and k not in cols: cols[k] = s
G = pd.DataFrame(cols).sort_index()
G = G[G.index.day_of_week < 5]
assert MARKET in G and all(f in G for f, _, _ in STYLES), 'market or a style factor is missing from the workbook'

# --- coverage names: S&P adjusted closes and FY+1 P/E ----------------------------------------------------
d = json.load(open(os.path.join(repo, 'data.json')))
px = json.load(open(os.path.join(repo, 'daily_px.json')))
idx = pd.to_datetime(d['dates'])
S = pd.DataFrame(px['px'], index=idx).astype(float)
PE = pd.DataFrame(d['pe'], index=idx).astype(float)
names = [t for sec in d['sectors'].values() for t in sec]

# --- weekly log returns, Friday to Friday, complete weeks only ------------------------------------------
cut = min(G.index[-1], pd.Timestamp(px['asof']), pd.Timestamp(d['asof']))
wk = lambda X: X.resample('W-FRI').last()
keep = lambda X: X[X.index <= cut]
gr = keep(np.log(wk(G)).diff() * 100)
sr = keep(np.log(wk(S[names])).diff() * 100)
pr = keep(np.log(wk(PE[names])).diff() * 100)
pr.columns = ['pe:' + t for t in names]
W = pd.concat([sr, gr, pr], axis=1).loc[gr.index]
W = W.iloc[1:]                                     # the first week has no previous Friday
W = W[W[MARKET].notna()]
r = lambda v: None if v is None or (isinstance(v, float) and not math.isfinite(v)) else round(float(v), 3)
weekly = {'columns': ['week'] + list(W.columns),
          'data': [[w.strftime('%Y-%m-%d')] + [r(v) for v in row] for w, row in zip(W.index, W.values)]}

# --- catalog ---------------------------------------------------------------------------------------------
series = [{'id': t, 'label': t, 'kind': 'name', 'group': d['sector_of'][t]} for t in names]
series.append({'id': MARKET, 'label': 'S&P 500 ex Mag 7', 'kind': 'market', 'group': 'Market'})
series += [{'id': f, 'label': lab, 'kind': 'style', 'group': desc} for f, lab, desc in STYLES]
style_ids = {f for f, _, _ in STYLES}
series += [{'id': k, 'label': theme.get(k, k), 'kind': 'theme', 'group': group.get(k, '')}
           for k in G.columns if k != MARKET and k not in style_ids]

pairs = [{'pair': f"{q['a']}/{q['b']}", 'a': q['a'], 'b': q['b'], 'sector': q['sec']}
         for q in json.load(open(os.path.join(repo, 'q_pairs.json')))]
pairs.sort(key=lambda p: (list(d['sectors']).index(p['sector']) if p['sector'] in d['sectors'] else 99, p['pair']))

code = open(os.path.abspath(__file__), encoding='utf-8').read()
src = (f"{os.path.basename(wb)}, sheet GS FACTORS (Bloomberg BQL px_last, {G.index[0].date()} to {G.index[-1].date()}); "
       f"the P/E dashboard's daily_px.json (S&P adjusted closes to {px['asof']}) and data.json (FY+1 P/E to {d['asof']})")
meta = [{'label': 'mkfactors.py', 'value': code, 'type': 'code', 'lang': 'python'}, {'label': 'Inputs', 'value': src},
        {'label': 'Weeks', 'value': f"{len(W)} weeks ending {W.index[0].date()} to {W.index[-1].date()} (Friday closes; the last week "
                                     f"ends on the latest Friday that both the factors and the share prices reach)"}]
weekly['meta'] = meta
for fn, obj in [('factor_weekly.json', weekly), ('factor_series.json', {'rows': series, 'meta': meta}),
                ('factor_pairs.json', {'rows': pairs, 'meta': meta})]:
    with open(os.path.join(out, fn), 'w') as f: json.dump(obj, f, separators=(',', ':'), allow_nan=False)
    print(f'{fn}: {os.path.getsize(os.path.join(out, fn)) / 1e3:.0f} KB')
print(f'weeks {len(W)}: {W.index[0].date()} -> {W.index[-1].date()} | names {len(names)} | GS series {G.shape[1]} '
      f'(themes {sum(s["kind"] == "theme" for s in series)}) | pairs {len(pairs)}')
