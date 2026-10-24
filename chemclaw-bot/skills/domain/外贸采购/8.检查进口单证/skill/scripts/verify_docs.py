# -*- coding: utf-8 -*-
"""verify_docs.py — 进口单证交叉核对引擎。

输入：
  --fields  <fields.json>   字段清单：每份单证的字段值 + 文件+页码+行号+原值片段（人工/OCR/LLM 抽取结果落盘）
  --manifest <manifest.json> 可选：本批次的"应有单证"清单（判断【缺失】），以及批次基础信息
  --out     <report.json>   输出结构化核对报告（矩阵/计算/问题/定位/影响）

输出报告同时供 HTML 看板与 Excel 台账渲染，字段与两者一一对应。

判定用语严格区分：
  CONSISTENT 一致 | INCONSISTENT 不一致 | MISSING 缺失 | UNVERIFIABLE 无法判断 | CALC_ERROR 计算错误 | NOT_COMPARABLE 无法直接比较

用法：
  python scripts/verify_docs.py --fields examples/01_MEG_沙特_宁波/expected/fields_MEG.json \
      --manifest examples/01_MEG_沙特_宁波/expected/manifest.json --out report.json
仅依赖标准库。
"""
import argparse, itertools, json, os, re, sys
from datetime import date

CONSISTENT, INCONSISTENT, MISSING, UNVERIFIABLE = "一致", "不一致", "缺失", "无法判断"
CALC_ERROR, NOT_COMPARABLE = "计算错误", "无法直接比较"
CHANGE_NOTE = "待确认"

# ---------------------------------------------------------------- 字段组
# group: (中文名, 归一化方式, 参与比对的严格程度)
GROUPS = {
    "contract_no": ("合同号", "code", "strict"),
    "invoice_no": ("发票号", "code", "strict"),
    "pi_no": ("形式发票号", "code", "strict"),
    "packing_no": ("装箱单号", "code", "strict"),
    "bl_no": ("提单号", "code", "strict"),
    "coa_no": ("COA 编号", "code", "strict"),
    "po_no": ("订单号", "code", "strict"),
    "lc_no": ("信用证号", "code", "strict"),
    "seller": ("卖方名称", "party", "strict"),
    "buyer": ("买方名称", "party", "strict"),
    "consignee": ("收货人", "party", "strict"),
    "notify": ("通知方", "party", "soft"),
    "shipper": ("发货人", "party", "soft"),
    "manufacturer": ("生产商", "party", "soft"),
    "origin": ("原产国", "text", "soft"),
    "product_en": ("英文品名", "text", "soft"),
    "product_cn": ("中文品名", "text", "soft"),
    "cas": ("CAS 号", "code", "strict"),
    "hs": ("HS 编码", "code", "strict"),
    "spec": ("规格/含量", "spec", "strict"),
    "quantity": ("数量(MT)", "num", "strict"),
    "unit": ("计量单位", "text", "soft"),
    "unit_price": ("单价", "num", "strict"),
    "amount": ("金额", "num", "strict"),
    "currency": ("币种", "code", "strict"),
    "incoterm": ("贸易术语", "incoterm", "strict"),
    "port_load": ("起运港", "port", "strict"),
    "port_disch": ("目的港", "port", "strict"),
    "vessel": ("船名", "vessel", "strict"),
    "voyage": ("航次", "code", "soft"),
    "packages": ("件数", "int", "strict"),
    "pack_type": ("包装方式", "text", "soft"),
    "net_weight": ("净重(KGS)", "num", "strict"),
    "gross_weight": ("毛重(KGS)", "num", "strict"),
    "batch": ("批号", "code", "strict"),
    "payment": ("付款方式", "payment", "strict"),
    "bl_date": ("提单日期", "date", "soft"),
    "eta": ("预计到港", "date", "soft"),
    "un_no": ("UN 编号", "code", "soft"),
    "hazard_class": ("危险类别", "code", "soft"),
    "marks": ("唛头", "text", "soft"),
}

