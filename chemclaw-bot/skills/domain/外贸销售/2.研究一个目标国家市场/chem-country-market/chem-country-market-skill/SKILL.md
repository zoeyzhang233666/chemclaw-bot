---
name: chem-country-market
description: >
  研究一个目标国家的市场：为某个化工产品（可换任何品类、任何国家）产出一份可交付、
  每个数字都能追溯到出处的国别市场研究报告（自包含交互式 HTML + 17 表 Excel）。
  九个必答问题：当地相关产业与下游应用 / 近 3–5 年进口金额数量与增长 / 中国出口该国的规模份额变化 /
  主要竞争来源国与当地生产企业 / 市场规模产能与进口依赖 / 关税贸易协定非关税措施与进口政策 /
  与中国的贸易关系及近期政策变化 / 公开研报协会商务部指南官方统计要点 / 仍缺哪些影响销售判断的数据。
  触发词：国别市场 / 目标国家市场 / 出口市场研究 / 某国市场多大 / 这个国家能卖多少 /
  进口依存度 / 当地有没有产能 / 关税多少 / 中国出口到某国 / 竞争对手是哪些国家 / country market study。
  风格：只写能核实的，核实不了的明确写“缺口”并给出补法，不臆造市场规模、产能或客户需求。
license: MIT
---

# 研究一个目标国家市场（化工品外贸版）

## 命令速查（30 秒上手）

```bash
# 1) 拉海关数据（免密钥）
python scripts/fetch_trade.py --reporter 360 --product 283620 --years 2021-2025 --exporter 156
# 2) 原始数据 → 分析结果 → 回写 case.json
python scripts/calc_trade.py raw/comtrade_360_283620.json
python scripts/sync_case.py case.json --raw raw/comtrade_360_283620.json
# 3) 校验（case.json 是唯一人工维护的文件）
python scripts/validate.py case.json
# 4) 一条命令出全部产物，并做静态 + 浏览器渲染校验
python scripts/build_all.py case.json --render
# 5) 脚本链自检（合成数据，不联网）
python scripts/selftest.py --case case.json
```

`build_all.py` 内部依次调用 `build_html.py`（自包含 HTML）、`build_xlsx.py`（17 表 Excel）、
`check_html.py`、`check_xlsx.py`、`qa_render.py`（可选：驱动本机 Edge/Chrome 检查图表是否真有像素、
有无 JS 报错/文字溢出/占位泄漏）。任何一步失败即判定不可交付。

## 这个技能解决什么

外贸销售拿到“去研究一下 X 国市场”时，最常见的两种失败是：
1. **只写产业描述**——“该国玻璃工业发达、需求旺盛”，没有一个可核验的数字，客户一问就露馅；
2. **把估算当事实**——“市场规模 25 万吨”，实际来自某个付费报告的摘要，被客户用海关数据一戳就崩。

本技能的做法：**以海关数据为骨架，以官方/企业公开资料为血肉，把不知道的部分明确标成缺口**。
产出物是一个销售可以直接拿去说服客户、又经得起客户核对的包：
一份自包含交互式 HTML 报告（离线可开、图表可交互、每个数字点得开来源）
＋ 一份 17 个工作表的 Excel 工作底稿（可批注、可交接、可当调研清单继续跑）。

## 何时用

- “帮我看看 XX 国这个产品能不能卖 / 卖多少 / 谁在买”
- “客户问我们中国货在当地占多少份额”
- “这个国家有没有本地厂，会不会替代进口”
- “税多少、有没有反倾销、能不能用 Form E”
- 任何需要把“国别市场”写成可交付材料的场景

不适用：只要一个现货价格（用 `chem-market-brief`）；只要客户名单（用 `b2b-lead-sourcing` / `benchmark-lead-sourcing`）。

## 核心原则（违反其中任何一条都不算完成）

