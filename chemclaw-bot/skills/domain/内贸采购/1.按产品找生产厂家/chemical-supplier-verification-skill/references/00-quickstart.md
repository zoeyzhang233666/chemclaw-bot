# 快速上手：从一条需求到两份附件

本页给 agent 和人都能用。目标：30 分钟内产出一份“能拿去做采购初筛”的 Excel + HTML。

## 0. 环境

```bash
python --version      # 3.10+
pip install -r requirements.txt
```

只有 Excel 生成需要 `openpyxl`；HTML 只用标准库。

## 1. 确认输入

至少四项：

- 产品（含等级/形态）；
- 下游用途；
- 数量（月需/年需）；
- 收货地（城市/园区）。

缺什么就先用**明确标注的示例 RFQ** 跑通，把缺口写进 `gaps`。

## 2. 建样本

按 `references/01-research-protocol.md` 检索，目标 15–30 家生产厂家。

每家先回答：

- 有没有生产地址？
- 有没有装置/产能/产量/环评/政府项目之一？
- 有没有至少一条 A 或 B 级证据？

三个“有”才算生产厂家候选；只有经营范围或店铺 SKU 的，进 `traders`。

## 3. 填 `project.json`

从 `templates/project.example.json` 复制，或直接改 `examples/soda-ash/project.json`。

最小可跑字段：

```json
{
  "meta": {"title": "...", "brand": "...", "product": "...", "product_short": "...",
           "application": "...", "destination": "...", "destination_short": "...",
           "as_of": "2026-10-19", "capacity_unit": "万吨/年", "quantity_unit": "吨",
           "sample_note": "..."},
  "rfq": {"title": "...", "product": "...", "qty_month": 2000, "qty_year": 24000, "destination": "..."},
  "specs": [{"id": "s1", "label": "主含量", "requirement": "≥ 99.4%"}],
  "sources": [{"id": "S01", "org": "...", "title": "...", "date": "2026-04-30", "grade": "A", "url": "...", "used": "..."}],
  "companies": [{"id": "co1", "name": "...", "full_name": "...", "identity": "producer",
                 "capacity": 100, "capacity_year": "2025A",
                 "certainty": 95, "spec_score": 80, "availability": 85,
                 "plants": [...], "evidence": [...], "spec_rows": [...], "action": "..."}],
  "traders": [...], "conflicts": [...], "gaps": [...], "actions": [...],
  "scoring": {"weights": {"certainty": 0.35, "spec": 0.30, "scale": 0.20, "distance": 0.15},
              "tiers": [{"min": 84, "label": "优先谈判"}, {"min": 78, "label": "重点备选"}, {"min": 0, "label": "观察/成本备选"}]}
}
```

字段细节见 `references/03-data-model.md`。

## 4. 校验

```bash
python scripts/validate_project.py my-project.json
```

常见报错：

| 报错 | 原因 | 修法 |
|---|---|---|
| `只有 C/D 级证据，不能作为生产厂家` | 没有 A/B 级证据 | 补来源，或移到 `traders` |
| `spec_rows 缺少指标` | 规格没覆盖全 | 每个公司补齐所有 `specs.id` |
| `未知来源 S99` | `source_id` 不在 `sources` | 补来源或改 ID |
| `scoring.weights 合计为 0.950` | 权重不等于 1 | 调整权重 |
| `rank 重复` | 排名冲突 | 重排 |

## 5. 生成

```bash
python scripts/run_all.py my-project.json --outdir output
```

输出：

```text
output/{产品}_生产厂家核验池_{收货地}_{YYYYMM}.xlsx
output/{产品}_生产厂家核验池_{收货地}_{YYYYMM}.html
```

也可以分开跑：

```bash
python scripts/build_excel.py my-project.json --out output/report.xlsx
python scripts/build_html.py  my-project.json --out output/report.html
```

## 6. 打开检查

- 打开 Excel：看 `00_封面` 的 KPI 与 RFQ 是否正确；
- 打开 HTML：点第一行，切四个页签；勾 2 家做对比；
- 检查 `01_候选供应商池` 的排名与 `05_评分与排序` 是否一致；
- 检查 `06_贸易商与排除名单` 没有混入厂家；
- 按 `references/07-qa-checklist.md` 过一遍。

## 7. 交付

用 `SKILL.md` 末尾的“交付话术模板”，写清：

- 样本数与覆盖；
- 优先/备选；
- 不含报价/账期/运费；
- 无批次 COA 不写符合；
- 下一步动作。

## 常见问题

**Q：能不能不写 `scale_score` / `distance_score`？**
A：可以，但建议写；不写时综合分不会按权重计算，HTML 的对比表会缺规模/距离维度。

**Q：能不能只生成 HTML？**
A：可以，但标准交付是 Excel + HTML 两份。

**Q：能不能用旧版 `project.json`（字段名不同）？**
A：不能。字段名固定；旧数据请按 `references/03-data-model.md` 映射后再跑校验。

**Q：生成的中文文件名乱码？**
A：这是终端编码问题，文件本身是 UTF-8 名称；在 Windows 下用资源管理器/Excel 打开即可。

**Q：HTML 能在手机看吗？**
A：可以，表格自身横向滚动，页面本身不溢出；抽屉在窄屏占满宽度。
