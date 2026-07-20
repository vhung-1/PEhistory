# PE Data API — Claude Code Agent Skill

Connect any Claude Code agent to the live diversified-financials NTM forward-P/E dataset served on GitHub Pages.

---

## Discovery endpoint

Start here. Returns the full manifest: universe, date range, all endpoint schemas.

```
GET https://vhung-1.github.io/PEhistory/api.json
```

Check `asof` to know how fresh the data is (updates when `main` is pushed).

---

## Base URL

```
https://vhung-1.github.io/PEhistory/
```

All endpoints are `GET`, return JSON, and are served with `Access-Control-Allow-Origin: *` (no auth, no CORS issue).

---

## Endpoints

### `data.json` — NTM forward P/E panel (primary)

```
GET https://vhung-1.github.io/PEhistory/data.json
```

**Shape:**
```jsonc
{
  "asof": "2026-07-17",           // date of last settled close
  "dates": ["2020-07-20", ...],   // 1565 weekday-only ISO dates
  "pe": {
    "CME US":  [29.5, 29.8, null, ...],  // NTM fwd P/E per date; null = no data
    "SCHW US": [18.2, 18.1, 18.4, ...],
    ...                           // 91 tickers total
  },
  "sectors": {
    "Exchanges":         ["CME US", "ICE US", "NDAQ US", ...],
    "Info Services":     ["SPGI US", "MCO US", ...],
    "Payments & Fintech":["V US", "MA US", "PYPL US", ...],
    "M&A Boutiques":     ["LAZ US", "EVR US", ...],
    "Alternatives":      ["BX US", "KKR US", "APO US", ...],
    "Traditional AM":    ["BLK US", "TROW US", ...],
    "Wealth & Brokers":  ["SCHW US", "LPLA US", ...]
  },
  "sector_of": { "CME US": "Exchanges", ... },  // reverse lookup
  "excluded": []                  // tickers with no data (normally empty)
}
```

**Key rule:** `pe[TICKER][i]` is the P/E on `dates[i]`. Arrays are index-aligned.

---

### `daily_px.json` — Daily adjusted close prices

```
GET https://vhung-1.github.io/PEhistory/daily_px.json
```

**Shape:**
```jsonc
{
  "asof": "2026-07-17",
  "note": "S&P Global daily ADJUSTED close (total return, local currency, single back-adjustment basis), aligned to trading days, holiday-ffilled",
  "px": {
    "CME US":  [272.15, 257.76, ...],  // aligned to data.json dates
    "SCHW US": [72.4, 73.1, ...],
    ...
  }
}
```

`null` before each ticker's listing/IPO date. Use for share-price return calculations.

---

### `q_pairs.json` — Quarterly pair consistency records

```
GET https://vhung-1.github.io/PEhistory/q_pairs.json
```

**Shape:** array of 101 records, sorted by hit rate descending.

```jsonc
[
  {
    "a": "LPLA US", "b": "SCHW US",
    "sec": "Wealth & Brokers",
    "nq": 14,           // quarters tested
    "hit": 79,          // % quarters where long-cheap beat short-rich
    "avgq": 2.34,       // average quarterly LS return (%)
    "cum": 38,          // cumulative LS return (%)
    "ic": 0.42,         // Spearman IC (z-score vs next-quarter LS return)
    "devnow": -12.3,    // current relative P/E vs expanding avg (%)
    "q": [              // per-quarter detail
      {
        "p": "Q3 '26",        // quarter label (period end)
        "dm": "2026-06",      // signal month
        "dev": -12.3,         // relative P/E deviation (%)
        "long": "LPLA US",    // which leg to go long
        "ret": 4.2,           // realised LS return (%)
        "win": true
      }, ...
    ],
    "ser": [            // monthly premium/discount series
      {"t": "2020-07", "d": -5.2}, ...
    ]
  }, ...
]
```

---

### `bt_results.json` — Backtest reference metrics

```
GET https://vhung-1.github.io/PEhistory/bt_results.json
```

Contains IC by horizon (1/3/6/12m), conditional means, portfolio Sharpe/mean/vol, trend-filter splits, cost analysis.

---

### `btdata.json` — Monthly price panel (backtest)

```
GET https://vhung-1.github.io/PEhistory/btdata.json
```

```jsonc
{
  "XMONTHS": ["2022-06", "2022-07", ...],  // ~49 month-end dates
  "PX": { "CME US": [220.4, null, ...], ... }
}
```

---

### `sw_data.json` — Software reference panel

```
GET https://vhung-1.github.io/PEhistory/sw_data.json
```

NTM forward P/E for 8 software names (MSFT, ORCL, CRM, NOW, WDAY, ADBE, INTU, ADSK). Reference only — NOT in the 91-name universe.

---

## Coverage universe — 91 tickers across 7 sub-sectors

