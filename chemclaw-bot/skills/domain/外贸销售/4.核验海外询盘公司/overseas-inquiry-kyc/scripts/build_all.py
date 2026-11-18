#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键：校验 → 生成 HTML + Excel → 结构自检 → 写 build_report.json

用法:
    python build_all.py inquiry.json outdir [--name 前缀]

产出:
    outdir/{name}_核验报告.html
    outdir/{name}_核验工作簿.xlsx
    outdir/build_report.json
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import traceback

import _common as C

if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def slugify(s):
    return "".join(ch for ch in str(s) if ch not in '\\/:*?"<>|').strip() or "inquiry"


def main():
    ap = argparse.ArgumentParser(description="生成核验报告 HTML + Excel")
    ap.add_argument("data")
    ap.add_argument("outdir")
    ap.add_argument("--name", default="", help="文件名前缀，默认取 meta.client_slug")
    ap.add_argument("--skip-validate", action="store_true")
    a = ap.parse_args()

    report = {"input": os.path.abspath(a.data), "outdir": os.path.abspath(a.outdir), "warnings": [], "steps": []}

    # 1 校验
    import validate
    errors, warns, infos, D = validate.run(a.data, strict=False)
    report["validate"] = {"errors": errors, "warnings": warns, "infos": infos}
    report["steps"].append({"step": "validate", "ok": not errors})
    for e in errors:
        print(f"[ERROR] {e}")
    for w in warns:
        print(f"[warn]  {w}")
    if errors and not a.skip_validate:
        print("\n数据校验未通过，已停止。修好 inquiry.json 后重跑（或 --skip-validate 强制生成）。")
        return 1

    D = C.normalize(C.load_json(a.data))
    name = slugify(a.name or D["meta"].get("client_slug") or "inquiry")
    os.makedirs(a.outdir, exist_ok=True)
    html_path = os.path.join(a.outdir, f"{name}_核验报告.html")
    xlsx_path = os.path.join(a.outdir, f"{name}_核验工作簿.xlsx")

    # 2 HTML
    import build_html
    build_html.build(a.data, html_path, os.path.basename(xlsx_path))
    report["steps"].append({"step": "html", "ok": True, "path": html_path,
                            "bytes": os.path.getsize(html_path), "sha256": C.sha256_file(html_path)})
    print(f"[ok] HTML  {html_path}  {os.path.getsize(html_path) / 1024:.1f} KB")

    # 3 Excel
    import build_xlsx
    build_xlsx.build(a.data, xlsx_path)
    report["steps"].append({"step": "xlsx", "ok": True, "path": xlsx_path,
                            "bytes": os.path.getsize(xlsx_path), "sha256": C.sha256_file(xlsx_path)})
    print(f"[ok] XLSX  {xlsx_path}  {os.path.getsize(xlsx_path) / 1024:.1f} KB")

    # 4 结构自检（Excel 必跑；HTML 渲染检查只在装了 playwright 时跑）
    try:
        import check_xlsx
        ex, ew, _notes, wb = check_xlsx.run(xlsx_path)
        report["check_xlsx"] = {"errors": ex, "warnings": ew, "sheets": len(wb.sheetnames)}
        report["steps"].append({"step": "check_xlsx", "ok": not ex})
        for e in ex:
            print(f"[xlsx ERROR] {e}")
        for w in ew:
            print(f"[xlsx warn]  {w}")
        print(f"[ok] XLSX 结构自检：{len(wb.sheetnames)} 表，{len(ex)} error / {len(ew)} warning")
    except Exception as e:  # 自检失败不阻断交付，但必须记录
        report["warnings"].append(f"check_xlsx 未执行：{e}")
        print(f"[warn] XLSX 结构自检失败：{e}")

    if os.environ.get("KYC_RENDER_QA") == "1":
        try:
            import check_render  # noqa: F401  (以子进程方式调用更稳)
            import subprocess
            rc = subprocess.call([sys.executable, os.path.join(HERE, "check_render.py"), html_path])
            report["steps"].append({"step": "check_render", "ok": rc == 0})
        except Exception as e:
            report["warnings"].append(f"check_render 未执行：{e}")

    report["summary"] = {
        "checks": D["stats"]["checks_total"],
        "verified": D["stats"]["status"]["verified"],
        "discrepancy": D["stats"]["status"]["discrepancy"],
        "unverified": D["stats"]["status"]["unverified"],
        "sources": D["stats"]["sources"],
        "requests": len(D["requests"]),
        "verdict": D["stats"]["verdict_line"],
    }
    rep_path = os.path.join(a.outdir, "build_report.json")
    C.write_text(rep_path, json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[ok] 回执 {rep_path}")
    fail = [s for s in report["steps"] if not s["ok"]]
    if fail:
        print(f"\n注意：{len(fail)} 个步骤未通过：{[s['step'] for s in fail]}")
        return 1
    print(f"\n完成：{report['summary']['checks']} 项核验（已核实 {report['summary']['verified']} / "
          f"疑点 {report['summary']['discrepancy']} / 未核实 {report['summary']['unverified']}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
