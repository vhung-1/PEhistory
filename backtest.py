import json, math
from statistics import mean, pstdev
import itertools

# ---------- load data ----------
pe_d = json.load(open('data.json'))
PE_dates = pe_d['dates']; PE_raw = pe_d['pe']; SECOF = pe_d['sector_of']
panel = json.load(open('prices_all.json'))
MONTHS = panel['MONTHS']                       # price months 2022-06..2026-06 (49)
PX = panel['PX']
PXNAMES = set(PX)

# ---------- resample daily P/E -> month-end (last valid obs per calendar month) ----------
def ym(dstr): return dstr[:7]
PE_M = {}            # ticker -> {ym: pe}
allmonths = sorted({ym(d) for d in PE_dates})    # 2021-06 .. 2026-06
for t,arr in PE_raw.items():
    last={}
    for d,v in zip(PE_dates,arr):
        if v is not None and v==v and v>0:
            last[ym(d)] = v        # later dates overwrite -> month-end last value
    PE_M[t]=last
PEMONTHS = allmonths               # 61 months incl pre-price history for baselines
print('P/E months:', len(PEMONTHS), PEMONTHS[0],'->',PEMONTHS[-1])

# ---------- curated tradeable clusters (same as dashboard) ----------
CLUSTERS=[['CME US','ICE US','NDAQ US','CBOE US'],['LSEG LN','DB1 GY','ENX FP'],['TW US','MKTX US'],
['SPGI US','MCO US'],['EFX US','TRU US','EXPN LN'],['MSCI US','SPGI US','FDS US'],['V US','MA US'],
['FIS US','FISV US','GPN US'],['PYPL US','XYZ US','ADYEN NA'],['TOST US','FOUR US','XYZ US'],
['AFRM US','KLAR US','SOFI US'],['SOFI US','CHYM US'],['CPAY US','WEX US'],['WU US','WISE LN','RELY LN'],
['LAZ US','EVR US','MC US','HLI US','PWP US','PJT US','PIPR US'],
['BX US','KKR US','APO US','ARES US','CG US','BAM US','TPG US','OWL US'],
['EQT SS','CVC NA','ICG LN','PGHN SW'],['STEP US','HLNE US'],
['BLK US','TROW US','BEN US','IVZ US','AB US'],['DWS GY','AMUN FP'],
['SCHW US','LPLA US','RJF US','SF US'],['SCHW US','IBKR US','HOOD US','ETOR US'],
['SAVE SS','IGG LN','AJB LN'],
['HOOD US','COIN US'],['COIN US','CRCL US'],['FTK GY','SQ SW','FBK IM'],['FBK IM','BGN IM']]
clset=[set(c) for c in CLUSTERS]
def comparable(a,b): return any(a in s and b in s for s in clset)

# enumerate unique tradeable pairs where BOTH have prices & P/E
names_with_data=[t for t in PE_M if t in PXNAMES and len(PE_M[t])>=18]
pairs=[]
seen=set()
for s in clset:
    members=[x for x in s if x in PXNAMES and x in PE_M]
    for a,b in itertools.combinations(sorted(members),2):
        if (a,b) in seen: continue
        seen.add((a,b)); pairs.append((a,b))
print('tradeable pairs testable:', len(pairs))

# ---------- helpers ----------
MIDX={m:i for i,m in enumerate(MONTHS)}
def price_ret(t, m, h):
    i=MIDX.get(m); 
    if i is None or i+h>=len(MONTHS): return None
    a=PX.get(t); 
    if not a: return None
    p0=a[i]; p1=a[i+h]
    if p0 is None or p1 is None or p0<=0: return None
    return p1/p0-1.0

def expanding_z_single(t, m):
    # z of P/E at month m vs all monthly P/E up to & incl m (min 18)
    hist=[PE_M[t][mm] for mm in PEMONTHS if mm<=m and mm in PE_M[t]]
    if len(hist)<18 or m not in PE_M[t]: return None
    mu=mean(hist); sd=pstdev(hist)
    if sd<=0: return None
    return (PE_M[t][m]-mu)/sd

def expanding_z_pair(a,b,m):
    lr=[math.log(PE_M[a][mm]/PE_M[b][mm]) for mm in PEMONTHS if mm<=m and mm in PE_M[a] and mm in PE_M[b]]
    if len(lr)<18: return None
    if m not in PE_M[a] or m not in PE_M[b]: return None
    cur=math.log(PE_M[a][m]/PE_M[b][m]); mu=mean(lr); sd=pstdev(lr)
    if sd<=0: return None
    return (cur-mu)/sd

