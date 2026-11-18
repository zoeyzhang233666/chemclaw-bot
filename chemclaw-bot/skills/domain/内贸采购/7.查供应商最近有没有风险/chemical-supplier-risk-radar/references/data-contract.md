# data.json 数据契约 v1.0

一份 `data.json` = 一次「某产品 × 某批供应商 × 某时间窗口」的公开风险扫描。HTML 与 Excel 都只读这一个文件。

- 编码：UTF-8
- 日期：`YYYY-MM-DD`
- 金额/产能：字符串，**带单位**（如 `"60.31 亿元"`、`"780 万吨/年"`）
- 枚举：中文，区分大小写
- 未知：写 `"未披露"` / `"未检索到公开记录"` / `"—"`，不要留空

机器可读版本：`schema/data.schema.json`（JSON Schema 2020-12）。它用于编辑器提示/集成，**最终以 `scripts/validate.py` 为准**。

---

## 1. 顶层结构

```json
{
  "meta": {},
  "suppliers": [],
  "events": [],
  "industry": [],
  "coverage_check": [],
  "method": {}
}
```

| 键 | 必填 | 说明 |
|---|---|---|
| `meta` | 是 | 产品、窗口、标题、截止时间 |
| `suppliers` | 是 | 至少 1 家 |
| `events` | 是 | 至少 1 条；没有事件也要用 `coverage_check` 说明 |
| `industry` | 建议 | 2–4 条行业背景，解释事件分量 |
| `coverage_check` | 强烈建议 | 六类“查了没有/待复核” |
| `method` | 建议 | 口径、证据分级、局限、查询式、免责声明 |

---

## 2. `meta`

```json
{
  "schema_version": "1.0",
  "title": "纯碱供应商近期风险雷达",
  "subtitle": "内贸采购 · 供应商准入与续约前的公开风险扫描",
  "product": "纯碱",
  "product_en": "SODA ASH",
  "product_full": "纯碱（轻质 / 重质）",
  "query_date": "2026-10-19",
  "query_time": "2026-10-19 13:20",
  "window_default": "6m",
  "windows": {
    "3m":  {"label": "近3个月", "start": "2026-07-19", "end": "2026-10-19"},
    "6m":  {"label": "近6个月", "start": "2026-04-19", "end": "2026-10-19"},
    "12m": {"label": "近1年",  "start": "2025-10-19", "end": "2026-10-19"}
  },
  "scope_note": "仅覆盖公开渠道；不替代完整尽调。",
  "scope_summary": "默认近 6 个月（…），可切换…。覆盖 7 家纯碱生产企业：…。",
  "financial_period": "2026H1",
  "period_tag": "2026-10",
  "channels": "公司公告 / 交易所 / 证监局 / 海关 / 主流财经媒体 / 行业资讯",
  "nature": "公开信息桌面检索，辅助采购决策，不替代完整尽调",
  "industry_title": "2026 年纯碱供需与检修"
}
```

| 字段 | 必填 | 用途 |
|---|---|---|
| `title` | 是 | 页面标题、Excel 封面、文件名默认值 |
| `subtitle` | 建议 | 封面副标题 |
| `product` | 是 | 页面主标题、筛选、Excel 列名 |
| `product_en` | 建议 | Excel 封面英文眉题；缺省 `CHEMICAL` |
| `product_full` | 建议 | 封面“查询产品”，写规格/牌号 |
| `query_date` | 是 | 截止日期；默认窗口 end 应与它一致 |
| `query_time` | 是 | 精确到分钟，页面“截至” |
| `window_default` | 是 | `3m` / `6m` / `12m` 之一，必须是 `windows` 的键 |
| `windows` | 是 | 至少两个窗口；模板按 3/6/12 个月设计 |
| `scope_note` | 建议 | 口径提示 |
| `scope_summary` | 建议 | “数据范围”整段；不填则自动生成 |
| `financial_period` | 建议 | 财务列名，如 `2026H1`；缺省 `本期` |
| `period_tag` | 建议 | 文件名与页脚月份，如 `2026-10`；缺省取 `query_date[:7]` |
| `channels` | 建议 | 封面“信息渠道” |
| `nature` | 建议 | 封面“报告性质” |
| `industry_title` | 建议 | `08_行业背景` 标题 |

