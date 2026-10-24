# research.json 数据契约

一个案例 = 一个目录，核心是 `data/research.json`。本文逐字段说明。

> 设计哲学：**能验证的才写数字，验证不了的写 `null` 并登记到 `gaps`。**
> `null` 和 `0` 含义完全不同：`null` = 未知，`0` = 已确认零成本。

---

## 顶层结构

```jsonc
{
  "meta":       { ... },   // 案例元信息
  "request":    { ... },   // 用户的原始需求
  "product":    { ... },   // 产品与规格
  "basis":      { ... },   // 比价口径声明
  "normalization": { ... },// 归一化规则
  "sources":    [ ... ],   // 来源清单（S1、S2…）
  "quotes":     [ ... ],   // 地区报价（Q-XX）
  "destination":{ ... },   // 收货地
  "routes":     [ ... ],   // 运输线路（R-XX）
  "regions":    [ ... ],   // 区域绑定（quote + route）
  "benchmark_region_id": "XX",
  "cost_params":{ ... },   // 费用参数（可全空）
  "history":    { ... },   // 历史价差（可空）
  "gap_rules":  [ ... ],   // 口径红线
  "gaps":       [ ... ],   // 缺口清单
  "assumptions":[ ... ]    // 假设清单
}
```

---

## 1. `meta`

```json
{ "scenario_id": "01-soda-ash-su-zhou", "scenario": "live", "generated_at": "2026-10-19", "version": "1.0" }
```

- `scenario`: `"live"` = 真实数据；`"demo"` = 合成数据（HTML 会显示醒目提示）。**演示数据必须标 demo。**

## 2. `request`

```json
{ "product": "重质纯碱", "spec": "工业级 Na₂CO₃ ≥98%，重质，25/50kg 袋装", "receipt_address": "江苏苏州", "quantity_t": 100 }
```

`receipt_address` 会出现在标题与首屏，写清"省+市"。

## 3. `product`

```json
{
  "name": "重质纯碱", "formula": "Na₂CO₃", "grade": "重质（重灰）",
  "spec": "工业级，Na₂CO₃ ≥98%",
  "unit": "吨", "density": 1.0,
  "tax": { "goods_vat": 0.13, "goods_vat_note": "纯碱适用 13% 增值税" }
}
```

`density`（t/m³）只在价格按 `元/立方米` 报价时才用得上。

## 4. `sources[]`

**每一个价格都必须挂到一个 source。** 字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✓ | `S1`、`S2`… |
| `name` | ✓ | 来源名称（含日期） |
| `url` | ✓ | 可点开的原文链接 |
| `type` | ✓ | 资讯商 / 交易所 / 期货公司研报 / 行业门户 / 企业公告 |
| `level` | ✓ | 口径等级：`全国基准价` / `分区现货区间` / `单一市场成交` / `基差报盘` |
| `retrieved_at` | ✓ | 采集日 |
| `note` | | 需要注意的口径陷阱 |

`level` 很重要：**`基差报盘` 不能和 `分区现货区间` 混在一起算平均。**

## 5. `quotes[]` —— 价格

六要素缺一不可（校验器会卡）：

```json
{
  "id": "Q-SH",
  "source_id": "S1",
  "date": "2026-10-16",
  "market": "山东（华北），主报点：淄博/潍坊",
  "region_key": "山东",
  "grade": "重碱",
  "spec": "工业级 Na₂CO₃ ≥98%",
  "price_low": 1100,
  "price_high": 1200,
  "price": 1150,
  "price_type": "区间中值",
  "unit": "元/吨",
  "tax_included": true,
  "delivery_basis": "送到",
  "evidence": "化盟网 2026-10-16 分区价格表：华北 重碱 1100-1200…",
  "verify": "其他交叉验证说明",
  "comparable": true
}
```

| 字段 | 要求 |
|---|---|
| `price_low` / `price_high` | 原始区间。只有单点时都填同一个值 |
| `price` | **实际进入计算的取用值**。默认取中值，也可取低端/高端 |
| `price_type` | 说明 `price` 怎么来的：`区间中值` / `低端` / `高端` / `单一报价` |
| `tax_included` | ☑ 必填布尔值，不能缺 |
| `delivery_basis` | `送到` / `出厂` / `自提` / `库提` —— 含"自提"会被标橙色警示 |
| `comparable` | 设为 `false` 时该报价不参与比较（例如 ChemicalBook 的零售挂牌） |

> **区间宽的报价**（上下限差 ≥ 100 元）会在 HTML 里被标记"建议上下限各算一遍"，因为中值可能掩盖高低端货源的真实差距。

## 6. `routes[]` —— 线路与里程

三种 `basis`，按可信度从高到低：

### 6.1 `measured_legs`（推荐）多条实测「起→终」里程

一个区域常用两个起点（低端/高端），因为它们代表省内不同的产区：

