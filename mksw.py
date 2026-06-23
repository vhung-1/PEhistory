import os, json
import pandas as pd

# Build sw_data.json: the SOFTWARE reference panel for the JKHY tab.
# Source = the Bloomberg software workbook (same HC layout as the coverage file).
# Run AFTER mkdata.py — it aligns to data.json's dates. JKHY is intentionally
# excluded here (the tab draws JKHY from the main coverage panel for consistency).
SRC = os.environ.get('SW_WORKBOOK', 'bbg_software_mults.xlsx')

xl = pd.ExcelFile(SRC)
sheet = next((s for s in xl.sheet_names if s.lower() == 'hc'), xl.sheet_names[0])
raw = pd.read_excel(SRC, sheet_name=sheet, header=None)

tickers = [str(x).strip() for x in raw.iloc[2, 1:].tolist() if str(x).strip() not in ('nan', '')]
dates = pd.to_datetime(raw.iloc[5:, 0], errors='coerce')
df = raw.iloc[5:, 1:1 + len(tickers)].apply(pd.to_numeric, errors='coerce')
df.columns = tickers
df.index = dates
df = df[df.index.notna()].sort_index()
df.index = df.index.strftime('%Y-%m-%d')

SWN = [t for t in tickers if t != 'JKHY US']           # JKHY comes from the main panel
main = json.load(open('data.json'))
D = main['dates']                                       # align to the coverage calendar
pe = {t: {d: (None if pd.isna(v) else round(float(v), 2)) for d, v in df[t].items()} for t in SWN}
out = {'asof': main['asof'], 'names': SWN, 'pe': {t: [pe[t].get(d) for d in D] for t in SWN}}

json.dump(out, open('sw_data.json', 'w'), separators=(',', ':'))
print(f"sw_data.json: {len(SWN)} names aligned to {len(D)} dates ({SWN})")
