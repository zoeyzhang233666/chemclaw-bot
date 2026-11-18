# 输入参数说明

所有参数通过一个 JSON 文件传入。**必填项缺失时引擎会明确报错或跳过对应模块，不会用默认值悄悄顶替。**

---

## 1. 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `foreign_currency` | string | ✔ | 合同结算币种代码，如 `USD`、`EUR`、`SAR`、`JPY` |
| `local_currency` | string | | 本币，默认 `CNY` |
| `pair` | string | | 汇率对写法，如 `USD/CNY`；缺省由币种自动拼 |
| `quote_direction` | string | ✔ | **`FC_CNY`**（1 外币 = X 人民币）或 `CNY_FC`（1 人民币 = X 外币）。默认 `FC_CNY`，但强烈建议显式写。 |
| `direction` | string | | `IMPORT_PAYMENT`（进口付汇，默认）/ `IMPORT_RECEIPT` |
| `amount_fc` | number | ✔ | 合同外币金额 |
| `quantity` | number | 条件 | 合同数量（吨/千克等），算单位成本与毛利时必填 |
| `budget_rate` | number | | 预算/内部核算汇率（`FC_CNY`），填了会额外算一档“预算汇率情景” |
| `history_windows` | array | | 历史区间（年），默认 `[1, 3, 5]` |

```json
{
  "foreign_currency": "USD",
  "local_currency": "CNY",
  "pair": "USD/CNY",
  "quote_direction": "FC_CNY",
  "direction": "IMPORT_PAYMENT",
  "amount_fc": 1000000,
  "quantity": 1136.4,
  "budget_rate": 6.80
}
```

---

## 2. `rates` — 四类汇率

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `market` | number | | 市场汇率（ECB/ER-API 等） |
| `pboc` | number | | 人民币汇率中间价（CFETS 9:15） |
| `bank` | number | 强烈建议 | **银行现汇卖出价**。缺失时降级到 `pboc`，并产生告警 |
| `customs` | number | 建议 | 海关计征汇率。缺失时回退到基准汇率并打 `customs_rate_fallback` |
| `basis` | string | ✔ | 计算基准口径：`bank` / `pboc` / `market` / `customs` |
| `as_of` | object | | 各口径的取值时点与来源，用于报告展示 |

```json
"rates": {
  "market":  6.6807, "market_source": "ECB 欧元参考汇率（经 EUR 交叉折算）", "market_date": "2026-10-19",
  "pboc":    6.7200, "pboc_source":   "CFETS/中国人民银行中间价",            "pboc_date":   "2026-10-20 09:15",
  "bank":    6.7435, "bank_source":   "演示：中间价 +35bp（须以成交日银行牌价替换）", "bank_date": "2026-10-19",
  "customs": 6.7200, "customs_source":"演示：按海关总署令272号第十三条",      "customs_date":"2026-09-16",
  "basis": "bank"
}
```

**基准口径优先级**：`bank` > `pboc` > `market`。若 `basis` 指定的口径缺失，引擎回退并在 `warnings` 中记录。

---

## 3. `costs` — 到厂成本参数

### 3.1 外币计价的费用（会随汇率变动）

| 字段 | 单位 | 说明 |
|---|---|---|
| `freight_fc` | 外币 | 国际运费（FOB 成交时填，CFR/CIF 时填 0） |
| `insurance_fc` | 外币 | 保险费（CIF 成交时填 0） |
| `other_fc` | 外币 | 其他外币费用 |

### 3.2 人民币计价的费用（**不随汇率变动**）

| 字段 | 单位 | 案例值 |
|---|---|---|
| `cny_freight` | 元 | — |
| `cny_port` | 元 | 38,000（港杂费） |
| `cny_customs_agent` | 元 | 12,000（报关代理费） |
| `cny_inland` | 元 | 26,000（内陆运输费） |
| `cny_storage` | 元 | 9,000（仓储及其他） |
| `cny_bank_fee` | 元 | 6,800（银行手续费及汇兑费用） |
| `cny_other` | 元 | — |

> 这一组务必只填**人民币固定金额**。若误把外币金额填进来，敏感性会被错误放大。

### 3.3 税费

| 字段 | 单位 | 案例值 | 说明 |
|---|---|---|---|
| `duty_rate` | **百分数**（5.5 表示 5.5%） | 5.5 | 最惠国税率 |
| `cdc_rate` | 百分数 | 0 | 消费税（从价） |
| `vat_rate` | 百分数 | 13 | 进口增值税率 |
| `vat_mode` | string | `deductible` | `deductible`（可抵扣，不计入成本）/ `cost`（不可抵扣，计入成本） |

