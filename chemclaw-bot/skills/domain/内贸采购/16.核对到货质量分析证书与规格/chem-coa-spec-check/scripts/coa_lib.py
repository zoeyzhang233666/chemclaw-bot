# -*- coding: utf-8 -*-
"""coa_lib.py —— COA / 采购规格 核对的计算内核。

设计原则
--------
1. 数值一律"解析成结构"再比较：单值 / 最大值(≤) / 最小值(≥) / 范围(a~b) / 未检出(ND) /
   小于检出限(<LOD) / 定性(<字号> / 通过 / 合格)。不做字符串比较。
2. 单位换算只在**量纲一致**时进行；换算前后都写进审计轨迹（value_conv.note）。
   换算后跨越判定线（如 98.9 % 换成 989000 ppm 后 ≥998000 ppm 不成立）必须显式提示。
3. 指标"名称相似"不等于"可比"。可比性由 5 项共同决定：
   名称/同义词 → 量纲 → 检测方法 → 基准(干基/湿基, 折百/非折百) → 规格限值类型。
   任一不满足，状态直接落"无法判断"，并把原因写进 comparability 字段。
4. 判定状态固定六种，不允许自造：
   符合 / 不符合 / 规格未约定 / COA未检测 / 无法判断 。
   （另有一个工程状态"COA未提供"仅用于整份 COA 缺失，或在"无法判断"的说明里出现。）
5. 引擎只给"事实与判断"，不给"收/退货"结论。收货决定由人做。

本文件零第三方依赖，Python 3.9+。
"""

import datetime as _dt
import math
import re
from collections import OrderedDict

# --------------------------------------------------------------------------------------
# 0. 常量：判定状态、严重度、优先级
# --------------------------------------------------------------------------------------

ST_OK = "符合"
ST_FAIL = "不符合"
ST_UNSPEC = "规格未约定"
ST_UNTESTED = "COA未检测"
ST_UNKNOWN = "无法判断"
STATUS_SET = (ST_OK, ST_FAIL, ST_UNSPEC, ST_UNTESTED, ST_UNKNOWN)
LOD_KINDS = ("single", "lod")   # 微量杂质：报单一数值时的默认结构实际是该法的检出限
HIT_STATUS = (ST_FAIL, ST_UNTESTED, ST_UNKNOWN, ST_UNSPEC)   # 需要人看的

SEV = {"高": 3, "中": 2, "低": 1}
SEV_ORDER = ["高", "中", "低"]

# 可比性 5 维，任一项 False → 无法判断
COMP_DIMS = OrderedDict([
    ("name", "指标名称/同义词对应"),
    ("dimension", "量纲可换算"),
    ("method", "检测方法与约定一致"),
    ("basis", "基准一致（干基/湿基、折百/非折百）"),
    ("limit", "限值类型可比（上下限/范围/定性）"),
])


# --------------------------------------------------------------------------------------
# 1. 量纲与单位换算
# --------------------------------------------------------------------------------------

