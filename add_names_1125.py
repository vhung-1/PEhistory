"""
add_names_1125.py — add the four names that joined the coverage universe on 2026-11-25 (EMG LN, AMG US,
NAVN US, INTU US) to daily_px.json. Run after mkdata.py and the day's splice (the axis does not move here).

Each new name has no stored prices, so its own full-history S&P pull (2020-11-01 -> asof, daily, adjusted,
back-adjusted to the asof) defines its basis: F = 1. Only returns are read from px, so the basis is free.
The realign follows the splice's rules: holiday forward-fill only after the first sourced close, null
before listing (NAVN listed 2025-10-30). Existing names are left byte-identical. spot gets each new
name's last close, as the splice writes it.
"""
import json, os, sys
PULL = ('/root/.claude/projects/-home-user-PEhistory/8a11d578-e9f0-5dd3-8083-8128422f78d9/tool-results/'
        'mcp-S_P_Global-get_prices_from_identifiers-1795631430582-w3li2k.txt')
NEW = {'LSE:EMG': 'EMG LN', 'NYSE:AMG': 'AMG US', 'NAVN': 'NAVN US', 'INTU': 'INTU US'}

data = json.load(open('data.json')); dates = data['dates']
dpx = json.load(open('daily_px.json'))
assert dpx['asof'] == data['asof'], (dpx['asof'], data['asof'])
assert all(len(v) == len(dates) for v in dpx['px'].values())
raw = json.load(open(PULL))['results']
for key, t in NEW.items():
    assert t in data['pe'], t
    assert t not in dpx['px'], f'{t} already in daily_px.json'
    blk = raw[key]; dd = blk.get('data', {}) or {}
    print(f"  {key:9s} -> {t:8s} {blk.get('company_name') or dd.get('company_name')} ({blk.get('ticker') or dd.get('ticker')})")
    ps = [p for p in dd.get('prices', []) if p.get('close', {}).get('value') not in (None, '', 'N/A')]
    pm = {p['date']: float(p['close']['value']) for p in ps}
    assert ps[-1]['date'] == data['asof'], f'{t}: pull ends {ps[-1]["date"]}'
    out, last = [], None
    for d in dates:
        if d in pm: last = round(pm[d], 2)
        out.append(last)
    dpx['px'][t] = out
    dpx['spot'][t] = [float(ps[-1]['close']['value']), ps[-1]['close'].get('unit'), ps[-1]['date']]
    first = next(i for i, v in enumerate(out) if v is not None)
    print(f'     {sum(v is not None for v in out)} values from {dates[first]}; spot {dpx["spot"][t]}')
dpx['px'] = dict(sorted(dpx['px'].items())); dpx['spot'] = dict(sorted(dpx['spot'].items()))
json.dump(dpx, open('daily_px.json', 'w'), separators=(',', ':'))
print(f"daily_px.json {os.path.getsize('daily_px.json')/1e6:.2f} MB | tickers {len(dpx['px'])} | asof {dpx['asof']}")
