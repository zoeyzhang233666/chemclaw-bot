# -*- coding: utf-8 -*-
"""build_all.py — 一次跑完：校验 → HTML → XLSX（可选 LibreOffice 重算）。

    python scripts/build_all.py data.json --outdir out [--name 前缀] [--no-recalc]

产出：
    <outdir>/<前缀>.html   单文件交互式报告
    <outdir>/<前缀>.xlsx   供应商评估工作簿
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _stream in (sys.stdout, sys.stderr):  # Windows 控制台默认 GBK，改用 UTF-8 输出
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
sys.path.insert(0, HERE)
import cmplib as L  # noqa: E402


def parse_args(argv):
    """极简参数解析：位置参数 1 个（data.json），--outdir / --name 支持空格或等号。"""
    data_path, outdir, name = None, "out", None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--outdir"):
            if "=" in a:
                outdir = a.split("=", 1)[1]
            else:
                i += 1
                outdir = argv[i] if i < len(argv) else outdir
        elif a.startswith("--name"):
            if "=" in a:
                name = a.split("=", 1)[1]
            else:
                i += 1
                name = argv[i] if i < len(argv) else name
        elif not a.startswith("--"):
            data_path = a
        i += 1
    return data_path, outdir, name


def main():
    data_path, outdir, name = parse_args(sys.argv[1:])
    if not data_path:
        print("usage: python scripts/build_all.py data.json --outdir out [--name 前缀] [--no-recalc]")
        raise SystemExit(2)

    data = json.load(io.open(data_path, encoding="utf-8"))
    meta = data.get("meta", {})
    base = name or meta.get("export_base") or os.path.splitext(os.path.basename(data_path))[0]

    # 1) 校验
    r = subprocess.run([sys.executable, os.path.join(HERE, "validate.py"), data_path],
                       capture_output=True)
    raw = (r.stdout or b"") + (r.stderr or b"")
    out = ""
    for enc in ("utf-8", "gbk", "mbcs"):
        try:
            out = raw.decode(enc).strip()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    print(out if out else "（校验器无输出，返回码 %d）" % r.returncode)
    if r.returncode != 0:
        print("校验未通过，已停止出报告。")
        raise SystemExit(1)

    os.makedirs(outdir, exist_ok=True)
    html_out = os.path.join(outdir, base + ".html")
    xlsx_out = os.path.join(outdir, base + ".xlsx")

    # 2) HTML
    import render_html
    html = render_html.render(data)
    io.open(html_out, "w", encoding="utf-8", newline="\n").write(html)
    print("HTML -> %s (%.1f KB)" % (html_out, len(html.encode("utf-8")) / 1024))

    # 3) XLSX
    import render_xlsx
    render_xlsx.build(data, xlsx_out)

    # 4) 可选：LibreOffice 重算，让公式带缓存值
    if "--no-recalc" not in sys.argv:
        node = os.environ.get("LO_KIT_NODE")
        cli = os.environ.get("LO_KIT_CLI")
        tmp = xlsx_out.replace(".xlsx", ".recalc.xlsx")
        if node and cli and os.path.exists(node) and os.path.exists(cli):
            try:
                subprocess.run([node, cli, "recalculate", "--input", xlsx_out, "--output", tmp],
                               check=True, capture_output=True)
                os.replace(tmp, xlsx_out)
                print("XLSX 已重算公式缓存：%s" % xlsx_out)
            except Exception as exc:  # noqa: BLE001
                print("（跳过重算：%s）" % exc)
        else:
            print("（未配置 LO_KIT_NODE / LO_KIT_CLI，跳过公式重算；Excel 打开时会自动计算）")
    print("完成：%s / %s" % (html_out, xlsx_out))


if __name__ == "__main__":
    main()
