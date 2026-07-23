"""
splice_721.py — Add 2026-07-21 daily closes to daily_px.json via the scale-factor
splice (CLAUDE.md §7c). One new trading day. old axis = git HEAD:data.json (7/20),
new axis = current data.json (7/21). Reads the 3 S&P pull files, computes
F=median(base/pull) over the June–July overlap, applies F to 7/21, realigns.
"""
import json, statistics, subprocess, sys, os

TR = '/root/.claude/projects/-home-user-PEhistory/8a11d578-e9f0-5dd3-8083-8128422f78d9/tool-results'
PULL_FILES = [
    TR + '/mcp-S_P_Global-get_prices_from_identifiers-1784792307389.txt',
    TR + '/mcp-S_P_Global-get_prices_from_identifiers-1784792314298.txt',
    TR + '/mcp-S_P_Global-get_prices_from_identifiers-1784792321624.txt',
]
NEW_DATES = {'2026-07-22'}

# Build S&P-key -> BBG map as the inverse of the BBG -> identifier map used for the pull
FOREIGN={'LSEG LN':'LSE:LSEG','DB1 GY':'XTRA:DB1','ENX FP':'ENXTPA:ENX','EXPN LN':'LSE:EXPN','WISE LN':'LSE:WISE','ADYEN NA':'ENXTAM:ADYEN','PGHN SW':'SWX:PGHN','EQT SS':'OM:EQT','CVC NA':'ENXTAM:CVC','DWS GY':'XTRA:DWS','AMUN FP':'ENXTPA:AMUN','ICG LN':'LSE:ICG','FTK GY':'XTRA:FTK','BGN IM':'BIT:BGN','FBK IM':'BIT:FBK','SAVE SS':'OM:SAVE','IGG LN':'LSE:IGG','AJB LN':'LSE:AJB','AZA SS':'OM:AZA','SQN SW':'SWX:SQN'}
QUAL={'MA US':'NYSE:MA','V US':'NYSE:V','BAM US':'NYSE:BAM','MC US':'NYSE:MC'}

new_data = json.load(open('data.json'))
new_dates = new_data['dates']
univ = set(new_data['pe'].keys())

SMAP={}
for t in univ:
    if t in FOREIGN: SMAP[FOREIGN[t]]=t
    elif t in QUAL: SMAP[QUAL[t]]=t
    elif t.endswith(' US'): SMAP[t[:-3]]=t

def load_pull(fp):
    raw = json.loads(open(fp).read())
    out = {}
    for key, blk in raw['results'].items():
        bbg = SMAP.get(key)
        if not bbg:
            print(f'  WARN: no SMAP entry for key {key!r}'); continue
        prices = (blk or {}).get('data', {}).get('prices', []) or []
        pm = {}
        for p in prices:
            v = p.get('close', {}).get('value')
            if v not in (None, '', 'N/A'):
                try: pm[p['date']] = float(v)
                except (ValueError, TypeError): pass
        if pm: out[bbg] = pm
        else: print(f'  WARN: {bbg} ({key}) — no price data')
    return out

print('Loading pull files...')
pull = {}
for fp in PULL_FILES:
    for bbg, pm in load_pull(fp).items():
        pull.setdefault(bbg, {}).update(pm)
print(f'  Pull tickers: {len(pull)}')

# Old axis + old daily_px (7/20, on disk after branch reset)
old_dates = json.loads(subprocess.check_output(['git','show','HEAD:data.json']).decode())['dates']
print(f'  Old dates: {old_dates[0]} -> {old_dates[-1]} ({len(old_dates)})')
old_dpx = json.load(open('daily_px.json'))
old_px = {}
for bbg, arr in old_dpx['px'].items():
    old_px[bbg] = {old_dates[i]: v for i, v in enumerate(arr) if v is not None}
print(f'  New dates: {new_dates[0]} -> {new_dates[-1]} ({len(new_dates)}) | universe {len(univ)}')

missing = sorted(univ - set(pull.keys()))
if missing:
    print(f'!! HALT: {len(missing)} names missing from pull: {missing}'); sys.exit(1)

print('\nComputing scale factors and splicing 7/21...')
flags = []; full = {}
for bbg in sorted(univ):
    base_pm = dict(old_px.get(bbg, {}))
    pull_pm = pull.get(bbg, {})
    overlap = [d for d in pull_pm if d in base_pm and pull_pm[d] > 0 and base_pm[d] > 0]
    if len(overlap) < 5:
        print(f'  WARN: {bbg} only {len(overlap)} overlap points'); F = 1.0
    else:
        ratios = [base_pm[d] / pull_pm[d] for d in overlap]
        F = statistics.median(ratios)
        max_dev = max(abs(r / F - 1) for r in ratios)
        if max_dev > 0.01: flags.append((bbg, round(max_dev*100, 2), len(overlap)))
    for d in NEW_DATES:
        if d in pull_pm and pull_pm[d] > 0:
            base_pm[d] = round(pull_pm[d] * F, 2)
    full[bbg] = base_pm

if flags:
    print('\nScale-factor anomalies >1% (single-date holiday ffill artifacts expected):')
    for f in flags: print('  ', f)
else:
    print('  Scale factors: all OK (<1%)')

us = [t for t in univ if t.endswith(' US')]
for nd in sorted(NEW_DATES):
    miss = [t for t in us if nd not in full.get(t, {})]
    if miss:
        print(f'!! HALT: {len(miss)} US names missing {nd}: {miss}'); sys.exit(1)
    print(f'  {nd}: all {len(us)} US names present')

DPX = {}
for t in sorted(univ):
    pm = full.get(t, {}); out = []; last = None
    for dt in new_dates:
        if dt in pm: last = round(pm[dt], 2)
        out.append(last)
    assert len(out) == len(new_dates), f'{t}: len mismatch'
    DPX[t] = out

payload = {'asof': new_data['asof'],
           'note': 'S&P Global daily ADJUSTED close (total return), local currency, single back-adjustment basis, aligned to trading days, holiday-ffilled',
           'px': DPX}
json.dump(payload, open('daily_px.json', 'w'), separators=(',', ':'))
print(f"\ndaily_px.json {os.path.getsize('daily_px.json')/1e6:.2f} MB | tickers {len(DPX)} | panel {len(new_dates)} | asof {payload['asof']}")
