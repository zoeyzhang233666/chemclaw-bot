# research.json 数据契约

`research.json` 是整个 Skill 的**唯一手填文件**。所有派生数字（四层成本、四价差、
瀑布、归因、敏感性、场景）都由它计算得出，不允许手工改 `data.json`。

运行 `python scripts/validate.py <research.json>` 会按本契约逐条校验。

---

## 顶层结构

```jsonc
{
  "meta":           { ... },   // 必填：品种、规格、地区、单位、日期
  "overseas":       { ... },   // 必填：海外报价（六要素）
  "domestic":       { ... },   // 必填：国内现货（六要素）
  "compare_quote":  { ... },   // 可选：对比期海外报价（做归因用）
  "compare_dom":    { ... },   // 可选：对比期国内价
  "cost_params":    { ... },   // 必填：汇率、运费、税率等全部外生参数
  "fx_history":     { "YYYY-MM-DD": 6.7423, ... }, // 历史汇率
  "freight_history":{ ... },   // 历史运费（本 Skill 要求逐期标注来源）
  "history":        [ ... ],   // 观测序列：海外报价 + 国内价 + 运费 + 来源标签
  "sensitivity":    { ... },   // 敏感性取值范围
  "scenarios":      { "rounds": [ ... ] }, // 情景对比
  "sources":        [ ... ],   // 数据来源清单（出现在报告第 7 节）
  "gaps":           [ ... ],   // 数据缺口清单（出现在报告第 8 节）
  "disclaimers":    [ "..." ]  // 免责声明（出现在报告第 10 节）
}
```

---

## 1. meta（必填）

| 字段 | 类型 | 说明 |
|---|---|---|
| `product` | str | 品种中文名，如「乙二醇」 |
| `product_code` | str | 简称/代码，如「MEG」 |
| `spec` | str | **规格必须可判定**：纯度、等级、形态、包装 |
| `title` | str | 报告标题 |
| `quote_region` | str | 海外报价对应的市场/港口 |
| `quote_basis` | str | 报价口径的文字说明（含运费保险与否） |
| `quote_term` | str | 建议的贸易术语（面板默认选中） |
| `dom_region` | str | 国内基准地，越具体越好（如「张家港/太仓/江阴」） |
| `dom_basis` | str | 国内价口径（含税、送到、现汇…） |
| `hs_code` | str | 10 位海关编码 |
| `hs_desc` | str | 编码对应描述 |
| `currency` | str | 报价币种，一般 `USD` |
| `unit` | str | 金额单位，一般「元/吨」 |
| `base_date` | str | **基准时点**（ISO 日期） |
| `window` | str | 观察窗口的人读描述 |
| `window_start` | str | 观察窗口起点 |
| `compare_date` | str | 归因对比期时点 |
| `generated_at` | str | 生成日期 |
| `must_read` | [str] | 必读三句（口径警告） |
| `focus` | [str] | 本次分析要盯住的点 |

**基准时点的选择规则**：取「海外报价 + 国内价 + 汇率」三者**同一天齐全**的最后一个交易日。
若海外报价已停更而国内更新到更近，基准点仍应取三者齐全的那天，并在缺口里说明「国内价已行至 X 日」。

---

## 2. 价格节点（六要素）

`overseas` / `domestic` / `compare_quote` / `compare_dom` 四个节点结构相同：

| 字段 | 必填 | 说明 |
|---|---|---|
| `price` | ✔ | 数值；有区间时用 `price_range` 写 `"680-690"`，代码取中值 |
| `spec` | ✔ | 规格 |
| `region` | ✔ | 地区/港口 |
| `currency` | ✔（海外）| `USD` / `CNY`；国内节点省略则默认 CNY |
| `tax` | ✔ | `含税` / `不含税` / `不含中国进口税` |
| `term` | ✔ | 术语（海外）或交货方式（国内，如「送到主港」） |
| `date` | ✔ | 该数值对应的日期，**不是抓取日期** |
| `source` | ✔ | 一句话来源：媒体 + 文章标题 + 关键原文 |
| `source_url` | 建议 | 直达链接 |
| `conf` | 建议 | 可信度 `高`/`中`/`低` |

> `price` 与 `date` 必须成对。把「今天抓到的昨天的数」写成今天的日期，是最常见的口径错误。

---

## 3. cost_params（必填）

| 键 | 单位 | 默认 | 备注 |
|---|---|---|---|
| `fx_usdcny` | CNY/USD | — | 基准日汇率 |
| `purity` | 倍 | 1.0 | 折纯用 |
| `gross_weight_factor` | 倍 | 1.0 | 毛净比 |
| `inland_origin` | 原币/t | 0 | 仅 EXW 需要 |
| `export_clear` | 原币/t | 0 | 仅 EXW 需要 |
| `ocean_freight` | 原币/t | 0 | **术语含运费时必须为 0** |
| `insurance_rate` | 倍 | 1.1 | 加成率 |
| `insurance_rate_pct` | 小数 | 0 | 费率；CIF 时为 0 |
| `discharge_fee` | 原币/t | 0 | 目的港卸货 |
| `inland_dest` | 原币/t | 0 | 进口国内陆运 |
| `unload_fee` | 原币/t | 0 | 装卸/损耗附加 |
| `duty_rate` | 小数 | 0 | **最惠国 ≠ 实际执行，见缺口** |
| `other_tax_rate` | 小数 | 0 | 反倾销/反补贴 |
| `vat_rate` | 小数 | 0.13 | 进口增值税 |
| `vat_credit_ratio` | 0~1 | 1.0 | 可抵扣比例 |
| `_src` | obj | {} | 每个参数的数据来源备注，写进报告 |

