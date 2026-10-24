# -*- coding: utf-8 -*-
"""
示例骨架：纯碱（SA，郑商所）—— 演示"换品种"时只需换数据，不碰渲染代码。

⚠ 重要说明
  本文件是【结构与变量选择思路】的示范，不是一份已完成的研究。
  其中标注 "待核实" 的数值需要在正式使用时用当日真实数据替换；
  references/数据缺失处理规则.md 要求：核实前一律写 "数据缺失"。
  —— 这里保留 "待核实" 是为了让你看清每个格子里该填什么。

  运行方式：
      python scripts/make.py --payload examples/示例-纯碱-骨架/payload_纯碱.py \
          --html examples/示例-纯碱-骨架/index.html \
          --xlsx examples/示例-纯碱-骨架/纯碱-变量观察.xlsx

  设计要点：纯碱与甲醇的变量结构差异
     甲醇：进口断供 + 港口低库存 + MTO 负反馈（供需双端剧烈）
     纯碱：产能大幅扩张 + 光伏/浮法玻璃需求 + 高库存（供给过剩型）
  因此两者的入选变量完全不同——这正是"变量由实际数据决定"的体现。
"""

AS_OF = "<<<填写数据截止日，如 2026-10-19>>>"

META = {
    "commodity": "纯碱（SA，郑商所）",
    "cycle": "<<<研究周期，如：未来1个月>>>",
    "as_of": AS_OF,
    "window_start": "<<<起>>>",
    "window_end": "<<<止>>>",
    "analyst": "期现研究",
    "version": "v0.1-骨架",
    "contract_focus": "<<<主力合约、基差口径>>>",
    "region_focus": "华东（江苏、连云港）为主销区；西北（青海、内蒙古）为低成本产区；华北（河北）为玻璃需求地",
    "price_basis": "现货为出厂/送到含税价；期货为主力收盘；基差=沙河/华东重碱-主力",
    "research_position": "期现兼顾",
}

# ---------------------------------------------------------------------
# 与甲醇的关键差异：纯碱的价格弹性主要来自【产能投放节奏】与【重碱需求(玻璃)】，
# 而非进口或港口库存。因此候选池的重点完全不同。
# ---------------------------------------------------------------------
SNAPSHOT = [
    dict(indicator="纯碱企业库存（隆众口径）",
         value="待核实（万吨，日期）",
         recent="待核实（环比/同比）",
         history="待核实（近五年分位）",
         scope="隆众：企业库存合计",
         source="<<<隆众周报 + 日期>>>"),
    dict(indicator="纯碱行业开工率 / 周产量",
         value="待核实（% / 万吨，日期）",
         recent="待核实",
         history="待核实",
         scope="隆众全样本",
         source="<<<隆众周报>>>"),
    dict(indicator="重碱下游：浮法玻璃在产日熔量",
         value="待核实（万吨/日，日期）",
         recent="待核实（冷修/点火）",
         history="待核实",
         scope="隆众/卓创在产产能口径",
         source="<<<卓创 + 日期>>>"),
    dict(indicator="光伏玻璃在产日熔量",
         value="待核实（万吨/日，日期）",
         recent="待核实",
         history="待核实",
         scope="隆众/卓创",
         source="<<<隆众 + 日期>>>"),
    dict(indicator="纯碱现货（重碱/轻碱）与基差",
         value="待核实（元/吨，日期）",
         recent="待核实",
         history="待核实",
         scope="沙河/华东送到价；基差=现货-主力",
         source="<<<生意社/隆众>>>"),
    dict(indicator="原盐与煤炭成本 / 联碱、氨碱利润",
         value="待核实",
         recent="待核实",
         history="待核实",
         scope="按工艺分列（氨碱/联碱/天然碱）",
         source="<<<隆众/卓创>>>"),
]

