# CLAUDE.md — Relative-Value Forward-P/E Dashboard (operating manual)

> **How to use this file.** Drop it in the repo root as `CLAUDE.md` (Claude Code reads it automatically) and keep the source files described in §2 alongside it. This is a complete operating manual: it assumes **no prior conversation context**. Read §1 (what this is), §3 (build), §4 (the gate), and §7 (refresh) before changing anything.

> ⚠️ **Licensing first (see §11).** The dashboard **embeds licensed Bloomberg NTM forward-P/E and S&P-Global-derived adjusted prices** directly in the HTML. Anyone who can open the file can read the data. **Do not publish to a public site.** Private repo + access control only.

---

## 1. What this is

A **single, self-contained interactive HTML dashboard** for a long/short **diversified-financials** equity investor. It does relative **NTM forward-P/E** valuation across **85 names in 7 sub-sectors**, plus validated **mean-reversion pair backtests**, **per-pair quarterly consistency** analysis, single-name P/E history, a sub-sector small-multiples grid, and a **click-to-measure share-price-return tool** on the pair chart.

**Technical shape**
- **No runtime dependencies, no framework, no build step needed to *view*.** Plain HTML + one inline `<script>` of vanilla JS + inline SVG + one `<canvas>`. Opens by double-click. Current size ≈ **2.0 MB**.
- **All data is embedded** as JavaScript constants near the top of the script (see §5).
- **Ten tabs** (§6): Pairs · Name P/E · Flags · Summary · Screen · Matrix · Grid · Coverage · Consistency · Backtest.
- CSS is one `<style>` block themed entirely with custom properties (`--ink`, `--ink2`, `--muted`, `--faint`, `--line`, `--line2`, `--bg`, `--panel`, `--panel2`, `--accent`, `--series` `#15697A`, `--avg` `#E2733A`, `--cheap` `#2E7D52`, `--rich` `#C0392B`, `--mono`, `--sans`).

**The product is the file `Relative_PE_Dashboard.html`.** Everything else exists to regenerate it reproducibly.

---

## 2. Repo layout — canonical files vs scratch

**Canonical (needed to rebuild and maintain):**

| File | Role |
|---|---|
| `template.html` | **Source of truth.** The full dashboard with the embedded data replaced by 4 tokens: `__QDATA__`, `__BTDATA__`, `__DATA__`, `__DPX__`. All tab code (incl. the former `con.js`/`grid.js`/`namepe.js` modules and the portable backtest core) is already merged in here. |
| `mkdata.py` | Builds `data.json` (the P/E panel) from the uploaded Bloomberg workbook. |
| `q_pairs.py` | Builds `q_pairs.json` (Consistency tab records) from `data.json` + `prices_all.json`. |
| `backtest.py` | The Python backtest engine (reference implementation). |
| `bt_export.py` | Runs `backtest.py`'s setup and dumps `bt_results.json` (the numeric reference for the gate). |
| `bt_verify.js` | **The validation gate.** Re-derives the backtest from the *built HTML* and asserts 39 numeric checks against `bt_results.json`. |
| `build_dpx3.py` | Builds `daily_px.json` (the daily price panel) from S&P price pulls via the splice procedure (§7c). Latest version — supersedes `build_dpx.py`/`build_dpx2.py`. |
| `prices.py` + `prices_all.json` | **Monthly** adjusted-close panel for the backtest/consistency (hard-coded values, *not* a live resolver). |
| Data outputs: `data.json`, `q_pairs.json`, `btdata.json`, `prices_all.json`, `bt_results.json`, `daily_px.json` | The embedded/reference data (see §5). |

**Scratch / superseded — safe to ignore or delete:** `app2.js`…`app9.js`, `app_extracted.js`, `nt2.js`…`nt7.js`, `nodetest.js`, `bt_inject.js`, `bt_render.js`, `bt_core.js` (standalone copy of the core that now lives in `template.html`), `cov.js`, `ingest.py`, `resolve_daily.py`, `recalc.py`, `trapcost_proto.py`, `quarterly_backtest.py`, `q_results.json`, `perpair.json`, `PX_auto.json`, `bt_ready.json`, `built_script.js`, `build.py` (old), `build_dpx.py`, `build_dpx2.py`. (`con.js`, `grid.js`, `namepe.js` are also historical — their code is already in `template.html`.)

