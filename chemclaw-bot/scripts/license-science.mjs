import { writeFileSync, readFileSync } from 'node:fs'
const revision = '593377bb048752abb0152deab9fbb1083a6087df'
const origin = `https://raw.githubusercontent.com/K-Dense-AI/scientific-agent-skills/${revision}/LICENSE.md`
const response = await fetch(origin)
if (!response.ok) throw new Error(`License fetch: ${response.status}`)
const license = await response.text()
if (!license.includes('MIT License') || !license.includes('K-Dense')) throw new Error('Unexpected license')
for (const name of ['rdkit', 'networkx', 'scientific-visualization', 'statistical-analysis', 'sympy']) writeFileSync(`skills/supplemental/${name}/LICENSE-K-Dense.txt`, license)
const items = JSON.parse(readFileSync('seed/supplemental-sources.json', 'utf8'))
for (const item of items) Object.assign(item, { skillAuthor: 'K-Dense Inc.', licenseNoticeSource: origin, licenseNoticeRevision: revision, note: 'Skill contents come from the user-provided archive identified by its SHA-256; the pinned upstream license supplies the full author notice. Individual SKILL.md library license declarations are retained.' })
writeFileSync('seed/supplemental-sources.json', JSON.stringify(items, null, 2) + '\n')
for (const [name, url] of [
  ['rdkit', 'https://raw.githubusercontent.com/rdkit/rdkit/Release_2025_09_3/license.txt'],
  ['networkx', 'https://raw.githubusercontent.com/networkx/networkx/networkx-3.5/LICENSE.txt'],
  ['sympy', 'https://raw.githubusercontent.com/sympy/sympy/sympy-1.14.0/LICENSE'],
]) {
  const result = await fetch(url)
  if (!result.ok) throw new Error(`${name} license: ${result.status}`)
  writeFileSync(`skills/supplemental/${name}/LICENSE-library.txt`, await result.text())
}
