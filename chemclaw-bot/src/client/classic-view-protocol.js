import { checkShownView } from '../shared/views.js'

// Pure adapter for the DSH tool.call.toolview result shape. A model-supplied
// blueprint is NEVER proof that the Host accepted the call.
const resultText = block => (Array.isArray(block?.content) ? block.content : [])
  .filter(part => part?.type === 'text').map(part => part.text ?? '').join('\n')

export function classicNativeViewState(phase, block) {
  if (phase !== 'result') return { status: 'pending' }
  if (block?.isError === true || block?.error) return { status: 'failed' }
  const reply = resultText(block)
  if (!/^The view is on screen\.$/u.test(reply.trim())) return { status: 'rejected', reply }
  const args = block?.args
  const raw = typeof block?.argsRaw === 'string' ? (() => { try { return JSON.parse(block.argsRaw) } catch { return {} } })() : {}
  const title = typeof args?.value === 'function' ? args.value('title') : raw.title
  const view = typeof args?.value === 'function' ? args.value('view') : raw.view
  const checked = checkShownView(title, view)
  if (checked.error !== undefined || checked.interactive) return { status: 'invalid', error: checked.error ?? 'This view needs a submit action.' }
  return { status: 'ready', title: checked.title, view: checked.view }
}
