# -*- coding: utf-8 -*-
"""Fill optional sections so a sparse data.json still renders instead of crashing."""

CATS = ["工商", "司法", "处罚", "安全环保", "经营动态"]
COV_CATS = ["经营异常", "行政处罚", "诉讼仲裁", "安全环保事故", "重大股权变化", "停产/项目变化"]


def normalize(data):
    data.setdefault("suppliers", [])
    data.setdefault("events", [])
    data.setdefault("industry", [])
    if not data.get("coverage_check"):
        data["coverage_check"] = [
            {"cat": c, "status": "未填写", "note": "data.json 未提供覆盖检查；请补充渠道与结论。", "level": "待复核"}
            for c in COV_CATS
        ]
    method = data.setdefault("method", {})
    method.setdefault("scope", ["公开信息桌面检索；具体范围见 meta.scope_summary。"])
    method.setdefault("evidence_levels", [
        {"level": "A", "label": "可直接核对", "desc": "公司公告、交易所、政府/监管原文。"},
        {"level": "B", "label": "需回查", "desc": "主流财经媒体、行业媒体转述；需回查原文。"},
        {"level": "C", "label": "仅作线索", "desc": "聚合平台、论坛、未具名信源；不能单独支撑结论。"},
    ])
    method.setdefault("limits", ["公开信息可能存在滞后、遗漏或口径差异；未检索到不等于无风险。"])
    method.setdefault("search_queries", [])
    method.setdefault("disclaimer", "本报告基于公开信息整理，仅供采购决策参考，不构成法律、财务或投资意见；未检索到不等于无风险。")
    return data
