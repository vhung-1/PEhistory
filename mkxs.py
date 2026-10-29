"""Builds xs_data.json: investor-supplied reference P/E series, shown in the Name P/E tab and offered
as a P/E-basis option for their base ticker on the Pairs tab.

Each source is a two-column text file (dd/mm/yyyy, value) pasted by the investor, kept in the
repo so the series can be rebuilt exactly. Series are stored by DATE, not by index:
template.html aligns each one to DATA.dates when the page loads, so a daily refresh needs no
step here. A date the series lacks (e.g. a US holiday row in the panel) stays null; nothing is
filled. Reference only -- never merged into data.json, the sub-sector aggregates, screens, the
Consistency records or the backtest.
"""
import json, datetime as dt

SOURCES = {
    'RJF US CY2': dict(file='xs_rjf_cy2.txt', base='RJF US', label='RJF US · CY2 fwd', short='CY2 fwd',
                       kind='calendarized 2-yr-forward P/E', added='2026-10-29',
                       desc='calendarized 2-year-forward P/E, pasted by the investor on 29 Oct 2026',
                       note='Unlike the FY+1 series it does not step at the October FY results, but it has steps of its own '
                            'on a flat share price: \u221215.6% on 3 Oct 2025, \u22129.5% on 12 Dec 2024 and \u22127.3% on 15 Jul 2024.',
                       pairnote='It runs about a year further out than RJF\u2019s FY+1: its implied EPS has been 9\u201320% higher on 80% of dates '
                                '(median 16%), level only just after RJF\u2019s late-October roll. Against a peer\u2019s FY+1 the ratio '
                                'therefore sits lower by about a year of RJF growth, so read it against its own average rather than as a level.'),
}

data = json.load(open('data.json'))
panel = set(data['dates'])
out = {'series': {}}
for key, s in SOURCES.items():
    assert s['base'] in data['pe'], f"{key}: base ticker {s['base']} not in data.json"
    rows = []
    for ln in open(s['file'], encoding='utf-8'):
        if not ln.strip():
            continue
        d, v = ln.split()
        rows.append((dt.datetime.strptime(d, '%d/%m/%Y').date(), float(v)))
    ds = [r[0] for r in rows]
    assert ds == sorted(ds) and len(set(ds)) == len(ds), f'{key}: dates must be strictly increasing'
    assert all(d.weekday() < 5 for d in ds), f'{key}: weekend row'
    assert all(0 < v < 200 for _, v in rows), f'{key}: value outside 0-200x'
    iso = [d.isoformat() for d in ds]
    off = [d for d in iso if d >= data['dates'][0] and d not in panel]
    assert not off, f'{key}: dates inside the panel window but not on its axis: {off[:5]}'
    out['series'][key] = {**{f: s[f] for f in ('base', 'label', 'short', 'kind', 'desc', 'note', 'pairnote', 'added')},
                          'dates': iso, 'pe': [v for _, v in rows]}
    gaps = sum(1 for d in data['dates'] if iso[0] <= d <= iso[-1] and d not in set(iso))
    print(f'{key}: {len(rows)} rows {iso[0]} -> {iso[-1]} | panel dates in span without a value: {gaps}')
json.dump(out, open('xs_data.json', 'w'), separators=(',', ':'))
print('wrote xs_data.json')
