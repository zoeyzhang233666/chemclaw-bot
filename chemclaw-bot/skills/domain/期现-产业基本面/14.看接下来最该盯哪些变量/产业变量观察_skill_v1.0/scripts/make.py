# -*- coding: utf-8 -*-
"""
一键构建：数据源(payload) → HTML 看板 + Excel 工作簿 → 契约校验。

用法：
    # 构建自带甲醇案例（默认）
    python scripts/make.py

    # 构建自己的品种
    python scripts/make.py --payload my_case.py --html out/index.html --xlsx out/观察表.xlsx

产物两个文件由同一份 payload 生成，数字天然一致；改数据只改 payload 后重新生成。
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import contract  # noqa: E402
import render_excel  # noqa: E402
import render_html  # noqa: E402

# 默认案例：examples/示例-甲醇-2026Q4/payload_甲醇.py
DEFAULT_CASE_DIR = SKILL_ROOT / "examples" / "示例-甲醇-2026Q4"
DEFAULT_PAYLOAD = DEFAULT_CASE_DIR / "payload_甲醇.py"


def load_payload(module_path: Path) -> dict:
    if not module_path.exists():
        raise SystemExit(f"找不到 payload 文件：{module_path}")
    # 让 payload 能 import 同目录的辅助模块
    sys.path.insert(0, str(module_path.parent))
    spec = importlib.util.spec_from_file_location("payload_mod", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    if hasattr(mod, "PAYLOAD"):
        return mod.PAYLOAD
    if hasattr(mod, "build_payload"):
        return mod.build_payload()
    raise SystemExit(f"{module_path} 未暴露 PAYLOAD 或 build_payload()")


def main() -> int:
    ap = argparse.ArgumentParser(description="产业变量观察：一键生成 HTML 看板 + Excel 工作簿")
    ap.add_argument("--payload", default=str(DEFAULT_PAYLOAD), help="数据源 .py 文件")
    ap.add_argument("--html", default=None, help="输出 HTML 路径")
    ap.add_argument("--xlsx", default=None, help="输出 Excel 路径")
    args = ap.parse_args()

    payload_path = Path(args.payload)
    payload = load_payload(payload_path)

    problems = contract.validate(payload)
    if problems:
        print("✗ 契约校验未通过：")
        for p in problems:
            print("   -", p)
        return 1
    print("✓ 契约校验通过：变量 %d 个 / 事件 %d 个 / 快照 %d 行 / 缺口 %d 项"
          % (len(payload["variables"]), len(payload["events"]),
             len(payload["snapshot"]), len(payload["gaps"])))

    out_dir = Path(args.html).parent if args.html else (payload_path.parent)
    out_dir.mkdir(parents=True, exist_ok=True)

    html_path = Path(args.html) if args.html else out_dir / "index.html"
    xlsx_path = Path(args.xlsx) if args.xlsx else out_dir / "变量观察工作簿.xlsx"

    html = render_html.render(payload, validate_first=False)
    html_path.write_text(html, encoding="utf-8")
    print(f"✓ HTML  {html_path}  ({html_path.stat().st_size/1024:.1f} KB)")

    render_excel.build(payload, str(xlsx_path), validate_first=False)
    print(f"✓ Excel {xlsx_path}  ({xlsx_path.stat().st_size/1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
