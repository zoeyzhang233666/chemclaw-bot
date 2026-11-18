# 数据契约（data.json）

`data.json` 是 **唯一输入**。引擎不认识 PDF、不认识扫描件、不认识 Excel——
先把文件变成这份 JSON（可以用 `scripts/extract.py` 辅助，但**必须人工确认**），再交给引擎。

> 设计理由：COA 核对出错，九成不是判错，而是**读错**（小数点、单位、批号、同名不同指标）。
> 把"读"和"判"分成两步，读的那步留痕、可回退，判的那步才可复现。

---

## 1. 顶层结构

```jsonc
{
  "meta":     { ... },   // 谁、什么时候、核哪一批
  "product":  { ... },   // 产品与指标别名表（判定"名称是否可比"的唯一依据）
  "contract": { ... },   // 合同/订单及质量条款（只作文本引用，不作判定）
  "specs":    [ ... ],   // 采购规格书 / 合同技术附件（可多份，按 priority 取高者）
  "standards":[ ... ],   // 国家/行业标准（仅在规格未约定时兜底）
  "coas":     [ ... ],   // 一份或多份质量分析证书（含目标批次）
  "history":  [ ... ]    // 历史批次（趋势用，可空）
}
```

---

## 2. `meta`

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | ✓ | 报告标题 |
| `as_of` | ✓ | 核对基准日 `YYYY-MM-DD`（决定"复检期是否已过"等时间判断） |
| `target_coa_batch` | ✓ | 重点批次，必须出现在 `coas[].batch_no` 中 |
| `buyer_name` / `buyer_contact` | | 采购方与联系人，用于函件落款 |
| `spec_ref` | | 规格依据的展示串（如 `CMSY-QS-MEG-2026-03 Rev.C`） |
| `tone` | | 默认函件语气：`formal` / `firm` / `soft` |
| `simulated` | | `true` 时报告全篇加水印并禁用索赔用途 |
| `sim_note` | | `simulated=true` 时必填 |
| `export_base` | | 输出文件名前缀 |

---

## 3. `product`

```jsonc
{
  "name": "工业用乙二醇",
  "grade": "优等品",          // 可空
  "cas": "107-21-1",
  "un": "3082",
  "use": "作为聚酯切片生产的直接原料……",   // 影响"严重度"和"用途相关性"
  "indicator_aliases": [ { "canonical": "水分", "aliases": ["水份","water","H2O","水分(质量分数)"] } ],
  "equivalent_methods": [ ["GB/T 6283-2008","ISO 760"], ["GB/T 3143-1982","ASTM D1209"] ]
}
```

### `indicator_aliases` 是硬约束

- **不在别名表里的名称，一律 `无法判断`**，不允许"看起来像就比"。
  例：`酸度` 与 `总酸`、`醛类` 与 `乙醛`、`色度` 与 `透光率` 是否同一指标，必须由人确认后写进表里。
- 同一个别名**不能**挂在两个不同的 `canonical` 下（`validate.py` 会拦）。
- `canonical` 是"规格侧的写法"。COA 侧写变体（`水份`、`Water`）时，`name_key` 统一写成 `canonical`。

### `equivalent_methods` 决定"方法不同"是否阻断判定

- 列出的括号内方法视为**等效**：方法不同但可比，报告中注明即可。
- **未列出的一律视为不可比**（落 `无法判断`）。
  这是刻意的保守设定：方法比对是专业判断，不能由脚本默认放宽。

---

## 4. `contract`

```jsonc
{
  "no": "CMSY-HT-2026-0417",
  "annex": "附件2 技术附件",
  "quality_clause": "§7.2 到货检验以本合同技术附件为准……",
  "loc": "合同 P.12 §7.2"
}
```

---

## 5. `specs[]` —— 采购规格书 / 合同技术附件

