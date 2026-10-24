# customer360-chemical · 客户360画像 Skill

面向化工/材料行业内贸销售的**单客户深研**技能：输入"一家目标企业 + 你卖的产品"，输出可直接使用的客户画像。产品无关（纯碱、烧碱、氟化工、锂电材料、聚合物、助剂……通用），研究流程与交付结构固定。

## 交付物（每次必出两份）

| 文件 | 内容 |
|---|---|
| `客户360_{公司}_画像.html` | 单文件交互式一页画像：首屏三问结论 → 产品与工厂 / 项目与动态 / 采购关系 / 企业风险 / 核实清单 五个分区，每个判断可点击展开证据链接 |
| `客户360_{公司}_核查台账.xlsx` | ≥10 个 sheet 的证据台账：使用说明 / 销售摘要 / 主体确认 / 七项核查 / 产品与工厂 / 项目与动态 / 采购关系 / 风险与关注 / 核实清单 / 证据台账 |

明确不输出：信用评级、授信额度、履约/违约概率。

## 目录结构

```
customer360-chemical/
├── SKILL.md                  # 技能主文件：工作流与硬性边界（喂给 Agent 的入口）
├── README.md                 # 本文件：安装与使用说明
├── references/
│   ├── playbook.md           # 检索手册：各分区查询模板、信息源清单、化工品采购逻辑推断法
│   └── data-schema.md        # data.json 字段规范 + 手工交付规格
├── scripts/
│   └── build.py              # data.json → Excel + HTML 渲染器（openpyxl 可选，缺失降级 CSV）
└── examples/                 # 参考例子（详见 examples/README.md）
    ├── README.md             # 四个范例的教学点对照表
    ├── example-1-haihua-sodaash-salt/      # 真实研究：原盐→纯碱上市公司（山东海化）
    ├── example-2-viscose-caustic-direct-fit/ # 虚构：烧碱→粘胶工厂（直接原料正例）
    ├── example-3-trader-not-a-customer/      # 虚构：环氧丙烷→贸易商（"不是目标客户"反例）
    └── example-4-lithium-plant-capex-window/ # 虚构：耐腐蚀泵→在建锂电厂（项目窗口期）
```

## 快速使用

```bash
# 1. Agent 按 SKILL.md 研究并把事实填成 data.json（规范见 references/data-schema.md，范例见 examples/）
# 2. 一键生成交付物（以范例1为例）：
python scripts/build.py examples/example-1-haihua-sodaash-salt/data.json -o output/
# → output/客户360_山东海化股份有限公司_画像.html
# → output/客户360_山东海化股份有限公司_核查台账.xlsx
```

依赖：Python 3.8+；openpyxl（可选，缺失时 Excel 自动降级为同名 CSV 系列）。

## 安装到不同的电脑 / Agent

- **Claude Code / 支持技能目录的 Agent**：把整个 `customer360-chemical/` 目录复制到其技能目录（如 `~/.claude/skills/`），说"用 customer360-chemical 调研XX公司"即可触发。
- **Codex / 任意 CLI Agent**：把本目录放到项目内，在 `AGENTS.md` / 系统提示中加一行：`研究单一目标客户时，阅读并遵循 customer360-chemical/SKILL.md`。
- **chemclaw / workbuddy 等业务 Agent**：直接把 `SKILL.md` + `references/` 作为上下文附件提供；Agent 只需具备网页搜索与抓取能力即可执行研究部分；生成附件时运行 `scripts/build.py`（或按 data-schema.md 的手工规格输出）。
- **无 Python 环境**：build.py 会降级生成 CSV；或让 Agent 依照 data-schema.md 附录直接手写 Excel/HTML——分区与 sheet 结构不得增删合并。

## 定制

- 新增行业信息源（如氟化工 Track 环评、锂电材料排产），编辑 `references/playbook.md` 第 6 节，分区结构保持不变。
- 修改交付样式：编辑 `scripts/build.py` 内嵌 HTML 模板；新增 sheet：同步改 `data-schema.md` 与 build.py，保持版本一致。
