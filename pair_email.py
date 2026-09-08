"""
pair_email.py — daily relative-P/E monitor email.

One chart per curated pair plus a short absolute-P/E watchlist, on a 1-year horizon.

The charts are the dashboard's own charts: mkcharts.mjs drives the built
Relative_PE_Dashboard.html in headless Chromium and screenshots its Pairs / Name P/E
canvases to PNG, which this email references by URL. Mail clients strip both <canvas>
and <svg>, so a real line chart has to travel as an image; rendering the site's own
chart rather than re-drawing it means the email can never drift from the dashboard.

Every figure here is computed the way the dashboard's stat() computes it, so the two
agree cell for cell:
  * a pair is the premium/discount  P/E_A / P/E_B - 1,  not a ratio multiple;
  * the 1-year window is a calendar cut 12 months back from the last date (~262
    weekday rows), matching the dashboard's own "1Y" button, not a fixed 252-row count;
  * the standard deviation is the sample one (n-1) and the percentile counts strictly
    below the current value.

Images can be blocked by the reader's mail client, so the summary table and the
per-chart stat strips are inline HTML and carry every number on their own.

Usage:  python pair_email.py            # build /tmp/pair_email.html only
        python pair_email.py --send     # build and send via Brevo
Env:    BREVO_API_KEY (required to send), PE_SRC, PE_RECIPIENT, PE_SENDER,
        PE_SENDER_NAME, PAIR_CHART_BASE, PAIR_SUBJECT_TAG
"""
import json, os, sys, math, datetime, ssl, urllib.request, urllib.error

# Outbound HTTPS here goes through a proxy with its own CA bundle; build an SSL context from
# it so an unattended (scheduled) run verifies cleanly. Falls back to the default elsewhere.
def _ctx():
    ca = os.environ.get('SSL_CERT_FILE') or '/root/.ccr/ca-bundle.crt'
    try:
        if os.path.exists(ca): return ssl.create_default_context(cafile=ca)
    except Exception:
        pass
    return None
CTX = _ctx()

SRC        = os.environ.get('PE_SRC', 'data.json')
RECIPIENT  = os.environ.get('PE_RECIPIENT', 'vhung@attelascap.com')
SENDER     = os.environ.get('PE_SENDER', 'vhung@attelascap.com')
SENDER_NM  = os.environ.get('PE_SENDER_NAME', 'P/E monitor agent')
DASH_URL   = 'https://vhung-1.github.io/PEhistory/Relative_PE_Dashboard.html'
CHART_BASE = os.environ.get('PAIR_CHART_BASE', 'https://vhung-1.github.io/PEhistory/charts')
MONTHS     = 12          # window, in months — the dashboard's "1Y"
IMGW       = 560         # displayed chart width, px (fits a 600px body)

# Curated pairs, in the order requested. 'BLK/ROW' read as BLK/TROW (T. Rowe Price).
# Keep in step with PAIRS / SINGLES in mkcharts.mjs.
PAIRS = [('FDS US','LSEG LN'), ('MCO US','MSCI US'), ('LPLA US','SCHW US'),
         ('LPLA US','RJF US'), ('HOOD US','IBKR US'), ('V US','MA US'),
         ('ARES US','BX US'),  ('KKR US','BX US'),    ('TPG US','CG US'),
         ('EQT SS','CVC NA'),  ('BLK US','TROW US'),  ('LAZ US','PJT US'),
         ('EVR US','PJT US'),  ('EVR US','HLI US'),   ('MC US','PJT US'),
         ('AMUN FP','DWS GY'), ('SAVE SS','AZA SS')]
SINGLES = ['XYZ US', 'ADYEN NA', 'CHYM US']

INK, MUTED, FAINT, LINE = '#16303B', '#6B7A85', '#F3F6F8', '#D8DEE3'
# Dashboard convention (CLAUDE.md §9.5): green = cheap, red = rich.
GREEN, RED, SERIES, AVG = '#2E7D52', '#C0392B', '#15697A', '#E2733A'
SHORT = {
  'FDS US':'FactSet','LSEG LN':'LSEG','MCO US':'Moody’s','MSCI US':'MSCI','LPLA US':'LPL Financial',
  'SCHW US':'Schwab','RJF US':'Raymond James','HOOD US':'Robinhood','IBKR US':'Interactive Brokers',
  'V US':'Visa','MA US':'Mastercard','ARES US':'Ares','BX US':'Blackstone','KKR US':'KKR',
  'TPG US':'TPG','CG US':'Carlyle','EQT SS':'EQT','CVC NA':'CVC','BLK US':'BlackRock',
  'TROW US':'T. Rowe Price','LAZ US':'Lazard','PJT US':'PJT Partners','EVR US':'Evercore',
  'HLI US':'Houlihan Lokey','MC US':'Moelis','AMUN FP':'Amundi','DWS GY':'DWS','SAVE SS':'Nordnet',
  'AZA SS':'Avanza','XYZ US':'Block','ADYEN NA':'Adyen','CHYM US':'Chime'}

