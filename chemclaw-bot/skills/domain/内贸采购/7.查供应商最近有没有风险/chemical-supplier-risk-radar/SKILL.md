---
name: chemical-supplier-risk-radar
description: Use when a procurement or sourcing team asks whether a chemical supplier has had recent public risk events — 查供应商最近有没有风险 / 供应商风险扫描 / 准入前风险 / 续约前风险 / 供应商尽调 / 最近半年有没有处罚、诉讼、事故、停产、股权变化 — for any chemical product. Builds a supplier universe, sweeps 工商 / 司法 / 处罚 / 安全环保 / 经营动态 public records over 3/6/12-month windows, separates fact from inference, and delivers a self-contained interactive HTML dashboard plus a styled 9-sheet Excel workbook with evidence-graded sources, procurement questions, and an explicit coverage check. Product-agnostic: 纯碱、烧碱、钛白粉、甲醇、尿素、PVC、助剂、树脂 etc. Triggers supplier risk radar / chemical supplier due diligence / 供应商风险雷达.
---

# 化工供应商风险雷达

把「这家供应商最近有没有事」变成一条条**有时间、有主体、有来源、有采购含义**的公开事件，而不是一句“听说有问题”。

**产品无关**：纯碱、烧碱、钛白粉、甲醇、尿素、PVC、PTA、助剂、树脂都走同一套流程；换产品只换 `data.json`，生成器和版式不变。

## 什么时候用

用：
- 准入 / 续约 / 大额询价前，需要快速扫一遍供应商的公开风险。
- 老板或采购问「这几家最近有没有处罚、诉讼、事故、停产、股权变化」。
- 已有供应商名单，需要一份能直接开会讲的时间线 + 待核实清单。
- 需要把“公开新闻”与“是否影响交付”分开说清楚，避免过度推断。

不用：
- 只要价格 / 行情 → 用 `chem-market-brief`。
- 只要找客户 / 下游名单 → 用 `b2b-lead-sourcing` 或 `benchmark-lead-sourcing`。
- 需要完整财务、法律、现场尽调 → 本 skill 只做**公开信息桌面扫描**，是尽调的前置筛查，不替代尽调。

## 交付物（至少这两个）

1. **自包含 HTML**（单文件，约 80–120 KB，离线可开）
   - 首屏：产品、窗口、供应商数、事件数、高/中/低分布、分类雷达。
   - 五个视图：总览 / 事件时间线 / 供应商 / 方法与来源。
   - 筛选：近 3 个月 / 6 个月 / 1 年、五个风险分类、供应商、关键词、只看中高风险。
   - 点事件看：事实、采购关注点、待确认问题、来源、证据等级。
   - 点供应商看：产能、财务、风险标签、覆盖说明、该供应商全部事件。
   - 打印 / PDF 样式。
2. **9 表 Excel**
   - `00_封面` / `01_风险总览` / `02_事件时间线` / `03_分类汇总` / `04_供应商画像` / `05_待核实清单` / `06_来源清单` / `07_方法与口径` / `08_行业背景`。
   - 风险色阶、超链接、筛选、冻结窗格、打印区域。

两个文件都由同一份 `data.json` 生成，**数字天然一致**。

## 三步走

```
① 研究（本 skill 的方法）      → 结构化事实
② 写 data.json（数据契约）     → 一个 JSON 描述一次扫描
③ 生成 + 体检                  → HTML + Excel + QA
```

### ① 研究：先定边界，再扫五类

| 步骤 | 要回答的问题 | 主要取证通道 | 落到字段 |
|---|---|---|---|
| 0 定范围 | 是什么规格/牌号？买家拿它做什么？国内还是进口？时间窗口？ | 采购需求、牌号标准、合同 | `meta.product` / `scope_note` |
| 1 建全集 | 这个产品国内有哪些生产企业？上市/非上市、工艺、产能、基地 | 年报/公告、协会名单、产能统计、环评/备案、行业媒体 | `suppliers[]` |
| 2 工商治理 | 经营异常、股权冻结、控制权变更、董监高异常、注册地变更 | 国家企业信用信息公示系统、信用中国、交易所公告 | `events[]`（工商） |
| 3 司法监管 | 诉讼、仲裁、被执行、失信、证监会/交易所监管措施 | 裁判文书网、执行信息公开网、交易所/证监局 | `events[]`（司法） |
| 4 行政处罚 | 海关、税务、市场监管、生态环境、应急管理处罚 | 海关总署/直属海关、信用中国、地方局公示 | `events[]`（处罚） |
| 5 安全环保 | 事故、火灾、泄漏、停产整改、排污许可、环保处罚 | 应急管理部/地方应急局、生态环境局、事故通报 | `events[]`（安全环保） |
| 6 经营动态 | 检修/减量/复产、业绩、项目投产、融资、重组、关停 | 公司公告、交易所、环评/备案、行业资讯 | `events[]`（经营动态） |
| 7 行业背景 | 新增产能、开工率、价格、检修季，解释事件的分量 | 协会、期货研究、隆众/卓创、行业媒体 | `industry[]` |
| 8 覆盖检查 | 哪一类“查了但没有”？哪类渠道没覆盖？ | 检索记录 | `coverage_check[]` |

