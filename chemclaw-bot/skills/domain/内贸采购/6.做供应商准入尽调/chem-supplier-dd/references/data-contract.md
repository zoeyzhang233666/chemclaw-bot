# data.json 数据契约

一个 `data.json` 描述**一份底稿的全部内容**。渲染器不认识"纯碱"，只认识这里的字段。
结构 = 元信息 + 11 个模块（sections）+ 证据表；每个模块由若干**区块（block）**组成。

最小骨架见 `templates/data.template.json`；完整实例见 `examples/soda-ash/data.json`。

---

## 1. 顶层字段

```jsonc
{
  "meta":   { … },        // 必填：编号、主体、品类、截止日
  "hero":   { … },        // 封面区
  "seal":   { … },        // 右上角结论印章
  "kpis":   [ … ],        // 封面下 3–5 个数字
  "nav":    [ … ],        // 左侧目录（与 sections 一一对应）
  "donut":  { … },        // 目录下方环形指标
  "verdict":{ "scores": [ … ] },   // 维度评分（结论页复用）
  "sections":[ … ],       // 必填：正文模块
  "certificates": [ … ],  // 全量资质（Excel 第 05 页用，HTML 只展示重点项）
  "evidence": [ … ],      // 必填：证据索引
  "status_defs": { … },   // 可选：覆盖状态词
  "ui": { … }             // 可选：覆盖界面文案
}
```

### meta
| 字段 | 说明 |
|---|---|
| `doc_no` | 底稿编号，如 `DD-2026-SH-001` |
| `title` | 底稿标题，默认"供应商准入尽调底稿" |
| `target` | 被调查主体全称 |
| `product` | 本次采购品类 |
| `as_of` | 数据截止日 `YYYY-MM-DD`，全文唯一时间基准 |
| `author` / `reviewer` | 编制 / 复核岗位 |
| `version` | 如 `v1.0` |
| `page_title` | 可选，浏览器标题 |
| `export_name` | 可选，导出 HTML 的默认文件名 |
| `usage_notes` | 可选，Excel 首页的"使用边界"五条 |
| `extra_rows` | 可选，Excel 首页追加的 `[[k,v], …]` |

### hero / seal
`hero`：`eyebrow`、`h1`、`h1_sub`、`target`、`target_sub`、`scene`（可含 HTML）、`chips:[{k,v}]`。
`seal`：`kicker`、`value`、`line1`、`line2`。`value` 就是结论词，如"有条件准入"。

### kpis
`[{label, value, note, tone}]`，`tone` ∈ `""` / `gold` / `warn`。

### nav
`[{id, title}]`，`id` 必须与 `sections[].id` 一致（`s00`、`s01`…）。

---

## 2. sections（正文模块）

```jsonc
{ "id": "s03", "no": "03", "title": "实际生产与供应能力",
  "sub": "产能是不是真的、产得出来多少、改造期会不会断供",
  "blocks": [ { "type": "lead", "text": "…" }, … ] }
```

`no` 是页面显示的编号（两位数），`sub` 是标题下一行小字。

### 区块类型

| type | 用途 | 字段 |
|---|---|---|
| `verdict` | 结论大块 | `kicker, headline, text, rows:[{k,v}]` |
| `gates` | 准入闸门四宫格 | `title, items:[{code,name,text}]` |
| `lead` | 判断段（带卡片） | `text, muted?` |
| `note` | 提示条 | `text, tone?(warn), mt?` |
| `rows` | 键值行 + 状态 + 证据 | `name?, items:[{k,v,state,evid,note}]` |
| `table` | 通用表格 | 见下 |
| `certs` | 资质表（自动算到期） | `items:[{no,name,start,end,scope,holder}]` |
| `grid2` / `grid3` | 两列/三列卡片 | `cards:[{h, text?, muted?, scores?, table?, chain?, notes?}]` |
| `kpis` | 数字卡 | `grid?, items:[{label,value,note}]` |
| `risks` | 风险卡序列 | `items:[risk…]` |
| `matrix` | 证据强度 × 采购影响矩阵 | `title?, foot?, items?`（不填则自动取本文所有风险） |
| `timeline` | 事件时间轴 | `items:[{date,text,tag}], foot?, hot_tags?` |
| `checklist` | 可勾选清单 | `kind:"mat"|"site", title, items:[…]` |
| `chain` | 控制链条 | `title?, items:[{name,role,code,self}]` |
| `scores` | 评分条 | `title?, items:[{name,value,note,state}], foot?` |
| `evidence` | 证据索引 | `title?`（数据取顶层 `evidence`） |
| `html` | 逃生舱 | `text`（原样插入） |

