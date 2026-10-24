# QA 清单

## 1. 构建前（数据）

```bash
python scripts/validate.py <data.json>
```

必须通过（exit 0）。重点看：

- [ ] `meta.product/product_short/unit/asof/buyer_site/spec` 齐全；
- [ ] `meta.processes` 非空，候选 `process` 都在其中；
- [ ] `baseline` 有 name/short/process/capacity/distance/freight_low/high；
- [ ] 候选 5–15 家（校验允许 2–20，少于 5 会警告）；
- [ ] 每家候选 `qualified` 是布尔值，`risk_level` 在 `低/中/中高/高`，`risk_score` 1–5；
- [ ] 每家候选 `evidence` 至少 1 条，且 ID 存在于 `sources`；
- [ ] `spec_items` 9–15 项，`id` 唯一；
- [ ] `spec_status` 每家 × 每项都有值，且只能是 `COA/试样/审核`；
- [ ] `same_source` 的 `entities`/`relation`/`implication`/`flag` 完整；
- [ ] `risks` 每条有 company/type/fact/impact/status；`source_id` 存在；
- [ ] `actions` 有 phase/action/detail/owner/output；
- [ ] `sources` 的 id/name/url/grade 完整，A/B/C 合法；
- [ ] 警告逐条读：少于 5 家、同组多选、来源无 URL、风险少于 3 条等。

## 2. 构建

```bash
python scripts/build_all.py <data.json> <outdir> --prefix <产品简称>
```

检查输出：

- [ ] `build_report.json` 生成；
- [ ] HTML/XLSX 文件名含产品与截止日；
- [ ] `build_report.json` 的 counts 与数据一致；
- [ ] 哈希存在（交付/归档用）。

## 3. HTML 结构 QA

```bash
python scripts/qa.py <outdir> --node /path/to/node
```

自动检查：

- [ ] 无 `__DATA__`/`__APP__`/`__STYLE__`/`__TITLE__`/`__XLSX_NAME__` 占位符；
- [ ] 有 `</html>`、关键容器（baselineCard/pool/cmptable/scatter/sources）；
- [ ] 内嵌 JSON 可解析，候选数 ≥2，`meta.product` 非空；
- [ ] 第二个 `<script>` 通过 `node --check`；
- [ ] Excel 10 个工作表名称/顺序正确；
- [ ] `01`/`04` 行数 ≥ 候选数。

手动检查（浏览器）：

- [ ] 断网/离线打开正常，无外部请求；
- [ ] 页头数字与数据一致；现有供应商基线正确；
- [ ] 参数改月量/费率，车次/运费估算变化；
- [ ] 搜索、筛选（近场/资质/新装置/同源/工艺）、排序、卡片/表格切换正常；
- [ ] 勾选 2 家 → 对比按钮可用；勾选 >5 家提示上限；
- [ ] 对比弹窗：第一列现有供应商、20+ 行、雷达、差异列表；
- [ ] 散点 hover 显示企业/产能/运距；图例正确；
- [ ] 同源卡片颜色/提示；同组多选提示；
- [ ] 规格矩阵三态颜色；新装置/非资质显示“必须试样”；
- [ ] 风险筛选/来源链接；
- [ ] 行动清单/方法/来源/页脚；
- [ ] 打印预览只保留对比弹窗，A4 横向可读；
- [ ] 移动端 720px 不横向溢出（表格可滚动）。

## 4. Excel 结构 QA

用 `openpyxl`/Excel 打开：

- [ ] 10 个表：`00_说明`…`09_尽调清单`；
- [ ] `00` 标题/场景/方法/判断/导航/免责完整；纵向打印；
- [ ] `01` 33 列、冻结 C5、筛选 A4:AG、数据条/色阶/超链接；
- [ ] `02` 3 张图（产能/运费/工艺饼），图例/标题/数据区可读；
- [ ] `03` 现有 + 12 家列、类别合并、冻结 D7、数值色阶；
- [ ] `04` 规格矩阵列数 = 3 + 6 + spec 数 + 3；状态下拉；三态颜色；
- [ ] `05` 同源组、flag 颜色；
- [ ] `06` 风险类型/状态颜色、来源可点；
- [ ] `07` 动作/责任/产出、状态下拉；
- [ ] `08` 来源 A/B/C 颜色、链接、日期；
- [ ] `09` 候选 × 尽调项、状态下拉、重点尽调；
- [ ] 打印：横向、fitToWidth、标题行重复、页脚页码；
- [ ] 中文不乱码；长文本不截断（行高自适应）；
- [ ] 没有 `#REF!`/`#VALUE!`/空图表。

## 5. 内容/合规 QA（最重要）

- [ ] 没有“建议换成 X”“X 最佳”“综合得分第一”；
- [ ] 没有把“待核实”写成事实；
- [ ] 没有把贸易商/代理商写成“生产企业”；
- [ ] 同源/同集团/纵向竞争有显著提示；
- [ ] 每个关键数字有来源；来源可点；
- [ ] 产能/产量/运费/距离口径写清；
- [ ] 没有把集团产能当可售货源；
- [ ] 新装置/新工艺/非准入有“必须试样”与稳定性验证；
- [ ] 数据截止日/证据等级/缺口写在交付物里；
- [ ] 免责声明保留。

## 6. 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| `validate.py` 报 `process 不在 meta.processes` | 候选工艺名与 meta 不一致 | 统一命名或补 process |
| `evidence 引用不存在` | 来源 ID 写错/漏加 | 补 sources 或改 ID |
| `spec_status` 报错 | 漏项/值不是三态 | 每家×每项补齐 |
| HTML 空白 | JS 语法/数据注入错误 | `node --check`、看控制台 |
| 对比按钮不可用 | 选中 <2 | 勾选 2–5 家 |
| 雷达缺一家 | 数据 process 不在 meta | 补 process |
| Excel 图表空 | 数据区/表头引用错 | 检查 `02` 数据行 |
| 中文文件名乱码 | 终端编码/zip 标志 | 用 UTF-8；zip 设 0x800 |
| 打开 HTML 无样式 | 模板占位符未替换 | 重跑 build_html |
| Excel 行高截断 | 长文本/列宽 | 调 `fit_row` 上限/列宽 |

## 7. 交付前签字

```text
数据截止：
候选数/来源数：
验证通过：validate / build_all / qa
人工检查：HTML（浏览器） / Excel（打开/打印）
未解决缺口：
决策边界：排序≠建议，最终由采购决定
```

> 自动化只能证明“结构没坏”，不能证明“研究对”。研究结论必须由人复核来源、口径和同源关系。
