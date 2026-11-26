import os
import pandas as pd, numpy as np, json
raw = pd.read_excel(os.environ.get('WORKBOOK','Coverage_PE_multiples.xlsx'), sheet_name='HC', header=None)
# The sheet can carry a second block to the right: the CALENDARIZED P/E for non-December year-ends
# (added 2026-10-30, columns CQ.. with their own DATES column, CP). It repeats tickers from the main
# block, so the FY+1 panel is read only from the columns before that block's DATES column.
_hdr = [str(x).strip().upper() for x in raw.iloc[4].tolist()]
CAL_DATES_COL = next((c for c in range(1, raw.shape[1]) if _hdr[c] == 'DATES'), None)
MAIN_END = CAL_DATES_COL if CAL_DATES_COL is not None else raw.shape[1]
tickers=[str(x).strip() for x in raw.iloc[2,1:MAIN_END].tolist()]
dates=pd.to_datetime(raw.iloc[5:,0],errors='coerce')
data=raw.iloc[5:,1:MAIN_END].apply(pd.to_numeric,errors='coerce'); data.columns=tickers; data.index=dates
# A ticker typed into a second FY+1 column (AMP US in column CV of the 2026-11-26 afternoon workbook) is dropped
# only if that column is EMPTY; two copies that both carry values still stop the build.
_keep=[]
for _i,_t in enumerate(tickers):
    _dup=_t and _t!='nan' and tickers.count(_t)>1
    if _dup and data.iloc[:,_i].notna().sum()==0: print(f'  dropping empty duplicate FY+1 column for {_t} (sheet column {_i+1})'); continue
    _keep.append(_i)
data=data.iloc[:,_keep]; tickers=[tickers[i] for i in _keep]
_named=[t for t in tickers if t and t!='nan']
assert len(_named)==len(set(_named)), 'duplicate tickers in the FY+1 block'
data=data[data.index.notna()].sort_index()
ASOF='2026-11-25'  # latest settled US close (Wed 25 Nov): all 95 names moved at full precision. The workbook was
# saved Thu 26 Nov (Thanksgiving, US market shut) at 09:25 UTC; the Thursday row is excluded by this cap.
data=data[data.index<=ASOF]
data=data[data.index.dayofweek<5]  # exclude weekend rows (Sat/Sun); series are trading-day only

SECTORS = {
 'Exchanges': ['CME US','ICE US','NDAQ US','CBOE US','LSEG LN','DB1 GY','ENX FP','TW US','MKTX US','MIAX US','MRX US'],
 'Info Services': ['SPGI US','MCO US','MSCI US','FDS US','EFX US','TRU US','EXPN LN','FICO US','VRSK US'],
 'Payments & Fintech': ['V US','MA US','PYPL US','XYZ US','ADYEN NA','TOST US','SHOP US','SOFI US','FISV US','FIS US','GPN US','JKHY US','CPAY US','WEX US','AFRM US','KLAR US','BILL US','CHYM US','MQ US','FOUR US','WISE LN','RELY US','WU US','NAVN US','INTU US','DAVE US'],
 'M&A Boutiques': ['LAZ US','EVR US','MC US','HLI US','PWP US','PJT US','PIPR US'],
 'Alternatives': ['PGHN SW','EQT SS','CVC NA','ICG LN','ARES US','APO US','BX US','KKR US','OWL US','CG US','BAM US','TPG US','STEP US','HLNE US','BPT LN'],
 'Traditional AM': ['BLK US','TROW US','DWS GY','AMUN FP','AB US','BEN US','IVZ US','EMG LN','AMG US'],
 'Wealth & Brokers': ['SCHW US','LPLA US','HOOD US','IBKR US','COIN US','RJF US','SF US','WLTH US','ETOR US','SQN SW','FTK GY','BGN IM','FBK IM','CRCL US','FIGR US','AZA SS','SAVE SS','IGG LN','AJB LN','AMP US'],  # AMP (Ameriprise) moved from Traditional AM, investor request 2026-11-26
}
SECNAMES = [t for v in SECTORS.values() for t in v]   # canonical coverage drives the universe
has = {t: (t in data.columns and int(data[t].notna().sum())>0) for t in SECNAMES}

