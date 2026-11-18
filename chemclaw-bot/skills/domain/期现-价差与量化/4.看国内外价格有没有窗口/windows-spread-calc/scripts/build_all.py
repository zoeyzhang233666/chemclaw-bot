# -*- coding: utf-8 -*-
"""一键跑完整条流水线：validate → assemble → build_html → build_xlsx → 各项自检。

用法：
    python scripts/build_all.py examples/01-meg-cfr-china-huadong
    python scripts/build_all.py <案例目录> --skip-node    # 不用 node 时跳过 JS 比对

任何一步失败即中止（fail fast），因为后续产物都建立在前一步的结果上。
"""
import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
STEP = [0]


def step(title):
    STEP[0] += 1
    print("\n" + "=" * 68)
    print("【%d】%s" % (STEP[0], title))
    print("=" * 68)


def run(args, allow_fail=False):
    cmd = [PY] + args
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900)
    out = (r.stdout or "") + (r.stderr or "")
    print(out.rstrip())
    if r.returncode != 0 and not allow_fail:
        print("\n[中止] 上一步失败，构建停止。")
        sys.exit(r.returncode)
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description="一键构建内外价差报告与 Excel 模型")
    ap.add_argument("case_dir")
    ap.add_argument("--skip-node", action="store_true", help="跳过 Python/JS 内核比对")
    ap.add_argument("--skip-selftest", action="store_true", help="跳过内核自检")
    ap.add_argument("--skip-package", action="store_true", help="跳过包完整性检查")
    args = ap.parse_args()

    case = os.path.abspath(args.case_dir)
    res = os.path.join(case, "research.json")
    build = os.path.join(case, "build")
    out = os.path.join(case, "output")
    os.makedirs(build, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    data = os.path.join(build, "data.json")

    if not os.path.exists(res):
        print("[中止] 找不到 research.json：%s" % res)
        sys.exit(2)

    t0 = __import__("time").time()

    if not args.skip_selftest:
        step("内核自检（恒等式 / 术语屏蔽 / 边界）")
        run([os.path.join(SCRIPTS, "selftest.py")])

    if not args.skip_node:
        step("Python 内核 ≡ 浏览器内核 比对")
        rc = run([os.path.join(SCRIPTS, "check_consistency.py")], allow_fail=True)
        if rc != 0:
            print("[警告] 两套内核不一致；HTML 与 Excel 会给出不同数字，请先修内核再发布。")

    step("校验 research.json 六要素与历史取值规则")
    run([os.path.join(SCRIPTS, "validate.py"), res])

    step("组装 data.json（唯一事实源）")
    run([os.path.join(SCRIPTS, "assemble.py"), res, "--out", data])

    step("生成自包含交互 HTML")
    run([os.path.join(SCRIPTS, "build_html.py"), data,
         "--out", os.path.join(out, "report.html")])

    step("生成 Excel 活公式模型")
    run([os.path.join(SCRIPTS, "build_xlsx.py"), data,
         "--out", os.path.join(out, "model.xlsx")])

    if not args.skip_package:
        step("包完整性检查")
        run([os.path.join(SCRIPTS, "check_package.py")], allow_fail=True)

    print("\n" + "=" * 68)
    print("构建完成，用时 %.1f 秒" % (__import__("time").time() - t0))
    print("  HTML: %s" % os.path.join(out, "report.html"))
    print("  XLSX: %s" % os.path.join(out, "model.xlsx"))
    print("  DATA: %s" % data)
    print("=" * 68)


if __name__ == "__main__":
    main()
