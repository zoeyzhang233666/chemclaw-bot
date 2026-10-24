#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Schema + logic checks for one data.json.

Usage:
  python validate.py data.json
Exit code 1 when errors exist; warnings do not block the build.
"""
from __future__ import annotations

import json
import sys

import common


def _ids(items, label, errors):
    seen = set()
    for i, x in enumerate(items):
        xid = x.get("id")
        if not xid:
            errors.append(f"{label}[{i}] 缺少 id")
        elif xid in seen:
            errors.append(f"{label} id 重复: {xid}")
        seen.add(xid)
    return seen


def check(D):
    errors, warnings = [], []
    meta = D.get("meta") or {}
    for key in ("product", "region", "province", "city", "asof", "target_lon", "target_lat"):
        if meta.get(key) in (None, ""):
            errors.append(f"meta.{key} 必填")
    if not D.get("companies"):
        errors.append("companies 不能为空")
    if not D.get("plants"):
        errors.append("plants 不能为空")
    if not D.get("sources"):
        errors.append("sources 不能为空（每条产能至少能回到一个来源）")
    if not D.get("conflicts"):
        warnings.append("conflicts 为空：至少记录 1 条口径冲突或明确写“未发现冲突”")
    if not D.get("gaps"):
        warnings.append("gaps 为空：缺少数据缺口章节，报告容易显得“什么都查到了”")

    prov_names = {p.get("province") for p in D.get("plants") or []}
    if meta.get("province") and meta.get("province") not in prov_names:
        warnings.append(f"meta.province={meta.get('province')} 未出现在任何工厂的 province 中；检查省市命名是否一致（如“广东省” vs “广东”）")
    comp_ids = _ids(D.get("companies") or [], "companies", errors)
    plant_ids = _ids(D.get("plants") or [], "plants", errors)
    _ids(D.get("projects") or [], "projects", errors)
    _ids(D.get("prospects") or [], "prospects", errors)
    src_ids = _ids(D.get("sources") or [], "sources", errors)
    for src in D.get("sources") or []:
        if not src.get("url"):
            warnings.append(f"来源 {src.get('id')} 缺少 url；HTML/Excel 将无法点击")
        if not src.get("title") or not src.get("org"):
            warnings.append(f"来源 {src.get('id')} 缺少 org/title")

    for p in D.get("plants") or []:
        if not p.get("name"):
            errors.append(f"工厂 {p.get('id')} 缺少 name")
        if p.get("company_id") not in comp_ids:
            errors.append(f"工厂 {p.get('id')} 的 company_id 不存在: {p.get('company_id')}")
        if p.get("capacity") is None or p["capacity"] <= 0:
            errors.append(f"工厂 {p.get('id')} 产能必须 > 0")
        if not p.get("source_ids"):
            errors.append(f"工厂 {p.get('id')} 至少需要 1 个来源")
        if p.get("lon") is None or p.get("lat") is None:
            errors.append(f"工厂 {p.get('id')} 缺少经纬度")
        for sid in p.get("source_ids") or []:
            if sid not in src_ids:
                errors.append(f"工厂 {p.get('id')} 引用不存在的来源 {sid}")
    for c in D.get("companies") or []:
        if not c.get("name"):
            errors.append(f"企业 {c.get('id')} 缺少 name")
        if c.get("capacity") is None or c["capacity"] <= 0:
            errors.append(f"企业 {c.get('id')} 产能必须 > 0")
        if not c.get("source_ids"):
            errors.append(f"企业 {c.get('id')} 至少需要 1 个来源")
        if c.get("plant_count") and c["plant_count"] != len(c.get("plants") or []):
            errors.append(f"企业 {c.get('id')} plant_count 与 plants 数不一致")
        for sid in c.get("source_ids") or []:
            if sid not in src_ids:
                errors.append(f"企业 {c.get('id')} 引用不存在的来源 {sid}")
        if c.get("output") is not None and c.get("capacity"):
            util = c["output"] / c["capacity"]
            if util > 1.35:
                warnings.append(f"企业 {c.get('short') or c.get('id')} 产量/产能={util:.0%}，需确认是否含贸易/代工/口径差异")
    for pr in D.get("projects") or []:
        if not pr.get("name"):
            errors.append(f"项目 {pr.get('id')} 缺少 name")
        if pr.get("company_id") not in comp_ids:
            errors.append(f"项目 {pr.get('id')} 的 company_id 不存在: {pr.get('company_id')}")
        if pr.get("capacity") is None or pr["capacity"] <= 0:
            errors.append(f"项目 {pr.get('id')} capacity 必须 > 0")
        if not pr.get("source_ids"):
            errors.append(f"项目 {pr.get('id')} 至少需要 1 个来源")
        if pr.get("year") and not (2000 <= int(pr["year"]) <= 2100):
            errors.append(f"项目 {pr.get('id')} year 不合理: {pr['year']}")
        for sid in pr.get("source_ids") or []:
            if sid not in src_ids:
                errors.append(f"项目 {pr.get('id')} 引用不存在的来源 {sid}")
    for cu in D.get("prospects") or []:
        if not cu.get("source_ids"):
            errors.append(f"潜客 {cu.get('id')} 至少需要 1 个来源")
        if not cu.get("name"):
            errors.append(f"潜客 {cu.get('id')} 缺少 name")
        for sid in cu.get("source_ids") or []:
            if sid not in src_ids:
                errors.append(f"潜客 {cu.get('id')} 引用不存在的来源 {sid}")

    # Arithmetic: recompute from plants and compare with the normalized totals.
    plants = D.get("plants") or []
    companies = D.get("companies") or []
    cap_from_plants = round(sum(p["capacity"] for p in plants), 2)
    cap_from_companies = round(sum(c["capacity"] for c in companies), 2)
    if abs(cap_from_plants - cap_from_companies) > 0.51:
        errors.append(f"企业产能合计 {cap_from_companies} ≠ 工厂产能合计 {cap_from_plants}")
    if D.get("total_cap") is not None and abs(D["total_cap"] - cap_from_companies) > 0.51:
        errors.append(f"total_cap {D['total_cap']} ≠ 企业合计 {cap_from_companies}")
    bands = D.get("bands") or []
    if bands and abs(sum(b["capacity"] for b in bands) - cap_from_plants) > 0.51:
        errors.append("bands 合计 ≠ 工厂产能合计")

    # Narrative sanity: no unsupported share claim.
    text = json.dumps(D.get("narrative") or {}, ensure_ascii=False)
    if "市场份额" in text and "不" not in text:
        warnings.append("narrative 出现“市场份额”，但未见否定/限定语；请改成样本覆盖/样本内占比")
    if "全国" in text and "样本" not in text:
        warnings.append("narrative 出现“全国”，建议同时写“样本”或“公开口径”，避免把样本当全行业")
    if D.get("total_cap") and D.get("meta", {}).get("coverage"):
        cov = D["meta"]["coverage"]
        lo, hi = cov.get("industry_low"), cov.get("industry_high")
        if lo and hi and hi >= lo:
            ratio = D["total_cap"] / hi
            if ratio > 1.05:
                warnings.append("样本产能大于全国口径上限；请检查 coverage 或样本口径")

    return errors, warnings


def main():
    if len(sys.argv) != 2:
        raise SystemExit("用法: python validate.py data.json")
    raw = common.load_raw(sys.argv[1])
    D = common.build(raw)
    E, W = check(D)
    for x in E:
        print("[ERROR]", x)
    for x in W:
        print("[WARN ]", x)
    print(f"companies={D['total_companies']} plants={D['total_plants']} cap={D['total_cap']} output={D['total_out']}")
    if E:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
