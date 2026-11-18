# 填空骨架

复制这个目录，把 `project.json` 里所有 `<尖括号>` 替换成真实数据，然后跑：

```bash
python scripts/build_all.py 你的目录
```

## 重要：骨架本身不能构建

`_skeleton/project.json` 里的数值全是 `0` 或 `null`，**直接构建会失败**——这是故意的：

- `validate.py` 会报 `PROJ_CAP`（设计产能必须 > 0）、`BASE_VALUE`（关键分母必须 > 0）等 error
- `build_all.py` 检测到 error 会**中止，不产出任何交付物**

这样避免"拿一堆 0 生成一份看起来正常的报告"这种最危险的情况。

## 最小可构建集

想先看到产物长什么样，先把这 7 个字段填上（其余可留空，会被渲染成缺口）：

| 字段 | 说明 |
|---|---|
| `project.design_capacity_t` | 设计产能，**吨** |
| `project.name` / `project.owner` | 项目与业主 |
| `project.startup_plan.year` / `.month` | 投产年月 |
| `meta.product` | 产品名（用于文件名） |
| `chain` + `unit_consumption` | 工艺链与单耗（原料需求测算的基础） |
| `capacity_bases` 至少 `national` 一项 | 否则所有占比都算不出来 |
| `scenarios` 至少一条 `kind: "基准"` | 否则 KPI 与情景表为空 |

## 字段取值规矩

- **一律存吨**（`design_capacity_t`、`value_t`、`capacity_t`、`demand_t` 都是吨/年），展示时脚本自动折成万吨。
- **查不到就填 `null` 或 `0`**，不要编造。填 `0` 的分母会被渲染为"分母缺失，无法计算"并自动进入缺口，不会让报告崩掉。
- **证据等级必填**（`evidence.level` ∈ E1–E5），无来源的填 `E5`。
- **单耗**：`range` 给 `[下限, 上限]`，`purity` 给纯度（0–1）。原料需求 = 产量 × Π(单耗 ÷ 纯度)。
- **`on_site`**：该原料是本项目自建（`true`）还是外购中间体（`false`）。外购的不产生对更上游的新增需求。

## 五个情景是必须的

`scenarios` 至少要有 `保守`、`基准`、`乐观`、`上限`、`延期` 五类。
其中 `上限`（`ramp_model: "none"`, `steady_lf: 1.0`, 1 月开车）**专门用来演示"把设计产能当首年产量会高估多少倍"**，报告里会自动算出这个倍数——这是本技能最重要的一句提醒。

## 参考完整范例

`examples/01-pp-pdh-40wt-sim/` 是一个填满的完整案例（40 万吨/年 PDH-PP，模拟项目，
但单耗与分母全部来自可查证的公开来源），可以直接对照它抄结构。
