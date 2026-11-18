# chem-procure-brief · 看原料近期行情（采购侧）

给化工采购的一套"可核验的行情底稿"生成器。输入手填的 `research.json`，输出：

- **单文件离线 HTML 看板**（零外链，双击即开，可直接发微信/邮件）
- **12 表 Excel 工作簿**（价格序列、涨跌与分位、区域价差、成本拆解、产业链自证、库存开工、事件时间线、可用事实与话术、缺口与来源、方法口径）

核心承诺：**每个数字都带点位 + 规格 + 含税 + 提货方式 + 日期 + 来源；拿不到的一律写成缺口；不做任何价格预测。**

## 安装

```bash
# 放到技能目录（任选其一）
copy chem-procure-brief  %USERPROFILE%\.agents\skills\
# 或解压 zip 后改名保持目录名为 chem-procure-brief
```

依赖：Python 3.9+ 与 `openpyxl`；渲染自检需要 `playwright`（没有会自动跳过）。

```bash
python -m pip install openpyxl playwright
python -m playwright install chromium    # 仅渲染自检需要
```

Windows/PowerShell 下建议先 `$env:PYTHONUTF8='1'`，避免中文输出乱码。

## 快速上手

```bash
# 1) 复制模板
cp chem-procure-brief/examples/research.template.json ./research.json

# 2) 按 references/data-contract.md 填数据（只填原始数据，不填涨跌幅/分位）

# 3) 一键生成（校验→装配→HTML→Excel→四项自检）
python chem-procure-brief/scripts/build_all.py research.json --out out --name 品种-地区
```

产物：

```
out/品种-地区_原料行情底稿_采购.html
out/品种-地区_原料行情底稿_采购.xlsx
build/data.json
```

看到这段就是通过：

```
--- 静态自检：0 error ---
--- 工作簿自检：0 error ---
== 0 项失败
```

## 先看例子

`examples/01-meoh-huadong/` 是一个真实跑通的完整实例（华东甲醇 3 个月行情），
含 `research.json`、`data.json`、HTML、Excel 与自检截图。建议先把它跑一遍，再改自己的品种。

## 目录

| 路径 | 作用 |
|---|---|
| `SKILL.md` | 技能的完整说明（铁律、工作流、失败模式、质量门） |
| `references/price-data-standard.md` | 六项口径、报价类型可信度、口径冲突处理 |
| `references/time-series-analysis.md` | 涨跌/分位/异常点算法与样本量纪律 |
| `references/chain-mapping.md` | 工艺路线自证法（**不含任何品种的现成链表**） |
| `references/event-verification.md` | 四级证据、事件五问、传闻处置 |
| `references/presentation-spec.md` | HTML/Excel 结构与文案规范 |
| `references/data-contract.md` | `research.json` 字段手册 |
| `references/qa-checklist.md` | 交付前 40 项人工自检 |
| `references/no-forecast-policy.md` | 禁用词表与改写对照 |
| `references/adapters.md` | 数据源分层与抓取解析要点 |
| `scripts/` | 校验、装配、生成、自检（离线运行，不联网） |
| `templates/dashboard.html` | HTML 模板（可改样式，不改结构） |

## 单步命令（调试用）

```bash
python scripts/validate.py research.json            # 契约校验
python scripts/assemble.py research.json            # 只算 data.json
python scripts/build_html.py build/data.json --out out/x.html
python scripts/build_xlsx.py build/data.json --out out/x.xlsx
python scripts/check_html.py out/x.html build/data.json
python scripts/check_xlsx.py out/x.xlsx build/data.json
python scripts/qa_render.py out/x.html build/data.json --shots shots
python scripts/fetch_futures.py <symbol> --out raw/XX_daily.json   # 可选
```

## 适用范围

- 大宗化工品、精细化工品、中间体均可（链由 `research.json` 提供，工具不预设任何品种）。
- 不适用于：价格预测、贸易投机决策、需要实时行情的盯盘场景。

## 已知限制

- 资讯商的动态价格图通常为前端加密渲染，**无法**在服务端还原；只用文中文字披露的数字，并登记为缺口。
- 现货是稀疏报价，分位的统计意义受样本数限制，报告会强制显示样本数。
- 成本表只用"单耗 × 单价"算**原料成本**；加工费没有可靠来源时不做合计（这是刻意的）。

## 许可与免责

本工具只做数据整理与呈现，不构成任何投资或采购建议。所有结论须以当日供应商报价与合同为准。
