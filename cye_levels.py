"""
cye_levels.py — "Close your eyes" valuation-level findings email (HTML, via Brevo).

For every covered name with >1yr history and clean (non-near-breakeven) earnings,
relate the entry 1-yr-forward P/E to the subsequent 12-month TOTAL return (adjusted
closes). A "buy level" is the multiple at/below which forward returns were
consistently strong; a "sell level" the multiple at/above which they were
consistently weak. Not every name has a clean one of either.

The headline metric is the EDGE = mean 12m return when cheap (bottom quartile of the
name's own multiple history) minus mean when rich (top quartile). 2020-26 was a
strong up-market for financials, so raw hit rates run high; the edge isolates the
valuation-specific signal from that beta. Then flag names sitting at a level NOW.

Data: data.json + daily_px.json (total-return prices). Email-safe HTML.

Usage: python cye_levels.py [--send] [--subject-tag SAMPLE]
"""
import json, os, sys, ssl, statistics as st, datetime, urllib.request, urllib.error

def _ctx():
    ca = os.environ.get('SSL_CERT_FILE') or '/root/.ccr/ca-bundle.crt'
    try:
        if os.path.exists(ca): return ssl.create_default_context(cafile=ca)
    except Exception: pass
    return None
CTX = _ctx()
SRC_PE  = os.environ.get('PE_SRC', 'data.json')
SRC_PX  = os.environ.get('PX_SRC', 'daily_px.json')
RECIPIENT = os.environ.get('PE_RECIPIENT', 'vhung@attelascap.com')
SENDER    = os.environ.get('PE_SENDER', 'vhung@attelascap.com')
SENDER_NM = os.environ.get('PE_SENDER_NAME', 'P/E monitor agent')
DASH = 'https://vhung-1.github.io/PEhistory/Relative_PE_Dashboard.html'
H = 252  # 12-month forward window

NM={'CME US':'CME Group','ICE US':'Intercontinental Exch','NDAQ US':'Nasdaq','CBOE US':'Cboe','LSEG LN':'LSEG',
 'DB1 GY':'Deutsche Börse','ENX FP':'Euronext','TW US':'Tradeweb','MKTX US':'MarketAxess','MIAX US':'Miami Intl',
 'MRX US':'Marex','SPGI US':'S&P Global','MCO US':'Moody’s','MSCI US':'MSCI','FDS US':'FactSet','EFX US':'Equifax',
 'TRU US':'TransUnion','EXPN LN':'Experian','FICO US':'Fair Isaac','VRSK US':'Verisk','V US':'Visa','MA US':'Mastercard',
 'CPAY US':'Corpay','WEX US':'WEX','JKHY US':'Jack Henry','GPN US':'Global Payments','FIS US':'FIS','FISV US':'Fiserv',
 'WU US':'Western Union','LAZ US':'Lazard','EVR US':'Evercore','MC US':'Moelis','HLI US':'Houlihan Lokey',
 'PWP US':'Perella Weinberg','PJT US':'PJT Partners','PIPR US':'Piper Sandler','PGHN SW':'Partners Group','EQT SS':'EQT',
 'CVC NA':'CVC','ICG LN':'ICG','ARES US':'Ares','APO US':'Apollo','BX US':'Blackstone','KKR US':'KKR','OWL US':'Blue Owl',
 'CG US':'Carlyle','BAM US':'Brookfield AM','TPG US':'TPG','STEP US':'StepStone','HLNE US':'Hamilton Lane',
 'BLK US':'BlackRock','TROW US':'T. Rowe Price','DWS GY':'DWS','AMUN FP':'Amundi','AB US':'AllianceBernstein',
 'BEN US':'Franklin Res','IVZ US':'Invesco','AMP US':'Ameriprise','SCHW US':'Schwab','LPLA US':'LPL Financial',
 'IBKR US':'Interactive Brokers','RJF US':'Raymond James','SF US':'Stifel','BGN IM':'Banca Generali',
 'FBK IM':'FinecoBank','FTK GY':'Flatexdegiro','SQN SW':'Swissquote','AZA SS':'Avanza','SAVE SS':'Nordnet',
 'IGG LN':'IG Group','AJB LN':'AJ Bell','HOOD US':'Robinhood','COIN US':'Coinbase'}