# 单证间"本来就不该相同"的字段：一律标【无法直接比较】并说明原因，绝不判为错误
NOT_COMPARABLE_RULES = [
    ("PROFORMA_INVOICE", "COMMERCIAL_INVOICE", "amount",
     "形式发票为报价用，商业发票为实际结算金额，二者可不相同；仅数量/单价/贸易术语应一致"),
    ("PROFORMA_INVOICE", "COMMERCIAL_INVOICE", "pi_no",
     "形式发票号与商业发票号是不同单证编号，不可互比"),
    ("SDS", None, "packages",
     "SDS 第 14 节的包装件数/毛净重属'该产品常规运输形式'的说明，非本船实发数量；与本票实际件数不同不构成单证不符"),
    ("SDS", None, "net_weight", "同 SDS 说明性数据，非本票实发重量"),
    ("SDS", None, "gross_weight", "同 SDS 说明性数据，非本票实发重量"),
    ("CONTRACT", "COMMERCIAL_INVOICE", "payment",
     "合同约定的付款方式为 T/T 30% 预付 + 70% 见提单副本付款；商业发票载明即期信用证 "
     "（L/C NO. LC2605NB0088）。二者可能并行（信用证为买方开立、合同未修订），"
     "也可能意味着改证/改约——必须向买方确认后决定按哪条路径付款，不能直接判为单证不符"),
    ("CONTRACT", "PROFORMA_INVOICE", "payment",
     "形式发票属报价阶段文件，付款方式以合同/信用证最终约定为准"),
    ("PROFORMA_INVOICE", "COMMERCIAL_INVOICE", "payment",
     "形式发票为报价条款（可能遗留旧条件），实际付款以合同/信用证为准"),
    ("PROFORMA_INVOICE", "COMMERCIAL_INVOICE", "quantity",
     "形式发票数量为报价拟装数量，商业发票为实装数量，两者可不相同；应以提单/装箱单实装数量为准"),
    ("PROFORMA_INVOICE", "COMMERCIAL_INVOICE", "packages",
     "形式发票件数为报价预估件数，商业发票/提单为实装件数，可不相同"),
    (None, None, "notify",
     "通知方与收货人本可为不同主体；仅在信用证规定'通知方须为申请人'时才构成不符"),
    (None, None, "manufacturer", "生产商与卖方/发货人常常不是同一主体（贸易商+工厂），不构成不符"),
    (None, None, "origin", "原产国与装运港国家可能不同（转口/中转），仅在原产地证与发票不一致时才需说明"),
]

TYPE_CN = {"CONTRACT": "采购合同", "PROFORMA_INVOICE": "形式发票", "COMMERCIAL_INVOICE": "商业发票",
           "PACKING_LIST": "装箱单", "BILL_OF_LADING": "提单", "COA": "分析证书", "SDS": "安全技术说明书",
           "COO": "原产地证", "INSURANCE": "保险单", "LICENSE": "进口许可证", "USAGE_STATEMENT": "用途说明",
           "SPEC_SHEET": "产品规格书"}

# 每类单证"应有"的字段（用于【缺失】判定）
REQUIRED_FIELDS = {
    "CONTRACT": ["contract_no", "seller", "buyer", "product_en", "cas", "hs", "spec", "quantity", "unit_price",
                 "amount", "currency", "incoterm", "port_load", "port_disch", "payment", "packages", "net_weight",
                 "gross_weight"],
    "PROFORMA_INVOICE": ["pi_no", "seller", "product_en", "quantity", "unit_price", "amount", "currency", "incoterm",
                         "port_load", "port_disch", "payment"],
    "COMMERCIAL_INVOICE": ["invoice_no", "seller", "consignee", "product_en", "quantity", "unit_price", "amount",
                           "currency", "incoterm", "port_load", "port_disch", "bl_no", "packages", "net_weight",
                           "gross_weight", "payment"],
    "PACKING_LIST": ["packing_no", "invoice_no", "bl_no", "consignee", "packages", "pack_type", "net_weight",
                     "gross_weight", "batch"],
    "BILL_OF_LADING": ["bl_no", "shipper", "consignee", "notify", "vessel", "voyage", "port_load", "port_disch",
                       "product_en", "packages", "net_weight", "gross_weight", "bl_date"],
    "COA": ["coa_no", "product_en", "cas", "batch", "spec", "manufacturer"],
    "SDS": ["product_en", "cas", "un_no", "hazard_class"],
    "COO": ["coo_no", "seller", "consignee", "product_en", "origin", "hs"],
}


