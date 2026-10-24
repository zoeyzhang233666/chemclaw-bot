# 03 · 数据契约（JSON 字段文档）

所有文件放在 `data/` 目录下。UTF-8 无 BOM。顶层都是 `{"meta": {...}, "<key>": [...]}` 形式。

必需文件（缺一个校验 FATAL）：`meta.json`、`nodes.json`、`relations.json`、`core_checklist.json`、`sources.json`

其余可选但强烈建议：`processes.json`、`prices_verified.json`、`enterprises.json`、`projects.json`、`events.json`、`forbidden_links.json`、`price_series.json`

---

## meta.json

```json
{
  "chain_id": "SBS",
  "product_name": "SBS 热塑性弹性体",
  "product_full_name": "苯乙烯-丁二烯-苯乙烯嵌段共聚物（TPE-S/TPS/SBC 族中的 SBS 型）",
  "focus_question": "以 SBS 为中心，向上展开……（一句话研究命题）",
  "user_params": {
    "up_depth": 2, "down_depth": 2,
    "branches": ["道路改性沥青", "建筑防水卷材", "鞋材 TPR"],
    "show_price": true, "show_enterprises": true, "show_projects": true, "show_events": true,
    "region": "中国大陆",
    "price_window": "2026-09-20 ~ 2026-10-20"
  },
  "price_basis": {"default": "出厂价/现货市场价（含税，人民币）", "note": "不同节点口径不同，画图时须分别标注"},
  "generated_at": "2026-10-20"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `chain_id` | ✅ | 短标识，用于文件名与报告标题 |
| `product_name` | ✅ | 品种名 |
| `product_full_name` | | 全称（防混淆） |
| `focus_question` | | 研究命题，会显示在封面 |
| `user_params` | ✅ | 层级、支链、是否显示价格/企业等（渲染时读取） |

---

## nodes.json

```json
{
  "meta": {"column_note": "column 是图谱列号……"},
  "columns": [
    {"col": -6, "label": "原油", "side": "up"},
    {"col": 0,  "label": "聚合单体与基料", "side": "core"},
    {"col": 5,  "label": "终端应用", "side": "down"}
  ],
  "nodes": [
    {
      "id": "N_SM",
      "name": "苯乙烯（SM）",
      "aliases": ["苯乙烯", "styrene", "SM", "乙烯基苯"],
      "node_class": "commodity",
      "node_role": "monomer",
      "segment": "石化单体",
      "column": 0,
      "cas": {"value": "100-42-5", "status": "verified", "note": ""},
      "hs_code": "2902.50.00",
      "specs": ["工业级 ≥99.7%", "阻聚剂 TBC 10~15ppm"],
      "unit": "元/吨",
      "missing_flags": [],
      "identification_confidence": "high",
      "notes": null,
      "evidence": ["S06", "S07"]
    }
  ]
}
```

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `id` | ✅ | str | 唯一；建议 `N_XXX` |
| `name` | ✅ | str | 展示名。**保持适中长度**（≤24 全角字符），过长会导致图谱节点换行 |
| `aliases` | | list | 常见名称，参与搜索 |
| `node_class` | ✅ | enum | `commodity` / `material` / `application`（另允许 `route`/`utility`，不进入主图） |
| `node_role` | ✅ | str | 见下表；决定同列内的排布顺序（band） |
| `segment` | ✅ | str | 所属产业环节（中文短词） |
| `column` | ✅ | int | 图谱列号，从左到右递增；兼容旧字段名 `layer` |
| `cas` | ✅ | obj | `{value, status, note}`。`status` ∈ `verified` / `unverified` / `不适用` |
| `hs_code` | | str/obj | 报关编码；不确定可不填 |
| `specs` | | list | 规格/牌号维度，**价格可比性的依据** |
| `unit` | | str | 计量单位 |
| `missing_flags` | ✅ | list | 缺口标记数组（见下），必须是数组，可为空 |
| `identification_confidence` | | str | `high` / `medium` / `low` |
| `price_mapped_note` | | str | 若价格是缺口，写清"为什么缺 + 到哪里补"（满足 `price_mapped` 判定） |
| `evidence` | ✅ | list | 指向 sources 的 id |

### node_role 取值与排布 band

同一列内按下列顺序从上到下排列，同 band 之间留白分区：

`raw` → `byproduct` → `intermediate` → `monomer` → `auxiliary` → `target` → `compound` → `article` → `system` → `derivative` → `same_family` → `substitute` → `end_market`

| role | 含义 |
|---|---|
| `raw` | 最上游原料 |
| `byproduct` | 副产物/联产物节点 |
| `intermediate` | 中间体 |
| `monomer` | 聚合单体 |
| `auxiliary` | 配套原料/辅料（如基质沥青、填充油） |
| `target` | **目标品种**（必须有且仅有一个典型情形） |
| `compound` | 配方材料/改性料 |
| `article` | 制品 |
| `system` | 系统材料/成套材料 |
| `derivative` | 衍生化学品（SEBS） |
| `same_family` | 同族并列品（SIS） |
| `substitute` | 替代品（TPU/EVA/POE/SBR） |
| `end_market` | 终端应用市场 |

### missing_flags 词表

| flag | 含义 |
|---|---|
| `price_missing` | 无公开可核验价格序列 |
| `price_partial` | 有价格但样本不足 |
| `cas_disputed` | CAS 存疑 |
| `unit_mixed` | 存在多种计量单位，不可加总 |
| `capacity_missing` | 产能无公开数据 |
| `evidence_missing` | 无 A~C 级证据 |
| `quant_missing` | 关键单耗缺失 |

---

## relations.json

```json
{"relations": [
  {
    "id": "R03",
    "from": "N_EB",
    "to": "N_SM",
    "relation_type": "conversion",
    "process": "乙苯催化脱氢（Fe2O3-K2O 系催化剂，600~650℃，负压）",
    "family": "脱氢",
    "typical": true,
    "quant": {
      "from_per_to": 1.04,
      "from_unit": "t 乙苯 / t 苯乙烯",
      "yield": null,
      "basis": "按质量收率 ~96% 折算：1/0.96 ≈ 1.04；含循环乙苯回收口径",
      "basis_grade": "工业级（装置基准，未含分馏损失）",
      "from_per_to_range": null,
      "range_note": null
    },
    "quant_status": "commercial_grade",
    "quant_confidence": "medium",
    "evidence": ["S06"],
    "flow": "mass",
    "edge_style": "solid",
    "notes": "选型说明……",
    "route_ids": ["RT_EB_DEH"]
  }
]}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `from` / `to` | ✅ | 节点 id；物质流方向 |
| `relation_type` | ✅ | 见 `02-relation-taxonomy.md` |
| `process` | ✅ | 工艺描述（越具体越好，会显示在侧栏与 Excel） |
| `family` | | 工艺族（用于「工艺筛选」下拉） |
| `typical` | | 是否主流路线；`false` 表示并列/非主流 |
| `quant.from_per_to` | | 单耗数值；没有就 `null` |
| `quant.from_unit` | | 单位，格式 `t X / t Y`；Excel 会拆成"分子/分母" |
| `quant.yield` | | 收率（0~1） |
| `quant.basis` | ✅（有数值时） | 计算口径说明 |
| `quant.basis_grade` | ✅（有数值时） | 规格基准 |
| `quant.from_per_to_range` | | `[low, high]` 区间 |
| `quant_status` | ✅ | 见下 |
| `evidence` | ✅ | sources id 列表；量化边**必须**有，且不能只挂 D 级 |
| `flow` | | `mass` / `none`（替代边为 none） |
| `edge_style` | | `solid` / `dashed` / `dotted` / `shortdash` |

