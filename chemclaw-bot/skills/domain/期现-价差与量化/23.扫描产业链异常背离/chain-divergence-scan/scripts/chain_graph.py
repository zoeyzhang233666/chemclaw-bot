# -*- coding: utf-8 -*-
"""产业链图谱（化工品种池）与候选配对构建规则。

本文件是"扫描产业链异常背离"的**第一层**：先用真实产业关系筛出有业务意义的配对，
再做统计扫描。所有关系条目都带 relation_type / strength / direction / source。

relation_type 取值（与 references/01-产业关系类型与配对规则.md 一致）：
  upstream_downstream  直接上下游（A 是 B 的直接原料/产品）
  common_feedstock     共用同一主要原料（如 PP 与 LLDPE 共用丙烯/乙烯链、MTO 甲醇）
  substitute           替代关系（同一终端应用可互换）
  same_process_output  同一装置/同一工艺的联产或多用途切换（如全密度装置 PE 牌号切换）
  proxy_same_end_use   与终端需求同为聚酯/农业等同一下游，但非直接原料关系（弱关系，仅作背景）
  cross_chain_cost     跨链条成本传导（原料端同源、成本共振，非直接物料关系）
"""
import json
import os

# ---------------------------------------------------------------------------
# 1. 品种池
# ---------------------------------------------------------------------------
# 单位统一为元/吨（期货主力连续收盘价）。
# weight_basis: 计算"标准化价格变化"与价差/比价时使用的量纲基准（吨计）
UNIVERSE = [
    # code, name, exchange_prefix, category, chain, contract_multiplier_t
    dict(code='PP0',  name='聚丙烯 PP',            cat='聚烯烃-塑料',   chain='丙烯链(PP)',        mult=5,
         spec='大商所聚丙烯期货主力连续，元/吨'),
    dict(code='L0',   name='线型低密度聚乙烯 LLDPE', cat='聚烯烃-塑料',   chain='乙烯链(PE)',        mult=5,
         spec='大商所 LLDPE 期货主力连续，元/吨'),
    dict(code='V0',   name='聚氯乙烯 PVC',          cat='聚烯烃-塑料',   chain='电石/乙烯法PVC',    mult=5,
         spec='大商所 PVC 期货主力连续，元/吨'),
    dict(code='PX0',  name='对二甲苯 PX',           cat='芳烃-聚酯原料', chain='芳烃链(PX)',        mult=5,
         spec='郑商所 PX 期货主力连续，元/吨（2023-09 上市，历史仅约 2.9 年）'),
    dict(code='TA0',  name='精对苯二甲酸 PTA',       cat='芳烃-聚酯原料', chain='芳烃链(PTA)',       mult=5,
         spec='郑商所 PTA 期货主力连续，元/吨'),
    dict(code='EG0',  name='乙二醇 MEG',            cat='芳烃-聚酯原料', chain='乙烯链(EG)',        mult=10,
         spec='大商所 乙二醇期货主力连续，元/吨'),
    dict(code='MA0',  name='甲醇 MA',               cat='能源化工-醇',   chain='甲醇(煤/气/油)',    mult=10,
         spec='郑商所 甲醇期货主力连续，元/吨'),
    dict(code='EB0',  name='苯乙烯 EB',             cat='芳烃-苯链',     chain='苯乙烯链',          mult=5,
         spec='大商所 苯乙烯期货主力连续，元/吨'),
    dict(code='SA0',  name='纯碱 SA',               cat='无机化工-两碱',  chain='联碱/氨碱',         mult=20,
         spec='郑商所 纯碱期货主力连续，元/吨'),
    dict(code='UR0',  name='尿素 UR',               cat='化肥',          chain='煤制化肥',          mult=20,
         spec='郑商所 尿素期货主力连续，元/吨'),
    dict(code='J0',   name='焦炭 J',                cat='煤焦',          chain='煤焦钢',            mult=100,
         spec='大商所 焦炭期货主力连续，元/吨'),
    dict(code='JM0',  name='焦煤 JM',               cat='煤焦',          chain='煤焦钢',            mult=60,
         spec='大商所 焦煤期货主力连续，元/吨'),
    dict(code='RB0',  name='螺纹钢 RB',             cat='黑色',          chain='煤焦钢',            mult=10,
         spec='上期所 螺纹钢期货主力连续，元/吨'),
    dict(code='BU0',  name='沥青 BU',               cat='油品-沥青',     chain='原油-沥青',         mult=10,
         spec='上期所 沥青期货主力连续，元/吨'),
    dict(code='FU0',  name='燃料油 FU',             cat='油品',          chain='原油-燃料油',       mult=10,
         spec='上期所 燃料油期货主力连续，元/吨'),
]

