# -*- coding: utf-8 -*-
"""共享工具：加载案例、状态元数据、文本处理。"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

STATUS = {
    "A":  {"label": "公开可见",   "short": "公开可见", "color": "green", "hex": "E7F6EC", "hex_deep": "166534"},
    "B":  {"label": "需核对原件", "short": "需核对",   "color": "amber", "hex": "FDF3D8", "hex_deep": "92400E"},
    "C":  {"label": "无公开信息", "short": "无公开",   "color": "red",   "hex": "FDE7E7", "hex_deep": "991B1B"},
    "NA": {"label": "不适用",     "short": "不适用",   "color": "gray",  "hex": "ECEEF1", "hex_deep": "374151"},
}

SEVERITY = {
    "高": {"hex": "FDE7E7", "deep": "991B1B"},
    "中": {"hex": "FDF3D8", "deep": "92400E"},
    "低": {"hex": "E7F6EC", "deep": "166534"},
}


def load_case(path: str | os.PathLike) -> Dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data["_path"] = str(p)
    return data


def status_meta(code: str) -> Dict[str, str]:
    return STATUS.get(code, STATUS["NA"])


def norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def initials(name: str) -> str:
    """给封面取一个短名：优先括号内/第一个分隔符前。"""
    name = norm_space(name)
    m = re.search(r"[（(]([^）)]+)[）)]", name)
    if m:
        return m.group(1)
    return name


def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    return name.strip().strip(".")


def verdict_style(code: str) -> Dict[str, str]:
    if code == "NON_HAZCHEM":
        return {"hex": "E7F6EC", "deep": "166534", "icon": "✓"}
    if code == "HAZCHEM":
        return {"hex": "FDF3D8", "deep": "92400E", "icon": "!"}
    return {"hex": "FDE7E7", "deep": "991B1B", "icon": "!"}


def count_status(checks: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    out = {"A": 0, "B": 0, "C": 0, "NA": 0, "total": 0}
    for c in checks:
        out[c.get("status", "NA")] = out.get(c.get("status", "NA"), 0) + 1
        out["total"] += 1
    return out


def retention_summary(case: Dict[str, Any]) -> List[Dict[str, str]]:
    """从义务清单汇总留存与备案口径。"""
    rows: List[Dict[str, str]] = []
    for group, key in (("销售方", "seller"), ("买方", "buyer"), ("双方", "joint")):
        for o in case["obligations"].get(key, []):
            rows.append({
                "group": group,
                "id": o["id"],
                "item": o["item"],
                "basis": o["basis"],
                "retention": o["retention"],
                "filing": o["filing"],
                "timing": o["timing"],
                "evidence": o["evidence"],
            })
    return rows
