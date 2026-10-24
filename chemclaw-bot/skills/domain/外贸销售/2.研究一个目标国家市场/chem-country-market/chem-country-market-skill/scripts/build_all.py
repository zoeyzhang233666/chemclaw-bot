"""
build_all.py — 一条命令跑完整流水线：校验 → HTML → Excel → 静态检查 →（可选）浏览器渲染。

  python build_all.py case.json
  python build_all.py case.json --outdir out --render
  python build_all.py case.json --strict          # 有任何 warning 也判失败

产物：out/<国家>-<产品>_国别市场研究.html / .xlsx / data.json / qa/

设计：任何一步失败都立即停下并打印原因；不做“部分成功也交付”。
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import build_html  # noqa: E402
import build_xlsx  # noqa: E402


def run(cmd, label):
    print("\n$ %s" % " ".join('"%s"' % c if " " in str(c) else str(c) for c in cmd))
    r = subprocess.run([sys.executable] + [str(c) for c in cmd], text=True,
                       encoding="utf-8", errors="replace", capture_output=True)
    out = (r.stdout or "") + (r.stderr or "")
    print(out.strip()[-4000:])
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--outdir", default="")
    ap.add_argument("--render", action="store_true", help="额外跑一遍真浏览器渲染校验")
    ap.add_argument("--strict", action="store_true", help="有 warning 即失败")
    ap.add_argument("--skip-xlsx", action="store_true")
    a = ap.parse_args()

    case_path = os.path.abspath(a.case)
    case = C.load_json(case_path)
    outdir = a.outdir or os.path.join(os.path.dirname(case_path), "out")
    os.makedirs(outdir, exist_ok=True)
    name = build_html.default_name(case)
    stem = os.path.splitext(name)[0]
    html_path = os.path.join(outdir, name)
    data_path = os.path.join(outdir, "data.json")
    xlsx_path = os.path.join(outdir, stem + ".xlsx")

    print("=" * 62)
    print("国别市场研究流水线：%s" % case["meta"]["title"])
    print("=" * 62)

    # 1 validate
    errs, warns = C.validate_case(case)
    print("\n[1/5] 校验 case.json")
    for w in warns:
        print("  WARN ", w)
    for e in errs:
        print("  ERROR", e)
    if errs:
        print("\n校验失败：共 %d 个 error，已停止（不生成半成品）" % len(errs))
        return 1
    if warns and a.strict:
        print("\n--strict：存在 %d 个 warning，已停止" % len(warns))
        return 1
    print("  通过（error 0 / warning %d）" % len(warns))

    # 2/3 build
    print("\n[2/5] 生成 HTML")
    html, data = build_html.build_html(case)
    build_html.write(html, html_path)
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("  → %s（%.2f MB）" % (html_path, len(html.encode()) / 1048576.0))
    print("  → %s" % data_path)

    if not a.skip_xlsx:
        print("\n[3/5] 生成 Excel")
        out, n = build_xlsx.build(case, xlsx_path)
        print("  → %s（%d 个工作表）" % (out, n))
    else:
        print("\n[3/5] 跳过 Excel")

    # 4 static checks
    print("\n[4/5] 静态检查")
    ok_html = run([os.path.join(HERE, "check_html.py"), html_path], "check_html")
    ok_xlsx = True if a.skip_xlsx else run([os.path.join(HERE, "check_xlsx.py"), xlsx_path], "check_xlsx")

    # 5 optional browser
    ok_render = True
    if a.render:
        print("\n[5/5] 浏览器渲染校验")
        r = subprocess.run([sys.executable, os.path.join(HERE, "qa_render.py"), html_path,
                            "--outdir", os.path.join(outdir, "qa")],
                           text=True, encoding="utf-8", errors="replace", capture_output=True)
        try:
            res = json.loads(r.stdout)
            probe = res.get("probe") or {}
            charts = probe.get("charts", [])
            blank = [c["id"] for c in charts if not c.get("hasCanvas") or c.get("ink") in (0, None)]
            print("  图表 %d 个，空白 %s；JS 报错 %s；溢出 %s；占位泄漏 %s" % (
                len(charts), blank or "无", res.get("errors") or "无",
                probe.get("overflowing") or "无", probe.get("placeholderLeaks") or "无"))
            ok_render = bool(charts) and not blank and not res.get("errors") and not probe.get("overflowing") \
                and not probe.get("placeholderLeaks")
        except Exception:  # noqa: BLE001
            print(r.stdout[-1500:] or r.stderr[-1500:])
            ok_render = False
    else:
        print("\n[5/5] 跳过浏览器校验（加 --render 开启）")

    ok = ok_html and ok_xlsx and ok_render
    print("\n" + "=" * 62)
    print("结果：%s" % ("全部通过，可以交付" if ok else "有步骤失败，请按上面的 ERROR 修正后重跑"))
    print("交付物：\n  HTML  %s\n  Excel %s" % (html_path, xlsx_path))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