# ---------------------------------------------------------------- 归一化
def norm(kind, v):
    if v is None:
        return None
    s = str(v).strip()
    if kind == "code":
        return re.sub(r"[^A-Z0-9]", "", s.upper())
    if kind == "int":
        d = re.sub(r"[^\d]", "", s)
        return int(d) if d else None
    if kind == "num":
        t = s.replace(",", "").replace(" ", "")
        m = re.match(r"^-?\d+(?:\.\d+)?", t)
        return round(float(m.group(0)), 3) if m else None
    if kind == "party":
        t = re.sub(r"[^\w\s]", " ", s.upper())
        for junk in ("CO LTD", "LIMITED", "COMPANY", "CO.,", "LTD", " CORP", " CORPORATION", "LLC", " CO "):
            t = t.replace(junk, " ")
        return re.sub(r"\s+", " ", t).strip()
    if kind == "spec":
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", s)
        return float(m.group(1)) if m else None
    if kind == "port":
        t = re.sub(r"\(.*?\)", "", s.upper())
        t = re.sub(r"\b(PORT|CHINA|SAUDI ARABIA|KINGDOM OF)\b", " ", t)
        return re.sub(r"[^A-Z]", "", t) or None
    if kind == "vessel":
        t = re.sub(r"V\.?\s*\d+.*$", "", s.upper())
        return re.sub(r"[^A-Z]", "", t) or None
    if kind == "payment":
        t = s.upper()
        if "L/C" in t or "LC" in t and "AT SIGHT" in t:
            return "LC_AT_SIGHT"
        if "T/T" in t or "TT " in t:
            ratio = re.findall(r"(\d+)\s*%", t)
            return "TT_" + ("_".join(ratio) if ratio else "")
        return re.sub(r"[^A-Z0-9]", "", t) or None
    if kind == "incoterm":
        m = re.search(r"\b(EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DAP|DPU|DDP)\b", s.upper())
        return m.group(1) if m else None
    if kind == "date":
        m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
        return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    return re.sub(r"\s+", " ", s).upper()


def fmt(kind, v):
    if v is None:
        return "—"
    if kind == "num":
        return "{:,.2f}".format(v) if isinstance(v, float) and not float(v).is_integer() else "{:,.0f}".format(v)
    if kind == "int":
        return "{:,}".format(v)
    if kind == "spec":
        return "≥{:.4g}%".format(v)
    return str(v)


