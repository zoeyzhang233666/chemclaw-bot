import { isMyInstallation, skillLabel } from './skills.js'
import { CURATED_SKILL_EXAMPLES_ZH } from './skill-examples.js'

export const BUILTIN_SKILL_PRESENTATION = {
  'domain-1': ['🏭', '查找山东省实际生产工业级双氧水的厂家，列出厂址、主要产品、生产资质线索和官网来源，排除纯贸易商。'],
  'domain-2': ['🏷️', '核对华东地区最近30天工业级重质纯碱的公开报价，统一规格、含税与交货条件，判断可比价格区间并列出证据。'],
  'domain-3': ['🚚', '比较山东和江苏采购100吨重质纯碱送到杭州的含税到厂成本，分别测算采购价、运费和交期，缺少数据时注明。'],
  'domain-4': ['📈', '研究华东甲醇最近30天的现货价格、煤炭成本、港口库存和下游开工变化，整理采购谈判要点。'],
  'domain-5': ['📋', '为采购100吨重质纯碱、50吨工业双氧水和20吨甲醇分别寻找国内候选生产商，列明生产证据与联系渠道。'],
  'domain-6': ['📜', '拟采购100吨工业级重质纯碱，请先起草示范采购合同，再审查质量验收、延期交货、付款及违约条款风险。'],
  'domain-7': ['🪪', '核查山东海化股份有限公司公开披露的生产业务、经营资质和相关证照，说明哪些文件仍需向供应商索取。'],
  'domain-8': ['🧪', '制作工业级重质纯碱到货COA与采购规格核验清单，逐项列出应核对的关键质量指标、检测方法和异常处理。'],
  'domain-9': ['🧮', '假设甲醇占某化工产品成本30%、原成本5000元/吨，测算甲醇采购价上涨5%、10%、20%时产品成本变化。'],
  'domain-10': ['📍', '以苏州工业园区为收货地点，寻找周边可以供应工业级纯碱的厂家或仓储供应商，附地址与供货证据。'],
  'domain-11': ['🔄', '每月需在华东采购200吨工业级重质纯碱，请建立备选供应商清单，比较产地、交期、生产证据和切换风险。'],
  'domain-12': ['🗺️', '研究中国双氧水主要生产企业、产能分布、工艺和未来一年新增项目，分析采购端潜在供应风险并附来源。'],
  'domain-13': ['🔍', '核查山东海化股份有限公司是否实际生产纯碱，提供生产基地、装置或产能的公开证据，区分厂家和贸易商。'],
  'domain-14': ['🛡️', '对山东海化股份有限公司做公开资料层面的纯碱供应商准入尽调，核查产品、工厂、经营信息及合规风险。'],
  'domain-15': ['🚨', '核查山东海化股份有限公司最近三个月公开可查的司法、监管、生产和经营风险，注明事件日期及来源。'],
  'domain-16': ['⚖️', '比较山东海化、唐山三友化工和江苏苏盐井神的纯碱生产能力、运输区位、产品适配和公开风险，不编造实际报价。'],
  'domain-17': ['🏷️', '假设采购100吨纯碱，A报价2000元/吨含税到厂，B报价1900元/吨含税出厂另加运费120元/吨，C报价1980元/吨含税出厂另加运费60元/吨，请计算总成本并排序。'],
  'domain-18': ['🎯', '寻找江苏和浙江实际使用工业级纯碱的玻璃和洗涤剂生产企业，附工厂、产品和原料使用的公开证据。'],
  'domain-19': ['🤝', '准备拜访旗滨集团玻璃生产业务，请根据公开资料整理产品、生产基地、纯碱用料场景和需要确认的五个问题。'],
  'domain-20': ['💬', '整理以下销售跟进信息：周一客户问每月50吨纯碱到厂价，周二销售答复核实运费，周五客户催要COA。列出待办、承诺与下一次跟进安排。'],
  'domain-21': ['✍️', '把以下微信润色得专业且不增加承诺：王经理您好，纯碱到厂价还在确认运费，COA已联系工厂核实，确认后第一时间发您。'],
  'domain-22': ['🗺️', '整理江苏、浙江、安徽可能采购工业级纯碱的玻璃和洗涤剂工厂分布，按城市、行业及公开证据制定拜访优先级。'],
  'domain-23': ['🔭', '比较山东海化、唐山三友化工和远兴能源的纯碱产能区域、产品布局及公开销售渠道，附可追溯来源。'],
  'domain-24': ['📈', '查询华东重质纯碱最近30天现货价格和涨跌幅，并与华北同规格价格比较，为销售报价准备市场依据。'],
  'domain-25': ['🏷️', '客户声称华东重质纯碱含税到厂价为2100元/吨，请核验最近30天公开报价，检查规格、地区、运费及税费口径。'],
  'domain-26': ['⚖️', '比较最近30天华东与华南工业级重质纯碱含税现货价，分析区域价差和跨区域运输成本对销售的影响。'],
  'domain-27': ['📝', '按模拟询盘起草工业级重质纯碱报价回复：杭州买方要100吨、含税到厂、15天内交货并附COA，明确待确认价格及付款条款。'],
  'domain-28': ['🛡️', '准备在上海向工业清洗企业销售工业级双氧水，请列出买卖双方资质、危化品运输和用途核验要求并附法规来源。'],
  'domain-29': ['🧩', '参考旗滨集团和信义玻璃的公开玻璃生产业务，在江苏浙江寻找使用纯碱的相似潜在生产客户，列出工厂证据。'],
  'domain-30': ['🏗️', '查找未来12个月国内玻璃企业公开的新建、扩建和技改项目，列出企业、地点、进度、预计投产日期与来源。'],
  'domain-31': ['📣', '查找最近30天公开发布的工业甲醇采购公告或招标，列出采购方、数量、截止时间、资质要求和原公告链接。'],
  'domain-32': ['🔎', '在华东寻找十家可能使用工业级纯碱的生产企业，按原料需求、项目动态和企业真实性排列销售跟进优先级。'],
  'domain-33': ['🏢', '研究旗滨集团玻璃业务的主要生产基地、产品和原料采购场景，分析工业级纯碱供应商有哪些潜在切入点。'],
  'domain-34': ['⭐', '评估旗滨集团作为工业级纯碱潜在客户的价值，综合原料需求、扩产线索、采购信息和公开风险给出结论。'],
  'domain-35': ['🧭', '向旗滨集团销售工业级纯碱时，使用部门、工厂采购、集团采购及供应商准入各承担什么角色？给出联系顺序。'],
  'domain-36': ['💡', '调查旗滨集团最近六个月公开披露的玻璃产线、技改和项目变化，寻找可用于纯碱业务拜访的真实话题。'],
  'domain-37': ['🌍', '统计中国最近12个月甲醇进口来源国及数量占比，比较同比变化，注明海关口径、统计期和数据来源。'],
  'domain-38': ['📜', '假设从沙特进口1000吨工业甲醇、CIF上海、美元结算，请拟定示范采购条款并审查品质、付款和保险风险。'],
  'domain-39': ['🌐', '研究沙特阿拉伯甲醇主要生产商、出口港口及对华贸易线索，评估中国采购企业可能面临的供应和运输风险。'],
  'domain-40': ['🏭', '查找沙特阿拉伯可供应工业甲醇的真实生产企业，核实其官网、产品资料、工厂和可公开验证的贸易线索。'],
  'domain-41': ['🔍', '根据SABIC公开信息核查与甲醇相关的生产业务、产品资料和企业身份，区分已验证事项与待索取的供货资质。'],
  'domain-42': ['🚢', '假设甲醇CIF上海报价350美元/吨、汇率7.20、采购1000吨，请列出税费、港杂和运输计算过程，缺少税率时查询官方规定。'],
  'domain-43': ['🪟', '比较最近30天甲醇CFR中国公开报价与华东甲醇现货价，统一汇率、税费和交货口径，判断进口窗口是否存在。'],
  'domain-44': ['📋', '从沙特进口工业甲醇到上海作为化工原料，需要哪些报关、危化品和质量资料？列出适用规定及官方链接。'],
  'domain-45': ['✅', '制作沙特进口1000吨工业甲醇的发票、装箱单与提单核对清单，说明品名、数量、重量、港口与主体信息如何相互匹配。'],
  'domain-46': ['💱', '假设采购1000吨甲醇、合同价350美元/吨，测算人民币兑美元汇率7.0、7.2、7.4时的货值成本差异。'],
  'domain-47': ['🌍', '比较越南、印度尼西亚和泰国作为中国金红石型钛白粉出口市场的需求、准入要求和竞争情况，筛选优先国家。'],
  'domain-48': ['📜', '为向越南客户出口100吨金红石型钛白粉、FOB上海、美元结算编写示范合同并检查质量、付款与违约责任。'],
  'domain-49': ['💱', '假设钛白粉出口报价2300美元/吨、人民币成本15000元/吨、90天后收款，测算汇率6.9、7.2、7.5时的毛利变化。'],
  'domain-50': ['🧾', '按模拟订单制作金红石型钛白粉出口报价单及形式发票：卖方中国出口商A，买方越南客户B，100吨，FOB上海，2300美元/吨。'],
  'domain-51': ['🌐', '研究越南金红石型钛白粉的涂料、塑料等下游需求，整理真实买家类型和中国出口商需要核查的进口要求。'],
  'domain-52': ['🎯', '寻找越南可能采购金红石型钛白粉的真实涂料或塑料生产企业，优先列出官网能验证产品用途的买家。'],
  'domain-53': ['🔎', '寻找一家公开可验证的越南涂料生产企业，核查其公司身份、业务、地址、联系方式及钛白粉原料使用线索。'],
  'domain-54': ['📨', '模拟英文询盘为：We need 100 MT rutile TiO2, FOB Shanghai, shipment next month. Please quote. 请提取需求、补充询价问题并起草英文回复。'],
  'domain-55': ['🛃', '核查中国金红石型钛白粉出口越南的中国出口要求、越南进口准入和标签规定，注明适用条件与官方来源。'],
  'domain-56': ['🔢', '金红石型二氧化钛颜料以粉末出口越南时可能对应哪些HS编码？根据成分、是否配制和用途列出归类候选及依据。'],
  'domain-57': ['🧮', '假设出口越南100吨金红石型钛白粉，成本15000元/吨、内陆运费300、港杂费150、汇率7.20，请测算FOB报价成本底线。'],
  'domain-58': ['✅', '以100吨金红石型钛白粉FOB上海出口越南为例，制作商业发票、装箱单及提单的品名、数量、重量与主体信息核对清单。'],
  'domain-59': ['📖', '用通俗语言介绍甲醇的用途、工艺、供需和价格驱动，列出关键变量。'],
  'domain-60': ['🏭', '整理甲醇最近一个月的检修、开工和产量事件，核实发生时间。'],
  'domain-61': ['🛒', '整理甲醇下游最近一个月的生产、订单与消费变化，区分事实和预期。'],
  'domain-62': ['⛓️', '沿实际工艺路线分析煤价变化如何传导到甲醇及其下游成本。'],
  'domain-63': ['💰', '统一价格、单耗和时间口径，比较甲醇产业链各环节的利润变化。'],
  'domain-64': ['👀', '把当前甲醇研究中的分歧整理成可跟踪指标，说明观察频率和验证条件。'],
  'domain-65': ['🌅', '整理甲醇今日价格、供需和产业事件，生成有来源、有缺口说明的晨报。'],
  'domain-66': ['🗞️', '按附件重点客户名单整理一周情报，提炼变化和可跟进行动。'],
  'domain-67': ['🗓️', '回顾纯碱本周价格、供需和产业事件，更新驱动判断与下周观察项。'],
  'domain-68': ['📑', '围绕甲醇新增产能对华东供应的影响，组织证据并形成专题研究报告。'],
  'domain-69': ['💡', '用一个具体例子解释基差、月差和期现关系，说明哪些条件需要核实。'],
  'domain-70': ['🏗️', '跟踪国内甲醇新增产能与项目进度，区分规划、在建、投产和实际爬坡。'],
  'domain-71': ['🕸️', '绘制甲醇上下游产业链结构图，标明产品、工艺和连接依据。'],
  'domain-72': ['🗺️', '制作甲醇产业链价格地图，每个价格点标明日期、规格和来源。'],
  'domain-73': ['🏢', '研究这家产业企业的产品、装置、产能和价值链位置，附上证据。'],
  'domain-74': ['📰', '汇总纯碱产业资讯，识别重复报道，定位真实事件及发生时间。'],
  'domain-75': ['🏭', '整理国内主要纯碱生产企业和产能，逐项标注口径与来源。'],
  'domain-76': ['🗺️', '梳理山东甲醇产业的企业、园区、产能和下游分布。'],
  'domain-77': ['🏗️', '分析这套新增甲醇产能可能影响哪些企业和地区，区分预期与实际供应。'],
  'domain-78': ['📣', '核实这条产业新闻的事件与时间，分析影响范围并列出尚需验证的条件。'],
  'domain-79': ['📊', '核对纯碱当前价格在可比历史样本中的位置，说明样本和规格口径。'],
  'domain-80': ['📉', '解释甲醇最近一个月的涨跌，逐项核实价格、供需和事件证据。'],
  'domain-81': ['⚖️', '检查这轮纯碱涨价是否有供需基本面支持，同时列出反证和缺口。'],
  'domain-82': ['📏', '统一现货和期货口径，比较纯碱当前基差与可比历史区间。'],
  'domain-83': ['🌦️', '整理可比开工率历史，检查季节规律，注明样本变化和异常年份。'],
  'domain-84': ['🌦️', '按一致合约和现货口径，检查甲醇基差的历史季节分布。'],
  'domain-85': ['🔗', '对齐这两组指标的频率和样本，检验相关性并检查异常值与共同趋势。'],
  'domain-86': ['⏱️', '检验这两组指标谁领先谁，检查不同滞后期及结果是否稳健。'],
  'domain-87': ['📦', '在可比样本中检验甲醇库存与价格的关系，说明相关性与因果的区别。'],
  'domain-88': ['⚙️', '结合工艺和供需背景，检验开工率与价格的关系及稳健性。'],
  'domain-89': ['🧪', '按可复现的样本和规则，检验基差是否包含后续价格表现的信息。'],
  'domain-90': ['🛑', '围绕这些装置停车事件，定义观察窗口与对照条件，检验相关市场变化。'],
  'domain-91': ['🏗️', '区分项目预期、投产和实际爬坡时间，研究新增产能对市场的影响。'],
  'domain-92': ['🏛️', '核实这项政策内容和落地时间，设计观察窗口并检验市场反应。'],
  'domain-93': ['🗓️', '拆解甲醇合约月差变化，核对交割、库存和供需证据。'],
  'domain-94': ['📡', '在统一口径下筛查异常基差，标明历史位置与需要核实的因素。'],
  'domain-95': ['📡', '按一致合约结构扫描异常月差，区分季节性与特殊变化。'],
  'domain-96': ['📡', '统一地区、规格和交付口径，筛查异常区域价差与运输约束。'],
  'domain-97': ['📡', '沿真实产业联系扫描价格和利润背离，标明可比性限制与验证路径。'],
  'domain-98': ['🕰️', '用当前供需和价格状态定义可比指标，找历史上相似的阶段并比较差异。'],
  'domain-99': ['🧪', '把这个研究判断改写成可检验假设，明确样本、指标和反证条件。'],
  'domain-100': ['🔬', '按这条明确规则进行回测，考虑交易成本、前视偏差和样本外表现。'],
  'domain-101': ['⚖️', '统一地区、规格和交付条件，比较甲醇区域价差并解释变化。'],
  'domain-102': ['🪟', '统一汇率、税费和贸易口径，比较甲醇国内外价格及进出口窗口。'],
  'domain-103': ['↔️', '核实这两个相关品种的产业联系，分析价格背离的供需与替代因素。'],
  'domain-104': ['🔗', '沿实际工艺路线比较上下游价格变化，检验成本传导和时滞。'],
  'domain-105': ['⚖️', '确认这两个品种的产业联系与可比单位，分析比价变化和历史位置。'],
  'domain-106': ['🌦️', '按同一价格口径比较多年季节走势，标明样本范围和异常年份。'],
  'domain-107': ['📦', '用完整资源目录检查库存季节性，审核历史口径和样本可比性。'],
  'domain-108': ['📦', '整理同口径库存历史，分析季节规律、异常年份和样本变化。'],
  'aux-networkx': ['🕸️', '分析附件企业与供应链数据的连接关系，绘制网络图并说明关键节点。'],
  'aux-rdkit': ['🧬', '核验这些分子结构的相似性，计算所需描述符，交付结构图和分析表。'],
  'aux-scientific-visualization': ['📊', '把附件科学数据制作成可导出的专业图表，保留可编辑绘图代码。'],
  'aux-statistical-analysis': ['📐', '为附件数据选择合适的统计检验，解释结果、假设条件和局限。'],
  'aux-sympy': ['🔢', '推导这个公式并求解方程，列出符号定义、计算过程和验证结果。'],
  'chemclaw-presentations': ['🎞️', '把附件研究资料整理成用于客户拜访的可编辑 PowerPoint，保留引用来源。'],
  'guizang-ppt-skill': ['🖥️', '把这份分享提纲制作成可以在浏览器横向翻页的演示文稿。'],
  'chemclaw-chemistry': ['⚗️', '通过数据库交叉核验这个化合物的名称、CAS 和结构是否一致。'],
  'chemclaw-delivery': ['📁', '把这份分析整理成可打开、可核验的报告与数据文件，并提供交付链接。'],
  'chemclaw-research-process': ['🧭', '围绕这个业务问题制定研究计划，核验来源，整理结论与信息缺口。'],
}