def spearman(xs, ys):
    n=len(xs)
    if n<4: return None
    def rank(v):
        idx=sorted(range(len(v)), key=lambda i:v[i]); r=[0]*len(v); 
        i=0
        while i<len(v):
            j=i
            while j+1<len(v) and v[idx[j+1]]==v[idx[i]]: j+=1
            avg=(i+j)/2.0+1
            for k in range(i,j+1): r[idx[k]]=avg
            i=j+1
        return r
    rx,ry=rank(xs),rank(ys)
    mx,my=mean(rx),mean(ry)
    num=sum((a-mx)*(b-my) for a,b in zip(rx,ry))
    den=math.sqrt(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))
    return num/den if den>0 else None

HORIZONS=[1,3,6,12]
json.dump({'ok':True}, open('bt_ready.json','w'))
print('setup OK. names_with_data:', len(names_with_data))

print('\n'+'='*70)
print('PAIR SIGNAL BACKTEST  (signal = -z of ln(PE_A/PE_B) vs own expanding history)')
print('Positive signal = A cheap vs B = go long A / short B. Forward return = r_A - r_B (local ccy, FX-hedged).')
print('='*70)

# Precompute per (pair, month): z and fwd LS returns
pairobs={h:[] for h in HORIZONS}   # list of (z, fwdLS, pair, month)
permonth={h:{} for h in HORIZONS}  # month -> list of (-z, fwdLS)
for (a,b) in pairs:
    for m in MONTHS:
        z=expanding_z_pair(a,b,m)
        if z is None: continue
        for h in HORIZONS:
            ra=price_ret(a,m,h); rb=price_ret(b,m,h)
            if ra is None or rb is None: continue
            ls=ra-rb
            pairobs[h].append((z,ls,(a,b),m))
            permonth[h].setdefault(m,[]).append((-z,ls))

# 1) per-month cross-sectional IC
print('\n[1] Pair IC (cross-sectional Spearman of signal vs forward LS return), averaged over months:')
print(f'{"horizon":>8} | {"meanIC":>7} | {"t-stat":>6} | {"%mths>0":>7} | {"nmonths":>7} | {"avg pairs/mth":>12}')
for h in HORIZONS:
    ics=[]; sizes=[]
    for m,lst in sorted(permonth[h].items()):
        if len(lst)<5: continue
        xs=[s for s,_ in lst]; ys=[r for _,r in lst]
        ic=spearman(xs,ys)
        if ic is not None: ics.append(ic); sizes.append(len(lst))
    if ics:
        mIC=mean(ics); sd=pstdev(ics) if len(ics)>1 else 0
        t=mIC/(sd/math.sqrt(len(ics))) if sd>0 else float('nan')
        pos=100*sum(1 for x in ics if x>0)/len(ics)
        print(f'{h:>6}m  | {mIC:>7.3f} | {t:>6.2f} | {pos:>6.0f}% | {len(ics):>7} | {mean(sizes):>12.1f}')

# 2) buy-the-discount conditional
print('\n[2] "Buy the discount" conditional forward LS returns (pooled over all pairs & months):')
print('    z<-1  => A at historic DISCOUNT vs B -> trade = long A/short B ; expect LS>0')
print('    z>+1  => A at historic PREMIUM  vs B -> expect LS<0 (i.e. fade)')
print(f'{"horizon":>8} | {"disc z<-1 meanLS":>16} {"hit%":>5} {"N":>5} | {"prem z>+1 meanLS":>16} {"hit%":>5} {"N":>5} | {"mid|z|<1 meanLS":>15}')
for h in HORIZONS:
    disc=[ls for z,ls,_,_ in pairobs[h] if z<-1]
    prem=[ls for z,ls,_,_ in pairobs[h] if z>1]
    mid =[ls for z,ls,_,_ in pairobs[h] if -1<=z<=1]
    def stat(v, sign=1): 
        if not v: return (float('nan'),float('nan'),0)
        return (mean(v)*100, 100*sum(1 for x in v if x*sign>0)/len(v), len(v))
    dm,dh,dn=stat(disc,+1); pm,ph,pn=stat(prem,-1); mm,_,_=stat(mid)
    # for premium, hit% = fraction where LS<0 (fade works)
    print(f'{h:>6}m  | {dm:>14.2f}% {dh:>4.0f}% {dn:>5} | {pm:>14.2f}% {ph:>4.0f}% {pn:>5} | {mm:>13.2f}%')
