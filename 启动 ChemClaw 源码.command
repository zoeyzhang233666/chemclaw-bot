#!/bin/bash
set -euo pipefail

preview_dir="${CHEMCLAW_PREVIEW_DIR:-$HOME/Documents/Codex/ChemClaw-source-preview}"
app_node="/Applications/ChemClaw.app/Contents/Resources/primary-runtime/dependencies/node/bin"
export CHEMCLAW_PREVIEW_DIR="$preview_dir"
export PATH="$preview_dir/tools/bin:$HOME/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v node >/dev/null; then
  export PATH="$app_node:$PATH"
fi

keep_error_visible() {
  local status=$?
  if [[ "$status" -ne 0 && -t 0 && -t 1 ]]; then
    printf '\n启动失败。按回车键退出。\n' >&2
    read -r _ || true
  fi
}
trap keep_error_visible EXIT

if ! command -v node >/dev/null || ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) < 24 ? 1 : 0)'; then
  printf '需要 Node.js 24 或更新版本。请安装 Node.js 24 LTS，或将 ChemClaw 放在「应用程序」中。\n' >&2
  exit 1
fi

# The program is embedded so Finder and Terminal can run this file from any folder.
node --input-type=module - "$@" <<'JS'
import { execFileSync, spawn } from 'node:child_process'
import { createHash } from 'node:crypto'
import { closeSync, existsSync, mkdirSync, openSync, readFileSync, realpathSync, unlinkSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const repo = 'zoeyzhang233666/chemclaw-bot'
const remote = `https://github.com/${repo}.git`
const base = resolve(process.env.CHEMCLAW_PREVIEW_DIR)
const depot = join(base, 'repository.git')
const usage = '用法：启动 ChemClaw 源码.command [PR 编号 | latest | main] [--info | --sync-only]\n用 --list 查看开放的 PR。'
const args = process.argv.slice(2)
const flags = args.filter(arg => arg.startsWith('--'))
const selections = args.filter(arg => !arg.startsWith('--'))

function capture(command, argv, options = {}) {
  return execFileSync(command, argv, {
    encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 30_000, maxBuffer: 4 * 1024 ** 2, ...options,
  }).trim()
}

const git = (...args) => capture('git', [`--git-dir=${depot}`, ...args])
const inSource = (source, ...args) => capture('git', ['-C', source, ...args])

function openPulls() {
  let rows
  try {
    const raw = capture('gh', ['pr', 'list', '--repo', repo, '--state', 'open', '--limit', '100',
      '--json', 'number,title,headRefOid,isDraft'])
    rows = JSON.parse(raw).map(pr => ({ number: pr.number, title: pr.title, sha: pr.headRefOid, draft: pr.isDraft }))
  } catch {
    const url = `https://api.github.com/repos/${repo}/pulls?state=open&sort=created&direction=desc&per_page=100`
    try {
      const raw = capture('/usr/bin/curl', ['--fail', '--silent', '--show-error', '--max-time', '20', url])
      rows = JSON.parse(raw).map(pr => ({ number: pr.number, title: pr.title, sha: pr.head.sha, draft: pr.draft }))
    } catch {
      throw new Error('暂时无法获取 GitHub 的 PR 列表。请检查网络，或在终端传入已知的 PR 编号。')
    }
  }
  return rows.sort((a, b) => b.number - a.number)
}

function pick(pulls) {
  const options = [
    ...pulls.map(pr => ({ value: String(pr.number), label: `#${pr.number}  ${pr.title}  ·  ${pr.sha.slice(0, 8)}${pr.draft ? ' · 草稿' : ''}` })),
    { value: 'main', label: 'main · 在隔离目录预览' },
    { value: 'number', label: '输入其他 PR 编号…' },
  ]
  const chooser = `
function run(argv) {
  const app = Application.currentApplication()
  app.includeStandardAdditions = true
  const options = JSON.parse(argv[0])
  const first = options[0].label
  const list = app.chooseFromList(options.map(item => item.label), {
    withTitle: 'ChemClaw 源码启动器',
    withPrompt: '选择要从 GitHub 同步的 PR。每个 PR 有自己的测试数据。',
    defaultItems: [first],
  })
  if (!list) return ''
  const chosen = options.find(item => item.label === list[0]).value
  if (chosen !== 'number') return chosen
  try { return app.displayDialog('请输入 GitHub PR 编号', { defaultAnswer: '', withTitle: 'ChemClaw 源码启动器' }).textReturned.trim() }
  catch (error) { if (error.errorNumber === -128) return ''; throw error }
}`
  return capture('/usr/bin/osascript', ['-l', 'JavaScript', '-e', chooser, JSON.stringify(options)], { timeout: undefined })
}

function managedSource(path, head) {
  if (!existsSync(path)) {
    git('worktree', 'add', '--detach', path, head)
    return path
  }
  const common = inSource(path, 'rev-parse', '--path-format=absolute', '--git-common-dir')
  if (realpathSync(common) !== realpathSync(depot)
      || realpathSync(inSource(path, 'rev-parse', '--show-toplevel')) !== realpathSync(path)) {
    throw new Error(`该路径已被其他目录占用：${path}`)
  }
  const dirty = inSource(path, 'status', '--porcelain', '--untracked-files=normal') !== ''
  if (dirty || inSource(path, 'branch', '--show-current')) return undefined
  if (inSource(path, 'rev-parse', 'HEAD') !== head) inSource(path, 'switch', '--detach', '--no-overwrite-ignore', head)
  return path
}

function fetchSource(key, remoteRef) {
  if (!existsSync(depot)) capture('git', ['init', '--bare', depot])
  const localRef = `refs/chemclaw-preview/${key}`
  console.log(`正在同步 GitHub ${key} …`)
  capture('git', [`--git-dir=${depot}`, '-c', 'credential.interactive=never', 'fetch', '--no-tags',
    '--no-write-fetch-head', '--depth=1', remote, `+${remoteRef}:${localRef}`], { timeout: 180_000 })
  const head = git('rev-parse', '--verify', `${localRef}^{commit}`)
  const checkouts = join(base, 'checkouts')
  mkdirSync(checkouts, { recursive: true })
  let source = managedSource(join(checkouts, key), head)
  if (!source) {
    console.log('原预览检出有本地修改。正在打开单独的 GitHub 源码检出。')
    source = managedSource(join(checkouts, `${key}-${head.slice(0, 12)}`), head)
  }
  if (!source) throw new Error('对应工作树含本地修改。请先保存这些修改，再重新同步。')
  return { source, head }
}

function lock(key) {
  const path = join(base, `${key}.lock`)
  let fd
  try { fd = openSync(path, 'wx', 0o600) }
  catch (error) {
    if (error.code !== 'EEXIST') throw error
    const pid = Number(readFileSync(path, 'utf8'))
    if (!Number.isSafeInteger(pid) || pid < 2) throw new Error('此预览正在启动。请稍后重试。')
    try { process.kill(pid, 0) } catch (probe) {
      if (probe.code !== 'ESRCH') throw probe
      unlinkSync(path)
      return lock(key)
    }
    throw new Error('此预览正在运行。关闭它后，再同步并重启。')
  }
  try { writeFileSync(fd, String(process.pid)) } finally { closeSync(fd) }
  return () => unlinkSync(path)
}

async function run(command, argv, cwd, env = process.env) {
  const child = spawn(command, argv, { cwd, env, stdio: 'inherit' })
  const interrupt = () => child.kill('SIGINT')
  const terminate = () => child.kill('SIGTERM')
  process.once('SIGINT', interrupt)
  process.once('SIGTERM', terminate)
  try {
    await new Promise((done, fail) => {
      child.once('error', fail)
      child.once('exit', (code, signal) => {
        if (code === 0 || signal === 'SIGINT' || signal === 'SIGTERM') done()
        else fail(new Error(`${command} 退出（${code ?? signal}）。请查看上方错误。`))
      })
    })
  } finally {
    process.removeListener('SIGINT', interrupt)
    process.removeListener('SIGTERM', terminate)
  }
}

async function ensureDependencies(source, part, required) {
  const path = join(source, part)
  const fingerprint = createHash('sha256')
    .update(`${process.platform}:${process.arch}:${process.versions.modules}`)
    .update(readFileSync(join(path, 'package.json')))
    .update(readFileSync(join(path, 'package-lock.json')))
    .digest('hex')
  const stamp = join(path, 'node_modules', '.chemclaw-preview-lock')
  if (existsSync(stamp) && existsSync(join(path, 'node_modules', required))
      && readFileSync(stamp, 'utf8') === fingerprint) return

  console.log(`正在安装 ${part} 的锁定依赖 …`)
  await run('npm', ['ci', '--no-audit', '--no-fund'], path)
  if (!existsSync(join(path, 'node_modules', required))) throw new Error(`${part} 缺少 ${required}。`)
  writeFileSync(stamp, fingerprint)
}

async function main() {
  if (flags.includes('--help')) return console.log(usage)
  if (selections.length > 1 || flags.some(flag => !['--list', '--info', '--sync-only'].includes(flag))) throw new Error(usage)
  if (flags.includes('--list')) return console.log(JSON.stringify(openPulls(), null, 2))
  const requested = selections[0]
  const choice = requested === 'latest' ? String(openPulls()[0]?.number ?? '') : requested ?? pick(openPulls())
  if (!choice && !requested) return
  const number = /^(?:pr-|#)?([1-9]\d*)$/.exec(choice)?.[1]
  if (!number && choice !== 'main') throw new Error('没有选择可用的 PR。' + usage)
  const key = number ? `pr-${number}` : 'main'
  const remoteRef = number ? `refs/pull/${number}/head` : 'refs/heads/main'
  mkdirSync(base, { recursive: true })
  const unlock = lock(key)
  try {
    const { source, head } = fetchSource(key, remoteRef)
    const launcher = join(source, 'scripts', 'launch-chemclaw.mjs')
    if (!existsSync(launcher)) throw new Error('所选 GitHub 提交没有 ChemClaw 源码启动脚本。')
    const home = join(base, 'profiles', key)
    mkdirSync(join(home, '.chemclaw-dev'), { recursive: true })
    writeFileSync(join(home, '.chemclaw-dev', 'source.json'), JSON.stringify({
      source, profile: key, selection: number ? { kind: 'pr', number: Number(number), profile: key } : { kind: 'main', profile: key },
      remoteConfirmed: true,
      manifest: number ? { included: [{ number: Number(number), branch: 'GitHub PR', sha: head }] } : undefined,
    }))
    console.log(`GitHub ${key} @ ${head}\n源码：${source}\n测试数据：${home}`)
    if (!flags.includes('--info')) {
      try { capture('npm', ['--version']) }
      catch { throw new Error('找不到 npm。请安装包含 npm 的 Node.js 24 LTS。') }
      await ensureDependencies(source, 'chemclaw-bot', 'esbuild/package.json')
      await ensureDependencies(source, 'app', 'electron/package.json')
    }
    const env = { ...process.env, CHEMCLAW_LAUNCH_HOME: home, CHEMCLAW_NO_PICKER: '1' }
    await run(process.execPath, [launcher, '--source', source, '--no-picker', ...flags], source, env)
  } finally {
    unlock()
  }
}

try { await main() } catch (error) {
  console.error(error.stderr?.toString().trim() || error.message)
  process.exitCode = 1
}
JS
