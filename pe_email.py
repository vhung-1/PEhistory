"""
pe_email.py — Weekly coverage P/E monitor email (HTML, email-safe) sent via Brevo.

For each sub-sector: a table of every covered name with its 1-year-forward (FY+1)
P/E, the 1-week change in that multiple, and a range-position graphic showing where
today's multiple sits within its own trailing-1-year history — so cheap/expensive
vs own history reads at a glance.

The position graphic is driven by the PERCENTILE within the trailing year, not the
raw min-max position: a single near-breakeven spike (EPS -> 0, P/E explodes) blows
out the max and would make a genuinely mid-range name look "cheap" on a min-max
basis. Percentile is robust to that (same reasoning as the dashboard's Range tab).

Data source: data.json (the same 1-yr-forward P/E panel the dashboard embeds). Run
locally against the repo copy, or point SRC at the live https URL for a scheduled
job. Email-safe HTML only: inline styles, role=presentation tables, fixed-px bars,
no JS / SVG / external images.

Usage:
  python pe_email.py                 # build HTML -> /tmp/pe_email.html (no send)
  python pe_email.py --send          # build + send via Brevo to RECIPIENT
  python pe_email.py --send --subject-tag SAMPLE
"""
import json, os, sys, datetime, urllib.request, urllib.error

SRC       = os.environ.get('PE_SRC', 'data.json')
RECIPIENT = os.environ.get('PE_RECIPIENT', 'vhung@attelascap.com')
SENDER    = os.environ.get('PE_SENDER', 'vhung@attelascap.com')
SENDER_NM = os.environ.get('PE_SENDER_NAME', 'Coverage P/E Monitor')
DASH_URL  = 'https://vhung-1.github.io/PEhistory/Relative_PE_Dashboard.html'
WIN       = 252   # trailing weekday rows ~ 1 calendar year

# skill display labels -> data.json sub-sector keys (membership validated against the panel)
ORDER = [('Exchanges & Trading Venues','Exchanges'),('Information Services','Info Services'),
         ('Payments / Fintech','Payments & Fintech'),('M&A Boutiques','M&A Boutiques'),
         ('Alternative Asset Managers','Alternatives'),('Traditional Asset Managers','Traditional AM'),
         ('Wealth / Brokers','Wealth & Brokers')]
NAMES = {'CME US':'CME Group','ICE US':'Intercontinental Exch','NDAQ US':'Nasdaq','CBOE US':'Cboe',
  'LSEG LN':'LSEG','DB1 GY':'Deutsche Börse','ENX FP':'Euronext','TW US':'Tradeweb','MKTX US':'MarketAxess',
  'MIAX US':'Miami Intl','MRX US':'Marex','SPGI US':'S&P Global','MCO US':'Moody’s','MSCI US':'MSCI',
  'FDS US':'FactSet','EFX US':'Equifax','TRU US':'TransUnion','EXPN LN':'Experian','FICO US':'Fair Isaac',
  'VRSK US':'Verisk','V US':'Visa','MA US':'Mastercard','PYPL US':'PayPal','XYZ US':'Block','ADYEN NA':'Adyen',
  'TOST US':'Toast','SHOP US':'Shopify','SOFI US':'SoFi','FISV US':'Fiserv','FIS US':'FIS','GPN US':'Global Payments',
  'JKHY US':'Jack Henry','CPAY US':'Corpay','WEX US':'WEX','AFRM US':'Affirm','KLAR US':'Klarna','BILL US':'BILL',
  'CHYM US':'Chime','MQ US':'Marqeta','FOUR US':'Shift4','WISE LN':'Wise','RELY US':'Remitly','WU US':'Western Union',
  'LAZ US':'Lazard','EVR US':'Evercore','MC US':'Moelis','HLI US':'Houlihan Lokey','PWP US':'Perella Weinberg',
  'PJT US':'PJT Partners','PIPR US':'Piper Sandler','PGHN SW':'Partners Group','EQT SS':'EQT','CVC NA':'CVC',
  'ICG LN':'ICG','ARES US':'Ares','APO US':'Apollo','BX US':'Blackstone','KKR US':'KKR','OWL US':'Blue Owl',
  'CG US':'Carlyle','BAM US':'Brookfield AM','TPG US':'TPG','STEP US':'StepStone','HLNE US':'Hamilton Lane',
  'BLK US':'BlackRock','TROW US':'T. Rowe Price','DWS GY':'DWS','AMUN FP':'Amundi','AB US':'AllianceBernstein',
  'BEN US':'Franklin Res','IVZ US':'Invesco','AMP US':'Ameriprise','SCHW US':'Schwab','LPLA US':'LPL Financial',
  'HOOD US':'Robinhood','IBKR US':'Interactive Brokers','COIN US':'Coinbase','RJF US':'Raymond James',
  'SF US':'Stifel','BGN IM':'Banca Generali','FBK IM':'FinecoBank','FTK GY':'Flatexdegiro','CRCL US':'Circle',
  'FIGR US':'Figure','ETOR US':'eToro','WLTH US':'Wealthfront','SQN SW':'Swissquote','AZA SS':'Avanza',
  'SAVE SS':'Nordnet','IGG LN':'IG Group','AJB LN':'AJ Bell'}

