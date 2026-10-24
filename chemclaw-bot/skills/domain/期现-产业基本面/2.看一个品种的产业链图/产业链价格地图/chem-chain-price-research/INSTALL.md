# 安装与跨 agent 使用

这个技能包是"一个目录 + 一份 SKILL.md"的形态（Agent Skills 通用约定），
不含任何机器专属路径、不依赖第三方库、不需要联网即可生成与校验页面。

## 目录内容

```
chem-chain-price-research/
├── SKILL.md                  技能入口（YAML frontmatter + 工作流）
├── agents/openai.yaml        OpenAI/Codex 风格接口声明（可选，不影响其他平台）
├── scripts/
│   ├── chain_layout.py       布局引擎（生成器与校验器共用，不单独运行）
│   ├── build_chain_html.py   数据 → 自包含交互 HTML
│   ├── validate_dataset.py   数据契约校验
│   ├── verify_html.py        产物自检（自包含 / 几何 / 数据一致性）
│   └── verify_render.js      渲染冒烟（可选，需要 Node）
├── references/
│   ├── workflow.md           研究流程与自检清单
│   ├── data-contract.md      chain-data.json 全字段说明
│   ├── html-deliverable.md   HTML 交付规范
│   └── adapters.md           数据源适配与降级（含没有数据工具时怎么办）
└── examples/
    ├── sbs/                  SBS 完整实例（真实数据 + 生成物 + 研究记录）
    └── template-example/     空白模板（无价格，起手照抄）
```

## 环境要求

| 需要 | 说明 |
|---|---|
| Python 3.8+ | 只用标准库（`argparse`/`json`/`re`/`os`/`sys`），无需 pip 安装 |
| Node.js（可选） | 只有 `verify_render.js` 需要；没有就跳过该步 |
| 网络（可选） | 仅取价阶段需要；生成与校验完全离线 |
| 浏览器 | 打开产物 HTML 用；产物无外部依赖，断网可用 |

## 安装：三步通用法

1. **放进技能目录**
   找到目标 agent 的技能目录，把整个 `chem-chain-price-research/` 目录复制进去
   （保持目录名不变，`SKILL.md` 必须在目录根下）。常见位置：

   - ChemClaw：宿主行业技能目录，例如本机为
     `<宿主安装目录>\state\deepseek-harness\<会话或工作区 id>\industry-skills\`
     （实际路径随宿主安装位置变化，以宿主显示的资源路径为准）。
   - Claude Code 类：用户级 `~/.claude/skills/`，或项目级 `.claude/skills/`。
   - Codex / OpenAI 风格：放到其技能（skills）目录；`agents/openai.yaml` 会被该类平台读取。
   - WorkBuddy 及其他知识工作 agent：若有技能/知识库导入功能，导入本目录即可；
     若无，见下面「没有技能机制时」。

2. **确认脚本路径**
   技能被加载时通常会给一个资源根路径（如 ChemClaw 的
   `resourceBase: {kind: "directory", path: "<...>"}`），脚本就用这个根路径拼绝对路径调用。
   例如：

   ```bash
   python "<技能根>/scripts/validate_dataset.py" chain-data.json
   python "<技能根>/scripts/build_chain_html.py" chain-data.json -o <product>-chain.html
   python "<技能根>/scripts/verify_html.py" <product>-chain.html --source chain-data.json
   ```

   不要假定某个 agent 会把脚本放进 PATH，也不要依赖当前工作目录——
   `verify_html.py` 与 `build_chain_html.py` 都会自己定位 `chain_layout.py`。

3. **验证安装**
   让 agent 执行一次最小回归（本包自带示例，不需要网络）：

   ```bash
   python scripts/validate_dataset.py examples/sbs/chain-data.json
   python scripts/build_chain_html.py examples/sbs/chain-data.json -o /tmp/sbs-check.html
   python scripts/verify_html.py /tmp/sbs-check.html --source examples/sbs/chain-data.json
   ```

   三条都通过（0 错误 / 0 问题），说明包完整、环境可用。
   若 agent 具备技能枚举能力，也应能在技能列表里看到 `chem-chain-price-research`。

## 没有技能机制时（降级用法）

把 `SKILL.md` 的正文当作 SOP 直接贴进对话或写进项目规则文件（如 `AGENTS.md`、`.cursorrules`），
并把 `scripts/`、`references/`、`examples/` 放在工作区里供其读写。
脚本是纯标准库 Python，任何能执行 shell 的 agent 都能跑；此时技能包退化为
"一份流程文档 + 四个可执行检查器"，功能不损失。

## 轻量安装（只想要能用的部分）

只要 `scripts/` 三个文件 + `examples/template-example/chain-data.json` 就能出图；
`references/` 与 `examples/sbs/` 是给人看的方法论与参考，不影响运行。

## 常见问题

| 现象 | 原因与处理 |
|---|---|
| `python` 不存在 | 试 `py`（Windows）或 `python3` |
| `validate_dataset.py` 报"缺单位" | 补 `meta.unit` 或该节点的 `unit`；缺单位的数字不允许上图 |
| `verify_html.py` 报文本超宽 | 缩短对应文案（名称 ≤ 8 字，口径 ≤ 18 字，应用短句 ≤ 24 字） |
| 页面打开是空白 | 确认 `<script>` 未被浏览器扩展拦截；用 `node verify_render.js` 定位 |
| 中文文件名/路径报错 | 脚本按 UTF-8 读写；Windows 上用 PowerShell 并确保代码页为 UTF-8 |
