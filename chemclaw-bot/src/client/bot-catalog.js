import { createElement as h, useState } from 'react'
import { BotAvatar, RoomAvatar } from './mark.js'
import { SearchIcon, ChevronRightIcon } from './icons.js'
import { t } from './i18n.js'
import { botCategoryId, roomCategoryId, sidebarCategories, sortCategories } from '../shared/sidebar-prefs.js'
import { CategoryMenu, categoryLabel } from './sidebar-categories.js'

export function BotCatalog({ actions, roster, kind = 'role' }) {
  const [category, setCategory] = useState('')
  const [query, setQuery] = useState('')
  const groups = kind === 'group'
  const records = groups ? roster.rooms : roster.bots
  const sidebar = roster.prefs?.sidebar ?? {}
  const categoryId = item => groups ? roomCategoryId(item, sidebar) : botCategoryId(item, sidebar)
  const byCategory = new Map(sidebarCategories(roster, groups ? 'room' : 'bot').map(category => [category.id, category]))
  for (const item of records) {
    const id = categoryId(item)
    if (!byCategory.has(id)) byCategory.set(id, { id, name: id.startsWith('rooms:') ? id.slice(6) : id })
  }
  const categories = sortCategories([...byCategory.values()], { sort: 'manual', categoryOrder: sidebar.categoryOrder ?? [] })
  const categoryOf = item => categoryLabel(byCategory.get(categoryId(item)))
  const selected = byCategory.has(category) ? category : ''
  const wanted = query.trim().toLowerCase()
  const items = records.filter(item => (!selected || categoryId(item) === selected) && `${item.name} ${categoryOf(item)} ${item.templateInfo?.description ?? ''} ${(item.templateInfo?.examples ?? []).join(' ')}`.toLowerCase().includes(wanted))
  return h('section', { className: 'bt-expert-library' },
    h('p', { className: 'bt-library-intro' }, t(groups ? 'Your collaboration teams are ready. Choose a group and describe your task.' : 'Your specialist Bots are ready. Browse by category and talk with a chemical expert.')),
    h('div', { className: 'bt-catalog-tools' },
      h('div', { className: 'bt-catalog-search' }, h(SearchIcon), h('input', { value: query, onChange: event => setQuery(event.target.value), placeholder: t('Search scenarios and experts'), 'aria-label': t('Search scenarios and experts') })),
      h(CategoryMenu, { roster, actions, manage: true, kinds: [groups ? 'room' : 'bot'], selected: selected ? { kind: groups ? 'room' : 'bot', id: selected } : null,
        onPick: (_kind, id) => setCategory(id ?? ''), onCreated: item => setCategory(item.id), onDeleted: result => setCategory(result.targetId) })),
    h('div', { className: 'bt-catalog-categories', role: 'group', 'aria-label': t('Sidebar category') },
      h('button', { type: 'button', 'aria-pressed': !selected, onClick: () => setCategory('') }, t('All')),
      categories.map(category => h('button', { key: category.id, type: 'button', 'aria-pressed': selected === category.id, onClick: () => setCategory(category.id) }, categoryLabel(category)))),
    h('div', { className: 'bt-expert-grid' }, items.map(item => {
      const info = item.templateInfo ?? {}
      return h('article', { key: item.id, className: 'bt-expert-card', 'data-template': item.templateId },
        h('header', null, groups ? h(RoomAvatar, { room: item, roster, size: 44 }) : h(BotAvatar, { bot: item, size: 44, badge: false, live: false }), h('div', null, h('h3', null, item.name), h('span', { className: 'bt-eyebrow' }, categoryOf(item)))),
        h('p', { className: 'bt-expert-description' }, info.description || (groups ? item.notice?.split('\n')[0] : item.role)),
        info.examples?.[0] ? h('div', { className: 'bt-expert-example' }, h('span', null, t('Try asking')), h('p', null, info.examples[0])) : null,
        h('details', null, h('summary', null, t('Inputs and deliverables'), h(ChevronRightIcon)), h('dl', null,
          [['Inputs', info.inputs], ['Team', groups ? item.members.map(id => roster.byId[id]?.name).filter(Boolean).join(' · ') : null], ['Deliverables', info.deliverables]].filter(([, value]) => value).map(([label, value]) => h('div', { key: label }, h('dt', null, t(label)), h('dd', null, value))))),
        h('footer', null,
          h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => actions.openSettings(groups ? 'groups' : 'bots', item.id) }, t('Settings')),
          h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => { actions.closeSettings(); actions.openSession(item.id) } }, t('Open conversation'))))
    })),
    items.length === 0 ? h('p', { className: 'bt-set-hint' }, t('No matching conversations.')) : null)
}
