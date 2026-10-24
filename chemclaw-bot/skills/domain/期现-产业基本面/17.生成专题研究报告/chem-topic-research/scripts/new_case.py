# -*- coding: utf-8 -*-
"""
new_case.py —— 生成一份空白 case.json（结构完整、校验通过），供新专题起步。

    python new_case.py --title "中国XX行业新增产能对供应格局的影响" --product 纯碱 \
        --shape 重质纯碱 --audience 产业研究员 --out my-case.json

生成后请按顺序填空：meta → research_brief → audience_frameworks（提纲）→ sources/projects/…
提示：提纲阶段只需要填到 audience_frameworks，其余可留空；validate 会提示缺什么。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

# 通用章节包目录（与具体产品无关）：(pack, 章节名, 要回答的问题, 为什么需要, 验伪点, 依赖数据, 方法)
PACK_CATALOG = [
    ("research_design", "研究问题、范围与数据口径",
     "这份研究要回答什么、不回答什么、数据口径怎么定？",
     "先定问题与边界，避免写成行业综述",
     "问题是否可回答；口径是否足以支撑比较",
     "研究问题清单、口径说明", "问题树拆解 + 口径表"),
    ("structure", "现有产能结构、工艺与企业集中度",
     "现在的产能由谁、用什么工艺、分布在哪里构成？",
     "任何供需判断都要先有结构基线，否则无法判断“谁被替代”",
     "工艺占比与集中度是否能解释成本分化",
     "产能结构、企业清单、区域分布", "结构分解 + CRn + 成本分档"),
    ("projects", "在建与新投产项目核验",
     "哪些项目已投产、在建、规划？哪些只是搬迁置换？",
     "“预计投产”与“已发生供给”差一个量级，不核验就会高估供给",
     "投产状态是否有公告/统计依据；是否净新增",
     "项目台账、开工与投产日期、置换披露", "逐项目三态核验 + 证据强度"),
    ("calculation", "预计投产 ≠ 新增供给：有效供给转化测算",
     "名义产能如何折算为可实现的供给增量？",
     "决定结论量级的核心一步，参数必须可复算",
     "爬坡率、时间权重、置换扣减是否合理",
     "投产时间、负荷率、置换关系", "分层折算 + 情景上下限"),
    ("cost", "成本曲线与产能出清阈值",
     "谁在亏、亏到什么程度才会退出？",
     "过剩能否被消化取决于成本曲线的尾部退出",
     "成本档位与现金成本是否被突破",
     "工艺成本、现金成本、利润", "成本曲线 + 现金成本线"),
    ("demand", "需求侧约束",
     "下游能否吸收新增供给？",
     "供给增加不等于价格下跌，还要看需求弹性与结构",
     "下游开工、产量、库存是否同步走弱",
     "下游产量、开工率、宏观指标", "需求分解 + 弹性判断"),
    ("price_history", "价格、库存与利润的历史校验",
     "历史上同类扩产如何传导到价格与库存？",
     "用历史类比校准幅度，避免线性外推",
     "历史可比性是否成立（供给节奏、需求周期）",
     "长周期价格、库存、开工", "类比校验 + 分位定位"),
    ("region", "区域格局与物流半径",
     "供给与需求在空间上是否匹配？",
     "区域过剩与全国过剩是两件事",
     "区域价差与运费是否支持跨区流动",
     "区域产能/需求、运费、价差", "区域平衡表"),
    ("company", "企业集团与竞争行为",
     "谁有能力、有意愿改变供给节奏？",
     "供给是企业的决策结果，不是统计结果",
     "企业扩产动机、资金与成本位置",
     "集团产能、负债、扩产公告", "企业画像 + 行为推断"),
    ("process", "工艺路线与替代关系",
     "不同工艺的替代边界在哪里？",
     "解释成本曲线移动的方向",
     "工艺成本差、原料可得性",
     "工艺成本、原料价格", "工艺对比"),
    ("chain", "产业链上下游传导",
     "成本与价格如何在上中下游传导？",
     "判断价格变化的持续性",
     "传导系数、时滞",
     "上下游价格、加工费", "传导链分析"),
    ("policy", "政策与合规约束",
     "哪些政策会改变供给或需求的边界？",
     "政策是供给侧的硬约束",
     "政策是否有执行时间表",
     "产能置换、环保、能耗政策", "政策梳理 + 执行强度"),
    ("conclusion", "结论、反证条件与后续核验",
     "结论是什么，什么情况下会被推翻？",
     "没有反证条件的结论不可用于决策",
     "每条判断是否有可观测的推翻信号",
     "关键变量与阈值", "结论分级 + 变量清单"),
    ("risk", "风险与情景",
     "在哪些情景下结论会变化？",
     "为决策留出情景空间",
     "情景假设是否互斥且可辨识",
     "情景假设参数", "情景分析"),
]

PACK_BY_NAME = {p[0]: p for p in PACK_CATALOG}

DEFAULT_AUDIENCE_PACKS = {
    "management": ["research_design", "structure", "calculation", "risk", "conclusion"],
    "sales": ["research_design", "structure", "demand", "price_history", "region", "conclusion"],
    "procurement": ["research_design", "structure", "cost", "projects", "price_history", "conclusion"],
    "rnd": ["research_design", "structure", "process", "chain", "demand", "conclusion"],
    "industry-researcher": ["research_design", "structure", "projects", "calculation", "cost",
                            "demand", "price_history", "conclusion"],
}

AUDIENCE_FOCUS = {
    "management": "回答“格局变成什么样、我们在其中处于什么位置、未来 12 个月要做什么决定”。不展示推导过程，但每个判断都能展开到证据与计算。",
    "sales": "回答“供给变多会不会让客户压价、哪个区域先松动、我该怎么报价与备货”。重点是价格弹性与区域差异。",
    "procurement": "回答“什么时候买、买多少、要不要锁价、供应商的涨价理由是否站得住”。重点是成本曲线与议价窗口。",
    "rnd": "回答“工艺路线会不会被替代、新项目的技术选择意味着什么”。重点是工艺成本与替代关系。",
    "industry-researcher": "回答“未来 12–24 个月供应格局如何演化、关键假设是什么、哪些判断最脆弱”。要求推导完整、口径可复算、结论可证伪。",
}


def chapter_from_pack(pack, idx):
    p = PACK_BY_NAME[pack]
    return {
        "no": "%02d" % idx,
        "title": p[1],
        "question": p[2],
        "why": p[3],
        "verify": p[4],
        "data": [x.strip() for x in p[5].split("、")],
        "method": p[6],
    }


def build_case(title, product, shape, topic_type, audience, horizon, date):
    packs = DEFAULT_AUDIENCE_PACKS.get(audience, DEFAULT_AUDIENCE_PACKS["industry-researcher"])
    frameworks = {}
    for k, ps in DEFAULT_AUDIENCE_PACKS.items():
        frameworks[k] = {
            "audience_key": k,
            "label": C.AUDIENCE_CN.get(k, k),
            "positioning": AUDIENCE_FOCUS.get(k, ""),
            "focus": AUDIENCE_FOCUS.get(k, ""),
            "answer_style": "结论先行 + 证据可下钻" if k in ("management", "sales", "procurement") else "推导完整 + 口径可复算",
            "chapters": [chapter_from_pack(p, i + 1) for i, p in enumerate(ps)],
            "suppressed_topic_packs": [p[0] for p in PACK_CATALOG if p[0] not in ps],
            "evidence_policy": "每章至少 1 条 A/B 级证据；判断类结论必须写反证条件",
            "length_target": {"management": "5–7 章", "sales": "6 章", "procurement": "6 章",
                              "rnd": "6 章", "industry-researcher": "8–10 章"}.get(k, "6 章"),
            "chart_preferences": ["结构对比", "时间序列", "情景区间"],
        }
    return {
        "schema": C.SCHEMA_VERSION,
        "meta": {
            "slug": "new-topic",
            "title": title,
            "subtitle": "（一句话说明这份研究要回答的判断及其决策含义）",
            "audience": audience,
            "audience_label": C.AUDIENCE_CN.get(audience, audience),
            "product_cn": product,
            "product_shape": shape,
            "topic_type": topic_type,
            "report_date": date,
            "data_cutoff": date,
            "horizon": horizon,
            "version": "v0.1-提纲",
            "org": "",
            "author": "",
            "disclaimer": "本材料为研究结论与决策参考，不构成投资建议、价格承诺或生产计划保证。",
        },
        "audience_frameworks": frameworks,
        "research_brief": {
            "objective": "（一句话：这份研究要支撑什么决策）",
            "questions": [
                {"id": "Q1", "question": "现有产能结构与集中度如何？", "answered": "no",
                 "note": "（数据可获得性预判）"},
                {"id": "Q2", "question": "新增产能中多少已真实投产？", "answered": "no", "note": ""},
                {"id": "Q3", "question": "未来 12–24 个月新增供给的确定性如何？", "answered": "no", "note": ""},
                {"id": "Q4", "question": "需求端能否吸收新增供给？", "answered": "no", "note": ""},
                {"id": "Q5", "question": "哪些信号会推翻当前判断？", "answered": "no", "note": ""},
            ],
            "scope_in": ["（纳入范围）"],
            "scope_out": ["（不纳入范围）"],
            "assumptions": [],
        },
        "method_notes": [
            {"topic": "状态分级", "rule": "已投产=有公告或统计确认投产月份；在建=已开工未点火；规划=有公告但投产在 2 年以上"},
            {"topic": "证据强度", "rule": "A=企业公告/官方统计；B=行业媒体引用第三方数据；C=研报转述/单一来源"},
            {"topic": "结论分级", "rule": "事实=可直接引用来源；计算=可复现公式；解释=基于事实的机理说明；判断=需假设与反证条件"},
        ],
        "sources": [],
        "data_gaps": [],
        "glossary": [],
        "companies": [],
        "projects": [],
        "capacity_structure": {"rows": [], "shares": []},
        "kpis": [],
        "calculations": [],
        "conclusions": [],
        "key_variables": [],
        "sections": [],
    }


ALIASES = {"管理层": "management", "销售": "sales", "采购": "procurement",
           "研发": "rnd", "产业研究员": "industry-researcher", "研究员": "industry-researcher"}


def resolve_audience(token):
    """同时接受受众键与中文名（命令行传中文时可能被系统编码破坏，做一次兜底）。"""
    token = (token or "").strip()
    if token in DEFAULT_AUDIENCE_PACKS:
        return token
    if token in ALIASES:
        return ALIASES[token]
    # 兜底：按 UTF-8 误解码后重试（Windows 控制台常见）
    try:
        fixed = token.encode("latin-1").decode("utf-8")
        if fixed in ALIASES:
            return ALIASES[fixed]
        if fixed in DEFAULT_AUDIENCE_PACKS:
            return fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    raise SystemExit("未知受众 %r；可用：%s 或中文名 %s"
                     % (token, "、".join(DEFAULT_AUDIENCE_PACKS), "、".join(ALIASES)))


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成空白 case.json")
    ap.add_argument("--title", required=True)
    ap.add_argument("--product", default="（产品）")
    ap.add_argument("--shape", default="")
    ap.add_argument("--topic", default="供应格局/产能扩张", dest="topic_type")
    ap.add_argument("--audience", default="industry-researcher",
                    help="management / sales / procurement / rnd / industry-researcher，或中文名")
    ap.add_argument("--horizon", default="未来 12–24 个月")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--out", default="case.json")
    a = ap.parse_args(argv)
    audience = resolve_audience(a.audience)
    case = build_case(a.title, a.product, a.shape, a.topic_type, audience, a.horizon, a.date)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=2)
    errs, warns = C.validate(case)
    print("已生成 ->", a.out)
    print("受众框架：%s（%d 章）" % (case["audience_frameworks"][audience]["label"],
                                 len(case["audience_frameworks"][audience]["chapters"])))
    print("校验：错误 %d · 警告 %d" % (len(errs), len(warns)))
    for e in errs[:6]:
        print("  -", e)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