CODE2 = {u['code']: u for u in UNIVERSE}

# ---------------------------------------------------------------------------
# 2. 产业关系条目（只写"有业务意义"的关系）
#    每条都是双向可查询的；这里按品种对唯一存储一次。
#    k            : 经济/工艺系数（比价或价差换算用），含义见 coef_note
#    coef_kind    : ratio (B/A 合理中枢，用于价差 = B - k*A) / None（不做价差，仅做比价）
# ---------------------------------------------------------------------------
RELATIONS = [
    # ---------------- 用户指定重点组合 ----------------
    dict(a='PP0', b='L0', rtype='substitute', strength='strong',
         direction='unclear',
         a_role='国内 PP 主要原料来源：油制(石脑油裂解/催化裂化)、MTO(甲醇制烯烃)、PDH(丙烷脱氢)、'
                '外购丙烯聚合',
         b_role='国内 PE（含全密度装置）主要原料来源：石脑油裂解乙烯、MTO 乙烯；全密度装置可灵活切换 PE/PP 牌号',
         mechanism='终端替代：注塑件、包装中空件、薄膜与编织包装相互替代；共同上游为"烯烃"（石脑油/甲醇/丙烷/炼厂丙烯），'
                   '成本端同受原油与煤炭驱动，但丙烯端额外受丙烷、甲醇、PDH 新增产能影响',
         k=None, coef_kind=None,
         market_convention='业内常以 LLDPE − PP 价差（元/吨）与 LLDPE/PP 比价监测；两者强弱分化主要来自各自投产周期与开工率差异',
         source_ids=['S1', 'S2', 'S3', 'S4', 'S8'],
         comparability='中：均为大商所同一交易所、元/吨、主力连续；但 PP 与 L 的主力合约月份与换月节奏存在差异'),
    dict(a='PX0', b='TA0', rtype='upstream_downstream', strength='strong',
         direction='b_follows_a',
         a_role='PTA 的直接原料（PX 经醋酸溶剂空气氧化 → CTA → 加氢精制 → PTA）',
         b_role='PX 的最大单一下游（中国 PX 消费绝大多数流向 PTA）',
         mechanism='加工费（PTA 现货价 − 0.655×PX 折算价）是两品种价差的产业锚；PX 检修/新增产能与 PTA 开工率决定加工费',
         k=0.655, coef_kind='ratio',
         market_convention='PTA 加工费 ≈ PTA − 0.655×PX（行业通用计算系数，化学计量下限约 0.639）',
         source_ids=['S5', 'S6', 'S7', 'S9'],
         comparability='中低：PX 期货 2023-09 上市，可比重叠历史仅约 2.9 年；两品种均为郑商所、元/吨'),

    # ---------------- 共用原料 / 替代 ----------------
    dict(a='MA0', b='PP0', rtype='upstream_downstream', strength='medium',
         direction='b_follows_a',
         a_role='MTO（甲醇制烯烃）路线 PP 的直接原料',
         b_role='甲醇的化工下游之一（MTO/MTP），另有大量 PP 产能为油制与 PDH 路线',
         mechanism='仅 MTO 路线存在直接物料关系，MTO 利润（PP − 约 2.9×甲醇，粗略折算）影响 MTO 装置开工与外采甲醇需求',
         k=2.9, coef_kind='ratio',
         market_convention='业界常用 MTO 利润价差监测；生产 1 吨烯烃约耗 3 吨甲醇（系数随工艺/催化剂/产品结构变化），MTO 装置同产 PE 与 PP，不构成单一的 PP−MA 物料关系',
         source_ids=['S1', 'S3', 'S10'],
         comparability='中低：PP 只有部分产能是 MTO 路线，物料关系被油制/PDH 稀释'),
    dict(a='MA0', b='L0', rtype='cross_chain_cost', strength='weak',
         direction='unclear',
         a_role='MTO 乙烯路线 PE 的原料',
         b_role='甲醇下游之一（MTO 乙烯 → PE）',
         mechanism='仅 MTO 乙烯路线 PE 存在物料关系，占比低于 PP 的 MTO 占比；多数为成本共振',
         k=None, coef_kind=None,
         market_convention='一般不做直接价差，仅在 MTO 利润口径下联看',
         source_ids=['S1', 'S3'],
         comparability='低：直接物料占比小，主要靠原油/煤炭成本共振'),
    dict(a='MA0', b='EG0', rtype='cross_chain_cost', strength='weak',
         direction='unclear',
         a_role='国内煤制/外购甲醇 MTO-EG 路线 EG 的原料',
         b_role='甲醇下游之一（MTO-EG）',
         mechanism='国内 EG 以乙烯法（石脑油/煤制烯烃）为主，甲醇直接相关产能有限，属成本共振型关系',
         k=None, coef_kind=None,
         market_convention='以乙二醇利润（EG − 乙烯×系数）监测，少见与甲醇直接价差',
         source_ids=['S1'],
         comparability='低：物料相关性弱'),
    dict(a='TA0', b='EG0', rtype='common_feedstock', strength='medium',
         direction='unclear',
         a_role='聚酯（PET）二元酸单体',
         b_role='聚酯（PET）二元醇单体',
         mechanism='同为聚酯产业链主要原料（合计约占聚酯成本 85%~90%），共同下游为聚酯/涤纶长丝/瓶片；'
                   '两者强弱分化反映"酸端"与"醇端"供需差',
         k=None, coef_kind=None,
         market_convention='业内常用 PTA/EG 比价或 PTA − a×EG 监测聚酯成本结构',
         source_ids=['S6', 'S7', 'S11'],
         comparability='中：大商所(EG)与郑商所(PTA)分属不同交易所，主力月与交割规则不同，但均元/吨'),
    dict(a='PX0', b='EG0', rtype='cross_chain_cost', strength='weak',
         direction='unclear',
         a_role='同为石脑油/重整与裂解链条产物（PX 来自重整/歧化，EG 来自乙烯氧化）',
         b_role='同上',
         mechanism='无直接物料关系，主要经"石脑油—芳烃/烯烃"炼化一体化利润与原油成本共振',
         k=None, coef_kind=None, market_convention='一般仅作背景，不建价差',
         source_ids=['S5', 'S11'],
         comparability='低：PX 历史短，EG 2018-12 起'),
    dict(a='EB0', b='MA0', rtype='cross_chain_cost', strength='weak',
         direction='unclear',
         a_role='苯乙烯（苯 + 乙烯）',
         b_role='MTO 可提供乙烯/苯侧原料',
         mechanism='仅少量外购型苯乙烯装置与甲醇/乙烯相关；主因同为原油与烯烃成本共振',
         k=None, coef_kind=None, market_convention='通常不做直接价差',
         source_ids=['S1'],
         comparability='低'),
    dict(a='PP0', b='V0', rtype='substitute', strength='medium',
         direction='unclear',
         a_role='PP：管材、板材、注塑件、包装',
         b_role='PVC：型材、管材、地板、电缆料（受房地产/基建主导）',
         mechanism='管材/板材/型材等建材领域存在部分替代，但 PVC 需求端与地产强绑定，PP 更偏消费包装，'
                   '成本端差异大（PVC 电石法与乙烯法，PP 为丙烯聚合）',
         k=None, coef_kind=None,
         market_convention='偶有 PP/PVC 比价研究，替代弹性有限',
         source_ids=['S2', 'S12'],
         comparability='中：均为大商所、元/吨，但产业驱动不同，关系稳定性弱'),
    dict(a='L0', b='V0', rtype='substitute', strength='medium',
         direction='unclear',
         a_role='LLDPE：包装薄膜、农膜',
         b_role='PVC：管材型材（软制品用 PVC 与 PE 薄膜在部分包装/农用膜场景互替）',
         mechanism='农膜、包装膜领域存在部分替代；PVC 另有电石法成本逻辑',
         k=None, coef_kind=None, market_convention='替代逻辑弱，通常仅作背景',
         source_ids=['S2', 'S12'],
         comparability='中：均大商所、元/吨'),

    # ---------------- 煤焦钢（同链条上下游，作为对照） ----------------
    dict(a='JM0', b='J0', rtype='upstream_downstream', strength='strong',
         direction='b_follows_a',
         a_role='炼焦煤，焦炭的直接原料（炼焦配煤，吨焦约耗 1.3~1.33 吨炼焦煤）',
         b_role='炼焦煤的最大下游（约 1.3~1.4 吨焦煤/吨焦炭，受配比影响）',
         mechanism='焦化利润 = 焦炭 − 配煤成本；焦煤供给（进口/安检）与焦化开工决定利润',
         k=1.33, coef_kind='ratio',
         market_convention='业内看焦化利润 = 焦炭 − 1.33×焦煤（经验公式），系数随配煤结构变动，不宜机械使用',
         source_ids=['S13'],
         comparability='高：均为大商所、元/吨，历史重叠长'),
    dict(a='J0', b='RB0', rtype='upstream_downstream', strength='medium',
         direction='b_follows_a',
         a_role='高炉炼铁还原剂与燃料',
         b_role='螺纹钢（长流程：焦炭 → 铁水 → 粗钢 → 螺纹）',
         mechanism='钢材利润（钢厂盈利率）反向影响焦炭采购；供给侧（粗钢压减/环保限产）常造成阶段性背离',
         k=None, coef_kind=None,
         market_convention='多用螺焦比价与钢厂利润监测',
         source_ids=['S13'],
         comparability='高：均为元/吨，跨交易所（大商所/上期所）'),
    dict(a='JM0', b='RB0', rtype='cross_chain_cost', strength='weak',
         direction='unclear',
         a_role='', b_role='', mechanism='经焦炭转导的二级成本关系', k=None, coef_kind=None,
         market_convention='一般不直接用，仅作背景', source_ids=['S13'], comparability='中'),

    # ---------------- 油品、盐化工 ----------------
    dict(a='BU0', b='FU0', rtype='substitute', strength='weak',
         direction='unclear',
         a_role='原油一次加工副产物（减压渣油为主）',
         b_role='原油一次加工副产物（减压渣油/燃料油混调）',
         mechanism='同为原油下游重质油品，原料端（渣油、稀释沥青）与炼厂排产可相互挤占；需求端完全不同（道路 vs 船燃/发电）',
         k=None, coef_kind=None,
         market_convention='偶用作炼厂利润监测，关系不稳定',
         source_ids=['S14'],
         comparability='低：主力换月与季节性差异大'),
    dict(a='SA0', b='UR0', rtype='common_feedstock', strength='medium',
         direction='unclear',
         a_role='联碱法（氨碱法/联产氯化铵）与氨碱法纯碱，以原盐 + 合成氨/CO2 为宜',
         b_role='尿素以合成氨 + CO2 合成',
         mechanism='共同依赖合成氨/无烟煤成本，联碱企业同时产出纯碱与氯化铵，与尿素存在氮肥替代（氯化铵替代尿素）',
         k=None, coef_kind=None,
         market_convention='业内关注氯化铵-尿素价差，纯碱与尿素本身无直接价差',
         source_ids=['S15'],
         comparability='中：郑商所同一交易所、元/吨，但产业链不直接相连'),
    dict(a='MA0', b='UR0', rtype='common_feedstock', strength='weak',
         direction='unclear',
         a_role='煤化工：均以煤（无烟煤/烟煤）为主要原料',
         b_role='同上',
         mechanism='同为煤化工，成本端（煤价、气价政策）共振，物料无直接关系',
         k=None, coef_kind=None, market_convention='仅成本背景',
         source_ids=['S10', 'S15'], comparability='中'),
]

