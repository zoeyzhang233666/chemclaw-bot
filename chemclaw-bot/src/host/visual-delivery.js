import { randomUUID } from 'node:crypto'
import { ADVANCED_CHART_KINDS } from '../shared/advanced-charts.js'

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

// Only explicit drawing instructions are enforceable. Discussions of a chart
// problem should not force another rendering attempt.
const REQUEST_FAMILIES = [
  ['heatmap', /热力图|heat[\s-]*map/iu],
  ['sankey', /桑基图|sankey/iu],
  ['scatter', /散点图|scatter[\s-]*plot/iu],
  ['radar', /雷达图|radar[\s-]*chart/iu],
  ['funnel', /漏斗图|funnel[\s-]*chart/iu],
  ['treemap', /树图|矩形树图|treemap/iu],
  ['gauge', /仪表图|仪表盘图|gauge[\s-]*chart/iu],
  ['timeline', /时间轴|时间线|timeline/iu],
  ['mermaid', /mermaid|流程关系图/iu],
]

export function requestedChartKinds(text) {
  const requested = new Set()
  for (const clause of String(text ?? '').split(/[，,。！？!?；;\n]/u)) {
    if (/为什么|怎么|如何|是否|能不能|能否|有没有|没有|无法|失败|报错|修复|原因|排查|不显示|不工作|不支持|\b(?:why|error|broken|failed|fail)\b/iu.test(clause)) continue
    if (!/(?:给我|给出|绘制|生成|画|制作|用|使用|采用|展示|输出|添加|加上|补充|提供|\b(?:show|draw|render|plot|create|generate|include|add|use|make)\b)/iu.test(clause)) continue
    for (const [kind, pattern] of REQUEST_FAMILIES) if (pattern.test(clause)) requested.add(kind)
  }
  return [...requested]
}

export function deliveredViewKinds(view) {
  const found = new Set()
  const accepted = new Set([...REQUEST_FAMILIES.map(([kind]) => kind), 'line', 'area', 'bar', 'hbar', 'donut', 'table', 'metric'])
  const walk = (node, depth = 0) => {
    if (!node || typeof node !== 'object' || depth > 20) return
    if (Array.isArray(node)) { for (const child of node) walk(child, depth + 1); return }
    const type = String(node.type ?? node.component ?? '').toLowerCase()
    const kind = String(node.kind ?? node.chartType ?? '').toLowerCase()
    if (accepted.has(type)) found.add(type)
    if ((type === 'chart' || type === 'echart') && accepted.has(kind)) found.add(kind)
    if (type === 'diagram' || type === 'mermaid') found.add('mermaid')
    for (const child of Object.values(node)) if (child && typeof child === 'object') walk(child, depth + 1)
  }
  walk(view)
  return found
}

