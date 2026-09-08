/**
 * mkcharts.mjs — render the dashboard's own Pairs and Name P/E charts to PNG.
 *
 * The daily email (pair_email.py) needs the same charts the dashboard draws, and mail
 * clients strip both SVG and <canvas>, so the charts have to travel as images. Rather than
 * re-implement the drawing and risk drifting from the site, this drives the built
 * Relative_PE_Dashboard.html in headless Chromium, sets the tab state (ST.A/ST.B/ST.m for a
 * pair, ST.npName/ST.npM for a single name), calls the page's own render function and
 * screenshots the chart element. The output is pixel-identical to what the dashboard shows.
 *
 * Window is ST.m = 12 months, matching the dashboard's own "1Y" range button (a calendar-year
 * cut, ~262 weekday rows, not a fixed 252-row count).
 *
 * Usage: node mkcharts.mjs [outDir] [dashboardPath]
 */
// Prefer the full `playwright` package (what CI installs, so it resolves its own downloaded
// Chromium) and fall back to `playwright-core` for local runs, where the browser is supplied
// out-of-band via CHROMIUM_PATH.
let chromium;
try { ({ chromium } = await import('playwright')); }
catch { ({ chromium } = await import('playwright-core')); }
import fs from 'fs';
import path from 'path';

const OUT  = process.argv[2] || 'charts';
const DASH = path.resolve(process.argv[3] || 'Relative_PE_Dashboard.html');

// Keep in step with PAIRS / SINGLES in pair_email.py.
const PAIRS = [['FDS US','LSEG LN'],['MCO US','MSCI US'],['LPLA US','SCHW US'],['LPLA US','RJF US'],
  ['HOOD US','IBKR US'],['V US','MA US'],['ARES US','BX US'],['KKR US','BX US'],['TPG US','CG US'],
  ['EQT SS','CVC NA'],['BLK US','TROW US'],['LAZ US','PJT US'],['EVR US','PJT US'],['EVR US','HLI US'],
  ['MC US','PJT US'],['AMUN FP','DWS GY'],['SAVE SS','AZA SS']];
const SINGLES = ['XYZ US','ADYEN NA','CHYM US'];

const slug = s => s.replace(/ /g, '').toLowerCase();
// Point at an explicit binary when one is provided or the local sandbox copy is present;
// otherwise let playwright resolve the Chromium it installed itself (the CI path).
const EXEC = process.env.CHROMIUM_PATH
  || ['/opt/pw-browsers/chromium-1194/chrome-linux/chrome'].find(p => fs.existsSync(p));

fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch(EXEC ? { executablePath: EXEC } : {});
// Width matters: drawChart() centres its last x-axis label on the final plotted point and
// leaves only 14px of right padding, so at most widths that label is clipped by the canvas
// edge (and clipped in the bitmap, not just the screenshot). Of the widths tried, a 960px
// viewport leaves the most clearance -- ~30px, enough for a "28 Aug 26" label -- because it
// happens to put the label stride on a kinder index. Re-check this if drawChart's padding or
// label-density maths ever change.
// 960px viewport -> ~878 CSS px of chart; at dpr 1.3 that is a ~1140px PNG shown at 560px in
// the mail, i.e. ~2x for a retina screen without a needlessly heavy payload.
const pg = await browser.newPage({ viewport: { width: 960, height: 760 }, deviceScaleFactor: 1.3 });
await pg.goto('file://' + DASH);
await pg.waitForFunction(() => typeof renderPairs === 'function' && typeof D !== 'undefined');
await pg.waitForTimeout(400);

const asof = await pg.evaluate(() => D[N - 1]);
let n = 0;

await pg.evaluate(() => switchTab('pairs'));
await pg.waitForTimeout(400);
for (const [a, b] of PAIRS) {
  const obs = await pg.evaluate(([a, b]) => {
    ST.A = a; ST.B = b; ST.m = 12; renderPairs();
    return (typeof CHART !== 'undefined' && CHART.n) || 0;
  }, [a, b]);
  if (!obs) { console.error(`!! ${a}/${b}: chart drew 0 points`); process.exitCode = 1; continue; }
  await pg.waitForTimeout(90);
  await pg.locator('#chart').screenshot({ path: `${OUT}/${slug(a)}-${slug(b)}.png` });
  n++;
}

await pg.evaluate(() => switchTab('namepe'));
await pg.waitForTimeout(400);
for (const t of SINGLES) {
  const ok = await pg.evaluate((t) => {
    ST.npName = t; ST.npM = 12; renderNamePE();
    return !!document.querySelector('#np-chart svg');
  }, t);
  if (!ok) { console.error(`!! ${t}: no chart rendered`); process.exitCode = 1; continue; }
  await pg.waitForTimeout(90);
  await pg.locator('#np-chart').screenshot({ path: `${OUT}/${slug(t)}.png` });
  n++;
}

await browser.close();
console.log(`wrote ${n} charts to ${OUT}/ (asof ${asof})`);
