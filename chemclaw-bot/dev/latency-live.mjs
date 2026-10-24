// Live APIHub TTFT bench: full preset team, real Flash route, isolated profile.
// Loads APIHUB_API_KEY from .chemclaw-dev credentials into process.env only — never logs it.
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs'
import { resolve, join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { setTimeout as delay } from 'node:timers/promises'

const root = resolve(import.meta.dirname, '../..')
const home = join(root, `.dsh-test-latency-live-${Date.now()}`)
mkdirSync(home)

function loadApiHubKey() {
  if (process.env.APIHUB_API_KEY) return true
  const candidates = [
    join(root, '.chemclaw-dev/data/.credentials.yaml'),
    join(process.env.USERPROFILE || process.env.HOME || '', '.dsh/.credentials.yaml'),
  ]
  for (const path of candidates) {
    if (!path || !existsSync(path)) continue
    const text = readFileSync(path, 'utf8')
    const match = text.match(/(?:^|\n)\s*APIHUB_API_KEY:\s*(.+?)\s*(?:\n|$)/)
    if (!match) continue
    let value = match[1].trim()
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1)
    }
    if (value.length < 4) continue
    process.env.APIHUB_API_KEY = value
    return true
  }
  return false
}

if (!loadApiHubKey()) {
  console.error('latency-live: APIHUB_API_KEY missing (set env or place it in .chemclaw-dev/data/.credentials.yaml)')
  process.exit(2)
}

for (const key of Object.keys(process.env)) {
  if (key === 'APIHUB_API_KEY') continue
  if (/KEY|TOKEN|PASSWORD|SECRET|DSH_WEB_/i.test(key)) delete process.env[key]
}
process.env.DSH_HOME = home

const require = createRequire(join(root, 'app/package.json'))
const electron = process.versions.electron ? await import('electron') : undefined
if (electron) await electron.app.whenReady()
let window
const boot = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-app-boot')))
const { runProfile } = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh/profile-boot')))

const portProbe = createServer()
await new Promise(resolve => portProbe.listen(0, '127.0.0.1', resolve))
const webPort = portProbe.address().port
await new Promise(resolve => portProbe.close(resolve))