def _f(x, d=10):
    """安全浮点。"""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _tok(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


def _mkdim(members, label, levels=None, hint="g"):
    """构造量纲表。members: {归一化符号: 换算到(或从)基准单位的系数}

    ppm 族："≤10 ppm 的铁" = "≤1e-5 %" = "≤0.01 mg/kg"，基准取 %。
    ppb 族：独立基准，因为 "1 ppb = 0.001 ppm" 在中文 COA 里常被写成错误的值。
    hint: 该量纲规范显示单位（ppm 族以 ppm 为显示单位，避免 865 ppm 显示成 0.0865%）
    """
    m = {_tok(k): v for k, v in members.items()}
    lv = {_tok(k): v for k, v in (levels or {}).items()}
    return {"members": m, "label": label, "levels": lv, "hint": hint}


DIMENSIONS = {
    # 质量分数 / 含量
    "%": _mkdim({
        "%": 1.0, "wt%": 1.0, "质量分数%": 1.0, "含量%": 1.0, "百分含量%": 1.0,
        "ppm": 1e-4, "mg/kg": 1e-4, "mg·kg-1": 1e-4, "μg/g": 1e-4, "µg/g": 1e-4,
        "ug/g": 1e-4, "m/mppm": 1e-4,
        "ppb": 1e-7, "μg/kg": 1e-7, "µg/kg": 1e-7, "ug/kg": 1e-7,
        "g/kg": 0.1, "mg/g": 0.1,
    }, "质量分数（基准 %）",
        levels={"%": ("高", "低"), "ppm": ("高", "中"), "mg/kg": ("高", "中"), "ppb": ("高", "低"),
                "μg/kg": ("高", "低"), "g/kg": ("中", "中"), "mg/g": ("中", "中")},
        hint="ppm"),
    # 浓度
    "mg/L": _mkdim({
        "mg/l": 1.0, "mg·l-1": 1.0, "ppm(v/v)": 1.0, "ppm(v)": 1.0,
        "μg/l": 1e-3, "µg/l": 1e-3, "ug/l": 1e-3, "g/l": 1000.0,
    }, "质量浓度（基准 mg/L）", hint="mg/L"),
    # 温度
    "℃": _mkdim({"℃": 1.0, "°c": 1.0, "ºc": 1.0, "度": 1.0, "degc": 1.0, "c": 1.0,
                 "℉": 1.0, "°f": 1.0}, "温度（℃/℉ 需仿射换算）", hint="℃"),
    # 质量（桶重/净重/密度的相邻量）
    "kg": _mkdim({"kg": 1.0, "千克": 1.0, "公斤": 1.0, "吨": 1000.0, "t": 1000.0, "g": 1e-3, "克": 1e-3},
                 "质量（基准 kg）", hint="kg"),
    # 体积
    "L": _mkdim({"l": 1.0, "升": 1.0, "ml": 1e-3, "毫升": 1e-3, "m3": 1000.0, "立方米": 1000.0},
                "体积（基准 L）", hint="L"),
    # 密度/相对密度
    "g/cm³": _mkdim({"g/cm3": 1.0, "g/cm³": 1.0, "g·cm-3": 1.0, "kg/m3": 1e-3, "kg/m³": 1e-3,
                     "g/ml": 1.0, "kg/l": 1000.0, "相对密度": 1.0}, "密度（基准 g/cm³，20℃）", hint="g/cm³"),
    # 时间/日期
    "min": _mkdim({"min": 1.0, "分钟": 1.0, "s": 1 / 60.0, "秒": 1 / 60.0, "h": 60.0, "h/25℃": 60.0,
                   "小时": 60.0, "d": 1440.0, "天": 1440.0}, "时间（基准 min）", hint="min"),
    # 色度
    "Hazen": _mkdim({"hazen": 1.0, "pt-co": 1.0, "ptco": 1.0, "铂钴": 1.0, "铂-钴": 1.0,
                     "cu": 1.0, "铂钴色号": 1.0}, "色度（Hazen/铂钴）", hint="Hazen"),
    # 无单位计数
    "—": _mkdim({"": 1.0, "—": 1.0, "-": 1.0, "1": 1.0, "无": 1.0, "个": 1.0}, "无量纲", hint="—"),
    # 定性
    "定性": _mkdim({"定性": 1.0}, "定性判定（通过/未检出/合格）", hint="—"),
}

# 中文/别名 → 归一化符号
UNIT_ALIAS = {
    "%": ["%", "％", "wt%", "WT%", "m/m", "质量分数"],
    "ppm": ["ppm", "PPM", "mg/kg", "mg·kg-1", "μg/g", "µg/g", "ug/g", "m/m ppm", "wppm"],
    "ppb": ["ppb", "PPB", "μg/kg", "µg/kg", "ug/kg"],
    "mg/L": ["mg/L", "mg/l", "ppm(v/v)", "ppm(v)"],
    "g/kg": ["g/kg"], "mg/g": ["mg/g"],
    "℃": ["℃", "°C", "度", "DegC", "℉", "°F"],
    "kg": ["kg", "千克", "公斤", "吨", "t"],
    "L": ["L", "升", "ml", "mL"],
    "g/cm³": ["g/cm3", "g/cm³", "g·cm-3", "g/ml", "kg/m3", "kg/m³"],
    "min": ["min", "分钟", "s", "秒", "h", "小时"],
    "Hazen": ["Hazen", "Pt-Co", "PtCo", "铂钴", "铂-钴", "CU"],
    "定性": ["定性", "—", "-", ""],
}


def unit_token(raw):
    """把任意写法的单位串归一化成 (量纲, 归一符号)；识别不了返回 (None, 原文)。"""
    t = _tok(raw)
    if t in ("", "-", "—", "－", "无"):
        return "定性", "定性"
    # 先查精确表
    for dim, members in DIMENSIONS.items():
        for k in members["members"]:
            if t == k:
                return dim, k
    # 再查别名表（大小写/全角）
    for sym, alts in UNIT_ALIAS.items():
        for a in alts:
            if t == _tok(a):
                dim = _dim_of_symbol(sym)
                if dim:
                    return dim, sym
    # 形如 "mg/kg" 带全角斜杠、"%"前后有空格
    t2 = t.replace("／", "/").replace("·", "").replace("μ", "u").replace("µ", "u")
    for dim, members in DIMENSIONS.items():
        for k in members["members"]:
            if t2 == k or t2 == k.replace("·", ""):
                return dim, k
    return None, str(raw or "").strip()


def _dim_of_symbol(sym):
    for dim, members in DIMENSIONS.items():
        if sym in members["members"]:
            return dim
    return None


def temperature_convert(v, src, dst):
    src, dst = _tok(src), _tok(dst)
    if src in ("f", "℉", "°f") and dst in ("c", "℃", "°c", "ºc", "degc", "度"):
        return (v - 32.0) * 5.0 / 9.0
    if src in ("c", "℃", "°c", "ºc", "degc", "度") and dst in ("f", "℉", "°f"):
        return v * 9.0 / 5.0 + 32.0
    return v


def convert(value, unit_from, unit_to):
    """返回 (换算后数值, 说明)。量纲不一致 → (None, 原因)。

    注意：质量分数 ↔ 质量浓度（% ↔ mg/L）不做换算——缺少密度就是缺条件，
    这正是"不允许猜测"的典型场景。
    """
    if value is None:
        return None, "无值"
    d1, u1 = unit_token(unit_from)
    d2, u2 = unit_token(unit_to)
    if d1 is None or d2 is None:
        return None, f"单位无法识别：{unit_from!r} → {unit_to!r}"
    if d1 != d2:
        return None, (f"量纲不一致（{DIMENSIONS[d1]['label']} → {DIMENSIONS[d2]['label']}），"
                      f"不可直接换算；% 与 mg/L 之间换算需先提供同温度密度，属缺条件")
    if d1 == "℃":
        if _tok(u1) == _tok(u2):
            return value, f"{value:g} {u2}（同单位）"
        nv = temperature_convert(value, u1, u2)
        return nv, f"{value:g} {unit_from} = {nv:.4g} {unit_to}（仿射换算 F=(C×9/5+32)）"
    if d1 == "定性":
        return value, "定性指标，不做数值换算"
    f1 = DIMENSIONS[d1]["members"][u1]
    f2 = DIMENSIONS[d1]["members"][u2]
    if abs(f1 - f2) < 1e-18:
        return value, f"{value:g} {unit_to}（同单位）"
    nv = value * f1 / f2
    return nv, f"{value:g} {unit_from} × {f1:g}/{f2:g} = {nv:.6g} {unit_to}"


def exact_score(dim, unit):
    """判断换算是否"精确可逆"。ppm↔% 涉及 1e-4 的十进制比例，属精确；
    ppm↔ppb 在不同起草人手里有 1/1000 还是 1/100 的歧义，标记为"按 1 ppb=0.001 ppm"。"""
    if dim in ("%", "g/kg") and _tok(unit) in ("ppm", "ppb", "mg/kg", "μg/kg", "ug/kg"):
        return False
    return True


# --------------------------------------------------------------------------------------
# 2. 数值 / 限值解析
# --------------------------------------------------------------------------------------

NUM_RE = r"[-+]?\d+(?:[.,]\d+)?"
LOD_RE = re.compile(r"(?:[<＜≤]\s*=?\s*|小于\s*|低于\s*|不超过\s*)(\d+(?:[.,]\d+)?)")
RANGE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:~|～|〜|-|－|—|至|到|\+/-|±)\s*(\d+(?:[.,]\d+)?)")
QUAL_PASS = ("通过", "合格", "符合", "无", "未检出", "nd", "pass", "ok", "-", "—", "无浑浊", "澄清",
             "无色", "透明", "无机械杂质", "无异臭", "无刺激性气味")
