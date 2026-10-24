// Ephemeral group drafts. Private exchanges never enter this view or the room log.
// A finished stream is held until the round commits or discards it, so the UI never
// blanks between the last token and postInRound.
import { stripWrittenCalls } from './turns.js'
import { isPass, stripOwnName } from './groups.js'

export function install(rt) {
  const drafts = new Map()
  const ownerOf = sessionId => {
    const owner = rt.groupOwners.get(sessionId)
    if (!owner) return undefined
    const room = rt.roomOf(owner.roomId)
    return room?.members.includes(owner.botId) ? owner : undefined
  }
  // Live streaming only: private roles and cancelled turns never enter the map.
  const streaming = sessionId => {
    const owner = ownerOf(sessionId)
    const entry = rt.live.get(sessionId)
    if (!owner || entry?.turn === undefined) return undefined
    if (['request', 'stopped', 'handoff'].includes(entry.info?.role)) return undefined
    if (rt.isStoppedRoomTurn?.(entry.info?.exchangeId)) return undefined
    return owner
  }
  // Held drafts stay after the Session turn ends until commit/discard.
  const showing = (sessionId, draft) => (draft.held ? ownerOf(sessionId) : streaming(sessionId))
  rt.ctx.on('agent/assistant-stream', ({ agent, frame }) => {
    if (frame.type === 'start') {
      if (streaming(agent.id)) drafts.set(agent.id, { attemptId: frame.attemptId, text: '', held: false })
      return
    }
    const draft = drafts.get(agent.id)
    if (!draft || draft.attemptId !== frame.attemptId) return
    if (!streaming(agent.id)) { drafts.delete(agent.id); return }
    if (frame.type === 'chunk' && frame.chunk?.type === 'text-delta') draft.text += frame.chunk.text
  })
  rt.ctx.on('session/event', (session, event) => {
    // Hold through assistant/message and turn/end: postInRound commits; pass/miss discards.
    if (['assistant/message', 'turn/end'].includes(event.type)) {
      const draft = drafts.get(session.id)
      if (draft) draft.held = true
    }
  })
  rt.commitRoomDraft = sessionId => { drafts.delete(sessionId) }
  rt.discardRoomDraft = sessionId => { drafts.delete(sessionId) }
  rt.roomDrafts = roomId => [...drafts].flatMap(([sessionId, draft]) => {
    const owner = showing(sessionId, draft)
    if (owner?.roomId !== roomId) return []
    const bot = rt.botOf(owner.botId)
    if (!bot) return []
    const text = stripOwnName(bot.name, stripWrittenCalls(draft.text))
    // Do not flash the protocol's silence marker while it is still arriving.
    if (isPass(text) || /^[\s[【(（]*(?:p(?:a(?:s(?:s)?)?)?)?$/i.test(text)) return []
    return [{ botId: bot.id, attemptId: draft.attemptId, text }]
  })
  rt.ctx.effect(() => () => drafts.clear(), 'chemclaw-bot: group drafts')
}
