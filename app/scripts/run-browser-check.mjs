import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const env = { ...process.env }
delete env.ELECTRON_RUN_AS_NODE
for (const key of Object.keys(env)) if (/KEY|TOKEN|PASSWORD|SECRET/iu.test(key)) delete env[key]
const executable = process.argv[2] ?? createRequire(import.meta.url)('electron')
const child = spawn(executable, [fileURLToPath(new URL('./check-browser.mjs', import.meta.url))], {
  env, windowsHide: true, stdio: 'inherit',
})
child.once('error', error => { console.error(error); process.exitCode = 1 })
child.once('exit', code => { process.exitCode = code ?? 1 })
