# -*- coding: utf-8 -*-
"""端到端流水线：读取一票单证 → 识别类型 → 抽取字段 → 跨单证比对 → 输出 JSON。"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import compare
import extract
import taxonomy

# 模板 / 内部标准 / 填制指引类文件不是本票业务单证
REF_MARKERS = ("模板", "TEMPLATE", "填写说明", "GUIDELINE", "STANDARD", "标准",
               "填制要求", "作业指引", "范本", "使用说明")


def _is_reference_doc(text, filename):
    """模板/标准/指引类文件。只检查**标题区**（前 200 字），避免把 COA 里的
    "执行标准 STANDARD" 或合同里的"标准条款"误判为参考文件。"""
    head = text[:200]
    up = head.upper()
    if re.search(r"(模板|TEMPLATE|填制要求|作业指引|填写说明|使用说明|范本)", up):
        has_number = bool(re.search(r"(HYE|COSU|CCPIT)[-\w]*\d{4}", text))
        return not has_number
    # 标题中就写"标准/STANDARD + 文件/单证/EXPORT DOC"这类
    if re.search(r"(文件标准|单证标准|EXPORT\s*DOC\w*\s*STANDARD|DOCUMENT\s*STANDARD)", up):
        return True
    # "公司/内部/作业 + 出口单证/文件 + 标准/规范/流程" 标题
    if re.search(r"(公司|内部|企业|集团|部门|作业|业务)", up) and \
            re.search(r"(出口|单证|单据|文件|DOCUMENT)", up) and \
            re.search(r"(标准|规范|流程|指引|制度|手册|STANDARD|GUIDE|PROCEDURE|POLICY|MANUAL)",
                      up):
        return True
    if re.search(r"(要求|说明|指引|规范)\s*[（(]?\s*(DEMO|模拟)", head):
        return True
    return False


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files.extend(sorted(glob.glob(os.path.join(p, "*.pdf"))))
            files.extend(sorted(glob.glob(os.path.join(p, "*.PDF"))))
        elif os.path.isfile(p):
            files.append(p)
    seen, out = set(), []
    for f in files:
        k = os.path.abspath(f).lower()
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def _hint_type(d, path):
    if d.doc_type and d.doc_type != "UNKNOWN":
        return d.doc_type
    base = os.path.basename(path).upper()
    for code, meta in taxonomy.DOC_TYPES.items():
        for alias in meta.get("aliases", []) + [meta.get("cn", ""), meta.get("en", "")]:
            if alias and alias.upper() in base:
                return code
    return d.doc_type


def run(paths, use_filename_hint=True):
    files = collect(paths)
    docs = [extract.Document(p) for p in files]
    anchor = extract.find_anchor(docs)
    docs_out = []
    for d, path in zip(docs, files):
        if use_filename_hint:
            hint = _hint_type(d, path)
            if hint != d.doc_type:
                d.cls["doc_type"] = hint
                d._tables = None
        joined = " ".join(pg.text for pg in d.pages)
        if _is_reference_doc(joined, os.path.basename(path)):
            docs_out.append({
                "id": "REF%d" % len(docs_out), "type": d.doc_type or "REF",
                "type_cn": "参考文件（非本票业务单证）",
                "filename": os.path.basename(path), "path": path,
                "pages": len(d.pages), "fields": {}, "expected": [],
                "excluded": True,
                "reason": "检测到模板/标准/指引类文本，不作为本票单据参与核对",
            })
            continue
        exp = taxonomy.expected_fields(d.doc_type)
        fields = extract.extract_document(d, exp)
        docs_out.append({
            "id": d.doc_type if d.doc_type != "UNKNOWN" else os.path.basename(path).split("_")[0],
            "type": d.doc_type,
            "type_cn": taxonomy.DOC_TYPES.get(d.doc_type, {}).get("cn", d.doc_type),
            "filename": os.path.basename(path),
            "path": path,
            "pages": len(d.pages),
            "fields": fields,
            "expected": exp,
        })
    live = [d for d in docs_out if not d.get("excluded")]
    # 同类型多份时避免 id 冲突
    used = {}
    for d in live:
        if d["id"] in used:
            used[d["id"]] += 1
            d["id"] = "%s%d" % (d["id"], used[d["id"]])
        else:
            used[d["id"]] = 1
    # 把原始页面文本挂到每份单证上，供"柜数/体积容量"这类跨字段推导使用
    by_name = {os.path.basename(p): p for p in files}
    for d in live:
        f = by_name.get(d["filename"])
        if f:
            d["text"] = "\n".join(pg.text for pg in extract.Document(f).pages)
    payload = compare.build_matrix(live)
    matrix = payload["matrix"]
    checks = compare.compute_checks(payload["field_values"],
                                    {d["id"]: d.get("text", "") for d in live})
    issues = compare.build_issues(live, matrix, checks)
    summary = compare.summarize(matrix, issues, checks)
    anchor = dict(anchor or {})
    anchor.update(_ticket_headline(live))
    return {"docs": docs_out, "anchor": anchor, "matrix": matrix,
            "checks": checks, "issues": issues, "summary": summary,
            "run_at": __import__("datetime").datetime.now().isoformat(timespec="seconds")}


def _pick(live, fid):
    """按可信度优先取某字段的值（销售合同 > 商业发票 > 其它）。"""
    order = {"SC": 0, "CI": 1, "PI": 2, "BL": 3}
    best = None
    for d in sorted(live, key=lambda x: order.get(x["id"], 9)):
        rec = (d.get("fields") or {}).get(fid)
        if rec and rec.get("value"):
            if best is None:
                best = str(rec["value"])
    return best or ""


def _ticket_headline(live):
    """票面摘要：供检查页/报告标题栏使用。"""
    return {
        "contract_no": _pick(live, "contract_no"),
        "ci_no": _pick(live, "ci_no"),
        "bl_no": _pick(live, "bl_no"),
        "seller": _pick(live, "seller_name"),
        "buyer": _pick(live, "buyer_name"),
        "product": _pick(live, "product_name_en"),
        "pol": _pick(live, "pol"),
        "pod": _pick(live, "pod"),
        "quantity": _pick(live, "quantity"),
        "amount": _pick(live, "amount"),
        "incoterm": _pick(live, "incoterm"),
    }


def main():
    args = sys.argv[1:]
    out = None
    if "--out" in args:
        i = args.index("--out")
        out = args[i + 1]
        del args[i:i + 2]
    res = run(args or ["."])
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(txt)
        print("已输出:", out)
        s = res["summary"]
        print("单证 %d 份 | 差异 %d | 缺失 %d | 计算不符 %d | 问题 %d (S1=%d)" % (
            len([d for d in res["docs"] if not d.get("excluded")]),
            s["cells"]["DIFF"], s["cells"]["MISS"], s["cells"]["CALC"],
            s["issues"], s["severity"].get("S1", 0)))
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(txt)


if __name__ == "__main__":
    main()