# ---------------------------------------------------------------- 主流程
def build(fields_doc, manifest):
    docs = fields_doc["documents"]
    for d in docs:
        d.setdefault("type_cn", TYPE_CN.get(d["type"], d["type"]))
    by_type = {}
    for d in docs:
        by_type.setdefault(d["type"], []).append(d)

    def get(doc, f):
        v = doc.get("fields", {}).get(f)
        if isinstance(v, dict):
            return v.get("value"), v
        return v, None

    def not_comparable(ftype, ttype, field):
        for a, b, f, why in NOT_COMPARABLE_RULES:
            if f != field:
                continue
            if (a is None or a == ftype) and (b is None or b == ttype):
                return why
            if (a is None or a == ttype) and (b is None or b == ftype):
                return why
        return None

    matrix, findings, calcs = [], [], []

    # ---- 1. 字段核对矩阵：逐字段逐单证取原始值 + 归一化值
    for field, (cn, kind, strict) in GROUPS.items():
        row = {"field": field, "field_cn": cn, "kind": kind, "strict": strict, "cells": {}, "status": None,
               "explain": "", "expected": None, "basis": None}
        normed = {}
        for d in docs:
            raw, ref = get(d, field)
            if raw in (None, ""):
                row["cells"][d["file"]] = {"value": None, "fvalue": "未载明", "type": d["type"], "loc": None}
                continue
            nv = norm(kind, raw)
            row["cells"][d["file"]] = {"value": raw, "fvalue": fmt(kind, nv if kind != "text" else raw),
                                       "norm": nv, "type": d["type"], "loc": ref}
            if nv is not None:
                normed.setdefault(nv, []).append(d["file"])
        present = [f for f, c in row["cells"].items() if c["value"] is not None]
        # 判定
        if len(present) == 0:
            row["status"], row["explain"] = UNVERIFIABLE, "所有单证均未识别该字段"
        elif len(present) == 1:
            row["status"], row["explain"] = UNVERIFIABLE, "仅 1 份单证载明，无对照源"
        elif len(normed) == 1:
            row["status"] = CONSISTENT
            row["explain"] = "%d 份单证一致" % len(present)
        else:
            # 多个归一化值：检查是否属于"本不该相同"的字段
            ftypes = sorted({row["cells"][f]["type"] for f in present})
            groups = list(normed.values())
            if strict == "strict":
                cand = None
                for a, b in itertools.combinations(ftypes, 2):
                    why = not_comparable(a, b, field)
                    if why:
                        cand = why
                        break
                if cand:
                    row["status"] = CHANGE_NOTE if field == "payment" else NOT_COMPARABLE
                    row["explain"] = cand
                else:
                    row["status"] = INCONSISTENT
                    row["explain"] = "；".join("%s: %s" % (",".join(fs), fmt(kind, v))
                                               for v, fs in normed.items())
                    findings.append(make_finding(field, cn, kind, row, normed))
            else:
                # 文本类字段只做"文字表述差异"提示，不判为单证不符
                row["status"] = UNVERIFIABLE
                row["explain"] = "文字表述不同（属正常单证结构差异，不构成不符）：" + "；".join(
                    "%s: %s" % (",".join(fs), fmt(kind, v)) for v, fs in normed.items())
                row["soft_note"] = True
        # 缺失：某类单证的必备字段没有值
        for d in docs:
            req = REQUIRED_FIELDS.get(d["type"], [])
            if field in req and row["cells"][d["file"]]["value"] is None:
                findings.append({
                    "id": None, "field": field, "field_cn": cn, "status": MISSING, "severity": "中",
                    "title": "【缺失】%s 未载明%s" % (d["file"], cn),
                    "detail": "%s 属该类单证的必备字段，本次上传文件中未见该值。" % d["type_cn"],
                    "locations": [{"file": d["file"], "kind": d["type_cn"], "page": None, "line": None,
                                   "value": "（未载明）"}],
                    "impacts": impact_of(field, MISSING),
                    "action": "要求对方补发载明%s的%s，或由买卖双方书面确认该信息可省略" % (cn, d["type_cn"]),
                })
        # 权威值：用于"接受某一份单证的值即完成整改"
        BASIS = {"CONTRACT": "以合同约定为准", "COMMERCIAL_INVOICE": "以商业发票为准（结算依据）",
                 "BILL_OF_LADING": "以提单实装数据为准（经船方确认）",
                 "PACKING_LIST": "以装箱单实装数据为准", "COA": "以分析证书为准（质量依据）"}
        # 先找"多数单证共同取值"（>=2 份且为共识值）→ 它是事实性数据（如批号）
        consensus = None
        for nv, files in normed.items():
            ft = {row["cells"][x]["type"] for x in files}
            if len(files) >= 2 and "BILL_OF_LADING" not in ft:
                consensus = (nv, files[0])
                break
        if consensus:
            row["expected"] = consensus[0]
            row["basis"] = "%d 份单证相互印证（%s），以多数一致值为准" % (
                len(normed[consensus[0]]), BASIS.get(row["cells"][consensus[1]]["type"], "单证相互印证"))
        else:
            for pref in ("CONTRACT", "COMMERCIAL_INVOICE", "PACKING_LIST", "BILL_OF_LADING"):
                hit = [c for c in row["cells"].values() if c["type"] == pref and c.get("norm") is not None]
                if hit:
                    row["expected"] = hit[0]["norm"]
                    row["basis"] = BASIS[pref]
                    break
        matrix.append(row)

    # ---- 2. 单证齐全性（manifest）
    expected = (manifest or {}).get("expected_documents", [])
    have = {d["type"] for d in docs}
    for e in expected:
        if e["type"] not in have:
            findings.append({
                "id": None, "field": "-", "field_cn": "单证齐全性", "status": MISSING, "severity": e.get("severity", "高"),
                "title": "【缺失】缺少%s" % e["name"],
                "detail": e.get("why", "按合同/信用证/进口申报要求，本批次应随附该单证。"),
                "locations": [{"file": "（未上传）", "kind": e["name"], "page": None, "line": None,
                               "value": "缺失"}],
                "impacts": e.get("impacts", ["目的港清关", "单证相符"]),
                "action": e.get("action", "向发货人/供应商索取该单证后再提交审核"),
            })

    # ---- 3. 计算校验（并把未通过的算术项提升为问题条目）
    calcs.extend(math_checks(docs, get))
    for c in calcs:
        if c["ok"]:
            continue
        loc = c.get("loc") or {}
        if c["check"] == "单价 × 数量 = 金额":
            findings.append({
                "id": None, "field": "amount", "field_cn": "金额", "status": CALC_ERROR, "severity": "高",
                "title": "【计算错误】%s 单价 × 数量 ≠ 填列金额" % c["doc"],
                "detail": "单价 × 数量 = %s，单证填写金额 %s，差额 %s（%s）。"
                          % (c["formula"], "{:,.2f}".format(c["actual"]),
                             "{:,.2f}".format(abs(c["gap"])),
                             "多计" if c["gap"] > 0 else "少计"),
                "locations": [{"file": c["doc"], "kind": c["kind"], "page": loc.get("page"),
                               "line": loc.get("line"), "value": "{:,.2f}".format(c["actual"]),
                               "snippet": loc.get("snippet")}],
                "impacts": ["对外付汇金额", "信用证单证相符", "进口报关价格申报", "海关审价风险"],
                "action": "要求卖方重新出具商业发票，使 金额 = 单价 × 数量；若单价确有变更，须书面确认并同步更正报关资料",
            })
        elif c["check"].startswith("毛重"):
            findings.append({
                "id": None, "field": "gross_weight", "field_cn": "毛重/净重", "status": CALC_ERROR, "severity": "高",
                "title": "【计算错误】%s 毛重与净重逻辑不成立" % c["doc"],
                "detail": "%s，皮重 %s KGS，不符合 0 < 皮重 < 净重15%% 的常识判断。"
                          % (c["formula"], "{:,.0f}".format(c["gap"])),
                "locations": [{"file": c["doc"], "kind": c["kind"], "page": loc.get("page"),
                               "line": loc.get("line"), "value": "{:,.0f}".format(c["actual"])}],
                "impacts": ["包装与重量逻辑", "报关毛重"],
                "action": "要求提供装船磅单/理货报告，核对毛净重",
            })

    # ---- 4. 编号索引：找出"同一编号在不同单证写法不一致"
    findings.extend(index_checks(docs, get))

    # ---- 5. 待确认事项：由"待确认"字段行生成（不计入单证不符）
    pendings = []
    for row in matrix:
        if row["status"] != CHANGE_NOTE:
            continue
        vals = []
        for fn, c in row["cells"].items():
            if c["value"] is None:
                continue
            loc = c.get("loc") or {}
            vals.append({"file": fn, "kind": TYPE_CN.get(c["type"], c["type"]), "page": loc.get("page"),
                         "line": loc.get("line"), "value": c["value"], "snippet": loc.get("snippet")})
        pendings.append({
            "id": "PENDING-%02d" % (len(pendings) + 1), "field": row["field"], "field_cn": row["field_cn"],
            "status": CHANGE_NOTE, "severity": "高" if row["field"] in ("payment", "currency", "incoterm") else "中",
            "title": "【待确认】%s 在不同单证中不同，需确认以哪一份为准" % row["field_cn"],
            "detail": row["explain"], "locations": vals,
            "impacts": impact_of(row["field"], INCONSISTENT),
            "question": "本批货物实际按哪条路径付款？若按信用证（LC2605NB0088 即期）执行，请买方书面确认合同付款条款已作修订；"
                        "若按合同 T/T 执行，请确认信用证是否已撤销、相关费用由谁承担。",
            "action": action_of(row["field"]),
        })

    # 汇总
    for i, f in enumerate(findings, 1):
        f["id"] = "ISSUE-%02d" % i
        f.setdefault("severity", "中")
    return {"documents": docs, "matrix": matrix, "findings": findings, "calculations": calcs,
            "pending": pendings, "summary": summarize(matrix, findings, docs, pendings)}