```jsonc
{
  "title": "工业用乙二醇 采购质量规格书",
  "spec_no": "CMSY-QS-MEG-2026-03",
  "rev": "Rev.C",
  "type": "customer_spec",     // customer_spec=采购规格书 / contract_annex=合同技术附件
  "priority": 2,              // 数字越小优先级越高；合同技术附件应为 1
  "loc": "规格书 P.1-2 §4 质量指标表",
  "items": [
    { "name": "水分", "unit": "%", "limit": "≤0.08", "method": "GB/T 6283-2008",
      "basis": "as_received", "category": "physical", "loc": "§4 表1 第2行" }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `limit` | **原文照抄**，保留 `≤`/`≥`/`~`/`≥且≤` 等符号。允许：`≤0.08`、`≥99.9`、`0.001~0.005`、`无色透明`、`检测不出`、`—` |
| `method` | 约定方法。留空或 `—` 表示规格未规定方法 → 方法维度不阻断，但报告会提示 |
| `basis` | `as_received`（湿基/收到基，默认） / `dry`（干基） / `solution`（溶液基） |
| `category` | `physical` / `chemical` / `purity` / `appearance` / `safety`……仅用于分组展示 |
| `loc` | 原文位置，报告"点指标跳原文"功能依赖它 |

**多份规格的取用规则**：`priority` 最小者的 `limit` 生效；其余同 `priority` 冲突时，
引擎取先出现者并在报告"口径提示"中列出冲突（`_pick_spec`）。

---

## 6. `standards[]` —— 适用标准

结构同 `specs[]`，只是 `type: "standard"`。
**只在规格完全没有约定该指标时才兜底**，且报告中必须标注"依据：标准（非合同引用）"。
合同中明确排除了某项标准时，引擎不会用它提高要求（本例：合同把含量放宽到 ≥99.85 %，
GB/T 4649 的 ≥99.9 % 不得覆盖合同，已在样例中验证）。

---

## 7. `coas[]` —— 质量分析证书

```jsonc
{
  "file": "COA_B_东越石化.pdf",
  "batch_no": "DY-EG-260603B",         // 以到货单/合同批号为准
  "header": {
    "product_name": "工业用乙二醇", "grade": null, "producer": "……",
    "batch_no": "DY260603B",           // ← 证书上写的批号（可能与 batch_no 不一致！）
    "report_no": "DY-QC-26-0603",
    "mfg_date": "2026-06-03", "test_date": "2026-06-04", "retest_date": null,
    "test_standard": "GB/T 4649-2018",
    "conclusion": "符合优等品要求",
    "packing": "槽车散装 / 31.4 t"
  },
  "signoff": { "cert_code": null, "inspector": "张", "reviewer": null, "issuer": null },
  "items": [
    { "name": "水分", "name_key": "水分", "value": "865", "unit": "ppm",
      "method": "GB/T 6283-2008", "lod": "", "basis": "as_received", "loc": "指标表 第2行" }
  ]
}
```

### `batch_no` 与 `header.batch_no` 的区别（重要）

- `batch_no`：**这份货**的批号（合同/到货单口径）。
- `header.batch_no`：**证书纸上写的**批号。
两者不一致 = 证书不能证明这批货，属高优先级完整性问题。**不要为了"对上"而改写其中任何一个。**

### `items[].value` 允许的写法

| 原文 | `kind` | 判定要点 |
|---|---|---|
| `0.075` | single | 与限值比大小 |
| `≤0.08` / `＜0.001` | max | 与上限比 |
| `≥99.9` | min | 与下限比 |
| `1.113~1.115` | range | 区间落在限值区间内才算符合 |
| `未检出` / `ND` / `＜LOD` | nd | **必须**有 `lod`，否则 `无法判断` |
| `未检测` / `—` / 空 | unspecified | → `COA未检测` |
| `无色透明液体` | text | 与规格关键词比对（定性） |

### `lod`（检出限）

写成 `"8 ppb"` 这种"数值+单位"。
- 报 `未检出` 但无 `lod`：不给"符合"，落 `COA未检测`（无法证明 ≤ 限值）。
- 报了一个极小的确定值、且恰好是限值的 1/5 量级：引擎会给出"疑似检出限"提示 → `无法判断`（`_lod_structure`）。

### `basis`（基准）

`as_received` / `dry` / `solution`。与规格侧不一致 → 缺换算系数时 `无法判断`。

---

## 8. `history[]`

```jsonc
{ "batch_no": "DY-EG-260418L", "mfg_date": "2026-04-18", "test_date": "2026-04-19",
  "source": "历史 COA 台账", "items": [ { "name": "水分", "value": "0.073", "unit": "%" } ] }
```

历史批次只用于趋势。**趋势里的每个点都会先换算到规格单位再比较**，
报告会列出发生过换算的批次，避免"865 ppm 与 0.08 % 直接拉平"。

---

## 9. 可选：`notes` / `review_log`

```jsonc
"review_log": [
  { "field": "COA_B.items.铁含量.value", "raw_ocr": "5B0", "confirmed": "580",
    "by": "林工", "at": "2026-06-08", "evidence": "原件高清扫描第3项" }
]
```

所有人工改动都记在这里，报告会单列"人工确认记录"——**这是把结论变成可审计底稿的关键**。
