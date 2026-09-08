"""
realign_0908.py — Realign daily_px.json to the new data.json date axis.

The 2026-09-08 workbook is a revisions-only refresh: ASOF stays 2026-09-04 (5/6 Sep
weekend, 7 Sep US Labor Day, 8 Sep intraday — all excluded per CLAUDE.md §7a), so no
trading day is added. The workbook's rolling 6-year window did advance, dropping the
oldest row (2020-09-07), so the axis shrinks 1565 -> 1564 rows.

The new axis is a strict subset of the old one, so this is a pure date-keyed remap of
the already-spliced panel: no new S&P pull, no interpolation, and the single
back-adjustment basis (CLAUDE.md §9 invariant 3) is preserved exactly. See §7c step 6.
"""
import json

new_dates = json.load(open('data.json'))['dates']
old = json.load(open('/tmp/dpx_prev.json'))
old_dates = json.load(open('/tmp/data_prev.json'))['dates']

missing = [d for d in new_dates if d not in set(old_dates)]
assert not missing, f'new axis has dates absent from the spliced panel: {missing}'

oi = {d: i for i, d in enumerate(old_dates)}
px = {t: [ser[oi[d]] for d in new_dates] for t, ser in old['px'].items()}

out = {'asof': new_dates[-1], 'note': old['note'], 'px': px}
json.dump(out, open('daily_px.json', 'w'), separators=(',', ':'))

drop = [d for d in old_dates if d not in set(new_dates)]
print(f'realigned {len(px)} tickers to {len(new_dates)} rows '
      f'({new_dates[0]} -> {new_dates[-1]}); dropped {drop}')
print('asof', out['asof'], '| all series full length:',
      all(len(v) == len(new_dates) for v in px.values()))
