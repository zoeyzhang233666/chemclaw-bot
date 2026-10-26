import { readFileSync, writeFileSync } from 'node:fs'
const pairs = [
  ['README.md', 'README.zh.md'],
  ['chemclaw-bot/README.md', 'chemclaw-bot/README.zh.md'],
  ['chemclaw/docs/README.md', 'chemclaw/docs/README.zh.md'],
]
for (const [english, chinese] of pairs) {
  const en = readFileSync(english, 'utf8').replaceAll('Scenarios and experts', 'Bots').replaceAll('Only the coordinator is created initially. Open **Bots → Built-in experts**, inspect inputs and examples, and enable what you need. Repeated activation preserves custom instructions and does not duplicate the team.', 'All 50 Bots and 15 collaboration groups are created automatically and shown in expanded sidebar categories. Open Bots or Group chats to see purposes, members, inputs and examples, then start a conversation directly. Existing teams receive missing presets without duplicating conversations or replacing custom instructions.')
  const zh = readFileSync(chinese, 'utf8').replaceAll('「场景与专家」', '「Bot」').replaceAll('首次只创建主控；点击「Bot → 内置专家」查看用途、输入、成员分工和示例，再按需启用。重复启用不重复建队，不覆盖自定义指令。', '50 位 Bot 和 15 个协作群会自动建好，并在侧栏按分类全部显示。打开「Bot」或「群聊」可查看用途、输入、成员分工和示例，直接开始对话，无需启用或组队。旧团队自动补齐预设，保留已有对话和自定义指令。')
  const enNote = '\n\nCurrent review: the UI changes run from source. A new EXE will be built only after the user explicitly confirms the reviewed interface. An older EXE in dist-pack is not this revision.\n\nModels: ChemClaw Settings → Models includes APIHub first. Get a Key at https://apihub.chem-cloud.cn/; the fixed API endpoint is https://apihub.chem-cloud.cn/v1. Paste the Key, fetch models and choose the models to save. Other providers remain available.\n\nKeyless web search is supplied by dsh-free-search 0.9.12, including fallback engines. Search results carry sources; one failed engine does not establish that all networking is unavailable. Huagongshe anonymous chemistry capabilities are listed under Public research data; optional authorization is folded separately.\n'
  const zhNote = '\n\n本轮状态：先审阅源码 GUI，得到用户明确确认后才重建 EXE。dist-pack 中的旧 EXE 不包含本轮界面修改。\n\n模型：ChemClaw 设置 → 模型，APIHub 放在首位。领取 Key：https://apihub.chem-cloud.cn/；固定 API 地址：https://apihub.chem-cloud.cn/v1。填 Key、获取模型、勾选保存即可，其他供应商仍可添加。\n\n已内置 dsh-free-search 0.9.12 的免费搜索与回退能力，结果保留出处。一个引擎失败不代表所有联网能力不可用。化工社匿名能力在公开研究数据中，可选授权单独折叠。\n'
  writeFileSync(english, en + (en.includes('Current review:') ? '' : enNote))
  writeFileSync(chinese, zh + (zh.includes('本轮状态：') ? '' : zhNote))
}
const guide = 'chemclaw/docs/使用指南.md'
const guideText = readFileSync(guide, 'utf8').replaceAll('「场景与专家」', '「Bot」').replaceAll('打开「Bot → 内置专家」，看介绍和示例，点击「启用并打开」。只启用需要的角色；重复点击会回到已有对话。', '侧栏已列出全部专业 Bot 和业务协作群。点击即可开始对话；在「Bot」和「群聊」页可按分类查看用途、输入、成员分工及示例，无需启用。')
writeFileSync(guide, guideText + (guideText.includes('本轮新增模型入口：') ? '' : '\n\n本轮新增模型入口：侧栏「模型」或设置「模型」→ APIHub。领取链接 https://apihub.chem-cloud.cn/，无需切换经典 DSH 界面。模型 Key 与公司 MCP Key 是两种不同用途的凭据。高级 MCP 和密钥录入表单均随当前主题配色。EXE 会在界面确认后再打包。\n'))
