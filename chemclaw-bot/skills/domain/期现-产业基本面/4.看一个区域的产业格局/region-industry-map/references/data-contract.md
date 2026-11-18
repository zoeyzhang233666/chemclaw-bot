# regions.json 数据契约

一份 JSON 描述一个品种在一个区域的产业格局。`build_html.py` 与 `build_xlsx.py` 都只读这一份文件。

> 约定：`null` / 缺省 = **未取得**。不要用 `0` 表示"没有数据"；确实为零（如"该市无纯碱产能"）才写 `0`。

---

## meta（必需）

| 字段 | 类型 | 说明 |
|---|---|---|
| `product` | str | 品种全称，可带学名/规格：`"纯碱（碳酸钠 Na2CO3；轻质/重质）"` |
| `region` | str | 区域名：`"山东省"` |
| `region_level` | str | `省` / `市` / `大区` / `全国` |
| `asof` | str | 数据截止日 `YYYY-MM-DD` |
| `capacity_unit` | str | 默认 `万吨/年` |
| `capacity_basis` | str | 默认口径：`名义/设计产能（≠产量、≠可售量）` |
| `scope_note` | str | 覆盖说明：已核实厂区 + 地区级记录 |
| `title` / `subtitle` | str | HTML 首屏标题与副标题（副标题要包含**结论性的数字**） |
| `tags` | [str] | 3–6 个标签，首屏展示 |
| `focus_provinces` | [str] | 地图高亮省（不带"省"字也可，`norm_prov` 会归一） |
| `hub_label` | str | 中心枢纽标签（如"山东纯碱装置（潍坊）"） |
| `capacity_scope_total` | num | 区域**公开口径**产能合计（用于覆盖率）；未取得则省略 |
| `capacity_scope_note` | str | 公开口径的出处 |
| `data_notes` | [str] | 首屏展示的 2–3 条口径提醒 |
| `filters` | obj | `{site_types, processes, grades}`，决定筛选器选项 |

---

## sites[]（核心，一行 = 一个厂区/据点）

| 字段 | 必填 | 说明 |
|---|---|---|
| `site_id` | ✔ | 唯一 id，推荐 `省缩写-企业-厂区`：`sd-haihua-hs` |
| `company_id` | ✔ | 指向 `companies[].id`；否证条目也要先建 company |
| `site_name` | ✔ | **厂区名**，不是公司名 |
| `role` | ✔ | `production` / `trader` / `downstream` |
| `site_type` | ✔ | `生产工厂` / `一体化/配套装置` / `贸易/仓储` / `仓储` / `下游工厂` |
| `route` | ✔ | 工艺：按品种改枚举。未确认写 `"未知"`，非生产写 `"—"` |
| `capacity` | 数值 or null | **换算后的数值**（万吨/年）；无公开口径 → null |
| `raw_capacity` | str | **原文摘录**，一个字都不改 |
| `capacity_basis` | str | 口径：设计/名义/实际产量/历史产能/否证 |
| `status` | ✔ | `在产` / `在建` / `拟建` / `停产` / `退出` |
| `province` `city` `district` | ✔ | 行政区，`district` 可空 |
| `park_id` | | 指向 `parks[].id`；园区未核实则省略（不要瞎填） |
| `lon` `lat` | | 无可靠依据 → null |
| `precision` | ✔ | `精确` / `园区级` / `县级` / `市级` |
| `coord_source` | ✔ | `企业官网`/`政府公示`/`园区公开资料`/`新闻报道`/`地图地名库`/`人工核对`/`未核实` |
| `reg_address` `reg_address_type` | ✔ | 类型：`注册地址` / `实际生产地址（注册地同址）` / `园区地址` |
| `plant_address` `address_type` | ✔ | 类型：`实际生产地址` / `园区地址` / `镇村地名` / `未核实` |
| `products` | [str] | 产品清单 |
| `upstream` `downstream` | [str] | 定性关联（人读，不参与计算） |
| `evidence_grade` | ✔ | A/B/C/D，见 `evidence-grading.md` |
| `source_ids` | [str] | 指向 `sources[].id`；空数组 = 未核实 |
| `note` | str | 关键判断的理由（为什么降级、为什么并列两个口径） |
| `verify` | [str] | **待核实清单**（会进 Excel 与缺口表） |

