// Numeric timings only: no prompts, answers, credentials, URLs or model headers.
export function install(rt) {
  const rows = new Map()
  rt.ctx.on('session/event', (session, event) => {
    if (!rt.isBotSession(session.id)) return
    if (event.type === 'turn/start') {
      rows.delete(session.id)
      rows.set(session.id, { startedAt: Date.now(), kind: rt.groupOwners.has(session.id) ? 'group' : 'direct', requests: 0 })
      while (rows.size > 40) rows.delete(rows.keys().next().value)
    } else if (event.type === 'turn/end') {
      const row = rows.get(session.id)
      if (row) row.endMs = Date.now() - row.startedAt
    }
  })
  rt.ctx.on('llm/stream', (options, next) => {
    if (options.purpose !== undefined || rt.ownRequest?.(options) || !rt.isBotSession(options.sessionId)) return next()
    return (async function* timed() {
      const row = rows.get(options.sessionId)
      if (row) { row.requestMs ??= Date.now() - row.startedAt; row.requests += 1 }
      for await (const chunk of next()) {
        if (row && ['text-delta', 'reasoning-delta', 'tool-call-delta'].includes(chunk.type)) {
          row.firstChunkMs ??= Date.now() - row.startedAt
          if (chunk.type === 'text-delta' && chunk.text) row.firstTextMs ??= Date.now() - row.startedAt
        }
        yield chunk
      }
    })()
  })
  rt.responseTimings = () => [...rows.values()].map(row => ({ ...row })).slice(-20)
  rt.ctx.effect(() => () => rows.clear(), 'chemclaw-bot: response timings')
}
