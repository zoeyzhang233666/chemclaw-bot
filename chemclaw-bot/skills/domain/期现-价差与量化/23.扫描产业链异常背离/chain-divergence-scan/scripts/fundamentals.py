# -*- coding: utf-8 -*-
"""第二层：把统计异常接回基本面与事件。

系统原则：
- 基本面数值优先用"自动核算"（来自同一份价格序列 + 明确公式），可复核、可重算；
- 行业口径数据（港口库存万吨、装置开工率）没有公开可复算的连续序列时，**只记录检索到的
  定性/时点事实与来源链接**，绝不编造数字；
- 事件只用于解释"为什么这段区间不一样"，不用于把相关性升级为因果，也不构成交易建议。
"""
import datetime

# ---------------------------------------------------------------------------
# 1. 事件库（截至 2026-10-20 检索到的公开信息，逐条带来源）
#    日期用于把事件定位到窗口；ticker 用于把事件指到具体品种
# ---------------------------------------------------------------------------
EVENTS = [
    dict(id='E01', ticker='MA0', date='2026-10-09', kind='政策/制裁',
         title='伊朗甲醇相关船舶被列入 SDN 清单，进口供应链担忧升温',
         detail='美国财政部海外资产控制办公室（OFAC）更新制裁名单，9 艘长期承运伊朗甲醇对华货源的船舶被列入 SDN，'
                '合计年运力超 400 万吨，据隆众资讯报道约占伊朗甲醇对华出口的 40%。',
         direction_hint='利多远月合约/抬升进口成本',
         source='S20'),
    dict(id='E02', ticker='MA0', date='2026-10-09', kind='库存',
         title='甲醇港口库存降至约 30 万吨，创历史新低（媒体报道口径）',
         detail='媒体 10 月 9 日报道称甲醇港口库存仅剩 30 万吨、创历史新低；'
                '另据券商/期货研报，霍尔木兹海峡封锁叠加伊朗冬季限气，四季度进口维持低位、港口持续去库。',
         direction_hint='现货偏紧，近月/基差走强',
         source='S21'),
    dict(id='E03', ticker='MA0', date='2026-10-12', kind='供需',
         title='国内供应回升、下游对高价接受度低，甲醇期现价格大幅回落',
         detail='盛达期货研报：国产供应增加，下游需求对高价接受度低；沿海 MTO 开工低位，传统下游综合利润好转、开工提升。',
         direction_hint='压制高价持续性',
         source='S22'),
    dict(id='E04', ticker='PX0', date='2026-10-08', kind='检修/供应',
         title='海外汽柴油偏强挤压亚洲 PX 负荷，PX/PTA 计划外检修增加，PX 主力涨停',
         detail='国庆期间地缘摩擦升温、成品油偏强，挤压亚洲（除中国外）PX 负荷；韩国、日本、中国台湾四季度有检修计划；'
                'PX 与 PTA 新增计划外检修，10 月 8 日 PX 主力大幅上涨至涨停。',
         direction_hint='PX 供应收紧，PX 相对 PTA 走强',
         source='S23'),
    dict(id='E05', ticker='TA0', date='2026-10-08', kind='检修/供应',
         title='华东 300 万吨与 150 万吨 PTA 装置 10 月初停车检修',
         detail='首创期货：供应方面，华东一条 300 万吨 PTA 装置 10 月初停车检修，另一条 150 万吨 10 月 6 日停车检修；'
                'PTA 社会库存与码头库存绝对水平仍处低位，成本端受原油上涨支撑。',
         direction_hint='供应收缩，短期偏强',
         source='S24'),
    dict(id='E06', ticker='TA0', date='2026-10-15', kind='供需',
         title='PTA 检修装置陆续重启，供需由紧平衡转向边际累库，旺季不及预期',
         detail='建信/中国金融信息网：PX 检修高峰尚未过去、原油地缘溢价仍在，但 PTA 检修装置重启、开工与周产量回升，'
                '下游纺织旺季不及预期，供需转向边际累库，价格上行空间受限。',
         direction_hint='压制 PTA 加工费',
         source='S25'),
    dict(id='E07', ticker='PP0', date='2026-10-14', kind='库存',
         title='中国聚丙烯商业库存 62.08 万吨，环比 -9.73%（生产企业 -11.34%）',
         detail='隆众口径：截至 2026-10-14 中国聚丙烯商业库存总量 62.08 万吨，较上期下降 6.69 万吨、环比 -9.73%；'
                '生产企业库存 -11.34%，样本贸易商库存 -8.02%，样本港口仓库 -1.73%。',
         direction_hint='低库存支撑现货与基差',
         source='S26'),
    dict(id='E08', ticker='PP0', date='2026-10-17', kind='成本/供应',
         title='丙烯价格强于 PP，"停 PP 卖丙烯"仍存，PP 产能利用率低位（约 65%）',
         detail='隆众预计下周 PP 计划内检修损失量窄幅下降，但临时故障频繁、供应回归缓慢，丙烯价格优势强于 PP；'
                '节后拉丝均价较节前上涨约 7.35%，需求端银十成色不足、补库持续性受限。'
                '另据华联观察，PP 前期集中检修使开工率偏低，四季度新增产能集中投放，中期供强需弱。',
         direction_hint='成本支撑 + 低库存，但需求弱',
         source='S26'),
    dict(id='E09', ticker='L0', date='2026-10-15', kind='供应',
         title='9 月国内 PE 产量 272.19 万吨（环比 -2.32%），PE 开工负荷 74.44%',
         detail='卓创资讯：9 月国内 PE 产量 272.19 万吨，其中 LLDPE 126.27 万吨；9 月 PE 开工负荷 74.44%，'
                '环比 +0.69pct、同比 -0.28pct；9 月 PE 石化企业检修损失量 57.52 万吨。10 月预计供应偏紧 + 刚性需求，'
                'LLDPE 价格重心或有上移，但中下旬需求转淡、海峡局势存不确定性。',
         direction_hint='供应偏紧，LLDPE 相对偏强',
         source='S27'),
    dict(id='E10', ticker='L0', date='2026-10-20', kind='现货',
         title='聚乙烯现货弱势整理，LLDPE 主流 9580-10080 元/吨（2026-10-20）',
         detail='百川盈孚：2026-10-20 国内聚乙烯市场均价 9770 元/吨，较前一工作日 -19 元/吨（-0.19%）；'
                'LLDPE 市场价 9580-10080 元/吨，HDPE 9230-9930，LDPE 12130-12780。',
         direction_hint='现货贴水走弱，成交未放量',
         source='S28'),
    dict(id='E11', ticker='EG0', date='2026-10-10', kind='库存',
         title='9 月乙二醇港口库存继续下探，现货流动性紧张加剧',
         detail='隆众：2026 年 9 月乙二醇国产量持续提升但进口到货维持低位，港口库存继续下降，'
                '现货流动性与基差走强；9 月产量预估 184.49 万吨（乙烯制 118.18 万吨、合成气制 66.31 万吨）。',
         direction_hint='低库存，EG 相对偏强',
         source='S29'),
    dict(id='E12', ticker='MA0', date='2026-10-08', kind='地缘',
         title='伊朗宣布霍尔木兹海峡关闭，原油与能化板块整体大幅上行',
         detail='多家机构与媒体提及 10 月 7-8 日伊朗宣称关闭霍尔木兹海峡，原油风险溢价抬升，能化品种普涨，'
                '成本端成为 10 月上旬主要驱动。',
         direction_hint='系统性成本冲击，抬升全部化工品',
         source='S23'),
]

