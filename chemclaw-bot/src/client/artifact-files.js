import { createElement as h } from 'react'
import { contentText } from './text.js'
import { t } from './i18n.js'

export function generatedFiles(call) {
  if (call.kind !== 'tool-result' || call.isError) return []
  try {
    const result = JSON.parse(contentText(call.content))
    const seen = new Set()
    return (Array.isArray(result.files) ? result.files : []).filter(file => {
      if (typeof file?.path !== 'string' || !/^(?:[a-z]:[\\/]|\/)/i.test(file.path)
        || [...file.path].some(character => character.charCodeAt(0) < 32) || seen.has(file.path)) return false
      seen.add(file.path)
      return true
    })
  } catch { return [] }
}

export function ArtifactFiles({ files, openFile }) {
  if (!files.length || !openFile) return null
  return h('div', { className: 'bt-artifact-files' }, files.map(file => {
    const name = file.path.split(/[\\/]/).at(-1)
    return h('button', { key: file.path, type: 'button', className: 'bt-artifact-file', title: file.path,
      'aria-label': t('Open generated file {name}', { name }), onClick: () => openFile(file.path) },
    h('strong', null, name), h('span', null, t('Click to open file')))
  }))
}