const connectorsOff = process.env.LIVE_CONNECTORS !== '1'
const dir = join(home, 'profiles/latency-live')
boot.initProfile(dir, ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', 'chemclaw-bot'])
writeFileSync(join(dir, 'cordis.patch.yml'), `- id: chemclaw
  config:
    companyConnectors: ${connectorsOff ? 'false' : 'true'}
    updateCheck: false
    warmRooms: false
- id: llm-pi-ai
  config:
    providers:
      apihub:
        displayName: APIHub
        api: openai-completions
        baseURL: https://apihub.chem-cloud.cn/v1
        apiKeyEnv: APIHUB_API_KEY
        models:
          - { id: deepseek-v4.1-flash, contextWindow: 100000, maxTokens: 8000 }
- id: session-log-deepseek
  disabled: true
- id: session-telemetry-otel
  disabled: true
- id: workspace-changes
  disabled: true
`)

let running
let exitCode = 0
const results = []
try {
  running = await runProfile({
    environment: boot.loadLayeredEnv('dsh'),
    profile: 'latency-live',
    resolvedProfile: {
      profile: boot.loadProfileDirectory('dsh', dir, join(root, 'app/package.json')),
      installAnchor: join(root, 'app/package.json'),
    },
    args: ['--no-open', '--port', String(webPort)],
    patchFiles: [],
  })
  const ctx = running.ctx
  const connection = ctx.get('connection')
  const base = `http://127.0.0.1:${webPort}`
  const response = await fetch(connection.authenticatedUrl(base), { redirect: 'manual' })
  const cookie = response.headers.getSetCookie().map(value => value.split(';')[0]).join('; ')
  const api = async (endpoint, payload = {}) => {
    const response = await fetch(new URL('/api/bot', base), {
      method: 'POST',
      headers: { cookie, 'content-type': 'application/json' },
      body: JSON.stringify({ endpoint, payload }),
    })
    const result = await response.json()
    assert.ok(result.ok, `${endpoint}: ${result.error?.message}`)
    return result.value
  }

  const team = await api('state')
  console.log(JSON.stringify({
    event: 'ready',
    bots: team.bots.length,
    rooms: team.rooms.length,
    connectors: connectorsOff ? 'off' : 'on',
    keyPresent: true,
  }))
  assert.equal(team.bots.length, 50)
  assert.equal(team.rooms.length, 15)

  const bot = team.bots.find(b => b.templateId && !team.mainBotIds.includes(b.id))
  const room = team.rooms.find(r => r.members.includes(bot.id) && r.admin === bot.id) ?? team.rooms[0]
  for (const member of team.bots.filter(m => room.members.includes(m.id) || m.id === bot.id)) {
    await api('update-bot', { id: member.id, model: 'apihub/deepseek-v4.1-flash' })
  }

  if (electron) {
    window = new electron.BrowserWindow({
      show: false, width: 1280, height: 900,
      webPreferences: { contextIsolation: true, nodeIntegration: false, backgroundThrottling: false },
    })
    await window.loadURL(connection.authenticatedUrl(base))
    window.showInactive()
  }

  const assistantSeen = async (botId, beforeCount) => {
    const page = await api('chat', { botId })
    const parts = page?.parts ?? page?.items ?? page?.messages ?? []
    const texts = JSON.stringify(parts)
    return texts.length > beforeCount + 20 ? texts.length : 0
  }

  for (const [kind, id] of [['direct', bot.sessionId], ['group-cold', room.id], ['group-warm', room.id]]) {
    console.log(JSON.stringify({ event: 'case', kind }))
    if (window) {
      await window.webContents.executeJavaScript(
        `document.querySelector('[${kind === 'direct' ? 'data-bot-id' : 'data-room-id'}="${id}"]')?.click()`,
      )
      await delay(400)
    }
    if (kind === 'group-cold') await api('warm-room', { roomId: id })
    // Wait out a prior round so warm does not read leftover drafts as TTFT.
    // Committed replies may linger on the progress payload; only speaking/drafts block.
    if (kind !== 'direct') {
      const quietDeadline = Date.now() + 30_000
      for (;;) {
        const progress = await api('room-progress', { roomId: id })
        const busy = progress.some(p => p.speaking || p.drafts?.some(d => d.text))
        if (!busy) break
        if (Date.now() > quietDeadline) break
        await delay(100)
      }
      await delay(300)
    }

    const marker = `ping-${kind}-${Date.now()}`
    const baseline = kind === 'direct' ? JSON.stringify(await api('chat', { botId: bot.id })).length : 0
    const start = Date.now()
    let firstStatus, firstText, blankAfterDraft = 0, sawDraft = false
    const sent = api('send', { sessionId: id, text: `用一句话回复：${marker}` })
    const deadline = start + 120_000
    let sentDone = false
    void sent.then(() => { sentDone = true }).catch(() => { sentDone = true })
    for (;;) {
      if (kind === 'direct') {
        const grew = await assistantSeen(bot.id, baseline)
        if (grew && !firstText) firstText = Date.now() - start
        if (firstText !== undefined) break
        if (sentDone && Date.now() - start > 500) break
      } else {
        const progress = await api('room-progress', { roomId: id })
        if (progress.some(p => p.speaking) && !firstStatus) firstStatus = Date.now() - start
        const hasDraft = progress.some(p => p.drafts?.some(d => d.text))
        const hasReply = progress.some(p => p.replies?.some(r => r.text && r.kind === undefined))
        if ((hasDraft || hasReply) && !firstText) firstText = Date.now() - start
        if (hasDraft) sawDraft = true
        if (progress.length > 0 && sawDraft && !hasDraft && !hasReply) blankAfterDraft += 1
        if (hasReply) break
        if (sentDone && firstText !== undefined) break
      }
      if (Date.now() > deadline) throw new Error(`Timed out: ${kind}`)
      await delay(50)
    }
    await sent
    if (kind === 'direct' && firstText === undefined) {
      // chatPage may not grow until after send resolves; mark upper bound.
      firstText = Date.now() - start
    }
    if (kind !== 'direct') {
      assert.ok(firstText !== undefined, 'Group must show draft or reply text')
      assert.equal(blankAfterDraft, 0, 'Group draft must not blank before the committed reply')
    }
    const row = {
      kind,
      statusMs: firstStatus ?? null,
      firstDraftMs: firstText ?? null,
      handoffBlankPolls: blankAfterDraft,
      doneMs: Date.now() - start,
      connectors: connectorsOff ? 'off' : 'on',
    }
    results.push(row)
    console.log(JSON.stringify(row))
  }

  const warm = results.find(r => r.kind === 'group-warm')
  const direct = results.find(r => r.kind === 'direct')
  const cold = results.find(r => r.kind === 'group-cold')
  const warmGateMs = Number(process.env.LIVE_TTFT_GATE_MS || 2500)
  const coldGateMs = Number(process.env.LIVE_TTFT_COLD_GATE_MS || 8000)
  if (warm?.firstDraftMs != null) assert.ok(warm.firstDraftMs <= warmGateMs, `group-warm firstDraft ${warm.firstDraftMs}ms > ${warmGateMs}ms`)
  if (direct?.firstDraftMs != null) assert.ok(direct.firstDraftMs <= warmGateMs, `direct firstDraft ${direct.firstDraftMs}ms > ${warmGateMs}ms`)
  if (cold?.firstDraftMs != null) assert.ok(cold.firstDraftMs <= coldGateMs, `group-cold firstDraft ${cold.firstDraftMs}ms > ${coldGateMs}ms`)

  writeFileSync(join(root, 'chemclaw/verification/latency-live.json'), JSON.stringify({ live: true, connectors: connectorsOff ? 'off' : 'on', results }, null, 2))
} catch (error) {
  exitCode = 1
  console.error(error?.stack || error)
  writeFileSync(join(root, 'chemclaw/verification/latency-live.json'), JSON.stringify({ live: true, error: String(error?.message || error), results }, null, 2))
} finally {
  window?.destroy()
  await running?.shutdown.shutdown(exitCode)
  process.exitCode = exitCode
  electron?.app.exit(exitCode)
}
