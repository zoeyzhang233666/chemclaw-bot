import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { zipSync, strToU8 } from 'fflate'
import { createRuntime } from './legacy-runtime.js'
import { fakeContext } from './fake-ctx.js'
import { githubSkills, identifySkills, unpackSkills } from '../src/host/skill-import.js'
import { managedSkillPath, parseSkill, safeSkillPath } from '../src/host/skill-files.js'
import { parseServiceDraft } from '../src/host/service-install.js'
import { skillEmoji, skillExample } from '../src/shared/skill-presentation.js'

const content = (name = 'example') => `---\nname: ${name}\ndescription: A complete skill\n---\nRead references/data.csv and scripts/run.py.\n`
const archive = () => zipSync({ 'bundle/示例/SKILL.md': strToU8(content()), 'bundle/示例/references/data.csv': strToU8('中文,123\n'), 'bundle/示例/scripts/run.py': strToU8('raise RuntimeError("never run at install")\n'), 'bundle/second/SKILL.md': strToU8(content('second')) })
async function fixture(t) {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-skills-'))
  const ctx = fakeContext()
  const rt = createRuntime(ctx, { home, github: false, diagnosticsFile: false })
  await rt.load()
  t.after(async () => { await ctx.dispose(); await rm(home, { recursive: true, force: true, maxRetries: 5 }) })
  return { rt, home }
}

test('ZIP identifies multiple nested skills and retains binary and Chinese resources', () => {
  const entries = unpackSkills(archive())
  const skills = identifySkills(entries)
  assert.equal(skills.length, 2)
  assert.equal(skills[0].name, 'example')
  assert.equal(skills[0].files, 3)
  assert.equal(entries.find(item => item.path.endsWith('data.csv')).data.toString(), '中文,123\n')
  const binary = Buffer.from([0, 255, 1, 128])
  const unpacked = unpackSkills(zipSync({ 'SKILL.md': strToU8(content()), 'assets/template.bin': binary }))
  assert.deepEqual(unpacked.find(item => item.path.endsWith('.bin')).data, binary)
})

test('archives reject traversal, Windows collisions, symlinks, encryption and oversized declarations', () => {
  for (const path of ['../escape', '/absolute', 'C:/escape', 'safe/../escape', 'NUL.txt', 'bad./x', 'safe//x']) assert.throws(() => safeSkillPath(path), /Unsafe/)
  assert.throws(() => unpackSkills(Buffer.from('invalid')), /Invalid ZIP/)
  assert.throws(() => unpackSkills(zipSync({ '../escape': strToU8('x') })), /Unsafe/)
  assert.throws(() => unpackSkills(zipSync({ 'SKILL.md': strToU8(content()), 'skill.MD': strToU8(content()) })), /Duplicate/)
  const mutate = update => {
    const bytes = Buffer.from(archive())
    const central = bytes.indexOf(Buffer.from([0x50, 0x4b, 0x01, 0x02]))
    update(bytes, central)
    return bytes
  }
  assert.throws(() => unpackSkills(mutate((bytes, at) => bytes.writeUInt32LE(0xa1ff0000, at + 38))), /links/)
  assert.throws(() => unpackSkills(mutate((bytes, at) => bytes.writeUInt16LE(1, at + 8))), /Encrypted/)
  assert.throws(() => unpackSkills(mutate((bytes, at) => bytes.writeUInt32LE(600 * 1024 * 1024, at + 24))), /500 MB/)
})

test('frontmatter preserves original names and invocation restrictions; invalid metadata is per-skill', () => {
  const parsed = parseSkill(content('中文技能'))
  assert.match(parsed.name, /^skill-[a-f0-9]+$/)
  assert.equal(parsed.originalName, '中文技能')
  assert.deepEqual(parseSkill('---\nname: limited\ndescription: Test\nuser-invocable: false\ndisable-model-invocation: true\n---\nBody').invocation, { userInvocable: false, modelInvocable: false })
  assert.throws(() => parseSkill('---\nname: limited\nuser-invocable: maybe\n---\nBody'), /Invalid user-invocable/)
  const invalid = identifySkills([{ path: 'broken/SKILL.md', data: Buffer.from('---\nname: [broken\n---\nBody') }, { path: 'valid/SKILL.md', data: Buffer.from(content()) }])
  assert.equal(invalid[0].valid, false)
  assert.equal(invalid[1].valid, true)
})

