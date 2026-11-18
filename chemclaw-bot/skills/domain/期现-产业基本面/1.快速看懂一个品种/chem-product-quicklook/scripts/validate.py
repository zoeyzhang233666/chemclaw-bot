#!/usr/bin/env python3
"""validate.py — research.json 结构/来源/口径校验（0 error 才允许出图）

用法:
    python scripts/validate.py research.json [--strict]

规则见 references/data-contract.md §8。error 会导致 build_all 中止；warn 需人工解释。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

DIRECTIONAL = ["预计上涨", "预计下跌", "看涨", "看跌", "必涨", "必跌", "抄底", "可以囤货", "建议囤货", "底部已现"]
VAGUE_NUM = re.compile(r"(约|大约|左右|估计|预计|认为|可能)\s*\d")
DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
# 纯展示字段允许为空（不承载事实）
DECORATIVE = re.compile(r"(\.cap|\.spot|\.unit|\.share|\.meta|_gap|\.url|\.sub|\.desc|\.note|\.note_en|\.role|\.status|\.tax|\.region|\.spec|\.freq|\.caliber|\.why|\.source|\.n)$")


class Report:
    def __init__(self):
        self.errors = []
        self.warns = []

    def err(self, code, msg):
        self.errors.append(f"[{code}] {msg}")

    def warn(self, code, msg):
        self.warns.append(f"[{code}] {msg}")


def iter_strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def walk_nodes(nodes, parent=None, acc=None, depth=0):
    acc = acc if acc is not None else []
    for n in nodes:
        acc.append((n, parent, depth))
        for ch in n.get("children", []) or []:
            acc.append(({"id": ch.get("id"), "name": ch.get("name"), "_child": True}, n, depth + 1))
    return acc


def validate(data: dict, strict=False) -> Report:
    r = Report()

    # 1 meta
    meta = data.get("meta") or {}
    for k in ["title", "data_asof", "generated", "version", "output_name"]:
        if not meta.get(k):
            r.err("meta.missing", f"meta.{k} 缺失")
    if meta.get("data_asof") and not DATE_RE.match(str(meta["data_asof"])):
        r.err("meta.date", f"meta.data_asof 格式应为 YYYY-MM-DD，实为 {meta['data_asof']}")

    # 2 product
    p = data.get("product") or {}
    if not p.get("name_cn"):
        r.err("product.name", "product.name_cn 缺失")
    if not (p.get("cas") or p.get("hs")):
        r.err("product.id", "product.cas 与 product.hs 至少提供 1 个，否则品种身份不成立")
    if p.get("cas") and not re.match(r"^\d{2,7}-\d{2}-\d$", str(p["cas"])):
        r.warn("product.cas", f"CAS 格式可疑：{p['cas']}")
    if not p.get("card"):
        r.err("product.card", "product.card 为空，首屏无法渲染")
    for c in p.get("card", []):
        if not c.get("k"):
            r.err("product.card", "card 条目缺 k")
        if "v" in c and c["v"] == "":
            r.err("empty.value", f"card「{c.get('k')}」值为空字符串；缺口请用 null 或省略")
    if "has_futures" not in p:
        r.err("product.has_futures", "必须显式声明 has_futures（true/false），由研究决定而非模板默认")

    # 3 chain
    ch = data.get("chain") or {}
    cols = ch.get("cols") or []
    if len(cols) < 3:
        r.err("chain.cols", f"产业链列数 {len(cols)} < 3")
    col_ids = [c.get("id") for c in cols]
    nodes = ch.get("nodes") or []
    if len(nodes) < 5:
        r.err("chain.nodes", f"节点数 {len(nodes)} 过少（<5），无法构成产业链")
    ids = {}
    for n in nodes:
        if not n.get("id"):
            r.err("chain.id", f"节点缺 id：{n.get('name')}")
            continue
        if n["id"] in ids:
            r.err("chain.dup", f"节点 id 重复：{n['id']}")
        ids[n["id"]] = n
        if n.get("col") not in col_ids:
            r.err("chain.col", f"节点 {n['id']} 的 col={n.get('col')} 不在 cols 中")
        if n.get("parent") and n["parent"] not in ids and n["parent"] not in {x.get("id") for x in nodes}:
            r.err("chain.parent", f"节点 {n['id']} 的 parent={n['parent']} 不存在")
    selfs = [n for n in nodes if n.get("is_self") or n.get("kind") == "self"]
    if len(selfs) != 1:
        r.err("chain.self", f"is_self/kind=self 节点应为 1 个，实为 {len(selfs)}")
    # 环检测
    for n in nodes:
        seen, cur = set(), n
        while cur and cur.get("parent"):
            if cur["parent"] in seen:
                r.err("chain.cycle", f"父子关系成环：{n['id']}")
                break
            seen.add(cur["parent"])
            cur = ids.get(cur["parent"])

    # 4 sources
    src_ids = {s.get("id") for s in data.get("sources") or []}
    if not src_ids:
        r.err("sources.empty", "sources 为空：研究入口页不允许零来源交付")
    for s in data.get("sources") or []:
        if not s.get("id"):
            r.err("sources.id", "来源缺 id")
        if not s.get("date"):
            r.warn("sources.date", f"来源 {s.get('id')} 缺日期")
        if s.get("url") and not str(s["url"]).startswith("http"):
            r.err("sources.url", f"来源 {s.get('id')} URL 非 http(s)：{s['url']}")
    for path, txt in iter_strings(data):
        pass  # 引用检查见下（结构化）

    def chk_src_refs(ids_list, where):
        for i in ids_list or []:
            if i not in src_ids:
                r.err("sources.ref", f"{where} 引用了不存在的来源 {i}")

    for n in nodes:
        chk_src_refs(n.get("src"), f"节点 {n.get('id')}.src")
        for k in ("sources",):
            chk_src_refs((n.get("research") or {}).get(k), f"节点 {n.get('id')}.research.{k}")
        for sp in (n.get("research") or {}).get("spot", []) or []:
            chk_src_refs(sp.get("src"), f"节点 {n.get('id')}.spot")
        for cp in (n.get("research") or {}).get("companies", []) or []:
            chk_src_refs(cp.get("src"), f"节点 {n.get('id')}.companies")
    for pnl in data.get("panels") or []:
        for bi, blk in enumerate(pnl.get("body") or []):
            where = f"panel[{pnl.get('id')}].body[{bi}]"
            chk_src_refs(blk.get("src"), where)
            for it in blk.get("items") or []:
                chk_src_refs(it.get("src"), where + ".items")
                for ln in it.get("lines") or []:
                    chk_src_refs(ln.get("src"), where + ".lines")
            for row in blk.get("rows") or []:
                chk_src_refs(row.get("src") or row.get("srcs"), where + ".rows")
            for g in blk.get("groups") or []:
                chk_src_refs(g.get("src"), where + ".groups")
                for it in g.get("items") or []:
                    chk_src_refs(it.get("src"), where + ".groups.items")

    # 5 futures 一致性
    has_f = bool(p.get("has_futures"))
    fr = (data.get("research") or {}).get("futures") or {}
    if has_f:
        items = fr.get("items") or []
        if not items:
            r.err("futures.missing", "has_futures=true 但 research.futures.items 为空")
        blob = json.dumps(fr, ensure_ascii=False)
        for need in ["交易所", "合约", "交易单位", "交割"]:
            if need not in blob:
                r.err("futures.field", f"期货模块缺少「{need}」相关条款")
        for it in items:
            chk_src_refs(it.get("src"), "futures.items")
            if not it.get("src"):
                r.warn("futures.src", f"期货卡「{it.get('title')}」未挂来源")
        # 必须有交割品级与现货主流规格对应
        cap_hit = any((b.get("type") == "table") and re.search(r"交割|现货规格|对应", b.get("caption", "") + json.dumps(b.get("columns", []), ensure_ascii=False))
                      for pnl in data.get("panels") or [] for b in pnl.get("body") or [])
        if not cap_hit:
            r.warn("futures.spot_map", "未发现「交割标准品 ↔ 现货主流规格」对照表，期现衔接不完整")
    else:
        if fr.get("items"):
            r.err("futures.conflict", "has_futures=false 却填写了期货条款")
        gapnote = any(b.get("type") == "gapnote" for pnl in data.get("panels") or [] for b in pnl.get("body") or [])
        if not gapnote:
            r.err("futures.gapnote", "无期货品种必须用 gapnote 说明“不设期现模块”")

    # 6 模糊数
    for path, txt in iter_strings(data):
        if VAGUE_NUM.search(txt):
            r.warn("vague.num", f"{path}: 数值带模糊词「{VAGUE_NUM.search(txt).group(0).strip()}」→ {txt[:40]}")
        if txt.strip() == "":
            if strict and not DECORATIVE.match(path):
                r.err("empty.value", f"{path}: 空字符串（装饰性字段之外不允许空串）")

    # 7 方向性表述
    blob = json.dumps(data, ensure_ascii=False)
    for w in DIRECTIONAL:
        if w in blob:
            r.err("directional", f"含方向性表述「{w}」，品种入门页不做行情判断")

    # 8 panels 完整性
    panels = data.get("panels") or []
    if len(panels) < 4:
        r.err("panels.count", f"下方面板仅 {len(panels)} 个，至少 4 个（工艺/产能/下游/期现或指标）")
    pids = [x.get("id") for x in panels]
    for need in ["routes", "capacity", "demand", "indicators"]:
        if need not in pids:
            r.err("panels.id", f"缺少标准面板「{need}」（可直接留空 block 并写 gapnote，不可删）")

    # 9 frame
    if len(data.get("frame") or []) < 3:
        r.err("frame", "研究指标框架少于 3 个维度")

    # 10 gaps / caveats
    if not data.get("gaps"):
        r.warn("gaps.empty", "未声明任何缺口：请确认不是“全都有数”，而是漏写")
    if not data.get("caveats"):
        r.warn("caveats.empty", "未写口径提醒")

    if strict:
        for w in list(r.warns):
            r.errors.append(w)
        r.warns = []
    return r


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("research")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    data = json.loads(Path(a.research).read_text(encoding="utf-8-sig"))
    r = validate(data, a.strict)
    for w in r.warns:
        print("WARN " + w)
    for e in r.errors:
        print("ERROR " + e)
    print(f"[validate] error={len(r.errors)} warn={len(r.warns)}")
    return 0 if not r.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
