// Run with Electron, using only throwaway data and a local fixture. No model or credentials.
import assert from 'node:assert/strict'
import { app, BrowserWindow, WebContentsView, session } from 'electron'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:http'
import { join, resolve } from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { BotBrowserGuests } from '../src/bot-browser.mjs'
import { BotViews } from '../src/bot-views.mjs'
import { openBotBrowser } from '../../chemclaw-bot/src/host/browser/session.js'
import { gateScope } from '../../chemclaw-bot/src/host/browser/gate.js'

const root = fileURLToPath(new URL('../../', import.meta.url))
const work = mkdtempSync(join(root, '.dsh-test-browser-runtime-'))
mkdirSync(join(work, 'shell'))
app.setPath('userData', join(work, 'shell'))
app.disableHardwareAcceleration()
const timer = setTimeout(() => { console.error('browser-check: timed out'); app.exit(1) }, 120_000)
let posts = 0
let deletes = 0
const fixture = createServer((request, response) => {
  if (request.url === '/report') { response.setHeader('content-disposition', 'attachment; filename=report.txt'); response.end('fixture-report'); return }
  if (request.url === '/delete') { deletes += 1; response.end('Deleted'); return }
  if (request.method === 'POST') { posts += 1; response.end('<h1>Saved</h1>'); return }
  response.setHeader('content-type', 'text/html; charset=utf-8')
  response.end(`<!doctype html><title>Browser fixture</title><h1>Supplier directory</h1>
    <form method="get"><label>Company <input name="company"></label><button>Search</button></form>
    <form method="post"><button>Confirm</button></form>
    <label>Password <input type="password" autocomplete="current-password"></label>
    <button aria-label="Pay now">Pay now</button>
    <a href="/second" target="_blank">Second page</a>
    <button onclick="fetch('/delete', {method:'POST'}).then(() => document.querySelector('#status').textContent='Deleted')">Delete item</button>
    <label>Upload file <input type="file" onchange="document.querySelector('#status').textContent=this.files[0].name"></label>
    <a href="/report">Download report</a><p id="status"></p>`)
})
const live = []
let views
let window
let held = null
const require = createRequire(import.meta.url)
const options = () => ({ playwrightUrl: pathToFileURL(require.resolve('playwright-core')).href, botId: 'bot-a', profileRoot: join(work, 'profiles'),
  downloadDir: work, uploadRoots: async () => [work],
  connect: id => views.endpoint(id, { downloadRoots: [work] }), getHold: () => held,
  onHold: value => { held = value },
})
const ref = (snapshot, label) => {
  const line = snapshot.split('\n').find(line => line.includes(label) && /\[ref=e\d+\]/u.test(line))
  assert.ok(line, `No ref for ${label}: ${snapshot}`)
  return /\[ref=(e\d+)\]/u.exec(line)[1]
}
const open = async value => { const browser = await openBotBrowser(value); live.push(browser); return browser }
async function check() {
  try {
    await app.whenReady()
    await new Promise(done => fixture.listen(0, '127.0.0.1', done))
    const url = `http://127.0.0.1:${fixture.address().port}/`
    window = new BrowserWindow({ show: false, webPreferences: { sandbox: true, contextIsolation: true } })
    await window.loadURL('about:blank')
    const guests = new BotBrowserGuests({ session, origin: () => 'http://127.0.0.1:43117', devTools: false })
    views = new BotViews({ window: () => window, WebContentsView, guests, origin: () => 'http://127.0.0.1:43117', statePath: join(work, 'views.json') })
    let browser = await open(options())
    let snapshot = await browser.open(url)
    assert.match(snapshot, /Supplier directory/u)
    snapshot = await browser.type(ref(snapshot, 'textbox "Company"'), 'ChemClaw')
    snapshot = await browser.click(ref(snapshot, 'button "Search"'))
    assert.match(snapshot, /company=ChemClaw/u)
    console.log('browser-check: navigation, ARIA refs, input and GET form passed')

    let approvals = 0
    await assert.rejects(gateScope.run(async () => { approvals += 1; throw new Error('Rejected by user') },
      () => browser.click(ref(snapshot, 'button "Confirm"'))), /Rejected by user/u)
    assert.equal(posts, 0)
    assert.equal(approvals, 1)
    snapshot = await browser.snapshotText()
    snapshot = await gateScope.run(async action => { assert.equal(action.kind, 'post'); approvals += 1 },
      () => browser.click(ref(snapshot, 'button "Confirm"')))
    assert.equal(posts, 1)
    assert.match(snapshot, /Saved/u)
    console.log('browser-check: rejected submission made no request; approved submission completed once')

    snapshot = await browser.open(url)
    await assert.rejects(browser.click(ref(snapshot, 'button "Pay now"')), /payment/u)
    await assert.rejects(browser.type(ref(snapshot, 'textbox "Password"'), 'fixture'), /entered by the user/u)
    browser.handoff('login', 'Please sign in')
    await assert.rejects(browser.open(url), /waiting for the user/u)
    held = null
    snapshot = await browser.open(url)
    assert.match(snapshot, /Supplier directory/u)
    console.log('browser-check: payment refusal and login handoff passed')

    let deleteRef = ref(snapshot, 'button "Delete item"')
    snapshot = await browser.click(deleteRef)
    assert.match(snapshot, /Nothing was deleted yet/u)
    assert.equal(deletes, 0)
    deleteRef = ref(snapshot, 'button "Delete item"')
    snapshot = await gateScope.run(async action => assert.equal(action.kind, 'delete'),
      () => browser.click(deleteRef, { confirm: true }))
    assert.equal(deletes, 1)

    const file = join(work, 'fixture.txt')
    writeFileSync(file, 'fixture-upload')
    snapshot = await browser.snapshotText()
    const upload = ref(snapshot, 'Upload file')
    await assert.rejects(gateScope.run(async () => { throw new Error('Upload rejected') },
      () => browser.upload(upload, [file])), /Upload rejected/u)
    snapshot = await gateScope.run(async action => assert.equal(action.kind, 'upload'), () => browser.upload(upload, [file]))
    assert.match(snapshot, /fixture.txt/u)

    const download = ref(snapshot, 'link "Download report"')
    const refused = await gateScope.run(async () => { throw new Error('Download rejected') }, () => browser.click(download))
    assert.match(refused, /Download rejected/u)
    assert.equal(existsSync(join(work, 'report.txt')), false)
    snapshot = await browser.snapshotText()
    const saved = await gateScope.run(async action => assert.equal(action.kind, 'download'),
      () => browser.click(ref(snapshot, 'link "Download report"')))
    assert.match(saved, /Downloaded "report.txt"/u)
    assert.equal(readFileSync(join(work, 'report.txt'), 'utf8'), 'fixture-report')
    console.log('browser-check: delete confirmation, upload approval and download approval passed')

    const entry = views.sync('bot-a')[0]
    // A harmless storage marker verifies isolation without reading or exporting cookies.
    await views.operate('bot-a', 'read', { tabId: entry.tabId, script: "localStorage.setItem('fixture-marker', 'bot-a'); true" })
    const other = await open({ ...options(), botId: 'bot-b' })
    await other.open(url)
    const otherEntry = views.sync('bot-b')[0]
    assert.equal(await views.operate('bot-b', 'read', { tabId: otherEntry.tabId, script: "localStorage.getItem('fixture-marker')" }), null)
    await assert.rejects(views.operate('bot-b', 'focus', { tabId: entry.tabId }), /does not belong/u)
    await browser.close()
    await views.close('bot-a', entry.tabId)
    browser = await open(options())
    await browser.open(url)
    const restored = views.sync('bot-a')[0]
    assert.equal(await views.operate('bot-a', 'read', { tabId: restored.tabId, script: "localStorage.getItem('fixture-marker')" }), 'bot-a')
    console.log('browser-check: persistent partition and cross-Bot isolation passed')

    held = { by: 'user' }
    await views.hold('bot-a', true)
    await assert.rejects(browser.open(url), /taken over/u)
    await assert.rejects(views.endpoint('bot-a'), /taken over/u)
    held = null
    await views.hold('bot-a', false)
    browser = await open(options())
    assert.match(await browser.open(url), /Supplier directory/u)
    assert.match(await other.snapshotText(), /Supplier directory/u)
    console.log('browser-check: takeover revokes control, give-back reconnects, other Bot stays usable')

    const image = await browser.shot()
    assert.ok(image.image)
    writeFileSync(join(work, 'browser.jpg'), Buffer.from(image.image, 'base64'))
    console.log(`browser-check: PASS; isolated evidence at ${resolve(work)}`)
  } catch (error) {
    console.error(error)
    process.exitCode = 1
  } finally {
    for (const browser of live) await browser.close().catch(() => {})
    views?.dispose()
    window?.destroy()
    fixture.closeAllConnections()
    await new Promise(done => fixture.close(done))
    clearTimeout(timer)
    app.exit(process.exitCode ?? 0)
  }

}
void check()
