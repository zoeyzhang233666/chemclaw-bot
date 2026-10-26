const EXTENSION = /\.(?:html?|xlsx?|csv|tsv|pptx?|docx?|pdf|md|txt|json|png|jpe?g|svg|webp)$/i

export function artifactPath(value) {
  if (typeof value !== 'string' || value.length > 2048 || /[\x00-\x1f]/.test(value)) return undefined
  let path = value.replace(/#L\d+(?:-L\d+)?$/, '')
  try { path = decodeURIComponent(path) } catch { return undefined }
  path = path.replaceAll('\\', '/').replace(/^\/([a-z]:\/)/i, '$1')
  if (/^(?![a-z]:\/)[a-z][\w+.-]*:/i.test(path) || path.startsWith('//') || /[?#\x00-\x1f]/.test(path)) return undefined
  return EXTENSION.test(path) ? path : undefined
}

// Only exact table cells, inline code and authored links are candidates. Prose,
// fenced examples and URLs do not become file names by resemblance alone.
export function artifactReferences(text) {
  const refs = []
  let fence
  let offset = 0
  for (const line of text.split('\n')) {
    const marker = /^\s{0,3}(`{3,}|~{3,})/.exec(line)?.[1]
    if (marker) {
      if (!fence) fence = marker
      else if (marker[0] === fence[0] && marker.length >= fence.length) fence = undefined
      offset += line.length + 1
      continue
    }
    if (!fence) {
      const add = (start, end, value, label, suffix = '') => {
        if (refs.length >= 40 || !artifactPath(value) || refs.some(ref => start < ref.end && end > ref.start)) return
        refs.push({ start, end, value, label, suffix })
      }
      for (const match of line.matchAll(/(?<!!)\[([^\]\n]*)\]\((?:<([^>\n]+)>|([^\s)]+))\)/g)) {
        const value = match[2] ?? match[3]
        add(offset + match.index, offset + match.index + match[0].length, value, match[1], /#L\d+(?:-L\d+)?$/.exec(value)?.[0])
      }
      for (const match of line.matchAll(/(?<!`)`([^`\n]+)`(?!`)/g)) {
        add(offset + match.index, offset + match.index + match[0].length, match[1], match[1])
      }
      if (line.includes('|')) {
        for (const match of line.matchAll(/(?:^|(?<=\|))([^|]+)/g)) {
          const value = match[1].trim()
          if (/[`\[\]*<>]/.test(value)) continue
          const start = offset + match.index + match[0].indexOf(value)
          add(start, start + value.length, value, value)
        }
      }
    }
    offset += line.length + 1
  }
  return refs.sort((a, b) => a.start - b.start)
}

export function linkArtifacts(text, refs, files) {
  let linked = text
  for (const ref of [...refs].reverse()) {
    const path = files[ref.value]
    if (typeof path !== 'string' || !artifactPath(path)) continue
    const href = encodeURI(path.replaceAll('\\', '/')).replaceAll('#', '%23').replaceAll('?', '%3F').replaceAll('(', '%28').replaceAll(')', '%29')
    const label = ref.label.replaceAll('\\', '\\\\').replaceAll('[', '\\[').replaceAll(']', '\\]')
    linked = `${linked.slice(0, ref.start)}[${label}](<${href}${ref.suffix ?? ''}>)${linked.slice(ref.end)}`
  }
  return linked
}
