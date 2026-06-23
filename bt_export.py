import json, math
from statistics import mean, pstdev
# reuse the validated setup (everything before the first results banner)
src=open('backtest.py').read().split("print('\\n'+'='*70)")[0]
exec(src)

def spearman_safe(xs,ys):
    r=spearman(xs,ys); return r

# ---- recompute structured pair results ----
pairobs={h:[] for h in HORIZONS}; permonth={h:{} for h in HORIZONS}
for (a,b) in pairs:
    for m in MONTHS:
        z=expanding_z_pair(a,b,m)
        if z is None: continue
        for h in HORIZONS:
            ra=price_ret(a,m,h); rb=price_ret(b,m,h)
            if ra is None or rb is None: continue
            ls=ra-rb; pairobs[h].append((z,ls,(a,b),m)); permonth[h].setdefault(m,[]).append((-z,ls))

pair_ic={}; 
for h in HORIZONS:
    ics=[]; 
    for m,lst in sorted(permonth[h].items()):
        if len(lst)<5: continue
        ic=spearman([s for s,_ in lst],[r for _,r in lst])
        if ic is not None: ics.append(ic)
    mIC=mean(ics); sd=pstdev(ics) if len(ics)>1 else 0
    pair_ic[str(h)]={'ic':round(mIC,3),'t':round(mIC/(sd/math.sqrt(len(ics))),2) if sd>0 else None,
                     'pos':round(100*sum(1 for x in ics if x>0)/len(ics)),'nm':len(ics)}

pair_cond={}
for h in HORIZONS:
    disc=[ls for z,ls,_,_ in pairobs[h] if z<-1]; prem=[ls for z,ls,_,_ in pairobs[h] if z>1]; mid=[ls for z,ls,_,_ in pairobs[h] if -1<=z<=1]
    pair_cond[str(h)]={'dm':round(mean(disc)*100,2),'dh':round(100*sum(1 for x in disc if x>0)/len(disc)),'dn':len(disc),
                       'pm':round(mean(prem)*100,2),'ph':round(100*sum(1 for x in prem if x<0)/len(prem)),'pn':len(prem),
                       'mm':round(mean(mid)*100,2)}

pair_dec={}
for h in HORIZONS:
    obs=sorted(pairobs[h], key=lambda x:x[0]); n=len(obs); arr=[]
    for d in range(10):
        lo=d*n//10; hi=(d+1)*n//10; ch=obs[lo:hi]; zs=[c[0] for c in ch]; ls=[c[1] for c in ch]
        arr.append({'lo':round(min(zs),2),'hi':round(max(zs),2),'mean':round(mean(ls)*100,2),'n':len(ch)})
    pair_dec[str(h)]=arr

# pair portfolio (1m, dollar-neutral, z-weighted) with equity curve
def clip(x,a,b): return max(a,min(b,x))
mons=[]; rets=[]
for i,m in enumerate(MONTHS[:-1]):
    lst=permonth[1].get(m,[])
    if len(lst)<5: continue
    sig=[clip(s,-3,3) for s,_ in lst]; rr=[r for _,r in lst]; mu=mean(sig); w=[s-mu for s in sig]; g=sum(abs(x) for x in w)
    if g<=0: continue
    w=[x/g for x in w]; rets.append(sum(wi*ri for wi,ri in zip(w,rr))); mons.append(MONTHS[i+1])
eq=[]; c=1.0
for r in rets: c*=(1+r); eq.append(round(c,4))
muP=mean(rets); sdP=pstdev(rets)
pair_port={'sharpe':round(muP/sdP*math.sqrt(12),2),'mean':round(muP*100,3),'vol':round(sdP*100,3),
           'hit':round(100*sum(1 for x in rets if x>0)/len(rets)),'n':len(rets),'eq':eq,'mon':mons}