### quant_status 词表

| 值 | 含义 | 是否可用于计算 |
|---|---|---|
| `stoichiometric` | 纯化学计量（分子量推算） | ✅ 理论值 |
| `stoichiometric_derived` | 化学计量 + 给定收率折算 | ✅ |
| `commercial_grade` | 工业级单耗（有装置/行业基准） | ✅ |
| `formulation` | 配方比（每 100 份） | ✅ 仅用于配方体系 |
| `industrial_range_literature` | 文献区间 | ⚠️ 只作区间 |
| `byproduct_yield_range` | 副产收率区间 | ⚠️ 只作区间 |
| `missing` | 明确缺失，未估算 | ❌ |
| `not_applicable` | 该类关系不需量化（如 application） | — |

---

## sources.json

```json
{"sources": [
  {
    "id": "S01",
    "title": "SBS：深耕新兴领域 多方齐头并进",
    "publisher": "中国化工信息周刊",
    "date": "2026-08-04",
    "url": "https://...",
    "tier": "B",
    "verified": "opened",
    "key_quotes": ["截至2026年7月，我国SBS总产能达到197.5万吨/年", "……"]
  }
]}
```

| 字段 | 说明 |
|---|---|
| `tier` | **A**=协会/标准/官方披露/SEC/EIA；**B**=行业媒体、期货公司研究；**C**=信息商公开页；**D**=二手（**不得支撑量化关系**，校验 FATAL） |
| `verified` | `opened`（正文已读）/ `opened_title_only` / `snippet_only`（仅摘要） |
| `key_quotes` | 关键原文摘录（数组）；这是"可追溯"的实证 |

