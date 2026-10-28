// Scheduled tasks: Settings → Scheduled tasks, a Bot's card in its settings, and the
// line in its details panel. DSH runs the tasks (see src/host/schedules.js); a task
// sends its prompt to the Bot's chat when it is due.
import { createElement as h, Fragment, useEffect, useId, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { BotAvatar, RoomAvatar } from './mark.js'
import { ChevronLeftIcon, ChevronRightIcon, ClockIcon, CloseIcon, PlusIcon, TrashIcon } from './icons.js'
import { Segmented } from './motion.js'
import { dateLocale, hostText, t } from './i18n.js'
import { useEscape } from './overlay-hooks.js'
import { dateKey, monthDays, runsOnDay } from './schedule-calendar.js'
import { TASK_TEMPLATES } from './schedule-templates.js'
import { DateTimePicker, TimePicker, SCHEDULE_PICKER_CSS } from './schedule-picker.js'

const POLL_MS = 30_000

// One view for every surface that shows tasks; each asks again when it mounts.
let shared = null
const listeners = new Set()
function publish(view) {
  shared = view
  for (const listener of listeners) listener(view)
}
export function useSchedules(actions) {
  const [view, setView] = useState(shared)
  useEffect(() => {
    listeners.add(setView)
    let stopped = false
    let timer
    const load = () => actions.schedules?.()
      .then((next) => { if (!stopped) publish(next) })
      .catch(() => {})
      .finally(() => { if (!stopped) timer = setTimeout(load, POLL_MS) })
    load()
    return () => { stopped = true; clearTimeout(timer); listeners.delete(setView) }
  }, [])
  return view
}

const localZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone
const clock = time => String(time ?? '').slice(0, 5)
const when = (ms, options) => new Intl.DateTimeFormat(dateLocale(), options).format(ms)
function dayAndTime(ms) {
  const sameYear = new Date(ms).getFullYear() === new Date().getFullYear()
  return when(ms, { ...(sameYear ? {} : { year: 'numeric' }), month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
function weekdayNames(days) {
  const names = days.map(day => when(Date.UTC(2024, 0, day), { weekday: 'short', timeZone: 'UTC' }))
  return names.join(dateLocale().startsWith('zh') ? '、' : ', ')
}
function everyText(seconds) {
  if (seconds % 86400 === 0) return seconds === 86400 ? t('Every day') : t('Every {count} days', { count: seconds / 86400 })
  if (seconds % 3600 === 0) return seconds === 3600 ? t('Every hour') : t('Every {count} hours', { count: seconds / 3600 })
  return t('Every {count} minutes', { count: Math.round(seconds / 60) })
}

// How often a task runs, in the user's words.
export function timingText(task) {
  const zone = task.timeZone && task.timeZone !== localZone() ? ` (${task.timeZone})` : ''
  switch (task.kind) {
    case 'after':
    case 'at': return t('Once, {time}', { time: dayAndTime(Date.parse(task.scheduledAt)) })
    case 'every': return everyText(task.everySeconds)
    case 'daily': return `${t('Every day at {time}', { time: clock(task.time) })}${zone}`
    case 'weekly': {
      const days = (task.weekdays ?? []).join()
      const text = days === '1,2,3,4,5' ? t('Every weekday at {time}', { time: clock(task.time) })
        : days === '6,7' ? t('Every weekend at {time}', { time: clock(task.time) })
          : days === '1,2,3,4,5,6,7' ? t('Every day at {time}', { time: clock(task.time) })
            : t('Every {days} at {time}', { days: weekdayNames(task.weekdays ?? []), time: clock(task.time) })
      return `${text}${zone}`
    }
    case 'cron': return `${t('On the schedule {expression}', { expression: task.expression })}${zone}`
    default: return ''
  }
}
const nextText = task => (task.status === 'active' ? t('Next: {time}', { time: dayAndTime(Date.parse(task.scheduledAt)) }) : t('Finished'))

function TaskRow({ task, actions, onView, showBot, roster }) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!confirming) return undefined
    const timer = setTimeout(() => setConfirming(false), 3000)
    return () => clearTimeout(timer)
  }, [confirming])
  const remove = () => {
    if (!confirming) { setConfirming(true); return }
    setBusy(true)
    setError('')
    void actions.scheduleDelete(task.sessionId, task.id).then(onView, failure => {
      setBusy(false)
      setConfirming(false)
      setError(hostText(failure?.message ?? String(failure)))
    })
  }
  const room = task.roomId ? roster.roomsById[task.roomId] : undefined
  return h('div', { className: 'bt-set-row bt-task', 'data-done': task.status === 'active' ? undefined : '', 'data-busy': busy || undefined },
    showBot ? h(BotAvatar, { bot: roster.byId[task.botId], size: 28, badge: false, live: false }) : null,
    h('span', { className: 'bt-set-copy' },
      h('span', { className: 'bt-task-title' }, task.title),
      h('span', { className: 'bt-set-hint' }, [timingText(task), room ? t('in {name}', { name: room.name }) : ''].filter(Boolean).join(' · ')),
      task.prompt && task.prompt !== task.title ? h('span', { className: 'bt-task-prompt' }, task.prompt) : null,
      error ? h('span', { className: 'bt-danger bt-set-hint', role: 'alert' }, error) : null),
    h('span', { className: 'bt-task-next' }, nextText(task)),
    h('button', {
      type: 'button', className: 'bt-mini bt-task-remove', 'data-confirm': confirming || undefined, disabled: busy,
      'aria-label': confirming ? t('Click again to delete') : t('Delete task'), title: confirming ? undefined : t('Delete task'), onClick: remove,
    }, confirming ? t('Delete') : h(TrashIcon)))
}