def sym(t): return t.rsplit(' ', 1)[0]
def slug(t): return t.replace(' ', '').lower()

# ---------- statistics: mirrors the dashboard's sliceMonths() + stat() ----------
def slice_months(dates, vals, m):
    """Calendar cut m months back from the last observation (the dashboard's 1Y button)."""
    if not vals: return [], []
    last = datetime.date.fromisoformat(dates[-1])
    y, mo = last.year, last.month - m
    while mo <= 0: mo += 12; y -= 1
    d = min(last.day, [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1])
    cut = datetime.date(y, mo, d)
    keep = [(dt, v) for dt, v in zip(dates, vals) if datetime.date.fromisoformat(dt) >= cut]
    return [dt for dt, _ in keep], [v for _, v in keep]

def stat(dates, vals):
    if not vals: return None
    n = len(vals)
    mean = sum(vals) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in vals) / (n - 1 if n > 1 else 1))  # sample, as JS
    cur = vals[-1]
    return dict(dates=dates, vals=vals, n=n, mean=mean, sd=sd, cur=cur,
                lo=min(vals), hi=max(vals),
                pile=100.0 * sum(1 for x in vals if x < cur) / n,   # strictly below, as JS
                z=((cur - mean) / sd if sd else 0.0))

def pair_series(pe, dates, a, b):
    """Premium / discount of A over B, as the dashboard defines it: P/E_a / P/E_b - 1."""
    dd, vv = [], []
    for dt, x, y in zip(dates, pe[a], pe[b]):
        if x is not None and y not in (None, 0):
            dd.append(dt); vv.append(x / y - 1.0)
    return dd, vv

def name_series(pe, dates, t):
    keep = [(dt, v) for dt, v in zip(dates, pe[t]) if v is not None]
    return [d for d, _ in keep], [v for _, v in keep]

# ---------- formatting ----------
def sgn(x, dp=1):
    """Signed percentage with the dashboard's typographic minus."""
    v = 100.0 * x
    if abs(v) < 0.05: v = 0.0
    return ('+' if v >= 0 else '−') + ('{:.%df}' % dp).format(abs(v)) + '%'
def fx(x): return '{:.1f}x'.format(x)
def col(x): return RED if x > 1e-9 else GREEN if x < -1e-9 else INK
def pcol(p):
    """Colour a percentile only at a real extreme — see the note under the summary table."""
    return RED if p >= 60 else GREEN if p <= 40 else MUTED

# ---------- building blocks ----------
def kv(label, value, color=INK, bold=True):
    return ('<td><div class="k">{l}</div><div class="{w}" style="color:{c}">{v}</div></td>'
            ).format(l=label, c=color, v=value, w='v' if bold else 'n')

def img(name, alt, ver):
    return ('<a href="{u}" style="text-decoration:none"><img src="{b}/{n}.png?v={ver}" '
            'width="{w}" alt="{alt}" style="display:block;width:{w}px;max-width:100%;'
            'height:auto;border:1px solid {L}"></a>').format(
                u=DASH_URL, b=CHART_BASE, n=name, ver=ver, w=IMGW, alt=alt, L=LINE)

def block(title, sub, cells, name, alt, ver):
    return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            'class="t b" style="width:100%">'
            '<tr><td style="padding:0 0 4px">'
            '<span style="font-size:15px;font-weight:700;color:{i}">{t}</span>'
            '<span style="font-size:11px;color:{m}"> &nbsp;{s}</span></td></tr>'
            '<tr><td style="padding:0 0 7px"><table role="presentation" cellpadding="0" '
            'cellspacing="0" border="0" class="t s"><tr>{c}</tr></table></td></tr>'
            '<tr><td>{im}</td></tr></table>').format(
                i=INK, t=title, m=MUTED, s=sub, c=''.join(cells), im=img(name, alt, ver))

