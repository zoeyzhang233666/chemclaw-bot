import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { createReadStream, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { isAbsolute, join, relative, resolve } from 'node:path'

const [mode, argument] = process.argv.slice(2)
const repo = process.env.GH_REPO
const tag = process.env.RELEASE_TAG ?? 'v0.3.1'
assert.equal(repo, 'zoeyzhang233666/chemclaw-bot')
assert.match(tag, /^v\d+\.\d+\.\d+$/)
assert.ok(process.env.RUNNER_TEMP, 'Use an isolated Actions runner')
const temporary = resolve(process.env.RUNNER_TEMP)
const owned = path => {
  const part = relative(temporary, path)
  assert.ok(part && part !== '..' && !part.startsWith('../') && !isAbsolute(part), 'Temporary output escaped RUNNER_TEMP')
  return path
}
const command = (file, args, options = {}) => execFileSync(file, args, { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024, ...options })
const api = path => JSON.parse(command('gh', ['api', 'repos/' + repo + '/' + path]))
const release = () => {
  const value = api('releases/tags/' + tag)
  assert.equal(value.tag_name, tag)
  assert.equal(value.draft, false)
  assert.equal(value.prerelease, false)
  return value
}
const digest = async path => {
  const hash = createHash('sha256')
  for await (const chunk of createReadStream(path)) hash.update(chunk)
  return 'sha256:' + hash.digest('hex')
}
const snapshot = assets => assets.map(({ id, name, digest }) => ({ id, name, digest })).sort((a, b) => a.name.localeCompare(b.name))
const unchanged = (assets, baseline) => {
  for (const original of baseline) assert.deepEqual(snapshot(assets).find(asset => asset.id === original.id), original, 'An existing release asset changed')
}
const root = owned(resolve(temporary, 'mac-dmg-supplement'))

if (mode === 'build') {
  assert.equal(process.platform, 'darwin')
  assert.ok(['arm64', 'x64'].includes(argument))
  assert.equal(process.arch, argument)
  assert.ok(!existsSync(root), 'Use fresh temporary output')
  mkdirSync(root)
  const version = tag.slice(1)
  const sourceCommit = command('git', ['rev-parse', tag + '^{}']).trim()
  command('git', ['merge-base', '--is-ancestor', sourceCommit, 'origin/main'])
  const baseline = release()
  const zipName = 'ChemClaw-' + version + '-mac-' + argument + '.zip'
  const asset = baseline.assets.find(asset => asset.name === zipName)
  assert.match(asset?.digest ?? '', /^sha256:[a-f0-9]{64}$/)
  command('gh', ['release', 'download', tag, '--repo', repo, '--pattern', zipName, '--dir', root], { stdio: 'inherit' })
  const zip = join(root, zipName)
  assert.equal(await digest(zip), asset.digest, 'The downloaded ZIP differs from the published asset')
  const extracted = owned(join(root, 'input'))
  mkdirSync(extracted)
  command('/usr/bin/ditto', ['-x', '-k', zip, extracted])
  const app = join(extracted, 'ChemClaw.app')
  command('/usr/bin/codesign', ['--verify', '--deep', '--strict', app], { stdio: 'inherit' })
  assert.equal(command('/usr/libexec/PlistBuddy', ['-c', 'Print :CFBundleShortVersionString', join(app, 'Contents', 'Info.plist')]).trim(), version)
  assert.equal(command('/usr/bin/lipo', ['-archs', join(app, 'Contents', 'MacOS', 'ChemClaw')]).trim(), argument === 'x64' ? 'x86_64' : 'arm64')
  const require = createRequire(new URL('../../app/package.json', import.meta.url))
  const asar = require('@electron/asar')
  const archive = join(app, 'Contents', 'Resources', 'app.asar')
  const paths = ['main.mjs', 'app-path.mjs', 'mac-install.mjs', 'bot-views.mjs', 'host-process.mjs', 'renderer-recovery.mjs', 'updates.mjs']
  for (const name of paths) {
    const expected = execFileSync('git', ['show', tag + ':app/src/' + name])
    assert.deepEqual(asar.extractFile(archive, 'src/' + name), expected, 'Packaged source differs from ' + tag + ': ' + name)
  }
  assert.equal(JSON.parse(asar.extractFile(archive, 'package.json')).version, version)
  const output = owned(join(root, 'output'))
  command(process.execPath, [resolve('app/node_modules/electron-builder/out/cli/cli.js'), '--mac', 'dmg', '--' + argument,
    '--prepackaged', app, '--config', 'electron-builder.mac-dmg.yml', '--config.extraMetadata.version=' + version,
    '--config.directories.output=' + output, '--publish', 'never'], { cwd: resolve('app'), stdio: 'inherit' })
  const dmgName = 'ChemClaw-' + version + '-mac-' + argument + '.dmg'
  const dmg = join(output, dmgName)
  assert.ok(existsSync(dmg))
  command(process.execPath, ['.github/scripts/check-macos-dmg-layout.mjs', dmg, join(root, 'check'), app], { stdio: 'inherit' })
  const check = JSON.parse(readFileSync(join(root, 'check', 'summary.json')))
  assert.equal(check.nativeMountAndStructurePassed, true)
  assert.equal(check.appContentsMatch, true)
  assert.equal(check.finderScreenshotAvailable, true, 'Record the actual Finder installation window')
  const input = { tag, sourceCommit, toolingCommit: process.env.GITHUB_SHA, arch: argument,
    originalAssets: snapshot(baseline.assets), zip: { name: zipName, digest: asset.digest },
    dmg: { name: dmgName, digest: await digest(dmg) }, appContents: check.appContents }
  writeFileSync(join(root, 'input.json'), JSON.stringify(input, null, 2) + '\n')
  console.log(JSON.stringify(input))
} else if (mode === 'publish') {
  assert.equal(process.env.GITHUB_REF, 'refs/heads/main', 'Publish supplementary assets from main')
  const inputs = owned(resolve(argument))
  const records = ['arm64', 'x64'].map(arch => {
    const directory = join(inputs, arch)
    const input = JSON.parse(readFileSync(join(directory, 'input.json')))
    const check = JSON.parse(readFileSync(join(directory, 'check', 'summary.json')))
    assert.equal(input.tag, tag)
    assert.equal(input.arch, arch)
    assert.equal(check.nativeMountAndStructurePassed, true)
    assert.equal(check.appContentsMatch, true)
    return { directory, input }
  })
  assert.equal(records[0].input.sourceCommit, records[1].input.sourceCommit)
  assert.equal(api('commits/' + tag).sha, records[0].input.sourceCommit, 'The release tag moved')
  assert.deepEqual(records[0].input.originalAssets, records[1].input.originalAssets)
  const before = release()
  unchanged(before.assets, records[0].input.originalAssets)
  const files = []
  for (const { directory, input } of records) {
    assert.ok(!before.assets.some(asset => asset.name === input.dmg.name), 'A DMG already exists; do not overwrite it')
    const path = owned(join(directory, 'output', input.dmg.name))
    assert.equal(await digest(path), input.dmg.digest)
    files.push(path)
  }
  // Existing assets are immutable here; no --clobber and no tag or product rebuild.
  command('gh', ['release', 'upload', tag, '--repo', repo, ...files], { stdio: 'inherit' })
  const after = release()
  unchanged(after.assets, records[0].input.originalAssets)
  for (const { input } of records) assert.equal(after.assets.find(asset => asset.name === input.dmg.name)?.digest, input.dmg.digest)
  const marker = '<!-- chemclaw-mac-dmg-supplement -->'
  if (!(after.body ?? '').includes(marker)) {
    const currentNotes = (after.body ?? '').replace('标准正式包保留 ZIP；DMG 拖拽窗口目前仍是可选预览。', 'DMG 提供 Finder 拖拽安装窗口，ZIP 作为备用下载保留。')
    const notes = currentNotes + '\n\n' + marker + '\n## macOS 拖拽安装包补充\n\n'
      + '- Apple 芯片请选择 ChemClaw-' + tag.slice(1) + '-mac-arm64.dmg；Intel 请选择对应的 mac-x64.dmg。\n'
      + '- 打开 DMG 后，先完全退出旧版，将 ChemClaw 拖到窗口中的 Applications 图标，再从“应用程序”打开。\n'
      + '- DMG 内应用与现有 ZIP 逐文件内容一致，正式源码标签未变；ZIP 继续保留作为备用下载。\n'
      + '- 仍使用临时签名，首次打开可能需要系统对本应用放行。\n'
    const path = owned(join(inputs, 'release-notes.md'))
    writeFileSync(path, notes)
    command('gh', ['release', 'edit', tag, '--repo', repo, '--notes-file', path], { stdio: 'inherit' })
  }
  mkdirSync(root, { recursive: true })
  writeFileSync(join(root, 'published.json'), JSON.stringify({ tag, sourceCommit: records[0].input.sourceCommit,
    existingAssetsUnchanged: true, assets: snapshot(after.assets) }, null, 2) + '\n')
  console.log(JSON.stringify({ tag, sourceCommit: records[0].input.sourceCommit, existingAssetsUnchanged: true, added: files.length }))
} else throw new Error('Use build <arch> or publish <download-directory>')
