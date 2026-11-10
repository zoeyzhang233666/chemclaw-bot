import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { isAbsolute, join, relative, resolve, sep } from 'node:path'
import { test } from 'node:test'
import { watchAppPath } from '../src/app-path.mjs'

function fixture(t, options = {}) {
  const parent = resolve(tmpdir()), root = mkdtempSync(join(parent, 'chemclaw-app-path-'))
  const bundle = join(root, 'ChemClaw.app'), executable = join(bundle, 'Contents', 'MacOS', 'ChemClaw')
  mkdirSync(join(bundle, 'Contents', 'MacOS'), { recursive: true })
  writeFileSync(executable, 'synthetic executable, never run')
  const app = new EventEmitter(), errors = []
  const guard = watchAppPath({ app, execPath: executable, platform: 'darwin', packaged: true, intervalMs: 0, onInvalid: error => errors.push(error), ...options })
  t.after(() => {
    guard.dispose()
    const part = relative(parent, resolve(root))
    assert.ok(part && part !== '..' && !part.startsWith(`..${sep}`) && !isAbsolute(part))
    rmSync(root, { recursive: true, force: true })
  })
  return { root, bundle, executable, app, errors, guard, move: () => renameSync(bundle, join(root, 'Moved.app')) }
}

function contents() {
  return Object.assign(new EventEmitter(), { isDestroyed: () => false, stops: 0, stop() { this.stops += 1 } })
}

test('unchanged bundle stays available; saved data is outside the guard', t => {
  const f = fixture(t)
  const history = join(f.root, 'synthetic-history.json')
  writeFileSync(history, '{"message":"saved"}')
  assert.equal(f.guard.check(), true)
  f.guard.assertAvailable()
  f.move()
  assert.throws(() => f.guard.assertAvailable(), { code: 'CHEMCLAW_APP_PATH_CHANGED' })
  assert.equal(readFileSync(history, 'utf8'), '{"message":"saved"}')
  assert.equal(f.errors.length, 1)
})

test('the first operation immediately after a live move fails without waiting for a timer', t => {
  const f = fixture(t)
  f.move()
  for (let i = 0; i < 3; i++) assert.throws(() => f.guard.assertAvailable(), { code: 'CHEMCLAW_APP_PATH_CHANGED' })
  assert.equal(f.errors.length, 1)
})

test('replacement at the same path is detected and the failure remains latched', t => {
  const f = fixture(t)
  f.move()
  mkdirSync(join(f.bundle, 'Contents', 'MacOS'), { recursive: true })
  writeFileSync(f.executable, 'replacement fixture')
  assert.equal(f.guard.check(), false)
  assert.equal(relative(f.root, f.bundle), 'ChemClaw.app')
  rmSync(f.bundle, { recursive: true })
  renameSync(join(f.root, 'Moved.app'), f.bundle)
  assert.equal(f.guard.check(), false)
  assert.equal(f.errors.length, 1)
})

test('renderer iframe navigation and webview attachment are cancelled after a move', t => {
  const f = fixture(t), page = contents()
  f.app.emit('web-contents-created', {}, page)
  let prevented = 0
  page.emit('will-frame-navigate', { preventDefault: () => { prevented += 1 } })
  assert.equal(prevented, 0)
  f.move()
  for (const name of ['will-frame-navigate', 'will-navigate', 'will-redirect', 'will-attach-webview']) {
    page.emit(name, { preventDefault: () => { prevented += 1 } })
  }
  assert.equal(prevented, 4)
  assert.equal(page.stops, 1)
  assert.equal(f.errors.length, 1)
})

test('idle polling detects a moved bundle without a browser action', async t => {
  const f = fixture(t, { intervalMs: 5 })
  f.move()
  const end = Date.now() + 1000
  while (f.errors.length === 0 && Date.now() < end) await new Promise(done => setTimeout(done, 5))
  assert.equal(f.errors.length, 1)
})

test('a fresh process can use the new location after the old process disposes', t => {
  const f = fixture(t)
  f.move()
  assert.equal(f.guard.check(), false)
  f.guard.dispose()
  const reopened = watchAppPath({ app: f.app, execPath: join(f.root, 'Moved.app', 'Contents', 'MacOS', 'ChemClaw'), platform: 'darwin', packaged: true, intervalMs: 0, onInvalid: error => { throw error } })
  t.after(() => reopened.dispose())
  assert.equal(reopened.check(), true)
})

test('disposing removes app and page listeners', t => {
  const f = fixture(t), page = contents()
  f.guard.bind(page)
  assert.equal(page.listenerCount('will-frame-navigate'), 1)
  f.guard.dispose()
  assert.equal(page.listenerCount('will-frame-navigate'), 0)
  assert.equal(f.app.listenerCount('web-contents-created'), 0)
})

test('Windows and development runs do not inspect Mac bundle paths', t => {
  for (const options of [{ platform: 'win32' }, { packaged: false }]) {
    const f = fixture(t, options)
    f.move()
    assert.equal(f.guard.check(), true)
    f.guard.assertAvailable()
    assert.deepEqual(f.errors, [])
    assert.equal(f.app.listenerCount('web-contents-created'), 0)
  }
})

test('a missing executable at startup fails closed without creating web contents', t => {
  const f = fixture(t)
  const missing = watchAppPath({ app: f.app, platform: 'darwin', packaged: true, execPath: join(f.root, 'missing.app', 'Contents', 'MacOS', 'ChemClaw'), intervalMs: 0, onInvalid: error => f.errors.push(error) })
  t.after(() => missing.dispose())
  assert.equal(missing.check(), false)
  assert.equal(f.errors.length, 1)
  assert.equal(existsSync(f.executable), true)
})

test('an isolated data home does not disable packaged Mac path protection', t => {
  const previous = process.env.DS_BOT_HOME
  process.env.DS_BOT_HOME = join(tmpdir(), 'synthetic-app-path-home')
  t.after(() => {
    if (previous === undefined) delete process.env.DS_BOT_HOME
    else process.env.DS_BOT_HOME = previous
  })
  const f = fixture(t)
  f.move()
  assert.throws(() => f.guard.assertAvailable(), { code: 'CHEMCLAW_APP_PATH_CHANGED' })
  assert.equal(f.errors.length, 1)
})
