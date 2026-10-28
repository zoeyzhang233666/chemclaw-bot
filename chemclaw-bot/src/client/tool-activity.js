import { createElement as h } from 'react'
import { TerminalIcon, SearchIcon } from './icons.js'
import { t } from './i18n.js'

const ToolIcon = () => h('svg', { width: 16, height: 16, viewBox: '0 0 20 20', fill: 'none', stroke: 'currentColor', strokeWidth: 1.4, 'aria-hidden': true },
  h('path', { d: 'M10 3 12 8 17 10 12 12 10 17 8 12 3 10 8 8Z' }))

export function ToolActivities({ entries, name }) {
  entries = Array.isArray(entries) ? entries.filter(entry => entry && typeof entry.tool === 'string' && typeof entry.summary === 'string' && typeof entry.label === 'string') : []
  if (!entries.length) return null
  return h('div', { className: 'bt-tool-activity' }, entries.map(entry => {
    const status = { running: 'Running', done: 'Completed', failed: 'Failed', stopped: 'Stopped' }[entry.status] ?? 'Running'
    const Icon = entry.label === 'Running command' ? TerminalIcon : entry.label === 'Searching' ? SearchIcon : ToolIcon
    return h('details', { key: entry.id, className: 'bt-tool-step', 'data-state': entry.status },
      h('summary', null,
        h('span', { className: 'bt-tool-icon', 'aria-hidden': true }, h(Icon)),
        name ? h('span', { className: 'bt-tool-bot' }, name) : null,
        h('span', { className: 'bt-tool-kind' }, t(entry.label)),
        h('span', { className: 'bt-tool-separator', 'aria-hidden': true }, '·'),
        h('span', { className: 'bt-tool-summary', title: entry.summary }, entry.summary),
        h('span', { className: 'bt-tool-status', role: 'status' }, t(status))),
      h('div', { className: 'bt-tool-detail' }, h('span', { className: 'bt-tool-name' }, entry.tool),
        typeof entry.detail === 'string' && entry.detail ? h('pre', null, entry.detail) : null))
  }))
}
