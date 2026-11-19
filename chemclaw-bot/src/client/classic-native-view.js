import { createElement as h } from 'react'
import { checkShownView } from '../shared/views.js'
import { t } from './i18n.js'
import { DeliveredView } from './widget-cell.js'

function acceptedClassicView(block) {
  if (block.isError || block.error || block.meta?.stopped) return null
  const result = block.content.filter(part => part.type === 'text').map(part => part.text).join('\n').trim()
  if (result !== 'The view is on screen.') return null
  const view = checkShownView(block.args.text('title'), block.args.value('view'))
  return view.error === undefined && !view.interactive ? view : null
}

function collectViews(block, cards) {
  if (block.kind === 'tool-result' && block.name === 'show_view') cards.set(block.callId, acceptedClassicView(block))
  for (const child of block.subCalls ?? []) collectViews(child, cards)
}

export function ClassicNativeViews({ sessionId, turn, useClassicViewCalls, useRoster }) {
  const tools = useClassicViewCalls(String(turn.turn))
  const teamOwned = useRoster(state => state.byId[sessionId] !== undefined || state.roomsById[sessionId] !== undefined)
  if (teamOwned) return null
  const cards = new Map()
  for (const { root } of tools) collectViews(root, cards)
  const views = [...cards].filter(([, view]) => view !== null)
  if (views.length > 0) return views.map(([id, view]) => h('div', { key: id, className: 'bt-q-inline', 'data-classic-native-view': '' }, h(DeliveredView, view)))
  return cards.size > 0 ? h('p', { role: 'status', className: 'bt-view-muted' }, t('The native card could not be displayed.')) : null
}
