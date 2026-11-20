import { randomUUID } from 'node:crypto'
import { ADVANCED_CHART_KINDS } from '../shared/advanced-charts.js'
import { genuiFences, genuiMarkdown, repairGenuiGraphicFences } from '../shared/genui-fences.js'
import { asksForRelationships, capacityDataRequest, capacityMeasurementsInAnswer, isQuantitativeLookup, needsFlowDiagram, needsSvgIllustration } from './flow-intent.js'
import { marketQuoteIntent, mixedOverlayRequested, spotPriceRequest } from './market-quote-intent.js'
import { genuiViewAvailable, nativeViewAvailable } from './native-view-session.js'

export const VISUAL_NOTICE = '[chemclaw-visual-delivery'
const textOf = content => Array.isArray(content) ? content.filter(block => block?.type === 'text').map(block => block.text ?? '').join('\n') : ''
export const textOnlyRequested = text => /\b(?:text[- ]only|no (?:charts|visuals|cards))\b|(?:只要|只用|仅用)(?:纯)?文字|(?:不要|不用)(?:图表|卡片|可视化)|纯文字(?:回答|回复)/iu.test(text)

// Only historical traded-market price requests need the one-shot OHLC-first guard.
// Do not penalize spot chemical quotes, conceptual questions or current-only quotes.
export function marketHistoryRequest(text) {
  const query = String(text ?? '')
  // The OHLC-first guard is for a standalone traded market, never for an
  // explicitly requested physical spot / futures overlay or basis comparison.
  if (['spot', 'mixed'].includes(marketQuoteIntent(query))) return false
  if (!/(?:股票|股价|A股|港股|美股|ETF|期货|股指|WTI|布伦特|Brent|原油期货|期指|\b(?:stock|share|futures|equity|etf)\b)/iu.test(query)) return false
  if (/(?:为什么无法|怎么修复|为什么不|如何实现|能不能实现|是否支持|接口开发|技术方案|代码审查)/iu.test(query)) return false
  const historical = /(?:最近|近(?:一个|一|两|三|\d+)(?:月|周|天|日|年)|过去|一个月|上月|本月|月内|日线|日K|月线|周线|走势|趋势|历史|区间|(?:\d+|一|两|三)(?:天|日|周|月|年)|(?:20\d{2}[-年]\d{1,2}))/iu.test(query)
  const prices = /(?:行情|股价|价格|收盘|开盘|涨跌|走势|K线|k线|蜡烛图|(?:price|chart|history|historical|trend))/iu.test(query)
  const currentOnly = /(?:现在|目前|当前|实时|最新|此刻|现价|现报|多少钱)/iu.test(query)
  return historical ? prices || /股价|期货|WTI|Brent/iu.test(query) : prices && !currentOnly
}

const genuiFence = /^ {0,3}```[ \t]*dsh-ui(?:[>`"'.,;:)\]】」』]+)?[ \t]*\r?$/imu

// Explicitly comparing two assets may legitimately need two different charts.
export function multiAssetMarketRequest(text) {
  const query = String(text ?? '')
  return marketQuoteIntent(query) === 'mixed'
    || /(?:对比|比较|分别|并列|两只|多只|多种|多合约|多品种|\b(?:versus|vs\.?|compare)\b)/iu.test(query)
}

// Market chart deduplication applies only to *price visuals* in a single
// user-requested market-history turn. Metrics and evidence tables stay allowed.
export function marketPriceVisual(view) {
  if (!view || typeof view !== 'object') return false
  if (Array.isArray(view)) return view.some(marketPriceVisual)
  if (view.type === 'html') return true
  if (view.type === 'chart' && ['candlestick', 'line', 'area'].includes(view.kind ?? 'bar')) return true
  return Array.isArray(view.children) && view.children.some(marketPriceVisual)
}

// Do not ask people to pick an implementation for an ordinary public-market
// data request. Ambiguous tickers / exchanges are still valid questions.
export function redundantMarketSourceQuestion(question, options = []) {
  const optionText = (Array.isArray(options) ? options : []).map(option => typeof option === 'string' ? option : option?.label ?? '').join(' ')
  const questionText = String(question ?? '')
  return /(怎么查|如何查|怎样查|用什么查|怎么查询|从哪查|没有.*(?:接口|权限|行情)|怎么获取|用哪种方式|如何获取|数据来源|查询方式)/iu.test(questionText)
    && /(网页|网上|搜索|网站|akshare|数据源|接口|不(?:用了|需要)|行情软件|finance|web)/iu.test(questionText + ' ' + optionText)
}
 

