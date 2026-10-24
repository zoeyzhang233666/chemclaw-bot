# 数据契约：input.json / result.json 字段规范

> 填 `input.json` 是使用本技能的核心动作。**只填原始数据，不填结果**（结果由 `cost_engine.py` 算）。
> 完整模板见 `examples/input.template.json`；可用 `python scripts/validate.py input.json` 自检。

## 1. `meta`（必填）

| 字段 | 必填 | 说明 |
|---|---|---|
| `product` | ✅ | 产品全称 + 常用名 + CAS，例：`DOP（邻苯二甲酸二辛酯 / DEHP，CAS 117-81-7）` |
| `product_cas` | | CAS 号 |
| `product_formula` | | 分子式（用于理论单耗校验） |
| `product_short` | | 简称，用于图表标签（≤6 字） |
| `as_of` | ✅ | 数据截止日 `YYYY-MM-DD`（不是写作日） |
| `region` | | 区域口径说明 |
| `buyer` | | 采购方/视角，例：`华东增塑剂厂 · 采购部` |
| `process_id` / `process_name` / `process_desc` | | 工艺标识与说明 |
| `reaction` | | 反应式，例：`C8H4O3 + 2 C8H18O -> C24H38O4 + H2O` |
| `target_tax_basis` | ✅ | `tax_included` 或 `tax_excluded`（全模型统一口径） |
| `vat_rate_note` | | 税率说明，默认 13% 须注明"默认值" |
| `caveats` | | 展示在页面的边界声明数组 |
| `allowed_scope_mix` | | 允许跨工艺混用的依据（默认不允许，见 validate） |

## 2. `fx`

```json
{"usd_cny": 7.10, "as_of": "2026-10-20", "source": "中国外汇交易中心中间价"}
```
USD 计价时必填；缺失则相关原料判为"口径无法统一"，列为缺口（不猜汇率）。

## 3. `process_params`

| 字段 | 说明 |
|---|---|
| `basis` | `net`（净单耗）/ `apparent`（表观投料）/ `theoretical`（理论） |
| `yield_pct` / `conversion_pct` / `recycle_pct` | 收率/转化率/回收率，用于说明单耗来源，**不在模型里再连乘一次** |
| `notes` | 说明这些参数怎么来的、有没有双扣风险 |

## 4. `materials[]`（核心）

```json
{
  "id": "pa",                         // 必填，唯一；历史序列靠它关联
  "name": "苯酐（邻苯二甲酸酐，PA）",
  "cas": "85-44-9",
  "role": "main",                     // main | aux
  "spec": "≥99.0%",
  "region": "华东",
  "delivery": "自提",
  "tax_included": true,
  "dosage": {
    "value": 0.383,
    "unit": "t/t",                    // t/t | kg/t | kg/kg | g/t
    "source": "eia",                  // user|enterprise|eia|patent|standard|assoc|textbook|research|media|simulated|none
    "scope": "半连续酯化 + 连续脱醇（某厂 10 万吨/年）",   // 必填，用于工艺一致性校验
    "ref": "环评报告书表 3.2-1 产品吨耗（38250 t/a ÷ 10 万 t/a）",
    "note": "疑略偏低，理论值 0.3792 可作下界"
  },
  "price": {
    "value": 10616.67,
    "unit": "CNY/t",                  // CNY/t | CNY/kg | USD/t | 元/吨 ...
    "tax_included": true,
    "spec": "≥99.0%",
    "region": "华东",
    "delivery": "市场价",
    "date": "2026-10-20",
    "source_ref": "生意社（100ppi.com）苯酐基准价",
    "url": "https://www.100ppi.com/rawmex/detail-541.html"
  }
}
```

**规则**
- `price.value` 为 `null` → 该原料不计入成本，页面显示"未计入（不是 0）"，并进缺口清单。
- `price` 整段可省略 → 同上。
- `dosage.value` 必填且 > 0。
- `dosage.scope`：主料必须一致，否则 error（除非 `meta.allowed_scope_mix`）。
- `role: "aux"` 的辅料不参与"主料合计"，但只要有价格就计入总成本。

