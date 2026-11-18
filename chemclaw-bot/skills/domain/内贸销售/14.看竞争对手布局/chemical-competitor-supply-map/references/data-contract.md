# 数据契约 · data.json

> 唯一数据源。HTML 和 Excel 都从它生成；换产品/区域只改这个文件。
> 机器校验以 `scripts/validate.py` 为准，本文件解释字段和常见错误。

## 1. 最小可用结构

```json
{
  "meta": {
    "product": "产品全称",
    "product_short": "简称",
    "unit": "万吨/年",
    "asof": "2026-10-19",
    "region": "省 · 市",
    "province": "省",
    "city": "市",
    "target_lon": 113.08,
    "target_lat": 22.58,
    "anchor_customer": "锚点客户全称",
    "anchor_short": "锚点简称",
    "processes": [
      {"name": "工艺甲", "color": "#2F6F8F"},
      {"name": "工艺乙", "color": "#B4642D"}
    ],
    "distance_bands": [
      {"label": "≤300km 本地", "max": 300},
      {"label": "300–800km 近邻", "max": 800},
      {"label": "800–1500km 长途", "max": 1500},
      {"label": ">1500km 超长途", "max": null}
    ]
  },
  "target": {
    "province": "省",
    "city": "市",
    "region": "省 · 市",
    "lon": 113.08,
    "lat": 22.58,
    "customer": "锚点客户全称",
    "customer_short": "锚点简称"
  },
  "companies": [
    {
      "id": "co_1",
      "name": "企业全称",
      "short": "简称",
      "ticker": "000000 / 非上市",
      "alias": "曾用名（可选）",
      "hq": "总部",
      "process": "工艺甲",
      "capacity": 100,
      "output": 80,
      "cap_year": "2025",
      "grade": "A",
      "products": "产品/牌号",
      "coverage": "区域覆盖线索（D）",
      "new": "新增/在建描述",
      "source_ids": ["S01"],
      "projects": ["pr_1"]
    }
  ],
  "plants": [
    {
      "id": "pl_1",
      "company_id": "co_1",
      "name": "工厂名",
      "province": "省",
      "city": "市",
      "lon": 111.7,
      "lat": 38.5,
      "process": "工艺甲",
      "capacity": 100,
      "cap_year": "2025",
      "products": "产品",
      "note": "口径/备注",
      "grade": "A",
      "source_ids": ["S01"],
      "label_position": "right"
    }
  ],
  "projects": [
    {
      "id": "pr_1",
      "company_id": "co_1",
      "name": "项目名",
      "location": "省 · 市",
      "process": "工艺甲",
      "capacity": 50,
      "kind": "新建",
      "status": "环评",
      "year": 2027,
      "timing": "2027E",
      "net": "净增 50（假设无置换）",
      "impact": "对目标区域的影响",
      "grade": "B",
      "source_ids": ["S02"],
      "lon": 111.7,
      "lat": 38.5
    }
  ],
  "prospects": [
    {
      "id": "cu_1",
      "name": "客户全称",
      "short": "客户简称",
      "city": "市",
      "province": "省",
      "segment": "玻璃",
      "scale": "2×600t/d",
      "ash": "0.5–1.0 万吨/年*",
      "scene": "重碱/玻璃窑炉",
      "priority": "S",
      "why": "为什么优先",
      "next": "下一步动作",
      "grade": "C",
      "source_ids": ["S03"]
    }
  ],
  "sources": [
    {
      "id": "S01",
      "org": "机构",
      "title": "标题",
      "date": "2026-01-10",
      "url": "https://...",
      "used": "用于哪个数字",
      "type": "A"
    }
  ],
  "conflicts": [
    {
      "item": "冲突项",
      "a": "口径 A",
      "b": "口径 B",
      "adopt": "采用",
      "why": "理由",
      "impact": "影响"
    }
  ],
  "gaps": [
    {"title": "样本不是全行业", "body": "下一步怎么补"}
  ],
  "boundaries": [
    {"title": "不推算市场份额", "body": "本报告只做样本覆盖"}
  ],
  "demand_by_prov": {
    "省": "需求/空白线索，写年份与来源"
  },
  "narrative": {}
}
```

## 2. 字段说明

### `meta`（必填）