---

## prices_verified.json

```json
{
  "fetched_at": "2026-10-20 14:41:23",
  "series": [
    {
      "id": "PR_SM", "node_id": "N_SM", "product": "苯乙烯",
      "source": "oilchem_seo", "seo_id": "128",
      "point_name": "苯乙烯全国主流市场均价",
      "basis": "全国主流市场均价", "region": "全国", "unit": "元/吨", "tax": "含税",
      "available": true, "fetched_at": "2026-10-20 14:41:08",
      "url": "https://www.oilchem.net/seo-128-7.html",
      "points": [{"date": "2026-10-19", "price": "10934.58", "chg": "50", "chg_rate": "0.46"}]
    }
  ]
}
```

- `available: false` + `gap`/`caveat` 表示该序列是**缺口**，不是 0。
- `points` 里的 `price` 建议用字符串以免浮点误差；构建器会照样输出。
- **不同 `basis`/`tax`/`region` 的序列不得合并。**

---

## enterprises.json / projects.json / events.json

```json
{"enterprises": [
  {"id": "E01", "name": "某石化", "node_id": "N_PRIMARY",
   "province": "湖南", "capacity_sbs": 20.0, "capacity_sbc": 38.0, "capacity_unit": "万吨/年",
   "capacity_status": "verified_sbs", "year": "1980s",
   "evidence": ["S01","S02"], "note": "说明"}
]}

{"projects": [
  {"id": "PJ01", "name": "某 25 万吨 SBC 装置", "node_id": "N_PRIMARY", "company": "…",
   "province": "上海", "stage": "已投产", "capacity": 25.0,
   "capacity_basis": "SBC 合计：SBS 14 + SEBS 5 + SIS 6",
   "start_time": "2025-11", "evidence": ["S01","S02"], "note": "…"}
]}

{"events": [
  {"id": "EV01", "date": "2025-11", "title": "…", "detail": "…",
   "affects": ["N_PRIMARY","N_SEBS"], "direction": "supply_+", "strength": "高",
   "evidence": ["S01"]}
]}
```

> 注意：构建器对字段名做了兼容（`capacity`/`capacity_sbs`、`province`/`region`、`affects`/`node_ids`、`evidence`/`evidence_ids`），但**请优先用上面这套规范名**。

---

## core_checklist.json

```json
{
  "meta": {
    "purpose": "开工前冻结的核心清单……",
    "frozen_at": "2026-10-20T09:00:00+08:00",
    "scope_statement": "覆盖：……；不覆盖：……",
    "effective_depth": {"up": 2, "down": 2, "note": "延长线不计入清单"},
    "criteria_definitions": {"node_present": "……", "quant_available": "……"}
  },
  "core_nodes": [
    {"id": "core_node_01", "node_id": "N_PRIMARY", "label": "SBS（目标品种）",
     "priority": "P0",
     "required_criteria": ["node_present","identity_verified","role_classified","evidence_linked","price_mapped"]}
  ],
  "core_relations": [
    {"id": "core_rel_01", "from": "N_SM", "to": "N_PRIMARY", "relation_type": "conversion",
     "label": "苯乙烯→SBS", "priority": "P0",
     "required_criteria": ["node_present","direction_verified","quant_available","evidence_linked"]}
  ]
}
```

判定词：`node_present` / `identity_verified` / `role_classified` / `evidence_linked` / `price_mapped` / `capacity_mapped` / `direction_verified` / `quant_available`。

---

## forbidden_links.json

```json
{"forbidden": [
  {"id": "F01", "from": "N_PRIMARY", "to": "N_APP_FOOTWEAR",
   "wrong_types": ["conversion", "blend"],
   "why": "SBS 不会直接变成『鞋』……必须经 TPR 与鞋底两层",
   "worksheet": "终端用途只能通过 material→application 的 application 边表达"}
]}
```

- `wrong_types` 里出现的关系类型 → 校验 **FATAL**。
- `wrong_types: ["copy"]` 是特殊约定：表示"方向/口径存疑"，只 **WARN**（`FORBIDDEN_SUSPECT`），用于登记有争议但需保留的边。

---

## processes.json（可选，工艺路线台账）

```json
{"processes": [
  {"id": "RT_EB_DEH", "name": "乙苯催化脱氢", "target": "N_SM", "feed": ["N_EB"],
   "status": "工业主流", "note": "…", "evidence": ["S06"]}
]}
```

---

## 最小可用数据集

一个能跑通的最少文件：`meta.json` + `nodes.json`（≥2 节点）+ `relations.json`（≥1 边）+ `sources.json`（≥1 条）+ `core_checklist.json`（≥1 节点条目）。
参见 `examples/minimal/`。
