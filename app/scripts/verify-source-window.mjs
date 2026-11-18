// Exercise the real app with isolated data and verify native window visibility.
import assert from 'node:assert/strict'
import { app, BrowserWindow } from 'electron'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

if (!process.env.DS_BOT_HOME || !process.env.DS_BOT_SHELL_DATA) throw new Error('Set isolated test folders first')
app.setAppPath(resolve(dirname(fileURLToPath(import.meta.url)), '..'))
let checked = false
let exitCode = 0
app.once('will-quit', () => { app.exit(exitCode) })
const timeout = setTimeout(() => {
  console.error('Source window did not become visible within 60 seconds')
  exitCode = 1
  app.quit()
}, 60_000)
app.on('browser-window-created', (_event, window) => {
  window.webContents.on('did-finish-load', () => {
    if (checked || !/^http:\/\/127\.0\.0\.1:\d+\//u.test(window.webContents.getURL())) return
    checked = true
    setTimeout(async () => {
      try {
        assert.ok(window.isVisible(), 'the desktop window must be visible')
        assert.equal(window.isMinimized(), false)
        assert.equal(BrowserWindow.getAllWindows().length, 1)
        console.log('Source GUI: native window visible, not minimized, local application loaded')
      } catch (error) { console.error(error); exitCode = 1 }
      finally { clearTimeout(timeout); app.quit() }
    }, 700)
  })
})
await import('../src/main.mjs')