### table
```jsonc
{ "type": "table", "name": "judicial",
  "title": "…", "foot": "…", "note": "…",
  "columns": [{"h":"核查项","width":"150px"}, {"h":"状态","align":"c"}],
  "rows": [["被执行","未查到","none","E01","备注"]],
  "tag_cols":  {"4": {"高":"exp","中":"soon","低":"ok"}},
  "pill_cols": {"2": true},
  "evid_cols": [3] }
```
- `align`：`l`(默认) / `c` / `r`
- `tag_cols`：列索引 → 值到色调的映射（`exp` 红 / `soon` 琥珀 / `ok` 绿）
- `pill_cols`：列索引 → `true`，该列值按状态词渲染成胶囊
- `evid_cols`：哪几列是证据 ID（渲染成直链原文的标签）

### risk（风险条目）
```jsonc
{ "id":"R03", "dim":"经营", "level":"high", "strength":"strong",
  "impact_level":"high",
  "title":"…", "fact":"…", "impact":"…", "action":"…", "evid":["E05","E08"] }
```
- `level`：`high|mid|low` → 高/中/低风险（决定颜色与排序）
- `strength`：`strong|mid|weak` → 证据强度（矩阵横轴）
- `impact_level`：`high|mid|low` → 对本次采购的影响（矩阵纵轴）
- `fact` 写事实与数字，`impact` 写对我方的具体影响，`action` 写可执行动作

### checklist item
材料：`{code:"M01", category:"主体", name:"营业执照副本", note:"核对要点", priority:"高"}`
实地：`{code:"S01", area:"正门", name:"…", note:"拍摄带时间水印照片", priority:"高"}`

---

## 3. certificates（全量资质）

```jsonc
{ "no":38, "name":"排污许可证", "start":"2023.09.20", "end":"2028.09.19",
  "scope":"…", "holder":"纯碱厂", "relevance":"core" }
```
- 日期支持 `YYYY.MM.DD` / `YYYY-MM-DD` / `YYYY.MM` / `YYYY`
- `relevance`：`core`（本次采购必须）/ `related` / `irrelevant`
- 到期状态由 `as_of` 自动计算：已到期 / N 天后到期（≤180 天）/ 有效

## 4. evidence（证据索引）

```jsonc
{ "id":"E01", "name":"2025 年年度报告", "source":"巨潮资讯网",
  "date":"2026-03-21", "url":"https://static.cninfo.com.cn/…",
  "note":"主体信息、产能、资质清单、股权、财务、诉讼与处罚披露口径" }
```
**正文里出现的每一个证据 ID，都必须在这里有对应条目**（`validate.py` 会拦）。

## 5. 状态词

| key | 默认标签 | 使用场景 |
|---|---|---|
| `ok` | 已核实 | 有一手文件直接支撑 |
| `pub` | 公开可查 | 公开渠道可查，但非一手披露 |
| `none` | 无公开信息 | 查不到，且**不得**解释为"不存在" |
| `todo` | 待核验 | 须供应商材料或现场确认 |
| `risk` | 风险 | 已识别的负面事实 |

覆盖方式：`"status_defs": {"none": {"label":"未取得", "desc":"…", "color":"gray"}}`。

## 6. 文本里能用什么 HTML

`text` / `fact` / `note` 等字段是"富文本段落"，支持：
- 内联标签：`<b>`、`<span class="muted">`、`<br>`
- 空行分段：`\n\n` 会渲染成 `<p>`

不支持 Markdown。标签必须成对（`validate.py` 会警告）。

## 7. 命名约定（Excel 依赖）

`rows` 区块和 `table` 区块加上 `name` 后，Excel 会自动归位：
`subject`→02 主体、`shareholders`/`related`→03 股权、`capacity`/`industry`→04 生产、
`judicial`→06 风险页旁的司法表、`crosscheck`→10 交叉核对。
不带 `name` 也能渲染，只是不进 Excel 的专属页签。
