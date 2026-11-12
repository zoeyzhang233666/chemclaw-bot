import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { install } from '../src/host/context-recovery.js'
import { HANDOFF_ACK } from '../src/host/constants.js'
import { contextRecoveryNotice, validContextRecovery } from '../src/shared/context-recovery.js'

function start(t, saved) {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-context-recovery-'))
  const file = join(home, 'state.json')
  const state = structuredClone(saved ?? { bots: { b: { id: 'b' }, a: { id: 'a' } }, rooms: { r: { id: 'r', members: ['b', 'a'] } } })
  const listeners = new Map()
  const disposers = []
  const notices = []
  let saveError
  let readOnly
  const rt = {
    state,
    ctx: { on(name, fn) { listeners.set(name, fn) }, effect(fn) { disposers.push(fn()) } },
    chatOwners: new Map([['s', 'b'], ['a', 'a']]), groupOwners: new Map([['g', { botId: 'b', roomId: 'r' }]]), pastOwners: new Map(),
    botOf: id => state.bots[id], roomOf: id => state.rooms[id], isBotSession: id => rt.chatOwners.has(id) || rt.groupOwners.has(id),
    readOnly: () => readOnly, warn() {}, noteFailure: entry => notices.push(entry),
    async save(options) {
      assert.equal(options.required, true)
      if (saveError) throw saveError
      writeFileSync(file, JSON.stringify(state))
    },
  }
  install(rt)
  t.after(async () => { for (const dispose of disposers) await dispose(); rmSync(home, { recursive: true, force: true }) })
  return {
    rt, notices, state, recovery: rt.contextRecovery,
    saved: () => JSON.parse(readFileSync(file, 'utf8')),
    emit: (id, type, data) => listeners.get('session/event')({ id }, { type, data }),
    failSave: value => { saveError = value ? new Error('mock disk full') : undefined },
    setReadOnly: value => { readOnly = value },
  }
}

const user = id => [{ id, source: { kind: 'user' } }]
const message = (text = 'done', reason = 'stop') => ({ message: { content: [{ type: 'text', text }] }, stream: [{ type: 'chunk', time: 1, chunk: { type: 'finish', reason: { kind: reason } } }] })

test('two recovery switches are durable and a third consecutive failure blocks across Sessions and restart', async t => {
  const run = start(t)
  await run.recovery.userInput('s', user('request-1'))
  assert.equal(await run.recovery.advance('s'), true)
  assert.equal(run.saved().bots.b.contextRecovery.attempts, 1)
  run.rt.chatOwners.delete('s')
  run.rt.pastOwners.set('s', { botId: 'b' })
  run.rt.chatOwners.set('fresh', 'b')
  assert.equal(await run.recovery.advance('fresh'), true)
  const restarted = start(t, run.saved())
  assert.equal(await restarted.recovery.advance('s'), false)
  assert.equal(restarted.saved().bots.b.contextRecovery.attempts, 3)
  assert.equal(restarted.recovery.blocked('s'), true)
  assert.equal(await restarted.recovery.advance('s'), false)
  assert.equal(restarted.notices.length, 1)
})

test('private chats, groups and other Bots have independent recovery budgets', async t => {
  const { recovery, state } = start(t)
  for (let i = 0; i < 3; i += 1) await recovery.advance('s')
  assert.equal(recovery.blocked('s'), true)
  assert.equal(await recovery.advance('g'), true)
  assert.equal(await recovery.advance('a'), true)
  assert.equal(state.rooms.r.contextRecovery.b.attempts, 1)
  assert.equal(state.bots.a.contextRecovery.attempts, 1)
})

