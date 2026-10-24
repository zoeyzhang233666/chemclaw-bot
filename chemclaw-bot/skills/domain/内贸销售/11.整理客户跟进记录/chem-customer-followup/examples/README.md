# 示例

四个目录，每个都是一个可独立运行的完整案例：`input.json` 是数据，`.xlsx` / `.html` / `.md` 是生成结果。

| 目录 | 产品 | 阶段 / 停滞 | 演示重点 |
|---|---|---|---|
| `example-1-soda-ash-glass/` | 纯碱 → 浮法玻璃 | 报价谈判 / 5 天 | 价格差 70 元 + 账期核心卡点；**我方承诺逾期 5 天**；客户比价表被遮挡；手写底线价认不出 |
| `example-2-tio2-coatings/` | 钛白粉 → 涂料 | 合同 / 2 天 | 只剩质量罚则与账期起算点两条；履约记录全部按期；**年框量是我方口径不是客户承诺** |
| `example-3-methanol-stalled/` | 甲醇 → 甲醛（危化品） | 停滞 / 7 天 | 客户长约未到期（结构性）；危化品运输资质未闭环；**两条我方逾期**；催办≠推进 |
| `_skeleton/` | 占位 | 报价谈判 / 5 天 | 最小可运行样例，4 条时间线跑通全流程，复制它开始填 |

## 怎么用

**照着改**（最省事）：

```bash
cp -R example-1-soda-ash-glass my-case
rm my-case/*.xlsx my-case/*.html my-case/*.md
# 编辑 my-case/input.json：保留结构，替换内容，改 meta.slug
python ../scripts/build_followup.py my-case/input.json -o my-case --md
python ../scripts/selfcheck.py my-case/input.json --outdir my-case
```

**挑最接近的那个抄**：

- 报价没谈拢、我方还欠客户东西 → `example-1`
- 条款在磨、快签了 → `example-2`
- 客户没动静、要资质 → `example-3`
- 想从最小结构开始 → `_skeleton`

## 三个案例在结构上的差别

三个案例的 JSON **结构完全一致**（同一套 key），差别只在内容与状态取值：

| 差异点 | example-1 | example-2 | example-3 |
|---|---|---|---|
| `stage.current` | 报价谈判 | 合同 | 停滞 |
| 阶段 `state` | `current` | `current` | `stalled`（当前阶段即停滞） |
| `stall.days` | 5 | 2 | 7 |
| 逾期承诺 | 1 项 | 0 项 | 2 项 |
| 卡点分型 | 价格型 + 我方型 | 流程型 | 结构型 + 资质型 |
| 特殊字段 | 手写批注待辨认 | 建档资料（REACH） | 危化资质 / 罐容 |

所以换案例时**不需要改结构**，只需要改 `stage.current`、各阶段 `state`、以及内容本身。

## 三个案例的自检预期

跑 `selfcheck.py` 应全部 `[pass]`：

| 案例 | 时间线 | 停滞 | 逾期 |
|---|---|---|---|
| example-1 | 22 条 | 5 天 | 1 项 |
| example-2 | 15 条 | 2 天 | 0 项 |
| example-3 | 14 条 | 7 天 | 2 项 |
| _skeleton | 4 条 | 5 天 | 1 项 |

数字对不上，先怀疑数据（`as_of_date` 是不是今天、最后一条客户记录日期对不对），不要怀疑脚本。

## 注意

- 三个案例的客户、公司、价格**全部虚构**，仅用于演示结构与方法。
- `example-3` 里「停滞 7 天」与「业务实质停在 09-28（21 天）」两个数并存，是刻意的：客户 10-12 只来催资质，不构成业务推进。口径说明见 `../references/stages.md`。