QUAL_FAIL = ("不通过", "不合格", "不符合", "有", "fail", "浊", "混浊", "有色", "杂质", "异味", "臭")
QUAL_KEYWORDS = ("无色透明", "无可见机械杂质", "无机械杂质", "透明", "澄清", "无悬浮物")
QUAL_NEGATIVE = ("微带浅黄", "浅黄", "黄色", "微黄", "发黄", "浑浊", "混浊", "略差", "有色", "沉淀", "悬浮物",
                 "分层", "异味", "杂质")


def _norm_text(s):
    return (str(s or "").replace(" ", "").replace("，", "、").replace(",", "、")
            .replace("；", "、").replace(";", "、"))


def _num(s):
    return float(str(s).replace(",", "."))


def parse_value(raw, kind_hint=None):
    """把 COA/规格里的"值"解析成结构化 dict。

    返回 {"kind": single|max|min|unspecified|range|nd|lod|text,
          "value": float|None, "range": (lo,hi)|None, "text": str, "display": str}
    kind_hint: "ref"(实测值) / "limit"(限值) —— 影响 "<" 的语义：
      ref 里的 "<5" 是"低于检出限/低于量化限"；limit 里的 "<5" 是上限 5。
    """
    out = {"kind": "unspecified", "value": None, "range": None, "text": "", "display": ""}
    if raw is None:
        out["display"] = "（空）"
        return out
    s = str(raw).strip()
    out["display"] = s
    if s == "":
        return out
    low = s.lower()
    if low in ("/", "未测", "未检测", "n/a", "na", "—未测"):
        out["kind"] = "unspecified"
        return out

    # 未检出 / ND
    if re.fullmatch(r"(未检出|未测出|nd|n\.d\.|n\.d|not detected|未检出\(nd\))", low):
        out["kind"] = "nd"
        out["text"] = "未检出"
        return out
    # 低于检出限
    m = re.match(r"^\s*(?:[<＜]|小于|低于)\s*(?:=\s*)?(\d+(?:[.,]\d+)?)\s*(.*)$", s)
    if m:
        v = _num(m.group(1))
        tail = m.group(2).strip()
        out["value"] = v
        out["text"] = tail
        out["kind"] = "lod" if kind_hint != "limit" else "max"
        if kind_hint == "limit":
            out["value"] = v
        out["display"] = s
        return out
    # ≤ / ≥
    m = re.match(r"^\s*(?:[≤＜<]\s*=|不大于|不超过|最高|至多|≤|＜)\s*(\d+(?:[.,]\d+)?)\s*(.*)$", s)
    if m:
        out["kind"], out["value"], out["text"] = "max", _num(m.group(1)), m.group(2).strip()
        return out
    m = re.match(r"^\s*(?:[≥＞>]\s*=|不低于|不小于|最低|至少|≥|＞)\s*(\d+(?:[.,]\d+)?)\s*(.*)$", s)
    if m:
        out["kind"], out["value"], out["text"] = "min", _num(m.group(1)), m.group(2).strip()
        return out
    # 范围
    m = RANGE_RE.search(s)
    if m:
        lo, hi = _num(m.group(1)), _num(m.group(2))
        if re.search(r"\+/-|±", s):
            c = _num(m.group(1))
            lo, hi = c - _num(m.group(2)), c + _num(m.group(2))
        out["kind"], out["range"] = "range", (min(lo, hi), max(lo, hi))
        out["text"] = s[m.end():].strip()
        return out
    # 纯数值
    m = re.match(r"^\s*([-+]?\d+(?:[.,]\d+)?)\s*(.*)$", s)
    if m:
        out["kind"], out["value"], out["text"] = "single", _num(m.group(1)), m.group(2).strip()
        return out
    # 定性
    out["kind"] = "text"
    if low in QUAL_PASS:
        out["text"] = s
        out["value"] = 1.0
    elif low in QUAL_FAIL:
        out["text"] = s
        out["value"] = 0.0
    else:
        out["text"] = s
    return out


