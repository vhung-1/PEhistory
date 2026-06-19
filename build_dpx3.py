# build_dpx3.py - build daily_px.json (daily price panel) via the scale-factor splice.
# See CLAUDE.md §7c. PER REFRESH update: SP_PULLS_DIR (env; folder holding the S&P
# get_prices_from_identifiers_*.json pulls), and the RECENT/EARLY filename constants
# + the date boundaries in their branches. Base = previously-stored full-history pulls
# (they define the reference adjustment basis that early/recent are scaled onto).
import os
import json,glob,os,statistics
d=json.load(open('data.json')); DATES=d['dates']; UNIV=set(d['pe'].keys())
US={t for t in UNIV if t.endswith(' US')}
FMAP={'SWX:PGHN':'PGHN SW','OM:EQT':'EQT SS','ENXTAM:CVC':'CVC NA','XTRA:DWS':'DWS GY','XTRA:DB1':'DB1 GY','XTRA:FTK':'FTK GY','LSE:LSEG':'LSEG LN','LSE:EXPN':'EXPN LN','LSE:WISE':'WISE LN','LSE:ICG':'ICG LN','ENXTPA:ENX':'ENX FP','ENXTPA:AMUN':'AMUN FP','ENXTAM:ADYEN':'ADYEN NA','BIT:BGN':'BGN IM','BIT:FBK':'FBK IM'}
def bbg_of(es):
    if es in FMAP: return FMAP[es]
    c=es.split(':')[-1]+' US'; return c if c in US else None
def load_prices(fp):
    raw=json.load(open(fp)); txt=None
    for el in raw:
        if isinstance(el,dict) and isinstance(el.get('text'),str): txt=el['text']; break
    res=json.loads(txt).get('results',{}); out={}
    for k,blk in res.items():
        blk=blk or {}; bbg=bbg_of(blk.get('ticker',k))
        if not bbg: continue
        pm={}
        for p in blk.get('data',{}).get('prices',[]) or []:
            v=p.get('close',{}).get('value')
            if v not in (None,'','N/A'):
                try: pm[p['date']]=float(v)
                except: pass
        if pm: out[bbg]=pm
    return out
RECENT='toolu_014xCrLsUFYxJeYsGmrQ8GQ8'; EARLY='toolu_01GygGQqwR8zQmYk7UVVAfda'
MONTHLY=['toolu_01JpJPSppGhQeymS4PXi2s28','toolu_01YATGhGdZ3PyFsjuiG3uWxP']
allf=sorted(glob.glob(os.path.join(os.environ.get('SP_PULLS_DIR','tool_results'),'S_P_Global_get_prices_from_identifiers_*.json')))
basef=[f for f in allf if not any(s in f for s in [RECENT,EARLY]+MONTHLY)]
base={}
for fp in basef:
    for bbg,pm in load_prices(fp).items():
        if bbg not in base or len(pm)>len(base[bbg]): base[bbg]=pm
early=load_prices([f for f in allf if EARLY in f][0])
recent=load_prices([f for f in allf if RECENT in f][0])
print("base names:",len(base),"| early names:",len(early),"| recent names:",len(recent))
missing=sorted(UNIV-set(base)); print("UNIV missing from base:", missing if missing else "none")

def F(seg,bpm):
    rr=[bpm[dd]/seg[dd] for dd in seg if dd in bpm and seg.get(dd) and bpm.get(dd)]
    if len(rr)<5: return None,None,len(rr)
    f=statistics.median(rr); return f,max(abs(r/f-1) for r in rr),len(rr)

flags=[]; full={}
for bbg in UNIV:
    pm=dict(base.get(bbg,{}))
    if bbg in recent:
        f,dev,n=F(recent[bbg],base.get(bbg,{}))
        if f is None: f=1.0
        if dev and dev>0.01: flags.append((bbg,'recent',round(dev*100,2),n))
        for dd in ('2026-06-16','2026-06-17','2026-06-18'):
            if dd in recent[bbg]: pm[dd]=recent[bbg][dd]*f
    if bbg in early:
        f,dev,n=F(early[bbg],base.get(bbg,{}))
        if f is None: f=1.0
        if dev and dev>0.01: flags.append((bbg,'early',round(dev*100,2),n))
        for dd,v in early[bbg].items():
            if dd<'2021-06-16': pm[dd]=v*f
    full[bbg]=pm
print("scale-factor anomalies >1% (possible split/data issue in overlap):", flags if flags else "none")

DPX={}
for t in sorted(UNIV):
    pm=full.get(t,{}); out=[]; last=None
    for dt in DATES:
        if dt in pm: last=round(pm[dt],2)
        out.append(last)
    DPX[t]=out
json.dump({'asof':d['asof'],'note':'S&P Global daily ADJUSTED close (total return), local currency, single back-adjustment basis, aligned to trading days, holiday-ffilled','px':DPX},
          open('daily_px.json','w'),separators=(',',':'))
print("daily_px.json %.2f MB | tickers"%(os.path.getsize('daily_px.json')/1e6),len(DPX),"| panel len",len(DATES))
