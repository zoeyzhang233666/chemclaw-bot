import { createElement as h } from 'react'
import { MarkdownText } from './dsh-primitives.js'
import { mdLabels } from './btw.js'
import { t } from './i18n.js'

export function DeliveryResult({ sessionId, useRoster }) {
  const roster = useRoster(value => value)
  const owner = roster.roomsById[sessionId]?.id ?? roster.byId[sessionId]?.id
  const results = roster.deliveries?.[owner] ?? []
  if (!results.length) return null
  return h('div', { className: 'bt-delivery-results' }, results.map(result => h('section', { key: result.id, className: 'bt-delivery-result', 'aria-label': t('Task delivery') },
    h('strong', null, t('This task has ended with partial results.')),
    result.label ? h('p', null, result.label) : null,
    h('p', null, t('Further research and Bot discussion have stopped. The collected replies below may be incomplete; missing data has not been filled in.')),
    result.notes.length ? h('details', { open: true }, h('summary', null, t('Collected results')),
      result.notes.map((note, index) => h('div', { key: index }, h('b', null, note.name), h(MarkdownText, { text: note.text, labels: mdLabels(), variant: 'compact' }))))
      : h('p', null, t('No usable result was returned. Check the data connection or narrow the question and try again.')))))
}

export const DELIVERY_CSS = `
.bt-delivery-results{max-height:35vh;overflow:auto}
.bt-delivery-result{margin:6px 0;padding:12px 16px;border:1px solid var(--bt-line-2);border-radius:12px;background:var(--bt-card);color:var(--bt-ink);font-size:12px;line-height:1.6}
.bt-delivery-result p{margin:4px 0;color:var(--bt-ink-2)}
.bt-delivery-result summary{cursor:pointer;color:var(--bt-accent)}
.bt-delivery-result details>div{margin-top:10px}
`
