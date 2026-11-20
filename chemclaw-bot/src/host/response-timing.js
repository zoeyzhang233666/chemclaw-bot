// Numeric timings only: no prompts, answers, credentials, URLs or model headers.
export function install(rt) {
  const rows = new Map()
  rt.ctx.on('session/event', (session, event) => {
    if (event.type === 'turn/start') {
      if (session.header?.parentSession !== undefined || rt.roomOf?.(session.id)) return
      const kind = rt.groupOwners.has(session.id) ? 'group' : rt.isBotSession(session.id) ? 'direct' : 'classic'
      rows.delete(session.id)
      rows.set(session.id, { startedAt: Date.now(), kind, requests: 0 })
      while (rows.size > 40) rows.delete(rows.keys().next().value)
    } else if (event.type === 'turn/end') {
      const row = rows.get(session.id)
      if (row) row.endMs = Date.now() - row.startedAt
    }
  })
  rt.ctx.on('llm/stream', (options, next) => {
    const row = rows.get(options.sessionId)
    if (!row || row.endMs !== undefined || options.purpose !== undefined || rt.ownRequest?.(options)) return next()
    return (async function* timed() {
      row.requestMs ??= Date.now() - row.startedAt
      row.requests += 1
      for await (const chunk of next()) {
        if (['text-delta', 'reasoning-delta', 'tool-call-delta'].includes(chunk.type)) {
          const elapsed = Date.now() - row.startedAt
          row.firstChunkMs ??= elapsed
          if (chunk.type === 'text-delta' && chunk.text) row.firstTextMs ??= elapsed
          if (chunk.type === 'reasoning-delta') row.firstReasoningMs ??= elapsed
          if (chunk.type === 'tool-call-delta') row.firstToolMs ??= elapsed
        }
        yield chunk
      }
    })()
  })
  rt.responseTimings = () => [...rows.values()].map(row => ({ ...row })).slice(-20)
  rt.ctx.effect(() => () => rows.clear(), 'chemclaw-bot: response timings')
}
