"""
realign_sw.py — realign sw_data.json to the current data.json date axis WITHOUT the
software workbook.

Why this exists: `mksw.py` needs `bbg_software_mults.xlsx`, which is gitignored (licensed
vendor data, never committed), so a fresh container cannot run it. But mksw.py's alignment
step is a pure date-keyed lookup — build {date: value} from the workbook, then emit
[map.get(d) for d in data.json['dates']], with None for any date the workbook lacks (every
date after SW_ASOF included). That lookup can be reproduced exactly from the PREVIOUS
sw_data.json plus the previous date axis: re-key the stored values by their own dates and
re-emit against the new axis.

This re-indexes already-sourced values by the dates they were sourced for. It interpolates
nothing and invents nothing (CLAUDE.md §7 hard rule): a date absent from the old axis — i.e.
the newly added trading day, which is after SW_ASOF anyway — comes out None, exactly as
mksw.py would produce it. Same idea as realign_0908.py for the price panel.

Run mksw.py instead whenever the workbook is present; this is the fallback.
"""
import json, sys

old_dates = json.load(open('/tmp/data_prev.json'))['dates']
sw = json.load(open('sw_data.json'))
main = json.load(open('data.json'))
D = main['dates']

for t, arr in sw['pe'].items():
    if len(arr) != len(old_dates):
        sys.exit(f'!! HALT: {t} has {len(arr)} values against an old axis of {len(old_dates)}')

# re-key by date, then re-emit against the new axis
out = {}
for t, arr in sw['pe'].items():
    m = {d: v for d, v in zip(old_dates, arr) if v is not None}
    out[t] = [m.get(d) for d in D]

# every value that survives must be identical to the one stored for that same date
for t in out:
    m = {d: v for d, v in zip(old_dates, sw['pe'][t]) if v is not None}
    for d, v in zip(D, out[t]):
        if v is not None and m[d] != v:
            sys.exit(f'!! HALT: {t} {d} changed value during realign')

lost = [d for d in old_dates if d not in set(D)]
gained = [d for d in D if d not in set(old_dates)]
print(f'old axis {old_dates[0]} -> {old_dates[-1]} | new axis {D[0]} -> {D[-1]}')
print(f'dropped {lost} | added {gained} (added dates are after SW_ASOF, so None as mksw.py emits)')
for t in out:
    print(f'  {t:10s} non-null {sum(1 for v in out[t] if v is not None):5d}  last non-null '
          f'{max((D[i] for i, v in enumerate(out[t]) if v is not None), default=None)}')

payload = {'asof': main['asof'], 'names': sw['names'], 'pe': out}
json.dump(payload, open('sw_data.json', 'w'), separators=(',', ':'))
print(f"sw_data.json realigned to {len(D)} dates, asof {payload['asof']}")
