// Registers one browser plugin's tools. ds-bot passes a key function that resolves
// the Bot; a standalone package can pass the Session id instead.
import { rm } from 'node:fs/promises'
import { join } from 'node:path'
import { openBotBrowser } from './session.js'
import { gateScope } from './gate.js'

export const browserOutput = {
  schema: {
    oneOf: [
      { type: 'string' },
      {
        type: 'object',
        properties: {
          text: { type: 'string', required: true },
          image: { type: 'string' },
        },
        additionalProperties: false,
      },
    ],
  },
  render(_args, value) {
    if (value && typeof value === 'object') {
      const blocks = [{ type: 'text', text: String(value.text ?? '') }]
      if (value.image) blocks.push({ type: 'image', data: value.image, mediaType: 'image/jpeg' })
      return blocks
    }
    return [{ type: 'text', text: String(value) }]
  },
}

/**
 * @param {any} ctx
 * @param {{ toolDefs: any[], defineTool: Function, keyOf: (exec: any) => Promise<string|undefined>, profileRoot: string, downloadRoot?: string, downloadRoots?: (botId: string) => Promise<string[]>, uploadRoots?: (botId: string) => Promise<string[]>, headless: boolean, playwrightUrl?: string, executablePath?: string, actionTimeout?: number, authorize?: (exec: any, botId: string, action: any) => Promise<void>, completeFor?: (exec: any) => Function, connect?: (botId: string, downloadRoots?: string[]) => Promise<string>, getHold?: (botId: string) => any, onHold?: (botId: string, hold: any) => void, subscribeHolds?: (listener: (botId: string, hold: any) => void) => (() => void) | undefined, openSession?: typeof openBotBrowser, api?: object }} options
 */
export function mountBrowserPlugin(ctx, { toolDefs, defineTool, keyOf, profileRoot, downloadRoot, downloadRoots, uploadRoots, headless, playwrightUrl, executablePath, actionTimeout, authorize, completeFor, connect, getHold, onHold, subscribeHolds, openSession = openBotBrowser, api }) {
  const sessions = new Map()
  const turns = new Map()
  let stopped = false
  const unsubscribeHolds = subscribeHolds?.((botId, hold) => {
    if (hold?.by !== 'user') return
    const session = sessions.get(botId)
    if (!session) return
    sessions.delete(botId)
    void Promise.resolve(session).then(s => s.close(), () => {}).catch(() => {})
  })
  ctx.effect(() => async () => {
    stopped = true
    unsubscribeHolds?.()
    const open = [...sessions.values()]
    sessions.clear()
    await Promise.all(open.map(session => Promise.resolve(session).then(opened => opened.close(), () => {})))
  }, 'chemclaw: browser plugin')

  // Closes a Bot's browser and removes its profile directory; used when the Bot is deleted.
  async function drop(botId) {
    const session = sessions.get(botId)
    sessions.delete(botId)
    if (session !== undefined) await Promise.resolve(session).then(opened => opened.close(), () => {})
    await rm(join(profileRoot, botId), { recursive: true, force: true }).catch(() => {})
  }

  for (const spec of toolDefs) {
    ctx.tools.register(defineTool({
      name: spec.name,
      description: spec.description,
      parameters: spec.parameters ?? {},
      output: browserOutput,
      async execute(args, exec) {
        const botId = await keyOf(exec)
        if (!botId) return 'Only Bots on the team have a browser.'
        const previous = turns.get(botId) ?? Promise.resolve()
        const turn = previous.catch(() => {}).then(async () => {
          if (stopped) throw new Error('The browser plugin has stopped.')
          exec.signal?.throwIfAborted()
          if (getHold?.(botId)?.by === 'user') throw new Error('The user has taken over this browser. Wait for them to give it back.')
          let session = sessions.get(botId)
          if (spec.needsBrowser && session === undefined) {
            // Store the opening promise before resolving roots so concurrent calls share the launch.
            const opening = Promise.resolve().then(async () => {
              const roots = downloadRoots ? await downloadRoots(botId) : undefined
              return openSession({
                botId,
                profileRoot,
                downloadDir: roots === undefined
                  ? join(downloadRoot ?? join(profileRoot, 'browser-downloads'), botId)
                  : async () => (await downloadRoots(botId))[0],
                headless,
                playwrightUrl,
                executablePath,
                actionTimeout,
                connect: connect ? id => connect(id, roots ?? []) : undefined,
                getHold: () => getHold?.(botId),
                onHold: hold => onHold?.(botId, hold),
                uploadRoots: uploadRoots ? () => uploadRoots(botId) : undefined,
              })
            })
            sessions.set(botId, opening)
            opening.catch(() => {
              if (sessions.get(botId) === opening) sessions.delete(botId)
            })
            session = opening
          }
          session = await session
          if (exec.signal?.aborted) {
            sessions.delete(botId)
            await session?.close().catch(() => {})
            exec.signal.throwIfAborted()
          }
          if (getHold?.(botId)?.by === 'user') throw new Error('The user has taken over this browser. Wait for them to give it back.')
          const abort = () => {
            sessions.delete(botId)
            void session?.close().catch(() => {})
          }
          exec.signal?.addEventListener('abort', abort, { once: true })
          const gate = authorize ? async action => {
            exec.signal?.throwIfAborted()
            await authorize(exec, botId, action)
            exec.signal?.throwIfAborted()
            if (getHold?.(botId)?.by === 'user') throw new Error('The user has taken over this browser.')
          } : undefined
          try {
            return await gateScope.run(gate, () => spec.execute(args ?? {}, {
              botId,
              profileDir: join(profileRoot, botId),
              session,
              complete: completeFor?.(exec),
              signal: exec.signal,
            }))
          } finally { exec.signal?.removeEventListener('abort', abort) }
        })
        turns.set(botId, turn)
        try { return await turn } finally { if (turns.get(botId) === turn) turns.delete(botId) }
      },
    }))
  }

  // An object return would be collected as an effect by cordis, so the api is an out-param.
  if (api) api.drop = drop
}