def limit_eval(v, ref):
    """实测值 v 对限值 ref（parse_value 结果）是否满足。返回 (ok, reason)。"""
    if ref["kind"] == "unspecified":
        return None, "规格未约定"
    if ref["kind"] == "max":
        return (v <= ref["value"] + 1e-12), f"实测 {v:g} / 上限 {ref['value']:g}"
    if ref["kind"] == "min":
        return (v >= ref["value"] - 1e-12), f"实测 {v:g} / 下限 {ref['value']:g}"
    if ref["kind"] == "range":
        lo, hi = ref["range"]
        return (lo - 1e-12 <= v <= hi + 1e-12), f"实测 {v:g} / 范围 {lo:g}~{hi:g}"
    if ref["kind"] == "single":
        return abs(v - ref["value"]) <= max(1e-9, abs(ref["value"]) * 1e-6), \
            f"实测 {v:g} / 规定值 {ref['value']:g}"
    if ref["kind"] == "text":
        if ref["value"] == 1.0:
            return (v == 1.0), "定性：应为" + ref["display"]
        if ref["value"] == 0.0:
            return (v == 0.0), "定性：应为" + ref["display"]
        return None, "限值为描述性要求，需人工判定"
    return None, "限值类型不可计算"


# --------------------------------------------------------------------------------------
# 3. 判定状态
# --------------------------------------------------------------------------------------

