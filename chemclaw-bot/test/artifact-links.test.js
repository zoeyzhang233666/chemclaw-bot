import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, readFile, rm, symlink, realpath } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { artifactPath, artifactReferences, linkArtifacts } from '../src/shared/artifact-links.js'
import { resolveArtifacts } from '../src/host/artifact-paths.js'
import { previewWorkbook } from './xlsx-fixture.js'

test('only explicit local links, inline filenames and exact table cells are resolved', () => {
  const text = '| 文件 | 大小 |\n|---|---|\n| 纯碱 成本.xlsx | 200 |\n`报告.html`\n[查看](<reports/报告.pdf#L2-L4>)\n[网站](https://example.com/x.html)\n```md\n| 不应链接.xlsx |\n```\n普通叙述 不是产物.xlsx'
  const refs = artifactReferences(text)
  assert.deepEqual(refs.map(ref => ref.value), ['纯碱 成本.xlsx', '报告.html', 'reports/报告.pdf#L2-L4'])
  const linked = linkArtifacts(text, refs, { '纯碱 成本.xlsx': 'D:\\work\\纯碱 成本.xlsx', '报告.html': '/work/报告.html', 'reports/报告.pdf#L2-L4': '/work/报告.pdf' })
  assert.match(linked, /\[纯碱 成本.xlsx\]\(<D:\/work\/%E7/)
  assert.match(linked, /%E6%8A%A5%E5%91%8A.pdf#L2-L4/)
  assert.match(linked, /https:\/\/example.com\/x.html/)
  assert.match(linked, /\| 不应链接.xlsx \|/)
  assert.equal(linkArtifacts(text, refs, {}), text)
})

test('Windows drive links and percent escapes normalize without accepting remote schemes', () => {
  assert.equal(artifactPath('/D:/work/%E6%8A%A5%E5%91%8A.xlsx'), 'D:/work/报告.xlsx')
  assert.equal(artifactPath('D:\\work\\报告.html'), 'D:/work/报告.html')
  for (const value of ['javascript:evil.html', 'https://example.com/a.xlsx', '//server/a.pdf', '%00.html', '%ZZ.html']) assert.equal(artifactPath(value), undefined)
})

async function bench(t) {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-artifact-links-'))
  t.after(() => rm(home, { recursive: true, force: true, maxRetries: 5 }))
  const team = join(home, 'team')
  const own = join(home, 'writer')
  const data = join(home, 'private-data')
  await Promise.all([team, own, data].map(path => mkdir(path)))
  const bot = { id: 'writer', workDir: own }
  const room = { id: 'room', members: ['writer'], sessions: { writer: 'member-session' } }
  const rt = {
    botOf: id => id === 'writer' ? bot : undefined,
    roomOf: id => id === 'room' ? room : undefined,
    selfOf: id => id === 'writer' ? 'writer' : undefined,
    teamFolder: () => team, defaultTeamFolder: () => team,
    inData: async path => path === data || path.startsWith(data + '/'),
    ctx: { sessionController: { inspect: async () => ({ meta: { cwd: own } }) } },
  }
  const call = values => resolveArtifacts(rt, { sessionId: 'room', botId: 'writer', values })
  return { home, team, own, data, rt, call }
}

test('a group resolves relative links against its author and finds nested delivery basenames', async t => {
  const { own, call } = await bench(t)
  await mkdir(join(own, '交付'))
  const html = join(own, '报告.html')
  const xlsx = join(own, '交付', '纯碱.xlsx')
  await Promise.all([html, xlsx].map(path => writeFile(path, 'test')))
  const { files } = await call(['报告.html', '纯碱.xlsx', '/wrong/报告.html'])
  // realpath may return the Windows 8.3 form; compare the resolved paths.
  assert.equal(files['报告.html'], await realpath(html))
  assert.equal(files['纯碱.xlsx'], await realpath(xlsx))
  assert.equal(files['/wrong/报告.html'], await realpath(html))
})

test('ambiguous basenames, deleted files and traversal do not receive links', async t => {
  const { own, team, call } = await bench(t)
  await Promise.all([own, team].map(async root => { await mkdir(join(root, 'out')); await writeFile(join(root, 'out', '报告.pdf'), 'test') }))
  const { files } = await call(['报告.pdf', '已删除.xlsx', '../missing/报告.pdf'])
  assert.deepEqual(Object.keys(files), [])
})

test('resolving exact and nested workbook links preserves every original byte', async t => {
  const { own, call } = await bench(t)
  await mkdir(join(own, 'reports'))
  const path = join(own, 'reports', 'original.xlsx')
  const original = await previewWorkbook()
  await writeFile(path, original)
  for (const value of ['reports/original.xlsx', 'original.xlsx']) {
    assert.equal((await call([value])).files[value], await realpath(path))
    assert.deepEqual(await readFile(path), original)
  }
})

test('files outside known workspaces and private data are never returned', async t => {
  const { home, own, data, call } = await bench(t)
  const outside = join(home, 'outside.html')
  const secret = join(data, 'private.pdf')
  await Promise.all([outside, secret].map(path => writeFile(path, 'test')))
  if (process.platform !== 'win32') await symlink(data, join(own, 'linked-data'))
  assert.deepEqual(Object.keys((await call([outside, secret, 'private.pdf'])).files), [])
})

test('an incomplete scan cannot claim a basename is unique', async t => {
  const { own, call } = await bench(t)
  await writeFile(join(own, 'exists.html'), 'test')
  await mkdir(join(own, ...Array(8).fill('deep')), { recursive: true })
  const result = await call(['/wrong/exists.html'])
  assert.equal(result.truncated, true)
  assert.deepEqual(Object.keys(result.files), [])
})

test('unknown members, too many requests and cancelled scans are refused', async t => {
  const { rt } = await bench(t)
  await assert.rejects(resolveArtifacts(rt, { sessionId: 'room', botId: 'other', values: ['a.pdf'] }), /Unknown member/)
  await assert.rejects(resolveArtifacts(rt, { sessionId: 'room', values: Array(41).fill('a.pdf') }), /40/)
  await assert.rejects(resolveArtifacts(rt, { sessionId: 'room', botId: 'writer', values: ['a.pdf'] }, AbortSignal.abort()), { name: 'AbortError' })
})