function genuiKinds(text, native = false) {
  const kinds = new Set()
  for (const match of text.matchAll(/^ {0,3}```[ \t]*dsh-ui(?:[>`"'.,;:)\]】」』]+)?[ \t]*\r?\n([\s\S]*?)^ {0,3}```[ \t]*\r?$/gimu)) {
    try {
      const spec = JSON.parse(match[1])
      if (!Array.isArray(spec?.items) || spec.items.length === 0 || (!native && spec.panel === true)) continue
      for (const kind of deliveredViewKinds(spec.items)) kinds.add(kind)
    } catch { /* Malformed fences belong to the upstream GenUI repair. */ }
  }
  return kinds
}

export function missingRequestedKinds(requested, delivered) {
  return [...requested].filter(kind => !delivered.has(kind))
}

export function requestedViewReminder(turn, bot, kinds) {
  return VISUAL_NOTICE + ' turn=' + turn + ']\n'
    + 'The user explicitly requested ' + kinds.join(', ') + ', but the successfully delivered views do not include those kinds. '
    + 'Add ONLY the missing view(s) using already verified data; do not repeat existing prose, views, research or external actions. '
    + (bot ? 'Use show_view for supported ECharts chart kinds, and an inline dsh-ui fence without panel:true for GenUI timelines/diagrams. '
      : 'Use the installed GenUI components in an inline dsh-ui fence. ')
    + 'If data or a renderer is unavailable, explain the limitation without fabricating measurements. Follow the conversation language.'
}

export function visualReminder(turn, bot) {
  return `${VISUAL_NOTICE} turn=${turn}]\nThe user-facing answer has no inline visual delivery. Add only the missing view now, using the evidence already obtained; do not repeat the prose, research or external actions. ${bot ? 'Prefer show_view for the existing charts and cards; use an inline dsh-ui fence for richer GenUI components (omit panel:true).' : 'Use an inline dsh-ui fence with the installed GenUI components.'} Choose from the information: numbers → metrics/chart, comparison → chart/table, events → timeline, process → steps/diagram, explanation or a short answer → a compact card. Include units and sources where available. Never invent missing values to draw a chart. An HTML/file link does not replace the inline view. Follow the conversation language.`
}

// One check at the documented stop boundary; successful visual answers add no
// model round trip. A missing view receives at most one same-turn reminder.
export function install(rt) {
  const { ctx } = rt
  const turns = new Map()
  const fresh = turn => ({ turn, text: '', visual: false, human: false, textOnly: false, reminded: false, repairing: false, requested: new Set(), kinds: new Set(), calls: new Map() })
  const stateOf = id => {
    if (!turns.has(id)) turns.set(id, fresh(rt.live?.get(id)?.turn))
    return turns.get(id)
  }
  const observe = (session, event) => {
    const id = String(session.id)
    if (event.type === 'turn/start') { turns.set(id, fresh(event.data?.turn)); return }
    const entry = stateOf(id)
    if (event.type === 'tool/call' && event.data?.name === 'show_view') entry.calls.set(event.data.callId, event.data.args?.view ?? event.data.input?.view)
    if (event.type === 'tool/result') {
      const message = event.data?.message
      const result = message?.toolCallId ? message : message?.content?.find(block => block.type === 'tool-result')
      if (result && entry.calls.has(result.toolCallId)) {
        const view = entry.calls.get(result.toolCallId)
        entry.calls.delete(result.toolCallId)
        if (!result.isError && !event.data.error && /^The view is (?:on screen|staged)/u.test(textOf(result.content))) {
          entry.visual = true
          for (const kind of deliveredViewKinds(view)) entry.kinds.add(kind)
        }
      }
    } else if (event.type === 'user/message') {
      const source = event.data?.source
      const text = textOf(event.data?.content)
      if (source?.form === 'notice' && text.startsWith(VISUAL_NOTICE)) { entry.reminded = true; return }
      if (source?.kind === 'user') { entry.human = true; entry.textOnly = textOnlyRequested(text); entry.requested = new Set(requestedChartKinds(text)) }
      else if (source?.kind === 'schedule' || source?.audience === 'user') entry.human = true
      else if (source?.kind === 'bot' && source.role === 'room' && !source.askedBy) {
        const current = text.split(/This round so far[^\n]*:\n/u)[1]?.split('\n\n')[0] ?? ''
        const user = [...current.matchAll(/^User: (.*)$/gmu)].at(-1)?.[1]
        if (user !== undefined) { entry.textOnly = textOnlyRequested(user); entry.requested = new Set(requestedChartKinds(user)) }
      }
    } else if (event.type === 'assistant/message') {
      const text = textOf(event.data?.message?.content)
      if (text.trim()) entry.text = text
      entry.visual ||= hasInlineGenui(text, !rt.isBotSession?.(id))
      for (const kind of genuiKinds(text, !rt.isBotSession?.(id))) entry.kinds.add(kind)
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
  rt.noteVisualDelivery = (id, view) => { const entry = stateOf(id); entry.visual = true; for (const kind of deliveredViewKinds(view)) entry.kinds.add(kind) }
  ctx.on('agent/turn-stopping', ({ agent, turn, signal }) => {
    const session = agent.session
    const id = String(session.id)
    if (signal.aborted || session.header?.parentSession !== undefined || rt.roomOf?.(id)) return
    restore(session)
    const entry = turns.get(id)
    if (!entry || entry.turn !== turn || entry.reminded || entry.repairing || entry.textOnly || !entry.text.trim()) return
    const enabledRequests = [...entry.requested].filter(kind => rt.state?.prefs?.advancedCharts !== false || !ADVANCED_CHART_KINDS.includes(kind))
    const missing = missingRequestedKinds(enabledRequests, entry.kinds)
    const knownMismatch = entry.visual && entry.kinds.size > 0 && missing.length > 0
    if (entry.visual && !knownMismatch) return
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
      const reminder = knownMismatch ? requestedViewReminder(turn, bot, missing) : visualReminder(turn, bot)
      agent.steer({ id: randomUUID(), role: 'user', source, content: [{ type: 'text', text: reminder }] })
    } catch (error) { rt.warn?.('chemclaw-bot: visual delivery reminder failed: %s', error) }
  })
}
