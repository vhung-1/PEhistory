"""
splice_new.py — Build new daily_px.json by splicing 3 new S&P price pull files
onto the existing daily_px.json. Handles date-axis realignment.
"""
import json, statistics, sys

TR = '/root/.claude/projects/-home-user-PEhistory/8a11d578-e9f0-5dd3-8083-8128422f78d9/tool-results'
PULL_FILES = [
    TR + '/mcp-S_P_Global-get_prices_from_identifiers-1784475413122.txt',
    TR + '/mcp-S_P_Global-get_prices_from_identifiers-1784475414185.txt',
    TR + '/mcp-S_P_Global-get_prices_from_identifiers-1784475416404.txt',
]

# S&P result key → BBG ticker
SMAP = {
    # plain US
    'CME':'CME US','ICE':'ICE US','NDAQ':'NDAQ US','CBOE':'CBOE US','TW':'TW US',
    'MKTX':'MKTX US','MIAX':'MIAX US','MRX':'MRX US',
    'SPGI':'SPGI US','MCO':'MCO US','MSCI':'MSCI US','FDS':'FDS US','EFX':'EFX US',
    'TRU':'TRU US','FICO':'FICO US','VRSK':'VRSK US',
    'PYPL':'PYPL US','XYZ':'XYZ US','TOST':'TOST US','SHOP':'SHOP US','SOFI':'SOFI US',
    'FISV':'FISV US','FIS':'FIS US','GPN':'GPN US','JKHY':'JKHY US','CPAY':'CPAY US',
    'WEX':'WEX US','AFRM':'AFRM US','KLAR':'KLAR US','BILL':'BILL US','CHYM':'CHYM US',
    'MQ':'MQ US','FOUR':'FOUR US','RELY':'RELY US','WU':'WU US',
    'LAZ':'LAZ US','EVR':'EVR US','HLI':'HLI US','PWP':'PWP US','PJT':'PJT US',
    'PIPR':'PIPR US','ARES':'ARES US','APO':'APO US','BX':'BX US','KKR':'KKR US',
    'OWL':'OWL US','CG':'CG US','TPG':'TPG US','STEP':'STEP US','HLNE':'HLNE US',
    'BLK':'BLK US','TROW':'TROW US','AB':'AB US','BEN':'BEN US','IVZ':'IVZ US',
    'AMP':'AMP US','SCHW':'SCHW US','LPLA':'LPLA US','HOOD':'HOOD US','IBKR':'IBKR US',
    'COIN':'COIN US','RJF':'RJF US','SF':'SF US','WLTH':'WLTH US','ETOR':'ETOR US',
    'CRCL':'CRCL US','FIGR':'FIGR US',
    # exchange-qualified US
    'NYSE:MA':'MA US','NYSE:V':'V US','NYSE:BAM':'BAM US','NYSE:MC':'MC US',
    # foreign
    'SWX:PGHN':'PGHN SW','OM:EQT':'EQT SS','ENXTAM:CVC':'CVC NA','XTRA:DWS':'DWS GY',
    'XTRA:DB1':'DB1 GY','XTRA:FTK':'FTK GY','LSE:LSEG':'LSEG LN','LSE:EXPN':'EXPN LN',
    'LSE:WISE':'WISE LN','LSE:ICG':'ICG LN','ENXTPA:ENX':'ENX FP','ENXTPA:AMUN':'AMUN FP',
    'ENXTAM:ADYEN':'ADYEN NA','BIT:BGN':'BGN IM','BIT:FBK':'FBK IM',
    'OM:SAVE':'SAVE SS','LSE:IGG':'IGG LN','LSE:AJB':'AJB LN','OM:AZA':'AZA SS',
    'SWX:SQN':'SQN SW',
}

def load_pull(fp):
    """Extract date->close map per BBG ticker from a pull result file."""
    raw = json.loads(open(fp).read())
    out = {}
    for key, blk in raw['results'].items():
        bbg = SMAP.get(key)
        if not bbg:
            print(f'  WARN: no SMAP entry for key {key!r}')
            continue
        prices = (blk or {}).get('data', {}).get('prices', []) or []
        pm = {}
        for p in prices:
            v = p.get('close', {}).get('value')
            if v not in (None, '', 'N/A'):
                try:
                    pm[p['date']] = float(v)
                except (ValueError, TypeError):
                    pass
        if pm:
            out[bbg] = pm
        else:
            print(f'  WARN: {bbg} ({key}) — no price data')
    return out

