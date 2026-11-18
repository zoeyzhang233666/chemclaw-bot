# project.json 数据契约

所有字段。**缺字段就写进 `gaps`，不要编。**

## 顶层

```jsonc
{
  "schema": "cost-pass-through/v1",
  "product_chain": "PX（对二甲苯）→ PTA（精对苯二甲酸）",
  "window": {
    "start": "20251001",        // 建议用两列都有价的第一个交易日
    "end": "20261020"
  },
  "upstream":   { ...价格口径... },
  "downstream": { ...价格口径... },
  "process":    { ...工艺... },
  "materials":  [ ...单耗... ],
  "params":     { ...模型参数... },
  "price_series":   { "px": {"20251001": 6800.0, ...}, "pta": {...} },
  "material_series": { "PX": "px" },   // 原料名 → price_series 的键
  "calibration_anchors": [ ...锚点校验... ],
  "gaps": [ ...数据缺口... ]
}
```

## upstream / downstream（价格口径，六个字段都要）

| 字段 | 例 | 说明 |
|---|---|---|
| `name` | `"PX"` | 品种名 |
| `series_key` | `"px"` | 对应 `price_series` 的键 |
| `spec` | `"生意社PX基准价"` | 规格/牌号/标准 |
| `region` | `"中国（华东）"` | 地区 |
| `unit` | `"元/吨"` | 必须是元/吨；若原为美元，先在 `price_series` 里换好 |
| `tax` | `"含增值税"` | 含税/不含税/待确认 |
| `source` | `"生意社 100ppi 基准价日评"` | 来源 |
| `source_url` | `"https://..."` | 可点击的来源页 |
| `granularity` | `"日度评估价，非成交价"` | 评估价还是成交价，频率 |
| `futures_contract` | `"CZCE TA"` | 可选，有期货时填 |

## process（工艺核实）

```jsonc
"process": {
  "route": "PX 液相空气氧化 → 粗对苯二甲酸 → 加氢精制 → PTA",
  "equation": "PX + 3O2 → PTA + 2H2O",
  "verified": true,        // 是否已核实到可引用来源
  "note": "国内 PTA 装置均采用氧化催化工艺"
}
```

`verified: false` 时，报告会自动在首页打"工艺待核实"标记。

## materials（单耗，核心）

```jsonc
"materials": [
  {
    "name": "PX",
    "unit": 0.655,          // 吨原料 / 吨下游，主模型用这个值
    "low": 0.648,           // 敏感性下界（新装置）
    "high": 0.665,          // 敏感性上界（早期装置）
    "unit_basis": "吨 PX / 吨 PTA",
    "source": "行业通用加工费口径 0.655；技术区间 0.648~0.665"
  }
]
```

- `unit` 必填。`low`/`high` 可缺，缺了敏感性列留空。
- 不要写没有来源的单耗。理论值（按分子量算）要单独说明"这是理论下限"。

## optional_materials（拿不到价格就先不做，但要声明）

```jsonc
"optional_materials": [
  { "name": "醋酸", "unit": 0.03, "low": 0.029, "high": 0.04,
    "status": "未纳入主模型：缺少同期间醋酸日度基准价" }
]
```

这比"悄悄忽略辅料"诚实得多，也让读者知道价差里还少算了什么。

## params

```jsonc
"params": {
  "unit_default": 0.655,
  "spread_definition": "加工价差 = PTA价格 − 0.655×PX价格",
  "spread_excludes": ["能源/公用工程", "辅料与催化剂", "人工", "折旧",
                      "财务费用", "检维修", "包装与运费", "库存损益"],
  "not_profit_statement": "加工价差是价差口径，不是企业生产利润"
}
```

## calibration_anchors（锚点校验，强烈建议填）

```jsonc
"calibration_anchors": [
  { "date": "2025-10", "kind": "月度均值", "reported": 154.0,
    "source": "界面新闻引用 10月平均加工费" },
  { "date": "2026-08-20~2026-08-26", "kind": "周度均值", "reported": 712.73,
    "source": "隆众资讯 PTA加工费周数据统计" },
  { "date": "2026-09-24", "kind": "单日现货", "reported": 662.63,
    "source": "期货日报《PTA加工费修复能否持续？》" }
]
```

`date` 支持三种写法：`YYYY-MM`（整月均值）、`A~B`（区间均值）、`YYYY-MM-DD`（单日）。
脚本会算 `model` 与 `gap`，判定标准见 [`calibers.md`](calibers.md)。

## gaps

```jsonc
"gaps": [
  { "item": "醋酸价格序列", "reason": "未找到同期间日度基准价",
    "impact": "价差少算约 100~160 元/吨（按醋酸 2500 元/吨估算）" },
  { "item": "装置级成本", "reason": "无企业级能耗与折旧数据",
    "impact": "只能做行业价差，不能判断单个装置盈亏" }
]
```

`impact` 要量化，读的人才判断得出这份报告能用到什么程度。

## price_series 的键

- 日期键统一 `YYYYMMDD`（带横线的 `YYYY-MM-DD` 也兼容，脚本会归一）
- 值为数字（元/吨），**不要放字符串**，不要放 `null`（缺失就不要给这个键）
- 两列日期不必完全对齐，脚本按交集+前值填充处理，并输出 `filled` 天数
