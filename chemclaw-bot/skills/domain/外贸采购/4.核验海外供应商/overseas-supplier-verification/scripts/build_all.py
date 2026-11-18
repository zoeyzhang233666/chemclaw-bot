# -*- coding: utf-8 -*-
"""
build_all.py — one command: validate → html → xlsx (+ manifest).

    python scripts/build_all.py project.json -o out/
    python scripts/build_all.py project.json -o out/ --strict
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ovslib as L  # noqa: E402

VERSION = "1.0.0"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None):
    L.force_utf8()
    ap = argparse.ArgumentParser(description="Validate and render both artefacts.")
    ap.add_argument("project")
    ap.add_argument("-o", "--outdir", default="out")
    ap.add_argument("-n", "--name", default=None)
    ap.add_argument("--strict", action="store_true", help="warnings become failures")
    ap.add_argument("--skip-validate", action="store_true")
    ap.add_argument("--no-xlsx", action="store_true")
    args = ap.parse_args(argv)

    project = L.load_project(args.project)
    meta = project.setdefault("meta", {})
    meta.setdefault("build", {})
    meta["build"]["tool"] = f"overseas-supplier-verification v{VERSION}"
    meta["build"]["input_sha256"] = sha256(args.project).upper()

    if not args.skip_validate:
        import validate
        rc = validate.main([args.project] + (["--strict"] if args.strict else []))
        if rc != 0:
            print("\n[abort] 校验未通过，未生成文件。修复后重跑，或用 --skip-validate 强制生成（不推荐）。")
            return rc

    os.makedirs(args.outdir, exist_ok=True)
    import build_html
    build_html.main([args.project, "-o", args.outdir] + (["-n", args.name] if args.name else []))

    produced = []
    if not args.no_xlsx:
        try:
            import build_xlsx
            build_xlsx.main([args.project, "-o", args.outdir] + (["-n", args.name] if args.name else []))
            produced.append("xlsx")
        except SystemExit as exc:
            print(f"[warn] xlsx 跳过：{exc}")
        except Exception as exc:  # pragma: no cover
            print(f"[warn] xlsx 生成失败：{exc}")
    produced.append("html")

    counts = L.collect_all_states(project)
    print(f"\n结论分布：已核实 {counts['verified']}｜存在疑点 {counts['doubt']}｜"
          f"未核实 {counts['unverified']}｜未知 {counts['unknown']}｜不适用 {counts['na']}")
    print(f"证据 {len(L.as_list(project.get('evidence')))} 条｜"
          f"缺口 {len(L.as_list(project.get('gaps')))} 项｜"
          f"询证 {len(L.as_list((project.get('rfi') or {}).get('clauses')))} 条")
    print(f"[done] 产物：{', '.join(produced)} → {os.path.abspath(args.outdir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
