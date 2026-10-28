import { createElement as h, useLayoutEffect, useRef, useState } from 'react'
import { ChevronLeftIcon, ChevronRightIcon, ClockIcon } from './icons.js'
import { dateLocale, t } from './i18n.js'
import { useEscape } from './overlay-hooks.js'
import { dateKey, monthDays } from './schedule-calendar.js'

const pad = value => String(value).padStart(2, '0')
const format = (date, options) => new Intl.DateTimeFormat(dateLocale(), options).format(date)

// A native popover stays above the task dialog and its scrolling form, while all
// its controls and colors are ours. Native light-dismiss also handles outside taps.
function PickerPopover({ anchor, label, onClose, onDismiss, children }) {
  const ref = useRef(null)
  useEscape(onClose)
  useLayoutEffect(() => {
    const node = ref.current
    node.showPopover()
    const place = () => {
      const rect = anchor.current.getBoundingClientRect()
      const viewport = window.visualViewport
      const top = viewport?.offsetTop ?? 0
      const bottom = top + (viewport?.height ?? window.innerHeight)
      const left = viewport?.offsetLeft ?? 0
      const right = left + (viewport?.width ?? window.innerWidth)
      node.style.left = `${Math.max(left + 12, Math.min(rect.left, right - node.offsetWidth - 12))}px`
      const below = rect.bottom + 6
      const above = rect.top - node.offsetHeight - 6
      node.style.top = `${Math.max(top + 12, Math.min(below + node.offsetHeight <= bottom - 12 ? below : above, bottom - node.offsetHeight - 12))}px`
    }
    place()
    for (const selected of node.querySelectorAll('[aria-selected=true]')) selected.scrollIntoView({ block: 'nearest' })
    node.querySelector('[aria-selected=true], [aria-pressed=true]')?.focus({ preventScroll: true })
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    window.visualViewport?.addEventListener('resize', place)
    return () => {
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
      window.visualViewport?.removeEventListener('resize', place)
    }
  }, [])
  return h('div', {
    ref, popover: 'auto', className: 'bt-schedule-popover', role: 'dialog', 'aria-label': label,
    onToggle: event => { if (event.newState === 'closed') onDismiss() },
  }, children)
}

function TimeColumn({ label, count, value, onChange }) {
  const keyboard = event => {
    const current = Number(event.target.dataset.index)
    const index = { ArrowDown: (current + 1) % count, ArrowUp: (current + count - 1) % count, Home: 0, End: count - 1 }[event.key]
    if (index === undefined) return
    event.preventDefault()
    onChange(pad(index))
    const option = event.currentTarget.querySelector(`[data-index="${index}"]`)
    option.focus({ preventScroll: true })
    option.scrollIntoView({ block: 'nearest' })
  }
  return h('section', { className: 'bt-schedule-time-column' },
    h('h4', null, label),
    h('div', { className: 'bt-schedule-time-options', role: 'listbox', 'aria-label': label, onKeyDown: keyboard },
      Array.from({ length: count }, (_, index) => h('button', {
        key: index, type: 'button', role: 'option', 'data-index': index, 'aria-selected': pad(index) === value,
        tabIndex: pad(index) === value ? 0 : -1, onClick: () => onChange(pad(index)),
      }, pad(index)))))
}

export function TimePicker({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const anchor = useRef(null)
  const button = useRef(null)
  const [hour, minute] = /^([01]\d|2[0-3]):[0-5]\d$/.test(value) ? value.split(':') : ['00', '00']
  const close = () => { setOpen(false); button.current?.focus() }
  return h('div', { className: 'bt-schedule-time', ref: anchor },
    h('input', {
      type: 'text', inputMode: 'numeric', required: true, maxLength: 5, pattern: '([01][0-9]|2[0-3]):[0-5][0-9]',
      placeholder: 'HH:mm', value, 'aria-label': t('Time'), onChange: event => onChange(event.target.value),
    }),
    h('button', {
      ref: button, type: 'button', className: 'bt-icon-btn', 'aria-label': t('Choose time'),
      'aria-haspopup': 'dialog', 'aria-expanded': open, onClick: () => setOpen(!open),
    }, h(ClockIcon)),
    open ? h(PickerPopover, { anchor, label: t('Choose time'), onClose: close, onDismiss: () => setOpen(false) },
      h('div', { className: 'bt-schedule-time-columns' },
        h(TimeColumn, { label: t('Hours'), count: 24, value: hour, onChange: next => onChange(`${next}:${minute}`) }),
        h(TimeColumn, { label: t('Minutes'), count: 60, value: minute, onChange: next => onChange(`${hour}:${next}`) })),
      h('footer', { className: 'bt-schedule-picker-foot' }, h('span', null, `${hour}:${minute}`),
        h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: close }, t('Done')))) : null)
}

