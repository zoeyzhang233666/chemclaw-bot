"""
validate.py — case JSON 契约校验。0 error 才允许出报告。

  python validate.py case.json
  python validate.py case.json --strict     # warning 也算失败（交付版建议用）
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="校验 case JSON 结构与证据链")
    ap.add_argument("case")
    ap.add_argument("--strict", action="store_true", help="若有 warning 则返回非 0")
    a = ap.parse_args()
    case = C.load_json(a.case)
    errs, warns = C.validate_case(case)
    for w in warns:
        print("WARN  ", w)
    for e in errs:
        print("ERROR ", e)
    try:
        idx = C.build_index(case)
        print("INFO   结构年份 %s；金额 CAGR %s；数量 CAGR %s" % (
            idx["structure_year"], C.fmt_pct(idx["cagr_value"]), C.fmt_pct(idx["cagr_qty"])))
    except Exception as ex:  # noqa: BLE001
        errs.append("build_index 失败：%s" % ex)
        print("ERROR  build_index 失败：%s" % ex)
    print("—" * 60)
    print("%d error / %d warning" % (len(errs), len(warns)))
    if errs or (a.strict and warns):
        sys.exit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
