# -*- coding: utf-8 -*-
"""跨单证比对引擎：字段矩阵 / 计算核验 / 问题清单。

设计要点
--------
1. 不是"字段不同即冲突"。每个字段带 kind：
   * fact —— 业务事实，必须跨单据一致（品名、CAS、HS、数量、金额、币种、港口…）
   * role —— 取决于单据用途，允许合理不同（卖方=承运人提单 shipper、买方 vs 收货人）
   * calc —— 计算派生量，靠"关系式"校验而不是直接比对
2. 状态取值：OK 一致 / DIFF 不一致 / MISS 缺失 / CALC 计算不符 / NA 本单证不适用 / UNK 无法判断
3. 任何"读不清/读不到"的数值都标记 UNK 并要求人工确认，绝不猜测。
"""
import re
from typing import Any, Dict, List, Optional

from taxonomy import (CALC_FIELDS, DOC_FIELDS, DOC_TYPES, FACT_FIELDS, FIELDS,
                      FIELD_BY_ID, GROUP_LABEL, NOT_EXPECTED, SEVERITY, STATUS,
                      expected_fields)

# ---------------------------------------------------------------- 归一化
CJK = re.compile(r"[\u4e00-\u9fff]")
NUM_RX = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")
UNIT_RX = re.compile(r"\b(KG|KGS|MT|MTS|T|TON|TONS|CBM|M3|BAG|BAGS|CTNR|CNTR|PCS)\b", re.I)

UNIT_FACTOR = {  # 折成 KG / MT / CBM
    "KG": 1.0, "KGS": 1.0,
    "MT": 1000.0, "MTS": 1000.0, "T": 1000.0, "TON": 1000.0, "TONS": 1000.0,
    "CBM": 1.0, "M3": 1.0,
}


