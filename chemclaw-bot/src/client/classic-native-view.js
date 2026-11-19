import { createElement as h } from 'react'
import { checkShownView } from '../shared/views.js'
import { parseReplies } from '../shared/group-replies.js'
import { groupsFor } from './surface.js'
import { contentText, isHiddenTurn, toolArgs, toolName } from './text.js'
import { t } from './i18n.js'
import { DeliveredView } from './widget-cell.js'

function displayView(title, blueprint) {
  const view = checkShownView(title, blueprint)
  return view.error === undefined && !view.interactive ? view : null
}

function collectViews(block, cards) {
  if (block.kind === 'tool-result') {
    const name = toolName(block)
    const settled = !block.isError && !block.error && !block.meta?.stopped
    if (name === 'show_view') {
      const args = toolArgs(block)
      const shown = settled && contentText(block.content).trim() === 'The view is on screen.'
      cards.set(block.callId, shown ? displayView(args.text('title'), args.value('view')) : null)
    } else if (name === 'group_relay' && settled) {
      for (const [index, reply] of parseReplies(contentText(block.content)).replies.entries()) {
        if (reply.kind !== 'view') continue
        const view = displayView(reply.title, reply.view)
        if (view) cards.set(`${block.callId}:${index}`, view)
      }
    }
  }
  for (const child of block.subCalls ?? []) collectViews(child, cards)
}

export function ClassicNativeViews({ sessionId, turn, useClassicViewCalls, useRoster, useSurface }) {
  const tools = useClassicViewCalls(String(turn.turn))
  const expertSurface = useSurface(state => groupsFor(state).conversation)
  const replayAllowed = useRoster(state => state.ready && !isHiddenTurn(state, sessionId, turn.turn))
  const teamOwned = useRoster(state => state.byId[sessionId] !== undefined || state.roomsById[sessionId] !== undefined)
  if (expertSurface || !replayAllowed) return null
  const cards = new Map()
  for (const { root } of tools) collectViews(root, cards)
  const views = [...cards].filter(([, view]) => view !== null)
  if (views.length > 0) return views.map(([id, view]) => h('div', { key: id, className: 'bt-q-inline', 'data-classic-native-view': '' }, h(DeliveredView, view)))
  return cards.size > 0 && !teamOwned ? h('p', { role: 'status', className: 'bt-view-muted' }, t('The native card could not be displayed.')) : null
}