# 关系类型中文与业务说明
RTYPE_INFO = {
    'upstream_downstream': dict(cn='上下游', order=1,
                                desc='A 是 B 的直接原料/产品，存在明确物料流与加工利润关系'),
    'common_feedstock': dict(cn='共用原料', order=2,
                             desc='两品种主要原料相同，物料关系不直接但成本同源，常是聚酯/烯烃配对的主逻辑'),
    'substitute': dict(cn='替代', order=3,
                       desc='在部分终端应用中可互换，替代弹性有限，关系稳定性弱于物料关系'),
    'same_process_output': dict(cn='同装置切换', order=4,
                                desc='同一装置/工艺多用途切换（如全密度装置 PE 与 PP 切换）'),
    'cross_chain_cost': dict(cn='成本共振', order=5,
                             desc='无直接物料或替代关系，仅因原料端（原油/煤炭/石脑油）同源共振；按规则不进主榜单'),
}

# ---------------------------------------------------------------------------
# 3. 配对构建规则
# ---------------------------------------------------------------------------
PAIR_RULES = dict(
    min_strength_for_primary=['strong', 'medium'],   # 主榜单准入
    weak_relation_report_only=True,                  # weak 关系只做背景，不进主榜单
    min_overlap_days=250,                            # 两品种可比重叠交易日下限
    note='候选组合必须先满足产业关系（RELATIONS 中 rtype 属于允许集合、strength 达标、来源可查），'
         '再进入统计扫描；不对无产业关联的品种做全组合搜索，以避免 p-hacking。',
)


def build_pairs():
    """返回去重后的候选关系列表（保留无重复的 relations）。"""
    out, seen = [], set()
    for r in RELATIONS:
        if r.get('_duplicate'):
            continue
        key = tuple(sorted([r['a'], r['b']])) + (r['rtype'],)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


if __name__ == '__main__':
    pairs = build_pairs()
    print('universe', len(UNIVERSE), 'relations', len(pairs))
    for r in pairs:
        print(r['a'], r['b'], r['rtype'], r['strength'])
