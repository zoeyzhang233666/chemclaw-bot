const RELATIONSHIP_QUESTION = /为什么|为何|成因|主要原因|背后的原因|产业链|供应链|价值链|上中下游|传导|作用机制|工作原理|来龙去脉|因果|依赖关系|决策|排查|方案对比|优缺点|实施(?:路径|步骤|流程)|生产流程|处理流程|(?:怎么|如何|怎样)(?:选|做|判断|制定|排查|运作|形成|执行|实现|处理|应对|安排|解释)|\b(?:why|root causes?|trade[- ]offs?|supply chain|value chain|workflow|decision (?:tree|path)|mechanism|how (?:does|do|to|would))\b/iu
const ANALYSIS_CUE = /原因|机制|逻辑|路径|瓶颈|依赖|传导|约束|方案|步骤|相互|导致|条件|权衡|\b(?:causes?|mechanism|logic|drivers?|depends?|constraints?|steps?|trade[- ]offs?)\b/iu
const GREETING = /^\s*(?:你好|您好|哈[喽啰]|嗨|在吗|早上好|晚上好|谢谢|收到|好[的呀]|hi|hello|hey|thanks|ok)[\p{P}\s]*$/iu
const DATA_LOOKUP = /(?:价格|行情|产量|销量|库存|持仓量|产能|市场份额)(?:走势|分布|排行|历史|数据|查询)|\b(?:price history|production (?:volume|distribution)|market share)\b/iu
const ANSWER_STRUCTURE = /^\s*(?:#{1,5}[ \t]+|\d{1,2}[.、)）][ \t]*|[-*][ \t]+)/gmu
const FENCE = /^ {0,3}\x60{3}[^\n]*\n[\s\S]*?^ {0,3}\x60{3}[ \t]*\r?$/gmu

export function needsFlowDiagram(question, answer = '') {
  if (GREETING.test(question)) return false
  if (RELATIONSHIP_QUESTION.test(question)) return true
  if (DATA_LOOKUP.test(question)) return false
  const prose = answer.replace(FENCE, '')
  return (prose.match(/→|⇒/gu)?.length ?? 0) >= 2
    || (ANALYSIS_CUE.test(prose) && Array.from(prose.matchAll(ANSWER_STRUCTURE)).length >= 3)
}
