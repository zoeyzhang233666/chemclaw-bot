# 数据契约 · research.json → HTML / Excel

> 本 Skill 的唯一原则：**模板不含任何品种事实**。HTML、Excel 的全部文字、数字、结构都来自 `research.json`。
> 换品种 = 换 `research.json`；换骨架顺序 = 改 `chain.cols`；品种没有期货 = `product.has_futures=false`，期现模块自动降级为缺口声明。

## 0. 顶层结构

```jsonc
{
  "meta":     { ... },        // 标题、基准日、版本、免责声明
  "product":  { ... },        // 品种身份与核心信息卡（→ 首屏 + Excel 01/02）
  "frame":    [ ... ],        // 首屏研究指标框架（→ 首屏底栏 + Excel 09 摘要）
  "chain":    { "cols": [...], "nodes": [...] },  // 产业链图谱（→ 首屏骨架 + Excel 04/08）
  "research": { ... },        // 六个研究模块（→ 下方面板 + Excel 05~07、09）
  "panels":   [ ... ],        // 下方面板（渲染为 HTML 区块；文本已内嵌，避免重复维护）
  "sources":  [ ... ],        // 来源总表（id 被全篇引用）
  "gaps":     [ ... ],        // 缺口声明
  "caveats":  [ "..." ],      // 口径提醒
  "purposes": [ ... ],        // 研究目的切换（期货研究/现货贸易/采购/销售…）
  "scenes":   { ... },        // 节点上的“深入场景”按钮 → 任务模板
  "chart_note": "..."
}
```

字段缺失的约定：**能不填就不填，不得填 `""` 或 `null` 冒充实数**。渲染器会把缺失显示为 `⚠ 缺口` 标签，Excel 写成“缺口”。

---

## 1. meta

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | ✓ | 页面标题，如 `甲醇 · 品种研究入口` |
| `data_asof` | ✓ | 数据基准日 `YYYY-MM-DD`，指本轮核实的最后日期 |
| `generated` | ✓ | 生成日期 |
| `version` | ✓ | Skill 版本 `v1.0.0` |
| `output_name` | ✓ | 输出文件名主干，如 `甲醇-品种研究入口` |
| `footnote` | ✓ | 页脚免责声明（建议固定写“事实与判断分离、缺口不补数”） |
| `labels` | | `{ "upstream": "原料/能源", "process": "工艺", ... }` 覆盖节点列缺省中文名 |

## 2. product（身份卡）

```jsonc
"product": {
  "name_cn": "甲醇", "name_en": "Methanol",
  "aliases": ["木醇", "木精", "甲基醇"],            // 中文别名
  "synonyms_en": ["methyl alcohol", "wood alcohol"],
  "cas": "67-56-1",
  "hs": [{ "code": "2905110000", "desc": "甲醇(methanol)", "src": "S03" }],
  "un": "1230（3类易燃液体，易燃毒性）",
  "formula": "CH4O / CH3OH", "mw": "32.04",
  "appearance": "无色透明液体，有刺激性气味",
  "boiling_point": "64.7 ℃（101.3 kPa）",
  "freezing_point": "-97.6 ℃",
  "density": "0.7918 g/cm³（20 ℃）",
  "flash_point": "11 ℃（闭杯）",
  "solubility": "与水、醇、醚任意比互溶",
  "hazard_class": "《危险化学品目录（2015版）》序号 2102；GHS 易燃液体2、急性毒性3",
  "identity_confidence": { "level": "高", "basis": "CAS 67-56-1 唯一对应甲醇；HS 2905.11；期货代码 MA", "src": ["S01"] },
  "scene": ["期货研究", "现货贸易", "MTO 采购"],
  "main_spec": "国标 GB 338-2011 优等品（纯度 ≥99.9%）",
  "grades": ["GB 338-2011 优等品/一等品/合格品", "工业甲醇 / 燃料甲醇（M100、船用甲醇）", "试剂级/色谱纯"],
  "packages": "散装（船运/槽车/罐车）、桶装（200 L）",
  "uses_cn": ["甲醇制烯烃", "甲醛", "醋酸", "二甲醚", "燃料"],
  "has_futures": true,
  "card": [ { "k": "中文通用名", "v": "甲醇", "sub": "别名：木醇/木精" } ],   // 首屏 12 格核心信息，2 列宽用 "wide": true
  "oneliner": "一句话定位（≤80 字，必须含“是什么+行业地位+是否期货”）
}
```

