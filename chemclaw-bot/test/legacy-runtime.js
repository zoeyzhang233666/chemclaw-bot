// Upstream behavior suites exercise an isolated Chief fixture. Product seeding and
// chemical connectors have their own integration suites with production defaults.
import { createRuntime as runtime } from '../index.js'
export * from '../index.js'
// updateCheck must stay off in the shared test fixture: the 15s startup fetch keeps
// the process alive after dispose if a suite runs longer than the delay (Node 24 on
// Linux then never exits the test child). Opt in only in update.test.js.
const defaults = { seedTeam: false, companyConnectors: false, updateCheck: false, mainName: 'Chief', mainRole: 'Chief of Staff' }
export const createRuntime = (ctx, config) => runtime(ctx, { ...defaults, ...config })
export const apply = (ctx, config) => { createRuntime(ctx, config) }
