# 03 · `project.json` 数据模型

`project.json` 是唯一事实源；Excel 和 HTML 都由它生成。字段名固定，换产品只换值，不改脚本。

## 1. 顶层结构

```json
{
  "meta": {},
  "rfq": {},
  "specs": [],
  "sources": [],
  "companies": [],
  "traders": [],
  "conflicts": [],
  "gaps": [],
  "actions": [],
  "rfq_questions": [],
  "recommendations": [],
  "scoring": {}
}
```

完整 Schema 见 `templates/project.schema.json`。

## 2. `meta`

| 字段 | 必填 | 说明 | 示例 |
|---|---|---|---|
| `title` | 是 | 报告标题 | 纯碱生产厂家核验池 |
| `brand` | 是 | 品牌/项目名 | 碱链核验 |
| `product` | 是 | 产品全称 | 重质纯碱（碳酸钠，Na₂CO₃） |
| `product_short` | 是 | 图表/标题用短名 | 纯碱 |
| `cas` | 否 | CAS 号 | 497-19-8 |
| `hs` | 否 | HS 编码 | 2836.20 |
| `standard` | 否 | 执行标准 | GB/T 210-2022 |
| `application` | 是 | 下游用途 | 光伏玻璃 / 浮法玻璃 |
| `destination` | 是 | 收货地全称 | 江苏·苏州（苏州工业园区） |
| `destination_short` | 是 | 距离/地图用短名 | 苏州 |
| `as_of` | 是 | 数据截止日 | 2026-10-19 |
| `capacity_unit` | 是 | 产能单位 | 万吨/年 |
| `quantity_unit` | 是 | 数量单位 | 吨 |
| `currency` | 否 | 币种 | CNY |
| `sample_note` | 是 | 样本覆盖说明 | 17 家、3,030 万吨，约占全国 4,468 万吨的 68% |
| `lede` | 否 | HTML 导语 | 以“……”为示例…… |
| `disclaimer` | 否 | 免责声明 | 仅作采购初筛…… |
| `output_basename` | 否 | 输出文件名前缀 | 纯碱生产厂家核验池_苏州_202610 |

## 3. `rfq`

| 字段 | 说明 |
|---|---|
| `title` | RFQ 标题 |
| `product` | 产品 + 等级 |
| `spec_ref` | 规格标准/参照 |
| `qty_month` | 月需数量（数字） |
| `qty_year` | 年需数量（数字） |
| `destination` | 收货地 |
| `region_pref` | 区域偏好 |
| `application` | 下游用途 |
| `packaging` | 包装 |
| `delivery` | 交付要求 |
| `note` | 备注（示例需求/可替换） |

## 4. `specs`

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 英文短 ID，如 `na2co3` |
| `label` | 是 | 指标中文名 |
| `requirement` | 是 | 采购要求，如 `≥ 99.4%` |
| `unit` | 否 | 单位 |
| `method` | 否 | 检测方法 |
| `why` | 否 | 为什么关键 |
| `critical` | 否 | 是否关键项（true/false） |

## 5. `companies`

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 英文短 ID |
| `name` | 是 | 常用名 |
| `full_name` | 是 | 法定全称 |
| `ticker` | 否 | 股票代码；非上市写 `—` |
| `listed` | 否 | 是否上市 |
| `identity` | 是 | `producer` / `trader` / `agent` / `unknown` |
| `ownership` | 否 | 国有/民营/外资/上市公司子公司 |
| `founded` | 是 | 成立年份或日期 |
| `founded_note` | 否 | 成立说明 |
| `employees` | 否 | 员工数；无则 null |
| `employees_note` | 否 | 员工数口径 |
| `reg_cap` | 否 | 注册资本 |
| `hq` | 是 | 总部/主要基地 |
| `regions` | 是 | 区域数组，如 `["华东","西北"]` |
| `process` | 是 | 工艺/路线 |
| `products` | 是 | 主营产品 |
| `capacity` | 是 | 集团/样本产能（数字） |
| `capacity_year` | 是 | 产能数据年份/口径 |
| `output` | 否 | 产量；无则 null |
| `output_year` | 否 | 产量年份 |
| `scale_note` | 否 | 规模说明 |
| `certainty` | 是 | 生产确定性 0–100 |
| `spec_score` | 是 | 规格匹配 0–100 |
| `availability` | 是 | 外销可得性 0–100 |
| `plants` | 是 | 基地数组 |
| `evidence` | 是 | 证据数组，至少 1 条 A/B |
| `spec_profile` | 否 | 规格画像（标准/重质/低铁等） |
| `spec_rows` | 是 | 规格逐项对照 |
| `strengths` | 是 | 优势数组 |
| `gaps` | 是 | 数据缺口数组 |
| `action` | 是 | 推荐动作 |
| `tier` | 否 | 优先谈判/重点备选/观察/成本备选 |
| `rank` | 否 | 排名 |
| `composite` | 否 | 综合分 |
| `scale_score` | 否 | 规模分 |
| `distance_score` | 否 | 距离分 |
| `spec_open` | 否 | 有公开信息的规格项数 |
| `spec_conclusion` | 否 | 规格结论 |

