---
name: new-capacity-project-tracker
description: >
  Use when someone needs to track NEW CAPACITY and the projects behind it for a chemical product or
  industrial material — 跟踪新增产能和项目 / 新增产能 / 在建项目 / 拟建项目 / 产能扩张 / 未来两年投产 /
  产能投放节奏 / 装置投产进度 / 项目备案环评开工试车投产 / 产能增量平衡表. Applies to any product
  (聚丙烯PP、聚乙烯PE、纯碱、烧碱、尿素、甲醇、PVC、PTA、乙二醇、苯乙烯、丙烯酸、工业硅、多晶硅、
  磷酸铁锂、EVA、ABS…). Delivers a UNIQUE project archive with append-only progress log and
  expected-startup change history, an interactive HTML dashboard (timeline, annual capacity chart,
  project map, filterable detail table, watchlist), and a multi-sheet Excel workbook — in which
  备案/环评/在建/计划 NEVER count as effective supply, and every number traces to a dated source.
  Triggers: 跟踪新增产能和项目, new capacity tracking, project pipeline, startup schedule,
  产能投放, 投产节奏, 项目进度跟踪, 期现研究, 产业基本面.
---

# 跟踪新增产能和项目（New Capacity & Project Tracker）

一套**证据驱动**的新增产能跟踪方法。适用于任何化工品/工业材料，不绑定品种。

## 这个技能解决什么问题

做期现研究时，"未来有多少新产能要投产"是最容易出错、代价最大的判断。常见错误有三种：

1. **把"计划"当"供应"**。备案、环评、开工、建设中、计划投产，全部被加总成"新增产能"，得出一个漂亮但错误的大数字。
2. **重复计算**。同一个项目的多条生产线被登记成多个项目；同一个项目在不同来源里名字不同、产能不同，被当成两个项目；已投产的产能被再次算进新增。
3. **覆盖历史**。每次更新就把上一次的"预计投产时间"改掉，结果永远无法回答"这个项目改过几次口、每次是谁说的、当初为什么判断错了"。

本技能用**三表数据契约 + 追加式记录制度 + 机械可审计的缺口判定**彻底解决这三个问题。

## 九步工作法

| 步骤 | 做什么 | 关键产出 | 详见 |
|---|---|---|---|
| 1 | 检索最近 6-12 个月新披露的项目 + 未来 1-2 年预计投产的项目 | 线索池 | `references/01-检索与信源.md` |
| 2 | 逐项目核实：业主、所属集团、项目名称、所在地区、产品、设计产能、工艺路线、项目性质 | 项目档案 | `references/02-字段口径.md` |
| 3 | 跟踪进度：备案→环评→开工→建设→设备安装→试车→投产→达产 | 进展记录 | `references/03-进展阶段与证据.md` |
| 4 | 记录首提预计投产 vs 最新预计投产，判断是否延期 | 变更史 | `references/04-计划时间与延期.md` |
| 5 | 每条进展标消息日期、事实发生日期、来源、证据等级 | 可追溯链 | `references/03-进展阶段与证据.md` |
| 6 | 按预计投产时间排出时间线 | 时间线 | `references/06-交付物规范.md` |
| 7 | 按年度、地区汇总未来产能，与现有产能比 | 平衡表 | `references/05-汇总口径.md` |
| 8 | 区分新建/置换/扩建/重复披露，避免重复计算 | 去重映射 | `references/07-去重与更新规则.md` |
| 9 | 明确投产时间与爬坡的不确定性 | 不确定性说明 | `references/05-汇总口径.md` |

## 铁律（违反即结论作废）

> **不得把备案、建设中或计划投产的项目直接认定为已经形成有效供应。**

由此派生四条操作规则：

- **只有"试车/投产/产出合格品/达产/商业运营"且证据等级为 A 或 B，才可以写"已形成有效供应"。**
- **产能状态必须随身携带。** 任何一张表、任何一个数字，都要能回答"这是哪一状态的产能"。不允许出现不标状态的裸产能数字。
- **四类口径互斥。** 已投产 / 试车调试 / 建设中 / 计划（仅批文），同一套装置在同一时刻只归一类。四类相加 = 名义新增，不重复不遗漏。
- **设计产能 ≠ 年度产量。** 不做"产能 × 开工率 = 供应量"的混算。

