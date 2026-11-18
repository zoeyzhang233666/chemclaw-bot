# chain-divergence-scan ｜ 扫描产业链异常背离

在**有真实产业关系**的化工品种对里，找"最近价格关系明显不对劲"的组合，
并把「产业关系 + 统计异常程度 + 基本面可解释性 + 数据可比性」四件事一起交代清楚。

---

## 三十秒上手

```bash
# 1) 自检（24 项已知答案，确认环境没问题）
python scripts/selftest.py

# 2) 直接跑内置的 15 品种 / 16 组关系
python scripts/run_scan.py --data data --out out --perm 1200

# 3) 历史回看（量化假阳性率，必须跑）
python scripts/run_hist.py --data data --out out --months 12

# 4) 出交付物
python scripts/build_excel.py --pack out/scan_pack.json --hist out/hist_scan.json --out 产业链异常背离扫描.xlsx
python scripts/build_html.py  --pack out/scan_pack.json --web out/series_web/web_series.json --hist out/hist_scan.json --out 看板.html
```

全程只需 Python 3.9+；统计内核零第三方依赖，只有 `build_excel.py` 需要 `openpyxl`。

---

## 目录结构

```
chain-divergence-scan/
├── SKILL.md                     # Skill 主文件（触发条件、流程、红线）
├── README.md                    # 本文件
├── scripts/
│   ├── stats_core.py            # 统计内核（纯标准库）
│   ├── chain_graph.py           # 品种池 + 16 组产业关系登记表  ← 换品种改这里
│   ├── sources.py               # 32 条来源（数据/关系/事件）    ← 加来源改这里
│   ├── fundamentals.py          # 事件库 + 双方基本面五问模板
│   ├── run_scan.py              # 主扫描
│   ├── run_hist.py              # 历史回看（假阳性率）
│   ├── build_excel.py           # 16 表工作簿
│   ├── build_html.py            # 交互看板
│   ├── fetch_futures.py         # 新浪财经日线抓取
│   ├── selftest.py              # 24 项断言
│   └── probe_html.py            # 无头浏览器自检（可选）
├── references/
│   ├── 01-产业关系类型与配对规则.md
│   ├── 02-统计指标与阈值.md
│   ├── 03-多重检验与伪异常检查清单.md
│   ├── 04-数据源与可比性清单.md
│   └── 05-报告写作模板.md
├── assets/templates/            # 模板文件
├── data/                        # 15 个品种的真实日线（截至 2026-10-20）
├── examples/pp-lldpe-px-pta/    # 完整跑通的案例（含交付物与结论）
└── 工作区/说明.txt
```

---

## 内置品种池（15 个）

**炼化/芳烃**：PX（对二甲苯）、TA（PTA）
**烯烃**：PP（聚丙烯）、L（LLDPE）、V（PVC）、EB（苯乙烯）、EG（乙二醇）
**煤化工**：MA（甲醇）、UR（尿素）、SA（纯碱）
**黑色**：JM（焦煤）、J（焦炭）、RB（螺纹钢）
**油品**：BU（沥青）、FU（燃料油）

## 内置产业关系（16 组）

| 类型 | 组合 | 强度 |
|---|---|---|
| 上下游 | PX/TA、MA/PP、JM/J、J/RB | strong / medium / strong / strong |
| 共用原料 | TA/EG、SA/UR、MA/UR | strong / medium / weak |
| 替代 | PP/L、PP/V、L/V、BU/FU | medium / medium / weak / weak |
| 成本共振 | MA/EG、MA/L、PX/EG、EB/MA、JM/RB | 全部 weak |

进主榜单（strong+medium）：9 组；仅背景（weak）：7 组。

---

## 换成自己的品种 / 关系

### 加一个品种

1. 把日线放到 `data/{代码}.csv`：

```csv
date,open,high,low,close,volume,open_interest,settle
2026-10-20,9350,9400,9300,9376,123456,234567,9360
```

2. 在 `scripts/chain_graph.py` 的 `UNIVERSE` 里登记代码、名称、分类、产业链、合约乘数、口径。

### 加一组产业关系

在 `RELATIONS` 里加一条（十二个字段都要填，见 `references/01` 第 6 节）：
`a, b, rtype, strength, direction, a_role, b_role, mechanism, k, coef_kind,
market_convention, source_ids, comparability`

**别忘了给 `source_ids` 里的每个编号在 `sources.py` 补上标题+URL+日期+用途。**

### 换数据源

只要 CSV 有 `date` 和 `close` 两列就能跑。若改用现货序列，记得在报告里改口径说明。

---

## 参数（先定后跑，不许事后调）

| 参数 | 默认 | 含义 |
|---|---|---|
| `--window` | 60 | 滚动相关与滚动 z 的窗口（交易日） |
| `--z` | 2.0 | 价差偏离阈值 \|z\| |
| `--persist` | 5 | 连续超阈值天数 |
| `--drop` | 0.45 | 相关性脱钩阈值 |
| `--perm` | 1200 | 置换检验次数（0 = 关闭） |

四门槛**必须同时满足**才算"异常背离（候选）"。

---

## 常见问题

**Q：为什么扫描结果里一个"异常"都没有？**
A：那说明本期数据里确实没有异常。这是可接受的正常结果，**不要为了出结论去调阈值**。
先看历史回看命中率：如果历史上也从不报警，说明阈值或数据有问题；
如果历史上会报警而今天不报，说明"没有异常"这个结论是稳健的。

**Q：某个组合 z 很高但被判"偏离但未达门槛"？**
A：看它连续超阈值几天。单日跳空（换月、事故、政策）会产生 z=3~5 但只持续 1 天，
持续性门槛就是为了过滤这种。

**Q：PX 的历史分位能信吗？**
A：只能有限相信。PX 2023-09 才上市，745 个交易日只覆盖一个制度区间。
报告里必须注明。

**Q：为什么 BU/FU 明明通过了部分门槛却被排除？**
A：三个独立理由：关系强度 weak（无产业锚）、三段滚动相关均值极差 0.52（关系本身在换制度）、
BU 在 2026-10-14 有未查明的跳空。任一理由都足以排除。

**Q：能不能加库存、开工率这些基本面序列？**
A：可以，但需要你自己提供 CSV。本工具不内置付费数据，也**不会估算**——
拿不到就写"未取得"。

---

## 案例

`examples/pp-lldpe-px-pta/` 是完整跑通的真实案例（数据真实，截至 2026-10-20）：

- **PP-LLDPE**：z = −1.42（分位 19.7%），0 日超阈值，滚动相关 0.95（分位 95.9%）→ 偏离但未达门槛
- **PX-PTA**：z = −0.36（分位 36.8%），0 日超阈值，滚动相关 0.956（分位 47.5%）→ 偏离但未达门槛
- **结论**：16 组关系中**没有一个**同时满足四门槛

详见该目录的 `案例研究.md`。

---

## 合规

本工具输出的是**统计描述与产业逻辑说明**，不含方向判断、不含仓位建议、不构成投资建议或交易建议。
统计相关不等于因果；历史偏离不等于未来回归；期货价格不等于现货成交价。