---

## companies[] / cities[] / parks[]

```json
// companies[]：企业层，不承担产能
{"id": "haihua", "name": "山东海化股份有限公司", "group": "山东海化集团",
 "listed": "000822.SZ", "note": "氨碱老线 120 + 新线 160 = 280 万吨"}

// cities[]：区域层，与厂区口径对账用
{"province": "山东省", "city": "潍坊市", "registered": null, "reg_unit": "（工商口径未取得）",
 "capacity": 430, "capacity_covered": 430, "data_grade": "A", "note": "全省纯碱产能 100%"}

// parks[]
{"id": "park-wfbinhai", "name": "潍坊滨海化工产业园", "level": "省级",
 "province": "山东省", "city": "潍坊市", "district": "滨海经济技术开发区", "short": "潍坊滨海",
 "main_industries": ["盐化工/纯碱", "氯碱"], "soda_relevance": "海化纯碱厂所在园区",
 "supporting": ["益羊铁路大家洼站接轨胶济线", "毗邻潍坊港中港区"],
 "lon": 119.02, "lat": 37.13, "precision": "园区级", "coord_basis": "企业群中心 ±2 km",
 "evidence_grade": "A", "source_ids": ["wfbinhai-park"], "note": ""}
```

`cities[].capacity` 是**公开口径**；`capacity_covered` 可省略。
两者都留空表示"该市公开口径未取得"——此时不要用厂区合计回填。

---

## projects[]

| 字段 | 说明 |
|---|---|
| `id` `name` `company_id` | 标识 |
| `type` | `新建` / `扩建` / `技改` / `置换` / `退出` |
| `capacity` `capacity_retired` | 毛新增 / 退出。**置换类必须两栏都填** |
| `net` | 可省略，`common.normalize()` 自动算 `capacity - capacity_retired` |
| `status` `status_asof` | 状态 + **时点**（必需） |
| `start` `online` | 计划开工/投产（`YYYY-MM`） |
| `products` `impact` | 产品与影响（不同产品分开写） |
| `park` `district` `lon/lat` `precision` | 位置 |
| `verify` | 待核实 |

---

## upstream[] / downstream[] / nodes[] / flows[]

```json
// upstream[]
{"material": "原盐（海盐）", "spec": "滩晒海盐", "name": "山东海化股份公司羊口盐场",
 "province": "山东省", "city": "潍坊市", "quant": "采矿面积 120.39 km²，生产规模 240 万吨",
 "note": "原盐全部供海化纯碱厂，但自产不足、外购超 50%", "evidence_grade": "B", "source_ids": [...]}

// downstream[]
{"segment": "浮法玻璃", "company": "山东金晶科技股份有限公司", "plant": "淄博基地（博山区）",
 "province": "山东省", "city": "淄博市", "scale": "5×600t/d（一条暂时停产）",
 "use": "重碱作助熔剂", "note": "部分由海天纯碱配套", "evidence_grade": "A", "source_ids": [...]}

// nodes[]：物流节点
{"id": "n-wfport", "name": "潍坊港中港区", "role": "port", "province": "山东省", "city": "潍坊市",
 "lon": ..., "lat": ..., "precision": "园区级",
 "cap_note": "12 泊位、通过能力 799 万吨", "evidence": "装卸清单含纯碱",
 "evidence_grade": "B", "source_ids": [...]}
// role 枚举：port 港口 / rail 铁路专用线 / depot 交割仓储 / market 交易市场 / road 陆路通道 / logistics_park 物流园

// flows[]：有公开来源的流向（没来源就别写）
{"id": "f1", "kind": "downstream", "material": "重碱", "from_site": "sd-haihua-hs",
 "to_node": "n-wfport", "volume": "未取得", "note": "...", "evidence_grade": "C", "source_ids": [...]}
```

