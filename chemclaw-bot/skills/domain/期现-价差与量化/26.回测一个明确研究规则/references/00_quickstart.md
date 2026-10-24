# futures-rule-backtest · 快速开始

5 分钟跑通第一个回测。

## 环境要求

- Python 3.10+
- `pandas`, `numpy`, `openpyxl`（生成 Excel 需要）
- 可选：`pyyaml`（规格用 YAML 时）

```bash
python -c "import pandas, numpy, openpyxl; print('ok')"
```

## 三步跑通

### 1. 校验规格

```bash
python scripts/run_backtest.py validate --config examples/methanol-inventory-basis/rule_spec.json
# VALID  fingerprint=ad5534b3d5dc67c9
```

### 2. 跑全套分析

```bash
python scripts/run_backtest.py analyze \
  --config examples/methanol-inventory-basis/rule_spec.json \
  --out out/
```

产物：`stats.json`, `trades.csv`, `daily_equity.csv`, `signal_alignment.csv`,
`sensitivity.json`, `oos.json`, `cost_sensitivity.csv`

### 3. 生成报告

```bash
python scripts/build_reports.py \
  --config examples/methanol-inventory-basis/rule_spec.json \
  --out out/
```

产物：`research_platform.html`（双击打开）、`backtest_workbook.xlsx`

## 没有数据？用模拟数据先验证引擎

```bash
python examples/make_simulated_example.py --out /tmp/sim
python scripts/run_backtest.py analyze --config /tmp/sim/sim_spec.json --out /tmp/sim/out
python scripts/build_reports.py --config /tmp/sim/sim_spec.json --out /tmp/sim/out
```

⚠️ 模拟数据的产出**必须**标注为"模拟数据，非真实策略收益"。

## 用你自己的规则

1. 复制 `examples/methanol-inventory-basis/rule_spec.json` 为你的规格。
2. 按 `references/01_rule_specification.md` 的清单逐条填。
3. 准备四个 CSV（格式见下）。
4. 校验 → 分析 → 报告。

## 输入文件格式

### 指标文件（`indicator_file`）

| 列 | 必需 | 说明 |
|---|---|---|
| `asof_date` | ✅ | 数据对应的日期（YYYY-MM-DD） |
| `value_wan_ton` 或 `value` | ✅ | 指标数值 |
| `publish_dt_verified` | 推荐 | 原始发布时刻（可空，空 = 不可核验） |

### 合约文件（`contracts_file`）

| 列 | 必需 | 说明 |
|---|---|---|
| `contract` | ✅ | 合约代码（如 MA2609） |
| `delivery_month` | ✅ | 交割月（2026-09 或 26-09） |
| `date` | ✅ | 交易日 |
| `open`, `high`, `low`, `close`, `settle` | ✅ | 价格 |
| `volume`, `open_interest` | ✅ | 用于合约选择 |

### 交易日历（`calendar_file`）

| 列 | 必需 |
|---|---|
| `date` | ✅ |
| `prev_date`, `next_date` | 推荐（缺失时自动派生） |

### 现货文件（`spot_file`）

| 列 | 必需 |
|---|---|
| `date` | ✅ |
| `spot_east_cn`（或按 `price_filter` 配置指定） | ✅ |

## 只跑一部分

```bash
python scripts/run_backtest.py run         --config <spec> --out out/   # 只回测
python scripts/run_backtest.py sensitivity --config <spec> --out out/   # 只敏感性
python scripts/run_backtest.py oos         --config <spec> --out out/   # 只样本外
python scripts/run_backtest.py run --config <spec> --out out2/ --mode backfill_assumed
```

## 跑测试

```bash
python tests/test_engine.py
```

覆盖：未来函数防护、连续下降识别、通道判定、换月与禁交易窗口、成本对账。

## 目录说明

```
SKILL.md               技能总纲与铁律
references/            6 份方法论参考
scripts/frbt/          引擎模块
scripts/run_backtest.py    回测命令
scripts/build_reports.py   报告生成
examples/              真实示例 + 模拟示例
tests/                 单元测试
assets/                下位技能需要的模板拷贝
```

## 常见问题

**Q: 为什么我的信号完全不触发？**
A: 检查 `signal_alignment.csv` 的 `warmup` 列（预热期）与各 op 的 `detail` 列（判定理由）。常见原因是 `min_history` 太大或 `threshold` 单位不对。

**Q: 为什么 `availability_session` 全是 NaT？**
A: strict 模式下，`publish_dt_verified` 为空的行会被排除。检查你的指标文件是否提供了发布时刻。

**Q: 收益和 Excel 里的数对不上？**
A: 检查手数与资金口径。`position.lots` 改变会按比例放大所有金额，但百分比收益只有在名义敞口比例不变时才线性。

**Q: 能跑股票吗？**
A: 本引擎专为期货设计（乘数、保证金、换月、交割窗口）。股票需要另做映射。