**证据等级**：
- **A**：公告/交易所/政府或监管原文，可直接核对。
- **B**：主流财经媒体、行业媒体转述，需回查原文。
- **C**：聚合平台、论坛、未具名信源，只能当线索。

**每条事件都要写四层**，不要混在一起：
1. `fact`：谁、何时、发生了什么、数字是多少。
2. `why`：为什么采购要在意；只说到“可能需要确认”的程度。
3. `questions[]`：3 个可直接问供应商的问题。
4. `action`：采购下一步做什么（索证、条款、替代源、复检）。

> 公开新闻 ≠ 未来断供。`why` 里禁止写“将断供”“一定涨价”“肯定停产”；只能写“可能影响…需确认…”。

详细取证通道、查询模板、误判清单见 `references/research-playbook.md`。

### ② 写 data.json

字段、枚举、校验规则见 `references/data-contract.md`；机器可读 schema 见 `schema/data.schema.json`。最小骨架：

```json
{
  "meta": {
    "title": "某产品供应商近期风险雷达",
    "product": "某产品",
    "product_en": "PRODUCT",
    "product_full": "某产品（牌号/规格）",
    "query_date": "2026-10-19",
    "query_time": "2026-10-19 13:20",
    "window_default": "6m",
    "windows": {
      "3m":  {"label": "近3个月", "start": "2026-07-19", "end": "2026-10-19"},
      "6m":  {"label": "近6个月", "start": "2026-04-19", "end": "2026-10-19"},
      "12m": {"label": "近1年",  "start": "2025-10-19", "end": "2026-10-19"}
    },
    "financial_period": "2026H1",
    "period_tag": "2026-10",
    "scope_summary": "默认近 6 个月…覆盖 N 家…"
  },
  "suppliers": [
    {"id": "S1", "name": "…", "full_name": "…", "code": "000000.SZ", "market": "深交所主板",
     "region": "…", "process": "…", "capacity": "…", "capacity_short": "…",
     "revenue": "…", "profit": "…", "profit_yoy": "…",
     "risk_level": "低", "risk_label": "…", "conclusion": "…", "coverage": "…", "tags": ["…"]}
  ],
  "events": [
    {"id": "E1", "date": "2026-09-01", "supplier_id": "S1", "supplier": "…",
     "category": "经营动态", "severity": "低", "direction": "中性",
     "title": "…", "fact": "…", "why": "…", "source": "…", "source_type": "公司公告",
     "source_date": "2026-09-01", "url": "https://…", "url_label": "公告原文",
     "evidence": "A", "questions": ["…", "…", "…"], "action": "…", "tags": ["…"]}
  ],
  "industry": [{"text": "…", "source": "…", "date": "2026-10-01"}],
  "coverage_check": [{"cat": "经营异常", "status": "未检索到公开记录", "note": "…", "level": "待复核"}],
  "method": {"scope": ["…"], "evidence_levels": [{"level": "A", "label": "可直接核对", "desc": "…"}],
             "limits": ["…"], "search_queries": ["…"], "disclaimer": "…"}
}
```

写完后先跑校验：

```bash
python scripts/validate.py data.json
```

### ③ 生成 + 体检

```bash
python scripts/build_all.py data.json --out out --name 产品-2026-10
python scripts/qa.py data.json "out/产品-2026-10.html" "out/产品-2026-10.xlsx"
```

`build_all.py` 会调用 `build_xlsx.py` 和 `build_html.py`；`qa.py` 做静态体检：占位符、DATA 注入、事件/供应商是否都在、Excel 表数与来源链接是否齐全。没有浏览器也能跑。

