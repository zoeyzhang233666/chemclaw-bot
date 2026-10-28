import { createElement as h, useState } from 'react'
import { language, t } from './i18n.js'
import { SkillLibrary } from './skill-library.js'
import { skillLabel } from '../shared/skills.js'

export const capabilityLabel = item => skillLabel(item, language())
const statusText = status => !status ? undefined : status.state === 'ready' ? t('Ready')
  : status.state === 'needs-approval' ? t('Needs approval')
    : status.state === 'error' ? t('Could not connect: {error}', { error: status.error ?? '' }) : t('Connecting…')

export function CapabilitiesPage({ roster, actions, selectedId }) {
  return h(SkillLibrary, { roster, actions, selectedId })
}

export function BotCapabilitiesCard({ bot, roster, actions, run, Card, SwitchRow }) {
  const items = [...(roster.capabilities ?? [])].sort((a, b) => Number(b.kind === 'pack') - Number(a.kind === 'pack') || a.name.localeCompare(b.name))
  const attached = new Set(bot.capabilities ?? [])
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const statuses = roster.capabilityStatuses?.[bot.id] ?? {}
  if (items.length === 0) return null
  const needle = query.trim().toLowerCase()
  const searching = needle !== ''
  const shown = searching
    ? items.filter(item => `${capabilityLabel(item)} ${item.purpose || item.description} ${item.name}`.toLowerCase().includes(needle))
    : items
  const expanded = open || searching
  const count = attached.size
  const summary = count === 0 ? t('None enabled')
    : count === 1 ? t('1 enabled')
      : t('{count} enabled', { count })
  return h(Card, null,
    h('button', {
      type: 'button', className: 'bt-set-row bt-bs-row bt-cap-toggle',
      'aria-expanded': expanded,
      'aria-label': expanded ? t('Hide capabilities') : t('Show capabilities'),
      onClick: () => setOpen(value => !value),
    },
    h('span', { className: 'bt-set-copy' },
      h('span', { className: 'bt-bs-label' }, t('Capabilities')),
      h('span', { className: 'bt-set-hint' }, summary)),
    h('span', { className: 'bt-cap-caret', 'data-open': expanded || undefined, 'aria-hidden': true }, '▸')),
    h('div', { className: 'bt-set-row' }, h('input', {
      className: 'bt-input', placeholder: t('Search tasks, skills, or keywords'), value: query,
      onChange: event => setQuery(event.target.value),
      'aria-label': t('Search tasks, skills, or keywords'),
      onClick: event => event.stopPropagation(),
    })),
    expanded ? h('div', { className: 'bt-cap-list' },
      shown.length === 0
        ? h('div', { className: 'bt-cap-empty' }, t('No matching capabilities'))
        : shown.map(item => h(SwitchRow, {
          key: item.name, label: capabilityLabel(item),
          hint: [item.purpose || item.description, attached.has(item.name) ? statusText(statuses[item.name]) : undefined].filter(Boolean).join(' · '),
          on: attached.has(item.name), onChange: enabled => void run(actions.setBotCapability(bot.id, item.name, enabled)),
        }))) : null)
}
