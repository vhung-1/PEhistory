"""
pair_email.py — daily relative-P/E monitor email.

Sends an HTML email with a premium/discount chart for each curated pair (leg A's
1-yr-forward P/E divided by leg B's, rebased so its own 1-year mean sits at zero),
followed by absolute-P/E charts for a short watchlist. Horizon is 252 weekday rows
(~1 calendar year) ending at the panel's asof.

Charts are drawn in pure HTML table cells — no JS, no SVG, no external images — so
they render in every mail client with nothing to load and nothing to host.

Usage:  python pair_email.py            # build /tmp/pair_email.html only
        python pair_email.py --send     # build and send via Brevo
Env:    BREVO_API_KEY (required to send), PE_SRC, PE_RECIPIENT, PE_SENDER,
        PE_SENDER_NAME, PAIR_SUBJECT_TAG
"""
import json, os, sys, math, datetime, ssl, urllib.request, urllib.error

# Outbound HTTPS here goes through a proxy with its own CA bundle; build an SSL context
# from it so an unattended (scheduled) run verifies cleanly. Falls back to the default.
def _ctx():
    ca = os.environ.get('SSL_CERT_FILE') or '/root/.ccr/ca-bundle.crt'
    try:
        if os.path.exists(ca): return ssl.create_default_context(cafile=ca)
    except Exception:
        pass
    return None
CTX = _ctx()

SRC       = os.environ.get('PE_SRC', 'data.json')
RECIPIENT = os.environ.get('PE_RECIPIENT', 'vhung@attelascap.com')
SENDER    = os.environ.get('PE_SENDER', 'vhung@attelascap.com')
SENDER_NM = os.environ.get('PE_SENDER_NAME', 'P/E monitor agent')
DASH_URL  = 'https://vhung-1.github.io/PEhistory/Relative_PE_Dashboard.html'
WIN       = 252          # trailing weekday rows ~ 1 calendar year
STEP      = 7            # plot every 7th row -> 36 columns
COLW      = 14           # column width, px  (36 * 14 = 504px chart)
HALF      = 58           # px above / below the zero line

# Curated pairs, in the order requested. 'BLK/ROW' read as BLK/TROW (T. Rowe Price).
PAIRS = [('FDS US','LSEG LN'), ('MCO US','MSCI US'), ('LPLA US','SCHW US'),
         ('LPLA US','RJF US'), ('HOOD US','IBKR US'), ('V US','MA US'),
         ('ARES US','BX US'),  ('KKR US','BX US'),    ('TPG US','CG US'),
         ('EQT SS','CVC NA'),  ('BLK US','TROW US'),  ('LAZ US','PJT US'),
         ('EVR US','PJT US'),  ('EVR US','HLI US'),   ('MC US','PJT US'),
         ('AMUN FP','DWS GY'), ('SAVE SS','AZA SS')]
SINGLES = ['XYZ US', 'ADYEN NA', 'CHYM US']

INK, MUTED, FAINT, LINE = '#16303B', '#6B7A85', '#F3F6F8', '#D8DEE3'
GREEN, RED = '#157A3C', '#CC2A22'
BG, BR = '#173', '#C22'               # 3-char equivalents, repeated ~1,700x in the bars
DGREEN, DRED = '#053', '#811'         # latest column, drawn darker
PALE_R, PALE_G = '#FCF3F2', '#F2F9F4'
SHORT = {  # display names for the tickers this email touches
  'FDS US':'FactSet','LSEG LN':'LSEG','MCO US':'Moody’s','MSCI US':'MSCI','LPLA US':'LPL Financial',
  'SCHW US':'Schwab','RJF US':'Raymond James','HOOD US':'Robinhood','IBKR US':'Interactive Brokers',
  'V US':'Visa','MA US':'Mastercard','ARES US':'Ares','BX US':'Blackstone','KKR US':'KKR',
  'TPG US':'TPG','CG US':'Carlyle','EQT SS':'EQT','CVC NA':'CVC','BLK US':'BlackRock',
  'TROW US':'T. Rowe Price','LAZ US':'Lazard','PJT US':'PJT Partners','EVR US':'Evercore',
  'HLI US':'Houlihan Lokey','MC US':'Moelis','AMUN FP':'Amundi','DWS GY':'DWS','SAVE SS':'Nordnet',
  'AZA SS':'Avanza','XYZ US':'Block','ADYEN NA':'Adyen','CHYM US':'Chime'}

