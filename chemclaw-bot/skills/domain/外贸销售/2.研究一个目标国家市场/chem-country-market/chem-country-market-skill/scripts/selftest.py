"""
selftest.py — 不用联网、不用真实数据，验证本技能脚本链是自洽的。

  python selftest.py                       # 用内置的最小合成 case，全流程跑一遍
  python selftest.py --case 你的case.json   # 用真实 case 走一遍（更快，不检查合成逻辑）

它会检查：
 1. common.build_index 对缺失数据不抛异常、不臆造数值（数量缺失时 CAGR 必须是 None）
 2. validate 能抓出该类错误（缺字段、来源引用不存在的 id、金额量级异常、预测性表述）
 3. build_html 生成的文件包含 ECharts、数据块可解析、九大板块齐全
 4. build_xlsx 生成的表数量与必需 sheet 齐全
 5. check_html / check_xlsx 对合格产物返回 0
"""
import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import build_html  # noqa: E402
import build_xlsx  # noqa: E402

FAIL = []


def ok(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        FAIL.append(msg)


BASE = {
    "meta": {
        "title": "合成用例 · 某化工品出口某国",
        "subject": {"product_cn": "测试产品", "hs_code": "2836.20", "grade": "工业级", "unit": "t"},
        "country": {"name_cn": "测试国", "name_en": "Testland", "un_m49": 999},
        "research_year": 2024, "window": 3, "data_asof": "2025-01-01",
        "trade_source": {"name": "UN Comtrade", "dataset": "C/A/HS", "value_basis": "CIF", "weight_basis": "netWgt",
                         "pull_record": "selftest", "notes": ["合成数据，仅用于自检"]},
    },
    "structure": {"product": ["合成"], "hs_scope_note": "合成", "hs_scope_sources": ["s1"]},
    "trade": {
        "imports": [
            {"year": 2022, "value_usd": 100000000, "qty_t": 500000, "source": "comtrade"},
            {"year": 2023, "value_usd": 120000000, "qty_t": None, "source": "comtrade"},
            {"year": 2024, "value_usd": 90000000, "qty_t": 400000, "source": "comtrade"},
        ],
        "imports_history": [
            {"year": 2022, "value_usd": 100000000, "qty_t": 500000, "source": "comtrade"},
            {"year": 2023, "value_usd": 120000000, "qty_t": None, "source": "comtrade"},
            {"year": 2024, "value_usd": 90000000, "qty_t": 400000, "source": "comtrade"},
        ],
        "partners": {"2024": [{"rank": 1, "name": "甲国 Alpha", "code": 1, "value_usd": 60000000, "qty_t": 260000},
                              {"rank": 2, "name": "中国 China", "code": 156, "value_usd": 25000000, "qty_t": 110000}]},
        "china_exports": [{"year": 2022, "to_idn_usd": 20000000, "to_idn_t": 100000, "to_world_usd": 200000000},
                          {"year": 2024, "to_idn_usd": 25000000, "to_idn_t": 110000, "to_world_usd": 260000000}],
        "exports": [{"year": 2024, "value_usd": 2000000, "qty_t": 9000, "top_dest": "乙国 Beta"}],
        "local_supply": [], "consumption_reference": [],
    },
    "industries": {
        "description_note": "合成",
        "local_production": [{"id": "f1", "name": "测试工厂", "role": "生产", "location": "X", "capacity_t": 300000,
                              "capacity_basis": "新闻稿", "status": "在建", "status_asof": "2025-01-01",
                              "products": ["测试产品"], "facts": ["合成事实"], "sources": ["s1"], "verify": ["投产时间"]}],
        "local_absence_evidence": [{"claim": "合成本地无产能", "source": "s1", "kind": "media"}],
        "consumers": [{"id": "c1", "name": "测试客户", "type": "下游", "location": "Y", "products": "成品",
                       "buying_role": "直接用户", "facts": ["合成"], "sources": ["s1"], "verify": ["年用量"]}],
        "consumers_unnamed": [{"segment": "中小厂", "why_unnamed": "无资料", "search_hint": "工商名录"}],
    },
    "downstream": {"note": "合成", "items": [{"segment": "玻璃", "demand_signal": "合成信号", "scale_note": "—",
                                              "sources": ["s1"], "gap": "产量"}]},
    "competition": {"source_countries": [{"name": "甲国 Alpha", "basis": "合成", "evidence": "comtrade"}],
                    "distributors": [{"name": "测试贸易商", "role": "分销", "products": "测试产品", "source": "s1"}],
                    "price_observation": [], "china_hs_code_note": "合成"},
    "policy": {
        "hs_line": {"code": "2836.20.00", "description": "测试", "verify_note": "待核实"},
        "tariffs": [{"id": "t1", "item": "MFN", "rate_pct": None, "status": "gap", "detail": "未取得", "sources": ["s1"]}],
        "ntm": [{"id": "p1", "item": "进口许可", "status": "need_confirm", "detail": "待确认", "sources": ["s1"]}],
        "trade_relations": [{"id": "r-rcep", "item": "RCEP", "status": "fact", "detail": "合成", "sources": ["s1"]}],
    },
    "reports": [{"id": "rp1", "type": "机构估算", "title": "合成研报", "key_points": ["合成"], "source": "s1",
                 "caveat": "仅参考"}],
    "sources": [{"id": "s1", "kind": "media", "publisher": "测试社", "title": "测试报道", "url": "https://example.com/a",
                 "date": "2025-01-01", "tier": 2},
                {"id": "comtrade", "kind": "official", "publisher": "UN", "title": "Comtrade",
                 "url": "https://comtradeapi.un.org/public/v1/preview/C/A/HS", "date": "2025-01-01", "tier": 1}],
    "gaps": [{"id": "g1", "level": "数据级", "item": "数量", "why": "未报送", "impact": "无法算增速", "how_to_close": "查统计局"}],
    "verify_actions": [{"priority": "P0", "action": "核税号", "owner": "销售", "when": "报价前"}],
}


def t1_index():
    print("[1] build_index 不臆造数值")
    idx = C.build_index(copy.deepcopy(BASE))
    ok(idx["cagr_value"] is not None, "金额 CAGR 可算")
    ok(idx["cagr_qty"] is not None, "首末年份都有数量时，数量 CAGR 可算（%.1f%%）" % (idx["cagr_qty"] or 0))
    case2 = copy.deepcopy(BASE)
    case2["trade"]["imports"][-1]["qty_t"] = None
    case2["trade"]["imports_history"][-1]["qty_t"] = None
    idx2 = C.build_index(case2)
    ok(idx2["cagr_qty"] is None, "末年份数量缺失 → 数量 CAGR = None（不插值、不估算）")
    ok(idx2["qty_missing_years"] == [2023, 2024], "缺失年份被正确记录")
    ok(idx2["kpi"][2]["kind"] == "gap", "数量缺失时 KPI 卡片标为“缺口”")
    ok(any(k["kind"] == "gap" for k in idx2["kpi"]), "至少有一个 KPI 明确标记为缺口")


def t2_validate():
    print("[2] validate 能抓错")
    e, w = C.validate_case(copy.deepcopy(BASE))
    ok(not e, "基准用例 0 error（实际：%s）" % e)
    bad = copy.deepcopy(BASE)
    del bad["meta"]["subject"]["hs_code"]
    ok(any("hs_code" in x for x in C.validate_case(bad)[0]), "缺 hs_code 被抓出")
    bad2 = copy.deepcopy(BASE)
    bad2["industries"]["local_production"][0]["sources"] = ["s-not-exist"]
    ok(any("未在 sources 中登记" in x for x in C.validate_case(bad2)[0]), "引用不存在的来源 id 被抓出")
    bad3 = copy.deepcopy(BASE)
    bad3["trade"]["imports"][0]["value_usd"] = 1e13
    ok(any("量级异常" in x for x in C.validate_case(bad3)[0]), "金额漏乘单位被抓出")
    bad4 = copy.deepcopy(BASE)
    bad4["gaps"][0]["how_to_close"] = "预计将增长，份额必将扩大"
    ok(any("未授权表述" in x or "预测性" in x for x in C.validate_case(bad4)[0]), "预测性表述被抓出")
    bad5 = copy.deepcopy(BASE)
    bad5["gaps"] = []
    ok(any("gaps" in x for x in C.validate_case(bad5)[1]), "缺口为空时给出警告")
    bad6 = copy.deepcopy(BASE)
    bad6["trade"]["partners"]["2024"][0]["value_usd"] = 10 ** 9
    ok(any("超过进口合计" in x for x in C.validate_case(bad6)[0]), "伙伴金额超过合计被抓出")


def t3_html(tmp):
    print("[3] build_html 产物结构")
    html, data = build_html.build_html(copy.deepcopy(BASE))
    p = os.path.join(tmp, "t.html")
    open(p, "w", encoding="utf-8").write(html)
    ok("echarts" in html[:200000].lower(), "ECharts 已内联")
    ok("__DATA__" not in html, "无 __DATA__ 占位")
    seg = html[html.index("const D = ") + 10:]
    blob = seg[:seg.index("\nconst $ =")].rstrip().rstrip(";")
    try:
        d = json.loads(blob)
        ok(d["case"]["meta"]["country"]["name_cn"] == "测试国", "数据块可被 JSON 解析")
    except Exception as ex:  # noqa: BLE001
        ok(False, "数据块解析失败：%s" % ex)
    for rid in ("kpiGrid", "chartTrade", "chartPie", "gapGrid", "mapTable", "sec-policy"):
        ok(('id="%s"' % rid) in html, "包含元素 #%s" % rid)
    r = subprocess.run([sys.executable, os.path.join(HERE, "check_html.py"), p],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok(r.returncode == 0, "check_html 通过（%s）" % (r.stdout or r.stderr)[-300:].replace("\n", " "))


def t4_xlsx(tmp):
    print("[4] build_xlsx 产物结构")
    p = os.path.join(tmp, "t.xlsx")
    out, n = build_xlsx.build(copy.deepcopy(BASE), p)
    ok(n >= 15, "工作表数量 %d ≥ 15" % n)
    r = subprocess.run([sys.executable, os.path.join(HERE, "check_xlsx.py"), p, "--min-gap-cells", "3"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok(r.returncode == 0, "check_xlsx 通过（%s）" % (r.stdout or r.stderr)[-300:].replace("\n", " "))


def t5_real(case_path):
    print("[5] 真实 case 全流程")
    case = C.load_json(case_path)
    e, w = C.validate_case(case)
    ok(not e, "validate 0 error（%s）" % (e[:2] if e else "ok"))
    html, data = build_html.build_html(case)
    ok(len(html) > 800000, "HTML 体积正常（%.2f MB）" % (len(html) / 1048576.0))
    idx = C.build_index(case)
    ok(bool(idx["structure_rows"]), "伙伴结构可用（%s 年）" % idx["structure_year"])
    ok(idx["gap_count"] > 0, "有缺口清单（%d 项）" % idx["gap_count"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="ccm_selftest_")
    t1_index()
    t2_validate()
    t3_html(tmp)
    t4_xlsx(tmp)
    if a.case:
        t5_real(a.case)
    print("—" * 56)
    if FAIL:
        print("FAILED %d 项：" % len(FAIL))
        for f in FAIL:
            print("  -", f)
        return 1
    print("全部自检通过")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

