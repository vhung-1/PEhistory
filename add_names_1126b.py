"""
add_names_1126b.py — add DAVE US (Dave Inc), which joined the coverage universe on 2026-11-26, to
daily_px.json. Run after mkdata.py and splice_1126.py (the axis does not move here).

Each new name has no stored prices, so its own full-history S&P pull (2020-11-01 -> asof, daily, adjusted,
back-adjusted to the asof) defines its basis: F = 1. Only returns are read from px, so the basis is free.
The realign follows the splice's rules: holiday forward-fill only after the first sourced close, null
before listing (Dave Inc from its 2022-01-06 de-SPAC). Existing names are left byte-identical. spot gets each new
name's last close, as the splice writes it.
"""
import json, os, sys
PULL = ('/root/.claude/projects/-home-user-PEhistory/8a11d578-e9f0-5dd3-8083-8128422f78d9/tool-results/'
        'mcp-S_P_Global-get_prices_from_identifiers-1795715048649-41t5mj.txt')
NEW = {'DAVE': 'DAVE US'}
# The pull starts 2021-04-26 with the SPAC (VPC Impact Acquisition Holdings III), whose trust-value prices are not
# Dave's. Dave Inc began trading as DAVE on 2022-01-06 when the merger closed; prices start there.
START = {'DAVE US': '2022-01-06'}

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
        if d in pm and d >= START.get(t, ''): last = round(pm[d], 2)
        out.append(last)
    dpx['px'][t] = out
    dpx['spot'][t] = [float(ps[-1]['close']['value']), ps[-1]['close'].get('unit'), ps[-1]['date']]
    first = next(i for i, v in enumerate(out) if v is not None)
    print(f'     {sum(v is not None for v in out)} values from {dates[first]}; spot {dpx["spot"][t]}')
dpx['px'] = dict(sorted(dpx['px'].items())); dpx['spot'] = dict(sorted(dpx['spot'].items()))
json.dump(dpx, open('daily_px.json', 'w'), separators=(',', ':'))
print(f"daily_px.json {os.path.getsize('daily_px.json')/1e6:.2f} MB | tickers {len(dpx['px'])} | asof {dpx['asof']}")
