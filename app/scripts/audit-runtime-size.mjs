// Read-only distribution size audit. The AKShare archive (packed into app.asar)
// and the DSH Office standalone runtime both carry Python 3.12 today.
// Report the actual build sizes rather than guessing compression savings.
import { appendFileSync, existsSync, lstatSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export function sizeOf(path) {
  if (!existsSync(path)) return null
  const s = lstatSync(path)
  if (s.isSymbolicLink()) return 0
  if (s.isFile()) return s.size
  if (!s.isDirectory()) return 0
  return readdirSync(path).reduce((sum, child) => sum + (sizeOf(join(path, child)) || 0), 0)
}

export function runtimeSizeReport({
  app = resolve(fileURLToPath(new URL('..', import.meta.url))),
  platform = process.platform,
  arch = process.arch,
} = {}) {
  const office = join(app, 'build', 'runtime', 'primary-runtime', 'dependencies')
  const market = join(app, 'node_modules', 'chemclaw-bot', 'runtime', 'bundled')
  const name = platform + '-' + arch
  const marketArchive = join(market, name + '.tar.gz')
  let manifest
  try { manifest = JSON.parse(readFileSync(join(market, name + '.json'), 'utf8')) } catch { manifest = null }
  const installerDir = join(app, 'dist-pack')
  let installer = null
  if (existsSync(installerDir)) {
    const files = readdirSync(installerDir).filter(s => s.toLowerCase().startsWith('chemclaw-') &&
      /\.(?:exe|deb|appimage|zip)$/i.test(s))
    installer = files.map(name => ({ name, bytes: statSync(join(installerDir, name)).size }))
  }
  return {
    platform, arch,
    officePythonBytes: sizeOf(join(office, 'python')),
    officeNodeBytes: sizeOf(join(office, 'node')),
    officeTotalBytes: sizeOf(join(app, 'build', 'runtime', 'primary-runtime')),
    marketArchiveBytes: sizeOf(marketArchive),
    marketUnpackedBytes: manifest?.unpackedBytes ?? null,
    marketPythonVersion: manifest?.python || null,
    installer,
    // Report overlap only. Merging is unsafe without testing AKShare's own
    // pandas version alongside the locked Office pandas version.
    duplicatePythonDistributions: Boolean(sizeOf(join(office, 'python')) && sizeOf(marketArchive)),
  }
}

function fmt(bytes) { return bytes == null ? 'n/a' : (bytes / 1048576).toFixed(1) + ' MiB' }
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const report = runtimeSizeReport()
  console.log('runtime-size-audit: ' + JSON.stringify(report))
  const lines = [
    '### ChemClaw Office + AKShare runtime size audit',
    '| Component | Size |', '|---|---:|',
    '| Bundled Office Python (unpacked) | ' + fmt(report.officePythonBytes) + ' |',
    '| Bundled Office Node (unpacked) | ' + fmt(report.officeNodeBytes) + ' |',
    '| Office runtime total (unpacked) | ' + fmt(report.officeTotalBytes) + ' |',
    '| AKShare market Python archive (compressed) | ' + fmt(report.marketArchiveBytes) + ' |',
    '| AKShare market environment (unpacked) | ' + fmt(report.marketUnpackedBytes) + ' |',
    ...(report.installer || []).map(f => '| Installer ' + f.name + ' | ' + fmt(f.bytes) + ' |'),
    '',
    report.duplicatePythonDistributions
      ? '**Release gate:** two Python distributions detected. Do not remove either without AKShare regression coverage.'
      : '**Caution:** an absent runtime measurement is not proof that a duplicate was removed.',
  ]
  if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, lines.join('\n') + '\n')
  console.log(lines.join('\n'))
}
