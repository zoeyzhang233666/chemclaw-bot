const NODE_KEYS = ['id', 'label', 'detail', 'tone']
const EDGE_KEYS = ['from', 'to', 'label', 'uncertain']
const TONES = ['info', 'good', 'warn', 'bad']
const idPattern = /^[a-zA-Z][a-zA-Z0-9_-]{0,23}$/u
const fieldsAllowed = (item, keys) => item !== null && typeof item === 'object'
  && !Array.isArray(item) && Object.keys(item).every(key => keys.includes(key))
const shortText = (value, max) => typeof value === 'string' && value.trim() !== '' && [...value].length <= max

// Longest-path levels put joins below all their predecessors.
export function flowLevels(nodes, edges) {
  const waiting = new Map(nodes.map(node => [node.id, 0]))
  const next = new Map(nodes.map(node => [node.id, []]))
  const ranks = new Map(nodes.map(node => [node.id, 0]))
  for (const { from, to } of edges) {
    waiting.set(to, waiting.get(to) + 1)
    next.get(from).push(to)
  }
  const queue = nodes.filter(node => waiting.get(node.id) === 0).map(node => node.id)
  for (const id of queue) {
    for (const target of next.get(id)) {
      ranks.set(target, Math.max(ranks.get(target), ranks.get(id) + 1))
      waiting.set(target, waiting.get(target) - 1)
      if (waiting.get(target) === 0) queue.push(target)
    }
  }
  if (queue.length !== nodes.length) return null
  const levels = []
  for (const node of nodes) (levels[ranks.get(node.id)] ??= []).push(node)
  return levels
}

export function checkFlow({ nodes, edges, caption }, path) {
  if (!Array.isArray(nodes) || nodes.length < 2 || nodes.length > 12) return `${path}.nodes: expected 2 to 12 steps`
  if (!Array.isArray(edges) || edges.length < 1 || edges.length > 18) return `${path}.edges: expected 1 to 18 connections`
  const ids = new Set()
  for (const [i, node] of nodes.entries()) {
    const at = `${path}.nodes[${i}]`
    if (!fieldsAllowed(node, NODE_KEYS)) return `${at}: use id, label, detail and tone only`
    if (typeof node.id !== 'string' || !idPattern.test(node.id) || ids.has(node.id)) return `${at}.id: expected a unique short ASCII identifier`
    if (!shortText(node.label, 48)) return `${at}.label: expected 1 to 48 characters`
    if (node.detail !== undefined && !shortText(node.detail, 96)) return `${at}.detail: expected 1 to 96 characters`
    if (node.tone !== undefined && !TONES.includes(node.tone)) return `${at}.tone: expected info, good, warn or bad`
    ids.add(node.id)
  }
  const relations = new Set()
  const connected = new Set()
  for (const [i, edge] of edges.entries()) {
    const at = `${path}.edges[${i}]`
    if (!fieldsAllowed(edge, EDGE_KEYS)) return `${at}: use from, to, label and uncertain only`
    if (!ids.has(edge.from) || !ids.has(edge.to) || edge.from === edge.to) return `${at}: connect two different existing node IDs`
    const relation = `${edge.from}:${edge.to}`
    if (relations.has(relation)) return `${at}: duplicate connection`
    if (edge.label !== undefined && !shortText(edge.label, 26)) return `${at}.label: expected 1 to 26 characters`
    if (edge.uncertain !== undefined && typeof edge.uncertain !== 'boolean') return `${at}.uncertain: expected a boolean`
    connected.add(edge.from).add(edge.to)
    relations.add(relation)
  }
  if (connected.size !== ids.size) return `${path}.edges: every step needs a connection`
  if (caption !== undefined && !shortText(caption, 180)) return `${path}.caption: expected 1 to 180 characters`
  if (flowLevels(nodes, edges) === null) return `${path}.edges: use an acyclic flow, or use GenUI Mermaid for a loop`
  return undefined
}
