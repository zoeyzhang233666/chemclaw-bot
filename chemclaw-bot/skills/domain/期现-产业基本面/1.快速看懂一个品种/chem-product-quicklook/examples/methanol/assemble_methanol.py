# -*- coding: utf-8 -*-
"""组装 methanol research.json"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from methanol_sources import SOURCES
from methanol_a import META, PRODUCT, FRAME
from methanol_chain import COLS, NODES
from methanol_panels1 import PANELS
from methanol_panels2 import PANELS2

GAPS = [
    {"area": "现货价格序列（华东/华南/内蒙/山东）",
     "desc": "无逐日可引用序列；报价分散在卓创/隆众/金联创/生意社，且六项口径（规格·地区·含税·日期·来源）不齐会污染基差。",
     "how": "接入产业数据源后，按 references/research-playbook.md 补齐六项口径，再进 build_anchors 计算。",
     "impact": "基差与区域价差无法量化，只能用方向描述"},
    {"area": "港口/厂库/仓单库存",
     "desc": "华东、华南港口库存；生产企业库存；期货仓单量本轮未取得绝对值。",
     "how": "交易所仓单日报为公开数据（czce.com.cn），港口库存需订阅卓创/隆众。",
     "impact": "库存-价格关系与月差判断缺数据支撑"},
    {"area": "期货规则原文（czce.com.cn）",
     "desc": "最小变动价位、最低保证金、交割单位、交割品级与升贴水条款未从交易所原文核实（站点反爬拦截）。",
     "how": "人工打开交易所合约文本与交割细则 PDF，逐条核对并回填 S21。",
     "impact": "期货条款标注为“需复核”，不得用于交易/交割决策"},
    {"area": "进出口分国别明细与出口量",
     "desc": "仅有 2025 年进口总量预估与“伊朗为主”的定性表述；分国别、月度、出口量未取得。",
     "how": "海关总署统计月报或 UN Comtrade（HS 290511）补数。",
     "impact": "贸易结构与依存度无法量化"},
    {"area": "分省产能与区域价差/运费",
     "desc": "仅内蒙古有明确数值（3073.5 万吨/28.73%），陕西/宁夏/山东/新疆分省值缺失；典型运费未取得。",
     "how": "隆众/卓创区域调研报告；物流平台运费指数。",
     "impact": "区域套利与物流成本判断缺乏依据"},
    {"area": "企业级单套产能与商业牌号",
     "desc": "集团口径与单套口径混杂；商业牌号不公开。",
     "how": "上市公司年报、环评公示、企业官网逐家核实，并标注口径。",
     "impact": "企业产能榜只能作集团层面参考"},
    {"area": "下游分项（2025 年）与部分单耗",
     "desc": "除 MTO 48.9% 外，2025 年各分项占比未公开；甲胺/甲烷氯化物/硫酸二甲酯单耗未取得。",
     "how": "订阅隆众/卓创下游月度数据。",
     "impact": "需求结构只能用 2024 年第三方口径"},
    {"area": "MTO/MTO-PP 装置利润与烯烃价格序列",
     "desc": "外采 MTO 利润仅以文字表述（2025 年均亏超 1000 元/吨）。",
     "how": "烯烃价格（PP/PE）+ 甲醇价格 + 单耗构建利润模型。",
     "impact": "需求开关的量化阈值缺失"},
]

CAVEATS = [
    "口径第一：全国产能同时存在 1.15 亿吨（氮肥协会）与 10,804.5 万吨（隆众产能基数）两个数，引用时必须带机构与时点，不能只说“中国甲醇产能”。",
    "税价第二：期货价为不含税合约价，现货多为含税价。基差比较前必须先做含税↔不含税的换算（增值税 13%），否则基差符号可能整体反转。",
    "参数第三：吨煤耗 1.5–1.6 吨、吨气耗约 1050 m³、碳排 2.0–2.5 t/t 均为公开工艺资料典型值，不代表任一企业实测值。",
    "单耗第四：MTO 单耗有 2.66（DMTO-Ⅲ 中试）、2.87（宝丰二期盘库）、约 3.0（一代技术）三个值，技术代际不同，估算乙烯利润时必须声明用哪个。",
    "占比第五：下游占比只能用 2025 年 MTO 48.9% 这一个权威值，其余分项引用 2024 年第三方口径，两者不可相加。",
    "期货第六：本页合约要素（涨跌停、最后交易日）转自东财对郑商所合约的转录，交易所原文未取得，交易前必须以 czce.com.cn 复核。",
    "本页不做方向判断：所有“研究判断”已标注，仅用于建立框架，不构成交易建议。",
]

PURPOSES = [
    {"id": "futures", "name": "期货研究", "panel": "trade_futures",
     "emphasize": ["self", "downstream"],
     "highlight_indicators": ["0-0", "4-0", "4-1", "0-2"]},
    {"id": "spot", "name": "现货贸易", "panel": "capacity",
     "emphasize": ["upstream", "self"],
     "highlight_indicators": ["3-1", "3-2", "1-0"]},
    {"id": "mto_procure", "name": "MTO 采购/外采", "panel": "demand",
     "emphasize": ["downstream", "enduse"],
     "highlight_indicators": ["1-1", "1-2", "2-0"]},
    {"id": "supply", "name": "供给与在建跟踪", "panel": "capacity",
     "emphasize": ["process", "upstream"],
     "highlight_indicators": ["0-0", "0-1", "0-3"]},
    {"id": "research", "name": "通用研究", "panel": "indicators",
     "emphasize": [], "highlight_indicators": []},
]

SCENES = {
    "price_history": {"name": "价格历史与分位", "skill": "chem-market-brief",
                      "template": "拉取 {product} 近 3 年逐日价格，计算 1/3/5 年分位、区间极值、最大回撤，并标出异常波动日"},
    "basis_scan": {"name": "基差与月差研判", "skill": "chem-market-brief / 期现-价差与量化",
                   "template": "计算 {product} 华东现货−MA主力 基差（先统一含税口径）、1-5/5-9 月差，并对照港口库存与 MTO 开工"},
    "capacity_survey": {"name": "产能调查", "skill": "期现-产业基本面/3.看主要生产企业和产能",
                        "template": "按 集团/单厂/单套 三种口径梳理 {product} 生产企业与装置，标注投产时间与在建状态"},
    "news_scan": {"name": "产业新闻", "skill": "期现-产业基本面/21.聚合产业资讯并定位事件",
                  "template": "聚合近 7 天 {product} 相关的装置停车、进口到港、地缘与政策事件，按影响路径归类"},
    "cost_curve": {"name": "成本曲线", "skill": "期现-产业基本面/13.看产业链利润变化",
                   "template": "构建 {product} 分路线（煤制/焦炉气/天然气）成本曲线，标出当前价格位置与外采 MTO 盈亏线"},
}



DATA = {
    "meta": META,
    "product": PRODUCT,
    "frame": FRAME,
    "chain": {"cols": COLS, "nodes": NODES},
    "research": {"futures": [b for p_ in (PANELS + PANELS2) for b in p_["body"] if b["type"] == "futures"][0]},
    "panels": PANELS + PANELS2,
    "sources": SOURCES,
    "gaps": GAPS,
    "caveats": CAVEATS,
    "purposes": PURPOSES,
    "scenes": SCENES,
    "vcs": {
        "来源抓取": "2026-10-20 无头浏览器抓取 11 条网页原文（chemall/sina/7hcn/eastmoney/dicp/people.cn/chinafood等），全部成功并落盘 _verify/raw",
        "价格序列": "MA0 日线 2862 个交易日（2014-12-24 → 2026-10-19），由新浪 InnerFuturesNewService 拉取，与本地已有序列逐日一致",
        "锚点计算": "build_anchors.py 从原始日线计算分位/区间/成交/持仓，未手写任何数字",
        "未核实项": "郑商所官网被反爬拦截 3 次；最小变动价位/保证金/交割品级/交割单位标记为缺口",
        "冲突处理": "产能与下游占比存在多口径，已在 05/06 表与 caveats 中列冲突而非择一",
    },
    "chart_note": "节点详情中的曲线为示意，不代表实测序列；真实价格请用 build_anchors.py 生成后替换。",
}

out = HERE.parent / "_build_output" / "research.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(DATA, ensure_ascii=False, indent=1), encoding="utf-8")
print("nodes", len(NODES), "panels", len(DATA["panels"]), "sources", len(SOURCES), "→", out)
