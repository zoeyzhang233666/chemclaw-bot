# data.json 数据契约

`data.json` 是唯一数据源。HTML 和 Excel 都由它生成；不要手改生成物，否则下一次构建会被覆盖。

脚本会做一次 `normalize()`（`scripts/common.py`），容忍少量旧写法，但**推荐直接按本契约写**。

## 顶层结构

```json
{
  "meta": {},
  "params": {},
  "baseline": {},
  "candidates": [],
  "spec_items": [],
  "spec_status": {},
  "same_source": [],
  "risks": [],
  "actions": [],
  "sources": []
}
```

| 键 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `meta` | object | 是 | 产品、单位、截止日、收货地、工艺、标签 |
| `params` | object | 是 | 月量、运费率、车重、价格假设 |
| `baseline` | object | 是 | 现有供应商 |
| `candidates` | array | 是 | 5–15 家备选（校验允许 2–20） |
| `spec_items` | array | 是 | 9–15 项规格（校验允许 3–20） |
| `spec_status` | object | 是 | 候选 × 规格的状态矩阵 |
| `same_source` | array | 建议 | 同源/同集团/纵向竞争 |
| `risks` | array | 建议 | 公开风险台账（至少 3 条） |
| `actions` | array | 建议 | 30/60/90 天动作（至少 3 条） |
| `sources` | array | 是 | 来源表；正文用 ID 引用 |

---

## meta

| 字段 | 类型 | 必填 | 说明 / 示例 |
|---|---|---|---|
| `title` | string | 否 | 页面标题；缺省用 `product_short + 第二供应源备选池` |
| `product` | string | 是 | 产品全称，例：`重质纯碱（碳酸钠）` |
| `product_short` | string | 是 | 简称，例：`重质纯碱` |
| `unit` | string | 是 | 产能单位，例：`万吨/年` |
| `asof` | string | 是 | 数据截止日，`YYYY-MM-DD` |
| `buyer_site` | string | 是 | 收货地，例：`江苏苏州（工业园区）` |
| `buyer_short` | string | 否 | 图中简称，例：`苏州`；缺省从 `buyer_site` 截取 |
| `volume` | string | 是* | 采购量，例：`800 吨/月` |
| `volume_t` | number | 是* | 月量（吨），例：`800`；`volume` 与 `volume_t` 至少一个 |
| `volume_period` | string | 否 | `月` 或 `年`，默认 `月` |
| `spec` | string | 是 | 关键规格摘要（页头/Excel 说明用） |
| `use_case` | string | 否 | 下游用途，例：`浮法 / 光伏玻璃` |
| `scenario` | string | 否 | 页头场景说明；写清“示例/真实” |
| `qualification_label` | string | 否 | 资质长标签，例：`郑商所纯碱免检交割品牌` |
| `qualification_short` | string | 否 | 资质短标签，例：`免检`；默认 `准入` |
| `grade_label` | string | 否 | 等级/牌号列名，例：`重质 / 品牌` |
| `near_km` | number | 否 | 近场阈值，默认 `500` |
| `distance_bands` | array | 否 | `{label,max}`；当前 HTML 主要用于文档/扩展 |
| `processes` | array | 是 | `{name,color,cost_score}`；工艺颜色/成本刻度 |
| `risk_categories` | array | 否 | 风险筛选类目，默认 `财务/装置/资质/同源/行业` |
| `same_source_note` | string | 否 | 同源特别提示（页尾/同源区） |
| `spec_note` | string | 否 | 首样/检测口径（规格矩阵下方） |
| `process_insight` | string | 否 | 工艺结构图的解读 |
| `disclaimer` | string | 否 | 免责声明 |
| `action_window` | string | 否 | 行动窗口，默认 `90 天` |
| `fin_year` | string | 否 | 财务年份，例 `2025`；用于“2025 营收/净利”标签 |
| `output_year` | string | 否 | 产量年份，例 `2024`；用于“2024 产量”标签 |
| `price_assumption` | number | 否 | 货值假设（元/吨），用于运费占比 |
| `method_steps` | array | 否 | `{label,text}`；研究方法 |
| `key_judgements` | array | 否 | `{label,text}`；关键判断 |
| `method_note` | string | 否 | 方法区副标题 |
| `dd_items` | array | 否 | `{label,hint}`；尽调清单列；缺省用通用 13 项 |
| `stamp_note` | string | 否 | 页头角标，例：`公开信息研究 · 非报价 · 非决策建议` |

`processes[].cost_score` 是 0–100 的**相对成本潜力**（不是成本绝对值）：天然碱/一体化路线高，氨碱/高能耗路线低。它只用于雷达“成本潜力”轴。

`processes[].color` 建议深色、可区分；HTML 会用它做工艺标签/散点/堆叠。

---

## params

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `product` | string | 否 | 与 `meta.product` 一致即可 |
| `spec` | string | 否 | 规格摘要 |
| `monthly` | number | 是 | 月采购量（吨） |
| `receiver` | string | 是 | 收货地 |
| `baseline` | string | 否 | 现有供应商全称 |
| `freight_rate` | number | 是 | 汽运费率（元/吨·km），例 `0.45` |
| `water_rate` | number | 否 | 水运费率，例 `0.12` |
| `truck_load_t` | number | 否 | 单车吨位，默认 `30` |
| `price_assumption` | number | 否 | 货值（元/吨），用于运费占比 |