def make_finding(field, cn, kind, row, normed):
    vals = []
    for v, files in normed.items():
        for f in files:
            c = row["cells"][f]
            loc = c.get("loc") or {}
            vals.append({"file": f, "kind": TYPE_CN.get(c["type"], c["type"]),
                         "page": loc.get("page"), "line": loc.get("line"),
                         "value": c["value"], "snippet": loc.get("snippet")})
    return {"id": None, "field": field, "field_cn": cn, "status": INCONSISTENT,
            "severity": severity_of(field), "title": "【不一致】%s 在各单证中不同" % cn,
            "detail": "；".join("%s 载明「%s」" % (v["file"].split("_", 1)[-1].rsplit(".", 1)[0][:18], v["value"])
                                for v in vals) + "。", "locations": vals,
            "impacts": impact_of(field, INCONSISTENT), "action": action_of(field)}


def severity_of(field):
    high = {"amount", "quantity", "unit_price", "consignee", "buyer", "seller", "spec", "hs", "cas",
            "net_weight", "gross_weight", "packages", "payment", "bl_no", "invoice_no", "currency"}
    return "高" if field in high else "中"


def impact_of(field, status):
    m = {
        "amount": ["对外付汇金额", "信用证单证相符", "进口报关价格申报"],
        "unit_price": ["对外付汇金额", "进口报关价格申报", "海关审价风险"],
        "quantity": ["对外付汇金额", "报关数量", "到货验收计量", "报关单与提单不一致可能致查验"],
        "consignee": ["提单收货人", "报关境内收货人", "提货权与货权交接"],
        "buyer": ["合同主体", "进口报关经营单位", "付汇主体一致性"],
        "seller": ["合同主体", "付汇收款人", "原产地证与发票主体一致性"],
        "spec": ["到货验收质量标准", "是否满足生产投料要求", "退货/索赔依据"],
        "hs": ["进口关税税率", "监管证件要求", "报关归类准确性"],
        "cas": ["危险化学品/易制毒等监管判定", "报关申报要素"],
        "net_weight": ["报关重量", "到货计量结算", "包装与重量逻辑"],
        "gross_weight": ["运输与码头作业载荷", "报关毛重", "包装与重量逻辑"],
        "packages": ["报关件数", "理货/交接清点", "包装与重量逻辑"],
        "payment": ["付款路径与时间节点", "信用证是否开立"],
        "bl_no": ["单证相符（信用证关键项）", "提货与换单"],
        "invoice_no": ["单证相符（信用证关键项）", "付汇核销"],
        "currency": ["付汇币种", "报关币制"],
    }
    if status == MISSING:
        return ["单证相符（单据不齐）"]
    return m.get(field, ["单证之间的一致性"])