| Sub-sector | Tickers |
|---|---|
| Exchanges (11) | CME US · ICE US · NDAQ US · CBOE US · LSEG LN · DB1 GY · ENX FP · TW US · MKTX US · MIAX US · MRX US |
| Info Services (9) | SPGI US · MCO US · MSCI US · FDS US · EFX US · TRU US · EXPN LN · FICO US · VRSK US |
| Payments & Fintech (23) | V US · MA US · PYPL US · XYZ US · ADYEN NA · TOST US · SHOP US · SOFI US · FISV US · FIS US · GPN US · JKHY US · CPAY US · WEX US · AFRM US · KLAR US · BILL US · CHYM US · MQ US · FOUR US · WISE LN · RELY US · WU US |
| M&A Boutiques (7) | LAZ US · EVR US · MC US · HLI US · PWP US · PJT US · PIPR US |
| Alternatives (14) | PGHN SW · EQT SS · CVC NA · ICG LN · ARES US · APO US · BX US · KKR US · OWL US · CG US · BAM US · TPG US · STEP US · HLNE US |
| Traditional AM (8) | BLK US · TROW US · DWS GY · AMUN FP · AB US · BEN US · IVZ US · AMP US |
| Wealth & Brokers (19) | SCHW US · LPLA US · HOOD US · IBKR US · COIN US · RJF US · SF US · WLTH US · ETOR US · SQN SW · FTK GY · BGN IM · FBK IM · CRCL US · FIGR US · AZA SS · SAVE SS · IGG LN · AJB LN |

Tickers are Bloomberg-style: `"CME US"`, `"LSEG LN"`, `"DB1 GY"`, etc.

---

## How to use in a Claude Code agent

### Fetch and parse in Python

```python
import json, urllib.request

BASE = "https://vhung-1.github.io/PEhistory/"

def fetch(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.load(r)

data = fetch("data.json")
dates = data["dates"]
pe    = data["pe"]

# Latest P/E for a ticker
def latest_pe(ticker):
    arr = pe.get(ticker, [])
    for v in reversed(arr):
        if v is not None:
            return v
    return None

print(latest_pe("CME US"))    # e.g. 24.3
print(data["asof"])            # e.g. "2026-07-17"
```

### Get a full P/E history as a date→value dict

```python
def pe_series(ticker):
    arr = pe.get(ticker, [])
    return {dates[i]: arr[i] for i in range(len(dates)) if arr[i] is not None}

cme = pe_series("CME US")
# {"2020-07-20": 26.1, "2020-07-21": 26.4, ...}
```

### Sector aggregate (equal-weighted mean, excluding a ticker)

```python
from statistics import mean

def sector_avg(sector_name, exclude=None):
    members = [t for t in data["sectors"][sector_name] if t != exclude]
    result = {}
    for i, dt in enumerate(dates):
        vals = [pe[t][i] for t in members if pe.get(t) and pe[t][i] is not None]
        result[dt] = mean(vals) if vals else None
    return result
```

### Compute relative P/E z-score (pair signal)

```python
import math
from statistics import mean, pstdev

def pair_z(ticker_a, ticker_b):
    """Expanding-window z-score of ln(PE_a / PE_b). Min 18-month history."""
    a_pe = {dates[i]: pe[ticker_a][i] for i in range(len(dates))
            if pe.get(ticker_a) and pe[ticker_a][i]}
    b_pe = {dates[i]: pe[ticker_b][i] for i in range(len(dates))
            if pe.get(ticker_b) and pe[ticker_b][i]}
    months = sorted({d[:7] for d in dates})
    # last value per month
    def monthly(pm):
        m = {}
        for d, v in sorted(pm.items()):
            if v and v > 0: m[d[:7]] = v
        return m
    ma, mb = monthly(a_pe), monthly(b_pe)
    common = sorted(m for m in months if m in ma and m in mb)
    if len(common) < 18:
        return None
    log_ratios = [math.log(ma[m] / mb[m]) for m in common]
    mu, sd = mean(log_ratios), pstdev(log_ratios)
    cur = log_ratios[-1]
    return (cur - mu) / sd if sd > 0 else None

print(pair_z("LPLA US", "SCHW US"))  # e.g. -1.4 (LPLA cheap vs SCHW)
```

### Quick check for stale data

```python
from datetime import date

d = fetch("data.json")
asof = date.fromisoformat(d["asof"])
lag  = (date.today() - asof).days
if lag > 5:
    print(f"WARNING: data is {lag} days old (asof {asof})")
```

---

## Notes

- **No auth required.** CORS is open — works from any browser, Python, Node, etc.
- **Refresh cadence:** data updates when a new workbook is pushed to `main`. Check `asof` before running analysis.
- **Array alignment:** every array in `pe` and `px` is index-aligned to `dates`. Always zip against `dates`, never assume date ordering independently.
- **Nulls before IPO:** `daily_px.json` has `null` for dates before a name's listing. `data.json` `pe` also has `null` gaps for names where no estimate was available.
- **Population std dev** is used throughout (not sample): `pstdev` in Python's `statistics` module, or divide by `n` not `n-1`.
- **Tickers are Bloomberg-style strings** including the exchange suffix: `"V US"` not `"V"`, `"LSEG LN"` not `"LSEG"`.