> 运费是估算：`distance × freight_rate`。不要把它写成承运商报价；铁路/水运/短驳需另询。

---

## baseline / candidates

两者字段基本一致。`baseline` 建议加 `warn`；`candidates` 必须有 `evidence` 和 `verify`。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | `S00` / `C01`…；唯一 |
| `name` | string | 是 | 企业全称 |
| `short` | string | 是 | 图表/表头简称 |
| `role` | string | 否 | `现有供应商` / `备选` |
| `province` | string | 否 | 省 |
| `city` | string | 否 | 市 |
| `site` | string | 否 | 园区/厂区地址 |
| `distance` | number | 是 | 到收货地地理运距 km |
| `transport` | string | 否 | `汽运 / 铁路 / 水运` |
| `freight_low` | number | 是 | 运费区间下限 元/吨 |
| `freight_high` | number | 是 | 运费区间上限 元/吨 |
| `process` | string | 是 | 必须出现在 `meta.processes[].name` |
| `capacity` | number | 是 | 名义产能（`meta.unit`） |
| `capacity_note` | string | 否 | 几条线、投产、重质比例、实际产量 |
| `grade` | string | 否 | 等级/品种，例：`重质为主` |
| `brand` | string | 否 | 牌号/品牌 |
| `qualified` | boolean | 是 | 是否具备该行业准入/交割品牌 |
| `listed` | string | 否 | `上交所/深交所/未上市` |
| `code` | string | 否 | 股票代码；无写 `—` |
| `group` | string | 否 | 集团 |
| `controller` | string | 否 | 实控人 |
| `ownership` | string | 否 | 国企/民营/外资/央企 |
| `employees` | string | 否 | 员工（公开口径） |
| `revenue` | string/number | 否 | 最近一年营收（亿元）；未披露写 `未披露` |
| `profit` | string/number | 否 | 最近一年归母净利（亿元）；亏损用负号 |
| `output` | string/number | 否 | 最近一年产量（万吨）；没有写 `—` |
| `products` | string | 否 | 主营产品 |
| `spec_fit` | string | 否 | `高/中高/中/低/待核/基准` |
| `sample` | string | 否 | `建议/必须/—` |
| `risk_score` | number | 是 | 1–5；**低=好** |
| `risk_level` | string | 是 | `低/中/中高/高` |
| `risk_summary` | string | 否 | 一段话风险摘要 |
| `same_source` | string | 否 | `无` / 关系简述 |
| `same_note` | string | 否 | 同源说明 |
| `diff` | string | 否 | 与现有供应商的差异（一句话） |
| `tags` | array | 否 | 卡片标签，例：`["近场","新装置"]` |
| `tag_tones` | object | 否 | 标签→颜色类：`{"近场":"green"}`；可选 || `new_plant` | boolean | 否 | 是否 2025 年后新装置/新线 |
| `verify` | array | 否 | 需人工核实项（字符串） |
| `evidence` | array | 是 | 来源 ID 列表，例 `["SRC01","SRC02"]` |
| `warn` | string | 否 | 仅现有供应商：基准风险提示 |

`revenue`/`profit`/`output` 可以是数字或字符串；字符串用于 `未披露`、`-0.015`、`10.62（归母，前三季）`。

**证据要求**：每个候选至少 1 条 `evidence`；关键数字（产能/财务/资质）建议 2 条以上。`evidence` 必须引用 `sources[].id`，校验会报错。

---

## spec_items

