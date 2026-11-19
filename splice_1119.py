"""
splice_1119.py — Add 2026-11-17 (backfill) and 2026-11-18 daily closes to daily_px.json via the scale-factor splice
(CLAUDE.md §7c), and fill IGG LN's blank 2026-11-16. 17 Nov was left blank by the 2026-11-17 after-close refresh (S&P had
no US closes yet); IG's 16 Nov was blank because S&P had no close for it then. S&P now carries IG's new Jersey listing as
one continuous series with the old one (F = 1.0000 over the overlap), so its 16-18 Nov closes are sourced.
old axis = /tmp/data_prev.json (11/17), new axis = current data.json (11/18). A date is filled only where the stored panel
has no value for it, so no stored price changes.
"""
import json, statistics, subprocess, sys, os

TR = '/root/.claude/projects/-home-user-PEhistory/8a11d578-e9f0-5dd3-8083-8128422f78d9/tool-results'
PULL_FILES = [
    TR + '/mcp-S_P_Global-get_prices_from_identifiers-1795073178174-npbo2k.txt',
    TR + '/mcp-S_P_Global-get_prices_from_identifiers-1795073180444-rdiqfz.txt',
    TR + '/mcp-S_P_Global-get_prices_from_identifiers-1795073182308-vk99xq.txt',
]
NEW_DATES = {"2026-11-16", "2026-11-17", "2026-11-18"}

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

SPOT = {}   # ticker -> [last close as quoted, currency, date]; feeds the scenario panels' share price

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
        # The pull's last close is the actual (unadjusted) close: S&P back-adjusts to the end date, so
        # the end-date value carries no adjustment (checked against an adjusted=false pull, 2026-11-03).
        last = [q for q in prices if q.get('close', {}).get('value') not in (None, '', 'N/A')]
        if bbg and last:
            SPOT[bbg] = [float(last[-1]['close']['value']), last[-1]['close'].get('unit'), last[-1]['date']]
    return out

print('Loading pull files...')
pull = {}
for fp in PULL_FILES:
    for bbg, pm in load_pull(fp).items():
        pull.setdefault(bbg, {}).update(pm)
print(f'  Pull tickers: {len(pull)}')

# Old axis + old daily_px (7/20, on disk after branch reset)
old_dates = json.load(open('/tmp/data_prev.json'))['dates']
print(f'  Old dates: {old_dates[0]} -> {old_dates[-1]} ({len(old_dates)})')
old_dpx = json.load(open('/tmp/dpx_prev.json'))
old_px = {}
for bbg, arr in old_dpx['px'].items():
    old_px[bbg] = {old_dates[i]: v for i, v in enumerate(arr) if v is not None}
print(f'  New dates: {new_dates[0]} -> {new_dates[-1]} ({len(new_dates)}) | universe {len(univ)}')

missing = sorted(univ - set(pull.keys()))
if missing:
    print(f'!! HALT: {len(missing)} names missing from pull: {missing}'); sys.exit(1)

print('\nComputing scale factors and splicing 11/16 (IGG only) + 11/17 + 11/18...')
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
        if d in pull_pm and pull_pm[d] > 0 and d not in base_pm:   # fill blanks only; never overwrite a stored close
            base_pm[d] = round(pull_pm[d] * F, 2)
    full[bbg] = base_pm

if flags:
    print('\nScale-factor anomalies >1% (single-date holiday ffill artifacts expected):')
    for f in flags: print('  ', f)
else:
    print('  Scale factors: all OK (<1%)')

# Presence guard. Every previous splice added a single ordinary trading day, so requiring all
# 71 US names to be priced was sufficient. 2026-09-07 is US Labor Day — the market was shut, so
# S&P returns no US close at all and that blanket check fired on a perfectly good pull. The
# distinction that matters is partial vs total absence:
#   * NO US name priced  -> market holiday. The realign below carries the prior close forward,
#     which is the correct representation (CLAUDE.md §7c step 4). Confirm it really is a holiday
#     by checking some non-US name did trade that day; if nothing traded anywhere, the pull is bad.
#   * SOME US names priced and others not -> genuinely incomplete pull. Halt.
us = [t for t in univ if t.endswith(' US')]
foreign = [t for t in univ if not t.endswith(' US')]
for nd in sorted(NEW_DATES):
    have = [t for t in us if nd in full.get(t, {})]
    miss = [t for t in us if nd not in full.get(t, {})]
    if not have:
        fo = [t for t in foreign if nd in full.get(t, {})]
        if not fo:
            print(f'!! HALT: {nd} priced for nothing at all ({len(us)} US and {len(foreign)} '
                  f'non-US all absent) — bad pull, not a holiday'); sys.exit(1)
        print(f'  {nd}: US market holiday — 0/{len(us)} US priced, {len(fo)}/{len(foreign)} '
              f'non-US priced; US will be forward-filled')
    elif miss:
        print(f'!! HALT: {nd} partially priced — {len(miss)} of {len(us)} US names missing '
              f'while {len(have)} are present: {sorted(miss)}'); sys.exit(1)
    else:
        print(f'  {nd}: all {len(us)} US names present')

# No-fill guard (CLAUDE.md §10): forward-filling a new date is right only when the name's market was shut.
# A name with no close on a new date while other names on the same exchange did trade (IGG LN on 2026-11-16:
# the old IG Group plc was delisted at 8am that day when the Jersey holding company listed in its place) gets
# null from that date on, never the prior close.
exch = lambda t: FOREIGN[t].split(':')[0] if t in FOREIGN else 'US'
traded = {(exch(t), d) for t in univ for d in NEW_DATES if d in full.get(t, {})}
DPX = {}
for t in sorted(univ):
    pm = full.get(t, {}); out = []; last = None
    for dt in new_dates:
        if dt in pm: last = round(pm[dt], 2)
        elif dt in NEW_DATES and (exch(t), dt) in traded:
            if last is not None: print(f'  NO-FILL: {t} has no close on {dt} although {exch(t)} traded; left null')
            last = None
        out.append(last)
    assert len(out) == len(new_dates), f'{t}: len mismatch'
    DPX[t] = out

payload = {'asof': new_data['asof'],
           'note': 'S&P Global daily ADJUSTED close (total return), local currency, single back-adjustment basis, aligned to trading days, holiday-ffilled',
           'px': DPX,
           'spot': {t: SPOT[t] for t in sorted(univ) if t in SPOT}}
json.dump(payload, open('daily_px.json', 'w'), separators=(',', ':'))
print(f"\ndaily_px.json {os.path.getsize('daily_px.json')/1e6:.2f} MB | tickers {len(DPX)} | panel {len(new_dates)} | asof {payload['asof']}")
