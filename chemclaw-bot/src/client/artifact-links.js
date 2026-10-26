import { useEffect, useMemo, useState } from 'react'
import { call } from './api.js'
import { artifactReferences, linkArtifacts } from '../shared/artifact-links.js'

export function useArtifactLinks(text, { sessionId, botId, live }) {
  const refs = useMemo(() => live ? [] : artifactReferences(text), [text, live])
  const key = JSON.stringify([sessionId, botId, refs.map(ref => ref.value)])
  const [resolved, setResolved] = useState({ key: null, files: {} })
  useEffect(() => {
    if (!sessionId || !refs.length) return undefined
    const controller = new AbortController()
    call('artifact-paths', { sessionId, botId, values: [...new Set(refs.map(ref => ref.value))] }, controller.signal)
      .then(result => setResolved({ key, files: result.files }))
      .catch(() => {})
    return () => controller.abort()
  }, [key])
  return resolved.key === key ? linkArtifacts(text, refs, resolved.files) : text
}
