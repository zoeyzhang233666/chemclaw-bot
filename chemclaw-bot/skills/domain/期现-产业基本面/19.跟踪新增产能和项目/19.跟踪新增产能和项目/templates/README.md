# templates · 空白模板

四个 JSON 数据文件 + 一个地理数据文件。**把 `_说明`、`_关键设计` 等下划线开头的键连同示例数据整体替换成真实内容。**

## 文件说明

| 文件 | 内容 | 你必须填的 |
|---|---|---|
| `projects.json` | 项目库（含 `baseline` 与 `excluded`） | 每个项目的身份、规模、性质、阶段、判断字段 |
| `progress.json` | 进展事实日志（只追加） | 每条有日期、有来源、有等级的事实 |
| `sources.json` | 来源登记簿 | 每个被引用来源的标题、发布者、URL、日期、等级 |
| `config.json` | 产品参数与口径配置 | 产能基数、路线结构、区域结构、爬坡区间 |
| `geo_cn.json` | 中国省级边界（SVG path） | **通常不用改**，已随模板分发。换其他国家/地区时需重新生成 |

## 最小可用数据集

想快速跑通，最少需要：

- `projects.json`：1 个项目 + 1 个 unit
- `progress.json`：2 条记录（1 条进展 + 1 条带 `plan_change` 的）
- `sources.json`：2 个来源
- `config.json`：填上 `product` / `as_of` / `baseline_capacity_wan`

## 填之前先读这三篇

1. **`references/02-字段口径.md`** —— 每个字段怎么填、边界怎么划。字段填错，后面所有汇总都错
2. **`references/07-去重与更新规则.md`** —— 九条去重规则。这是新产能研究里 80% 量级错误的来源
3. **`references/03-进展阶段与证据.md`** —— 阶段判定、证据分级、负结果记录法

## 填完的自检

```bash
python scripts/ppctl.py validate <项目目录>
```

校验会拦下这些问题：

- `project_id` 重复
- 引用了不存在的来源
- 进展记录没有 `source_ids`
- 自评等级高于来源最高等级
- 时间格式无法解析
- 只有"拟建"阶段记录（说明没有真实进展）
- 阶段倒挂（投产之后又出现环评受理）

**警告（不阻断）**：时间无法解析、同一 URL 被登记为多个来源、项目只有批文阶段记录。

## 目录结构

`ppctl.py init` 生成的骨架：

```
<项目目录>/
  data/
    projects.json      # 你要填
    progress.json      # 你要填
    sources.json       # 你要填
    config.json        # 你要填
    geo_cn.json        # 从 templates/ 复制
    derived/           # 自动生成，不要手改
      units.csv
      projects.csv
      progress.csv
      plan_history.csv
      summary_yearly.csv
      summary_region.csv
      deferred.csv
  out/                 # 自动生成的交付物
    <产品>新增产能与项目跟踪看板.html
    <产品>新增产能与项目跟踪台账_YYYYMMDD.xlsx
  snapshots/           # 每次 build 的数据快照，用于回溯
```

**`derived/` 里的一切都是生成物，不要手改。** 改数据源，重跑 `ppctl.py build`。
