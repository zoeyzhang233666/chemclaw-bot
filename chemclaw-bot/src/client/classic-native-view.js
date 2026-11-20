import { createElement as h } from 'react'
import { checkShownView } from '../shared/views.js'
import { parseReplies } from '../shared/group-replies.js'
import { groupsFor } from './surface.js'
import { contentText, isHiddenTurn, toolArgs, toolName } from './text.js'
import { t } from './i18n.js'
import { DeliveredView } from './widget-cell.js'
import { GroupMessage } from './cells.js'
import { hasGenuiFence } from './genui-surfaces.js'

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
        const key = `${block.callId}:${index}`
        if (reply.kind === 'view') {
          const view = displayView(reply.title, reply.view)
          if (view) cards.set(key, view)
        } else if (reply.kind === undefined && reply.botId && typeof reply.text === 'string' && hasGenuiFence(reply.text)) {
          cards.set(key, { reply, source: `chemclaw-bot/group/${block.callId}`, eventSeq: block.seq, contentBlockIndex: index })
        }
      }
    }
  }
  for (const child of block.subCalls ?? []) collectViews(child, cards)
}

function GroupGenuiReplay({ item, sessionId, useRoster, actions }) {
  const roster = useRoster(state => state)
  const { reply, source, eventSeq, contentBlockIndex } = item
  const bot = roster.byId[reply.botId] ?? { id: reply.botId, name: reply.name, color: reply.color ?? 'gray' }
  return h(GroupMessage, {
    bot, roster, actions, room: roster.roomsById[sessionId], text: reply.text, time: reply.time, duration: reply.duration,
    genui: [{ source, threadId: sessionId, eventSeq, contentBlockIndex }],
  })
}

export function ClassicNativeViews({ sessionId, turn, useClassicViewCalls, useRoster, useSurface, actions }) {
  const tools = useClassicViewCalls(String(turn.turn))
  const expertSurface = useSurface(state => groupsFor(state).conversation)
  const replayAllowed = useRoster(state => state.ready && !isHiddenTurn(state, sessionId, turn.turn))
  const teamOwned = useRoster(state => state.byId[sessionId] !== undefined || state.roomsById[sessionId] !== undefined)
  if (expertSurface || !replayAllowed) return null
  const cards = new Map()
  for (const { root } of tools) collectViews(root, cards)
  const views = [...cards].filter(([, view]) => view !== null)
  if (views.length > 0) return views.map(([id, view]) => view.reply
    ? h(GroupGenuiReplay, { key: id, item: view, sessionId, useRoster, actions })
    : h('div', { key: id, className: 'bt-q-inline', 'data-classic-native-view': '' }, h(DeliveredView, view)))
  return cards.size > 0 && !teamOwned ? h('p', { role: 'status', className: 'bt-view-muted' }, t('The native card could not be displayed.')) : null
}