# Load all 3 pull files
print('Loading pull files...')
pull = {}
for fp in PULL_FILES:
    batch = load_pull(fp)
    for bbg, pm in batch.items():
        if bbg in pull:
            pull[bbg].update(pm)  # merge (shouldn't overlap across batches)
        else:
            pull[bbg] = pm
print(f'  Pull tickers: {len(pull)}')

# Load existing daily_px.json and reconstruct date->price dict using old dates
# Old dates from git HEAD: 2020-07-15 to 2026-07-14 (1565 days)
import subprocess
old_dates_raw = subprocess.check_output(['git','show','HEAD:data.json']).decode()
old_dates = json.loads(old_dates_raw)['dates']
print(f'  Old dates: {old_dates[0]} -> {old_dates[-1]} ({len(old_dates)} days)')

old_dpx_raw = json.load(open('daily_px.json'))
old_px = {}  # BBG -> date->price
for bbg, arr in old_dpx_raw['px'].items():
    pm = {}
    for i, v in enumerate(arr):
        if v is not None:
            pm[old_dates[i]] = v
    old_px[bbg] = pm

# Load new data.json dates
new_data = json.load(open('data.json'))
new_dates = new_data['dates']
univ = set(new_data['pe'].keys())
print(f'  New dates: {new_dates[0]} -> {new_dates[-1]} ({len(new_dates)} days)')
print(f'  Universe: {len(univ)} tickers')

NEW_DATES = {'2026-07-15', '2026-07-16', '2026-07-17'}

# Splice and build
print('\nComputing scale factors and splicing...')
flags = []
full = {}  # BBG -> date->price (on old basis, extended to new dates)

missing_from_pull = sorted(univ - set(pull.keys()))
if missing_from_pull:
    print(f'!! HALT: {len(missing_from_pull)} names missing from pull: {missing_from_pull}')
    sys.exit(1)

for bbg in sorted(univ):
    base_pm = dict(old_px.get(bbg, {}))
    pull_pm = pull.get(bbg, {})

    # Overlap: dates present in both base and pull
    overlap = [d for d in pull_pm if d in base_pm and pull_pm[d] > 0 and base_pm[d] > 0]
    if len(overlap) < 5:
        print(f'  WARN: {bbg} only {len(overlap)} overlap points')
        F = 1.0
        max_dev = 0.0
    else:
        ratios = [base_pm[d] / pull_pm[d] for d in overlap]
        F = statistics.median(ratios)
        max_dev = max(abs(r / F - 1) for r in ratios)
        if max_dev > 0.01:
            flags.append((bbg, round(max_dev * 100, 2), len(overlap)))

    # Apply F to new dates from pull
    for d in NEW_DATES:
        if d in pull_pm and pull_pm[d] > 0:
            base_pm[d] = round(pull_pm[d] * F, 2)

    full[bbg] = base_pm

if flags:
    print(f'\nScale-factor anomalies >1% (possible split artifact):')
    for f in flags:
        print(f'  {f}')
else:
    print('  Scale factors: all OK (max dev < 1%)')

# Verify all 3 new dates present for US names
us_names = [t for t in univ if t.endswith(' US')]
for nd in sorted(NEW_DATES):
    missing_nd = [t for t in us_names if nd not in full.get(t, {})]
    if missing_nd:
        print(f'!! HALT: {len(missing_nd)} US names missing {nd}: {missing_nd}')
        sys.exit(1)
    print(f'  {nd}: all {len(us_names)} US names present')

# Realign to new date axis (forward-fill exchange holidays, null before listing)
print('\nRealigning to new date axis...')
DPX = {}
for t in sorted(univ):
    pm = full.get(t, {})
    out = []
    last = None
    for dt in new_dates:
        if dt in pm:
            last = round(pm[dt], 2)
        out.append(last)
    DPX[t] = out
    # Verify length
    assert len(out) == len(new_dates), f'{t}: length mismatch {len(out)} vs {len(new_dates)}'

print(f'  All {len(DPX)} tickers aligned to {len(new_dates)} dates')

# Write
import os
payload = {
    'asof': new_data['asof'],
    'note': 'S&P Global daily ADJUSTED close (total return), local currency, single back-adjustment basis, aligned to trading days, holiday-ffilled',
    'px': DPX
}
json.dump(payload, open('daily_px.json', 'w'), separators=(',', ':'))
sz = os.path.getsize('daily_px.json') / 1e6
print(f'\ndaily_px.json {sz:.2f} MB | tickers {len(DPX)} | panel len {len(new_dates)}')
print(f'asof: {payload["asof"]}')
