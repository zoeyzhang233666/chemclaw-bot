# 数据契约（followup.json）

一份 JSON 同时驱动 Excel 与 HTML。**只改 JSON，不手改产物**——计数、停滞天数、逾期状态都是算出来的。

脚本读取时用 `utf-8-sig`，所以文件带 BOM 也能读（Windows 编辑器常自动加 BOM，不要紧）。

## 顶层结构

| 键 | 必填 | 说明 |
|---|---|---|
| `schema_version` | 建议 | 固定 `"1.0"` |
| `meta` | ✅ | 抬头信息，见下 |
| `headline` | ✅ | 一句话结论，可含 `<b>` 强调 |
| `profile` | ✅ | 客户速览，`[{label, value, note?}]` |
| `kpis` | ✅ | 4 张指标卡，`[{label, value, note, tone}]` |
| `stage` | ✅ | 阶段与停滞，见下 |
| `blockers` | ✅ | 卡点，`[{title, status, status_tone, detail, impact, facts[]}]` |
| `timeline` | ✅ | 时间线，`[{no, date, time, source, actor, text, category, flag?}]` |
| `requirements` | ✅ | ① 客户明确需求 |
| `objections` | ✅ | ② 客户异议 |
| `promises` | ✅ | ③ 我方承诺 |
| `pending` | ✅ | ④ 待确认事项 |
| `ai_summary` | ✅ | AI 摘要（独立区块） |
| `unknowns` | ✅ | 无法辨认 / 缺失（无内容时给 `[]`） |
| `field_confirm` | ✅ | 字段确认清单 |
| `next_actions` | ✅ | 下一步动作 |
| `payload` | 可选 | 联动面板内容（微信草稿、邮件、通话提纲…） |
| `sources` | ✅ | 素材清单 |
| `rules` | ✅ | 整理口径，`[{title, desc}]` |
| `legend` | 可选 | 分类图例，缺省用内置七类 |

各表下方的 `*_note` 是可选的整段说明，会渲染在对应区块底部：

`requirements_note` `objections_note` `promises_note` `pending_note` `unknowns_note` `field_note` `stage_note` `timeline_note` `disclaimer_note`

---

## meta

| 字段 | 必填 | 说明 |
|---|---|---|
| `slug` | ✅ | 输出文件名（不含扩展名），如 `纯碱_德润玻璃_跟进卡` |
| `title` | ✅ | 跟进卡标题 |
| `doc_title` | 可选 | 浏览器标签/页脚用的长标题，缺省用 `title` |
| `eyebrow` | 可选 | 页面上方小标签，默认「内贸销售 · 客户跟进记录整理」 |
| `customer_name` | ✅ | 客户全称 |
| `customer_suffix` | 可选 | 抬头副标题，如「纯碱 · 泰州厂」 |
| `cover` | 可选 | 抬头下方一行摘要，可含 `<b>` |
| `product` / `product_family` / `industry` / `region` | 建议 | 产品牌号、品类、下游行业、区域 |
| `owner` | 建议 | 我方负责人 |
| `as_of_date` | ✅ | **时间基准，填今天**（`YYYY-MM-DD`） |
| `generated_at` | ✅ | 生成时间戳 |
| `quote_expiry` | 可选 | 报价有效期，用于「剩 N 天」提醒 |
| `source_count` | 建议 | 素材份数 |
| `subject` / `description` / `keywords` / `creator` | 可选 | 写进 Excel 文档属性 |
| `disclaimer` | ✅ | 页脚免责声明 |

---

## stage

```json
{
  "current": "报价谈判",
  "judgement": "为什么判这个阶段（可含 <b>）",
  "assets": "我方可复用的筹码",
  "risk_note": "口径说明 / 最重要的风险提醒",
  "stages": [
    { "name": "初次接触", "label": "✔ 已完成", "state": "done",
      "date": "09-18", "basis": "判断依据（要能指到证据）", "note": "一句话点评" }
  ],
  "stall": {
    "days": 5,
    "reasons": [{ "title": "分型", "detail": "具体表现" }],
    "risks":   [{ "title": "风险", "detail": "说明" }]
  }
}
```

- `current` 取值必须是六阶段之一：`初次接触` `需求确认` `送样` `报价谈判` `合同` `停滞`
- `state` 取值：`done` / `current` / `stalled` / `todo` / `risk`
  - `current` = 金色高亮；`stalled` = 红色高亮（当前阶段已停滞时用它）
- `stages` 建议固定 6 条，顺序就是六阶段
- `stall.days` 写不写都行：**写了但和核算值不一致，`validate` 会报 warning**；不写则用核算值

---

## timeline

```json
{ "no": 1, "date": "09-18", "time": "10:32", "source": "截图1",
  "actor": "客户", "category": "客户需求",
  "text": "客户询价：<q>你们重质纯碱什么价位</q>", "flag": "采购动机" }
```

- `category` 只能是七类之一：`客户需求` `客户异议` `我方承诺` `待确认` `客户动作` `我方动作` `系统提醒`
- 颜色按 `category` 自动分配，不需要你指定
- `text` 里客户原话用 `<q>…</q>`（渲染成浅黄底），我方转述直接写
- `flag` 是可选的角标：`停滞起点` `最后一条` `逾期` `无法辨认` 等
- 时间线必须**正序**；`no` 从 1 连续

