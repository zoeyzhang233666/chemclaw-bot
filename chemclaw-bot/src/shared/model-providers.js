export const APIHUB = Object.freeze({
  id: 'apihub',
  name: 'APIHub',
  baseURL: 'https://apihub.chem-cloud.cn/v1',
  tokenUrl: 'https://apihub.chem-cloud.cn/keys',
  portalUrl: 'https://apihub.chem-cloud.cn/',
  api: 'openai-completions',
})

// OpenCode Zen Go: same key as Zen (`OPENCODE_API_KEY`), different base from `opencode`.
export const OPENCODE_GO = Object.freeze({
  id: 'opencode-go',
  name: 'opencode-go',
  baseURL: 'https://opencode.ai/zen/go/v1',
  api: 'openai-completions',
  apiKeyEnv: 'OPENCODE_API_KEY',
})
