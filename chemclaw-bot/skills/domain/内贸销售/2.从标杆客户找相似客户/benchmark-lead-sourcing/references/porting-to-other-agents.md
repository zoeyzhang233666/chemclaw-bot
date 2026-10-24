# 移植到其他 agent / 机器

本包只依赖三样东西：**Markdown 指令**、**Python 3.8+ 标准库**、**宿主自己的联网与文件能力**。
没有任何机器特定路径、环境变量或私有工具依赖。

---

## 1. 能力矩阵：哪一步需要什么

| 步骤 | 需要的能力 | 没有时的降级 |
|---|---|---|
| 步骤 1 契约 | 向用户提问 | 让用户一次性提供四项输入 |
| 步骤 2 通道探测 | 联网（任一通道）+ 执行命令 | 只能用宿主内置抓取；再不行让用户在浏览器代抓 |
| 步骤 3 lane 设计 | 模型产业知识 | 不可降级（这是本 skill 的核心智力活动） |
| 步骤 4 brief 生成 | 执行 Python | 手写 brief（照 `lane-brief-template.md` 填） |
| 步骤 5 lane 执行 | **子代理**（并行）+ 写文件 + 联网 | 无子代理 → 主 agent 串行跑，lane 数降到 4–6、每条 8–12 条线索 |
| 步骤 6 体检 | 执行 Python | 人工检查 JSON 字段 |
| 步骤 7 抽检 | 子代理或 Python | `fetch.py check` 单独跑（不需要子代理） |
| 步骤 8 出表 | Python + `openpyxl` | 无 openpyxl → 只出 HTML（无第三方依赖）+ 导出 CSV |
| 步骤 9 交付 | 写文件 | 直接把报告正文贴在对话里 |

**两个硬需求**：① **联网**（发现+核验）；② **能写文件**（lane 必须落盘，否则上下文必崩）。
若宿主连文件写入都没有，改用「每个 lane 直接返回 JSON 数组，主 agent 立刻写出」的串行模式，并把 lane 数压到 3–4。

---

## 2. 各 agent 的接入方式

### Claude Code / DSH（`.claude/skills`、`.agents/skills`）

```bash
python scripts/install.py --target all      # 自动装到两个目录
```
它们读取 `SKILL.md` 的 YAML frontmatter（`name` + `description`）自动注册技能；`description` 里已写入中英文触发词。子代理工具名不同（`Task` / `subagent`），但语义一致——都用「一个 brief 一个子代理」。

### Codex / AGENTS.md 系

包内 `AGENTS.md` 可直接照抄到项目根或 `~/.codex/AGENTS.md`；或在其中加一行指针：

```markdown
- 标杆客户复制找客户：先读 <包路径>/SKILL.md，按其九步工作流执行。
```
Codex 无内置子代理时，用「串行 lane」模式（步骤 5 降级）。

### chemclaw / workbuddy / 自研 agent

- 有技能/工具注册表：把 `SKILL.md` 注册为技能，把 `scripts/*.py` 注册为命令工具（注意给 `fetch.py` 声明超时与网络权限）。
- 只有系统提示词：把 `SKILL.md` + `references/workflow.md` 拼进提示词，`scripts/` 放工作目录，用 `python scripts/xxx.py` 调用。
- 有原生搜索/浏览工具但没有子代理：串行 lane + 把 `fetch.py` 当唯一取证通道。

---

## 3. 联网能力对照（按优先级探测，每级只试一次）

| 通道 | 探测命令 | 通了就用它做 |
|---|---|---|
| 宿主 web_search | 任意查询 | **发现**新企业、找协会名录/园区名单 |
| 宿主 web_fetch / browser | 打开一家公司官网 | **核验**主体与业务板块 |
| `python scripts/fetch.py` | `fetch.py cninfo -k "测试 产品名" -n 3` | **结构化取证**（公告原文、资料页、批量查链） |
| shell（`curl` / `iwr`） | `curl -sI http://www.cninfo.com.cn` | 兜底 |
| 用户浏览器 | — | 全部失败时的最后手段（并整体降一档置信度） |

**代理环境**：`HTTPS_PROXY` / `HTTP_PROXY` / `NO_PROXY` 会被 `fetch.py` 自动遵循（标准库行为），无需改代码。

---

## 4. 机器差异

| 差异 | 影响 | 处理 |
|---|---|---|
| 无 Python | 步骤 4/6/7/8 无法自动执行 | 手写 brief、人工体检、HTML 由 agent 直接写文件输出 |
| 无 `openpyxl` | 出不了 Excel | `pip install openpyxl`，或先只出 HTML/CSV |
| Windows 控制台中文乱码 | 仅显示层 | 不影响文件；必要时把统计写文件再读 |
| 目录分隔符 | 无影响 | 脚本全部用 `os.path` / `pathlib` |
| 文件编码 | 无影响 | 读入统一 `utf-8-sig`，写出 `utf-8` |
| 时区/区域 | 无影响 | 不依赖时间 |

---

## 5. 打包分发

```bash
python scripts/install.py --pack benchmark-lead-sourcing.zip   # 生成可搬运 zip（排除 __pycache__）
```
接收方解压后：装了依赖 → 跑一遍 `examples/soda-ash-huadong/` 的 merge/build_workbook/make_html_report 验证环境 → 再开新项目。
`examples/` 可删（约 0.5 MB）以减小体积；删了只是失去「开箱自检」的样例。
