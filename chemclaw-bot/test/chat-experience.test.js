import assert from 'node:assert/strict'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { runInNewContext } from 'node:vm'
import { build } from 'esbuild'

const bundle = await build({
  stdin: { contents: "export * from './src/client/skill-menu-view.js'; export * from './src/client/artifact-files.js'", resolveDir: fileURLToPath(new URL('..', import.meta.url)) },
  bundle: true, format: 'cjs', platform: 'node', write: false, external: ['react'],
})
const module = { exports: {} }
runInNewContext(bundle.outputFiles[0].text, { module, exports: module.exports, require: () => ({
  createElement: (type, props, ...children) => ({ type, props, children: children.flat() }),
  useMemo: make => make(),
}) })
const { installSkillMenu, localizedSkillSnapshot, generatedFiles, ArtifactFiles } = module.exports

test('the menu wraps the public slot locale seat and keeps native pick routing', () => {
  const picks = []
  const original = { component: () => {}, options: { id: 'slash-menu', order: 0 }, locale: 'slash.menu',
    inject: () => ({ menu: {}, onPick: (...args) => picks.push(args), hooks: { original: true } }) }
  let registered
  const slots = { entries: () => [original], subscribe: () => () => {}, register: (options, component) => { registered = { options, component }; return () => {} } }
  const off = installSkillMenu(slots, () => ({ hooks: { roster: true } }), -100)
  assert.equal(registered.options.id, 'slash-menu')
  assert.equal(registered.options.locale, 'slash.menu')
  const face = registered.options.inject('session')
  face.onPick('skill', 2)
  assert.deepEqual(picks, [['skill', 2]])
  assert.equal(face.hooks.original, true)
  assert.equal(face.hooks.roster, true)
  off()
})

test('both skill sources and original-name aliases show business copy without changing the controller', () => {
  const items = [{ name: 'domain-18', originalName: 'lead-workflow', kind: 'skill', labels: { zh: '找下游工厂' }, purpose: '按原料用途寻找工厂', category: '内贸销售' }]
  const native = { name: 'lead-workflow', description: 'English description' }
  const state = { groups: [{ source: 'skill', items: [native, { name: 'ask-matt' }] }, { source: 'chemclaw-skills', items: [{ name: 'domain-18' }] }, { source: 'command', items: [{ name: 'goal' }] }] }
  const projected = localizedSkillSnapshot(state, items, 'zh')
  assert.equal(projected.groups[0].items[0].name, '找下游工厂')
  assert.equal(projected.groups[0].items[0].description, '按原料用途寻找工厂')
  assert.equal(projected.groups[0].items[1].label, '帮我选择工作方法')
  assert.equal(projected.groups[1].items[0].name, '找下游工厂')
  assert.equal(projected.groups[2], state.groups[2])
  assert.equal(native.name, 'lead-workflow')
  assert.equal(native.description, 'English description')
})

test('unknown host skills shorten long English titles; mapped native skills stay Chinese', () => {
  const long = 'Use when starting any conversation - establishes how to find and use skills, requiring skill invocation before ANY response including clarifying questions'
  const unknown = { name: 'some-unknown-host-skill', label: long, description: long }
  const mapped = { name: 'using-superpowers', label: long, description: long }
  const state = { groups: [{ source: 'skill', items: [unknown, mapped] }] }
  const projected = localizedSkillSnapshot(state, [], 'zh')
  const [shortened, chinese] = projected.groups[0].items
  assert.equal(shortened.name, 'some-unknown-host-skill')
  assert.equal(shortened.label, 'some-unknown-host-skill')
  assert.ok(shortened.description.length <= 81)
  assert.match(shortened.description, /\u2026$|\.\.\.$|…$/)
  assert.equal(chinese.label, '先按技能流程工作')
  assert.match(chinese.description, /[\u4e00-\u9fff]/)
  assert.equal(unknown.label, long)
  assert.equal(mapped.name, 'using-superpowers')
})

test('only successful generated file results produce openers, including Unicode and spaces', () => {
  const paths = ['D:\\work\\客户报告 10月.xlsx', '/work/报告.html']
  const call = { kind: 'tool-result', content: [{ type: 'text', text: JSON.stringify({ files: [...paths, paths[0], 'https://example.com/x', 'javascript:alert(1)', 'relative.html'].map(path => ({ path })) }) }] }
  const files = generatedFiles(call)
  assert.equal(files.length, 2)
  assert.deepEqual(Array.from(files, file => file.path), paths)
  assert.equal(generatedFiles({ ...call, isError: true }).length, 0)
  assert.equal(generatedFiles({ ...call, kind: 'tool-call' }).length, 0)
  assert.equal(generatedFiles({ ...call, content: [{ type: 'text', text: 'invalid' }] }).length, 0)
  const opened = []
  const view = ArtifactFiles({ files, openFile: path => opened.push(path) })
  for (const button of view.children) button.props.onClick()
  assert.deepEqual(opened, paths.map(path => path.replaceAll('\\', '/')))
})
