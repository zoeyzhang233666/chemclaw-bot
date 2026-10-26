// Run against a signed .app; this never replaces a release asset.
import { appendFile, mkdir, stat, writeFile } from 'node:fs/promises'
import { basename, join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import { performance } from 'node:perf_hooks'

if (process.platform !== 'darwin') throw new Error('Run this benchmark on macOS')
const [source, destination] = process.argv.slice(2)
if (!source || !destination) throw new Error('Usage: node scripts/benchmark-mac-zip.mjs <signed.app> <new-output-folder>')
const app = resolve(source)
const output = resolve(destination)
if (!app.endsWith('.app') || !(await stat(app)).isDirectory()) throw new Error('Give a signed .app directory')
// An existing directory is deliberately refused so previous evidence is retained.
await mkdir(output)
const run = (command, args) => {
  const result = spawnSync(command, args, { encoding: 'utf8', timeout: 20 * 60_000 })
  if (result.error) throw result.error
  if (result.status !== 0) throw new Error(`${command} failed: ${result.stderr}`)
}
run('codesign', ['--verify', '--deep', '--strict', app])
const results = []
for (const level of [1, 6, 9]) {
  const archive = join(output, `level-${level}.zip`)
  const start = performance.now()
  run('ditto', ['-c', '-k', '--sequesterRsrc', '--keepParent', '--zlibCompressionLevel', String(level), app, archive])
  const seconds = (performance.now() - start) / 1000
  const unpacked = join(output, `level-${level}`)
  await mkdir(unpacked)
  run('ditto', ['-x', '-k', archive, unpacked])
  run('codesign', ['--verify', '--deep', '--strict', join(unpacked, basename(app))])
  results.push({ level, seconds: Number(seconds.toFixed(2)), bytes: (await stat(archive)).size })
}
await writeFile(join(output, 'results.json'), JSON.stringify({ compressor: 'ditto', architecture: process.arch, results }, null, 2))
const table = ['| ZIP level (ditto) | Seconds | MiB |', '| --- | ---: | ---: |', ...results.map(row => `| ${row.level} | ${row.seconds} | ${(row.bytes / 1048576).toFixed(1)} |`)].join('\n')
console.log(table)
if (process.env.GITHUB_STEP_SUMMARY) await appendFile(process.env.GITHUB_STEP_SUMMARY, `\n### macOS ${process.arch} ZIP benchmark\n\n${table}\n\nAll archives passed extraction and signature verification. This compares ditto levels; it does not change electron-builder's release compressor.\n`)
