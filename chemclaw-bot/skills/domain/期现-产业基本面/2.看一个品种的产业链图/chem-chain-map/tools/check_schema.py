#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_schema.py — 用 assets/schemas/*.schema.json 校验 data 目录

优先用 jsonschema（若已安装）；否则退化为内置的最小校验（只查 required/type/enum）。

用法：
    python tools/check_schema.py --data-dir examples/sbs/data
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(os.path.dirname(HERE), "assets", "schemas")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

# 数据文件 → schema 文件
MAP = {
    "nodes.json": "nodes.schema.json",
    "relations.json": "relations.schema.json",
    "sources.json": "sources.schema.json",
    "core_checklist.json": "core_checklist.schema.json",
    "forbidden_links.json": "forbidden_links.schema.json",
    "processes.json": "processes.schema.json",
    "enterprises.json": "enterprises.schema.json",
    "projects.json": "projects-events.schema.json",
    "events.json": "projects-events.schema.json",
    "prices_verified.json": "price_series.schema.json",
    "price_series.json": "price_series.schema.json",
}

_TYPES = {
    "object": dict, "array": list, "string": str, "number": (int, float),
    "integer": int, "boolean": bool, "null": type(None),
}


def _type_ok(val, t):
    ts = t if isinstance(t, list) else [t]
    for one in ts:
        py = _TYPES.get(one)
        if py is None:
            continue
        if one == "integer" and isinstance(val, bool):
            continue
        if one in ("number", "integer") and isinstance(val, bool):
            continue
        if isinstance(val, py):
            return True
    return False


def mini_validate(val, schema, path="$", errs=None):
    """最小 JSON Schema 校验：type / required / enum / items / properties。"""
    if errs is None:
        errs = []
    if not isinstance(schema, dict):
        return errs
    t = schema.get("type")
    if t and not _type_ok(val, t):
        errs.append("%s: 期望类型 %s，实际 %s" % (path, t, type(val).__name__))
        return errs
    if "enum" in schema and val not in schema["enum"]:
        errs.append("%s: 值 %r 不在枚举 %s 内" % (path, val, schema["enum"]))
    if isinstance(val, dict):
        for req in schema.get("required", []):
            if req not in val:
                errs.append("%s: 缺少必填字段 %r" % (path, req))
        props = schema.get("properties") or {}
        for k, v in val.items():
            if k in props:
                mini_validate(v, props[k], path + "." + k, errs)
    if isinstance(val, list) and "items" in schema:
        for i, it in enumerate(val):
            mini_validate(it, schema["items"], "%s[%d]" % (path, i), errs)
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    try:
        from jsonschema import Draft202012Validator  # noqa: F401
        have_js = True
    except Exception:  # noqa: BLE001
        have_js = False

    total_err = 0
    checked = 0
    for fname, sname in MAP.items():
        fpath = os.path.join(args.data_dir, fname)
        if not os.path.exists(fpath):
            continue
        spath = os.path.join(SCHEMA_DIR, sname)
        if not os.path.exists(spath):
            continue
        inst = json.load(open(fpath, encoding="utf-8"))
        schema = json.load(open(spath, encoding="utf-8"))
        checked += 1
        if have_js:
            from jsonschema import Draft202012Validator
            v = Draft202012Validator(schema)
            errs = ["%s: %s" % ("/".join(str(p) for p in e.path), e.message)
                    for e in sorted(v.iter_errors(inst), key=lambda x: list(x.path))]
        else:
            errs = mini_validate(inst, schema)
        if errs:
            total_err += len(errs)
            print("\n[%s] %d 处不符合 %s" % (fname, len(errs), sname))
            for e in errs[:12]:
                print("   -", e)
        elif not args.quiet:
            print("[OK] %-24s ← %s" % (fname, sname))

    mode = "jsonschema" if have_js else "内置最小校验"
    print("\n校验文件 %d 个，问题 %d 处（%s）" % (checked, total_err, mode))
    if not have_js:
        print("提示：pip install jsonschema 可获得完整校验（含 allOf/if-then 等）")
    return 0 if total_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
