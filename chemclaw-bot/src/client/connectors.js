import { createElement as h, useEffect, useRef, useState } from 'react'
import { useMorph } from './motion.js'
import { MaskedInput } from './secret-card.js'
import { t } from './i18n.js'
import { ApiHubMark, CloudMark, ChemistryMark } from './brand-icons.js'
import { PlugIcon } from './icons.js'
import { ServiceInstaller } from './service-installer.js'

const TOKEN_URL = 'https://github.com/settings/personal-access-tokens/new'
const CHEMCLOUD_CHIPS = ['Compounds', 'Companies & customers', 'Trades & orders', 'Market & prices']

export const GitHubMark = () => h('svg', { width: 20, height: 20, viewBox: '0 0 16 16', fill: 'currentColor', 'aria-hidden': true },
  h('path', { d: 'M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z' }))

const MARKS = { github: GitHubMark, 'chem-data-hub': ApiHubMark, huagongshe: ChemistryMark }
const ABOUT = { github: () => t('Repositories, issues, and pull requests') }

function statusText(connector) {
  if (connector.state === 'connecting') return t('Connecting…')
  if (connector.state === 'error') return t('Could not connect: {error}', { error: connector.error ?? '' })
  if (connector.state === 'ready') return connector.account ? t('Connected as {account}', { account: connector.account }) : t('Connected')
  return connector.description ? t(connector.description) : ABOUT[connector.id]?.() ?? ''
}

function useConnectorForm(connector, actions) {
  const [form, setForm] = useState(false)
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const run = (task, after) => {
    setBusy(true)
    setError(null)
    return task.then(() => { after?.() }, failure => setError(failure?.message ?? String(failure))).finally(() => setBusy(false))
  }
  const connect = () => {
    if (busy || token.trim() === '') return
    void run(actions.connectorConnect(connector.id, token), () => { setToken(''); setForm(false) })
  }
  const cancel = () => { setForm(false); setToken(''); setError(null) }
  return { form, setForm, token, setToken, busy, error, run, connect, cancel, on: connector.state !== 'off', tokenUrl: connector.tokenUrl ?? TOKEN_URL }
}

function ConnectorActions({ connector, actions, form, setForm, busy, run, on }) {
  return h('span', { className: 'bt-connector-actions' },
    !connector.generic && (connector.anonymous || connector.authenticated || connector.state === 'error') ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => setForm(!form) }, t('Change key')) : null,
    connector.state === 'error' ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => void run(actions.connectorRetry(connector.id)) }, t('Try again')) : null,
    on
      ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => void run(actions.connectorDisconnect(connector.id)) }, t('Disconnect'))
      : form ? null : h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => connector.anonymous ? void run(actions.connectorConnect(connector.id, '')) : setForm(true) }, t('Connect')))
}

function ConnectorKeyForm({ connector, form, token, setToken, busy, connect, cancel, tokenUrl }) {
  if (!form) return null
  return h('div', { className: 'bt-connector-form' },
    connector.url ? h('span', { className: 'bt-set-hint' }, connector.url) : null,
    h('label', { className: 'bt-q-field bt-secret-field' }, h(MaskedInput, { value: token, onChange: setToken, onEnter: connect, label: t('Paste or enter a key'), autoFocus: true })),
    h('div', { className: 'bt-connector-form-row' },
      h('a', { className: 'bt-connector-link', href: tokenUrl, target: '_blank', rel: 'noopener noreferrer' }, t(connector.id === 'github' ? 'Create a token on GitHub' : 'Get an API key')),
      h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: cancel }, t('Cancel')),
      h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy || token.trim() === '', onClick: connect }, busy ? t('Connecting…') : t('Connect'))))
}

function ConnectorRow({ connector, actions }) {
  const state = useConnectorForm(connector, actions)
  const Mark = MARKS[connector.id]
  const row = useRef(null)
  useMorph(row, `${state.form}:${state.error !== null}:${connector.state}`)
  return h('div', { ref: row, className: 'bt-connector', 'data-state': connector.state },
    h('div', { className: 'bt-connector-head' },
      h('span', { className: 'bt-connector-mark' }, h(Mark ?? PlugIcon)),
      h('span', { className: 'bt-connector-text' },
        h('span', { className: 'bt-connector-name' }, t(connector.name)),
        h('span', { className: 'bt-connector-status' }, statusText(connector))),
      h(ConnectorActions, { connector, actions, ...state })),
    h(ConnectorKeyForm, { connector, ...state }),
    state.error ? h('div', { className: 'bt-connector-error', role: 'alert' }, state.error) : null)
}