# ---------------------------------------------------------------------
# 事件：纯碱的关注点是"投产节点 + 冷修/点火 + 库存周报"
# ---------------------------------------------------------------------
EVENTS = [
    dict(date="<<<YYYY-MM-DD>>>", date_label="<<<>>",
         title="纯碱企业库存周报（隆众/卓创，通常周四）",
         kind="定期数据", cat="库存",
         certainty="固定周度发布节奏",
         impact="直接反映供给过剩是否延续，决定库存拐点",
         source="隆众/卓创"),
    dict(date="<<<YYYY-MM-DD>>>", date_label="<<<>>",
         title="<<<新增产能投放节点（如某 100 万吨/年装置计划投产）>>>",
         kind="已披露·时点模糊", cat="供给",
         certainty="计划投产，实际以装置动态与产量爬坡为准",
         impact="若兑现将抬高月度供给，压制现货",
         source="<<<来源 + 日期>>>"),
    dict(date="<<<YYYY-MM-DD>>>", date_label="<<<>>",
         title="<<<浮法/光伏玻璃产线冷修或点火>>>",
         kind="条件触发·观察窗", cat="需求",
         certainty="计划冷修/点火，时点不确定；不代表必然按期发生",
         impact="影响重碱日耗，是需求端主要边际变化来源",
         source="<<<来源>>>"),
]

# ---------------------------------------------------------------------
# 候选池：注意与甲醇的差异
# ---------------------------------------------------------------------
CANDIDATES = [
    dict(name="企业库存（隆众/卓创）", cat="库存", verifiability="高（周度、双源）", selected=True,
         reason="供给过剩型品种的定价核心：库存方向决定现货压力与基差"),
    dict(name="重碱需求：玻璃在产日熔量", cat="需求", verifiability="高（周度，冷修/点火可追踪）", selected=True,
         reason="重碱约一半需求在玻璃，日熔量是最直接的刚需代理"),
    dict(name="开工率与周产量", cat="供给", verifiability="高（周度）", selected=True,
         reason="高利润能否维持高开工，决定供给弹性；检修季有季节性"),
    dict(name="新增产能投放节奏", cat="供给", verifiability="中（计划公开，实际爬坡难核实）", selected=True,
         reason="产能集中投放期，新装置的达产速度决定过剩加深程度"),
    dict(name="纯碱现货与基差", cat="价差", verifiability="高（日频）", selected=True,
         reason="高库存常伴随期货贴水/现货垮塌，基差是压力的直接读数"),
    dict(name="原盐/煤炭成本", cat="成本", verifiability="高", selected=False,
         reason="成本决定现金成本支撑，但短期不如库存与需求弹性大，列为二级观察"),
    dict(name="轻碱/重碱价差", cat="价差", verifiability="高", selected=False,
         reason="可反映重碱需求相对强弱，但与日熔量高度相关，暂作二级观察"),
]

