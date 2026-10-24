# 看上下游价格联动 · 技能包

## 这是什么

一个可复用的分析流程：给定一组上下游品种，产出「价格是否联动、价差高低、哪个阶段背离」
的完整结论，附带交互式报告与公式化工作簿。

## 目录结构

```
SKILL.md                      技能主文件（用途、触发条件、七步流程、硬约束）
README.md                     本文件
references/
  01-方法论.md                为什么容易做错 + 正确顺序 + 七步详解
  02-工艺与单耗台账.md         只允许使用的单耗来源（PX→PTA 完整台账）
  03-公式与统计口径.md         13 个公式的算法、Excel 写法、陷阱
  04-口径清单.md              拿到数据先过的 A~H 八张表
  05-红线清单.md              十条不能破的规则 + 交付自查
  06-事件与分期台账.md         阶段划分原则 + 事件记录 + 表述模板
  07-报告模板.md              九节结构 + 写法规范 + 图表规范
scripts/
  config.py                   品种/单耗/阶段/窗口 集中配置
  researchlib.py              统计内核（纯标准库，无第三方依赖）
  selftest.py                 内核自检（21 项）
  parse_100ppi.py             解析生意社商品情报快照
  parse_sunsirs.py            解析生意社逐日日页（含日期错位校正）
  validate_sources.py         双源互校与日期对齐检验
  build_dataset.py            日历对齐、缺失登记、质量报告
  analysis.py                 七步分析引擎
  industry_graph.py           产业关系图（内联 SVG）
  build_html.py              生成单文件交互式报告
  build_excel.py             生成 13 表公式工作簿
  build_template.py          生成空白模板
  xlfn_fix.py                 Excel 新版函数前缀修补
  verify_excel.py            工作簿公式校验（重算后比对 Python）
  verify_template.py         模板校验
  run_all.py                 一条命令跑完整流程
  cdp_fetch.js               无头 Chrome 抓取（绕过反爬）
  mkjobs.py / mkurls_jobs.py 抓取任务生成
  coverage.py                抓取进度统计
assets/templates/
  report.html                报告模板（含示例数据，可直接改）
  联动分析模板.xlsx           空白工作簿模板
examples/px-pta-price-linkage/
  README.md                  案例说明与结论摘要
  report.html                完整案例报告
  px_pta_workbook.xlsx       完整案例工作簿
  analysis.json              七步分析结果
  data/                      面板数据、质量报告、事件台账
```

## 快速开始

```bash
# 1. 自检
python scripts/selftest.py

# 2. 换品种：改 config.py 的品种、单耗、阶段，把价格 CSV 放到 processed/
#    CSV 格式：date,px,pta（列名可改，config 里对应）

# 3. 跑全流程
python scripts/run_all.py

# 4. 校验工作簿
python scripts/verify_excel.py build/px_pta_workbook.xlsx build/analysis.json recalc.xlsx
```

## 环境要求

- Python 3.9+，**仅标准库**（统计内核不依赖 numpy/pandas，便于分发）
- 生成 Excel 需要 `openpyxl`
- 公式校验需要 LibreOffice（或任意能重算 xlsx 的工具）
- 抓取需要 Node.js + Chrome/Chromium

## 设计取舍

| 决策 | 理由 |
|---|---|
| 统计内核只用标准库 | 换机器/换环境不会因依赖问题跑不起来 |
| 缺失不插值 | 插值会人为压低波动率、抬高相关性 |
| 单耗台账独立成文 | 系数是所有价差的唯一来源，必须可核查 |
| Excel 全部活公式 | 读者能自己改参数看结论怎么变 |
| 阶段预先定义 | 避免按结果切分导致的数据窥探 |
| 报告单文件 HTML | 可直接邮件转发、离线打开 |

## 已知局限

- 未内置库存/开工率等产业高频数据（公开连续序列获取困难，需业务方指定来源）
- 醋酸等辅料价格未接入，其他成本默认 0
- 事件解释只能到「时间窗口一致」，不是因果证明

## 相关技能

- 单品种行情：`chem-market-brief`
- 两个指标相关性：`12.查两个指标的相关性`
- 下游客户线索：`b2b-lead-sourcing`
