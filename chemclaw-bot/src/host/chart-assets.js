import { readFile } from 'node:fs/promises'
import { CHART_ENGINE_ROUTE } from '../shared/chart-engine.js'

export function install(rt) {
  let script
  rt.ctx.effect(() => rt.ctx.connection.fetch.register({
    path: CHART_ENGINE_ROUTE,
    methods: ['GET'],
    requestBody: 'buffered',
    fetch: async () => {
      // Read only our own packaged asset, never a path supplied by the client.
      script ??= readFile(new URL('../../runtime/chart-engine.js', import.meta.url)).catch(error => { script = undefined; throw error })
      return new Response(await script, { headers: {
        'content-type': 'text/javascript; charset=utf-8',
        'cache-control': 'private, max-age=3600',
        'x-content-type-options': 'nosniff',
      } })
    },
  }), 'chemclaw-bot: chart engine')
}
