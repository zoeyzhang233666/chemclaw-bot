# 化工品供应市场全景（采购视角）· chemical-supply-market-map

一个**产品无关**的研究技能包：给任意化工品做「供应端全景」，输出可交互 HTML + 可追溯 Excel。
研究框架、口径纪律、缺口规则、交付结构都固化在包里，换产品只需换配置。

```
输入：产品名 + 地域 + 基准年（+ 可选采购量）
输出：<产品>供应格局全景_<年>.html   ← 单文件，离线可开，6 个标签页，点击企业/项目看详情
      <产品>供应格局数据包_<年>.xlsx ← 16 张表，含图表、公式模拟器、尽调与评分模板
```

## 它解决什么问题

采购在做「这个品种能不能放心买、从谁买、怎么谈」时，真正需要的是六件事：

1. 谁在产、产多少、什么口径（**产能**）
2. 集中在哪些省、贸易活跃度如何（**区域**）
3. 哪几条工艺、原料依赖什么、成本区间在哪（**工艺与成本**）
4. 未来 1–2 年多出来多少（**净新增，不是名义新增**）
5. 价格走了什么周期、现在在什么位置（**价格**）
6. 断供、单源、区域集中的风险在哪，合同怎么写（**采购关注**）

本技能把这六个问题做成固定的分析模块 + 固定的交付结构，并用五道 gate 防止「看起来很完整、
实际不可用」的报告。

## 五道 gate

| gate | 规矩 |
|---|---|
| 口径 | 多套公开数字**并列不平均** |
| 缺口 | 缺失值写「数据缺口」，**不估算、不外推** |
| 净增 | 置换/搬迁必须扣退出产能，不确定标「待确认」 |
| 来源 | 每个数字对应 S 编号来源，无来源标「未核实」 |
| 集中度 | CR5/HHI 注明样本口径；覆盖率 <70% 必须提示 |

## 快速开始

```bash
# 1. 依赖（只有 Excel 需要；HTML 纯标准库）
pip install -r requirements.txt

# 2. 建一个新项目
python scripts/new_project.py --dir work/urea-cn-2026 \
    --product "尿素（CO(NH₂)₂）" --short 尿素 --cas 57-13-6 \
    --grades "小颗粒/大颗粒" --year 2025 --forward 2026,2027

# 3. 填 project.json / plants.json / companies.json / projects.json
# 4. 体检（只检查不出文件）
python scripts/build_all.py --dir work/urea-cn-2026 --check

# 5. 出交付物
python scripts/build_all.py --dir work/urea-cn-2026

# 6. 交付前终检
python scripts/check_project.py --dir work/urea-cn-2026
```

## 直接看示例

```bash
# 完整示例：纯碱（32 基地 / 24 集团 / 9 项目 / 30 来源）
python scripts/build_all.py --dir examples/soda-ash-cn-2026
python scripts/check_project.py --dir examples/soda-ash-cn-2026

# 精简示例：烧碱（8 基地 / 5 项目 / 3 来源，含无 URL 的来源占位）
python scripts/build_all.py --dir examples/caustic-soda-cn-2026
```

两个示例用**同一套脚本**生成 —— 这就是「产品无关」的证明。

## 安装到各种 agent

```bash
python scripts/install.py                       # Claude Code + DSH
python scripts/install.py --target claude       # ~/.claude/skills/
python scripts/install.py --target dsh          # ~/.agents/skills/
python scripts/install.py --target /path/to/skills   # 自定义（chemclaw / workbuddy）
python scripts/install.py --pack chem-map.zip   # 打包搬运
```

- **Claude Code / DSH / Claude Skills**：读 `SKILL.md` 的 frontmatter 自动注册。
- **Codex / WorkBuddy**：读 `AGENTS.md`。把包内 `AGENTS.md` 追加到项目 `AGENTS.md`，
  或在全局指令里加一行指向 `SKILL.md`。
- **chemclaw / 自建工具**：把目录放到 agent 能读的位置，在 system prompt 里贴 `AGENTS.md`。

细节见 `references/porting-to-other-agents.md`。

## 目录结构

```
chemical-supply-market-map/
├── SKILL.md                 ← 技能主文件（框架 / gate / 十步 / 交付结构）
├── AGENTS.md                ← 给 AGENTS.md 型 agent 的加载指令
├── README.md                ← 本文件
├── requirements.txt         ← openpyxl
├── scripts/
│   ├── new_project.py       ← 建项目骨架
│   ├── build_all.py         ← 一键出 HTML + Excel（--check / --html-only / --excel-only）
│   ├── build_excel.py       ← 16 表工作簿
│   ├── _render.py           ← HTML 片段渲染
│   ├── _common.py           ← 配置装载 / 校验 / 指标计算
│   ├── check_project.py     ← 数据 + HTML + Excel 三项体检
│   ├── ui_check.py          ← Playwright 真点一遍（可选）
│   └── install.py           ← 安装 / 打包
├── assets/                  ← template.html / style.css / app.js（内联进产物）
├── references/              ← 10 份方法论（按需读）
├── templates/               ← 空白行模板与 lane 作业书
└── examples/
    ├── soda-ash-cn-2026/    ← 纯碱：完整示例（含已生成 HTML + Excel）
    └── caustic-soda-cn-2026/ ← 烧碱：精简示例（演示数据不全时的样子）
```

## 产物长什么样

- **HTML**：单文件、零外部依赖、可打印成 PDF；6 个标签页（全景 / 企业表 / 项目时间线 / 价格 /
  采购关注 / 数据与来源）；点企业出尽调抽屉，点项目出净增还原抽屉。
- **Excel**：16 张表 + 5 个原生图表 + 活公式（合计、供应商加权、采购量模拟器）+ 数据校验 +
  冻结窗格 + 横向打印区域；缺失值全部写「数据缺口」。

## 原则

> 产能数据不足的部分请明确说明，不要估算。

这句话不是免责声明，是方法：**缺口本身就是采购决策的一项风险**，写出来比补上去更有用。

## License

MIT
