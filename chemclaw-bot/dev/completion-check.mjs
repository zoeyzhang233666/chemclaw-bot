// Regression for the removed answer budgets. Run only in a fresh mock bench:
// node dev/bench-windows.mjs completion-NAME --completion-check
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { setTimeout as sleep } from 'node:timers/promises'
import { zstdDecompressSync } from 'node:zlib'

const [name, port] = process.argv.slice(2)
if (!/^[a-z0-9-]+$/.test(name) || !/^\d+$/.test(port)) throw new Error('Use an isolated mock bench name and port')
const home = resolve(import.meta.dirname, '../..', `.dsh-test-${name}`)
const login = readFileSync(resolve(home, 'web.log'), 'utf8').match(/http:\/\/127\.0\.0\.1:\d+\/\?token=[^\s]+/)[0]
const auth = await fetch(login, { redirect: 'manual' })
const cookie = auth.headers.getSetCookie().map(value => value.split(';')[0]).join('; ')
const api = async (endpoint, payload = {}) => {
  let response
  for (let attempt = 0; ; attempt += 1) {
    try {
      response = await fetch(`http://127.0.0.1:${port}/api/bot`, { method: 'POST', headers: { 'content-type': 'application/json', cookie }, body: JSON.stringify({ endpoint, payload }) })
      break
    } catch (error) {
      // A busy local Host can reset a reused socket. Only retry the read-only poll.
      if (endpoint !== 'state' || attempt >= 2) throw new Error(`${endpoint}: ${error.cause?.code ?? error.message}`)
      await sleep(300)
    }
  }
  const answer = await response.json()
  if (!answer.ok) throw new Error(`${endpoint}: ${answer.error?.message}`)
  return answer.value
}
const saved = () => JSON.parse(readFileSync(resolve(home, 'chemclaw/state.json'), 'utf8'))
const eventsOf = id => {
  for (const folder of readdirSync(resolve(home, 'sessions'))) {
    const file = resolve(home, 'sessions', folder, id, 'session.v4.jsonl.zstd')
    if (!existsSync(file)) continue
    const events = []
    let input = readFileSync(file)
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
const settle = async () => {
  const deadline = Date.now() + 90_000
  let quietAt = Date.now()
  while (Date.now() < deadline) {
    const { activity = {}, work = {} } = await api('state')
    if (Object.keys(activity).length || Object.keys(work.turns ?? {}).length) quietAt = Date.now()
    else if (Date.now() - quietAt >= 2500) return
    await sleep(300)
  }
  throw new Error('Mock work did not finish')
}
const checkAnswer = id => {
  const events = eventsOf(id)
  assert.ok(events.filter(event => event.type === 'tool/call' && event.data?.name === 'list_bots').length >= 12, 'research reaches beyond the former quick step budget')
  assert.ok(events.some(event => event.type === 'assistant/message' && JSON.stringify(event.data).includes('任务完成验收：12 步研究后已交付')), 'final answer is in the conversation without another question')
  assert.ok(events.some(event => event.type === 'tool/call' && event.data?.name === 'show_view'), 'inline view was delivered')
  const files = events.filter(event => event.type === 'assistant/message').flatMap(event => [...JSON.stringify(event.data).matchAll(/\]\(([^)]+\.(?:html|xlsx))\)/g)].map(match => JSON.parse(`"${match[1]}"`)))
  assert.equal(new Set(files.map(file => file.split('.').at(-1))).size, 2, 'both HTML and Excel are linked')
  assert.ok(files.every(existsSync), 'linked files exist')
  assert.ok(!events.some(event => event.data?.reason?.reason === 'chemclaw-bot/deliver-now'), 'no budget cancellation')
}

await settle()
const view = await api('state')
const chief = view.bots.find(bot => bot.id === view.mainBotId)
const model = view.models.at(-1).ref
await api('update-bot', { id: chief.id, model })
const writer = await api('create-bot', { name: 'Writer', role: 'Research', model })
await settle()
const question = '验收甲醇现货价格和上下游产业链'
await api('send', { sessionId: chief.id, text: question })
await settle()
checkAnswer(saved().bots[chief.id].sessionId ?? chief.id)
console.log('completion-check: private answer completes 12 research steps, files and inline view')
await api('send', { sessionId: chief.id, text: `转告 Writer: ${question}` })
await settle()
checkAnswer(saved().bots[writer.id].sessionId ?? writer.id)
console.log('completion-check: delegated work completes without a shared answer budget')
const room = await api('create-room', { name: 'Completion check', members: [chief.id, writer.id], admin: chief.id })
await settle()
await api('send', { sessionId: room.id, text: question })
await settle()
const group = saved().rooms[room.id]
checkAnswer(group.sessions[chief.id])
assert.ok(group.log.some(line => line.text?.includes('任务完成验收：12 步研究后已交付')), 'group final answer is visible without asking for results')
assert.equal(group.paused?.length ?? 0, 0, 'research tools do not consume the group relay count')
assert.ok(eventsOf(group.id).some(event => event.type === 'tool/result' && JSON.stringify(event.data).includes('任务完成验收（合成数据）')), 'group relay preserves the chart for conversation replay')
assert.equal(saved().answerRuns, undefined, 'the answer budget runtime is absent')
console.log('completion-check: group completes research, files and chart without Continue or a follow-up')
