const RELATIONSHIP_QUESTION = /为什么|为何|成因|主要原因|背后的原因|产业链|供应链|价值链|上中下游|传导|作用机制|工作原理|来龙去脉|因果|依赖关系|决策|排查|方案对比|优缺点|实施(?:路径|步骤|流程)|生产流程|处理流程|(?:怎么|如何|怎样)(?:选|做|判断|制定|排查|运作|形成|执行|实现|处理|应对|安排|解释)|\b(?:why|root causes?|trade[- ]offs?|supply chain|value chain|workflow|decision (?:tree|path)|mechanism|how (?:does|do|to|would))\b/iu
const ANALYSIS_CUE = /原因|机制|逻辑|路径|瓶颈|依赖|传导|约束|方案|步骤|相互|导致|条件|权衡|\b(?:causes?|mechanism|logic|drivers?|depends?|constraints?|steps?|trade[- ]offs?)\b/iu
const GREETING = /^\s*(?:你好|您好|哈[喽啰]|嗨|在吗|早上好|晚上好|谢谢|收到|好[的呀]|hi|hello|hey|thanks|ok)[\p{P}\s]*$/iu
const DATA_LOOKUP = /(?:价格|报价|行情|产量|销量|库存|持仓量|产能|市场份额)(?:走势|分布|排行|历史|数据|查询|对比)|(?:趋势|历史|最近|过去|近[一二三两四五六七八九十\d]+).{0,20}(?:价格|报价|行情|产量|销量|库存|持仓量|产能)|\b(?:price history|historical prices|production (?:volume|distribution)|market share)\b/iu
const ANSWER_STRUCTURE = /^\s*(?:#{1,5}[ \t]+|\d{1,2}[.、)）][ \t]*|[-*][ \t]+)/gmu
const FENCE = /^ {0,3}\x60{3}[^\n]*\n[\s\S]*?^ {0,3}\x60{3}[ \t]*\r?$/gmu
const CAPACITY_METRIC = /产能|产量|开工率|装置利用率|配额|\b(?:production (?:capacity|volume)|installed capacity|operating rate|capacity utili[sz]ation|(?:export|production) quota)\b/iu
const QUANTITATIVE_CUE = /多少|几成|数值|数据|对比|比较|排名|排行|规模|走势|趋势|各地|各省|各国|各地区|\b(?:how (?:much|many)|data|compare|ranking|trend|by (?:region|country|company))\b/iu
const CAPACITY_UNIT = /\d+(?:[.,]\d+)*\s*(?:%|％|(?:亿|万|千)?(?:吨|桶|立方米|方|加仑)|(?:million\s+|thousand\s+)?(?:metric\s+)?(?:tonnes?|tons?|barrels?|bpd|mtpa|ktpa)\b)/iu

export function capacityDataRequest(question) {
  if (!CAPACITY_METRIC.test(question)) return false
  if (/什么意思|什么叫|怎么(?:计算|定义)|如何(?:计算|定义)|有何区别|\b(?:definition|what (?:does .+ mean|is meant by)|how (?:to|do .*?) calculate)\b/iu.test(question)) return false
  return QUANTITATIVE_CUE.test(question) || !RELATIONSHIP_QUESTION.test(question)
}

export function capacityMeasurementsInAnswer(answer) {
  const prose = answer.replace(FENCE, '')
  return CAPACITY_METRIC.test(prose) && CAPACITY_UNIT.test(prose)
}

export const needsSvgIllustration = question => /剖面(?:图|结构|示意)|截面(?:结构|示意)|空间(?:位置|结构|排布)|形态(?:对比|示意)|零件(?:位置|分布)|矢量(?:图|插图)|\b(?:cross[- ]section|cutaway|vector illustration|spatial arrangement)\b/iu.test(question)
export const asksForRelationships = question => RELATIONSHIP_QUESTION.test(question)
export const isQuantitativeLookup = question => capacityDataRequest(question) || DATA_LOOKUP.test(question)

export function needsFlowDiagram(question, answer = '', dataDelivered = false) {
  if (GREETING.test(question)) return false
  if (capacityDataRequest(question)) return false
  if (RELATIONSHIP_QUESTION.test(question)) return true
  if (isQuantitativeLookup(question) || dataDelivered) return false
  const prose = answer.replace(FENCE, '')
  return (prose.match(/→|⇒/gu)?.length ?? 0) >= 2
    || (ANALYSIS_CUE.test(prose) && Array.from(prose.matchAll(ANSWER_STRUCTURE)).length >= 3)
}
