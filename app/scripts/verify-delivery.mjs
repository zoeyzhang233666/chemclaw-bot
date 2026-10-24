import { app, BrowserWindow, session } from 'electron'
import assert from 'node:assert/strict'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

app.whenReady().then(async () => {
const folder = resolve('../chemclaw/verification')
mkdirSync(folder, { recursive: true })
const blocked = []
session.defaultSession.webRequest.onBeforeRequest((details, done) => {
  const remote = /^https?:/.test(details.url)
  if (remote) blocked.push(details.url)
  done({ cancel: remote })
})
const win = new BrowserWindow({ width: 1320, height: 940, show: false, webPreferences: { sandbox: true, contextIsolation: true } })
const errors = []
win.webContents.on('console-message', event => { if (/error|not defined|failed/i.test(event.message)) errors.push(event.message) })
try {
  await win.loadFile(resolve(folder, 'deliverables/验收样例 sample.html'))
  await delay(700)
  const state = await win.webContents.executeJavaScript(`({ title: document.title, charts: document.querySelectorAll('.chart').length, svgs: document.querySelectorAll('.chart svg').length, canvases: document.querySelectorAll('.chart canvas').length, mapPaths: document.querySelector('#chart-2').querySelectorAll('path').length, overflow: document.documentElement.scrollWidth > innerWidth })`)
  assert.equal(state.charts, 3); assert.ok(state.svgs >= 2); assert.ok(state.canvases > 0); assert.ok(state.mapPaths > 2); assert.equal(state.overflow, false)
  writeFileSync(resolve(folder, 'report-desktop.png'), (await win.webContents.capturePage()).toPNG())
  writeFileSync(resolve(folder, 'report-printed.pdf'), await win.webContents.printToPDF({ printBackground: true, preferCSSPageSize: true }))
  await win.webContents.executeJavaScript(`document.getElementById('filter').value='2026-10-22';document.getElementById('filter').dispatchEvent(new Event('input'))`)
  assert.equal(await win.webContents.executeJavaScript(`document.querySelectorAll('tbody tr:not([hidden])').length`), 1)
  win.setSize(430, 900); await delay(400)
  assert.equal(await win.webContents.executeJavaScript(`document.documentElement.scrollWidth > innerWidth`), false)
  writeFileSync(resolve(folder, 'report-mobile.png'), (await win.webContents.capturePage()).toPNG())
  assert.deepEqual(blocked, []); assert.deepEqual(errors, [])
  writeFileSync(resolve(folder, 'delivery-browser-check.json'), JSON.stringify({ ...state, remoteRequests: blocked.length, errors, filtering: true, mobile: true, print: true }, null, 2))
  console.log('Offline delivery: charts, map, filter, responsive layout and PDF print passed')
} catch (error) { console.error(error); process.exitCode = 1 }
finally { win.destroy(); app.quit() }
}).catch(error => { console.error(error); app.exit(1) })
