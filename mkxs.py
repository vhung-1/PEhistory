"""Builds xs_data.json: reference P/E series, shown in the Name P/E tab and offered as a P/E-basis
option for their base ticker on the Pairs tab.

Two sources:
  1. cal_pe.json, written by mkdata.py from the CALENDARIZED block of the coverage workbook (FY+1 P/E
     calendarized to a December year-end, for the non-December year-end names). It refreshes with
     the workbook, so run this script after mkdata.py on every refresh.
  2. Pasted two-column text files (dd/mm/yyyy, value) listed in PASTED, kept in the repo so a series
     can be rebuilt exactly. None at present.
Series are stored by DATE, not by index: template.html aligns each one to DATA.dates when the page
loads. A date the series lacks (e.g. a US holiday row in the panel) stays null; nothing is filled.
Reference only -- never merged into data.json, the sub-sector aggregates, screens, the Consistency
records or the backtest.
"""
import json, datetime as dt

# Pasted series: key -> dict(file, base, label, short, kind, desc, note, pairnote, added). The RJF
# calendarized 2-yr-forward paste (29 Oct 2026) was retired on 30 Oct 2026, when the workbook began
# carrying calendarized P/E; it is in git history (xs_rjf_cy2.txt) if it is ever wanted back.
PASTED = {}

# Calendarized series from the workbook. When each one steps forward, measured from its unexplained
# one-day moves against the S&P share price, 2021-2026 (checked 30 Oct 2026).
ROLL = {
    'V US': 'late January', 'RJF US': 'late January', 'BEN US': 'late January', 'FICO US': 'late January or early February',
    'JKHY US': 'early February', 'HLNE US': 'early February', 'STEP US': 'early February', 'BILL US': 'early February',
    'AFRM US': 'early February', 'FDS US': 'late March', 'EXPN LN': 'mid-May', 'ICG LN': 'late May', 'AJB LN': 'late May',
}
CAVEAT = {
    'RJF US': 'It dips about 14% from 1 to 12 Oct 2026 on a flat share price and snaps back on 13 Oct, which looks like a vendor glitch.',
    'IGG LN': 'It is noisy: unexplained one-day jumps of +26% on 16 Dec 2025 and −57% on 30 Jul 2026.',
    'WISE LN': 'It is noisy: many unexplained one-day jumps of 10–25%.',
    'WLTH US': 'It is noisy: history only from Jan 2026, with unexplained jumps of up to +79% and −85% in Feb–Mar 2026 and −40% on 9 Oct 2026.',
    'AFRM US': 'It is noisy before 2025, with frequent unexplained jumps and multiples up to 165x.',
    'BILL US': 'Near-zero earnings in 2021–23 put the multiple above 200x on 108 dates (up to 16,502x in Aug 2022).',
}

data = json.load(open('data.json'))
panel = set(data['dates'])
out = {'series': {}}

def check(key, iso, vals, base, cap=None):
    assert base in data['pe'], f'{key}: base ticker {base} not in data.json'
    assert iso == sorted(iso) and len(set(iso)) == len(iso), f'{key}: dates must be strictly increasing'
    assert all(dt.date.fromisoformat(d).weekday() < 5 for d in iso), f'{key}: weekend row'
    assert all(v > 0 and (cap is None or v < cap) for v in vals), f'{key}: value out of range'
    off = [d for d in iso if d >= data['dates'][0] and d not in panel]
    assert not off, f'{key}: dates inside the panel window but not on its axis: {off[:5]}'
    gaps = sum(1 for d in data['dates'] if iso[0] <= d <= iso[-1] and d not in set(iso))
    print(f'{key}: {len(iso)} rows {iso[0]} -> {iso[-1]} | panel dates in span without a value: {gaps}')

cal = json.load(open('cal_pe.json'))
assert cal['asof'] == data['asof'], f"cal_pe.json asof {cal['asof']} != data.json asof {data['asof']}: re-run mkdata.py"
for t, s in sorted(cal['series'].items()):
    key = t + ' CAL'
    check(key, s['dates'], s['pe'], t)
    early = t in ROLL and ('January' in ROLL[t] or 'February' in ROLL[t])
    roll = (f' It steps forward once a year in {ROLL[t]}, '
            + ('close to when most December-year-end peers roll (February).' if early else 'later than most December-year-end peers (February).')) if t in ROLL else ''
    out['series'][key] = dict(
        base=t, label=f'{t} · calendarized', short='Calendarized', kind='calendarized FY+1 P/E', src='workbook', added='2026-10-30',
        desc='Bloomberg FY+1 P/E calendarized to a December year-end, from the coverage workbook',
        note=('Most of the year it covers the same calendar year as a December-year-end peer’s FY+1.' + roll + (' ' + CAVEAT[t] if t in CAVEAT else '')).strip(),
        pairnote=('Most of the year this compares the same calendar year of earnings as a December-year-end peer’s FY+1.' + roll
                  + (' ' + CAVEAT[t] if t in CAVEAT else '')).strip(),
        dates=s['dates'], pe=s['pe'])

for key, s in PASTED.items():
    rows = []
    for ln in open(s['file'], encoding='utf-8'):
        if ln.strip():
            d, v = ln.split()
            rows.append((dt.datetime.strptime(d, '%d/%m/%Y').date().isoformat(), float(v)))
    check(key, [r[0] for r in rows], [r[1] for r in rows], s['base'], cap=200)
    out['series'][key] = {**{f: s[f] for f in ('base', 'label', 'short', 'kind', 'desc', 'note', 'pairnote', 'added')},
                          'src': 'paste', 'dates': [r[0] for r in rows], 'pe': [r[1] for r in rows]}

json.dump(out, open('xs_data.json', 'w'), separators=(',', ':'))
print('wrote xs_data.json:', len(out['series']), 'series')
