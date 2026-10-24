# -*- coding: utf-8 -*-
"""audit_html.py —— 成品 HTML 的最终审计：外链、禁用词、声明、占位符"""
import re
import sys

p = sys.argv[1]
h = open(p, encoding="utf-8").read()
print("文件大小 MB:", round(len(h.encode()) / 1048576, 2))

ext = re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', h)
print("外链数量:", len(ext))
for e in ext[:8]:
    print("   ", e)

FORBIDDEN = ["预计将上涨", "预计将下跌", "看跌", "看涨", "大概率会", "建议锁汇", "推荐远期",
             "推荐期权", "必涨", "必跌", "应该锁汇", "肯定会上涨", "肯定会下跌", "稳赚"]
hits = [w for w in FORBIDDEN if w in h]
print("禁用词命中:", hits if hits else "无 ✓")

checks = {
    "含「不预测汇率走势」声明": "不预测汇率走势" in h,
    "含 SAFE 官方来源链接": "safe.gov.cn" in h,
    "含「模拟」标签样式": "bt mock" in h or "模拟" in h,
    "含「真实」标签样式": "bt real" in h,
    "含未计入因素（手续费）": "手续费" in h,
    "含未计入因素（远期）": "远期" in h,
    "含未计入因素（点差）": "点差" in h,
    "含平衡汇率": "平衡汇率" in h,
    "含历史分位": "分位" in h,
    "无未替换占位符": not [m for m in re.findall(r"__[A-Z]{3,}__", h)
                        if m not in ("__COMPONENT__", "__READY__")],
    "ECharts 已内联": "echarts" in h.lower(),
    "含数据截至日期": "2026-10-19" in h,
}
for k, v in checks.items():
    print(("[PASS] " if v else "[FAIL] ") + k)

sys.exit(0 if all(checks.values()) and not hits else 1)