# --- CARRY (investor decision 2026-11-15). When a coverage name's workbook column comes back EMPTY (a failed
# Bloomberg pull, not a delisting), keep the history already sourced from earlier workbooks instead of dropping
# the name: its values are re-keyed by date from data.json / cal_pe.json at the pinned commit, and every date
# after that file's asof stays null (nothing is filled forward, so nothing is invented). Applies only while the
# column is empty; once a workbook carries the name again, its own values are used and the entry should go.
# IGG LN: both columns (FY+1 and calendarized) empty in the 2026-11-15 workbook although IG Group traded normally.
import subprocess
# HOLD mode (investor decision 2026-11-17): the 2026-11-17 after-close workbook's IGG LN column carries the NEW Jersey listing
# (one value, 6.80x on 2026-11-17, no history; S&P has no price for it yet). Until the investor decides to join the
# two listings, the old listing's history stays carried and the new listing's values are left out.
# JOIN mode (investor decision 2026-11-19): once S&P priced the new listing (one continuous price series with the old,
# scale factor exactly 1.0), IG's P/E continues from the new listing: the old listing's sourced values up to the pinned
# commit's asof (2026-11-12), then the workbook's own values after it. The calendarized series stays the old one (it
# ends 2026-10-29, before the switch). Where the two overlap (23 Oct-12 Nov) the new series runs about 1% above the old,
# so the joined series carries a small step at 13 Nov.
CARRY = {'IGG LN': ('68263bc', 'join')}   # ticker -> (commit with the last sourced values, 'empty' | 'hold' | 'join')
JOIN_FROM = {}                             # ticker -> first date taken from the workbook (join mode)
CARRIED, CARRIED_CAL = {}, {}
for _t, (_sha, _mode) in CARRY.items():
    if has.get(_t) and _mode == 'empty':
        print(f'CARRY: {_t} has data in this workbook again; remove its CARRY entry'); continue
    if has.get(_t) and _mode == 'hold':
        _wb = data[_t].dropna()
        print(f'CARRY (hold): {_t} workbook values left out: {[(d.strftime("%Y-%m-%d"), round(float(v), 2)) for d, v in _wb.items()][-5:]}')
    _src = json.loads(subprocess.check_output(['git', 'show', f'{_sha}:data.json']))
    CARRIED[_t] = dict(zip(_src['dates'], _src['pe'][_t]))
    _cs = json.loads(subprocess.check_output(['git', 'show', f'{_sha}:cal_pe.json']))['series'].get(_t)
    if _cs: CARRIED_CAL[_t] = _cs
    if _mode == 'join': JOIN_FROM[_t] = _src['asof']   # workbook values strictly after this date
    has[_t] = True
    print(f'CARRY: {_t} {_mode}; carrying its sourced history to {_src["asof"]} from {_sha}' + (' then the workbook after it' if _mode == 'join' else ''))
excluded = [t for t in SECNAMES if not has[t]]         # coverage names absent/empty in this workbook
SECTORS_F = {k:[t for t in v if has[t]] for k,v in SECTORS.items()}
sec_of = {t:k for k,v in SECTORS_F.items() for t in v}

