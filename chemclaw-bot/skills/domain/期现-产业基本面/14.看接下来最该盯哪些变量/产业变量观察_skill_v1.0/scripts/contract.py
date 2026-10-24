# -*- coding: utf-8 -*-
"""
通用产业变量观察 —— 数据结构契约（Schema）

任何品种/周期都可以通过一份符合本契约的 JSON/Python dict 喂给 render_html.render() 与
render_excel.build()，从而产出同一套看板与工作簿。案例 facts.py 与本文件保持完全同构。

必填字段全部在此声明；缺失数据一律使用 NODATA 标记，严禁留空或写"暂无可用数据"以外的臆测。
"""
from __future__ import annotations

NODATA = "数据缺失"  # 统一缺失标记，用于校验与可视化

# 顶层结构
TOP_KEYS = ["meta", "snapshot", "events", "candidates", "variables", "secondary", "gaps"]

SCHEMA = {
    "meta": {
        "required": ["commodity", "cycle", "contract_focus", "region_focus",
                     "price_basis", "research_position"],
        "optional": ["as_of", "window_start", "window_end", "analyst", "version"],
    },
    "snapshot": {  # 产业状态快照，每项一条
        "required": ["indicator", "value", "recent", "history", "scope", "source"],
        "optional": ["flag"],  # flag: 极低/极低回升/高位/背离...
    },
    "events": {
        "required": ["date", "date_label", "title", "kind", "cat", "certainty", "impact", "source"],
        "optional": ["date_certainty"],
        # kind ∈ 已披露·确定时点 / 已披露·时点模糊 / 已披露·进行中 / 定期数据 / 季节性·条件触发 / 条件触发·观察窗
    },
    "candidates": {
        "required": ["name", "cat", "verifiability", "selected", "reason"],
    },
    "variables": {
        "required": ["vid", "name", "cat", "rank", "importance", "verifiability", "urgency",
                     "horizon", "current", "recent_change", "history_pos", "why", "mechanism",
                     "key_data", "verify_yes", "verify_no", "invalidate",
                     "source", "freq", "next_date", "confidence", "gap"],
        "optional": ["score_note", "chart"],
        # cat ∈ 供给 / 需求 / 库存 / 成本 / 价差 / 政策
    },
    "secondary": {"required": ["name", "why"]},
    "gaps": {"required": ["item", "why", "workaround", "limit"]},
}

CATEGORIES = ["供给", "需求", "库存", "成本", "价差", "政策"]

CAT_COLOR = {
    "供给": "#e0693a",
    "需求": "#2f7fd1",
    "库存": "#7c5cd6",
    "成本": "#c99427",
    "价差": "#1a9b8a",
    "政策": "#b8446b",
}


def validate(payload: dict) -> list[str]:
    """返回问题清单；空列表代表通过。"""
    problems: list[str] = []
    if not isinstance(payload, dict):
        return ["payload 必须是 dict"]
    for k in TOP_KEYS:
        if k not in payload:
            problems.append(f"缺少顶层字段：{k}")
    if problems:
        return problems

    meta = payload["meta"]
    for k in SCHEMA["meta"]["required"]:
        if not meta.get(k):
            problems.append(f"meta.{k} 为空")

    for section in ("snapshot", "events", "candidates", "variables", "secondary", "gaps"):
        items = payload[section]
        if not isinstance(items, list) or not items:
            problems.append(f"{section} 必须是非空列表")
            continue
        req = SCHEMA[section]["required"]
        for i, it in enumerate(items):
            for k in req:
                if k not in it:
                    problems.append(f"{section}[{i}] 缺少 {k}")

    # 变量必须 3-6 个，且 rank 唯一
    vs = payload["variables"]
    if not (3 <= len(vs) <= 6):
        problems.append(f"variables 数量应为 3-6，当前 {len(vs)}")
    ranks = [v.get("rank") for v in vs]
    if len(set(ranks)) != len(ranks):
        problems.append("variables.rank 存在重复")
    for v in vs:
        if v.get("cat") not in CATEGORIES:
            problems.append(f"变量 {v.get('vid')} 的分类 {v.get('cat')} 不在 {CATEGORIES}")
        for score_key in ("importance", "verifiability", "urgency"):
            val = v.get(score_key)
            if not isinstance(val, int) or not (1 <= val <= 5):
                problems.append(f"变量 {v.get('vid')} 的 {score_key} 须为 1-5 的整数")
    return problems


def sort_variables(vs: list[dict]) -> list[dict]:
    """按综合分降序再按 rank 升序，保证展示顺序稳定。"""
    return sorted(vs, key=lambda v: (-(v["importance"] * 2 + v["verifiability"] + v["urgency"]), v["rank"]))