需要 PDF 时：

```bash
python scripts/build_all.py data.json --out out --name 产品-2026-10 --pdf
```

只有装了 LibreOffice（`soffice`）才会转；没有就跳过，不影响 HTML/Excel。

## 质量红线（不达标别交付）

1. **不把公开新闻等同于断供**。每条 `why` 只写“可能影响交付/合规，需确认什么”，不写“将断供/必涨价”。
2. **每条事件四件套齐全**：发生日期、责任主体、可核事实、来源链接。缺一个就不要放进去。
3. **“未检索到”≠“无风险”**。`coverage_check` 必须列出六类，明确哪些“查了但没有”、哪些“渠道没覆盖”、哪些“待复核”。
4. **主体要核清**：母公司 ≠ 子公司 ≠ 同名公司；事件发生在哪个基地、哪条线、哪个法人，写清楚。
5. **计划检修 ≠ 事故**；**罚单金额 ≠ 交付影响**；**亏损 ≠ 断供**。性质判断放在 `why`，不要混进 `fact`。
6. **证据等级不虚标**：A 必须能点开原文；只有媒体转述就标 B；聚合平台/论坛标 C，且 C 不能单独支撑“高风险”结论。
7. **风险等级是采购视角标签，不是信用评级**。页面与 Excel 都要有这句话。
8. **数据必须真实可核**。没有证据就写“未检索到公开记录”，不要编企业、日期、金额、产能、财务。

## 常见坑（都是真踩过的）

- **日期错位**：把 2025 年的旧闻当成 2026 年；再版/转载会刷新“发布时间”。以事件发生日期为准，来源日期单列。
- **同名公司**：只凭公司名搜索会把同名贸易商、子公司、关联方混进来；用统一社会信用代码/证券代码/注册地交叉确认。
- **母公司公告写的是子公司**：事件主体写子公司全称，`supplier` 仍是采购合同相对方，避免张冠李戴。
- **名义产能 ≠ 可供量**：检修、减量、试生产、许可证到期都会让可供量低于名义产能；`capacity` 写清口径。
- **“未检索到事故”被写成“无事故”**：公开渠道没有 ≠ 没发生；只能写“未检索到公开事故记录”。
- **链接失效**：政府网站改版、临时链接会 404；优先存“来源名称 + 发布日期 + 可访问 URL”，并在 `url_label` 写清是什么文件。
- **财务口径混用**：H1 与全年、归母与合并、亿元与万元；`financial_period` 必须写清，数字带单位。
- **页面数字与 Excel 对不上**：两边都从同一份 `data.json` 生成；不要手改 HTML 里的计数。
- **中文列宽/行高**：openpyxl 不会自动适应；生成器已按 CJK 字符估算，改列宽后要复查是否压字。

## 不同 agent 上怎么用

见 `references/adapters.md`。要点：整个目录是一个自包含单元，`SKILL.md` 是入口，`scripts/` 只依赖 Python 3 + openpyxl；HTML 无 CDN、无外部资源。Claude Code 放 `~/.claude/skills/`，Codex / chemclaw / workbuddy / 通用 agent 放项目 `skills/` 或把 `SKILL.md` 作为系统指令、目录挂到工作区。

## 示例

- `examples/01-soda-ash-2026-10/`：完整真实案例（纯碱，7 家供应商 / 19 条事件 / 6 个月窗口 16 条），含 `data.json`、成品 HTML/Excel/PDF，是最好的写作范本。
- `examples/02-minimal-demo/`：4 家虚构供应商 / 6 条虚构事件的**占位演示**，用来学最小数据契约和跑通生成器；不可用于任何真实判断。

先读 01 的 `data.json` 看真实颗粒度，再用 02 练手。

## 最小提示词

```
读取 chemical-supplier-risk-radar/SKILL.md，按其中「三步走」执行。
产品：<产品 + 规格/牌号>   采购区域：<区域>   截止日：<YYYY-MM-DD>
候选供应商：<名单，或让模型先建>
要求：
1) 只写可核实的公开事实，每条带日期、主体、来源链接与证据等级；
2) 事实、采购含义、待确认问题分开写，不把新闻等同于断供；
3) 六类覆盖检查都要有，明确“未检索到”的类别；
4) 生成 HTML + Excel，跑 validate.py 和 qa.py 通过；
5) 数据不足就标“未检索到/待复核”，不要编。
```