> `card` 建议 10–14 格，按“身份 → 规格 → 计量 → 贸易 → 期货 → 价格口径”排序，看完 30 秒内能抓住品种。

## 3. frame（首屏研究指标框架）

```jsonc
"frame": [
  { "name": "供应", "value": "—", "value_note": "开工率/产量/进口", "items": [
      { "name": "全国甲醇开工率", "caliber": "周度", "gap": false },
      { "name": "月度产量", "caliber": "万吨", "gap": true } ] }
]
```
建议固定 5–6 个：供应、需求、库存、价格/成本、期现、政策与产能。
`gap:true` 的条目会在卡面显示“⚠n 项缺口”。

## 4. chain（产业链图谱）

```jsonc
"chain": {
  "cols": [
    { "id": "upstream",   "name": "上游原料/能源" },
    { "id": "process",    "name": "生产工艺" },
    { "id": "self",       "name": "本品种" },
    { "id": "downstream", "name": "下游产品" },
    { "id": "enduse",     "name": "终端消费" }
  ],
  "nodes": [
    { "id": "coal", "col": "upstream", "name": "原料煤", "meta": "近三年均价 …",
      "cap": "", "spot": "", "level": 0, "parent": null, "parents": [],
      "children": [ { "id": "coal_x", "name": "动力煤", "cap": "" } ],
      "kind": "upstream", "src": ["S11"],
      "research": { ... 见 §6 } }
  ]
}
```

要点：

- `cols` 就是骨架的列，**顺序即产业链顺序**。煤→甲醇 是 3 列，油→PX→PTA→聚酯 可能是 5 列；精细化学品常用 4 列（原料/合成/精制/下游）。
- `children` 是**仅用于面板展示的子节点摘要**（点击父节点展开可见）；`nodes` 里的完整节点用 `parent` 指向父 id，两者可并存。
- `is_self: true` 的节点是“本品种”，全页只有 1 个；`kind` 取 `upstream|process|self|downstream|enduse|other`。
- `parents` 用于多原料指向（如甲醇 ← 煤/天然气/焦炉气），渲染“上游指向”。
- `cap`（产能/规模摘要）、`spot`（价格摘要）只是面板上的小标签，**不要放长文本**。
- 研究深浅决定节点数：快速版 12–20 个节点；深度版可 30–60 个，建议 `level` 分层以控制首屏噪声。

## 5. research（六个研究模块）

`research` 下按**场景 id** 分区，每个分区是“若干卡片/表格块”。模块名与顺序由 `panels` 定义，推荐六块：

| id | 中文名 | 对应用户原问题 |
|---|---|---|
| `identity_specs` | 产品百科与规格 | 1) 是什么/名称/牌号/规格/计价 |
| `routes` | 工艺与原料 | 2) 工艺路线、单耗、产品差异 |
| `demand` | 下游与应用 | 3) 下游、终端用途 |
| `capacity` | 企业与产能 | 4) 生产企业、基地、公开产能、区域 |
| `trade_futures` | 贸易与期现 | 5) 6) 贸易区域、期货合约与交割 |
| `indicators` | 研究指标与逻辑 | 7) 8) 跟踪哪些指标、产业逻辑 |

### 5.1 内容块（block）通用写法

`panels[].body` 是 block 数组，支持 9 种 `type`：

| type | 必填字段 | 用途 |
|---|---|---|
| `text` | `title`, `html` | 叙述段落（允许内联 HTML，但**不要放数据表**） |
| `cards` | `title`, `items[{title,lead,lines[{k,v,sub}],src}]` | 2 列并排事实卡 |
| `table` | `columns[{k,type}], rows[{...}]` | 通用事实表；`type:"num"` 右对齐；列 `k:"来源"` 渲染来源 |
| `routes` | `items[{name,brief,share,status,steps,params,body,src}]` | 工艺路线卡（默认折叠，点击展开） |
| `companies` | `items[{name,site,cap,unit,process,src}]`, `total` | 企业产能条形榜 |
| `regions` | `items[{name,scope,value,unit,note,mix,share}]` | 区域格局卡片（可带产能结构条） |
| `indicators` | `groups[{name,items[{name,caliber,freq,importance,points,src}]}]` | 研究指标折叠列表 |
| `logic` | `items[{name,sub,steps[]}]` | 产业逻辑链（带序号） |
| `futures` | `items[{title,rows[{k,v}],src}]` | 期货合约/交割 KV 卡 |
| `gapnote` | `title`, `text` | 无期货 / 数据未覆盖声明 |