# zone colour ramp by percentile (green = cheap vs own history, red = expensive).
# Returns (strong, pale, tag). Pale fills are solid hex, not alpha — 8-digit hex is
# unreliable across Gmail / Outlook.
def zone(pc):
    if pc is None: return ('#9AA7B3','#EAEEF1','')
    if pc <= 10:  return ('#1B7A4B','#DCEDE3','▼ cheap')
    if pc <= 30:  return ('#3A9E68','#E1F0E8','')
    if pc <= 50:  return ('#8CA36B','#EDF1E6','')
    if pc <= 70:  return ('#C99A3F','#F6EEDD','')
    if pc <= 90:  return ('#C0632E','#F6E4D8','')
    return ('#B02418','#F5DEDB','▲ rich')

def ordinal(k):
    m = k % 100
    suf = 'th' if 11 <= m <= 13 else {1:'st',2:'nd',3:'rd'}.get(k % 10, 'th')
    return suf

def compute(d):
    D, PE, N = d['dates'], d['pe'], len(d['dates'])
    by = {}
    for disp, key in ORDER:
        out = []
        for t in d['sectors'][key]:
            a = PE.get(t)
            if not a: continue
            ci = next((i for i in range(N-1,-1,-1) if a[i] is not None), None)
            if ci is None: continue
            cur = a[ci]
            wi = ci-5; prev = a[wi] if wi>=0 and a[wi] is not None else None
            chg = (cur-prev) if prev is not None else None
            win = [a[i] for i in range(max(0,ci-WIN+1),ci+1) if a[i] is not None]
            if len(win) >= 20:
                lo, hi = min(win), max(win)
                pc = round(100*sum(1 for v in win if v <= cur)/len(win))
            else:
                lo = hi = pc = None
            out.append(dict(t=t, nm=NAMES.get(t,t), cur=cur, chg=chg, lo=lo, hi=hi, pc=pc, n=len(win)))
        out.sort(key=lambda r: r['pc'] if r['pc'] is not None else 999)   # cheapest first
        by[disp] = out
    return by