```json
{
  "id": "R-SH",
  "region_id": "SH",
  "label": "山东 → 苏州",
  "origin_city": "济宁",
  "dest_city": "苏州",
  "basis": "measured_legs",
  "mode": "公路整车（13m 半挂）",
  "legs": [
    { "from": "济宁", "to": "苏州", "km": 707, "hours": 7.8,
      "source": "车主手册 icauto.com.cn「城际路线大全」单程高速方案",
      "url": "https://www.icauto.com.cn/route/160_133.html",
      "road": "G3 京台→G2 京沪" },
    { "from": "潍坊", "to": "苏州", "km": 760, "hours": 8.1, "...": "..." }
  ],
  "distance_ref_note": "主报点济宁 707 km；潍坊 760 km。",
  "alternatives": [
    { "mode": "内河/海运联运", "note": "潍坊港装船→长江口，适合 1000 吨以上；需另询船代运价" }
  ],
  "freight_unit": null,
  "freight_total": null,
  "loading_total": null,
  "unloading_total": null,
  "inspection_total": null,
  "other_total": 0,
  "freight_unit_note": "待填：元/吨（公路整车包干运价，含 9% 增值税）"
}
```

引擎取 `legs` 中最短为 `km`（低端），最长为 `km_high`（高端）。模型会把它渲染成 **707~760 km** 的区间。

### 6.2 `measured` 单一实测里程

```json
{ "basis": "measured", "measured_km": 436, "distance_source": "高德路线规划 2026-10-19" }
```

### 6.3 `via_points` 途经点折线（兜底）

```json
{ "basis": "via_points", "via_points": ["连云港", "淮安", "扬州", "苏州"], "detour_factor": 1.0 }
```

沿城市链累加大圆距离。**途经点每 100~200 km 放一个枢纽城市**，否则会低估。`detour_factor` 默认 1.0（已标定），不要随意改大。

### 运费字段（三种填法，按优先级）

| 字段 | 单位 | 优先级 |
|---|---|---|
| `freight_total` | 元（整单） | 1（最高） |
| `freight_unit` | 元/吨 | 2 |
| 全部 `null` | — | → 到厂成本显示"待补" |

`loading_total` / `unloading_total` / `inspection_total` / `other_total` 为整单金额（元），也可都不填。

## 7. `regions[]`

```json
{ "id": "SH", "name": "山东", "label": "山东（潍坊/淄博）", "market": "华北",
  "quote_id": "Q-SH", "route_id": "R-SH",
  "producers": ["山东海化", "海天生物"], "include": true }
```

`producers` 用于 HTML 的"找供应商"区块，只写区域主要产能方。

## 8. `cost_params`

```json
{ "qty": 100, "unit": "t", "loadingUnit": null, "unloadingUnit": null,
  "inspectionUnit": null, "taxRate": 9, "priceBasis": "incl_tax" }
```

`loadingUnit` 等为 `null` = 未知。**如果装卸费已包含在运价里，填 `0` 并在 `assumptions` 里说明。**

## 9. `history`

可整段省略（HTML 会显示"暂无历史序列"）。

```json
{
  "span": "2026-07-21 ~ 2026-10-19",
  "series": [
    { "key": "national_heavy", "name": "全国重碱基准价", "source_id": "S7",
      "points": [ { "date": "2026-10-19", "value": 1062.86 } ] }
  ],
  "regional_spread": [
    { "date": "2026-10-16", "region_key": "山东", "heavy_low": 1100, "heavy_high": 1200,
      "region_note": "华北送到", "source_id": "S1" }
  ],
  "price_change_window": { "from": "2026-07-21", "to": "2026-10-19", "pct": -7.8 }
}
```

**`regional_spread` 只放"同一天、同规格、同交货口径"都有报价的日期。** 缺的日期不要插值补，宁可比对日少。

## 10. `gaps[]`

```json
{
  "key": "freight",
  "title": "全部线路运费",
  "what": "山东/河北/河南/江苏 → 苏州 的整车运价（元/吨 或 整单元）",
  "why": "未取得承运方报价；公开渠道的吨公里价是行业均价，不是本线路报价",
  "how_to_fix": "找 2~3 家回程车/专线询价，注明含税与否、是否含装卸",
  "impact": "缺此项无法计算到厂成本，只能比较裸价与距离",
  "severity": "blocker"
}
```

`severity`: `blocker` = 阻断排名；`warn` = 影响精度但不阻断。

## 11. `assumptions[]`

```json
{ "key": "A2", "text": "交货口径：沙河列为自提…", "source": "S8" }
```

所有"未注明口径的数字都按这个理解"的说明都写这里。

## 12. `gap_rules[]`

字符串数组，显示在 HTML 与 Excel 的"口径红线"区。建议固定这几条：

```json
[
  "未取得运费报价时，只展示裸价差、运输距离与待补项目，不估算运费金额。",
  "任一区域的运费或装卸费缺失时，不给出到厂成本排名。",
  "不同交货口径（自提/出厂/送到）不直接相减得出『谁更便宜』。",
  "所有价格须标注 数值+规格+地区+含税口径+日期+来源，缺一项即视为不完整。"
]
```
