import { randomUUID } from 'node:crypto'
import { DOMParser } from '@xmldom/xmldom'
import { genuiFences, genuiMarkdown, repairGenuiGraphic } from '../shared/genui-fences.js'

const renderable = /^status=valid\r?$/mu
const repairedBody = /^next=emit_repaired_fence\r?$[\s\S]*?^repaired_json:\r?\n```\r?\n([\s\S]+?)\r?\n```$/mu
const MAX_CHECKS = 12
const SVG_NAMESPACE = 'http://www.w3.org/2000/svg'
const parser = new DOMParser({ onError: () => { throw new Error('Ill-formed SVG') } })

function hasUsableSvg(body) {
  if (!body.includes('"svg"')) return true
  let spec
  try { spec = JSON.parse(body) } catch { return true } // The GenUI parser can repair some JSON.
  const walk = (node, depth = 0) => {
    if (!node || typeof node !== 'object' || depth > 24) return true
    if (node.type === 'svg') {
      if (typeof node.code !== 'string' || node.code.length > 12_000 || /<!DOCTYPE/iu.test(node.code)) return false
      try {
        const root = parser.parseFromString(node.code, 'image/svg+xml').documentElement
        return root?.localName === 'svg' && (!root.namespaceURI || root.namespaceURI === SVG_NAMESPACE)
      } catch { return false }
    }
    return ['items', 'children', 'tabs'].every(key => !Array.isArray(node[key]) || node[key].every(child => walk(child, depth + 1)))
  }
  return walk(spec)
}

// Run the installed GenUI parser through the public tool executor. These
// service calls are local and have no conversation step or visible tool card.
export async function checkedGenuiText(ctx, text, signal) {
  const result = { text, failed: false }
  if (!ctx.tools.execute || !ctx.tools.executable?.('validate_dsh_ui')) return result
  const seen = new Map()
  const validate = async body => {
    if (seen.has(body)) return seen.get(body)
    if (seen.size >= MAX_CHECKS || signal?.aborted) return undefined
    if (!hasUsableSvg(body)) {
      seen.set(body, null)
      return null
    }
    let verdict
    try {
      const batch = await ctx.tools.execute({
        signal: signal ?? new AbortController().signal,
        calls: [{ type: 'tool-call', id: randomUUID(), name: 'validate_dsh_ui', arguments: JSON.stringify({ spec: body }) }],
      })
      const validated = batch.results[0]?.result
      if (validated?.isError === false) verdict = validated.value
    } catch { /* An unavailable validator is different from a rejected fence. */ }
    if (typeof verdict !== 'string' || !verdict.startsWith('[genui-validation]\n')) return undefined
    const repaired = repairedBody.exec(verdict)?.[1]
    const bodyToRender = renderable.test(verdict) ? body : repaired && hasUsableSvg(repaired) ? repaired : null
    seen.set(body, bodyToRender)
    return bodyToRender
  }
  const recover = async body => {
    let spec
    try { spec = JSON.parse(body) } catch { return null }
    if (!Array.isArray(spec?.items) || spec.items.length < 2 || spec.items.length > MAX_CHECKS) return null
    const items = []
    for (const item of spec.items) {
      if (await validate(JSON.stringify({ ...spec, items: [item] }))) items.push(item)
    }
    if (!items.length || items.length === spec.items.length) return null
    // Preserve root state, title and panel mode, and check the remaining
    // components together before publishing them.
    return await validate(JSON.stringify({ ...spec, items })) ?? null
  }

  let out = ''
  let offset = 0
  for (const fence of genuiFences(text)) {
    let accepted = await validate(fence.body)
    if (accepted === null) {
      result.failed = true
      accepted = await recover(fence.body)
    } else if (typeof accepted === 'string' && accepted !== fence.body) {
      // JSON repair may expose a legacy visual type or field alias.
      const canonical = repairGenuiGraphic(accepted)
      if (canonical !== undefined) accepted = await validate(canonical) ?? accepted
    }
    if (accepted === null) result.failed = true
    if (accepted === undefined || (accepted === fence.body && fence.closed)) continue
    out += text.slice(offset, fence.start) + (accepted === null ? '' : genuiMarkdown(accepted))
    offset = fence.end
  }
  if (offset) result.text = (out + text.slice(offset)).trimEnd()
  return result
}
