# 移植到其他 agent / 机器

本包只依赖：**Markdown 指令**、**Python 3.8+（出表需 openpyxl）**、**宿主联网与写文件能力**。无机器特定路径。

## 1. 能力矩阵

| 步骤 | 需要 | 缺失时降级 |
|---|---|---|
| ① 契约 | 向用户提问 | 让用户一次给全五件输入 |
| ② 研究 | 联网（任一通道） | 用用户提供的资料 + 模型产业知识，卡内注明"未联网核实"并整体降一档可信度 |
| ③ 组装 | 模型知识 | 不可降级（核心智力活动） |
| ④ Excel | Python + openpyxl | 按 `output-spec.md` 手工建 8 表；或交付 CSV 集 + 说明 |
| ⑤ HTML | 写文件 | 直接在回复中给完整 HTML 代码块，由用户保存 |
| ⑥ 体检 | 逐项自查 | 打印检查单请用户抽查两条来源 |

**硬需求**：能写文件。连文件都写不了 → 本 skill 无法交付，只能输出内容让用户自己存。

## 2. 各 agent 接入

### DSH 系（ChemClaw / WorkBuddy / DeepSeek Harness）
- 有技能目录：整个文件夹放进技能根目录，`SKILL.md` frontmatter 自动注册。
- 无技能目录：对 bot 说"读取 `<路径>/SKILL.md` 并按六步工作流执行"。

### Codex / AGENTS.md 系
- 把包内 `AGENTS.md` 合并进 `AGENTS.md`（项目根或 `~/.codex/AGENTS.md`），或加一行指针指向 `SKILL.md`。

### Claude Code
- 复制到 `.claude/skills/customer-visit-brief/`，重启会话生效。

### 自研 agent（仅系统提示词）
- 提示词 = `SKILL.md` + `references/workflow.md`；`scripts/templates/examples` 放工作目录。

## 3. 联网通道探测（每级试一次即止）

宿主 web_search → 宿主 web_fetch/browser → shell `curl`/`iwr` → 用户浏览器代抓（注明降级）。
代理环境遵循 `HTTPS_PROXY` 标准库行为。

## 4. 机器差异

| 差异 | 处理 |
|---|---|
| Windows 控制台中文乱码 | 仅显示层；必要时把输出写文件再读，或 `sys.stdout.reconfigure(encoding='utf-8')` |
| 无 openpyxl | `pip install -r requirements.txt`；或 HTML+CSV |
| 路径分隔符 | 脚本只用 `pathlib`/`os.path`，无影响 |
| 编码 | 读 `utf-8-sig`，写 `utf-8` |

## 5. 打包分发

```powershell
Compress-Archive -Path customer-visit-brief -DestinationPath customer-visit-brief.zip
```
```bash
zip -r customer-visit-brief.zip customer-visit-brief -x "*__pycache__*"
```

接收方解压后先跑 README 的验证命令（用 examples 重出一次 Excel）。
