import os
import pandas as pd, numpy as np, json
raw = pd.read_excel(os.environ.get('WORKBOOK','Coverage_PE_multiples.xlsx'), sheet_name='HC', header=None)
tickers=[str(x).strip() for x in raw.iloc[2,1:].tolist()]
dates=pd.to_datetime(raw.iloc[5:,0],errors='coerce')
data=raw.iloc[5:,1:].apply(pd.to_numeric,errors='coerce'); data.columns=tickers; data.index=dates
data=data[data.index.notna()].sort_index()
ASOF='2026-10-16'  # latest settled US close (Fri 16 Oct): all 91 names moved at full precision.
                   # The workbook was pulled Sat 17 Oct 16:00 UTC; the Sat 17 Oct row is a weekend
                   # forward-fill (0 changes) and is excluded by the weekday filter below.
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

# DROP — unusable sourced observations, removed (set null) rather than published or replaced.
# Distinct from HOLD above: HOLD re-pins dates to values that WERE genuinely sourced from an
# earlier workbook; DROP is for a date where no trustworthy value exists in any workbook, so the
# only options are to publish a value known to be wrong or to drop it. CLAUDE.md §7's hard rule
# ("if a series is unavailable, drop the name — do not invent values") makes dropping the correct
# treatment; carrying the prior day forward would be fabrication.
#
# CRCL US 2026-10-15: the workbook prints 1.79x, down from 51.31x on 14 Oct (-96.5% overnight),
# and forward-fills it into the 16 Oct pull-day row. Circle's share price over the same day went
# 79.55 -> 86.97 (+9.3%, S&P adjusted close), so the vendor's FY+1 EPS is wrong by ~31x: not a
# market event and not the annual FY+1 roll (§9b). Same signature as TOST US on 2026-09-11, which
# the vendor fixed three days later. lastVal() scans back to the last non-null, so the
# cross-sectional tabs fall back to CRCL's 14 Oct observation. Remove once the vendor corrects it.
# 2026-10-17 workbook: NOT fixed. 10-15 is unchanged at 1.79x, and 16 Oct prints 1.69x. That day's
# -5.46% P/E move matches the share price's -5.46% (86.97 -> 82.22), so the vendor has simply carried
# the broken EPS (implied ~48.5 against ~1.55 before) forward. 16 Oct is the same blow-up; dropped too.
#
# SPGI US 2026-10-16: the workbook prints 12.07x, down from 21.06x on 15 Oct (-42.7% overnight), while
# S&P Global's share price rose +1.14% (424.81 -> 429.64). Implied FY+1 EPS jumps from 20.17 to 35.60
# in one day. The S&P pull shows no corporate action (adjusted-price ratio between pulls exactly 1.0),
# SPGI's annual roll is in February, and Capital IQ's FY2027 normalized EPS consensus is 20.17 mean
# (range 19.54-21.01): the pre-break Bloomberg level matched it exactly, and 35.60 is 70% above the
# highest single estimate. A vendor error on a brand-new date. Remove once the vendor corrects it.
DROP = {'CRCL US': ['2026-10-15', '2026-10-16'], 'SPGI US': ['2026-10-16']}
for _t,_ds in DROP.items():
    if _t in PE:
        for _i,_d in enumerate(DATES):
            if _d in _ds: PE[_t][_i] = None


payload = dict(asof=DATES[-1], dates=DATES, sectors=SECTORS_F, sector_of=sec_of, excluded=excluded, pe=PE)
js = json.dumps(payload, separators=(',',':'))
open('data.json','w').write(js)
print('tickers with data:', len(PE), '| dates:', len(DATES), '| excluded:', excluded)
print('JSON size: %.2f MB' % (len(js)/1e6))
