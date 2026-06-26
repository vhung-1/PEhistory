# CLAUDE.md — Relative-Value Forward-P/E Dashboard (operating manual)

> **How to use this file.** Drop it in the repo root as `CLAUDE.md` (Claude Code reads it automatically) and keep the source files described in §2 alongside it. This is a complete operating manual: it assumes **no prior conversation context**. Read §1 (what this is), §3 (build), §4 (the gate), and §7 (refresh) before changing anything.

> ⚠️ **Licensing first (see §11).** The dashboard **embeds licensed Bloomberg NTM forward-P/E and S&P-Global-derived adjusted prices** directly in the HTML. Anyone who can open the file can read the data. **Do not publish to a public site.** Private repo + access control only.

---

## 1. What this is

A **single, self-contained interactive HTML dashboard** for a long/short **diversified-financials** equity investor. It does relative **NTM forward-P/E** valuation across **87 names in 7 sub-sectors**, plus validated **mean-reversion pair backtests**, **per-pair quarterly consistency** analysis, single-name P/E history, a sub-sector small-multiples grid, a **click-to-measure share-price-return tool** on the pair chart, and a **Software reference tab for JKHY**.

**Technical shape**
- **No runtime dependencies, no framework, no build step needed to *view*.** Plain HTML + one inline `<script>` of vanilla JS + inline SVG + one `<canvas>`. Opens by double-click. Current size ≈ **2.1 MB**.
- **All data is embedded** as JavaScript constants near the top of the script (see §5).
- **Eleven tabs** (§6): Pairs · Name P/E · **Software** · Flags · Summary · Screen · Matrix · Grid · Coverage · Consistency · Backtest.
- CSS is one `<style>` block themed entirely with custom properties (`--ink`, `--ink2`, `--muted`, `--faint`, `--line`, `--line2`, `--bg`, `--panel`, `--panel2`, `--accent`, `--series` `#15697A`, `--avg` `#E2733A`, `--cheap` `#2E7D52`, `--rich` `#C0392B`, `--mono`, `--sans`).

**The product is the file `Relative_PE_Dashboard.html`.** Everything else exists to regenerate it reproducibly.

---

## 2. Repo layout — canonical files vs scratch

**Canonical (needed to rebuild and maintain):**

| File | Role |
|---|---|
| `template.html` | **Source of truth.** The full dashboard with the embedded data replaced by 5 tokens: `__QDATA__`, `__BTDATA__`, `__DATA__`, `__DPX__`, `__SWDATA__`. All tab code (incl. the former `con.js`/`grid.js`/`namepe.js` modules, the Software tab, and the portable backtest core) is already merged in here. |
| `build.py` | The 5-token build → `Relative_PE_Dashboard.html`. |
| `mkdata.py` | Builds `data.json` (the P/E panel) from the uploaded Bloomberg coverage workbook. |
| `mksw.py` | Builds `sw_data.json` (the Software reference panel) from the Bloomberg software workbook. Run **after** `mkdata.py` (aligns to its dates). |
| `q_pairs.py` | Builds `q_pairs.json` (Consistency tab records) from `data.json` + `prices_all.json`. |
| `backtest.py` | The Python backtest engine (reference implementation). |
| `bt_export.py` | Runs `backtest.py`'s setup and dumps `bt_results.json` (the numeric reference for the gate). |
| `bt_verify.js` | **The validation gate.** Re-derives the backtest from the *built HTML* and asserts 39 numeric checks against `bt_results.json`. |
| `build_dpx3.py` | Builds `daily_px.json` (the daily price panel) from S&P price pulls via the splice procedure (§7c). |
| `prices.py` + `prices_all.json` | **Monthly** adjusted-close panel for the backtest/consistency (hard-coded values, *not* a live resolver). |
| Data outputs: `data.json`, `q_pairs.json`, `btdata.json`, `prices_all.json`, `bt_results.json`, `daily_px.json`, `sw_data.json` | The embedded/reference data (see §5). |

