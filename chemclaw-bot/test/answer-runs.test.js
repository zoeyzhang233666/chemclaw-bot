import assert from 'node:assert/strict'
import { test } from 'node:test'
import { install } from '../src/host/answer-runs.js'
import { SOURCE_KIND } from '../src/host/constants.js'
import { fakeContext } from './fake-ctx.js'

function setup(t, state = {}) {
  let now = 100_000
  t.mock.method(Date, 'now', () => now)
  const ctx = fakeContext()
  const agents = new Map()
  const delivered = []
  const rt = {
    ctx, state, config: { answerBudget: { steps: 2, relays: 1, ms: 1000 }, answerFinalMs: 1000, answerRestoreMs: 0 },
    live: new Map(), groupOwners: new Map([['ga', { roomId: 'room', botId: 'a' }], ['gb', { roomId: 'room', botId: 'b' }]]),
    load: async () => {}, save: async () => {}, warn() {},
    selfOf: id => id === 'ga' ? 'a' : id === 'gb' ? 'b' : id,
    botOf: id => ['a', 'b', 'c'].includes(id) ? { id, name: id.toUpperCase() } : undefined,
    roomOf: id => id === 'room' ? room : undefined,
    isBotSession: id => ['a', 'b', 'c', 'ga', 'gb'].includes(id), chatOf: id => id,
    resolveAgent: async id => agent(id),
    deliver: async input => {
      delivered.push(input)
      const target = agent(input.sessionId)
      target.inbox.nextTurn.push({ id: 'final', source: { answerRun: input.answerRun, role: input.role } })
    },
  }
  const room = { id: 'room', paused: [] }
  const agent = id => {
    if (!agents.has(id)) {
      const nextTurn = []
      const cancellations = []
      agents.set(id, { id, session: { id }, cancellations,
        ctx: { tools: { restrict: () => () => {} } },
        inbox: { nextStep: [], nextTurn, remove: key => { const at = nextTurn.findIndex(item => item.id === key); if (at >= 0) nextTurn.splice(at, 1) } },
        cancel: reason => { cancellations.push(reason); rt.live.delete(id) },
      })
    }
    return agents.get(id)
  }
  install(rt)
  t.after(() => ctx.dispose())
  const hook = ctx.listeners.get('agent/pre-step')[0]
  const message = (text, source = { kind: 'user' }) => ({ role: 'user', content: [{ type: 'text', text }], source })
  const step = async (id, messages = []) => {
    agent(id).inbox.nextTurn.splice(0)
    rt.live.set(id, { turn: 1 })
    return hook({ agent: agent(id), signal: new AbortController().signal }, async () => ({ kind: 'enter', messages }))
  }
  const emit = (id, type, data) => { for (const listener of ctx.listeners.get('session/event')) listener({ id }, { type, data }) }
  const complete = (id, text) => {
    emit(id, 'assistant/message', { message: { content: [{ type: 'text', text }] } })
    rt.live.delete(id)
    emit(id, 'turn/end', { reason: { kind: 'completed' } })
  }
  return { rt, ctx, step, message, emit, complete, delivered, agent, room, advance: ms => { now += ms } }
}

test('private delegation shares the original budget and automatically starts one final synthesis', async t => {
  const host = setup(t)
  await host.step('a', [host.message('价格走势')])
  const run = host.rt.answerRunOf('a')
  assert.equal(host.rt.answerRelay('a'), undefined)
  const inherited = host.rt.inheritAnswerRun({ fromId: 'a', toId: 'b', sessionId: 'b', role: 'request', exchangeId: 'x' })
  assert.equal(inherited, run)
  await host.step('b', [host.message('查数据', { kind: SOURCE_KIND, answerRun: run })])
  host.complete('b', '2026-10-27：已取得两笔数据，第三笔缺失。')
  const rejected = await host.step('a')
  assert.equal(rejected.kind, 'reject')
  assert.equal(host.delivered.length, 1)
  assert.equal(host.delivered[0].sessionId, 'a')
  assert.match(host.delivered[0].text, /第三笔缺失/)
  assert.equal(host.rt.state.answerRuns.tasks[run].steps, 3)
  assert.match(host.ctx.guards[0]({ name: 'message_bot', agent: host.agent('a') }), /synthesis/)
  assert.equal(host.ctx.guards[0]({ name: 'show_view', agent: host.agent('a') }), undefined)
  await host.rt.sweepAnswers()
  assert.equal(host.delivered.length, 1, 'the final turn is scheduled once')
})

