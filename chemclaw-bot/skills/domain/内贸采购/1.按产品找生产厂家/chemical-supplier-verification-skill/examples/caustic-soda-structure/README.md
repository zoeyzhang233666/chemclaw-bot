# 示例二：32% 液碱（结构示例，匿名占位）

## 这是什么

一个**只演示结构**的最小示例：告诉你在换成“液体产品、危化品、短运输半径”时，`project.json` 要改什么。

> ⚠️ 本示例的公司名、产能、地址、证据全部是**匿名占位**，不是真实企业数据。
> 禁止用于采购、报价、供应商准入或对外报告。

## 它演示的 6 个差异

| 方面 | 纯碱示例 | 本示例（32% 液碱） |
|---|---|---|
| 产品形态 | 固体、吨袋 | 液体、槽车/ISO 罐 |
| 关键规格 | 总碱量、水分、Fe₂O₃、堆积密度、粒度 | NaOH 浓度、Na₂CO₃、NaCl、Fe₂O₃、SiO₂、色度 |
| 规模阈值 | 万吨/年，600+ 为大 | 仍用万吨/年，但 60–120 已算区域主力 |
| 距离权重 | 15% | 25%（危化品运输半径短） |
| 合规 gate | 环评/排污许可 | 安全生产许可、危化品登记、危化品运输资质 |
| 贸易商 | 大宗商品贸易商多 | 代理/经销商更多，必须有授权链 |

## 文件

```text
project.json                                  4 家匿名占位企业
output/烧碱生产厂家核验池_结构示例_202610.xlsx
output/烧碱生产厂家核验池_结构示例_202610.html
```

## 复现

```bash
python scripts/validate_project.py examples/caustic-soda-structure/project.json
python scripts/run_all.py examples/caustic-soda-structure/project.json --outdir examples/caustic-soda-structure/output
```

运行时会看到一条警告：

```text
[WARN] 样本仅 4 家；建议 15–30 家，或明确写“样本有限”
```

这是预期的：结构示例只用 4 家讲清楚字段与流程。

## 关键字段对照

### `specs`

```json
{"id": "naoh", "label": "NaOH 浓度", "requirement": "≥ 32.0%", "unit": "%", "method": "滴定/密度换算", "critical": true}
```

换成液体产品后，`unit` 可能是 `%`、`ppm`、`Hazen`、`g/cm³`、`mm`；`method` 要写检测方法，便于 RFQ 追问。

### `scoring.weights`

```json
{"certainty": 0.30, "spec": 0.25, "scale": 0.20, "distance": 0.25}
```

距离从 15% 提到 25%：液碱用槽车/ISO 罐，运输半径直接影响到厂成本。

### `scoring.tiers`

```json
[{"min": 84, "label": "优先谈判"}, {"min": 78, "label": "重点备选"}, {"min": 0, "label": "观察/成本备选"}]
```

分级阈值可按项目调整，但要在 `references/04-scoring.md` 里写清理由。

### `meta.theme`

```json
{"accent": "#1d4ed8", "accent_2": "#60a5fa", "accent_soft": "#e8f0fe", "ink": "#0b1726"}
```

HTML 的强调色由 `meta.theme` 控制；不写就用默认的青色。

## 用它练手

1. 把 4 家占位企业换成 2 家真实企业（只填能公开验证的部分）；
2. 把 `sources` 换成真实链接；
3. 把 `gaps` 里的“真实数据未核”删掉，换成真实缺口；
4. 跑 `validate_project.py`，看是否还报错；
5. 跑 `run_all.py`，打开 HTML 检查抽屉与对比。

这样做一遍，就知道换产品时需要改哪些字段、哪些不能改。
