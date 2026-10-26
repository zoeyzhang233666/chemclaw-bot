import { readFileSync, writeFileSync } from 'node:fs'
const file = new URL('../chemclaw-bot/seed/catalog.json', import.meta.url)
const catalog = JSON.parse(readFileSync(file, 'utf8'))
const legacyCatalog = JSON.parse(readFileSync(new URL('../chemclaw-bot/seed/bots.json', import.meta.url), 'utf8'))
const names = [
  'ChemClaw',
  '下游客户开发专家', '标杆客户拓展顾问', '扩产项目商机专家', '采购商机情报员', '重点客户研究员', '客户拜访顾问', '区域市场规划师',
  '供应商寻源专家', '生产厂家核验员', '供应商尽调专家', '资质风控专员', '采购比价分析师', '采购合同顾问',
  '海外市场研究员', '海外客户开发专家', '海外询盘顾问', '出口合规顾问', '出口报价单证专员', '海外供应商尽调员', '进口采购分析师',
  '现货行情分析师', '产业链研究员', '供需研究员', '产能装置研究员', '成本利润分析师', '产业资讯分析师', '企业深度研究员', '品种研究员',
  '基差研究员', '月差研究员', '区域价差分析师', '内外盘价差分析师', '季节性研究员', '价格联动研究员', '事件研究员', '策略回测研究员',
  '化学信息专家', '工艺文献研究员', '质量检验顾问', '物料能耗工程师', '生产数据分析师',
  'HTML 报告设计师', '图表地图设计师', 'PPT 演示设计师', 'Excel 数据分析师', '文档与纪要专员', '化工双语译审',
  '业务方案质询官', '任务规划与验收官',
]
const groups = ['客户开发作战群', '客户拜访跟进群', '采购寻源比价群', '供应商尽调评审群', '海外客户开拓群', '出口报价单证群', '进口采购研判群', '行情供需研讨群', '产业链装置跟踪群', '期现价差研究群', '策略回测讨论群', '化学质量会诊群', '工艺生产分析群', '研报与演示协作群', '业务方案评审群']
const examples = [
  '我销售纯碱，想拓展华东玻璃厂客户，请组织团队给出有证据的客户清单和拜访计划。',
  '帮我找江苏、浙江实际使用纯碱的玻璃工厂，区分生产企业和贸易商，交付带来源的客户表。',
  '以我提供的三家标杆客户为样本，分析共同的工艺和原料需求，再寻找相似客户。',
  '找华东未来一年可能投产的玻璃扩产项目，列出新增纯碱需求的依据和联系时点。',
  '扫描近一个月与甲醇相关的公开招标和采购线索，标出有效期、规格和联系入口。',
  '研究这家目标客户的产品、工厂和采购需求，整理下一次销售沟通的问题清单。',
  '把这段微信记录整理成客户跟进卡，列出异议、承诺、待办和下次拜访重点。',
  '梳理山东纯碱下游客户的城市分布，做一张区域地图并安排三天的拜访路线。',
  '寻找可向华东供货的工业级甲醇生产厂家，列明产地、装置、资质和证据。',
  '核验这份供应商名单中谁有真实生产装置，谁是贸易商，不能确认的逐项标注。',
  '对这家原料供应商做准入尽调，核实主体、生产、履约和风险，输出证据清单。',
  '核对供应商营业执照和许可证的主体、有效期与供货范围，列出风险和待补资料。',
  '对比这三份含税运到报价，统一包装、付款和账期口径，计算采购总成本。',
  '审阅这份采购合同，重点检查质量标准、验收、交付、付款和违约条款。',
  '研究越南钛白粉进口市场，区分终端行业、潜在客户、合规要求和信息缺口。',
  '寻找越南涂料行业的钛白粉买家，核实真实业务和采购匹配度，保留来源。',
  '整理这封海外询盘，核对产品规格、数量、贸易术语，起草英文澄清邮件。',
  '核验这款化工品出口所需的 HS 编码依据和监管条件，标出需要报关机构确认的部分。',
  '根据成本和运费做 FOB 与 CIF 初步报价，并列出装箱单、发票和单证核对项。',
  '核验这家海外供应商的注册信息、工厂证据和付款风险，整理验证路径。',
  '统一这两份甲醇进口报价的币种、税费和到岸口径，测算完税成本与进口窗口。',
  '整理纯碱近一个月的现货行情，注明地区、规格、税基、报价日期和来源。',
  '画出甲醇上下游产业链，标明主要工艺、产品流向和需要跟踪的关键变量。',
  '梳理纯碱季度供需平衡，区分已知数据、计算假设和缺失项。',
  '跟踪 PVC 近期新增产能和检修装置，整理产能、时点及来源证据。',
  '测算不同煤价情景下甲醇成本与利润，明确单耗、价格口径和假设。',
  '解释这条装置停产新闻可能影响哪些产品，区分已核实事件和市场推测。',
  '研究这家化工企业的产品、产能和经营风险，提供引用和待核实清单。',
  '做一份纯碱品种研究报告，覆盖供需、成本、库存与风险，交付 HTML 和明细表。',
  '用我上传的现货与期货数据计算纯碱基差，统一交割品级、地区、日期和单位。',
  '分析甲醇 1 月与 5 月合约月差，标出合约年份和换月影响。',
  '比较华东与华南甲醇价格，纳入运费、税基和品质差异后分析区域价差。',
  '比较境内外甲醇价格，统一汇率、贸易术语、税费和时间口径。',
  '分析这份尿素历史数据的季节性，说明样本年数、异常年份和不确定性。',
  '研究煤价与甲醇价格的相关性和滞后关系，检查缺失值、频率与样本稳定性。',
  '分析历史装置检修事件前后纯碱价格的变化，设置对照窗口并说明归因局限。',
  '用上传数据回测这个基差规则，纳入手续费、滑点和换月，检查未来数据泄漏。',
  '核对乙酸乙酯的名称、CAS、结构和物性，交叉验证数据库并列出来源。',
  '检索甲醇合成工艺文献，比较研究路线和证据边界，整理可查阅的文献表。',
  '对比采购规格与这份 COA，检查指标、单位、检测方法和不符合项。',
  '按我提供的反应式和单耗做物料衡算，列明收率、损耗和边界假设。',
  '分析这份生产日报的产量、单耗和异常，注明数据质量和进一步核查方向。',
  '把这些研究材料制作成离线可打开的 HTML 报告，支持目录、筛选和打印。',
  '用这份价格和区域数据做可缩放的行情图与客户分布图，保留数据表和来源。',
  '把这份研究报告做成 12 页管理层汇报 PPT，保留数据来源和关键图表。',
  '清洗这份采购 Excel，统一单位和日期，生成可核查的对比表和图表。',
  '将会议录音转写稿整理为决策纪要、责任人和截止日期，交付 Word 与 PDF。',
  '译审这份化工品英文报价和 COA，核对术语、单位、产品规格和歧义。',
  '质询这份采购方案的关键假设、反证和资源约束，给出可以验证的修改建议。',
  '把这个客户开发项目拆成任务、证据要求和交付标准，并复核最终成果。',
]
const groupExamples = [examples[1], examples[6], examples[8], examples[10], examples[15], examples[18], examples[20], examples[21], examples[22], examples[29], examples[36], examples[37], examples[41], examples[44], examples[48]]
const groupDescriptions = [
  '从产品应用出发，协同完成潜客筛选、标杆复制、扩产商机和区域拜访规划。',
  '汇总客户背景与沟通记录，梳理需求、异议、承诺和下一次拜访行动。',
  '寻找真实货源，核验生产身份，统一报价口径，给出可比较的采购候选表。',
  '联合审查企业、生产、资质和合同证据，形成供应商准入意见与待补资料。',
  '先研究目标市场，再筛选海外买家，核验客户匹配度并准备外联材料初稿。',
  '协同处理询盘、出口合规、报价和单证，降低规格、条款与语言歧义。',
  '核验海外货源，测算完税到货成本，研究进口窗口和采购风险。',
  '联合梳理现货行情、供需、成本和产业新闻，解释变化依据与数据缺口。',
  '跟踪上下游产业链、在建项目、产能和装置变化，定位潜在供需影响。',
  '统一现货和合约口径，研究基差、月差及区域和内外盘价差，不执行交易。',
  '把策略想法变成可检验的研究规则，检查样本、费用、换月和回测偏差。',
  '交叉核验化学身份、物性、结构与 COA 指标，整理质量疑点和资料依据。',
  '组合工艺文献、物料能耗测算与生产数据分析，为工程人员提供辅助研究。',
  '先完成证据核验与研究结构，再协作制作 HTML、图表、明细表和汇报 PPT。',
  '由质询与验收角色检验业务方案，明确反证、资源约束和可操作的改进建议。',
]
const teams = [
  ['role-1-1', 'role-1-2', 'role-1-3', 'role-1-4', 'role-1-5', 'role-1-7', 'role-7-4'],
  ['role-1-6', 'role-1-5', 'role-7-5', 'role-7-6'],
  ['role-2-1', 'role-2-2', 'role-2-5', 'role-6-3', 'role-7-4'],
  ['role-2-3', 'role-2-4', 'role-2-6', 'role-6-3', 'role-7-5'],
  ['role-3-2', 'role-3-1', 'role-1-5', 'role-3-4', 'role-7-6'],
  ['role-3-5', 'role-3-3', 'role-3-4', 'role-7-6', 'role-7-5'],
  ['role-3-7', 'role-3-6', 'role-2-5', 'role-4-1', 'role-7-4'],
  ['role-4-1', 'role-4-3', 'role-4-5', 'role-4-6', 'role-4-8', 'role-7-2'],
  ['role-4-2', 'role-4-4', 'role-4-3', 'role-4-7', 'role-7-2'],
  ['role-5-1', 'role-5-2', 'role-5-3', 'role-5-4', 'role-5-5', 'role-4-1', 'role-7-2', 'role-7-4'],
  ['role-5-8', 'role-5-6', 'role-5-7', 'role-5-5', 'role-8-1', 'role-7-4'],
  ['role-6-1', 'role-6-3', 'role-6-2', 'role-7-6'],
  ['role-6-2', 'role-6-4', 'role-6-5', 'role-6-1', 'role-7-4'],
  ['role-4-8', 'role-7-1', 'role-7-2', 'role-7-3', 'role-7-4', 'role-7-5', 'role-8-2'],
  ['role-8-1', 'role-8-2', 'role-4-7', 'role-7-5'],
]
const legacy = { '潜客猎手': 1, '拜访顾问': 6, '外贸销售': 15, '准入尽调': 10, '外贸采购': 20, '行情报价': 21, '产业基本面': 23, '价差量化': 29, '产品情报': 37, 'PPT设计师': 44, '表格专家': 45, '文档撰稿': 46, '产业链制图': 43, '深度研究员': 27, '舆情雷达': 26, '市场研报': 28, '中英译审': 47, '质询官': 48, '流程参谋': 49 }
const legacyGroups = { 0: '客户开发作战室', 2: '采购寻源台', 9: '期现研究台', 5: '进出口协作', 13: '交付工坊' }
const colors = ['#2877B8', '#B86D39', '#248478', '#8461B6', '#B34E67', '#4E7C3C', '#936F26', '#47739A', '#735D8E']
// Lobster plus the original distinct mascots; ChemClaw stays lobster, others rotate.
const shapes = ['lobster', 'star', 'moon', 'gumdrop', 'peanut', 'bunny', 'kitty', 'acorn']
catalog.version = 3
catalog.roles.forEach((role, index) => {
  role.previousNames = [...new Set([...(role.previousNames ?? []), role.name, ...Object.entries(legacy).filter(([, value]) => value === index).map(([name]) => name)])].filter(name => name !== names[index])
  role.name = names[index]
  role.examples = [examples[index], ...(role.examples ?? []).slice(1)]
  role.color = colors[index % colors.length]
  // ChemClaw (index 0) is lobster; the rest cycle the same pool so looks stay distinct.
  role.avatar = { shape: shapes[index % shapes.length] }
})
catalog.groups.forEach((group, index) => {
  group.previousMembers ??= group.members
  if (!group.previousNotices) {
    const oldRole = id => { const role = catalog.roles.find(item => item.id === id); return { ...role, name: role.previousNames[0] ?? role.name } }
    const owner = oldRole(group.admin)
    const members = group.previousMembers.map(oldRole)
    const description = `由${owner.name}负责组织，${members.filter(role => role.id !== owner.id).map(role => role.name).join('、')}分别核验相关材料，形成可追溯结论与交付文件。`
    const notice = `${description}\n负责人：${owner.name}\n分工：${members.map(role => `${role.name}：${role.description}`).join('\n')}\n交付：可追溯结论、HTML 报告和明细表。\n示例：请启动${group.previousNames[0]}，产品是纯碱，先确认研究范围与交付要求。`
    group.previousNotices = [notice, legacyCatalog.rooms.find(item => item.name === legacyGroups[index])?.notice].filter(Boolean)
  }
  group.members = teams[index]
  group.previousNames = [...new Set([...(group.previousNames ?? []), group.name, legacyGroups[index]].filter(Boolean))].filter(name => name !== groups[index])
  group.name = groups[index]
  group.description = groupDescriptions[index]
  group.examples = [groupExamples[index]]
  group.deliverables = `${group.name}结论与行动清单；带来源的 HTML 分析报告及所需明细表、文档或 PPT。`
  const owner = catalog.roles.find(role => role.id === group.admin)
  group.inputs = owner.inputs
  group.sources = owner.sources
  group.limits = owner.limits
  group.category = catalog.roles.find(role => role.id === group.admin).category
  group.color = colors[index % colors.length]
  delete group.avatar
})
writeFileSync(file, `${JSON.stringify(catalog, null, 2)}\n`)
