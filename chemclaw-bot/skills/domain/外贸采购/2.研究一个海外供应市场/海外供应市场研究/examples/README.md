# Examples 使用说明

本目录是"**跑通的实例**"，不是示例占位。每个子目录都是一次完整的海外供应市场研究，可直接作为下一次研究的骨架。

---

## 目录

| 目录 | 国家 | 产品 | 说明 |
|---|---|---|---|
| `saudi-meg/` | 沙特阿拉伯 | 乙二醇 MEG（HS 2905.31） | 完整实例：12 套装置、5 年贸易、6 家生产法人、双通道物流、16 个供应事件 |

每个实例包含：

```
<实例>/
  data.json     # 全部结构化数据（报告与 Excel 都由它生成）
  README.md     # 结论 + 研究过程 + 复现步骤 + 可迁移经验
```

---

## 如何用模板新建另一个国家/产品（15 分钟起步）

### 1. 复制骨架

```bash
cp -r examples/saudi-meg examples/<国家>-<产品>
```

### 2. 替换 `data.json` 的五个核心块

| 块 | 要改什么 | 最容易漏的 |
|---|---|---|
| `meta` | 国家、产品、HS、基准日 | `as_of_note`（重大时点） |
| `sites` | 工业城名、经纬度、`coast` | `coast` 决定东西海岸/通道分析 |
| `companies` | 生产法人、股权、主体类型 | 集团 ≠ 生产法人 |
| `plants` | 逐套装置 + 产能口径 + 证据等级 | `cap_basis` 必须写清数字来源 |
| `trade` | 逐年出口 + 目的地 | 税号覆盖范围写进 `hs_note` |

其余块（feedstock / logistics / policy / events / risks / unverified / next_steps）按实际填充，宁可"少而准"。

### 3. 工艺适配

先读 `references/03_工艺适配矩阵.md`，确认你这款产品的"必查字段"（例如精细化工要查反应釜，钾肥要查折纯口径）。

### 4. 生成与自检

```bash
python scripts/build_html.py  examples/<新实例>/data.json assets/report_template.html out/报告.html
python scripts/build_excel.py examples/<新实例>/data.json out/工作簿.xlsx
node   scripts/verify_report.mjs out/报告.html
```

### 5. 过质量门槛

逐项核对 `references/08_质量检查清单.md`，特别是 A 组（口径）与 B 组（企业与装置）。

---

## 常见改造点

| 情况 | 需要改的地方 |
|---|---|
| 没有"东西海岸"之分 | `sites.coast` 全部写同一值即可，HTML 会自动归为单通道 |
| 产品不是液体散装 | 改 `logistics.vessel` 与船型描述；HTML 物流区块文字通用 |
| 企业数很多（>10） | 可在 `companies` 中只保留主要主体，其余在 `unverified` 说明 |
| 没有官方年报 | 全部降级为 B/C，并在 `data_grades` 中说明 |
| 目标是"是否值得进口"而非深度报告 | 仍建议跑完整流程，结论自然浮现；不要跳过装置核实 |

---

## 注意

- **不要**把 `saudi-meg/data.json` 里的数字直接沿用到别的国家——它只是**结构和写法**的参照。
- **不要**为了让图表"好看"而补充估算值；缺口表比假数据更有价值。
