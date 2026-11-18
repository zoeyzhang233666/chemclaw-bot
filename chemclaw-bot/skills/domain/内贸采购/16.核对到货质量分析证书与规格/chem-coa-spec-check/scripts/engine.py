# -*- coding: utf-8 -*-
"""engine.py —— 把 data.json 跑成"逐项比对结果 + 完整性 + 方法差异 + 趋势 + 异议要点"。

输入：符合 references/data-contract.md 的 data.json。
输出：一个内存 dict（由 render_html.py / render_xlsx.py 消费），
      同时可用 `python engine.py data.json --json out.json` 落盘供审计。

关键实现：**规格回退链**
    合同规格（如无）→ 采购规格书 → 适用标准（GB/T / ASTM 合同引用项）
    三者任一命中即用；都不命中 → 状态落"规格未约定"，不拿生产规格当验收线。
"""

import json
import os
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coa_lib as L  # noqa: E402

# 证书完整性必检字段（任何化工品 COA 都应具备）
REQ_HEADER = OrderedDict([
    ("product_name", "产品名称"),
    ("producer", "生产企业"),
    ("batch_no", "生产批号"),
    ("mfg_date", "生产日期"),
    ("test_date", "检测日期"),
    ("report_no", "证书/报告编号"),
    ("test_standard", "检测依据/标准"),
    ("conclusion", "检测结论/判定"),
    ("cert_code", "证书防伪码/编制审核签发"),
])
# 按指标类别补充的完整性要求
CATEGORY_REQ = {
    "含量": ["检测方法"],
    "水分": ["检测方法", "检出限"],
    "杂质": ["检测方法", "检出限（微量项）"],
    "物性": ["检测方法", "检测温度"],
    "外观": ["检测方法（目视条件）"],
}


# ---------------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------------

def _get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def index_items(items):
    """指标名 → item（按 name_key 建索引，同时保留原顺序）。"""
    idx = OrderedDict()
    for it in items:
        idx.setdefault(it["name_key"], it)
    return idx


def build_alias_index(registry):
    idx = {}
    for e in registry:
        for k in [e["canonical"]] + list(e.get("aliases", [])):
            idx[L._tok(k) if False else _norm_name(k)] = e
        idx[_norm_name(e["canonical"])] = e
    return idx


def _norm_name(s):
    t = str(s or "").strip()
    t = t.replace("（", "(").replace("）", ")").replace("：", ":")
    t = t.replace(" ", "").replace("　", "")
    return t


# ---------------------------------------------------------------------------------
# 1. 逐项比对
# ---------------------------------------------------------------------------------

def _pick_spec(it, specs, stds):
    """规格回退链：合同 → 采购规格 → 标准。返回 (source_dict|None, origin_label)。"""
    for sp in specs:
        if it["name_key"] in sp["items_idx"]:
            return sp["items_idx"][it["name_key"]], f"{sp.get('doc_type') or '采购规格书'} {sp.get('spec_no', '')}".strip()
    for st in stds:
        if it["name_key"] in st["items_idx"]:
            return st["items_idx"][it["name_key"]], f"适用标准 {st.get('code', '')}".strip()
    return None, ""


def compare(data):
    product = data["product"]
    aliases = build_alias_index(product.get("indicator_aliases", []))
    eq_methods = product.get("equivalent_methods", [])
    product_basis = product.get("basis", "as_received")

    specs = []
    for s in data.get("specs", []):
        s = dict(s)
        s["items_idx"] = index_items(s.get("items", []))
        specs.append(s)
    # 合同技术附件优先
    specs.sort(key=lambda s: 0 if s.get("doc_type", "").startswith("合同") else 1)
    stds = []
    for s in data.get("standards", []):
        s = dict(s)
        s["items_idx"] = index_items(s.get("items", []))
        stds.append(s)

    coas = data.get("coas", [])
    target = data.get("meta", {}).get("target_coa_batch") or (coas[0].get("batch_no") if coas else None)
    target_coa = next((c for c in coas if c.get("batch_no") == target), coas[0] if coas else None)

    results_by_coa = OrderedDict()
    for coa in coas:
        results_by_coa[coa.get("batch_no")] = _compare_one(coa, specs, stds, aliases, eq_methods,
                                                            product_basis, data, target_coa)
    completeness = {c.get("batch_no"): check_completeness(c, specs, stds, aliases, results_by_coa[c.get("batch_no")])
                    for c in coas}
    method_issues = {c.get("batch_no"): method_diff(coa=c, specs=specs, stds=stds, aliases=aliases,
                                                   eq_methods=eq_methods,
                                                   results=results_by_coa[c.get("batch_no")], data=data)
                     for c in coas}
    trends = {b: build_trends(results_by_coa[b], data) for b in results_by_coa}

    return {
        "meta": data.get("meta", {}),
        "product": product,
        "supplier": data.get("supplier", {}),
        "contract": data.get("contract", {}),
        "specs": [{k: v for k, v in s.items() if k != "items_idx"} for s in specs],
        "standards": [{k: v for k, v in s.items() if k != "items_idx"} for s in stds],
        "coas": coas,
        "batch_order": [c.get("batch_no") for c in coas],
        "target_batch": target,
        "results": results_by_coa,
        "completeness": completeness,
        "method_issues": method_issues,
        "trends": trends,
        "summary": {b: L.summarize([r["status"] for r in rs]) for b, rs in results_by_coa.items()},
        "alerts": data.get("alerts", []),
    }