test('a paused group is automatically synthesized and a failed synthesis produces a durable partial delivery', async t => {
  const host = setup(t)
  host.emit('room', 'user/message', { content: [{ type: 'text', text: '基差走势' }], source: { kind: 'user' } })
  const run = host.rt.answerRunOf('room')
  host.rt.inheritAnswerRun({ roomId: 'room', role: 'room', sessionId: 'ga', toId: 'a' })
  await host.step('ga', [host.message('基差', { kind: SOURCE_KIND, answerRun: run })])
  host.complete('ga', '已返回 65 元/吨，最新一日尚未取得。')
  host.room.paused.push({ id: 'b', name: 'B' })
  host.advance(1100)
  await host.rt.sweepAnswers()
  assert.equal(host.delivered[0].roomId, 'room')
  assert.equal(host.delivered[0].role, 'delivery-result')
  assert.deepEqual(host.room.paused, [])
  assert.equal(host.rt.answerClosing('room'), true)
  // Synthesis follow-up must survive cancel sweeps while closing is in flight.
  host.agent('ga').inbox.nextTurn.push({ id: 'synth', source: { answerRun: run, role: 'delivery-result' } })
  host.advance(1100)
  await host.rt.sweepAnswers()
  assert.ok(host.agent('ga').inbox.nextTurn.some(item => item.source?.role === 'delivery-result'))
  const [result] = host.rt.answerResults().room
  assert.match(result.notes[0].text, /最新一日尚未取得/)
  assert.equal(host.rt.state.answerRuns.tasks[run].phase, 'ended')
  assert.equal(host.ctx.guards[0]({ name: 'read_file', agent: host.agent('ga') }), 'This user task has ended. Wait for a new user request.')
})

test('a group finisher over budget queues synthesis after abort and keeps delivery-result', async t => {
  const host = setup(t)
  host.emit('room', 'user/message', { content: [{ type: 'text', text: '自动收敛群验收' }], source: { kind: 'user' } })
  const run = host.rt.answerRunOf('room')
  host.rt.inheritAnswerRun({ roomId: 'room', role: 'room', sessionId: 'ga', toId: 'a' })
  await host.step('ga', [host.message('自动收敛群验收', { kind: SOURCE_KIND, answerRun: run })])
  await host.step('ga')
  const rejected = await host.step('ga')
  assert.equal(rejected.kind, 'reject')
  assert.equal(host.delivered.length, 1)
  assert.equal(host.delivered[0].sessionId, 'ga')
  assert.equal(host.delivered[0].role, 'delivery-result')
  assert.equal(host.rt.state.answerRuns.tasks[run].phase, 'closing')
  assert.ok(host.agent('ga').cancellations.length >= 1, 'finisher research turn is aborted before synthesis')
  assert.ok(host.agent('ga').inbox.nextTurn.some(item => item.source?.role === 'delivery-result'))
  const closing = await host.step('ga', [host.message('合成', { kind: SOURCE_KIND, answerRun: run, role: 'delivery-result' })])
  assert.equal(closing.kind, 'enter')
  host.complete('ga', '自动收敛完成：已交付当前结果，最新一天缺失，不再继续讨论。')
  assert.equal(host.rt.state.answerRuns.tasks[run].phase, 'done')
  assert.match(host.rt.state.answerRuns.tasks[run].notes.at(-1).text, /自动收敛完成/)
})

test('an older task cannot cancel a new user question or reuse its budget', async t => {
  const host = setup(t)
  await host.step('a', [host.message('价格走势')])
  const old = host.rt.answerRunOf('a')
  await host.step('a', [host.message('新的企业问题')])
  const fresh = host.rt.answerRunOf('a')
  assert.notEqual(fresh, old)
  host.advance(1100)
  await host.rt.sweepAnswers()
  assert.equal(host.rt.state.answerRuns.tasks[old].phase, 'done')
  assert.equal(host.agent('a').cancellations.length, 1, 'only the new task reaches its own deadline')
  assert.equal(host.delivered[0].answerRun, fresh)
})

test('completed short answers do not produce a later timeout notice and saved tasks keep their step count', async t => {
  const host = setup(t)
  await host.step('a', [host.message('你好')])
  const run = host.rt.answerRunOf('a')
  host.complete('a', '你好，有什么业务问题？')
  await host.rt.sweepAnswers()
  assert.equal(host.rt.state.answerRuns.tasks[run].phase, 'done')
  host.advance(5000)
  await host.rt.sweepAnswers()
  assert.equal(host.delivered.length, 0)
  await host.step('a', [host.message('继续查询')])
  const active = host.rt.answerRunOf('a')
  const restored = setup(t, JSON.parse(JSON.stringify(host.rt.state)))
  await restored.step('a', [restored.message('接续', { kind: SOURCE_KIND, answerRun: active })])
  assert.equal(restored.rt.state.answerRuns.tasks[active].steps, 2)
  assert.equal((await restored.step('a')).kind, 'reject')
  assert.equal(restored.delivered.length, 1)
})