> **表头命名约定**：`columns[].k` 就是页面上显示的表头文字，必须直接写中文，
> 例如来源列写 `{"k": "来源"}`，**不要写 `{"k": "src"}`**——那样会把英文数据键
> 原样渲染成表头，`qa_render.py` 的“表头无英文数据键泄漏”检查会直接判失败。

### 5.2 期货模块的强制要求

- 有期货：`futures` 卡必须逐项写 **交易所、合约代码、交易单位、报价单位、最小变动、涨跌停、保证金、交割月份、最后交易日、交割品级、交割方式、交割地**，每项挂来源；
  另附一张 **“交割标准品 ↔ 现货主流规格”对应表**（用 `table`）。
- 无期货：`panels[].body` 只放一个 `gapnote`，写明“本品种无场内期货/期权，不设期现模块”，**不得**虚构合约。

## 6. 节点 `research`（抽屉详情）

```jsonc
"research": {
  "summary": "该节点在本链条中的作用（1 句）",
  "points":  ["研究要点 1", "要点 2"],
  "share":   "占甲醇消费 52%（2024）",      // 可选
  "single_use": "1 t 烯烃 ≈ 2.9–3.0 t 甲醇",  // 可选
  "spot":    [ { "name":"太仓甲醇现货", "value":"2,480", "unit":"元/吨", "spec":"国标优等品",
                 "region":"江苏太仓", "tax":"含税", "date":"2026-10-16", "src":["S21"] } ],
  "price_gap": "公开渠道未取得逐日序列",
  "indicators": [ { "name":"港口库存", "caliber":"周度，万吨", "why":"表征可交割供给" } ],
  "companies":  [ { "name":"…", "site":"…", "cap":120, "unit":"万吨/年", "note":"…", "src":["S31"] } ],
  "companies_gap": "公开信息未披露单套产能",
  "cap_structure": [ { "name":"煤制", "value":"8,250 万吨", "share":"75%", "date":"2025" } ],
  "projects":   [ { "name":"…", "cap":"80 万吨/年", "status":"环评公示", "when":"2026", "region":"宁东" } ],
  "news":       [ { "title":"…", "date":"2026-09-18", "org":"…", "impact":"中性" } ],
  "actions":    [ { "id":"price_history", "name":"价格历史", "desc":"查该节点 3 年价格与分位" } ],
  "sources":    ["S11"], "gaps": ["…"]
}
```
`actions[].id` 必须能在 `scenes` 里找到同名场景，否则按钮点了只提示“未登记”。

## 7. sources / gaps / purposes / scenes

```jsonc
"sources": [ { "id":"S03", "org":"海关总署", "title":"…", "url":"https://…", "date":"2025-12-31",
               "type":"官方统计", "use":"HS 编码与进出口量" } ],
"gaps":    [ { "area":"月度开工率", "desc":"…", "how":"留空，进入“看供给端”场景补数" } ],
"purposes":[ { "id":"futures", "name":"期货研究", "panel":"indicators",
               "emphasize":["self","downstream"], "highlight_indicators":["0-0","0-1"] } ],
"scenes":  { "price_history": { "name":"价格历史", "skill":"chem-market-brief",
               "template":"查 {product} 近3年现货价格与历史分位" } }
```

**source id 规则**：`S01` 起顺排，一经使用不得复用改号；每条 sources 必须有 `date`（无链接的纸质资料写“报告年度”）。

---

## 8. 校验规则（`scripts/validate.py` 强制）

1. `meta` 六字段齐全；`product.cas` 或 `product.hs` 至少有 1 个，否则“身份”不成立。
2. 恰好 1 个 `is_self`；`chain.cols` ≥ 3 列；每个节点 `col` 必须在 `cols` 里；`parent` 必须存在且不成环。
3. 所有 `src` / `sources` 引用必须存在于顶层 `sources`。
4. `product.has_futures=false` 时，`research.futures` 必须为空且存在 `gapnote`；`=true` 时 `futures` 必须含交易所与合约代码。
5. 数值字段出现 `约/左右/预计/判断/可能` 等模糊词 → warn（数字必须带口径或来源）。
6. 禁用词：`预计上涨/看涨/看跌/抄底/必涨` → error（研究入口页不做方向判断）。
7. 任何 `value` 为空字符串 → error（用 `null` 或省略表示缺口）。