**Scratch / superseded — safe to ignore or delete:** `app*.js`, `nt*.js`, `nodetest.js`, `bt_inject.js`, `bt_render.js`, `bt_core.js` (standalone copy of the core now living in `template.html`), `cov.js`, `ingest.py`, `resolve_daily.py`, `recalc.py`, `trapcost_proto.py`, `quarterly_backtest.py`, `q_results.json`, `perpair.json`, `PX_auto.json`, `bt_ready.json`, `built_script.js`, `sw_block.js`, `build_dpx.py`, `build_dpx2.py`. (`con.js`, `grid.js`, `namepe.js` are also historical — their code is already in `template.html`.)

A first good task in Claude Code: move the scratch files into an `_archive/` folder so the working tree shows only the canonical set.

---

## 3. Build pipeline (token replacement)

The build replaces the 5 tokens in `template.html` with their JSON payloads. **Order matters:** `__DATA__` is a substring of `__QDATA__` and `__BTDATA__`, so those must be replaced first. `__DPX__` and `__SWDATA__` are independent (neither contains, nor is contained by, `__DATA__`). Replace each exactly once and assert none remain.

The relevant declarations in `template.html`:
```js
const DATA = __DATA__;
const BT   = __BTDATA__;
const QD   = __QDATA__;
const DPXMETA = __DPX__;
const DPX  = DPXMETA.px;   // daily price map keyed by ticker
const SW   = __SWDATA__;   // software reference panel {asof, names, pe}
```

`build.py`:
```python
import pathlib
tpl = pathlib.Path("template.html").read_text(encoding="utf-8")
out = tpl
ORDER = [("__QDATA__","q_pairs.json"), ("__BTDATA__","btdata.json"),
         ("__DATA__","data.json"), ("__DPX__","daily_px.json"), ("__SWDATA__","sw_data.json")]
for tok, f in ORDER:
    assert tpl.count(tok) == 1, f"{tok} count != 1"
    out = out.replace(tok, pathlib.Path(f).read_text(encoding="utf-8").strip(), 1)
assert not any(t in out for t,_ in ORDER), "token left"
pathlib.Path("Relative_PE_Dashboard.html").write_text(out, encoding="utf-8")
print(f"built Relative_PE_Dashboard.html ({len(out)/1e6:.2f} MB)")
```

---

## 4. Validation gate — **non-negotiable, run after every rebuild**

Two checks. Both must pass before the file is considered good or deployed. (The Software tab is isolated — it does not affect the gate — but always run the gate anyway.)

**(a) JS syntax.** Extract the largest `<script>` from the built HTML and `node --check` it:
```bash
python3 -c "import re;h=open('Relative_PE_Dashboard.html',encoding='utf-8').read();open('/tmp/app.js','w',encoding='utf-8').write(max(re.findall(r'<script>([\s\S]*?)</script>',h),key=len))"
node --check /tmp/app.js   # must exit 0
```

**(b) Backtest gate.** `node bt_verify.js` must print **`✅ ALL CHECKS PASSED (39 passed)`** (0 failed).