def parse_num(s: Any) -> Optional[float]:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = NUM_RX.search(str(s).replace(" ", ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def parse_qty(s: Any) -> Optional[Dict[str, Any]]:
    """把 "1,000.000 MT" / "1,000,000.000 KG" 解析成 {value, unit, base_kg}。"""
    if not s:
        return None
    txt = str(s)
    v = parse_num(txt)
    if v is None:
        return None
    m = UNIT_RX.search(txt)
    unit = m.group(1).upper() if m else ""
    if unit in ("MTS",):
        unit = "MT"
    if unit in ("KGS",):
        unit = "KG"
    if unit in ("TON", "TONS"):
        unit = "T"
    if unit in ("M3",):
        unit = "CBM"
    factor = UNIT_FACTOR.get(unit)
    return {"value": v, "unit": unit, "base": (v * factor) if factor else None,
            "comparable": factor is not None}


def norm_company(s: str) -> str:
    """公司名归一：大小写、标点、CO./LTD 等后缀差异不算冲突。

    但"主体 + 仓库/工厂"（PT X - GUDANG CIKARANG）与"PT X"是不同交货地址，
    比对时必须区分，因此保留仓库/工厂段，只做标点与法律后缀归一。
    """
    if not s:
        return ""
    t = str(s).upper()
    t = t.replace("­", "-")
    t = re.sub(r"[,.'\"()?]", " ", t)
    t = re.sub(r"\b(CO|COMPANY|LTD|LIMITED|INC|CORP|CORPORATION|LLC|SDN|BHD)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def norm_id(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"[^0-9A-Z]", "", str(s).upper())


def norm_port(s: str) -> str:
    """港口归一：去国家/别名、含中文括注、取主港名。"""
    if not s:
        return ""
    t = str(s).upper()
    t = re.sub(r"[（(][^)）]*[)）]", " ", t)          # 去掉中文/英文括注
    t = re.sub(r"\b(PORT OF|PORT|CITY|CHINA|INDONESIA|JAKARTA|CN|ID)\b", " ", t)
    t = re.sub(r"[.,]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def norm_incoterm(s: str) -> Dict[str, str]:
    """CFR TANJUNG PRIOK, JAKARTA, INDONESIA (INCOTERMS 2020) → {term:CFR, place:...}"""
    if not s:
        return {}
    t = str(s).upper()
    m = re.match(r"\s*(EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DAP|DPU|DDP)\b", t)
    term = m.group(1) if m else ""
    rest = t[m.end():] if m else t
    rest = re.sub(r"[（(][^)）]*[)）]", " ", rest)
    rest = re.sub(r"INCOTERMS\s*\d{4}", " ", rest)
    return {"term": term, "place": norm_port(rest)}


def norm_date(s: str) -> str:
    if not s:
        return ""
    m = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", str(s))
    if m:
        return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return str(s).strip()


def norm_product(s: str) -> str:
    """品名归一：去掉括注、规格词、括号内中文，只留核心英文/中文名。"""
    if not s:
        return ""
    t = str(s)
    out_en, out_cn = [], []
    for m in re.finditer(r"([A-Z][A-Z0-9 &'\-/\.]{2,})|([\u4e00-\u9fff]{2,})", t):
        if m.group(1):
            out_en.append(m.group(1).strip())
        else:
            out_cn.append(m.group(2))
    return (" ".join(out_en) or " ".join(out_cn)).strip()


# ---------------------------------------------------------------- 比对规则
def values_match(fid: str, a: str, b: str) -> Optional[bool]:
    """两个值是否"实质上一致"。返回 None 表示无法判断。"""
    f = FIELD_BY_ID.get(fid) or {}
    fmt = f.get("fmt", "text")
    if not a or not b:
        return None
    if fmt in ("num", "money", "int"):
        qa, qb = parse_qty(a), parse_qty(b)
        if qa and qb:
            if qa["comparable"] and qb["comparable"]:
                if qa["unit"] and qb["unit"] and qa["unit"] != qb["unit"]:
                    return abs(qa["base"] - qb["base"]) < 0.51
                return abs(qa["value"] - qb["value"]) < 0.51
            return abs(qa["value"] - qb["value"]) < 0.51
        return None
    if fmt == "code":
        na, nb = norm_id(a), norm_id(b)
        if fid in ("incoterm",):
            ia, ib = norm_incoterm(a), norm_incoterm(b)
            return ia.get("term") == ib.get("term")
        if fid in ("pol", "pod", "final_dest"):
            pa, pb = norm_port(a), norm_port(b)
            return bool(pa and pb) and (pa in pb or pb in pa)
        if fid in ("currency",):
            return re.sub(r"[^A-Z]", "", a.upper()) == re.sub(r"[^A-Z]", "", b.upper())
        if fid == "vessel_voyage":
            va = re.sub(r"[^A-Z0-9]", "", a.upper())
            vb = re.sub(r"[^A-Z0-9]", "", b.upper())
            return bool(va) and (va in vb or vb in va)
        return bool(na) and (na in nb or nb in na)
    if fmt == "hs":
        na = re.sub(r"\D", "", a)
        nb = re.sub(r"\D", "", b)
        return bool(na) and na == nb or (bool(na) and bool(nb) and na[:8] == nb[:8])
    if fmt == "cas":
        return re.sub(r"\D", "", a) == re.sub(r"\D", "", b)
    if fmt == "date":
        return norm_date(a) == norm_date(b)
    if fmt == "port":
        pa, pb = norm_port(a), norm_port(b)
        return bool(pa and pb) and (pa in pb or pb in pa)
    if fid in ("seller_name", "buyer_name", "consignee_name", "notify_name"):
        # 订货意图/指示类文字不是主体名称（"For Buyer's Confirmation" / "TO ORDER OF SHIPPER"）
        if re.search(r"CONFIRMATION|TO ORDER|AS PER|清关|确认", str(a).upper()) or \
           re.search(r"CONFIRMATION|TO ORDER|AS PER|清关|确认", str(b).upper()):
            return None
        ca, cb = norm_company(a), norm_company(b)
        if not ca or not cb:
            return None
        if ca == cb:
            return True
        # 允许 token 级包含（PT SAMUDRA ANDALAN KIMIA vs SAMUDRA ANDALAN KIMIA），
        # 但要求短的完整出现在长的里面且长度差不超过 2 个词
        wa, wb = ca.split(), cb.split()
        if (ca in cb or cb in ca) and abs(len(wa) - len(wb)) <= 2:
            return True
        # 去掉 IMPORT/EXPORT 后仍不同 → 视为不同主体
        return False
    if fid in ("product_name_en", "product_name_cn", "spec"):
        pa, pb = norm_product(a).upper(), norm_product(b).upper()
        if not pa or not pb:
            return None
        if pa == pb or pa in pb or pb in pa:
            return True
        # 共同词占比
        wa, wb = set(pa.split()), set(pb.split())
        if wa and wb and len(wa & wb) / float(min(len(wa), len(wb))) >= 0.75:
            return True
        return False
    if fid in ("marks",):
        ta = re.sub(r"[^0-9A-Z]", "", a.upper())
        tb = re.sub(r"[^0-9A-Z]", "", b.upper())
        return bool(ta) and (ta in tb or tb in ta)
    ta, tb = norm_id(a), norm_id(b)
    if ta and tb:
        return ta == tb or ta in tb or tb in ta
    return None


# ---------------------------------------------------------------- 计算核验
def _f(rec: Optional[Dict[str, Any]]) -> Optional[float]:
    if not rec:
        return None
    return parse_num(rec.get("value"))


def compute_checks(field_values: Dict[str, Dict[str, Dict[str, Any]]],
                   doc_texts: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """关系式核验。field_values: {doc_id: {fid: rec}}"""
    out: List[Dict[str, Any]] = []

    def get(fid, docs=None):
        for d, fields in field_values.items():
            if docs and d not in docs:
                continue
            if fid in fields:
                return fields[fid], d
        return None, None

    qty_rec, qty_doc = get("quantity")
    price_rec, price_doc = get("unit_price")
    amt_rec, amt_doc = get("amount")

    # 1) 数量 × 单价 = 金额。优先在同一张单证内自洽校验（商业发票），
    #    其次才跨单证组合 —— 跨单证组合只能发现"不一致"，不能直接断定谁错。
    same_doc = None
    for did, fields in field_values.items():
        if all(k in fields for k in ("quantity", "unit_price", "amount")):
            same_doc = did
            break
    if same_doc:
        qty_rec, price_rec, amt_rec = (field_values[same_doc]["quantity"],
                                       field_values[same_doc]["unit_price"],
                                       field_values[same_doc]["amount"])
        qty_doc = price_doc = amt_doc = same_doc
    if qty_rec and price_rec and amt_rec:
        q = parse_qty(qty_rec["value"])
        p = parse_num(price_rec["value"])
        a = parse_num(amt_rec["value"])
        if q and p and a and q["value"]:
            # 数量单位是 MT、单价是 /MT → 直接乘；数量是 KG 而单价 /MT 则换算
            factor = 1.0
            if q["unit"] == "KG" and "/MT" in str(price_rec.get("value", "")).upper():
                factor = 0.001
            calc = q["value"] * factor * p
            if abs(calc - a) > max(0.02, abs(a) * 0.0001):
                out.append({"id": "C1", "name": "数量 × 单价 = 总金额",
                            "expect": calc, "actual": a, "ok": False,
                            "docs": [qty_doc, price_doc, amt_doc],
                            "detail": "%s %s × %s = %s，单证金额为 %s" % (
                                fmt_money(q["value"]), q["unit"] or "", fmt_money(p),
                                fmt_money(calc), fmt_money(a))})
            else:
                out.append({"id": "C1", "name": "数量 × 单价 = 总金额",
                            "expect": calc, "actual": a, "ok": True, "docs": [qty_doc, price_doc, amt_doc],
                            "detail": "%s × %s = %s 与金额一致" % (
                                fmt_money(q["value"]), fmt_money(p), fmt_money(a))})

    # 2) 净重 = 单件净重 × 件数；毛重 = 净重 + 皮重
    net_rec, net_doc = get("net_weight")
    gross_rec, gross_doc = get("gross_weight")
    pkg_rec, pkg_doc = get("package_count")
    n, g, k = _f(net_rec), _f(gross_rec), _f(pkg_rec)
    if qty_rec and net_rec:
        q = parse_qty(qty_rec["value"])
        if q and q["base"] and n is not None:
            if abs(q["base"] - n) > max(1.0, n * 0.001):
                out.append({"id": "C2", "name": "数量与净重一致（1 MT = 1,000 KG）",
                            "expect": q["base"], "actual": n, "ok": False,
                            "docs": [qty_doc, net_doc],
                            "detail": "数量 %s %s 折合 %s KG，净重为 %s KG" % (
                                fmt_money(q["value"]), q["unit"], fmt_money(q["base"]), fmt_money(n))})
            else:
                out.append({"id": "C2", "name": "数量与净重一致（1 MT = 1,000 KG）",
                            "expect": q["base"], "actual": n, "ok": True, "docs": [qty_doc, net_doc],
                            "detail": "%s KG = %s MT" % (fmt_money(n), fmt_money(q["value"]))})
    if n is not None and g is not None:
        tare = round(g - n, 3)
        per_bag = (tare / k) if (k and k > 0) else None
        ok = tare > 0 and (per_bag is None or 1.0 <= per_bag <= 10.0)
        out.append({"id": "C3", "name": "毛重 − 净重 = 皮重（吨袋单件 1–10 KG 合理）",
                    "expect": tare, "actual": g - n, "ok": bool(ok),
                    "docs": [net_doc, gross_doc],
                    "detail": ("毛重 %s − 净重 %s = 皮重 %s KG%s" % (
                        fmt_money(g), fmt_money(n), fmt_money(tare),
                        "（单件 %s KG）" % fmt_money(round(per_bag, 2)) if per_bag is not None else ""))})
    # 3) 净重 = 件数 × 50 KG（1000KG 吨袋 / 1 MT 净重）
    if n is not None and k:
        per = n / k
        ok = abs(per - 1000.0) < 5.0
        out.append({"id": "C4", "name": "单件净重 = 净重 ÷ 件数（应为 1,000 KG/袋）",
                    "expect": 1000.0, "actual": round(per, 3), "ok": bool(ok),
                    "docs": [net_doc, pkg_doc],
                    "detail": "%s KG ÷ %s 袋 = %s KG/袋" % (fmt_money(n), fmt_money(k), fmt_money(round(per, 2)))})
    # 4) 体积：43 个 40'HQ 柜容量 vs 申报体积
    vol_rec, vol_doc = get("volume")
    v, c = _f(vol_rec), _f(pkg_rec)
    m_cnt = _container_count(field_values, doc_texts)
    if v is not None and m_cnt:
        ok = v <= m_cnt * 76.0
        out.append({"id": "C5", "name": "体积不超过柜型容量（40'HQ 约 67–76 CBM/柜）",
                    "expect": m_cnt * 76.0, "actual": v, "ok": bool(ok), "docs": [vol_doc],
                    "detail": "%s 个 40'HQ 最大约 %s CBM，申报体积 %s CBM%s" % (
                        m_cnt, fmt_money(m_cnt * 76.0), fmt_money(v),
                        "" if ok else "（已超出柜容量，装不下）")})
    # 6) 单据编号自洽：PI 号带多余后缀 / 与其它单证引用不符
    pi_rec, pi_doc = get("pi_no")
    if pi_rec:
        val = str(pi_rec.get("value", "")).strip()
        refs = []
        for d, fields in field_values.items():
            for other in ("contract_no", "ci_no"):
                r = fields.get(other)
                if r and "PI" in str(r.get("value", "")).upper():
                    refs.append(str(r["value"]))
        mismatched = [x for x in refs if x.upper() != val.upper()]
        if mismatched:
            out.append({"id": "C6", "name": "形式发票号与其它单证引用一致",
                        "expect": mismatched[0], "actual": val, "ok": False, "docs": [pi_doc],
                        "detail": "PI 号为 %s，其它单证引用为 %s" % (val, mismatched[0])})
        if re.search(r"\d{4}[A-Z]{1,3}$", val):
            out.append({"id": "C6", "name": "单据编号无多余后缀",
                        "expect": re.sub(r"[A-Z]+$", "", val), "actual": val, "ok": False,
                        "docs": [pi_doc],
                        "detail": "形式发票号 %s 末尾带多余字母后缀，易与信用证/发票引用不符" % val})
    return out


def _container_count(field_values, doc_texts=None):
    """找出柜数（43×40'HQ / 43 CTNR / 共 43 个 40'HQ 柜）。字段值优先，其次原文。"""
    pats = (r"(\d{1,3})\s*[X×*]\s*40", r"(\d{1,3})\s*(?:CTNR|CNTR|CONTAINERS?)",
            r"共\s*(\d{1,3})\s*个", r"(\d{1,3})\s*个\s*40")
    best = None
    pool = []
    for d, fields in field_values.items():
        for rec in fields.values():
            pool.append(str(rec.get("value", "")).upper())
    for txt in (doc_texts or {}).values():
        pool.append(txt.upper())
    for v in pool:
        for pat in pats:
            for m in re.finditer(pat, v):
                n = int(m.group(1))
                if 1 <= n <= 500 and (best is None or n > best):
                    best = n
    return best


def fmt_money(x: Any) -> str:
    if x is None:
        return "—"
    try:
        return "{:,.2f}".format(float(x)) if abs(float(x)) % 1 else "{:,.0f}".format(float(x))
    except (TypeError, ValueError):
        return str(x)


# ---------------------------------------------------------------- 矩阵
def build_matrix(docs: List[Dict[str, Any]], extra_status: Optional[Dict] = None) -> Dict[str, Any]:
    """docs: [{id, type, filename, pages, fields:{fid:rec}}] → 字段矩阵 + 结论"""
    extra_status = extra_status or {}
    field_values = {d["id"]: d["fields"] for d in docs}
    doc_types = {d["id"]: d["type"] for d in docs}

    # 需要参与比对的字段：至少出现在两份单据里的 fact 字段 + 所有已有字段
    seen_fields: List[str] = []
    for f in FIELDS:
        fid = f["id"]
        if any(fid in d["fields"] for d in docs):
            seen_fields.append(fid)

    matrix: List[Dict[str, Any]] = []
    for fid in seen_fields:
        meta = FIELD_BY_ID.get(fid) or {}
        row = {"field": fid, "cn": meta.get("cn", fid), "en": meta.get("en", ""),
               "group": meta.get("group", ""), "kind": meta.get("kind", "fact"),
               "unit": meta.get("unit", ""), "cells": {}}
        vals = {}
        for d in docs:
            did = d["id"]
            rec = d["fields"].get(fid)
            if rec is None:
                expected = fid in expected_fields(d["type"])
                row["cells"][did] = {"status": "MISS" if expected else "NA",
                                     "value": "", "page": None, "bbox": None,
                                     "note": "" if expected else "本单证不要求此字段"}
                continue
            vals[did] = rec
            row["cells"][did] = {"status": "OK", "value": rec.get("value", ""),
                                 "page": rec.get("page"), "bbox": rec.get("bbox"),
                                 "how": rec.get("how", ""), "note": ""}
        # 判定
        if len(vals) >= 2:
            items = list(vals.items())
            base_did, base_rec = items[0]
            diffs = []
            for did, rec in items[1:]:
                m = values_match(fid, base_rec.get("value", ""), rec.get("value", ""))
                if m is False:
                    diffs.append(did)
            if diffs:
                # 取"多数派"为基准
                groups = {}
                for did, rec in items:
                    key = None
                    for gk, members in groups.items():
                        if values_match(fid, field_values[gk[0]][fid]["value"] if False else vals[gk[0]]["value"],
                                        rec["value"]):
                            key = gk
                            break
                    if key is None:
                        groups[(did,)] = [did]
                    else:
                        groups[key].append(did)
                major = max(groups.values(), key=len)
                for did in row["cells"]:
                    if did not in vals:
                        continue
                    if did in major and len(major) < len(vals):
                        row["cells"][did]["status"] = "OK"
                    elif did in major:
                        row["cells"][did]["status"] = "DIFF"
                    else:
                        row["cells"][did]["status"] = "DIFF"
                        ref = vals[major[0]]["value"]
                        row["cells"][did]["note"] = "与 %s 不一致" % DOC_NAME.get(major[0], major[0])
                row["cells"][major[0]]["note"] = "与其他单证不一致"
            else:
                unknown = [did for did, rec in items
                           if values_match(fid, items[0][1].get("value", ""), rec.get("value", "")) is None]
                for did in vals:
                    row["cells"][did]["status"] = "UNK" if did in unknown else "OK"
        # "单证日期"是各单据自己的签发日，跨单证本就不应相同 → 只做单证内合理性判断
        if fid == "date":
            for did, cell in row["cells"].items():
                if cell["status"] in ("OK", "DIFF", "UNK"):
                    cell["status"] = "NA"
                    cell["note"] = "各单证签发日期不同属正常，不参与跨单证比对"
            matrix.append(row)
            continue
        # 单证自洽：编号类字段的"多余后缀/内部不一致"即使只有一份也要标出
        for did, cell in row["cells"].items():
            if cell["status"] == "OK" and _self_inconsistent(fid, cell["value"]):
                cell["status"] = "DIFF"
                cell["note"] = "编号格式异常（末尾多余后缀）"
        matrix.append(row)
    return {"matrix": matrix, "field_values": field_values, "doc_types": doc_types}


def _self_inconsistent(fid: str, val: str) -> bool:
    """仅一份单证时也能判定的自洽问题：编号末尾多出字母后缀（PI 号 0817A）。"""
    if fid not in ("pi_no", "ci_no", "contract_no", "co_no", "bl_no", "lc_no"):
        return False
    v = str(val or "").strip().upper()
    return bool(re.search(r"\d{4}[A-Z]{1,3}$", v))


DOC_NAME = {
    "SC": "销售合同", "PI": "形式发票", "CI": "商业发票", "PL": "装箱单", "BL": "提单",
    "COA": "COA", "SDS": "SDS", "CO": "原产地证", "CUSTOMS": "报关单", "LC": "信用证",
    "DGD": "危包证", "INSP": "检验证书",
}


# ---------------------------------------------------------------- 问题清单
def build_issues(docs, matrix, checks) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    n = 0

    def add(**kw):
        nonlocal n
        n += 1
        kw.setdefault("id", "I%02d" % n)
        issues.append(kw)

    for row in matrix:
        for did, cell in row["cells"].items():
            if cell["status"] == "DIFF":
                n_ok = sum(1 for c in row["cells"].values() if c["status"] == "OK")
                sev = "S1" if row["kind"] == "fact" and row["field"] in CRITICAL else "S2"
                add(field=row["field"], field_cn=row["cn"], doc=did, status="DIFF",
                    severity=sev, value=cell["value"], page=cell.get("page"),
                    bbox=cell.get("bbox"), note=cell.get("note", ""),
                    advice=advice_for(row["field"], cell["value"], row, did),
                    peers={d: c["value"] for d, c in row["cells"].items() if c["status"] == "OK"})
            elif cell["status"] == "MISS" and row["kind"] == "fact" and row["field"] in CRITICAL:
                add(field=row["field"], field_cn=row["cn"], doc=did, status="MISS",
                    severity="S3", value="", page=None, bbox=None,
                    note="本单证应当载明该字段但未识别到",
                    advice="确认该单证是否遗漏此项；若单据确有但为图片/扫描件，请人工核对后手工录入。",
                    peers={d: c["value"] for d, c in row["cells"].items() if c["status"] == "OK"})
    for c in checks:
        if not c["ok"]:
            docs_u = list(dict.fromkeys(c.get("docs") or []))
            add(field=c["id"], field_cn=c["name"],
                doc=(docs_u[0] if len(docs_u) == 1 else "、".join(
                    DOC_NAME.get(d, d) for d in docs_u)),
                status="CALC", severity="S1", value=fmt_money(c["actual"]), page=None, bbox=None,
                note=c["detail"],
                advice="按关系式逐项复核并统一修改（%s）；金额/重量类错误会直接影响报关与结汇。" % (
                    "%s 应为 %s" % (c["name"], fmt_money(c["expect"]))),
                peers={})
    return issues


CRITICAL = {
    "product_name_en", "product_name_cn", "cas_no", "hs_code", "quantity", "unit_price",
    "amount", "currency", "net_weight", "gross_weight", "package_count", "incoterm",
    "pol", "pod", "contract_no", "ci_no", "bl_no", "consignee_name", "seller_name",
    "batch_no", "co_no", "pi_no",
}


def advice_for(fid, value, row, did):
    peers = {d: c["value"] for d, c in row["cells"].items() if c["status"] == "OK"}
    ref = next(iter(peers.values()), "")
    if peers:
        base = "与 %s 的取值不一致（该单证为 %s），请以合同/信用证为准统一修改 %s。" % (
            "、".join(DOC_NAME.get(d, d) for d in list(peers)[:3]),
            ref if len(str(ref)) <= 60 else str(ref)[:58] + "...",
            DOC_NAME.get(did, did))
    else:
        base = "该字段仅在本单证出现且形态异常（%s），请按合同/单证编号规则核正 %s。" % (
            (str(value)[:48] + "...") if len(str(value)) > 48 else value,
            DOC_NAME.get(did, did))
    if fid in ("amount", "unit_price", "quantity"):
        base += " 价格与数量类字段需与合同/信用证一致，否则影响结汇与通关。"
    elif fid in ("net_weight", "gross_weight", "package_count"):
        base += " 重量与件数类差异会被海关/船公司视为申报不实。"
    elif fid in ("consignee_name", "notify_name"):
        base += " 收货人/通知方须与提单指示一致，否则目的港无法提货。"
    elif fid in ("pol", "pod"):
        base += " 港口错误会导致提单与舱单不符。"
    elif fid in ("cas_no", "hs_code"):
        base += " 化学品 CAS/HS 编码不一致会影响归类、监管证件与目的港清关。"
    elif fid == "incoterm":
        base += " 贸易术语决定运费保险由谁承担，须与报关单「成交方式」一致。"
    elif fid in ("pi_no", "ci_no", "contract_no", "bl_no", "co_no", "lc_no"):
        base += " 单证编号须与其它单证引用的编号完全一致，否则会被视为单证不符。"
    return base


# ---------------------------------------------------------------- 汇总
def summarize(matrix, issues, checks) -> Dict[str, Any]:
    stat = {"total_cells": 0, "OK": 0, "DIFF": 0, "MISS": 0, "NA": 0, "UNK": 0, "CALC": 0}
    for row in matrix:
        for c in row["cells"].values():
            stat["total_cells"] += 1
            stat[c["status"]] = stat.get(c["status"], 0) + 1
    stat["CALC"] = sum(1 for c in checks if not c["ok"])
    sev = {"S1": 0, "S2": 0, "S3": 0}
    for i in issues:
        sev[i.get("severity", "S3")] = sev.get(i.get("severity", "S3"), 0) + 1
    return {"cells": stat, "issues": len(issues), "severity": sev,
            "calculations": {"total": len(checks), "failed": stat["CALC"]},
            "verdict": "存在必须修改后才能交单的问题" if sev.get("S1") else
                       ("存在需人工确认的疑点" if issues else "未发现明显问题")}
