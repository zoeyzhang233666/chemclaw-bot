# 模板使用说明

本目录的两个文件由 `scripts/build_outputs.py` 从甲醇案例的**真实运行结果**生成，
既是"成品示例"，也是可直接改造的模板。

| 文件 | 说明 |
|---|---|
| `report_template_methanol_case.html` | 自包含交互式报告（无外链 CDN，离线可用）。数据以 JSON 内嵌在 `<script>const D = {...}` 中 |
| `workbook_template_methanol_case.xlsx` | 多表数据工作簿 |

## 改成别的品种

**不要手改 HTML 里的数字。** 正确流程是：

1. 准备 `inventory_weekly.csv`（列：`asof, pub_ts, value, url`）与 `prices_daily.csv`（列：`date, spot, fut[, basis]`）
2. 写一份 `config.json`（照抄 `examples/methanol-port-inventory/config.json`，改品种参数与阈值）
3. 写一份 `narrative.json`（照抄同目录示例，改标题、结论、产业解释）
4. 运行：

```bash
python scripts/pipeline.py --config <你的 config.json>
python -c "from scripts.build_outputs import build_report, build_workbook; \
           build_workbook('out', narr, 'out/workbook.xlsx'); \
           build_report('out', narr, 'out/report.html')"
```

`build_outputs.py` 会读取 pipeline 产出的 `res_*.csv` 与 `summary.json`，
自动填充所有表格、图表与 KPI；`narrative.json` 只提供**文字**部分（结论、产业解释、限制）。

## 报告结构（固定 8~10 节）

1 数据与口径 → 3 库存与价格总览 → 4 因子×未来表现（可筛选 + 热力图）
→ 5 分组分布（bootstrap CI）→ 6 分年度与样本内外 → 7 显著性与安慰剂 + 共线性
→ 8 市场结构差异 → 10 结论（成立的/不成立的/产业解释/限制）

若某品种缺某类结果（如无 placebo），对应小节会自动跳过，不会留空白版面。