| 字段 | 类型 | 说明 |
|---|---|---|
| `product` | str | 产品全称，进标题/Excel |
| `product_short` | str | 简称，进标题/图例；缺省用 product |
| `unit` | str | 默认 `万吨/年`；全文统一 |
| `asof` | str | 数据截至日 `YYYY-MM-DD`；也是项目“未来”基准年 |
| `region` | str | `省 · 市`，显示用 |
| `province` / `city` | str | 目标省/市，必须与 target 一致 |
| `target_lon` / `target_lat` | number | 目标经纬度，必填；用于距离和地图 |
| `anchor_customer` / `anchor_short` | str | 锚点客户全称/简称 |
| `processes` | array | `[{name, color}]`；颜色建议 4–8 个 |
| `distance_bands` | array | `[{label, max}]`；最后一条 `max:null` |
| `coverage` | object | 可选 `{industry_low, industry_high}`；用于样本覆盖度，不用于市场份额 |
| `output_year` | str | 产量年份，如 `2025` |
| `target_demand` / `target_demand_label` | number/str | 目标区域需求（可选，标 `*`） |
| `target_note` | str | 目标卡脚注（距离/需求口径） |
| `dose_label` / `use_label` | str | 潜客表列名，如“用碱量级”“用碱场景” |
| `label_province` | str | 地图上默认显示产能标签的省 |
| `label_capacity_min` | number | 工厂标签显示阈值，默认 330 |
| `project_labels` | array | 地图上显示项目标签的 project id |
| `map_center` / `map_zoom` | array/number | 地图初始视角 |
| `grade_note` | str | 证据分级说明 |
| `disclaimer` | str | 页脚免责声明 |
| `is_synthetic` | bool | 示例数据必须 `true`，防止误用 |
| `brand_name` / `brand_sub` / `brand_mark` | str | 页眉品牌 |

### `target`（必填）

| 字段 | 说明 |
|---|---|
| `province` / `city` / `region` | 目标区域 |
| `lon` / `lat` | 目标坐标；必须与 meta 一致 |
| `customer` / `customer_short` | 锚点客户全称/简称 |
| `note` | 可选，目标备注 |

### `companies`（必填，≥1）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 唯一，建议 `co_*` |
| `name` | 是 | 企业全称 |
| `short` | 建议 | 矩阵/地图简称 |
| `ticker` / `alias` | 否 | 代码/曾用名 |
| `hq` | 建议 | 总部 |
| `process` | 是 | 必须出现在 `meta.processes`（否则自动补色） |
| `capacity` | 是* | 样本产能；省略则自动=工厂合计 |
| `output` | 否 | 最新产量；没有就 `null`，不要用产能替代 |
| `cap_year` | 建议 | 产能数据年份 |
| `grade` | 是 | A/B/C/D |
| `products` | 否 | 产品/牌号 |
| `coverage` | 否 | 区域覆盖线索（D 推断） |
| `new` | 否 | 新增/在建摘要 |
| `source_ids` | 是 | 至少 1 个存在的来源 |
| `projects` | 否 | project id 数组；脚本也会按 `company_id` 自动挂 |

> `capacity` 与工厂合计差 >0.51 会直接报错。多基地企业务必拆工厂。

### `plants`（必填，≥1）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 唯一，建议 `pl_*` |
| `company_id` | 是 | 必须存在 |
| `name` | 是 | 工厂/基地名 |
| `province` / `city` | 是 | 工厂所在地，不是总部 |
| `lon` / `lat` | 是 | 工厂坐标 |
| `process` | 是 | 工艺 |
| `capacity` | 是 | >0 |
| `cap_year` | 建议 | 产能年份 |
| `products` | 否 | 产品 |
| `note` | 否 | 口径/备注 |
| `grade` | 是 | A/B/C/D |
| `source_ids` | 是 | 至少 1 个 |
| `label_position` | 否 | 地图标签方位 `left/right/top/bottom` |

### `projects`（建议 ≥1）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 唯一 |
| `company_id` | 是 | 必须存在 |
| `name` | 是 | 项目名 |
| `location` | 是 | 地点 |
| `process` | 是 | 工艺 |
| `capacity` | 是 | >0（本项目毛增量） |
| `kind` | 是 | 新建/扩建/技改/搬迁/置换 |
| `status` | 是 | 规划/备案/环评/开工/试生产/投产 |
| `year` | 是 | 预计年；用于时间线和 2026+ 汇总 |
| `timing` | 是 | 时间/进展描述 |
| `net` | 是 | 净增判断；不要只写规模 |
| `impact` | 是 | 对目标区域的影响 |
| `grade` | 是 | 证据等级 |
| `source_ids` | 是 | 至少 1 个 |
| `lon` / `lat` | 否 | 有则地图显示项目点 |

