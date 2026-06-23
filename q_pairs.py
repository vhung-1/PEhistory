import json, math
from statistics import mean, pstdev
P=json.load(open('prices_all.json')); D=json.load(open('data.json'))
MONTHS=P['MONTHS']; PX=P['PX']; PE=D['pe']; DATES=D['dates']; SECOF=D['sector_of']
CLUSTERS=[['CME US','ICE US','NDAQ US','CBOE US'],['LSEG LN','DB1 GY','ENX FP'],['TW US','MKTX US'],
 ['SPGI US','MCO US'],['EFX US','TRU US','EXPN LN'],['MSCI US','SPGI US','FDS US'],['V US','MA US'],
 ['FIS US','FISV US','GPN US'],['PYPL US','XYZ US','ADYEN NA'],['TOST US','FOUR US','XYZ US'],
 ['AFRM US','KLAR US','SOFI US'],['SOFI US','CHYM US'],['CPAY US','WEX US'],['WU US','WISE LN','RELY LN'],
 ['LAZ US','EVR US','MC US','HLI US','PWP US','PJT US','PIPR US'],
 ['BX US','KKR US','APO US','ARES US','CG US','BAM US','TPG US','OWL US'],
 ['EQT SS','CVC NA','ICG LN','PGHN SW'],['STEP US','HLNE US'],
 ['BLK US','TROW US','BEN US','IVZ US','AB US'],['DWS GY','AMUN FP'],
 ['SCHW US','LPLA US','RJF US','SF US'],['SCHW US','IBKR US','HOOD US','ETOR US'],
 ['HOOD US','COIN US'],['COIN US','CRCL US'],['FTK GY','SQ SW','FBK IM'],['FBK IM','BGN IM']]
ym=lambda s:s[:7]
PEM={};mset=set()
for t,a in PE.items():
    last={}
    for i,v in enumerate(a):
        if v is not None and v>0: last[ym(DATES[i])]=v; mset.add(ym(DATES[i]))
    PEM[t]=last
PEMONTHS=sorted(mset)
def ezp(a,b,m):
    pa,pb=PEM.get(a,{}),PEM.get(b,{})
    if m not in pa or m not in pb: return None
    arr=[math.log(pa[mm]/pb[mm]) for mm in PEMONTHS if mm<=m and mm in pa and mm in pb]
    if len(arr)<18: return None
    mu=mean(arr);sd=pstdev(arr)
    return (math.log(pa[m]/pb[m])-mu)/sd if sd>0 else None
def relgap(a,b,m):
    # returns (z, dev) where dev = current relative P/E vs its expanding historical average, in fraction
    pa,pb=PEM.get(a,{}),PEM.get(b,{})
    if m not in pa or m not in pb: return None
    arr=[math.log(pa[mm]/pb[mm]) for mm in PEMONTHS if mm<=m and mm in pa and mm in pb]
    if len(arr)<18: return None
    mu=mean(arr); sd=pstdev(arr)
    if sd<=0: return None
    cur=math.log(pa[m]/pb[m])
    return ((cur-mu)/sd, math.exp(cur-mu)-1)
def mseries(a,b):
    out=[]
    for m in PEMONTHS:
        g=relgap(a,b,m)
        if g is not None: out.append({'t':m,'d':round(g[1]*100,1)})
    return out
def devnow(a,b):
    for m in reversed(PEMONTHS):
        g=relgap(a,b,m)
        if g is not None: return g[1]
    return None
def znow(a,b):
    for m in reversed(PEMONTHS):
        z=ezp(a,b,m)
        if z is not None: return z
    return None
QE=[m for m in MONTHS if m[5:7] in ('03','06','09','12')]
qi={m:MONTHS.index(m) for m in QE}
QLAB={'03':'Q1','06':'Q2','09':'Q3','12':'Q4'}
def qlabel(m): return QLAB[m[5:7]]+" '"+m[2:4]
def qret(t,i):
    a=PX.get(t)
    if a is None or i+1>=len(QE): return None
    p0=a[qi[QE[i]]];p1=a[qi[QE[i+1]]]
    return p1/p0-1 if (p0 and p1 and p0>0) else None
def spear(xs,ys):
    n=len(xs)
    if n<4: return None
    def rk(v):
        idx=sorted(range(n),key=lambda i:v[i]);r=[0]*n;i=0
        while i<n:
            j=i
            while j+1<n and v[idx[j+1]]==v[idx[i]]:j+=1
            a=(i+j)/2+1
            for k in range(i,j+1):r[idx[k]]=a
            i=j+1
        return r
    rx,ry=rk(xs),rk(ys);mx=mean(rx);my=mean(ry)
    num=sum((rx[i]-mx)*(ry[i]-my) for i in range(n));dx=sum((x-mx)**2 for x in rx);dy=sum((y-my)**2 for y in ry)
    return num/math.sqrt(dx*dy) if dx>0 and dy>0 else None
pairs=[];seen=set()
for c in CLUSTERS:
    mem=sorted(x for x in c if x in PX and len(PEM.get(x,{}))>=18)
    for i in range(len(mem)):
        for j in range(i+1,len(mem)):
            if (mem[i],mem[j]) not in seen: seen.add((mem[i],mem[j]));pairs.append((mem[i],mem[j]))
recs=[]
for (a,b) in pairs:
    zs=[];ls=[];sg=[];qarr=[]
    for i in range(2,len(QE)-1):
        g=relgap(a,b,QE[i])
        if g is None: continue
        z,dev=g
        r=qret(a,i); rb=qret(b,i)
        if r is None or rb is None: continue
        lsf=r-rb; d=1 if z<0 else -1; signed=d*lsf
        zs.append(z);ls.append(lsf);sg.append(signed)
        qarr.append({'p':qlabel(QE[i+1]),'dm':QE[i],'dev':round(dev*100,1),'long':(a if z<0 else b),'ret':round(signed*100,1),'win':bool(signed>0)})
    nq=len(sg)
    if nq<6: continue
    hit=100*sum(1 for x in sg if x>0)/nq
    avgq=mean(sg)*100
    cum=1.0
    for x in sg: cum*=(1+x)
    cum=(cum-1)*100
    ic=spear([-z for z in zs],ls)
    recs.append({'a':a,'b':b,'sec':SECOF.get(a,'?'),'nq':nq,'hit':round(hit),'avgq':round(avgq,2),
                 'cum':round(cum),'ic':round(ic,2) if ic is not None else None,'devnow':round((devnow(a,b) or 0)*100,1),'q':qarr,'ser':mseries(a,b)})
recs.sort(key=lambda r:(-r['hit'],-r['avgq']))
json.dump(recs,open('q_pairs.json','w'))
print('records:',len(recs),'| size',round(len(json.dumps(recs))/1024,1),'KB')
print('sample detail (LPLA/SCHW first 4 q):')
ex=[r for r in recs if r['a']=='LPLA US' and r['b']=='SCHW US'][0]
for o in ex['q'][:4]: print('  ',o)
print('  ...total',len(ex['q']),'quarters, hit',ex['hit'],'%, cum',ex['cum'],'%')