DATES=[d.strftime('%Y-%m-%d') for d in data.index]
PE={}
for t in SECNAMES:
    if not has[t]: continue
    if t in CARRIED:
        if t in JOIN_FROM and t in data.columns:
            _wbv = {d.strftime('%Y-%m-%d'): v for d, v in data[t].items()}
            PE[t] = [CARRIED[t].get(d) if d <= JOIN_FROM[t] else (None if pd.isna(_wbv.get(d)) else round(float(_wbv[d]), 2)) for d in DATES]
        else:
            PE[t] = [CARRIED[t].get(d) for d in DATES]
        continue
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
# Empty is the normal state. Last used for CRCL US 2026-10-15/16 and SPGI US 2026-10-16 (vendor EPS
# blow-ups: 1.79x/1.69x and 12.07x against share prices that moved +9.3%/-5.5% and +1.1%); the
# 2026-10-20 workbook corrected all three (55.07x, 52.06x, 21.29x, each day's move now matching the
# share price), so the entries were removed.
# NAVN US (added 2026-11-25): two single-day spikes in its implied FY+1 EPS, each flanked on both sides by the
# same value: 2026-05-14 (170.43x; implied EPS 0.109 against 0.166 either side, share price +2.5%) and 2026-06-04
# (113.96x; 0.195 against 0.166 either side, share price +0.5%). No earlier workbook has a value for them, so
# they are dropped to null rather than replaced. Remove an entry if a later workbook corrects the date.
DROP = {'NAVN US': ['2026-05-14', '2026-06-04']}
for _t,_ds in DROP.items():
    if _t in PE:
        for _i,_d in enumerate(DATES):
            if _d in _ds: PE[_t][_i] = None


# --- Calendarized P/E block (non-December year-ends) -> cal_pe.json, consumed by mkxs.py. Keyed by
# its own dates (column CP), with the same rules as the main panel: weekdays only, capped at ASOF,
# coverage tickers only, 2 dp. A missing value stays missing; nothing is filled.
CAL = {}
if CAL_DATES_COL is not None:
    _cdr = raw.iloc[5:, CAL_DATES_COL]
    # Since the 2026-11-24 workbook this column can hold Excel serial numbers (43831 = 2020-01-01) instead of dates.
    _num = pd.to_numeric(_cdr, errors='coerce')
    _cd = pd.to_datetime(_num, unit='D', origin='1899-12-30') if _num.notna().sum() > 0.9 * _cdr.notna().sum() else pd.to_datetime(_cdr, errors='coerce')
    for c in range(CAL_DATES_COL + 1, raw.shape[1]):
        t = str(raw.iloc[2, c]).strip()
        if t not in SECNAMES: continue
        assert t not in CAL, f'duplicate calendarized column for {t}'
        s_ = pd.Series(pd.to_numeric(raw.iloc[5:, c], errors='coerce').values, index=_cd.values)
        s_ = s_[s_.index.notna()].sort_index()
        s_ = s_[(s_.index <= ASOF) & (s_.index >= data.index[0]) & (s_.index.dayofweek < 5)].dropna()
        if len(s_):
            CAL[t] = dict(dates=[d.strftime('%Y-%m-%d') for d in s_.index], pe=[round(float(v), 2) for v in s_.values])
    for _t, _cs in CARRIED_CAL.items():   # CARRY (above): the name's calendarized series from the pinned commit
        if _t in CAL and CARRY[_t][1] == 'empty': continue
        _keep = [(d, v) for d, v in zip(_cs['dates'], _cs['pe']) if DATES[0] <= d <= ASOF]
        if _keep: CAL[_t] = dict(dates=[d for d, _ in _keep], pe=[v for _, v in _keep])
    _order = [str(raw.iloc[2, c]).strip() for c in range(CAL_DATES_COL + 1, raw.shape[1])]   # keep column order
    CAL = {t: CAL[t] for t in sorted(CAL, key=lambda t: _order.index(t) if t in _order else len(_order))}
    _f = str(raw.iloc[4, CAL_DATES_COL + 1]).strip()
    open('cal_pe.json', 'w').write(json.dumps(dict(asof=ASOF, formula=_f, series=CAL), separators=(',', ':')))
    print('calendarized series:', len(CAL), sorted(CAL))

payload = dict(asof=DATES[-1], dates=DATES, sectors=SECTORS_F, sector_of=sec_of, excluded=excluded, pe=PE)
js = json.dumps(payload, separators=(',',':'))
open('data.json','w').write(js)
print('tickers with data:', len(PE), '| dates:', len(DATES), '| excluded:', excluded)
print('JSON size: %.2f MB' % (len(js)/1e6))