print('    (discount hit% = P(long-A/short-B return>0); premium hit% = P(return<0, i.e. A underperforms))')

# 3) z-decile monotonicity at 6m
print('\n[3] Forward 6m LS return by z-decile (pooled). Monotonic? lower z (A cheap) should -> higher LS:')
h=6; obs=sorted(pairobs[h], key=lambda x:x[0])
n=len(obs); 
print(f'{"decile":>6} | {"z range":>16} | {"mean fwd6m LS":>13} | {"N":>5}')
for d in range(10):
    lo=d*n//10; hi=(d+1)*n//10
    chunk=obs[lo:hi]
    zs=[c[0] for c in chunk]; ls=[c[1] for c in chunk]
    print(f'{d+1:>6} | {min(zs):>7.2f}..{max(zs):>6.2f} | {mean(ls)*100:>11.2f}% | {len(chunk):>5}')

# 4) tradeable z-weighted dollar-neutral 1-month pair portfolio
print('\n[4] Tradeable pair portfolio: each month, weight每 pair by -z (clip +-3), dollar-neutral, hold 1m:')
def clip(x,a,b): return max(a,min(b,x))
preturns=[]
for m in MONTHS[:-1]:
    lst=permonth[1].get(m,[])
    if len(lst)<5: continue
    sig=[clip(s,-3,3) for s,_ in lst]; rets=[r for _,r in lst]
    mu=mean(sig); w=[s-mu for s in sig]
    g=sum(abs(x) for x in w)
    if g<=0: continue
    w=[x/g for x in w]
    preturns.append(sum(wi*ri for wi,ri in zip(w,rets)))
if preturns:
    mu=mean(preturns); sd=pstdev(preturns)
    sharpe=mu/sd*math.sqrt(12) if sd>0 else float('nan')
    print(f'   monthly mean {mu*100:.3f}%  vol {sd*100:.3f}%  ann.Sharpe {sharpe:.2f}  hit {100*sum(1 for x in preturns if x>0)/len(preturns):.0f}%  nmonths {len(preturns)}')

# 5) per-pair predictive power ranking (avg IC over 3/6/12m, need >=12 obs/horizon)
print('\n[5] Per-pair predictive power (Spearman -z vs fwd LS, averaged over 3/6/12m; >=12 obs each). NOISY:')
perpair=[]
for (a,b) in pairs:
    ics=[]; nmin=99
    for h in [3,6,12]:
        sub=[(-z,ls) for z,ls,p,_ in pairobs[h] if p==(a,b)]
        if len(sub)<12: ics=None; break
        ic=spearman([s for s,_ in sub],[r for _,r in sub])
        if ic is None: ics=None; break
        ics.append(ic); nmin=min(nmin,len(sub))
    if ics: perpair.append((mean(ics), a, b, nmin))
perpair.sort(reverse=True)
print(' TOP 12 (signal most predictive of mean-reversion):')
for ic,a,b,n in perpair[:12]:
    print(f'   {a:>8} / {b:<8}  avgIC {ic:+.2f}  (n>={n})')
print(' BOTTOM 6 (signal works in reverse = momentum / divergent):')
for ic,a,b,n in perpair[-6:]:
    print(f'   {a:>8} / {b:<8}  avgIC {ic:+.2f}  (n>={n})')
print(f' pairs with enough data ranked: {len(perpair)}; share with positive avgIC: {100*sum(1 for x in perpair if x[0]>0)/len(perpair):.0f}%')
json.dump({'perpair':perpair}, open('perpair.json','w'))

print('\n'+'='*70)
print('SINGLE-NAME SIGNAL BACKTEST  (signal = -z of own forward P/E vs own expanding history)')
print('Positive signal = cheap vs own history. Returns measured SECTOR-RELATIVE (vs sub-sector peers).')
print('='*70)

