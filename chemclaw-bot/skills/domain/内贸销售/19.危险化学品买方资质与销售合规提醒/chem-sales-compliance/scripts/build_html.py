# -*- coding: utf-8 -*-
"""把 case.json 渲染成自包含、可交互的 HTML 合规提醒卡。

用法:
    python build_html.py case.json out.html [--template templates/reminder.template.html]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from case_lib import load_case  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE.parent / "templates" / "reminder.template.html"


def render(case: dict, template_path: Path) -> str:
    tpl = template_path.read_text(encoding="utf-8")
    payload = json.dumps(case, ensure_ascii=False, indent=2)
    # 防止 JSON 中的 </script> 提前闭合脚本块
    payload = payload.replace("</", "<\\/")
    html = tpl.replace("/*__CASE__*/ null", payload)
    title = f"{case['meta']['title']} ｜ {case['meta']['case_no']}"
    html = html.replace("__TITLE__", title)
    return html


def build(case_path: str, out_path: str, template_path: str | None = None) -> Path:
    case = load_case(case_path)
    tpl = Path(template_path) if template_path else DEFAULT_TEMPLATE
    if not tpl.exists():
        raise SystemExit(f"模板不存在: {tpl}")
    html = render(case, tpl)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main(argv):
    if len(argv) < 3:
        print("用法: python build_html.py case.json out.html [template.html]")
        return 2
    out = build(argv[1], argv[2], argv[3] if len(argv) > 3 else None)
    print(f"OK  {out}  {out.stat().st_size/1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
