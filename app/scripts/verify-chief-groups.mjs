// Run with Electron after scripts/launch-chemclaw.mjs --sync-only. All data and
// screenshots belong to a fresh .dsh-test- folder, never the user's application.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { fileURLToPath } from 'node:url'
import { app } from 'electron'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const bench = join(root, `.dsh-test-chief-ui-${Date.now()}`)
const home = join(bench, 'data')
const shots = join(bench, 'screenshots')
mkdirSync(shots, { recursive: true })
for (const key of Object.keys(process.env)) if (/KEY|TOKEN|PASSWORD|SECRET/i.test(key)) delete process.env[key]
Object.assign(process.env, { DSH_HOME: home, DS_BOT_HOME: home, DS_BOT_SHELL_DATA: join(bench, 'shell'), DS_BOT_WORKSPACE: join(bench, 'workspace') })
app.setAppPath(join(root, 'app'))
app.disableHardwareAcceleration()
const mock = spawn(process.execPath, [join(root, 'chemclaw-bot/dev/mock-llm.mjs')], {
  env: { ...process.env, ELECTRON_RUN_AS_NODE: '1', MOCK_PORT: '0', MOCK_LOG: join(bench, 'mock.jsonl') },
  windowsHide: true, stdio: ['ignore', 'pipe', 'inherit'],
})
process.once('exit', () => mock.kill())
const base = await new Promise((resolve, reject) => {
  let output = ''
  mock.stdout.on('data', chunk => { output += chunk; const url = output.match(/http:\/\/127\.0\.0\.1:\d+\/v1/u)?.[0]; if (url) resolve(url) })
  mock.once('error', reject)
  mock.once('exit', code => reject(new Error(`Mock stopped: ${code}`)))
})
Object.assign(process.env, { DEEPSEEK_API_KEY: 'mock-key', DEEPSEEK_BASE_URL: base })
const { initProfile } = await import('@deepseek-ai/dsh-app-boot')
const profile = join(home, 'profiles/chemclaw')
initProfile(profile, ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', 'chemclaw-bot'])
writeFileSync(join(profile, 'cordis.patch.yml'), '- id: chemclaw\n  config:\n    companyConnectors: false\n    updateCheck: false\n- id: session-log-deepseek\n  disabled: true\n- id: session-telemetry-otel\n  disabled: true\n')

let checked = false
let exitCode = 0
app.once('will-quit', () => { mock.kill(); app.exit(exitCode) })
const timeout = setTimeout(() => { console.error('Chief group UI check timed out'); exitCode = 1; app.quit() }, 120_000)
app.on('browser-window-created', (_event, window) => {
  window.webContents.on('did-finish-load', async () => {
    if (checked || !/^http:\/\/127\.0\.0\.1:\d+\//u.test(window.webContents.getURL())) return
    checked = true
    const run = expression => window.webContents.executeJavaScript(expression, true)
    const waitFor = async expression => {
      const until = Date.now() + 40_000
      while (Date.now() < until) { if (await run(expression)) return; await delay(200) }
      throw new Error(`UI condition timed out: ${expression}`)
    }
    const shot = async name => { await delay(350); writeFileSync(join(shots, `${name}.png`), (await window.webContents.capturePage()).toPNG()) }
    try {
      await waitFor(`document.querySelectorAll('[data-room-id]').length === 15 && document.querySelectorAll('[data-bot-id]').length === 50`)
      const roster = await run(`fetch('api/bot', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({endpoint:'state',payload:{}})}).then(r=>r.json()).then(r=>r.value)`)
      const chief = roster.bots.find(bot => bot.templateId === 'chemclaw')
      assert.ok(chief)
      assert.equal(roster.mainBotIds.includes(chief.id), true)
      for (const room of roster.rooms) {
        assert.equal(room.members.filter(id => id === chief.id).length, 1)
        assert.notEqual(room.admin, chief.id)
        assert.equal(room.mode, 'admin')
      }
      for (const room of [roster.rooms[0], roster.rooms.find(room => room.templateId === 'scene-10')]) {
        await run(`document.querySelector(${JSON.stringify(`[data-room-id="${room.id}"]`)}).click()`)
        await waitFor(`document.querySelector('.bt-pill-name')?.textContent === ${JSON.stringify(room.name)}`)
        await run(`fetch('api/bot',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({endpoint:'warm-room',payload:{roomId:${JSON.stringify(room.id)}}})}).then(r=>r.json())`)
        await run(`document.querySelector('.bt-pill').click()`)
        await waitFor(`Array.from(document.querySelectorAll('.bt-member-name')).some(el=>el.textContent===${JSON.stringify(chief.name)})`)
        const admin = roster.bots.find(bot => bot.id === room.admin)
        assert.equal(await run(`Array.from(document.querySelectorAll('.bt-member')).some(el=>el.textContent.includes(${JSON.stringify(admin.name)})&&el.querySelector('.bt-tag'))`), true)
        await shot(`members-${room.templateId}`)
        await run(`document.querySelector('.bt-pill').click()`)
        await waitFor(`!document.querySelector('.bt-panel:not([data-leaving])')`)
      }
      await run(`Array.from(document.querySelectorAll('[role=textbox][contenteditable=true],textarea')).at(-1).focus()`)
      window.webContents.insertText('@Chem')
      await waitFor(`Array.from(document.querySelectorAll('[role=option]')).some(el=>el.textContent.includes(${JSON.stringify(chief.name)}))`)
      await shot('mention-menu')
      console.log(`Chief group UI passed: 50 Bots, 15 specialist-led groups, coordinator member and mention menu. Screenshots: ${shots}`)
    } catch (error) {
      console.error(error)
      exitCode = 1
      await shot('failure').catch(() => {})
    } finally { clearTimeout(timeout); app.quit() }
  })
})
await import('../src/main.mjs')