def _compare_one(coa, specs, stds, aliases, eq_methods, product_basis, data, target_coa):
    """常规比对：以本合同/本次采购规格为基线，逐项核对本 COA。"""
    rows = []
    seen = set()
    coa_idx = {i["name_key"]: i for i in coa.get("items", [])}
    # 全指标域：规格 ∪ 标准 ∪ 本 COA ∪ 历史批次出现过
    domain = []
    for sp in specs:
        domain += [i["name_key"] for i in sp["items"]]
    for st in stds:
        domain += [i["name_key"] for i in st["items"]]
    domain += [i["name_key"] for i in coa.get("items", [])]
    for c in data.get("coas", []):
        domain += [i["name_key"] for i in c.get("items", [])]
    for k in domain:
        if k in seen:
            continue
        seen.add(k)
        rows.append(_row(k, coa, coa_idx, specs, stds, aliases, eq_methods, product_basis, data))
    return rows


def _row(k, coa, coa_idx, specs, stds, aliases, eq_methods, product_basis, data):
    ent = aliases.get(k, {})
    name = (coa_idx.get(k, {}) or {}).get("name") or ent.get("canonical") or k
    spec_src, origin = _pick_spec({"name_key": k}, specs, stds)
    coa_it = coa_idx.get(k)

    ref_display = coa_it.get("value") if coa_it else None
    ref_unit = (coa_it or {}).get("unit") or (spec_src or {}).get("unit", "")
    lim_display = (spec_src or {}).get("limit")
    spec_unit = (spec_src or {}).get("unit", "")
    meas_display = coa_it.get("value") if coa_it else "（COA 未列该指标）"

    ref = L.parse_value(ref_display, "ref")
    lim = L.parse_value(lim_display, "limit") if lim_display not in (None, "") else {"kind": "unspecified",
                                                                                   "display": "", "value": None,
                                                                                   "range": None, "text": ""}
    if spec_src is None:
        lim = {"kind": "unspecified", "display": "", "value": None, "range": None, "text": ""}

    item = {
        "name": name, "name_key": k,
        "ref_unit": ref_unit, "meas_unit": spec_unit or ref_unit,
        "method_coa": (coa_it or {}).get("method"),
        "method_spec": (spec_src or {}).get("method"),
        "basis_coa": (coa_it or {}).get("basis") or product_basis,
        "basis_spec": (spec_src or {}).get("basis") or "as_received",
        "method_ref_fallback": bool(ent),
        "_coa_absent": coa_it is None,
    }
    # 双方法多结果（电解法+红外法）：方法一致的那一个优先
    picked = None
    if coa_it and coa_it.get("replicate") and spec_src and spec_src.get("method"):
        for r in coa_it["replicate"]:
            if L.method_relation(r.get("method"), spec_src.get("method"), eq_methods) in ("same", "equivalent"):
                picked = r
                break
        if picked:
            ref = L.parse_value(picked.get("value"), "ref")
            meas_display = f"{picked.get('value')}（{picked.get('method')} 结果，与约定方法一致）"
            item["method_coa"] = picked.get("method")
    comp = L.comparability(item, aliases, eq_methods, product_basis)

    # 规格未约定时：用生产规格生成"建议值"（不改变判断状态）
    inferred = None
    if spec_src is None:
        cand = {"name_key": k, "meas_unit": ref_unit, "spec_unit": ref_unit,
                "other_sources": _other_sources(k, data, coa)}
        inferred = L.infer_spec(cand)

    nd_allowed = bool(lim.get("kind") in ("max", "single") and
                      re_is_lod_style(lim))
    if coa_it is None:
        status, reason, notes = L.ST_UNTESTED, "COA 未列该指标", []
    elif ref["kind"] == "unspecified" and lim["kind"] != "unspecified":
        status, reason, notes = L.ST_UNTESTED, "COA 该行数值为空或标注未检测", []
    else:
        status, reason, notes = L.determine_status(ref, ref_unit, spec_unit or ref_unit, comp,
                                                   nd_allowed=nd_allowed, lim=lim)
    if coa_it is None and lim["kind"] != "unspecified":
        status, reason = L.ST_UNTESTED, "COA 未列该指标（规格已约定）"
    if spec_src is None:
        status, reason = L.ST_UNSPEC, (f"采购规格书/合同未约定该指标限值；"
                                       f"生产规格建议 {inferred['limit_display']} {inferred['unit']}（仅供参考，"
                                       f"不作为验收依据）" if inferred else "采购规格书/合同未约定该指标限值")

    dev = L.deviation(status, ref, ref_unit or spec_unit, lim, spec_unit or ref_unit)
    basis = (ent or {}).get("basis", "customer")
    adj = None
    if ref["kind"] in ("single", "max", "min") and lim["kind"] in ("max", "min", "range", "single"):
        v = ref["value"]
        if v is not None and lim["value"] is not None:
            try:
                adj = abs(L.convert(v, ref_unit, spec_unit or ref_unit)[0] - lim["value"]) / max(abs(lim["value"]), 1e-12)
            except TypeError:
                adj = None
        elif v is not None and lim["kind"] == "range":
            lo, hi = lim["range"]
            adj = 0.0 if lo <= v <= hi else min(abs(v - lo), abs(v - hi)) / max(abs(v), 1e-12)

    sev = _severity(k, status, dev, lim, spec_unit, basis, item)
    return OrderedDict([
        ("name", name), ("name_key", k),
        ("category", (ent or {}).get("category") or (spec_src or {}).get("category", "其他")),
        ("critical", bool((spec_src or {}).get("critical")) or bool((ent or {}).get("critical"))),
        ("basis", basis),
        ("coa_value", meas_display),
        ("coa_unit", ref_unit),
        ("coa_raw", ref_display),
        ("spec_limit", lim_display),
        ("spec_unit", spec_unit),
        ("spec_source", origin),
        ("spec_doc_type", (specs[0].get("doc_type") if specs else "") or ""),
        ("method_coa", item["method_coa"] or ""),
        ("method_spec", item["method_spec"] or ""),
        ("method_relation", item.get("_method_relation", "")),
        ("basis_coa", L.basis_label(item["basis_coa"])),
        ("basis_spec", L.basis_label(item["basis_spec"])),
        ("status", status), ("reason", reason), ("notes", notes),
        ("deviation", dev),
        ("adjustment", adj),
        ("severity", sev),
        ("comparability", [[k2, bool(v2), comp.get("_why", {}).get(k2, "")] for k2, v2 in comp.items()
                           if k2 != "_why"]),
        ("inferred_spec", inferred),
        ("lod", (coa_it or {}).get("lod")),
        ("std_method", (spec_src or {}).get("method") or ""),
        ("loc", {"coa": (coa_it or {}).get("loc"), "spec": (spec_src or {}).get("loc")}),
        ("replicate", (coa_it or {}).get("replicate")),
        ("comment", (coa_it or {}).get("comment")),
    ])


