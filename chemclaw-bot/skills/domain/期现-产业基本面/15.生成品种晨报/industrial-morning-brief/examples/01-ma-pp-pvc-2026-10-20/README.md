# 案例：甲醇 / PP / PVC 产业研究晨报（2026-10-20）

这是用**真实数据**跑出来的一份完整晨报，可以当模板复制了改。

## 这一天发生了什么（案例要验证的判断点）

2026-10-20（周二），三个品种走出了完全不同的方向，正好用来检验「变化检测是否真的能分辨差异」：

| 品种 | 主力收盘（10-19 vs 10-16） | 本期核心变化 |
|---|---|---|
| 甲醇 | 3,366 → 3,143（**-6.63%**） | 沿海 MTO 全线停车，需求端塌陷；基差被动走扩 +204 元至 822 元 |
| PP | 9,343 → 9,320（-0.25%） | 几乎没有变化；近端检修多但节后累库，缺乏方向 |
| PVC | 4,858 → 4,904（**+0.95%**） | 开工降至 61.50%（环比 -2.99pct）创新低 + 电石成本上移，逆势上涨 |

甲醇与 PP 在同一个地缘事件（霍尔木兹海峡受阻、原油高企）下走出相反结果，说明「成本抬升」与「需求崩塌」在不同品种上的权重不同——这正是晨报需要讲清楚的事。

## 这份案例特意保留了哪些「坏数据」

为了让判定逻辑可被检验，`raw/events_raw.json` 里**故意混入了**真实工作中会遇到的干扰项：

- **重复转载**：E01 与 E02 都是霍尔木兹海峡袭击事件，来自两个不同媒体、标题完全不同；
- **旧闻混入**：E04（10-10 国能榆林停车）、E13（10-08 检修损失）、E15（产能投放计划）；
- **无信息量泛评**：E08、E09、E18 全是「机构称短期震荡偏弱」这类没有数字也没有路径的表述。

`excluded` 里还记了两条**跨年度误采**的真实教训：搜索结果里藏着 2025-10-20 的同名稿件（价格 2,275 元/吨），如果直接采信就会把去年数据当今天用。

## 跑出来的结果

```
指标 24 条（有基线 22 / 新增 2）；A 级 6 / B 级 11 / C 级 7
事件 18 条（A 11 / B 4 / C 3），自动合并转载 2 条，识别旧闻 4 条
数据缺口 9 项（全部写明缺什么、为什么、怎么补）
被排除资讯 6 条（含 2 条跨年度误采）
```

其中 4 条指标标了「未更新」（库存、开工、MTO、PVC 开工，数据日期 10-15 / 10-18），正文里都没有被称为「当天变化」。

## 文件说明

| 文件 | 作用 |
|---|---|
| `research.json` | 本期研究配置（人工填写）。这是唯一的「判断」入口 |
| `research_full.json` | 把去重后的事件合入后的完整配置，`assemble.py` 的输入 |
| `baseline_2026-10-16.json` | 上一期基线，用于验证「上期→本期」的变化检测链路 |
| `raw/*.json` | 抓下来的原始行情序列（34 个序列，2025-01-02 起，430+ 个交易日） |
| `raw/events_raw.json` | 20 条**未经去重**的原始事件（含各类干扰项） |
| `raw/events.json` | 去重与分级后的结果 |
| `build/data.json` | 组装后的完整数据，HTML 与 Excel 的共同数据源 |
| `output/*.html` | 交付用的互动晨报 |
| `output/*.xlsx` | 交付用的 Excel 底稿 |

## 复现步骤

```bash
cd examples/01-ma-pp-pvc-2026-10-20

# 事件去重 + 重要性分级
python ../../scripts/dedupe.py raw/events_raw.json --out raw/events.json \
       --report-date 2026-10-20 --baseline-date 2026-10-16

# 把事件合入配置
python -c "
import json
cfg = json.load(open('research.json', encoding='utf-8'))
cfg['events'] = json.load(open('raw/events.json', encoding='utf-8'))
json.dump(cfg, open('research_full.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
"

# 变化检测与组装
python ../../scripts/assemble.py research_full.json --out build/data.json \
       --baseline baseline_2026-10-16.json

# 渲染
python ../../scripts/build_html.py build/data.json \
       --out output/甲醇-PP-PVC_产业研究晨报_2026-10-20.html
python ../../scripts/build_xlsx.py build/data.json \
       --out output/甲醇-PP-PVC_产业研究晨报_2026-10-20.xlsx

# 校验
python ../../scripts/check_html.py \
       output/甲醇-PP-PVC_产业研究晨报_2026-10-20.html build/data.json
python ../../scripts/check_xlsx.py \
       output/甲醇-PP-PVC_产业研究晨报_2026-10-20.xlsx build/data.json
```

## 当模板用

下一期这样做：

1. 复制整个目录改名，例如 `02-ma-pp-pvc-2026-10-21`；
2. `research.json` 里改 `report_date`、`prev_baseline_date`，把每条指标的 `base` 改成本期 `current` 的值；
3. 把本期的 `build/data.json` 复制成下一期的 `baseline_2026-10-20.json`，用 `--baseline` 指过去；
4. 重跑上面的命令。

**不要改 `id`**——它是跨期关联的唯一键，改了等于宣告这是新指标，上一期数据不再继承。

## 数据来源与验证

所有数字都标注了来源与日期。关键交叉核对：

- 期货收盘：东方财富行情 vs 生意社 10-19 结算表（MA2701 结算 3,143，收盘 3,143，一致）；
- 甲醇各月份合约：与 100ppi 结算表逐月核对（2701 3,143 / 2702 3,100 / 2703 3,050 / 2705 2,960…）；
- 现货：同花顺 iFinD 逐区域报价，与生意社基准价方向、量级吻合。

数据仅用于演示方法论，不构成任何投资建议。
