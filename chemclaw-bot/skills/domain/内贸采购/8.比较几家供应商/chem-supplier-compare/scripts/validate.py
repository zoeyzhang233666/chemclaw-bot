# -*- coding: utf-8 -*-
"""validate.py — data.json 的证据一致性校验（不通过则不允许出报告）。

    python scripts/validate.py data.json [--strict]

检查项：
  1. 结构：meta/suppliers/dimensions/evidence 必填字段；
  2. 引用：每个 V:/S:/M:/X: 标签必须带至少一个存在的证据编号；
  3. 标签一致：证据来源类型与标签是否冲突（年报标 M、官网自述标 V 会被提示）；
  4. 空白：维度单元格为空、风险等级缺失；
  5. 禁用词：不得出现“最佳供应商”“综合评分”“推荐供应商”等结论性表述；
  6. 报价一致性：quotes.status=none 时，商业条款不得出现具体价格数字；
  7. 时效：as_of 与当前日期差距过大时提示。
"""
import datetime
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cmplib as L  # noqa: E402

BANNED = [
    (r"最佳供应商", "不得给出“最佳供应商”结论"),
    (r"最优供应商", "不得给出“最优供应商”结论"),
    (r"综合评分|综合得分|综合打分", "不得做综合评分"),
    (r"首选供应商|建议选择|推荐采购", "不得替采购方下选择结论"),
]

# 证据来源类型 → 允许/禁止的标签
SRC_HINT = {
    "上市公司年报": {"V"},
    "上市公司半年报": {"V"},
    "环评公示": {"V"},
    "法院文书": {"V"},
    "政府网站": {"V"},
    "企业官网（自述）": {"S"},
    "第三方百科": {"M"},
    "媒体报道": {"M"},
    "行业媒体": {"M"},
    "第三方转载": {"M"},
    "缺口登记": {"U"},
}


def check(data):
    errs, warns = [], []
    m = data.get("meta") or {}
    for k in ("doc_no", "as_of", "title"):
        if not m.get(k):
            errs.append("meta.%s 缺失" % k)
    sups = data.get("suppliers") or []
    if not (2 <= len(sups) <= 5):
        errs.append("suppliers 数量应为 2–5，当前 %d" % len(sups))
    ids = [s.get("id") for s in sups]
    if len(set(ids)) != len(ids):
        errs.append("supplier.id 重复：%s" % ids)

    ev = {e.get("id"): e for e in (data.get("evidence") or [])}
    if not ev:
        errs.append("evidence 为空：所有标签都必须能落到证据")
    for e in ev.values():
        if not e.get("url"):
            warns.append("证据 %s 缺少 url" % e.get("id"))

    dims = data.get("dimensions") or []
    if len(dims) < 6:
        warns.append("维度少于 6 个，横向比较可能过于单薄")
    keys = [d.get("key") for d in dims]
    if len(set(keys)) != len(keys):
        errs.append("dimension.key 重复")

    types = {e.get("id"): e.get("type") for e in ev.values()}

    def check_cell(path, raw):
        if isinstance(raw, dict):
            v = raw.get("v", "")
            evid = raw.get("ev", "")
        else:
            v, evid = str(raw or ""), ""
        for label, eids_, _note in L.split_evidence(evid):
            if label in "VSMX" and not eids_:
                errs.append("%s：标签 %s 未附证据编号" % (path, label))
            for i in eids_:
                if i not in ev:
                    errs.append("%s：引用不存在的证据 %s" % (path, i))
                    continue
                allowed = SRC_HINT.get(types.get(i))
                if allowed and label not in allowed:
                    warns.append("%s：证据 %s 来源为「%s」，却标为 %s（建议改为 %s）"
                                 % (path, i, types.get(i), L.LABELS[label]["cn"],
                                    "/".join(L.LABELS[x]["cn"] for x in sorted(allowed))))
        return v

    for s in sups:
        sd = s.get("dims") or {}
        for d in dims:
            k = d["key"]
            if d.get("type") == "terms":
                continue
            if k not in sd:
                errs.append("供应商 %s 缺少维度 %s" % (s.get("id"), k))
                continue
            v = check_cell("%s.%s" % (s.get("id"), k), sd[k])
            if not str(v).strip():
                errs.append("供应商 %s 维度 %s 内容为空" % (s.get("id"), k))
            if d.get("type") in ("risk", "event") and not sd[k].get("lvl"):
                errs.append("供应商 %s 维度 %s 缺少等级 lvl" % (s.get("id"), k))
        if s.get("producer") not in L.PRODUCER:
            errs.append("供应商 %s 的 producer 取值非法" % s.get("id"))
        for ct in s.get("certs") or []:
            if ct.get("end"):
                L.parse_date(ct["end"]) or warns.append(
                    "供应商 %s 证照「%s」有效期无法解析：%s" % (s.get("id"), ct.get("name"), ct.get("end")))

    # 禁用词：只扫描“结论性叙述”，规则说明性文本（meta.use_note 等）不参与
    narr = []
    for s_ in sups:
        for k, cell in (s_.get("dims") or {}).items():
            narr.append(str(cell.get("v", "") if isinstance(cell, dict) else cell))
            narr.append(str(cell.get("note", "") if isinstance(cell, dict) else ""))
        narr.append(str(s_.get("summary", "")))
    for f in data.get("findings") or []:
        narr += [str(f.get("title", "")), str(f.get("text", ""))]
    for it in data.get("intel") or []:
        narr.append(str(it.get("text", "")))
    for grp in (data.get("questions") or {}).values():
        for q in grp:
            narr += [str(q.get("q", "")), str(q.get("why", ""))]
    blob = "\n".join(narr)
    for pat, why in BANNED:
        hit = re.search(pat, blob)
        if hit:
            errs.append("出现禁用表述「%s」：%s（上下文：…%s…）"
                        % (pat, why, blob[max(0, hit.start() - 24):hit.end() + 24].replace("\n", " ")))

    # 报价一致性
    q = data.get("quotes") or {}
    if q.get("status") == "none":
        for s in sups:
            for k, cell in (s.get("quote") or {}).items():
                if cell.get("status") not in (None, "pending", "missing"):
                    errs.append("供应商 %s 条款 %s 状态与 quotes.status=none 冲突" % (s.get("id"), k))
                if re.search(r"\d+\s*元", str(cell.get("v", ""))):
                    errs.append("供应商 %s 条款 %s 出现具体价格，但声明为未报价" % (s.get("id"), k))

    # 时效
    as_of = L.parse_date(m.get("as_of"))
    if as_of:
        gap = (datetime.date.today() - as_of).days
        if gap > 90:
            warns.append("数据截止日距今天 %d 天，请更新证据后再出报告" % gap)
        if gap < 0:
            warns.append("数据截止日在未来（%s），请核对" % m.get("as_of"))

    # 问题清单覆盖
    qs = data.get("questions") or {}
    for s in sups:
        if not qs.get(s.get("id")):
            warns.append("供应商 %s 没有问询问题清单" % s.get("id"))
    return errs, warns


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    strict = "--strict" in sys.argv
    if not args:
        print("usage: python validate.py data.json [--strict]")
        raise SystemExit(2)
    data = json.load(io.open(args[0], encoding="utf-8"))
    errs, warns = check(data)
    print("── 校验：%s" % args[0])
    for w in warns:
        print("  [警告] %s" % w)
    for e in errs:
        print("  [错误] %s" % e)
    print("结果：%d 个错误，%d 个警告" % (len(errs), len(warns)))
    if errs or (strict and warns):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
