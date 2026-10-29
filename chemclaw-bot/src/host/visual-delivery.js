import { randomUUID } from 'node:crypto'

export const VISUAL_NOTICE = '[chemclaw-visual-delivery'
const textOf = content => Array.isArray(content) ? content.filter(block => block?.type === 'text').map(block => block.text ?? '').join('\n') : ''
export const textOnlyRequested = text => /\b(?:text[- ]only|no (?:charts|visuals|cards))\b|(?:只要|只用|仅用)(?:纯)?文字|(?:不要|不用)(?:图表|卡片|可视化)|纯文字(?:回答|回复)/iu.test(text)

const genuiFence = /^ {0,3}```[ \t]*dsh-ui(?:[>`"'.,;:)\]】」』]+)?[ \t]*\r?$/imu

export function hasInlineGenui(text, native = false) {
  for (const match of text.matchAll(/^ {0,3}```[ \t]*dsh-ui(?:[>`"'.,;:)\]】」』]+)?[ \t]*\r?\n([\s\S]*?)^ {0,3}```[ \t]*\r?$/gimu)) {
    try {
      const spec = JSON.parse(match[1])
      if (spec && Array.isArray(spec.items) && spec.items.length && (native || spec.panel !== true)) return true
    } catch { /* GenUI's own feedback handles malformed fences. */ }
  }
  return false
}

export function visualReminder(turn, bot) {
  return `${VISUAL_NOTICE} turn=${turn}]\nThe user-facing answer has no inline visual delivery. Add only the missing view now, using the evidence already obtained; do not repeat the prose, research or external actions. ${bot ? 'Prefer show_view for the existing charts and cards; use an inline dsh-ui fence for richer GenUI components (omit panel:true).' : 'Use an inline dsh-ui fence with the installed GenUI components.'} Choose from the information: numbers → metrics/chart, comparison → chart/table, events → timeline, process → steps/diagram, explanation or a short answer → a compact card. Include units and sources where available. Never invent missing values to draw a chart. An HTML/file link does not replace the inline view. Follow the conversation language.`
}

// One check at the documented stop boundary; successful visual answers add no
// model round trip. A missing view receives at most one same-turn reminder.
export function install(rt) {
  const { ctx } = rt
  const turns = new Map()
  const fresh = turn => ({ turn, text: '', visual: false, human: false, textOnly: false, reminded: false, repairing: false, calls: new Set() })
  const stateOf = id => {
    if (!turns.has(id)) turns.set(id, fresh(rt.live?.get(id)?.turn))
    return turns.get(id)
  }
  const observe = (session, event) => {
    const id = String(session.id)
    if (event.type === 'turn/start') { turns.set(id, fresh(event.data?.turn)); return }
    const entry = stateOf(id)
    if (event.type === 'tool/call' && event.data?.name === 'show_view') entry.calls.add(event.data.callId)
    if (event.type === 'tool/result') {
      const message = event.data?.message
      const result = message?.toolCallId ? message : message?.content?.find(block => block.type === 'tool-result')
      if (result && entry.calls.delete(result.toolCallId) && !result.isError && !event.data.error) {
        entry.visual ||= /^The view is (?:on screen|staged)/u.test(textOf(result.content))
      }
    } else if (event.type === 'user/message') {
      const source = event.data?.source
      const text = textOf(event.data?.content)
      if (source?.form === 'notice' && text.startsWith(VISUAL_NOTICE)) { entry.reminded = true; return }
      if (source?.kind === 'user') { entry.human = true; entry.textOnly = textOnlyRequested(text) }
      else if (source?.kind === 'schedule' || source?.audience === 'user') entry.human = true
      else if (source?.kind === 'bot' && source.role === 'room' && !source.askedBy) {
        const current = text.split(/This round so far[^\n]*:\n/u)[1]?.split('\n\n')[0] ?? ''
        const user = [...current.matchAll(/^User: (.*)$/gmu)].at(-1)?.[1]
        if (user !== undefined) entry.textOnly = textOnlyRequested(user)
      }
    } else if (event.type === 'assistant/message') {
      const text = textOf(event.data?.message?.content)
      if (text.trim()) entry.text = text
      entry.visual ||= hasInlineGenui(text, !rt.isBotSession?.(id))
      // Leave malformed fences to GenUI's own validation/repair budget. A valid
      // panel-only reply in a Bot surface still needs an inline equivalent.
      if (genuiFence.test(text)) entry.repairing = !hasInlineGenui(text, true)
    }
  }
  const restore = session => {
    const id = String(session.id)
    if (turns.has(id)) return
    turns.set(id, fresh(rt.live?.get(id)?.turn))
    const events = session.snapshotEvents?.() ?? []
    const start = events.findLastIndex(event => event.type === 'turn/start')
    for (const event of events.slice(Math.max(0, start))) observe(session, event)
  }
  ctx.on('session/event', (session, event) => { restore(session); observe(session, event) })
  ctx.on('session/disposed', session => turns.delete(String(session.id)))
  rt.noteVisualDelivery = id => { stateOf(id).visual = true }
  ctx.on('agent/turn-stopping', ({ agent, turn, signal }) => {
    const session = agent.session
    const id = String(session.id)
    if (signal.aborted || session.header?.parentSession !== undefined || rt.roomOf?.(id)) return
    restore(session)
    const entry = turns.get(id)
    if (!entry || entry.turn !== turn || entry.visual || entry.reminded || entry.repairing || entry.textOnly || !entry.text.trim()) return
    if ((rt.state?.exchangeTurns?.[id] ?? []).includes(turn)) return
    const info = rt.live?.get(id)?.info
    if (info?.handoff && !info.resume || info?.role === 'request' && info.audience !== 'user') return
    const group = rt.groupOwners?.has(id)
    if (group && info?.askedBy && info.askedBy !== 'user') return
    const bot = rt.isBotSession?.(id) === true
    if (!entry.human && !rt.chatOwners?.has(id) && !(group && info?.role === 'room')) return
    if (rt.state?.questions?.[id] || rt.state?.views?.[id]) return
    entry.reminded = true
    const source = session.header?.version >= 4
      ? { kind: 'plugin:chemclaw-bot', form: 'notice', summary: 'Inline visual delivery required' }
      : { kind: 'plugin', plugin: 'chemclaw-bot', form: 'notice', summary: 'Inline visual delivery required' }
    try {
      agent.steer({ id: randomUUID(), role: 'user', source, content: [{ type: 'text', text: visualReminder(turn, bot) }] })
    } catch (error) { rt.warn?.('chemclaw-bot: visual delivery reminder failed: %s', error) }
  })
}
