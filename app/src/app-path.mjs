import { realpathSync, statSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

// Electron caches Helper paths. After a live bundle move, creating a renderer
// can hit a native CHECK before any JavaScript error handler can run.
export function watchAppPath({ app, platform = process.platform, packaged = app.isPackaged,
  execPath = process.execPath, intervalMs = 1000, onInvalid, report = console.error,
}) {
  const enabled = platform === 'darwin' && packaged
  const bound = new Map()
  let baseline
  let problem
  let timer
  let disposed = false
  const snapshot = () => [execPath, dirname(dirname(dirname(execPath)))].map(path => {
    const stat = statSync(path)
    return { real: realpathSync.native(path), dev: stat.dev, ino: stat.ino, size: stat.isFile() ? stat.size : undefined, modified: stat.isFile() ? stat.mtimeMs : undefined }
  })
  if (enabled) {
    try { baseline = JSON.stringify(snapshot()) } catch { /* check() reports a failed startup without creating a window. */ }
  }
  const check = () => {
    if (!enabled) return true
    if (disposed || problem) return false
    try { if (baseline !== undefined && JSON.stringify(snapshot()) === baseline) return true } catch { /* A moved or replaced bundle is unavailable. */ }
    problem = Object.assign(new Error('ChemClaw was moved or replaced. Quit and reopen it from Applications.'), { code: 'CHEMCLAW_APP_PATH_CHANGED' })
    clearInterval(timer)
    for (const contents of bound.keys()) {
      try { if (!contents.isDestroyed()) contents.stop() } catch { /* Already closing. */ }
    }
    try { Promise.resolve(onInvalid(problem)).catch(report) } catch (error) { report(error) }
    return false
  }
  const assertAvailable = () => { if (!check()) throw problem ?? new Error('ChemClaw is closing.') }
  const bind = contents => {
    if (!enabled || disposed || bound.has(contents)) return
    const prevent = event => { if (!check()) event.preventDefault() }
    const events = ['will-frame-navigate', 'will-navigate', 'will-redirect', 'will-attach-webview']
    const remove = () => {
      for (const name of events) contents.off(name, prevent)
      contents.off('destroyed', remove)
      bound.delete(contents)
    }
    bound.set(contents, remove)
    for (const name of events) contents.on(name, prevent)
    contents.once('destroyed', remove)
    if (!check()) { try { contents.stop() } catch { /* Already closing. */ } }
  }
  const created = (_event, contents) => bind(contents)
  const dispose = () => {
    disposed = true
    clearInterval(timer)
    app.off('web-contents-created', created)
    for (const remove of [...bound.values()]) remove()
  }
  if (enabled) {
    app.on('web-contents-created', created)
    if (intervalMs > 0) { timer = setInterval(check, intervalMs); timer.unref() }
  }
  return { check, assertAvailable, bind, dispose }
}
