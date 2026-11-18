# 示例 02：空白模板（换品种照这个填）

用来跑通流程的最小骨架：占位数值 + 完整字段。**里面所有数字都是占位示例**，
填表时必须替换；替换后请把 `meta.data_nature` 与 `quote.test_badge` 改成实际说明。

## 文件

```
02-template-blank/
├── research.json              ← 按 references/data-contract.md 填
├── specs/template.json        ← 品种规格骨架（真实项目请放到 skill 的 specs/ 下并改名）
└── （output/ 由 build_report.py 生成）
```

## 三步换品种

1. **建规格文件**：复制 `specs/_template.json` → `specs/<品种代码>.json`，
   按 `references/product-family-specs.md` 填 `spec_terms`、`regions`、`annual_anchors`、`events`。
   乙二醇的 `specs/meg.json` 只能当例子看，**不要把它的术语/地区/锚点抄到别的品种**。
2. **填 research.json**：`meta.spec_file` 指向新规格文件；`market.spot_anchors` 至少一条真实市场价；
   `benchmark.primary_anchor_id` 必须等于其中一条的 `id`（脚本会校验并给出可用 ID 列表）。
3. **生成**：

```bash
python scripts/build_report.py examples/02-template-blank/research.json --out out/
```

## 只拿到部分数据时，这条也能跑

| 缺什么 | 填法 | 报告表现 |
|---|---|---|
| 没有历史序列 | `series_files` 留空 `{}` | 分位图表显示"数据缺口"，不画假曲线 |
| 没有逐日现货快照 | `spot_series_3m: []` | 短线图显示缺口说明 |
| 没有年度锚点 | 规格文件 `annual_anchors: []` | 锚点图显示缺口说明 |
| 没有运价 | `interval_by_target."included|delivered"` 留 null | 到厂靶心显示"报价靶心缺失"，不出偏离 |
| 规格不一致 | `comparability` 里该项 `label: "不可比"` | 首屏出现橙色口径不匹配横幅 |

**任何一种缺失都不许用估算值补齐**——报告宁可显示缺口。
