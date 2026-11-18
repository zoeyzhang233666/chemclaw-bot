# 示例 02 · 最小 schema 模板（合成数据，不是研究）

> **这不是真实企业、不是真实价格、不是研究结论。**
> 它只演示 `data.json` 的字段、结构与生成物长什么样；复制本目录，替换成你的产品和候选即可。

## 里面有什么

- 3 家虚构候选：示例 A / B / C（其中 A、B 同属“示例集团”，用来演示同源提示）；
- 5 项虚构规格：主含量、水分、粒度、关键杂质、包装；
- 3 条虚构来源（`example.com`）；
- 1 组同源关系、3 条风险、3 条行动；
- 生成好的 HTML + Excel，可直接打开看结构。

## 快速复制

```bash
cp -r examples/02-minimal-template my-project
# 编辑 my-project/data.json：替换 meta / params / baseline / candidates / spec_items / spec_status / same_source / risks / actions / sources
python scripts/validate.py my-project/data.json
python scripts/build_all.py my-project/data.json my-project/out --prefix 我的产品
```

## 应该先改哪里

1. `meta.product/product_short/unit/asof/buyer_site/spec/use_case`；
2. `meta.processes`：你的工艺路线、颜色、成本潜力；
3. `meta.qualification_label/short`、`grade_label`：行业资质/等级叫法；
4. `params`：月量、收货地、运费率、车重；
5. `baseline`：现有供应商真实信息；
6. `candidates`：5–15 家真实候选（生产企业，不是贸易商）；
7. `spec_items`：9–15 项可检测指标；
8. `spec_status`：每家 × 每项三态；
9. `same_source`/`risks`/`actions`/`sources`。

## 文件

| 文件 | 说明 |
|---|---|
| `data.json` | 合成 schema 示例 |
| `示例化工品X_第二供应源备选池_对比工作台_2026-10-19.html` | 生成物（可打开看交互） |
| `示例化工品X_第二供应源备选池_对比工作簿_2026-10-19.xlsx` | 生成物（10 表） |
| `build_report.json` | 构建回执 |

## 注意

- 校验会对“3 家候选”和“同组两家同时入选”给警告，这是**预期**：模板故意小，且故意演示同源；
- 真实项目不要用虚构来源；`sources[].url` 必须是可核验链接；
- 不要把这个模板的“判断”当成研究结论；它没有研究。