```json
{"id": "na2co3", "label": "Na₂CO₃ 含量", "target": "≥99.2%"}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 英文/拼音短 ID，唯一；用于 `spec_status` |
| `label` | 是 | 表头显示名 |
| `target` | 否 | 目标值/方法/客户要求 |

顺序 = HTML/Excel 矩阵列顺序。建议 9–15 项，覆盖：主含量、关键杂质、物理形态（粒度/堆密度/白度）、水分/稳定性、包装/运输。

---

## spec_status

```json
{
  "C01": {"na2co3": "COA", "nacl": "COA", "fe": "试样", "pack": "审核"}
}
```

- 每家候选 × 每个 `spec_items[].id` 都必须有值；
- 值只允许：`COA`（可凭批次 COA/出厂检验追溯）、`试样`（必须首样/小批验证）、`审核`（现场审核/封样/包装确认）；
- 缺项会被校验判错；不确定就写 `试样`，不要写 `COA`。

---

## same_source

```json
{
  "group": "博源集团 / 远兴能源",
  "parent": "内蒙古博源控股集团（戴连荣）",
  "entities": ["远兴能源（000683）", "中源化学（远兴持股 81.71%）"],
  "relation": "母子公司（2014 年收购并表）",
  "implication": "二者只能算一个供应源；同时入选会高估第二供应源的独立性。",
  "verify": "中源化学销售主体、关联交易定价",
  "flag": "同源"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `group` | 是 | 组名 |
| `parent` | 否 | 母公司/实控人 |
| `entities` | 是 | 主体列表（至少 1，同源/同集团建议 2+） |
| `relation` | 是 | 母子公司/同集团/同园区不同股东/纵向竞争 |
| `implication` | 是 | 对“第二源独立性”的影响 |
| `verify` | 是 | 下一步核实 |
| `flag` | 是 | `同源/同集团/纵向竞争/多厂区/非同源/单一` |

**同源不是“不能采购”**，而是“不能同时算两个独立源”。如果两家同源，二选一，或只把一家计入双源。

---

## risks

```json
{
  "company": "远兴能源",
  "type": "资质",
  "category": "资质",
  "fact": "“远兴牌”不是郑商所纯碱免检品牌",
  "impact": "到货需按批检验，交割/质押便利性弱",
  "source_id": "SRC18",
  "status": "已公开"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `company` | 是 | 企业简称/全行业 |
| `type` | 是 | 原始类型：财务/成本/装置/资质/股权/规模/环保/同源/独立性/价格/供给/产能 |
| `category` | 否 | 展示类目；缺省按 `type` 映射到 5 类 |
| `fact` | 是 | 公开事实，尽量带时间/数字 |
| `impact` | 是 | 对供应/质量/商务的影响 |
| `source_id` | 建议 | 必须存在于 `sources`；与 `source/url` 至少一个 |
| `source` | 否 | 来源名（冗余展示） |
| `url` | 否 | 来源链接（冗余） |
| `status` | 是 | `已公开` / `待核实` |

`待核实` 只能作为线索，不能写进“结论”；在页面上会以琥珀色显示。

---

## actions

```json
{
  "phase": "第 31–60 天",
  "action": "首样与小试",
  "detail": "每家 20–50 kg 首样，按 9 项指标检测；新装置追加 3 批稳定性验证。",
  "owner": "质量部",
  "output": "检测报告、封样、小试结论",
  "deadline": "T+60"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `phase` | 是 | `第 0–30 天` / `第 31–60 天` / `第 61–90 天` / `持续` |
| `action` | 是 | 动作名 |
| `detail` | 是 | 做什么、做到什么程度 |
| `owner` | 是 | 岗位，不是人名 |
| `output` | 是 | 可验收产出 |
| `deadline` | 否 | 目标完成；缺省按顺序生成 |

---

## sources

```json
{"id": "SRC01", "name": "山东海化 2025 年年度报告", "url": "https://...", "grade": "A", "date": "2026-03-21"}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | `SRC01`…；唯一；正文引用 |
| `name` | 是 | 来源标题（含机构/日期更好） |
| `url` | 是 | http(s)；无链接的来源不能进正文 |
| `grade` | 是 | `A` / `B` / `C` |
| `date` | 否 | 发布/数据日期，`YYYY-MM-DD` 或 `YYYY-MM` |

**A**：上市公司公告/年报/政府网站/交易所/环评批复；**B**：行业协会/券商研报/主流财经媒体；**C**：企业官网/百科/招聘/招商稿。C 级需二次核验。

---

## 可选扩展

### `tag_tones`

```json
"tags": ["近场", "新装置", "同源"],
"tag_tones": {"近场": "green", "新装置": "amber", "同源": "red"}
```

可用类：`green` / `amber` / `red` / `blue`。不填则按关键词自动判断。

### `meta.dd_items`

不同行业的尽调项不同。默认 13 项通用清单；建议按产品覆盖：

- 纯碱：免检品牌、SC、纯碱生产许可；
- 钛白粉：硫酸法/氯化法准入、危化品、REACH；
- 危化品：安全生产许可、危化品经营/运输；
- 食品添加剂：SC/FSSC 22000；
- 电池材料：IATF 16949、客户认证、磁异物/水分。

### 旧字段兼容

`normalize()` 接受：

- `candidates` 缺失时读 `suppliers`；
- `spec_items` 用 `[id, label, target]` 数组；
- `sources` 用 `[name, url, grade, date]` 数组；
- `baseline.heavy` → `grade`、`jianmian` → `qualified`（示例 01 转换时用，建议新数据直接用新字段）。

不推荐依赖兼容层；新项目直接按本契约写。

---

## 常见错误

| 错误 | 后果 | 修正 |
|---|---|---|
| `process` 不在 `meta.processes` | 校验报错；图表缺色 | 补 process 或改名 |
| `evidence` 引用不存在的 ID | 校验报错；页面“证据待补” | 补 `sources` 或改 ID |
| `spec_status` 漏项 | 校验报错；矩阵空 | 每家 × 每项都填 |
| `qualified` 写成 `"是"` | 校验报错（需 boolean） | 用 `true/false` |
| `risk_level` 用 `中高风险` | 校验报错 | 只用 `低/中/中高/高` |
| `freight_low > freight_high` | 校验报错 | 调换 |
| `source.url` 为空 | 警告；正文不可点 | 补链接或降为“待核实” |
| 同组两家同时入选 | 警告 | 二选一，或标注“同源不独立” |
| 把贸易商写进候选 | 研究失真 | 放渠道备注，不占名额 |
