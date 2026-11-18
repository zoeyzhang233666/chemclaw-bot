import assert from 'node:assert/strict'
import { test } from 'node:test'
import { install } from '../src/host/desktop-runtime.js'
import { fakeContext } from './fake-ctx.js'

const executable = '/Applications/ChemClaw.app/Contents/MacOS/ChemClaw'
function start({ desktop = true, app = executable } = {}) {
  const ctx = fakeContext()
  install({ ctx }, { env: desktop ? { DS_BOT_APP: '1' } : {}, executable: app })
  const execute = ctx.listeners.get('tools/execute')?.[0]
  const session = { id: 'ordinary-agent' }
  const exec = command => ({ name: 'bash', arguments: { command }, agent: { id: session.id, session } })
  const event = (target, type) => ctx.listeners.get('session/event')[0](target, { type })
  return { ctx, execute, session, exec, event }
}

test('desktop guidance reaches ordinary Agent Sessions and Bots without claiming browser availability', () => {
  const { ctx } = start()
  const section = ctx.sections.get('chemclaw-desktop-runtime')
  for (const id of ['ordinary-agent', 'bot', 'group-member']) {
    const text = section.text({ agent: { id } })
    assert.match(text, /Ordinary Agent Sessions may have no browser tools/)
    assert.match(text, /load_workspace_dependencies/)
    assert.match(text, /rendering and screenshots were not verified/)
    assert.match(text, /drawn approximation is not a browser screenshot/)
  }
  assert.equal(start({ desktop: false }).ctx.listeners.size, 0)
})

test('the observed inline and script-writing private binding probes stop before shell execution', async () => {
  const { execute, exec } = start()
  for (const binding of ['electron_browser_app', 'electron_browser_window']) {
    for (const command of [
      `ELECTRON_RUN_AS_NODE=1 "${executable}" -e "process._linkedBinding('${binding}')"`,
      `cat > main.js <<'JS'\ntry { process._linkedBinding('${binding}') } catch {}\nJS\n"${executable}" app3`,
    ]) {
      let ran = false
      await assert.rejects(execute(exec(command), async () => { ran = true }), { code: 'CHEMCLAW_UNSUPPORTED_BROWSER_RUNTIME' })
      assert.equal(ran, false)
    }
  }
  await assert.rejects(execute(exec(`"${executable}" -e "require('electron/js2c/browser_init')"`), async () => assert.fail('must not spawn')))
})

test('ordinary Node, Python, Office, browser tools and source edits remain usable', async () => {
  const { execute, exec } = start()
  const success = { isError: false, content: [{ type: 'text', text: 'ok' }] }
  for (const command of [
    'node --check page.js', 'python3 build.py',
    `ELECTRON_RUN_AS_NODE=1 "${executable}" office.js convert --input report.docx`,
    `"${executable}" -e "console.log(process.version)"`,
    `cat > notes.md <<'EOF'\nprocess._linkedBinding('electron_browser_app')\nEOF`,
  ]) assert.equal(await execute(exec(command), async () => success), success)
  assert.equal(await execute({ ...exec(''), name: 'browser_screenshot' }, async () => success), success)
})

test('Windows paths and PowerShell probes receive the same protection', async () => {
  const app = 'C:\\Apps\\ChemClaw\\ChemClaw.exe'
  const { execute, exec } = start({ app })
  for (const path of [app, app.replaceAll('\\', '/'), JSON.stringify(app)]) {
    await assert.rejects(execute({ ...exec(`& ${path} -e "process._linkedBinding('electron_browser_app')"`), name: 'pwsh' }, async () => assert.fail('must not spawn')), { code: 'CHEMCLAW_UNSUPPORTED_BROWSER_RUNTIME' })
  }
})

test('an indirect native failure is returned once, then repeated application launches stop for that turn', async () => {
  const { execute, exec, event, session } = start()
  const command = `"${executable}" app3`
  const failed = { isError: true, content: [{ type: 'text', text: 'code=139\nbash: Segmentation fault: 11' }] }
  assert.equal(await execute(exec(command), async () => failed), failed)
  await assert.rejects(execute(exec(command), async () => assert.fail('must not repeat')), { code: 'CHEMCLAW_UNSUPPORTED_BROWSER_RUNTIME' })
  const success = { content: [{ type: 'text', text: 'ok' }] }
  assert.equal(await execute(exec('python3 build.py'), async () => success), success)
  const other = { ...exec(command), agent: { session: { id: 'other-agent' } } }
  assert.equal(await execute(other, async () => success), success)
  event(session, 'turn/start')
  assert.equal(await execute(exec(command), async () => success), success)
})

test('late failures and non-native JavaScript errors do not block a new turn', async () => {
  const { execute, exec, event, session } = start()
  const command = `"${executable}" script.js`
  let finish
  const pending = execute(exec(command), () => new Promise(resolve => { finish = resolve }))
  event(session, 'turn/start')
  finish({ content: [{ type: 'text', text: 'SIGSEGV' }] })
  await pending
  const jsError = { content: [{ type: 'text', text: 'TypeError: undefined' }] }
  assert.equal(await execute(exec(command), async () => jsError), jsError)
  assert.equal(await execute(exec(command), async () => jsError), jsError)
})

test('thrown native failures stop retries and return no command or environment data', async () => {
  const { execute, exec } = start()
  await assert.rejects(execute(exec(`"${executable}" script.js`), async () => { throw new Error('SIGSEGV') }), /SIGSEGV/)
  await assert.rejects(execute(exec(`PRIVATE_TOKEN=do-not-copy "${executable}" app3`), async () => assert.fail('must not repeat')), error => {
    assert.equal(error.code, 'CHEMCLAW_UNSUPPORTED_BROWSER_RUNTIME')
    assert.doesNotMatch(error.message, /PRIVATE_TOKEN|do-not-copy|Applications/)
    return true
  })
})
