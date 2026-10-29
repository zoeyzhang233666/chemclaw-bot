// Real browser acceptance of the production view components; synthetic data, no model or credentials.
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve, join } from 'node:path'
import { gzipSync } from 'node:zlib'
import { build } from 'esbuild'
import { CHART_EXAMPLES } from './chart-examples.mjs'
import { CHART_ENGINE_ROUTE } from '../src/shared/chart-engine.js'

const root = resolve(import.meta.dirname, '../..')
const output = join(root, '.dsh-test-chart-browser')
mkdirSync(output, { recursive: true })
const require = createRequire(join(root, 'app/package.json'))
const { chromium } = require('playwright-core')
const { outputFiles } = await build({
  stdin: { resolveDir: resolve(import.meta.dirname, '..'), contents: `
    import React from 'react'; import { createRoot } from 'react-dom/client';
    import { DeliveredView, WIDGET_CSS } from './src/client/widget-cell.js';
    import { SHARED_CSS } from './src/client/styles.js';
    import { allThemes, themeCss } from './src/client/themes.js';
    const theme = document.createElement('style'); document.head.append(theme);
    const sheet = document.createElement('style'); sheet.textContent = SHARED_CSS + WIDGET_CSS; document.head.append(sheet);
    const root = createRoot(document.getElementById('root'));
    window.setTheme = (id='paper', dark=false, accent) => { theme.textContent = themeCss(allThemes()[id],accent); document.body.toggleAttribute('data-ds-dark-theme',dark); };
    window.setTheme();
    window.showCharts = (views) => root.render(React.createElement(React.Fragment,null,...views.map((view,at)=>React.createElement('section',{key:JSON.stringify(view)},React.createElement(DeliveredView,{title:view.kind+' · synthetic data',view})))));
  ` },
  bundle: true, format: 'iife', platform: 'browser', write: false,
  nodePaths: [join(root, 'app/node_modules')],
  plugins: [{ name: 'test-primitives', setup(bundler) {
    bundler.onResolve({ filter: /^@deepseek-ai\/dsh-client-ui-primitives$/ }, () => ({ path: 'primitives', namespace: 'test' }))
    bundler.onLoad({ filter: /.*/, namespace: 'test' }, () => ({ contents: 'export const MarkdownText=()=>null; export const FishLogo=()=>null;' }))
  } }],
})
const engine = readFileSync(new URL('../runtime/chart-engine.js', import.meta.url))
let engineRequests = 0
const server = createServer((request, response) => {
  if (request.url === CHART_ENGINE_ROUTE) { engineRequests += 1; response.writeHead(200, { 'content-type': 'text/javascript' }).end(engine); return }
  if (request.url === '/gallery.js') { response.writeHead(200, { 'content-type': 'text/javascript' }).end(outputFiles[0].text); return }
  response.writeHead(200, { 'content-type': 'text/html' }).end(`<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;padding:32px;font-family:Arial,sans-serif;background:var(--bt-main);color:var(--bt-ink)}#root{max-width:1040px;margin:auto;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:32px}section{min-width:0;padding:16px;border:1px solid var(--bt-line);border-radius:12px}@media(max-width:600px){body{padding:12px}#root{grid-template-columns:minmax(0,1fr);gap:16px}section{padding:12px}}</style></head><body><div id="root"></div><script src="/gallery.js"></script></body></html>`)
})
await new Promise(done => server.listen(0, '127.0.0.1', done))
const base = `http://127.0.0.1:${server.address().port}`
const binary = process.env.CHROME_BIN ?? ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(existsSync)
const browser = await chromium.launch({ headless: true, executablePath: binary })
const context = await browser.newContext({ viewport: { width: 1240, height: 1050 }, permissions: ['clipboard-read', 'clipboard-write'] })
const page = await context.newPage()
const errors = []
page.on('pageerror', error => errors.push(error.message))
const visiblePlot = '.bt-advanced-plot-wrap:not([data-table]) svg'
const show = async views => { await page.evaluate(views => window.showCharts(views), views); await page.locator('figure').first().waitFor() }
try {
  await page.goto(base)
  await page.waitForFunction(() => window.showCharts)
  const simple = { type: 'chart', kind: 'bar', categories: ['A', 'B', 'C'], series: [{ values: [30, null, 50] }] }
  await show([simple])
  await page.locator('.bt-chart-svg').waitFor()
  assert.equal(engineRequests, 0, 'native SVG views do not load the engine')
  const coldStart = performance.now()
  await show([CHART_EXAMPLES.radar])
  await page.locator(visiblePlot).waitFor()
  const coldMs = performance.now() - coldStart
  assert.equal(engineRequests, 1)
  const warmStart = performance.now()
  await show([CHART_EXAMPLES.sankey])
  await page.locator(visiblePlot).waitFor()
  const warmMs = performance.now() - warmStart
  assert.equal(engineRequests, 1)
  await page.getByRole('button', { name: 'Chart options', exact: true }).click()
  await page.getByRole('menuitem', { name: 'View as table' }).click()
  await page.getByRole('cell', { name: 'Glass', exact: true }).first().waitFor()
  await page.getByRole('button', { name: 'Chart options', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Copy data' }).click()
  assert.match(await page.evaluate(() => navigator.clipboard.readText()), /Soda ash,Glass,70/)
  await page.getByRole('button', { name: 'Chart options', exact: true }).click()
  const download = page.waitForEvent('download')
  await page.getByRole('menuitem', { name: 'Download image' }).click()
  const image = await download
  await image.saveAs(join(output, 'sankey-export.png'))
  await page.getByRole('button', { name: 'Chart options', exact: true }).click()
  await page.getByRole('menuitem', { name: 'View as chart' }).click()
  await show(Object.values(CHART_EXAMPLES))
  for (const kind of Object.keys(CHART_EXAMPLES)) {
    const figure = page.locator(`figure[data-kind="${kind}"]`)
    await figure.scrollIntoViewIfNeeded()
    await figure.locator('.bt-advanced-plot-wrap:not([data-table]) svg').waitFor()
    assert.ok(await figure.locator('svg path,svg rect,svg circle').count() > 0, `${kind} draws actual marks`)
  }
  await page.setViewportSize({ width: 1240, height: 1500 })
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: join(output, 'charts-paper.png'), fullPage: true })
  await page.evaluate(() => window.setTheme('paper', true))
  await page.screenshot({ path: join(output, 'charts-dark.png'), fullPage: true })
  const before = await page.locator('figure[data-kind="radar"] svg').innerHTML()
  await page.evaluate(() => window.setTheme('paper', false, '#4d6bfe'))
  await page.waitForFunction(previous => document.querySelector('figure[data-kind="radar"] svg')?.innerHTML !== previous, before)
  assert.match(await page.locator('figure[data-kind="radar"] svg').innerHTML(), /#4d6bfe|rgb\(77,\s*107,\s*254\)/i)
  await page.evaluate(() => { document.body.dataset.btAdvancedCharts = 'off' })
  await page.waitForFunction(() => document.querySelectorAll('.bt-advanced-plot-wrap:not([data-table])').length === 0)
  assert.equal(await page.locator('figure table').count(), 7)
  await page.evaluate(() => { document.body.dataset.btAdvancedCharts = 'on' })
  await page.locator(visiblePlot).first().waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.evaluate(() => window.setTheme('paper', false))
  await page.screenshot({ path: join(output, 'charts-mobile.png'), fullPage: true })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'narrow charts do not overflow the page')
  const blank = await context.newPage()
  await blank.route(`**${CHART_ENGINE_ROUTE}`, route => route.abort())
  await blank.goto(base)
  await blank.waitForFunction(() => window.showCharts)
  await blank.evaluate(view => window.showCharts([view]), CHART_EXAMPLES.scatter)
  await blank.getByRole('button', { name: 'Retry', exact: true }).waitFor()
  assert.equal(await blank.locator('table tbody tr').count(), 4)
  await blank.unroute(`**${CHART_ENGINE_ROUTE}`)
  await blank.getByRole('button', { name: 'Retry', exact: true }).click()
  await blank.locator(visiblePlot).waitFor()
  await blank.close()
  assert.deepEqual(errors, [])
  const report = { coldMs: Math.round(coldMs), warmMs: Math.round(warmMs), engineBytes: engine.length, engineGzipBytes: gzipSync(engine).length, nativeEngineRequests: 0, sharedEngineRequests: 1, charts: Object.keys(CHART_EXAMPLES), checks: ['theme', 'dark', 'accent', 'mobile', 'table', 'CSV', 'PNG', 'disable', 'fallback', 'retry', 'unmount'] }
  writeFileSync(join(output, 'results.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report))
} finally { await browser.close(); await new Promise(done => server.close(done)) }
