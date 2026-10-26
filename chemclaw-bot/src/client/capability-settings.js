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
  const statuses = roster.capabilityStatuses?.[bot.id] ?? {}
  if (items.length === 0) return null
  return h(Card, { title: t('Capabilities') },
    h('div', { className: 'bt-set-row' }, h('input', { className: 'bt-input', placeholder: t('Search tasks, skills, or keywords'), value: query, onChange: event => setQuery(event.target.value), 'aria-label': t('Search tasks, skills, or keywords') })),
    items.filter(item => `${capabilityLabel(item)} ${item.purpose || item.description} ${item.name}`.toLowerCase().includes(query.toLowerCase())).map(item => h(SwitchRow, {
      key: item.name, label: capabilityLabel(item),
      hint: [item.purpose || item.description, attached.has(item.name) ? statusText(statuses[item.name]) : undefined].filter(Boolean).join(' · '),
      on: attached.has(item.name), onChange: enabled => void run(actions.setBotCapability(bot.id, item.name, enabled)),
    })))
}
