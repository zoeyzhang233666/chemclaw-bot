import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { copyFileSync, existsSync, lstatSync, mkdirSync, readlinkSync, writeFileSync } from 'node:fs'
import { isAbsolute, join, relative, resolve } from 'node:path'
import { randomUUID } from 'node:crypto'
import { setTimeout as sleep } from 'node:timers/promises'

const [image, output, extractedApp] = process.argv.slice(2).map(value => resolve(value))
assert.equal(process.platform, 'darwin', 'Native macOS only')
assert.ok(process.env.RUNNER_TEMP, 'GitHub temporary runner directory is required')
const owned = path => {
  const part = relative(resolve(process.env.RUNNER_TEMP), path)
  assert.ok(part && part !== '..' && !part.startsWith('../') && !isAbsolute(part), 'All mutations must stay inside RUNNER_TEMP')
  return path
}
owned(output)
owned(extractedApp)
assert.ok(image.endsWith('.dmg') && extractedApp.endsWith('.app'))
assert.ok(!existsSync(output), 'Do not reuse an evidence directory')
mkdirSync(output, { recursive: true })
const report = { nativeMountAndStructurePassed: false, realBrowserDownload: false, warningFreeInstallVerified: false,
  installedIntoApplications: false, finderLayoutReviewed: false, priorUnquarantinedBaseline: true, operations: [] }
const command = (file, args, required = true) => {
  const result = spawnSync(file, args, { encoding: 'utf8', timeout: 120_000 })
  const entry = { file, args, status: result.status, error: result.error?.message ?? null,
    stdout: result.stdout ?? '', stderr: result.stderr ?? '' }
  report.operations.push(entry)
  if (required && (result.error || result.status !== 0)) throw new Error(file + ' failed: ' + (result.error?.message ?? result.status))
  return entry
}
const copy = join(output, 'ChemClaw-layout-preview.dmg')
const mount = join(output, 'mount')
let attached = false
try {
  copyFileSync(image, owned(copy))
  mkdirSync(owned(mount))
  try {
    command('/usr/bin/hdiutil', ['attach', '-readonly', '-nobrowse', '-mountpoint', mount, copy])
    attached = true
    const app = join(mount, 'ChemClaw.app'), link = join(mount, 'Applications')
    assert.ok(lstatSync(app).isDirectory())
    assert.ok(lstatSync(link).isSymbolicLink())
    assert.equal(readlinkSync(link), '/Applications')
    assert.ok(existsSync(join(mount, '.DS_Store')), 'Finder layout metadata is missing')
    command('/usr/bin/codesign', ['--verify', '--deep', '--strict', app])
    command('/usr/bin/codesign', ['--display', '--verbose=4', app])
    const finder = command('/usr/bin/osascript', ['-e', 'on run argv\ntell application "Finder"\nopen (POSIX file (item 1 of argv) as alias)\nactivate\nend tell\nend run', mount], false)
    if (finder.status === 0 && !finder.error) {
      await sleep(1500)
      const shot = command('/usr/sbin/screencapture', ['-x', join(output, 'finder-layout.png')], false)
      report.finderScreenshotAvailable = shot.status === 0 && !shot.error
    } else report.finderScreenshotAvailable = false
    report.nativeMountAndStructurePassed = true
  } finally {
    if (attached) command('/usr/bin/hdiutil', ['detach', mount])
  }
  // Simulate quarantine only on owned copies, keeping the original artifacts unchanged.
  // This assessment is not an actual Safari download or first-launch acceptance test.
  const quarantine = '0083;' + Math.floor(Date.now() / 1000).toString(16) + ';ChemClawAudit;' + randomUUID()
  for (const [file, args] of [[copy, ['--assess', '--type', 'open', '--context', 'context:primary-signature', '--verbose=4']],
    [extractedApp, ['--assess', '--type', 'execute', '--verbose=4']]]) {
    command('/usr/bin/xattr', ['-w', 'com.apple.quarantine', quarantine, owned(file)])
    command('/usr/bin/xattr', ['-p', 'com.apple.quarantine', file])
    const assessment = command('/usr/sbin/spctl', [...args, file], false)
    const key = file.endsWith('.dmg') ? 'quarantinedDmgAssessment' : 'quarantinedAppAssessment'
    report[key] = { status: assessment.status, error: assessment.error, output: assessment.stdout + assessment.stderr }
  }
} catch (error) { report.error = error.message; process.exitCode = 1 }
finally { writeFileSync(join(output, 'summary.json'), JSON.stringify(report, null, 2) + '\n') }
console.log(JSON.stringify({ nativeMountAndStructurePassed: report.nativeMountAndStructurePassed, warningFreeInstallVerified: false, error: report.error ?? null }))