**窗口语义**：
- 事件日期 `date` 满足 `start <= date <= end` 才计入该窗口。
- 默认窗口用于首屏 KPI、Excel `01/02/03` 计数。
- 12 个月窗口用于背景事件；`validate.py` 会拦 12 个月外的事件。
- 切换窗口时，页面重新计数；`chipEvents` 保持全部事件数，`chipInWindow` 变。

---

## 3. `suppliers[]`

```json
{
  "id": "S1",
  "name": "博源化工",
  "full_name": "内蒙古博源化工股份有限公司",
  "code": "000683.SZ",
  "market": "深交所主板",
  "region": "内蒙古鄂尔多斯 / 阿拉善",
  "process": "天然碱法",
  "capacity": "780 万吨/年（含规划）",
  "capacity_short": "780 万吨（规划）",
  "revenue": "60.31 亿元",
  "profit": "8.34 亿元",
  "profit_yoy": "+12.27%",
  "risk_level": "中低",
  "risk_label": "债券兑付 + 项目投产",
  "conclusion": "一句话结论：窗口内发生了什么、采购上意味着什么。",
  "coverage": "公告、交易所、行业资讯覆盖充分；地方处罚待复核",
  "tags": ["上市", "天然碱法", "规划产能"]
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 唯一；事件用 `supplier_id` 关联 |
| `name` | 是 | 短名，页面/Excel 显示 |
| `full_name` | 是 | 工商全称 |
| `code` | 是 | 证券代码；非上市写 `"非上市"` |
| `market` | 是 | 交易所/板块；非上市写 `"非上市"` |
| `region` | 是 | 主要基地/注册地 |
| `process` | 是 | 工艺路线/技术路线 |
| `capacity` | 是 | 长口径（含规划/在建/权益） |
| `capacity_short` | 是 | 表格/卡片短口径 |
| `revenue` | 建议 | 最近一期营收；兼容旧字段 `h1_revenue` |
| `profit` | 建议 | 最近一期净利；兼容旧字段 `h1_profit` |
| `profit_yoy` | 建议 | 净利同比；无则 `"—"` |
| `risk_level` | 是 | `高` / `中` / `中低` / `低` |
| `risk_label` | 是 | 2–8 字标签，概括主要风险 |
| `conclusion` | 是 | 1–3 句，事实 + 采购含义，不断供 |
| `coverage` | 是 | 公开信息覆盖说明，含缺口 |
| `tags` | 否 | 页面搜索/标签用 |

**风险等级建议**（采购视角，不是信用评级）：
- `高`：可能影响交付/合规，需 1–2 周内核实（事故、非计划停产、许可证问题、重大诉讼/执行）。
- `中`：值得关注，纳入询价/合同条款（亏损、计划检修、关联交易监管、项目延期）。
- `中低`：有事件但影响有限（小额罚单、常规人事）。
- `低`：无高/中风险事件，或仅正向事件。

---

## 4. `events[]`

```json
{
  "id": "E1",
  "date": "2026-09-04",
  "supplier_id": "S2",
  "supplier": "中盐化工",
  "category": "经营动态",
  "severity": "中",
  "direction": "风险",
  "title": "500 万吨纯碱项目环评公示",
  "fact": "谁、何时、发生了什么、数字是多少。只写可核事实。",
  "why": "为什么采购要在意；只写到“可能影响/需确认”，不写“将断供”。",
  "source": "公司公告 / 省生态环境厅公示",
  "source_type": "公司公告",
  "source_date": "2026-09-04",
  "url": "https://…",
  "url_label": "公告原文",
  "evidence": "A",
  "questions": ["问题1？", "问题2？", "问题3？"],
  "action": "采购下一步动作（索证/条款/替代源/复检）。",
  "tags": ["项目", "环评"]
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 唯一；Excel 时间线第一列 |
| `date` | 是 | 事件发生日期，不是新闻发布时间 |
| `supplier_id` | 是 | 必须存在于 `suppliers[].id` |
| `supplier` | 是 | 供应商短名；应与 `supplier_id` 对应 |
| `category` | 是 | `工商` / `司法` / `处罚` / `安全环保` / `经营动态` |
| `severity` | 是 | `高` / `中` / `低`（正向事件也用 `低`） |
| `direction` | 是 | `风险` / `中性` / `正向` |
| `title` | 是 | 一句话事件标题，≤ 40 字 |
| `fact` | 是 | 2–4 句，含主体/时间/动作/数字；≥ 40 字 |
| `why` | 是 | 采购含义，含“需确认”的边界 |
| `source` | 是 | 来源名称，写清文件类型 |
| `source_type` | 是 | 公司公告 / 交易所 / 监管公示 / 海关 / 法院 / 媒体 / 行业资讯 |
| `source_date` | 是 | 文件日期 |
| `url` | 是 | `http(s)`；付费/易失效在 `url_label` 注明 |
| `url_label` | 建议 | 链接文字；缺省“打开原文” |
| `evidence` | 是 | `A` / `B` / `C` |
| `questions` | 是 | 非空数组，建议 3 个 |
| `action` | 是 | 可执行动作，不要写“关注一下” |
| `tags` | 否 | 搜索/标签用 |

**分类口径**：
- `工商`：经营异常、股权冻结、控制权、董监高、注册信息。
- `司法`：诉讼、仲裁、被执行、失信、监管处罚中的司法部分。
- `处罚`：海关、税务、市场监管、生态环境、应急等行政处罚。
- `安全环保`：事故、火灾、泄漏、环保督察、停产整改、排污许可。
- `经营动态`：检修、减量、复产、业绩、融资、项目、关停、股权交易。

> 同一事件只归一类；跨类时选“对采购决策最直接”的那类，其余在 `tags` 体现。

---

## 5. `industry[]`

```json
{"text": "2026 年纯碱新增产能…", "source": "协会月报 / 券商研报", "date": "2026-10-10"}
```

2–4 条即可；只用于解释个体事件的分量，不替代事件证据。

---

## 6. `coverage_check[]`

固定六类，顺序建议如下：

```json
[
  {"cat": "经营异常", "status": "未检索到公开记录", "note": "已查…；地方数据可能滞后。", "level": "待复核"},
  {"cat": "行政处罚", "status": "1 条（海关，9 万元）", "note": "金额低；需确认整改。", "level": "低"},
  {"cat": "诉讼仲裁", "status": "1 条（已和解）", "note": "…", "level": "中"},
  {"cat": "安全环保事故", "status": "未检索到事故", "note": "仅见计划检修。", "level": "待复核"},
  {"cat": "重大股权变化", "status": "未检索到", "note": "…", "level": "—"},
  {"cat": "停产/项目变化", "status": "7 条", "note": "…", "level": "中"}
]
```

| 字段 | 说明 |
|---|---|
| `cat` | 六类之一；页面/Excel 按此渲染 |
| `status` | 查到几条 / 未检索到 / 待复核 |
| `note` | 查了哪些渠道、为什么可能漏、下一步 |
| `level` | `高` / `中` / `低` / `待复核` / `—` |

**注意**：`status` 写“未检索到公开记录”，不要写“无风险”。

---

## 7. `method`

```json
{
  "scope": ["范围1", "范围2"],
  "evidence_levels": [
    {"level": "A", "label": "可直接核对", "desc": "公告/交易所/政府原文"},
    {"level": "B", "label": "需回查", "desc": "主流媒体转述"},
    {"level": "C", "label": "仅作线索", "desc": "聚合平台/论坛"}
  ],
  "limits": ["非上市财务不公开", "地方处罚公示分散", "公开信息滞后"],
  "search_queries": ["\"公司名\" 行政处罚", "..."],
  "disclaimer": "本报告基于公开信息…不构成法律/财务/投资意见；未检索到≠无风险。"
}
```

页面“方法与来源”与 Excel `07_方法与口径` 都读这里。

---

## 8. 校验规则（`validate.py`）

**Error（必须修）**
- `meta` 缺 title/product/query_date/query_time/window_default/windows。
- `window_default` 不在 `windows`；窗口日期非法或 start > end。
- `suppliers` 为空；id 重复；必填字段缺失；`risk_level` 非枚举。
- `events` 为空；id 重复；日期非法；`supplier_id` 不存在；分类/严重度/方向/证据非枚举。
- 事件超出 12 个月窗口；`url` 非 http(s)；`questions` 为空。
- `coverage_check` 项缺字段。

**Warning（可交付但建议修）**
- 缺 `financial_period` / `period_tag` / `subtitle` / `scope_summary` / `product_en`。
- 供应商缺营收/净利。
- `fact` 少于 40 字。
- 事件供应商名与 `supplier_id` 对应名不一致。
- 缺 `coverage_check` / `industry` / `method` 子项。
- 默认窗口 end 与 `query_date` 不一致。

---

## 9. 最小可运行骨架

```json
{
  "meta": {
    "title": "示例品供应商风险雷达",
    "product": "示例品",
    "product_en": "DEMO",
    "product_full": "示例品（演示）",
    "query_date": "2026-10-19",
    "query_time": "2026-10-19 13:20",
    "window_default": "6m",
    "windows": {
      "3m":  {"label": "近3个月", "start": "2026-07-19", "end": "2026-10-19"},
      "6m":  {"label": "近6个月", "start": "2026-04-19", "end": "2026-10-19"},
      "12m": {"label": "近1年",  "start": "2025-10-19", "end": "2026-10-19"}
    },
    "financial_period": "2026H1",
    "period_tag": "2026-10"
  },
  "suppliers": [
    {"id": "S1", "name": "示例化工", "full_name": "示例化工有限公司", "code": "非上市",
     "market": "非上市", "region": "某省某市", "process": "某工艺",
     "capacity": "100 万吨/年", "capacity_short": "100 万吨",
     "revenue": "未披露", "profit": "未披露", "profit_yoy": "—",
     "risk_level": "低", "risk_label": "常规跟踪",
     "conclusion": "未检索到高/中风险事件；地方公示待复核。",
     "coverage": "公告与信用公示已查；非上市财务不公开", "tags": ["非上市"]}
  ],
  "events": [
    {"id": "E1", "date": "2026-09-01", "supplier_id": "S1", "supplier": "示例化工",
     "category": "经营动态", "severity": "低", "direction": "中性",
     "title": "计划检修 10 天", "fact": "公司公告称…（演示文本，需替换为真实事实）。",
     "why": "短期可供量下降；另一条线正常，需确认排产。",
     "source": "公司公告", "source_type": "公司公告", "source_date": "2026-09-01",
     "url": "https://example.com/demo", "url_label": "公告原文", "evidence": "A",
     "questions": ["减少多少吨？", "另一条线能否覆盖？", "何时复产？"],
     "action": "索取排产表与复产确认。", "tags": ["检修"]}
  ],
  "industry": [],
  "coverage_check": [
    {"cat": "经营异常", "status": "未检索到公开记录", "note": "演示", "level": "待复核"},
    {"cat": "行政处罚", "status": "未检索到", "note": "演示", "level": "—"},
    {"cat": "诉讼仲裁", "status": "未检索到", "note": "演示", "level": "—"},
    {"cat": "安全环保事故", "status": "未检索到", "note": "演示", "level": "—"},
    {"cat": "重大股权变化", "status": "未检索到", "note": "演示", "level": "—"},
    {"cat": "停产/项目变化", "status": "1 条", "note": "计划检修", "level": "低"}
  ],
  "method": {"scope": ["演示"], "evidence_levels": [], "limits": ["演示"], "search_queries": [], "disclaimer": "演示数据"}
}
```

---

## 10. 旧字段兼容

- `h1_revenue` → `revenue`
- `h1_profit` → `profit`

生成器优先读新字段，缺失时回退旧字段；新数据请直接用 `revenue` / `profit`。

---

## 11. 常见数据错误

| 现象 | 原因 | 修法 |
|---|---|---|
| 页面显示 `undefined` | 字段名拼错/缺失 | 对照本契约；跑 `validate.py` |
| Excel 封面还是旧产品 | 改了模板没改数据 | 只改 `data.json`，不要手改生成物 |
| 事件在 6 个月里不出现 | `date` 写成发布时间/格式错 | 改成事件发生日期 `YYYY-MM-DD` |
| 分类筛选少一类 | `category` 用了别名（如“环保”） | 用固定五类；环保归 `安全环保` |
| 链接点不开 | 政府页面改版/需登录 | 换原文/稳定链接；`url_label` 注明 |
| 供应商弹窗空白 | `supplier_id` 与 `id` 不一致 | 对齐 id |