function DatePicker({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const [month, setMonth] = useState(() => new Date(`${value}T12:00`))
  const anchor = useRef(null)
  const close = () => { setOpen(false); anchor.current?.focus() }
  const select = date => { onChange(dateKey(date)); close() }
  const move = delta => setMonth(current => new Date(current.getFullYear(), current.getMonth() + delta, 1))
  return h('div', { className: 'bt-schedule-date' },
    h('button', {
      ref: anchor, type: 'button', className: 'bt-schedule-date-trigger', 'aria-label': t('Choose date'),
      'aria-haspopup': 'dialog', 'aria-expanded': open,
      onClick: () => { setMonth(new Date(`${value}T12:00`)); setOpen(!open) },
    }, format(new Date(`${value}T12:00`), { year: 'numeric', month: 'short', day: 'numeric' }), h(ChevronRightIcon)),
    open ? h(PickerPopover, { anchor, label: t('Choose date'), onClose: close, onDismiss: () => setOpen(false) },
      h('header', { className: 'bt-schedule-date-head' },
        h('button', { type: 'button', className: 'bt-icon-btn', 'aria-label': t('Previous month'), onClick: () => move(-1) }, h(ChevronLeftIcon)),
        h('strong', { 'aria-live': 'polite' }, format(month, { year: 'numeric', month: 'long' })),
        h('button', { type: 'button', className: 'bt-icon-btn', 'aria-label': t('Next month'), onClick: () => move(1) }, h(ChevronRightIcon))),
      h('div', { className: 'bt-schedule-date-grid' },
        Array.from({ length: 7 }, (_, index) => h('span', { key: `weekday-${index}`, 'aria-hidden': true }, format(new Date(2024, 0, index + 1), { weekday: 'narrow' }))),
        monthDays(month).map(date => h('button', {
          key: dateKey(date), type: 'button', 'aria-pressed': value === dateKey(date),
          'data-outside': month.getMonth() !== date.getMonth() || undefined,
          'aria-current': dateKey(date) === dateKey(new Date()) ? 'date' : undefined,
          'aria-label': format(date, { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }),
          onClick: () => select(date),
        }, date.getDate()))),
      h('footer', { className: 'bt-schedule-picker-foot' }, h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => select(new Date()) }, t('Today')))) : null)
}

export function DateTimePicker({ value, onChange }) {
  const date = value.slice(0, 10)
  const time = value.slice(11, 16)
  return h('div', { className: 'bt-schedule-datetime', role: 'group', 'aria-label': t('Date and time') },
    h(DatePicker, { value: date, onChange: next => onChange(`${next}T${time}`) }),
    h(TimePicker, { value: time, onChange: next => onChange(`${date}T${next}`) }))
}

export const SCHEDULE_PICKER_CSS = `
.bt-schedule-time{display:flex;align-items:center;gap:4px;width:126px;max-width:100%;box-sizing:border-box;min-height:34px;padding:1px 4px 1px 10px;border:1px solid var(--bt-line);border-radius:8px;background:var(--bt-main);color:var(--bt-ink)}
.bt-schedule-time:focus-within{border-color:var(--bt-line-2)}
.bt-schedule-time input{width:64px;min-width:0;flex:1;border:0;outline:none;padding:0;background:none;color:inherit;font:inherit;font-size:13px;font-variant-numeric:tabular-nums}
.bt-schedule-time .bt-icon-btn{width:26px;height:28px;flex:none;color:var(--bt-ink-2)}
.bt-schedule-popover{position:fixed;inset:auto;margin:0;box-sizing:border-box;width:252px;max-width:calc(100vw - 24px);max-height:calc(100dvh - 24px);overflow:auto;padding:10px;border:1px solid var(--bt-line-2);border-radius:12px;background:var(--bt-card);color:var(--bt-ink);box-shadow:0 12px 36px var(--bt-line-2);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;scrollbar-width:thin}
.bt-schedule-time-columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.bt-schedule-time-column h4{margin:0;padding:6px 0 10px;text-align:center;font-size:11px;font-weight:500;color:var(--bt-ink-2)}
.bt-schedule-time-options{display:flex;flex-direction:column;gap:3px;max-height:min(210px,40dvh);overflow:auto;scrollbar-width:thin;scrollbar-color:var(--bt-line-2) transparent;overscroll-behavior:contain}
.bt-schedule-time-options button{flex:none;height:34px;border:0;border-radius:6px;background:none;color:var(--bt-ink);font:inherit;font-size:14px;font-variant-numeric:tabular-nums;cursor:pointer}
.bt-schedule-time-options button:hover{background:var(--bt-hover)}
.bt-schedule-time-options button[aria-selected=true]{background:var(--bt-user);color:var(--bt-user-ink);font-weight:600}
.bt-schedule-popover button:focus-visible{outline:2px solid var(--bt-accent);outline-offset:-2px}
.bt-schedule-picker-foot{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:10px;padding-top:10px;border-top:1px solid var(--bt-line);font-size:12px;font-variant-numeric:tabular-nums;color:var(--bt-ink-2)}
.bt-schedule-datetime{display:flex;align-items:center;flex-wrap:wrap;gap:8px;min-width:0}
.bt-schedule-date{min-width:0}
.bt-schedule-date-trigger{display:flex;align-items:center;justify-content:space-between;gap:12px;max-width:100%;min-height:34px;padding:0 10px;border:1px solid var(--bt-line);border-radius:8px;background:var(--bt-main);color:var(--bt-ink);font:inherit;font-size:13px;cursor:pointer}
.bt-schedule-date-trigger svg{flex:none;color:var(--bt-ink-2)}
.bt-schedule-date-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}
.bt-schedule-date-head strong{font-size:13px;font-weight:600}
.bt-schedule-date-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:2px}
.bt-schedule-date-grid>span{text-align:center;padding:6px 0;color:var(--bt-ink-2);font-size:10px}
.bt-schedule-date-grid>button{height:30px;padding:0;border:1px solid transparent;border-radius:6px;background:none;color:var(--bt-ink);font:inherit;font-size:12px;cursor:pointer}
.bt-schedule-date-grid>button:hover{background:var(--bt-hover)}
.bt-schedule-date-grid>button[data-outside]{color:var(--bt-ink-3)}
.bt-schedule-date-grid>button[aria-current=date]{border-color:var(--bt-line-2)}
.bt-schedule-date-grid>button[aria-pressed=true]{background:var(--bt-user);color:var(--bt-user-ink)}
@media(max-width:640px){.bt-schedule-time input{font-size:16px}}
`
