// The source picker can execute an older entry launcher's JS while loading
// this PR's desktop app. Therefore prepare the pinned Office runtime in the
// selected Electron parent as well, before booting the DSH Host. No changes to
// Windows ACLs, system Python or the DSH sandbox are needed.
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
// Do not import build-time packages here: packaged Electron omits devDependencies.

export async function ensureOfficePreviewRuntime({
  packaged = false,
  profile = process.env.CHEMCLAW_PROFILE_KEY,
  appDir,
  platform = process.platform,
  arch = process.arch,
  prepare,
  reusable,
  fileExists = existsSync,
  run = spawnSync,
} = {}) {
  if (packaged || !/^(?:pr-\d+|integration|worktree-[\w.-]+)$/.test(profile || '')) return { status: 'skipped' }
  if (!appDir) throw new Error('Office preview requires the selected application directory')
  // This JS file is shipped in the EXE, but scripts/ and its build-time npm
  // dependencies are not. The import must happen only for a source PR preview.
  const runtime = await import('../scripts/prepare-runtime.mjs')
  prepare ??= runtime.preparePrimaryRuntime
  reusable ??= runtime.runtimeReusable
  const { primaryRuntimeManifest, runtimeTarget } = runtime
  const target = runtimeTarget(platform, arch)
  if (!target) throw new Error('Unsupported Office runtime platform: ' + platform + '/' + arch)
  const pkg = JSON.parse(readFileSync(join(appDir, 'package.json'), 'utf8'))
  if (typeof pkg.scripts?.runtime !== 'string') return { status: 'skipped' }
  const output = join(appDir, 'build', 'runtime')
  const payload = join(output, 'primary-runtime')
  const manifest = primaryRuntimeManifest(target, pkg.version)
  const assets = join(output, 'office-skills', 'office', 'SKILL.md')
  const ready = () => reusable(output, manifest) && fileExists(assets)
  if (!ready()) {
    console.info('ChemClaw: preparing the Office Python/Node runtime for this preview before DSH starts.')
    await prepare({
      target, output, cache: process.env.CHEMCLAW_OFFICE_RUNTIME_CACHE ?? join(appDir, 'build', 'runtime-cache'),
      version: pkg.version,
    })
    if (!ready()) throw new Error('Office preview runtime was not complete after preparation.')
  }
  const python = join(payload, 'dependencies', 'python', ...(platform === 'win32' ? ['python.exe'] : ['bin', 'python3']))
  const node = join(payload, 'dependencies', 'node', 'bin', platform === 'win32' ? 'node.exe' : 'node')
  // In particular, do not accidentally test system Python 3.14 on the user's PATH.
  for (const [binary, args] of [
    [node, ['--version']],
    [python, ['-I', '-B', '-c', 'import docx, pptx, openpyxl; print("OFFICE_READY")']],
  ]) {
    const result = run(binary, args, { encoding: 'utf8', timeout: 30000, windowsHide: true })
    if (result.error || result.status !== 0) {
      throw new Error('Office preview interpreter is unusable: ' + binary + ': ' +
        String(result.stderr || result.error?.message || 'nonzero exit').slice(0, 1000))
    }
  }
  console.info('ChemClaw: Office preview runtime verified (standalone Node + Python with docx/pptx/openpyxl).')
  return { status: 'ready', node, python, output }
}