def re_is_lod_style(lim):
    """规格用 '≤x' 上限表述时，COA 报'未检出'可视为满足。"""
    return lim.get("kind") == "max"


def _other_sources(k, data, coa):
    src = []
    coa_idx = {i["name_key"]: i for i in coa.get("items", [])}
    for c in data.get("coas", []):
        i = next((x for x in c.get("items", []) if x["name_key"] == k), None)
        if i and i.get("value") not in (None, ""):
            src.append({"source": f"COA {c.get('batch_no')}", "value": str(i.get("value")),
                        "unit": i.get("unit", "")})
    for b in data.get("historical_batches", []):
        i = next((x for x in b.get("items", []) if x["name_key"] == k), None)
        if i:
            src.append({"source": f"历史批次 {b.get('batch_no')}", "value": str(i.get("value")),
                        "unit": i.get("unit", "")})
    for std in data.get("standards", []):
        i = next((x for x in std.get("items", []) if x["name_key"] == k), None)
        if i:
            src.append({"source": std.get("code", "标准"), "value": i.get("limit", ""),
                        "unit": i.get("unit", "")})
    return src


def _untested_label(r):
    v = r["coa_value"]
    if v in (None, "", "（COA 未列该指标）"):
        return "：COA 未列该项"
    return "：COA 标注「" + str(v) + "」"


def _severity(k, status, dev, lim, unit, basis, item):
    """严重度只看三件事：限值类型、偏离幅度、指标对用途的相关性（basis）。
    与收货决策无关——它只回答"这条异议值不值得写进函件"。"""
    if status not in (L.ST_FAIL, L.ST_UNTESTED, L.ST_UNKNOWN, L.ST_UNSPEC):
        return ""
    lk = lim.get("kind")
    if lk in ("max",) and lim.get("value") in (None,):
        return "低"
    if status == L.ST_FAIL:
        strong = lk == "max" or (lk == "range" and dev.get("direction") == "超上限")
        pct = dev.get("pct") or 0
        if strong:
            return "高"
        if lk == "min":
            return "高" if basis == "mandatory" else "中"
        return "中"
    if status == L.ST_UNTESTED:
        if item.get("_coa_absent"):
            return "高" if (basis == "mandatory" or item.get("critical") or lk == "max") else "中"
        if basis == "mandatory" or item.get("critical"):
            return "高"
        if lk in ("max", "single"):
            return "高"
        return "中"
    if status == L.ST_UNKNOWN:
        return "中" if (basis == "mandatory" or item.get("critical")) else "低"
    # 规格未约定
    return "中" if (basis == "mandatory") else "低"


# ---------------------------------------------------------------------------------
# 2. 证书完整性
# ---------------------------------------------------------------------------------

