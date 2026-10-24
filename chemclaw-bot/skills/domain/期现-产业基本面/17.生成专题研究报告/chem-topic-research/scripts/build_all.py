# -*- coding: utf-8 -*-
"""
build_all.py —— 一条命令产出全部交付物。

    python build_all.py <case.json> [--outdir <目录>] [--audiences 管理层,产业研究员]

产出（全部同名不同后缀，便于归档）：
    <title>_<受众>.html              交互式报告
    <title>_<受众>_数据底稿.xlsx      13 页 Excel
    <title>_<受众>_研究提纲_已确认.md  已确认提纲
    <title>_<受众>_执行记录.md        执行记录
    <title>_<受众>_报告全文.md        纯文字稿
    build_report.json                本次构建的清单与自检结果

受众既可传键（management / industry-researcher …），也可传中文（管理层 / 产业研究员 …）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import build_html  # noqa: E402
import build_md  # noqa: E402
import build_xlsx  # noqa: E402

ALIASES = {
    "管理层": "management", "销售": "sales", "采购": "procurement",
    "研发": "rnd", "产业研究员": "industry-researcher", "研究员": "industry-researcher",
    "management": "management", "sales": "sales", "procurement": "procurement",
    "rnd": "rnd", "industry-researcher": "industry-researcher",
}


def resolve_audience(token):
    if not token:
        return None
    key = ALIASES.get(token.strip())
    if not key:
        raise SystemExit("未知受众 %r，可用：%s" % (token, "、".join(sorted(set(ALIASES)))) )
    return key


def build_one(case, audience, outdir):
    prof = C.audience_profile(case, audience)
    label = prof.get("label") or prof.get("audience_key")
    base = C.default_filename(case, prof["audience_key"], "")
    paths = {}

    html, payload, errs, warns = build_html.build(case, prof["audience_key"])
    if errs:
        raise SystemExit("case.json 校验失败：" + "；".join(errs))
    paths["html"] = build_html.write(html, os.path.join(outdir, base + ".html"))

    _, checks = build_xlsx.build(case, os.path.join(outdir, base + "_数据底稿.xlsx"))
    paths["xlsx"] = os.path.join(outdir, base + "_数据底稿.xlsx")

    with open(os.path.join(outdir, base + "_研究提纲_已确认.md"), "w", encoding="utf-8") as f:
        f.write(build_md.build_outline(case, "confirmed", prof["audience_key"]))
    paths["outline"] = os.path.join(outdir, base + "_研究提纲_已确认.md")

    with open(os.path.join(outdir, base + "_执行记录.md"), "w", encoding="utf-8") as f:
        f.write(build_md.build_record(case, prof["audience_key"]))
    paths["record"] = os.path.join(outdir, base + "_执行记录.md")

    with open(os.path.join(outdir, base + "_报告全文.md"), "w", encoding="utf-8") as f:
        f.write(build_md.build_report(case, prof["audience_key"]))
    paths["report_md"] = os.path.join(outdir, base + "_报告全文.md")

    return {
        "audience": prof["audience_key"],
        "audience_label": label,
        "files": paths,
        "stats": {
            "sections": len(payload["sections"]),
            "conclusions": len(payload["conclusions"]),
            "calculations": len(payload["calculations"]),
            "sources": len(payload["sources"]),
            "gaps": len(payload["gaps"]),
            "charts": sum(1 for s in payload["sections"] for b in s["blocks"] if b.get("type") == "chart"),
        },
        "checks_passed": sum(1 for c in checks if c[1]),
        "checks_failed": [{"check": c[0], "detail": c[2]} for c in checks if not c[1]],
        "warnings": warns,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="一键生成全部交付物")
    ap.add_argument("case")
    ap.add_argument("--outdir", default="")
    ap.add_argument("--audiences", default="", help="逗号分隔，如 管理层,产业研究员；默认用 case 中的受众")
    a = ap.parse_args(argv)

    case = C.load(a.case)
    meta = case.get("meta") or {}
    outdir = a.outdir or os.path.join(os.path.dirname(os.path.abspath(a.case)), "交付物")
    C.ensure_dir(outdir)

    tokens = [t for t in (a.audiences or "").split(",") if t.strip()]
    if not tokens:
        tokens = [None]
    results = []
    for t in tokens:
        aud = resolve_audience(t) if t else None
        r = build_one(case, aud, outdir)
        results.append(r)
        print("— %s —" % r["audience_label"])
        for k, v in r["files"].items():
            print("   %-6s %s" % (k, os.path.basename(v)))
        s = r["stats"]
        print("   章节 %d · 结论 %d · 计算 %d · 来源 %d · 缺口 %d · 图表 %d · 自检 %d 项通过"
              % (s["sections"], s["conclusions"], s["calculations"], s["sources"], s["gaps"],
                 s["charts"], r["checks_passed"]))
        if r["checks_failed"]:
            for f in r["checks_failed"]:
                print("   !! 自检未通过：%s（%s）" % (f["check"], f["detail"]))
        if r["warnings"]:
            for w in r["warnings"]:
                print("   ⚠ ", w)

    manifest = {
        "generator": "chem-topic-research/1.0",
        "case_file": os.path.abspath(a.case),
        "schema": case.get("schema"),
        "title": meta.get("title"),
        "report_date": meta.get("report_date"),
        "data_cutoff": meta.get("data_cutoff"),
        "outdir": os.path.abspath(outdir),
        "builds": results,
    }
    mpath = os.path.join(outdir, "build_report.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("\n清单 ->", mpath)
    failed = [r for r in results if r["checks_failed"]]
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