def determine_status(ref, ref_unit, meas_unit, comp, cmp_mode=None, nd_allowed=False,
                     lim=None):
    """返回 (status, reason, notes[])。

    ref, lim: parse_value 结果（lim 为规格侧解析结果，用于"规格是否约定"判断）
    优先级（固定，不允许调换）：
      规格未约定 → COA未检测 → 无法判断(可比性) → 符合/不符合
    """
    notes = []
    # 3.1 规格是否约定
    if lim is not None and lim["kind"] == "unspecified":
        return ST_UNSPEC, "采购规格书未对该指标约定限值，供应商建议值不作为验收依据", notes
    if lim is None and ref["kind"] == "unspecified":
        return ST_UNSPEC, "采购规格书未对该指标约定限值", notes
    # 3.2 COA 是否检测
    if ref["kind"] == "unspecified":
        return ST_UNTESTED, "COA 该行数值为空、为斜杠或标注未测", notes
    # 3.3 可比性
    bad = [d for d, ok in comp.items() if not ok and d != "_why"]
    if bad:
        why = comp.get("_why", {})
        return ST_UNKNOWN, "可比性不满足：" + "；".join(
            f"{COMP_DIMS[d]}{('（' + why[d] + '）') if why.get(d) else ''}" for d in bad), notes
    # 3.4 数值判断
    R = ref
    if R["kind"] == "nd":
        if nd_allowed:
            notes.append("规格允许'未检出'（≤检出限）")
            return ST_OK, "未检出，且规格采用上限表述，视为满足", notes
        if ref_unit and ref_unit != "" and re.search(r"[<≤]", ref["display"]):
            pass
        return ST_UNTESTED, "COA 报'未检出'但未给出检出限数值，无法与限值比较", notes
    if R["kind"] == "lod":
        # 实测 <LOD，规格为上限：若 LOD ≤ 上限 → 满足；否则无法判断
        val_conv, nv = convert(R["value"], ref_unit, meas_unit)
        if val_conv is None:
            return ST_UNKNOWN, nv, notes
        if nv:
            notes.append(nv)
        if lim is not None and lim["kind"] == "max":
            limv, ln = convert(lim["value"], ref_unit, meas_unit)
            if limv is None:
                return ST_UNKNOWN, ln, notes
            if nv:
                notes.append("规格上限=" + ln)
            if val_conv <= limv + 1e-12:
                notes.append("检出限不高于规格上限，未检出即满足上限要求")
                return ST_OK, f"实测低于检出限 {R['value']:g}{ref_unit}，检出限≤上限 {lim['value']:g}{ref_unit}", notes
            return ST_UNKNOWN, (f"实测仅报'低于检出限 {R['value']:g}{ref_unit}'，而检出限高于规格上限，"
                                f"无法确认是否达标"), notes
        if lim is not None and lim["kind"] in ("min", "range"):
            lo = lim["value"] if lim["kind"] == "min" else lim["range"][0]
            lov, ln2 = convert(lo, ref_unit, meas_unit)
            if lov is None:
                return ST_UNKNOWN, ln2, notes
            if val_conv < lov:
                notes.append("实测未达检出限且检出限低于规格下限 → 判不符合成立")
                return ST_FAIL, f"低于检出限 {R['value']:g}{ref_unit}，规格下限 {lo:g}{ref_unit}", notes
            return ST_UNKNOWN, "低于检出限，但检出限不低于下限，不能认定不符合", notes
        return ST_UNKNOWN, "低于检出限，规格限值类型不支持推断", notes
    if R["kind"] == "text":
        # 定性/描述性：只做"客观可判定"的部分
        #   - 规格里的关键词全部在 COA 描述中出现 → 符合（如"无色透明、无可见机械杂质"全部出现）
        #   - COA 出现规格禁止字样或相反表述（微带浅黄色 / 透明度略差）→ 不符合，且理由是词面证据
        #   - 其余 → 无法判断，交人工比对（不替人判定目视结果）
        if lim is None or lim["kind"] == "text" and not lim["text"] and not lim["value"]:
            return ST_UNKNOWN, "规格侧未给出定性要求", notes
        spec_txt = str(lim["display"] or "")
        coa_txt = str(R["display"] or "")
        s_norm = _norm_text(spec_txt)
        c_norm = _norm_text(coa_txt)
        kw = [k for k in QUAL_KEYWORDS if k in s_norm]
        if kw and all(k in c_norm for k in kw):
            return ST_OK, f"COA 描述「{coa_txt}」覆盖规格要求「{spec_txt}」的全部要素", notes
        neg = [k for k in QUAL_NEGATIVE if k in c_norm and k not in s_norm]
        if (kw or neg) and neg:
            return ST_FAIL, (f"COA 描述「{coa_txt}」出现与规格「{spec_txt}」相悖的表述：" +
                             "、".join(neg) + "；目视结论以原始照片/样品复核为准"), notes
        return ST_UNKNOWN, (f"定性/描述性指标，需人工比对：实测「{coa_txt}」，约定「{spec_txt}」"), notes
    if R["kind"] not in ("single", "max", "min", "range"):
        return ST_UNKNOWN, "实测值结构不支持自动判断", notes

    # 实测值代表值（对范围取中值，并标注）
    if R["kind"] == "range":
        v = (R["range"][0] + R["range"][1]) / 2.0
        notes.append(f"实测为范围 {R['range'][0]:g}~{R['range'][1]:g}，按中值 {v:g} 比较，需人工确认")
    elif R["kind"] == "min" and lim["kind"] == "min":
        v = R["value"]
    elif R["kind"] == "max" and lim["kind"] == "max" and cmp_mode != "strict":
        v = R["value"]
        notes.append("COA 以'≤'表述实测值，按上限值保守比较")
    else:
        v = R["value"]
    # 微量杂质结构检出限：COA 只写一个数值（在 ≤ 规格上限的 1/5 处），这在仪器法 COA 里
    # 实际表示"低于报告下限/LOD"，而不是测得了一个精确值。必须提示人工确认，不得当成合格结论。
    trig = _lod_structure(ref, lim, ref_unit, meas_unit)
    if trig:
        notes.append(trig)
        return ST_UNKNOWN, trig, notes

    vc, nv = convert(v, ref_unit, meas_unit)
    if vc is None:
        return ST_UNKNOWN, nv, notes
    if nv and "×" in nv:
        notes.append("单位换算：" + nv)
        cross = _crosses_limit(v, vc, ref_unit, meas_unit, lim)
        if cross:
            notes.append(cross)
    ok, reason = limit_eval(vc, lim)
    if ok is None:
        return ST_UNKNOWN, reason, notes
    return (ST_OK if ok else ST_FAIL), reason, notes


def _digits(v):
    """原文有效数字位数量级（1.5→0.1，0.0015→0.0001，1.112→0.001）。"""
    d = format(float(v), ".12g")
    if "e" in d or "E" in d:
        mant, _ = re.split("[eE]", d)
    else:
        mant = d
    if "." in mant:
        return 10 ** (-len(mant.split(".")[1]))
    return 1.0


def _lod_structure(ref, lim, ref_unit, meas_unit):
    """识别"检出限被写成一个实测值"的结构性异常。返回提示串或 None。"""
    if ref["kind"] not in LOD_KINDS or lim is None or lim["kind"] != "max":
        return None
    if ref["value"] is None or lim["value"] in (None, 0):
        return None
    if _digits(ref["value"]) > _digits(lim["value"]):
        return None
    try:
        th = convert(lim["value"] * 0.2, ref_unit, meas_unit)[0]
    except TypeError:
        return None
    if th is None:
        return None
    if ref["value"] <= th + 1e-15:
        return (f"数值结构提示：COA 报 {ref['display']} {ref_unit}，为规格上限 {lim['display']} {ref_unit} 的"
                f"五分之一量级（低一个数量级），常见于仪器法'低于报告下限/检出限即按 LOD 值报出'的写法。"
                f"该数可能是检出限而非真实测得值，需人工确认原始图谱与检出限，不能直接判符合")
    return None


def _crosses_limit(v, vc, ref_unit, meas_unit, lim):
    """换算后是否跨过判定线（单位/量级错误的典型症状）。"""
    try:
        a, _ = limit_eval(v, lim)
        b, _ = limit_eval(vc, lim)
    except TypeError:
        return None
    if a is None or b is None or a == b:
        return None
    return (f"⚠ 换算前后判定结论发生变化（{v:g} {ref_unit} → {vc:.6g} {meas_unit}）："
            f"换算前{'符合' if a else '不符合'}、换算后{'符合' if b else '不符合'}。"
            f"这通常意味着 COA 单位标注或小数点有误，必须人工复核原件，禁止按任一结果下结论")


