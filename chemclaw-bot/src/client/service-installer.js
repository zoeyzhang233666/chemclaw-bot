import { createElement as h, useEffect, useRef, useState } from 'react'
import { t } from './i18n.js'

export function ServiceInstaller({ actions, onClose }) {
  const [mode, setMode] = useState('url')
  const [draft, setDraft] = useState({ name: '', description: '', url: '', command: '', args: '', env: '{}', headers: '{}', json: '', key: '' })
  const [review, setReview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef(null)
  useEffect(() => () => { if (pending.current) void actions.cancelService(pending.current).catch(() => {}) }, [])
  const set = (key, value) => setDraft(old => ({ ...old, [key]: value }))
  const field = (key, label, multiline = false, placeholder) => h('label', { key }, t(label), h(multiline ? 'textarea' : 'input', { className: 'bt-input', value: draft[key], placeholder, type: key === 'key' ? 'password' : undefined, autoComplete: 'off', spellCheck: false, onChange: event => set(key, event.target.value) }))
  const inspect = async event => {
    event.preventDefault(); setError(''); setBusy(true)
    try { if (pending.current) await actions.cancelService(pending.current); const result = await actions.previewService({ mode, ...draft }); pending.current = result.token; setReview(result) } catch (failure) { setError(failure.message) } finally { setBusy(false) }
  }
  const save = async () => {
    setBusy(true); setError('')
    try {
      await actions.saveService({ token: review.token })
      pending.current = null
      setDraft({ name: '', description: '', url: '', command: '', args: '', env: '{}', headers: '{}', json: '', key: '' }); onClose()
    } catch (failure) { setError(failure.message) } finally { setBusy(false) }
  }
  return h('section', { className: 'bt-skill-wizard bt-set-card', 'aria-label': t('Add a tool service') },
    h('header', { className: 'bt-skill-section-head' }, h('h3', null, t('Add a tool service')), h('button', { className: 'bt-soft', disabled: busy, onClick: onClose }, t('Cancel'))),
    review ? h('div', { className: 'bt-skill-form' },
      h('p', null, t('Review the connection before saving. Credentials are stored securely.')),
      review.items.map(item => h('article', { key: item.name, className: 'bt-skill-detected' }, h('strong', null, item.name), h('p', null, item.description), h('p', null, item.transport === 'stdio' ? t('Local command: {command}', { command: item.command }) : item.url), h('p', null, t('{count} credential fields', { count: item.credentials })), item.transport === 'stdio' ? h('p', { className: 'bt-set-hint' }, t('Confirming starts this command on your computer when a Bot uses the service.')) : null)),
      h('div', { className: 'bt-actions' }, h('button', { className: 'bt-soft', disabled: busy, onClick: () => setReview(null) }, t('Back')), h('button', { className: 'bt-soft bt-skill-primary', disabled: busy, onClick: () => void save() }, t('Confirm and test connection')))) : h('form', { className: 'bt-skill-form', onSubmit: inspect },
      h('div', { className: 'bt-catalog-categories' }, [['url', 'Service address'], ['json', 'Paste configuration'], ['stdio', 'Local command']].map(([id, label]) => h('button', { key: id, type: 'button', 'aria-pressed': mode === id, onClick: () => setMode(id) }, t(label)))),
      mode === 'json' ? h('div', null, field('json', 'Paste the service configuration from its provider', true, '{"mcpServers":{"my-service":{"url":"https://example.com/mcp"}}}')) : h('div', { className: 'bt-skill-form' }, field('name', 'Service ID', false, 'my-service'), field('description', 'What this service helps with'),
        mode === 'url' ? h('div', { className: 'bt-skill-form' }, field('url', 'Service address', false, 'https://example.com/mcp'), field('key', 'API key (optional)')) : h('div', { className: 'bt-skill-form' }, field('command', 'Command', false, 'npx'), field('args', 'Arguments (one per line)', true))),
      mode !== 'json' ? h('details', { className: 'bt-advanced' }, h('summary', null, t('Advanced configuration')), mode === 'stdio' ? field('env', 'Environment (JSON)', true) : field('headers', 'Headers (JSON)', true)) : null,
      h('button', { className: 'bt-soft', disabled: busy }, t('Review connection'))),
    busy ? h('p', { role: 'status' }, t('Checking connection…')) : null,
    error ? h('p', { role: 'alert', className: 'bt-error' }, error) : null)
}
