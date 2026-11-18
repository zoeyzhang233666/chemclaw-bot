# chem-sales-compliance

化工品内贸销售的「危险化学品买方资质与销售合规提醒」工具：
一个 case.json → 一份自包含交互 HTML + 一份 12 表 Excel。

## 快速开始

```bash
# 1) 生成 Excel
python scripts/build_workbook.py examples/01-纯碱-福莱特/case.json out.xlsx

# 2) 生成 HTML
python scripts/build_html.py examples/01-纯碱-福莱特/case.json out.html

# 3) 校验（必须 PASS）
python scripts/verify.py examples/01-纯碱-福莱特/case.json --html out.html --xlsx out.xlsx
```

Windows 下若控制台中文乱码：

```powershell
$env:PYTHONIOENCODING="utf-8"
```

依赖：Python 3.10+、openpyxl（仅 Excel 生成需要）。

## 产物长什么样

**HTML（单文件，双击可开，无需联网）**

- 概览：判定结论 + 三条"不适用" + 免责
- 产品身份：8 个产品可点选对照、5 个身份问答、8 项规格、手动输入自查
- 判定卡：8 项名录标记、GHS 分类、交易后果、5 条依据（可展开）、6 个边界条件
- 买方资质：A/B/C/NA 统计 + 13 张核查卡（可筛选）
- 合规清单：19 项，可勾选、可写备注、localStorage 保存、可导出 JSON/CSV
- 证照：12 项卡片（必备/建议/分支/可选）
- 留存备案：矩阵表 + 结论条
- 缺口话术：5 个缺口 + 三版草稿（邮件标准/仅缺口/微信），可编辑可复制
- 对照表、法规索引、人工确认

**Excel（12 表，可打印、可归档）**

`00 封面` / `01 产品身份` / `02 判定卡` / `03 判定依据` / `04 买方核查` /
`05 合规清单（下拉勾选）` / `06 索取证照` / `07 留存备案` / `08 缺口话术` /
`09 产品对照` / `10 法规索引` / `11 人工确认`

## 换一单生意怎么改

复制 `examples/01-纯碱-福莱特/` 为 `examples/02-你的案例/`，改 `case.json`：

1. `meta`：买卖双方、数量、用途、交货；
2. `product`：名称/CAS/浓度/形态/等级/规格；
3. `determination`：结论、8 项名录标记、GHS、依据、边界；
4. `buyer_checks`：逐项标 A/B/C/NA，NA 必附依据；
5. `obligations` / `documents` / `gaps` / `draft`；
6. 重跑两条 build + verify。

不要手改 HTML/Excel——所有数字来自 case.json，手改会漏掉联动。

## 判定口径（摘要）

- 危化品以《危险化学品目录（2015 版）》列入为准；未列入但特性不明的，按 60 号令鉴定；
- 剧毒/易制爆：买方资质查验 + 销售记录 ≥3 年 + 3 日内报县级公安备案 + 禁止互联网销售；
- 易制毒：第一类购买许可证，第二/三类购买前备案；
- 一般化工品：无法定 3 年要求，建议商务资料 ≥5 年，会计凭证 30 年。

详见 `references/03-法条索引.md`。

## 免责

本工具输出为资料提醒，不构成法律意见。最终以监管部门与企业安全合规部门判定为准。
