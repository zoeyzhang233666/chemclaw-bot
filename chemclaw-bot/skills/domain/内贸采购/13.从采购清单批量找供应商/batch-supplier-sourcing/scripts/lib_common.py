# -*- coding: utf-8 -*-
"""batch_sourcing.common — 通用工具：读写数据、单位换算、CAS 校验、字典加载。"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_assets():
    return {
        "materials": load_json(os.path.join(ASSET_DIR, "materials-reference.json")),
        "field_map": load_json(os.path.join(ASSET_DIR, "field-map.json")),
        "rules": load_json(os.path.join(ASSET_DIR, "rules.json")),
    }


def shanghai_now():
    return datetime.now(timezone(timedelta(hours=8)))


# ---------------------------------------------------------------- 文本清洗
_FW_PAIRS = {"０": "0", "１": "1", "２": "2", "３": "3", "４": "4", "５": "5", "６": "6",
             "７": "7", "８": "8", "９": "9", "（": "(", "）": ")", "【": "[", "】": "]",
             "％": "%", "＋": "+", "－": "-", "，": ",", "．": ".", "：": ":", "；": ";"}


def clean_text(v):
    if v is None:
        return ""
    s = str(v)
    for k, val in _FW_PAIRS.items():
        s = s.replace(k, val)
    s = s.replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    s = re.sub(r"[ \t\r\n]+", " ", s)
    return s.strip()


def norm_key(v):
    """表头归一：去空格、去括号注释、转小写。"""
    s = clean_text(v).lower()
    s = re.sub(r"[（(].*?[)）]", "", s)
    s = re.sub(r"[\s_\-/]+", "", s)
    return s


def is_form_variant(a, b):
    """同一物质的不同形态/浓度（纯碱 vs 纯碱(轻质)、氯化钙 vs 氯化钙溶液）不算歧义。"""
    return a.get("cas") and a.get("cas") == b.get("cas") and a["key"] != b["key"]


# ---------------------------------------------------------------- CAS
def cas_valid(cas):
    if cas is None:
        return False
    s = clean_text(cas).replace("CAS", "").replace("cas", "").strip()
    if not re.match(r"^\d{2,7}-\d{2}-\d$", s):
        return False
    digits = s.replace("-", "")
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (i + 1) for i, d in enumerate(reversed(body)))
    return total % 10 == check


def cas_norm(cas):
    if not cas:
        return ""
    s = clean_text(cas).upper().replace("CAS", "").replace("NO.", "").replace("NO", "")
    s = s.replace("：", ":").replace(" ", "")
    m = re.search(r"\d{2,7}-\d{2}-\d", s)
    return m.group(0) if m else s


# ---------------------------------------------------------------- 数值
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def to_number(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = _NUM_RE.search(clean_text(v).replace(",", ""))
    return float(m.group(0)) if m else None


def fmt_num(x, nd=2):
    if x is None or x == "":
        return ""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return str(x)
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}"
    return f"{x:,.{nd}f}"


# ---------------------------------------------------------------- 单位
def normalize_unit(unit, rules):
    """返回 (规范单位, 换算系数(到 t 或原文系数), 类别, 是否歧义)。"""
    s = clean_text(unit).lower().replace(" ", "")
    if s == "":
        return ("", None, "missing", True)
    u = rules["units"]
    if s in (x.lower() for x in ("t", "吨", "公吨", "mt")):
        return ("t", 1.0, "mass", False)
    for table, cat in (("mass", "mass"), ("volume", "volume"), ("gas", "gas")):
        for k, v in u[table].items():
            if s == k.lower():
                if isinstance(v, (int, float)):
                    return (u["canonical_mass"] if cat == "mass" else k, v if cat == "mass" else None, cat, False)
                return (k, None, cat, True)
    if s in (x.lower() for x in u["count"]):
        return (s, None, "count", True)
    if len(s) == 1 and s.isalpha() and s == "吨"[0]:
        return ("t", 1.0, "mass", False)
    return (clean_text(unit), None, "unknown", True)


# ---------------------------------------------------------------- 字典
class MaterialsDict:
    def __init__(self, materials_json):
        self.items = materials_json["materials"]
        self.by_cas = {}
        self.by_alias = {}
        for m in self.items:
            if m.get("cas"):
                self.by_cas.setdefault(m["cas"], []).append(m)
            names = [m["name"], m.get("en", "")] + list(m.get("aliases") or [])
            for n in names:
                if not n:
                    continue
                k = self._alias_key(n)
                self.by_alias.setdefault(k, []).append(m)

    @staticmethod
    def _alias_key(s):
        s = clean_text(s).lower()
        s = re.sub(r"[\s\-_()（）/、,，.。:：]+", "", s)
        return s

    def match_name(self, raw):
        """返回匹配到的候选物料列表（可能多个 = 歧义）。"""
        k = self._alias_key(raw)
        if not k:
            return []
        hits = self.by_alias.get(k, [])
        if hits:
            return hits
        # 包含匹配：名称里带数字/规格的写法，例如 "双氧水27.5%" "工业级烧碱"
        best, best_len = [], 0
        for alias, mats in self.by_alias.items():
            if len(alias) >= 2 and (alias in k or k in alias):
                if len(alias) > best_len:
                    best, best_len = [], len(alias)
                if len(alias) == best_len:
                    for m in mats:
                        if m not in best:
                            best.append(m)
        return best

    def lookup_cas(self, cas):
        return self.by_cas.get(cas_norm(cas), [])


def resolve_path(p, base=None):
    if os.path.isabs(p):
        return p
    return os.path.normpath(os.path.join(base or os.getcwd(), p))