test('installation previews, skips conflicts, replaces atomically, keeps resources and uninstalls bindings', async t => {
  const { rt, home } = await fixture(t)
  const preview = await rt.skillImportEndpoint('skill-import-preview', { archive: Buffer.from(archive()).toString('base64') })
  assert.equal(rt.state.capabilities.items.example, undefined)
  const result = await rt.skillImportEndpoint('skill-import-commit', { token: preview.token, selections: [{ key: '0', displayName: '示例分析', purpose: '处理用户数据', category: '内贸销售' }] })
  assert.deepEqual(result.installed, ['example'])
  const item = rt.state.capabilities.items.example
  const root = managedSkillPath(home, item.directory)
  assert.equal(await readFile(join(root, 'references/data.csv'), 'utf8'), '中文,123\n')
  assert.match(await readFile(join(root, 'scripts/run.py'), 'utf8'), /never run/)
  assert.equal(item.displayName, '示例分析')
  assert.equal(item.category, '内贸销售')
  assert.equal(rt.capabilityLibraryView().find(item => item.name === 'example').content, undefined)
  assert.equal(rt.capabilityLibraryView().find(item => item.name === 'example').directory, undefined)
  assert.equal((await rt.skillDefinition('example')).resourceBase.path, root)
  const duplicate = await rt.skillImportEndpoint('skill-import-preview', { archive: Buffer.from(archive()).toString('base64') })
  assert.equal(duplicate.candidates[0].exists, true)
  assert.deepEqual((await rt.skillImportEndpoint('skill-import-commit', { token: duplicate.token, selections: [{ key: '0' }] })).skipped, ['example'])
  const retry = await rt.skillImportEndpoint('skill-import-preview', { files: [{ path: 'SKILL.md', data: Buffer.from(content()).toString('base64') }] })
  const save = rt.save
  rt.save = async () => { throw new Error('simulated disk error') }
  await assert.rejects(rt.skillImportEndpoint('skill-import-commit', { token: retry.token, selections: [{ key: '0', conflict: 'replace' }] }), /simulated disk/)
  assert.equal(rt.state.capabilities.items.example, item)
  assert.equal(await readFile(join(root, 'references/data.csv'), 'utf8'), '中文,123\n')
  rt.save = save
  await rt.skillImportEndpoint('skill-import-commit', { token: retry.token, selections: [{ key: '0', conflict: 'replace', displayName: '更新技能' }] })
  assert.equal(rt.state.capabilities.items.example.displayName, '更新技能')
  rt.state.bots.worker = { id: 'worker', name: 'Worker', capabilities: ['example'] }
  await rt.capabilityDelete('example', { ui: true })
  assert.deepEqual(rt.state.bots.worker.capabilities, [])
  assert.ok(rt.state.removedSkills.includes('example'))
})

test('GitHub repository, branch with slashes, directory and SKILL.md links retain sibling resources', async () => {
  const bytes = zipSync({ 'repo-sha/skills/example/SKILL.md': strToU8(content()), 'repo-sha/skills/example/scripts/run.py': strToU8('pass'), 'repo-sha/other/SKILL.md': strToU8(content('other')) })
  const request = async url => {
    if (url.includes('codeload.github.com')) return new Response(bytes)
    if (url.endsWith('/commits/feature%2Fwork')) return Response.json({ sha: 'resolved-sha' })
    if (url.includes('/commits/')) return new Response('', { status: 404 })
    return Response.json({ private: false, default_branch: 'main' })
  }
  const repo = await githubSkills('https://github.com/owner/repo', { request })
  assert.equal(identifySkills(repo.entries).length, 2)
  for (const url of ['https://github.com/owner/repo/tree/feature/work/skills/example', 'https://github.com/owner/repo/blob/feature/work/skills/example/SKILL.md']) {
    const result = await githubSkills(url, { request })
    assert.deepEqual(result.entries.map(item => item.path), ['SKILL.md', 'scripts/run.py'])
    assert.equal(result.source.revision, 'resolved-sha')
  }
  for (const url of ['https://github.com.evil.test/o/r', 'http://github.com/o/r', 'https://user:pass@github.com/o/r']) await assert.rejects(githubSkills(url, { request }), /public/)
})

