# 装置停车事件研究（unit-outage-event-study）

给化工研究/期现团队的一套**可审计**的装置停车事件研究工具：把一次停车钉到明确的事件日，
算事件前后与之后 1/5/10/20 个交易日的价格路径、分布，以及相对板块基准的异常收益。

## 30 秒上手

```bash
# ① 自检（不需要网络，验证换月复权等核心算法）
python scripts/selftest.py

# ② 复现完整案例（甲醇 2026）
python scripts/build_all.py examples/methanol-outage-2026 --benchmark market_model
```

产出在 `examples/methanol-outage-2026/output/`：
- `甲醇装置停车事件研究_2026_报告.html`（单文件交互报告）
- `甲醇装置停车事件研究_2026_工作簿.xlsx`（11 张表）

## 自己的品种怎么用

```
你的项目目录/
├── events.csv            ← 事件表（三种日期、产能、证据、原文）
├── project.json          ← 口径配置（标题、品种、阈值、免责声明）
├── data/
│   ├── raw_contracts/MA/ ← 逐合约日线 JSON（或直接给 prices.csv）
│   ├── prices.csv        ← 主力连续（后向复权）
│   ├── benchmark.csv     ← 基准（可选；没有就不算异常收益）
│   └── spot.csv          ← 现货（可选；没有就留空基差）
└── output/               ← 产物
```

```bash
python scripts/build_event_table.py --project <你的项目> --out <项目>/output/事件样本确认表.html
#  ↑ 先让用户确认样本，再往下走
python scripts/build_all.py <你的项目> --benchmark market_model
```

## 三条硬规则

1. **先确认样本，再出结论**：未经确认只能出“演示版”，且必须在文件名、首屏、图表标题、Excel 首行同时标注。
2. **缺数据就留空**：现货取不到就写“缺失”，不插值、不倒推、不前向填充。
3. **不说因果**：事件窗口内的涨跌 ≠ 停车导致；同期成本、宏观、下游开工、地缘都是竞争性解释。

## 目录

```
unit-outage-event-study/
├── SKILL.md                    技能入口（给 Agent 读的流程）
├── references/                 9 份方法文档
│   ├── 01-event-taxonomy.md    事件分类与三种日期
│   ├── 02-event-table-spec.md  事件表字段与校验
│   ├── 03-screening-and-dedup.md 阈值与去重
│   ├── 04-method.md            对齐/窗口/基准/统计
│   ├── 05-data-sources.md      数据源与覆盖边界
│   ├── 06-report-spec.md       报告与工作簿规范
│   ├── 07-confirmation-protocol.md 确认话术与演示标记
│   ├── 08-qa-checklist.md      交付前检查
│   └── 09-no-causation-policy.md 因果边界
├── scripts/
│   ├── core.py                 事件读写/日历/去重/统计
│   ├── build_prices.py         主力连续 + 换月后向复权
│   ├── build_benchmark.py      等权化工期货指数
│   ├── eventstudy.py           事件对齐与异常收益
│   ├── build_event_table.py    待确认样本表
│   ├── build_html.py           交互报告
│   ├── build_excel.py          11 表工作簿
│   ├── build_all.py            一键流水线
│   ├── check_report.py         交付自检
│   └── selftest.py             算法自检（离线）
├── assets/
│   ├── echarts.min.js          内联图表库（离线可开）
│   └── templates/
└── examples/methanol-outage-2026/  完整真实案例
```

## 核心算法说明：换月复权

主力连续在换月日会把两个不同合约的价格直接相连，产生并非真实成交的跳空。
若事件窗口跨换月，这段假跳空会被算进收益。

本工具的复权口径（panama 比率法）：
- **段内**（同一合约）：相邻日收益 == 真实收益；
- **换月日**：跳空归零（换月价差不被当作涨跌）；
- **最新一天**：价格 == 真实成交价（不缩放）。

`scripts/selftest.py` 用合成数据逐项验证这三条（实测 25 次换月，最大残留 0.0000%）。

## 依赖

- Python 3.9+，**标准库即可**运行全部计算脚本
- `openpyxl` 仅用于生成 Excel
- 不需要联网（`echarts.min.js` 已内联；数据已落地在 `raw_contracts/`）
