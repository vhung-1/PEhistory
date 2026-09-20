"""
realign_dpx_nofill.py — realign daily_px.json to the new data.json date axis WITHOUT
inventing a close for a trading day we could not fetch.

Why: the S&P Global connector was disconnected and needs re-authorization, which a
non-interactive session cannot do, so Fri 2026-09-18's closes could not be pulled. The P/E
panel advances to 18 Sep on its own sourced workbook data; the price panel cannot.

The splice scripts' realign loop forward-fills (`if dt in pm: last = ...; out.append(last)`),
which is correct for an exchange HOLIDAY — the market was shut, there is genuinely no new
close, and carrying the prior one forward is the standard convention. It is NOT correct here:
18 Sep was a real, open session with a real close that we simply do not have. Carrying 17 Sep
forward would present a stale price as that day's close, which is the fabrication §7's hard
rule forbids, and would silently corrupt every click-to-measure return ending on 18 Sep.

So this re-keys the stored prices by their own dates and re-emits against the new axis with NO
fill past the last sourced date. 2026-09-18 comes out null for all 91 names, and `asof` stays
at the last date actually sourced. `template.html` already handles exactly this: PXASOF =
DPXMETA.asof, and pxLagNote() renders a red banner saying prices run one day behind and the
latest date was left blank rather than carried forward, so measuring to it returns nothing.

Backfill by running the normal splice for 2026-09-18 once the connector is authorized again.
"""
import json, sys

old_dates = json.load(open('/tmp/data_prev.json'))['dates']
prev = json.load(open('/tmp/dpx_prev.json'))
main = json.load(open('data.json'))
D = main['dates']
LAST_SOURCED = prev['asof']          # last date with real fetched closes

for t, arr in prev['px'].items():
    if len(arr) != len(old_dates):
        sys.exit(f'!! HALT: {t} has {len(arr)} values against an old axis of {len(old_dates)}')

out = {}
for t, arr in prev['px'].items():
    m = {d: v for d, v in zip(old_dates, arr) if v is not None}
    out[t] = [(m.get(d) if d <= LAST_SOURCED else None) for d in D]

# nothing that survives may change value, and nothing may appear past the last sourced date
for t in out:
    m = {d: v for d, v in zip(old_dates, prev['px'][t]) if v is not None}
    for d, v in zip(D, out[t]):
        if v is not None and (d > LAST_SOURCED or m[d] != v):
            sys.exit(f'!! HALT: {t} {d} is wrong after realign')

unsourced = [d for d in D if d > LAST_SOURCED]
print(f'old axis {old_dates[0]} -> {old_dates[-1]} | new axis {D[0]} -> {D[-1]}')
print(f'last sourced close: {LAST_SOURCED}')
print(f'left blank (no sourced close, NOT carried forward): {unsourced}')
for d in unsourced:
    i = D.index(d)
    assert all(out[t][i] is None for t in out), f'{d} should be blank for every name'
print(f'  verified blank for all {len(out)} names')
i = D.index(LAST_SOURCED)
print(f'populated on {LAST_SOURCED}: {sum(1 for t in out if out[t][i] is not None)}/{len(out)}')

payload = {'asof': LAST_SOURCED, 'note': prev['note'], 'px': out}
json.dump(payload, open('daily_px.json', 'w'), separators=(',', ':'))
print(f"daily_px.json realigned to {len(D)} dates, asof {payload['asof']} (P/E panel asof {main['asof']})")
