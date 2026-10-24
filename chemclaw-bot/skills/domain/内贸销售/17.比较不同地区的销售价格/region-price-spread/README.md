# region-price-spread · 多地区价格与区域价差对比

给化工品内贸销售用：选 2–5 个区域，看同一口径下的价格、裸价差、价差历史，
再把运费与区域供需从价差里剥出来，判断**报价环境**——不是判断套利。

## 产出

| 文件 | 内容 |
|---|---|
| `…多地区价格对比.html` | 自包含交互页（约 1 MB，离线可开）：区域多选、价格/价差曲线、价差矩阵、价差分解、当前价差表、历史统计、区域下钻 |
| `…多地区价格对比.xlsx` | 10 表：概览 / 口径与时间轴 / 价格序列 / 价差分解 / 价差矩阵 / 价差统计 / 运费矩阵 / 供需与客户 / 数据缺口 / 方法与免责 |

## 快速开始

```bash
python scripts/build_all.py examples/01-soda-ash-5-regions/data.json \
       --out examples/01-soda-ash-5-regions/out \
       --name 纯碱多地区价格对比
```

只依赖 Python 3 + openpyxl。`scripts/assets/echarts.min.js` 已内置，无需联网。

## 目录

```
SKILL.md                 技能入口（何时用、红线、坑）
references/
  data-contract.md       data.json 字段与校验规则
  method.md              价差/运费/残差定义与判读规则
  qa-checklist.md        交付前 15 条体检
scripts/
  common.py              计算层（价差、运距、运费、统计）
  build_html.py          模板 + 数据 + ECharts → 单文件 HTML
  build_xlsx.py          10 表 Excel
  build_all.py           一键：校验 → HTML → Excel → 体检
  validate.py            数据契约校验
  qa.py                  产物体检（含 HTML/Excel 数字一致性）
  smoke.cjs              Node 冒烟测试（可选，抓白屏级 JS 错误）
  templates/dashboard.html
  assets/echarts.min.js
examples/01-soda-ash-5-regions/
  data.json              真实案例：纯碱重碱 5 区，2026-07-17 ~ 10-16
  out/                   成品 HTML + Excel
```

## 换产品

只改 `data.json`：产品、区域（含枢纽坐标与 `water_ok`）、价格序列、运费费率、结论文字。
脚本不动。填错的字段会被 `validate.py` 拦住。

## 三条纪律

1. 同一时间口径，缺样本断开不插值。
2. 裸价差、运费、残差分三列，不合并。
3. 价差不是机会；残差不是利润。结论只描述报价环境。
