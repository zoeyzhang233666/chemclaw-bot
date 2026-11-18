# 数据契约：`project.json` 字段手册（唯一真源）

> 本技能的所有数字都来自**一个** `project.json`。HTML 与 Excel 由脚本从它生成，**禁止手改产物里的数字**。
> 字段名是本契约的接口，换品种时不改名，只换内容。

---

## 0. 设计原则

1. **事实与假设在结构上分开**：`project` / `capacity_bases` / `unit_consumption` 主张"这是查到的"；`assumptions` 主张"这是我们设的"。
2. **所有量用"吨/年"存储**：避免万吨/吨混淆；展示层统一换算。
3. **每个数字都带证据**：`evidence: {level, source, url, date}`，可缺省但缺省即 `E5`。
4. **派生值不写进 JSON**：占比、产量、原料需求一律由 `scripts/compute.py` 计算，不手工填。

---

## 1. 顶层结构

```json
{
  "meta": { ... },
  "project": { ... },
  "chain": { ... },
  "capacity_bases": [ ... ],
  "unit_consumption": [ ... ],
  "assumptions": { ... },
  "scenarios": [ ... ],
  "stakeholders": [ ... ],
  "regional": { ... },
  "facts": [ ... ],
  "gaps": [ ... ],
  "sources": [ ... ]
}
```

### 1.1 `meta`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | str | ✅ | 报告标题 |
| `product` | str | ✅ | 产品名，如"聚丙烯" |
| `product_en` | str | | 英文/简称，如 PP |
| `process` | str | | 工艺路线简述 |
| `asof` | str `YYYY-MM-DD` | ✅ | **数据截止日**（不是写作日） |
| `analyst` | str | | 编制人/机构 |
| `disclaimer` | str | | 免责声明（默认有） |
| `simulated` | bool | | **模拟输入标记**：为 true 时，HTML/Excel 顶部强制显示"模拟数据，非真实项目"横幅 |
| `simulated_note` | str | | 模拟说明 |

---

## 2. `project`：项目事实核验卡

```json
"project": {
  "name": "本文所称项目名（可用占位）",
  "owner": "业主全称",
  "owner_short": "简称",
  "location": {"province": "", "city": "", "district": "", "park": "", "lat": 0.0, "lon": 0.0},
  "product_spec": "产品与牌号范围",
  "design_capacity_t": 400000,
  "capacity_scope": "一期单套装置公称能力",
  "stage": "备案",
  "stage_note": "环评公示已受理，尚未开工",
  "startup_plan": {"year": 2027, "month": 6, "text": "公告原文：计划 2027 年 6 月建成投产", "announce_date": "2025-12-01"},
  "invest_cny": 0,
  "phasing": "一期 40 万吨，二期规划 40 万吨",
  "detail": [ {"k": "工艺路线", "v": "PDH(Oleflex) + 环管聚丙烯", "evidence": {...}} ],
  "stage_vocab": ["拟建", "备案", "在建", "试车", "已投产"],
  "phase_confidence": {"design_capacity": "E1", "process": "E2", "stage": "E1", "startup": "E2"}
}
```

| 字段 | 说明 |
|---|---|
| `design_capacity_t` | **计算的主输入**，单位吨/年（40 万吨 → `400000`） |
| `stage` | 只能取 `stage_vocab` 之一；环评受理/批复统一归 `备案` |
| `startup_plan.year/month` | 计算用；`month` 必须是 1–12 |
| `detail[]` | 事实核验卡的逐条明细（业主/地点/产品/产能/工艺/阶段/投产 + 补充） |
| `phase_confidence` | 四项关键字段各自的证据等级，用于核验卡着色 |

---

## 3. `chain`：工艺链（用于产业链影响图与原料单耗连乘）

```json
"chain": {
  "nodes": [
    {"id": "propane", "name": "丙烷", "type": "upstream", "sub": "进口冷冻丙烷"},
    {"id": "pdh",     "name": "PDH 丙烷脱氢", "type": "process"},
    {"id": "propylene","name": "丙烯", "type": "intermediate"},
    {"id": "pp",      "name": "聚丙烯", "type": "product"},
    {"id": "bopp",    "name": "BOPP 薄膜", "type": "downstream"},
    {"id": "hydrogen","name": "副产氢气", "type": "byproduct"}
  ],
  "edges": [
    {"from": "propane", "to": "pdh", "label": "1.18 t/t", "unit_key": "propane_to_propylene"},
    {"from": "pdh", "to": "propylene", "label": "收率"},
    {"from": "propylene", "to": "pp", "label": "1.03 t/t", "unit_key": "propylene_to_pp"},
    {"from": "hydrogen", "to": "pdh", "label": "副产", "reverse": true}
  ]
}
```

`unit_key` 指向 `unit_consumption[].key`，用于计算；图上的 `label` 只是显示。

---

## 4. `capacity_bases`：分母（现有产能）

```json
"capacity_bases": [{
  "key": "national",
  "label": "全国聚丙烯产能",
  "value_t": 48000000,
  "year": 2025,
  "scope": "含粉料，含在建已试车装置",
  "region_included": ["全国"],
  "level": "E4",
  "source": "XXX 行业统计",
  "url": "https://...",
  "note": "另一口径 4600 万吨（有效产能），作敏感性"
}]
```

