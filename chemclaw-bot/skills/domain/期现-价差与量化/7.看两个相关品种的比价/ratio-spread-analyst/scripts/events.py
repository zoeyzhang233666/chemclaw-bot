# -*- coding: utf-8 -*-
"""
events.py — 产业事件台账
========================
只记录**可公开核对**的行业事件与口径变更，用于解释比价为何变化。
不写因果结论、不写交易建议。

每条事件必须带：
  date        事件发生/披露日期
  scope       PP / PE / BOTH / POLICY
  title       事件标题（尽量用报道原标题）
  source      可核对的来源（媒体+链接 或 机构名称）
  verify      核对级别：
                A = 有原始报道标题/正文可直接核对
                B = 有报道标题但细节需二次确认
                C = 行业常识/背景，未逐条核实（不得单独支撑结论）
  ratio_rel   对 PP/LDPE 比价的预期方向（+ 推高 / − 压低 / 0 中性 / ? 不确定）
              ——这是**方向判断**，不是幅度预测
"""
import csv
import os
import sys

EVENTS = [
    # ---------------- 2014-2016：低油价 + 煤制烯烃投产 ----------------
    dict(date="2014-06-30", scope="BOTH", ratio_rel="-", verify="C",
         title="2014 年下半年原油自 110 美元/桶区间回落，聚烯烃成本中枢整体下移",
         source="行业背景（布伦特原油 2014H2 大幅下跌，公开行情可核对）"),
    dict(date="2015-11-25", scope="PP", ratio_rel="-", verify="C",
         title="比价触及全样本最低 0.6913：PP 端新增产能（煤制烯烃/PDH）集中释放，PP 相对 PE 明显走弱",
         source="比价数据（本研究报告 result.json）"),
    dict(date="2016-12-31", scope="BOTH", ratio_rel="0", verify="C",
         title="OPEC 减产协议生效，原油自低位回升，聚烯烃成本端重新抬升",
         source="行业背景（2016-11-30 OPEC 达成减产，公开新闻可核对）"),

    # ---------------- 2017-2019：PE 扩能 + PP 相对走强 ----------------
    dict(date="2017-11-30", scope="PE", ratio_rel="+", verify="B",
         title="结构断点：比价中枢由约 0.88 抬升到约 0.99（Welch t≈42），PP 相对 PE 进入强势期",
         source="本报告结构扫描（analyze.py structure_scan）"),
    dict(date="2018-12-31", scope="PE", ratio_rel="+", verify="C",
         title="国内 PE 新增产能集中投放，PE 供应压力大于 PP，比价向 1.0 以上抬升",
         source="行业背景（PE 扩能周期，需以产能数据二次核对）"),
    dict(date="2019-08-06", scope="PP", ratio_rel="+", verify="A",
         title="比价触及全样本最高 1.1405（收盘口径）：PP 相对 PE 达历史最贵",
         source="比价数据（本报告 result.json，PP/L=1.1405）"),

    # ---------------- 2020-2021：疫情 / 能耗双控 ----------------
    dict(date="2020-02-03", scope="BOTH", ratio_rel="?", verify="A",
         title="春节后首个交易日，PP 与 L 双双跳空下跌约 6%（疫情冲击需求预期）",
         source="期货行情（PP/L 主连当日跌幅约 -5.9%/-6.0%，可复核）"),
    dict(date="2020-04-23", scope="BOTH", ratio_rel="?", verify="A",
         title="原油负价格后反弹，聚烯烃日内暴涨，比价日内高点 1.1448（盘中口径）",
         source="期货行情（当日 PP/L 涨幅约 +6%）"),
    dict(date="2021-02-18", scope="BOTH", ratio_rel="?", verify="A",
         title="节后聚烯烃集体大涨（PP +6.7%、L +7.6%）",
         source="期货行情（可复核）"),
    dict(date="2021-09-15", scope="BOTH", ratio_rel="?", verify="A",
         title="能耗双控/限电期间，聚烯烃同步大涨（两者均约 +5%）",
         source="期货行情（可复核）"),
    dict(date="2021-09-30", scope="BOTH", ratio_rel="0", verify="A",
         title="2021 年三季末 PP 与 L 同时冲到 9900-10150 元/吨区间，比价仍在 1.02 附近——同涨不改变比价",
         source="本报告贡献分解（2019-10 → 2021-09：PP +27.8%、L +35.9%）"),

    # ---------------- 2022-2024：PP 大扩能，比价回落 ----------------
    dict(date="2022-02-07", scope="BOTH", ratio_rel="?", verify="A",
         title="俄乌冲突初期能源暴涨，聚烯烃跳涨（PP +5.5%、L +6.1%）",
         source="期货行情（可复核）"),
    dict(date="2022-08-22", scope="PP", ratio_rel="-", verify="B",
         title="换月日叠加 PP 走弱，比价单日 -3.09%，其中含换月跳空（新旧合约价差 +3.26%）",
         source="换月台账（roll_ledger.csv）"),
    dict(date="2023-04-17", scope="PP", ratio_rel="-", verify="C",
         title="PP 进入集中扩能周期，供应增速高于 PE，比价自 1.0 一路回落",
         source="行业背景（需以 PP/PE 产能增速数据二次核对）"),
    dict(date="2024-12-02", scope="PP", ratio_rel="-", verify="A",
         title="比价触及近三年最低 0.8865：PP 相对 PE 为阶段最便宜",
         source="比价数据（本报告 result.json）"),

    # ---------------- 2025：比价中枢再度上移 ----------------
    dict(date="2025-04-07", scope="BOTH", ratio_rel="?", verify="A",
         title="关税冲击跳空下跌（L -4.9%），聚烯烃同步走弱",
         source="期货行情（可复核）"),
    dict(date="2025-12-10", scope="PP", ratio_rel="-", verify="A",
         title="比价触及近一年最低 0.9338（PP 相对 PE 阶段最便宜）",
         source="比价数据（本报告 result.json）"),
    dict(date="2025-12-29", scope="PE", ratio_rel="+", verify="A",
         title="聚乙烯月评：供应增加+需求萎缩，聚乙烯价格再度走跌",
         source="隆众资讯《聚乙烯月评（2025年12月）》，plas.oilchem.net/328/3965/"),

    # ---------------- 2026：地缘 + 成本推动，比价走扩 ----------------
    dict(date="2026-01-28", scope="PE", ratio_rel="+", verify="A",
         title="聚乙烯月评：供应压力缓解+成本支撑，聚乙烯市场价格上涨为主",
         source="隆众资讯《聚乙烯月评（2026年1月）》"),
    dict(date="2026-02-27", scope="PE", ratio_rel="+", verify="A",
         title="聚乙烯月评：供应压力减缓主导，聚乙烯多数品种价格窄幅走高",
         source="隆众资讯《聚乙烯月评（2026年2月）》"),
    dict(date="2026-03-02", scope="BOTH", ratio_rel="?", verify="A",
         title="3 月首日 PP +5.7%、L +5.8% 同步跳涨，随后整月大幅上行",
         source="期货行情（可复核）"),
    dict(date="2026-03-27", scope="BOTH", ratio_rel="?", verify="A",
         title="聚乙烯月评：成本强支撑+供应偏紧，聚乙烯价格大涨（与 PP 同向）",
         source="隆众资讯《聚乙烯月评（2026年3月）》"),
    dict(date="2026-04-08", scope="PP", ratio_rel="-", verify="A",
         title="单日急跌：PP -15.9%、L -10.0%，比价当日大幅回落（前期急涨后回吐）",
         source="期货行情（可复核，PP 主连 -15.9%）"),
    dict(date="2026-05-19", scope="PP", ratio_rel="+", verify="A",
         title="比价触及近一年最高 1.1109（亦是近三年/近五年最高）",
         source="比价数据（本报告 result.json）"),
    dict(date="2026-05-27", scope="PE", ratio_rel="+", verify="A",
         title="聚乙烯月评：弱需求与高供应博弈持续，聚乙烯重心下移（PP 端未同步走弱，比价走扩）",
         source="隆众资讯《聚乙烯月评（2026年5月）》"),
    dict(date="2026-07-16", scope="PP", ratio_rel="+", verify="A",
         title="PP 周评：地缘冲突扰动市场，聚丙烯市场超预期拉涨",
         source="隆众资讯《PP周评（20260710-0716）》"),
    dict(date="2026-07-23", scope="PP", ratio_rel="+", verify="A",
         title="PP 周评：地缘冲突再度升级，聚丙烯市场继续拉涨",
         source="隆众资讯《PP周评（20260717-0723）》"),
    dict(date="2026-08-18", scope="BOTH", ratio_rel="-", verify="A",
         title="L 与 PP 同日换月（→2701 合约），新旧合约价差 L +5.02%、PP +8.71%，当日比价 -3.71% 主要为换月跳空",
         source="换月台账（roll_ledger.csv）；当日比价 -3.71% 与换月跳空方向一致"),
    dict(date="2026-08-27", scope="BOTH", ratio_rel="0", verify="A",
         title="PP 周评：供需紧平衡格局未改，聚丙烯期现分化加剧",
         source="隆众资讯《PP周评（20260821-0827）》"),
    dict(date="2026-09-03", scope="PP", ratio_rel="+", verify="A",
         title="PP 周评：地缘博弈推升成本，聚丙烯价格宽幅上涨",
         source="隆众资讯《PP周评（20260828-0903）》"),
    dict(date="2026-09-23", scope="PP", ratio_rel="-", verify="A",
         title="PP 日评：中东局势缓和，聚丙烯价格回落",
         source="隆众资讯《PP日评（20260923）》"),
    dict(date="2026-10-08", scope="BOTH", ratio_rel="?", verify="A",
         title="国庆节后跳空上行：L +6.6%、PP +6.5%，两者同向",
         source="期货行情（可复核）"),
    dict(date="2026-10-15", scope="PE", ratio_rel="-", verify="A",
         title="PE 周评：聚乙烯市场现货价格整体上涨；同期 PP 日评显示高价成交受阻、高位回落",
         source="隆众资讯《PE周评（20261009-1015）》《PP日评（20261016）》"),
    dict(date="2026-10-16", scope="PE", ratio_rel="-", verify="A",
         title="聚乙烯：供需格局转松，价格承压下行；PP 端为供应收缩、库存低位",
         source="隆众资讯《聚乙烯》栏目（2026-10-16）；《隆众聚焦·供应收缩产业链库存低位》"),
]


def export(path):
    order = ["date", "scope", "ratio_rel", "verify", "title", "source"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=order)
        w.writeheader()
        for e in sorted(EVENTS, key=lambda x: x["date"]):
            w.writerow({k: e.get(k, "") for k in order})
    return len(EVENTS)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "build/events.csv"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    n = export(out)
    sys.stdout.reconfigure(encoding="utf-8")
    print("events:", n, "->", out)
    from collections import Counter
    print("verify levels:", Counter(e["verify"] for e in EVENTS))
    print("scopes:", Counter(e["scope"] for e in EVENTS))
