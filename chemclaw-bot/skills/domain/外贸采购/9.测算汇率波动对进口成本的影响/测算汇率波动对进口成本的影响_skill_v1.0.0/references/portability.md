# 换币种 / 换商品 / 换合同条款的操作步骤

本 Skill 的核心参数**全部来自 `input.json`**，没有任何硬编码的 USD/CNY 或固定付款条件。换场景只需改输入文件，不需要改代码。

---

## 1. 换币种

### 1.1 支持哪些

历史数据 `data/fx_real_data.json` 内置：
`USD` `EUR` `GBP` `JPY` `SGD` `AUD` `KRW` `INR` `HKD` → CNY，另加 `SAR`（USD/CNY × 3.75 挂钩折算）。

### 1.2 操作

```json
{
  "foreign_currency": "EUR",
  "pair": "EUR/CNY",
  "quote_direction": "FC_CNY",
  "amount_fc": 500000
}
```

`rates` 里的四个值也换成 EUR/CNY 口径（ECB 直报，无需交叉折算）。

### 1.3 没有历史数据的币种怎么办

**不得伪造序列。** 处理方式：

1. 只做当前汇率 + 敏感性 + 到厂成本，**跳过历史分位**，输出中标注“该币种暂无公开日频序列，未提供分位”；
2. 或由用户提供可靠来源的序列，按 `{"daily": {"XXXCNY": [["YYYY-MM-DD", 值], ...]}}` 结构加入数据文件，并注明来源。

### 1.4 交叉折算币种（如 SAR）

ECB 不发布 SAR，需经 USD 折算：

```
SAR/CNY = USD/CNY × (1 / 3.75)      # SAMA 官方挂钩 3.75
```

若有 CFETS 直报的 `CNY/SAR`，**优先用直报值**（`SAR/CNY = 1 / CNY_SAR`），并在报告中说明来源差异。

案例实测：折算 `6.7200 / 3.75 = 1.7920`；CFETS 直报 `1 / 0.56010 = 1.78540`；差 0.37%，采用直报值。

---

## 2. 换商品（主要影响税率与规格）

商品差异体现在 `costs` 与 `product` 两处：

```json
"product": {
  "name": "工业级乙二醇（MEG）",
  "spec": "聚酯级 ≥99.9%",
  "hs_code": "2905310000",
  "origin": "沙特阿拉伯（Jubail）",
  "incoterm": "CFR 华东主港"
},
"costs": {
  "duty_rate": 5.5,
  "cdc_rate": 0,
  "vat_rate": 13,
  "vat_mode": "deductible"
}
```

### 2.1 换商品时必须重新核实的四件事

| # | 事项 | 为什么 |
|---|---|---|
| 1 | **HS 编码与最惠国税率** | 关税率直接决定税基放大比例 |
| 2 | **是否有进口暂定税率** | 暂定税率优先于最惠国税率 |
| 3 | **是否征消费税** | 成品油、烟酒、小汽车等从价/从量计征 |
| 4 | **增值税率** | 多数货物 13%，部分农产品/图书 9% |

### 2.2 常见化工品税率参考（**使用时必须复核**）

| 商品 | HS | 最惠国税率 | 增值税 | 消费税 |
|---|---|---|---|---|
| 乙二醇（MEG） | 2905310000 | 5.5% | 13% | 0 |
| 甲醇 | 2905110000 | 5.5% | 13% | 0 |
| 纯碱 | 2836200000 | 5.5% | 13% | 0 |
| 钛白粉 | 3206111000 | 6.5% | 13% | 0 |

> 上表仅供起点参考。**税率每年调整，必须以当年《中华人民共和国进出口税则》及海关总署公告为准。** 本 Skill 不做税则判断。

### 2.3 反倾销/反补贴

若该商品存在贸易救济措施（如原产于某国的 MEG、PVC 等曾被调查），需在 `duty_rate` 之外另计，或把综合税率填入 `duty_rate`。**本 Skill 不自动判断是否适用**，需人工确认后在 `product` 备注中说明。

