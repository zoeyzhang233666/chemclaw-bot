# 26 · 回测一个明确研究规则

把一条自然语言写下的期货研究规则，变成**可复核、可复现、诚实披露数据缺口**的回测研究。

> 本目录是一个**完整交付包**：既是可执行的方法技能（Skill），也包含一份用真实数据跑通的完整示例。

## 先看这两个文件

| 文件 | 作用 |
|---|---|
| [SKILL.md](SKILL.md) | 技能总纲：七条铁律、四步流程、产出物、常见失败模式 |
| [examples/methanol-inventory-basis/FINDINGS.md](examples/methanol-inventory-basis/FINDINGS.md) | 真实示例的**结论页**（结论是"D 数据不足 / C 不成立"，不是"策略有效"） |

## 直接打开成果

- **交互式研究工作台**：[examples/methanol-inventory-basis/out/research_platform.html](examples/methanol-inventory-basis/out/research_platform.html)
  单文件、离线可开。含权益曲线、回撤曲线、逐笔成交筛选、信号时点对齐审计、参数敏感性热力表、样本外对比、风险与数据缺口页。
- **可复核工作簿**：[examples/methanol-inventory-basis/out/backtest_workbook.xlsx](examples/methanol-inventory-basis/out/backtest_workbook.xlsx)
  11 张表；`06_Daily_Equity` 的收益与回撤是**活公式**，改动权益数字会自动重算。

## 示例规则

> 甲醇港口库存连续两周下降，且甲醇基差高于过去 3 年滚动 80% 分位时，
> 在信号可获得后的下一交易日建立甲醇期货多头，持有 10 个交易日。

### 示例结论（摘要）

| 口径 | 笔数 | 累计收益 | 最大回撤 | 胜率 | 盈亏比 |
|---|---|---|---|---|---|
| strict（仅可核验发布时刻） | 9 | +1.47% | −1.94% | 44.4% | 1.48 |
| backfill_assumed（含假设时刻） | 16 | **−0.80%** | −3.52% | 31.3% | 0.84 |

- 参数敏感性：21 个变体，基准排名 3/21，正收益占比 84%
- 样本外（2025-07 起）：7 笔，+1.91%；样本内仅 2 笔
- 块自助检验：P(均值>0) = **0.705**；2026 年单年贡献 132%

**判断：D 数据不足 / C 不成立。两种数据时点口径结论方向相反，说明结果主要由假设驱动。历史回测不代表未来收益。**

## 目录结构

```
26.回测一个明确研究规则/
├── README.md                        本文件
├── SKILL.md                         技能总纲（铁律 / 流程 / 分级）
├── references/                      6 份方法论参照
│   ├── 00_quickstart.md             5 分钟跑通
│   ├── 01_rule_specification.md     自然语言 → 显式规格
│   ├── 02_lookahead_and_timing.md   无未来函数：时点核实清单
│   ├── 03_config_reference.md       配置字段全表
│   ├── 04_contracts_and_costs.md    真实合约、换月、成本
│   ├── 05_robustness_and_conclusion.md  敏感性/样本外/结论分级
│   └── 06_reporting_and_deliverables.md 报告规范
├── scripts/
│   ├── run_backtest.py              validate / run / sensitivity / oos / analyze
│   ├── build_reports.py             生成 HTML + Excel
│   └── frbt/                        引擎模块（商品无关，配置驱动）
├── examples/
│   ├── methanol-inventory-basis/    真实数据完整示例
│   │   ├── rule_spec.json           规则规格 + 假设溯源
│   │   ├── data/                    库存 / 合约 / 日历 / 现货
│   │   ├── out/                     HTML + Excel + 全部 CSV/JSON
│   │   └── FINDINGS.md              结论页
│   └── simulated_demo/              模拟数据示例（用于验引擎，不得当业绩）
├── configs/                         可复用配置模板
└── tests/test_engine.py             8 项单元测试
```

## 复现

```bash
# 完整示例
cd examples/methanol-inventory-basis
python ../../scripts/run_backtest.py validate --config rule_spec.json
python ../../scripts/run_backtest.py analyze  --config rule_spec.json --out out
python ../../scripts/build_reports.py        --config rule_spec.json --out out
```

已验证：从零重跑得到与 FINDINGS 完全一致的数字（trades=9, +1.4695%, MDD −1.9412%, 胜率 44.44%, PF 1.4760）。

## 这个技能明确不做

- 不自动搜索最赚钱的参数组合
- 不把回测结果表述为未来收益保证
- 不生成对外发布的交易信号或评级
- 不接实盘、不下单
- 数据不可得时展示缺口，不编造

## 适用与不适用

**适用**：指定了触发条件与持有期的期货/商品研究规则；需要核实"有没有用未来数据"；需要把结果交给别人复核。

**不适用**：需要毫秒级撮合仿真的高频策略；期权组合；股票/ETF（引擎针对期货的乘数、保证金、换月、交割窗口设计）。