---

## 四类清单

```json
// ① requirements
{ "dimension": "价格预期", "content": "到厂含税 ≤1580",
  "source": "纪要2 / 邮件3", "confidence": "高", "note": "书面重申" }

// ② objections
{ "no": 1, "content": "价格偏高", "source": "邮件3",
  "status": "未解决 · 差 70", "tone": "risk", "given": "让至 1650", "advice": "用账期换价格" }

// ③ promises
{ "no": 1, "content": "10-14 中午前回复付款政策", "promised_on": "10-13",
  "due": "2026-10-14", "source": "邮件4", "status": "逾期", "detail": "客户已表达担心" }

// ④ pending
{ "no": 1, "content": "付款政策最终口径", "type": "交易条款",
  "owner": "我方财务", "impact": "核心卡点", "target": "今天下班前" }
```

| 字段 | 说明 |
|---|---|
| `confidence` | `高` / `中` / `低` / `无法辨认` |
| `tone` | `risk` / `warn` / `ok` / `info`，控制配色 |
| `due` | 承诺截止日 `YYYY-MM-DD`；写不出具体日期时用 `随合同` `未定` 这类文字 |
| `status`（promises） | 人工写的初值。**逾期与否由 `due` 自动重算**，写 `未到期` 也会被改成 `逾期 N 天` |
| `owner`（pending） | 必须写清卡在谁：我方财务 / 客户采购 / 需用户补料 |

---

## ai_summary

```json
{ "badge": "AI 推断 · 非客户原话",
  "title": "这笔单子现在到底卡在哪",
  "paragraphs": ["第一段…", "第二段…"],
  "points": [{ "h": "判断", "p": "…" }, { "h": "建议顺序", "p": "…" }] }
```

`badge` / `title` 可省略。段落里可以含 `<b>`。**这一节是模型推断，不许出现客户没说过的"事实"**。

---

## next_actions

```json
{ "prio": "P0", "when": "今天 10-19 下班前",
  "action": "做什么（可含 <b>）", "closure": "闭环标准",
  "link": "wx", "link_label": "润色客户微信", "owner": "林芳" }
```

- `prio`：`P0` / `P1` / `P2`，决定颜色
- `link` 取值：`wx` / `mail` / `call` / `visit` / `upload` / 空
  - 有值时 HTML 会渲染按钮，点开显示 `payload[link]` 面板
  - `link` 为空则按钮不显示

---

## payload（联动面板）

```json
{
  "wx":     { "title": "微信话术草稿", "draft": "整段可直接复制的话术", "note": "润色原则" },
  "mail":   { "title": "邮件要点", "items": ["要点1", "要点2"] },
  "call":   { "title": "通话提纲", "items": ["…"] },
  "visit":  { "title": "拜访大纲", "items": ["…"] },
  "upload": { "title": "补传清单", "items": ["…"], "note": "补传后重新生成" }
}
```

`draft` 会带「复制」按钮；`items` 渲染成列表。两者可同时存在。

---

## sources / rules / legend

```json
"sources": [{ "no": "SOURCE 01", "name": "微信截图 OCR", "detail": "13 张 · 09-18 → 10-14", "count": "13" }],
"rules":   [{ "title": "只依据上传素材", "desc": "客户没说过的需求一律不补" }],
"legend":  [{ "name": "客户需求", "desc": "客户明确说过的条件" }]
```

`legend` 省略时用内置七类图例。

---

## 最小可运行示例

```json
{
  "schema_version": "1.0",
  "meta": {
    "slug": "demo", "title": "客户跟进卡 · 示例", "customer_name": "某化工厂",
    "as_of_date": "2026-10-19", "generated_at": "2026-10-19 10:00",
    "disclaimer": "示例数据"
  },
  "headline": "一句话结论",
  "profile": [{ "label": "产品", "value": "纯碱" }],
  "kpis": [{ "label": "Stage", "value": "报价谈判", "note": "", "tone": "info" }],
  "stage": { "current": "报价谈判", "judgement": "…", "assets": "…",
    "stages": [{ "name": "初次接触", "label": "✔", "state": "done", "date": "09-01", "basis": "…", "note": "…" }],
    "stall": { "reasons": [], "risks": [] } },
  "blockers": [],
  "timeline": [{ "no": 1, "date": "09-01", "time": "10:00", "source": "截图1",
    "actor": "客户", "category": "客户需求", "text": "要 100 吨" }],
  "requirements": [{ "dimension": "数量", "content": "100 吨", "source": "截图1", "confidence": "高" }],
  "objections": [], "promises": [], "pending": [],
  "ai_summary": { "paragraphs": ["…"] },
  "unknowns": [], "field_confirm": [],
  "next_actions": [], "sources": [], "rules": []
}
```

跑起来：

```bash
python scripts/build_followup.py demo.json -o out/
python scripts/selfcheck.py demo.json --outdir out/
```

完整可运行样例见 `examples/_skeleton/`（空白模板）与三个正式案例。
