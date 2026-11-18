# 整理询盘并生成报价草稿 · inquiry-to-quotation

内贸销售（化工品）用：把微信/邮件/PDF/Excel 里的散装询盘，先整理成**可逐项确认的标准字段**
（缺失黄色高亮，分“必须补充”与“可按假设”两类），再在销售**自己确认单价与税费/运费口径**之后，
生成一份**可审阅的报价草稿**。

> 核心一句话：**价格是销售的决定，不是系统的输出。** 系统只抽字段、算算术、排版、标缺口。

## 30 秒看懂

1. 打开 `examples/example-1-soda-ash-glass/案例研究_纯碱询盘报价.html` → 看完整效果；
2. 打开同目录的 `询盘工作台_华宇玻璃纯碱.html` → 上传区 + 默认文本 + 字段确认 + 价格闸门；
3. 打开 `报价工作簿_华宇玻璃纯碱.xlsx` → 7 表审批版（单价默认空白）；
4. 看 `examples/example-1-soda-ash-glass/demo/` → 销售确认 1,180 元/吨后的报价效果（标 DEMO）。

## 快速开始（自己的客户）

```bash
PY=<python>; S=scripts

# 1) 询盘 → 标准字段（不产生价格）
$PY $S/extract.py 询盘素材.txt -o fields.json --as-of 2026-10-19 --inquiry-no INQ-20261019-01

# 2) 字段 → 交互式工作台（打开即有默认文本）
$PY $S/build_workbench.py fields.json -o 询盘工作台.html --demo-text-file 询盘素材.txt

# 3) 字段 → 7 表 Excel（单价留空）
$PY $S/build_xlsx.py fields.json -o 报价工作簿.xlsx

# 4) 销售确认价格与口径后，才生成带价格的草稿
$PY $S/build_quote.py fields.json --price <确认价> --qty 200 \
     --tax "含税（13% 增值税专用发票）" --freight "到厂价（含运费）" \
     --company "我方公司全称" --ack "我确认该单价为我方销售价格" --xlsx
```

不带 `--ack`，`build_quote.py` 直接拒绝（exit 2）并列出缺哪几项。

## 两类分桶

- **A 类 · 必须补充后才能报价**：产品、规格、数量、交货地点、客户名称、税费口径、运费口径、单价
- **B 类 · 可先按假设准备**：包装、交期、付款条件、运输方式、报价有效期（报价里逐条标“我方假设 · 待客户确认”）

## 价格红线

无默认价、无参考价、无区间价、无建议价、无历史价回填。单价只有一条来路：销售填写 + 勾选确认语
（脚本等价 `--ack`）。示例里的 1,180 元/吨只是版式演示，不是建议价或成交价。

## 交付物

| 文件 | 说明 |
|---|---|
| `询盘工作台_<客户>.html` | 上传 + 字段确认（黄色高亮）+ 口径选择 + 价格闸门 + 报价草稿 + 复制/导出/打印/转合同审阅；单文件离线可用 |
| `报价工作簿_<客户>.xlsx` | 01 概要 / 02 字段确认 / 03 缺失与假设 / 04 价格与口径 / 05 报价草稿 / 06 口径与边界 / 07 素材与证据 |
| `报价_<客户>-报价草稿.md` | 报价单正文（七要素） |
| `fields_<客户>.json` | 标准字段（不含价格） |
| `案例研究_<客户>.html` | 客户原声 + 字段提取 + 缺口 + 报价效果 + 复用方法 |

## 示例

`examples/example-1-soda-ash-glass/`：纯碱 → 浮法玻璃完整案例，含可上传的微信截图、邮件 `.eml`、
需求表 XLSX/PDF，客户名称只有简称、付款条件缺失、手写比价表有读不出的 `1?30`。
输入与产物齐全；`demo/` 是销售确认 1,180 元/吨后的版式效果（明确标 DEMO）。

换品类从 `examples/_skeleton/` 复制，按 `examples/README.md` 操作。

## 自检

```bash
$PY scripts/selfcheck.py fields.json --html 询盘工作台.html --xlsx 报价工作簿.xlsx
node scripts/selftest_workbench.mjs 询盘工作台.html --price 1180
node scripts/selftest_case.mjs examples/example-1-soda-ash-glass/案例研究_纯碱询盘报价.html
```

## 移植

见 `INSTALL.md`：复制整个目录即可；无服务、无数据库、无网络依赖。Claude/Codex 放 skills 目录，
ChemClaw/WorkBuddy 可把 `SKILL.md` 或 `PORTABLE_PROMPT.md` 当系统提示词；脚本仍可独立跑。
没有文件系统的 agent，直接用 `PORTABLE_PROMPT.md`（纯提示词版，不需要 Python）。

## 目录

```
inquiry-to-quotation/
├── SKILL.md / README.md / INSTALL.md / AGENTS.md
├── products/                纯碱产品画像 + 空白模板
├── schemas/                 fields / quote JSON Schema
├── references/              字段口径、抽取规则、报价写法、价格红线、研究手册、QA
├── scripts/                 抽取、HTML、Excel、报价、自检、案例素材生成
├── templates/               工作台模板、默认报价模板
└── examples/                纯碱完整案例 + 空白骨架
```
