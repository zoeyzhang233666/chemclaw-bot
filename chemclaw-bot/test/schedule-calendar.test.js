import assert from 'node:assert/strict'
import { test } from 'node:test'
import { dateKey, monthDays, runsOnDay } from '../src/client/schedule-calendar.js'

const task = (changes = {}) => ({ id: 'one', title: 'Research', status: 'active', kind: 'at', scheduledAt: '2030-01-01T09:00:00Z', ...changes })

test('month grid starts on Monday, includes adjacent months and crosses years', () => {
  const days = monthDays(new Date(2029, 11, 15))
  assert.equal(days.length, 42)
  assert.equal(days[0].getDay(), 1)
  assert.equal(dateKey(days[0]), '2029-11-26')
  assert.equal(dateKey(days.at(-1)), '2030-01-06')
  assert.ok(monthDays(new Date(2032, 1, 1)).some(day => dateKey(day) === '2032-02-29'))
})

test('single runs and cron use the service next date; finished/invalid tasks stay out', () => {
  const at = task()
  const day = new Date(at.scheduledAt)
  assert.equal(runsOnDay([at, task({ status: 'done' }), task({ scheduledAt: 'bad' })], day).length, 1)
  const cron = task({ kind: 'cron', expression: '* * * * *' })
  assert.equal(runsOnDay([cron], day).length, 1)
  day.setDate(day.getDate() + 1)
  assert.equal(runsOnDay([at, cron], day).length, 0)
})

test('daily and weekly projections respect the task zone and the next-run boundary', () => {
  const daily = task({ kind: 'daily', time: '09:00:00', timeZone: 'Asia/Shanghai', scheduledAt: '2030-01-02T01:00:00Z' })
  assert.equal(runsOnDay([daily], new Date('2030-01-01T01:00:00Z')).length, 0)
  assert.equal(runsOnDay([daily], new Date('2030-01-03T01:00:00Z'))[0].at, Date.parse('2030-01-03T01:00:00Z'))
  const weekly = { ...daily, kind: 'weekly', weekdays: [1, 5] }
  assert.equal(runsOnDay([weekly], new Date('2030-01-03T01:00:00Z')).length, 0)
  assert.equal(runsOnDay([weekly], new Date('2030-01-04T01:00:00Z')).length, 1)
})

test('minute repeats aggregate a day without expanding each execution', () => {
  const day = new Date(2030, 0, 5)
  const first = new Date(2030, 0, 5, 0, 0)
  const nextDay = new Date(2030, 0, 6)
  const repeat = task({ kind: 'every', everySeconds: 60, scheduledAt: first.toISOString() })
  const [run] = runsOnDay([repeat], day)
  assert.equal(run.at, first.getTime())
  assert.equal(run.count, (nextDay - day) / 60000)
  const [later] = runsOnDay([repeat], nextDay)
  assert.equal(later.at, nextDay.getTime())
})

test('DST changes keep a daily wall time and do not duplicate an ambiguous time', () => {
  const daily = task({ kind: 'daily', time: '09:00:00', timeZone: 'America/New_York', scheduledAt: '2030-03-08T14:00:00Z' })
  assert.equal(runsOnDay([daily], new Date('2030-03-09T14:00:00Z'))[0].at, Date.parse('2030-03-09T14:00:00Z'))
  assert.equal(runsOnDay([daily], new Date('2030-03-10T13:00:00Z'))[0].at, Date.parse('2030-03-10T13:00:00Z'))
  const autumn = task({ kind: 'daily', time: '01:30:00', timeZone: 'America/New_York', scheduledAt: '2030-11-02T05:30:00Z' })
  const [run] = runsOnDay([autumn], new Date('2030-11-03T06:30:00Z'))
  assert.equal(run.at, Date.parse('2030-11-03T05:30:00Z'))
  assert.equal(run.count, 1)
})

test('intervals keep elapsed time across a local DST day', () => {
  const day = new Date(2030, 2, 10)
  const start = new Date(2030, 2, 10)
  const end = new Date(2030, 2, 11)
  const [run] = runsOnDay([task({ kind: 'every', everySeconds: 3600, scheduledAt: start.toISOString() })], day)
  assert.equal(run.count, (end - start) / 3600000)
})

test('unknown legacy timezone falls back to the service next run', () => {
  const legacy = task({ kind: 'daily', time: '09:00:00', timeZone: 'Unknown/Zone' })
  assert.equal(runsOnDay([legacy], new Date(legacy.scheduledAt))[0].at, Date.parse(legacy.scheduledAt))
})

test('the authoritative next run is retained when the scheduler resolves a DST gap', () => {
  const gap = task({ kind: 'daily', time: '02:30:00', timeZone: 'America/New_York', scheduledAt: '2030-03-10T07:00:00Z' })
  const [run] = runsOnDay([gap], new Date(gap.scheduledAt))
  assert.equal(run.at, Date.parse(gap.scheduledAt))
  assert.equal(run.count, 1)
})
