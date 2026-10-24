// Upstream behavior suites exercise an isolated Chief fixture. Product seeding and
// chemical connectors have their own integration suites with production defaults.
import { createRuntime as runtime } from '../index.js'
export * from '../index.js'
const defaults = { seedTeam: false, companyConnectors: false, updateCheck: true, mainName: 'Chief', mainRole: 'Chief of Staff' }
export const createRuntime = (ctx, config) => runtime(ctx, { ...defaults, ...config })
export const apply = (ctx, config) => { createRuntime(ctx, config) }
