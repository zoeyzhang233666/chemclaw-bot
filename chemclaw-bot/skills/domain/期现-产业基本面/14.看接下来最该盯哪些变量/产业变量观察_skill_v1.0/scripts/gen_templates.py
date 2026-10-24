# -*- coding: utf-8 -*-
"""
用「空白 payload 模板」生成一份最小可运行示例，产出 templates/ 下的正式模板文件。
最小示例只填结构、不填真实数据（数值统一写"数据缺失"），用于：
  1. 演示模板长什么样
  2. 供引擎回归测试（每次改渲染器后跑一遍，确保不崩）
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL / "scripts"))

import render_excel  # noqa
import render_html  # noqa

DEMO = {
    "meta": {
        "commodity": "【品种名】（交易所代码）",
        "cycle": "未来 1 个月（YYYY-MM-DD ~ YYYY-MM-DD）",
        "as_of": "YYYY-MM-DD",
        "analyst": "填写研究人",
        "version": "template",
        "contract_focus": "填写主力合约与基差口径",
        "region_focus": "填写重点区域（产销区/港口/成本地）",
        "price_basis": "填写现货与期货口径（含税否、出库/到岸、收盘/结算）",
        "research_position": "期货 / 现货 / 期现兼顾",
    },
    "as_of": "YYYY-MM-DD",
    "snapshot": [
        dict(indicator="价格：主力收盘 / 现货",
             value="数据缺失", recent="数据缺失", history="数据缺失",
             scope="填写口径", source="填写来源与日期"),
        dict(indicator="库存（口径 A）",
             value="数据缺失", recent="数据缺失", history="数据缺失",
             scope="填写口径 A", source="填写来源与日期"),
        dict(indicator="库存（口径 B，注意不可与 A 混用）",
             value="数据缺失", recent="数据缺失", history="数据缺失",
             scope="填写口径 B", source="填写来源与日期"),
        dict(indicator="开工率 / 产量",
             value="数据缺失", recent="数据缺失", history="数据缺失",
             scope="填写口径", source="填写来源与日期"),
        dict(indicator="下游需求（主力下游开工）",
             value="数据缺失", recent="数据缺失", history="数据缺失",
             scope="填写口径", source="填写来源与日期"),
        dict(indicator="成本与利润（原料价 / 生产利润）",
             value="数据缺失", recent="数据缺失", history="数据缺失",
             scope="填写口径", source="填写来源与日期"),
    ],
    "events": [
        dict(date="YYYY-MM-DD", date_label="MM-DD",
             title="周度库存与开工数据发布",
             kind="定期数据", cat="库存",
             certainty="固定周度发布节奏",
             impact="反映供需边际变化", source="填写来源"),
        dict(date="YYYY-MM-DD", date_label="MM-DD",
             title="【某装置检修/复产/投产事件】",
             kind="已披露·进行中", cat="供给",
             certainty="已开始，结束时间以复产公告为准",
             impact="影响供给量", source="填写来源与日期"),
        dict(date="YYYY-MM-DD", date_label="MM-DD",
             title="【条件触发类事件，如季节性/政策窗口】",
             kind="季节性·条件触发", cat="政策",
             certainty="历史规律，具体时点逐年浮动，不代表必然发生",
             impact="若发生将改变供需节奏", source="填写来源与日期"),
    ],
    "candidates": [
        dict(name="【示例：核心库存】", cat="库存", verifiability="高（周度双源）", selected=True,
             reason="填写：为什么它在产业逻辑上直接、可验证、周期匹配"),
        dict(name="【示例：下游开工】", cat="需求", verifiability="高（周度）", selected=True,
             reason="填写入选理由"),
        dict(name="【示例：成本端】", cat="成本", verifiability="高（周度）", selected=False,
             reason="填写落选的具体理由与提级条件"),
    ],
    "variables": [
        dict(
            vid="V1", name="【变量一：一句话说清看什么】", cat="库存",
            rank=1, importance=5, verifiability=4, urgency=5,
            horizon="周度",
            current="数据缺失（填写：数值 + 日期 + 口径）",
            recent_change="数据缺失（填写：方向 + 幅度）",
            history_pos="数据缺失（填写：分位/极值/同比）",
            why="填写：它如何改变供需平衡或价格形成机制",
            mechanism="填写：可检验的因果链",
            key_data="①数据1 ②数据2 ③数据3",
            verify_yes="填写确认信号（须含数字阈值）",
            verify_no="填写否证信号（须含数字阈值）",
            invalidate="填写什么情况会让该指标失去解释力",
            source="填写来源 + 日期", freq="周度",
            next_date="YYYY-MM-DD（具体日期）",
            confidence="填写高/中/低 + 理由",
            gap="填写口径与局限",
        ),
        dict(
            vid="V2", name="【变量二】", cat="需求",
            rank=2, importance=4, verifiability=4, urgency=4,
            horizon="周度",
            current="数据缺失", recent_change="数据缺失", history_pos="数据缺失",
            why="填写关注原因", mechanism="填写传导机制",
            key_data="① ② ③",
            verify_yes="填写确认信号（须含数字阈值）",
            verify_no="填写否证信号（须含数字阈值）",
            invalidate="填写失效条件",
            source="填写来源", freq="周度", next_date="YYYY-MM-DD",
            confidence="填写", gap="填写",
        ),
        dict(
            vid="V3", name="【变量三】", cat="价差",
            rank=3, importance=4, verifiability=5, urgency=4,
            horizon="日频",
            current="数据缺失", recent_change="数据缺失", history_pos="数据缺失",
            why="填写关注原因", mechanism="填写传导机制",
            key_data="① ② ③",
            verify_yes="填写确认信号（须含数字阈值）",
            verify_no="填写否证信号（须含数字阈值）",
            invalidate="填写失效条件",
            source="填写来源", freq="日频", next_date="YYYY-MM-DD",
            confidence="填写", gap="填写",
        ),
    ],
    "secondary": [
        dict(name="【二级观察指标】", why="填写：为什么不单列 + 提级触发条件（带数字）"),
    ],
    "gaps": [
        dict(item="【不可得指标】", why="填写为什么不可得",
             workaround="填写替代口径", limit="填写局限"),
    ],
    "charts": {},
    "weekly_calendar": [
        dict(when="每周X", what="填写查询内容", src="填写来源"),
        dict(when="每日", what="填写查询内容", src="填写来源"),
    ],
}


def main():
    out_html = HERE.parent / "templates" / "template_demo_index.html"
    out_xlsx = HERE.parent / "templates" / "workbook_template.xlsx"

    html = render_html.render(DEMO, validate_first=True)
    out_html.write_text(html, encoding="utf-8")
    print("✓", out_html, f"{out_html.stat().st_size/1024:.1f} KB")

    render_excel.build(DEMO, str(out_xlsx), validate_first=True)
    print("✓", out_xlsx, f"{out_xlsx.stat().st_size/1024:.1f} KB")

    # 同时刷新示例模板（带真实内容的完整模板）
    tpl_html = HERE.parent / "templates" / "dashboard_template.html"
    case = SKILL / "examples" / "示例-甲醇-2026Q4"
    if (case / "index.html").exists():
        import shutil
        shutil.copy(case / "index.html", tpl_html)
        shutil.copy(case / "甲醇-变量观察-2026Q4.xlsx", HERE.parent / "templates" / "case_template.xlsx")
        print("✓ 已同步 dashboard_template.html / case_template.xlsx（甲醇完整案例副本）")


if __name__ == "__main__":
    main()
