# 数据契约

四个文件在流水线上传递数据。所有 JSON 均为 **UTF-8 无 BOM**。

```
case.json ──┐
            ├─ run_case.py ──> scenario.json ──┬─ build_html.py  ──> *.html
fx_series.json ┘                                └─ build_xlsx.py  ──> *.xlsx
```

---

## 1. `case.json` —— 一笔业务的输入

由使用者填写（或由上游系统生成）。最小可用示例：

```json
{
  "case_id": "01-export-soda-ash-usd",
  "meta": {
    "title": "重质纯碱 10 万美元出口 · 汇率风险测算",
    "product": "重质纯碱",
    "spec": "Dense Soda Ash, Na2CO3 ≥ 99.2%",
    "direction": "export",
    "currency": "USD",
    "amount_fx": 100000,
    "trade_date": "2026-10-19",
    "settle_date": "2027-01-17",
    "cny_cost": 600000,
    "target_margin_pct": 0.10,
    "toll_rate": 0,
    "bank_band_pct": 0.0025,
    "rate_mode": "auto",
    "shifts": [-0.05, -0.03, -0.02, -0.01, 0, 0.01, 0.02, 0.03, 0.05],
    "simulated_fields": ["cny_cost", "settle_date", "batches_alt"]
  },
  "batches": []
}
```

### `meta` 字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | string | ✅ | 显示标题 |
| `product` / `spec` | string | ✅ | 产品名与规格 |
| `direction` | `"export"` \| `"import"` | ✅ | 决定整套公式的符号 |
| `currency` | string | ✅ | ISO 代码；日元写 `100JPY` |
| `amount_fx` | number | ✅ | 外币金额 |
| `trade_date` | `YYYY-MM-DD` | ✅ | 交易日 / 报价日 |
| `settle_date` | `YYYY-MM-DD` | ✅ | 预计结算日 |
| `cny_cost` | number | 出口必填 | 出口的人民币成本 |
| `resale_cny` | number | 进口必填 | 进口后的人民币销售收入 |
| `target_margin_pct` | number | 可选 | 目标毛利率，小数（0.10 = 10%） |
| `target_margin_cny` | number | 可选 | 目标毛利额（元） |
| `toll_rate` | number | 可选 | 银行费用率，默认 0 |
| `bank_band_pct` | number | 可选 | 单侧点差带，默认 0.0025 |
| `rate_mode` | `"auto"` \| `"mid"` \| `"mid_x_band"` \| `"actual"` | 可选 | 基准汇率取哪个口径 |
| `actual_bank_rate` | number | 可选 | 银行实际成交价，给了就用 |
| `shifts` | number[] | 可选 | 敏感性档位，默认 ±1/2/3/5% |
| `simulated_fields` | string[] | ✅ | **列出所有模拟字段**，会写进交付物 |

### `batches`

分批结算方案。空数组表示用 `batches_alt` 的示例方案。

```json
"batches": [
  {"label": "T/T 30% 定金", "amount_fx": 30000, "days": 0,  "rate": 6.703998},
  {"label": "装运后 60 天 40%", "amount_fx": 40000, "days": 60, "rate": 6.703998},
  {"label": "提单日 90 天 30%", "amount_fx": 30000, "days": 90, "rate": 6.703998}
]
```

`rate` 是该批次的**假设汇率**（不是预测）。各批合计应等于 `amount_fx`，校验脚本会检查。

---

## 2. `fx_series.json` —— 汇率历史序列

由 `build_fx_series.py` 从 SAFE 原始数据生成，跨案例复用。

