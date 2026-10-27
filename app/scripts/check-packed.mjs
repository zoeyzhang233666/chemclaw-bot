// Check a packaged app: start it on throwaway folders with the ds-bot mock model, choose a model,
// send a message, wait for the reply, then close the window the way a user does and wait until
// the app has exited. Fails on a page error or a non-zero exit.
// Usage: node scripts/check-packed.mjs [app executable] [screenshot.png]
// The executable defaults to the one that `npm run pack` or `npm run dist` writes into dist-pack/.
import { spawn, spawnSync } from 'node:child_process'
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, dirname, isAbsolute, join, relative, resolve } from 'node:path'
import { setTimeout as sleep } from 'node:timers/promises'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import { createServer } from 'node:http'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const [given, shotFile] = process.argv.slice(2)
const source = given === '--source'
if (source) {
  const plugin = resolve(root, '../chemclaw-bot')
  const installed = dirname(createRequire(import.meta.url).resolve('chemclaw-bot/package.json'))
  if (resolve(installed) !== plugin) for (const path of ['package.json', 'index.js', 'client.js', 'NOTICE', 'src/host', 'src/shared']) cpSync(join(plugin, path), join(installed, path), { recursive: true })
}
const executable = source ? process.env.CHEMCLAW_TEST_ELECTRON || createRequire(import.meta.url)('electron') : given || packedExecutable()

function packedExecutable() {
  const out = join(root, 'dist-pack')
  if (process.platform === 'win32') return join(out, 'win-unpacked', 'ChemClaw.exe')
  const dir = ['mac-arm64', 'mac'].find(name => existsSync(join(out, name))) ?? 'mac'
  return join(out, dir, 'ChemClaw.app', 'Contents', 'MacOS', 'ChemClaw')
}

if (!existsSync(executable)) {
  console.error(`check-packed: no app at ${executable}. Run npm run pack first.`)
  process.exit(2)
}

const work = realpathSync.native(mkdtempSync(join(realpathSync.native(tmpdir()), 'ds-bot-packed-')))
mkdirSync(join(work, 'home'))
mkdirSync(join(work, 'workspace'))
const browserFixture = createServer((_request, response) => {
  response.setHeader('content-type', 'text/html; charset=utf-8')
  response.end('<!doctype html><title>ChemClaw Browser Check</title><h1>企业资料查询测试</h1><p>此网页仅用于隔离测试，无需登录。</p>')
})
const children = []
let updateRequests = 0
const updateFeed = createServer((_request, response) => {
  updateRequests++
  response.setHeader('content-type', process.platform === 'darwin' ? 'application/json' : 'text/yaml')
  response.end(process.platform === 'darwin' ? '[]' : `version: 0.0.0\nfiles:\n  - url: unused.exe\n    sha512: ${Buffer.alloc(64).toString('base64')}\n`)
})

function stopChildren() {
  for (const child of children) {
    if (child.exitCode !== null || child.signalCode !== null) continue
    // On Windows a plain kill ends only the main process; /T takes the Host and Electron's helpers along.
    if (process.platform === 'win32') spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
    else child.kill()
  }
}

// An app that hangs, for example behind its error box, must not hold up CI.
setTimeout(() => {
  console.error('check-packed: FAILED: gave up after 8 minutes')
  stopChildren()
  process.exit(1)
}, 8 * 60_000).unref()

// Run from inside this checkout, the app would find a module that the build left out in the
// checkout's own node_modules, so the check runs a copy of the app from the throwaway folder.
function outsideCheckout(file) {
  const fromCheckout = relative(resolve(root, '..'), file)
  if (fromCheckout.startsWith('..') || isAbsolute(fromCheckout)) return file
  const appDir = process.platform === 'darwin' ? resolve(file, '..', '..', '..') : dirname(file)
  const copy = join(work, basename(appDir))
  cpSync(appDir, copy, { recursive: true, verbatimSymlinks: true })
  console.log(`check-packed: runs a copy of ${appDir} in ${work}`)
  return join(copy, relative(appDir, file))
}