test('only a complete real model response clears the budget', async t => {
  const run = start(t)
  await run.recovery.advance('s')
  for (const [type, data] of [
    ['assistant/attempt', message()],
    ['assistant/message', { ...message(), interrupted: true }],
    ['assistant/message', message('partial', 'error')],
    ['assistant/message', message('partial', 'aborted')],
    ['assistant/message', message(HANDOFF_ACK)],
    ['assistant/message', message('', 'max-tokens')],
    ['assistant/message', { message: { content: [{ type: 'text', text: 'partial' }] } }],
    ['turn/end', { reason: { kind: 'completed' } }],
  ]) {
    run.emit('s', type, data)
    await run.recovery.settled()
    assert.equal(run.state.bots.b.contextRecovery.attempts, 1, type)
  }
  run.emit('a', 'assistant/message', message())
  await run.recovery.settled()
  assert.equal(run.state.bots.b.contextRecovery.attempts, 1)
  run.emit('s', 'assistant/message', message('tool call', 'tool-calls'))
  await run.recovery.settled()
  assert.equal(run.state.bots.b.contextRecovery, undefined)
  assert.equal(await run.recovery.advance('s'), true)
  assert.equal(run.state.bots.b.contextRecovery.attempts, 1)
})

test('forwarded input and replay of the original input cannot reset the budget; a new user message can', async t => {
  const run = start(t)
  await run.recovery.userInput('s', user('original'))
  for (let i = 0; i < 3; i += 1) await run.recovery.advance('s')
  const restarted = start(t, run.saved())
  await restarted.recovery.userInput('s', user('original'))
  await restarted.recovery.userInput('s', [{ id: 'copied-id', source: { kind: 'user', contextRecoveryForwarded: true } }])
  assert.equal(restarted.recovery.blocked('s'), true)
  await restarted.recovery.userInput('s', user('new-user-request'))
  assert.equal(restarted.recovery.blocked('s'), false)
  assert.equal(await restarted.recovery.advance('s'), true)
  assert.equal(restarted.saved().bots.b.contextRecovery.attempts, 1)
})

test('a user group message resets only that group, and model changes reset that Bot in all conversations', async t => {
  const run = start(t)
  for (const id of ['s', 'g', 'a']) for (let i = 0; i < 3; i += 1) await run.recovery.advance(id)
  await run.recovery.userInput('r', user('group-request'))
  assert.equal(run.recovery.blocked('g'), false)
  assert.equal(run.recovery.blocked('s'), true)
  assert.equal(run.recovery.blocked('a'), true)
  await run.recovery.resetBot('b')
  assert.equal(run.recovery.blocked('s'), false)
  assert.equal(run.recovery.blocked('a'), true)
})

test('write failure grants no fresh part, does not reset on a late response, and needs a durable user retry', async t => {
  const run = start(t)
  await run.recovery.advance('s')
  run.failSave(true)
  assert.equal(await run.recovery.advance('s'), false)
  assert.equal(run.saved().bots.b.contextRecovery.attempts, 1)
  assert.equal(run.recovery.blocked('s'), true)
  run.emit('s', 'assistant/message', message())
  await run.recovery.settled()
  assert.equal(run.recovery.blocked('s'), true)
  await assert.rejects(run.recovery.userInput('s', user('retry')), /mock disk full/)
  assert.equal(run.recovery.blocked('s'), true)
  run.failSave(false)
  await run.recovery.userInput('s', user('retry'))
  assert.equal(run.recovery.blocked('s'), false)
})

test('read-only hosts never mutate recovery state and concurrent failures cannot spend an extra retry', async t => {
  const run = start(t)
  run.setReadOnly('mock second host')
  assert.equal(await run.recovery.advance('s'), false)
  assert.equal(run.state.bots.b.contextRecovery, undefined)
  run.setReadOnly(undefined)
  assert.deepEqual(await Promise.all(Array.from({ length: 6 }, () => run.recovery.advance('s'))), [true, true, false, false, false, false])
})

test('recovery records validate without accepting corrupt counters, and blocked state has a visible notice', () => {
  for (const value of [null, [], {}, { attempts: -1, blocked: false }, { attempts: 4, blocked: true }, { attempts: 3, blocked: false }, { attempts: 1, blocked: true }]) assert.equal(validContextRecovery(value), false)
  assert.equal(validContextRecovery({ attempts: 3, blocked: true, userMessageId: 'request' }), true)
  assert.match(contextRecoveryNotice({ contextRecovery: { blocked: true } }), /history is preserved/)
  assert.match(contextRecoveryNotice(undefined, { contextRecovery: { b: { blocked: true } } }), /send a message to retry/)
  assert.equal(contextRecoveryNotice({}), '')
})