function ChemcloudCard({ connector, actions, focusKey = false }) {
  const { token, setToken, busy, error, run, connect, on, tokenUrl } = useConnectorForm(connector, actions)
  const card = useRef(null)
  const keyRef = useRef(null)
  useMorph(card, `${error !== null}:${connector.state}`)
  useEffect(() => {
    if (!focusKey) return undefined
    card.current?.scrollIntoView?.({ block: 'nearest' })
    const timer = setTimeout(() => { keyRef.current?.querySelector?.('input')?.focus?.() }, 0)
    return () => clearTimeout(timer)
  }, [focusKey])
  return h('article', { ref: card, className: 'bt-chemcloud', 'data-state': connector.state, 'aria-label': t('Chemcloud Data Hub') },
    h('header', null,
      h('span', { className: 'bt-connector-mark' }, h(ApiHubMark)),
      h('div', { className: 'bt-chemcloud-title' },
        h('span', { className: 'bt-eyebrow' }, t('Chemcloud MCP')),
        h('h3', null, t('Chemcloud Data Hub'))),
      h('span', { className: 'bt-connector-actions' },
        connector.state === 'error' ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => void run(actions.connectorRetry(connector.id)) }, t('Try again')) : null,
        on ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => void run(actions.connectorDisconnect(connector.id)) }, t('Disconnect')) : null)),
    h('p', { className: 'bt-chemcloud-intro' }, t('Query chemical industry data in your AI client: compounds, company profiles, trade records and market prices.')),
    h('div', { className: 'bt-chemcloud-chips' }, CHEMCLOUD_CHIPS.map(label => h('span', { key: label, className: 'bt-chemcloud-chip' }, t(label)))),
    h('p', { className: 'bt-chemcloud-status', 'data-state': connector.state }, statusText(connector)),
    h('div', { className: 'bt-chemcloud-key', ref: keyRef },
      h('label', { className: 'bt-q-field bt-secret-field' }, h(MaskedInput, { value: token, onChange: setToken, onEnter: connect, label: t('Paste or enter a key'), autoFocus: focusKey })),
      h('div', { className: 'bt-chemcloud-key-row' },
        h('a', { className: 'bt-connector-link', href: tokenUrl, target: '_blank', rel: 'noopener noreferrer' }, t('Get an API key')),
        h('span', { className: 'bt-chemcloud-portal' }, tokenUrl.replace(/^https?:\/\//, '').replace(/\/$/, '')),
        h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy || token.trim() === '', onClick: connect }, busy ? t('Connecting…') : t(on ? 'Change key' : 'Connect')))),
    error ? h('div', { className: 'bt-connector-error', role: 'alert' }, error) : null)
}


