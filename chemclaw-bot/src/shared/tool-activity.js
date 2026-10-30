// Only presentation fields travel to the activity view; tool output and arbitrary
// arguments can contain credentials or whole documents.
export function activityText(value) {
  return String(value ?? '')
    .replace(/\b(?:sk-[\w-]{8,}|(?:Bearer|Basic)\s+[^\s"']+|(?:ghp|gho|ghu|ghs|ghr)_[\w]{16,}|github_pat_[\w]{16,})/gi, '[hidden]')
    .replace(/((?:api[_-]?key|token|password|secret|authorization|cookie)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;]+)/gi, '$1[hidden]')
    .replace(/(https?:\/\/)[^\s/@]+:[^\s/@]+@/gi, '$1[hidden]@')
    .replace(/([?&#](?:key|access_token|apikey)=)[^&\s"']+/gi, '$1[hidden]')
    .slice(0, 600)
}

export function toolActivityDetail(name, arg) {
  const first = keys => keys.map(arg).find(value => typeof value === 'string' && value.trim())?.trim()
  const label = /skill/i.test(name) ? 'Loading skill'
    : /shell|bash|pwsh|powershell|exec|command|terminal/i.test(name) ? 'Running command'
      : /search|grep|glob|find/i.test(name) ? 'Searching'
        : /read|view|cat|fetch|browse/i.test(name) ? 'Reading'
          : /write|edit|patch|replace/i.test(name) ? 'Writing changes' : 'Tool call'
  const detail = /secret|credential|password|cookie/i.test(name) ? undefined
    : first(['command', 'cmd', 'file_path', 'path', 'url', 'query', 'pattern', 'skill', 'name'])
  const description = first(['description', 'justification'])
  return { tool: name, label, summary: activityText(description || detail || name), ...(detail ? { detail: activityText(detail) } : {}) }
}

// The status row only needs a short user-facing task, never full shell commands or output.
export function liveActivitySummary(name, arg) {
  if (/secret|credential|password|cookie|authorization/i.test(name)) return ''
  const first = keys => keys.map(key => arg(key)).find(value => typeof value === 'string' && value.trim())?.trim()
  const described = first(['description', 'justification', 'task', 'summary'])
  const query = first(['query', 'search_query', 'keywords', 'pattern', 'skill', 'name'])
  const path = first(['file_path', 'path'])?.split(/[\\/]/).filter(Boolean).at(-1)
  let site
  try { site = new URL(first(['url'])).hostname } catch { /* no URL */ }
  const text = described ?? query ?? path ?? site
  if (!text) return ''
  const safe = activityText(text.replace(/\s+/g, ' ').trim()).slice(0, 160)
  return safe.includes('[hidden]') ? '' : safe
}