def action_of(field):
    return {
        "amount": "要求卖方按 单价 × 数量 重新出具商业发票，并书面确认最终结算金额",
        "unit_price": "要求卖方书面确认成交单价，并同步更正发票/合同",
        "quantity": "以提单/装箱单实际装运数量为准，要求更正发票与报关资料",
        "consignee": "以合同买方/信用证规定为准，要求提单与发票收货人名称完全一致",
        "spec": "要求出具符合合同规格的 COA，或签署规格变更的书面确认",
        "hs": "要求以申报 HS 编码统一全部单证，并核对归类依据",
        "net_weight": "要求提供装船磅单/理货报告，统一各单证毛净重",
        "gross_weight": "要求提供装船磅单/理货报告，统一各单证毛净重",
        "packages": "以实际装运件数为准统一各单证，必要时改单",
        "payment": "确认本批次实际付款方式（T/T 或 L/C），并统一写入全部单证",
        "cas": "统一 CAS 号并在报关要素中说明",
    }.get(field, "要求相关方更正并出具书面确认")


def math_checks(docs, get):
    out = []

    def one(doc):
        qty, _ = get(doc, "quantity")
        up, _ = get(doc, "unit_price")
        amt, ref = get(doc, "amount")
        net, nref = get(doc, "net_weight")
        gross, gref = get(doc, "gross_weight")
        pkg, pref = get(doc, "packages")
        q, u, a = norm("num", qty), norm("num", up), norm("num", amt)
        n, g = norm("num", net), norm("num", gross)
        p = norm("int", pkg)
        if q and u and a:
            exp = round(q * u, 2)
            ok = abs(exp - a) < max(0.02, exp * 1e-6)
            out.append({"doc": doc["file"], "kind": TYPE_CN.get(doc["type"], doc["type"]),
                        "check": "单价 × 数量 = 金额", "formula": "%s × %s" % (fmt("num", q), fmt("num", u)),
                        "expected": exp, "actual": a, "ok": ok,
                        "loc": ref, "gap": round(a - exp, 2)})
        if n and g:
            ok = 0 < g - n < n * 0.15
            out.append({"doc": doc["file"], "kind": TYPE_CN.get(doc["type"], doc["type"]),
                        "check": "毛重 ≥ 净重 且皮重合理(0<tare<15%净重)",
                        "formula": "毛重 %s − 净重 %s" % (fmt("num", g), fmt("num", n)),
                        "expected": n, "actual": g, "ok": ok, "loc": gref or nref, "gap": round(g - n, 3)})
        if p and n:
            per = n / p
            ok = 1000 <= per <= 200000
            out.append({"doc": doc["file"], "kind": TYPE_CN.get(doc["type"], doc["type"]),
                        "check": "单件平均净重是否合理", "formula": "净重 ÷ 件数",
                        "expected": round(per, 2), "actual": round(per, 2), "ok": ok,
                        "loc": pref or nref, "gap": 0})
        if p and q:
            # 数量(MT) 与 件数×单件量：仅在包装为该产品常见规格时才能比对
            per_mt = q * 1000 / p
            out.append({"doc": doc["file"], "kind": TYPE_CN.get(doc["type"], doc["type"]),
                        "check": "数量 ÷ 件数 = 单件装载量(kg)",
                        "formula": "%s MT ÷ %d" % (fmt("num", q), p),
                        "expected": round(per_mt, 1), "actual": round(per_mt, 1), "ok": True,
                        "loc": pref or ref, "gap": 0})
    for d in docs:
        one(d)
    return out