## 快速上手（10 分钟跑通）

```bash
# 1. 初始化项目目录
python scripts/ppctl.py init ./my-product-tracker

# 2. 按 templates/ 的字段填 data/projects.json、data/progress.json、data/sources.json
#    再用你的产品参数改 data/config.json（产能基数、单位等）

# 3. 校验 -> 展开 -> 生成 -> 自检
python scripts/ppctl.py all ./my-product-tracker
```

产物在 `out/`：
- `xxx跟踪看板.html` —— 单文件自包含交互看板，双击即用，无网络依赖
- `xxx跟踪台账_YYYYMMDD.xlsx` —— 14 表工作簿

依赖：Python 3.8+，Excel 生成需要 `openpyxl`（其余纯标准库）。

## 仓库结构

```
SKILL.md                        本文件：方法总纲与九步法
references/
  01-检索与信源.md               检索路径、信源分级、常用检索词、失效引擎规避
  02-字段口径.md                 项目档案的每个字段怎么填、边界怎么划
  03-进展阶段与证据.md           阶段枚举、证据分级、事实日vs消息日、负结果记录法
  04-计划时间与延期.md           两段式计划时间、延期判定、精度变化的陷阱
  05-汇总口径.md                 年度/地区汇总、四类互斥、隐性供给缺口、爬坡折扣
  06-交付物规范.md               HTML看板与Excel工作簿的必备要素
  07-去重与更新规则.md           ★核心：九条去重规则、更新制度、剔除留痕
  08-跨Agent移植.md              在其他Agent/环境中复用本技能
  09-失败案例库.md               真实踩过的坑与修正过程
examples/
  pp-2026/                       完整案例：中国聚丙烯2026-2028新增产能
    README.md                    案例导读与核心结论
    data/                        projects.json / progress.json / sources.json / config.json / geo_cn.json
    out/                         成品HTML看板 + Excel台账
templates/
  projects.json / progress.json / sources.json / config.json 的空白模板（含逐字段说明）
scripts/
  ppctl.py                       主引擎：init/validate/expand/build/check/all
  build_excel.py                 Excel 生成器
  build_html.py                  HTML 看板生成器
  build_check.py                 交付自检
  make_geo.py                    中国省级边界生成（产物已随模板分发，通常不必重跑）
```

## 三个最容易被忽略、但决定质量的动作

**1. 记录"负结果"。**
"截至某日，未检索到该项目试车或投产的任何公开报道"——这句话本身就是一条有价值的进展记录。
它把"没有证据"和"没查过"区分开了。`examples/pp-2026` 里有 8 条这样的记录，它们直接决定了若干项目的结论强度。

**2. 算"隐性供给缺口"。**
名义计划落在当年、但工程证据不支持年内形成供应的产能。本技能的判定规则是机械的（`scripts/ppctl.py` 中的 R1/R2/R3），不靠主观打分，因此可被他人复核。
案例中 2026 年名义新增 480 万吨，其中 280 万吨（58%）被判定为年内不可能形成供应——**这才是这个技能的核心价值所在**。

**3. 去重要留痕，不要静默删除。**
每一条被排除的记录都写明理由与依据来源编号（见 `data/projects.json` 的 `excluded[]`）。
去重不是删掉，是让后来者看到"为什么不算"，避免同一个错误被反复引入。

## 适用与不适用

**适用**：任何有明确装置级产能、有公开批文与工程进度的化工品/材料；需要判断"未来 6-24 个月真实会新增多少供应"的场景。

**不适用**：
- 产能高度分散、无单个装置规模意义的品种（如部分精细化工中间体）
- 完全依赖进口、国内无新增项目的品种
- 需要判断"新增产能会不会真的开车"以外的商业决策（本技能只回答工程与批文事实，不预测厂商的商业博弈结果——但会把这类风险显式标注出来，例如"已建成但择机试生产"）

## 一句话总结

**把每一个产能数字，都拴在一条有日期、有来源、有证据等级的事实上；把每一次判断，都留成可回溯的记录。**
