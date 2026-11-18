# 示例：甲醇 港口库存连降 + 基差高分位 → 做多 10 个交易日

这是本技能的**完整真实数据**示例：用一条用户指定的规则，走完"规则固化 → 数据时点核实 → 真实合约回测 → 敏感性/样本外 → 报告"全流程。

> ⚠️ 本示例的结论是 **C 不成立 / B 弱证据**，不是"策略有效"。请先读 `FINDINGS.md`。
> 示例的价值在于演示流程与数据缺口的处理方式，而不在于收益数字。

## 快速复现

```bash
# 1. 校验规格
python ../../scripts/run_backtest.py validate --config rule_spec.json

# 2. 跑全套（回测 + 敏感性 + 样本外）
python ../../scripts/run_backtest.py analyze --config rule_spec.json --out out

# 3. 生成 HTML 平台与 Excel 工作簿
python ../../scripts/build_reports.py --config rule_spec.json --out out
```

## 目录

| 文件 | 内容 |
|---|---|
| `rule_spec.json` | 规则规格（唯一事实源，含 provenance） |
| `data/inventory_weekly.csv` | 港口库存周度值 + 原始发布时刻（部分可核验） |
| `data/contracts_daily.csv` | 真实挂牌合约日线（未复权） |
| `data/calendar.csv` | 交易日历 |
| `data/spot_daily.csv` | 华东现货价格 |
| `out/` | 回测产出（HTML / Excel / CSV / JSON） |
| `FINDINGS.md` | 结论与数据缺口说明 |

## 数据时点的关键处理

港口库存周报的**原始发布时刻**在整个样本期内只有一部分可核验：

| 时段 | 可核验 | 处理 |
|---|---|---|
| 2022-04 → 2024-07 | ❌ 数据商回填发布 | strict 模式排除；另跑 assumed 对照 |
| 2024-10 → 2026-10 | ✅ 原文发布时间可核对（周三 13:00–14:33） | 直接使用 |

因此：

- **主结论（strict）**：只用可核验区间，信号事件只发生在 2025 年之后。
- **对照（backfill_assumed）**：对不可核验周假设 14:00 发布，样本更长但含假设。

两种模式的结论**方向不同**，这本身就是本示例最重要的发现——见 `FINDINGS.md`。