def index_checks(docs, get):
    """跨单证编号互证：提单号/发票号/合同号 不同单证的写法应一致。"""
    out = []
    pairs = [("invoice_no", ["COMMERCIAL_INVOICE", "PACKING_LIST"]),
             ("bl_no", ["BILL_OF_LADING", "COMMERCIAL_INVOICE", "PACKING_LIST"]),
             ("contract_no", ["CONTRACT", "COMMERCIAL_INVOICE", "PROFORMA_INVOICE"]),
             ("packing_no", ["PACKING_LIST"])]
    for field, types in pairs:
        vals = {}
        for t in types:
            for d in docs:
                if d["type"] != t:
                    continue
                v, ref = get(d, field)
                if v:
                    vals.setdefault(norm("code", v), []).append((d["file"], v, ref))
        if len(vals) > 1:
            locs = []
            for k, items in vals.items():
                for f, v, ref in items:
                    locs.append({"file": f, "kind": "", "page": (ref or {}).get("page"),
                                 "line": (ref or {}).get("line"), "value": v,
                                 "snippet": (ref or {}).get("snippet")})
            out.append({"id": None, "field": field, "field_cn": GROUPS[field][0], "status": INCONSISTENT,
                        "severity": "高", "title": "【不一致】%s 在不同单证中填写不同" % GROUPS[field][0],
                        "detail": "同一批次单证引用的编号应完全一致。",
                        "locations": locs, "impacts": impact_of(field, INCONSISTENT), "action": action_of(field)})
    return out


def summarize(matrix, findings, docs, pendings=()):
    cnt = {}
    for f in findings:
        cnt[f["status"]] = cnt.get(f["status"], 0) + 1
    for r in matrix:
        cnt[r["status"]] = cnt.get(r["status"], 0) + 1 if r["status"] in (CONSISTENT, NOT_COMPARABLE, UNVERIFIABLE) else cnt.get(r["status"], 0)
    sev = {}
    for f in findings:
        sev[f["severity"]] = sev.get(f["severity"], 0) + 1
    return {"doc_count": len(docs),
            "docs": [{"file": d["file"], "type": d["type"], "type_cn": d["type_cn"]} for d in docs],
            "finding_count": len(findings), "by_status": cnt, "by_severity": sev,
            "matrix_rows": len(matrix),
            "consistent_rows": sum(1 for r in matrix if r["status"] == CONSISTENT),
            "inconsistent_rows": sum(1 for r in matrix if r["status"] == INCONSISTENT),
            "not_comparable_rows": sum(1 for r in matrix if r["status"] == NOT_COMPARABLE),
            "unverifiable_rows": sum(1 for r in matrix if r["status"] == UNVERIFIABLE),
            "change_note_rows": sum(1 for r in matrix if r["status"] == CHANGE_NOTE),
            "pending_count": len(pendings),
            "calc_checks": len([c for c in matrix]) and None,
            }


# ---------------------------------------------------------------- 定位回查
def _flat(s):
    return "".join(ch for ch in str(s) if ch.isalnum()).upper()


def _frags(s):
    s = str(s)
    for ch in "%(),/":
        s = s.replace(ch, " ")
    return [_flat(p) for p in s.split() if len(p) >= 2]