### `prospects`（建议 ≥3）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 唯一 |
| `name` / `short` | 是 | 客户全称/简称 |
| `city` / `province` | 是 | 所在地 |
| `segment` | 是 | 赛道，用于筛选 |
| `scale` | 是 | 公开规模（产线/产能/项目） |
| `ash` 或 `dose` | 是 | 用量级，标 `*` 表示推算 |
| `scene` | 是 | 使用场景 |
| `priority` | 是 | S/A/B/C |
| `why` | 是 | 为什么优先 |
| `next` | 是 | 下一步动作 |
| `grade` | 是 | 证据等级 |
| `source_ids` | 是 | 至少 1 个 |

### `sources`（必填，≥1）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 唯一，建议 `S01` |
| `org` | 是 | 机构 |
| `title` | 是 | 标题 |
| `date` | 是 | 日期 |
| `url` | 是 | 公开链接；HTML/Excel 可点击 |
| `used` | 是 | 用于哪个数字 |
| `type` | 是 | A/B/C/D |

### `conflicts`（建议 ≥1）

| 字段 | 说明 |
|---|---|
| `item` | 冲突项 |
| `a` / `b` | 两个口径 |
| `adopt` | 采用哪个 |
| `why` | 为什么 |
| `impact` | 如果采用另一个，结论怎么变 |

### `gaps` / `boundaries`

`gaps` 是“下一步取证清单”；`boundaries` 是“本报告不做什么”。每项 `{title, body}`。建议 `gaps ≥5`。

### `demand_by_prov`

`{"省": "需求/空白线索（年份+来源）"}`。没有就留空，不要编。

### `narrative`

| 字段 | 用途 |
|---|---|
| `hero_lede` | 首屏导语 |
| `national_note` / `how_to_read` | 右侧面板说明 |
| `map_sub` / `density_sub` / `pipeline_intro` / `prospect_intro` / `prospect_note` | 各章节导语 |
| `conclusions` | 首屏 3 张结论卡：`no/tag/title/body/foot/big` |
| `pipeline_foot` | 时间线底部判断 |
| `anchor_facts` | 锚点客户事实卡：`[{label,value}]` |
| `anchor_use_value` / `anchor_use_label` | 锚点用量大数字 |
| `anchor_note` | 锚点脚注 |
| `prospect_conclusions` | 潜客区 3 张动作卡 |
| `method_conclusions` | 方法区 3 张结论卡 |
| `prospect_scope_note` | 潜客范围说明 |

## 3. 自动计算字段

`common.build()` 会自动补：

- `target`（从 meta 生成）；
- 每个工厂的 `km`、`band`、`process_color`、`company`、`company_short`；
- 每个企业的 `plants`、`plant_count`、`min_km`、`band`、`projects`；
- 每个项目的 `company`、`company_short`、`process_color`；
- `provs`（省级聚合：产能、工厂、企业、主导工艺、最近 km、潜客数）；
- `bands`（距离带合计）；
- `process_totals`、`total_cap`、`total_out`、`total_companies`、`total_plants`；
- `prospect_by_prov`、`source_map`、`narrative` 默认值。

这些字段**不要手写**；手写会被覆盖。

## 4. 常见错误

| 现象 | 原因 | 修法 |
|---|---|---|
| `企业产能 100 与工厂合计 80 不一致` | 企业产能没扣非目标产品/多基地漏拆 | 拆工厂或改企业产能 |
| `工厂 ... 缺少 lon/lat` | 只写地址没坐标 | 补经纬度；用地图/官网核对 |
| `引用不存在的来源 S99` | source_ids 拼错/漏 source | 补 source 或改 ID |
| 地图上工厂堆在总部 | 用总部坐标 | 改成工厂坐标 |
| 距离带合计对不上 | 工厂产能/band 异常 | 看 `bands` 是否被手写覆盖 |
| 样本覆盖率 >100% | 样本口径 > 全国口径 | 检查 coverage 或样本 |
| HTML `None` | 模板空值 | 补字段；或检查 `sources.used` |
| Excel 合并重叠 | 手工改表 | 重新生成，不要手改 |

## 5. 版本与兼容

- `data.json` 是普通 JSON，无 schema 版本号；新增字段应保持向后兼容。
- 新增必填字段会破坏旧数据；尽量不要。
- 如果平台只接受 YAML/CSV，先转成 JSON 再构建；不要直接改脚本里的数据。

## 6. 最小自检命令

```bash
python scripts/validate.py data.json
python scripts/build_all.py data.json out/
python scripts/qa.py --data data.json --html out/*.html --xlsx out/*.xlsx
```