SECLBL={'Exchanges':'Exchanges','Info Services':'Info Services','Payments & Fintech':'Payments/Fintech',
 'M&A Boutiques':'M&A Boutiques','Alternatives':'Alt Asset Mgrs','Traditional AM':'Traditional AM','Wealth & Brokers':'Wealth/Brokers'}

def pctl(s,q):
    s=sorted(s); n=len(s); f=q*(n-1); lo=int(f)
    return s[lo] if f==lo else s[lo]+(f-lo)*(s[lo+1]-s[lo])

def compute():
    d=json.loads(urllib.request.urlopen(SRC_PE,timeout=60,context=CTX).read()) if SRC_PE.startswith('http') else json.load(open(SRC_PE))
    pxj=json.loads(urllib.request.urlopen(SRC_PX,timeout=60,context=CTX).read()) if SRC_PX.startswith('http') else json.load(open(SRC_PX))
    D,PE,SEC=d['dates'],d['pe'],d['sector_of']; px=pxj['px']; N=len(D)
    out=[]
    for t in PE:
        a=PE[t]; p=px.get(t)
        if not p: continue
        idx=[i for i in range(N) if a[i] is not None and p[i] is not None]
        if len(idx)<300: continue
        peh=[a[i] for i in idx]; med=st.median(peh)
        if med<=0 or pctl(peh,0.95)/med>2.6: continue   # near-breakeven: multiple meaningless
        pairs=[(a[i],p[i+H]/p[i]-1) for i in idx if i+H<N and p[i+H] is not None and p[i]>0]
        if len(pairs)<800: continue                      # ~4yr+ of forward-12m obs
        peA=[q[0] for q in pairs];
        p25=pctl(peA,.25); p75=pctl(peA,.75)
        cheap=[f for pe,f in pairs if pe<=p25]; rich=[f for pe,f in pairs if pe>=p75]
        cur=next((a[i] for i in range(N-1,-1,-1) if a[i] is not None),None)
        curpc=round(100*sum(1 for v in peh if v<=cur)/len(peh))
        def S(xs): return dict(hit=round(100*sum(1 for x in xs if x>0)/len(xs)), mean=round(100*st.mean(xs)))
        c,r=S(cheap),S(rich); edge=c['mean']-r['mean']
        out.append(dict(t=t,nm=NM.get(t,t),sec=SECLBL.get(SEC[t],SEC[t]),cur=round(cur,1),curpc=curpc,
            buy=round(p25,1),sell=round(p75,1),n=len(pairs),chit=c['hit'],cmean=c['mean'],rhit=r['hit'],rmean=r['mean'],edge=edge))
    return d['asof'],out

def bar(pc, col):
    W=120; fill=max(3,round(W*pc/100))
    return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="%d" style="width:%dpx;background:#E3E8EC;border-radius:4px;">'
            '<tr><td height="8" width="%d" style="width:%dpx;background:%s;border-radius:4px 0 0 4px;font-size:0;line-height:0;">&nbsp;</td>'
            '<td height="8" style="font-size:0;line-height:0;">&nbsp;</td></tr></table>')%(W,W,fill,fill,col)

