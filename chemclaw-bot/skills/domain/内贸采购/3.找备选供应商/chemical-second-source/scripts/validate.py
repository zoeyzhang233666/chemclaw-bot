#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate data.json before building. Exit 1 on hard errors."""
from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import urlparse

import common

RISK_LEVELS = {"低", "中", "中高", "高"}
SPEC_STATES = {"COA", "试样", "审核"}
RISK_STATES = {"已公开", "待核实"}


def _num(x, default=None):
    try:
        return float(x)
    except Exception:
        return default


def check(D):
    errors, warnings = [], []
    M = D.get("meta") or {}
    base = D.get("baseline") or {}
    cands = D.get("candidates") or []
    specs = D.get("spec_items") or []
    status = D.get("spec_status") or {}
    srcs = D.get("sources") or []
    src_ids = {s.get("id") for s in srcs}

    for k in ("product", "product_short", "unit", "asof", "buyer_site", "spec"):
        if not str(M.get(k) or "").strip():
            errors.append(f"meta.{k} 必填")
    if not (M.get("volume") or M.get("volume_t")):
        errors.append("meta.volume 或 meta.volume_t 至少填一个")
    if not M.get("processes"):
        errors.append("meta.processes 至少填一个工艺路线")
    proc_names = [p.get("name") if isinstance(p, dict) else p for p in (M.get("processes") or [])]
    if len(proc_names) != len(set(proc_names)):
        errors.append("meta.processes 有重复工艺名")

    for k in ("name", "short", "process"):
        if not str(base.get(k) or "").strip():
            errors.append(f"baseline.{k} 必填")
    if _num(base.get("capacity"), 0) <= 0:
        errors.append("baseline.capacity 必须 >0")
    if _num(base.get("distance"), None) is None or _num(base.get("distance")) < 0:
        errors.append("baseline.distance 必须 >=0")
    if _num(base.get("freight_low"), None) is None or _num(base.get("freight_high"), None) is None:
        errors.append("baseline.freight_low / freight_high 必填")
    elif _num(base.get("freight_low")) > _num(base.get("freight_high")):
        errors.append("baseline.freight_low 不能大于 freight_high")
    base_proc = base.get("process")
    if proc_names and base_proc not in proc_names:
        errors.append(f"baseline.process={base_proc!r} 不在 meta.processes 中")

    if not (2 <= len(cands) <= 20):
        errors.append(f"candidates 数量应在 2–20 家，当前 {len(cands)}")
    elif len(cands) < 5:
        warnings.append("candidates 少于 5 家，作为“备选池”偏薄；建议 5–15 家")

    seen_ids, seen_names = set(), set()
    for i, c in enumerate(cands, 1):
        tag = c.get("id") or f"#{i}"
        for k in ("id", "name", "short", "process"):
            if not str(c.get(k) or "").strip():
                errors.append(f"candidate {tag}: {k} 必填")
        if c.get("id") in seen_ids:
            errors.append(f"candidate id 重复: {c.get('id')}")
        seen_ids.add(c.get("id"))
        nm = str(c.get("name") or "").strip()
        if nm in seen_names:
            errors.append(f"candidate 企业名重复: {nm}")
        seen_names.add(nm)
        if proc_names and c.get("process") not in proc_names:
            errors.append(f"{tag} process={c.get('process')!r} 不在 meta.processes 中")
        if _num(c.get("capacity"), 0) <= 0:
            errors.append(f"{tag} capacity 必须 >0")
        if _num(c.get("distance"), None) is None or _num(c.get("distance")) < 0:
            errors.append(f"{tag} distance 必须 >=0")
        if _num(c.get("freight_low"), None) is None or _num(c.get("freight_high"), None) is None:
            errors.append(f"{tag} freight_low / freight_high 必填")
        elif _num(c.get("freight_low")) > _num(c.get("freight_high")):
            errors.append(f"{tag} freight_low 不能大于 freight_high")
        if c.get("risk_level") not in RISK_LEVELS:
            errors.append(f"{tag} risk_level 必须是 低/中/中高/高")
        rs = _num(c.get("risk_score"), None)
        if rs is None or not (1 <= rs <= 5):
            errors.append(f"{tag} risk_score 必须是 1–5")
        if not isinstance(c.get("qualified"), bool):
            errors.append(f"{tag} qualified 必须是 true/false")
        ev = c.get("evidence") or []
        if not ev:
            warnings.append(f"{tag} 没有 evidence 来源 ID")
        for sid in ev:
            if sid not in src_ids:
                errors.append(f"{tag} evidence 引用了不存在的 source id: {sid}")

    if not (3 <= len(specs) <= 20):
        errors.append(f"spec_items 数量应在 3–20 项，当前 {len(specs)}")
    spec_ids = [s.get("id") for s in specs]
    if len(spec_ids) != len(set(spec_ids)):
        errors.append("spec_items.id 重复")
    for s in specs:
        if not s.get("id") or not s.get("label"):
            errors.append("spec_items 每项都要有 id 和 label")

    for c in cands:
        cid = c.get("id")
        st = status.get(cid)
        if not isinstance(st, dict):
            errors.append(f"{cid} 缺少 spec_status")
            continue
        for sid in spec_ids:
            v = st.get(sid)
            if v not in SPEC_STATES:
                errors.append(f"{cid}.spec_status.{sid} 必须是 COA/试样/审核，当前 {v!r}")
        extra = set(st) - set(spec_ids)
        if extra:
            warnings.append(f"{cid}.spec_status 有未定义指标: {sorted(extra)}")

    if not (1 <= len(srcs) <= 200):
        errors.append(f"sources 数量应在 1–200 条，当前 {len(srcs)}")
    seen_src = set()
    for s in srcs:
        sid = s.get("id")
        if not sid:
            errors.append("source 缺少 id")
        if sid in seen_src:
            errors.append(f"source id 重复: {sid}")
        seen_src.add(sid)
        if not s.get("name"):
            errors.append(f"source {sid} 缺少 name")
        if s.get("grade") not in {"A", "B", "C"}:
            errors.append(f"source {sid} grade 必须是 A/B/C")
        u = str(s.get("url") or "")
        if not u:
            warnings.append(f"source {sid} 没有 URL")
        elif not (u.startswith("http://") or u.startswith("https://")):
            errors.append(f"source {sid} URL 必须是 http(s): {u}")
        else:
            try:
                host = urlparse(u).netloc
                if "." not in host:
                    warnings.append(f"source {sid} URL host 可疑: {host}")
            except Exception:
                pass

    for i, g in enumerate(D.get("same_source") or [], 1):
        tag = g.get("group") or f"group#{i}"
        if not g.get("group") or not g.get("relation"):
            errors.append(f"same_source {tag}: group/relation 必填")
        ents = g.get("entities") or []
        if not isinstance(ents, list) or len(ents) < 1:
            errors.append(f"same_source {tag}: entities 至少 1 个")
        if g.get("flag") in {"同源", "同集团", "纵向竞争"} and len(ents) < 2:
            warnings.append(f"same_source {tag}: flag={g.get('flag')} 但 entities 少于 2 个")

    for i, r in enumerate(D.get("risks") or [], 1):
        tag = f"risk#{i}"
        for k in ("company", "type", "fact", "impact"):
            if not str(r.get(k) or "").strip():
                errors.append(f"{tag} 缺少 {k}")
        sid = r.get("source_id")
        if sid and sid not in src_ids:
            errors.append(f"{tag} source_id 不存在: {sid}")
        if not sid and not (r.get("url") or r.get("source")):
            warnings.append(f"{tag} 没有 source_id / source / url")
        if r.get("status") not in RISK_STATES:
            warnings.append(f"{tag} status 建议用 已公开/待核实，当前 {r.get('status')!r}")
    if len(D.get("risks") or []) < 3:
        warnings.append("risks 少于 3 条，风险台账偏薄")

    for i, a in enumerate(D.get("actions") or [], 1):
        tag = f"action#{i}"
        for k in ("phase", "action", "detail", "owner", "output"):
            if not str(a.get(k) or "").strip():
                warnings.append(f"{tag} 缺少 {k}")
    if len(D.get("actions") or []) < 3:
        warnings.append("actions 少于 3 条，行动清单偏薄")

    # same-source independence warning
    flags = {g.get("group"): g for g in (D.get("same_source") or [])}
    for g in flags.values():
        names = set(g.get("entities") or [])
        hits = [c.get("name") for c in cands if c.get("name") in names]
        if len(hits) >= 2 and g.get("flag") in {"同源", "同集团"}:
            warnings.append(f"候选池内同组 {g.get('group')} 有 {len(hits)} 家（{', '.join(hits)}），同时入选不能算两个独立源")

    return errors, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    a = ap.parse_args()
    raw = common.load(a.data)
    D = common.normalize(raw)
    errors, warnings = check(D)
    for w in warnings:
        print("[WARN ]", w)
    for e in errors:
        print("[ERROR]", e)
    if errors:
        sys.exit(1)
    print(f"OK  data valid: {len(D['candidates'])} candidates / {len(D['spec_items'])} spec items / {len(D['sources'])} sources")


if __name__ == "__main__":
    main()
