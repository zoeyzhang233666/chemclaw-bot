# 03 · data.json 字段规范（渲染器唯一输入）

`scripts/build.py` 只认这一个文件。所有内容必须可追溯到 `evidence[]`；本文件既是规范也是校验规则的说明。

---

## 顶层结构

```jsonc
{
  "meta":        { … },   // 必填：公司、代码、目的、时间窗口
  "evidence":    [ … ],   // 必填：证据台账，编号 E01…
  "entity_note": "…",     // 建议：主体边界一句话说明
  "base_info":   [ … ],   // 工商登记字段
  "disambiguation": [ … ],// 主体消歧表
  "conclusion":  [ … ],   // 研究结论卡
  "conclusion_note": "…",
  "kpis":        [ … ],   // 关键指标卡
  "ownership":   { … },   // 股权树
  "entities":    [ … ],   // 子分公司清单（Excel 用）
  "units":       [ … ],   // 装置清单
  "products":    [ … ],   // 产品与产能
  "products_note": "…",
  "chain_flow":  [ … ],   // 产业链五泳道
  "processes":   [ … ],   // 工艺路线
  "chain":       [ … ],   // 产业链明细（Excel 用）
  "regions":     [ … ],   // 区域布局
  "plants":      [ … ],   // 生产基地（含坐标）
  "plants_ev":   [ … ],
  "projects":    [ … ],
  "projects_ev": [ … ],
  "finance_years": ["2023年","2024年","2025年","2026H1"],
  "finance_note": "…", "finance_caveat": "…",
  "finance":     [ … ], "finance_ev": [ … ],
  "risks":       [ … ], "risks_ev": [ … ],
  "timeline":    [ … ], "timeline_ev": [ … ],
  "gaps":        [ … ],
  "filter_index":[ … ]    // 全量结论筛选器数据
}
```

任何区块缺省或为空，HTML 会自动渲染为「无公开资料」灰框——**不要为了填满而编造**。

---

## meta

| 字段 | 必填 | 说明 |
|---|---|---|
| `company` | ✔ | 研究主体全称 |
| `uscc` | ✔ | 统一社会信用代码，未知写 `""` |
| `listing` | | 上市信息，非上市写 `""` 或「非上市」 |
| `purpose` | ✔ | `supplier` / `customer` / `competitor` / `industry` / `investment` |
| `subtitle` | ✔ | 一句话定位（≤ 60 字，含主导产品与关键规模） |
| `as_of` | ✔ | 检索窗口，如「截至2026-10-20（近12个月覆盖 2025-10-20 → 2026-10-20）」 |
| `hero_stats` | ✔ | 4–6 个 `{k,v,m}`；`m` 为口径或同比 |

## evidence（证据台账）

```jsonc
{"eid":"E05","title":"公告全称","publisher":"巨潮资讯网/深交所","date":"2026-02-26",
 "type":"官方公告","url":"https://…","quote":"原文摘录（可直接引用的句子）",
 "note":"补充说明，如'媒体转载、正文未获取'"}
```

规则：
- `eid` 从 `E01` 起顺排，**不得重号**；正文只引用 `eid`。
- `type` 建议取值：`官方公告` / `企业官网` / `环评公示` / `政府平台` / `财经媒体` / `行业媒体` / `行业资讯` / `公告索引` / `投资者关系`。
- `quote` 为原文摘录（可截断），**不要改写数字**；摘录里出现的数字应与正文一致。
- `url` 必须可直接打开；若页面需登录或无直链，写 `note` 说明。

## base_info（工商登记字段）

```jsonc
{"group":"工商登记（官方披露）"}                       // 分组标题行
{"label":"统一社会信用代码","value":"9137…","ev":["E02"],"grade":"A","note":"…"}
```

- `value` 为 `null` 时渲染「无公开资料」（用于已知缺失项）。
- 建议覆盖：企业全称、统一社会信用代码、法定代表人、注册与办公地址、注册资本/实收股本、成立时间、登记机关、经营状态、实际控制人、行业与主营、员工人数。

## disambiguation

见 `02-entity-disambiguation.md` §6，字段：`name / uscc / relation / verdict / in_scope / ev / grade`。

## conclusion（研究结论卡）

```jsonc
{"q":"它是什么主体？","tone":"k","a":"一句话结论 ≤30字",
 "why":"用 <b>粗体</b> 标关键数字的证据化理由",
 "grade":"A","ev":["E02","E17"]}
```

- `q` 由研究目的决定（供应商→交付与资质；客户→用途与需求；对手→产能与工艺；产业→地位与产能变化）。
- `tone`：`k` 关键（绿边）/ `r` 风险（红边）/ `w` 关注（黄边）/ 空（蓝边）。
- `a` 必须能在 `why` 里找到证据支撑，不做无证据评价。

## kpis

```jsonc
{"k":"纯碱设计产能","v":"280 万吨/年","m":"老线120 + 新线160（氨碱法）","ev":["E02"],"neg":false}
```

`neg:true` 让数值显示为红色（亏损、负现金流）。

## ownership（股权树）