SECTORS=sorted(set(SECOF[t] for t in PXNAMES if t in SECOF))
# per (name,month): z ; per month per sector: returns to demean
snobs={h:[] for h in HORIZONS}     # (z, sector_rel_ret, name, month)
permonth_sn={h:{} for h in HORIZONS}
for h in HORIZONS:
    for m in MONTHS:
        # gather names with valid z & fwd ret this month
        rows=[]
        for t in PXNAMES:
            if t not in SECOF: continue
            z=expanding_z_single(t,m); r=price_ret(t,m,h)
            if z is None or r is None: continue
            rows.append((t,SECOF[t],z,r))
        if len(rows)<6: continue
        # sector-demean returns and signal
        secret={}; 
        for s in set(x[1] for x in rows):
            rr=[x[3] for x in rows if x[1]==s]; secret[s]=mean(rr)
        lst=[]
        for t,s,z,r in rows:
            rrel=r-secret[s]
            snobs[h].append((z,rrel,t,m)); lst.append((-z,rrel))
        permonth_sn[h][m]=lst

print('\n[1] Single-name sector-neutral IC (Spearman of signal vs sector-relative fwd return):')
print(f'{"horizon":>8} | {"meanIC":>7} | {"t-stat":>6} | {"%mths>0":>7} | {"nmonths":>7}')
for h in HORIZONS:
    ics=[]
    for m,lst in sorted(permonth_sn[h].items()):
        if len(lst)<6: continue
        ic=spearman([s for s,_ in lst],[r for _,r in lst])
        if ic is not None: ics.append(ic)
    mIC=mean(ics); sd=pstdev(ics) if len(ics)>1 else 0
    t=mIC/(sd/math.sqrt(len(ics))) if sd>0 else float('nan')
    pos=100*sum(1 for x in ics if x>0)/len(ics)
    print(f'{h:>6}m  | {mIC:>7.3f} | {t:>6.2f} | {pos:>6.0f}% | {len(ics):>7}')

print('\n[2] Single-name conditional (pooled): cheap vs own history (z<-1) vs rich (z>+1):')
print(f'{"horizon":>8} | {"cheap z<-1 meanRel":>18} {"hit%":>5} {"N":>5} | {"rich z>+1 meanRel":>17} {"hit%":>5} {"N":>5}')
for h in HORIZONS:
    cheap=[r for z,r,_,_ in snobs[h] if z<-1]
    rich =[r for z,r,_,_ in snobs[h] if z>1]
    def st(v,sign): return (mean(v)*100,100*sum(1 for x in v if x*sign>0)/len(v),len(v)) if v else (float('nan'),)*3
    cm,ch,cn=st(cheap,1); rm,rh,rn=st(rich,-1)
    print(f'{h:>6}m  | {cm:>16.2f}% {ch:>4.0f}% {cn:>5} | {rm:>15.2f}% {rh:>4.0f}% {rn:>5}')

print('\n[3] Single-name quintile: forward 6m sector-relative return by signal quintile (pooled):')
h=6; obs=sorted(snobs[h], key=lambda x:-x[0])  # sort by z desc; we want by signal=-z, so cheap (low z) last
obs=sorted(snobs[h], key=lambda x:x[0])  # ascending z: Q1=cheapest
n=len(obs)
for q in range(5):
    lo=q*n//5; hi=(q+1)*n//5; ch=obs[lo:hi]
    lab=['Q1 cheapest','Q2','Q3','Q4','Q5 richest'][q]
    print(f'   {lab:>12}: zmid {ch[len(ch)//2][0]:+.2f}  mean fwd6m sector-rel {mean([c[1] for c in ch])*100:+.2f}%  (N={len(ch)})')

print('\n[4] Single-name factor portfolio (monthly, sector-neutral signal, dollar-neutral, 1m hold):')
def clip(x,a,b): return max(a,min(b,x))
prn=[]
for m in MONTHS[:-1]:
    lst=permonth_sn[1].get(m,[])
    if len(lst)<6: continue
    sig=[clip(s,-3,3) for s,_ in lst]; r=[x for _,x in lst]
    mu=mean(sig); w=[s-mu for s in sig]; g=sum(abs(x) for x in w)
    if g<=0: continue
    w=[x/g for x in w]; prn.append(sum(wi*ri for wi,ri in zip(w,r)))
mu=mean(prn); sd=pstdev(prn); print(f'   monthly mean {mu*100:.3f}%  vol {sd*100:.3f}%  ann.Sharpe {mu/sd*math.sqrt(12):.2f}  hit {100*sum(1 for x in prn if x>0)/len(prn):.0f}%  nmonths {len(prn)}')

print('\nNOTE: forward returns overlap for h>1 (monthly sampling) -> t-stats overstate significance; treat as indicative.')
print('Usable entry window ~2023-01..2026-05 (need >=18m P/E baseline before each entry + forward returns).')