# --------------------------------------------------------------------------------------
# 4. 偏离程度
# --------------------------------------------------------------------------------------

def deviation(status, ref, ref_unit, lim, meas_unit):
    """返回偏离 dict：direction / absolute / pct / mde / formula / human。"""
    d = {"direction": "", "absolute": None, "pct": None, "mde": None,
         "formula": "", "human": ""}
    if status != ST_FAIL or lim is None:
        return d
    if ref["kind"] in ("unspecified", "nd", "text", "lod"):
        d["human"] = "非数值型不符合，不做百分比偏离，按定性结论处理"
        return d
    v = ref["value"] if ref["kind"] not in ("range",) else (ref["range"][0] + ref["range"][1]) / 2.0
    vc, _ = convert(v, ref_unit, meas_unit)
    if vc is None:
        d["human"] = "量纲不一致，不做偏离计算"
        return d
    if lim["kind"] == "max":
        L = lim["value"]
        d["direction"] = "超上限"
        d["absolute"] = vc - L
        d["pct"] = (vc - L) / L * 100 if L else None
        d["formula"] = f"(实测 {vc:g} − 上限 {L:g}) ÷ 上限 {L:g} × 100% = {d['pct']:+.2f}%"
        d["human"] = f"超出上限 {d['absolute']:g}{meas_unit}（{d['pct']:+.2f}%）"
    elif lim["kind"] == "min":
        L = lim["value"]
        d["direction"] = "低于下限"
        d["absolute"] = L - vc
        d["pct"] = (L - vc) / L * 100 if L else None
        d["formula"] = f"(下限 {L:g} − 实测 {vc:g}) ÷ 下限 {L:g} × 100% = {d['pct']:.2f}%"
        d["human"] = f"低于下限 {d['absolute']:g}{meas_unit}（{d['pct']:.2f}%）"
    elif lim["kind"] == "range":
        lo, hi = lim["range"]
        if vc > hi:
            d["direction"], d["absolute"], d["pct"] = "超上限", vc - hi, (vc - hi) / hi * 100
            d["formula"] = f"(实测 {vc:g} − 上限 {hi:g}) ÷ 上限 {hi:g} × 100% = {d['pct']:+.2f}%"
            d["human"] = f"超出范围上限 {d['absolute']:g}{meas_unit}（{d['pct']:+.2f}%）"
        else:
            d["direction"], d["absolute"], d["pct"] = "低于下限", lo - vc, (lo - vc) / lo * 100
            d["formula"] = f"(下限 {lo:g} − 实测 {vc:g}) ÷ 下限 {lo:g} × 100% = {d['pct']:.2f}%"
            d["human"] = f"低于范围下限 {d['absolute']:g}{meas_unit}（{d['pct']:.2f}%）"
    elif lim["kind"] == "single":
        L = lim["value"]
        d["direction"] = "偏离规定值"
        d["absolute"] = vc - L
        d["pct"] = (vc - L) / L * 100 if L else None
        d["formula"] = f"(实测 {vc:g} − 规定值 {L:g}) ÷ 规定值 {L:g} × 100% = {d['pct']:+.2f}%"
        d["human"] = f"偏离规定值 {d['absolute']:g}{meas_unit}（{d['pct']:+.2f}%）"
    # 最小可检测偏离（MDE）：限值口径下，一个末位单位所对应的百分比
    if lim.get("value") and lim["kind"] in ("max", "min"):
        decimals = 0
        m = re.search(r"\.(\d+)", str(lim["display"]))
        if m:
            decimals = len(m.group(1))
        step = 10 ** (-decimals)
        d["mde"] = step / abs(lim["value"]) * 100
        d["mde_note"] = f"限值末位 {step:g}{meas_unit}，一个末位约等于 {d['mde']:.4f}%"
    return d


# --------------------------------------------------------------------------------------
# 5. 批次趋势（历史批次对照）
# --------------------------------------------------------------------------------------

