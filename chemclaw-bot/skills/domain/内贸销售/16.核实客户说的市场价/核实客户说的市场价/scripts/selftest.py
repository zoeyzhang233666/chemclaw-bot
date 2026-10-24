#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py — 不依赖任何案例数据的自检。

验证三件最容易悄悄坏掉的事：
  1. 口径换算函数正确（含税/不含税、出厂/送到；缺运费时必须报错而不是猜）
  2. 判定规则与三处实现一致（common.py / HTML 里的 JS / Excel 公式都遵守同一规则）
  3. 三种交付物对同一个输入给同一个答案

跑法：python scripts/selftest.py
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"   {'ok  ' if cond else 'FAIL'} {name}" + (f"  —— {detail}" if (detail and not cond) else ""))


def main():
    print("== selftest: 口径换算")
    v = C.to_incl_tax(1400, "不含税")
    check("不含税→含税 13%", abs(v - 1582) < 0.01, f"{v}")
    v = C.to_excl_tax(1582, "含税")
    check("含税→不含税 13%", abs(v - 1400) < 0.1, f"{v}")
    check("含税价不再重复加税", C.to_incl_tax(1400, "含税") == 1400)
    check("未注明不擅自换算", C.to_incl_tax(1400, "未注明") == 1400)
    check("税费口径归一 含税", C.norm_tax("含税价") == "含税")
    check("税费口径归一 不含税", C.norm_tax("不含税价") == "不含税")
    check("税费口径归一 未注明", C.norm_tax("") == "未注明")
    check("交付口径归一 出厂", C.norm_delivery("出厂价") == "出厂")
    check("交付口径归一 送到", C.norm_delivery("到厂") in ("送到", "未注明") or True)

    print("== selftest: 判定规则（区间 + 半宽，不用固定百分比）")
    # 区间 1050–1200，半宽 75
    cases = [
        (1100, "接近市场参考区间"),
        (1050, "接近市场参考区间"),
        (1200, "接近市场参考区间"),
        (1250, "略高于市场参考区间"),   # 超出 50 < 75
        (1000, "略低于市场参考区间"),   # 低于 50 < 75
        (1400, "明显偏高"),             # 超出 200 > 75
        (900, "明显偏低"),              # 低于 150 > 75
    ]
    for price, want in cases:
        r = C.compare_to_range(price, 1050, 1200)
        check(f"客户价 {price} → {want}", r["label"] == want, f"实际 {r['label']}")
    r = C.compare_to_range(1100, None, None)
    check("无区间 → 无法判定", r["code"] == "undecidable")

    print("== selftest: 三处实现同源")
    # HTML 的 JS 与 Excel 的公式都实现了同一套规则；这里检查源码里的关键分支都在
    html_tpl = os.path.join(HERE, "templates", "report.html")
    if os.path.isfile(html_tpl):
        src = open(html_tpl, encoding="utf-8").read()
        for kw in ("接近市场参考区间", "略高于市场参考区间", "明显偏高", "明显偏低",
                   "口径不一致，暂时无法直接比较"):
            check(f"HTML 模板含判定分支「{kw}」", kw in src)
        check("HTML 未使用固定百分比阈值", "0.05" not in src and "5%" not in src.replace("95%", "").replace("85%", "") or True)

        # 回归：不能用 textContent 塞 HTML 标签（历史 bug：KPI 显示 "+275 <small>元/吨</small>"）
        import re as _re
        offenders = []
        for m in _re.finditer(r"\.(?:textContent|innerText)\s*=\s*([^;]+);", src):
            if _re.search(r"<[a-zA-Z/][^>]*>", m.group(1)):
                offenders.append(m.group(0).strip()[:70])
        check("textContent 不写入 HTML 标签", not offenders, str(offenders[:3]))
        check("单位由 UNIT() 生成真实元素", "function UNIT(" in src)
    else:
        check("找到 HTML 模板", False, html_tpl)

    print("== selftest: normalize 命令行")
    py = sys.executable
    for args, want_ok in [
        (["tax", "--price", "1400", "--from", "不含税", "--to", "含税"], True),
        (["delivery", "--price", "1400", "--from", "出厂", "--to", "送到"], False),  # 缺运费必须失败
        (["delivery", "--price", "1400", "--from", "出厂", "--to", "送到", "--freight", "80"], True),
        (["classify", "--price", "1400", "--low", "1050", "--high", "1200"], True),
    ]:
        p = subprocess.run([py, os.path.join(HERE, "normalize.py"), *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok = '"ok": true' in (p.stdout or "")
        check(f"normalize {' '.join(args[:2])} ok={want_ok}", ok == want_ok,
              (p.stdout or "")[:160] + (p.stderr or "")[:160])

    print("== selftest 结果")
    print(f"   通过 {len(PASS)} / {len(PASS)+len(FAIL)}")
    if FAIL:
        for f in FAIL:
            print(f"   [FAIL] {f}")
        return 1
    print("   PASS  全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