| `key` | 含义 | 是否必需 |
|---|---|---|
| `national` | 全国 | ✅ |
| `regional` | 目标区域 | ✅ |
| `radius` | 竞争半径内（由 `regional.neighbors` 求和或直接给值） | ✅ |
| `grade` | 目标牌号 | 可缺（缺则标缺口） |
| `consumption` | 表观消费量 | 建议 |
| `imports` / `exports` | 进出口 | 建议 |

脚本额外接受 `value_t_alt` 与 `alt_label` 用于口径敏感性对照。

---

## 5. `unit_consumption`：单耗

```json
"unit_consumption": [{
  "key": "propane_to_propylene",
  "from": "丙烷", "to": "丙烯",
  "value": 1.18,
  "unit": "t/t",
  "basis": "C1 工程值",
  "range": [1.15, 1.25],
  "purity": 0.97,
  "evidence": {"level": "E1", "source": "某 PDH-PP 项目环评报告书 主要原辅材料消耗表", "url": "https://...", "date": "2025-06-01"},
  "on_site": true
}]
```

- `basis` 取 `C1 工程值 / C2 区间中值 / C3 化学计量下限 / C4 情景假设`
- `on_site`: 该段是否在本项目内自建（决定是否产生对上游的**新增采购需求**）
- 计算时按 `chain` 的顺序**连乘**：原料需求 = 产能 × Π(单耗/纯度)

---

## 6. `assumptions`：情景参数（与事实物理分开）

```json
"assumptions": {
  "steady_lf": 0.90,
  "steady_lf_basis": "同类 PDH-PP 装置 3 年平均负荷（假设）",
  "ramp_model": "s_curve",
  "ramp_months": 12,
  "ramp_basis": "同类装置经验中值（假设）",
  "commissioning_months": 2,
  "commissioning_ratio": 0.5,
  "landing_price_cny_t": null,
  "fx_note": "..."
}
```

**所有假设值都会在 HTML/Excel 的"假设汇总"表中被单独列出并标注"假设"。**

---

## 7. `scenarios`：情景列表

```json
"scenarios": [{
  "id": "S2", "label": "中性", "kind": "基准",
  "start_month": 6,
  "ramp_model": "s_curve", "ramp_months": 12,
  "steady_lf": 0.90,
  "note": "公告计划 6 月开车，按同类装置中值爬坡"
}]
```

`kind` 取 `保守 / 基准 / 乐观 / 上限 / 延期 / 自定义`。`S 上限` 情景应设 `steady_lf: 1.0` 且 `ramp_model: "none"`。

---

## 8. `stakeholders`：受影响对象

```json
"stakeholders": [{
  "id": "h1", "name": "具名企业", "type": "competitor",
  "region": "浙江宁波", "lat": 0, "lon": 0,
  "capacity_t": 600000,
  "note": "受影响的具体机制描述",
  "evidence": {"level": "E2", "source": "", "url": "", "date": ""},
  "impact_basis": {"transmission": 1.0, "lag": 1.0, "volume_basis_t": null}
}]
```

`type` 取 `upstream / competitor / downstream / logistics / byproduct / policy`。
`impact_basis.volume_basis_t` 若为空，则用 `capacity_t` 或上游需求作为体量基；计算见 `scripts/compute.py`。

---

## 9. `regional`

```json
"regional": {
  "name": "华东",
  "provinces": ["浙江", "江苏", "上海", "安徽"],
  "self_sufficiency_now": 0.0,
  "self_sufficiency_basis": "",
  "flow_direction": "净输入",
  "freight_cny_t": null,
  "price_spread": {"label": "华东-全国均价", "value": null, "date": "", "source": ""},
  "neighbors": [ {"name": "", "province": "", "capacity_t": 0, "distance_km": 0, "lat": 0, "lon": 0, "level": "E2", "source": "", "url": ""} ]
}
```

`neighbors[].distance_km` 可留空，由脚本按 `project.location.lat/lon` 与邻居经纬度用 haversine 计算。

---

## 10. `facts` / `gaps` / `sources`

```json
"facts":  [ {"text": "", "category": "事实|计算|情景", "level": "E1", "source": "", "url": "", "date": ""} ],
"gaps":   [ {"item": "", "impact": "影响哪一步计算", "plan": "补齐路径", "owner": "", "priority": "高|中|低"} ],
"sources":[ {"name": "", "url": "", "type": "官方|媒体|数据商", "date": ""} ]
```

`facts[].category` 是**三类结论分离**的物理落点：报告里的事实、计算、情景三栏全部由此生成。

---

## 11. 校验规则摘要（`scripts/validate.py`）

| 规则 | 级别 |
|---|---|
| `project.design_capacity_t > 0` | error |
| `project.stage ∈ stage_vocab` | error |
| `startup_plan.month ∈ 1..12` | error |
| `capacity_bases` 至少含 `national`、`regional` | error |
| 每个 `unit_consumption` 的 `evidence` 缺失或 `level=E5` | warn（报告里必须标"情景参数"） |
| `chain.edges[].unit_key` 必须能在 `unit_consumption` 找到 | error |
| `assumptions` 里每个数都要有 `*_basis` | warn |
| 出现涨跌/预测词（BANNED 词表） | error |
| `sources[].url` 非 http(s) | warn（降级为"未核实"） |
| `meta.simulated=true` 但存在看似真实的业主名 | info（提示在 HTML 顶部加模拟横幅） |
