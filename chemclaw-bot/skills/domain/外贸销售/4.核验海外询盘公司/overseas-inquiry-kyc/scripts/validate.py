#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据校验：inquiry.json 结构 + 本 skill 的硬性纪律。

用法:
    python validate.py inquiry.json [--strict]

退出码：0 = 通过（可能有 warning）；1 = 有 error。
纪律检查（error 级）与“文风”检查（warning 级）分开，避免把建议当错误。
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

import _common as C

# Windows 控制台默认 GBK，中文输出会炸；统一转 UTF-8
if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# 只拦截“给出概率/给主体定性”的表述；防止误伤“不给出诈骗概率”这类澄清句
_FRAUD = r"(?:诈骗|欺诈|骗局|欺诈交易|money\s*scam)\s*(?:的)?\s*(?:概率|可能性|几率|风险值)"
FORBIDDEN_PATTERNS = [
    (r"(?<!不)(?<!不得)(?<!不给)(?<!未经)" + _FRAUD + r"\s*(?:约为|大约|约)?\s*\d+(?:\.\d+)?\s*%", "不得给出诈骗概率"),
    (r"(?:诈骗|欺诈)(?:概率|可能性)\s*[:：]\s*\d", "不得给出诈骗概率"),
    (r"(?:大概|大概率|很可能|极可能|应该)是\s*(?:骗子|诈骗|虚假公司|空壳)", "不得主观推断为骗子/虚假企业"),
    (r"注册时间(?:短|很新).{0,12}(?:说明|证明).{0,10}(?:虚假|皮包|骗子)", "不得以域名注册时间判断企业真假"),
    (r"(?<!不得)(?<!不能)(?<!未)确定为虚假企业|肯定是假公司|确认是虚假企业", "不得在未取得登记信息时给“虚假”定性"),
]

REQUIRED_TOP = [
    "meta", "inquiry", "extraction", "subject", "domains", "email_auth", "matrix",
    "business_fit", "checks", "linkage", "risks", "sources", "requests", "actions", "messages",
]

SECTION_KEYS = {s["id"] for s in C.SECTIONS}