## 5. `history`（可选，但强烈建议）

```json
{
  "as_of": "2026-10-20",
  "basis_note": "历史成本 = 固定净单耗 × 同日真实基准价",
  "offsets_pct": {"pa": 0, "eh": 0},          // 规格升贴水，% 
  "materials": [{
     "material_id": "pa", "name": "苯酐", "unit": "CNY/t",
     "source": "生意社（100ppi.com）基准价 · 苯酐",
     "source_url": "https://...",
     "spec": "≥99.0%", "region": "华东", "tax_included": true, "freq": "日",
     "retrieved_at": "2026-10-20",
     "method": "曲线接口 + HW_CHECK cookie + packer 解包；端点固定 93 天",
     "rows": [{"date": "2026-07-20", "value": 8666.67}, ...]
  }],
  "reference_series": [{      // 产品价（参照），用于算加工价差，不是成本
     "name": "DOP（产品，参照）", "unit": "CNY/t", "spec": "一级品",
     "region": "国内综合价", "source": "生意社", "source_url": "...",
     "tax_included": true, "rows": [...],
     "note": "仅用于与理论原料成本并列展示加工价差，不是成本的一部分"
  }],
  "gaps": [{"field": "...", "detail": "...", "impact": "...", "fix": "..."}],
  "blend": [{"date": "2026-07-20", "basis": "fixed_q0", "q": {"pa": 0.383, "eh": 0.678}}]
}
```

- `rows[].value` 可为 `null`：表示该日缺价，成本该日留空（不插值）。
- `blend` 必须覆盖 `rows` 的所有日期；`q` 的 key 必须与 `materials[].id` 一致。

## 6. `scenario_config` / `combo_scenarios`

```json
"scenario_config": {"amplitude_series": [{"label": "-10%", "pct": -10}, {"label": "+10%", "pct": 10}]},
"combo_scenarios": [
  {"id": "both_up", "name": "两种主料同时 +10%", "changes": {"pa": 10, "eh": 10}}
]
```

## 7. `not_included` / `unquantified` / `byproducts` / `data_sources` / `formula_doc`

| 字段 | 作用 |
|---|---|
| `not_included` | 未纳入成本项（`{item, reason}`）。**必填**，否则 validate 报警 |
| `unquantified` | 文献里有但无法量化的项（`{item, why, impact}`） |
| `byproducts` | 联产/副产（`{id, name, per_tonne, price_cny_per_t, note}`） |
| `data_sources` | 来源清单（`{id, type, title, url, used_for}`） |
| `formula_doc` | 用户可见的公式说明（`{name, f, v}`） |

## 8. `process_alternatives`（可选，多工艺对比）

```json
[{"id": "net", "name": "净单耗口径", "short": "环评 0.383/0.678", "dosage": {"pa": 0.383, "eh": 0.678}}]
```
HTML 顶部显示为可切换标签；**切换只改单耗，不改价格**。

---

## 9. `result.json`（引擎输出，不要手改）

| 键 | 内容 |
|---|---|
| `total` / `total_main` / `total_aux` | 总成本与主/辅料分项 |
| `materials[]` | 每条原料解析后的 `dosage`/`price`/`cost`/`share`/`price_steps`/`dosage_steps` |
| `coverage` | 计价完整度（n_all / n_computable / complete） |
| `sensitivity[]` | 逐原料 × 逐档 `cost_delta`/`new_total` |
| `combos[]` / `auto_combos[]` | 组合情景与全同步情景 |
| `history.rows[]` | 每日 `cost` 与分项 `items`（缺价日为 null） |
| `history.materials[]` | 历史原始序列（供 HTML 重算与抽屉展示） |
| `periods[]` | 30天/3个月/1年/3年 变化，含 `status: ok|gap` |
| `contribution[]` | 各窗口贡献分解 |
| `gaps[]` | 缺口清单（price / dosage / history / history_window） |