def sym(t): return t.rsplit(' ', 1)[0]

# ---------- statistics ----------
def stats(series, dates):
    """Trailing-window stats for one series (pair ratio or single-name P/E)."""
    pts = [(d, v) for d, v in zip(dates, series) if v is not None]
    if len(pts) < 30: return None
    vals = [v for _, v in pts]
    mean = sum(vals) / len(vals)
    var  = sum((v - mean) ** 2 for v in vals) / len(vals)      # population, per §9.6
    sd   = math.sqrt(var)
    cur  = vals[-1]
    lo, hi = min(vals), max(vals)
    pc   = 100.0 * sum(1 for v in vals if v <= cur) / len(vals)
    return dict(dates=[d for d, _ in pts], vals=vals, mean=mean, sd=sd, cur=cur,
                lo=lo, hi=hi, pc=pc, z=((cur - mean) / sd if sd > 0 else 0.0),
                dev=(cur / mean - 1.0) if mean else 0.0, n=len(vals))

def fmt(x, d=2): return ('{:,.%df}' % d).format(x)
def pct(x, d=1, sign=True):
    v = 100.0 * x
    if abs(v) < 0.05: return '0.0%'
    return ('{:+.%df}%%' % d).format(v) if sign else ('{:.%df}%%' % d).format(v)
def devcol(x): return RED if x > 0.0005 else GREEN if x < -0.0005 else INK

def pccol(pc):
    """Colour a percentile only at a genuine extreme.

    Percentile and deviation-from-mean can legitimately disagree on a skewed
    distribution (above the mean but below the median), so flipping the colour at
    exactly 50 puts a green bar next to a red premium and reads like a bug. Neutral
    through the middle of the range, coloured only in the outer 40%."""
    return RED if pc >= 60 else GREEN if pc <= 40 else MUTED

# ---------- chart ----------
# Markup is kept deliberately terse: 20 charts x ~51 columns means every byte per cell is
# multiplied ~2,000 times, and Gmail clips a message over ~102 KB. Row geometry (cell height,
# vertical-align, the pale premium/discount bands) lives in the stylesheet classes .U/.D so it
# is written once; only each bar's height and colour are inline. If a client drops <style> the
# bars still render at the correct size and colour, just top-aligned instead of on the centre
# line — degraded but readable.
STYLE = ('<style>'
         '.t{{border-collapse:collapse}}'
         '.U td{{height:{H}px;vertical-align:bottom;background:{pr};padding:0}}'
         '.D td{{height:{H}px;vertical-align:top;background:{pg};padding:0}}'
         '.Z td{{height:1px;background:{i};padding:0;font-size:0;line-height:0;'
         'mso-line-height-rule:exactly}}'
         '.U div,.D div{{font-size:0;line-height:0;mso-line-height-rule:exactly}}'
         '.w{{width:{w}px}}'
         '.x{{font-size:9px;color:{m}}}'
         '.x td{{padding-top:2px}}'
         '.k{{font-size:9px;color:{m};text-transform:uppercase;letter-spacing:.04em}}'
         '.v{{font-size:14px;font-weight:700}}'
         '.n{{font-size:14px;font-weight:400}}'
         '.s td{{padding:0 14px 0 0;white-space:nowrap}}'
         '.b{{margin:0 0 20px}}'
         '.c{{border:1px solid {L}}}'
         '</style>').format(H=HALF, pr=PALE_R, pg=PALE_G, i=INK, w=COLW, m=MUTED, L=LINE)

