import { createElement as h } from 'react'
import { currentPart } from './text.js'
import { t } from './i18n.js'

export function TeamIntro({ sessionId, useRoster, useSessions, actions }) {
  const roster = useRoster(value => value)
  const room = roster.roomsById[sessionId]
  const item = room ?? roster.bots.find(bot => currentPart(bot) === sessionId)
  // Only the DSH session's explicit blank flag proves that there is no chat yet.
  // A sidebar preview can be empty for a real conversation (tool-only turns, an
  // unready turn outline, or a fresh part after a context handoff).
  const empty = useSessions(list => {
    const session = list.byId[sessionId]
    const outline = list.projectionsBySession?.[sessionId]?.values?.turnOutline ?? session?.projectionValues?.turnOutline
    return session?.blank === true && (!Array.isArray(outline) || outline.length === 0)
  })
  const running = useSessionStatus(map => map.get(sessionId)?.running === true)
  // A Bot's previous parts are real conversation history even when its new
  // current part is blank. Group "parts" are member work sessions, not its chat.
  if (!item?.templateInfo || !empty || running || item.preview || (!room && item.parts?.length > 0)) return null
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
