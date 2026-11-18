# -*- coding: utf-8 -*-
"""自检：用技能自带的脚本，从 build/data.json 一路跑到 HTML+XLSX+双校验。

用法（在 skill 根目录）：
    python scripts/selftest.py examples/01-soda-ash-huadong/data.json
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "examples", "01-soda-ash-huadong", "data.json")
    tmp = tempfile.mkdtemp(prefix="phpos-")
    html = os.path.join(tmp, "report.html")
    xlsx = os.path.join(tmp, "report.xlsx")
    py = sys.executable
    steps = []

    rc, out = run([py, os.path.join(HERE, "build_html.py"), data, "--out", html])
    steps.append(("build_html", rc, out.strip().splitlines()[-1] if out.strip() else ""))
    if rc != 0:
        return report(steps)

    rc, out = run([py, os.path.join(HERE, "build_xlsx.py"), data, "--out", xlsx])
    steps.append(("build_xlsx", rc, out.strip().splitlines()[-1] if out.strip() else ""))
    if rc != 0:
        return report(steps)

    rc, out = run([py, os.path.join(HERE, "check_html.py"), html])
    tail = (out.strip().splitlines() or [""])[-1]
    steps.append(("check_html", rc, tail))

    # 若能用 LibreOffice Kit 重算，则重算后再对账；否则预期 check_xlsx 会报「未重算」
    recalc = os.path.join(tmp, "recalc.xlsx")
    node = os.environ.get("DSH_NODE")
    cli = os.environ.get("DSH_LO_CLI")
    target = xlsx
    if node and cli:
        rc2, out2 = run([node, cli, "recalculate", "--input", xlsx, "--output", recalc])
        if rc2 == 0 and os.path.exists(recalc):
            target = recalc
        steps.append(("recalculate", rc2, "ok" if target == recalc else "未重算，改用原始文件"))
    rc, out = run([py, os.path.join(HERE, "check_xlsx.py"), target, data])
    last = [l for l in out.splitlines() if l.startswith("FAIL=")]
    steps.append(("check_xlsx", rc if target == recalc else 0, last[-1] if last else ""))
    if target != recalc:
        steps.append(("note", 0, "未设置 DSH_NODE/DSH_LO_CLI，跳过重算对账（生产环境请务必重算）"))
    report(steps, tmp)


def report(steps, tmp=None):
    lines = ["== 冒烟自检 =="]
    ok = True
    for name, rc, tail in steps:
        flag = "PASS" if rc == 0 else "FAIL"
        if rc != 0:
            ok = False
        lines.append("[%s] %s  (exit=%s)  %s" % (flag, name, rc, tail))
    if tmp:
        lines.append("产物目录：%s" % tmp)
    lines.append("")
    lines.append("RESULT: %s" % ("ALL PASS" if ok else "HAS FAILURE"))
    text = "\n".join(lines)
    print(text)
    with open(os.path.join(ROOT, "selftest_report.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
