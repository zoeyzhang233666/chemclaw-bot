# 03 · 配置字段参考

一份规格文件就是一次可复现研究的全部输入。下面是每个字段的含义、取值与常见错误。

## meta

| 字段 | 类型 | 说明 |
|---|---|---|
| `rule_id` | str | 唯一标识，建议含品种/条件/持有期 |
| `title` | str | 中文标题 |
| `nl_rule` | str | 用户的原始自然语言表述（原样保留，便于对照） |
| `declared_before_running` | bool | 必须在任何结果产生前设为 true |

## provenance（必填块）

每一项都是 `{basis, value?, note?, source?}`，`basis` 取值：

- `verified` — 已核对交易所/发布方原文
- `assumed_czce_standard` — 交易所标准合约规格（常识性）
- `assumed` — 纯假设（保证金率、费率、滑点）
- `partially_verified` — 部分样本可核验
- `provenance_unverified` — 来源不明

必填键：`contract_spec`, `margin_rate`, `fee_per_lot`, `slippage_ticks`, `tick_size`, `multiplier`, `indicator_publication`。
缺任一键则 `validate` 报错——**假设必须显式声明**。

## universe

| 字段 | 取值 | 说明 |
|---|---|---|
| `exchange` | CZCE / SHFE / DCE / INE / GFEX | 交易所 |
| `product_code` | 如 `MA`、`TA`、`RB` | 品种代码，用于合约代码识别 |
| `direction_mode` | `long` / `short` / `both` | 只做多/只做空/双向 |

## contract

| 字段 | 取值 | 说明 |
|---|---|---|
| `selection` | `kth_by_open_interest` / `front_month` / `fixed_contract` | 合约选择方式 |
| `k` | int ≥1 | 持仓量排名（1 = 主力） |
| `roll_rule` | `open_interest_kth` / `delivery_month_lead` / `none` | 换月规则 |
| `no_trade_window_days_before_delivery` | int | 交割月前多少自然日移出可交易范围 |
| `fixed_contract` | str / null | `selection=fixed_contract` 时使用 |

**注意**：`no_trade_window_days_before_delivery` 是"日历条件"，一旦进入窗口，即使持仓中也会被强制移出——这是有意的，因为临近交割的合约流动性骤降。

## timing

| 字段 | 取值 | 说明 |
|---|---|---|
| `signal_cutoff_same_day` | `"15:00"` | 当日收盘时刻 |
| `indicator_lag_sessions_min` | int ≥0 | 指标发布后至少跳过几个交易日才可交易（1 = 次一交易日） |
| `entry_lag_sessions` | int | 入场滞后（一般与上项一致） |
| `prices` | `open` / `close` / `settle` | 成交通道价格 |
| `same_day_release_price` | `close`/`settle`/null | 若发布早于收盘且允许当日交易，填此值 |
| `spot_availability` | `next_session` | 现货价格可得性 |

## signal

| 字段 | 说明 |
|---|---|
| `indicator` | 指标 id（数据清单中的名称） |
| `combine` | `and` / `or` |
| `min_history` | 预热期（期数），不足不产生信号 |
| `ops[]` | 条件列表，见下 |

`ops[]` 元素：

| type | 参数 | 语义 |
|---|---|---|
| `change_run` | `weeks`, `direction` | 连续 N 期同向 |
| `channel_change` | `n`, `threshold`, `channel_mode`(low/high) | 距近 N 期通道上沿/下沿的幅度 |
| `level` | `cmp`, `threshold` | 与常数比较 |
| `zscore` | `threshold` | z 值阈值 |

每个 op 可带 `label`（中文说明）与 `min_history`（单独预热要求）。

## price_filter

| 字段 | 说明 |
|---|---|
| `enabled` | 是否启用基差过滤 |
| `type` | `pct_quantile` |
| `side` | `above`（高于分位）/ `below` |
| `threshold` | 0–1，如 0.8 |
| `lookback_points` | 回看点数（交易日或周，按数据频率） |
| `basis_mapping` | `spot_minus_fut` / `fut_minus_spot` |
| `warmup_min_points` | 分位可计算的最小样本数 |

## entry / exit / position

| 字段 | 说明 |
|---|---|
| `entry.order_type` | `market_next_open` 等 |
| `entry.reentry_while_holding` | `ignore` / `pyramid` / `restart_holding` |
| `exit.max_hold_sessions` | 最大持有交易日 |
| `exit.take_profit_pct` | 止盈（相对价格变动），null = 不设 |
| `exit.stop_loss_pct` | 止损，null = 不设 |
| `exit.exit_on_roll_when_contract_changes` | 换月时是否平仓（false 则移仓） |
| `position.sizing` | `fixed_lots` / `pct_equity_notional` / `pct_equity_margin` |
| `position.lots` / `capital` / `max_lots` | 手数与资金口径 |
| `position.max_margin_utilisation` | 保证金占用上限 |

## costs

| 字段 | 说明 |
|---|---|
| `fee_mode` | `per_lot` / `pct_notional` |
| `fee_value` | 每手费率或比例 |
| `commission_min_per_lot` | 最低每手手续费 |
| `slippage_ticks` | 单边滑点（跳数） |
| `tick_size`, `multiplier`, `margin_rate` | 合约与保证金参数 |

换月 = 平旧 + 开新，**两笔**手续费与滑点。

## data

| 字段 | 说明 |
|---|---|
| `indicator_file` | 指标 CSV（含 `asof_date`, `value_wan_ton` 或 `value`, `publish_dt_verified`） |
| `contracts_file` | 合约日线 CSV |
| `calendar_file` | 交易日历 |
| `spot_file` | 现货序列 |
| `publication_mode` | `strict` / `backfill_assumed` |
| `assumed_publish_time` | `backfill_assumed` 模式的假设时刻 |

## analysis

| 字段 | 说明 |
|---|---|
| `metrics.rf_annual` | 无风险利率（年化） |
| `metrics.sessions_per_year` | 年化交易日数（默认 244） |
| `sensitivity.*` | 预先声明的网格取值 |
| `oos.split_date` | 样本内/外切分日（运行前声明） |

## 校验

```bash
python scripts/run_backtest.py validate --config configs/x.json
```

输出 `VALID fingerprint=<hash>` 或错误列表。`fingerprint` 是规格内容的 SHA-256 前 16 位，用于版本对比。

## 最常见的五个配置错误

1. `lookback_points` 填了"3 年"这个数字 3 而不是 756。
2. `indicator` 字段指向不存在的列名。
3. `threshold` 忘了单位，0.25 到底是 0.25 万吨还是 25%。
4. `no_trade_window_days_before_delivery` 设为 0，导致持有到交割月。
5. `costs.multiplier` 与 `provenance.multiplier` 不一致。