def check_completeness(coa, specs, stds, aliases, rows):
    """证书完整性：字段齐备性 + 逻辑一致性 + 规格强制项的覆盖度。
    只评价"证书文件能否支撑验收"，不评价产品质量。"""
    issues = []
    hdr = coa.get("header", {})

    def add(level, field, msg, action, severity=None):
        issues.append({"level": severity or level, "field": field, "msg": msg, "action": action})

    for key, label in REQ_HEADER.items():
        v = hdr.get(key)
        if key == "cert_code":
            sub = coa.get("signoff", {})
            ok = bool(sub.get("cert_code") or sub.get("inspector") or sub.get("reviewer") or sub.get("issuer"))
            if not ok:
                add("中", label, "未提供防伪码/编制-审核-签发署名，证书可被复用或伪造而不易识别",
                    "索取带防伪码与签章的扫描件，并核对印章单位与生产企业是否一致")
            continue
        if v in (None, "", []):
            add("高" if key in ("batch_no", "mfg_date", "test_date", "test_standard") else "中",
                label, f"COA 缺少{label}", _action_for(key))
    # 日期逻辑
    d_mfg = L.parse_date(hdr.get("mfg_date"))[0]
    d_ret = L.parse_date(hdr.get("retest_date"))[0]
    d_tst = L.parse_date(hdr.get("test_date"))[0]
    if d_mfg and d_tst and d_tst < d_mfg:
        add("高", "日期逻辑", f"检测日期 {d_tst} 早于生产日期 {d_mfg}", "要求出具说明或重发证书")
    if d_mfg and d_tst and (d_tst - d_mfg).days > 30:
        add("中", "日期逻辑", f"检测日期距生产日期 {(d_tst - d_mfg).days} 天，超出常见出厂放行时限",
            "确认是否为出厂复检值；如为复检，须注明原始放行数据")
    if coa.get("collect_date") and d_tst:
        try:
            col = L.parse_date(coa["collect_date"])[0]
            if col and d_tst > col:
                add("高", "日期逻辑", f"检测日期 {d_tst} 晚于到货/收货日期 {col}", "证书与到货物可能不对应，需退回核实")
        except Exception:
            pass
    if d_ret and d_mfg and d_ret <= d_mfg:
        add("中", "复检期", "复检有效期早于或等于生产日期", "核对有效期条款")
    # 批号一致性
    bno = hdr.get("batch_no")
    if coa.get("linked_delivery_batch") and bno and L.batch_key(bno) != L.batch_key(coa["linked_delivery_batch"]):
        add("高", "批号", f"COA 批号 {bno} 与到货单批号 {coa['linked_delivery_batch']} 不一致",
            "要求供应商出具批号对应说明，否则该 COA 不能证明本批货")
    # 结论文本 vs 明细：证书内部自相矛盾，是异议里最硬的一条
    concl = (hdr.get("conclusion") or "")
    fails = [r for r in rows if r["status"] == L.ST_FAIL]
    if fails and ("合格" in concl or "符合" in concl):
        add("高", "结论一致性",
            f"证书结论写「{concl}」，但明细中有 {len(fails)} 项实测已超出合同/规格限值"
            f"（{ '、'.join(r['name'] for r in fails[:6]) } 等），结论与数据自相矛盾",
            "要求书面说明结论判定依据；如系笔误应作废重发，不得以'结论合格'覆盖超限数据")
    # 规格约定但 COA 未列/未测的指标（同行合并，不逐条刷屏）
    untested = [(r, _untested_label(r)) for r in rows if r["status"] == L.ST_UNTESTED and r["spec_limit"]]
    if untested:
        add("高" if any(r["basis"] == "mandatory" or r["severity"] == "高" for r, _ in untested) else "中",
            "缺失指标",
            f"{len(untested)} 项规格约定指标在 COA 中缺失或标注未检测：" +
            "；".join(f"{r['name']}（{r['spec_limit']} {r['spec_unit']}）{lab}" for r, lab in untested),
            "要求补充上列指标的检测结果，并注明检测方法与检出限")
    # 微量杂质无检出限
    for r in rows:
        u = L.unit_token(r["coa_unit"])[1] if r["coa_unit"] else ""
        if u in ("ppb", "μg/kg", "ug/kg", "ppm", "mg/kg") and not r.get("lod"):
            add("中", "检出限", f"微量杂质「{r['name']}」报 {r['coa_value']} {r['coa_unit']}，但未标注检出限",
                "要求注明检出限与定量限，否则无法判断是否满足 ≤ 限值")
    # 方法列整体缺失
    n_method = sum(1 for c in coa.get("items", []) if c.get("method"))
    if n_method == 0:
        add("高", "检测方法", "COA 全部指标均未标注检测方法", "索取带方法编号的正式 COA 或型式检验报告")
    elif n_method < len(coa.get("items", [])) * 0.6:
        add("中", "检测方法", f"仅 {n_method}/{len(coa.get('items', []))} 项标注检测方法",
            "补齐其余指标的方法编号")
    # 外观/包装等描述性指标
    return {"issues": issues,
            "score": _score(issues),
            "counts": {"高": sum(1 for i in issues if i["level"] == "高"),
                       "中": sum(1 for i in issues if i["level"] == "中"),
                       "低": sum(1 for i in issues if i["level"] == "低")}}


