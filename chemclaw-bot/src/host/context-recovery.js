// A provider can reject even an empty fresh part. Keep its recovery budget on the
// conversation, so neither changing Sessions nor restarting the host buys a retry.
import { lastAssistantStreamChunk } from '@deepseek-ai/dsh-llm'
import { HANDOFF_ACK } from './constants.js'
import { textOf } from './text.js'
import { CONTEXT_RECOVERY_LIMIT, CONTEXT_RECOVERY_NOTICE } from '../shared/context-recovery.js'

export function install(rt) {
  const { ctx, state } = rt
  const failed = new Set()
  const noticed = new Set()
  const inputs = new Map()
  let writing = Promise.resolve()

  const placeOf = id => {
    const botId = rt.chatOwners.get(id)
    if (botId !== undefined) return { botId }
    return rt.groupOwners.get(id) ?? rt.pastOwners.get(id)
  }
  const keyOf = place => JSON.stringify([place.botId, place.roomId ?? null])
  const recordOf = place => place.roomId === undefined ? rt.botOf(place.botId)?.contextRecovery
    : rt.roomOf(place.roomId)?.contextRecovery?.[place.botId]
  const put = (place, record) => {
    const owner = place.roomId === undefined ? rt.botOf(place.botId) : rt.roomOf(place.roomId)
    if (owner === undefined) return
    if (place.roomId === undefined) {
      if (record === undefined) delete owner.contextRecovery
      else owner.contextRecovery = record
    } else if (record === undefined) {
      if (owner.contextRecovery) {
        delete owner.contextRecovery[place.botId]
        if (Object.keys(owner.contextRecovery).length === 0) delete owner.contextRecovery
      }
    } else {
      owner.contextRecovery ??= {}
      owner.contextRecovery[place.botId] = record
    }
  }
  const enqueue = run => {
    const result = writing.then(run)
    writing = result.catch(() => {})
    return result
  }
  const blockedPlace = place => failed.has(keyOf(place)) || recordOf(place)?.blocked === true
  const blocked = id => {
    const place = placeOf(id)
    return place !== undefined && blockedPlace(place)
  }
  const notice = id => {
    const place = placeOf(id)
    if (place === undefined || noticed.has(keyOf(place))) return
    noticed.add(keyOf(place))
    rt.noteFailure?.({ level: 'warn', source: 'turn', text: CONTEXT_RECOVERY_NOTICE, sessionId: id })
  }
  async function commit(place, next) {
    const previous = recordOf(place)
    put(place, next)
    try {
      await rt.save({ required: true })
    } catch (error) {
      put(place, previous)
      // A failed write cannot grant a recovery whose budget would vanish on restart.
      failed.add(keyOf(place))
      throw error
    }
  }
  const clear = async place => {
    if (recordOf(place) !== undefined || failed.has(keyOf(place))) await commit(place, undefined)
    failed.delete(keyOf(place))
    noticed.delete(keyOf(place))
  }
  const advance = id => enqueue(async () => {
    const place = placeOf(id)
    if (place === undefined || rt.readOnly() !== undefined || blockedPlace(place)) return false
    const previous = recordOf(place)
    const attempts = (previous?.attempts ?? 0) + 1
    const userMessageId = inputs.get(keyOf(place)) ?? previous?.userMessageId
    try {
      await commit(place, { attempts, blocked: attempts > CONTEXT_RECOVERY_LIMIT, ...(userMessageId ? { userMessageId } : {}) })
    } catch (error) {
      rt.warn('chemclaw-bot: context recovery could not be recorded; no fresh part opened: %s', error)
      notice(id)
      return false
    }
    if (blockedPlace(place)) { notice(id); return false }
    return true
  })

  const userInput = (id, messages) => enqueue(async () => {
    if (rt.readOnly() !== undefined) return
    const message = messages.findLast(item => item.source?.kind === 'user' && item.source.contextRecoveryForwarded !== true)
    if (message?.id === undefined) return
    const room = rt.roomOf(id)
    const place = placeOf(id)
    const places = room ? room.members.map(botId => ({ botId, roomId: room.id })) : place ? [place] : []
    for (const entry of places) {
      const key = keyOf(entry)
      if (inputs.get(key) === message.id || recordOf(entry)?.userMessageId === message.id) continue
      await clear(entry)
      inputs.set(key, message.id)
    }
  })
  const resetBot = botId => enqueue(async () => {
    await clear({ botId })
    for (const room of Object.values(state.rooms)) if (room.contextRecovery?.[botId] !== undefined) await clear({ botId, roomId: room.id })
  })

  rt.contextRecovery = { advance, blocked, notice, userInput, resetBot, settled: () => writing }

  ctx.on('session/event', (session, event) => {
    if (event.type !== 'assistant/message' || event.data?.interrupted || !rt.isBotSession(session.id)) return
    const finish = lastAssistantStreamChunk(event.data?.stream ?? [], 'finish')
    if (!['stop', 'tool-calls', 'max-tokens'].includes(finish?.reason?.kind)
      || textOf(event.data?.message?.content) === HANDOFF_ACK) return
    const place = placeOf(session.id)
    if (place === undefined) return
    void enqueue(async () => {
      // A late response cannot unblock a conversation already stopped by a failure.
      if (rt.readOnly() === undefined && !blockedPlace(place) && recordOf(place) !== undefined) await clear(place)
    }).catch(error => rt.warn('chemclaw-bot: context recovery progress could not be saved: %s', error))
  })
  ctx.effect(() => () => writing, 'chemclaw-bot: context recovery writes')
}