A first good task in Claude Code: move the scratch files into an `_archive/` folder so the working tree shows only the canonical set.

---

## 3. Build pipeline (token replacement)

The build replaces the 4 tokens in `template.html` with the 4 JSON payloads. **Order matters:** `__DATA__` is a substring of `__QDATA__` and `__BTDATA__`, so the longer tokens must be replaced first. `__DPX__` is independent. Replace each exactly once and assert none remain.

The relevant declarations in `template.html` look like:
```js
const DATA = __DATA__;
const BT   = __BTDATA__;
const QD   = __QDATA__;
const DPXMETA = __DPX__;
const DPX  = DPXMETA.px;   // daily price map keyed by ticker
```

Canonical `build.py`:
```python
import pathlib
tpl  = pathlib.Path("template.html").read_text(encoding="utf-8")
qd   = pathlib.Path("q_pairs.json").read_text(encoding="utf-8").strip()
bt   = pathlib.Path("btdata.json").read_text(encoding="utf-8").strip()
data = pathlib.Path("data.json").read_text(encoding="utf-8").strip()
dpx  = pathlib.Path("daily_px.json").read_text(encoding="utf-8").strip()
for tok in ("__QDATA__","__BTDATA__","__DATA__","__DPX__"):
    assert tpl.count(tok) == 1, f"{tok} count != 1"
out = (tpl.replace("__QDATA__", qd, 1)
          .replace("__BTDATA__", bt, 1)
          .replace("__DATA__", data, 1)
          .replace("__DPX__", dpx, 1))
assert not any(t in out for t in ("__QDATA__","__BTDATA__","__DATA__","__DPX__")), "token left"
pathlib.Path("Relative_PE_Dashboard.html").write_text(out, encoding="utf-8")
print(f"built {len(out)/1e6:.2f} MB")
```

---

## 4. Validation gate — **non-negotiable, run after every rebuild**

Two checks. Both must pass before the file is considered good or deployed.

**(a) JS syntax.** Extract the largest `<script>` from the built HTML and `node --check` it:
```bash
python3 -c "import re;h=open('Relative_PE_Dashboard.html',encoding='utf-8').read();open('/tmp/app.js','w',encoding='utf-8').write(max(re.findall(r'<script>([\s\S]*?)</script>',h),key=len))"
node --check /tmp/app.js   # must print nothing / exit 0
```

**(b) Backtest gate.** `node bt_verify.js` must print **`✅ ALL CHECKS PASSED (39 passed)`** (0 failed).

