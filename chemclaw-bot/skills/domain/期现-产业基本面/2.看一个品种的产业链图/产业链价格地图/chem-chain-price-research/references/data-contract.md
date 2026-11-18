# chain-data.json 数据契约

页面只有一个数据源：`chain-data.json`。生成器、校验器都按本文的规则工作。
把数据写对，页面就对了；数据写错，生成器不会替你猜。

## 顶层结构

```json
{
  "meta":   { ... },          // 必填：标题、数据日、单位、来源
  "stages": [ ... ],          // 必填：产业链分列（上游 → 本体 → 下游）
  "nodes":  [ ... ],          // 必填：链上每个品种 / 环节
  "links":  [ ... ],          // 必填：环节之间的关系
  "tables": [ ... ],          // 可选：附加明细（资讯口径、参照品等）
  "gaps":   [ ... ],          // 强烈建议：没查到价格的环节
  "notes":  { ... }           // 强烈建议：口径、方法、来源说明
}
```

## meta

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | ✅ | 页面标题，如「SBS 产业链价格地图」 |
| `product` | | 品种代码，如 `SBS` |
| `data_date` | ✅ | 价格数据日，`YYYY-MM-DD`。页面所有"最新价"都以此为基准 |
| `retrieved_at` | | 检索时间（页面显示用） |
| `unit` | ✅ | 全局价格单位，如 `元/吨`。**缺单位不得画价格图** |
| `lang` | | 默认 `zh-CN` |
| `headline` | ✅（建议） | 一句话核心结论 |
| `basis_note` | | 明细区上方的一句话口径提示 |
| `sources` | ✅ 非空 | `[{name, type, note}]`，`type` 如 `price_db` / `news` / `report` |

## stages（分列，决定图的横向结构）

```json
{ "key": "up", "label": "上游原料", "color": "up" }
```

- `key` 必填且唯一；`label` 是列标题。
- `color` 可选，取调色板键：`up` / `mid` / `raw` / `product` / `app`（依次为蓝 / 绿 / 橙 / 紫 / 棕）。
  不写就按顺序自动分配。
- 列的顺序 = 数组顺序，**从左到右就是产业链方向**。

## nodes（环节卡片）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✅ | `^[a-zA-Z0-9_-]{1,40}$`，唯一；连线用它引用 |
| `name` | ✅ | 品种名，如 `丁二烯` |
| `stage` | ✅ | 必须等于某个 `stages[].key` |
| `role` | | `material`（默认，有价环节）或 `application`（下游应用，本次无价） |
| `price` | material ✅ | 图上大字标注价，**必须是本环节某条原始记录里的值** |
| `unit` | | 省略则用 `meta.unit` |
| `basis` | 建议 ✅ | 口径短句，如 `华东 · 聚合级 · 含税`（≤ 18 字） |
| `desc` | | 悬停/点击面板里的长说明 |
| `rows` | material ✅ 非空 | 原始报价记录，见下 |
| `gap_label` | application ✅ | 缺价原因，如 `本次无授权报价` |
| `short` | application ✅ 1–3 行 | 卡片上的短句（每行 ≤ 24 字） |

### rows（原始报价记录）

```json
{ "region": "华东", "spec": "聚合级", "price": "13,234", "date": "2026-10-15",
  "source": "现货报价库", "note": "自提、含税", "missing": false }
```

- `price` 必填。**查不到就写 `"missing": true` 并把原因写进 `note`，不要写 0、不要写区间估计**。
- `date` 省略即 `meta.data_date`。
- `region` 若原始数据里是占位值（`地区`、`——`），写成 `未标注` 或 `未细分`，不要伪装成真实地区。
- 同一 `(region, spec, price, date)` 重复行会被校验器提示去重（可保留，但应说明是多个来源同值）。

## links（关系）

```json
{ "from": "butadiene", "to": "sbsdry", "label": "聚合单体", "kind": "solid" }
```

- `from` / `to` 必须存在，不允许自环。
- `label` 是关系短标签（≤ 8 字），读者靠它理解传导方向。
- `kind`：`solid`（默认）用于主原料路径；`dashed` 用于溶剂、助剂、非等量投入。

## gaps（缺口清单）

```json
{ "scope": "SBS 改性沥青", "reason": "本次授权数据源中观测数为 0，未取到任何报价",
  "evidence": "行情接口返回 observations=0" }
```

`evidence` 让读者知道"没查到"是因为真的查了（而不是漏查）。缺口是这份交付物的正式内容，不是缺陷。

## notes（口径说明）

```json
{
  "price_basis": ["图上价格为…"],
  "chain_basis": ["产业链按示意绘制…"],
  "gap_notes":   ["未取到报价的环节保持空白，不以估算值填充"],
  "source_notes":["价格来源：现货报价库；资讯来源：市场资讯"]
}
```

## 版面预算（超了会报错，只能改文案）

字宽估算：CJK/全角 1 em，ASCII 约 0.56 em。

| 元素 | 上限 |
|---|---|
| 有价卡片宽度 | 320 px → `name` ≤ 8 字，`price+unit` ≤ 11 字符，`basis` ≤ 18 字 |
| 应用卡片宽度 | 460 px → `short` 每行 ≤ 24 字 |
| 有价卡片高度 | 固定 112 px |
| 应用卡片高度 | 40 + 26 + 22×行数 + 14 |

价格保留原始精度（千分位与小数位照抄），不要自己四舍五入——页面上的数字必须能在 `rows` 里逐字找到。

## 起手方式

复制 `examples/template-example/chain-data.json`，把 `stages` / `nodes` 换成目标品种，
先填结构（`price` 留空、`rows` 留空），跑一次 `build_chain_html.py` 看骨架，
再逐环节补 `rows` 和 `price`。骨架阶段校验器报的错可以先忽略（它要求有价环节必须有记录）。
