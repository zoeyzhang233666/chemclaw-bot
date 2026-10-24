import { createElement as h } from 'react'
import { currentPart, previewOf } from './text.js'
import { t } from './i18n.js'

export function TeamIntro({ sessionId, useRoster, useSessions, actions }) {
  const roster = useRoster(value => value)
  const item = roster.roomsById[sessionId] ?? roster.bots.find(bot => currentPart(bot) === sessionId)
  const preview = useSessions(list => previewOf(list, sessionId, roster.exchangeTurns[sessionId]))
  if (!item?.templateInfo || preview || item.preview) return null
  const info = item.templateInfo
  const main = item.id === roster.mainBotId
  return h('section', { className: 'bt-team-intro', 'aria-label': t('What this team can do') },
    h('h2', null, item.name),
    h('p', null, info.description),
    main ? h('div', { className: 'bt-team-shortcuts' }, roster.rooms.filter(room => ['scene-1', 'scene-3', 'scene-8', 'scene-10', 'scene-13', 'scene-14'].includes(room.templateId)).map(room => h('button', { key: room.id, type: 'button', onClick: () => actions.openSession(room.id) }, room.name))) : null,
    !main && item.admin ? h('p', { className: 'bt-set-hint' }, `${t('Admin')} · ${roster.byId[item.admin]?.name ?? ''} · ${item.members.map(id => roster.byId[id]?.name).filter(Boolean).join(' / ')}`) : null,
    h('div', { className: 'bt-team-example' }, h('span', null, t('Try asking')), h('p', null, info.examples[0])),
    main ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', onClick: () => actions.openSettings('groups') }, t('Group chats')) : h('p', { className: 'bt-set-hint' }, info.deliverables))
}