def chart(st):
    """Zero-centred premium/discount chart: leg ratio rebased on its own 1-yr mean."""
    devs = [v / st['mean'] - 1.0 for v in st['vals']]
    pick = devs[::-1][::STEP][::-1]                 # keep the latest point anchored right
    span = max(0.005, max(abs(x) for x in devs))    # per-chart scale, floor 0.5%
    ncol = len(pick)
    up, dn = [], []
    for i, x in enumerate(pick):
        h = int(round(min(1.0, abs(x) / span) * HALF))
        last = (i == ncol - 1)
        bar = '<td><div style="height:%dpx;background:%s"></div></td>'
        if x > 0:
            up.append(bar % (h, DRED if last else BR)); dn.append('<td></td>')
        else:
            up.append('<td></td>'); dn.append(bar % (h, DGREEN if last else BG))
    w = ncol * COLW
    return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            'class="t c" style="width:{w}px"><colgroup><col span="{n}" class="w"></colgroup>'
            '<tr class="U">{u}</tr><tr class="Z"><td colspan="{n}"></td></tr>'
            '<tr class="D">{d}</tr></table>'
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            'class="t x" style="width:{w}px"><tr><td align="left">{d0} &nbsp;· scale ±{s}</td>'
            '<td align="right">{d1}</td></tr></table>'
            ).format(w=w, u=''.join(up), n=ncol, d=''.join(dn),
                     d0=st['dates'][0], d1=st['dates'][-1], s=pct(span, 1, sign=False))

# ---------- blocks ----------
def kv(label, value, color=INK, bold=True):
    return ('<td><div class="k">{l}</div><div class="{w}" style="color:{c}">{v}</div></td>'
            ).format(l=label, c=color, v=value, w='v' if bold else 'n')

def block(title, sub, st, ratio=True):
    unit = 'x' if ratio else ''
    cells = [
        kv('now', fmt(st['cur']) + unit),
        kv('vs 1-yr mean', pct(st['dev']), devcol(st['dev'])),
        kv('1-yr mean', fmt(st['mean']) + unit, INK, False),
        kv('percentile', '{:.0f}'.format(st['pc']), pccol(st['pc'])),
        kv('z-score', '{:+.2f}'.format(st['z']), devcol(st['z'])),
        kv('1-yr range', fmt(st['lo']) + ' – ' + fmt(st['hi']), INK, False),
    ]
    return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            'class="t b" style="width:100%">'
            '<tr><td style="padding:0 0 4px">'
            '<span style="font-size:15px;font-weight:700;color:{i}">{t}</span>'
            '<span style="font-size:11px;color:{m}"> &nbsp;{s}</span></td></tr>'
            '<tr><td style="padding:0 0 6px"><table role="presentation" cellpadding="0" '
            'cellspacing="0" border="0" class="t s"><tr>{c}</tr>'
            '</table></td></tr><tr><td>{ch}</td></tr></table>'
            ).format(i=INK, t=title, m=MUTED, s=sub, c=''.join(cells), ch=chart(st))

