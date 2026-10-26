export const CHEM_CONNECTORS = [
  { id: 'chem-data-hub', name: 'Chemical Data Hub', description: 'Chemical prices, companies and industry chains', url: 'https://datahub.chem-cloud.cn/mcp', secret: 'CHEM_DATA_HUB', tokenUrl: 'https://mcp.chem-cloud.cn/' },
  { id: 'huagongshe', name: 'Huagongshe', description: 'Public chemistry search, structures and stoichiometry', url: 'https://huagongshe.com/mcp', secret: 'HUAGONGSHE', tokenUrl: 'https://huagongshe.com/zh-CN/mcp-guide', anonymous: true },
]

export function parseMcpImport(input) {
  let document
  try { document = typeof input === 'string' ? JSON.parse(input) : input } catch { throw new Error('Invalid MCP JSON; check its syntax') }
  if (!document?.mcpServers || typeof document.mcpServers !== 'object' || Array.isArray(document.mcpServers)) throw new Error('Expected mcpServers JSON')
  const entries = Object.entries(document.mcpServers)
  if (!entries.length || entries.length > 20) throw new Error('Import between 1 and 20 servers')
  const skipped = []
  const imported = []
  for (const [id, value] of entries) {
    if (!/^[a-z][a-z0-9_-]{0,31}$/i.test(id)) throw new Error('Invalid MCP server name')
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Only HTTP MCP servers are supported')
    if (typeof value.command === 'string' && value.command.trim() !== '') {
      skipped.push(id)
      continue
    }
    const kind = value.type ?? value.transport ?? (typeof value.url === 'string' ? 'streamable-http' : undefined)
    if (!['http', 'streamable-http'].includes(kind)) throw new Error('Only HTTP MCP servers are supported')
    const url = new URL(value.url)
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) throw new Error('MCP addresses must use HTTPS without credentials, query or fragment in the URL')
    const headers = value.headers ?? {}
    if (Object.keys(headers).some(key => key.toLowerCase() !== 'authorization')) throw new Error('Only the Authorization header is supported')
    const authorization = headers.Authorization ?? headers.authorization ?? ''
    if (typeof authorization !== 'string' || (authorization && !/^Bearer\s+\S+$/i.test(authorization))) throw new Error('Use Bearer authentication')
    imported.push({ id: id.toLowerCase(), url: url.href, token: authorization.replace(/^Bearer\s+/i, ''), disabled: value.disabled === true })
  }
  if (!imported.length) {
    if (skipped.length) throw new Error(`Stdio MCP (command) is not supported: ${skipped.join(', ')}`)
    throw new Error('Only HTTP MCP servers are supported')
  }
  imported.skipped = skipped
  return imported
}