def trend_stats(series, lim=None, unit=""):
    """series: [(batch, date, value_or_None)]。返回统计与趋势描述。"""
    vals = [(b, d, v) for (b, d, v) in series if v is not None]
    out = {"n": len(vals), "min": None, "max": None, "mean": None, "sd": None,
           "first": None, "last": None, "delta_abs": None, "delta_pct": None,
           "direction": "", "oos": [], "desc": "", "series": vals}
    if not vals:
        out["desc"] = "无可用数值序列"
        return out
    xs = [v for (_, _, v) in vals]
    out["min"], out["max"] = min(xs), max(xs)
    out["mean"] = sum(xs) / len(xs)
    if len(xs) > 1:
        var = sum((x - out["mean"]) ** 2 for x in xs) / (len(xs) - 1)
        out["sd"] = math.sqrt(var)
    out["first"] = vals[0][2]
    out["last"] = vals[-1][2]
    out["delta_abs"] = out["last"] - out["first"]
    if out["first"]:
        out["delta_pct"] = out["delta_abs"] / out["first"] * 100
    span = out["max"] - out["min"]
    if abs(out["delta_abs"]) <= max(1e-12, span * 0.05) and len(xs) > 2:
        out["direction"] = "平稳"
    elif out["delta_abs"] > 0:
        out["direction"] = "上升"
    elif out["delta_abs"] < 0:
        out["direction"] = "下降"
    else:
        out["direction"] = "平稳"
    if lim is not None and lim["kind"] in ("max", "min", "range"):
        lo = lim["value"] if lim["kind"] == "min" else (lim["range"][0] if lim["kind"] == "range" else None)
        hi = lim["value"] if lim["kind"] == "max" else (lim["range"][1] if lim["kind"] == "range" else None)
        for (b, d, v) in vals:
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                out["oos"].append((b, v))
    # 趋势描述（只陈述事实）
    parts = [f"{len(xs)} 个批次", f"均值 {out['mean']:.4g}{unit}",
             f"区间 {out['min']:.4g}~{out['max']:.4g}{unit}"]
    if out["sd"] is not None:
        parts.append(f"标准差 {out['sd']:.3g}")
    if out["delta_pct"] is not None and abs(out["delta_pct"]) > 0.01:
        parts.append(f"首末批{out['direction']} {out['delta_abs']:+.4g}{unit}（{out['delta_pct']:+.2f}%）")
    else:
        parts.append("首末批基本持平")
    if out["oos"]:
        parts.append("越限批次：" + "、".join(f"{b}({v:g})" for b, v in out["oos"]))
    out["desc"] = "；".join(parts)
    return out


# --------------------------------------------------------------------------------------
# 6. 检出限、方法与基准
# --------------------------------------------------------------------------------------

def parse_lod(s):
    """从"检出限：0.5 ppm"或"<0.5"解析出 (lod_value, lod_unit)。"""
    if not s:
        return None, None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*([a-zA-Z%℃/·³µμ]*\s*/\s*[a-zA-Z]+|%|ppm|ppb)?", str(s))
    if not m:
        return None, None
    return _num(m.group(1)), (m.group(2) or "").strip()


def method_id(s):
    """归一化检测方法编号：GB/T 14571.2-2018 / GB/T 14571.2 / gbt14571.2 → gbt14571.2

    保留标准号本体与部分，去掉年代号与排版差异；不同年代号视为同一方法编号
    （是否等效另由 method_relation + equivalent_methods 决定）。
    """
    if not s:
        return ""
    t = str(s).upper().replace("／", "/").replace("—", "-").replace("－", "-")
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[-:]\d{4}$", "", t)                 # 去年代号（-2018 / -16 / 2018）
    t = re.sub(r"[()（）\s]", "", t)
    t = t.replace("GB/T", "GBT").replace("GBT/", "GBT").replace("/T", "T")
    t = t.replace("HG/T", "HGT").replace("SH/T", "SHT").replace("/", "")
    t = t.replace("GBZ", "GBZT").replace("JJF", "JJF")
    return t


def method_relation(m_coa, m_spec, eq_methods=None):
    """判断 COA 方法 vs 合同方法的关系：same / equivalent / different / missing_*。"""
    a, b = method_id(m_coa), method_id(m_spec)
    if not a and not b:
        return "both_missing"
    if not a:
        return "missing_coa"
    if not b:
        return "missing_spec"
    if a == b:
        return "same"
    for grp in (eq_methods or []):
        ids = [method_id(x) for x in grp]
        if a in ids and b in ids:
            return "equivalent"
    return "different"


# --------------------------------------------------------------------------------------
# 7. 日期与批号
# --------------------------------------------------------------------------------------

DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日", "%Y-%m-%d %H:%M",
                "%Y/%m/%d %H:%M", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d", "%Y-%m", "%Y/%m")


def parse_date(s):
    """返回 (date|None, 原文, 提示)。识别不了不猜，返回提示。"""
    if s is None:
        return None, "", "日期为空"
    t = str(s).strip()
    if t == "":
        return None, t, "日期为空"
    for f in DATE_FORMATS:
        try:
            return _dt.datetime.strptime(t, f).date(), t, ""
        except ValueError:
            continue
    # 去中文空白再试
    t2 = re.sub(r"\s+", "", t)
    for f in DATE_FORMATS:
        try:
            return _dt.datetime.strptime(t2, f).date(), t, ""
        except ValueError:
            continue
    return None, t, f"日期格式无法识别：{t!r}，需人工确认（不猜测年份/月日顺序）"


def date_gap(d1, d2):
    if not d1 or not d2:
        return None
    return (d2 - d1).days


def batch_key(b):
    return re.sub(r"[\s\-_/]", "", str(b or "")).upper()


# --------------------------------------------------------------------------------------
# 8. 可比性判定（5 维）
# --------------------------------------------------------------------------------------