How `bt_verify.js` works (so you don't break it): it reads the built HTML, pulls the largest `<script>`, extracts the **portable backtest core** between the marker `function bmean(` and the comment `END PORTABLE CORE`, extracts the `CLUSTERS` array by bracket-balancing, parses `data.json` + `btdata.json`, runs `btPrep()`/`meanIC()`, and compares ~39 outputs (pair IC at 1/3/6/12m, single-name IC, the 6-month buy-the-discount conditional mean/N/hit, portfolio Sharpe/mean/vol/N, pair count, and the trend-filter splits) against `bt_results.json` with tolerances. It is a **self-consistency check**: the HTML engine must reproduce the Python reference. So if you change the backtest data, **regenerate `bt_results.json` with `python bt_export.py` before running the gate** — otherwise the engine and reference diverge and it fails.

If you edit the core's math, keep the `function bmean(` start marker and the `END PORTABLE CORE` end comment intact, and keep the core **DOM-free** (the verifier rejects it if it references `document.`/`getElementById`).

---

## 5. Data model (the embedded constants and their files)

**`data.json` → `const DATA`** — the valuation panel.
- `asof`: ISO date in the header.
- `dates`: array of **weekday-only** ISO dates (currently `2020-06-19` → `2026-06-18`, ~1,565 rows). **No weekend rows** (see §9).
- `pe`: `{ "<TICKER>": [number|null, …] }` — daily **NTM forward P/E**, aligned to `dates`. Tickers are Bloomberg-style: `"CME US"`, `"LSEG LN"`, `"DB1 GY"`, `"EQT SS"`, …
- `sectors`: `{ "<Sub-sector>": ["<TICKER>", …] }` (the 7 sub-sectors, §8).
- `sector_of`: reverse map `{ "<TICKER>": "<Sub-sector>" }`.
- `excluded`: tickers in the source dropped from the panel (currently `RELY LN`, `SQ SW`).

**`btdata.json` → `const BT`** — **monthly** price panel for the Backtest tab.
- `XMONTHS`: ~49 month-end ISO dates (currently `2022-06` … `2026-06`).
- `PX`: `{ "<name>": [number|null, …] }` — **monthly adjusted close** aligned to `XMONTHS`. Byte-identical content to `prices_all.json`. **Not** changed by the daily refresh (monthly cadence). **The backtest return window starts 2022-06 because this panel does** (see §7d).

**`q_pairs.json` → `const QD`** — precomputed per-pair quarterly records (currently 95). Each: `a`,`b` (tickers), `sec`, `nq`; headline `hit`,`avgq`,`cum`,`ic`,`devnow`; `q`: array of `{p,dm,dev,long,ret,win}` per quarter; `ser`: the **monthly premium/discount series** `{t:"YYYY-MM", d:%-vs-expanding-avg}` that the in-row chart plots, with the `q[].dm/dev` markers overlaid.

**`daily_px.json` → `const DPXMETA`, then `const DPX = DPXMETA.px`** — the **daily** price panel that powers the click-to-measure tool.
- `{ asof, note, px:{ "<TICKER>": [number|null, …] } }`, `px` arrays aligned to `DATA.dates`.
- **S&P-Global daily ADJUSTED close (total return), in local currency, on a single back-adjustment basis** (§7c), holiday-forward-filled, `null` before each name's listing/IPO date.

**Tab → source:** Pairs/Name P/E/Flags/Summary/Screen/Matrix/Grid/Coverage derive live from `DATA.pe`; the Pairs click-to-measure tool reads `DPX`; Consistency reads `QD`; Backtest reads `BT` and recomputes signals from `DATA.pe`.

---

## 6. The tabs (brief)

- **Pairs** — relative forward P/E of leg A ÷ leg B over time, with premium/discount stats, a window gauge, and ±-range. Either leg can be a single ticker **or** a sub-sector aggregate (sentinels `~avg~<sector>` / `~med~<sector>`); a sector-aggregate leg **excludes the other leg's ticker** from its own average/median. **Click-to-measure:** when leg A is a single ticker, click two dates on the chart to read **A's share-price total return** between them (dates, prices, calendar days, annualized). Disabled with a hint when A is an aggregate.
- **Name P/E** — single-name forward P/E vs its own history: ±1σ band, full-history mean, percentile, z-score, hover crosshair.
- **Flags / Summary / Screen / Matrix / Coverage** — cross-sectional cheap/rich views derived from `DATA.pe`.
- **Grid** — sub-sector small-multiple sparklines; each name vs its peer **median/average (excluding itself)**, or the curated intra-sub-sector pairs; with a cross-sector "Compare to" hero card.
- **Consistency** — each curated pair scored as a quarterly side-switching mean-reversion trade; expandable row with the annotated premium/discount chart (`ser` line + quarter win/loss dots + long-direction bands).
- **Backtest** — IC by horizon, return-by-z bars, trend filter, net-of-cost P&L.

---

## 7. DATA REFRESH PROCEDURE

> **Hard rule (carried from the original build): never fabricate, synthesise, interpolate, or placeholder a data point. Sourced primary data only. If a series is unavailable, drop the name — do not invent values.**

A full refresh updates **two** data layers in lockstep: the **P/E panel** (Bloomberg workbook) and the **daily price panel** (S&P Global). Do both so the click-to-measure tool never lags the chart.

### 7a. Forward P/E → `data.json`
1. The investor uploads a refreshed `Coverage_PE_multiples.xlsx` (sheet `HC`; ticker row at index 2; data from row index 5). It is **calendar-daily**, and **today's row plus weekends are forward-filled artifacts** — *not* clean closes.
2. In `mkdata.py` set `ASOF` to **the latest *real* trading day** = the most recent weekday that is **not today** (today's pull is intraday/forward-filled) and whose values differ from the prior day. In practice ASOF = "yesterday". The script caps at `ASOF` and then applies a **weekday filter** (`data.index.dayofweek < 5`) to drop Saturdays/Sundays.
3. Run `python mkdata.py` → `data.json` (2-dp rounding; `excluded` = `RELY LN`, `SQ SW`).
4. Sanity-check span/row-count, that there are **0 weekend rows**, and that historical overlap vs the prior `data.json` is stable (mean |Δ| ≈ 0.003x). New sourced P/E *revisions* on historical dates are fine — take the new file as truth.

### 7b. Regenerate the dependent references
```bash
python q_pairs.py     # -> q_pairs.json  (reads data.json + prices_all.json)
python bt_export.py   # -> bt_results.json (reads data.json + prices_all.json)
python build_dpx3.py  # -> daily_px.json  (after the S&P pulls in 7c)
```

### 7c. Daily prices → `daily_px.json` (S&P Global + the splice)
Source: the **S&P Global** MCP connector (`get_prices_from_identifiers`, `periodicity="day"`, `adjusted=true`). The connector must be configured in the Claude Code environment. Resolve each Bloomberg ticker with the **resolution map** below — several names mis-resolve on plain tickers.

**Adjusted-price basis caveat (the reason for the splice):** S&P adjusted closes are *back-adjusted to the fetch's end date*, so two fetches with different end dates sit on different bases and cannot be naively concatenated (names that paid dividends/split show a seam). The splice in `build_dpx3.py` handles this:
1. The previously-stored full-history S&P pulls define the **reference basis** (the `base` dict).
2. To add new days **or** extend history, fetch the new segment **with overlap** into the existing series (e.g. recent: `2026-01-01 → <new asof>`; early-history extension: `<earlier start> → 2021-08-31`). Both windows are large enough that the connector stores them to files under `/mnt/user-data/tool_results/…json`; **process those files with Python, never paste them into context.**
3. Per name, compute a **constant scale factor** `F = median(base[d] / new[d])` over the overlap dates; **verify F is stable** (max deviation < 1% ⇒ no split artifact — flag anything larger). Multiply the new segment by `F` to put it on the reference basis.
4. Reassemble each name's date→price map (base ∪ scaled-early ∪ scaled-recent), **realign to `data.json.dates`**, forward-fill exchange holidays, leave leading `null` before the listing date, round to 2 dp.
5. Verify seam continuity (day-over-day steps at the join should be ordinary moves, ≤ a couple %), correct listing dates, and that `len(px[t]) == len(dates)` for all 85.

**Ticker → S&P identifier resolution map** (verified):
- **US (66):** pass the **plain ticker** (`RJF`, `CME`, `SCHW`, `SPGI`, …).
- **US needing exchange qualification (4):** `MA US→NYSE:MA`, `V US→NYSE:V` (plain "Visa" mis-resolves to TSX), `BAM US→NYSE:BAM`, `MC US→NYSE:MC` (Moelis; plain "MC" can hit LVMH).
- **Foreign (15):** `LSEG LN→LSE:LSEG`, `DB1 GY→XTRA:DB1`, `ENX FP→ENXTPA:ENX`, `EXPN LN→LSE:EXPN`, `WISE LN→LSE:WISE`, `ADYEN NA→ENXTAM:ADYEN`, `PGHN SW→SWX:PGHN`, `EQT SS→OM:EQT`, `CVC NA→ENXTAM:CVC`, `DWS GY→XTRA:DWS`, `AMUN FP→ENXTPA:AMUN`, `ICG LN→LSE:ICG` (**not** `ICP` — that mis-resolves to a Kazakhstan listing), `FTK GY→XTRA:FTK`, `BGN IM→BIT:BGN`, `FBK IM→BIT:FBK`.
- **Always verify** the returned `company_name` and exchange in the `ticker` field after a pull, especially for foreign names and recent IPOs.

### 7d. Monthly prices → `btdata.json` / `prices_all.json` (only when extending the backtest)
The monthly panel is **hard-coded** and starts **2022-06**, which is why backtest *returns* start there even though the P/E baseline now reaches 2020. The daily refresh does **not** touch it. To extend the backtest's return window earlier, pull **monthly** adjusted closes (same resolution map) back to the new start, rebuild `prices_all.json`/`btdata.json`, regenerate `bt_results.json`, and re-run the gate.

### 7e. Rebuild + validate
`python build.py` → §4 gate (`node --check` + `node bt_verify.js` = 39/39) → confirm `asof`, span, 0 weekend rows, the latest day present, and that `DPX` spans the full date range. Only then is the file shippable.

---

## 8. Coverage universe — 7 sub-sectors, 85 tickers

```
Exchanges (11):        CME US · ICE US · NDAQ US · CBOE US · LSEG LN · DB1 GY · ENX FP · TW US · MKTX US · MIAX US · MRX US
Info Services (9):     SPGI US · MCO US · MSCI US · FDS US · EFX US · TRU US · EXPN LN · FICO US · VRSK US
Payments & Fintech(22):V US · MA US · PYPL US · XYZ US · ADYEN NA · TOST US · SHOP US · SOFI US · FISV US · FIS US ·
                       GPN US · JKHY US · CPAY US · WEX US · AFRM US · KLAR US · BILL US · CHYM US · MQ US · FOUR US · WISE LN · WU US
M&A Boutiques (7):     LAZ US · EVR US · MC US · HLI US · PWP US · PJT US · PIPR US
Alternatives (14):     PGHN SW · EQT SS · CVC NA · ICG LN · ARES US · APO US · BX US · KKR US · OWL US · CG US · BAM US · TPG US · STEP US · HLNE US
Traditional AM (8):    BLK US · TROW US · DWS GY · AMUN FP · AB US · BEN US · IVZ US · AMP US
Wealth & Brokers (14): SCHW US · LPLA US · HOOD US · IBKR US · COIN US · RJF US · SF US · BGN IM · FBK IM · FTK GY · CRCL US · FIGR US · ETOR US · WLTH US
```
Excluded from the P/E panel: `RELY LN`, `SQ SW`.

**Curated CLUSTERS** (26 hand-picked intra-sub-sector, model-/geography-matched peer groups) live as a `const CLUSTERS = [ … ]` array in `template.html` and define the tradeable pairs. **Changing coverage = edit that array and regenerate `q_pairs.json`** (and re-run the gate, since `bt_verify` extracts `CLUSTERS`).

---

## 9. Hard constraints / invariants (preserve in any refactor)

1. **Sourced data only** — never synthetic/interpolated/placeholder (§7 hard rule).
2. **Weekend exclusion** — every series is weekday-only; the Bloomberg workbook's weekend rows are spurious calendar-day artifacts, and **today's row is forward-filled** (cap at the latest real trading day).
3. **Single adjustment basis** for the daily price panel — extend via the scale-factor splice (§7c), never naive concat.
4. **Sub-sector aggregates are equal-weighted** (not cap-weighted) and **self-exclude** — a name is never compared against an average/median that includes itself.
5. **Color convention:** green = cheap / positive / trade won; red = rich / negative / trade lost. The generic `.pos`/`.neg` CSS classes are **intentionally inverted** (red for premium/rich) — reuse the existing inline colors, don't guess.
6. **Backtest math:** expanding-window z-score, **minimum 18-month** baseline; single-name signal = −z of own forward P/E; pair signal = −z of `ln(P/E_a / P/E_b)`; **population** standard deviation (to match the Python reference); returns from **monthly adjusted close in local currency**, cross-currency legs **FX-hedged**; pair LS return = `r_A − r_B`.
7. **The gate (§4) must pass 39/39 after every rebuild.**

---

## 10. Known gotchas

- **Ticker mis-resolution** on the S&P pull — use the §7c map; verify `company_name`/exchange; recent IPOs (CRCL, ETOR, FIGR, WLTH, MIAX, KLAR, CHYM, MQ, MRX, BAM, CVC, TPG, COIN, HOOD, TOST, SOFI, AFRM, BILL) only have data from listing.
- **Adjusted-price seams** — if a name shows a >1% scale-factor deviation across the overlap, there was a split in that window; handle that name specially (re-fetch its full history) rather than splicing.
- **Token substring order** — `__DATA__` ⊂ `__QDATA__`/`__BTDATA__`; replace the long ones first (§3).
- **`bt_verify` is self-consistent** — regenerate `bt_results.json` (`bt_export.py`) whenever the backtest inputs change, or the gate will "fail" only because the reference is stale.
- **Big S&P daily pulls** land in `/mnt/user-data/tool_results/*.json` — parse with Python; don't read them into context.
- **The backtest baseline window vs the chart window** — see §12.

---

## 11. Data licensing & hosting

The HTML **embeds licensed Bloomberg-sourced forward P/E and S&P-Global-derived adjusted prices**. **GitHub Pages always serves a publicly viewable site** — even from a private repo, anyone with the URL can read the page source and the embedded data, which likely breaches those licences.
- **Do not use a public repo / public Pages site.**
- Pages from a **private** repo needs a **paid plan**, and the *site is still public* — pair it with access control.
- For a genuinely private site: host on **Cloudflare Pages / Netlify / Vercel** behind **Cloudflare Access / Netlify Identity / a Vercel password** (these also allow a private source repo on free tiers).
- Operational limits: site ≤ ~1 GB, soft ~100 GB/mo bandwidth, ~10 builds/hr; Pages' terms forbid primarily-commercial/SaaS use. Treat this as an **internal, access-controlled tool**, not a public product.

If you wire CI: on push to `main`, set up Python 3 + Node, run `python build.py`, run the §4 gate (fail the job if either check fails), then deploy. Don't deploy a build that didn't pass the gate.

---

## 12. Current state & open decisions (handoff snapshot)

- **`asof` = 2026-06-18**; `dates` span **2020-06-19 → 2026-06-18** (~1,565 weekday rows); 85 tickers; daily price panel `daily_px.json` covers the full range on one basis.
- The P/E history was recently **extended back ~1 year to mid-2020**. Because the backtest baseline is an expanding z over **all** P/E months, the longer history **lengthened the baseline and let entries start ~2022 instead of 2023**, which moved the headline numbers (e.g. 6-month buy-the-discount reversion ≈ +2.98% → +4.54%; portfolio Sharpe ≈ 0.71 → 1.02) and shifted ~41/95 consistency decisions. This is the correct consequence of more data, and the gate still passes (engine and reference move together).
- **Open decision:** whether to **freeze the expanding-z baseline at the original 2021-06 start** (to preserve the prior validated figures) while still showing the longer chart history, vs. let it float to 2020 (current behavior). If freezing is wanted, constrain `PEMONTHS` to `>= '2021-06'` in `backtest.py`/`bt_export.py` (and optionally `q_pairs.py`), regenerate `bt_results.json`, and re-run the gate.
- A few names carry small **sourced P/E revisions** in the latest workbook (ENX FP, AMP US, PYPL US, TROW US, JKHY US) — taken as truth.

---

## 13. Definition of done (any change)
1. `python build.py` regenerates `Relative_PE_Dashboard.html` from `template.html` + the 4 JSON files with no leftover tokens.
2. `node --check` on the built script passes.
3. `node bt_verify.js` prints **`✅ ALL CHECKS PASSED (39 passed)`**.
4. Header `asof`, date span, and **0 weekend rows** are as expected; `DPX` spans the full `dates` range.
5. No public hosting over the licensed data (§11).
