// Compare two Windows builds from the same GitHub PR base/head under the same runner.
// Installer bytes, extracted distribution bytes and actual installed directory bytes
// are separate metrics. Market archive bytes must NOT be called installed bytes.
import assert from 'node:assert/strict'
import { appendFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { runtimeSizeReport, sizeOf } from './audit-runtime-size.mjs'

const mib = bytes => bytes == null ? 'n/a' : (bytes / 1048576).toFixed(2) + ' MiB'
const fields = [
  ['installerBytes', 'Windows NSIS installer (compressed)'],
  ['installedBytes', 'Windows installed files (logical bytes)'],
  ['unpackedAppBytes', 'Windows unpacked app (logical bytes)'],
  ['officePythonBytes', 'Office Python (unpacked)'],
  ['marketArchiveBytes', 'AKShare Python archive (compressed)'],
  ['marketUnpackedBytes', 'AKShare Python (unpacked, from manifest)'],
  ['officeNodeBytes', 'Office Node (unpacked)'],
  ['officeSkillsBytes', 'Office skills (unpacked)'],
  ['officeTotalBytes', 'Office complete runtime (unpacked)'],
]

export function snapshot(appDir, installedBytes = null) {
  const app = resolve(appDir)
  const data = runtimeSizeReport({ app, platform: 'win32', arch: 'x64' })
  const installers = data.installer?.filter(file => file.name.toLowerCase().endsWith('.exe')) ?? []
  assert.equal(installers.length, 1, 'expected exactly one Windows NSIS installer in ' + app)
  const unpackedAppBytes = sizeOf(join(app, 'dist-pack', 'win-unpacked'))
  assert.ok(unpackedAppBytes > 0, 'missing extracted Windows build ' + app)
  assert.ok(data.officePythonBytes > 0 && data.officeNodeBytes > 0 && data.marketArchiveBytes > 0,
    'both complete offline runtimes must be present')
  return {
    installerBytes: installers[0].bytes,
    installedBytes,
    unpackedAppBytes,
    officePythonBytes: data.officePythonBytes,
    marketArchiveBytes: data.marketArchiveBytes,
    marketUnpackedBytes: data.marketUnpackedBytes,
    officeNodeBytes: data.officeNodeBytes,
    officeSkillsBytes: sizeOf(join(app, 'build', 'runtime', 'office-skills')),
    officeTotalBytes: data.officeTotalBytes,
  }
}

export function compare(baseline, optimized) {
  const same = ['officePythonBytes', 'officeNodeBytes', 'officeSkillsBytes', 'officeTotalBytes']
  for (const field of same) assert.equal(optimized[field], baseline[field], field + ' changed despite packaging-only optimization')
  assert.equal(optimized.marketUnpackedBytes, baseline.marketUnpackedBytes, 'AKShare unpacked footprint unexpectedly changed')
  assert.ok(optimized.installerBytes < baseline.installerBytes,
    'optimized NSIS installer must be smaller on the same runner; investigate packaging patterns')
  assert.ok(optimized.unpackedAppBytes < baseline.unpackedAppBytes,
    'optimized unpacked app must shrink, otherwise resources were not removed')
  return Object.fromEntries(fields.map(([key]) => [key,
    baseline[key] == null || optimized[key] == null ? null : baseline[key] - optimized[key]]))
}

function summary(baseline, optimized, savings) {
  const rows = fields.map(([key, label]) =>
    '| ' + label + ' | ' + mib(baseline[key]) + ' | ' + mib(optimized[key]) + ' | ' +
    (savings[key] == null ? 'n/a' : mib(savings[key])) + ' |')
  return [
    '### ChemClaw same-runner, same-source-base Windows A/B size comparison',
    'Both GitHub checkouts use identical Node/toolchain and lockfiles; the optimized checkout differs only by the PR.',
    '| Metric | Baseline (PR base) | Optimized (PR head) | Saved |',
    '|---|---:|---:|---:|',
    ...rows,
    '',
    'Installed bytes sum file lengths in the real silent installation directory. They are not NTFS allocation-on-disk measurements.',
    'AKShare archive bytes and manifest unpacked bytes are distinct; market data runtime is not removed.',
    'An actual installed directory may contain NSIS-generated uninstaller entries absent from win-unpacked.',
  ].join('\n') + '\n'
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [baseDir, optimizedDir, installedFile] = process.argv.slice(2)
  if (!baseDir || !optimizedDir) throw new Error('Usage: node compare-runtime-size.mjs <baseline-app> <optimized-app> [installed-size.json]')
  const actual = installedFile && existsSync(installedFile) ? JSON.parse(readFileSync(installedFile, 'utf8')) : {}
  const a = snapshot(baseDir, actual.baseline ?? null)
  const b = snapshot(optimizedDir, actual.optimized ?? null)
  const savings = compare(a, b)
  const data = { baseline: a, optimized: b, savings }
  writeFileSync('installer-size-ab-results.json', JSON.stringify(data, null, 2) + '\n')
  const message = summary(a, b, savings)
  console.log(message)
  if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, message)
}
