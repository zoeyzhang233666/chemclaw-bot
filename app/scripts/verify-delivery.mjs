// Generic browser QA for a model-authored webpage; never a template generator.
import { app, BrowserWindow, session } from 'electron'
import assert from 'node:assert/strict'
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

app.whenReady().then(async () => {
  const file = process.argv[2] ?? process.env.CHEMCLAW_HTML_TO_VERIFY
  if (!file) throw new Error('Usage: electron app/scripts/verify-delivery.mjs <authored.html>')
  const blocked = []
  const errors = []
  session.defaultSession.webRequest.onBeforeRequest((details, done) => {
    const remote = /^https?:/.test(details.url)
    if (remote) blocked.push(details.url)
    done({ cancel: remote })
  })
  const win = new BrowserWindow({ width: 1320, height: 940, show: false, webPreferences: { sandbox: true, contextIsolation: true } })
  win.webContents.on('console-message', event => {
    if (/error|not defined|failed/i.test(event.message)) errors.push(event.message)
  })
  try {
    await win.loadFile(resolve(file))
    await delay(700)
    const desktop = await win.webContents.executeJavaScript(`({
      title: document.title,
      contentLength: document.body.innerText.trim().length,
      visuals: document.querySelectorAll('canvas,svg').length,
      overflow: document.documentElement.scrollWidth > innerWidth
    })`)
    assert.ok(desktop.contentLength > 0)
    assert.equal(desktop.overflow, false)
    writeFileSync(resolve('report-desktop.png'), (await win.webContents.capturePage()).toPNG())
    writeFileSync(resolve('report-printed.pdf'), await win.webContents.printToPDF({ printBackground: true, preferCSSPageSize: true }))
    win.setSize(430, 900)
    await delay(400)
    const mobileOverflow = await win.webContents.executeJavaScript('document.documentElement.scrollWidth > innerWidth')
    assert.equal(mobileOverflow, false)
    writeFileSync(resolve('report-mobile.png'), (await win.webContents.capturePage()).toPNG())
    assert.deepEqual(blocked, [])
    assert.deepEqual(errors, [])
    console.log(JSON.stringify({ ...desktop, mobileOverflow, remoteRequests: blocked.length, errors }, null, 2))
    console.log('Review screenshots and verify the data marks and interactions required by this particular report.')
  } catch (error) {
    console.error(error)
    process.exitCode = 1
  } finally {
    win.destroy()
    app.quit()
  }
}).catch(error => { console.error(error); app.exit(1) })
