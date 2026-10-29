// Actual native GenUI + ChemClaw plugins in a fresh keyless DSH profile.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const [name, port] = process.argv.slice(2)
if (!/^[a-z0-9-]+$/.test(name ?? '') || !/^\d+$/.test(port ?? '')) throw new Error('Expected isolated bench name and port')
const root = resolve(import.meta.dirname, '../..')
const home = join(root, `.dsh-test-${name}`)
const require = createRequire(join(root, 'app/package.json'))
const { chromium } = require('playwright-core')
const executablePath = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(existsSync)
const browser = await chromium.launch({ headless: true, executablePath })
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } })
const failures = []
const sentRequests = []
page.on('request', request => {
  if (request.method() !== 'POST' || new URL(request.url()).pathname !== '/api/bot') return
  const body = request.postDataJSON()
  if (body?.endpoint === 'send') sentRequests.push(body.payload)
})
page.on('pageerror', error => failures.push(error.message))
page.on('console', message => { if (message.type() === 'error') failures.push(message.text().replace(/token=\S+/g, 'token=[redacted]')) })
const logs = () => existsSync(join(home, 'mock.jsonl')) ? readFileSync(join(home, 'mock.jsonl'), 'utf8').trim().split('\n').filter(Boolean).map(line => JSON.parse(line)) : []
// Background memory consolidation is independent of local UI interaction.
const foregroundCalls = () => logs().filter(entry => !entry.last?.startsWith('The Bot:')).length
const api = async (endpoint, payload = {}) => {
  const result = await page.evaluate(async ([endpoint, payload]) => (await fetch('/api/bot', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ endpoint, payload }) })).json(), [endpoint, payload])
  assert.equal(result.ok, true, `${endpoint}: ${result.error?.message}`)
  return result.value
}
async function settle() {
  let count = logs().length
  let since = Date.now()
  const deadline = Date.now() + 90_000
  while (Date.now() < deadline) {
    await new Promise(done => setTimeout(done, 400))
    const state = await api('state')
    const next = logs().length
    if (next !== count || Object.keys(state.activity ?? {}).length || Object.keys(state.work?.turns ?? {}).length) { count = next; since = Date.now() }
    else if (Date.now() - since > 1800) return
  }
  throw new Error('Mock team did not settle')
}
const send = async (sessionId, text) => { await api('send', { sessionId, text }); await settle() }
const blocks = () => page.locator('[data-genui-explicit-fence]')
const dismissPreview = async () => {
  const notice = page.getByRole('dialog').getByRole('button', { name: /^(Continue|继续)$/ })
  if (await notice.isVisible()) await notice.click()
}
const open = async bot => { await dismissPreview(); await page.locator(`.bt-row[data-bot-id="${bot.id}"]`).first().click() }
async function checkNativeAnswer() {
  const native = JSON.parse(readFileSync(join(home, 'native-fixture.json'), 'utf8'))
  const nativeCalls = logs().filter(entry => entry.session === native.sessionId)
  assert.equal(nativeCalls.filter(entry => entry.last.startsWith('[chemclaw-visual-delivery')).length, 1, 'fresh root Agent receives exactly one visual correction')
  assert.ok(nativeCalls.at(-1).last.startsWith('[chemclaw-visual-delivery'), 'correction adds only the missing view after preceding tools')
  const expand = page.getByRole('button', { name: /展开其余.*会话|Show.*more.*sessions/i })
  if (await expand.first().isVisible()) await expand.first().click()
  const ungrouped = page.getByText(/^(未分组|Ungrouped)$/).first()
  if (await ungrouped.isVisible()) await ungrouped.click()
  await page.getByText(native.title, { exact: true }).first().click()
  await page.getByText('Synthetic compact answer card.', { exact: true }).waitFor({ timeout: 30_000 })
  await page.screenshot({ path: join(home, 'genui-native-answer.png') })
  console.log('ok   a fresh native Agent session automatically gains an inline card')
}
try {
  const login = readFileSync(join(home, 'web.log'), 'utf8').match(/http:\/\/127\.0\.0\.1:\d+\/\?token=\S+/)?.[0]
  assert.ok(login)
  await page.goto(login)
  await page.locator('.bt-tile').first().waitFor({ timeout: 60_000 })
  let state = await api('state')
  const main = state.bots.find(bot => bot.id === state.mainBotId)
  if (!main.model) await api('update-bot', { id: main.id, model: state.models.at(-1).ref })
  await settle()
  await dismissPreview()
  if (process.argv.includes('--native-only')) {
    await page.locator('.bt-account').first().click()
    await page.getByText(/^(Switch to classic Agent mode|切换经典 Agent 模式)$/).click()
    await checkNativeAnswer()
    assert.deepEqual(failures, [])
    console.log('ok   native automatic delivery verified without Bot-owned session state')
  } else {
  const suffix = Date.now().toString(36)
  await api('create-bot', { name: `GenUI A ${suffix}`, role: 'Renderer checks' })
  await api('create-bot', { name: `GenUI B ${suffix}`, role: 'State isolation checks' })
  state = await api('state')
  const a = state.bots.find(bot => bot.name === `GenUI A ${suffix}`)
  const b = state.bots.find(bot => bot.name === `GenUI B ${suffix}`)
  await open(a)
  await settle()
  const beforePlain = foregroundCalls()
  await send(a.id, 'Explain volatility briefly')
  await blocks().filter({ hasText: 'Synthetic compact answer card.' }).last().waitFor({ timeout: 30_000 })
  assert.equal(foregroundCalls() - beforePlain, 2, 'plain answer receives exactly one same-turn visual correction')
  console.log('ok   a plain conceptual answer automatically gains an inline card, one correction only')
  const beforeVisual = foregroundCalls()
  await send(a.id, 'GenUI check timeline')
  await blocks().filter({ hasText: 'Synthetic project milestones' }).getByText('Pilot', { exact: true }).waitFor({ timeout: 30_000 })
  assert.equal(foregroundCalls() - beforeVisual, 1, 'first-pass visual adds zero correction calls')
  console.log('ok   native GenUI timeline in actual ChemClaw private chat')
  await send(a.id, 'GenUI check form')
  let form = blocks().filter({ hasText: 'Synthetic local records' }).last()
  await form.getByRole('textbox', { name: 'Owner note' }).fill('Only A')
  const count = foregroundCalls()
  await form.getByRole('textbox', { name: 'Filter records' }).fill('Beta')
  await form.getByRole('cell', { name: 'Beta', exact: true }).waitFor()
  assert.equal(await form.getByRole('cell', { name: 'Alpha', exact: true }).count(), 0)
  await form.getByRole('textbox', { name: 'Filter records' }).fill('')
  await form.getByRole('columnheader', { name: 'Volume' }).click()
  assert.equal(foregroundCalls(), count, 'local filter and sort do not call the model')
  await page.screenshot({ path: join(home, 'genui-paper.png') })
  console.log('ok   local table filter and sort, zero model calls')
  await open(b)
  await send(b.id, 'GenUI check form')
  form = blocks().filter({ hasText: 'Synthetic local records' }).last()
  assert.equal(await form.getByRole('textbox', { name: 'Owner note' }).inputValue(), '')
  await form.getByRole('textbox', { name: 'Owner note' }).fill('Only B')
  await open(a)
  form = blocks().filter({ hasText: 'Synthetic local records' }).last()
  assert.equal(await form.getByRole('textbox', { name: 'Owner note' }).inputValue(), 'Only A')
  await page.reload()
  await open(a)
  form = blocks().filter({ hasText: 'Synthetic local records' }).last()
  assert.equal(await form.getByRole('textbox', { name: 'Owner note' }).inputValue(), 'Only A')
  const start = logs().length
  await form.getByRole('button', { name: 'Send review', exact: true }).click()
  await settle()
  const action = logs().slice(start).find(entry => entry.last?.startsWith('[genui-action] review'))
  assert.ok(action, 'real action reaches model')
  assert.equal(action.session, a.sessionId ?? a.id)
  assert.match(action.last, /Only A/)
  console.log('ok   identical forms isolated across Bots and reload; action reaches owning Bot')
  for (const kind of ['flow', 'plot']) {
    await send(a.id, `GenUI check ${kind}`)
    await blocks().last().locator('svg').first().waitFor({ timeout: 30_000 })
    console.log(`ok   native GenUI ${kind} renderer in ChemClaw`)
  }
  await send(a.id, '视图图表')
  await page.locator('.bt-chart-svg').waitFor({ timeout: 30_000 })
  await send(a.id, '高级图表验收 sankey')
  await page.locator('figure[data-kind="sankey"] svg').waitFor({ timeout: 30_000 })
  assert.ok(await blocks().count() >= 4)
  console.log('ok   original SVG, advanced chart and full GenUI coexist')
  await api('set-prefs', { theme: 'paper' })
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.waitForFunction(() => document.body.hasAttribute('data-ds-dark-theme'))
  await blocks().last().scrollIntoViewIfNeeded()
  await page.screenshot({ path: join(home, 'genui-dark.png') })
  await page.emulateMedia({ colorScheme: 'light' })
  await page.waitForFunction(() => !document.body.hasAttribute('data-ds-dark-theme'))
  await page.setViewportSize({ width: 390, height: 844 })
  await blocks().last().scrollIntoViewIfNeeded()
  await page.screenshot({ path: join(home, 'genui-mobile.png') })
  await page.setViewportSize({ width: 1400, height: 1000 })
  const room = await api('create-room', { members: [a.id, main.id] })
  await page.locator(`.bt-row[data-room-id="${room.id}"]`).first().click()
  await send(room.id, 'GenUI check timeline')
  await blocks().filter({ hasText: 'Synthetic project milestones' }).getByText('Pilot', { exact: true }).first().waitFor({ timeout: 30_000 })
  await page.screenshot({ path: join(home, 'genui-group.png') })
  console.log('ok   GenUI timeline in actual group delivery')
  await send(room.id, 'GenUI check form')
  form = blocks().filter({ hasText: 'Synthetic local records' }).last()
  await form.getByRole('textbox', { name: 'Owner note' }).fill('Group only')
  const groupStart = sentRequests.length
  await form.getByRole('button', { name: 'Send review', exact: true }).click()
  await settle()
  assert.ok(sentRequests.slice(groupStart).some(entry => entry.sessionId === room.id && entry.text?.startsWith('[genui-action] review') && entry.text.includes('Group only')), 'group action returns through room route')
  await page.reload()
  await page.locator(`.bt-row[data-room-id="${room.id}"]`).first().click()
  form = blocks().filter({ hasText: 'Synthetic local records' }).last()
  assert.equal(await form.getByRole('textbox', { name: 'Owner note' }).inputValue(), 'Group only')
  console.log('ok   group form action reaches group and group state survives reload')
  const beforeGroupCards = await blocks().filter({ hasText: 'Synthetic compact answer card.' }).count()
  await send(room.id, 'Explain volatility briefly')
  assert.ok(await blocks().filter({ hasText: 'Synthetic compact answer card.' }).count() > beforeGroupCards, 'direct human group answer gains an inline card automatically')
  console.log('ok   a direct human group answer receives automatic inline delivery')
  await open(a)
  await send(a.id, 'GenUI check panel')
  await page.locator('.bt-account').first().click()
  await page.getByText(/^(Switch to classic Agent mode|切换经典 Agent 模式)$/).click()
  await page.locator('[data-genui-panel]').waitFor({ timeout: 30_000 })
  const toggle = page.locator('[data-genui-panel] button[aria-expanded=false]').first()
  if (await toggle.isVisible()) await toggle.click()
  await page.locator('[data-genui-panel]').getByText('Native panel ready', { exact: true }).waitFor({ timeout: 30_000 })
  await page.screenshot({ path: join(home, 'genui-native-panel.png') })
  console.log('ok   upstream panel renders in classic Agent mode separately from Bot inline delivery')
  await checkNativeAnswer()
  assert.deepEqual(failures, [])
  writeFileSync(join(home, 'genui-results.json'), JSON.stringify({ passed: true, errors: failures, checks: ['automatic-short-answer', 'bounded-correction', 'no-extra-call-for-visual', 'timeline', 'filter', 'sort', 'isolation', 'reload', 'action', 'mermaid', 'plot', 'coexistence', 'themes', 'mobile', 'group', 'group-action', 'group-reload', 'group-automatic-answer', 'native-panel', 'native-automatic-answer'] }, null, 2))
  }
} catch (error) {
  await page.screenshot({ path: join(home, 'genui-failure.png') }).catch(() => {})
  console.error(JSON.stringify({ errors: failures, body: (await page.locator('body').innerText()).slice(-4500) }))
  throw error
} finally { await browser.close() }