**未取证的参数该填什么**：填 0，并在 `gaps` 里写清「按 0 计入会低估约 X 元/吨」。
**不要**填一个「看起来合理」的行业均值然后不说——那会让报告看起来更完整，实际更不可信。

---

## 4. history（观测序列）

```jsonc
{
  "date": "2026-08-18",        // 该观测点日期（ISO，必须严格递增）
  "ov_usd": 685.0,             // 海外报价（原币/t）
  "dom_cny": 5116.67,          // 国内价（元/t）
  "fx": 6.7423,                // 可选：行内汇率；不填则从 fx_history 按日期取
  "frt_usd": 0.0,              // 该时点运费（原币/t）
  "frt_source": "assumed_base",// 必填：actual | monthly_avg | assumed_base | gap
  "fx_source": "actual",       // 必填：actual | gap
  "note": "…",                 // frt_source=assumed_base 时必填，说明为何可用基准值
  "ov_source": "https://…",    // 报价取证链接
  "dom_source": "https://…"    // 国内价取证链接
}
```

### 标签语义（这是本 Skill 的核心纪律）

| `frt_source` | 含义 | 允许的前提 |
|---|---|---|
| `actual` | 该时点真实运价 | 有可追溯来源 |
| `monthly_avg` | 用当月可得运价均值 | 已获取月度数 |
| `assumed_base` | 沿用基准日参数 | **必须写 note 解释**；且该行结论只能读作条件性结果 |
| `gap` | 该时点无数据，不参与计算 | 曲线断开，不做插值 |

**校验会拦截**：3 条以上被标 `actual` 的运费完全相同（典型的「用今天冒充历史」）。
**汇率同理**：超过 `fx_max_stale_days`（默认 7 天）取不到就直接判 gap，绝不向外延伸。

> 特例：报价本身是 CIF/CFR 到岸价时，运费已含，`frt_usd=0` 是**口径结果**而非缺失。
> 此时 `frt_source` 仍按 `assumed_base` 标注，并在 note 写明「术语已含运费，置 0 非缺失」。

---

## 5. sensitivity

```jsonc
"sensitivity": {
  "price":    [500, 600, 685, 800],   // 海外报价候选值
  "freight":  [0, 20, 40, 60, 80],    // 运费候选值
  "fx":       [6.3, 6.5, 6.7423, 7.1],
  "duty":     [0, 0.02, 0.055, 0.10],
  "vat":      [0.09, 0.13],
  "insurance_pct": [0, 0.0015, 0.003],
  "credit":   [0, 0.5, 0.8, 1.0],
  "discharge":[0, 10, 20, 30],
  "term":     ["EXW","FOB","CFR","CIF","DAP"],
  "matrix":   { "fx": [6.4,6.55,6.7423,6.9,7.05],
                "freight": [0,20,40,60,80] }   // 行=运费，列=汇率
}
```

建议：候选值要覆盖「会改变结论符号」的区间，否则敏感性章节没有信息量。

---

## 6. sources / gaps / disclaimers

`sources[]`：
```jsonc
{ "role": "overseas|domestic|fx|freight|tax|cross",
  "name": "媒体名 + 栏目/文章类型",
  "conf": "高|中|低",
  "date": "覆盖日期范围",
  "urls": ["https://…", "…"],
  "note": "口径说明与已知局限" }
```

`gaps[]`：
```jsonc
{ "item":   "缺什么（具体到字段或数值）",
  "impact": "对结论的影响方向与量级（尽量给数字）",
  "fix":    "具体怎么补齐",
  "severity": "高|中|低",
  "scope":  "tax|freight|cost|series|spec|domestic|overseas" }
```

`disclaimers[]`：至少包含「非交易建议」「二手引用」「历史假设标注」「不含预测」四条。

---

## 7. 最小可用示例

```json
{
  "meta": {
    "product": "乙二醇", "product_code": "MEG",
    "spec": "聚酯级，纯度≥99.9%，散装船货",
    "title": "乙二醇 CFR 中国 vs 华东现货",
    "quote_region": "中国主港", "quote_basis": "中国到岸价（含运保）", "quote_term": "CIF",
    "dom_region": "华东", "dom_basis": "送到主港、含税、现汇",
    "hs_code": "2905310000", "currency": "USD", "unit": "元/吨",
    "base_date": "2026-08-18", "window": "2025-09 ~ 2026-08"
  },
  "overseas": { "price": 685, "spec": "聚酯级船货", "region": "中国主港",
                "currency": "USD", "tax": "不含中国进口税", "term": "CIF",
                "date": "2026-08-18", "source": "生意社外盘乙二醇价格一览" },
  "domestic": { "price": 5116.67, "spec": "聚酯级", "region": "华东",
                "tax": "含税", "term": "送到主港", "term_incl_freight": true,
                "date": "2026-08-18", "source": "生意社乙二醇基准价" },
  "cost_params": { "fx_usdcny": 6.7423, "ocean_freight": 0, "vat_rate": 0.13,
                   "vat_credit_ratio": 1.0, "duty_rate": 0 },
  "history": [],
  "sensitivity": {},
  "sources": [],
  "gaps": [{"item":"…","impact":"…","fix":"…","severity":"高"}],
  "disclaimers": ["本报告不构成交易建议"]
}
```