# ---- single-name structured ----
snobs={h:[] for h in HORIZONS}; permonth_sn={h:{} for h in HORIZONS}
for h in HORIZONS:
    for m in MONTHS:
        rows=[]
        for t in PXNAMES:
            if t not in SECOF: continue
            z=expanding_z_single(t,m); r=price_ret(t,m,h)
            if z is None or r is None: continue
            rows.append((t,SECOF[t],z,r))
        if len(rows)<6: continue
        secret={s:mean([x[3] for x in rows if x[1]==s]) for s in set(x[1] for x in rows)}
        for t,s,z,r in rows:
            rrel=r-secret[s]; snobs[h].append((z,rrel,t,m)); permonth_sn[h].setdefault(m,[]).append((-z,rrel))
sn_ic={}
for h in HORIZONS:
    ics=[]
    for m,lst in sorted(permonth_sn[h].items()):
        if len(lst)<6: continue
        ic=spearman([s for s,_ in lst],[r for _,r in lst])
        if ic is not None: ics.append(ic)
    mIC=mean(ics); sd=pstdev(ics) if len(ics)>1 else 0
    sn_ic[str(h)]={'ic':round(mIC,3),'t':round(mIC/(sd/math.sqrt(len(ics))),2) if sd>0 else None,'pos':round(100*sum(1 for x in ics if x>0)/len(ics)),'nm':len(ics)}
sn_cond={}
for h in HORIZONS:
    cheap=[r for z,r,_,_ in snobs[h] if z<-1]; rich=[r for z,r,_,_ in snobs[h] if z>1]
    sn_cond[str(h)]={'cm':round(mean(cheap)*100,2),'ch':round(100*sum(1 for x in cheap if x>0)/len(cheap)),'cn':len(cheap),
                     'rm':round(mean(rich)*100,2),'rh':round(100*sum(1 for x in rich if x<0)/len(rich)),'rn':len(rich)}

# ---- per-pair ranking with current z and discount-trade fwd6m ----
def latest_z(a,b):
    for m in reversed(MONTHS):
        z=expanding_z_pair(a,b,m)
        if z is not None: return z
    return None
perpair=[]
for (a,b) in pairs:
    ics=[]; nmin=10**9
    for h in [3,6,12]:
        sub=[(-z,ls) for z,ls,p,_ in pairobs[h] if p==(a,b)]
        if len(sub)<12: ics=None; break
        ic=spearman([s for s,_ in sub],[r for _,r in sub])
        if ic is None: ics=None; break
        ics.append(ic); nmin=min(nmin,len(sub))
    if not ics: continue
    d6=[ls for z,ls,p,_ in pairobs[6] if p==(a,b) and z<-1]
    perpair.append({'a':a,'b':b,'ic':round(mean(ics),2),'n':nmin,'cz':round(latest_z(a,b),2),
                    'd6':round(mean(d6)*100,1) if len(d6)>=3 else None})
perpair.sort(key=lambda x:-x['ic'])
breadth=round(100*sum(1 for x in perpair if x['ic']>0)/len(perpair))

# ---- trend filter (trailing-12m ln-spread trend rho) ----
RHO=0.5
def _spread(a,b): return [(mm,math.log(PE_M[a][mm]/PE_M[b][mm])) for mm in PEMONTHS if mm in PE_M[a] and mm in PE_M[b]]
def _trend(ser,m,win=12,minn=6):
    s=[v for (mm,v) in ser if mm<=m][-win:];n=len(s)
    if n<minn: return None
    mx=(n-1)/2.0;my=sum(s)/n;num=sum((i-mx)*(s[i]-my) for i in range(n));dx=sum((i-mx)**2 for i in range(n));dy=sum((y-my)**2 for y in s)
    if dx<=0 or dy<=0: return 0.0
    return num/math.sqrt(dx*dy)