VARIABLES = [
    dict(
        vid="V1", name="企业库存方向——过剩是否还在加深",
        cat="库存", rank=1, importance=5, verifiability=5, urgency=5,
        horizon="周度（周四）",
        current="待核实（万吨，日期）",
        recent_change="待核实",
        history_pos="待核实（近五年分位）",
        why="高库存+产能扩张下，库存拐点是纯碱最强的定价信号：去库对应现货企稳，累库对应进一步压价",
        mechanism="产能投放/开工 → 周产量 → 企业库存 → 现货报价与基差 → 盘面",
        key_data="①企业库存总量②分区域库存③厂家待发订单④纯碱库存天数",
        verify_yes="连续 3 周去库且降幅 >3%，同时现货报价止跌 → 过剩压力缓解，原“累库压价”判断需上调",
        verify_no="库存再创历史新高或单周增幅 >5% → 供给过剩加深，原判断得到强化",
        invalidate="若口径调整（样本扩容）或厂家转出口导致库存下降但国内供给未变，则不能以库存下降推断供给收缩",
        source="<<<隆众/卓创 + 日期>>>",
        freq="周度",
        next_date="<<<明确日期或“每周四”>>>",
        confidence="高（双源交叉）",
        gap="两口径样本不同，绝对量不可混用；分区域库存部分需付费",
    ),
    dict(
        vid="V2", name="玻璃日熔量——重碱刚需的边际",
        cat="需求", rank=2, importance=5, verifiability=4, urgency=4,
        horizon="周度",
        current="待核实",
        recent_change="待核实（冷修/点火净变动）",
        history_pos="待核实",
        why="重碱需求主要跟随浮法与光伏玻璃日熔量；冷修或点火是需求端最直接的边际变量",
        mechanism="日熔量 → 重碱日耗 → 纯碱采购 → 企业库存",
        key_data="①浮法在产日熔量②光伏在产日熔量③冷修/点火计划④玻璃厂纯碱库存天数",
        verify_yes="日熔量净下降 >1% 且玻璃厂补库意愿下降 → 需求走弱，原判断需下调",
        verify_no="日熔量净上升或冷修推迟 → 需求韧性仍在",
        invalidate="若玻璃厂以轻碱替代或降低纯碱单耗，则日熔量与纯碱需求的关系弱化",
        source="<<<来源>>>",
        freq="周度",
        next_date="待填写：每周四（库存/开工）/ 每日（价格）",
        confidence="高",
        gap="光伏产线投产进度披露滞后",
    ),
    dict(
        vid="V3", name="开工率与周产量——供给弹性",
        cat="供给", rank=3, importance=4, verifiability=5, urgency=4,
        horizon="周度",
        current="待核实",
        recent_change="待核实",
        history_pos="待核实",
        why="高利润下企业倾向满负荷；检修与复产节奏决定周度边际供给",
        mechanism="利润 → 开工 → 周产量 → 库存",
        key_data="①全行业开工②分工艺开工（氨碱/联碱/天然碱）③检修损失量",
        verify_yes="开工率较前周下降 >3pct 且多装置检修，供给收缩",
        verify_no="开工维持高位且新装置达产，供给继续释放",
        invalidate="企业装置开停不公告，开工样本变动导致口径不一致",
        source="<<<来源>>>", freq="周度", next_date="待填写：每周四（库存/开工）/ 每日（价格）",
        confidence="中", gap="开工为估算样本，非全口径统计",
    ),
    dict(
        vid="V4", name="现货与基差——压力的直接读数",
        cat="价差", rank=4, importance=4, verifiability=5, urgency=4,
        horizon="日频",
        current="待核实",
        recent_change="待核实",
        history_pos="待核实",
        why="高库存下的现货垮塌与基差走势，比任何预测更直接反映真实压力",
        mechanism="库存 → 现货报价 → 基差 → 盘面与套保",
        key_data="①沙河/华东重碱②轻碱③基差④月差",
        verify_yes="现货连续下跌且基差走弱至 -200 以下",
        verify_no="现货企稳且基差修复",
        invalidate="区域价差过大时统一用沙河或华东同一基准，不可混用",
        source="<<<来源>>>", freq="日频", next_date="待填写：每周四（库存/开工）/ 每日（价格）",
        confidence="高", gap="不同机构牌价与成交价有差异",
    ),
]

SECONDARY = [
    dict(name="原盐/煤炭成本",
         why="决定现金成本支撑；但当前供给过剩，成本更多是底部约束而非驱动。提级条件：现货跌破行业平均现金成本且开工明显下降。"),
    dict(name="轻碱/重碱价差",
         why="反映重碱相对强弱，但与日熔量高度相关，暂作二级。提级条件：轻碱价格显著强于重碱且持续 2 周以上。"),
]

GAPS = [
    dict(item="新增产能实际达产率",
         why="企业不披露，只能从月度产量与区域库存间接推断",
         workaround="用周产量增量 + 区域库存反向估算",
         limit="无法区分“新装置达产”与“老装置提负荷”，结论存在歧义"),
    dict(item="玻璃厂纯碱库存天数",
         why="属于终端调研数据，公开渠道多为定性描述",
         workaround="以下游成品库存与采购节奏代理",
         limit="只能判断方向，不能量化"),
]

CHARTS = {}

WEEKLY_CALENDAR = [
    dict(when="每周四", what="纯碱企业库存、开工率", src="隆众/卓创"),
    dict(when="每日", what="主力价格、基差、仓单", src="郑商所、期货公司日评"),
    dict(when="每月", what="纯碱进出口、玻璃产量", src="海关总署、统计局"),
]

PAYLOAD = {
    "meta": META, "as_of": AS_OF, "snapshot": SNAPSHOT, "events": EVENTS,
    "candidates": CANDIDATES, "variables": VARIABLES, "secondary": SECONDARY,
    "gaps": GAPS, "charts": CHARTS, "weekly_calendar": WEEKLY_CALENDAR,
}