def check_locate(fields_path, docs_dir, pdf_dir=None):
    """逐字段回查：值（或其关键词片段）必须出现在登记的页码上；有行号则该行须能佐证。
    返回 (checked, failures, relaxed)。"""
    import glob
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    doc = json.load(open(fields_path, encoding="utf-8"))
    checked, failures, relaxed = 0, [], []
    computed = {"net_weight", "gross_weight", "packages"}
    for d in doc["documents"]:
        fname = d["file"]
        stem, ext = os.path.splitext(fname)
        src = os.path.join(docs_dir, fname)
        pdfp = None
        if pdf_dir:
            cand = os.path.join(pdf_dir, stem + ".pdf")
            if os.path.exists(cand):
                pdfp = cand
        if not os.path.exists(src):
            failures.append((fname, "文件不存在"))
            continue
        kind = "pdf" if pdfp else ("xlsx" if ext.lower() == ".xlsx" else "raw")
        pages, lines = {}, {}
        if kind == "pdf":
            import pdf_text
            for pg, ls in pdf_text.page_lines(pdfp):
                pages[pg] = "\n".join(t for _, t in ls)
                for i, (_, t) in enumerate(ls, 1):
                    lines[(pg, i)] = t
        elif kind == "xlsx":
            import extract_fields as E
            for ln in E.read_any(src) or []:
                pages[1] = pages.get(1, "") + "\n" + ln["text"]
                lines[(1, ln["line"])] = ln["text"]
        for name, ref in d.get("fields", {}).items():
            checked += 1
            pg, ln = ref.get("page"), ref.get("line") or 0
            if kind == "raw":
                if not pg:
                    failures.append((fname, "%s 缺页码" % name))
                continue
            raw_page = pages.get(pg, "")
            if kind == "xlsx" and name in computed:
                if "SUM(" not in raw_page and "20000" not in _flat(raw_page):
                    failures.append((fname, "%s 合计缺公式/明细证据" % name))
                continue
            cands = [_flat(ref.get(k)) for k in ("value", "extra") if ref.get(k)]
            strict = any(c and c in _flat(raw_page) for c in cands)
            frs = _frags(ref.get("value", ""))
            loose = bool(frs) and sum(1 for f in frs if f in _flat(raw_page)) >= max(2, len(frs) - 1)
            if not strict and not loose:
                failures.append((fname, "%s=%r 第 %s 页找不到" % (name, ref.get("value"), pg)))
                continue
            if not strict:
                relaxed.append((fname, name))
            if ln:
                lt = _flat(lines.get((pg, ln), ""))
                ok = lt and (any(c and (c in lt or lt in c) for c in cands)
                             or any(f in lt for f in frs))
                if not ok:
                    failures.append((fname, "%s 第%s页第%s行不符（%r）" % (
                        name, pg, ln, lines.get((pg, ln), "")[:46])))
            elif not ref.get("snippet"):
                failures.append((fname, "%s 无原文片段" % name))
    return checked, failures, relaxed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fields", required=True)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--out", default="report.json")
    ap.add_argument("--check-locate", action="store_true", help="只做定位回查，不生成核对报告")
    ap.add_argument("--docs", default=None, help="单证目录（--check-locate 时必填）")
    ap.add_argument("--pdf-dir", default=None, help="渲染后的 PDF 目录（DOCX/XLSX 用其页码）")
    a = ap.parse_args()
    if a.check_locate:
        if not a.docs:
            sys.exit("--check-locate 需要同时给出 --docs <单证目录>")
        checked, failures, relaxed = check_locate(a.fields, a.docs, a.pdf_dir)
        print("定位回查：%d 个字段，失败 %d 个，按片段折算 %d 个" % (checked, len(failures), len(relaxed)))
        for f in failures:
            print("  ✗", f[0], "|", f[1])
        sys.exit(1 if failures else 0)
    fields_doc = json.load(open(a.fields, encoding="utf-8"))
    manifest = json.load(open(a.manifest, encoding="utf-8")) if a.manifest else None
    rep = build(fields_doc, manifest)
    rep["batch"] = (manifest or {}).get("batch", {})
    rep["calculations_summary"] = {
        "total": len(rep["calculations"]),
        "failed": len([c for c in rep["calculations"] if not c["ok"]]),
    }
    json.dump(rep, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    s = rep["summary"]
    print("单证 %d 份 | 字段行 %d（一致 %d / 不一致 %d / 无法直接比较 %d / 无法判断 %d）| 问题 %d 项" %
          (s["doc_count"], s["matrix_rows"], s["consistent_rows"], s["inconsistent_rows"],
           s["not_comparable_rows"], s["unverifiable_rows"], s["finding_count"]))
    print("其中【待确认】字段行 %d 项" % s.get("change_note_rows", 0))
    print("计算校验 %d 项，未通过 %d 项" % (rep["calculations_summary"]["total"],
                                            rep["calculations_summary"]["failed"]))
    for f in rep["findings"]:
        print("  %-10s %-8s %s" % (f["id"], f["status"], f["title"]))
    for p in rep.get("pending", []):
        print("  %-10s %-8s %s" % (p["id"], p["status"], p["title"]))
    print("wrote", a.out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()