def _action_for(key):
    return {
        "batch_no": "要求供应商在 COA 上补全批号，并与随车磅单/质检单批号对应",
        "mfg_date": "补全生产日期，以判定是否超过保质期/复检期",
        "test_date": "补全检测日期，以判断是否为本批出厂检验数据",
        "test_standard": "补全检测依据（国标/企标编号），否则无法判断方法与限值来源",
        "product_name": "补全产品名称与等级（如 优等品/一等品），等级决定限值",
        "producer": "补全生产企业名称与地址，确认与合同卖方/生产厂家一致",
        "report_no": "补全报告编号，便于溯源与交叉核对",
        "conclusion": "补全检测结论与判定依据",
    }.get(key, "要求供应商补全该字段")


def _score(issues):
    """完整性得分：100 分起扣，高 -18 / 中 -8 / 低 -3，不低于 0。
    这是"证书文件本身齐不齐"的度量，不是质量结论。"""
    s = 100 - 18 * sum(1 for i in issues if i["level"] == "高") \
            - 8 * sum(1 for i in issues if i["level"] == "中") \
            - 3 * sum(1 for i in issues if i["level"] == "低")
    return max(0, s)


# ---------------------------------------------------------------------------------
# 3. 方法差异
# ---------------------------------------------------------------------------------

def method_diff(coa, specs, stds, aliases, eq_methods, results, data):
    out = {"items": [], "header_note": ""}
    for r in results:
        rel = r["method_relation"]
        if rel in ("same", "both_missing"):
            continue
        ent = aliases.get(r["name_key"], {})
        note = (ent.get("method_note") or "")
        label = {
            "different": "方法与约定不同",
            "equivalent": "方法不同但等效（须在报告中注明）",
            "missing_coa": "COA 未标注方法",
            "missing_spec": "规格未约定方法",
        }.get(rel, rel)
        # 差异对结果的可能影响
        impact = ""
        if rel == "different":
            if "红外" in (r["method_coa"] or "") and "卡尔" in (r["method_spec"] or ""):
                impact = ("卡尔费休法测的是总水（含游离水+结晶水/溶解水）；红外法在部分基体中响应偏低，"
                          "两者不能直接互换。本次红外值高于卡尔法限值，换算或复测前不能放宽判定。")
            elif "滴定" in (r["method_coa"] or "") and "色谱" in (r["method_spec"] or ""):
                impact = "滴定法为非选择性方法，易受共存组分干扰；与色谱法结果不可直接比较。"
        elif rel == "missing_coa":
            impact = (f"COA 未标注方法，结果虽在限值内，但无法证明与约定方法 {r['method_spec']} 一致；"
                      f"如买方按约定方法复检，结果可能落在方法误差带内而改变判定。")
        elif rel == "equivalent":
            impact = "功能等效但非同一方法，须在报告中注明，复检时按约定方法执行。"
        out["items"].append({
            "name": r["name"], "coa_method": r["method_coa"], "spec_method": r["method_spec"],
            "relation": rel, "label": label, "note": note, "impact": impact,
            "status": r["status"], "coa_value": r["coa_value"], "spec_limit": r["spec_limit"],
        })
    # 标准差异：合同引用标准 vs 适用国标
    for sp in specs:
        for st in stds:
            if sp.get("standard_ref") and st.get("code") and sp["standard_ref"] != st.get("code"):
                out["header_note"] = (f"合同引用 {sp['standard_ref']}，本核对另参照 {st.get('code')}；"
                                      f"两者限值/方法不一致时以合同引用为准，差异须在合同中明确")
    for c in data.get("coas", []):
        pass
    return out


# ---------------------------------------------------------------------------------
# 4. 批次趋势
# ---------------------------------------------------------------------------------

def build_trends(target_rows, data):
    """批次趋势：**先统一到规格单位再比较**。
    不同批次 COA 的单位可能不同（% / ppm / ppb），不换算直接画序列是错误来源之一。"""
    hist = data.get("historical_batches", [])
    coas = data.get("coas", [])
    out = []
    for r in target_rows:
        k = r["name_key"]
        base_u = r["spec_unit"] or r["coa_unit"] or ""
        series = []
        for b in hist:
            i = next((x for x in b.get("items", []) if x["name_key"] == k), None)
            v = L.parse_value(i.get("value"), "ref")["value"] if i else None
            u = i.get("unit") if i else ""
            v2, note = (L.convert(v, u, base_u) if (v is not None and u and base_u) else (v, ""))
            series.append((b.get("batch_no"), b.get("mfg_date"), v2, u, note))
        for c in coas:
            i = next((x for x in c.get("items", []) if x["name_key"] == k), None)
            v = L.parse_value(i.get("value"), "ref")["value"] if i else None
            u = i.get("unit") if i else ""
            v2, note = (L.convert(v, u, base_u) if (v is not None and u and base_u) else (v, ""))
            series.append((c.get("batch_no"), _get(c, "header", "mfg_date"), v2, u, note))
        series.sort(key=lambda s: L.parse_date(s[1])[0] or L.parse_date("1900-01-01")[0])
        lim = L.parse_value(r["spec_limit"], "limit") if r["spec_limit"] else None
        st = L.trend_stats([(b, d, v) for (b, d, v, _u, _n) in series], lim, base_u)
        conv = [f"{b}：{orig} {(next((s[3] for s in series if s[0] == b), ''))} → {v:.6g} {base_u}"
                for (b, d, v, orig, note) in series if v is not None and note and "×" in note]
        st["conversions"] = conv
        st["name"] = r["name"]
        st["unit"] = base_u
        st["series"] = [{"batch": b, "date": L.human_dt(L.parse_date(d)[0]), "value": v, "unit": u,
                         "base_value": v2, "base_unit": base_u,
                         "is_target": b == _get(data, "meta", "target_coa_batch")}
                        for (b, d, v2, u, _n) in series]
        out.append(st)
    return out


