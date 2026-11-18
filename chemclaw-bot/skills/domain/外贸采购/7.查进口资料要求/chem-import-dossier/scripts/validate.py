#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate.py — 把 SKILL.md 的「硬纪律」变成可执行检查

用法：
    python scripts/validate.py examples/h2o2-kr-30/data.json [--json out.json]
退出码：0 = 全部通过（仅 WARN 可见）；1 = 存在 FAIL
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import imrules as R  # noqa: E402

FAIL, WARN, INFO = "FAIL", "WARN", "INFO"


class Report:
    def __init__(self):
        self.rows = []

    def add(self, level, code, msg, where=""):
        self.rows.append(dict(level=level, code=code, msg=msg, where=where))

    def fail(self, code, msg, where=""):
        self.add(FAIL, code, msg, where)

    def warn(self, code, msg, where=""):
        self.add(WARN, code, msg, where)

    def info(self, code, msg, where=""):
        self.add(INFO, code, msg, where)

    @property
    def fails(self):
        return [r for r in self.rows if r["level"] == FAIL]

    def summary(self):
        c = {FAIL: 0, WARN: 0, INFO: 0}
        for r in self.rows:
            c[r["level"]] += 1
        return c


def all_text(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def v01_schema(data, rep):
    req_top = ["as_of", "inputs", "product_identity", "hs_candidates", "hs_verdict", "tax_rates",
               "regulation_checklist", "danger_distinction", "transport", "documents",
               "uploaded", "gaps", "responsibilities", "to_confirm", "sources", "assessment"]
    for k in req_top:
        if k not in data:
            rep.fail("V01", f"缺少顶层字段 {k}")
    if not R.parse_date(data.get("as_of")):
        rep.fail("V01", "as_of 不是合法日期（必须 YYYY-MM-DD）")
    for k in ["product_name_cn", "cas", "concentration", "composition", "usage",
              "packing", "transport_mode", "origin_country"]:
        if not data.get("inputs", {}).get(k):
            rep.fail("V01", f"inputs.{k} 为空——产品身份未锁定", "inputs")
    comp = data.get("inputs", {}).get("composition", [])
    if not comp:
        rep.warn("V01", "未给出组成（成分表）——纯物质也建议至少写出主成分与稳定剂")
    for c in comp:
        if not c.get("cas"):
            rep.warn("V01", f"组分『{c.get('name')}』未给 CAS", "inputs.composition")


def v02_hs(data, rep):
    cands = data.get("hs_candidates", [])
    if not cands:
        rep.fail("V02", "无 HS 候选")
        return
    if not any(c.get("rank") == 1 for c in cands):
        rep.fail("V02", "HS 候选中没有 rank=1 的首选编码")
    for c in cands:
        if not c.get("basis"):
            rep.fail("V02", f"HS {c.get('code')} 未写归类依据", "hs_candidates")
        if not c.get("confidence"):
            rep.fail("V02", f"HS {c.get('code')} 未给出置信度", "hs_candidates")
        if c.get("rank") == 1 and len(cands) < 2:
            rep.warn("V02", "仅有一个 HS 候选——建议至少写出 1 个备选/兜底路径")
    rec = data.get("hs_verdict", {}).get("recommended")
    codes = {c.get("code", "").replace(".", "") for c in cands}
    if rec and rec.replace(".", "") not in codes:
        rep.fail("V02", f"推荐编码 {rec} 不在候选列表中")
    if not data.get("hs_verdict", {}).get("uncertainty"):
        rep.fail("V02", "未声明 HS 归类的不确定性")


def v03_regulation(data, rep):
    regs = data.get("regulation_checklist", [])
    if len(regs) < 6:
        rep.fail("V03", f"监管清单仅 {len(regs)} 项，明显不足（至少覆盖危化品、易制爆、运输、检验、两用物项、用途专项）")
    seen = set()
    for r in regs:
        rid = r.get("id")
        if rid in seen:
            rep.fail("V03", f"监管项编号重复 {rid}")
        seen.add(rid)
        if r.get("verdict") not in R.VERDICTS:
            rep.fail("V03", f"{rid} verdict 取值非法：{r.get('verdict')}")
        if not r.get("basis"):
            rep.fail("V03", f"{rid}『{r.get('item')}』未写法规依据")
        if not r.get("source"):
            rep.fail("V03", f"{rid}『{r.get('item')}』未关联证据来源")
        if r.get("verdict") in ("applies", "conditional") and not r.get("condition"):
            rep.fail("V03", f"{rid}『{r.get('item')}』结论为适用/视条件适用但未写适用条件")
        if r.get("verdict") == "conditional" and r.get("confidence") == "high":
            rep.warn("V03", f"{rid} 视条件适用却标 high 置信——请确认是否应降级")
    # 必须出现的关键监管层（方法论要求，不是产品结论）
    layers = " ".join(r.get("layer", "") for r in regs)
    for need, label in [("危险化学品", "危险化学品管理"), ("运输", "危险货物运输"),
                        ("检验", "检验检疫"), ("用途", "用途专项")]:
        if need not in layers:
            rep.fail("V03", f"监管清单缺少『{label}』维度")
    # 两套分类必须分别判定
    dd = data.get("danger_distinction", {})
    if not dd.get("chemical") or not dd.get("goods"):
        rep.fail("V03", "危险化学品与危险货物未分别判定")
    if dd.get("chemical") and dd.get("goods"):
        if dd["chemical"].get("regime") == dd["goods"].get("regime"):
            rep.fail("V03", "危险化学品与危险货物被写成了同一套体系——必须区分")
    if len(dd.get("matrix", [])) < 3:
        rep.warn("V03", "浓度/形态对照矩阵少于 3 行——阈值型产品建议覆盖阈值两侧")


def v04_documents(data, rep):
    docs = data.get("documents", [])
    if len(docs) < 15:
        rep.fail("V04", f"单证清单仅 {len(docs)} 项，明显不足")
    seen = set()
    for d in docs:
        did = d.get("id")
        if did in seen:
            rep.fail("V04", f"单证编号重复 {did}")
        seen.add(did)
        if d.get("required") not in ("必须", "视情形", "建议"):
            rep.fail("V04", f"{did} required 取值非法：{d.get('required')}")
        if d.get("status") not in R.DOC_STATUS:
            rep.fail("V04", f"{did} status 取值非法：{d.get('status')}")
        if not d.get("owner"):
            rep.fail("V04", f"{did} 未写明责任主体")
        if d.get("required") == "必须" and not d.get("basis"):
            rep.fail("V04", f"{did} 为必须件但未写依据")
        if d.get("status") == "partial" and not d.get("issue"):
            rep.fail("V04", f"{did} 状态 partial 但未说明问题")
    # 中文化学品资料必须存在（这是“进口危化品”的方法论要求，具体是否适用由监管清单判定）
    names = " ".join(d.get("name_cn", "") for d in docs)
    if "中文" not in names:
        rep.fail("V04", "单证清单中未出现任何中文合规文件（中文SDS/中文标签）——若是危化品则必然缺失")


def v05_upload(data, rep):
    docs = data.get("documents", [])
    up = data.get("uploaded", [])
    doc_ids = {d["id"]: d for d in docs}
    for u in up:
        ref = doc_ids.get(u.get("doc_ref")) if u.get("doc_ref") else None
        if not u.get("checks"):
            rep.fail("V05", f"{u.get('id')} 无检查项")
        for c in u.get("checks", []):
            if c.get("result") not in ("pass", "fail", "warn", "na"):
                rep.fail("V05", f"{u.get('id')} 检查项 {c.get('id')} result 非法")
        if u.get("verdict") not in R.UPLOAD_VERDICT:
            rep.fail("V05", f"{u.get('id')} verdict 非法")
        if not u.get("extracted"):
            rep.warn("V05", f"{u.get('id')} 未提取任何字段")
        if u.get("is_mock") and not u.get("mock_note"):
            rep.fail("V05", f"{u.get('id')} 标为模拟件但缺少 mock_note——必须显式标注")
        if u.get("is_mock") and "模拟" not in (u.get("file") or ""):
            rep.warn("V05", f"{u.get('id')} 文件名未带『模拟』字样，建议加上以免混淆")
    # 引用一致性：单证指向的上传件必须存在
    up_ids = {u.get("id") for u in up}
    for d in docs:
        if d.get("uploaded_id") and d["uploaded_id"] not in up_ids:
            rep.fail("V05", f"{d['id']} 引用了不存在的上传件 {d['uploaded_id']}")
        if d.get("uploaded_id") and d.get("status") == "missing":
            rep.fail("V05", f"{d['id']} 有上传件 {d['uploaded_id']} 却标为 missing")


def v06_gaps(data, rep):
    gaps = data.get("gaps", [])
    if not gaps:
        rep.fail("V06", "没有列出缺失资料——任何真实进口都不可能零缺口")
    ids = set()
    for g in gaps:
        if g.get("id") in ids:
            rep.fail("V06", f"缺口编号重复 {g.get('id')}")
        ids.add(g.get("id"))
        if g.get("priority") not in R.PRIORITIES:
            rep.fail("V06", f"{g.get('id')} priority 非法")
        for k in ("missing", "why", "ask", "owner"):
            if not g.get(k):
                rep.fail("V06", f"{g.get('id')} 缺少 {k}")
    if not any(g.get("blocking") == "是" for g in gaps) and any(d.get("status") in ("missing", "partial") for d in data.get("documents", []) if d.get("required") == "必须"):
        rep.fail("V06", "存在必须件缺失/不完整，但没有任何缺口被标为 blocking=是")


def v07_confirm(data, rep):
    qs = data.get("to_confirm", [])
    if len(qs) < 5:
        rep.fail("V07", f"待确认事项仅 {len(qs)} 项——法规类结论中至少应有归类/许可/税率/属地口径等")
    for q in qs:
        for k in ("topic", "why", "who", "impact_if_wrong"):
            if not q.get(k):
                rep.fail("V07", f"{q.get('id')} 缺少 {k}")
        if q.get("severity") not in ("高", "中", "低"):
            rep.fail("V07", f"{q.get('id')} severity 非法")


def v08_sources(data, rep):
    srcs = {s.get("id"): s for s in data.get("sources", [])}
    if len(srcs) < 10:
        rep.fail("V08", f"证据来源仅 {len(srcs)} 条，不足以支撑 15 项监管结论")
    for s in srcs.values():
        for k in ("title", "publisher", "url", "accessed"):
            if not s.get(k):
                rep.fail("V08", f"{s.get('id')} 缺少 {k}")
        if not str(s.get("url", "")).startswith("http"):
            rep.fail("V08", f"{s.get('id')} url 不是 http(s) 链接")
        if R.days_between(data.get("as_of"), s.get("accessed")) is None:
            rep.fail("V08", f"{s.get('id')} accessed 不是合法日期")
        if not s.get("supports"):
            rep.fail("V08", f"{s.get('id')} 未说明支撑了哪条结论")
    # 监管项引用的来源必须存在
    for r in data.get("regulation_checklist", []):
        for sid in re.split(r"[,，\s]+", r.get("source", "")):
            if sid and sid not in srcs:
                rep.fail("V08", f"{r.get('id')} 引用了不存在的来源 {sid}")
    for c in data.get("hs_candidates", []):
        for sid in re.split(r"[,，\s]+", c.get("source", "")):
            if sid and sid not in srcs:
                rep.fail("V08", f"HS {c.get('code')} 引用了不存在的来源 {sid}")
    # C 级来源不得作为唯一依据
    for r in data.get("regulation_checklist", []):
        sids = [s for s in re.split(r"[,，\s]+", r.get("source", "")) if s]
        if sids and all(srcs.get(s, {}).get("tier") == "C" for s in sids):
            rep.fail("V08", f"{r.get('id')}『{r.get('item')}』仅由 C 级来源支撑")


def v09_language(data, rep):
    txt = all_text(data)
    for pat, why in R.BANNED_PHRASES:
        for m in re.finditer(pat, txt):
            rep.fail("V09", f"出现禁用表述：『{m.group(0)}』（{why}）", m.group(0))
    # 「不属于」必须带目录依据
    for r in data.get("regulation_checklist", []):
        if r.get("verdict") == "not_applies":
            if not r.get("basis") or len(r.get("basis", "")) < 8:
                rep.fail("V09", f"{r.get('id')} 判定『不适用』但依据不足")
            if r.get("confidence") not in ("high", "medium"):
                rep.warn("V09", f"{r.get('id')} 判定不适用且置信度 {r.get('confidence')}，建议标 pending 或补强依据")


def v10_numbers(data, rep):
    """税费与计算口径一致性（只查结构，不重算商业数据）。"""
    tr = data.get("tax_rates", {})
    if not tr.get("mfn", {}).get("rate"):
        rep.fail("V10", "未给出最惠国税率")
    if not tr.get("vat", {}).get("rate"):
        rep.fail("V10", "未给出增值税税率")
    for f in tr.get("fta", []):
        if f.get("status") in ("disputed", "pending", "claimed") and not any(
                any(t in q.get("topic", "") for t in ("中韩", "FTA", "RCEP", "协定", "原产地"))
                for q in data.get("to_confirm", [])):
            rep.warn("V10", f"协定税率『{f.get('scheme')}』状态为 {f.get('status')}，但在待确认事项中没有对应条目")
    calc = data.get("calculation", {})
    if calc.get("cif_cny") and calc.get("duty_cny"):
        exp = round(float(calc["cif_cny"]) * float(str(calc["duty_rate"]).rstrip("%")) / 100, 2)
        if abs(exp - float(calc["duty_cny"])) > max(1.0, exp * 0.01):
            rep.fail("V10", f"关税试算不一致：{calc['cif_cny']}×{calc['duty_rate']}={exp}，但写的是 {calc['duty_cny']}")
    if calc.get("vat_base_cny") and calc.get("vat_cny"):
        exp = round(float(calc["vat_base_cny"]) * float(str(calc["vat_rate"]).rstrip("%")) / 100, 2)
        if abs(exp - float(calc["vat_cny"])) > max(1.0, exp * 0.01):
            rep.fail("V10", f"增值税试算不一致：{calc['vat_base_cny']}×{calc['vat_rate']}={exp}，但写的是 {calc['vat_cny']}")


def v11_responsibility(data, rep):
    rs = data.get("responsibilities", [])
    actors = {R.norm_actor(r.get("actor")) for r in rs}
    for need in ("海外供应商", "进口商", "报关代理"):
        if need not in actors:
            rep.fail("V11", f"责任划分缺少『{need}』——四类主体的资料义务必须分开写")
    for r in rs:
        if not r.get("items"):
            rep.fail("V11", f"{r.get('actor')} 未列明资料义务")
    for d in data.get("documents", []):
        if R.norm_actor(d.get("owner")) not in actors:
            rep.warn("V11", f"{d.get('id')} 的责任主体『{d.get('owner')}』未出现在责任划分表中")


def v12_transport(data, rep):
    dd = data.get("danger_distinction", {})
    goods = dd.get("goods", {})
    if goods.get("applicable") == "applies":
        for k in ("un", "cls", "pg", "proper_shipping_name"):
            if not goods.get(k):
                rep.fail("V12", f"判为危险货物但缺少 {k}")
        t = data.get("transport", {})
        if t.get("un") != goods.get("un"):
            rep.fail("V12", f"transport.un({t.get('un')}) 与 danger_distinction.goods.un({goods.get('un')}) 不一致")
        if not t.get("segregation"):
            rep.warn("V12", "危险货物未写积载隔离要求")
        if not t.get("labels"):
            rep.fail("V12", "危险货物未写标签（类项标志）")


def v13_identity(data, rep):
    pid = data.get("product_identity", {})
    if pid.get("identity_verdict") == "confirmed" and pid.get("unconfirmed"):
        rep.fail("V13", "identity_verdict=confirmed 但仍列出未确认项——应为 partial")
    if not pid.get("one_liner"):
        rep.fail("V13", "缺少一句话身份判断")
    if not pid.get("risk_points"):
        rep.warn("V13", "未列身份风险点")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--template", action="store_true",
                    help="骨架模板模式：占位符与最小条目数降级为 WARN，只拦住结构性错误")
    args = ap.parse_args()
    with open(args.data, encoding="utf-8") as f:
        data = json.load(f)

    rep = Report()
    for fn in (v01_schema, v02_hs, v03_regulation, v04_documents, v05_upload, v06_gaps,
               v07_confirm, v08_sources, v09_language, v10_numbers, v11_responsibility,
               v12_transport, v13_identity):
        fn(data, rep)

    if args.template:
        # 占位符导致的日期/数量类问题不算失败，只是提醒还没填
        keep = []
        for r in rep.rows:
            if r["level"] == FAIL and (r["code"] in ("V01", "V04", "V06", "V07", "V08")
                                       or "引用" in r["msg"] or "非法" in r["msg"] and "取值" not in r["msg"]):
                r["level"] = WARN
                r["msg"] = "（骨架待填）" + r["msg"]
            keep.append(r)
        rep.rows = keep

    s = rep.summary()
    print(f"== 校验 {os.path.basename(args.data)}{'（模板模式）' if args.template else ''} ==")
    for r in rep.rows:
        if r["level"] == INFO:
            continue
        print(f"[{r['level']}] {r['code']} {r['msg']}")
    print(f"\n结果：FAIL {s[FAIL]} / WARN {s[WARN]} / INFO {s[INFO]}")
    comp = R.doc_completeness(data.get("documents", []))
    print(f"单证完备度 {comp['pct']}%（必须件 {comp['n_required_ok']}/{comp['n_required']} 齐备）")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"rows": rep.rows, "summary": s, "completeness": comp}, f, ensure_ascii=False, indent=2)
    return 1 if rep.fails else 0


if __name__ == "__main__":
    sys.exit(main())