---

## 3. 换合同条款

### 3.1 换贸易术语（Incoterms）

| 术语 | `freight_fc` | `insurance_fc` | 说明 |
|---|---|---|---|
| FOB | 填实际运费 | 填实际保费 | 运保费由买方承担，进成本 |
| CFR | 0 | 填实际保费 | 运费已含在货价中 |
| CIF | 0 | 0 | 运保费均已含在货价中 |
| EXW | 填全部 | 填全部 | 买方承担最多 |

> **关键**：选 CFR/CIF 时，`amount_fc` 已包含运费，此时 `freight_fc` 必须填 0，否则**重复计费**。

### 3.2 换付款条件

```json
"payment": {
  "payment_date": "2027-03-15",
  "term": "T/T 120 days after B/L",
  "tranches": [
    {"name": "预付款 20%", "ratio": 0.20, "days": -90},
    {"name": "到港付款 40%", "ratio": 0.40, "days": 30},
    {"name": "尾款 40%", "ratio": 0.40, "days": 90}
  ]
}
```

规则：
- `ratio` 之和必须 = 1.0（或 100），否则报错；
- 批次数不限；
- `days` 相对 `payment_date` 计算结算日；
- 某批填 `locked_rate` 后，该批在情景矩阵中固定。

### 3.3 换基准口径

```json
"rates": { "basis": "pboc" }
```

- `bank`：算实付人民币（**推荐**）
- `pboc`：算官方口径参照
- `market`：算国际视角
- `customs`：算税款基准

---

## 4. 换到厂费用结构

按实际费用逐项填写，**人民币项与外币项必须分清**：

```json
"costs": {
  "freight_fc": 18000,
  "insurance_fc": 3200,
  "other_fc": 0,

  "cny_port": 42000,
  "cny_customs_agent": 15000,
  "cny_inland": 31000,
  "cny_storage": 12000,
  "cny_bank_fee": 8500,
  "cny_other": 4000,

  "duty_rate": 5.5,
  "cdc_rate": 0,
  "vat_rate": 13,
  "vat_mode": "deductible"
}
```

判断标准：**合同或发票上以外币计价的 → 外币项；以人民币计价的 → 人民币项。**

---

## 5. 换用途：只算付款额

用户只给了采购金额、没有售价与成本结构时：

```json
{
  "foreign_currency": "USD",
  "amount_fc": 800000,
  "quote_direction": "FC_CNY",
  "rates": { "market": ..., "pboc": ..., "bank": ..., "basis": "bank" }
}
```

**不填 `costs`、不填 `sales`。** 引擎会自动：

- 输出人民币付款额与 ±1/3/5% 敏感性；
- 输出四口径对照；
- **跳过**到厂成本、毛利、盈亏平衡模块；
- 在 `missing` 中记录“未提供成本参数，未计算到厂成本”等说明。

> 这对应硬性边界第 5 条：只有金额时只算付款额，不凭空假设利润。

---

## 6. 移植检查清单

换任何场景后，确认这 8 项：

- [ ] `foreign_currency` 与 `pair` 一致
- [ ] `quote_direction` 与实际报价方向一致（`FC_CNY` / `CNY_FC`）
- [ ] `rates.basis` 指定了正确的基准口径，且该口径有值
- [ ] 外币项与人民币项没有填错位置
- [ ] `duty_rate` / `vat_rate` 是**百分数**（5.5 而非 0.055）
- [ ] `vat_mode` 与纳税人身份匹配
- [ ] `sales.price_cny` 若为模拟值，`price_note` 已注明
- [ ] 分批 `ratio` 之和 = 100%

然后跑：

```bash
python scripts/fx_engine.py input.json --history data/fx_real_data.json -o result.json
```

看 `result.json` 的 `warnings` 和 `missing` 是否为空或可接受。
