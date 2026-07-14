import os
import pandas as pd, numpy as np, json
raw = pd.read_excel(os.environ.get('WORKBOOK','Coverage_PE_multiples.xlsx'), sheet_name='HC', header=None)
tickers=[str(x).strip() for x in raw.iloc[2,1:].tolist()]
dates=pd.to_datetime(raw.iloc[5:,0],errors='coerce')
data=raw.iloc[5:,1:].apply(pd.to_numeric,errors='coerce'); data.columns=tickers; data.index=dates
data=data[data.index.notna()].sort_index()
ASOF='2026-07-13'  # latest settled US close (Mon 13 Jul); pulled Tue 14 Jul, so Mon's US session has settled. 14 Jul (today) is excluded per CLAUDE.md §7a.
data=data[data.index<=ASOF]
data=data[data.index.dayofweek<5]  # exclude weekend rows (Sat/Sun); series are trading-day only

SECTORS = {
 'Exchanges': ['CME US','ICE US','NDAQ US','CBOE US','LSEG LN','DB1 GY','ENX FP','TW US','MKTX US','MIAX US','MRX US'],
 'Info Services': ['SPGI US','MCO US','MSCI US','FDS US','EFX US','TRU US','EXPN LN','FICO US','VRSK US'],
 'Payments & Fintech': ['V US','MA US','PYPL US','XYZ US','ADYEN NA','TOST US','SHOP US','SOFI US','FISV US','FIS US','GPN US','JKHY US','CPAY US','WEX US','AFRM US','KLAR US','BILL US','CHYM US','MQ US','FOUR US','WISE LN','RELY US','WU US'],
 'M&A Boutiques': ['LAZ US','EVR US','MC US','HLI US','PWP US','PJT US','PIPR US'],
 'Alternatives': ['PGHN SW','EQT SS','CVC NA','ICG LN','ARES US','APO US','BX US','KKR US','OWL US','CG US','BAM US','TPG US','STEP US','HLNE US'],
 'Traditional AM': ['BLK US','TROW US','DWS GY','AMUN FP','AB US','BEN US','IVZ US','AMP US'],
 'Wealth & Brokers': ['SCHW US','LPLA US','HOOD US','IBKR US','COIN US','RJF US','SF US','WLTH US','ETOR US','SQN SW','FTK GY','BGN IM','FBK IM','CRCL US','FIGR US','AZA SS','SAVE SS','IGG LN','AJB LN'],
}
SECNAMES = [t for v in SECTORS.values() for t in v]   # canonical coverage drives the universe
has = {t: (t in data.columns and int(data[t].notna().sum())>0) for t in SECNAMES}
excluded = [t for t in SECNAMES if not has[t]]         # coverage names absent/empty in this workbook
SECTORS_F = {k:[t for t in v if has[t]] for k,v in SECTORS.items()}
sec_of = {t:k for k,v in SECTORS_F.items() for t in v}

DATES=[d.strftime('%Y-%m-%d') for d in data.index]
PE={}
for t in SECNAMES:
    if not has[t]: continue
    col=data[t]
    PE[t]=[ (None if pd.isna(v) else round(float(v),2)) for v in col.values ]

payload = dict(asof=DATES[-1], dates=DATES, sectors=SECTORS_F, sector_of=sec_of, excluded=excluded, pe=PE)
js = json.dumps(payload, separators=(',',':'))
open('data.json','w').write(js)
print('tickers with data:', len(PE), '| dates:', len(DATES), '| excluded:', excluded)
print('JSON size: %.2f MB' % (len(js)/1e6))
