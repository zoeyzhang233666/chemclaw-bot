# -*- coding: utf-8 -*-
"""run_all.py — 一键跑完整流程

用法:
    python run_all.py --dataset dataset.json --out ./output
    python run_all.py --dataset dataset.json --out ./output --no-osrm     # 离线
    python run_all.py --dataset dataset.json --out ./output --skip-geo    # 复用已有底图

顺序: 校验 → 底图 → 距离 → 评分 → HTML → Excel
任何一步失败即中止（不要产出半成品）。
"""
import argparse, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(cmd, cwd=None):
    print("\n$ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        print(f"\n[run_all] 失败（退出码 {r.returncode}），中止。")
        sys.exit(r.returncode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default="output")
    ap.add_argument("--template", default=os.path.join(HERE, "..", "template", "report.html"))
    ap.add_argument("--no-osrm", action="store_true")
    ap.add_argument("--skip-geo", action="store_true")
    ap.add_argument("--name", default="", help="输出文件名前缀（默认取 dataset.meta.title）")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    ds = os.path.abspath(args.dataset)
    geo = os.path.join(args.out, "geo_simplified.json")

    run([PY, os.path.join(HERE, "validate_dataset.py"), ds, "--allow-missing-distance"])

    if not args.skip_geo:
        run([PY, os.path.join(HERE, "prepare_geo.py"), "--dataset", ds, "--out", geo])

    cmd = [PY, os.path.join(HERE, "compute_routes.py"), "--dataset", ds,
           "--out", os.path.join(args.out, "routes.json")]
    if args.no_osrm:
        cmd.append("--no-osrm")
    run(cmd)

    run([PY, os.path.join(HERE, "compute_scores.py"), "--dataset", ds])

    # 距离与评分落盘后做一次严格校验（此时缺距离就是错）
    run([PY, os.path.join(HERE, "validate_dataset.py"), ds])

    import json
    with open(ds, encoding="utf-8") as f:
        data = json.load(f)
    prefix = args.name or data["meta"].get("file_prefix") or data["meta"]["title"].replace(" ", "_")

    html = os.path.join(args.out, f"{prefix}.html")
    xlsx = os.path.join(args.out, f"{prefix}.xlsx")
    run([PY, os.path.join(HERE, "build_html.py"), "--dataset", ds, "--geo", geo,
         "--template", args.template, "--out", html])
    run([PY, os.path.join(HERE, "build_xlsx.py"), "--dataset", ds, "--out", xlsx])

    # 把数据与底图一起复制进输出目录，便于复算
    for src, name in ((ds, "dataset.json"), (geo, "geo_simplified.json")):
        if os.path.abspath(src) != os.path.abspath(os.path.join(args.out, name)):
            shutil.copyfile(src, os.path.join(args.out, name))

    print("\n=== 完成 ===")
    for p in (html, xlsx):
        print(f"  {p}  ({os.path.getsize(p)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