def row(r, kind):
    # kind: 'buy' or 'sell'
    if kind=='buy':
        col='#157A3C'; rule='Buy &le; %.1f&times;'%r['buy']; pay='%d%% positive &middot; %+d%% avg 12m'%(r['chit'],r['cmean'])
    else:
        col='#C0201C'; rule='Trim &ge; %.1f&times;'%r['sell']; pay='%d%% positive &middot; %+d%% avg 12m'%(r['rhit'],r['rmean'])
    return ('<tr>'
      '<td style="padding:9px 8px 9px 0;border-bottom:1px solid #EEF2F4;"><span style="font-weight:700;color:#16303B;">%s</span> '
      '<span style="color:#9AA7B3;font-size:11px;">%s &middot; %s</span></td>'
      '<td align="right" style="padding:9px 10px;border-bottom:1px solid #EEF2F4;font-weight:700;color:#16303B;font-variant-numeric:tabular-nums;">%.1f&times;</td>'
      '<td align="center" style="padding:9px 10px;border-bottom:1px solid #EEF2F4;"><span style="background:%s;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:3px;white-space:nowrap;">%s</span></td>'
      '<td style="padding:9px 0 9px 12px;border-bottom:1px solid #EEF2F4;white-space:nowrap;">%s <span style="color:%s;font-weight:700;font-size:12px;">%d<sup style="font-weight:400;font-size:9px;">%s</sup></span></td>'
      '<td style="padding:9px 0 9px 14px;border-bottom:1px solid #EEF2F4;font-size:11.5px;color:#5A6B78;white-space:nowrap;">%s <span style="color:%s;font-weight:700;">&middot; +%dpp edge</span></td>'
      '</tr>')%(r['nm'],r['t'],r['sec'],r['cur'],col,rule,bar(r['curpc'],col),col,r['curpc'],ordn(r['curpc']),pay,col,r['edge'])

def ordn(k):
    m=k%100; return 'th' if 11<=m<=13 else {1:'st',2:'nd',3:'rd'}.get(k%10,'th')

