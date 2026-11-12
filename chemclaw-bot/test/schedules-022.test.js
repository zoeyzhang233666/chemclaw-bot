import assert from 'node:assert/strict'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { createRuntime } from './legacy-runtime.js'
import { fakeContext } from './fake-ctx.js'

const team = {
  version: 1, mainBotIds: ['chief'],
  bots: {
    chief: { id: 'chief', name: 'ChemClaw', role: 'Chief', sessionId: 'a', createdAt: 1 },
    writer: { id: 'writer', name: 'Writer', role: 'Research', sessionId: 'b2', createdAt: 2, segments: [{ sessionId: 'b1', endedAt: 3 }] },
  },
  rooms: { ops: { id: 'ops', name: 'Ops', members: ['chief', 'writer'], mode: 'admin', admin: 'chief', sessions: {}, log: [], seq: 0, seen: {} } },
  agents: {}, exchanges: [], exchangeTurns: {}, questions: {},
}

function service() {
  let nextId = 0
  const tasks = new Map()
  return {
    tasks,
    async create(args) {
      const item = {
        ...args, id: 'task-' + (++nextId), status: 'active',
        scheduledAt: '2035-01-01T12:00:00.000Z',
      }
      tasks.set(item.id, item)
      return item
    },
    async catalog() { return [...tasks.values()] },
    async edit({ id, action, patch }) {
      const task = tasks.get(id)
      if (!task) throw new Error('missing schedule')
      if (action === 'delete') { tasks.delete(id); return }
      if (action === 'update') { Object.assign(task, patch); return task }
      throw new Error('unsupported edit')
    },
  }
}
function setup(t) {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-dsh-022-schedules-'))
  writeFileSync(join(home, 'state.json'), JSON.stringify(team))
  const schedule = service()
  const ctx = fakeContext({ services: { schedule } })
  let fetchRoute
  const original = ctx.connection.fetch.register
  ctx.connection.fetch.register = route => { fetchRoute = route; return original(route) }
  const rt = createRuntime(ctx, { home })
  const call = async (endpoint, payload = {}) => (
    await fetchRoute.fetch(new Request('http://localhost/api/bot', {
      method: 'POST', body: JSON.stringify({ endpoint, payload }),
    }))
  ).json()
  t.after(async () => {
    await ctx.dispose()
    rmSync(home, { recursive: true, force: true, maxRetries: 5 })
  })
  return { ctx, rt, call, schedule }
}

test('DSH 0.2.2 Host-wide tasks use session targets, remain private, and delete by validated ID', async t => {
  const { call, schedule } = setup(t)
  const made = await call('schedule-create', { target: 'writer', title: 'Buyer check', prompt: 'Check SBS spot prices', when: { kind: 'every', minutes: 30 } })
  assert.equal(made.ok, true, JSON.stringify(made))
  const [task] = schedule.tasks.values()
  assert.deepEqual(task.timing, { kind: 'every', every_seconds: 1800 })
  assert.deepEqual(task.target, { kind: 'session', sessionId: 'b2' })
  await schedule.create({ title: 'Other account', prompt: 'secret', timing: { kind: 'every', every_seconds: 60 }, target: { kind: 'session', sessionId: 'other' } })
  assert.deepEqual((await call('schedules')).value.tasks.map(item => item.title), ['Buyer check'])
  assert.equal((await call('schedule-delete', { sessionId: 'b2', id: 'task-2' })).ok, false, 'foreign task cannot be deleted by ID')
  const deleted = await call('schedule-delete', { sessionId: 'b2', id: task.id })
  assert.equal(deleted.ok, true)
  assert.equal(schedule.tasks.has(task.id), false)
  assert.equal(schedule.tasks.has('task-2'), true)
})

test('DSH 0.2.2 schedule migration retargets a live or paused task in place', async t => {
  const { rt, schedule } = setup(t)
  const job = await schedule.create({ title: 'Scheduled report', prompt: 'Prepare report', timing: { kind: 'daily', daily: { time: '08:00:00', time_zone: 'Asia/Shanghai' } }, target: { kind: 'session', sessionId: 'b2' } })
  const paused = await schedule.create({ title: 'Paused report', prompt: 'Prepare later', timing: { kind: 'every', every_seconds: 7200 }, target: { kind: 'session', sessionId: 'b2' } })
  paused.status = 'paused'
  await rt.moveSchedules('b2', 'b3')
  assert.equal(schedule.tasks.size, 2)
  assert.equal(schedule.tasks.get(job.id).target.sessionId, 'b3')
  assert.equal(schedule.tasks.get(paused.id).target.sessionId, 'b3')
  assert.equal(schedule.tasks.get(paused.id).status, 'paused')
})

test('DSH 0.2.2 tools refuse changing another Bot task or scheduling a new external Session', async t => {
  const { ctx, rt, schedule } = setup(t)
  await rt.load()
  const other = await schedule.create({ title: 'Other', prompt: 'No access', target: { kind: 'session', sessionId: 'a' } })
  const own = await schedule.create({ title: 'Own', prompt: 'Can access', target: { kind: 'session', sessionId: 'b1' } })
  const before = ctx.listeners.get('tools/pre-execute') ?? []
  const check = async id => {
    let result = { kind: 'allow' }
    for (const handler of before) {
      result = await handler({ name: 'schedule_edit', agent: { id: 'b2' }, arguments: { id } }, async () => result)
    }
    return result
  }
  assert.equal((await check(other.id)).kind, 'deny')
  assert.equal((await check(own.id)).kind, 'allow')
  const guards = ctx.guards
  const block = guards.map(guard => guard({ name: 'schedule_create', agent: { id: 'b2' }, arguments: { target: { kind: 'new_session' } } })).find(Boolean)
  assert.match(block, /own chat/)
})