## 6. `plants`

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | 是 | 基地名 |
| `province` | 是 | 省 |
| `city` | 是 | 市 |
| `address` | 是 | 公开地址 |
| `lon` / `lat` | 否 | 经纬度，用于直线距离 |
| `capacity` | 是 | 基地产能（数字） |
| `capacity_year` | 是 | 产能年份/口径 |
| `process` | 是 | 工艺 |
| `products` | 否 | 主要产品 |
| `note` | 否 | 备注 |
| `source_ids` | 是 | 来源 ID 数组 |
| `distance_km` | 否 | 到收货地直线距离 |
| `distance_band` | 否 | 距离带 |

## 7. `evidence`

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 证据 ID |
| `level` | 是 | `直接-A` / `直接-B` / `间接-C` / `仅工商-D` |
| `type` | 是 | 定期报告/政府公告/环评/官网/IR/新闻/招聘等 |
| `title` | 是 | 标题 |
| `date` | 是 | 日期 |
| `org` | 是 | 机构 |
| `url` | 否 | 链接 |
| `quote` | 是 | 原文摘录 |
| `proves` | 是 | 证明事项 |
| `source_id` | 是 | 来源库 ID |

## 8. `spec_rows`

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 对应 `specs.id` |
| `label` | 是 | 指标名 |
| `requirement` | 是 | 采购要求 |
| `status` | 是 | `部分公开` / `未公开` / `待验证` |
| `public_info` | 是 | 公开信息/标准 |
| `gap` | 是 | 缺口 |
| `next_action` | 否 | 下一步动作 |

## 9. `sources`

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | `S01` 格式 |
| `org` | 是 | 机构 |
| `title` | 是 | 标题 |
| `date` | 是 | 日期 |
| `grade` | 是 | A/B/C/D |
| `url` | 否 | 链接 |
| `used` | 是 | 用于什么 |
| `accessed` | 否 | 访问日 |

## 10. `traders`

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | 是 | 公司名 |
| `type` | 是 | 贸易商/代理/盐业流通/店铺 |
| `region` | 是 | 地区 |
| `level` | 是 | 证据等级 |
| `evidence` | 是 | 公开证据 |
| `why` | 是 | 为什么不是生产 |
| `action` | 是 | 处理/补证建议 |

## 11. `conflicts` / `gaps` / `actions`

```json
{
  "conflicts": [
    {"topic": "某公司产能", "a": "60万吨/年", "b": "35万吨/年", "resolution": "并列保留，待环评复核", "impact": "影响华南可供量"}
  ],
  "gaps": [
    {"gap": "批次COA缺失", "affected": "全部", "impact": "无法确认 Fe₂O₃/粒度", "verify": "索取连续3批COA", "priority": "P0"}
  ],
  "actions": [
    {"phase": "第1周", "action": "发统一RFQ", "detail": "统一规格/数量/收货地，要求出厂价+到厂价"}
  ]
}
```

## 12. `rfq_questions` / `recommendations`

```json
{
  "rfq_questions": ["请确认生产工厂全称、地址、产能与2025年实际产量。"],
  "recommendations": [
    {"tier": "主供候选", "company": "某公司", "note": "最近、产能大、证据强"}
  ]
}
```

## 13. `scoring`

```json
{
  "weights": {"certainty": 0.35, "spec": 0.30, "scale": 0.20, "distance": 0.15},
  "tiers": [
    {"min": 84, "label": "优先谈判"},
    {"min": 78, "label": "重点备选"},
    {"min": 0, "label": "观察/成本备选"}
  ]
}
```

## 14. 最小示例

见 `templates/project.example.json`。它只有 1 家公司，用于验证字段，不是完整报告。

## 15. 生成前自检

```bash
python scripts/validate_project.py my-project.json
```

校验会检查：

- 必填字段；
- `source_id` 是否存在；
- 每家公司是否至少有 1 条 A/B 证据；
- `spec_rows` 是否覆盖全部 `specs`；
- 是否存在“仅工商-D”却进入 `companies` 的公司；
- 产能/产量是否带年份；
- 权重是否合计为 1；
- 排名/评分是否可计算。