def build(asof, res):
    for r in res:
        r['buy_ok']=r['chit']>=90 and r['edge']>=20 and r['rmean']<8
        r['sell_ok']=(r['rmean']<=2 or r['rhit']<=45) and r['edge']>=18
    buys=sorted([r for r in res if r['buy_ok'] and r['curpc']<=35], key=lambda r:(r['curpc'],-r['edge']))
    sells=sorted([r for r in res if r['sell_ok'] and r['curpc']>=75], key=lambda r:(-r['curpc'],r['rmean']))
    play=sorted([r for r in res if r['buy_ok'] or r['sell_ok']], key=lambda r:-r['edge'])
    dt=datetime.date.fromisoformat(asof).strftime('%a %d %b %Y')
    S="font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
    h=['<div style="background:#F1F4F6;padding:22px 0;%s">'%S,
       '<table role="presentation" align="center" cellpadding="0" cellspacing="0" border="0" width="680" style="width:680px;max-width:680px;margin:0 auto;background:#fff;border:1px solid #E1E7EC;border-radius:8px;">']
    h.append('<tr><td style="padding:26px 30px 18px;border-bottom:2px solid #16404E;">'
      '<div style="font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#5A7A86;font-weight:600;">Coverage valuation study</div>'
      '<div style="font-size:23px;font-weight:700;color:#16303B;margin-top:4px;">“Close your eyes” buy &amp; sell levels</div>'
      '<div style="font-size:13px;color:#6B7A88;margin-top:6px;">Forward-P/E entry level vs the next 12 months’ total return &middot; %d names with &gt;1yr history &middot; as of <b style="color:#16303B;">%s</b></div>'
      '</td></tr>'%(len(res),dt))
    h.append('<tr><td style="padding:16px 30px 4px;font-size:13px;color:#3D4C5A;line-height:1.6;">'
      'For each name I measured the 12-month <b>total return</b> that followed buying at a given forward multiple. A <b style="color:#157A3C;">buy level</b> is where cheap entries paid off consistently; a <b style="color:#C0201C;">trim level</b> where rich entries didn’t. The <b>edge</b> is the gap between the two — the valuation-specific signal, stripped of the market’s overall rise. '
      'Right now <b style="color:#157A3C;">%d names sit at a buy level</b> and <b style="color:#C0201C;">%d at a trim level</b>.'
      '</td></tr>'%(len(buys),len(sells)))
    def section(title, sub, rows, kind, border):
        h.append('<tr><td style="padding:22px 30px 0;"><div style="font-size:15px;font-weight:700;color:#16404E;border-left:3px solid %s;padding-left:9px;">%s <span style="color:#9AA7B3;font-weight:500;font-size:12px;">%s</span></div></td></tr>'%(border,title,sub))
        h.append('<tr><td style="padding:8px 30px 0;"><table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="width:100%;border-collapse:collapse;font-size:13px;">')
        h.append('<tr style="font-size:10px;letter-spacing:.05em;text-transform:uppercase;color:#93A0AB;">'
          '<td style="padding:4px 8px 4px 0;border-bottom:1px solid #E1E7EC;">Name</td>'
          '<td align="right" style="padding:4px 10px;border-bottom:1px solid #E1E7EC;">Now</td>'
          '<td align="center" style="padding:4px 10px;border-bottom:1px solid #E1E7EC;">Rule</td>'
          '<td style="padding:4px 0 4px 12px;border-bottom:1px solid #E1E7EC;">In own range</td>'
          '<td style="padding:4px 0 4px 14px;border-bottom:1px solid #E1E7EC;">Historical 12m payoff</td></tr>')
        for r in rows: h.append(row(r,kind))
        h.append('</table></td></tr>')
    if buys:
        deep=[r for r in buys if r['curpc']<=15]; line=[r for r in buys if r['curpc']>15]
        if deep: section('At a buy level now — deep value','cheapest ~15% of their own history', deep,'buy','#157A3C')
        if line: section('At a buy level now — at the line','just into the buy zone', line,'buy','#157A3C')
    if sells:
        section('At a trim level now','richest end of their own history, where being expensive historically hurt', sells,'sell','#C0201C')
    # playbook
    h.append('<tr><td style="padding:24px 30px 0;"><div style="font-size:15px;font-weight:700;color:#16404E;border-left:3px solid #16404E;padding-left:9px;">The playbook <span style="color:#9AA7B3;font-weight:500;font-size:12px;">cleanest levels across coverage, by edge</span></div></td></tr>')
    h.append('<tr><td style="padding:8px 30px 0;"><table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="width:100%;border-collapse:collapse;font-size:12.5px;">')
    h.append('<tr style="font-size:10px;letter-spacing:.05em;text-transform:uppercase;color:#93A0AB;">'
      '<td style="padding:4px 8px 4px 0;border-bottom:1px solid #E1E7EC;">Name</td>'
      '<td align="right" style="padding:4px 8px;border-bottom:1px solid #E1E7EC;">Now</td>'
      '<td align="right" style="padding:4px 8px;border-bottom:1px solid #E1E7EC;">Buy&le;</td>'
      '<td align="right" style="padding:4px 8px;border-bottom:1px solid #E1E7EC;">Trim&ge;</td>'
      '<td align="right" style="padding:4px 8px;border-bottom:1px solid #E1E7EC;">Cheap→12m</td>'
      '<td align="right" style="padding:4px 8px;border-bottom:1px solid #E1E7EC;">Rich→12m</td>'
      '<td align="right" style="padding:4px 0 4px 8px;border-bottom:1px solid #E1E7EC;">Edge</td></tr>')
    for r in play[:22]:
        near = '#157A3C' if (r['buy_ok'] and r['curpc']<=35) else ('#C0201C' if (r['sell_ok'] and r['curpc']>=75) else '#16303B')
        wt = '700' if near!='#16303B' else '600'
        h.append('<tr>'
          '<td style="padding:6px 8px 6px 0;border-bottom:1px solid #EEF2F4;"><span style="font-weight:%s;color:%s;">%s</span> <span style="color:#9AA7B3;font-size:10.5px;">%s</span></td>'
          '<td align="right" style="padding:6px 8px;border-bottom:1px solid #EEF2F4;font-variant-numeric:tabular-nums;font-weight:600;">%.1f</td>'
          '<td align="right" style="padding:6px 8px;border-bottom:1px solid #EEF2F4;color:#157A3C;font-variant-numeric:tabular-nums;">%s</td>'
          '<td align="right" style="padding:6px 8px;border-bottom:1px solid #EEF2F4;color:#C0201C;font-variant-numeric:tabular-nums;">%s</td>'
          '<td align="right" style="padding:6px 8px;border-bottom:1px solid #EEF2F4;color:#157A3C;font-variant-numeric:tabular-nums;">%d%%/%+d%%</td>'
          '<td align="right" style="padding:6px 8px;border-bottom:1px solid #EEF2F4;color:#C0201C;font-variant-numeric:tabular-nums;">%d%%/%+d%%</td>'
          '<td align="right" style="padding:6px 0 6px 8px;border-bottom:1px solid #EEF2F4;font-weight:700;font-variant-numeric:tabular-nums;">+%d</td>'
          '</tr>'%(wt,near,r['t'],r['sec'],r['cur'],
                  ('%.1f'%r['buy']) if r['buy_ok'] else '—', ('%.1f'%r['sell']) if r['sell_ok'] else '—',
                  r['chit'],r['cmean'],r['rhit'],r['rmean'],r['edge']))
    h.append('</table></td></tr>')
    # method + caveats (plain concatenation — the text is full of literal % signs)
    h.append('<tr><td style="padding:22px 30px 26px;border-top:1px solid #E1E7EC;">'
      '<div style="font-size:11.5px;color:#93A0AB;line-height:1.65;">'
      '<b style="color:#6B7A88;">Method.</b> Daily 1-yr-forward (FY+1) P/E from Bloomberg; 12-month forward return from S&amp;P adjusted (total-return) closes. Cheap = bottom quartile of each name’s own multiple history, rich = top quartile; hit = share of 12m windows that were positive; edge = cheap-mean minus rich-mean. Buy/trim levels are that name’s 25th / 75th-percentile multiple. Near-breakeven names (multiple &gt; 2.6&times; its median) are excluded — their P/E is meaningless. Only names with 4yr+ of forward observations are ranked.<br><br>'
      '<b style="color:#C0392B;">Read with care.</b> The window is <b>2020&ndash;2026, a single regime and a strong up-market for financials</b> — which is why hit rates run so high; the <b>edge</b> is the more honest, valuation-specific number. 12-month windows overlap, so ~5&frac12; years holds only ~5 independent observations — treat “100%” as “reliable in this window,” not a guarantee. Figures are in-sample, gross, and absolute total return (not alpha vs the group). The FY+1 multiple steps once a year on each name’s results date; the level shown is the observed multiple you would act on. This is a screen, not advice — size and time it with your own judgement. Full history: <a href="'+DASH+'" style="color:#16697A;">the dashboard</a>.'
      '</div></td></tr>')
    h.append('</table></div>')
    return ''.join(h), buys, sells