function ImaCard({ connector, actions }) {
  const [clientId, setClientId] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(!connector.authenticated)
  const [query, setQuery] = useState('芯化智数')
  const [libraries, setLibraries] = useState([])
  const [cursor, setCursor] = useState('')
  const [isEnd, setIsEnd] = useState(true)
  const [searched, setSearched] = useState(false)
  const [searching, setSearching] = useState(false)
  const [notice, setNotice] = useState('')

  const find = async (term, nextCursor = '') => {
    setSearching(true); setError('')
    try {
      const result = await actions.imaLibraries(term, nextCursor)
      setLibraries(old => nextCursor ? [...old, ...(result.libraries ?? [])] : (result.libraries ?? []))
      setCursor(result.nextCursor ?? '')
      setIsEnd(result.isEnd !== false)
      setSearched(true)
    } catch (failure) { setError(failure?.message ?? String(failure)) }
    finally { setSearching(false) }
  }

  // A successful connection may be read-only. Do not assume membership until
  // the user's accessible knowledge-base list confirms the actual library ID.
  useEffect(() => {
    if (!connector.authenticated || connector.state !== 'ready') return
    void find('芯化智数')
  }, [connector.authenticated, connector.state])

  const connect = async () => {
    if (busy || !clientId.trim() || !apiKey.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      await actions.connectorConnect('ima', JSON.stringify({ clientId: clientId.trim(), apiKey: apiKey.trim() }))
      setClientId(''); setApiKey(''); setEditing(false)
      setSearched(false); setLibraries([])
    } catch (failure) { setError(failure?.message ?? String(failure)) }
    finally { setBusy(false) }
  }
  const act = async task => {
    setBusy(true); setError('')
    try { await task } catch (failure) { setError(failure?.message ?? String(failure)) }
    finally { setBusy(false) }
  }
  const pin = async library => {
    await act(actions.imaSelectLibrary(library.id).then(result => {
      setNotice(t('Verified access to {name}. ChemClaw will use it as the default knowledge base.', { name: result.pinned?.name ?? library.name }))
    }))
  }
  const pinned = connector.pinned

  return h('article', { className: 'bt-set-card bt-connectors-card', 'aria-label': t('Tencent ima Knowledge Base') },
    h('div', { className: 'bt-connector', 'data-state': connector.state },
      h('div', { className: 'bt-connector-head' },
        h('span', { className: 'bt-connector-mark' }, h(PlugIcon)),
        h('span', { className: 'bt-connector-text' },
          h('span', { className: 'bt-connector-name' }, t('Tencent ima Knowledge Base')),
          h('span', { className: 'bt-connector-status' }, statusText(connector))),
        h('span', { className: 'bt-connector-actions' },
          connector.state === 'error' && connector.authenticated
            ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => void act(actions.connectorRetry('ima')) }, t('Try again')) : null,
          connector.authenticated
            ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => setEditing(!editing) }, t('Change key')) : null,
          connector.authenticated
            ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => void act(actions.connectorDisconnect('ima').then(() => { setEditing(true); setClientId(''); setApiKey(''); setLibraries([]); setSearched(false); setNotice('') })) }, t('Disconnect')) : null)),
      h('div', { className: 'bt-connector-form' },
        h('strong', null, t('Featured chemical industry knowledge base')),
        h('div', null, '芯化智数 · 化工产业知识库'),
        h('p', { className: 'bt-set-hint' }, t('Curated chemical industry research and supply-chain materials maintained in ima. Subscription happens on the official ima website, not in ChemClaw.')),
        h('a', { className: 'bt-connector-link', href: 'https://ima.qq.com/wiki/?shareId=4d781b6d98e6949ec4e2cfb1b8b329106393fbc62de98215783ae9a78e79148b', target: '_blank', rel: 'noopener noreferrer' }, t('Open ima to subscribe to the Chemcloud library')),
        h('p', { className: 'bt-set-hint' }, t('Step 1: Open ima, sign in (ima may show a WeChat QR code), and subscribe to the library. This QR sign-in does not authorize ChemClaw.'))),
      editing ? h('div', { className: 'bt-connector-form' },
        h('p', { className: 'bt-set-hint' }, t('Step 2: In ima, open the official agent authorization page, create your personal Client ID and API Key, then paste them here once. The API Key may be shown only once; keep it private.')),
        h('a', { className: 'bt-connector-link', href: 'https://ima.qq.com/agent-interface', target: '_blank', rel: 'noopener noreferrer' }, t('Open ima authorization page')),
        h('label', { className: 'bt-q-field bt-secret-field' },
          h('span', null, t('Client ID')),
          h('input', { value: clientId, placeholder: t('Paste ima Client ID'), autoComplete: 'off', spellCheck: false, onChange: event => setClientId(event.target.value), 'aria-label': t('Client ID') })),
        h('label', { className: 'bt-q-field bt-secret-field' },
          h('span', null, t('API Key')),
          h(MaskedInput, { value: apiKey, onChange: setApiKey, onEnter: connect, label: t('Enter ima API Key') })),
        h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy || !clientId.trim() || !apiKey.trim(), onClick: connect }, t(busy ? 'Connecting…' : 'Connect')),
        h('p', { className: 'bt-set-hint' }, t('Your credentials are stored locally, are not shown to the AI model, and can be disconnected at any time.')) ) : null,
      connector.authenticated ? h('div', { className: 'bt-connector-form' },
        h('strong', null, t('Step 3: Verify your accessible knowledge bases')),
        h('p', { className: 'bt-set-hint' }, t('Search all readable knowledge bases, including subscriptions where ima OpenAPI permits access. Being connected is not proof that you subscribed.')),
        h('div', { className: 'bt-connector-form-row' },
          h('input', { value: query, onChange: event => setQuery(event.target.value), onKeyDown: event => { if (event.key === 'Enter' && !searching) void find(query) }, placeholder: t('Search knowledge base name'), 'aria-label': t('Search knowledge base name') }),
          h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: searching, onClick: () => void find(query) }, t('Search')),
          h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: searching, onClick: () => { setQuery(''); void find('') } }, t('Show my libraries'))),
        pinned ? h('div', { className: 'bt-set-hint' },
          t('Default readable library: {name}', { name: pinned.name }),
          ' · ',
          h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy, onClick: () => void act(actions.imaClearLibrary().then(() => setNotice(''))) }, t('Clear default'))) : null,
        searched && libraries.length === 0 ? h('p', { className: 'bt-set-hint' }, t('No accessible knowledge base matched. Subscribe on the ima website and search again.')) : null,
        libraries.map(library => h('div', { key: library.id, className: 'bt-connector-form-row' },
          h('span', { className: 'bt-connector-text' }, library.name),
          h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: busy || pinned?.id === library.id, onClick: () => void pin(library) },
            pinned?.id === library.id ? t('Selected') : t('Use for research')))),
        !isEnd && cursor ? h('button', { type: 'button', className: 'bt-soft bt-soft-sm', disabled: searching, onClick: () => void find(query, cursor) }, t('Load more')) : null,
        notice ? h('p', { role: 'status', className: 'bt-set-hint' }, notice) : null) : null,
      error ? h('div', { role: 'alert', className: 'bt-connector-error' }, error) : null))
}