How `bt_verify.js` works (so you don't break it): it reads the built HTML, pulls the largest `<script>`, extracts the **portable backtest core** between the marker `function bmean(` and the comment `END PORTABLE CORE`, extracts the `CLUSTERS` array by bracket-balancing, parses `data.json` + `btdata.json`, runs `btPrep()`/`meanIC()`, and compares ~39 outputs (pair IC at 1/3/6/12m, single-name IC, the 6-month buy-the-discount conditional mean/N/hit, portfolio Sharpe/mean/vol/N, pair count, trend-filter splits) against `bt_results.json` with tolerances. It is a **self-consistency check**: the HTML engine must reproduce the Python reference. So if you change the backtest data, **regenerate `bt_results.json` with `python bt_export.py` before running the gate** — otherwise engine and reference diverge and it "fails" spuriously.

If you edit the core's math, keep the `function bmean(` start marker and the `END PORTABLE CORE` end comment intact, and keep the core **DOM-free** (the verifier rejects it if it references `document.`/`getElementById`).

---

## 5. Data model (the embedded constants and their files)

**`data.json` → `const DATA`** — the valuation panel.
- `asof`: ISO date in the header.
- `dates`: array of **weekday-only** ISO dates (currently `2020-06-22` → `2026-06-18`, 1,564 rows). **No weekend rows** (see §9).
- `pe`: `{ "<TICKER>": [number|null, …] }` — daily **NTM forward P/E**, aligned to `dates`. Tickers are Bloomberg-style: `"CME US"`, `"LSEG LN"`, `"DB1 GY"`, `"EQT SS"`, …
- `sectors`: `{ "<Sub-sector>": ["<TICKER>", …] }` (the 7 sub-sectors, §8).
- `sector_of`: reverse map. `excluded`: coverage tickers with no data in the workbook (currently none).

**`btdata.json` → `const BT`** — **monthly** price panel for the Backtest tab.
- `XMONTHS`: ~49 month-end ISO dates (currently `2022-06` … `2026-06`). `PX`: `{ "<name>": [monthly adjusted close|null] }`. Byte-identical content to `prices_all.json`. **Not** changed by the daily refresh. **The backtest return window starts 2022-06 because this panel does** (§7d).

**`q_pairs.json` → `const QD`** — precomputed per-pair quarterly records (95). Each: `a`,`b`,`sec`,`nq`; headline `hit`,`avgq`,`cum`,`ic`,`devnow`; `q`: `[{p,dm,dev,long,ret,win}]` per quarter; `ser`: the monthly premium/discount series `{t:"YYYY-MM", d:%-vs-expanding-avg}`.

**`daily_px.json` → `const DPXMETA`, then `const DPX = DPXMETA.px`** — **daily** price panel for the click-to-measure tool.
- `{ asof, note, px:{ "<TICKER>": [number|null, …] } }`, `px` aligned to `DATA.dates`.
- **S&P-Global daily ADJUSTED close (total return), local currency, single back-adjustment basis** (§7c), holiday-forward-filled, `null` before each listing/IPO date.

**`sw_data.json` → `const SW`** — the **Software reference panel** (for the JKHY tab only).
- `{ asof, names:["MSFT US",…], pe:{ "<TICKER>": [number|null, …] } }`, `pe` aligned to `DATA.dates`.
- Daily NTM forward P/E for 8 software names (MSFT, ORCL, CRM, NOW, WDAY, ADBE, INTU, ADSK). **JKHY is deliberately NOT here** — the tab draws JKHY from `DATA.pe['JKHY US']` so it stays consistent with the rest of the dashboard. **These names are reference-only and are NOT in `DATA` / the 87-name universe**, so they never appear in Pairs/Screen/Matrix/Grid/Consistency/Backtest.

**Tab → source:** Pairs/Name P/E/Flags/Summary/Screen/Matrix/Grid/Coverage derive from `DATA.pe`; the Pairs click-to-measure tool reads `DPX`; Consistency reads `QD`; Backtest reads `BT`; the **Software tab reads `SW` (+ `DATA.pe['JKHY US']`)**.

---

## 6. The tabs (brief)

- **Pairs** — relative forward P/E of leg A ÷ leg B over time, with premium/discount stats, a window gauge, and ±-range. Either leg can be a single ticker **or** a sub-sector aggregate (sentinels `~avg~<sector>` / `~med~<sector>`); a sector-aggregate leg **excludes the other leg's ticker** from its own average/median. **Click-to-measure:** when leg A is a single ticker, click two dates on the chart to read **A's share-price total return** between them. Disabled with a hint when A is an aggregate.
- **Name P/E** — single-name forward P/E vs its own history: ±1σ band, full-history mean, percentile, z-score, hover crosshair.
- **Software** *(reference for JKHY)* — two pair-style selectors, **Focus** and **Compare to**, each drawn from a unified list: JKHY, **Software average**, **Software median**, and the 8 individual software names. The chart plots the two chosen series (focus teal, comparator orange) with the other software names as a faint backdrop; headline cards show each level, the focus-vs-comparator gap (red=richer/green=cheaper), and the focus's 5Y percentile; a reference table lists everyone with their own 5Y percentile. **Reference only** — `SW` is separate from the 87-name universe; nothing here feeds pairs/screens/the backtest. Default A=JKHY, B=Software median; state in `ST.swA`/`ST.swB`/`ST.swM`.
- **Flags / Summary / Screen / Matrix / Coverage** — cross-sectional cheap/rich views from `DATA.pe`.
- **Grid** — sub-sector small-multiple sparklines; each name vs its peer median/average (ex-self), or curated intra-sub-sector pairs; cross-sector "Compare to" hero card.
- **Consistency** — each curated pair scored as a quarterly side-switching mean-reversion trade; expandable annotated premium/discount chart.
- **Backtest** — IC by horizon, return-by-z bars, trend filter, net-of-cost P&L.

---

## 7. DATA REFRESH PROCEDURE

> **Hard rule: never fabricate, synthesise, interpolate, or placeholder a data point. Sourced primary data only. If a series is unavailable, drop the name — do not invent values.**

A full refresh updates the **P/E panel** (Bloomberg coverage workbook), the **daily price panel** (S&P Global), and — when a fresh software workbook is supplied — the **Software reference panel**.

### 7a. Forward P/E → `data.json`
1. The investor uploads a refreshed `Coverage_PE_multiples.xlsx` (sheet `HC`; ticker row at index 2; data from row index 5). It is **calendar-daily**, and **today's row, weekends, and US market holidays are forward-filled artifacts** — *not* clean closes.
2. In `mkdata.py` set `ASOF` to **the latest *settled* close** = the most recent completed US trading day that is **not today** (today's pull is intraday/forward-filled) and **not a market holiday**. The script caps at `ASOF` and applies a **weekday filter** (`dayofweek < 5`). Note holidays still appear as weekday rows in the workbook (forward-filled); the `ASOF` cap is what excludes them when they fall after the last real close. (Example seen in practice: a Friday Juneteenth + weekend + an intraday Monday pull ⇒ the latest settled close was the prior Thursday, so `ASOF` did **not** advance.)
3. Run `python mkdata.py` → `data.json` (2-dp rounding). The universe is **SECTORS-driven**: any coverage ticker absent from the workbook (or all-null) is auto-`excluded`, and workbook columns outside the SECTORS lists are ignored — so vendor re-tickering can't silently change coverage.
4. Sanity-check span/row-count, **0 weekend rows**, and that historical overlap vs the prior `data.json` is stable (mean |Δ| ≈ 0.003x). New sourced P/E **revisions** on historical dates are normal (the vendor restates NTM EPS — e.g. ENX FP, ICG LN, AMP US have all been restated across many dates) — take the new file as truth.

### 7b. Regenerate the dependent references
```bash
python q_pairs.py      # -> q_pairs.json    (reads data.json + prices_all.json)
python bt_export.py    # -> bt_results.json (reads data.json + prices_all.json)
python mksw.py         # -> sw_data.json    (reads bbg_software_mults.xlsx + data.json; §7f)
python build_dpx3.py   # -> daily_px.json   (after the S&P pulls in §7c)
```

### 7c. Daily prices → `daily_px.json` (S&P Global + the splice)
Source: the **S&P Global** connector (`get_prices_from_identifiers`, `periodicity="day"`, `adjusted=true`). Resolve each Bloomberg ticker with the **resolution map** below.

**Adjusted-price basis caveat (why the splice exists):** S&P adjusted closes are *back-adjusted to the fetch's end date*, so two fetches with different end dates sit on different bases and cannot be naively concatenated. `build_dpx3.py`:
1. The previously-stored full-history S&P pulls define the **reference basis** (the `base` dict).
2. To add new days **or** extend history, fetch the new segment **with overlap** into the existing series (recent: `2026-01-01 → <new asof>`; history extension: `<earlier start> → 2021-08-31`). Both windows are large enough that the connector stores them to files under `SP_PULLS_DIR` (default `tool_results/`); **process those files with Python, never paste them into context.**
3. Per name, compute a **constant scale factor** `F = median(base[d] / new[d])` over the overlap; **verify F is stable** (max deviation < 1% ⇒ no split artifact — flag anything larger). Multiply the new segment by `F` onto the reference basis.
4. Reassemble each name's date→price map, **realign to `data.json.dates`**, forward-fill exchange holidays, leave leading `null` before the listing date, round to 2 dp.
5. Verify seam continuity (joins are ordinary day-over-day moves), correct listing dates, and `len(px[t]) == len(dates)` for all 87.
6. **If nothing advances past the current asof** (e.g. a revisions-only refresh, or a holiday/intraday day excluded), no new pull is needed — just re-run `build_dpx3.py` to realign to the new date axis (the existing pulls already cover through the asof).

**Ticker → S&P identifier resolution map** (verified):
- **US (66):** plain ticker (`RJF`, `CME`, `SCHW`, …).
- **US needing exchange qualification (4):** `MA US→NYSE:MA`, `V US→NYSE:V` (plain "Visa" mis-resolves to TSX), `BAM US→NYSE:BAM`, `MC US→NYSE:MC` (Moelis; plain "MC" can hit LVMH).
- **Foreign (15):** `LSEG LN→LSE:LSEG`, `DB1 GY→XTRA:DB1`, `ENX FP→ENXTPA:ENX`, `EXPN LN→LSE:EXPN`, `WISE LN→LSE:WISE`, `ADYEN NA→ENXTAM:ADYEN`, `PGHN SW→SWX:PGHN`, `EQT SS→OM:EQT`, `CVC NA→ENXTAM:CVC`, `DWS GY→XTRA:DWS`, `AMUN FP→ENXTPA:AMUN`, `ICG LN→LSE:ICG` (**not** `ICP` — mis-resolves to a Kazakhstan listing), `FTK GY→XTRA:FTK`, `BGN IM→BIT:BGN`, `FBK IM→BIT:FBK`.
- **Always verify** the returned `company_name`/exchange after a pull, especially foreign names and recent IPOs.

### 7d. Monthly prices → `btdata.json` / `prices_all.json` (only when extending the backtest)
Hard-coded, starts **2022-06**, which is why backtest *returns* start there even though the P/E baseline reaches 2020. The daily refresh does **not** touch it. To extend the backtest's return window earlier, pull **monthly** adjusted closes (same resolution map) back to the new start, rebuild `prices_all.json`/`btdata.json`, regenerate `bt_results.json`, re-run the gate.

### 7e. Rebuild + validate
`python build.py` → §4 gate → confirm `asof`, span, 0 weekend rows, the latest day present, `DPX` and `SW` span the full date range. Only then ship.

### 7f. Software reference → `sw_data.json`
Only when a fresh `bbg_software_mults.xlsx` is supplied (same HC layout; sheet may be `hC`). `python mksw.py` excludes JKHY, aligns the 8 software names to `data.json.dates`, and writes `sw_data.json`. **The software workbook is on its own pull cadence** — if it wasn't refreshed this round, just re-run `mksw.py` to realign to the new dates (its latest values carry forward; the tab is reference-only). It uses Bloomberg forward P/E, so it **cannot** be refreshed from the S&P connector — it needs a new workbook upload.

---

## 8. Coverage universe — 7 sub-sectors, 87 tickers

```
Exchanges (11):        CME US · ICE US · NDAQ US · CBOE US · LSEG LN · DB1 GY · ENX FP · TW US · MKTX US · MIAX US · MRX US
Info Services (9):     SPGI US · MCO US · MSCI US · FDS US · EFX US · TRU US · EXPN LN · FICO US · VRSK US
Payments & Fintech(23):V US · MA US · PYPL US · XYZ US · ADYEN NA · TOST US · SHOP US · SOFI US · FISV US · FIS US ·
                       GPN US · JKHY US · CPAY US · WEX US · AFRM US · KLAR US · BILL US · CHYM US · MQ US · FOUR US · WISE LN · RELY US · WU US
M&A Boutiques (7):     LAZ US · EVR US · MC US · HLI US · PWP US · PJT US · PIPR US
Alternatives (14):     PGHN SW · EQT SS · CVC NA · ICG LN · ARES US · APO US · BX US · KKR US · OWL US · CG US · BAM US · TPG US · STEP US · HLNE US
Traditional AM (8):    BLK US · TROW US · DWS GY · AMUN FP · AB US · BEN US · IVZ US · AMP US
Wealth & Brokers (15): SCHW US · LPLA US · HOOD US · IBKR US · COIN US · RJF US · SF US · BGN IM · FBK IM · FTK GY · CRCL US · FIGR US · ETOR US · WLTH US · SQN SW
```
Excluded from the P/E panel: none. (The vendor re-tickered `RELY LN`→`RELY US` (Remitly) and `SQ SW`→`SQN SW` (Swissquote); both were added to the universe on 2026-06-25, taking it from 85 to 87.)
**Software reference names (NOT in the universe):** MSFT, ORCL, CRM, NOW, WDAY, ADBE, INTU, ADSK — plus JKHY (already above) as the comparison subject.

**Curated CLUSTERS** (26 hand-picked intra-sub-sector peer groups) live as a `const CLUSTERS = [ … ]` array in `template.html` and define the tradeable pairs. **Changing coverage = edit that array and regenerate `q_pairs.json`** (and re-run the gate, since `bt_verify` extracts `CLUSTERS`).

---

## 9. Hard constraints / invariants (preserve in any refactor)

1. **Sourced data only** — never synthetic/interpolated/placeholder (§7 hard rule).
2. **Weekday-only + settled closes** — exclude weekends, **US market holidays**, and **today's intraday row**; `ASOF` = the latest settled close.
3. **Single adjustment basis** for the daily price panel — extend via the scale-factor splice (§7c), never naive concat.
4. **Sub-sector aggregates are equal-weighted** and **self-exclude**.
5. **Color convention:** green = cheap / positive / won; red = rich / negative / lost. The generic `.pos`/`.neg` CSS classes are **intentionally inverted** (red for premium/rich) — reuse existing inline colors.
6. **Backtest math:** expanding-window z-score, **min 18-month** baseline; single-name signal = −z of own forward P/E; pair signal = −z of `ln(P/E_a / P/E_b)`; **population** standard deviation; monthly adjusted close, local currency, cross-currency legs FX-hedged; pair LS return = `r_A − r_B`.
7. **Software is reference-only and isolated** — `SW` must never be merged into `DATA`/the 87-name universe or the CLUSTERS; the Software tab must not feed pairs/screens/backtest.
8. **The gate (§4) must pass 39/39 after every rebuild.**

---

## 10. Known gotchas

- **Ticker mis-resolution** on the S&P pull — use the §7c map; verify `company_name`/exchange; recent IPOs (CRCL, ETOR, FIGR, WLTH, MIAX, KLAR, CHYM, MQ, MRX, BAM, CVC, TPG, COIN, HOOD, TOST, SOFI, AFRM, BILL) only have data from listing.
- **US market holidays** look like ordinary weekday rows in the Bloomberg workbook (forward-filled) — they are **not** settled closes. Juneteenth, Thanksgiving, July 4th, etc. must be excluded from `ASOF` just like today's intraday row.
- **Adjusted-price seams** — a >1% scale-factor deviation across the overlap means a split in that window; re-fetch that name's full history rather than splicing.
- **Token substring order** — `__DATA__` ⊂ `__QDATA__`/`__BTDATA__`; replace the long ones first (§3).
- **`bt_verify` is self-consistent** — regenerate `bt_results.json` (`bt_export.py`) whenever backtest inputs change, or the gate "fails" only because the reference is stale.
- **Big S&P pulls** land under `SP_PULLS_DIR` — parse with Python; don't read them into context.
- **The software workbook sheet** is `hC` (case differs from the coverage `HC`); `mksw.py` matches case-insensitively.

---

## 11. Data licensing & hosting

> **Status for this deployment:** the data owner has **confirmed distribution rights** for the embedded data, so the dashboard **is published publicly** — public repo + **GitHub Pages** at <https://vhung-1.github.io/PEhistory/>, built and gated by `.github/workflows/pages.yml` (the §4 gate must pass before any deploy). The guidance below is the **default for when distribution is _not_ authorized**.

The HTML **embeds Bloomberg-sourced forward P/E and S&P-Global-derived adjusted prices** (coverage + software). **GitHub Pages always serves a publicly viewable site** — anyone with the URL can read the page source and the embedded data. **Only publish publicly with the data owner's distribution permission** (granted for this deployment).
- Without that permission: **do not use a public repo / public Pages site.**
- Private-repo Pages needs a **paid plan**, and the *site is still public* — pair it with access control.
- For a genuinely private site: host on **Cloudflare Pages / Netlify / Vercel** behind **Cloudflare Access / Netlify Identity / a Vercel password** (these also allow a private source repo on free tiers).
- Operational limits: site ≤ ~1 GB, soft ~100 GB/mo bandwidth, ~10 builds/hr; Pages' terms forbid primarily-commercial/SaaS use.

**CI (live):** `.github/workflows/pages.yml` runs on push to `main` — sets up Python 3 + Node, runs `python build.py`, runs the §4 gate (JS syntax + `bt_verify.js` 39/39; the job fails if either fails), then deploys to Pages. A build that didn't pass the gate never deploys. Pages **Source** must be set to **GitHub Actions** (repo Settings → Pages).

---

## 12. Current state & open decisions (handoff snapshot)

- **`asof` = 2026-06-25**; `dates` span **2020-06-26 → 2026-06-25** (1,565 weekday rows); **87 tickers** (RELY US + SQN SW added 2026-06-25 after the vendor re-tickered RELY LN/SQ SW). `daily_px.json` and `sw_data.json` both span the same range.
- Most recent refresh was **revisions-only**: the coverage workbook restated ENX FP (~124 dates) and ICG LN (~81 dates) NTM forward P/E history, and the 6-year window rolled its start from 2020-06-19 to 2020-06-22. `asof` did **not** advance because Fri 19 Jun was **Juneteenth** (US markets closed), 20–21 was the weekend, and Mon 22 Jun was pulled intraday — so the latest settled close stayed Thu 18 Jun. No S&P pull was needed; all panels were realigned to the new date axis.
- The P/E history was earlier **extended back to mid-2020**, which lengthened the expanding-z baseline and let backtest entries start ~2022 instead of 2023 — moving headline numbers (6-month buy-the-discount reversion ≈ +4.54%; portfolio Sharpe ≈ 1.02). The gate passes because engine and reference move together.
- **Open decision:** whether to **freeze the expanding-z baseline at 2021-06** (to recover the pre-extension figures: 6m ≈ +2.98%, Sharpe ≈ 0.71) while still showing the longer chart history, vs. let it float to 2020 (current). To freeze: constrain `PEMONTHS` to `>= '2021-06'` in `backtest.py`/`bt_export.py` (and optionally `q_pairs.py`), regenerate `bt_results.json`, re-run the gate.
- The **Software tab** was added as a JKHY reference (separate `SW` constant + `__SWDATA__` token + `mksw.py`); it is fully isolated from the relative-value machinery.

---

## 13. Definition of done (any change)
1. `python build.py` regenerates `Relative_PE_Dashboard.html` from `template.html` + the **5** JSON files with no leftover tokens.
2. `node --check` on the built script passes.
3. `node bt_verify.js` prints **`✅ ALL CHECKS PASSED (39 passed)`**.
4. Header `asof`, date span, and **0 weekend rows** are as expected; `DPX` and `SW` span the full `dates` range.
5. No public hosting over the licensed data (§11).
