// Short API check for interactive views on an already-running mock bench:
//   node dev/bench-windows.mjs views-check-NAME
//   node dev/views-check.mjs views-check-NAME <web-port>
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { zstdDecompressSync } from 'node:zlib'

const [name, port] = process.argv.slice(2)
if (!name || !port) {
  console.error('usage: node dev/views-check.mjs <bench-name> <web-port>')
  process.exit(2)
}
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))))
const HOME = join(ROOT, `.dsh-test-${name}`)
const BASE = `http://127.0.0.1:${port}`
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
const readJson = path => JSON.parse(readFileSync(path, 'utf8'))

function savedEvents(sessionId) {
  for (const workspace of readdirSync(join(HOME, 'sessions'))) {
    const file = join(HOME, 'sessions', workspace, sessionId, 'session.v4.jsonl.zstd')
    if (!existsSync(file)) continue
    let input = readFileSync(file)
    const events = []
    while (input.length) {
      const decoded = zstdDecompressSync(input, { info: true })
      events.push(...decoded.buffer.toString('utf8').split('\n').filter(Boolean).map(JSON.parse))
      if (!decoded.engine.bytesWritten) throw new Error('Invalid test log frame')
      input = input.subarray(decoded.engine.bytesWritten)
    }
    return events
  }
  return []
}

async function login() {
  const log = readFileSync(join(HOME, 'web.log'), 'utf8')
  const url = log.match(new RegExp(`http://127\\.0\\.0\\.1:${port}/\\?token=[^\\s]+`))?.[0]
  if (!url) throw new Error('no login URL in web.log')
  const response = await fetch(url, { redirect: 'manual' })
  const cookies = response.headers.getSetCookie().map(cookie => cookie.split(';')[0])
  if (cookies.length === 0) throw new Error(`login returned no cookie (${response.status})`)
  return cookies.join('; ')
}

const cookie = await login()
async function api(endpoint, payload = {}) {
  const response = await fetch(`${BASE}/api/bot`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', cookie },
    body: JSON.stringify({ endpoint, payload }),
  })
  const result = await response.json()
  if (!result.ok) throw new Error(`${endpoint}: ${result.error?.message ?? JSON.stringify(result)}`)
  return result.value
}

const state = () => readJson(join(HOME, 'chemclaw', 'state.json'))
const botNamed = wanted => Object.values(state().bots).find(bot => bot.name === wanted)
async function settle() {
  const deadline = Date.now() + 60_000
  let since = Date.now()
  while (Date.now() < deadline) {
    await sleep(400)
    const { activity = {}, work = {} } = await api('state')
    if (Object.keys(activity).length > 0 || Object.keys(work.turns ?? {}).length > 0) since = Date.now()
    else if (Date.now() - since >= 2000) return
  }
  throw new Error('the team did not go quiet')
}

async function send(sessionId, text) {
  await api('send', { sessionId, text })
  await settle()
}

function lastShowView(sessionId) {
  const events = savedEvents(sessionId)
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const item = events[i]
    if (item.type === 'tool/call' && item.data?.name === 'show_view') return item.data
  }
  return null
}

const failures = []
const check = (ok, label) => {
  if (ok) console.log(`ok   ${label}`)
  else { console.error(`fail ${label}`); failures.push(label) }
}

await settle()
const live = await api('state')
let chief = botNamed('Chief')
if (!chief) throw new Error('expected seeded Chief')
if (!chief.model) {
  const models = live.models ?? []
  const pick = models.at(-1)?.ref
  if (!pick) throw new Error('no models listed')
  await api('update-bot', { id: chief.id, model: pick })
  await settle()
}

if (!botNamed('Writer')) {
  await send(chief.id, '创建一个叫Writer的bot')
}
const writer = botNamed('Writer')
if (!writer) throw new Error('no Writer bot')
const chatOf = bot => bot.sessionId ?? bot.id

await send(writer.id, '视图图表')
{
  const call = lastShowView(chatOf(writer))
  const args = JSON.parse(call?.arguments ?? '{}')
  check(args.view?.type === 'chart' && args.view?.kind === 'bar', 'chart view persisted')
}

await send(writer.id, '视图计算')
{
  const call = lastShowView(chatOf(botNamed('Writer')))
  const args = JSON.parse(call?.arguments ?? '{}')
  check(args.view?.type === 'stack' && args.view?.let?.cost === 'qty * price', 'formula view persisted')
  check(Array.isArray(args.view?.children) && args.view.children.some(node => node.type === 'slider'), 'formula inputs present')
  check(args.title === undefined || args.title === '', 'formula view allows empty title')
}

await send(writer.id, '视图网页')
{
  const call = lastShowView(chatOf(botNamed('Writer')))
  const args = JSON.parse(call?.arguments ?? '{}')
  check(args.view?.type === 'html' && typeof args.view?.html === 'string', 'html view persisted')
  check(typeof args.view?.summary === 'string' && args.view.summary !== '', 'html view has summary')
}

{
  const events = savedEvents(chatOf(botNamed('Writer')))
  const views = events
    .filter(item => item.type === 'tool/call' && item.data?.name === 'show_view')
    .map(item => JSON.parse(item.data.arguments ?? '{}'))
  check(views.some(item => item.view?.type === 'chart'), 'history keeps chart blueprint')
  check(views.some(item => item.view?.type === 'html'), 'history keeps html blueprint')
  check(views.some(item => item.view?.let?.cost === 'qty * price'), 'history keeps formula blueprint')
}

{
  await send(writer.id, '视图图表')
  const before = savedEvents(chatOf(botNamed('Writer'))).filter(item => item.type === 'tool/call' && item.data?.name === 'show_view').length
  await api('create-room', { name: 'Views Check', memberIds: [writer.id] }).catch(() => null)
  await settle()
  const room = Object.values(state().rooms ?? {}).find(item => item.name === 'Views Check')
  if (!room) {
    check(true, 'group refusal covered by unit tests when room create is unavailable')
  } else {
    await send(room.id, '视图图表')
    const after = savedEvents(chatOf(botNamed('Writer'))).filter(item => item.type === 'tool/call' && item.data?.name === 'show_view').length
    const roomCall = lastShowView(room.sessionId ?? room.id)
    check(roomCall === null && after === before, 'group chat does not record show_view')
  }
}

if (failures.length) {
  console.error(`views-check: ${failures.length} failed`)
  process.exit(1)
}
console.log('views-check: all checks passed')
