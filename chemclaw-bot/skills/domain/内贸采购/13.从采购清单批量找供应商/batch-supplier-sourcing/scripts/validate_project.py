# -*- coding: utf-8 -*-
"""项目级校验：结构、引用完整性、证据规则、覆盖度口径。

用法: python scripts/validate_project.py examples/northeast-china-batch/project.json
退出码 0 = 通过；1 = 有 ERROR；WARN 不影响退出码但应逐条处理。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_common  # noqa: E402
import lib_model  # noqa: E402

CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
GRADES = set("AaBCDEF")
IDENTITY = {"S", "P", "G", "T", "I", "U"}
COVERAGE = {"direct", "partial_spec", "disclose", "not_listed", "dist_only", "none"}
DEGREE = {"independent", "confirmable", "conditional", "co_list_only", "not_covered", "not_recommended"}


class Checker:
    def __init__(self):
        self.errors = []
        self.warns = []
        self.infos = []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warns.append(msg)

    def info(self, msg):
        self.infos.append(msg)


def validate(project):
    c = Checker()
    # ---------- 必填
    for k in ("meta", "list", "items", "suppliers", "evidence", "links"):
        if k not in project:
            c.err(f"缺少顶层字段: {k}")
    if c.errors:
        return c
    items = project["items"]
    if not items:
        c.err("items 为空")
    codes = [i["code"] for i in items]
    if len(codes) != len(set(codes)):
        c.err("items.code 有重复")
    sup_ids = [s["id"] for s in project["suppliers"]]
    if len(sup_ids) != len(set(sup_ids)):
        c.err("suppliers.id 有重复")
    ev_ids = [e["id"] for e in project["evidence"]]
    if len(ev_ids) != len(set(ev_ids)):
        c.err("evidence.id 有重复")
    ev_map = {e["id"]: e for e in project["evidence"]}

    # ---------- 物料
    for it in items:
        if not it.get("name") and it.get("status") != "unrecognized":
            c.err(f"{it['code']} 名称为空")
        if it.get("cas") and not CAS_RE.match(it["cas"]):
            c.err(f"{it['code']} CAS 格式非法: {it['cas']}")
        if it.get("status") not in {"ok", "ambiguous", "unrecognized", "conflict", "blocked"}:
            c.err(f"{it['code']} status 非法: {it.get('status')}")
        if it.get("status") != "ok" and not any(a.get("code") == it["code"] for a in project.get("ambiguities", [])):
            c.warn(f"{it['code']} 状态为 {it['status']} 但没有对应的待确认事项")
    for a in project.get("ambiguities", []):
        if a.get("code") not in codes:
            c.err(f"歧义项引用了不存在的物料: {a.get('code')}")
        if not a.get("question"):
            c.err(f"歧义项 {a.get('id')} 没有提问")

    # ---------- 企业
    for s in project["suppliers"]:
        if s["identity"] not in IDENTITY:
            c.err(f"企业 {s['id']} identity 非法")
        evs = [ev_map.get(e) for e in s.get("evidence_ids", [])]
        evs = [e for e in evs if e]
        if s["identity"] in ("S", "P") and not evs:
            c.err(f"厂家 {s['name']} 没有任何证据（不允许无证厂家）")
        if evs and s["identity"] != "U" and all(e["grade"] in ("D", "E") for e in evs):
            c.warn(f"{s['name']} 仅有 D/E 级证据，应重新判定为 U/待核实")
        if s["identity"] == "U" and any(ev_map.get(e, {}).get("grade") in ("A", "a", "B") for e in s.get("evidence_ids", [])):
            c.warn(f"{s['name']} 有 A/a/B 级证据但身份标为 U，请复核")

    # ---------- 证据
    for e in project["evidence"]:
        if e.get("grade") not in GRADES:
            c.err(f"证据 {e['id']} grade 非法")
        if not e.get("url"):
            if e.get("grade") != "D":
                c.warn(f"证据 {e['id']} 无 URL，只能作 D 级线索")
        elif not e["url"].startswith(("http://", "https://")):
            c.err(f"证据 {e['id']} URL 非法")
        if not e.get("quote"):
            c.warn(f"证据 {e['id']} 没有原文引用 quote")
        for code in e.get("items", []):
            if code not in codes:
                c.err(f"证据 {e['id']} 引用了不存在的物料 {code}")
        if e.get("date") and not re.match(r"^\d{4}", str(e["date"])):
            c.warn(f"证据 {e['id']} 日期格式应为 YYYY-MM-DD")

    # ---------- 关联
    for ln in project["links"]:
        if ln["item_code"] not in codes:
            c.err(f"关联引用了不存在的物料 {ln['item_code']}")
        if ln["supplier_id"] not in sup_ids:
            c.err(f"关联引用了不存在的企业 {ln['supplier_id']}")
        if ln.get("identity") not in IDENTITY:
            c.err(f"关联 {ln['item_code']}-{ln['supplier_id']} identity 非法")
        if ln.get("coverage") not in COVERAGE:
            c.err(f"关联 {ln['item_code']}-{ln['supplier_id']} coverage 非法")
        if ln.get("degree") not in DEGREE:
            c.err(f"关联 {ln['item_code']}-{ln['supplier_id']} degree 非法")
        if ln.get("coverage") == "direct" and ln.get("confidence") != "已证实":
            c.warn(f"关联 {ln['item_code']}-{ln['supplier_id']} 标为 direct 但置信度不是“已证实”")
        s = next((x for x in project["suppliers"] if x["id"] == ln["supplier_id"]), None)
        if s and ln.get("identity") == "S" and s["identity"] == "U" and ln.get("degree") != "not_recommended":
            c.err(f"关联 {ln['item_code']}-{ln['supplier_id']} 把 U 级主体（未证实）当作厂家")
    # 每个厂家-物料 direct 关系至少要有一条证据
    ev_index = {}
    for e in project["evidence"]:
        for code in e.get("items", []):
            ev_index.setdefault((code, e["org"]), []).append(e)
    for ln in project["links"]:
        if ln.get("coverage") in ("direct", "partial_spec", "disclose") and ln.get("identity") == "S":
            s = next(x for x in project["suppliers"] if x["id"] == ln["supplier_id"])
            sup_ev = {e: ev_map[e] for e in s.get("evidence_ids", []) if e in ev_map}
            if not sup_ev:
                c.err(f"{s['short']} 在物料 {ln['item_code']} 上被标为厂家但没有任何证据")
                continue
            hit = [(eid, e) for eid, e in sup_ev.items() if ln["item_code"] in e.get("items", [])]
            if not hit:
                c.warn(f"关联 {ln['item_code']}-{s['short']} 的企业证据没有命中该物料，"
                       f"请在该企业某条证据的 items 里补 {ln['item_code']}（跨品种推断须在证据中注明）")

    # ---------- 覆盖口径
    if "_calc" in project:
        for code, r in project["_calc"]["item_side"].items():
            if r["degree_adv"] > r["degree_current"]:
                c.err(f"{code} 厂家可达度 > 覆盖度")
        for s in project["_calc"]["supplier_rank"]:
            if s["adv_current"] > s["current"]:
                c.err(f"{s['supplier_id']} 厂家度 > 覆盖度")
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--strict", action="store_true", help="WARN 也算失败")
    args = ap.parse_args()
    project, _ = lib_model.load_project(args.project)
    c = validate(project)
    for m in c.errors:
        print("ERROR  ", m)
    for m in c.warns:
        print("WARN   ", m)
    for m in c.infos:
        print("INFO   ", m)
    print(f"\n结果: {len(c.errors)} ERROR / {len(c.warns)} WARN / {len(c.infos)} INFO")
    calc = project.get("_calc", {})
    if calc:
        print(f"物料 {len(project['items'])} | 企业 {len(project['suppliers'])} | 证据 {len(project['evidence'])} | 关联 {len(project['links'])}")
        print(f"多物料覆盖企业 {len(calc['multi'])} | 稀缺物料 {len(calc['scarce'])}")
    ok = not c.errors and (not args.strict or not c.warns)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
