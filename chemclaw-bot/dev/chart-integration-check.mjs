// Model → show_view → authenticated DSH asset → actual chat, on an isolated mock bench.
// node dev/bench-windows.mjs chart-check-NAME --chart-check
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { CHART_EXAMPLES } from './chart-examples.mjs'
import { CHART_ENGINE_ROUTE } from '../src/shared/chart-engine.js'

const [name, port] = process.argv.slice(2)
if (!/^[a-z0-9-]+$/.test(name ?? '') || !/^\d+$/.test(port ?? '')) throw new Error('Expected isolated bench name and web port')
const root = resolve(import.meta.dirname, '../..')
const home = join(root, `.dsh-test-${name}`)
const base = `http://127.0.0.1:${port}`
const require = createRequire(join(root, 'app/package.json'))
const { chromium } = require('playwright-core')
const binary = process.env.CHROME_BIN ?? ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(existsSync)
const browser = await chromium.launch({ headless: true, executablePath: binary })
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } })
const failures = []
let engineRequests = 0
page.on('pageerror', error => failures.push(error.message))
page.on('console', message => { if (message.type() === 'error') failures.push(message.text().replace(/token=\S+/g, 'token=[redacted]')) })
page.on('request', request => { if (new URL(request.url()).pathname === CHART_ENGINE_ROUTE) engineRequests += 1 })
page.on('response', async response => {
  if (new URL(response.url()).pathname === CHART_ENGINE_ROUTE && !response.ok()) console.error(`engine HTTP ${response.status()}: ${(await response.text()).slice(0, 300)}`)
})
const api = async (endpoint, payload = {}) => {
  const result = await page.evaluate(async ([endpoint, payload]) => (await fetch('/api/bot', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ endpoint, payload }),
  })).json(), [endpoint, payload])
  assert.equal(result.ok, true, `${endpoint}: ${result.error?.message}`)
  return result.value
}
const calls = () => existsSync(join(home, 'mock.jsonl')) ? readFileSync(join(home, 'mock.jsonl'), 'utf8').split('\n').filter(Boolean).length : 0
async function settle() {
  const deadline = Date.now() + 90_000
  let count = calls()
  let since = Date.now()
  while (Date.now() < deadline) {
    await new Promise(done => setTimeout(done, 400))
    const state = await api('state')
    const next = calls()
    if (next !== count || Object.keys(state.activity ?? {}).length || Object.keys(state.work?.turns ?? {}).length) {
      count = next; since = Date.now()
    } else if (Date.now() - since > 2500) return
  }
  throw new Error('Mock team did not settle')
}
const send = async (sessionId, text) => { await api('send', { sessionId, text }); await settle() }
const figure = kind => page.locator(`figure[data-kind="${kind}"]`).last()
async function visible(kind) {
  await figure(kind).waitFor({ state: 'attached', timeout: 30_000 })
  await figure(kind).scrollIntoViewIfNeeded()
  await figure(kind).locator('.bt-advanced-plot-wrap:not([data-table]) svg').waitFor({ timeout: 30_000 })
}
try {
  const unauthenticated = await fetch(base + CHART_ENGINE_ROUTE, { redirect: 'manual' })
  assert.ok(!unauthenticated.ok || !unauthenticated.headers.get('content-type')?.includes('javascript'), 'engine requires DSH authentication')
  const login = readFileSync(join(home, 'web.log'), 'utf8').match(/http:\/\/127\.0\.0\.1:\d+\/\?token=\S+/)?.[0]
  assert.ok(login, 'isolated login exists')
  await page.goto(login)
  const notice = page.getByRole('dialog').getByRole('button', { name: 'Continue' })
  await page.addLocatorHandler(notice, () => notice.click())
  await page.locator('.bt-tile').first().waitFor({ timeout: 60_000 })
  let state = await api('state')
  const main = state.bots.find(bot => bot.id === state.mainBotId)
  assert.ok(main)
  if (!main.model) await api('update-bot', { id: main.id, model: state.models.at(-1).ref })
  await settle()
  await api('create-bot', { name: 'Writer', role: 'Writer' })
  state = await api('state')
  const writer = state.bots.find(bot => bot.name === 'Writer')
  await page.locator(`.bt-row[data-bot-id="${writer.id}"]`).first().click()
  await send(writer.id, '视图图表')
  await page.locator('.bt-chart-svg').waitFor({ timeout: 30_000 })
  assert.equal(engineRequests, 0, 'existing chart does not request advanced engine')
  console.log('ok   original SVG chart in real DSH, zero engine requests')
  for (const kind of Object.keys(CHART_EXAMPLES)) {
    await send(writer.id, `高级图表验收 ${kind}`)
    await visible(kind)
    console.log(`ok   mock model → show_view → actual chat: ${kind}`)
  }
  assert.equal(engineRequests, 1, 'all advanced charts share one engine request')
  const engine = await page.evaluate(async path => { const response = await fetch(path); return { status: response.status, type: response.headers.get('content-type'), text: await response.text() } }, CHART_ENGINE_ROUTE)
  assert.equal(engine.status, 200)
  assert.match(engine.type, /javascript/)
  assert.equal(engine.text, readFileSync(new URL('../runtime/chart-engine.js', import.meta.url), 'utf8'))
  await page.screenshot({ path: join(home, 'private-chart.png') })
  await page.reload()
  await page.locator(`.bt-row[data-bot-id="${writer.id}"]`).first().click()
  for (const kind of Object.keys(CHART_EXAMPLES)) await visible(kind)
  console.log('ok   all seven chart blueprints replay after a full page reload')
  const room = await api('create-room', { members: [writer.id, main.id] })
  await page.locator(`.bt-row[data-room-id="${room.id}"]`).first().click()
  await send(room.id, '高级图表验收 sankey')
  await visible('sankey')
  await page.screenshot({ path: join(home, 'group-chart.png') })
  console.log('ok   advanced chart delivered in group chat for the human audience')
  const before = calls()
  await figure('sankey').locator('svg').hover()
  await page.waitForTimeout(500)
  assert.equal(calls(), before, 'local interaction does not call the model')
  assert.deepEqual(failures, [], 'no uncaught browser errors')
  writeFileSync(join(home, 'chart-results.json'), JSON.stringify({ charts: Object.keys(CHART_EXAMPLES), nativeEngineRequests: 0, sharedEngineRequests: 1, checks: ['authentication', 'packaged asset', 'private chat', 'history reload', 'group delivery', 'local interaction'] }, null, 2))
  console.log('chart-integration-check: all checks passed')
} catch (error) {
  await page.screenshot({ path: join(home, 'chart-failure.png') }).catch(() => {})
  console.error(JSON.stringify({ browserErrors: failures, engineRequests, chartStatus: await page.locator('.bt-advanced-status').allTextContents() }))
  throw error
} finally { await browser.close() }