def iter_text(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_text(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_text(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def run(path, strict=False):
    errors, warns, infos = [], [], []
    D = C.load_json(path)
    for k in REQUIRED_TOP:
        if k not in D:
            errors.append(f"缺少顶层字段 {k}")
    try:
        D = C.normalize(D)
    except ValueError as e:
        errors.append(str(e))
        return errors, warns, infos, None

    checks = D["checks"]
    if len(checks) < 8:
        warns.append(f"核验项只有 {len(checks)} 条，建议 ≥ 16 条（覆盖五区块）")

    # 1 每个区块都要有核验项
    for s in C.SECTIONS[:4]:
        n = [c for c in checks if c["section"] == s["id"]]
        if not n:
            errors.append(f"区块 {s['id']}（{s['title']}）没有任何核验项")
    unknown_sec = [c["id"] for c in checks if c["section"] not in SECTION_KEYS]
    if unknown_sec:
        errors.append(f"核验项 section 取值非法：{unknown_sec}")

    # 2 疑点项必须写清边界与下一步；核实项必须给来源
    for c in checks:
        if c["status"] == "discrepancy":
            if not c.get("boundary"):
                errors.append(f"{c['id']} 标为“存在疑点”，但没有写 boundary（边界说明）")
            if not c.get("next_ids"):
                errors.append(f"{c['id']} 标为“存在疑点”，但没有绑定 next_ids（下一步资料/动作）")
            if not c.get("doubts"):
                errors.append(f"{c['id']} 标为“存在疑点”，但 doubts 为空——疑点必须写具体矛盾")
        if c["status"] == "verified" and not c["source_ids"]:
            errors.append(f"{c['id']} 标为“已核实”，但没有 source_ids——已核实必须能点回来源")
        if not c["source_ids"] and c["status"] != "not_applicable":
            warns.append(f"{c['id']} 没有关联来源（状态 {c['status']}）")

    # 3 三种状态都要出现（否则就是没做区分）
    present = {c["status"] for c in checks}
    for need in ("verified", "discrepancy", "unverified"):
        if need not in present:
            warns.append(f"核验结果中没有出现“{C.STATUS_LABEL[need]}”状态——请确认是否真的做了三分")

    # 4 业务相关性区块至少一条 verified（产品与行业是否相关必须能判）
    if not [c for c in checks if c["section"] == "B" and c["status"] == "verified"]:
        warns.append("B 区块没有“已核实”项：业务相关性至少要有一项可核实的判断")

    # 5 来源：至少一条 A 级（官方）锚点，且必须有 id/url 字段
    grades = {s["grade"] for s in D["sources"]}
    if "A" not in grades:
        warns.append("来源库中没有 A 级（官方登记/政府）来源，主体核验缺锚点")
    for s in D["sources"]:
        if s["kind"] in ("registry", "sanctions", "regulation") and not s["url"]:
            errors.append(f"来源 {s['id']} 属于官方类，但没有 url")

    # 6 真伪声明：模拟主体必须打标
    if not isinstance(D["meta"].get("synthetic"), bool):
        errors.append("meta.synthetic 必须是布尔值（true=模拟，false=真实询盘）")
    if D["meta"].get("synthetic") and not D["meta"].get("synthetic_note"):
        errors.append("meta.synthetic=true 时必须写 meta.synthetic_note（说明哪些是虚构的）")

    # 7 同名/错配必须有规则
    if D["linkage"] and not any(l["relation"] == "name_collision" for l in D["linkage"]):
        warns.append("linkage 中没有 name_collision（同名企业）条目——这是本 skill 的核心风险")
    for l in D["linkage"]:
        if not l.get("rule"):
            warns.append(f"{l['id']}（{l['relation']}）没有写 rule（判定规则）")

    # 8 联系方式矩阵必须覆盖名称/地址/电话/邮箱
    items = " ".join(r["item"] for r in D["matrix"])
    for must, label in (("名称", "公司名称"), ("地址", "地址"), ("电话", "电话"), ("邮箱", "邮箱")):
        if must not in items:
            warns.append(f"matrix 没有覆盖 {label} 的一致性条目")

    # 9 资料清单：每个 P0 都必须有 why；索取项要有英文表述
    for q in D["requests"]:
        if not q.get("en"):
            errors.append(f"{q['id']} 缺少英文表述 en（需直接发给对方）")
        if not q.get("why"):
            warns.append(f"{q['id']} 没有写 why（为什么要这份材料）")
    if not [q for q in D["requests"] if q["priority"] == "P0"]:
        warns.append("资料清单里没有 P0 项")

    # 10 必须提供英文消息草稿
    if not D["messages"]:
        errors.append("缺少 messages：必须生成向对方索取资料的英文消息草稿")
    for m in D["messages"]:
        if not m.get("body_en"):
            errors.append(f"消息 {m.get('id')} 没有 body_en")
        if not re.search(r"Subject:", m.get("body_en") or ""):
            warns.append(f"消息 {m.get('id')} 的 body_en 没有 Subject 行")

    # 11 禁用表述扫描
    for path_, text in iter_text(D):
        for pat, why in FORBIDDEN_PATTERNS:
            if re.search(pat, text):
                errors.append(f"命中禁用表述（{why}）@ {path_}：{text[:60]}…")

    # 12 每条“已核实”的业务/官方结论都要有日期
    for c in checks:
        if c["status"] == "verified" and c["section"] in ("A", "D"):
            infos.append(f"{c['id']} 为 A/D 区块的“已核实”，请确认来源均有检索日期")

    # 13 统计
    st = D["stats"]
    infos.append(
        f"核验项 {st['checks_total']} 条：已核实 {st['status']['verified']} / "
        f"存在疑点 {st['status']['discrepancy']} / 未核实 {st['status']['unverified']}")
    infos.append(f"来源 {st['sources']} 条；资料索取 {sum(st['requests'].values())} 项")

    if strict and warns:
        errors.extend([f"[strict] {w}" for w in warns])
    return errors, warns, infos, D


def main():
    ap = argparse.ArgumentParser(description="校验 inquiry.json")
    ap.add_argument("data")
    ap.add_argument("--strict", action="store_true", help="把 warning 也当 error")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    errors, warns, infos, D = run(a.data, a.strict)
    if not a.quiet:
        for i in infos:
            print(f"[info]  {i}")
        for w in warns:
            print(f"[warn]  {w}")
        for e in errors:
            print(f"[ERROR] {e}")
    if errors:
        print(f"\n✗ 校验失败：{len(errors)} error / {len(warns)} warning")
        return 1
    print(f"\n✓ 校验通过：0 error / {len(warns)} warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