```json
{
  "meta": {
    "first_date": "2023-10-09",
    "last_date": "2026-10-19",
    "trading_days": 735,
    "base_unit": "CNY per 1 unit of foreign currency; JPY per 100"
  },
  "dates": ["2023-10-09", "2023-10-10", ...],
  "currency_list": [
    {"code": "USD", "name_cn": "美元", "unit": 1},
    {"code": "JPY", "name_cn": "日元", "unit": 100}
  ],
  "currencies": {
    "USD": {"code": "USD", "unit": 1, "values": {"2023-10-09": 7.1xx, ...}}
  },
  "sources": [ {...} ],
  "quality": {
    "duplicates": 0,
    "missing_weekdays": 56,
    "max_daily_jump_pct": 0.00938
  }
}
```

**关键约定**

- `values` 的键是日期，值是"1 单位外币 = X 人民币"（日元按 100）；
- **缺失的日期就是缺失**，不出现在 `values` 里。任何消费方都必须能处理 `undefined`，**不允许插值**；
- `unit` 字段记录该币种的口径倍数，JPY 为 100。

支持 25 个币种：USD EUR JPY HKD GBP AUD NZD SGD CHF CAD MOP MYR RUB ZAR KRW AED SAR HUF PLN DKK SEK NOK TRY MXN THB。

---

## 3. `scenario.json` —— 计算结果（中间产物）

由 `run_case.py` 生成，是 HTML 与 Excel 的唯一数据源。

```json
{
  "ok": true,
  "errors": [],
  "warnings": [],
  "meta": { ...case.meta 的补充... },
  "rate": {
    "mid": 6.7208,
    "band": 0.0025,
    "basis": "mid_x_band_estimate",
    "base_rate": 6.703998,
    "actual_bank_rate": null,
    "contract_rate": null
  },
  "stats": {
    "1y": {"n": 242, "min": ..., "max": ..., "mean": ..., "pctile_mid": 0.0021, ...},
    "3y": {"n": 725, ...}
  },
  "base": {
    "direction": "export", "rate": 6.703998, "amount_fx": 100000,
    "gross_cny": 670399.8, "toll_cny": 0,
    "net_cny": 670399.8, "revenue_cny": 670399.8,
    "cost_cny": 600000, "margin_cny": 70399.8, "margin_pct": 0.105012
  },
  "one_pct_cny": 6704,
  "sensitivity": [
    {"shift": -0.05, "rate": 6.368798, "gross_cny": ..., "net_cny": ...,
     "delta_cny": -33519.99, "delta_pct_of_base": -0.05,
     "margin_cny": 36879.81, "margin_pct": 0.057907}
  ],
  "margin_curve": [ {"rate": ..., "margin_cny": ...} ],
  "breakevens": {
    "zero": {"breakeven": 6.0, "distance_pct": -0.105},
    "target_pct": {"breakeven": 6.666667, "distance_pct": -0.0056}
  },
  "batch": null,
  "series": [ {"date": "...", "value": ...} ],
  "sources": [ ... ]
}
```

**消费方约定**：`ok: false` 时不要渲染，直接把 `errors` 显示给用户。

---

## 4. `visual_audit.json` / `qa.json` —— 校验产物

| 文件 | 生成者 | 用途 |
|---|---|---|
| `qa.json` | `qa_render.mjs` | 37 项渲染与交互检查结果 |
| `visual_audit.json` | `visual_audit.mjs` | 重叠 / 截断 / 对比度 / 字号 |

CI 里应把这两个文件归档，作为"这份交付物当时验证过"的证据。

---

## 5. 字段改名对照（易踩）

| 我可能想写 | 实际字段 |
|---|---|
| `drawdown` | `stats.1y.drawdown_from_max_pct` |
| `range_width` | `stats.1y.range_width_pct` |
| `upside` | `stats.1y.upside_to_max_pct`（注意语义是"距最高"） |
| `percentile` | `stats.1y.pctile_mid`（含 0.5 加权） |
| `vol` | `stats.1y.vol_annual` |

改字段名时同步改：`run_case.py`、`build_html.py`、`build_xlsx.py`、`verify_*.py`。**这五处必须一起改**，否则会出现"页面正常但 Excel 出错"的情况。
