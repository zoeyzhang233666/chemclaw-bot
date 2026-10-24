# 区域市场地图（化工品内贸）

一个可复用的 skill：输入**产品 + 区域**，输出**一张能安排行程的交互地图 + 一本 12 表的工作簿**，并保留完整的取证方法与口径。

产品无关。纯碱、钛白粉、环氧丙烷、颜料、助剂、树脂都能用；换产品只换一个 JSON。

```
chemical-region-market-map/
├── SKILL.md                     ← 入口：何时用、三步走、质量红线
├── README.md                    ← 本文件：快速开始与目录说明
├── references/
│   ├── data-contract.md         ← data.json 字段与校验规则（写数据前必读）
│   ├── research-playbook.md     ← 研究手册：取证通道、单耗推法、同行/误判 gate
│   ├── design-system.md         ← HTML/Excel 视觉与排版规范
│   ├── adapters.md              ← 在 Claude Code / Codex / DSH / 业务 agent 上怎么装
│   └── qa-checklist.md          ← 交付前检查清单 + 已知 bug 症状对照
├── scripts/
│   ├── build_all.py             ← 一条命令生成 HTML + Excel
│   ├── validate.py              ← 数据校验（error 阻断 / warning 提示）
│   ├── qa.py                    ← 产出体检（可选 headless 渲染核对）
│   ├── build_html.py, build_xlsx.py, common.py, fetch_assets.py
│   ├── templates/dashboard.html ← 页面模板（占位符 __ECHARTS__ / %%GEO%% / %%DATA%%）
│   └── assets/                  ← echarts 5.5.1、中国省界 GeoJSON、城市坐标库（离线）
└── examples/
    ├── 01-soda-ash-east-china/  ← 完整真实案例（纯碱·华东）+ 成品
    └── 02-skeleton-toy-region/  ← 最小骨架（占位数据）+ 成品
```

## 快速开始

```bash
pip install openpyxl

# 1) 校验
python scripts/validate.py examples/02-skeleton-toy-region/data.json

# 2) 生成
python scripts/build_all.py examples/02-skeleton-toy-region/data.json \
       --out out --name 我的产品-我的区域

# 3) 体检
python scripts/qa.py examples/02-skeleton-toy-region/data.json \
       "out/我的产品-我的区域市场地图.html" \
       "out/我的产品-我的区域客户分布与走访优先级.xlsx"
```

打开 `out/*.html` 即为成品（离线可用）。Excel 为 12 张表。

## 它回答的六个问题

1. 客户集中在哪些城市和化工园区，各多少家潜企业（估算）
2. 其中生产企业与贸易商各占多少
3. 主要下游行业是什么、为什么用这个产品、单耗多少
4. 代表头部企业是谁，中小企业藏在哪（数量口径，不编名字）
5. 最近有哪些新建/扩产/减产项目，何时接触
6. 本地价格 vs 区外差多少，报价怎么定

最后给出 S/A/B/C 分级、走访顺序、每周路线与天数预算。

## 设计原则（为什么长这样）

- **先给地图和汇总，再给名单**：使用者要的是"去哪里"，不是"有哪些公司"。
- **估算与核实分离**：每个数字要么有来源，要么标"估算"；同行与误判单列。
- **一份 JSON 出两个文件**：HTML 与 Excel 数字天然一致，不会对不上。
- **零依赖离线**：ECharts 与 GeoJSON 内联，发给客户也能直接打开。

## 授权与引用

示例中的事实性内容来自公开渠道（上市公司公告、行业协会、价格机构、地方园区资料），已在 `data.json` 的 `src` 字段逐条标注；示例仅为方法演示，商业使用前请自行复核时效性。