function startMock() {
  const mock = spawn(process.execPath, [join(root, '..', 'chemclaw-bot', 'dev', 'mock-llm.mjs')], {
    env: { ...process.env, MOCK_PORT: '0', MOCK_LOG: join(work, 'mock.log') }, stdio: ['ignore', 'pipe', 'inherit'],
  })
  children.push(mock)
  return new Promise((done, reject) => {
    let text = ''
    mock.stdout.setEncoding('utf8')
    mock.stdout.on('data', (chunk) => {
      text += chunk
      const url = /http:\/\/127\.0\.0\.1:\d+\/v1/u.exec(text)?.[0]
      if (url) done(url)
    })
    mock.once('exit', (code) => { reject(new Error(`check-packed: the mock model stopped (exit ${String(code)})`)) })
  })
}

async function appPage(port, deadline) {
  while (Date.now() < deadline) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${String(port)}/json/list`)).json()
      const page = targets.find(target => target.type === 'page' && /^http:\/\/127\.0\.0\.1:\d+\//u.test(target.url))
      if (page) return page
    } catch {
      // The debugging port is not listening yet.
    }
    await sleep(500)
  }
  throw new Error('the app window did not appear')
}

function devtools(url, problems) {
  const socket = new WebSocket(url)
  const pending = new Map()
  const requests = []
  let next = 1
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(String(event.data))
    if (message.method === 'Network.requestWillBeSent') requests.push(message.params.request.url)
    if (message.method === 'Runtime.exceptionThrown') problems.push(`exception: ${message.params.exceptionDetails.exception?.description ?? message.params.exceptionDetails.text}`)
    if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') problems.push(`console.error: ${message.params.args.map(arg => arg.value ?? arg.description).join(' ')}`)
    if (message.method === 'Log.entryAdded' && message.params.entry.level === 'error') {
      const entry = message.params.entry
      // Windows can refuse DSH's optional COM handler enumeration. Native handoffs
      // are verified separately below; missing-file requests deliberately return 404.
      if (entry.url?.includes('/api/present.open?') && /\b(?:500|404)\b/.test(entry.text)) console.log(`check-packed: native file endpoint: ${entry.text}`)
      else problems.push(`log: ${entry.text} ${entry.url ?? ''}`)
    }
    const entry = pending.get(message.id)
    if (entry === undefined) return
    pending.delete(message.id)
    if (message.error) entry.reject(new Error(message.error.message))
    else entry.resolve(message.result)
  })
  const opened = new Promise((done, reject) => {
    socket.addEventListener('open', done, { once: true })
    socket.addEventListener('error', reject, { once: true })
  })
  const call = (method, params = {}) => new Promise((done, reject) => {
    const id = next++
    const timer = setTimeout(() => {
      pending.delete(id)
      reject(new Error(`the window did not answer ${method}${params.expression ? ` (${params.expression.slice(0, 180)})` : ''}`))
    }, 90_000)
    const settle = action => (value) => { clearTimeout(timer); action(value) }
    pending.set(id, { resolve: settle(done), reject: settle(reject) })
    socket.send(JSON.stringify({ id, method, params }))
  })
  return { opened, call, requests }
}

// mica.css styles DSH's own page, which can change with a DSH upgrade; every rule must still
// find an element, on every platform, so the change shows here and not as a broken window.
function micaRules() {
  const css = readFileSync(join(root, 'src', 'mica.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//gu, '')
  return [...css.matchAll(/([^{}]+)\{/gu)].map(([, selectors]) => selectors.split(',')
    .map(selector => selector.trim().replace(/::(?:before|after)$/u, ''))
    .filter(selector => selector !== '' && selector !== 'body'))
    .filter(rule => rule.length > 0)
}

async function chat(cdp) {
  const evaluate = async expression => (await cdp.call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })).result.value
  const until = async (expression, label, ms = 120_000) => {
    console.log(`check-packed: waiting for ${label}`)
    const end = Date.now() + ms
    while (Date.now() < end) {
      if (await evaluate(`Boolean(${expression})`)) return
      await sleep(250)
    }
    throw new Error(`timed out waiting for ${label}`)
  }
  const text = needle => `document.body.innerText.includes(${JSON.stringify(needle)})`
  await cdp.call('Runtime.enable')
  await cdp.call('Log.enable')
  await cdp.call('Network.enable')
  await until("document.querySelector('.bt-tile[data-bot-id], .bt-row[data-bot-id]')", 'the team')
  await until("!document.body.innerText.includes('正在设置主 Bot')", 'the coordinator')
  if (await evaluate("document.body.innerText.includes('预览版说明') || document.body.innerText.includes('Preview Notice')")) throw new Error('The independent app still shows upstream preview onboarding')
  const catalog = await evaluate("fetch('api/bot', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ endpoint: 'scenario-catalog', payload: {} }) }).then(r => r.json()).then(r => r.value)")
  if (catalog.roles.length !== 50 || catalog.groups.length !== 15) throw new Error('Incomplete scenario catalog')
  if (!source) {
    await until('window.dsBotApp?.updates', 'the desktop update bridge')
    const status = await evaluate('window.dsBotApp.updates.check()')
    if (!status.enabled || !status.checkedAt || status.phase === 'failed') throw new Error('The packaged app did not check its isolated update feed')
    await evaluate("[...document.querySelectorAll('button')].find(node => /^(Bot|Bots)$/.test(node.textContent.trim())).click()")
    await until("document.querySelector('.bt-settings-nav')", 'settings')
    await evaluate("[...document.querySelectorAll('.bt-settings-item')].find(node => /^(关于 ChemClaw|About ChemClaw)$/.test(node.textContent.trim())).click()")
    const checkButton = "[...document.querySelectorAll('.bt-settings-page button')].find(node => /^(检查更新|Check for updates)$/.test(node.textContent.trim()))"
    await until(`${checkButton} && !${checkButton}.disabled`, 'the enabled app update button')
    const before = updateRequests
    await evaluate(`${checkButton}.click()`)
    const end = Date.now() + 15_000
    while (updateRequests === before && Date.now() < end) await sleep(100)
    if (updateRequests === before) throw new Error('About did not check the app update feed')
    await until(`${checkButton} && !${checkButton}.disabled`, 'the completed manual update check')
    await evaluate("document.querySelector('.bt-settings-close').click()")
    await until("!document.querySelector('.bt-settings')", 'settings to close')
    console.log('check-packed: About checked the isolated app update feed')
  }
  if (shotFile && !process.argv.includes('--browser-shot-only')) {
    const capture = async suffix => { await sleep(650); const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' }); writeFileSync(resolve(`${shotFile}.${suffix}.png`), Buffer.from(data, 'base64')) }
    await capture('home')
    await evaluate("[...document.querySelectorAll('button')].find(node => /^(Bot|Bots)$/.test(node.textContent.trim()))?.click()")
    await until(text('我的 Bot'), 'the Bots page')
    await evaluate("[...document.querySelectorAll('button')].find(node => /^(内置专家|Built-in experts)$/.test(node.textContent.trim()))?.click()")
    await until(text('下游客户开发'), 'scenario cards')
    await sleep(300)
    await capture('bots')
    await cdp.call('Emulation.setDeviceMetricsOverride', { width: 720, height: 950, deviceScaleFactor: 1, mobile: false })
    await sleep(250)
    await capture('bots-narrow')
    await cdp.call('Emulation.clearDeviceMetricsOverride')
    await evaluate("[...document.querySelectorAll('button')].find(node => /^(模型|Models)$/.test(node.textContent.trim()))?.click()")
    await until(text('APIHub'), 'the APIHub setup card')
    await capture('models')
    const paper = await evaluate("getComputedStyle(document.querySelector('.bt-apihub')).backgroundImage")
    await evaluate("document.body.setAttribute('data-ds-dark-theme', '')")
    await sleep(250)
    const dark = await evaluate("getComputedStyle(document.querySelector('.bt-apihub')).backgroundImage")
    if (paper === dark) throw new Error('The model card did not adapt to the dark theme')
    await capture('models-dark')
    await evaluate("document.body.removeAttribute('data-ds-dark-theme')")
    await evaluate("[...document.querySelectorAll('button')].find(node => /^(连接器|Connectors)$/.test(node.textContent.trim()))?.click()")
    await until("[...document.querySelectorAll('.bt-chemcloud')].some(node => node.textContent.includes('芯化和云数据中台'))", 'company connector')
    await until("document.querySelectorAll('.bt-data-card').length >= 5", 'public data cards')
    await evaluate("[...document.querySelectorAll('.bt-chemcloud')].find(node => node.textContent.includes('芯化和云数据中台')).querySelector('button').click()")
    await capture('connectors')
    await evaluate("[...document.querySelectorAll('summary')].find(node => /MCP JSON/.test(node.textContent)).click()")
    await evaluate("[...document.querySelectorAll('details')].find(node => node.textContent.includes('MCP JSON')).scrollIntoView({block:'center'})")
    await capture('advanced')
    await evaluate("document.querySelector('[role=dialog] [aria-label=\"Close\"], [role=dialog] [aria-label=\"关闭\"]')?.click()")
    await cdp.call('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  }
  const stale = await evaluate(`${JSON.stringify(micaRules())}.filter(rule => !rule.some(selector => document.querySelector(selector) !== null)).map(rule => rule.join(', '))`)
  if (stale.length > 0) throw new Error(`src/mica.css no longer matches DSH's page: ${stale.join(' | ')}`)
  const main = await evaluate("fetch('api/bot', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ endpoint: 'state', payload: {} }) }).then(r => r.json()).then(r => r.value.mainBotId)")
  await evaluate(`document.querySelector(${JSON.stringify(`[data-bot-id="${main}"]`)}).click()`)
  // Template Bots may already inherit the harness default model (no chip UI).
  {
    const end = Date.now() + 30_000
    let sawChip = false
    let sawGreeting = false
    while (Date.now() < end && !sawChip && !sawGreeting) {
      sawChip = await evaluate("Boolean(document.querySelector('.bt-model-chip:not(.bt-model-chip-quiet)'))")
      sawGreeting = await evaluate(text('今天想先解决哪个业务问题'))
      if (!sawChip && !sawGreeting) await sleep(250)
    }
    if (sawChip) await evaluate("document.querySelector('.bt-model-chip:not(.bt-model-chip-quiet)').click()")
  }
  // The mock model's greeting for a new team.
  await until(text('今天想先解决哪个业务问题'), 'the greeting')
  await evaluate("[...document.querySelectorAll('[role=textbox][contenteditable=true], textarea')].filter(node => !node.closest('.bt-side')).at(-1).focus()")
  await cdp.call('Input.insertText', { text: 'packaged app check' })
  for (const type of ['keyDown', 'keyUp']) await cdp.call('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  // The mock model starts its reply with 收到： and the message.
  await until(text('收到：packaged app check'), 'the reply')
  await until('window.dsBotApp?.browser?.views', 'the native browser bridge')
  await evaluate("[...document.querySelectorAll('[role=textbox][contenteditable=true], textarea')].filter(node => !node.closest('.bt-side')).at(-1).focus()")
  await cdp.call('Input.insertText', { text: `浏览器检查 http://127.0.0.1:${browserFixture.address().port}/` })
  for (const type of ['keyDown', 'keyUp']) await cdp.call('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  await until(text('浏览器检查完成：ChemClaw Browser Check'), 'the Bot browser tool through Host IPC')
  await evaluate("document.querySelector('.bt-pill').click()")
  const openBrowser = "[...document.querySelectorAll('button')].find(node => /^(Open browser|打开浏览器)$/.test(node.getAttribute('aria-label') || ''))"
  await until(openBrowser, 'the browser button')
  await evaluate(`${openBrowser}.click()`)
  await until("document.querySelector('.bt-browser-takeover')", 'the browser control bar')
  const control = label => `[...document.querySelectorAll('.bt-browser-takeover button')].find(node => node.textContent.trim() === ${JSON.stringify(label)})`
  const take = await evaluate("document.body.innerText.includes('接管浏览器')") ? '接管浏览器' : 'Take over'
  await evaluate(`${control(take)}.click()`)
  await until("document.querySelector('.bt-browser-takeover[data-held]')", 'the user takeover')
  const give = await evaluate("document.body.innerText.includes('交还给 Bot')") ? '交还给 Bot' : 'Give back'
  await evaluate(`${control(give)}.click()`)
  await until("document.querySelector('.bt-browser-takeover:not([data-held])')", 'the returned browser')
  if (shotFile) {
    await sleep(600)
    const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' })
    writeFileSync(resolve(`${shotFile}.browser.png`), Buffer.from(data, 'base64'))
  }
  // Closing details returns the workspace seat to the file-preview checks below.
  await evaluate("document.querySelector('.bt-pill').click()")
  console.log('check-packed: browser tool, native bridge, takeover and give-back passed')
  const sendMain = async message => {
    await evaluate("[...document.querySelectorAll('[role=textbox][contenteditable=true]')].at(-1).focus()")
    await cdp.call('Input.insertText', { text: message })
    for (const type of ['keyDown', 'keyUp']) await cdp.call('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  }
  await sendMain('长任务 6 1')
  await until(text('步骤0'), 'the active main task')
  await sendMain('/side 当前进展是什么？')
  await until("document.querySelector('.bt-side-input')", 'the side-chat panel')
  await until(text('Side note: 0 earlier pair(s) seen.'), 'the independent side answer')
  await evaluate("document.querySelector('.bt-side-input').focus()")
  await cdp.call('Input.insertText', { text: '继续解释一下' })
  for (const type of ['keyDown', 'keyUp']) await cdp.call('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  await until(text('Side note: 1 earlier pair(s) seen.'), 'the side follow-up')
  await until(text('长任务做完了'), 'the main task completing without interruption')
  if (shotFile) {
    const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' })
    writeFileSync(resolve(`${shotFile}.side.png`), Buffer.from(data, 'base64'))
  }
  await evaluate("document.querySelector('.bt-ptab-close').click()")
  console.log('check-packed: /side and follow-up answered while the main task continued')

  await evaluate("document.querySelector('.bt-account').click()")
  await until("document.querySelector('.bt-account-menu')", 'the account menu')
  await evaluate("[...document.querySelectorAll('.bt-account-menu button')].find(node => /^(设置|Settings)$/.test(node.textContent.trim())).click()")
  await until("document.querySelector('.bt-look-seg')", 'message layout settings')
  await evaluate("[...document.querySelectorAll('.bt-look-seg button')].find(node => /^(平铺|Flat)$/.test(node.textContent.trim())).click()")
  await until("document.body.dataset.btLayout === 'flat'", 'flat layout to apply')
  await until("document.querySelectorAll('.bt-range input').length === 2", 'independent text and bubble widths')
  await evaluate("(() => { const input = document.querySelector('.bt-range input'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '75'); input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true })); })()")
  await until("document.body.style.getPropertyValue('--bt-flat-w') === '0.75'", 'the saved text width')
  if (shotFile) { const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' }); writeFileSync(resolve(`${shotFile}.layout.png`), Buffer.from(data, 'base64')) }
  await evaluate("document.querySelector('.bt-settings-close').click()")
  await until("!document.querySelector('.bt-settings')", 'settings to close')
  await cdp.call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await cdp.call('Emulation.setTouchEmulationEnabled', { enabled: true })
  await sleep(500)
  const touch = await evaluate("(() => { const row = [...document.querySelectorAll('.bt-msg')].at(-1); row?.click(); return matchMedia('(hover: none)').matches; })()")
  if (!touch) throw new Error('Touch emulation did not remove hover')
  await until("document.querySelector('.bt-msg .bt-tools[data-open]')", 'tap-open message actions')
  const targetSize = await evaluate("(() => { const rect = document.querySelector('.bt-msg .bt-tools[data-open] .bt-tool').getBoundingClientRect(); return [rect.width, rect.height]; })()")
  if (targetSize.some(value => value < 44)) throw new Error('Touch message actions are smaller than 44px')
  if (shotFile) { const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' }); writeFileSync(resolve(`${shotFile}.mobile.png`), Buffer.from(data, 'base64')) }
  await cdp.call('Emulation.clearDeviceMetricsOverride')
  await cdp.call('Emulation.setTouchEmulationEnabled', { enabled: false })
  await evaluate("fetch('api/bot', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ endpoint: 'set-prefs', payload: { layout: 'bubble', flatWidth: 100 } }) }).then(r => r.json())")
  await until("document.body.dataset.btLayout === 'bubble'", 'the original layout')
  console.log('check-packed: layout, saved widths and 390px touch message actions passed')


  await evaluate("[...document.querySelectorAll('[role=textbox][contenteditable=true], textarea')].filter(node => !node.closest('.bt-side')).at(-1).focus()")
  await cdp.call('Input.insertText', { text: '要密钥 DEMO_THEME_TEST' })
  for (const type of ['keyDown', 'keyUp']) await cdp.call('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  await until("document.querySelector('.bt-secret-card .bt-q-x')", 'the secure-entry card')
  await sleep(650)
  if (shotFile) { const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' }); writeFileSync(resolve(`${shotFile}.secret.png`), Buffer.from(data, 'base64')) }
  await evaluate("document.querySelector('.bt-secret-card .bt-q-x').click()")
  await until("!document.querySelector('.bt-secret-card .bt-q-x')", 'secret request cancellation')
  const delivery = join(work, 'workspace', '中文文件 sample.html')
  writeFileSync(delivery, '<!doctype html><meta charset="utf-8"><title>ChemClaw delivery check</title><h1>可点击交付文件</h1><button onclick="this.textContent=\'交互成功\'">交互测试</button>')
  await evaluate("[...document.querySelectorAll('[role=textbox][contenteditable=true], textarea')].filter(node => !node.closest('.bt-side')).at(-1).focus()")
  await cdp.call('Input.insertText', { text: `交付 ${delivery}` })
  for (const type of ['keyDown', 'keyUp']) await cdp.call('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  await until("document.querySelector('[data-presented-file] button[aria-label]')", 'the present file card')
  await evaluate("document.querySelector('[data-presented-file] button[aria-label]').click()")
  await until("document.querySelector('iframe')", 'the HTML preview')
  await sleep(300)
  if (shotFile) {
    const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' })
    writeFileSync(resolve(`${shotFile}.delivery.png`), Buffer.from(data, 'base64'))
  }
  await evaluate("[...document.querySelectorAll('[data-presented-file] button')].at(-1).click()")
  await sleep(1500)
  const nativeUrl = cdp.requests.find(url => url.includes('/api/present.open?'))
  if (!nativeUrl) throw new Error('No native file action URL was offered: ' + JSON.stringify(await evaluate("[...document.querySelectorAll('[data-presented-file] button')].map(n=>n.outerHTML)")))
  // Association discovery is optional (and can wait on OS prompts in hosted
  // desktops). Opening and revealing the actual file must still succeed below.
  const discovery = await evaluate(`fetch(${JSON.stringify(nativeUrl)}, { signal: AbortSignal.timeout(5000) }).then(r => r.status).catch(error => { if (error.name === 'TimeoutError') return 'timed out (optional)'; throw error })`)
  console.log(`check-packed: native application discovery: ${discovery}`)
  for (const action of ['reveal', 'open']) {
    const status = await evaluate(`fetch(${JSON.stringify(nativeUrl + '&action=')} + ${JSON.stringify(action)}, { method: 'POST', signal: AbortSignal.timeout(30000) }).then(r => r.status)`)
    if (status !== 204) throw new Error(`Native ${action} failed: HTTP ${status}`)
  }
  rmSync(delivery)
  const missing = await evaluate(`fetch(${JSON.stringify(nativeUrl)}, { method: 'POST' }).then(r => r.status)`)
  if (missing !== 404) throw new Error(`Missing file did not return 404: ${missing}`)
  console.log('check-packed: present file card and HTML preview passed')
  await sleep(1000)
  console.log(`check-packed: chat ${JSON.stringify(await evaluate('document.body.innerText.slice(-200)'))}`)
}

let failed = false
const problems = []
try {
  await new Promise(resolve => updateFeed.listen(0, '127.0.0.1', resolve))
  await new Promise(resolve => browserFixture.listen(0, '127.0.0.1', resolve))
  const modelUrl = await startMock()
  const port = 9300 + Math.floor(Math.random() * 600)
  // A terminal inside an Electron-based editor may set ELECTRON_RUN_AS_NODE, which turns the app into plain Node.
  const { ELECTRON_RUN_AS_NODE: _runAsNode, ...env } = process.env
  for (const key of Object.keys(env)) if (/KEY|TOKEN|PASSWORD|SECRET/i.test(key)) delete env[key]
  Object.assign(env, {
    DS_BOT_HOME: join(work, 'home'), DS_BOT_SHELL_DATA: join(work, 'shell'),
    DS_BOT_WORKSPACE: join(work, 'workspace'),
    DEEPSEEK_BASE_URL: modelUrl, DEEPSEEK_API_KEY: 'mock-key',
    CHEMCLAW_UPDATE_URL: `http://127.0.0.1:${updateFeed.address().port}/`,
  })
  // Intel macOS runners may have no working EGL display. Exercise the same
  // renderer with software compositing rather than repeatedly crashing its GPU.
  const graphics = process.env.CI && process.platform === 'darwin' ? ['--disable-gpu'] : []
  const app = spawn(source ? executable : outsideCheckout(resolve(executable)), [...(source ? [root] : []), ...graphics, `--remote-debugging-port=${String(port)}`], { stdio: 'inherit', env, windowsHide: true })
  children.push(app)
  const exited = new Promise((done) => { app.once('exit', (code, signal) => { done({ code, signal }) }) })
  const cdp = devtools((await appPage(port, Date.now() + 120_000)).webSocketDebuggerUrl, problems)
  await cdp.opened
  const chatError = await chat(cdp).then(() => undefined, error => error)
  if (shotFile) {
    const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' })
    writeFileSync(resolve(shotFile), Buffer.from(data, 'base64'))
    console.log(`check-packed: saved ${resolve(shotFile)}`)
  }
  // Closed like a user closes it, also after a failure, so that the app stops its Host. The page
  // goes away with the window, so this call gets no answer.
  void cdp.call('Runtime.evaluate', { expression: 'window.close()' }).catch(() => undefined)
  const outcome = await Promise.race([exited, sleep(40_000).then(() => undefined)])
  if (chatError) throw chatError
  if (outcome === undefined) throw new Error('the app did not exit after its window closed')
  console.log(`check-packed: app exited (code ${String(outcome.code)}, signal ${String(outcome.signal)})`)
  if (outcome.code !== 0) throw new Error(`the app exited with code ${String(outcome.code)}`)
  if (problems.length > 0) throw new Error(`page problems:\n  ${problems.join('\n  ')}`)
  console.log('check-packed: passed')
} catch (error) {
  failed = true
  console.error(`check-packed: FAILED: ${error instanceof Error ? error.message : String(error)}`)
}
stopChildren()
await new Promise(resolve => updateFeed.close(resolve))
await new Promise(resolve => browserFixture.close(resolve))
await sleep(500)
rmSync(work, { recursive: true, force: true, maxRetries: 10, retryDelay: 500 })
process.exit(failed ? 1 : 0)