def build(d):
    dates, pe = d['dates'], d['pe']
    win = dates[-WIN:]
    rows, blocks = [], []

    for a, b in PAIRS:
        A, B = pe[a][-WIN:], pe[b][-WIN:]
        ser = [(x / y if (x is not None and y not in (None, 0)) else None) for x, y in zip(A, B)]
        st = stats(ser, win)
        if st is None:
            rows.append((a, b, None)); continue
        la = stats(A, win); lb = stats(B, win)
        sub = ('{sa} {va} ÷ {sb} {vb} &nbsp;·&nbsp; {na} / {nb} &nbsp;·&nbsp; '
               '{n} trading days to {d}').format(
                   sa=sym(a), va=fmt(la['cur']), sb=sym(b), vb=fmt(lb['cur']),
                   na=SHORT.get(a, a), nb=SHORT.get(b, b), n=st['n'], d=st['dates'][-1])
        blocks.append(block(sym(a) + ' / ' + sym(b), sub, st))
        rows.append((a, b, st))

    sblocks = []
    for t in SINGLES:
        st = stats(pe[t][-WIN:], win)
        if st is None: continue
        sub = '{n} &nbsp;·&nbsp; own 1-yr-forward P/E &nbsp;·&nbsp; {c} trading days to {d}'.format(
            n=SHORT.get(t, t), c=st['n'], d=st['dates'][-1])
        sblocks.append(block(sym(t), sub, st, ratio=False))

    # ---- summary table (requested order) ----
    tr = []
    for a, b, st in rows:
        if st is None:
            tr.append('<tr><td style="padding:5px 8px;border-bottom:1px solid {L}">{p}</td>'
                      '<td colspan="4" style="padding:5px 8px;border-bottom:1px solid {L};'
                      'color:{m}">insufficient overlapping history</td></tr>'.format(
                          L=LINE, m=MUTED, p=sym(a) + ' / ' + sym(b)))
            continue
        w = int(round(st['pc'] / 100.0 * 90))
        bar = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
               'style="border-collapse:collapse;width:90px;background:{f};'
               'border:1px solid {L}"><tr>'
               '<td style="width:{w}px;height:9px;padding:0;background:{c};font-size:0;'
               'line-height:0;mso-line-height-rule:exactly"></td>'
               '<td style="padding:0;font-size:0;line-height:0"></td></tr></table>'
               ).format(f=FAINT, L=LINE, w=max(3, w), c=pccol(st['pc']))
        td = 'padding:5px 8px;border-bottom:1px solid ' + LINE
        tr.append(('<tr><td style="{td};font-weight:700;white-space:nowrap">{p}</td>'
                   '<td style="{td};text-align:right">{cur}x</td>'
                   '<td style="{td};text-align:right;color:{dc};font-weight:700">{dev}</td>'
                   '<td style="{td};text-align:right;color:{pcc}">{pc:.0f}</td>'
                   '<td style="{td}">{bar}</td></tr>').format(
                      td=td, p=sym(a) + ' / ' + sym(b), cur=fmt(st['cur']),
                      dc=devcol(st['dev']), dev=pct(st['dev']), pcc=pccol(st['pc']),
                      pc=st['pc'], bar=bar))
    th = ('padding:5px 8px;border-bottom:2px solid ' + INK + ';font-size:9.5px;color:' + MUTED +
          ';text-transform:uppercase;letter-spacing:.04em;font-weight:700')
    summary = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
               'style="border-collapse:collapse;width:100%;font-size:12px;color:{i}">'
               '<tr><th style="{th};text-align:left">Pair</th>'
               '<th style="{th};text-align:right">Ratio</th>'
               '<th style="{th};text-align:right">vs 1-yr mean</th>'
               '<th style="{th};text-align:right">%ile</th>'
               '<th style="{th};text-align:left">1-yr position</th></tr>{r}</table>'
               ).format(i=INK, th=th, r=''.join(tr))

    ok = [(a, b, st) for a, b, st in rows if st]
    rich  = max(ok, key=lambda r: r[2]['dev']) if ok else None
    cheap = min(ok, key=lambda r: r[2]['dev']) if ok else None
    extremes = ''
    if rich and cheap:
        extremes = ('<div style="font-size:12px;color:{i};margin:0 0 10px">'
                    'Widest premium <b style="color:{R}">{rp} {rv}</b> &nbsp;·&nbsp; '
                    'widest discount <b style="color:{G}">{cp} {cv}</b> '
                    '<span style="color:{m}">vs their own 1-year means</span></div>').format(
                        i=INK, R=RED, G=GREEN, m=MUTED,
                        rp=sym(rich[0]) + '/' + sym(rich[1]), rv=pct(rich[2]['dev']),
                        cp=sym(cheap[0]) + '/' + sym(cheap[1]), cv=pct(cheap[2]['dev']))

    # ---- staleness banner ----
    asof = datetime.date.fromisoformat(d['asof'])
    today = datetime.date.today()
    lag = sum(1 for i in range(1, (today - asof).days + 1)
              if (asof + datetime.timedelta(days=i)).weekday() < 5)
    banner = ''
    if lag > 2:
        banner = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
                  'style="border-collapse:collapse;width:100%;margin:0 0 12px"><tr>'
                  '<td style="background:#FFF8E6;border:1px solid #E8D9A8;border-radius:5px;'
                  'padding:8px 12px;font-size:12px;color:#7A5B12">'
                  '<b>Panel is {l} trading days behind.</b> Latest settled close in the data is '
                  '{a}; nothing moves until a fresh coverage workbook is loaded.</td></tr></table>'
                  ).format(l=lag, a=d['asof'])

    h = [STYLE,
         '<div style="font-family:Segoe UI,Helvetica,Arial,sans-serif;color:%s;max-width:600px;'
         'margin:0 auto;padding:16px 18px;background:#ffffff">' % INK]
    h.append('<div style="font-size:10.5px;color:%s;letter-spacing:.06em;'
             'text-transform:uppercase">P/E monitor agent</div>' % MUTED)
    h.append('<h2 style="margin:3px 0 2px;font-size:19px">Relative P/E — 1-year horizon</h2>')
    h.append('<div style="font-size:12px;color:{m};margin:0 0 12px">{np} pairs and {ns} single '
             'names &nbsp;·&nbsp; 1-yr-forward (FY+1) P/E &nbsp;·&nbsp; '
             '{n} trading days to <b style="color:{i}">{a}</b></div>'.format(
                 m=MUTED, i=INK, np=len(PAIRS), ns=len(SINGLES), n=len(win), a=d['asof']))
    h.append(banner)
    h.append(extremes)
    h.append(summary)
    h.append('<div style="font-size:10.5px;color:{m};margin:5px 0 0;line-height:1.5">'
             '<b>%ile</b> is where today\u2019s ratio sits in its own trailing-year '
             'distribution (0 = cheapest of the year, 100 = richest); it is coloured only '
             'beyond the 40/60 marks. It can sit below 50 while the ratio is above its mean '
             'when the year\u2019s distribution is skewed \u2014 both readings are correct.'
             '</div>'.format(m=MUTED))
    h.append('<h3 style="margin:24px 0 2px;font-size:13px;letter-spacing:.03em;'
             'text-transform:uppercase;color:%s">Relative P/E charts</h3>' % MUTED)
    h.append('<div style="font-size:11px;color:{m};margin:0 0 14px;line-height:1.5">'
             'Each chart plots leg A’s forward P/E divided by leg B’s over the trailing '
             'year, rebased so the pair’s own 1-year mean is the centre line. '
             '<b style="color:{R}">Red above</b> = A rich vs B; '
             '<b style="color:{G}">green below</b> = A cheap vs B. The right-hand column is the '
             'latest close and is drawn darker. Vertical scale is set per pair.</div>'.format(
                 m=MUTED, R=RED, G=GREEN))
    h.extend(blocks)
    h.append('<h3 style="margin:26px 0 2px;font-size:13px;letter-spacing:.03em;'
             'text-transform:uppercase;color:%s">Absolute P/E charts</h3>' % MUTED)
    h.append('<div style="font-size:11px;color:{m};margin:0 0 14px;line-height:1.5">'
             'Each name’s own forward P/E against its trailing-1-year mean, same convention: '
             '<b style="color:{R}">red</b> = above its own mean, '
             '<b style="color:{G}">green</b> = below.</div>'.format(m=MUTED, R=RED, G=GREEN))
    h.extend(sblocks)
    h.append('<div style="font-size:10.5px;color:{m};margin-top:20px;border-top:1px solid {L};'
             'padding-top:8px;line-height:1.55">'
             'Source: Bloomberg 1-year-forward (FY+1) consensus P/E from the coverage panel, '
             'asof {a}. Weekday closes only — weekends, US market holidays and the intraday '
             'pull row are excluded. Percentile and z-score are computed on the trailing '
             '{n} rows; z uses the population standard deviation. The FY+1 denominator steps once '
             'a year on each company’s results date, which leaves a residual step of roughly '
             '3–4% in a pair even though both legs roll. '
             'Full history and the click-to-measure tool: '
             '<a href="{u}" style="color:#15697A">dashboard</a>.</div>'.format(
                 m=MUTED, L=LINE, a=d['asof'], n=len(win), u=DASH_URL))
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
    print('built /tmp/pair_email.html (%.0f KB) asof %s' % (len(html) / 1024, d['asof']))
    if '--send' in sys.argv:
        tag = os.environ.get('PAIR_SUBJECT_TAG', '')
        subj = 'Relative P/E — 1yr horizon — %s%s' % (d['asof'], tag)
        sys.exit(0 if send_brevo(html, subj) else 1)
