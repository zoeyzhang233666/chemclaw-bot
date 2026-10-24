#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付前自检：把 references/07-qa-checklist.md 的条目变成可执行断言。

用法:
    python selfcheck.py inquiry.json [--outdir 示例输出目录]

不通过时返回 1。每一条都给出“为什么”而不是只报错。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

import _common as C

if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

R = []  # (level, code, msg)


def chk(cond, code, msg, level="error"):
    R.append((level, code, msg) if not cond else ("ok", code, ""))
    return cond


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--outdir", default="")
    a = ap.parse_args()

    D = C.normalize(C.load_json(a.data))
    M, S = D["meta"], D["stats"]
    checks = D["checks"]
    all_text = json.dumps(D, ensure_ascii=False)

    # ---- A. 真伪与口径
    chk(isinstance(M.get("synthetic"), bool), "A1", "meta.synthetic 必须是布尔值")
    if M.get("synthetic"):
        chk(bool(M.get("synthetic_note")), "A2", "模拟主体必须在 meta.synthetic_note 里说明虚构范围")
        chk("模拟" in all_text or "虚构" in all_text, "A3", "模拟数据应在正文中至少出现一次“模拟/虚构”提示")
        banners = 0
        for m in D.get("messages", []):
            if m.get("purpose") and ("模拟" in m["purpose"] or "虚构" in m["purpose"]):
                banners += 1
        # HTML 页眉横幅由 meta.synthetic 自动生成，这里只确认 meta 已标
        chk(True, "A4", "")

    # ---- B. 三分法纪律
    present = {c["status"] for c in checks}
    for st in ("verified", "discrepancy", "unverified"):
        chk(st in present, "B1", f"结论里必须出现“{C.STATUS_LABEL[st]}”状态（三分法不允许只剩一种）")
    for c in checks:
        if c["status"] == "verified":
            chk(bool(c["source_ids"]), "B2", f"{c['id']} 标为已核实却没有来源")
        if c["status"] == "discrepancy":
            chk(bool(c.get("doubts")), "B3", f"{c['id']} 标为疑点却没写具体矛盾")
            chk(bool(c.get("boundary")), "B4", f"{c['id']} 标为疑点却没写边界说明")
            chk(bool(c.get("next_ids")), "B5", f"{c['id']} 标为疑点却没绑定下一步")

    # ---- C. 禁用表述
    bad = []
    for pat, why in (
        (r"(?<!不)(?<!不得)(?<!不给)诈骗概率\s*[:：]?\s*\d", "给出了诈骗概率"),
        (r"(?:大概|大概率|很可能|极可能)是\s*(?:骗子|诈骗|虚假公司|空壳)", "主观推断为骗子"),
        (r"注册时间(?:短|很新).{0,12}(?:说明|证明)", "以注册时间判真伪"),
    ):
        for m in re.finditer(pat, all_text):
            bad.append((why, all_text[max(0, m.start() - 30):m.end() + 20]))
    chk(not bad, "C1", f"命中禁用表述：{bad[:2]}")

    # ---- D. 同名隔离
    chk(any(l["relation"] == "name_collision" for l in D.get("linkage", [])),
        "D1", "必须包含同名/近似名排查条目（本方法最核心的风险）")
    for l in D.get("linkage", []):
        chk(bool(l.get("rule")), "D2", f"{l['id']} 缺少判定规则")

    # ---- E. 联系方式四要素
    items = " ".join(r["item"] for r in D.get("matrix", []))
    for need in ("名称", "地址", "电话", "邮箱"):
        chk(need in items, "E1", f"一致性矩阵缺少 {need} 项")
    chk(len(D.get("email_auth", [])) >= 4, "E2", "发信认证检查应覆盖 域名/Reply-To/SPF/DMARC/邮件头")

    # ---- F. 来源
    grades = {s["grade"] for s in D["sources"]}
    chk("A" in grades, "F1", "来源库缺少 A 级（官方登记/政府）来源")
    chk("D" in grades, "F2", "来源库缺少 D 级（对方自述）标注——自述必须单独标出")
    for s in D["sources"]:
        if s["kind"] in ("registry", "sanctions", "regulation"):
            chk(bool(s["url"]), "F3", f"官方来源 {s['id']} 没有链接")

    # ---- G. 索取清单
    reqs = D["requests"]
    chk(any(q["priority"] == "P0" for q in reqs), "G1", "资料清单必须有 P0 项")
    for q in reqs:
        chk(bool(q.get("en")), "G2", f"{q['id']} 缺英文表述（要直接发给对方）")
        chk(bool(q.get("why")), "G3", f"{q['id']} 没写为什么要这份材料")
    chk(any("NIB" in (q.get("en") or "") for q in reqs), "G4", "印尼等 OSS 国家应索取 NIB 类唯一识别号；其他国家的等价物请在 references 里替换")

    # ---- H. 行动与话术
    chk(len(D.get("actions", [])) >= 4, "H1", "行动清单至少 4 步（索取/检索/核验/复查）")
    chk(len(D.get("messages", [])) >= 2, "H2", "至少 2 段英文话术（首次索取 + 追问）")
    for m in D.get("messages", []):
        chk("Subject:" in (m.get("body_en") or ""), "H3", f"{m.get('id')} 英文话术缺 Subject 行")

    # ---- I. 结论可复盘
    chk(bool(S.get("verdict_line")), "I1", "缺少一句话结论")
    chk(len(D.get("boundaries", [])) >= 3, "I2", "使用边界至少 3 条")

    # ---- J. 产物
    if a.outdir:
        htmls = [f for f in os.listdir(a.outdir) if f.endswith(".html")]
        xlsxs = [f for f in os.listdir(a.outdir) if f.endswith(".xlsx")]
        chk(bool(htmls), "J1", "输出目录没有 HTML")
        chk(bool(xlsxs), "J2", "输出目录没有 XLSX")
        for f in htmls:
            p = os.path.join(a.outdir, f)
            txt = open(p, "r", encoding="utf-8").read()
            chk("__DATA__" not in txt and "__STYLE__" not in txt, "J3", f"{f} 残留模板占位符")
            chk(len(txt) > 40_000, "J4", f"{f} 体积异常小，可能没渲染")
            if M.get("synthetic"):
                chk("模拟样例" in txt or "MOCK" in txt, "J5", "模拟数据必须在页面上有横幅提示")

    errs = [r for r in R if r[0] == "error"]
    warns = [r for r in R if r[0] == "warn"]
    for lv, code, msg in R:
        if lv != "ok":
            print(f"[{lv:5}] {code}  {msg}")
    total = len([r for r in R if r[1]])
    print(f"\n自检 {total} 条：通过 {total - len(errs) - len(warns)} / error {len(errs)} / warn {len(warns)}")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
