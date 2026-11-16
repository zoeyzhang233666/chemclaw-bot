// Electron's Node mode has no browser process. Calling its private browser
// bindings there can segfault before a JavaScript catch can handle the error.
export const DESKTOP_RUNTIME_RULES = [
  '# ChemClaw desktop runtime',
  'The ChemClaw application executable is not a general-purpose Electron browser runner. Do not launch it to render or screenshot a page, probe process._linkedBinding("electron_browser_*") or initialize electron/js2c/browser_init. Electron Node mode cannot provide browser-process APIs.',
  'Use the browser tools actually present in this Session for rendering and screenshots. Ordinary Agent Sessions may have no browser tools even when Bot browsers are available. Do not invent unavailable tools or replace them with private Electron bindings.',
  'For Node.js or Python scripts, call load_workspace_dependencies when available and use the interpreter paths it returns. If no supported browser is available, finish the useful static checks and deliver the file with an explicit statement that browser/WebGL rendering and screenshots were not verified. A drawn approximation is not a browser screenshot.',
  'After a native browser-runner failure, stop that route and report the failed validation; do not repeat the same application-executable probes.',
].join('\n')

const SHELL_TOOLS = new Set(['bash', 'pwsh'])
const normalize = value => value.replaceAll('\\', '/').toLowerCase()
const browserBinding = /(?:_linkedBinding\s*\(\s*['"]electron_browser_|(?:require|import)\s*\(\s*['"]electron\/js2c\/browser_init['"])/u
const nativeFailure = /\bSIGSEGV\b|\bEXC_BAD_ACCESS\b|Segmentation fault|\bcode=139\b/u

function resultText(result) {
  return (Array.isArray(result?.content) ? result.content : [])
    .filter(block => block?.type === 'text').map(block => block.text ?? '').join('\n')
}

function refusal() {
  const error = new Error('ChemClaw cannot run a browser through its application executable or private Electron browser bindings. Use this Session\'s supported browser tools; if none are available, complete static checks and say that browser rendering was not verified. Do not retry this route.')
  error.code = 'CHEMCLAW_UNSUPPORTED_BROWSER_RUNTIME'
  return error
}

export function install(rt, { env = process.env, executable = process.execPath } = {}) {
  if (env.DS_BOT_APP !== '1') return
  const { ctx } = rt
  const ownExecutable = normalize(executable)
  const turns = new WeakMap()
  ctx.effect(() => ctx.systemPrompt.section({
    name: 'chemclaw-desktop-runtime', order: 647, interpolate: false,
    // This also reaches ordinary Agent Sessions, which have no Bot identity.
    text: () => DESKTOP_RUNTIME_RULES,
  }), 'chemclaw-bot: desktop runtime guidance')
  ctx.on('session/event', (session, event) => {
    if (event.type === 'turn/start') turns.set(session, { failed: false })
  })
  ctx.on('tools/execute', async (exec, next) => {
    const command = exec.arguments?.command
    if (!SHELL_TOOLS.has(exec.name) || typeof command !== 'string'
      || !normalize(command).includes(ownExecutable)) return next()
    const session = exec.agent?.session
    let turn = session && turns.get(session)
    if (session && !turn) { turn = { failed: false }; turns.set(session, turn) }
    if (browserBinding.test(command) || turn?.failed) throw refusal()
    const recordFailure = text => {
      // A late result from the previous turn must not block a fresh request.
      if (turn && turns.get(session) === turn && nativeFailure.test(text)) turn.failed = true
    }
    try {
      const result = await next()
      recordFailure(resultText(result))
      return result
    } catch (error) {
      recordFailure(String(error?.message ?? error))
      throw error
    }
  })
}