# 主要期货品种受同一地缘/成本事件影响的时点（用于解释"相关上升而非下降"）
COMMON_SHOCK = dict(
    focus='2026-10-08',
    note='10 月 8 日节后首日，地缘溢价抬升叠加检修，国内化工品普遍大幅跳空上行'
         '（PP/L/PX/TA/MA 同日上涨 6%~10%），属"共同冲击"而非品种间传导',
)

# ---------------------------------------------------------------------------
# 2. 基本面框架（每个品种：库存/开工/供需/成本/事件 五问清单 + 可查口径）
# ---------------------------------------------------------------------------
FUND_TEMPLATE = {
    'PP0': dict(
        inventory='聚丙烯商业库存（生产企业 + 样本贸易商 + 港口），隆众资讯周度；两油聚烯烃库存（周度）',
        operating='PP 产能利用率（%），周度；周度检修损失量（万吨）',
        supply_demand='新增产能投放节奏（油制/PDH/MTO）、检修与临停、拉丝/纤维下游开工、出口窗口',
        cost='丙烯价格（外采聚合）、丙烷 CFR（PDH）、甲醇（MTO）、石脑油裂解价差',
        events_keys='E07,E08,E12'),
    'L0': dict(
        inventory='PE 石化企业库存 + 港口库存 + 贸易商库存，卓创资讯周度；LLDPE 分牌号库存',
        operating='PE 开工负荷（%），周度；检修损失量（万吨）；全密度装置 PE/HDPE/LLDPE 排产',
        supply_demand='PE 三者（LLDPE/LDPE/HDPE）裂解与排产结构、农膜/包装/注射下游开工、进口到港',
        cost='乙烯 CFR 东北亚、石脑油裂解价差、外采乙烯成本',
        events_keys='E09,E10,E12'),
    'PX0': dict(
        inventory='PX 社会库存、聚酯产业链 PX 库存；亚洲 PX 装置负荷（%）；PXN 价差',
        operating='PX 装置负荷/开工率（%）；亚洲（韩国、日本、中国台湾）PX 检修与调油分流',
        supply_demand='PX 新增产能（2026 年计划 650 万吨，集中下半年）、PTA 开工率对 PX 的需求',
        cost='石脑油 CFR 日本、MX（混合二甲苯）、PXN 价差（美元/吨）',
        events_keys='E04,E12'),
    'TA0': dict(
        inventory='PTA 社会库存 + 主港库存（周末万吨）；主力供应商现货基差',
        operating='PTA 开工率/产能利用率（%）；周度检修损失量',
        supply_demand='PTA 2026 年无新增产能、装置检修与重启节奏、聚酯开工率与产销、终端纺织订单',
        cost='PX（0.655 系数）加工费、醋酸、燃动成本',
        events_keys='E05,E06,E12'),
    'EG0': dict(
        inventory='华东主港 MEG 库存（万吨，周度）；港口到货量',
        operating='乙二醇总产能利用率（%）；乙烯制/合成气制产量结构',
        supply_demand='新增产能（巴斯夫湛江 83 万吨 2026-02 计入基数）、进口到港、聚酯开工',
        cost='乙烯 CFR、石脑油、煤价（合成气制）',
        events_keys='E11,E12'),
    'MA0': dict(
        inventory='甲醇港口库存（华东 + 华南，万吨，周度）；内地企业库存',
        operating='甲醇装置开工率（%）；气头限气、煤头检修',
        supply_demand='伊朗进口与制裁、国内新增产能、MTO/传统下游（甲醛、二甲醚、醋酸）开工',
        cost='动力煤/无烟煤、天然气（气头）、进口到岸成本',
        events_keys='E01,E02,E03,E12'),
    'V0': dict(
        inventory='PVC 生产企业库存 + 社会库存；华东/华南仓库库存',
        operating='PVC 开工率（%）；电石开工与价格',
        supply_demand='房地产/基建需求、出口（印度反倾销等）、电石法/乙烯法成本分化',
        cost='电石价格、氯碱综合利润、乙烯基差',
        events_keys='E12'),
    'JM0': dict(inventory='焦煤港口/钢厂/焦化厂库存', operating='煤矿开工率、洗煤厂开工',
                supply_demand='进口（蒙煤/澳煤）、安全监管、焦化利润', cost='坑口煤价、运费', events_keys=''),
    'J0': dict(inventory='焦炭港口/钢厂/焦化厂库存', operating='焦化产能利用率（%）、焦化利润',
               supply_demand='钢厂高炉开工、粗钢产量政策、环保限产', cost='炼焦煤（1.33 系数）+ 160 元/吨经验数',
               events_keys=''),
    'RB0': dict(inventory='螺纹钢社会库存 + 厂内库存', operating='钢厂高炉/电炉开工率、盈利率',
                supply_demand='地产新开工、基建、出口、粗钢平控', cost='铁水成本（焦炭 0.5 + 铁矿石 + 废钢）',
                events_keys=''),
    'BU0': dict(inventory='沥青厂库 + 社会库存', operating='炼厂沥青开工率、稀释沥青贴水',
                supply_demand='道路施工季节性、防水需求', cost='原油/稀释沥青、渣油价格', events_keys=''),
    'FU0': dict(inventory='新加坡/舟山燃料油库存', operating='炼厂开工、船燃需求',
                supply_demand='航运需求（BDI）、发电需求（中东）、俄罗斯出口', cost='原油、渣油、裂解价差',
                events_keys=''),
    'SA0': dict(inventory='纯碱厂库 + 社会库存', operating='纯碱开工率（%)、氨碱/联碱利润',
                supply_demand='浮法玻璃与光伏玻璃日熔量、进口到港', cost='原盐、合成氨、煤炭', events_keys=''),
    'UR0': dict(inventory='尿素厂库 + 港口库存', operating='尿素产能利用率（%）、气头限产',
                supply_demand='农业追肥/储备、复合肥开工、出口政策', cost='无烟煤/烟煤、天然气', events_keys=''),
    'EB0': dict(inventory='苯乙烯港口库存', operating='EB 开工率（%）', supply_demand='下游 EPS/ABS/PS 开工，纯苯/乙烯成本',
                cost='纯苯 CFR、乙烯 CFR', events_keys=''),
}

