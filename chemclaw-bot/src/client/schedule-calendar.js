const DAY = 86400_000
const pad = value => String(value).padStart(2, '0')
export const dateKey = date => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`

export function monthDays(month) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1)
  const offset = (first.getDay() + 6) % 7
  return Array.from({ length: 42 }, (_, index) => new Date(first.getFullYear(), first.getMonth(), 1 - offset + index))
}

const formatters = new Map()
function zoneParts(ms, zone) {
  if (!formatters.has(zone)) formatters.set(zone, new Intl.DateTimeFormat('en-GB', {
    timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }))
  const parts = formatters.get(zone).formatToParts(ms)
  return Object.fromEntries(parts.filter(part => part.type !== 'literal').map(part => [part.type, Number(part.value)]))
}
const utcOf = parts => Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second)

// Resolve a wall-clock time with both offsets around a DST transition. A repeated
// time has two candidates; a nonexistent time has none. DSH remains authoritative.
function wallTimes(date, time, zone) {
  const [hour, minute, second = 0] = time.split(':').map(Number)
  const wall = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), hour, minute, second)
  const offsets = new Set([-DAY, 0, DAY].map(delta => utcOf(zoneParts(wall + delta, zone)) - (wall + delta)))
  return [...offsets].map(offset => wall - offset).filter(ms => utcOf(zoneParts(ms, zone)) === wall).sort((a, b) => a - b)
}

// One row per task per local day, even for minute intervals. Past/completed runs
// are not execution history, and arbitrary cron expressions show only DSH's next run.
export function runsOnDay(tasks, day) {
  const start = new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime()
  const end = new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1).getTime()
  const runs = []
  for (const task of tasks) {
    const next = Date.parse(task.scheduledAt)
    if (task.status !== 'active' || !Number.isFinite(next) || next >= end) continue
    let at = next
    let count = 1
    if (task.kind === 'every' && task.everySeconds > 0) {
      const interval = task.everySeconds * 1000
      at = next + Math.max(0, Math.ceil((start - next) / interval)) * interval
      count = Math.ceil((end - at) / interval)
    } else if (task.kind === 'daily' || task.kind === 'weekly') {
      try {
        const zone = task.timeZone || 'UTC'
        const parts = zoneParts(start, zone)
        const candidates = new Set(next >= start && next < end ? [next] : [])
        for (let delta = -1; delta <= 2; delta++) {
          const date = new Date(Date.UTC(parts.year, parts.month - 1, parts.day + delta))
          const weekday = date.getUTCDay() || 7
          if (task.kind === 'weekly' && !task.weekdays?.includes(weekday)) continue
          const times = wallTimes(date, task.time, zone)
          const occurrence = times.find(ms => ms >= next)
          if (occurrence >= start && occurrence < end) candidates.add(occurrence)
        }
        at = Math.min(...candidates)
        count = candidates.size
      } catch {
        // Unknown legacy zones/timings still expose the next run supplied by DSH.
      }
    }
    if (at >= start && at < end) runs.push({ task, at, count })
  }
  return runs.sort((a, b) => a.at - b.at || a.task.title.localeCompare(b.task.title))
}