STYLE = ('<style>'
         '.t{border-collapse:collapse}'
         '.k{font-size:9px;color:%s;text-transform:uppercase;letter-spacing:.04em}'
         '.v{font-size:14px;font-weight:700}'
         '.n{font-size:14px;font-weight:400}'
         '.s td{padding:0 14px 0 0;white-space:nowrap}'
         '.b{margin:0 0 22px}'
         '</style>') % MUTED

def build(d):
    dates, pe = d['dates'], d['pe']
    ver = d['asof']                      # cache-buster: clients cache by URL
    rows, blocks, sblocks = [], [], []

    for a, b in PAIRS:
        dd, vv = slice_months(*pair_series(pe, dates, a, b), MONTHS)
        st = stat(dd, vv)
        rows.append((a, b, st))
        if st is None: continue
        _, la = slice_months(*name_series(pe, dates, a), MONTHS)
        _, lb = slice_months(*name_series(pe, dates, b), MONTHS)
        sub = ('{sa} {va} ÷ {sb} {vb} &nbsp;·&nbsp; {na} / {nb} &nbsp;·&nbsp; '
               '{n} obs to {dt}').format(sa=sym(a), va=fx(la[-1]), sb=sym(b), vb=fx(lb[-1]),
                                         na=SHORT.get(a, a), nb=SHORT.get(b, b),
                                         n=st['n'], dt=st['dates'][-1])
        cells = [kv('current', sgn(st['cur']), col(st['cur'])),
                 kv('average · window', sgn(st['mean']), INK, False),
                 kv('current vs avg', sgn(st['cur'] - st['mean']), col(st['cur'] - st['mean'])),
                 kv('percentile', '{:.0f}'.format(st['pile']), pcol(st['pile'])),
                 kv('z-score', ('+' if st['z'] >= 0 else '−') + '{:.2f}'.format(abs(st['z'])),
                    col(st['z'])),
                 kv('range', sgn(st['lo'], 0) + ' · ' + sgn(st['hi'], 0), INK, False)]
        blocks.append(block(sym(a) + ' / ' + sym(b), sub, cells,
                            slug(a) + '-' + slug(b),
                            '%s vs %s relative P/E, 1 year' % (sym(a), sym(b)), ver))

    for t in SINGLES:
        dd, vv = slice_months(*name_series(pe, dates, t), MONTHS)
        st = stat(dd, vv)
        if st is None: continue
        up, dn = st['mean'] + st['sd'], st['mean'] - st['sd']
        sub = '{n} &nbsp;·&nbsp; own 1-yr-forward P/E &nbsp;·&nbsp; {c} obs to {dt}'.format(
            n=SHORT.get(t, t), c=st['n'], dt=st['dates'][-1])
        cells = [kv('current p/e', fx(st['cur']), col(st['cur'] - st['mean'])),
                 kv('average · window', fx(st['mean']), INK, False),
                 kv('+1σ', fx(up), INK, False), kv('−1σ', fx(dn), INK, False),
                 kv('percentile', '{:.0f}'.format(st['pile']), pcol(st['pile'])),
                 kv('z-score', ('+' if st['z'] >= 0 else '−') + '{:.2f}'.format(abs(st['z'])),
                    col(st['z']))]
        sblocks.append(block(sym(t), sub, cells, slug(t),
                            '%s forward P/E vs history, 1 year' % sym(t), ver))

    # ---- summary table (requested order; carries every number if images are blocked) ----
    td = 'padding:5px 8px;border-bottom:1px solid ' + LINE
    tr = []
    for a, b, st in rows:
        if st is None:
            tr.append('<tr><td style="{td};font-weight:700">{p}</td><td colspan="4" '
                      'style="{td};color:{m}">no overlapping history in the window</td></tr>'
                      .format(td=td, m=MUTED, p=sym(a) + ' / ' + sym(b)))
            continue
        w = max(3, int(round(st['pile'] / 100.0 * 90)))
        bar = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
               'class="t" style="width:90px;background:{f};border:1px solid {L}"><tr>'
               '<td style="width:{w}px;height:9px;padding:0;background:{c};font-size:0;'
               'line-height:0;mso-line-height-rule:exactly"></td>'
               '<td style="padding:0;font-size:0;line-height:0"></td></tr></table>'
               ).format(f=FAINT, L=LINE, w=w, c=pcol(st['pile']))
        tr.append(('<tr><td style="{td};font-weight:700;white-space:nowrap">{p}</td>'
                   '<td style="{td};text-align:right;color:{cc};font-weight:700">{cur}</td>'
                   '<td style="{td};text-align:right" >{mean}</td>'
                   '<td style="{td};text-align:right;color:{vc}">{vs}</td>'
                   '<td style="{td};text-align:right;color:{pc}">{pl:.0f}</td>'
                   '<td style="{td}">{bar}</td></tr>').format(
                      td=td, p=sym(a) + ' / ' + sym(b), cc=col(st['cur']), cur=sgn(st['cur']),
                      mean=sgn(st['mean']), vc=col(st['cur'] - st['mean']),
                      vs=sgn(st['cur'] - st['mean']), pc=pcol(st['pile']), pl=st['pile'],
                      bar=bar))
    th = ('padding:5px 8px;border-bottom:2px solid {i};font-size:9.5px;color:{m};'
          'text-transform:uppercase;letter-spacing:.04em;font-weight:700').format(i=INK, m=MUTED)
    summary = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
               'class="t" style="width:100%;font-size:12px;color:{i}">'
               '<tr><th style="{th};text-align:left">Pair</th>'
               '<th style="{th};text-align:right">Current</th>'
               '<th style="{th};text-align:right">Avg · 1yr</th>'
               '<th style="{th};text-align:right">vs avg</th>'
               '<th style="{th};text-align:right">%ile</th>'
               '<th style="{th};text-align:left">1-yr position</th></tr>{r}</table>'
               ).format(i=INK, th=th, r=''.join(tr))

    ok = [(a, b, st) for a, b, st in rows if st]
    ext = ''
    if ok:
        rich = max(ok, key=lambda r: r[2]['cur'] - r[2]['mean'])
        chp = min(ok, key=lambda r: r[2]['cur'] - r[2]['mean'])
        ext = ('<div style="font-size:12px;margin:0 0 10px">Furthest above its own average '
               '<b style="color:{R}">{rp} {rv}</b> &nbsp;·&nbsp; furthest below '
               '<b style="color:{G}">{cp} {cv}</b></div>').format(
                   R=RED, G=GREEN, rp=sym(rich[0]) + '/' + sym(rich[1]),
                   rv=sgn(rich[2]['cur'] - rich[2]['mean']),
                   cp=sym(chp[0]) + '/' + sym(chp[1]), cv=sgn(chp[2]['cur'] - chp[2]['mean']))

    # ---- staleness: the panel only moves when a fresh coverage workbook is loaded ----
    asof = datetime.date.fromisoformat(d['asof'])
    today = datetime.date.today()
    lag = sum(1 for i in range(1, (today - asof).days + 1)
              if (asof + datetime.timedelta(days=i)).weekday() < 5)
    banner = ''
    if lag > 2:
        banner = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
                  'class="t" style="width:100%;margin:0 0 12px"><tr><td style="background:#FFF8E6;'
                  'border:1px solid #E8D9A8;padding:8px 12px;font-size:12px;color:#7A5B12">'
                  '<b>Panel is {l} weekdays behind.</b> Latest settled close in the data is {a}; '
                  'nothing moves until a fresh coverage workbook is loaded.</td></tr></table>'
                  ).format(l=lag, a=d['asof'])

    h = [STYLE, '<div style="font-family:Segoe UI,Helvetica,Arial,sans-serif;color:%s;'
         'max-width:600px;margin:0 auto;padding:16px 18px;background:#ffffff">' % INK]
    h.append('<div style="font-size:10.5px;color:%s;letter-spacing:.06em;'
             'text-transform:uppercase">P/E monitor agent</div>' % MUTED)
    h.append('<h2 style="margin:3px 0 2px;font-size:19px">Relative P/E — 1-year horizon</h2>')
    h.append('<div style="font-size:12px;color:{m};margin:0 0 12px">{a} pairs and {b} single '
             'names &nbsp;·&nbsp; 1-yr-forward (FY+1) P/E &nbsp;·&nbsp; window ends '
             '<b style="color:{i}">{d}</b></div>'.format(m=MUTED, i=INK, a=len(PAIRS),
                                                         b=len(SINGLES), d=d['asof']))
    h.append(banner); h.append(ext); h.append(summary)
    h.append('<div style="font-size:10.5px;color:{m};margin:5px 0 0;line-height:1.5">'
             'A pair is quoted the dashboard’s way — leg A’s forward P/E over leg '
             'B’s, minus one — so <b>Current</b> is the premium (<span style="color:{R}">'
             'red</span>) or discount (<span style="color:{G}">green</span>) A trades at against '
             'B, and <b>vs avg</b> is that gap in percentage points against the pair’s own '
             '1-year average. <b>%ile</b> is where today sits in the window’s own '
             'distribution, coloured only beyond the 40/60 marks: it can read below 50 while the '
             'gap is above average when the year’s distribution is skewed, and both readings '
             'are correct.</div>'.format(m=MUTED, R=RED, G=GREEN))
    h.append('<h3 style="margin:24px 0 2px;font-size:13px;letter-spacing:.03em;'
             'text-transform:uppercase;color:%s">Relative P/E charts</h3>' % MUTED)
    h.append('<div style="font-size:11px;color:{m};margin:0 0 14px;line-height:1.5">'
             'The dashboard’s own Pairs chart for each name, on its 1Y window: '
             '<b style="color:{S}">teal</b> is the premium/discount through time, '
             '<b style="color:{A}">orange</b> the window average. Tap a chart to open the '
             'dashboard.</div>'.format(m=MUTED, S=SERIES, A=AVG))
    h.extend(blocks)
    h.append('<h3 style="margin:26px 0 2px;font-size:13px;letter-spacing:.03em;'
             'text-transform:uppercase;color:%s">Absolute P/E charts</h3>' % MUTED)
    h.append('<div style="font-size:11px;color:{m};margin:0 0 14px;line-height:1.5">'
             'The dashboard’s Name P/E chart: the name’s own forward P/E in '
             '<b style="color:{S}">teal</b>, its window average in <b style="color:{A}">orange</b>, '
             'with the shaded ±1σ band.</div>'.format(m=MUTED, S=SERIES, A=AVG))
    h.extend(sblocks)
    h.append('<div style="font-size:10.5px;color:{m};margin-top:20px;border-top:1px solid {L};'
             'padding-top:8px;line-height:1.55">'
             'Charts are screenshots of the dashboard’s own Pairs and Name P/E charts, so '
             'they match the site exactly; if your mail client blocks images, every figure is '
             'still in the table and the strips above each chart. Source: Bloomberg '
             '1-year-forward (FY+1) consensus P/E from the coverage panel, asof {a}. Weekday '
             'settled closes only. The 1-year window is a calendar cut 12 months back from the '
             'last date, and the standard deviation is the sample one — both as the dashboard '
             'computes them. The FY+1 denominator steps once a year on each company’s results '
             'date, which leaves a residual step of roughly 3–4% in a pair even though both '
             'legs roll. <a href="{u}" style="color:{S}">Open the dashboard</a>.</div>'.format(
                 m=MUTED, L=LINE, a=d['asof'], u=DASH_URL, S=SERIES))
    h.append('</div>')
    return ''.join(h)

