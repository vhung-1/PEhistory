#!/usr/bin/env python3
# Generate api.json — a discovery manifest for the static data API served on
# GitHub Pages. Reads data.json and writes api.json to the given dir (default cwd).
# Run in the Pages workflow after the data files are present: `python mkapi.py _site`.
import json, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
d = json.load(open('data.json'))

manifest = {
    "name": "Relative-Value Forward-P/E data API",
    "description": ("Static JSON endpoints for the diversified-financials NTM "
                    "forward-P/E dashboard. Array fields align index-for-index "
                    "to `dates` unless noted. Tickers are Bloomberg-style "
                    "(e.g. 'CME US', 'LSEG LN')."),
    "asof": d["asof"],
    "base_url": "https://vhung-1.github.io/PEhistory/",
    "dates": {"first": d["dates"][0], "last": d["dates"][-1], "count": len(d["dates"])},
    "universe": {
        "count": len(d["pe"]),
        "tickers": sorted(d["pe"].keys()),
        "sectors": d["sectors"],
        "excluded": d.get("excluded", []),
    },
    "endpoints": [
        {"path": "data.json",
         "shape": "{asof, dates[], pe{TICKER:[float|null,...]}, sectors{SECTOR:[TICKER,...]}, sector_of{TICKER:SECTOR}, excluded[]}",
         "desc": "NTM forward P/E panel. pe[TICKER][i] is the P/E on dates[i]."},
        {"path": "daily_px.json",
         "shape": "{asof, note, px{TICKER:[float|null,...]}}",
         "desc": "Daily adjusted close (total return, local currency, single basis), aligned to data.json dates; null before each listing date."},
        {"path": "sw_data.json",
         "shape": "{asof, names[], pe{TICKER:[float|null,...]}}",
         "desc": "Software reference panel (JKHY tab), aligned to data.json dates. Reference-only; NOT in the coverage universe."},
        {"path": "q_pairs.json",
         "shape": "[{a, b, sec, nq, hit, avgq, cum, ic, devnow, q[], ser[]}, ...]",
         "desc": "Per-pair quarterly mean-reversion consistency records."},
        {"path": "btdata.json",
         "shape": "{XMONTHS[], PX{NAME:[float|null,...]}}",
         "desc": "Monthly adjusted-close panel for the backtest, aligned to XMONTHS."},
        {"path": "bt_results.json",
         "shape": "{pair_ic{}, sn_ic{}, pair_cond{}, pair_port{}, trap{}, cost{}, meta{}}",
         "desc": "Backtest reference metrics: IC by horizon, conditional means, portfolio Sharpe/mean/vol, trend-filter splits."},
        {"path": "Relative_PE_Dashboard.html",
         "shape": "text/html",
         "desc": "The full interactive dashboard (human view)."},
    ],
    "notes": [
        "All endpoints are served by GitHub Pages with Access-Control-Allow-Origin: *.",
        "Data refreshes when `main` is rebuilt; read the top-level `asof` for the snapshot date.",
    ],
}

path = os.path.join(OUT, "api.json")
json.dump(manifest, open(path, "w"), indent=2)
print(f"wrote {path} | asof {manifest['asof']} | "
      f"{manifest['universe']['count']} tickers | {manifest['dates']['count']} dates")