test('manual emoji choices survive edits and reload, while invalid input leaves the saved skill intact', async t => {
  const { rt, home } = await fixture(t)
  const body = { name: 'custom-work', kind: 'skill', description: 'Custom workflow', content: 'Use the attached material.' }
  await rt.capabilitySave({ ...body, emoji: '🧬' }, { ui: true })
  await rt.capabilitySave({ ...body, description: 'Updated custom workflow' }, { ui: true })
  assert.equal(rt.capabilityLibraryView().find(item => item.name === body.name).emoji, '🧬')
  const ctx = fakeContext()
  const reloaded = createRuntime(ctx, { home, github: false, diagnosticsFile: false })
  t.after(() => ctx.dispose())
  await reloaded.load()
  assert.equal(reloaded.state.capabilities.items[body.name].emoji, '🧬')
  await assert.rejects(reloaded.capabilitySave({ ...body, emoji: 'not an emoji' }, { ui: true }), /Choose an emoji/)
  assert.equal(reloaded.state.capabilities.items[body.name].emoji, '🧬')
  await reloaded.capabilitySave({ ...body, emoji: '' }, { ui: true })
  assert.equal(skillEmoji(reloaded.state.capabilities.items[body.name]), '🧰')
})

test('known imports inherit curated presentation and replacement keeps manual choices', async t => {
  const { rt } = await fixture(t)
  const known = { name: 'domain-1', kind: 'skill', originalName: 'example', builtinSource: 'chemclaw',
    labels: { zh: '按产品找生产厂家' }, purpose: '查找生产企业', category: '内贸采购', examples: ['An unrelated role example.'] }
  rt.state.capabilities.items[known.name] = known
  await rt.save()
  const upload = { files: [{ path: 'SKILL.md', data: Buffer.from(content()).toString('base64') }] }
  let preview = await rt.skillImportEndpoint('skill-import-preview', upload)
  assert.equal(preview.candidates[0].emoji, '🏭')
  assert.equal(preview.candidates[0].examples[0], skillExample(known))
  await rt.skillImportEndpoint('skill-import-commit', { token: preview.token, selections: [{ key: '0', emoji: '🧪' }] })
  assert.equal(rt.state.capabilities.items.example.emoji, '🧪')
  preview = await rt.skillImportEndpoint('skill-import-preview', upload)
  assert.equal(preview.candidates[0].emoji, '🧪')
  await assert.rejects(rt.skillImportEndpoint('skill-import-commit', { token: preview.token, selections: [{ key: '0', conflict: 'replace', emoji: '<script>' }] }), /Choose an emoji/)
  assert.equal(rt.state.capabilities.items.example.emoji, '🧪')
  await rt.skillImportEndpoint('skill-import-commit', { token: preview.token, selections: [{ key: '0', conflict: 'replace' }] })
  assert.equal(rt.state.capabilities.items.example.emoji, '🧪')
})

test('guided service parsing stores placeholders, handles local arguments and refuses credentialed URLs', () => {
  const remote = parseServiceDraft({ mode: 'url', name: 'sample', url: 'https://example.test/mcp', key: 'synthetic-only-token', headers: '{}' })[0]
  assert.match(remote.item.headers.Authorization, /^\$DSH_SECRET_MCP_/)
  assert.ok(!JSON.stringify(remote.item).includes('synthetic-only-token'))
  const local = parseServiceDraft({ mode: 'json', json: JSON.stringify({ mcpServers: { sample: { command: 'node', args: ['server.js', '--token', 'synthetic-local-token'], env: { API_KEY: 'synthetic-env-key', MODE: 'dev' } } } }) })[0]
  assert.match(local.item.args[2], /^\$DSH_SECRET_MCP_/)
  assert.equal(local.item.env.MODE, 'dev')
  assert.match(local.item.env.API_KEY, /^\$DSH_SECRET_MCP_/)
  assert.equal(local.secrets.length, 2)
  assert.throws(() => parseServiceDraft({ mode: 'url', name: 'sample', url: 'https://example.test/mcp?key=hidden' }), /HTTPS/)
})
