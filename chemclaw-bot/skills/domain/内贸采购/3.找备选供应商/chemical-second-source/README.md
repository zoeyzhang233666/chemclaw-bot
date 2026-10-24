# chemical-second-source

化工品第二供应源 / 备选供应商池研究工作台。输入一份 `data.json`，输出：

- **单文件交互式 HTML**：卡片 + 表格、筛选、勾选 2–5 家横向对比、产能×运距散点、工艺结构、同源关系、规格/试样矩阵、风险台账、90 天行动、来源；
- **10-sheet Excel**：说明、备选池、图表、横向对比、试样计划、同源关系、风险台账、行动清单、数据来源、尽调清单；
- **build_report.json**：构建回执（数量、哈希、警告）。

产品无关。纯碱只是示例；换成钛白粉、烧碱、甲醇、树脂、溶剂、工业气体、食品添加剂、电池材料等，只改数据，不改代码。

## 快速开始

```bash
# 1) 安装唯一依赖
python -m pip install -r requirements.txt

# 2) 校验
python scripts/validate.py examples/02-minimal-template/data.json

# 3) 构建 HTML + Excel
python scripts/build_all.py examples/02-minimal-template/data.json out --prefix 示例化工品X

# 4) 可选 QA（需要 Node）
python scripts/qa.py out --node /path/to/node

# 5) 可选打包
python scripts/package.py . dist/chemical-second-source-skill.zip
```

在 Windows 上把 `python` 换成 `py -3` 或完整解释器路径。

## 先看成品

- `examples/01-soda-ash/`：**真实研究案例**（重质纯碱；现有供应商山东海化；收货地苏州；12 家备选、9 项规格、45 条来源）。直接打开：
  - `纯碱_第二供应源备选池_对比工作台_2026-10-19.html`
  - `纯碱_第二供应源备选池_对比工作簿_2026-10-19.xlsx`
- `examples/02-minimal-template/`：**合成 schema 模板**（3 家虚构企业、5 项规格、3 条来源），不是研究结论；复制它开始自己的项目。

## 研究口径（一句话版）

先把现有供应商的规格拆成可检测指标；再按工艺/产区/集团找**生产企业**；排除同源/贸易商；用 A/B/C 证据和“待核实”标注；新装置/新工艺/非准入一律首样；输出排序、差异、风险与 30/60/90 天验证计划，**不替采购决定替换**。

完整流程见 `SKILL.md`；字段见 `references/data-contract.md`；检索与核实见 `references/research-playbook.md`。

## 产物结构

### HTML

单文件、离线、无 CDN。内嵌 JSON、CSS、JS；支持：

- 关键词搜索 + 近场/准入/新装置/同源/工艺筛选；
- 卡片/表格切换、按运距/产能/风险/名称排序；
- 勾选 2–5 家 → 对比弹窗（现有供应商 + 备选，20+ 行对比 + 雷达 + 差异）；
- 产能×运距散点、工艺阵营、同源卡片、规格矩阵、风险台账、行动清单、来源；
- 打印比较（浏览器打印）。

### Excel（10 个工作表）

| 工作表 | 内容 |
|---|---|
| `00_说明` | 场景参数、方法、关键判断、导航、证据/风险口径、免责 |
| `01_备选池` | 33 列：身份、区位、运距、运费、工艺、产能、资质、财务、同源、风险、差异、证据 |
| `02_图表` | 产能/运费横条图 + 工艺饼图（数据可编辑） |
| `03_横向对比` | 现有 + 备选逐项对比；运距/运费/产能/风险色阶 |
| `04_试样计划` | 规格 × 候选矩阵；COA/试样/审核；状态下拉 |
| `05_同源关系` | 集团、母公司、主体、关系、影响、核实、标记 |
| `06_风险台账` | 公开事实、影响、来源、链接、已公开/待核实 |
| `07_行动清单` | 阶段、动作、说明、责任、产出、状态、目标完成 |
| `08_数据来源` | A/B/C 等级、日期、链接 |
| `09_尽调清单` | 候选 × 尽调项；状态下拉；可作审厂记录 |

## 目录

```
chemical-second-source/
├── SKILL.md              # 给 agent 的完整研究流程与约束
├── AGENTS.md             # 给 Codex/通用 agent 的短入口
├── README.md
├── requirements.txt
├── LICENSE
├── scripts/              # validate / build_html / build_xlsx / build_all / qa
│   └── templates/        # workbench.html + style.css + app.js
├── references/           # 检索、字段、证据、同源、规格、行业适配、设计、QA、适配器
├── examples/
│   ├── 01-soda-ash/
│   └── 02-minimal-template/
└── dist/                 # 可选打包
```

## 换电脑 / 换 agent

只依赖 Python 3.9+、`openpyxl`、文件读写和 shell。无需 DSH API、无需联网构建、无需 Node（Node 仅用于可选 JS 检查）。

- **Codex / Claude Code / ChemClaw / WorkBuddy**：把整个目录放进 skills 目录，让 agent 先读 `SKILL.md`，或直接读 `AGENTS.md`；数据用 `data.json`，产物用 `build_all.py`。
- **Windows**：中文文件名可用；Excel 字体“微软雅黑”，macOS 自动回退。
- **没有 openpyxl**：`pip install -r requirements.txt`；不要用 CSV 冒充 xlsx。
- **没有 Node**：跳过 `qa.py --node`，HTML 仍可打开。

## 边界

本工具输出采购研究辅助材料，不构成供应商授标、合同审批、法律尽调或投资建议。所有“待核实”必须以营业执照、生产许可、COA、现场审核、合同条款为准；最终决策权在采购组织。