| # | 原则 | 落到操作上 |
|---|---|---|
| 1 | **一个数字一个出处** | 每个数字必须指向 `sources[]` 里的一个 id；没有来源的数字不写 |
| 2 | **区分四类信息** | 实际贸易数据（海关）/ 机构估算（IndexBox 之类）/ 企业公开资料（新闻稿、年报）/ 一般产业描述。四类在报告里用不同徽标，不能混成一句话 |
| 3 | **不知道就写缺口** | 消费量、吨耗、应用拆分、对某客户的年用量——无法核实时一律进 `gaps`，并写清“怎么补”，**不填数字** |
| 4 | **两套口径不调和** | 印尼自华进口（CIF）与中国对印尼出口（FOB）天然不同，并列展示，不强行对齐 |
| 5 | **税率只用官方来源** | 第三方汇总站的 0% 只能写“第三方称”，状态标 `gap`；报价前必须用官方税则库核一次 |
| 6 | **不预测** | 不写“预计将增长”；写“过去 5 年 CAGR 为 X，最新年度份额为 Y，下一步看什么指标” |

## 工作流程（9 步，每步都有产物）

### 第 1 步：锁定口径（10 分钟，不省）
问自己四个问题并写进 `meta`：
- **HS 编码到底覆盖什么**：`2836.20` 碳酸钠包含重质+轻质、工业级+食品级，无法用海关数据拆分；这一句必须写进报告（`structure.hs_scope_note`）。
- **目标国用哪个 reporter**：UN Comtrade 的 `reporterCode`（印尼=360，中国=156），而不是“出口国=M、伙伴=目标国”的镜像口径。**用目标国自报的进口数据**，因为份额要跟同一国的分母比。
- **金额与数量口径**：进口=CIF 海关价值，出口=FOB；数量=`netWgt`（净重 kg）。净重没报送就是没报送，**不做换算、不做估算**。
- **窗口**：近 5 年 + 更长金额序列做对照。

### 第 2 步：拉海关数据
```bash
python scripts/fetch_trade.py --reporter 360 --product 283620 --years 2021-2025 --exporter 156
python scripts/sync_case.py case.json --raw raw/comtrade_360_283620.json
python scripts/calc_trade.py raw/comtrade_360_283620.json
```
- 数据源：UN Comtrade 公开预览 API（免密钥）。见 `references/source-playbook.md` 的接口、限流与备选。
- 必须过滤 `partner2Code == 0`（否则重复计数），并按伙伴代码去重。
- 数量和金额缺失：函数会打印“净重未报送…不做推算”，这就是报告里的缺口。

### 第 3 步：判断“谁在这里买”
按这个顺序找证据，命中即写、不命中记缺口：
1. **已投产下游企业**（玻璃、洗涤剂、冶金…）——企业官网产品线、招股书、环评、当地新闻
2. **在建/规划项目**——投资公告、园区新闻、总统/部长站台报道
3. **本地竞争者**——产能新闻、停产报道、进口替代路线
4. **分销/贸易商**——当地化工分销商目录、MSDS 上的进口商信息
5. **仍不知道的集群**——写进 `consumers_unnamed`，给检索建议

### 第 4 步：政策与关税
必须查的四块：MFN/协定税率、进口许可类非关税措施（LARTAS/配额/SNI/BPOM/Halal）、增值税与预缴所得税、本地化含量（TKDN 之类）。
**凡是没打开官方税则库逐条核过的税率，`rate_pct` 留 `null`、`status: "gap"`**，正文写“第三方称 0%，待核实”。
详见 `references/tariff-policy-guide.md`。

### 第 5 步：写 case.json
唯一需要人工维护的文件。契约见 `references/data-contract.md`；证据分级见 `references/evidence-grading.md`。
写完立刻校验：
```bash
python scripts/validate.py case.json
```
它会抓：缺字段、引用了未登记的来源、伙伴金额超过合计、金额量级异常（漏乘 1000/10000）、预测性表述、缺口为空。

### 第 6 步：生成
```bash
python scripts/build_all.py case.json --render
```
一次跑完：校验 → HTML → Excel → 静态检查 → 浏览器渲染（图表是否有像素、有无 JS 报错/溢出/占位泄漏）。
产物在 `out/`：`<国家>-<产品>_国别市场研究.html`、`.xlsx`、`data.json`、`qa/`。

### 第 7 步：自检
```bash
python scripts/selftest.py --case case.json
```
不联网、用合成数据验证“脚本链没有偷偷臆造数值”（例如数量缺失时 CAGR 必须是 `None`）。

### 第 8 步：交付 + 交接
报告第 5 节自带两个按钮，把结论带到下游技能：
- **找海外候选买家** → 传 `national_market_handoff`（产品、HS、国家、下游集群、已知企业）
- **查产品出口要求** → 传 `export_requirement_handoff`（HS、目标国、已核/待核政策项）

