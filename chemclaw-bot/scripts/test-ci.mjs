#!/usr/bin/env node
// CI / hang diagnosis: run each test/*.test.js in its own process, serially,
// with a per-file budget. Prints START/END so a stuck file is visible in logs.
import { spawn } from 'node:child_process'
import { readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const budgetMs = Number(process.env.TEST_FILE_BUDGET_MS ?? 180_000)
const files = readdirSync(join(root, 'test'))
  .filter(name => name.endsWith('.test.js'))
  .sort()

function runFile(file) {
  return new Promise((resolve) => {
    const child = spawn(
      process.execPath,
      ['--import', './test/harness-resolve.mjs', '--test', join('test', file)],
      { cwd: root, stdio: 'inherit', env: process.env },
    )
    const timer = setTimeout(() => {
      console.error(`[test-ci] HANG ${file} after ${budgetMs}ms — signalling child`)
      child.kill('SIGTERM')
      setTimeout(() => child.kill('SIGKILL'), 5000)
    }, budgetMs)
    child.on('exit', (code, signal) => {
      clearTimeout(timer)
      if (signal) {
        console.error(`[test-ci] ${file} killed by ${signal}`)
        resolve(1)
        return
      }
      resolve(code ?? 1)
    })
  })
}

let failed = 0
const started = Date.now()
console.log(`[test-ci] ${files.length} files, budget ${budgetMs}ms each, node ${process.version}`)
for (const file of files) {
  const at = new Date().toISOString()
  console.log(`[test-ci] START ${file} ${at}`)
  const code = await runFile(file)
  console.log(`[test-ci] END ${file} exit=${code} +${((Date.now() - started) / 1000).toFixed(1)}s`)
  if (code !== 0) {
    failed = code
    break
  }
}
process.exit(failed)