robs={h:[] for h in HORIZONS}
for (a,b) in pairs:
    ser=_spread(a,b)
    for m in MONTHS:
        z=expanding_z_pair(a,b,m)
        if z is None: continue
        rho=_trend(ser,m)
        if rho is None: continue
        for h in HORIZONS:
            ra=price_ret(a,m,h);rb=price_ret(b,m,h)
            if ra is None or rb is None: continue
            robs[h].append((z,ra-rb,rho))
def _st(v): return {'m':round(mean([x[1] for x in v])*100,2),'h':round(100*sum(1 for x in v if x[1]>0)/len(v)),'n':len(v)} if v else {'m':None,'h':None,'n':0}
trap={'rho':RHO,'disc':{}}
for h in HORIZONS:
    disc=[(z,ls,rho) for (z,ls,rho) in robs[h] if z<-1]
    tc=[x for x in disc if x[2]<=-RHO]; rb=[x for x in disc if x[2]>-RHO]
    trap['disc'][str(h)]={'all':_st(disc),'tc':_st(tc),'rb':_st(rb)}

# ---- net-of-cost 1m portfolio ----
mw={};mr={}
for (a,b) in pairs:
    for mi,m in enumerate(MONTHS):
        z=expanding_z_pair(a,b,m)
        if z is None: continue
        ra=price_ret(a,m,1);rb=price_ret(b,m,1)
        if ra is None or rb is None: continue
        mw.setdefault(mi,{})[(a,b)]=max(-3,min(3,-z));mr.setdefault(mi,{})[(a,b)]=ra-rb
seq=[]
for mi in sorted(mw):
    sig=mw[mi]
    if len(sig)<5: continue
    mu=sum(sig.values())/len(sig);w={k:v-mu for k,v in sig.items()};g=sum(abs(x) for x in w.values())
    if g<=0: continue
    w={k:x/g for k,x in w.items()};seq.append((mi,w,sum(w[k]*mr[mi][k] for k in w)))
turn=[];shortg=[]
for i in range(len(seq)):
    w=seq[i][1];pw=seq[i-1][1] if i>0 else {}
    turn.append(sum(abs(w.get(k,0)-pw.get(k,0)) for k in set(w)|set(pw)));shortg.append(sum(-x for x in w.values() if x<0))
gross=[g for _,_,g in seq]
def _shp(xs): m=mean(xs);s=pstdev(xs);return {'sharpe':round(m/s*math.sqrt(12),2) if s>0 else None,'mean':round(m*100,3)}
TX,BOR=10,50
net=[gross[i]-TX/1e4*turn[i]-BOR/1e4/12*shortg[i] for i in range(len(seq))]
eqg=[];c=1.0
for r in gross: c*=(1+r);eqg.append(round(c,4))
cost={'turn':round(mean(turn),3),'short':round(mean(shortg),3),'n':len(seq),'gross':_shp(gross),
      'net_10_50':_shp(net),'eqg':eqg,'mon':[MONTHS[seq[i][0]+1] for i in range(len(seq))]}

BT={'meta':{'names':len(PXNAMES),'pairs':len(pairs),'ranked':len(perpair),'breadth':breadth,
            'win':'Jun-2022 to Jun-2026','entry':'~2023 to 2026 (≥18m P/E baseline before each entry)'},
    'pair_ic':pair_ic,'pair_cond':pair_cond,'pair_dec':pair_dec,'pair_port':pair_port,
    'sn_ic':sn_ic,'sn_cond':sn_cond,'perpair':perpair,'trap':trap,'cost':cost}
json.dump(BT, open('bt_results.json','w'))
print('exported bt_results.json')
print('breadth %pos IC:', breadth, '| ranked pairs:', len(perpair))
print('pair 6m discount:', pair_cond['6'], '| portfolio sharpe:', pair_port['sharpe'], 'n', pair_port['n'])
print('top3:', [(p['a'],p['b'],p['ic']) for p in perpair[:3]])
print('size (KB):', round(len(json.dumps(BT))/1024,1))