export const SKILL_EMOJIS = [...new Set(['🧰', ...Object.values(BUILTIN_SKILL_PRESENTATION).map(([emoji]) => emoji), '📄', '📧', '💻', '🖼️', '🎨', '📅'])]
export const validSkillEmoji = value => typeof value === 'string' && SKILL_EMOJIS.includes(value)

const EMOJI_RULES = [
  ['📜', /合同|contract|agreement/i],
  ['🛡️', /合规|资质|证照|compliance|licen[cs]e|qualification/i],
  ['💱', /汇率|exchange[- ]rate|currency/i],
  ['🧮', /测算|成本|报价|利润|cost|calculat|quotation|profit/i],
  ['📦', /库存|inventory|stock[- ]level/i],
  ['🗺️', /地图|区域.*分布|market[- ]map|regional|geograph/i],
  ['📈', /行情|价格|price|pricing|market[- ]brief/i],
  ['🏭', /生产厂家|生产商|工厂|供应商|supplier|manufacturer|factor(?:y|ies)|sourcing/i],
  ['🎯', /下游客户|买家|潜客|商机|客户开发|buyer|prospect|lead[- ]sourcing/i],
  ['💬', /跟进|聊天|沟通|follow[- ]?up|conversation/i],
  ['🧬', /分子|化学结构|molecul|rdkit/i],
  ['⚗️', /化合物|化学|chemistry|compound/i],
  ['🕸️', /产业链|关系网络|networkx|network|value[- ]chain|supply[- ]chain/i],
  ['🎞️', /演示|幻灯|presentation|powerpoint|pptx|slides/i],
  ['📊', /图表|可视化|visualiz|chart|plot/i],
  ['📐', /统计|检验|statistic|hypothesis/i],
  ['🔢', /公式|方程|代数|符号计算|sympy|algebra|equation/i],
  ['📰', /新闻|资讯|情报|news|intelligence/i],
  ['📑', /报告|研究|report|research/i],
  ['📧', /邮件|email|e-mail/i],
  ['✍️', /写作|润色|文案|writing|copywriting|rewrite/i],
  ['📋', /清单|计划|任务|checklist|planning|task[- ](?:plan|manag)/i],
  ['📄', /文档|document|docx|pdf/i],
  ['💻', /代码|编程|coding|programming/i],
  ['🖼️', /图片|图像|image|photo/i],
]
const CATEGORY_EMOJI = { '内贸采购': '🛒', '外贸采购': '🚢', '内贸销售': '🤝', '外贸销售': '🌍', '产业基本面': '🔭', '价差与量化': '📊', '通用办公': '📁', '数据可视化': '📊', '科学分析': '🔬', '研发与调试': '💻', '基础流程': '🧭', '其他技能': '🧰' }
const builtinPresentation = item => Object.hasOwn(BUILTIN_SKILL_PRESENTATION, item.name) ? BUILTIN_SKILL_PRESENTATION[item.name] : undefined

