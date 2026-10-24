// Full preset team, OpenAI-compatible streaming, isolated profile; no real credentials.
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { fork } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve, join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { setTimeout as delay } from 'node:timers/promises'

const root = resolve(import.meta.dirname, '../..')
const home = join(root, `.dsh-test-latency-${Date.now()}`)
mkdirSync(home)
for (const key of Object.keys(process.env)) if (/KEY|TOKEN|PASSWORD|SECRET|DSH_WEB_/i.test(key)) delete process.env[key]
process.env.DSH_HOME = home
const require = createRequire(join(root, 'app/package.json'))
const live = process.env.CHEMCLAW_LIVE_LATENCY === '1'
const research = live && process.env.CHEMCLAW_LIVE_RESEARCH === '1'
// The explicitly requested live check reads only the saved model reference into
// memory. Never copy the credential document into the bench or record its contents.
const liveKey = live ? require('yaml').parse(readFileSync(join(root, '.chemclaw-dev/data/.credentials.yaml'), 'utf8')).refs?.APIHUB_API_KEY : undefined
if (live && !liveKey) throw new Error('APIHub credential is not configured in the source GUI')
const electron = process.versions.electron ? await import('electron') : undefined
if (electron) await electron.app.whenReady()
if (electron) electron.app.setPath('userData', join(home, 'shell'))
let window
const boot = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-app-boot')))
const { runProfile } = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh/profile-boot')))
const requests = []
const results = []
const toolCalls = []
const autoSkillLoads = []
const turnEnds = []
const mock = createServer(async (req, res) => {
  let raw = ''
  for await (const chunk of req) raw += chunk
  const body = JSON.parse(raw || '{}')
  if (!req.url.endsWith('/chat/completions')) { res.writeHead(404).end(); return }
  const record = {
    at: Date.now(), chars: raw.length, stream: body.stream === true, conversation: body.tools?.length > 0,
    toolCount: body.tools?.length ?? 0,
    toolNames: (body.tools ?? []).map(tool => tool.name ?? tool.function?.name ?? tool.type).filter(Boolean).slice(0, 80),
  }
  requests.push(record)
  record.skillCatalogs = (body.messages ?? []).flatMap(m => typeof m.content === 'string' ? [m.content] : []).filter(s => s.includes('<available_skills>')).map(s => ({ empty: s.includes('No skills are currently available'), chars: s.length }))
  if (live) {
    try {
      const upstream = await fetch('https://apihub.chem-cloud.cn/v1/chat/completions', {
        method: 'POST', headers: { 'content-type': 'application/json', Authorization: `Bearer ${liveKey}` },
        body: raw, signal: AbortSignal.timeout(90_000),
      })
      record.status = upstream.status
      res.writeHead(upstream.status, { 'content-type': upstream.headers.get('content-type') ?? 'application/json' })
      let pending = ''
      for await (const chunk of upstream.body) {
        record.first ??= Date.now()
        pending += Buffer.from(chunk).toString('utf8')
        const lines = pending.split('\n'); pending = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: {')) continue
          const delta = JSON.parse(line.slice(6)).choices?.[0]?.delta
          if (delta?.content) { record.firstText ??= Date.now(); record.preview = `${record.preview ?? ''}${delta.content}`.slice(0, 40) }
          if (delta?.reasoning_content) record.firstReasoning ??= Date.now()
        }
        res.write(chunk)
      }
      res.end(); record.end = Date.now()
    } catch { record.failed = true; record.end = Date.now(); res.destroy() }
    return
  }
  record.marker = `流式回复测试-${requests.length}`
  const text = record.conversation ? `这是${record.marker}。第一段应立即显示，后续内容逐步补充。完整回答结束。` : '[]'
  if (!body.stream) { res.setHeader('content-type', 'application/json'); res.end(JSON.stringify({ choices: [{ message: { role: 'assistant', content: text }, finish_reason: 'stop' }] })); return }
  res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' })
  const send = (delta, finish_reason = null) => res.write(`data: ${JSON.stringify({ id: 'mock', object: 'chat.completion.chunk', model: body.model, choices: [{ index: 0, delta, finish_reason }] })}\n\n`)
  await delay(100)
  record.first = Date.now()
  send({ role: 'assistant', content: text.slice(0, 10) })
  for (let i = 10; i < text.length; i += 5) { await delay(300); send({ content: text.slice(i, i + 5) }) }
  send({}, 'stop'); res.end('data: [DONE]\n\n'); record.end = Date.now()
})
await new Promise(resolve => mock.listen(0, '127.0.0.1', resolve))
const portProbe = createServer()
await new Promise(resolve => portProbe.listen(0, '127.0.0.1', resolve))
const webPort = portProbe.address().port
await new Promise(resolve => portProbe.close(resolve))
process.env.MOCK_API_KEY = 'mock-key'
const endpoint = `http://127.0.0.1:${mock.address().port}/v1`
const dir = join(home, 'profiles/latency')
boot.initProfile(dir, ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', 'chemclaw-bot'])
writeFileSync(join(dir, 'cordis.patch.yml'), `- id: chemclaw\n  config:\n    companyConnectors: false\n    updateCheck: false\n    warmRooms: false\n- id: llm-pi-ai\n  config:\n    providers:\n      mock-apihub:\n        api: openai-completions\n        baseURL: ${endpoint}\n        apiKeyEnv: MOCK_API_KEY\n        models:\n          - { id: deepseek-v4.1-flash, contextWindow: ${live ? 1000000 : 100000}, maxTokens: 8000 }\n- id: session-log-deepseek\n  disabled: true\n- id: session-telemetry-otel\n  disabled: true\n- id: workspace-changes\n  disabled: true\n`)
let running
let child
let exitCode = 0
writeFileSync(join(dir, 'cordis.patch.yml'), `${readFileSync(join(dir, 'cordis.patch.yml'), 'utf8')}\n- id: ui-settings-general\n  config:\n    welcomeNoticeVersion: "2026-09-28.1"\n- id: ui-settings-account\n  config:\n    version: 1\n    step: done\n    purpose: office\n    process: compact\n    completion: completed\n    usage: compact\n    developerTools: true\n`)
if (electron) electron.app.once('will-quit', () => electron.app.exit(exitCode))
try {
  let childUrl
  if (electron && !research) {
    child = fork(join(root, 'chemclaw-bot/dev/latency-host.mjs'), [dir, String(webPort)], { env: { ...process.env, ELECTRON_RUN_AS_NODE: '1' }, stdio: ['ignore', 'ignore', 'ignore', 'ipc'], windowsHide: true })
    child.on('message', message => {
      if (message.type !== 'diagnostic') return
      const event = { at: Date.now(), ...message.value }
      if (event.type === 'turn/end') turnEnds.push(event)
      writeFileSync(join(home, 'events.jsonl'), `${JSON.stringify(event)}\n`, { flag: 'a' })
    })
    childUrl = await new Promise((resolve, reject) => {
      child.once('error', reject)
      child.once('exit', code => reject(new Error(`Latency Host exited: ${code}`)))
      child.on('message', message => { if (message.type === 'ready') resolve(message.url) })
    })
  } else {
    running = await runProfile({ environment: boot.loadLayeredEnv('dsh'), profile: 'latency', resolvedProfile: { profile: boot.loadProfileDirectory('dsh', dir, join(root, 'app/package.json')), installAnchor: join(root, 'app/package.json') }, args: ['--no-open', '--port', String(webPort)], patchFiles: [] })
  }
  const ctx = running?.ctx
  ctx?.on('session/event', (_session, event) => {
    if (event.type === 'user/message' && event.data.source?.kind === 'chemclaw-skill-routing') autoSkillLoads.push(event.data.source.name)
  })
  ctx?.on('tools/execute', async (exec, next) => {
    const row = { name: exec.name, startedAt: Date.now() }
    toolCalls.push(row)
    try { const value = await next(); row.ok = !value?.isError; return value }
    catch (error) { row.ok = false; throw error }
    finally { row.elapsedMs = Date.now() - row.startedAt }
  })
  if (ctx) {
    const searchRows = (await ctx.get('pluginManager').listPlugins()).filter(row => row.moduleName === 'dsh-free-search').map(row => ({ module: row.moduleName, enabled: row.enabled, phase: row.fiberPhase }))
    console.log('Search plugin runtime:', JSON.stringify(searchRows))
    assert.ok(searchRows.some(row => row.enabled && row.phase === 'active'), 'Bundled search must be active')
  }
  if (research) {
    const saved = JSON.parse(readFileSync(join(process.env.APPDATA, 'chemclaw/locations.json'), 'utf8'))
    const key = JSON.parse(readFileSync(join(saved.dataDir, 'chemclaw/secrets.json'), 'utf8')).secrets?.find(s => s.name === 'CHEM_DATA_HUB')?.value
    if (!key) throw new Error('Saved desktop company connector is not configured')
    const loader = ctx.get('loader')
    const mod = await loader.import('@deepseek-ai/dsh-mcp-client')
    await ctx.plugin(loader.unwrapExports?.(mod) ?? mod.default ?? mod, { transport: 'streamable-http', serverName: 'chem-data-hub', url: 'https://datahub.chem-cloud.cn/mcp', headers: { Authorization: `Bearer ${key}` }, failOnStartupError: true }).await()
    console.log('Saved company connector: handshake complete')
  }
  const connection = ctx?.get('connection') ?? { authenticatedUrl: () => childUrl }
  // Use the same public route as the GUI, without exposing its authentication URL.
  const base = `http://127.0.0.1:${webPort}`
  const response = await fetch(connection.authenticatedUrl(base), { redirect: 'manual' })
  const cookie = response.headers.getSetCookie().map(value => value.split(';')[0]).join('; ')
  const api = async (endpoint, payload = {}) => {
    const response = await fetch(new URL('/api/bot', base), { method: 'POST', headers: { cookie, 'content-type': 'application/json' }, body: JSON.stringify({ endpoint, payload }) })
    const result = await response.json()
    assert.ok(result.ok, `${endpoint}: ${result.error?.message}`)
    return result.value
  }
  const team = await api('state')
  console.log('Latency bench: full team ready')
  assert.equal(team.bots.length, 50); assert.equal(team.rooms.length, 15)
  const bot = research ? team.bots.find(bot => bot.name === '产业链研究员') : team.bots.find(bot => bot.templateId && !team.mainBotIds.includes(bot.id))
  const room = team.rooms.find(room => room.members.includes(bot.id) && room.admin === bot.id) ?? team.rooms[0]
  console.log('Latency targets:', JSON.stringify({ bot: bot.name, room: room.name, adminMatches: room.admin === bot.id }))
  for (const member of team.bots.filter(member => room.members.includes(member.id) || member.id === bot.id)) {
    await api('update-bot', { id: member.id, model: 'mock-apihub/deepseek-v4.1-flash' })
  }
  if (electron) {
    window = new electron.BrowserWindow({ show: false, width: 1280, height: 900, webPreferences: { contextIsolation: true, nodeIntegration: false, backgroundThrottling: false } })
    window.webContents.on('console-message', (_event, level, message) => { if (level >= 2) console.log('Renderer diagnostic:', message.replace(/https?:\/\/\S+/g, '[url]').slice(0, 300)) })
    await window.loadURL(connection.authenticatedUrl(base))
    window.showInactive()
    console.log('Latency bench: GUI loaded')
    const deadline = Date.now() + 30_000
    while (!await window.webContents.executeJavaScript(`document.querySelectorAll('[data-room-id]').length === 15 && document.querySelectorAll('[data-bot-id]').length === 50`)) {
      if (Date.now() > deadline) throw new Error('UI did not load')
      await delay(100)
    }
    await window.webContents.executeJavaScript(`Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='继续')?.click()`)
    window.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'Escape' })
    window.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'Escape' })
  }
  for (const [kind, id] of (research ? [['direct', bot.sessionId]] : [['direct', bot.sessionId], ['group-cold', room.id], ['group-warm', room.id]])) {
    console.log(`Latency bench: ${kind}`)
    if (window) {
      await window.webContents.executeJavaScript(`document.querySelector('[${kind === 'direct' ? 'data-bot-id' : 'data-room-id'}="${kind === 'direct' ? bot.id : id}"]').click()`, true)
      const expected = kind === 'direct' ? bot.name : room.name
      const deadline = Date.now() + 20_000
      while (!await window.webContents.executeJavaScript(`document.querySelector('.bt-pill-name')?.textContent === ${JSON.stringify(expected)}`)) {
        if (Date.now() > deadline) {
          console.log('Navigation diagnostic:', JSON.stringify(await window.webContents.executeJavaScript(`({pill:document.querySelector('.bt-pill-name')?.textContent,selected:Array.from(document.querySelectorAll('[aria-current="page"]')).map(el=>el.getAttribute('data-bot-id')||el.getAttribute('data-room-id')),session:document.querySelector('[data-conversation-session]')?.getAttribute('data-conversation-session')})`)))
          throw new Error('GUI did not select the target conversation')
        }
        await delay(100)
      }
      await delay(500)
    }
    // group-cold = first message after the opening speaker Session is warmed (as when
    // the user opens the room). group-warm = a later message on the same Session.
    // warmed may be 0 when the GUI click already warmed the room.
    if (kind === 'group-cold') await api('warm-room', { roomId: id })
    const start = Date.now(); const offset = requests.length
    let firstStatus, firstText, uiText, screenshot = false, blankAfterDraft = 0, sawDraft = false
    const sent = api('send', { sessionId: id, text: research ? '请简要研究聚氨酯产业链全景：中国、MDI/TDI/聚醚主线。先核验一条产业链关系和一条近一个月的价格或装置动态，最多3次外部数据查询，输出200字有出处摘要。暂不生成文件，不需追问。' : live ? `请以「${kind}校验」开头，用约200字介绍你的职责和工作方法，分5句逐步说明；这是界面流式测试，不要调用工具或其他成员。` : '你好，请简单介绍一下。' })
    const deadline = start + (research ? 300_000 : live ? 120_000 : 60_000)
    for (;;) {
      const progress = kind === 'direct' ? [] : await api('room-progress', { roomId: id })
      if (progress.some(p => p.speaking) && !firstStatus) firstStatus = Date.now() - start
      const hasDraft = progress.some(p => p.drafts?.some(d => d.text))
      const hasReply = progress.some(p => p.replies?.some(r => r.text))
      if ((hasDraft || hasReply) && !firstText) firstText = Date.now() - start
      if (hasDraft) sawDraft = true
      if (progress.length > 0 && sawDraft && !hasDraft && !hasReply) blankAfterDraft += 1
      const request = requests.slice(offset).find(r => r.stream && r.conversation)
      const marker = request?.marker ?? request?.preview?.trim().slice(0, 10)
      if (window && marker && !uiText && await window.webContents.executeJavaScript(`Array.from(document.querySelectorAll('.bt-bubble')).some(el=>el.getBoundingClientRect().width>0 && el.textContent.includes(${JSON.stringify(marker)}))`)) uiText = Date.now() - start
      if (window && uiText && !screenshot && !request?.end) {
        screenshot = true
        writeFileSync(join(root, `chemclaw/verification/latency-${kind}.png`), (await window.webContents.capturePage()).toPNG())
      }
      const activeAgent = research ? (await ctx.get('sessionController').resolveAgent(id)).agent : undefined
      const directDone = !child || turnEnds.some(event => event.sessionId === id && event.at >= start)
      if (request?.end && (!research || activeAgent.status === 'idle') && (kind === 'direct' ? directDone : !progress.length)) break
      if (Date.now() > deadline) {
        console.log('Timeout diagnostic:', JSON.stringify({ requests: requests.slice(offset).map(r => ({ stream: r.stream, conversation: r.conversation, ended: !!r.end, tools: r.toolCount })), progress: progress.map(p => ({ speaking: p.speaking, drafts: p.drafts?.length, replies: p.replies?.length })) }))
        throw new Error(`Timed out: ${kind}`)
      }
      await delay(75)
    }
    await sent
    if (research) await (await ctx.get('sessionController').resolveAgent(id)).agent.whenIdle()
    const batch = requests.slice(offset).filter(r => r.stream && r.conversation)
    const request = batch[0]
    const roomHop = kind === 'direct' ? undefined : batch.reduce((min, row) => (min === undefined || row.chars < min.chars ? row : min), undefined)
    results.push({
      kind, statusMs: firstStatus, visibleTextMs: firstText, uiTextMs: uiText, handoffBlankPolls: blankAfterDraft,
      requestMs: request.at - start, providerFirstMs: request.first - start,
      providerTextMs: request.firstText === undefined ? undefined : request.firstText - start,
      providerReasoningMs: request.firstReasoning === undefined ? undefined : request.firstReasoning - start,
      doneMs: Date.now() - start, skillCatalogs: request.skillCatalogs,
      requestChars: request.chars, hopChars: batch.map(r => r.chars), roomHopChars: roomHop?.chars,
      toolCount: request.toolCount, toolNames: request.toolNames, executedTools: toolCalls, autoSkillLoads,
    })
    console.log(JSON.stringify(results.at(-1)))
    writeFileSync(join(root, `chemclaw/verification/latency${research ? '-research' : live ? '-live' : ''}.json`), JSON.stringify({ mock: !live, model: 'deepseek-v4.1-flash', results }, null, 2))
    if (kind !== 'direct') {
      assert.ok(firstText && firstText < request.end - start, 'Group must show text before completion')
      assert.equal(blankAfterDraft, 0, 'Group draft must not blank before the committed reply')
    }
    if (window) assert.ok(uiText && uiText < request.end - start, `${kind}: GUI must show text before completion`)
  }
  console.log(JSON.stringify(results, null, 2))
  writeFileSync(join(root, `chemclaw/verification/latency${research ? '-research' : live ? '-live' : ''}.json`), JSON.stringify({ mock: !live, model: 'deepseek-v4.1-flash', results }, null, 2))
} catch (error) {
  exitCode = 1
  console.error(error)
  if (window && !window.isDestroyed()) writeFileSync(join(root, 'chemclaw/verification/latency-failure.png'), (await window.webContents.capturePage()).toPNG())
} finally {
  window?.destroy()
  if (child && child.exitCode === null) {
    child.send({ type: 'shutdown' })
    await new Promise(resolve => child.once('exit', resolve))
  }
  await running?.shutdown.shutdown(exitCode)
  mock.closeAllConnections(); await new Promise(resolve => mock.close(resolve))
  process.exitCode = exitCode
  electron?.app.exit(exitCode)
}