def comparability(item, aliases_by_key, eq_methods, product_basis=None):
    """item 需含 name / ref_unit / meas_unit / method_coa / method_spec / basis_coa / basis_spec。"""
    comp = OrderedDict((k, True) for k in COMP_DIMS)
    why = {}
    # 名称：同义词表命中即视为对应（名称不一致但同义 → True，并记录）
    key = item["name_key"]
    entry = aliases_by_key.get(key)
    if entry is None:
        comp["name"] = False
        why["name"] = "指标名称未在别名表中命中，需人工确认是否为同一指标"
    # 量纲
    d1, u1 = unit_token(item.get("meas_unit") or item.get("ref_unit"))
    d2, u2 = unit_token(item.get("ref_unit") or item.get("meas_unit"))
    if d1 is None or d2 is None:
        comp["dimension"] = False
        why["dimension"] = f"单位无法识别：COA={item.get('ref_unit')!r} 规格={item.get('meas_unit')!r}"
    elif d1 != d2:
        comp["dimension"] = False
        why["dimension"] = f"量纲不同：COA={item.get('ref_unit')} 规格={item.get('meas_unit')}"
    # 方法
    rel = method_relation(item.get("method_coa"), item.get("method_spec"), eq_methods)
    item["_method_relation"] = rel
    if rel == "different":
        comp["method"] = False
        why["method"] = f"COA 用 {item.get('method_coa')}，约定 {item.get('method_spec')}"
    elif rel == "missing_coa":
        comp["method"] = False
        why["method"] = "COA 未标注检测方法，无法确认方法差异"
    elif rel == "missing_spec":
        # 规格未写方法而 COA 写了 → 以标准方法为参照，可判但需注明
        comp["method"] = True
        why["method"] = "规格未约定检测方法，已按适用标准方法参照"
    elif rel == "both_missing":
        comp["method"] = True
        why["method"] = "双方均未标注检测方法，仅按数值比较，方法一致性未经验证"
    # 基准
    b1 = (item.get("basis_coa") or "as_received")
    b2 = (item.get("basis_spec") or "as_received")
    if b1 != b2:
        comp["basis"] = False
        why["basis"] = f"COA 为 {basis_label(b1)}，规格为 {basis_label(b2)}，缺换算系数"
    if product_basis and b1 != product_basis and b2 != product_basis:
        why.setdefault("basis", "")
        why["basis"] = (why["basis"] + "；" if why["basis"] else "") + \
            f"双方均非 {basis_label(product_basis)}"
    item["_why"] = why
    comp["_why"] = why
    return comp


def basis_label(b):
    return {"as_received": "到货/收货基准（湿基）", "dry": "干基", "pure": "折百",
            "anhydrous": "无水基", "as_is": "原液"}.get(b or "as_received", b)


def fallback_method(item):
    """双方都没写方法时，若同一指标在 other_sources 里给了方法，允许作为参照。"""
    return bool(item.get("method_ref_fallback"))


# --------------------------------------------------------------------------------------
# 9. 规格侧自动生成（缺规格书时的建议限值）
# --------------------------------------------------------------------------------------

def infer_spec(item):
    """生产规格自动生成：取 上/下限 中最宽者；范围取并集。来源标记 ref_auto=True。
    仅用于"规格未约定"时的提示——绝不把建议值当验收依据，判断状态仍为 规格未约定。"""
    vals = []
    for src in item.get("other_sources", []):
        p = parse_value(src.get("value", ""))
        if p["kind"] in ("single", "max", "min") and p["value"] is not None:
            vals.append((p["kind"], p["value"], src))
        elif p["kind"] == "range":
            vals.append(("range", p["range"], src))
    if not vals:
        return None
    kinds = {k for k, _, _ in vals}
    if kinds == {"single"}:
        ns = [v for _, v, _ in vals]
        return {"limit_display": f"{min(ns):g}~{max(ns):g}", "unit": item.get("spec_unit") or item.get("meas_unit"),
                "basis": "生产规格区间（各来源取并集）", "ref_auto": True,
                "source": "；".join(s.get("source", "") for _, _, s in vals)}
    lo = max(v for k, v, _ in vals if k == "min") if "min" in kinds else None
    hi = min(v for k, v, _ in vals if k == "max") if "max" in kinds else None
    lomax = max((v for k, v, _ in vals if k == "range"), key=lambda r: r[1], default=None)
    if hi is None and lomax:
        hi = lomax[1]
    if lo is None and lomax:
        lo = lomax[0]
    if lo is not None and hi is not None:
        disp = f"{lo:g}~{hi:g}"
    elif hi is not None:
        disp = f"≤{hi:g}"
    else:
        disp = f"≥{lo:g}"
    return {"limit_display": disp, "unit": item.get("spec_unit") or item.get("meas_unit"),
            "basis": "生产规格（各来源取最宽值）", "ref_auto": True,
            "source": "；".join(s.get("source", "") for _, _, s in vals)}


# --------------------------------------------------------------------------------------
# 10. 总计
# --------------------------------------------------------------------------------------

def summarize(statuses):
    out = OrderedDict((s, 0) for s in STATUS_SET)
    for s in statuses:
        out[s] = out.get(s, 0) + 1
    return out


def human_dt(d):
    return d.isoformat() if isinstance(d, (_dt.date, _dt.datetime)) else ("" if d is None else str(d))


def fmt(v, nd=4):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.{nd}g}" if abs(v) >= 1e-4 or v == 0 else f"{v:.3e}"
    return str(v)


__all__ = [
    "ST_OK", "ST_FAIL", "ST_UNSPEC", "ST_UNTESTED", "ST_UNKNOWN", "STATUS_SET", "HIT_STATUS",
    "SEV", "SEV_ORDER", "COMP_DIMS", "DIMENSIONS", "unit_token", "convert", "parse_value",
    "limit_eval", "determine_status", "deviation", "trend_stats", "parse_lod", "method_id",
    "method_relation", "parse_date", "date_gap", "batch_key", "comparability", "infer_spec",
    "summarize", "basis_label", "human_dt", "fmt",
]
