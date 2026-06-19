# Runbook — rebuild & publish the Relative-Value Forward-P/E dashboard

End-to-end steps to reproduce the deliverable artifact (`Relative_PE_Dashboard.html`)
and publish it as an **org-private Claude Code artifact**. For the full operating
manual (data model, refresh procedure, invariants, licensing) see `CLAUDE.md`.

> ⚠️ The file embeds **licensed Bloomberg/S&P data**. Keep it private — see
> "Publish" below and `CLAUDE.md` §11. Never put it on a public site.

## 0. Prerequisites

- **Python 3** and **Node.js** on PATH (`python3 --version`, `node --version`).
- Git access to the private repo `vhung-1/PEhistory`.
- **To publish as an artifact** (step 5): the Claude Code **CLI** or **desktop app
  (≥ 1.13576.0)**, signed in with **`/login`** (not an API key / gateway token),
  on a **Team or Enterprise** plan, using the **Anthropic API** (not Bedrock /
  Vertex / Foundry). On Enterprise an admin must enable Artifacts in
  claude.ai → Settings → Claude Code → Capabilities. The org must not have
  ZDR / HIPAA / CMEK enabled. (These are why publishing can't run from a managed
  remote / Agent-SDK session — it's off by default there.)

## 1. Get the repo

```bash
git clone https://github.com/vhung-1/PEhistory.git
cd PEhistory
git checkout claude/relaxed-einstein-8q032y   # or `main` once PR #1 is merged
```

Canonical inputs: `template.html` (source of truth, 4 tokens) + the 4 JSON
payloads `data.json`, `q_pairs.json`, `btdata.json`, `daily_px.json`, plus the
gate files `bt_verify.js` / `bt_results.json`.

## 2. Build the artifact

```bash
python build.py
```

Substitutes the 4 tokens (long ones first) → writes **`Relative_PE_Dashboard.html`**
(~2.0 MB, self-contained). Prints `built Relative_PE_Dashboard.html (2.02 MB)`.

## 3. Validation gate — both must pass

**(a) JS syntax** — extract the largest `<script>` and syntax-check it:

```bash
python3 -c "import re;h=open('Relative_PE_Dashboard.html',encoding='utf-8').read();open('/tmp/app.js','w',encoding='utf-8').write(max(re.findall(r'<script>([\s\S]*?)</script>',h),key=len))"
node --check /tmp/app.js        # exit 0 / no output = pass
```

**(b) Backtest gate** — engine must reproduce the Python reference:

```bash
node bt_verify.js               # must print: ✅ ALL CHECKS PASSED (39 passed)
```

> If you changed any backtest input data, first regenerate the reference with
> `python bt_export.py` (and `python q_pairs.py`) — otherwise the gate "fails"
> only because `bt_results.json` is stale. See `CLAUDE.md` §4.

## 4. Confirm invariants

```bash
python3 - <<'PY'
import json, datetime
d = json.load(open('data.json')); px = json.load(open('daily_px.json'))['px']
dates = d['dates']
wk = [x for x in dates if datetime.date.fromisoformat(x).weekday() >= 5]
print('asof        :', d['asof'])
print('span        :', dates[0], '->', dates[-1], '(', len(dates), 'rows )')
print('weekend rows:', len(wk))
print('tickers     :', len(d['pe']), '/ sectors', len(d['sectors']))
print('DPX names   :', len(px), '| len mismatches:', sum(len(a)!=len(dates) for a in px.values()))
PY
```

Expect: `asof 2026-06-18`; span `2020-06-19 -> 2026-06-18` (~1565 rows);
**0 weekend rows**; 85 tickers / 7 sectors; 85 DPX names, 0 mismatches. Also
confirm no build tokens remain (`grep -c '__DATA__\|__QDATA__\|__BTDATA__\|__DPX__'`
→ 0).

To refresh the underlying data before rebuilding, follow `CLAUDE.md` §7.

## 5. Publish as an org-private Claude Code artifact

From a **local** Claude Code CLI (in the repo dir) or the desktop app, signed in
with `/login`:

```text
Publish Relative_PE_Dashboard.html as an artifact.
```

- Approve the prompt (*"Claude wants to publish … to a private page on claude.ai"*).
  Claude prints a **private URL** and opens your browser. Press `Ctrl+]` to reopen
  the most recent artifact.
- **Share** from the page header → grant specific people in your org, or everyone
  in it. It is visible only to you until you do. There is **no public option** —
  which is exactly what the data license requires.
- **Update later:** in a new session, give Claude the artifact URL and ask it to
  revise, e.g. `Update https://claude.ai/code/artifact/<id> with today's numbers.`
  Without the URL a new session creates a *new* artifact.
- If your org restricts outbound traffic, allowlist `*.claudeusercontent.com`.

Page constraints (all satisfied by this file): single self-contained `.html`,
≤ 16 MiB, **no external requests** (CSP blocks them; this file inlines everything).

To send the dashboard to someone **outside** your org, share the HTML **file**
directly instead — never a public link.
