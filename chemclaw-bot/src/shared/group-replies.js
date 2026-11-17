// Reads the replies of a settled group_relay result. Compaction can prune the
// middle of a long tool result, which leaves invalid JSON: then every complete
// reply object that survived is recovered so the turn still draws what it can.
const RELAY_LIST = /"replies"\s*:\s*\[/
// Compaction marks a pruned span with a literal bracketed note like
// "[... tool result middle pruned ...]". Its "]" looks like the end of the
// replies array to a naive scan, so the text is split on the marker first.
const PRUNE_MARKER = /\[\.\.\. tool result middle pruned \.\.\.\]/
export function parseReplies(text) {
  try {
    const value = JSON.parse(text)
    if (!value || typeof value !== 'object' || Array.isArray(value) || !Array.isArray(value.replies)) return { replies: [], broken: true }
    const replies = value.replies.filter(isReply)
    return { replies, broken: replies.length !== value.replies.length }
  } catch { /* fall through */ }
  const replies = []
  const head = RELAY_LIST.exec(text)
  if (head) {
    for (const piece of text.slice(head.index + head[0].length).split(PRUNE_MARKER)) {
      // The cut can start inside a string, leaving a fragment that keeps the
      // scanner inside quotes: restart at the first complete reply instead.
      const first = /\{\s*"/.exec(piece)
      if (first) scanReplies(piece, first.index, replies)
    }
  }
  return { replies, broken: true }
}

function isReply(reply) {
  return reply !== null && typeof reply === 'object' && !Array.isArray(reply)
    && (typeof reply.text === 'string' || typeof reply.kind === 'string')
    && (reply.text === undefined || typeof reply.text === 'string')
}

function scanReplies(text, start, replies) {
  let depth = 0
  let from = -1
  let inString = false
  let escaped = false
  for (let i = start; i < text.length; i += 1) {
    const ch = text[i]
    if (inString) {
      if (escaped) escaped = false
      else if (ch === '\\') escaped = true
      else if (ch === '"') inString = false
      continue
    }
    if (ch === '"') { inString = true; continue }
    if (ch === '{') {
      if (depth === 0) from = i
      depth += 1
    } else if (ch === '}') {
      depth -= 1
      if (depth === 0 && from >= 0) {
        try {
          const reply = JSON.parse(text.slice(from, i + 1))
          if (isReply(reply)) replies.push(reply)
        } catch { /* partial object */ }
        from = -1
      }
    } else if (ch === ']' && depth === 0) break
  }
}