// Syntax alone does not prove the GenUI ECharts payload can draw anything.
// The GenUI plugin remains responsible for full schema and browser validation.
const SPEC_FENCES = /^ {0,3}\u0060{3}[ \t]*dsh-ui(?:[>\u0060"'.,;:)\]】」』]+)?[ \t]*\r?\n([\s\S]*?)^ {0,3}\u0060{3}[ \t]*\r?$/gimu
const genuiSpecs = text => {
  const result = []
  for (const match of String(text ?? '').matchAll(SPEC_FENCES)) {
    try { result.push(JSON.parse(match[1])) } catch { /* handled by GenUI */ }
  }
  return result
}
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const hasDataPoint = data => Array.isArray(data) && data.some(value => value !== null && value !== undefined
  && (typeof value === 'number' ? Number.isFinite(value) : typeof value === 'string' ? value.trim() !== '' : record(value) || Array.isArray(value)))
const echartHasSeries = series => (Array.isArray(series) ? series : series ? [series] : [])
  .some(item => record(item) && hasDataPoint(item.data))
const echartHasDataset = dataset => (Array.isArray(dataset) ? dataset : dataset ? [dataset] : [])
  .some(item => record(item) && hasDataPoint(item.source))
export function genuiChartPayloadsUsable(items) {
  const walk = (node, depth = 0) => {
    if (!record(node) || depth > 24) return true
    if (node.type === 'echart') {
      if (node.option !== undefined) {
        if (!record(node.option) || !(echartHasSeries(node.option.series) || echartHasDataset(node.option.dataset))) return false
      } else if (!node.preset || !(hasDataPoint(node.data) || echartHasSeries(node.series))) return false
    }
    for (const key of ['children', 'items'])
      if (Array.isArray(node[key]) && !node[key].every(item => walk(item, depth + 1))) return false
    if (Array.isArray(node.tabs) && !node.tabs.every(tab => walk(tab.content, depth + 1))) return false
    return true
  }
  return Array.isArray(items) && items.length > 0 && items.every(item => walk(item))
}
const hasCompleteGenuiSpec = text => genuiSpecs(text).some(spec => record(spec) && Array.isArray(spec.items) && spec.items.length > 0)

// Shared chart schema allows missing observations; a wholly missing series
// must not create an empty canvas. Valid formula fields remain supported.
export function nativeChartPayloadsUsable(view) {
  const walk = (node, depth = 0) => {
    if (!record(node) || depth > 24) return true
    if (node.type === 'chart' && node.kind !== 'candlestick' && node.kind !== 'sankey') {
      if (!Array.isArray(node.series) || !node.series.some(series =>
        Array.isArray(series.values) && series.values.some(value =>
          (typeof value === 'number' && Number.isFinite(value))
          || (record(value) && typeof value['='] === 'string')))) return false
    }
    return !Array.isArray(node.children) || node.children.every(item => walk(item, depth + 1))
  }
  return walk(view)
}


// One complete, honest mixed-market view must contain a same-date overlay AND
// a dated basis series. This checks structure/data presence, not provenance:
// the model must still source physical spot and exchange futures separately.
const spotLeg = /现货|即期|出厂|到厂|\bspot\b/iu
const futuresLeg = /期货|期价|盘面|主力|连续|\bfutures?\b|\b(?:MA|EG|SA|PG|RB|SC)\d{0,4}\b/iu
const basisLeg = /基差|现期价差|\bbasis\b/iu
const usableNumber = value => typeof value === 'number' && Number.isFinite(value)
const chartNodes = view => {
  const charts = []
  const walk = (node, depth = 0) => {
    if (!node || typeof node !== 'object' || depth > 24) return
    if (Array.isArray(node)) { for (const child of node) walk(child, depth + 1); return }
    if (node.type === 'chart') charts.push(node)
    if (Array.isArray(node.children)) walk(node.children, depth + 1)
  }
  walk(view)
  return charts
}
export function mixedMarketVisualStatus(view) {
  const charts = chartNodes(view)
  const overlays = charts.flatMap(chart => {
    if (chart.kind !== 'line' || !Array.isArray(chart.categories) || chart.categories.length < 2) return []
    const spot = chart.series?.find(item => spotLeg.test(String(item?.name ?? '')))
    const futures = chart.series?.find(item => futuresLeg.test(String(item?.name ?? '')) && !spotLeg.test(String(item?.name ?? '')))
    if (!Array.isArray(spot?.values) || !Array.isArray(futures?.values)
      || spot.values.length !== chart.categories.length || futures.values.length !== chart.categories.length) return []
    const differences = new Map()
    chart.categories.forEach((date, index) => {
      if (usableNumber(spot.values[index]) && usableNumber(futures.values[index]))
        differences.set(String(date), spot.values[index] - futures.values[index])
    })
    return differences.size >= 2 ? [{ chart, differences }] : []
  })
  const basis = overlays.some(({ chart: overlayChart, differences }) => charts.some(chart => {
    // Basis has its own scale: never silently plot it as a third price series.
    if (chart === overlayChart || !['line', 'bar', 'area'].includes(chart.kind)
      || !Array.isArray(chart.categories) || chart.categories.length < 2) return false
    return (chart.series ?? []).some(item => {
      if (!basisLeg.test(String(item?.name ?? '')) || !Array.isArray(item.values)
        || item.values.length !== chart.categories.length) return false
      let matched = 0
      for (let i = 0; i < chart.categories.length; i += 1) {
        const expected = differences.get(String(chart.categories[i]))
        const actual = item.values[i]
        if (expected === undefined || !usableNumber(actual)) continue
        // Prices may have been rounded for display; the underlying calculation
        // must still agree with physical spot minus exchange futures.
        if (Math.abs(expected - actual) > 0.11) return false
        matched += 1
      }
      return matched >= 2
    })
  }))
  return { overlay: overlays.length > 0, basis, complete: Boolean(overlays.length > 0 && basis) }
}

// A mixed-market Bot/group answer should show native show_view, not a JSON
// protocol dump. Remove only view-shaped payloads; keep ordinary explanation
// and genuine non-UI JSON intact.
export function stripUnrenderedMixedViewText(text, streaming = false) {
  const original = String(text ?? '')
  const trimmed = original.trim()
  if (streaming) {
    // Also conceal *incomplete* fences while the model streams, preserving
    // useful prose that preceded the hidden protocol block.
    const fenceAt = original.search(/^ {0,3}`{3}(?:dsh-ui|json)(?:\s|$)/gimu)
    if (fenceAt >= 0) return original.slice(0, fenceAt).trim()
    if (/^\{/u.test(trimmed)) return ''
  }
  const withoutFences = original.replace(/^ {0,3}`{3}(?:dsh-ui|json)[^\n]*\r?\n([\s\S]*?)^ {0,3}`{3}[ \t]*$/gimu,
    (whole, body) => {
      if (/^ {0,3}`{3}dsh-ui/iu.test(whole)) return ''
      try {
        const spec = JSON.parse(body)
        if (spec && (Array.isArray(spec.items) || ['stack', 'row', 'chart'].includes(spec.type))) return ''
      } catch { /* ordinary JSON samples stay visible */ }
      return whole
    })
  const candidate = withoutFences.trim()
  if (candidate.startsWith('{')) {
    try {
      const spec = JSON.parse(candidate)
      if (spec && (Array.isArray(spec.items) || ['stack', 'row', 'chart'].includes(spec.type))) return ''
    } catch { /* keep ordinary text */ }
  }
  return withoutFences.trim()
}

export function hasInlineGenui(text, native = false) {
  for (const match of text.matchAll(/^ {0,3}```[ \t]*dsh-ui(?:[>`"'.,;:)\]】」』]+)?[ \t]*\r?\n([\s\S]*?)^ {0,3}```[ \t]*\r?$/gimu)) {
    try {
      const spec = JSON.parse(match[1])
      if (spec && genuiChartPayloadsUsable(spec.items) && (native || spec.panel !== true)) return true
    } catch { /* GenUI's own feedback handles malformed fences. */ }
  }
  return false
}

// Only explicit drawing instructions are enforceable. Discussions of a chart
// problem should not force another rendering attempt.
const MERMAID = /\bmermaid\b/iu
const SVG = /\bsvg\b/iu
const DIAGRAM = /\bdiagram\b/iu
const MERMAID_FENCE = /^ {0,3}\x60{3}[ \t]*mermaid[ \t]*\r?$/imu
const SVG_FENCE = /^ {0,3}\x60{3}[ \t]*svg[ \t]*\r?\n([\s\S]*?)^ {0,3}\x60{3}[ \t]*\r?$/gimu
const isSvg = code => typeof code === 'string' && code.length <= 12000 && /^\s*<svg\b[\s\S]*<\/svg>\s*$/iu.test(code)
const REQUEST_FAMILIES = [
  ['candlestick', /K[\s-]*线(?:图)?|蜡烛图|candlestick|ohlc/iu],
  ['heatmap', /热力图|heat[\s-]*map/iu],
  ['sankey', /桑基图|sankey/iu],
  ['scatter', /散点图|scatter[\s-]*plot/iu],
  ['radar', /雷达图|radar[\s-]*chart/iu],
  ['funnel', /漏斗图|funnel[\s-]*chart/iu],
  ['treemap', /树图|矩形树图|treemap/iu],
  ['gauge', /仪表图|仪表盘图|gauge[\s-]*chart/iu],
  ['timeline', /时间轴|时间线|timeline/iu],
  ['mermaid', MERMAID],
  ['svg', SVG],
  ['diagram', DIAGRAM],
  ['flow', /流程(?:关系)?图|逻辑关系图|\bflow[ -]?(?:chart|diagram)\b/iu],
]

export function requestedChartKinds(text) {
  const requested = new Set()
  for (const part of String(text ?? '').split(/[，,。！？!?；;\n]/u)) {
    const clause = part.split(/而不是|而非|不要用|不用|别用|\b(?:instead of|rather than|do not use|without)\b/iu)[0]
    if (/为什么|怎么|如何|是否|能不能|能否|有没有|没有|无法|失败|报错|修复|原因|排查|不显示|不工作|不支持|\b(?:why|error|broken|failed|fail)\b/iu.test(clause)) continue
    if (!/(?:给我|给出|绘制|生成|画|制作|用|使用|采用|展示|输出|添加|加上|补充|提供|想看|我要|想要|看一下|\b(?:show|draw|render|plot|create|generate|include|add|use|make)\b)/iu.test(clause)) continue
    for (const [kind, pattern] of REQUEST_FAMILIES) {
      if (kind === 'flow' && (MERMAID.test(clause) || SVG.test(clause) || DIAGRAM.test(clause))) continue
      if (kind === 'diagram' && (MERMAID.test(clause) || SVG.test(clause))) continue
      if (pattern.test(clause)) requested.add(kind)
    }
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
    if (type === 'svg') {
      if (isSvg(node.code)) found.add('svg')
    } else if (type === 'diagram') {
      if (typeof node.kind === 'string' && Array.isArray(node.nodes) && node.nodes.some(item => item?.id && item?.label)) found.add('diagram')
    } else if (accepted.has(type)) found.add(type)
    if ((type === 'chart' || type === 'echart') && accepted.has(kind)) found.add(kind)
    for (const child of Object.values(node)) if (child && typeof child === 'object') walk(child, depth + 1)
  }
  walk(view)
  return found
}

function genuiKinds(text, native = false) {
  const kinds = new Set()
  if (MERMAID_FENCE.test(text)) kinds.add('mermaid')
  if (native && Array.from(text.matchAll(SVG_FENCE)).some(match => isSvg(match[1]))) kinds.add('svg')
  for (const match of text.matchAll(/^ {0,3}```[ \t]*dsh-ui(?:[>`"'.,;:)\]】」』]+)?[ \t]*\r?\n([\s\S]*?)^ {0,3}```[ \t]*\r?$/gimu)) {
    try {
      const spec = JSON.parse(match[1])
      if (!Array.isArray(spec?.items) || spec.items.length === 0 || (!native && spec.panel === true)) continue
      for (const kind of deliveredViewKinds(spec.items)) if (spec.panel !== true || !['svg', 'diagram'].includes(kind)) kinds.add(kind)
    } catch { /* Malformed fences belong to the upstream GenUI repair. */ }
  }
  return kinds
}

export function missingRequestedKinds(requested, delivered, genui = true) {
  return [...requested].filter(kind => kind === 'flow' && genui
    ? !(delivered.has('diagram') || delivered.has('svg'))
    : !delivered.has(kind))
}

const diagramInstruction = 'Emit an inline dsh-ui type=diagram with short nodes {id,label,sub?} and edges {from,to,label?,kind?}. Use kind=flowchart for a short sequence or kind=architecture with x,y,w,h for a branching graph. Use dashed edges for unverified relationships.'
const svgInstruction = 'Emit inline dsh-ui type=svg using {"items":[{"type":"svg","title":"…","code":"<svg …>…</svg>"}]}. The SVG string belongs in code, never svg. Include xmlns and a padded viewBox.'
const relationshipInstruction = `Choose one view for the missing relationship. ${diagramInstruction} For a visual explanation that needs semantic colors, labelled lanes or shared branch lines, use SVG instead. ${svgInstruction}`
const capacityInstruction = 'Use one native show_view stack with a row of metric cards for the verified capacity, output, utilization or quota figures. Include the unit in each metric value string and the period in its caption. If a chart is also missing and there are at least two comparable verified observations, include a native hbar for entities or line for time in that stack.'
const relationshipKinds = new Set(['flow', 'diagram', 'svg', 'mermaid'])
const wantsGraph = entry => [...entry.requested].some(kind => relationshipKinds.has(kind)) || needsSvgIllustration(entry.question)
const specializedTable = question => /复杂(?:数据)?表|多级表头|合并单元格|表格热力底色|\b(?:merged cells|multi[- ]level headers)\b/iu.test(question)
const nativeDataRequest = question => /(?:原生|native).{0,22}(?:标签卡|指标卡|数据图|图表|折线图|\b(?:metrics?|cards?|charts?)\b)|(?:标签卡|指标卡).{0,12}(?:数据图|图表|折线图)/iu.test(question)
const dataPriority = entry => entry.nativeDataRequest || entry.spotReadout || entry.marketHistory || entry.mixedOverlayRequired
  || isQuantitativeLookup(entry.question)
const dataOnly = entry => dataPriority(entry) && !wantsGraph(entry) && (entry.nativeDataRequest || !asksForRelationships(entry.question))
const nativePairDelivered = entry => entry.nativeMetric && (entry.spotReadout === 'history' ? entry.spotLine : entry.nativeChart)
const unsuitableDataGraphic = (kind, question) => relationshipKinds.has(kind) && !(kind === 'svg' && specializedTable(question))
const quantityPattern = /[+-]?\d[\d,.]*\s*(?:元|美元|吨|桶|%|％|万吨|亿|万台|\b(?:usd|cny|tonnes?|bpd)\b)/giu
const datePattern = /(?:20\d{2}[-/.年])?\b\d{1,2}[-/.月]\d{1,2}(?:日)?\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\b/iu
const publicSearchTools = ['web_search', 'advanced_search', 'domain_search', 'platform_search', 'web_fetch', 'browser_open']
const sourceRestricted = /(?:不要|禁止|不(?:要)?许|不得|无需|不必|不用)(?:再)?(?:联网|上网|网络搜索|外部(?:来源|搜索))|(?:仅限|仅用|仅使用|只用|只使用|只看)(?:本地|库内|内部|已有|附件|给的|提供的)|\b(?:offline|no web|do not (?:browse|search online))\b/iu
const connectorGap = /(?:数据中台|平台|数据源|数据库|库里|工具|MCP|Data Hub).{0,28}(?:没有|不覆盖|未覆盖|暂缺|无数据|未收录|缺少|查不到|未查到|未找到|不可用|no (?:data|coverage)|not available)|(?:没有|未查到|缺乏|未能核实).{0,24}(?:数据|产量|行情|报价|价格|证据)/iu
const sourcePermissionQuestion = /(?:要不要|是否需要|需(?:要)?你确认|需要确认|请.{0,10}(?:授权|确认)|允许|\b(?:shall I|would you like me to|permission to)\b).{0,22}(?:联网|网搜|上网|外部检索|公开搜索|search (?:the )?web|browse)|(?:联网|网搜|上网|公开检索|外部检索).{0,22}(?:请确认|你确认|先确认|需.{0,6}(?:确认|授权))/iu
const canSeekPublicEvidence = entry => isQuantitativeLookup(entry.question) && !sourceRestricted.test(entry.question)

function sourceReminder(turn, native, textOnly) {
  return `${VISUAL_NOTICE} turn=${turn}]\nContinue the same public data lookup now. Search for the missing figure using available public search tools and open the original material to verify the date, geography and measurement. Do not ask for permission to search, repeat the same data-hub query, quote this notice, or discuss connector coverage. If sources still do not verify the figure, state only the specific evidence gap. ${native && !textOnly ? 'Deliver verified figures with a native metric row and comparable charts before detailed rows.' : 'Give the supported findings.'} Cite the original source links and follow the conversation language.`
}

function numericReminder(turn, entry, missing, breakdown) {
  const chart = entry.spotReadout === 'history'
    ? 'For two or more comparable dated physical spot observations, use kind=line with distinct dates and numeric spot prices on the same grade, region and price basis.'
    : breakdown ? 'Use separate bars for the verified producer-group and regional breakdowns, showing only the charts still missing. Exclude total rows and keep detailed evidence below the charts.'
    : 'Use a dated line for a time series or bars for a comparable snapshot when two or more verified observations support the chart.'
  return `${VISUAL_NOTICE} turn=${turn}]\nUse ONE native show_view stack to deliver ${missing.join(' and ')} from verified evidence already in this conversation. ${chart} Tables, SVG and diagrams cannot fulfill the metric or chart requirement. If historical coverage is insufficient, show only verified snapshots as metric cards and explain the gap. Use a source table as supporting detail. Do not fetch again, invent data, duplicate any native view already shown, or quote this notice. Follow the conversation language.`
}

function removeQuantitativeDiagrams(text, question) {
  const withoutGraphs = items => items.flatMap(item => {
    if (!record(item)) return [item]
    if (unsuitableDataGraphic(item.type, question)) return []
    if (item.type === 'tabs' && Array.isArray(item.tabs)) {
      const tabs = item.tabs.flatMap(tab => {
        if (!Array.isArray(tab?.items) || !tab.items.length) return [tab]
        const children = withoutGraphs(tab.items)
        return children.length ? [{ ...tab, items: children }] : []
      })
      return tabs.length || !item.tabs.length ? [{ ...item, tabs }] : []
    }
    if (!Array.isArray(item.items)) return [item]
    const children = withoutGraphs(item.items)
    return children.length || !item.items.length ? [{ ...item, items: children }] : []
  })
  let out = ''
  let offset = 0
  for (const fence of genuiFences(text)) {
    if (!fence.closed) continue
    let spec
    try { spec = JSON.parse(fence.body) } catch { continue }
    const original = Array.isArray(spec?.items) ? spec.items : [spec]
    const items = withoutGraphs(original)
    if (JSON.stringify(items) === JSON.stringify(original)) continue
    out += text.slice(offset, fence.start)
    if (items.length) out += genuiMarkdown(JSON.stringify({ ...spec, items }))
    offset = fence.end
  }
  return offset ? (out + text.slice(offset)).trimEnd() : text
}

export function requestedViewReminder(turn, native, kinds, requested, genui) {
  const explicit = kinds.filter(kind => requested.has(kind))
  return VISUAL_NOTICE + ' turn=' + turn + ']\n'
    + (explicit.length ? `The user explicitly requested ${explicit.join(', ')}. ` : '')
    + `The answer is still missing these inline views: ${kinds.join(', ')}. `
    + (kinds.includes('candlestick')
      ? (native
        ? 'For a candlestick use native show_view chart kind candlestick with 2-50 actual dated OHLC bars, no categories/series. Do not add a second line chart or HTML. '
        : 'For a candlestick use a single GenUI dsh-ui ECharts candlestick full-option view. ')
        + 'If the verified historical data contains only close/low or lacks complete OHLC, do not synthesize bars, fetch again or draw a substitute line: explain in one sentence that source OHLC is missing. Do not send another tool call. '
      : 'Add ONLY the missing view(s) using already verified data; do not repeat existing prose, views, research or external actions. ')
    + (kinds.includes('diagram') ? `${diagramInstruction} ` : '')
    + (kinds.includes('flow') && genui ? `${relationshipInstruction} ` : '')
    + (kinds.includes('svg') ? `${svgInstruction} ` : '')
    + (kinds.includes('metric') ? `${capacityInstruction} ` : '')
    + (kinds.includes('flow') && !genui ? 'Use the available show_view type=flow with concise nodes and edges. ' : '')
    + (native ? 'Use show_view for supported visuals and an inline dsh-ui fence without panel:true for other GenUI components. '
      : 'Use the installed GenUI components in an inline dsh-ui fence. ')
    + 'If data or a renderer is unavailable, explain the limitation without fabricating measurements. Follow the conversation language.'
}

const botMixedNeeded = (entry, isBot) => entry.mixedOverlayRequired && isBot && !entry.mixedVisualCommitted

export function visualReminder(turn, native) {
  return `${VISUAL_NOTICE} turn=${turn}]\nAdd only the missing inline visual using the existing answer and evidence. ${native ? 'Use show_view for cards and numeric charts or an inline dsh-ui component for other visuals.' : 'Use inline dsh-ui with an installed GenUI component.'} Omit panel:true. Use a compact text card for short answers. Keep the original prose and do not repeat research or external actions. Never invent data. Follow the conversation language.`
}

// One check at the documented stop boundary; successful visual answers add no
// model round trip. A missing view receives at most one same-turn reminder.
export function install(rt) {
  const { ctx } = rt
  const turns = new Map()
  // The closing block is authoritative. Repair a known field alias there so
  // both renderers and GenUI's own feedback receive the same canonical SVG.
  ctx.on('llm/stream', (options, next) => {
    if (options.sessionId === undefined || options.purpose !== undefined || rt.ownRequest?.(options)) return next()
    return (async function* () {
      for await (const chunk of next()) {
        if (chunk.type === 'block-end' && chunk.block.type === 'text') {
          const entry = turns.get(String(options.sessionId))
          let text = repairGenuiGraphicFences(chunk.block.text)
          if (entry && dataOnly(entry) && !nativePairDelivered(entry) && options.tools?.some(tool => tool.name === 'show_view')) {
            const filtered = removeQuantitativeDiagrams(text, entry.question)
            entry.withheldDiagram ||= filtered !== text
            text = filtered
          }
          if (text !== chunk.block.text) {
            yield { ...chunk, block: { ...chunk.block, text } }
            continue
          }
        }
        yield chunk
      }
    })()
  })
  const fresh = turn => ({ turn, text: '', question: '', visual: false, publicSearchTried: false, nativeMetric: false, nativeChart: false, nativeComparisons: new Set(), nativeDataRequest: false, spotReadout: undefined, spotLine: false, withheldDiagram: false, mixedVisualCommitted: false, mixedOverlayRequired: false, invalidGenuiChart: false, human: false, textOnly: false, marketHistory: false, quoteIntent: 'unspecified', multiAssetMarket: false, marketChartNudged: false, marketChartCommitted: false, marketOhlcStatus: 'untried', reminded: false, repairing: false, requested: new Set(), kinds: new Set(), calls: new Map() })
  const stateOf = id => {
    if (!turns.has(id)) turns.set(id, fresh(rt.live?.get(id)?.turn))
    return turns.get(id)
  }
  const recordNativeView = (entry, view) => {
    entry.visual = true
    if (entry.marketHistory && marketPriceVisual(view)) entry.marketChartCommitted = true
    if (entry.mixedOverlayRequired && mixedMarketVisualStatus(view).complete) entry.mixedVisualCommitted = true
    const kinds = deliveredViewKinds(view)
    entry.nativeMetric ||= kinds.has('metric')
    const charts = chartNodes(view)
    entry.nativeChart ||= charts.length > 0
    for (const chart of charts) {
      if (['bar', 'hbar', 'donut'].includes(chart.kind ?? 'bar') && chart.categories?.length >= 2) {
        entry.nativeComparisons.add(JSON.stringify(chart.categories.toSorted()))
      }
    }
    entry.spotLine ||= entry.spotReadout === 'history' && charts.some(chart => chart.kind === 'line' && chart.series?.some(series =>
      new Set((chart.categories ?? []).filter((date, index) => datePattern.test(date) && usableNumber(series.values?.[index]))).size >= 2))
    for (const kind of kinds) entry.kinds.add(kind)
  }
  const observe = (session, event) => {
    const id = String(session.id)
    if (event.type === 'turn/start') {
      const previous = turns.get(id)
      const next = fresh(event.data?.turn)
      // One human request may have multiple model turns (tools, steering,
      // continuation). Carry market chart delivery across those turns until the
      // next *real* user message resets it.
      if (previous?.marketHistory || previous?.nativeDataRequest || previous?.quoteIntent === 'spot' || previous?.quoteIntent === 'mixed') {
        next.marketHistory = previous.marketHistory
        next.quoteIntent = previous.quoteIntent
        next.multiAssetMarket = previous.multiAssetMarket
        next.marketChartNudged = previous.marketChartNudged
        next.marketChartCommitted = previous.marketChartCommitted
        next.mixedVisualCommitted = previous.mixedVisualCommitted
        next.mixedOverlayRequired = previous.mixedOverlayRequired
        next.marketOhlcStatus = previous.marketOhlcStatus
        next.textOnly = previous.textOnly
        next.visual = previous.visual
        next.publicSearchTried = previous.publicSearchTried
        next.nativeMetric = previous.nativeMetric
        next.nativeChart = previous.nativeChart
        next.nativeComparisons = previous.nativeComparisons
        next.nativeDataRequest = previous.nativeDataRequest
        next.spotReadout = previous.spotReadout
        next.spotLine = previous.spotLine
        next.question = previous.question
        next.requested = new Set(previous.requested)
        next.kinds = new Set(previous.kinds)
      }
      turns.set(id, next)
      return
    }
    const entry = stateOf(id)
    if (event.type === 'tool/call' && publicSearchTools.includes(event.data?.name)) entry.publicSearchTried = true
    if (event.type === 'tool/call' && event.data?.name === 'show_view') entry.calls.set(event.data.callId, event.data.args?.view ?? event.data.input?.view)
    if (event.type === 'tool/result') {
      const message = event.data?.message
      const result = message?.toolCallId ? message : message?.content?.find(block => block.type === 'tool-result')
      if (result && entry.calls.has(result.toolCallId)) {
        const view = entry.calls.get(result.toolCallId)
        entry.calls.delete(result.toolCallId)
        if (!result.isError && !event.data.error && /^The view is (?:on screen|staged)/u.test(textOf(result.content))) recordNativeView(entry, view)
      }
    } else if (event.type === 'user/message') {
      const source = event.data?.source
      const text = textOf(event.data?.content)
      if (source?.form === 'notice' && text.startsWith(VISUAL_NOTICE)) { entry.reminded = true; return }
      if (source?.kind === 'user') {
        entry.human = true
        entry.question = text
        entry.textOnly = textOnlyRequested(text)
        entry.quoteIntent = marketQuoteIntent(text)
        entry.nativeDataRequest = nativeDataRequest(text)
        const revisitsChart = entry.nativeDataRequest && /补上|刚才|上[一轮次]|为什么|不再生成|表格.{0,6}替代/u.test(text)
        entry.spotReadout = spotPriceRequest(text, entry.quoteIntent) ?? (revisitsChart ? entry.spotReadout : undefined)
        if (entry.spotReadout && entry.quoteIntent === 'unspecified') entry.quoteIntent = 'spot'
        entry.mixedOverlayRequired = mixedOverlayRequested(text)
        entry.marketHistory = marketHistoryRequest(text)
        entry.multiAssetMarket = multiAssetMarketRequest(text)
        entry.marketChartNudged = false
        entry.marketChartCommitted = false
        entry.mixedVisualCommitted = false
        entry.marketOhlcStatus = 'untried'
        entry.visual = false
        entry.publicSearchTried = false
        entry.nativeMetric = false
        entry.nativeChart = false
        entry.nativeComparisons.clear()
        entry.spotLine = false
        entry.withheldDiagram = false
        entry.invalidGenuiChart = false
        entry.kinds = new Set()
        entry.requested = new Set(requestedChartKinds(text))
      }
      else if (source?.kind === 'schedule' || source?.audience === 'user') entry.human = true
      else if (source?.kind === 'bot' && source.role === 'room' && (!source.askedBy || source.askedBy === 'user')) {
        const current = text.split(/This round so far[^\n]*:\n/u)[1]?.split('\n\n')[0] ?? ''
        const user = [...current.matchAll(/^User: (.*)$/gmu)].at(-1)?.[1]
        if (user !== undefined) {
          entry.question = user
          entry.textOnly = textOnlyRequested(user)
          entry.quoteIntent = marketQuoteIntent(user)
          entry.spotReadout = spotPriceRequest(user, entry.quoteIntent)
          entry.nativeDataRequest = nativeDataRequest(user)
          entry.mixedOverlayRequired = mixedOverlayRequested(user)
          entry.marketHistory = marketHistoryRequest(user)
          entry.multiAssetMarket = multiAssetMarketRequest(user)
          entry.requested = new Set(requestedChartKinds(user))
        }
      }
    } else if (event.type === 'assistant/message') {
      const text = textOf(event.data?.message?.content)
      if (text.trim()) entry.text = text
      entry.visual ||= hasInlineGenui(text, !rt.isBotSession?.(id))
      const kinds = genuiKinds(text, !rt.isBotSession?.(id))
      for (const kind of kinds) entry.kinds.add(kind)
      entry.visual ||= kinds.has('svg') || kinds.has('diagram') || kinds.has('mermaid')
      // Leave malformed fences to GenUI's own validation/repair budget. A valid
      // panel-only reply in a Bot surface still needs an inline equivalent.
      if (genuiFence.test(text)) {
        const complete = hasCompleteGenuiSpec(text)
        // Malformed fences belong to the upstream GenUI repair budget; valid
        // JSON with an empty ECharts payload needs our one native fallback.
        entry.repairing = !complete
        entry.invalidGenuiChart = complete && !hasInlineGenui(text, true)
      }
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
  ctx.on('tools/pre-execute', async (exec, next) => {
    const agent = exec.agent
    if (!['validate_dsh_ui', 'ask_user', 'ask_user_question'].includes(exec.name) || !agent?.session || agent.session.header?.parentSession !== undefined) return next()
    const decision = await next()
    if (decision.kind !== 'allow') return decision
    restore(agent.session)
    const entry = turns.get(String(agent.session.id))
    if (!(entry?.human || entry?.question)) return decision
    if (exec.name !== 'validate_dsh_ui') {
      if (!entry.publicSearchTried && canSeekPublicEvidence(entry) && sourcePermissionQuestion.test(JSON.stringify(exec.arguments ?? {}))
        && publicSearchTools.some(name => ctx.tools.get?.(name, agent, exec.toolSet))) {
        return { kind: 'deny', reason: 'Search available public sources for the missing requested data now. No user choice about the source is needed.' }
      }
      return decision
    }
    let spec = exec.arguments?.spec
    if (typeof spec === 'string') {
      try { spec = JSON.parse(spec) } catch { return decision }
    }
    const kinds = deliveredViewKinds(spec?.items ?? spec)
    if (dataOnly(entry) && !nativePairDelivered(entry) && nativeViewAvailable(ctx, agent, exec.toolSet)
      && [...kinds].some(kind => unsuitableDataGraphic(kind, entry.question))) {
      return { kind: 'deny', reason: 'Use native show_view metric cards and an appropriate data chart for the requested numbers. For spot history use a line on verified comparable dates, or metric snapshots if history is unavailable.' }
    }
    if (!kinds.has('mermaid') || entry.requested.has('mermaid')) return decision
    const instruction = entry.requested.has('svg') || needsSvgIllustration(entry.question) ? svgInstruction
      : entry.requested.has('diagram') ? diagramInstruction : relationshipInstruction
    return { kind: 'deny', reason: `${instruction} Keep the other GenUI components if useful and deliver the regular text answer.` }
  })
  rt.noteVisualDelivery = (id, view) => recordNativeView(stateOf(id), view)
  rt.marketHistoryOf = id => stateOf(id).marketHistory && !stateOf(id).textOnly
  rt.marketQuoteIntentOf = id => stateOf(id).quoteIntent
  rt.explicitSpotRequestOf = id => stateOf(id).quoteIntent === 'spot'
  rt.mixedMarketRequestOf = id => stateOf(id).quoteIntent === 'mixed'
  rt.strictMixedOverlayOf = id => stateOf(id).mixedOverlayRequired === true
  rt.marketOhlcStatus = id => stateOf(id).marketOhlcStatus
  rt.noteMarketOhlcSource = (id, status) => {
    if (!id) return
    const entry = stateOf(id)
    if (entry.marketHistory) entry.marketOhlcStatus = status === 'ready' ? 'ready' : 'unavailable'
  }
  rt.marketPriceViewAlreadyCommitted = (id, view) => {
    const entry = stateOf(id)
    return entry.marketHistory && !entry.multiAssetMarket && entry.marketChartCommitted && marketPriceVisual(view)
  }
  rt.requiresCandlestick = id => stateOf(id).requested.has('candlestick') && !stateOf(id).textOnly
  rt.deferMarketHistoryLineOnce = id => { const entry = stateOf(id); if (!entry.marketHistory || entry.textOnly || entry.marketChartNudged || entry.marketChartCommitted || entry.kinds.has('candlestick')) return false; entry.marketChartNudged = true; return true }
  ctx.on('agent/turn-stopping', ({ agent, turn, signal }) => {
    const session = agent.session
    const id = String(session.id)
    if (signal.aborted || session.header?.parentSession !== undefined || rt.roomOf?.(id)) return
    restore(session)
    const entry = turns.get(id)
    if (!entry || entry.turn !== turn || entry.reminded || !(entry.text.trim() || entry.withheldDiagram)) return
    const native = nativeViewAvailable(ctx, agent)
    const genui = genuiViewAvailable(ctx, agent)
    const prose = entry.text.replace(SPEC_FENCES, '')
    const missingPublicEvidence = !entry.publicSearchTried && canSeekPublicEvidence(entry)
      && (connectorGap.test(prose) || sourcePermissionQuestion.test(prose))
      && publicSearchTools.some(name => ctx.tools.get?.(name, agent))
    if (!missingPublicEvidence && (entry.textOnly || entry.repairing)) return
    const enabledRequests = new Set([...entry.requested].filter(kind => rt.state?.prefs?.advancedCharts !== false || !ADVANCED_CHART_KINDS.includes(kind)))
    if (!genui) { enabledRequests.delete('svg'); enabledRequests.delete('diagram') }
    const specified = ['mermaid', 'svg', 'diagram'].some(kind => enabledRequests.has(kind))
    if (!specified && genui && needsSvgIllustration(entry.question)) enabledRequests.add('svg')
    else if (!specified && !dataOnly(entry) && (native || genui)
      && (entry.kinds.has('mermaid') || needsFlowDiagram(entry.question, entry.text, entry.nativeMetric || entry.nativeChart))) enabledRequests.add('flow')
    const missing = missingRequestedKinds(enabledRequests, entry.kinds, genui)
    const missingCapacity = native && !entry.nativeMetric && !specified && !entry.requested.has('flow')
      && capacityDataRequest(entry.question) && capacityMeasurementsInAnswer(entry.text)
    if (missingCapacity) missing.push('metric')
    const quantities = [...prose.matchAll(quantityPattern)].length
    const tableDelivered = entry.kinds.has('table') || /^\s*\|?(?:[ \t]*:?-{3,}:?[ \t]*\|)+[ \t]*:?-{3,}:?[ \t]*\|?[ \t]*$/mu.test(prose)
    const breakdown = tableDelivered && capacityDataRequest(entry.question)
      && /^(?:#+|\s*[一二三四五12345][、.])[^\n]*(?:分集团|按集团|分企业|按企业)/mu.test(prose)
      && /^(?:#+|\s*[一二三四五12345][、.])[^\n]*(?:分地区|按地区|分区域|按区域)/mu.test(prose)
    const partialHistory = /(?:仅|只)(?:查到|找到|有|能确认|能核实|取得).{0,14}(?:当日|今日|单日|最新|一[次个条]|快照)|(?:没有|缺少|未找到|未取得|不足).{0,14}(?:历史|同口径|连续|可比|序列)|\b(?:only one verified|no comparable|insufficient history)\b/iu.test(prose)
    const missingData = []
    if (native && dataPriority(entry)) {
      const spotHistory = entry.spotReadout === 'history'
      if (!entry.nativeMetric && (entry.nativeDataRequest || quantities > 0 || (entry.nativeChart && !entry.mixedOverlayRequired)
        || tableDelivered || entry.withheldDiagram || entry.spotReadout)) {
        missingData.push('headline metric cards')
      }
      if (spotHistory && !entry.spotLine && !partialHistory) missingData.push('the dated spot chart')
      else if (breakdown && entry.nativeComparisons.size < 2) missingData.push('the missing production comparisons')
      else if (!spotHistory && !entry.nativeChart && !entry.marketHistory
        && (entry.nativeDataRequest || quantities > 1 || tableDelivered || entry.withheldDiagram)) missingData.push('the data chart')
    }
    const knownMismatch = entry.visual && entry.kinds.size > 0 && missing.length > 0
    const missingGraphic = missing.some(kind => ['flow', 'svg', 'diagram'].includes(kind))
    const mixedIncomplete = botMixedNeeded(entry, rt.isBotSession?.(id) === true)
    if (!missingPublicEvidence && entry.visual && !knownMismatch && !mixedIncomplete && !missingGraphic && !missingCapacity && !missingData.length) return
    if ((rt.state?.exchangeTurns?.[id] ?? []).includes(turn)) return
    const info = rt.live?.get(id)?.info
    if (info?.handoff && !info.resume || info?.role === 'request' && info.audience !== 'user') return
    const group = rt.groupOwners?.has(id)
    if (group && info?.askedBy && info.askedBy !== 'user') return
    if (!entry.human && !rt.chatOwners?.has(id) && !(group && info?.role === 'room')) return
    if (rt.state?.questions?.[id] || rt.state?.views?.[id]) return
    entry.reminded = true
    const source = session.header?.version >= 4
      ? { kind: 'plugin:chemclaw-bot', form: 'notice', summary: missingPublicEvidence ? 'Verify public data' : 'Inline visual delivery required' }
      : { kind: 'plugin', plugin: 'chemclaw-bot', form: 'notice', summary: missingPublicEvidence ? 'Verify public data' : 'Inline visual delivery required' }
    try {
      const reminder = missingPublicEvidence ? sourceReminder(turn, native, entry.textOnly) : mixedIncomplete
        ? `${VISUAL_NOTICE} turn=${turn}]\nThe user requested a dated spot/futures overlay with basis, but no successfully staged native show_view contains both the same-date spot/futures lines AND a basis series. In a Bot or group use ONE native show_view stack with (1) a 2-series line chart, and (2) a basis line (spot minus futures), if separately verified dated observations allow it. Do not output a dsh-ui fence, raw view JSON, standalone futures chart or regional spot bars. If spot history is unavailable, do NOT fabricate prices: give a clear partial-data explanation or table instead. Do not repeat research. Only one correction.`
        : missingData.length && (!missingCapacity || breakdown) ? numericReminder(turn, entry, missingData, breakdown)
        : knownMismatch || missingGraphic || missingCapacity ? requestedViewReminder(turn, native, missing, entry.requested, genui)
      : entry.invalidGenuiChart && native
        ? `${VISUAL_NOTICE} turn=${turn}]\nThe previous GenUI chart lacks drawable data. Use one native show_view chart with the verified observations in this answer, or a factual table when data is missing. Do not repeat research or invent data.`
        : visualReminder(turn, native)
      agent.steer({ id: randomUUID(), role: 'user', source, content: [{ type: 'text', text: reminder }] })
    } catch (error) { rt.warn?.('chemclaw-bot: visual delivery reminder failed: %s', error) }
  })
}
