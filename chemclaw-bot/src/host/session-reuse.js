// The native workspace picker may name any blank Session in the workspace,
// including an expert's. Keep native creation and validation in the DSH gateway,
// but leave out that reuse hint when ChemClaw owns the target.
const ENDPOINT = 'session/create'

export function install(rt) {
  if (process.env.DS_BOT_APP !== '1') return
  rt.ctx.inject(['typertGateway'], (ctx) => {
    ctx.effect(() => ctx.connection.fetch.register({
      path: `/api/${ENDPOINT}`,
      methods: ['POST'],
      requestBody: 'buffered',
      fetch: async (request) => {
        if (request.headers.get('content-type')?.split(';', 1)[0]?.trim().toLowerCase() !== 'application/json') {
          return new Response('content type must be application/json', { status: 415 })
        }
        let body
        try { body = await request.json() } catch { return new Response('body is not JSON', { status: 400 }) }
        const rpcId = typeof body?.rpcId === 'string' ? body.rpcId : 'invalid-request'
        const reply = result => Response.json({ type: 'server-response', rpcId, result })
        const fail = (code, message, details = {}) => reply({ ok: false, error: { code, message, details } })
        const args = body?.payload?.args
        if (body?.type !== 'client-request' || !rpcId || body.method !== ENDPOINT
          || typeof body.rpcId !== 'string' || !args || typeof args !== 'object' || Array.isArray(args)
          || Object.keys(body.payload).length !== 1) {
          return fail('gateway/bad-request', 'invalid session/create request')
        }
        try {
          const id = args.request?.sessionId
          if (typeof id === 'string') {
            await rt.load()
            if (rt.blocksSessionReuse(id)) delete args.request.sessionId
          }
          request.signal.throwIfAborted()
          const value = await ctx.typertGateway.invoke({
            namespace: 'session', method: 'create', args,
            signal: request.signal, peer: ctx.connection.browserPeer,
          })
          return reply({ ok: true, value })
        } catch (error) {
          return fail(error?.code ?? 'gateway/internal', error instanceof Error ? error.message : String(error), error?.details)
        }
      },
    }), 'chemclaw-bot: protect team Session ids from native reuse')
  })
}