def bar(r):
    # marker-on-track: light track, thin zone-tint fill to the percentile point, bold marker line.
    TRACK = 132
    if r['pc'] is None:
        return '<span style="color:#9AA7B3;font-size:12px;">insufficient history</span>'
    col, tint, tag = zone(r['pc'])
    fill = max(2, round(TRACK * r['pc']/100))
    track = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="%d" '
             'style="width:%dpx;background:#EAEEF1;border-radius:3px;border-collapse:separate;">'
             '<tr>'
             '<td height="13" width="%d" style="width:%dpx;background:%s;border-right:2px solid %s;'
             'border-radius:3px 0 0 3px;font-size:0;line-height:0;">&nbsp;</td>'
             '<td height="13" style="font-size:0;line-height:0;">&nbsp;</td>'
             '</tr></table>') % (TRACK, TRACK, fill, fill, tint, col)
    lo = ('%.1f' % r['lo']).rstrip('0').rstrip('.')
    hi = ('%.1f' % r['hi']).rstrip('0').rstrip('.')
    tagspan = (' <span style="color:%s;font-weight:600;font-size:11px;white-space:nowrap;">%s</span>' % (col, tag)) if tag else ''
    return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            '<td style="font:11px \'Segoe UI\',Arial,sans-serif;color:#9AA7B3;padding-right:6px;white-space:nowrap;">%sx</td>'
            '<td>%s</td>'
            '<td style="font:11px \'Segoe UI\',Arial,sans-serif;color:#9AA7B3;padding-left:6px;white-space:nowrap;">%sx</td>'
            '<td style="font:12px \'Segoe UI\',Arial,sans-serif;color:%s;font-weight:700;padding-left:10px;white-space:nowrap;">%s<sup style="font-weight:400;font-size:9px;">%s</sup>%s</td>'
            '</tr></table>') % (lo, track, hi, col, r['pc'], ordinal(r['pc']), tagspan)

def chg_cell(r):
    if r['chg'] is None:
        return '<span style="color:#9AA7B3;">–</span>'
    # dashboard convention: falling multiple = cheaper = green; rising = richer = red.
    # A move under 0.05x rounds to zero — show a flat neutral "0.0", never a signed "−0.0".
    if abs(r['chg']) < 0.05:
        return '<span style="color:#6B7A88;font-weight:600;">0.0</span>'
    c = '#2E7D52' if r['chg'] < 0 else '#C0392B'
    s = ('−%.1f' % abs(r['chg'])) if r['chg'] < 0 else ('+%.1f' % r['chg'])
    return '<span style="color:%s;font-weight:600;">%s</span>' % (c, s)