def send_brevo(html, subject):
    key = os.environ.get('BREVO_API_KEY')
    if not key:
        print('!! BREVO_API_KEY not set'); return False
    body = json.dumps({'sender': {'name': SENDER_NM, 'email': SENDER},
                       'to': [{'email': RECIPIENT}], 'subject': subject,
                       'htmlContent': html}).encode()
    req = urllib.request.Request('https://api.brevo.com/v3/smtp/email', data=body,
        headers={'api-key': key, 'content-type': 'application/json',
                 'accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
            print('Brevo %s: %s' % (r.status, r.read().decode()[:200]))
            return 200 <= r.status < 300
    except urllib.error.HTTPError as e:
        print('Brevo HTTPError %s: %s' % (e.code, e.read().decode()[:400])); return False
    except Exception as e:
        print('Brevo error: %r' % e); return False

if __name__ == '__main__':
    d = (json.loads(urllib.request.urlopen(SRC, timeout=60, context=CTX).read())
         if SRC.startswith('http') else json.load(open(SRC)))
    html = build(d)
    open('/tmp/pair_email.html', 'w').write(html)
    print('built /tmp/pair_email.html (%.0f KB) asof %s | charts from %s'
          % (len(html) / 1024, d['asof'], CHART_BASE))
    if '--send' in sys.argv:
        subj = 'Relative P/E — 1yr horizon — %s%s' % (
            d['asof'], os.environ.get('PAIR_SUBJECT_TAG', ''))
        sys.exit(0 if send_brevo(html, subj) else 1)