// Settings → Connectors: one row per connector.
export function ConnectorsPage({ roster, actions, focusId = null }) {
  const list = roster?.connectors ?? []
  const [json, setJson] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [data, setData] = useState(null)
  const [adding, setAdding] = useState(false)
  const chemcloud = list.find(item => item.id === 'chem-data-hub')
  const ima = list.find(item => item.id === 'ima')
  const others = list.filter(item => item.id !== 'huagongshe' && item.id !== 'chem-data-hub' && item.id !== 'ima')
  const check = () => actions.dataStatus().then(setData).catch(failure => setError(failure.message))
  useEffect(() => { void check() }, [list.map(item => `${item.id}:${item.state}`).join('|')])
  const importJson = async () => {
    setBusy(true); setError('')
    try {
      const result = await actions.connectorImport(json)
      setJson('')
      if (result?.skipped?.length) setError(t('Skipped stdio servers: {names}', { names: result.skipped.join(', ') }))
    } catch (failure) { setError(failure.message) } finally { setBusy(false) }
  }
  return h('section', { className: 'bt-set-section bt-connectors-page' },
    h('div', { className: 'bt-actions' }, h('button', { className: 'bt-soft', onClick: () => setAdding(!adding) }, t('Add a tool service'))),
    adding ? h(ServiceInstaller, { actions, onClose: () => setAdding(false) }) : null,
    error ? h('div', { className: 'bt-error', role: 'alert' }, error) : null,
    chemcloud ? h(ChemcloudCard, { connector: chemcloud, actions, focusKey: focusId === 'chem-data-hub' }) : null,
    ima ? h(ImaCard, { connector: ima, actions }) : null,
    !chemcloud && others.length === 0
      ? h('div', { className: 'bt-set-card bt-connectors-card' }, h('div', { className: 'bt-set-row' }, h('span', { className: 'bt-set-hint' }, t('No connectors'))))
      : others.length
        ? h('div', { className: 'bt-set-card bt-connectors-card' }, others.map(connector => h(ConnectorRow, { key: connector.id, connector, actions })))
        : null,
    h('p', { className: 'bt-set-hint' }, t('Huagongshe public queries need no key. Company credentials are optional for public research.')),
    h('h3', null, t('Public research data')),
    h('div', { className: 'bt-data-grid' }, data?.sources.map(source => h('article', { key: source.name, className: 'bt-data-card', 'data-state': source.state },
      h('header', null, h('span', { className: 'bt-connector-mark' }, h(source.name === 'Huagongshe' || source.name === 'PubChem' || source.name === 'OPSIN' ? ChemistryMark : CloudMark)), h('strong', null, t(source.name))),
      h('p', null, source.coverage),
      h('div', { className: 'bt-data-state' }, h('span', null, t(source.state)), h('span', null, t('No API key required'))),
      source.error ? h('p', { role: 'status' }, source.error) : null,
      source.name === 'Huagongshe' ? h('div', { className: 'bt-actions' }, h('button', { className: 'bt-soft bt-soft-sm', onClick: () => void (source.state === 'off' ? actions.connectorConnect('huagongshe', '') : actions.connectorRetry('huagongshe')).then(check).catch(failure => setError(failure.message)) }, t('Try again'))) : null))),
    h('details', { className: 'bt-advanced' }, h('summary', null, t('Optional Huagongshe authorization')),
      h('p', { className: 'bt-set-hint' }, t('Public chemistry search and drawing work anonymously. An AI Key is optional; private data and write tools remain disabled in this release.')),
      list.find(item => item.id === 'huagongshe') ? h(ConnectorRow, { connector: list.find(item => item.id === 'huagongshe'), actions }) : null),
    h('details', { className: 'bt-advanced' }, h('summary', null, t('Advanced: import MCP JSON')),
      h('textarea', { value: json, onChange: event => setJson(event.target.value), rows: 6, placeholder: '{"mcpServers":{"service":{"type":"http","url":"https://example.com/mcp"}}}', spellCheck: false, 'aria-label': t('MCP configuration JSON') }),
      h('button', { className: 'bt-soft', disabled: busy || !json.trim(), onClick: importJson }, t(busy ? 'Connecting…' : 'Import'))))
}
