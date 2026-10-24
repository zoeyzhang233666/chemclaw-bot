# 案例 02：最小演示（虚构数据）

**这不是真实案例。** 企业、事件、金额、日期、来源链接全部为占位，只用于：

- 学习最小 `data.json` 字段；
- 跑通 `validate.py → build_all.py → qa.py`；
- 改文案/版式时有一个不会涉及真实企业的测试样本。

## 文件

| 文件 | 说明 |
|---|---|
| [`data.json`](data.json) | 4 家虚构供应商、6 条虚构事件、6 类覆盖检查 |
| [`示例化工品供应商风险雷达_2026-10.html`](示例化工品供应商风险雷达_2026-10.html) | 生成后的 HTML |
| [`示例化工品供应商风险雷达_2026-10.xlsx`](示例化工品供应商风险雷达_2026-10.xlsx) | 生成后的 Excel |

## 这个样本故意覆盖了什么

- 4 家供应商：3 家“上市”、1 家“非上市”，验证 `code/market` 分支。
- 6 条事件覆盖五类：工商、司法、处罚、安全环保、经营动态。
- 一条**窗口外**事件（2026-03-01 春季检修），验证 6m/12m 计数差异。
- 一条**正向**事件（新增产能试生产），验证 `direction:"正向"` 与低严重度。
- 一家供应商**未披露财务**（示例化工C），验证“未披露”在页面/Excel 的显示。
- `coverage_check` 同时含“未检索到/待复核/中/低/—”，验证覆盖表。

## 跑一遍

```bash
python scripts/validate.py examples/02-minimal-demo/data.json
python scripts/build_all.py examples/02-minimal-demo/data.json \
  --out examples/02-minimal-demo --name 示例化工品供应商风险雷达_2026-10
python scripts/qa.py examples/02-minimal-demo/data.json \
  "examples/02-minimal-demo/示例化工品供应商风险雷达_2026-10.html" \
  "examples/02-minimal-demo/示例化工品供应商风险雷达_2026-10.xlsx"
```

## 怎么改成自己的

1. 复制 `data.json` 为 `my-product.json`。
2. 替换 `meta`：产品、英文名、规格、截止日、三个窗口、财务期间、`period_tag`。
3. 替换 `suppliers`：真实企业、代码、基地、工艺、产能、财务、结论、覆盖。
4. 替换 `events`：每条真实事件，日期用发生日期，`url` 用原文。
5. 替换 `coverage_check` / `industry` / `method`。
6. 跑校验、生成、QA。

删除所有“示例”“演示”“占位”字样后再交付。

## 再次提醒

`example.com` 链接是占位，点开不会看到真实公告；所有数字都不是真实数据。不要把本目录内容用于任何供应商判断。