---

## prices

```json
"prices": {
  "observations": [
    {"asof": "2026-10-19", "spec": "轻碱", "region": "华东（含山东）", "value": 1000,
     "unit": "元/吨", "basis": "出厂含税（华东）", "note": "隆众：1000-1100 元/吨",
     "sources": ["lz-1019"]}
  ],
  "regional_features": [
    {"region": "潍坊（滨海/昌邑）", "feature": "产地端，唯一大规模自产集散地", "source": ["wfsw-0921"]}
  ],
  "note": "价格只记观察值，同日多口径并列不取平均"
}
```

**价格观察的五个必备项**：日期、规格、区域、口径（出厂/送到/含税/承兑）、来源。缺一项就不写。
`value` 取区间时取中值并把区间写进 `note`——不要悄悄取中值。

---

## conclusions[] / narrative

```json
"conclusions": [
  {"text": "结论句（可含 HTML 加粗）", "method": "口径/依据", "sources": ["id1", "id2"]}
],
"narrative": {
  "coverage_note": "样本 430 = 280 + 150；另 450 口径出处…差额不分摊",
  "address_rule": "注册地址只用于确认法人主体…",
  "route_note": "工艺路线说明（氨碱/联碱/天然碱）",
  "sankey_note": "连线为定性流向，不表示吨位",
  "concentration_note": "集中度高 ≠ 有定价权，理由…",
  "project_note": "本区域只登记 N 个项目，XX 经否证不入表",
  "price_diff_factors": [{"text": "运费方向：…", "source": ["id"]}],
  "gaps": [{"item": "缺口事项", "scope": "涉及区域", "why": "为什么缺",
            "impact": "对结论的影响", "how": "补齐方式", "priority": "P0"}],
  "method": [{"k": "主体口径", "v": "企业 ≠ 厂区…"}],
  "usage": ["使用边界 1", "使用边界 2", "使用边界 3"]
}
```

`gaps` 是最重要的一节：它是**下一轮调研的作业单**，不是免责声明。每条必须能回答"怎么补"。

---

## sources[]

```json
{"id": "haihua-annual", "n": 1, "publisher": "山东海化股份有限公司（000822）",
 "title": "山东海化 2025 年年度报告（主要产品产能表）", "url": "https://...",
 "date": "2026-03", "doc_type": "上市公司年报", "grade": "A",
 "note": "纯碱设计产能 280 万吨/年、利用率 97.29%"}
```

- `id` 全局唯一，建议 `主体-类型-日期` 风格；
- `note` 写**你引用的那一句**，复核时只核这一句；
- 无公开链接的内部材料：`url` 留空，`note` 写材料名与取得时间，`grade` 不得为 A；
- `S<n>` 编号由脚本按顺序生成，正文里引用写成"来源 S1"。

---

## 枚举速查

| 字段 | 取值 |
|---|---|
| `role` | production / trader / downstream |
| `precision` | 精确 / 园区级 / 县级 / 市级 |
| `coord_source` | 企业官网 / 政府公示 / 园区公开资料 / 新闻报道 / 地图地名库 / 人工核对 / 未核实 |
| `evidence_grade` | A / B / C / D |
| `status` | 在产 / 在建 / 拟建 / 停产 / 退出 |
| `route`（纯碱） | 氨碱 / 联碱 / 天然碱 / 其他 / 未知（非生产写 "—"） |
| `project.type` | 新建 / 扩建 / 技改 / 置换 / 退出 |
| `node.role` | port / rail / depot / market / road / logistics_park |
| `priority` | P0 / P1 / P2 |

换品种时改 `scripts/common.py` 的 `PROCESSES` 与本表。
