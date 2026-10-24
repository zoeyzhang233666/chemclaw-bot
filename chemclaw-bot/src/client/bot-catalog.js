import { createElement as h, useState } from 'react'
import { BotAvatar, RoomAvatar } from './mark.js'
import { SearchIcon, ChevronRightIcon } from './icons.js'
import { t } from './i18n.js'

export function BotCatalog({ actions, roster, kind = 'role' }) {
  const [category, setCategory] = useState('')
  const [query, setQuery] = useState('')
  const groups = kind === 'group'
  const records = groups ? roster.rooms : roster.bots
  const categoryOf = item => item.templateInfo?.category || (groups ? t('Custom teams') : item.role || t('Custom Bots'))
  const wanted = query.trim().toLowerCase()
  const items = records.filter(item => (!category || categoryOf(item) === category) && `${item.name} ${categoryOf(item)} ${item.templateInfo?.description ?? ''} ${(item.templateInfo?.examples ?? []).join(' ')}`.toLowerCase().includes(wanted))
  return h('section', { className: 'bt-expert-library' },
    h('p', { className: 'bt-library-intro' }, t(groups ? 'Your collaboration teams are ready. Choose a group and describe your task.' : 'Your specialist Bots are ready. Choose an expert and start a conversation.')),
    h('div', { className: 'bt-catalog-search' }, h(SearchIcon), h('input', { value: query, onChange: event => setQuery(event.target.value), placeholder: t('Search scenarios and experts'), 'aria-label': t('Search scenarios and experts') })),
    h('div', { className: 'bt-catalog-categories', role: 'group', 'aria-label': t('Category') }, ['', ...new Set(records.map(categoryOf))].map(value => h('button', { key: value, type: 'button', 'aria-pressed': category === value, onClick: () => setCategory(value) }, value || t('All scenarios')))),
    h('div', { className: 'bt-expert-grid' }, items.map(item => {
      const info = item.templateInfo ?? {}
      return h('article', { key: item.id, className: 'bt-expert-card', 'data-template': item.templateId },
        h('header', null, groups ? h(RoomAvatar, { room: item, roster, size: 44 }) : h(BotAvatar, { bot: item, size: 44, badge: false, live: false }), h('div', null, h('h3', null, item.name), h('span', { className: 'bt-eyebrow' }, categoryOf(item)))),
        h('p', { className: 'bt-expert-description' }, info.description || (groups ? item.notice?.split('\n')[0] : item.role)),
        info.examples?.[0] ? h('div', { className: 'bt-expert-example' }, h('span', null, t('Try asking')), h('p', null, info.examples[0])) : null,
        h('details', null, h('summary', null, t('Inputs, deliverables and sources'), h(ChevronRightIcon)), h('dl', null,
          [['Inputs', info.inputs], ['Team', groups ? item.members.map(id => roster.byId[id]?.name).filter(Boolean).join(' · ') : null], ['Deliverables', info.deliverables], ['Sources', info.sources], ['Limits', info.limits]].filter(([, value]) => value).map(([label, value]) => h('div', { key: label }, h('dt', null, t(label)), h('dd', null, value))))),
        h('footer', null,
          h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => actions.openSettings(groups ? 'groups' : 'bots', item.id) }, t('Settings')),
          h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => { actions.closeSettings(); actions.openSession(item.id) } }, t('Open conversation'))))
    })),
    items.length === 0 ? h('p', { className: 'bt-set-hint' }, t('No matching conversations.')) : null)
}