def build_html(d):
    by = compute(d)
    asof = d['asof']
    dt = datetime.date.fromisoformat(asof).strftime('%a %d %b %Y')
    S = "font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
    h = []
    h.append('<div style="background:#F1F4F6;padding:22px 0;%s">' % S)
    h.append('<table role="presentation" align="center" cellpadding="0" cellspacing="0" border="0" width="660" '
             'style="width:660px;max-width:660px;margin:0 auto;background:#FFFFFF;border:1px solid #E1E7EC;border-radius:8px;">')
    # header
    h.append('<tr><td style="padding:26px 30px 18px;border-bottom:2px solid #16404E;">'
             '<div style="font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#5A7A86;font-weight:600;">Weekly coverage monitor</div>'
             '<div style="font-size:23px;font-weight:700;color:#16303B;margin-top:4px;">Forward P/E vs 1-year history</div>'
             '<div style="font-size:13px;color:#6B7A88;margin-top:6px;">1-year-forward (FY+1) P/E &middot; Bloomberg &middot; as of <b style="color:#16303B;">%s</b> &middot; %d names</div>'
             '</td></tr>' % (dt, sum(len(v) for v in by.values())))
    # legend
    h.append('<tr><td style="padding:14px 30px 6px;">'
             '<div style="font-size:12px;color:#6B7A88;line-height:1.6;">'
             'The bar shows where today’s multiple sits within its own trailing-year range '
             '(<span style="color:#9AA7B3;">low</span> → <span style="color:#9AA7B3;">high</span>); '
             'the number is its <b>percentile</b> in that year. '
             '<span style="color:#1B7A4B;font-weight:600;">Green / short = cheap</span> vs its own history, '
             '<span style="color:#B02418;font-weight:600;">red / long = expensive</span>. '
             '1-week &Delta; is coloured green when the multiple <i>fell</i> (cheaper), red when it <i>rose</i>. '
             'Rows are ordered cheapest first.'
             '</div></td></tr>')
    for disp, _ in ORDER:
        rows = by[disp]
        if not rows: continue
        h.append('<tr><td style="padding:22px 30px 0;">'
                 '<div style="font-size:15px;font-weight:700;color:#16404E;border-left:3px solid #16404E;padding-left:9px;">%s '
                 '<span style="color:#9AA7B3;font-weight:500;font-size:12px;">%d</span></div></td></tr>' % (disp, len(rows)))
        h.append('<tr><td style="padding:8px 30px 0;">')
        h.append('<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="width:100%;border-collapse:collapse;font-size:13px;">')
        h.append('<tr style="font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:#93A0AB;">'
                 '<td style="padding:5px 8px 5px 0;border-bottom:1px solid #E1E7EC;">Name</td>'
                 '<td align="right" style="padding:5px 10px;border-bottom:1px solid #E1E7EC;">P/E</td>'
                 '<td align="right" style="padding:5px 10px;border-bottom:1px solid #E1E7EC;">1w &Delta;</td>'
                 '<td style="padding:5px 0 5px 12px;border-bottom:1px solid #E1E7EC;">Position vs 1-yr range</td></tr>')
        for i, r in enumerate(rows):
            bg = '#FFFFFF' if i % 2 == 0 else '#F8FAFB'
            h.append('<tr style="background:%s;">'
                     '<td style="padding:7px 8px 7px 0;border-bottom:1px solid #EEF2F4;">'
                     '<span style="font-weight:600;color:#16303B;">%s</span> '
                     '<span style="color:#9AA7B3;font-size:11px;">%s</span></td>'
                     '<td align="right" style="padding:7px 10px;border-bottom:1px solid #EEF2F4;font-weight:700;color:#16303B;font-variant-numeric:tabular-nums;">%.1f</td>'
                     '<td align="right" style="padding:7px 10px;border-bottom:1px solid #EEF2F4;font-variant-numeric:tabular-nums;">%s</td>'
                     '<td style="padding:7px 0 7px 12px;border-bottom:1px solid #EEF2F4;">%s</td>'
                     '</tr>' % (bg, r['t'], r['nm'], r['cur'], chg_cell(r), bar(r)))
        h.append('</table></td></tr>')
    # footer
    h.append('<tr><td style="padding:22px 30px 26px;border-top:1px solid #E1E7EC;">'
             '<div style="font-size:11.5px;color:#93A0AB;line-height:1.65;">'
             'Percentile is today’s multiple ranked within its own trailing ~252 trading days; the low/high anchors are that window’s min and max. '
             'Position is percentile-based rather than raw min–max, so a near-breakeven spike in the multiple doesn’t distort the read. '
             'The multiple is 1-year-forward (FY+1), so each name’s denominator steps once a year on its results date — a 1-year window contains exactly one such step, which is why it is the right lookback here. '
             'Recent IPOs with under a year of history fall back to what they have. '
             'Full interactive history: <a href="%s" style="color:#16697A;">the dashboard</a>.'
             '</div></td></tr>' % DASH_URL)
    h.append('</table></div>')
    return ''.join(h)

def send_brevo(html, subject):
    key = os.environ.get('BREVO_API_KEY')
    if not key:
        print('!! BREVO_API_KEY not set'); return False
    body = json.dumps({
        'sender': {'name': SENDER_NM, 'email': SENDER},
        'to': [{'email': RECIPIENT}],
        'subject': subject,
        'htmlContent': html,
    }).encode()
    req = urllib.request.Request('https://api.brevo.com/v3/smtp/email', data=body,
        headers={'api-key': key, 'content-type': 'application/json', 'accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            print('Brevo %s: %s' % (resp.status, resp.read().decode()[:300]))
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        print('Brevo HTTPError %s: %s' % (e.code, e.read().decode()[:500])); return False
    except Exception as e:
        print('Brevo error: %r' % e); return False

if __name__ == '__main__':
    d = (json.loads(urllib.request.urlopen(SRC).read()) if SRC.startswith('http')
         else json.load(open(SRC)))
    html = build_html(d)
    open('/tmp/pe_email.html', 'w').write(html)
    print('built /tmp/pe_email.html (%.0f KB) asof %s' % (len(html)/1024, d['asof']))
    if '--send' in sys.argv:
        tag = ''
        if '--subject-tag' in sys.argv:
            tag = '[%s] ' % sys.argv[sys.argv.index('--subject-tag')+1]
        subj = '%sCoverage P/E vs 1-yr history — %s' % (tag, d['asof'])
        ok = send_brevo(html, subj)
        sys.exit(0 if ok else 1)