export function skillEmoji(item) {
  if (validSkillEmoji(item.emoji)) return item.emoji
  const builtin = builtinPresentation(item)
  if (builtin) return builtin[0]
  // Titles are more specific than descriptions, which often mention adjacent workflows.
  const title = [item.displayName, ...Object.values(item.labels ?? {}), item.originalName, item.name].filter(Boolean).join(' ')
  const purpose = [item.purpose, item.description].filter(Boolean).join(' ')
  for (const text of [title, purpose]) {
    const match = EMOJI_RULES.find(([, pattern]) => pattern.test(text))
    if (match) return match[0]
  }
  const category = item.category?.replace(/^期现-/, '')
  return Object.hasOwn(CATEGORY_EMOJI, category) ? CATEGORY_EMOJI[category] : '🧰'
}

export function skillExample(item, locale = 'zh') {
  // A user-installed skill must never inherit an unrelated built-in example
  // just because it shares the built-in skill's technical name.
  const userInstalled = item.kind === 'skill' && isMyInstallation(item)
  const example = item.examples?.find(value => typeof value === 'string' && value.trim())
  if (userInstalled && example) return example
  if (locale.startsWith('zh') && !userInstalled) {
    // The newly curated catalog examples supersede old generic examples
    // even for skills that were already present in the bundled presentation table.
    if (item.name === 'ppt-master') return ''
    if (Object.hasOwn(CURATED_SKILL_EXAMPLES_ZH, item.name)) return CURATED_SKILL_EXAMPLES_ZH[item.name]
    const builtin = builtinPresentation(item)
    if (builtin) return builtin[1]
  }
  if (example) return example
  // An unknown native/bundled skill cannot be promised a use case without
  // inspecting what its actual SKILL.md supports: omit the sample instead.
  if (item.nativeSkill || item.builtinSource) return ''
  const name = skillLabel(item, locale)
  return locale.startsWith('zh') ? `请用「${name}」处理这项任务：[填写具体需求，并附上已有资料]。`
    : `Use “${name}” for this task: [describe your requirements and attach relevant files].`
}
