---
name: research-hypothesis-test
description: >
  Use when a user brings a self-authored research hypothesis about 期现价差/基差/库存/开工率与价格的关系
  and wants it rigorously tested against history — 验证我的假设 / 这个规律历史上成立吗 / 帮我检验一下 /
  库存下降是不是基差会走强 / 这个信号有没有用 / 定个研究方案再跑数据. Turns the natural-language
  hypothesis into an explicitly confirmed, frozen research design (品种/口径/频率/样本期/信号/观察窗口/
  对照组), audits whether data actually suffices, then runs the registered statistical battery
  (Welch t, Wilson CI, direction rate, Mann-Whitney, block permutation, placebo, OLS+HAC, BH-FDR,
  non-overlap & monthly robustness, event study) and concludes only 支持 / 证据不足 / 与历史相反.
  Delivers a self-contained interactive HTML research page plus a 15-sheet Excel workbook in which
  every number is traceable to a source URL, every test is registered (no cherry-picking), and
  simulated data is hard-labelled SIMULATED and never used as a conclusion.
---

# 检验一个自定义研究假设（期现价差与量化）

## 这个 Skill 解决什么

用户带着一句**自己的判断**来：「甲醇港口库存连续两周下降时，随后两周基差更容易走强」。
这句话不是一个可以直接跑的检验，而是藏着 8–10 个未决定的口径。Skill 的职责是：

1. **先把它变成可执行、可复现的研究设计**，并把所有需要人拍板的开关摆到桌面上；
2. **先查数据够不够**，不够就直说不够，绝不用模拟数字或放宽标准凑出结论；
3. **在参数冻结之后**才跑统计，跑全部登记的检验（不是挑好看的），
   如实给出样本量、置信区间、分年与分阶段稳定性；
4. 结论只允许三种：**历史数据支持 / 证据不足 / 与历史相反**。

## 铁律（任何情况下不破）

| # | 铁律 | 落地方式 |
|---|---|---|
| 1 | 不为证明用户假设而调参数 | 设计文件 `approved_at` 冻结；改参数即新版本，旧版本留档 |
| 2 | 模糊变量不悄悄具体化 | 解析器给出候选 + 「需确认」标记；阻断性问题必须回答 |
| 3 | 先审数据再跑统计 | `run_hypothesis_test.py audit` 与 `run` 是两条独立命令 |
| 4 | 样本不足就说不足 | 预登记最小样本规则（信号≥12、对照≥10），触发即不报显著性 |
| 5 | 模拟数据只能验证流程 | 每行 `data_status=SIMULATED`，页面/工作簿整表紫色标记，结论栏禁止引用 |
| 6 | 全量登记，不挑汇报 | 每个检验带编号/族/N/效应量/CI/p/BH-q，不显著的照样列出 |
| 7 | 每个数字可回溯 | 数据行带 URL + `verified_at`；锚点（如 100ppi 原文价格）写进证据锁 |

## 工作流（9 步）

```
① 解析假设        hypothesis_parser.py     自然语言 → 变量/方向/窗口/候选口径 + 问题清单
② 设计固化        run_hypothesis_test.py design   生成 research_design.json（approved=false）
③ 数据可用性      run_hypothesis_test.py audit    覆盖度、缺口、最小样本规则 → data_audit.json
④ 拿真数据        抓取/回源核验（见 references/04-数据源与口径.md）
⑤ 参数确认        人确认 → approve_design.py     写入 approved_at + 数据指纹
⑥ 正式检验        study_engine.py            results.json + samples.csv（逐条样本）
⑦ 稳定性与修订    amendment_sensitivity.py + event_study.py
⑧ 模拟演示（可选）make_demo_simulation.py + study_engine.py --status SIMULATED
⑨ 交付            build_html.py + build_excel.py + check_html.py
```

**第 ⑤ 步是闸门**：`study_engine.py` 不接受未确认的设计（脚本层面不检查，但流程与文档要求先确认；
`run_hypothesis_test.py run` 会直接 `SystemExit`）。

## 三个模块

