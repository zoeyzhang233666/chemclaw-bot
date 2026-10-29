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
import { nativeOpenFixture } from './native-open-fixture.mjs'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const args = process.argv.slice(2).filter(arg => !arg.startsWith('--') || arg === '--source')
const flags = new Set(process.argv.slice(2).filter(arg => arg.startsWith('--')))
const given = args.find(arg => arg !== '--source')
const shotFile = args.filter(arg => arg !== '--source' && arg !== given).at(0)
const source = flags.has('--source') || given === '--source'
if (source) {
  const plugin = resolve(root, '../chemclaw-bot')
  const installed = dirname(createRequire(import.meta.url).resolve('chemclaw-bot/package.json'))
  if (resolve(installed) !== plugin) for (const path of ['package.json', 'index.js', 'client.js', 'NOTICE', 'src/host', 'src/shared', 'runtime']) cpSync(join(plugin, path), join(installed, path), { recursive: true })
}
const executable = source ? process.env.CHEMCLAW_TEST_ELECTRON || createRequire(import.meta.url)('electron') : given || packedExecutable()

function packedExecutable() {
  const out = join(root, 'dist-pack')
  if (process.platform === 'win32') return join(out, 'win-unpacked', 'ChemClaw.exe')
  if (process.platform === 'linux') return join(out, 'linux-unpacked', 'chemclaw')
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
mkdirSync(join(work, 'shell'))
writeFileSync(join(work, 'shell', 'tray-close-acknowledged'), '')
const nativeFixture = process.platform === 'linux' ? nativeOpenFixture(work) : undefined
const browserFixture = createServer((_request, response) => {
  response.setHeader('content-type', 'text/html; charset=utf-8')
  response.end('<!doctype html><title>ChemClaw Browser Check</title><h1>企业资料查询测试</h1><p>此网页仅用于隔离测试，无需登录。</p>')
})
const children = []
let updateRequests = 0
const updateFeed = createServer((request, response) => {
  updateRequests++
  // Manual updates (macOS and Linux deb/unpacked) request the GitHub releases API.
  const releases = request.headers.accept?.includes('application/vnd.github+json')
  response.setHeader('content-type', releases ? 'application/json' : 'text/yaml')
  response.end(releases ? '[]' : `version: 0.0.0\nfiles:\n  - url: unused.exe\n    sha512: ${Buffer.alloc(64).toString('base64')}\n`)
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

function checkSharp(app) {
  const resources = process.platform === 'darwin' ? resolve(app, '..', '..', 'Resources') : join(dirname(app), 'resources')
  const script = `
    const assert = require('node:assert/strict')
    const { createRequire } = require('node:module')
    const appRequire = createRequire(${JSON.stringify(join(resources, 'app.asar', 'package.json'))})
    const sharp = appRequire('sharp')
    if (process.platform === 'linux') assert.ok(sharp.versions.emscripten, 'Linux must use the packaged WASM backend')
    ;(async () => {
      const image = await sharp({ create: { width: 4, height: 4, channels: 3, background: '#ff0000' } }).png().toBuffer()
      const { data, info } = await sharp(image).resize(2, 2).removeAlpha().raw().toBuffer({ resolveWithObject: true })
      assert.equal(info.width, 2)
      assert.equal(info.height, 2)
      assert.deepEqual([...data], Array.from({ length: 4 }, () => [255, 0, 0]).flat())
      for (const format of ['jpeg', 'webp', 'gif', 'avif']) {
        const encoded = await sharp(image)[format]().toBuffer()
        const decoded = await sharp(encoded).resize(2, 2).raw().toBuffer({ resolveWithObject: true })
        assert.equal(decoded.info.width, 2, format)
        assert.equal(decoded.info.height, 2, format)
      }
      const svg = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"><rect width="4" height="4" fill="red"/></svg>')
      assert.equal((await sharp(await sharp(svg).png().toBuffer()).metadata()).width, 4)
      console.log('check-packed: sharp image processing passed (libvips ' + sharp.versions.vips + ')')
    })().catch(error => { console.error(error); process.exitCode = 1 })
  `
  // Use the shipped Electron and dependencies outside the checkout, just like the Host.
  const result = spawnSync(app, ['-e', script], {
    cwd: work, env: { ...process.env, ELECTRON_RUN_AS_NODE: '1', NODE_PATH: '' },
    encoding: 'utf8', timeout: 30_000,
  })
  if (result.error || result.status !== 0) throw new Error(`packaged sharp failed (exit ${String(result.status)}, signal ${String(result.signal)}): ${result.error?.message ?? ''}\n${result.stderr ?? ''}`)
  console.log(result.stdout.trim())
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
  return { opened, call, requests, close: () => new Promise(resolve => { socket.addEventListener('close', resolve, { once: true }); socket.close() }) }
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
  const evaluate = async expression => {
    const answer = await cdp.call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (answer.exceptionDetails) throw new Error(answer.exceptionDetails.exception?.description ?? answer.exceptionDetails.text)
    return answer.result.value
  }
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
  const openSettings = async () => {
    await until("document.querySelector('.bt-classic-settings, .bt-account')", 'the settings launcher')
    if (await evaluate("Boolean(document.querySelector('.bt-classic-settings'))")) {
      await evaluate("document.querySelector('.bt-classic-settings').click()")
    } else {
      if (!await evaluate("Boolean(document.querySelector('.bt-account-menu'))")) await evaluate("document.querySelector('.bt-account').click()")
      const item = "[...document.querySelectorAll('.bt-account-menu button')].find(node => /^(设置|Settings)$/.test(node.textContent.trim()))"
      await until(item, 'the account menu settings item')
      await evaluate(`${item}.click()`)
    }
    await until("document.querySelector('.bt-settings-nav')", 'settings')
  }
  await cdp.call('Runtime.enable')
  await cdp.call('Log.enable')
  await cdp.call('Network.enable')
  await cdp.call('Emulation.setFocusEmulationEnabled', { enabled: true })
  await until("document.querySelector('.bt-tile[data-bot-id], .bt-row[data-bot-id]')", 'the team')
  await until("!document.body.innerText.includes('正在设置主 Bot')", 'the coordinator')
  if (await evaluate("document.body.innerText.includes('预览版说明') || document.body.innerText.includes('Preview Notice')")) throw new Error('The independent app still shows upstream preview onboarding')
  const catalog = await evaluate("fetch('api/bot', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ endpoint: 'scenario-catalog', payload: {} }) }).then(r => r.json()).then(r => r.value)")
  if (catalog.roles.length !== 50 || catalog.groups.length !== 15) throw new Error('Incomplete scenario catalog')
  if (!source) {
    await until('window.dsBotApp?.updates', 'the desktop update bridge')
    const status = await evaluate('window.dsBotApp.updates.check()')
    if (!status.enabled || !status.checkedAt || status.phase === 'failed') throw new Error('The packaged app did not check its isolated update feed')
    await openSettings()
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
  await evaluate("document.querySelector('.bt-account').click()")
  const classicMode = "[...document.querySelectorAll('.bt-account-menu button')].find(node => /^(切换经典 Agent 模式|Switch to classic Agent mode)$/.test(node.textContent.trim()))"
  await until(classicMode, 'the classic Agent mode entry')
  await evaluate(`${classicMode}.click()`)
  await until("document.querySelector('.bt-classic-settings')", 'the classic settings button')
  await openSettings()
  await until("document.querySelector('.bt-look-seg')", 'classic mode appearance settings')
  await evaluate("document.querySelector('.bt-settings-close').click()")
  await until("!document.querySelector('.bt-settings')", 'classic settings to close')
  await evaluate("document.querySelector('.bt-return').click()")
  await until("document.querySelector('.bt-account')", 'the expert team account launcher')
  console.log('check-packed: classic Settings opened and returned to the expert team')
  if (shotFile && !process.argv.includes('--browser-shot-only')) {
    const capture = async suffix => { await sleep(650); const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' }); writeFileSync(resolve(`${shotFile}.${suffix}.png`), Buffer.from(data, 'base64')) }
    await capture('home')
    await openSettings()
    await evaluate("[...document.querySelectorAll('.bt-settings-item')].find(node => /^(专家|Experts)$/.test(node.textContent.trim())).click()")
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
  if (process.argv.includes('--office-preview-only') || process.argv.includes('--xlsx-preview-only')) {
    const wantXlsx = process.argv.includes('--xlsx-preview-only')
    const { deliver } = await import('../../chemclaw-bot/runtime/deliver.mjs')
    const formats = wantXlsx ? ['xlsx'] : ['pptx']
    const [file] = await deliver({ title: wantXlsx ? 'Excel预览隔离验收' : 'PPT预览隔离验收', filename: wantXlsx ? 'excel-preview-sample' : '中文演示 sample', summary: '合成验收内容，不是业务数据', sections: [
      { title: '合成数据', table: { columns: ['日期', '测试数值'], rows: [['2026-10-25', 100], ['2026-10-26', 102]] } },
    ] }, join(work, 'workspace'), formats)
    const original = readFileSync(file)
    await evaluate("[...document.querySelectorAll('[role=textbox][contenteditable=true], textarea')].filter(node => !node.closest('.bt-side')).at(-1).focus()")
    await cdp.call('Input.insertText', { text: `交付 ${file}` })
    await sleep(150)
    for (const type of ['keyDown', 'keyUp']) await cdp.call('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await until("document.querySelector('[data-presented-file] button[aria-label]')", 'the delivery card')
    await evaluate("document.querySelector('[data-presented-file] button[aria-label]').click()")
    if (wantXlsx) {
      await until("[...document.querySelectorAll('canvas')].some(node => { const rect = node.getBoundingClientRect(); return node.width > 200 && node.height > 200 && rect.width > 200 && rect.height > 200 }) && !/无法打开此表格|文件不存在/.test(document.body.innerText)", 'the rendered Excel grid')
      console.log('check-packed: actual Excel delivery card rendered a grid in the sidebar')
    } else {
      await until("[...document.querySelectorAll('canvas')].some(node => { const rect = node.getBoundingClientRect(); return node.width > 200 && node.height > 200 && rect.width > 200 && rect.height > 200 }) && !/Office 转换失败|文件不存在|Office conversion failed/.test(document.body.innerText)", 'the rendered PPT page')
      console.log('check-packed: actual PPT delivery card rendered a page in the sidebar')
    }
    if (!readFileSync(file).equals(original)) throw new Error('Preview changed the original Office file')
    return
  }
  if (process.argv.includes('--preview-only')) {
    await openSettings()
    await until("document.querySelector('.bt-look-seg')", 'the source layout controls')
    for (const label of ['消息布局', '气泡宽度', '显示思考过程']) {
      if (!await evaluate(text(label))) throw new Error(`The preview is missing ${label}`)
    }
    await evaluate("document.querySelectorAll('.bt-look-seg button')[1].click()")
    await until(text('正文宽度'), 'the source text width control')
    if (shotFile) { await sleep(300); const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' }); writeFileSync(resolve(`${shotFile}.settings.png`), Buffer.from(data, 'base64')) }
    await evaluate("[...document.querySelectorAll('.bt-settings-item')].find(node => /^(关于 ChemClaw|About ChemClaw)$/.test(node.textContent.trim())).click()")
    await until(text('开发预览'), 'the source revision in About')
    if (!await evaluate(`document.body.innerText.includes(${JSON.stringify(process.env.CHEMCLAW_SOURCE_REVISION)})`)) throw new Error('About does not identify the launched source revision')
    if (shotFile) { const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' }); writeFileSync(resolve(`${shotFile}.about.png`), Buffer.from(data, 'base64')) }
    console.log('check-packed: source layout controls and development revision passed')
    return
  }
  await evaluate("[...document.querySelectorAll('[role=textbox][contenteditable=true], textarea')].filter(node => !node.closest('.bt-side')).at(-1).focus()")
  await cdp.call('Input.insertText', { text: 'packaged app check' })
  await sleep(150)
  for (const type of ['keyDown', 'keyUp']) await cdp.call('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  // The mock model starts its reply with 收到： and the message.
  await until(text('收到：packaged app check'), 'the reply')
  await until('window.dsBotApp?.browser?.views', 'the native browser bridge')
  await evaluate("[...document.querySelectorAll('[role=textbox][contenteditable=true], textarea')].filter(node => !node.closest('.bt-side')).at(-1).focus()")
  await cdp.call('Input.insertText', { text: `浏览器检查 http://127.0.0.1:${browserFixture.address().port}/` })
  await sleep(150)
  for (const type of ['keyDown', 'keyUp']) await cdp.call('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  await until(text('浏览器检查完成：ChemClaw Browser Check'), 'the Bot browser tool through Host IPC')
  await evaluate("document.querySelector('.bt-pill').click()")
  const openBrowser = "[...document.querySelectorAll('button')].find(node => /^(Open browser|打开浏览器)$/.test(node.getAttribute('aria-label') || ''))"
  await until(openBrowser, 'the browser button')
  await evaluate(`${openBrowser}.click()`)
  await until("document.querySelector('.bt-browser-takeover')", 'the browser control bar')
  await until("typeof window.dsBotApp?.browser?.importSources === 'function'", 'the native login-import bridge')
  await until("document.querySelector('.bt-import-btn')", 'the login-import toolbar button')
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
    await sleep(150)
    for (const type of ['keyDown', 'keyUp']) await cdp.call('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  }
  await sendMain('长任务 6 1')
  await until(text('步骤0'), 'the active main task')
  await sendMain('/side 当前进展是什么？')
  await until("document.querySelector('.bt-side-input')", 'the side-chat panel')
  await until(text('Side note: 0 earlier pair(s) seen.'), 'the independent side answer')
  await evaluate("document.querySelector('.bt-side-input').focus()")
  await cdp.call('Input.insertText', { text: '继续解释一下' })
  await sleep(150)
  for (const type of ['keyDown', 'keyUp']) await cdp.call('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  await until(text('Side note: 1 earlier pair(s) seen.'), 'the side follow-up')
  await until(text('长任务做完了'), 'the main task completing without interruption')
  if (shotFile) {
    const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' })
    writeFileSync(resolve(`${shotFile}.side.png`), Buffer.from(data, 'base64'))
  }
  await evaluate("document.querySelector('.bt-ptab-close').click()")
  console.log('check-packed: /side and follow-up answered while the main task continued')

  await openSettings()
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

  const chartRoom = await evaluate(`fetch('api/bot', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ endpoint: 'state', payload: {} }) }).then(r => r.json()).then(async r => {
    const other = r.value.bots.find(bot => bot.id !== ${JSON.stringify(main)});
    const created = await fetch('api/bot', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ endpoint: 'create-room', payload: { name: '图表回答验收', members: [${JSON.stringify(main)}, other.id], admin: ${JSON.stringify(main)} } }) }).then(res => res.json());
    if (!created.ok) throw new Error(created.error?.message || 'Could not create chart test group');
    return { id: created.value.id, member: other.name };
  })`)
  const roomSelector = `[data-room-id="${chartRoom.id}"]`
  await until(`document.querySelector(${JSON.stringify(roomSelector)})`, 'the chart test group')
  await evaluate(`document.querySelector(${JSON.stringify(roomSelector)}).click()`)
  await sendMain(`@${chartRoom.member} 查询合成走势验证`)
  await until("document.querySelector('.bt-group-view .bt-chart-svg')", 'the completed member answer chart')
  const readableTicks = "(() => { const ticks = [...document.querySelectorAll('.bt-group-view .bt-chart-label')]; return ticks.length > 0 && ticks.every((node, at) => /^\\d{2}-\\d{2}$/.test(node.textContent) && (!at || node.getBoundingClientRect().left >= ticks[at - 1].getBoundingClientRect().right + 4)); })()"
  await until(readableTicks, 'readable dense chart dates')
  const hits = await evaluate("document.querySelectorAll('.bt-group-view .bt-chart-hit').length")
  if (hits !== 57) throw new Error('Thinning the axis removed observations')
  await evaluate("document.querySelectorAll('.bt-group-view .bt-chart-hit')[20].dispatchEvent(new PointerEvent('pointerover', { bubbles: true }))")
  await until("document.querySelector('.bt-chart-tip')?.textContent.includes('2026-09-21')", 'the complete hover date')
  if (!await evaluate("/缺失数据|No data/.test(document.querySelector('.bt-chart-tip').textContent)")) throw new Error('A missing chart point was converted to zero')
  await sleep(200)
  if (shotFile) { const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' }); writeFileSync(resolve(`${shotFile}.chart.png`), Buffer.from(data, 'base64')) }
  await cdp.call('Page.bringToFront')
  const rangeBox = await evaluate("(() => { const box = document.querySelector('.bt-chart-range-track').getBoundingClientRect(); return { x: box.x, y: box.y + box.height / 2, width: box.width }; })()")
  await cdp.call('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rangeBox.x, y: rangeBox.y })
  await cdp.call('Input.dispatchMouseEvent', { type: 'mousePressed', x: rangeBox.x, y: rangeBox.y, button: 'left', buttons: 1, clickCount: 1 })
  await sleep(100)
  await cdp.call('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rangeBox.x + rangeBox.width * 40 / 56, y: rangeBox.y, button: 'left', buttons: 1 })
  await sleep(100)
  await cdp.call('Input.dispatchMouseEvent', { type: 'mouseReleased', x: rangeBox.x + rangeBox.width * 40 / 56, y: rangeBox.y, button: 'left', buttons: 0, clickCount: 1 })
  await until("document.querySelectorAll('.bt-group-view .bt-chart-hit').length === 17", 'the zoomed chart range')
  if (shotFile) { const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' }); writeFileSync(resolve(`${shotFile}.chart-zoom.png`), Buffer.from(data, 'base64')) }
  const selectedBox = await evaluate("(() => { const box = document.querySelector('.bt-chart-range-window').getBoundingClientRect(); return { x: box.x + box.width / 2, y: box.y + box.height / 2 }; })()")
  await cdp.call('Input.dispatchMouseEvent', { type: 'mousePressed', x: selectedBox.x, y: selectedBox.y, button: 'left', buttons: 1, clickCount: 1 })
  await sleep(100)
  await cdp.call('Input.dispatchMouseEvent', { type: 'mouseMoved', x: selectedBox.x - rangeBox.width * 10 / 56, y: selectedBox.y, button: 'left', buttons: 1 })
  await sleep(100)
  await cdp.call('Input.dispatchMouseEvent', { type: 'mouseReleased', x: selectedBox.x - rangeBox.width * 10 / 56, y: selectedBox.y, button: 'left', buttons: 0, clickCount: 1 })
  await until("document.querySelector('.bt-chart-range-window').getAttribute('aria-valuenow') === '30'", 'the panned chart range')
  if (await evaluate("document.querySelectorAll('.bt-group-view .bt-chart-hit').length") !== 17) throw new Error('Panning changed the selected span')
  await evaluate("document.querySelector('.bt-chart-range-caption button').click()")
  await until("document.querySelectorAll('.bt-group-view .bt-chart-hit').length === 57", 'all observations restored')
  await cdp.call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await sleep(500)
  await until(readableTicks, 'readable mobile chart dates')
  if (shotFile) { const { data } = await cdp.call('Page.captureScreenshot', { format: 'png' }); writeFileSync(resolve(`${shotFile}.chart-mobile.png`), Buffer.from(data, 'base64')) }
  const touchBox = await evaluate("(() => { const box = document.querySelector('.bt-chart-range-track').getBoundingClientRect(); return { x: box.x, y: box.y + box.height / 2, width: box.width }; })()")
  await cdp.call('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: touchBox.x, y: touchBox.y }] })
  await sleep(100)
  await cdp.call('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: touchBox.x + touchBox.width * 10 / 56, y: touchBox.y }] })
  await sleep(100)
  await cdp.call('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  await until("document.querySelectorAll('.bt-group-view .bt-chart-hit').length === 47", 'the touch-selected chart range')
  await evaluate("document.querySelector('.bt-chart-range-caption button').click()")
  await cdp.call('Emulation.clearDeviceMetricsOverride')
  await cdp.call('Page.reload')
  await until(`document.querySelector(${JSON.stringify(roomSelector)})`, 'the group after reload')
  await evaluate(`document.querySelector(${JSON.stringify(roomSelector)}).click()`)
  await until("document.querySelectorAll('.bt-group-view .bt-chart-svg').length === 1", 'one persisted answer chart after reload')
  await evaluate(`document.querySelector(${JSON.stringify(`[data-bot-id="${main}"]`)}).click()`)
  await until(`document.querySelector(${JSON.stringify(`[data-bot-id="${main}"]`)})?.getAttribute('aria-current') === 'page' && !document.querySelector('.bt-group-view')`, 'the coordinator chat after the chart check')
  await sleep(300)
  console.log('check-packed: group @ answer chart, full hover dates, missing observations, range, mobile and reload passed')
  await evaluate("[...document.querySelectorAll('[role=textbox][contenteditable=true], textarea')].filter(node => !node.closest('.bt-side')).at(-1).focus()")
  await cdp.call('Input.insertText', { text: '要密钥 DEMO_THEME_TEST' })
  await sleep(100)
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
  await sleep(150)
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
  if (nativeFixture) {
    const received = nativeFixture.received()
    for (const path of [dirname(delivery), delivery]) {
      if (!received.includes(path)) throw new Error('The native desktop handler did not receive ' + path)
    }
    console.log('check-packed: Linux desktop handler received the exact reveal and open paths')
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
  const packedApp = source ? executable : outsideCheckout(resolve(executable))
  if (!source) checkSharp(packedApp)
  const modelUrl = await startMock()
  const port = 9300 + Math.floor(Math.random() * 600)
  // A terminal inside an Electron-based editor may set ELECTRON_RUN_AS_NODE, which turns the app into plain Node.
  const { ELECTRON_RUN_AS_NODE: _runAsNode, ...env } = process.env
  for (const key of Object.keys(env)) if (/KEY|TOKEN|PASSWORD|SECRET/i.test(key)) delete env[key]
  Object.assign(env, {
    ...nativeFixture?.env,
    DS_BOT_HOME: join(work, 'home'), DS_BOT_SHELL_DATA: join(work, 'shell'),
    DS_BOT_WORKSPACE: join(work, 'workspace'),
    DEEPSEEK_BASE_URL: modelUrl, DEEPSEEK_API_KEY: 'mock-key',
    CHEMCLAW_UPDATE_URL: `http://127.0.0.1:${updateFeed.address().port}/`,
  })
  // Intel macOS runners may have no working EGL display. Exercise the same
  // renderer with software compositing rather than repeatedly crashing its GPU.
  const graphics = process.env.CI && process.platform === 'darwin' ? ['--disable-gpu'] : []
  const app = spawn(packedApp, [...(source ? [root] : []), ...graphics, `--remote-debugging-port=${String(port)}`], { stdio: 'inherit', env, windowsHide: true })
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
  if (problems.length > 0) throw new Error(`page problems:\n  ${problems.join('\n  ')}`)
  await cdp.close()
  const browserTarget = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json()
  const quitSocket = new WebSocket(browserTarget.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { quitSocket.addEventListener('open', resolve, { once: true }); quitSocket.addEventListener('error', reject, { once: true }) })
  quitSocket.send(JSON.stringify({ id: 1, method: 'Browser.close' }))
  quitSocket.close()
  const outcome = await Promise.race([exited, sleep(40_000).then(() => undefined)])
  if (chatError) throw chatError
  if (outcome === undefined) throw new Error('the app did not exit after explicit quit')
  console.log(`check-packed: app exited (code ${String(outcome.code)}, signal ${String(outcome.signal)})`)
  if (outcome.code !== 0) throw new Error(`the app exited with code ${String(outcome.code)}`)
  if (problems.length > 0) throw new Error(`page problems:\n  ${problems.join('\n  ')}`)
  console.log('check-packed: passed')
} catch (error) {
  failed = true
  console.error(`check-packed: FAILED: ${error instanceof Error ? error.message : String(error)}`)
  if (problems.length) console.error(`check-packed: captured page problems:\n  ${problems.join('\n  ')}`)
}
stopChildren()
await new Promise(resolve => updateFeed.close(resolve))
await new Promise(resolve => browserFixture.close(resolve))
await sleep(500)
rmSync(work, { recursive: true, force: true, maxRetries: 10, retryDelay: 500 })
process.exit(failed ? 1 : 0)