```jsonc
{"headline":"…","ev":["E02"],
 "nodes":[
   {"id":"grp","name":"XX集团有限公司","role":"控股股东（注册资本7.24亿元）","kind":"state",
    "parent":"gov","pct":"国资100%","grade":"A","ev":["E02"]}
 ],
 "notes":["…（口径说明，如'51%但不控'）"]}
```

- `kind`：`state`（国资/上级股东）· `target`（研究主体）· `sub`（并表子公司/分公司）· `assoc`（参股/合营/联营）· `excluded`（同集团但不属研究主体）。
- `parent` 指向上层节点 `id`；根节点 `parent` 留空 `""`。
- `pct` 写持股比例或关系（如「40.34%（361,048,878股）」「分公司」）。
- `kind:"excluded"` 的节点会自动汇入「同集团易混淆主体」表，并显示 `note`（为什么容易混）。

## products（产品与产能）

```jsonc
{"id":"p_soda","name":"纯碱（重质/轻质）","tag":"主导产品","grade":"A","ev":["E02","E17"],
 "note":"产品说明：口径、2025年产量、收入占比",
 "producers":["XX股份有限公司 XX厂（老线120万吨+新线160万吨）"],
 "capacity":[
   {"label":"设计产能（年报口径）","value":"280 万吨/年","estimate":false,"ev":["E02"]},
   {"label":"改造后","value":"约 260 万吨/年","estimate":true,
    "basis":"160（新线设计产能）+100（公告新建联碱规模）直接相加","ev":["E02","E05"]}
 ],
 "downstream":["浮法玻璃","光伏玻璃"],
 "facts":["可核实的补充事实，每条一句话"]}
```

**校验规则**：`estimate:true` 必须带 `basis`，否则 `--strict` 失败。这是防止估算混入披露值的硬闸门。

## plants（生产基地）

```jsonc
{"id":"pl_cj","name":"纯碱厂（老线120+新线160）","short":"纯碱厂","city":"潍坊",
 "location":"潍坊滨海经开区沂河大街14201号","lat":37.20,"lon":119.15,
 "entity_name":"XX股份有限公司（分公司）","consolidated":true,"status":"在产",
 "color":"#1554c0",
 "capacity":[{"product":"纯碱","value":"280万吨/年"}],
 "capacity_text":"纯碱 280 万吨/年（氨碱法）；2025年产量272.42万吨",
 "grade":"A","ev":["E02","E17"]}
```

- 缺 `lat/lon` 时渲染器会用 `city` 在内置城市坐标表中匹配，仍匹配不到则该点不上图（并在图上提示）。
- `color` 建议：在产 `#1554c0`、在建/改造 `#c0392b`、参股不并表 `#5b46b8`、停用/减值 `#8a939f`。
- 底图是**示意图**，必须保留「非精确地理边界」提示文案（模板已内置）。

## projects（项目清单）

必填：`name / type / location / scale / capex / funding / status / timeline / grade / ev`。
- `status` 写事实进度 + 日期（如「基础设计评审 2026-08-21 通过」），不要写「预计将大幅提升产能」。
- `timeline` 用「日期 事件 → 日期 事件」串联；媒体口径的时间表要注明。

## finance / risks / timeline / gaps / filter_index

- `finance`：`{"item":"营业收入（亿元）","values":["85.28","60.13","47.45","21.28"],"grade":"A","ev":["E01"]}`，`values` 长度与 `finance_years` 对齐（缺失写 `"—"`）。
- `risks`：`{"category":"行政处罚","finding":"公开事实","status":"ok","grade":"A","ev":["E02"]}`；`status ∈ {ok,warn,risk,todo}`。
- `timeline`：`{"date":"2026-08-21","text":"…","category":"项目","kind":"p","grade":"A","ev":["E08"],"prod":["纯碱"],"region":["潍坊"],"entity":["…"]}`；`kind`：`p` 项目/扩产（红点）· `f` 财务（绿点）· `s` 战略/治理（黄点）· 空（蓝点）。
- `gaps`：`{"item":"缺什么","status":"无公开资料/部分披露/未查询","how":"建议核实途径"}`。
- `filter_index`：`{"type":"产能","subject":"纯碱","statement":"一句话结论","entity":"主体全称","region":"潍坊","grade":"A","ev":"E02","prod":["纯碱"]}`，供 HTML 筛选器使用；`prod/region/entity` 用于下拉过滤。

## 校验与常见失败

| 报错 | 原因 | 修法 |
|---|---|---|
| `证据编号 E09 不在 evidence[] 台账中` | 正文引用了不存在的编号 | 补进 `evidence[]` 或改正编号 |
| `grade='甲' 非法` | 等级用了中文/小写 | 只能是 `A/B/C/D` |
| `估算产能未写 basis` | 有 `estimate:true` 无口径 | 补 `basis` 写明计算公式与来源编号 |
| 页面出现「无公开资料」过多 | 数据确实缺 or 字段名写错 | 先确认字段名拼写（严格按本文件） |

运行：`python scripts/build.py my.json -o out --strict`