# ---------------------------------------------------------------------------
# 3. 基本面自动核算（只用可比价格 + 明确公式）
# ---------------------------------------------------------------------------


def fundamentals_for_pair(res, k=None, series=None):
    """对一对品种做"价格可复核的"基本面核算。

    返回的每一项都写明 formula（可直接在 Excel 里重算），不产生不可追溯的数字。
    """
    out = {}
    a, b = res['code_a'], res['code_b']
    ca, cb = res['close_a'], res['close_b']
    d = res['dates']
    pa0, pb0 = ca[-21], cb[-21] if len(ca) > 21 else (ca[0], cb[0])
    out['price'] = dict(
        a_last=ca[-1], b_last=cb[-1], date=d[-1],
        a_ret_20=ca[-1] / ca[-21] - 1 if len(ca) > 21 else None,
        b_ret_20=cb[-1] / cb[-21] - 1 if len(cb) > 21 else None,
        a_ret_60=ca[-1] / ca[-61] - 1 if len(ca) > 61 else None,
        b_ret_60=cb[-1] / cb[-61] - 1 if len(cb) > 61 else None,
        formula='收益率 = P_t / P_{t-N} - 1，N = 20/60 个交易日',
    )
    if k:
        out['processing_margin'] = dict(
            value=cb[-1] - k * ca[-1],
            unit='元/吨',
            formula=f'加工费/价差 = P_{b} - {k} × P_{a}（系数来自产业关系条目，仅作口径统一的近似）',
            v20=cb[-1] - k * ca[-1] - (cb[-21] - k * ca[-21]) if len(ca) > 21 else None,
            note='该系数是行业通用近似，非逐装置实测；且期货主力连续价格不等于厂库结算价',
        )
    if series is not None:
        sp = res['spread_series']
        if len(sp) > 60:
            out['spread_range'] = dict(v20=(min(sp[-20:]), max(sp[-20:])),
                                       v60=(min(sp[-60:]), max(sp[-60:])),
                                       all=(min(sp), max(sp)))
    out['checks'] = [(a, FUND_TEMPLATE.get(a, {})), (b, FUND_TEMPLATE.get(b, {}))]
    return out


def events_in_window(start, end, tickers):
    sel = []
    for e in EVENTS:
        if e['ticker'] in tickers and start <= e['date'] <= end:
            sel.append(e)
    sel.sort(key=lambda x: x['date'])
    return sel


def window_span(dates, n):
    """最近 n 个交易日的起止日期。"""
    if not dates:
        return None, None
    n = min(n, len(dates))
    return dates[-n], dates[-1]