### 第 9 步：明确告诉客户“这份报告不回答什么”
第 5 节列出缺口与待核实行动（P0/P1/P2）。**这一节不是免责声明，是下一次调研的提纲**，
也是你最专业的地方：敢写“我不知道吨耗，所以我不给你算消费量”的销售，比给一个漂亮假数字的更可信。

## 目录结构

```
chem-country-market/
├─ SKILL.md                     本文件
├─ README.md                    快速开始 & 与其它技能的边界
├─ references/
│  ├─ data-contract.md          case.json 字段契约（唯一人工维护的文件）
│  ├─ source-playbook.md        免费/权威数据源清单 + 检索与取数技巧
│  ├─ tariff-policy-guide.md    关税、协定、非关税措施怎么查、怎么标状态
│  ├─ evidence-grading.md       四类信息与 T1–T4 来源等级、判定口径
│  ├─ qa-checklist.md           交付前 40 项检查（人肉版）
│  └─ adapters.md               在 ChemClaw / WorkBuddy / Codex / Claude / DSH 中的调用方式
├─ scripts/
│  ├─ common.py                 校验 + 派生指标（份额、CAGR、HHI、KPI）
│  ├─ fetch_trade.py            Comtrade 取数
│  ├─ calc_trade.py             原始数据 → 分析结果
│  ├─ sync_case.py              重算结果回写 case.json
│  ├─ validate.py               校验
│  ├─ build_html.py             HTML 生成（内联 ECharts，离线可用）
│  ├─ build_xlsx.py             17 表 Excel 生成
│  ├─ build_all.py              一条命令跑全流程
│  ├─ check_html.py / check_xlsx.py   静态检查
│  ├─ qa_render.py              真浏览器渲染校验（可选，驱动本机 Edge/Chrome）
│  ├─ selftest.py               脚本链自检（合成数据，不联网）
│  ├─ templates/report.html     报告模板
│  └─ assets/echarts.min.js     离线图表库
└─ examples/01-idn-soda-ash/    完整案例：中国重质纯碱出口印度尼西亚
   ├─ case.json                 43 个来源、8 项缺口、9 条待核实行动
   ├─ raw/                      Comtrade 原始返回
   └─ out/                      成品 HTML / XLSX / data.json
```

## 换一个国家/产品，要改什么

只改 `case.json`。脚本、模板、样式都不用动：

| 要改的字段 | 例子 |
|---|---|
| `meta.subject` | 产品名、HS 6 位、品级、单位 |
| `meta.country` | 国家中文名、英文名、UN M49 代码 |
| `trade.*` | 用 `fetch_trade.py` 重新拉，`sync_case.py` 回写 |
| `industries.*` | 下游企业、本地生产、在建项目（这一步最费时间，也是报告最值钱的部分） |
| `policy.*` | 关税、非关税、协定、时间线 |
| `sources[]` | 每个来源的 URL、发布方、日期、tier |
| `gaps[]` / `verify_actions[]` | 不知道什么、怎么补、谁去补 |

## 常见错误（都踩过）

1. **用镜像数据算份额**：拿“中国对世界出口”当分母去算份额 → 份额全错。必须用目标国自报进口。
2. **把新闻稿的“产能”当产量**：30 万吨/年是设计产能，不是实际产出，要标 `capacity_basis`。
3. **把“在建”写成“已投产”**：用 `status` + `status_asof` 两个字段锁死时点。
4. **数量缺失时插值算增速**：`build_index` 会直接返回 `None` 并让 KPI 显示“未报送”，这是设计而不是 bug。
5. **第三方汇总站的税率直接写进报价单**：只能写“第三方称”，并进 P0 待核实。
6. **把机构估算的市场规模写成事实**：IndexBox 的“$280–360/t”“玻璃占 60–65%”只能标注为估算。

## 交付标准（Definition of Done）

- [ ] `validate.py` 0 error；`build_all.py --render` 全绿
- [ ] 九个必答问题在报告第 6 节的“口径对照表”里逐条能点到对应章节
- [ ] 每个数字带来源徽标；每个板块至少有 1 个 T1/T2 来源
- [ ] 缺口 ≥ 5 项，且每项写了“怎么补”
- [ ] 待核实行动有 P0 项（报价前必须解决的事）
- [ ] HTML 离线打开图表正常、无 JS 报错；Excel 17 个表无空格子歧义
