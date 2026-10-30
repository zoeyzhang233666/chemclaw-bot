import { defineTool } from '@deepseek-ai/dsh-tools'

export async function fetchPublic(url, { fetch: request = globalThis.fetch, signal } = {}) {
  const response = await request(url, { headers: { Accept: 'application/json', 'User-Agent': 'ChemClaw/0.2 (chemical research)' }, signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(20_000)]) : AbortSignal.timeout(20_000) })
  if (!response.ok) throw new Error(`Public source returned HTTP ${response.status}; retry or import a file. No substitute data was generated.`)
  const content = await response.text()
  if (content.length > 4_000_000) throw new Error('Public response is too large; narrow the query')
  return { source: url, retrievedAt: new Date().toISOString(), data: JSON.parse(content) }
}

export function publicUrl(service, query, language = 'zh') {
  const q = encodeURIComponent(String(query).trim())
  if (!q) throw new Error('Enter a compound or search term')
  if (service === 'pubchem') return `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/${q}/property/MolecularFormula,MolecularWeight,IUPACName,CanonicalSMILES,IsomericSMILES/JSON`
  if (service === 'opsin') return `https://opsin.ch.cam.ac.uk/opsin/${q}.json`
  if (service === 'wikipedia') return `https://${language === 'en' ? 'en' : 'zh'}.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch=${q}&gsrlimit=5&prop=extracts|info&exintro=1&explaintext=1&inprop=url&format=json&origin=*`
  throw new Error('Unknown public source')
}

export function install(rt) {
  const cache = new Map()
  let pubchemQueue = Promise.resolve()
  const output = { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] }
  rt.publicDataStatus = () => [{ name: 'Huagongshe', coverage: '匿名化学检索、分子与反应式绘图、投料计算；公开查询不需要 AI Key。', state: 'unqueried', ...rt.connectorStatus?.('huagongshe') }, ...[
    ['PubChem', '化合物标识、结构、分子式与分子量；物性需继续查阅原始实验来源'],
    ['OPSIN', '英文系统名称转结构；解析结果需要交叉核验'],
    ['Wikipedia', '中英文百科检索；不能作为价格或合规结论的唯一来源'],
    ['AKShare', '历史日频：国内主力连续和可覆盖的国外合约；首次使用自动准备行情组件，不保证实时'],
  ].map(([name, coverage]) => ({ name, coverage, ...(cache.get(name.toLowerCase()) ?? { state: 'unqueried' }) })), ...(rt.cninfoStatus ? [rt.cninfoStatus()] : [])]
  rt.searchPluginStatus = async () => {
    const rows = await rt.ctx.get?.('pluginManager')?.listPlugins?.().catch(() => []) ?? []
    const row = rows.find(row => row.moduleName === 'dsh-free-search')
    return {
      name: 'dsh-free-search',
      coverage: 'ChemClaw 随包内置的免 Key 联网搜索与网页读取插件。在插件页展开 ChemClaw 可查看 Free Search；已加载表示插件就绪，具体网站是否可访问以查询结果为准。',
      state: row?.enabled && row.fiberPhase === 'active' ? 'loaded' : row?.fiberPhase === 'failed' ? 'error' : 'off',
    }
  }
  rt.ctx.tools.register(defineTool({ name: 'chem_public_query', description: 'Query keyless PubChem, OPSIN or Chinese/English Wikipedia. Returns source and retrieval time. Cross-check identities; missing data is an explicit gap.', parameters: { service: { type: 'string', required: true, enum: ['pubchem', 'opsin', 'wikipedia'] }, query: { type: 'string', required: true }, language: { type: 'string', enum: ['zh', 'en'] } }, output, execute: async (args, exec) => {
    const url = publicUrl(args.service, args.query, args.language)
    const run = async () => {
      try {
        const result = await fetchPublic(url, { fetch: rt.config.publicFetch, signal: exec.signal })
        cache.set(args.service, { state: 'ready', checkedAt: result.retrievedAt })
        return JSON.stringify(result)
      } catch (error) {
        cache.set(args.service, { state: 'error', error: error.message })
        throw error
      }
    }
    if (args.service !== 'pubchem') return run()
    const result = pubchemQueue.then(run)
    pubchemQueue = result.catch(() => {}).then(() => new Promise(resolve => setTimeout(resolve, 250)))
    return result
  } }))
}