```json
"costs": {
  "cny_port": 38000, "cny_customs_agent": 12000, "cny_inland": 26000,
  "cny_storage": 9000, "cny_bank_fee": 6800,
  "duty_rate": 5.5, "cdc_rate": 0, "vat_rate": 13, "vat_mode": "deductible",
  "freight_fc": 0, "insurance_fc": 0
}
```

---

## 4. `sales` — 国内销售与毛利（可选）

**整块可选。不填则跳过毛利与盈亏平衡模块——这是刻意的设计：没有售价就不该算利润。**

| 字段 | 单位 | 说明 |
|---|---|---|
| `price_cny` | 元/吨 | 国内销售价。**若非用户提供，须标注“模拟”** |
| `other_cost_cny_unit` | 元/吨 | 非汇率相关单位成本（仓储、销售费用、资金占用等） |
| `revenue_basis` | string | `tax_included`（含税，默认）/ `tax_excluded` |
| `target_margins_pct` | array | 目标毛利率（百分数），用于盈亏平衡，如 `[0, 5, 10]` |
| `price_note` | string | 售价来源说明，会显示在输出中 |
| `other_cost_note` | string | 非汇率成本说明 |

```json
"sales": {
  "price_cny": 7600,
  "price_note": "模拟值：仅为演示毛利模块，须替换为实际销售价",
  "other_cost_cny_unit": 260,
  "revenue_basis": "tax_included",
  "target_margins_pct": [0, 5, 10]
}
```

---

## 5. `payment` — 付款与分批

| 字段 | 类型 | 说明 |
|---|---|---|
| `payment_date` | string | 计划付款日 `YYYY-MM-DD` |
| `term` | string | 付款条件，如 `T/T 90 days after B/L` |
| `tranches` | array | 分批定义，见下 |
| `scenario_pct` | array | 情景变动率，如 `[0, 1, 3, 5, -1, -3, -5]` |

### `tranches[]`

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 批次名，如 `预付款`、`尾款` |
| `ratio` | number | 比例（0–1 小数，或百分数——引擎自动识别） |
| `days` | number | 相对基准日的天数（负数为提前） |
| `date` | string | 也可直接给日期 |
| `locked_rate` | number | 已锁汇率（可选）。填了该批在情景矩阵中不再变化 |

**校验**：所有 `ratio` 之和必须为 100%（±0.0001 容差），否则报错。

```json
"payment": {
  "payment_date": "2027-01-18",
  "term": "T/T 90 days after B/L",
  "tranches": [
    {"name": "预付款 30%", "ratio": 0.30, "days": -60},
    {"name": "尾款 70%",   "ratio": 0.70, "days": 0}
  ],
  "scenario_pct": [0, 1, 3, 5, -1, -3, -5]
}
```

---

## 6. `meta` / `product` — 展示用信息

| 字段 | 说明 |
|---|---|
| `product.name` | 品名，如 `工业级乙二醇（MEG）` |
| `product.spec` | 规格，如 `聚酯级 ≥99.9%` |
| `product.hs_code` | HS 编码，如 `2905310000` |
| `product.origin` | 原产地，如 `沙特阿拉伯（Jubail）` |
| `product.incoterm` | 贸易术语，如 `CFR 华东主港` |
| `meta.title` | 报告标题 |
| `meta.prepared_for` | 使用方 |

这些字段只影响 HTML/Excel 的展示文案，不参与计算。

---

## 7. 校验规则汇总

| 规则 | 行为 |
|---|---|
| `amount_fc` 缺失或 ≤ 0 | 报错终止 |
| `quote_direction` 不合法 | 报错终止 |
| `basis` 指定的口径无值 | 回退并写 `warnings` |
| `bank` 缺失 | 回退到 `pboc`，写告警“银行购汇价缺失，实付人民币可能被低估” |
| `customs` 缺失 | 回退到基准汇率，打 `customs_rate_fallback: true` |
| 分批比例之和 ≠ 100% | 报错终止 |
| `sales` 缺 `price_cny` 或 `quantity` | 跳过毛利模块，写入 `missing` |
| `duty_rate` 等税率 > 100 | 告警（不终止，允许特殊情形） |

所有告警与缺失项都会出现在 `result.json` 的 `warnings` / `missing` 字段，并在 HTML/Excel 中可见——**不做静默处理**。
