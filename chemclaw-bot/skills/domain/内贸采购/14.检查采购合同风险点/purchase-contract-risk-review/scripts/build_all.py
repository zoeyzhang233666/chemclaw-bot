"""一键流程：校验 -> 生成 HTML -> 生成 Excel（可选生成演示合同）。

用法:
    python scripts/build_all.py --dir <案例目录> [--docx] [--note "内部备注"]

不改写源数据；只产出 <案例目录>/合同风险审查-交互页面.html 与 .xlsx。
只要 validate_case 报错，立即退出，不产出任何交付物。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_review_html  # noqa: E402
import build_review_xlsx  # noqa: E402
from common import load_case, validate_case  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="合同审查一键构建")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--note", default="")
    ap.add_argument("--docx", action="store_true", help="同时由数据生成演示合同 DOCX（仅演示用）")
    a = ap.parse_args()
    case_dir = Path(a.dir)
    case = load_case(case_dir)
    report = validate_case(case["contract"], case["review"])
    print(json.dumps({"errors": report["errors"], "warnings": report["warnings"], "stats": {
        "findings": report["stats"]["total"], "kind": report["stats"]["kind"],
        "severity": report["stats"]["severity"], "uncovered": report["stats"]["uncovered"]}}, ensure_ascii=False, indent=1))
    if report["errors"]:
        print("校验失败，未生成交付物。", file=sys.stderr)
        return 1
    html = case_dir / "合同风险审查-交互页面.html"
    xlsx = case_dir / "合同风险审查-风险事项与问题清单.xlsx"
    build_review_html.build(case_dir, html, None, None, a.note)
    build_review_xlsx.build(case_dir, xlsx)
    print("已生成:", html.name, "/", xlsx.name)
    if a.docx:
        import build_contract_docx  # noqa: PLC0415

        docx = case_dir / "虚构演示合同.docx"
        build_contract_docx.build(case_dir, docx)
        print("已生成演示合同:", docx.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