# ---------------------------------------------------------------------------------
# 5. 异议要点
# ---------------------------------------------------------------------------------

TONE = {
    "formal": "《质量异议函》正式、留痕、只陈述可证事实与请求，不作情绪化表述",
    "firm": "《质量异议函》立场强硬但全部落在合同/标准条款上，便于后续索赔",
    "soft": "《供应商沟通函》先沟通后定责，措辞留余地，适合长期合作供应商",
}


def objection_points(res, tone="formal"):
    """质量异议要点清单。每一点都必须能指回一条原始数据或一个文件位置。
    只写"要求供应商做什么"，不写"我方是否收货"。"""
    coa = next((c for c in res["coas"] if c.get("batch_no") == res["target_batch"]), None)
    rows = res["results"].get(res["target_batch"], [])
    comp = res["completeness"].get(res["target_batch"], {})
    meth = res["method_issues"].get(res["target_batch"], {})
    pts = []

    def add(sev, cat, title, facts, ask, evidence):
        pts.append({"no": len(pts) + 1, "severity": sev, "category": cat, "title": title,
                    "facts": facts, "ask": ask, "evidence": evidence})

    # 1) 不符合项
    for r in rows:
        if r["status"] == L.ST_FAIL:
            dev = r["deviation"]
            fact = (f"COA 实测 {r['name']} {r['coa_value']} {r['coa_unit']}，合同/规格要求 "
                    f"{r['spec_limit']} {r['spec_unit']}（依据：{r['spec_source'] or '规格书'}，"
                    f"检测方法：{r['method_coa'] or '未标注'}）")
            if dev.get("pct") is not None:
                fact += f"；{dev['direction']}，偏离 {dev['pct']:+.2f}%（{dev['absolute']:g} {r['spec_unit']}）"
            elif L.unit_token(r["coa_unit"])[0] == "定性":
                fact += f"；COA 描述与规格描述不一致（定性项，以原始目视记录/照片复核为准）"
            ask = ("请提供该批次的复检报告（同一样品、约定方法），或出具书面技术说明；"
                   "并对本批次与我方约定用途的适用性给出明确意见")
            if r["method_relation"] == "different":
                ask += f"。注意：COA 方法 {r['method_coa']} 与约定 {r['method_spec']} 不同，须按约定方法复测后方可据以判定"
            add("高" if r["severity"] == "高" else "中", "指标超限", f"{r['name']} 超出规格", fact, ask,
                [{"doc": "COA", "loc": r["loc"].get("coa")}, {"doc": "规格", "loc": r["loc"].get("spec")}])
    # 2) 关键指标未检：合并成一条（同一请求，分开写只会让函件变长）
    missing = [r for r in rows if r["status"] == L.ST_UNTESTED and r["spec_limit"]]
    if missing:
        names = "、".join(f"{r['name']}（{r['spec_limit']} {r['spec_unit']}）" for r in missing)
        ask_parts = []
        for r in missing:
            ask_parts.append(f"{r['name']}：{'原表标注未检测' if r['coa_value'] not in (None, '') else '未列该项'}")
        add("高" if any(r["severity"] == "高" for r in missing) else "中", "缺项",
            f"{len(missing)} 项规格约定指标 COA 缺失或未检测",
            f"合同/规格已约定以下指标限值，COA 未给出实测值：{names}",
            "请补充上述指标的检测结果，并在报告中注明检测方法与检出限（明细：" + "；".join(ask_parts) + "）",
            [{"doc": "COA", "loc": None}] + [{"doc": "规格", "loc": r["loc"].get("spec")} for r in missing[:4]])
    # 3) 方法差异
    for m in meth.get("items", []):
        if m["relation"] == "missing_coa":
            add("中", "方法差异", f"{m['name']} 未标注检测方法",
                f"该指标 COA 未给出检测方法（合同/规格约定 {m['spec_method']}），无法确认是否按约定方法检验",
                "要求在 COA 中补齐该指标的检测方法编号",
                [{"doc": "COA", "loc": None}, {"doc": "规格", "loc": None}])
            continue
        if m["relation"] == "different":
            add("中", "方法差异", f"{m['name']} 检测方法与约定不同",
                (f"COA 标注方法 {m['coa_method']}，合同/规格约定 {m['spec_method']}"
                 if m["coa_method"] not in (None, "", "—")
                 else f"COA 未标注方法，合同/规格约定 {m['spec_method']}")
                + f"。{m['impact'] or m['note']}".strip(),
                "请说明方法选择理由，并按约定方法复测；如主张方法等效，请提供方法比对/验证数据",
                [{"doc": "COA", "loc": None}, {"doc": "规格", "loc": None}])
    # 4) 证书完整性（高优先级项）
    for i in comp.get("issues", []):
        if i["level"] != "高":
            continue
        add("高", "证书完整性", i["field"], i["msg"], i["action"], [{"doc": "COA", "loc": None}])
    # 5) 结论矛盾（完整性检查已就"结论一致性"出条时不再重复）
    concl = _get(coa or {}, "header", "conclusion")
    fails = [r for r in rows if r["status"] == L.ST_FAIL]
    if fails and concl and ("合格" in concl or "符合" in concl) and \
            not any(i["field"] == "结论一致性" for i in comp.get("issues", [])):
        add("高", "结论矛盾", "COA 结论与检测数据矛盾",
            f"证书结论写「{concl}」，但 " + "、".join(f"{r['name']}={r['coa_value']} {r['coa_unit']}"
                                                for r in fails) + " 已超出规格限值",
            "请书面说明结论判定依据；如系笔误请作废并重发证书，不得以'结论合格'覆盖超限数据",
            [{"doc": "COA", "loc": None}])
    # 6) 规格未约定项 → 不代表不合格，但需确认
    unspecified = [r for r in rows if r["status"] == L.ST_UNSPEC]
    if unspecified:
        names = "、".join(f"{r['name']}（{r['coa_value']} {r['coa_unit']}）" for r in unspecified[:6])
        add("低", "规格口径", "部分指标超出合同约定范围，需确认口径",
            f"以下指标未在采购规格书中约定限值：{names}",
            "请供应商书面确认产品的生产规格（企标）与等级，供后续合同补充约定；本次不作为不合格依据",
            [{"doc": "规格", "loc": None}])
    # 排序：高→中→低
    pts.sort(key=lambda p: -L.SEV.get(p["severity"], 0))
    for i, p in enumerate(pts, 1):
        p["no"] = i
    return {"tone": tone, "tone_desc": TONE.get(tone, ""), "points": pts,
            "counts": {s: sum(1 for p in pts if p["severity"] == s) for s in L.SEV_ORDER}}


