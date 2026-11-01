// Discover only the native Office skills actually shipped with this ChemClaw host.
// These are read-only catalog entries: the native DSH skill provider owns invocation.
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { officeProvider } from './office-skills.js'
import { NATIVE_SKILL_ZH } from '../shared/native-skill-copy.js'

export const NATIVE_OFFICE_COPY = {
  office: ['Office 文档任务导航', '根据任务选择 Word、PPT、Excel 编辑或文件转换技能。'],
  'office-tools': ['Office 文件操作', '检查和编辑办公文件结构，运行原生 Office 操作命令。'],
  'office-docx': ['Word 文档制作', '制作、修改和核对合同、研究报告及其他 Word 文档。'],
  'office-pptx': ['PowerPoint 制作', '创建和修改可编辑的业务汇报与研究演示文稿。'],
  'office-xlsx': ['Excel 表格制作', '整理数据、制作工作簿和分析表，保留公式及口径。'],
  'office-render': ['Office 预览检查', '预览文档和幻灯片，检查排版、文字溢出及图表。'],
  'office-recalculate': ['Excel 公式重算', '重新计算 Excel 工作簿公式并核验结果。'],
  'office-export-pdf': ['Office 导出 PDF', '将 Word、PPT 或 Excel 文件转换为 PDF 并检查输出。'],
}

const USER_SOURCES = new Set(['user-dsh', 'user-agents', 'project-dsh', 'project-agents', 'custom'])
const isOffice = name => name === 'office' || name === 'office-tools' || name.startsWith('office-')
const nativeCategory = name => name === 'b2b-lead-sourcing' ? '内贸销售'
  : isOffice(name) ? '通用办公'
    : /^(?:rdkit|networkx|scientific-|statistical-|sympy)/.test(name) ? '科学分析' : '基础流程'

export function nativeOfficeSummary(name, description, provider, source = 'bundled', invocation) {
  const userInstalled = USER_SOURCES.has(source)
  const [title, purpose] = NATIVE_OFFICE_COPY[name] ?? NATIVE_SKILL_ZH[name]
    ?? ['专项技能 · ' + name, '按技能说明完成对应任务，查看技术名称和原始说明以了解适用范围。']
  return {
    kind: 'skill', name, originalName: name, labels: { zh: title, en: name },
    description, purpose, category: userInstalled ? '我的安装' : nativeCategory(name),
    ...(userInstalled ? { userInstalled: true } : { builtinSource: provider || 'dsh' }),
    nativeSkill: true, invocation: invocation ?? { userInvocable: true, modelInvocable: true },
    keywords: [name, description, title],
  }
}

export async function nativeSkillCatalog(registry, env = process.env) {
  const results = new Map()
  // The registry is authoritative for every available provider (Office,
  // packaged skills and user-installed DSH skills); never guess a native list.
  if (typeof registry?.list === 'function') {
    try {
      for (const skill of await registry.list({})) {
        if (!skill?.name || typeof skill.name !== 'string') continue
        // Managed capabilities already have editing/ownership metadata in the roster.
        if (skill.provider === 'chemclaw-user-skills' || skill.provider?.startsWith('chemclaw-bot-capability-skill-')) continue
        results.set(skill.name, nativeOfficeSummary(skill.name, skill.description || skill.name,
          skill.provider, skill.source, skill.invocation))
      }
    } catch { /* Keep verifiable packaged assets visible if discovery is incomplete. */ }
  }
  // This provider is shipped by the ChemClaw plugin itself. It can be registered
  // in a scoped layer which a global registry read does not include.
  for (const skill of await officeProvider().list()) {
    if (existsSync(skill.locator) && !results.has(skill.name)) {
      results.set(skill.name, nativeOfficeSummary(skill.name, skill.description, 'chemclaw-office'))
    }
  }
  const runtimeDir = env.CHEMCLAW_OFFICE_RUNTIME_DIR
  const officeRoot = runtimeDir && join(runtimeDir, 'office-skills')
  // The overlay is mounted only with a complete primary runtime. Do not
  // advertise Office skills when the installed payload is absent or broken.
  if (runtimeDir && existsSync(join(runtimeDir, 'primary-runtime', 'runtime.json'))
    && existsSync(join(officeRoot, 'office', 'SKILL.md'))) {
    for (const entry of readdirSync(officeRoot, { withFileTypes: true })) {
      if (!entry.isDirectory() || !Object.hasOwn(NATIVE_OFFICE_COPY, entry.name)) continue
      const file = join(officeRoot, entry.name, 'SKILL.md')
      if (!existsSync(file) || results.has(entry.name)) continue
      const source = readFileSync(file, 'utf8')
      const description = /^description:\s*(.+)$/m.exec(source)?.[1]?.replace(/^['"]|['"]$/g, '') || entry.name
      results.set(entry.name, nativeOfficeSummary(entry.name, description, 'dsh-office'))
    }
  }
  return [...results.values()]
}