| 模块 | 什么时候用 | 主脚本 |
|---|---|---|
| **条件检验** | 「A 出现后，B 是否更容易变强/变弱」 | `study_engine.py` |
| **相关性** | 「A 和 B 有没有关系」——需要两指标联合分析时转用兄弟 Skill 12 | — |
| **因果** | 「A 是否导致 B」——观测数据做不到，只能写「条件相关」 | 见 references/02 |

## 快速开始

```bash
# 0) 统计学自检（20 项，对照 scipy 参考值；必须先通过）
python scripts/selftest_stats.py

# 1) 解析假设
python scripts/hypothesis_parser.py \
  --text "甲醇港口库存连续两周下降时，随后两周基差更容易走强" \
  --template methanol_port_inventory-basis --out build/design_draft.json

# 2) 生成设计（approved=false）
python scripts/run_hypothesis_test.py design \
  --text-file hypothesis.txt --template methanol_port_inventory-basis \
  --out build/research_design.json

# 3) 审计数据
python scripts/run_hypothesis_test.py audit --design build/research_design.json

# 4) 人确认后冻结
python scripts/approve_design.py --design build/research_design.json \
  --by "张三" --note "Q4–Q7 按默认口径" \
  --data data/port_inventory_weekly.csv data/100ppi_sf.csv

# 5) 正式检验
python scripts/study_engine.py --design build/research_design.json \
  --inventory data/port_inventory_weekly.csv --price data/100ppi_sf.csv \
  --minute data/futures/MA0_60min.csv \
  --out build/results_real.json --samples build/samples_real.csv --status REAL

# 6) 稳定性、修订口径、事件研究
python scripts/amendment_sensitivity.py
python scripts/event_study.py --inventory data/port_inventory_weekly.csv \
  --price data/100ppi_sf.csv --out build/event_study.json

# 7) 模拟演示（明确标记）
python scripts/make_demo_simulation.py --weeks 208 --seed 20261020
python scripts/study_engine.py --design build/research_design.json \
  --inventory data/demo_weekly.csv --price data/demo_weekly.csv \
  --out build/results_demo.json --samples build/samples_demo.csv --status SIMULATED

# 8) 交付
python scripts/build_excel.py . out/研究假设检验.xlsx
python scripts/build_html.py --root . --out out/研究页.html
python scripts/check_html.py out/研究页.html
```

## 用户自带数据

```bash
python scripts/map_user_data.py --file 我的库存和基差.xlsx --out build/user_mapping.json
```

输出每个字段的识别置信度、单位猜测、频率推测，以及**必须人工确认的问题清单**。
低置信度（<0.8）的列与单位不明的列，在确认前不得进入正式检验。

## 目录

```
SKILL.md                         本文件
README.md                        给接手人看的说明（含样例结论）
references/01-方法论与检验清单.md   假设→设计的映射规则、检验选择依据
references/02-统计方法公式.md      每个检验的公式、适用条件、边界
references/03-前视函数与偏差清单.md  未来函数/幸存者/重叠/多重检验/选择效应
references/04-数据源与口径.md       可核查数据源、URL 规则、锚点校验、口径陷阱
references/05-报告写作模板.md       结论怎么措辞（支持/不足/相反）与交付清单
references/06-自然语言假设解析规则.md 词表、规则、必须反问的清单
references/07-字段识别与用户数据映射.md 上传 Excel 的处理流程
examples/                        三个完整案例（甲醇/纯碱/尿素）
assets/templates/                HTML 与 Excel 生成脚本模板
scripts/                         全部可运行脚本 + 自检
sources/                         本次研究的数据清单与核验记录
```

## 输出物

* **HTML 研究页**（单文件，离线可开）：设计 → 参数确认 → 数据可用性 → 样本 → 统计 →
  稳定性 → 修订口径 → 事件研究 → 模拟演示 → 局限 → 复现。
* **Excel 工作簿**（15 个 sheet）：封面结论、设计、参数确认、数据来源、原始数据×2、
  因子定义、样本面板、统计结果、稳定性、修订口径、事件研究、模拟演示、局限、复现。
* **results.json / samples.csv**：机器可读，便于复核与再分析。
