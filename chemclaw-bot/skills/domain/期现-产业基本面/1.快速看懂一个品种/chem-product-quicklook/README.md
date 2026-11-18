# chem-product-quicklook · 快速看懂一个品种

给化工期现/产业研究员用的**品种研究入口**生成器：一个品种进来，两件交付物出去。

- **交互式 HTML 研究页**（单文件、离线可开）：首屏核心信息卡 + 产业链骨架 + 研究指标框架；
  产业链节点可点击展开，查看价格锚点、企业、产能、在建项目；下方面板展开
  工艺 / 企业产能 / 下游 / 区域 / 期现 / 关键变量。
- **12 表 Excel 工作簿**：产品百科、牌号规格、工艺路线、产业链节点、企业产能、
  下游需求、贸易区域、期货交割、关键指标、来源清单、缺口与核验。

## 核心主张

**这不是一份 AI 生成的行业综述，而是一张可复核的研究底稿。**

1. 每个关键数字都带**来源 + 日期 + 口径**；拿不到就写"缺口"并给补数路径。
2. 同一指标出现多口径时**并列展示**（名义产能 vs 有效产能、集团 vs 单厂、不同年份的占比），
   不取平均、不擅自择一。
3. 价格**必须由原始序列计算**（分位、区间、成交、持仓），禁止手写"约 2500 元/吨"。
4. 四类信息分开标注：产业链事实 / 工艺典型参数 / 公开统计 / 研究判断。
5. 品种入口页**不做方向判断**（校验器会拦截"看涨/看跌/抄底"）。

## 快速开始

```bash
# 1. 复制数据模板
cp assets/research.template.json my-product.json

# 2. 按 references/question-framework.md 的 8 问填数据
#    抓网页正文用：
python scripts/fetch_source.py --list urls.txt --out raw/

# 3. 有期货的品种：从日线算真实价格锚点（不要手写价格）
python scripts/fetch_futures_series.py --symbol MA0 --out raw/MA0.json
python scripts/build_anchors.py raw/MA0.json --name "郑商所甲醇主连" --src S22 --out raw/anchors.json

# 4. 校验 → 出图 → QA
python scripts/validate.py my-product.json
python scripts/build_html.py my-product.json --out out/
python scripts/build_xlsx.py my-product.json --out out/
python scripts/qa_render.py "out/xxx.html" --shots out/shots
python scripts/check_xlsx.py "out/xxx.xlsx" --research my-product.json
```

## 交付前必须全部通过

| 命令 | 通过标准 |
|---|---|
| `validate.py` | `error=0` |
| `qa_render.py` | `失败 0 项`（29 项交互 + 设计回归） |
| `check_xlsx.py` | `error=0` |

## 目录

```
├── SKILL.md                 技能主文档（给 Agent 看的工作流）
├── manifest.yaml            结构化元信息
├── references/              方法手册（9 篇）
│   ├── question-framework.md    8 问怎么问、坑在哪
│   ├── data-contract.md         research.json 字段规范
│   ├── chain-graph-method.md    产业链图怎么建
│   ├── caliber-and-conflict.md  口径冲突处理四步法
│   ├── capacity-survey.md       企业与产能调查
│   ├── futures-rules.md         合约与交割要素清单
│   ├── indicator-library.md     指标库与"为什么看"
│   ├── route-library.md         工艺路线模板（仅方法参考）
│   └── qa-checklist.md          交付自检
├── assets/
│   ├── research.template.json   空白数据模板
│   └── research.schema.json     JSON Schema
├── examples/
│   ├── methanol/                甲醇完整案例（21 节点 / 17 来源 / 8 缺口）
│   └── no-futures-example/      无期货降级示例
└── scripts/                     8 个脚本 + 3 个模板
```

## 甲醇案例的实际状态

- 产能、产量、工艺结构、单套规模、MTO 占比、开工率 → 中国氮肥工业协会报告（2026-05 榆林会议）
- 进口、开工率分路线、MTO 利润、传统下游 → 期货日报（数据源隆众）2026-01
- 下游单耗（甲醛 0.45 / 醋酸 0.54 / MTBE 0.365 / BDO 0.88 / 二甲醚 1.4 / DMF 0.438）→ 国投安信期货 2024-09
- MTO 单耗 2.87 → 中科院大连化物所（宝丰二期盘库）；2.66 → DMTO-Ⅲ 中试（人民日报·中国能源报）
- 价格锚点 → MA 主连 2862 个交易日真实日线计算
- **缺口 8 条**：现货逐日序列、港口/厂库库存、郑商所规则原文、分国别进口、分省产能、
  企业单套产能、2025 年下游分项、MTO 利润序列

## 依赖

Python 3.9+，`openpyxl`、`playwright`（需 `playwright install chromium`）。无 Node 依赖。

## 不适用场景

- 只要当前行情与价格 → `chem-market-brief`
- 要找下游客户 → `b2b-lead-sourcing`
- 区域市场走访地图 → `chemical-region-market-map`
- 采购前价格研判 → `chem-procure-brief`