const pad = number => String(number).padStart(2, '0')
function inAnHour() {
  const date = new Date(Date.now() + 3600_000)
  date.setMinutes(0, 0, 0)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:00`
}
const KINDS = [['at', 'Once'], ['daily', 'Every day'], ['weekly', 'Every week'], ['every', 'Repeat']]
const UNITS = [['minutes', 1, 'minutes'], ['hours', 60, 'hours'], ['days', 1440, 'days']]

function TaskForm({ roster, actions, start, template, day, onDone, onCancel }) {
  // A task goes to a Bot's chat or to a group chat, where it reads as your message.
  const [target, setTarget] = useState(start ?? roster.bots[0]?.id ?? roster.rooms[0]?.id ?? '')
  const [title, setTitle] = useState(template ? t(template.title) : '')
  const [prompt, setPrompt] = useState(template ? t(template.prompt) : '')
  const [scope, setScope] = useState('')
  const [kind, setKind] = useState(template?.kind ?? (day ? 'at' : 'daily'))
  const [at, setAt] = useState(() => day && dateKey(day) !== dateKey(new Date()) ? `${dateKey(day)}T09:00` : inAnHour())
  const [time, setTime] = useState(template?.time ?? '09:00')
  const [weekdays, setWeekdays] = useState(template?.weekdays ?? [1, 2, 3, 4, 5])
  const [count, setCount] = useState(1)
  const [unit, setUnit] = useState('hours')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const close = () => { if (!busy) onCancel() }
  const timing = () => {
    if (kind === 'at') return { kind, at: new Date(at).toISOString() }
    if (kind === 'every') return { kind, minutes: Math.round(Number(count) * UNITS.find(([id]) => id === unit)[1]) }
    return { kind, time, timeZone: localZone(), ...(kind === 'weekly' ? { weekdays } : {}) }
  }
  const submit = (event) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    let when
    try { when = timing() } catch { setError(t('Pick a date and time')); setBusy(false); return }
    const instructions = template ? `${t('Research scope')}: ${scope.trim()}\n\n${prompt}` : prompt
    void actions.scheduleCreate({ target, title, prompt: instructions, when })
      .then(onDone, (failure) => { setError(hostText(failure?.message ?? String(failure))); setBusy(false) })
  }
  const toggleDay = day => setWeekdays(days => (days.includes(day) ? days.filter(item => item !== day) : [...days, day].sort()))
  return h(TaskDialog, { title: template ? t(template.title) : t('New task'), onClose: close },
    h('p', { className: 'bt-agenda-dialog-intro' }, template ? t(template.description) : t('Choose who should run the task, what to do, and when.')),
    h('form', { className: 'bt-set-card bt-task-form', onSubmit: submit },
    h('fieldset', { disabled: busy, className: 'bt-task-fields' },
    h('label', { className: 'bt-set-row bt-bs-row' },
      h('span', { className: 'bt-set-copy' }, h('span', { className: 'bt-bs-label' }, t('Send to'))),
      h('select', { className: 'bt-select bt-task-bot', value: target, onChange: event => setTarget(event.target.value) },
        h('optgroup', { label: t('Bots') }, roster.bots.map(bot => h('option', { key: bot.id, value: bot.id }, bot.name))),
        roster.rooms.length > 0 ? h('optgroup', { label: t('Group chats') }, roster.rooms.map(room => h('option', { key: room.id, value: room.id }, room.name))) : null)),
    h('label', { className: 'bt-set-row bt-bs-row' },
      h('span', { className: 'bt-set-copy' }, h('span', { className: 'bt-bs-label' }, t('Name'))),
      h('input', { className: 'bt-bs-input', value: title, maxLength: 120, required: true, placeholder: t('Morning briefing'), autoFocus: true, onChange: event => setTitle(event.target.value) })),
    template ? h('label', { className: 'bt-set-row bt-bs-row bt-bs-stack' },
      h('span', { className: 'bt-bs-label' }, t(template.scope)),
      h('input', { className: 'bt-bs-input', value: scope, required: true, placeholder: t(template.example), onChange: event => setScope(event.target.value) })) : null,
    h('label', { className: 'bt-set-row bt-bs-row bt-bs-stack' },
      h('span', { className: 'bt-set-copy' }, h('span', { className: 'bt-bs-label' }, t('What to do'))),
      h('textarea', { className: 'bt-bs-input bt-bs-area', value: prompt, required: true, rows: template ? 5 : 4, placeholder: t('Sum up what changed since yesterday and what needs me today.'), onChange: event => setPrompt(event.target.value) })),
    h('div', { className: 'bt-set-row bt-bs-row bt-bs-stack' },
      h('span', { className: 'bt-set-copy' }, h('span', { className: 'bt-bs-label' }, t('When'))),
      h(Segmented, { label: t('When'), value: kind }, KINDS.map(([id, label]) => h('button', { key: id, type: 'button', 'aria-pressed': kind === id, onClick: () => setKind(id) }, t(label)))),
      h('div', { key: kind, className: 'bt-task-when bt-veil' },
        kind === 'at' ? h(DateTimePicker, { value: at, onChange: setAt }) : null,
        kind === 'weekly' ? h('div', { className: 'bt-task-days', role: 'group', 'aria-label': t('Days') }, [1, 2, 3, 4, 5, 6, 7].map(day => h('button', {
          key: day, type: 'button', className: 'bt-task-day', 'aria-pressed': weekdays.includes(day), onClick: () => toggleDay(day),
        }, when(Date.UTC(2024, 0, day), { weekday: 'narrow', timeZone: 'UTC' })))) : null,
        kind === 'daily' || kind === 'weekly' ? h(TimePicker, { value: time, onChange: setTime }) : null,
        kind === 'every' ? h(Fragment, null,
          h('span', { className: 'bt-task-every' }, t('Every')),
          h('input', { className: 'bt-input bt-task-count', type: 'number', min: 1, max: 10080 / UNITS.find(([id]) => id === unit)[1], required: true, value: count, 'aria-label': t('How many'), onChange: event => setCount(event.target.value) }),
          h('select', { className: 'bt-select bt-task-unit', value: unit, 'aria-label': t('Unit'), onChange: event => setUnit(event.target.value) },
            UNITS.map(([id, , label]) => h('option', { key: id, value: id }, t(label))))) : null)),
    error ? h('div', { className: 'bt-set-row', role: 'alert' }, h('span', { className: 'bt-danger bt-set-hint' }, error)) : null),
    h('div', { className: 'bt-set-row bt-task-foot' },
      h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: close }, t('Cancel')),
      h('button', { type: 'submit', className: 'bt-send bt-soft-sm', disabled: busy || !target || !title.trim() || !prompt.trim() || (template && !scope.trim()) || (kind === 'weekly' && !weekdays.length) }, busy ? t('Creating…') : t('Create task')))))
}

function TaskDialog({ title, onClose, children }) {
  const ref = useRef(null)
  const heading = useId()
  useEscape(onClose)
  useEffect(() => {
    const dialog = ref.current
    dialog.showModal()
    return () => dialog.close()
  }, [])
  return createPortal(h('dialog', {
    ref, className: 'bt-agenda-dialog', 'aria-labelledby': heading,
    onCancel: event => event.preventDefault(),
    onMouseDown: event => { if (event.target === event.currentTarget) onClose() },
  }, h('div', { className: 'bt-agenda-dialog-body' },
    h('header', { className: 'bt-agenda-dialog-head' }, h('span', { className: 'bt-agenda-symbol' }, h(ClockIcon)),
      h('h2', { id: heading }, title),
      h('button', { type: 'button', className: 'bt-icon-btn', 'aria-label': t('Close'), onClick: onClose }, h(CloseIcon))),
    children)), document.body)
}

// Settings has no schedule service to show: Automation tasks are off in DSH.
function AutomationOff({ actions }) {
  return h('div', { className: 'bt-set-card bt-task-off' },
    h('span', { className: 'bt-task-off-mark' }, h(ClockIcon)),
    h('span', { className: 'bt-task-off-title' }, t('Turn on Automation tasks in DSH')),
    h('span', { className: 'bt-set-hint' }, t('Switch on Automation tasks on the Plugins page in Harness settings.')),
    actions.openHarnessSettings ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: actions.openHarnessSettings }, t('Open Harness settings')) : null)
}

export function SchedulesPage({ roster, actions, start }) {
  const view = useSchedules(actions)
  const [adding, setAdding] = useState(start ? { start } : null)
  const [tab, setTab] = useState('mine')
  const [layout, setLayout] = useState('calendar')
  const [day, setDay] = useState(() => new Date())
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1))
  const [detail, setDetail] = useState(null)
  useEffect(() => { if (start) setAdding({ start }) }, [start])
  if (view === null) return h('div', { className: 'bt-set-hint' }, t('Loading…'))
  if (!view.available) return h(AutomationOff, { actions })
  const shown = next => { publish(next); setAdding(null) }
  const add = (options = {}) => setAdding(options)
  const task = view.tasks.find(item => item.id === detail?.id && item.sessionId === detail?.sessionId)
  const byChat = [
    ...roster.bots.map(bot => [bot.id, h(BotAvatar, { bot, size: 18, badge: false, live: false }), bot.name, view.tasks.filter(task => task.botId === bot.id)]),
    ...roster.rooms.map(room => [room.id, h(RoomAvatar, { room, roster, size: 18 }), room.name, view.tasks.filter(task => task.botId === undefined && task.roomId === room.id)]),
  ].filter(([, , , tasks]) => tasks.length > 0)
  return h('div', { className: 'bt-agenda' },
    h('p', { className: 'bt-agenda-intro' }, t('Make time for research, customer follow-ups and team reviews.')),
    h('div', { className: 'bt-agenda-toolbar' },
      h(Segmented, { label: t('Task collection'), value: tab },
        [['mine', 'My schedule'], ['recommended', 'Recommended tasks']].map(([id, label]) => h('button', { key: id, type: 'button', 'aria-pressed': tab === id, onClick: () => setTab(id) }, t(label)))),
      h('div', { className: 'bt-agenda-tools' },
        tab === 'mine' ? h(Segmented, { label: t('Schedule view'), value: layout },
          [['calendar', 'Calendar'], ['list', 'List']].map(([id, label]) => h('button', { key: id, type: 'button', 'aria-pressed': layout === id, onClick: () => setLayout(id) }, t(label)))) : null,
        h('button', { type: 'button', className: 'bt-agenda-primary bt-with-icon', onClick: () => add() }, h(PlusIcon), t('New task')))),
    tab === 'recommended' ? h(TaskRecommendations, { onPick: template => add({ template, start: roster.bots.find(bot => bot.templateId === template.role)?.id }) })
      : layout === 'calendar' ? h(AgendaCalendar, { tasks: view.tasks, roster, day, month, setDay, setMonth, onAdd: () => add({ day }), onOpen: setDetail })
        : h('div', { className: 'bt-agenda-list' }, byChat.length === 0
          ? h('div', { className: 'bt-set-card' }, h('div', { className: 'bt-set-row' }, h('span', { className: 'bt-set-hint' }, t('No scheduled tasks yet.'))))
          : byChat.map(([id, avatar, name, tasks]) => h('section', { key: id, className: 'bt-set-section' },
            h('h3', { className: 'bt-task-head' }, avatar, name),
            h('div', { className: 'bt-set-card' }, tasks.map(task => h(TaskRow, { key: `${task.sessionId}:${task.id}`, task, actions, roster, onView: publish })))))),
    adding ? h(TaskForm, { roster, actions, ...adding, start: adding.start ?? start, onDone: shown, onCancel: () => setAdding(null) }) : null,
    task ? h(TaskDialog, { title: task.title, onClose: () => setDetail(null) },
      h('div', { className: 'bt-agenda-detail-meta' }, h(ClockIcon), timingText(task)),
      h('div', { className: 'bt-agenda-detail-prompt' }, task.prompt),
      h('p', { className: 'bt-set-hint' }, t('Results appear in {name}.', { name: destination(task, roster) })),
      h('div', { className: 'bt-set-card' }, h(TaskRow, { task, actions, roster, onView: publish }))) : null)
}

const destination = (task, roster) => task.botId ? roster.byId[task.botId]?.name ?? t('Bot') : roster.roomsById[task.roomId]?.name ?? t('Group chat')

function AgendaCalendar({ tasks, roster, day, month, setDay, setMonth, onAdd, onOpen }) {
  const days = useMemo(() => monthDays(month).map(date => ({ date, runs: runsOnDay(tasks, date) })), [tasks, month])
  const selected = days.find(item => dateKey(item.date) === dateKey(day))?.runs ?? []
  const monthTasks = new Set(days.filter(item => item.date.getMonth() === month.getMonth()).flatMap(item => item.runs.map(run => `${run.task.sessionId}:${run.task.id}`))).size
  const today = dateKey(new Date())
  const move = delta => {
    const next = new Date(month.getFullYear(), month.getMonth() + delta, 1)
    setMonth(next)
    setDay(new Date(next.getFullYear(), next.getMonth(), Math.min(day.getDate(), new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate())))
  }
  const select = date => { setDay(date); if (date.getMonth() !== month.getMonth()) setMonth(new Date(date.getFullYear(), date.getMonth(), 1)) }
  return h('div', { className: 'bt-agenda-columns' },
      h('section', { className: 'bt-agenda-month', 'aria-label': t('Calendar') },
        h('header', { className: 'bt-agenda-month-head' },
          h('button', { type: 'button', className: 'bt-icon-btn', 'aria-label': t('Previous month'), onClick: () => move(-1) }, h(ChevronLeftIcon)),
          h('h3', { 'aria-live': 'polite' }, when(month, { year: 'numeric', month: 'long' })),
          h('button', { type: 'button', className: 'bt-icon-btn', 'aria-label': t('Next month'), onClick: () => move(1) }, h(ChevronRightIcon)),
          h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => select(new Date()) }, t('Today')),
          h('span', { className: 'bt-agenda-month-count' }, t('{count} tasks', { count: monthTasks }))),
        h('div', { className: 'bt-agenda-weekdays', 'aria-hidden': true }, Array.from({ length: 7 }, (_, index) => h('span', { key: index }, when(Date.UTC(2024, 0, index + 1), { weekday: 'narrow', timeZone: 'UTC' })))),
        h('div', { className: 'bt-agenda-grid' }, days.map(({ date, runs }) => {
          const key = dateKey(date)
          return h('button', {
            key, type: 'button', className: 'bt-agenda-day', 'data-outside': date.getMonth() !== month.getMonth() || undefined,
            'aria-pressed': key === dateKey(day), 'aria-current': key === today ? 'date' : undefined,
            'aria-label': `${when(date, { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })}, ${t('{count} tasks', { count: runs.length })}`,
            onClick: () => select(date),
          }, h('span', { className: 'bt-agenda-date' }, date.getDate()),
          key === today ? h('span', { className: 'bt-agenda-today' }, t('Today')) : null,
          runs.length ? h('span', { className: 'bt-agenda-dots', 'aria-hidden': true }, Array.from({ length: Math.min(3, runs.length) }, (_, index) => h('i', { key: index })), runs.length > 3 ? h('small', null, `+${runs.length - 3}`) : null) : null)
        }))),
      h('section', { className: 'bt-agenda-daily', 'aria-label': t('Tasks on selected day') },
        h('header', { className: 'bt-agenda-daily-head' },
          h('div', { 'aria-live': 'polite' }, h('h3', null, when(day, { month: 'long', day: 'numeric', weekday: 'short' })), h('span', null, t('{count} tasks', { count: selected.length }))),
          h('button', { type: 'button', className: 'bt-agenda-add bt-icon-btn', 'aria-label': t('Add task on this day'), onClick: onAdd }, h(PlusIcon))),
        selected.length ? h('div', { className: 'bt-agenda-runs' }, selected.map(({ task, at, count }) => h('button', {
          key: `${task.sessionId}:${task.id}`, type: 'button', className: 'bt-agenda-run', onClick: () => onOpen(task),
        }, h('span', { className: 'bt-agenda-run-time' }, when(at, { hour: '2-digit', minute: '2-digit' }), count > 1 ? h('small', null, t('{count} runs', { count })) : null),
        h('span', { className: 'bt-agenda-run-copy' }, h('strong', null, task.title), h('span', null, destination(task, roster)), h('small', null, timingText(task))), h(ChevronRightIcon))))
          : h('div', { className: 'bt-agenda-empty' },
            h('span', { className: 'bt-agenda-empty-symbol' }, h(ClockIcon)),
            h('strong', null, t('A little room in your day')),
            h('p', null, t('No upcoming tasks on this date. Give your team something to work on.')),
            h('button', { type: 'button', className: 'bt-soft bt-soft-sm bt-with-icon', onClick: onAdd }, h(PlusIcon), t('Add task')))))
}

function TaskRecommendations({ onPick }) {
  return h('section', { className: 'bt-agenda-recommendations', 'aria-label': t('Recommended tasks') },
    h('div', { className: 'bt-agenda-recommend-head' }, h('h3', null, t('A starting point for your team')),
      h('p', null, t('Choose a task, set its scope, and send it to an expert or group.'))),
    h('div', { className: 'bt-agenda-template-grid' }, TASK_TEMPLATES.map(template => h('button', {
      key: template.id, type: 'button', className: 'bt-agenda-template', onClick: () => onPick(template),
    }, h('span', { className: 'bt-agenda-template-top' }, h('span', null, t(template.category)), h('span', null, template.mark)),
    h('strong', null, t(template.title)), h('span', { className: 'bt-agenda-template-desc' }, t(template.description)),
    h('span', { className: 'bt-agenda-template-output' }, t(template.output)),
    h('span', { className: 'bt-agenda-template-foot' }, h('span', null, timingText(template)), h(PlusIcon))))))
}

// A Bot's tasks in its settings form, with the way to add one.
export function BotSchedules({ bot, roster, actions }) {
  const view = useSchedules(actions)
  if (view === null) return null
  const tasks = view.available ? view.tasks.filter(task => task.botId === bot.id) : []
  return h('section', { className: 'bt-set-section' },
    h('h3', null, t('Scheduled tasks')),
    h('div', { className: 'bt-set-card' },
      !view.available
        ? h('div', { className: 'bt-set-row bt-bs-row' },
            h('span', { className: 'bt-set-copy' }, h('span', { className: 'bt-set-hint' }, t('Switch on Automation tasks on the Plugins page in Harness settings.'))),
            actions.openHarnessSettings ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: actions.openHarnessSettings }, t('Open Harness settings')) : null)
        : [
            ...tasks.map(task => h(TaskRow, { key: task.id, task, actions, roster, onView: publish })),
            h('button', { key: 'new', type: 'button', className: 'bt-set-row bt-bs-row bt-gs-add', onClick: () => actions.openSettings('schedules', bot.id) }, h(PlusIcon), t('New task')),
          ]))
}

// The details panel's line: the Bot's next tasks, or how to add one.
export function ScheduleSummary({ bot, actions }) {
  const view = useSchedules(actions)
  const tasks = view?.available ? view.tasks.filter(task => task.botId === bot.id && task.status === 'active') : []
  return h('div', null,
    h('div', { className: 'bt-section-title' }, t('Scheduled tasks')),
    tasks.length === 0
      ? h('button', { type: 'button', className: 'bt-more', onClick: () => actions.openSettings('schedules', bot.id) }, view?.available === false ? t('Switch on Automation tasks on the Plugins page in Harness settings.') : t('No scheduled tasks yet. Add one'))
      : h('div', { className: 'bt-task-list' }, tasks.slice(0, 3).map(task => h('button', { key: task.id, type: 'button', className: 'bt-task-line', onClick: () => actions.openSettings('schedules') },
          h(ClockIcon), h('span', { className: 'bt-task-line-title' }, task.title), h('span', { className: 'bt-task-line-when' }, timingText(task))))))
}

export const SCHEDULE_CSS = `
${SCHEDULE_PICKER_CSS}
.bt-agenda{display:flex;flex-direction:column;gap:20px;min-width:0;container-type:inline-size}
.bt-agenda-intro{margin:0;color:var(--bt-ink-2);font-size:13px;line-height:1.7}
.bt-agenda-toolbar,.bt-agenda-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.bt-agenda-toolbar{justify-content:space-between}
.bt-agenda-toolbar .bt-seg{flex:none}
.bt-agenda-toolbar .bt-seg button{flex:none;padding:0 14px;white-space:nowrap}
.bt-agenda-primary{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:9px 14px;border:0;border-radius:999px;background:var(--bt-user);color:var(--bt-user-ink);font:inherit;font-size:12px;cursor:pointer}
.bt-agenda-primary:hover{opacity:.85}
.bt-agenda-columns{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:18px;align-items:start}
.bt-agenda-month,.bt-agenda-daily{border:1px solid var(--bt-line);border-radius:16px;background:var(--bt-card);padding:18px;min-width:0}
.bt-agenda-month-head{display:flex;align-items:center;gap:6px;margin-bottom:22px;flex-wrap:wrap}
.bt-agenda-month-head h3{margin:0;font-size:15px;font-weight:650}
.bt-agenda-month-head .bt-soft{margin-left:4px}
.bt-agenda-month-count{margin-left:auto;color:var(--bt-ink-2);font-size:11px}
.bt-agenda-weekdays,.bt-agenda-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:4px}
.bt-agenda-weekdays{margin-bottom:10px;text-align:center;color:var(--bt-ink-2);font-size:11px}
.bt-agenda-day{position:relative;display:flex;align-items:center;flex-direction:column;min-width:0;min-height:62px;padding:8px 2px;border:1px solid transparent;border-radius:10px;background:none;color:var(--bt-ink);font:inherit;cursor:pointer;transition:background-color .12s ease,border-color .12s ease}
.bt-agenda-day:hover{background:var(--bt-hover)}
.bt-agenda-day[data-outside]{color:var(--bt-ink-3)}
.bt-agenda-day[aria-current=date]{border-color:var(--bt-line-2)}
.bt-agenda-day[aria-pressed=true]{background:var(--bt-user);color:var(--bt-user-ink);border-color:var(--bt-user)}
.bt-agenda-date{font-size:14px;line-height:18px;font-weight:600;font-variant-numeric:tabular-nums}
.bt-agenda-today{font-size:9px;line-height:12px}
.bt-agenda-dots{display:flex;align-items:center;gap:3px;margin-top:auto;padding-top:5px;color:var(--bt-accent);height:9px}
.bt-agenda-dots i{width:4px;height:4px;border-radius:50%;background:currentColor}
.bt-agenda-dots small{font-size:8px}
.bt-agenda-day[aria-pressed=true] .bt-agenda-dots{color:inherit}
.bt-agenda-day[data-outside] .bt-agenda-dots{opacity:.45}
.bt-agenda-daily-head{display:flex;justify-content:space-between;align-items:center;gap:12px;padding-bottom:18px}
.bt-agenda-daily-head h3{margin:0 0 5px;font-size:14px;font-weight:600}
.bt-agenda-daily-head span{font-size:11px;color:var(--bt-ink-2)}
.bt-agenda-add{background:var(--bt-hover);border-radius:50%}
.bt-agenda-empty{min-height:246px;border:1px dashed var(--bt-line-2);border-radius:12px;display:flex;align-items:center;justify-content:center;flex-direction:column;padding:24px 16px;text-align:center;gap:12px}
.bt-agenda-empty-symbol,.bt-agenda-symbol{display:flex;align-items:center;justify-content:center;flex:none;width:44px;height:44px;border-radius:12px;color:var(--bt-accent);background:color-mix(in srgb,var(--bt-accent) 10%,transparent)}
.bt-agenda-empty-symbol svg{width:22px;height:22px}
.bt-agenda-empty strong{font-size:14px;font-weight:550}
.bt-agenda-empty p{max-width:220px;margin:0;font-size:12px;line-height:1.7;color:var(--bt-ink-2)}
.bt-agenda-runs{display:flex;flex-direction:column;gap:8px;max-height:424px;overflow-y:auto;scrollbar-width:thin}
.bt-agenda-run{display:flex;align-items:flex-start;gap:10px;width:100%;border:1px solid var(--bt-line);border-radius:12px;padding:12px 10px;background:var(--bt-main);color:var(--bt-ink);font:inherit;text-align:left;cursor:pointer}
.bt-agenda-run:hover{border-color:var(--bt-line-2);background:var(--bt-hover)}
.bt-agenda-run>svg{flex:none;align-self:center;color:var(--bt-ink-3)}
.bt-agenda-run-time{display:flex;flex-direction:column;gap:4px;padding-top:1px;color:var(--bt-accent);font-size:12px;font-weight:600;font-variant-numeric:tabular-nums}
.bt-agenda-run-time small{font-size:9px;font-weight:400;color:var(--bt-ink-2)}
.bt-agenda-run-copy{display:flex;flex-direction:column;gap:6px;flex:1;min-width:0;overflow-wrap:anywhere}
.bt-agenda-run-copy strong{font-size:12px;line-height:1.5;font-weight:600}
.bt-agenda-run-copy>span,.bt-agenda-run-copy small{font-size:11px;color:var(--bt-ink-2);line-height:1.5}
.bt-agenda-list{display:flex;flex-direction:column;gap:20px}
.bt-agenda-recommend-head h3{font-size:17px;font-weight:600;margin:0 0 8px}
.bt-agenda-recommend-head p{font-size:12px;color:var(--bt-ink-2);margin:0 0 18px;line-height:1.7}
.bt-agenda-template-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.bt-agenda-template{display:flex;align-items:stretch;flex-direction:column;gap:12px;min-width:0;padding:18px;border:1px solid var(--bt-line);border-radius:16px;background:var(--bt-card);color:var(--bt-ink);text-align:left;font:inherit;cursor:pointer;transition:background-color .12s ease,border-color .12s ease}
.bt-agenda-template:hover{border-color:var(--bt-accent);background:color-mix(in srgb,var(--bt-accent) 4%,var(--bt-card))}
.bt-agenda-template-top{display:flex;justify-content:space-between;gap:8px;font-size:10px;color:var(--bt-ink-2)}
.bt-agenda-template-top>span:last-child{color:var(--bt-accent);font-variant-numeric:tabular-nums}
.bt-agenda-template>strong{font-size:14px;line-height:1.5;font-weight:600}
.bt-agenda-template-desc{font-size:12px;line-height:1.7;color:var(--bt-ink-2);flex:1}
.bt-agenda-template-output{font-size:10px;line-height:1.6;color:var(--bt-ink-2)}
.bt-agenda-template-foot{display:flex;justify-content:space-between;align-items:center;gap:6px;border-top:1px solid var(--bt-line);padding-top:12px;font-size:10px;line-height:1.5;color:var(--bt-ink-2)}
.bt-agenda-template-foot svg{flex:none;color:var(--bt-accent);width:14px;height:14px}
.bt-agenda-dialog{box-sizing:border-box;position:fixed;inset:0;width:min(580px,calc(100vw - 32px));max-height:calc(100dvh - 64px);margin:auto;padding:0;border:1px solid var(--bt-line-2);border-radius:20px;background:var(--bt-main);color:var(--bt-ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;box-shadow:0 24px 80px var(--bt-line-2);overflow-y:auto;scrollbar-width:thin}
.bt-agenda-dialog::backdrop{background:color-mix(in srgb,var(--bt-ink) 30%,transparent)}
.bt-agenda-dialog-body{padding:24px}
.bt-agenda-dialog-head{display:flex;align-items:center;gap:12px;margin-bottom:16px}
.bt-agenda-dialog-head h2{flex:1;min-width:0;overflow-wrap:anywhere;margin:0;font-size:18px;line-height:1.5;font-weight:600}
.bt-agenda-dialog-head .bt-icon-btn{flex:none}
.bt-agenda-dialog-intro{font-size:12px;line-height:1.8;color:var(--bt-ink-2);margin:0 0 20px}
.bt-task-fields{margin:0;padding:0;border:0;min-width:0}
.bt-task-fields>.bt-set-row+.bt-set-row{border-top:1px solid var(--bt-line)}
.bt-task-fields .bt-bs-stack{align-items:stretch}
.bt-task-fields .bt-bs-stack>.bt-bs-input{width:100%;box-sizing:border-box;max-width:none}
.bt-task-fields .bt-bs-stack>input.bt-bs-input{flex:none;height:36px;margin:0;background:var(--bt-main);border-color:var(--bt-line);text-align:left}
.bt-task-fields .bt-bs-input{font-size:12px;line-height:1.7}
.bt-agenda-detail-meta{display:flex;align-items:center;gap:8px;font-size:12px;line-height:1.7;color:var(--bt-ink-2)}
.bt-agenda-detail-prompt{margin:18px 0;padding:16px;border-radius:12px;background:var(--bt-card);white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.8}
.bt-agenda button:focus-visible{outline:2px solid var(--bt-accent);outline-offset:2px}
@container (max-width:720px){.bt-agenda-columns{grid-template-columns:minmax(0,1fr)}.bt-agenda-template-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.bt-agenda-empty{min-height:160px}.bt-agenda-day{min-height:58px}}
@container (max-width:400px){.bt-agenda-template-grid{grid-template-columns:minmax(0,1fr)}.bt-agenda-month,.bt-agenda-daily{padding:12px}.bt-agenda-month-count{display:none}.bt-agenda-day{min-height:52px}.bt-agenda-tools{justify-content:space-between;width:100%}}
.bt-task{gap:10px}
.bt-task[data-done]{opacity:.6}
.bt-task[data-busy]{opacity:.4}
.bt-task-title{font-size:13px;line-height:18px;font-weight:500;overflow-wrap:anywhere}
.bt-task-prompt{font-size:12px;line-height:16px;color:var(--bt-ink-2);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.bt-task-next{flex:none;font-size:12px;line-height:16px;color:var(--bt-ink-3);font-variant-numeric:tabular-nums;white-space:nowrap}
.bt-task-remove{display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:26px;color:var(--bt-ink-3)}
.bt-task-remove svg{width:14px;height:14px}
.bt-task-remove[data-confirm]{background:color-mix(in srgb,var(--bt-danger) 10%,transparent);color:var(--bt-danger)}
.bt-task-head{display:flex;align-items:center;gap:6px}
.bt-task-form{animation:bt-q-in .4s cubic-bezier(.22,1,.36,1),bt-veil-in .2s ease-out}
.bt-task-bot{width:auto;min-width:160px;max-width:58%}
.bt-task-when{display:flex;align-items:center;flex-wrap:wrap;gap:8px}
.bt-task-when .bt-input{width:auto;height:32px}
.bt-task-count{width:72px!important}
.bt-task-unit{width:auto;height:32px}
.bt-task-every{font-size:13px;color:var(--bt-ink-2)}
.bt-task-days{display:flex;gap:4px}
.bt-task-day{width:30px;height:30px;border-radius:50%;border:1px solid var(--bt-line);background:none;color:var(--bt-ink-2);font:inherit;font-size:12px;cursor:pointer;transition:background-color .12s ease,color .12s ease,border-color .12s ease}
.bt-task-day[aria-pressed=true]{background:var(--bt-user);border-color:var(--bt-user);color:var(--bt-user-ink)}
.bt-task-foot{flex-direction:row;justify-content:flex-end;gap:8px}
.bt-task-foot .bt-send{height:28px;font-size:12px}
.bt-task-off{align-items:center;gap:8px;padding:28px 20px;text-align:center}
.bt-task-off>*+*{border-top:0}
.bt-task-off-mark{width:44px;height:44px;border-radius:50%;background:var(--bt-hover);display:flex;align-items:center;justify-content:center;color:var(--bt-ink-2)}
.bt-task-off-mark svg{width:20px;height:20px}
.bt-task-off-title{font-size:14px;line-height:20px;font-weight:600}
.bt-task-off .bt-set-hint{max-width:380px}
.bt-task-list{display:flex;flex-direction:column;gap:2px}
.bt-task-line{display:flex;align-items:center;gap:8px;width:100%;min-width:0;padding:6px 8px;border:0;border-radius:8px;background:none;color:var(--bt-ink);font:inherit;font-size:13px;text-align:left;cursor:pointer;transition:background-color .12s ease}
.bt-task-line:hover{background:var(--bt-hover)}
.bt-task-line svg{flex:none;color:var(--bt-ink-3)}
.bt-task-line-title{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bt-task-line-when{flex:none;font-size:12px;color:var(--bt-ink-3)}
@media (prefers-reduced-motion:reduce){.bt-task-form{animation:none}}
/* Phone-width viewports: the form's fixed minimums would overflow; let the
   fields wrap and share the row. */
@media (max-width:640px){
  .bt-task-bot{min-width:0;width:100%;max-width:none}
  .bt-task-fields input.bt-bs-input{flex:none;width:100%;height:36px;margin:0;background:var(--bt-main);border-color:var(--bt-line);text-align:left}
  .bt-task-count{width:auto!important;flex:1 1 72px}
}
`