def draft_message(res, tone="formal"):
    """生成可直接粘贴的函件正文（纯文本）。不含任何"是否收货"的判断。"""
    o = objection_points(res, tone)
    p = res["product"]
    sp = res["supplier"]
    coa = next((c for c in res["coas"] if c.get("batch_no") == res["target_batch"]), {})
    h = coa.get("header", {})
    L_ = []
    ship = h.get("ship_date")
    col = coa.get("collect_date")
    bits = []
    if ship:
        bits.append(f"贵司于 {ship} 发出")
    if col:
        bits.append(f"我方于 {col} 到货")
    when = "、".join(bits) or "近期交付"
    if tone == "formal":
        L_.append(f"致：{sp.get('name', '供应商')}（{sp.get('contact', '')}）")
        L_.append("")
        grade = f"（{h['grade']}）" if h.get("grade") not in (None, "", "—") else ""
        L_.append(f"主题：{p.get('name')}{grade}到货批次质量异议 — 批号 {h.get('batch_no', '')}")
        L_.append("")
        L_.append(f"{sp.get('contact_name', '负责人')}：")
        L_.append(f"经核对贵司交付的{p.get('name')}（{when}；批号 {h.get('batch_no', '') or '（COA 未标注）'}；"
                  f"随车《质量分析证书》编号 {h.get('report_no', '') or '（未提供）'}），"
                  f"现将需要贵司书面回复的事项列明如下：")
    elif tone == "firm":
        L_.append(f"主题：【质量异议】{p.get('name')} 批号 {h.get('batch_no', '')} 未满足合同技术附件约定")
        L_.append("")
        L_.append(f"{sp.get('contact_name', '负责人')}：")
        L_.append("")
        L_.append(f"经核对，贵司随货提供的《质量分析证书》与我方采购质量规格书（{res['meta'].get('spec_ref', '')}）"
                  f"存在下列不符之处，请在 3 个工作日内书面答复：")
    else:
        L_.append(f"{sp.get('contact_name', '负责人')}您好：")
        L_.append("")
        L_.append(f"关于{p.get('name')}批号 {h.get('batch_no', '')} 的核对情况，先与您同步，"
                  f"有几处需要您方面协助确认：")
    for pt in o["points"]:
        L_.append("")
        L_.append(f"{pt['no']}.【{pt['severity']}】{pt['title']}")
        L_.append(f"   情况：{pt['facts']}")
        L_.append(f"   请贵司：{pt['ask']}")
    L_.append("")
    if tone == "formal":
        L_.append("以上事项请于收到本函后 3 个工作日内以书面形式回复。在贵司答复及我方完成复检确认前，"
                  "本批次的质量责任与处置方式按合同质量条款执行。")
    elif tone == "firm":
        L_.append("逾期未答复，我方将按合同质量条款保留相应权利，并以本合同约定的检测方法委托第三方复检。")
    else:
        L_.append("以上仅为技术核对结果，不涉及商务结论。烦请协助确认，谢谢！")
    # 语气相关的附注：只讲事实与口径，不替用户定调
    if tone == "formal":
        cmp_ = res["completeness"].get(res["target_batch"], {}).get("counts", {})
        if cmp_.get("高"):
            hi_pts = [p for p in res["objections"]["points"]
                      if p["severity"] == "高" and p["category"] == "证书完整性"]
            names = "、".join(p["title"] for p in hi_pts)
            L_.append(f"另：本批 COA 存在 {cmp_['高']} 项高优先级完整性缺陷"
                      + (f"（{names}）" if names else "") + "，请一并核对后补发正式证书。")
    if tone == "soft":
        ks = res["kpis"]
        L_.append("")
        L_.append(f"说明：本次核对共 {ks['total']} 项，其中符合 {ks['ok']} 项、不符合 {ks['fail']} 项、"
                  f"未检测 {ks['untested']} 项、无法判断 {ks['unknown']} 项。"
                  f"因贵司 COA 与合同规格在部分指标上存在口径差异，以上结论以合同技术附件为准。")
    L_.append("")
    L_.append("附件：1) 质量分析证书（原件扫描件）2) 采购质量规格书相关条款 3) 指标逐项比对表")
    L_.append(f"联系人：{res.get('meta', {}).get('buyer_name', '采购部')}  {res.get('meta', {}).get('buyer_contact', '')}")
    return "\n".join(L_)


