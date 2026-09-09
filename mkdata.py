import os
import pandas as pd, numpy as np, json
raw = pd.read_excel(os.environ.get('WORKBOOK','Coverage_PE_multiples.xlsx'), sheet_name='HC', header=None)
tickers=[str(x).strip() for x in raw.iloc[2,1:].tolist()]
dates=pd.to_datetime(raw.iloc[5:,0],errors='coerce')
data=raw.iloc[5:,1:].apply(pd.to_numeric,errors='coerce'); data.columns=tickers; data.index=dates
data=data[data.index.notna()].sort_index()
ASOF='2026-09-04'  # latest settled US close (Fri 4 Sep) — still, on the 9 Sep workbook. Mon 7 Sep was
                   # US Labor Day, and although Tue 8 Sep WAS a US trading day this pull does not carry
                   # its US closes: 64 of the 71 US names are byte-identical to 4 Sep across both 7 and
                   # 8 Sep, and the 7 that move shift by ~0.01-0.07 (consensus-EPS revisions, not price).
                   # The 20 European names are genuinely current to 8 Sep. Taking ASOF=8 Sep would ship
                   # two forward-filled US days AND mix a 8 Sep European leg against a 4 Sep US leg in
                   # every cross-border pair, so it stays 4 Sep per CLAUDE.md §7a / §9.2 and the §10
                   # diagnostic. A revisions-only refresh.
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

# --- Vendor-glitch hold (CLAUDE.md §10). The Bloomberg workbook carries a spurious V-trough in SQN SW's
# forward P/E over 2026-05-29..2026-07-15: -46% overnight, flat for 7 weeks, +69% snap-back, with the share
# price stable throughout. Per the investor's decision (2026-09-03) the window is held at the values sourced
# from the pre-glitch workbook (below, 2 dp) — sourced values only, no interpolation. Delete this block if the
# vendor corrects the series (verify: the raw workbook values for these dates return to the ~15-17x range).
HOLD = {'SQN SW': {
    '2026-05-29':15.94, '2026-06-01':15.71, '2026-06-02':15.66, '2026-06-03':15.33, '2026-06-04':15.51, '2026-06-05':15.33,
    '2026-06-08':15.54, '2026-06-09':15.33, '2026-06-10':15.18, '2026-06-11':15.27, '2026-06-12':15.84, '2026-06-15':16.07,
    '2026-06-16':16.07, '2026-06-17':15.91, '2026-06-18':15.87, '2026-06-19':15.58, '2026-06-22':15.64, '2026-06-23':15.64,
    '2026-06-24':15.45, '2026-06-25':15.36, '2026-06-26':14.93, '2026-06-29':14.98, '2026-06-30':15.24, '2026-07-01':15.48,
    '2026-07-02':15.95, '2026-07-03':16.13, '2026-07-06':16.77, '2026-07-07':16.78, '2026-07-08':16.52, '2026-07-09':16.71,
    '2026-07-10':16.76, '2026-07-13':16.62, '2026-07-14':16.86, '2026-07-15':17.02,
}}
for _t,_m in HOLD.items():
    if _t in PE:
        for _i,_d in enumerate(DATES):
            if _d in _m: PE[_t][_i] = _m[_d]


payload = dict(asof=DATES[-1], dates=DATES, sectors=SECTORS_F, sector_of=sec_of, excluded=excluded, pe=PE)
js = json.dumps(payload, separators=(',',':'))
open('data.json','w').write(js)
print('tickers with data:', len(PE), '| dates:', len(DATES), '| excluded:', excluded)
print('JSON size: %.2f MB' % (len(js)/1e6))
