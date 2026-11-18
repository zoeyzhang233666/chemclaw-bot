# -*- coding: utf-8 -*-
"""make_example.py · 一个命令重建一个示例的全部产物

用法：
    python make_example.py ../examples/example-1-id-soda-ash-dense
    python make_example.py ../examples/example-1-id-soda-ash-dense --tone formal --template reply_B_quote_structure
    python make_example.py ../examples --all          # 重建 examples/ 下所有 example-*

产出（写入示例目录）：
    01_标准化字段.json     字段 + 素材 + 问题（中间产物，全流程可复现）
    02_英文回复草稿.json   主题 + 正文 + 占位符
    03_英文回复草稿.md     可直接复制给客户
    04_询盘审阅板.html     单文件离线双栏审阅板（交给业务员用）
    05_询盘处理工作簿.xlsx 8 张表
    06_中文缺口简报.md     给主管看的两页纸
    07_运行自检.txt        本示例的自检结果
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(args, cwd=None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"   # Windows 控制台默认 GBK，会让子进程输出乱码
    env["PYTHONUTF8"] = "1"
    r = subprocess.run([PY] + args, cwd=cwd, capture_output=True, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace")
    err = (r.stderr or b"").decode("utf-8", "replace")
    if r.returncode != 0:
        sys.stderr.write("[fail] %s\n%s\n%s\n" % (" ".join(args), out, err))
        raise SystemExit(r.returncode)
    return out.strip()


def pick_input(ex_dir):
    inp = os.path.join(ex_dir, "input")
    eml = [f for f in sorted(os.listdir(inp)) if f.lower().endswith(".eml")]
    if not eml:
        raise SystemExit("input/ 下没有 .eml 文件：%s" % inp)
    return os.path.join(inp, eml[0])


def build_one(ex_dir, tone, template, inquiry_no=""):
    ex_dir = os.path.abspath(ex_dir)
    name = os.path.basename(ex_dir)
    src = pick_input(ex_dir)
    out_fields = os.path.join(ex_dir, "01_标准化字段.json")
    out_reply = os.path.join(ex_dir, "02_英文回复草稿.json")
    args = [os.path.join(HERE, "extract.py"), "--email", src, "--emit", ex_dir,
            "--tone", tone, "--template", template]
    if inquiry_no:
        args += ["--inquiry-no", inquiry_no]
    log = [run(args)]
    # extract 写的是 fields.json / reply.json，改名为带序号的文件（便于业务员按序看）
    for a, b in (("fields.json", "01_标准化字段.json"), ("reply.json", "02_英文回复草稿.json"),
                 ("questions.json", "01b_问题清单.json"), ("placeholders.json", "02b_占位符.json"),
                 ("snippets.json", "01c_素材.json"), ("gaps.txt", "01d_缺口摘要.txt")):
        pa, pb = os.path.join(ex_dir, a), os.path.join(ex_dir, b)
        if os.path.exists(pa):
            if os.path.exists(pb):
                os.remove(pb)
            os.rename(pa, pb)
    log.append(run([os.path.join(HERE, "build_md.py"), out_fields, out_reply,
                    "-o", os.path.join(ex_dir, "03_英文回复草稿.md")]))
    log.append(run([os.path.join(HERE, "build_md.py"), out_fields, out_reply, "--brief", "cn",
                    "-o", os.path.join(ex_dir, "06_中文缺口简报.md")]))
    log.append(run([os.path.join(HERE, "build_workbench.py"), out_fields, out_reply,
                    "-o", os.path.join(ex_dir, "04_询盘审阅板.html")]))
    log.append(run([os.path.join(HERE, "build_xlsx.py"), out_fields, out_reply,
                    "-o", os.path.join(ex_dir, "05_询盘处理工作簿.xlsx")]))
    try:
        log.append(run([os.path.join(HERE, "selfcheck.py"), ex_dir]))
    except SystemExit:
        log.append("[warn] selfcheck 未通过，见上方输出")
    with open(os.path.join(ex_dir, "07_运行自检.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("示例：%s\n参数：tone=%s template=%s\n\n" % (name, tone, template))
        f.write("\n".join(log) + "\n")
    print("[ok] %s 重建完成（%d 个产物）" % (name, len([x for x in os.listdir(ex_dir)
                                                 if not x.startswith(".") and x != "input"])))


def main():
    ap = argparse.ArgumentParser(description="一键重建示例产物")
    ap.add_argument("target", help="示例目录，或 examples 目录 + --all")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--tone", default="friendly-professional",
                    choices=["formal", "friendly-professional", "concise-direct"])
    ap.add_argument("--template", default="reply_A_confirm",
                    choices=["reply_A_confirm", "reply_B_quote_structure", "reply_C_sample", "reply_D_docs_only"])
    args = ap.parse_args()
    target = os.path.abspath(args.target)
    if args.all:
        dirs = [os.path.join(target, d) for d in sorted(os.listdir(target))
                if d.startswith("example-") and os.path.isdir(os.path.join(target, d, "input"))]
        if not dirs:
            raise SystemExit("没有找到 example-*/input 目录")
        for d in dirs:
            build_one(d, args.tone, args.template)
    else:
        build_one(target, args.tone, args.template)
    return 0


if __name__ == "__main__":
    sys.exit(main())