def send(html, subject):
    key=os.environ.get('BREVO_API_KEY')
    if not key: print('!! BREVO_API_KEY not set'); return False
    body=json.dumps({'sender':{'name':SENDER_NM,'email':SENDER},'to':[{'email':RECIPIENT}],'subject':subject,'htmlContent':html}).encode()
    req=urllib.request.Request('https://api.brevo.com/v3/smtp/email',data=body,headers={'api-key':key,'content-type':'application/json','accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=60,context=CTX) as resp:
            print('Brevo %s: %s'%(resp.status,resp.read().decode()[:200])); return 200<=resp.status<300
    except urllib.error.HTTPError as e:
        print('Brevo HTTPError %s: %s'%(e.code,e.read().decode()[:400])); return False

if __name__=='__main__':
    asof,res=compute()
    html,buys,sells=build(asof,res)
    open('/tmp/cye_email.html','w').write(html)
    print('built /tmp/cye_email.html (%.0f KB) | %d names | %d buys, %d sells | asof %s'%(len(html)/1024,len(res),len(buys),len(sells),asof))
    if '--send' in sys.argv:
        tag='[%s] '%sys.argv[sys.argv.index('--subject-tag')+1] if '--subject-tag' in sys.argv else ''
        sys.exit(0 if send(html,'%s“Close your eyes” buy/sell levels — %s'%(tag,asof)) else 1)
