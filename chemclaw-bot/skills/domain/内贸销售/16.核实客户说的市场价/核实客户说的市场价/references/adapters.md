# 在各平台上安装这个 Skill

这个 Skill 是**纯资源目录**：一个文件夹 + 一个 `SKILL.md` + `references/` + `scripts/` + `examples/`。
不依赖任何平台专属 SDK，所以主要工作就是"放对位置"。

---

## 一、通用原则

1. **整个文件夹一起放**，不要只拷 `SKILL.md`（脚本和模板在里面）
2. 文件夹名可以带序号（如 `16.核实客户说的市场价`），但 `SKILL.md` 不改名
3. `SKILL.md` 的 YAML front-matter（`name` + `description`）是给检索用的，别删
4. 放好后用一句话触发测试："客户说华东纯碱才1400，帮我核实一下这个市场价"

---

## 二、DeepSeek Harness (DSH)

```bash
# 用户级（对所有会话生效）
cp -r "核实客户说的市场价" "$HOME/.agents/skills/"

# 或带序号
cp -r "核实客户说的市场价" "$HOME/.agents/skills/16.核实客户说的市场价"
```

Windows:

```powershell
Copy-Item -Recurse "核实客户说的市场价" "$env:USERPROFILE\.agents\skills\16.核实客户说的市场价"
```

验证：
```bash
ls ~/.agents/skills/ | grep 核实
```
新开一个会话，问："客户说市场价才1400，帮我核实"，应该能看到这个 skill 被调用。

**依赖**：Python 3.10+（`openpyxl` 用于生成 Excel）。DSH 自带的 Python 运行时已包含。

---

## 三、ChemClaw

ChemClaw 的 skill 目录通常按业务场景分类：

```
chemclaw场景分类上下文/skills/<分类>/<序号>.<技能名>/
```

本 Skill 属于 **内贸销售** 分类：

```powershell
# 先看现有序号，不要猜
Get-ChildItem "../../../..\内贸销售" -Directory |
    Select-Object -ExpandProperty Name | Sort-Object
```

确认最大序号后，把文件夹放到 `内贸销售\<下一个序号>.核实客户说的市场价`。

**注意**：如果目标目录里已经放着 `chem-market-brief.zip` 这样的压缩包格式，
两种形式都可以，但**同一个技能不要既放解压版又放 zip**。

验证：在 ChemClaw 里问"客户说华东重质纯碱才1400"，应能命中。

---

## 四、WorkBuddy

按 WorkBuddy 的自定义技能目录放置（通常是用户目录下的 `skills/`）：

```powershell
# 找到 WorkBuddy 的技能目录（视版本而定，常见位置）
#   %APPDATA%\WorkBuddy\skills\
#   %USERPROFILE%\.workbuddy\skills\
```

放进去后重启 WorkBuddy，在技能列表里确认能看到"核实客户说的市场价"。

如果 WorkBuddy 只支持单文件技能：把 `SKILL.md` 作为主文件导入，其余目录保持
相对结构（`references/`、`scripts/` 与 `SKILL.md` 同级），这样脚本里的相对路径
（`os.path.dirname(__file__)`）仍然可用。

---

## 五、Codex / 其他兼容 Agent

这类工具通常支持 `AGENTS.md` 或类似的项目指令文件。两种接法：

### 接法 A：作为可检索技能（推荐）

放到 `~/.codex/skills/` 或该工具约定的 skills 目录，与 DSH 相同。

### 接法 B：作为项目指令

在项目根放一个 `AGENTS.md`，内容指向本 Skill：

```markdown
## 核实客户说的市场价

当用户说"客户说市场价才XXX""帮我核实这个价""客户说我们贵了"时，
读取 `skills/16.核实客户说的市场价/SKILL.md` 并严格按其中的八步流程执行，
同时遵守其中的"硬规则"（不替客户定性、不猜运费、不用固定百分比阈值）。
```

---

## 六、依赖

| 用途 | 依赖 | 是否必需 |
|---|---|---|
| 生成 HTML | 无（ECharts 已内联） | ✅ 内置 |
| 生成 Excel | `openpyxl>=3.0` | 需要 |
| HTML 自检（渲染） | Chrome / Edge（无头模式） | 可选，没有就只做静态检查 |
| Excel 自检 | `openpyxl`（公式求值器自带） | 需要 |

安装：

```bash
pip install openpyxl
```

`check_html.py` 找不到浏览器时会降级为静态检查并打印提示，不会失败。

---

## 七、装完之后的自检

```bash
cd "16.核实客户说的市场价"
python scripts/selftest.py                          # 27 项基础自检
python scripts/build_all.py examples/01-重质纯碱-华东   # 端到端跑一遍
```

两条都通过，说明环境没问题。

---

## 八、常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 构建报"数据契约未通过" | `research.json` 缺必填字段 | 按 `validate.py` 的 `[FAIL]` 逐条补 |
| HTML 打开是空白 | 浏览器太旧不支持 ECharts | 用 Chrome/Edge 最新版 |
| Excel 打开公式显示 `#NAME?` | 用了 Excel 不认识的函数 | 本 Skill 只用 IF/AND/ABS/AVERAGE 等基础函数，正常不会 |
| 历史序列全空 | `series_key` 没对上 | 检查 `meta.series_key` 与 `history[].spec` 是否一致 |
| 中文乱码 | 控制台编码 | 设置 `PYTHONIOENCODING=utf-8` |
| Excel 生成失败 | 缺 `openpyxl` | `pip install openpyxl` |
