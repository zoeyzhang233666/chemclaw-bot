# -*- coding: utf-8 -*-
"""PP 2026Q4 案例数据集 —— 供 build_report.py 复现验证

运行： python dataset_pp_2026q4.py <输出目录>
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from dataset_data import (SOURCES, PP_SERIES, PPF_SERIES, PROPYLENE, WTI, BRENT, BASIS, SPREAD_1019,
                          INVENTORY, SUPPLY, DEMAND, COST, EXPECT, EVIDENCE, CALIBER, SUMMARY, FUT_RAW)


def build_dataset():
    return dict(
        meta=dict(product="聚丙烯 PP（拉丝/纤维）", code="DCE.PP",
                  window="2026-10-01 ~ 2026-10-19", built="2026-10-20",
                  spot_caliber="生意社PP(拉丝)全国参考价 / 隆众华东拉丝主流报价",
                  fut_caliber="大商所PP：10/8主力收盘、10/19 PP2701结算价"),
        sources=SOURCES,
        series=dict(pp=PP_SERIES, ppf=PPF_SERIES, propylene=PROPYLENE, wti=WTI, brent=BRENT),
        windows=[
            dict(name="主窗口：PP拉丝现货", start="2026-10-01", start_price=9933.33,
                 end="2026-10-19", end_price=10756.67, abs_change=823.34, pct=8.29,
                 status="已核验", note="生意社全国参考价，两端均为原始披露值"),
            dict(name="PP纤维现货", start="2026-10-01", start_price=10162.50,
                 end="2026-10-19", end_price=10912.50, abs_change=750.00, pct=7.38,
                 status="已核验", note="纤维料同步跟涨"),
            dict(name="9月攻势", start="2026-09-01", start_price=9543.33,
                 end="2026-09-18", end_price=10116.67, abs_change=573.34, pct=6.01,
                 status="已核验", note="9月中上旬快速拉升"),
            dict(name="中期窗口（7/1起）", start="2026-07-01", start_price=7940.00,
                 end="2026-10-19", end_price=10756.67, abs_change=2816.67, pct=35.47,
                 status="已核验", note="含3月与9月两波行情"),
            dict(name="期货主力（单日）", start="2026-10-07", start_price=8631,
                 end="2026-10-08", end_price=9242, abs_change=611, pct=7.08,
                 status="推算", note="由收盘9242与涨幅+611反推前结"),
            dict(name="华东拉丝现货（10/8）", start="2026-09-30", start_price=10085,
                 end="2026-10-08", end_price=10371, abs_change=286, pct=2.84,
                 status="已核验", note="隆众转引，仅此两点"),
            dict(name="上游丙烯现货", start="2026-10-01", start_price=9707.67,
                 end="2026-10-19", end_price=10534.33, abs_change=826.66, pct=8.52,
                 status="已核验", note="10/12见高10751后回落"),
            dict(name="WTI原油", start="2026-10-01", start_price=89.38,
                 end="2026-10-19", end_price=101.41, abs_change=12.03, pct=13.46,
                 status="已核验", note="源文口径+9.2%，实算+13.46%"),
        ],
        fut_raw=FUT_RAW,
        spread=SPREAD_1019,
        basis=[dict(date=b["date"], spot=b["spot"], spot_caliber=b["spot_caliber"],
                    fut=b["fut"], contract="PP2701" if b["date"] == "2026-10-19" else "主力",
                    basis=b["basis"], status=b["status"], note=b.get("note", "")) for b in BASIS],
        inventory=INVENTORY, supply=SUPPLY, demand=DEMAND, cost=COST, expect=EXPECT,
        evidence=EVIDENCE,
        caliber=[dict(c, cadence={"现货口径": "日度", "期货口径": "日度", "统计滞后": "月度：次月中下旬",
                                  "库存口径": "周度", "利润口径": "周度", "基差口径": "日度"}.get(c["topic"], "周度"))
                 for c in CALIBER],
        summary=SUMMARY,
    )


if __name__ == "__main__":
    from build_report import build_all, stats
    outdir = sys.argv[1] if len(sys.argv) > 1 else "out"
    ds = build_dataset()
    html_p, xlsx_p = build_all(ds, outdir=outdir, tag="PP-基本面支撑核验")
    s = stats(ds)
    print("HTML :", html_p)
    print("XLSX :", xlsx_p)
    print("证据:", len(ds["evidence"]), s)