# ---------------------------------------------------------------------------------
# 6. 主流程
# ---------------------------------------------------------------------------------

def run(data):
    res = compare(data)
    res["tone"] = data.get("meta", {}).get("tone", "formal")
    res["kpis"] = _kpis(res)
    res["objections"] = objection_points(res, res["tone"])
    res["draft"] = draft_message(res, res["tone"])
    res["drafts"] = {t: draft_message(res, t) for t in ("formal", "firm", "soft")}
    res["kpis"]["objection_points"] = len(res["objections"]["points"])
    res["risks"] = _risks(res)
    return res


def _kpis(res):
    t = res["target_batch"]
    rows = res["results"].get(t, [])
    s = res["summary"].get(t, {})
    comp = res["completeness"].get(t, {})
    fails = [r for r in rows if r["status"] == L.ST_FAIL]
    maxdev = max([abs((r["deviation"].get("pct") or 0)) for r in fails], default=0)
    unspecified_ratio = (s.get(L.ST_UNSPEC, 0) / len(rows) * 100) if rows else 0
    verifiable = sum(s.get(x, 0) for x in (L.ST_OK, L.ST_FAIL))
    return {
        "target_batch": t, "total": len(rows), "counts": s,
        "fail": s.get(L.ST_FAIL, 0), "ok": s.get(L.ST_OK, 0),
        "untested": s.get(L.ST_UNTESTED, 0), "unknown": s.get(L.ST_UNKNOWN, 0),
        "unspec": s.get(L.ST_UNSPEC, 0),
        "max_dev_pct": maxdev,
        "completeness": comp.get("score", 0), "comp_high": comp.get("counts", {}).get("高", 0),
        "unspec_ratio": unspecified_ratio,
        "verifiable_ratio": (verifiable / len(rows) * 100) if rows else 0,
        "method_diff": sum(1 for m in res["method_issues"].get(t, {}).get("items", [])
                           if m["relation"] == "different"),

    }


def _risks(res):
    t = res["target_batch"]
    rows = res["results"].get(t, [])
    out = []
    for r in rows:
        if r["status"] == L.ST_FAIL:
            out.append({"sev": r["severity"], "type": "指标超限", "item": r["name"],
                        "desc": f"{r['coa_value']} {r['coa_unit']} vs {r['spec_limit']} {r['spec_unit']}；"
                                f"{r['deviation'].get('human', '')}"})
        elif r["status"] == L.ST_UNTESTED and r["spec_limit"]:
            out.append({"sev": r["severity"], "type": "关键指标未检", "item": r["name"],
                        "desc": f"规格 {r['spec_limit']} {r['spec_unit']}，COA 缺项"})
        elif r["status"] == L.ST_UNKNOWN:
            out.append({"sev": r["severity"], "type": "无法判断", "item": r["name"], "desc": r["reason"]})
    for i in res["completeness"].get(t, {}).get("issues", []):
        out.append({"sev": i["level"], "type": "证书完整性", "item": i["field"], "desc": i["msg"]})
    for m in res["method_issues"].get(t, {}).get("items", []):
        if m["relation"] == "different":
            out.append({"sev": "中", "type": "方法差异", "item": m["name"],
                        "desc": f"{m['coa_method']} vs {m['spec_method']}"})
    out.sort(key=lambda x: -L.SEV.get(x["sev"], 0))
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    res = run(load(a.data))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=str)
        print("written", a.json)
    else:
        k = res["kpis"]
        print(json.dumps(k, ensure_ascii=False, indent=1))
        for r in res["results"][res["target_batch"]]:
            print(f'{r["status"]:6s} {r["name"]:16s} COA={r["coa_value"]:>10s}{r["coa_unit"]:8s} '
                  f'SPEC={str(r["spec_limit"]):>12s}{r["spec_unit"]:6s} {r["reason"][:40]}')


if __name__ == "__main__":
    main()
