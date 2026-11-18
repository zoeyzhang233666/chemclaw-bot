# 化工供应商风险雷达 · Chemical Supplier Risk Radar

给采购 / 寻源团队用的**产品无关**供应商风险扫描 skill：输入任意化工品与供应商名单，输出一份可交互 HTML + 一本 9 表 Excel，逐条列出近 3/6/12 个月的公开风险事件、来源、采购含义与待确认问题。

> 定位：公开信息桌面筛查，不是完整尽调；不预测断供，不把新闻当结论。

## 30 秒开始

```bash
pip install -r requirements.txt

# 1) 校验数据（error 必须清零）
python scripts/validate.py examples/01-soda-ash-2026-10/data.json

# 2) 一次生成 HTML + Excel
python scripts/build_all.py examples/01-soda-ash-2026-10/data.json \
  --out out --name 纯碱-2026-10

# 3) 体检
python scripts/qa.py examples/01-soda-ash-2026-10/data.json \
  "out/纯碱-2026-10.html" "out/纯碱-2026-10.xlsx"
```

打开 `out/纯碱-2026-10.html` 即可；Excel 可直接用于开会、标注、发供应商。

## 它解决什么问题

| 常见问法 | 输出 |
|---|---|
| 这几家供应商最近有没有风险？ | 近 6 个月事件时间线 + 风险等级 |
| 有没有处罚、诉讼、事故、停产？ | 五类事件 + 六类覆盖检查 |
| 这条新闻会不会影响交付？ | 事实 / 采购含义 / 待确认问题分开写 |
| 哪些还没查到？ | 明确列出“未检索到”“待复核”“渠道未覆盖” |
| 会上怎么讲？ | HTML 总览 + Excel 一页页可查 |

## 目录

```
chemical-supplier-risk-radar/
├── SKILL.md                     # 给 agent 的入口（先读这个）
├── README.md
├── requirements.txt
├── schema/
│   └── data.schema.json         # 机器可读 JSON Schema（辅助，validate.py 为准）
├── scripts/
│   ├── validate.py              # 数据契约校验
│   ├── build_xlsx.py            # 9 表 Excel
│   ├── build_html.py            # 自包含 HTML
│   ├── build_all.py             # 一次生成两个交付物
│   ├── normalize.py             # 可选段落补默认值，避免空数据崩溃
│   ├── qa.py                    # 静态体检（无需浏览器）
│   └── assets/template.html     # HTML 模板（占位符 + DATA 注入）
├── references/
│   ├── research-playbook.md     # 六类取证通道、查询模板、误判清单
│   ├── data-contract.md         # 字段、枚举、校验规则
│   ├── design-system.md         # HTML/Excel 版式与交互
│   ├── adapters.md              # chemclaw / workbuddy / codex / Claude 安装
│   └── qa-checklist.md          # 交付前检查清单
└── examples/
    ├── 01-soda-ash-2026-10/     # 真实完整案例：纯碱 × 7 家
    └── 02-minimal-demo/         # 虚构占位：4 家 / 6 条，用来跑通流程
```

## 两个交付物

**HTML**：单文件、离线、无 CDN。首屏 KPI + 雷达；总览/时间线/供应商/方法四个视图；3/6/12 个月、五分类、供应商、关键词、只看中高风险筛选；事件与供应商弹窗；打印样式。

**Excel**：`00_封面`、`01_风险总览`、`02_事件时间线`、`03_分类汇总`、`04_供应商画像`、`05_待核实清单`、`06_来源清单`、`07_方法与口径`、`08_行业背景`。含风险色阶、超链接、筛选、冻结窗格、打印区域。

## 换一个产品怎么做

1. 复制 `examples/02-minimal-demo/data.json` 为 `my-product.json`。
2. 按 `references/data-contract.md` 填 `meta` / `suppliers` / `events` / `coverage_check` / `method`。
3. 跑 `validate.py` → `build_all.py` → `qa.py`。
4. 研究阶段照 `references/research-playbook.md` 的六类通道取证。

不需要改模板或生成器。产品名、供应商数、事件数、窗口、财务期间、行业标题都从 `data.json` 读取。

## 依赖

- Python 3.8+
- `openpyxl`（`pip install -r requirements.txt`）
- 可选：LibreOffice（`soffice`）用于 `--pdf`；没有不影响 HTML/Excel
- 不需要 Node、不需要 pandas、不需要联网 CDN

## 示例

- `examples/01-soda-ash-2026-10/`：纯碱 7 家（博源、中盐、三友、海化、双环、和邦、金山），19 条事件，6 个月窗口 16 条。含 `data.json`、`.html`、`.xlsx`、`.pdf` 与案例说明。
- `examples/02-minimal-demo/`：**虚构**的示例化工品，4 家供应商、6 条事件，只用于验证字段和生成器；所有内容均为占位，不可引用。

## 常见问题

**没有 Chrome 能跑 qa 吗？** 能。`qa.py` 是静态检查，不依赖浏览器；需要真实渲染时再人工打开 HTML。

**Excel 打开提示修复？** 生成器用 openpyxl 标准写法；若出现，先确认没有用 Excel 宏或外部链接，再重跑 `build_all.py`。

**中文字体不对？** Excel 用“微软雅黑”；macOS 没有该字体会回退，不影响内容。HTML 用系统宋体/黑体栈。

**可以加第六类风险吗？** 模板与 Excel 的筛选/配色按五类固定；加类需要同时改 `scripts/assets/template.html` 的 `CATS`、`validate.py` 的 `CATS` 和 `build_xlsx.py` 的分类顺序。一般建议把新类归入现有五类。

**数据里可以写英文吗？** 可以；字段值支持英文，页面照常渲染。但建议保留中文分类/严重度枚举，否则筛选与配色不生效。

## 使用边界

本 skill 只做公开信息检索与结构化，不构成法律、财务、投资或采购意见。公开信息可能滞后、遗漏、口径不一致；“未检索到”不等于“无风险”。准入/续约前仍应补充现场审核、财务尽调、征信报告与合同条款设计。
