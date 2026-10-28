import { createElement as h, useLayoutEffect, useRef, useState } from 'react'
import { t } from './i18n.js'

export function fitShortcuts(widths, available, gap = 6) {
  let used = 0
  let count = 0
  for (const width of widths) {
    const next = used + (count ? gap : 0) + width
    if (next > available) {
      if (count === 1 && available - used - gap >= 32) count++
      break
    }
    used = next
    count++
  }
  return Math.max(1, count)
}

// Measure every candidate outside layout so hidden shortcuts can return when the
// sidebar grows, without wrapping or clipping a partially visible button.
export function SidebarFilters({ items, children }) {
  const row = useRef(null)
  const probe = useRef(null)
  const [count, setCount] = useState(1)
  const key = items.map(item => `${item.id}:${item.label}:${item.pressed}`).join('|')
  useLayoutEffect(() => {
    const node = row.current
    const measure = () => {
      const trigger = node?.querySelector(':scope > .bt-side-filter')
      if (!trigger || !probe.current) return
      const widths = [...probe.current.children].map(button => button.getBoundingClientRect().width)
      const available = node.clientWidth - trigger.getBoundingClientRect().width - 7
      node.style.setProperty('--bt-shortcut-max', `${Math.max(32, available - widths[0] - 6)}px`)
      setCount(fitShortcuts(widths, available))
    }
    measure()
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null
    if (node) observer?.observe(node)
    if (probe.current) observer?.observe(probe.current)
    return () => observer?.disconnect()
  }, [key])
  const button = (item, measuring = false) => h('button', {
    key: item.id, type: 'button', title: item.label, 'aria-pressed': item.pressed,
    onClick: measuring ? undefined : item.pick,
  }, item.label)
  return h('div', { ref: row, className: 'bt-side-filter-row' },
    h('div', { className: 'bt-side-filters', role: 'group', 'aria-label': t('Filter by category') }, items.slice(0, count).map(item => button(item))),
    children,
    h('div', { ref: probe, className: 'bt-side-filters bt-side-filters-probe', 'aria-hidden': true, inert: true }, items.map(item => button(item, true))))
}
