export const ADVANCED_CHART_KINDS = ['scatter', 'radar', 'heatmap', 'funnel', 'treemap', 'sankey', 'gauge']
export const ADVANCED_CHART_PROPS = ['xValues', 'xUnit', 'maxima', 'max', 'links']

const finite = value => typeof value === 'number' && Number.isFinite(value)
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const extras = {
  scatter: ['xValues', 'xUnit'], radar: ['maxima'], heatmap: [], funnel: [], treemap: [],
  sankey: ['links'], gauge: ['max'],
}

// Only data crosses this boundary; arbitrary renderer options never reach ECharts.
export function checkAdvancedChart(node, path, ctx, isFormula) {
  const kind = node.kind
  const advanced = ADVANCED_CHART_KINDS.includes(kind)
  for (const key of ADVANCED_CHART_PROPS) {
    if (node[key] !== undefined && !extras[kind]?.includes(key)) return `${path}.${key}: not supported for ${kind ?? 'bar'}`
  }
  if (!advanced) return undefined
  const count = node.categories.length
  if (count > 80) return `${path}.categories: at most 80 labels for an advanced chart`
  if (node.categories.some(label => String(label).length > 120)) return `${path}.categories: labels must be at most 120 characters`
  if (node.unit !== undefined && typeof node.unit !== 'string') return `${path}.unit: expected a string`
  if (node.caption !== undefined && typeof node.caption !== 'string') return `${path}.caption: expected a string`
  if (kind === 'sankey') return checkLinks(node, path)
  if (kind === 'radar') {
    if (count < 3 || count > 12) return `${path}.categories: a radar requires 3 to 12 axes`
    if (!Array.isArray(node.maxima) || node.maxima.length !== count || node.maxima.some(value => !finite(value) || value <= 0)) return `${path}.maxima: expected a positive maximum for each axis`
  }
  if (kind === 'gauge' && (count !== 1 || !finite(node.max) || node.max <= 0)) return `${path}.max: a gauge requires one category and a positive max`
  if (Array.isArray(node.series)) {
    if (node.series.length > 12 || node.series.length * count > 480) return `${path}.series: at most 12 series and 480 values`
    if (['funnel', 'treemap', 'gauge'].includes(kind) && node.series.length !== 1) return `${path}.series: ${kind} takes one series`
    if (['funnel', 'treemap', 'radar', 'gauge'].includes(kind)) {
      for (const [index, series] of node.series.entries()) {
        if (!Array.isArray(series?.values)) continue
        for (const [at, value] of series.values.entries()) {
          if (finite(value) && value < 0) return `${path}.series[${index}].values[${at}]: ${kind} requires non-negative values`
          if (kind === 'radar' && finite(value) && finite(node.maxima?.[at]) && value > node.maxima[at]) return `${path}.series[${index}].values[${at}]: exceeds the axis maximum`
          if (kind === 'gauge' && finite(value) && finite(node.max) && value > node.max) return `${path}.series[${index}].values[${at}]: exceeds max`
        }
      }
    }
  }
  if (kind === 'scatter') {
    if (node.xUnit !== undefined && typeof node.xUnit !== 'string') return `${path}.xUnit: expected a string`
    if (!Array.isArray(node.xValues) || node.xValues.length !== count) return `${path}.xValues: expected one number or null per category`
    for (const [at, value] of node.xValues.entries()) {
      if (isFormula(value)) ctx.formulas.push({ source: value['='], path: `${path}.xValues[${at}]`, kind: 'number' })
      else if (value !== null && !finite(value)) return `${path}.xValues[${at}]: expected a number or null`
    }
  }
  return undefined
}

function checkLinks(node, path) {
  if (node.series !== undefined) return `${path}.series: use links for a sankey`
  if (new Set(node.categories.map(String)).size !== node.categories.length) return `${path}.categories: sankey node names must be unique`
  if (!Array.isArray(node.links) || node.links.length === 0 || node.links.length > 120) return `${path}.links: expected 1 to 120 links`
  const outgoing = node.categories.map(() => [])
  const degrees = node.categories.map(() => 0)
  const seen = new Set()
  for (const [at, edge] of node.links.entries()) {
    const where = `${path}.links[${at}]`
    if (!record(edge) || Object.keys(edge).some(key => !['source', 'target', 'value'].includes(key))) return `${where}: expected { source, target, value }`
    for (const key of ['source', 'target']) {
      if (!Number.isInteger(edge[key]) || edge[key] < 0 || edge[key] >= node.categories.length) return `${where}.${key}: expected a category index`
    }
    if (edge.source === edge.target) return `${where}: a link cannot point to itself`
    if (!finite(edge.value) || edge.value <= 0) return `${where}.value: expected a positive number`
    const key = `${edge.source}:${edge.target}`
    if (seen.has(key)) return `${where}: duplicate link`
    seen.add(key)
    outgoing[edge.source].push(edge.target)
    degrees[edge.target] += 1
  }
  const queue = degrees.flatMap((degree, at) => degree === 0 ? [at] : [])
  for (let at = 0; at < queue.length; at += 1) {
    for (const target of outgoing[queue[at]]) if (--degrees[target] === 0) queue.push(target)
  }
  return queue.length === node.categories.length ? undefined : `${path}.links: sankey links must not contain a cycle`
}
