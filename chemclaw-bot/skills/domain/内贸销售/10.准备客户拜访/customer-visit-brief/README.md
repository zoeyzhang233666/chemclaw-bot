# customer-visit-brief · 准备客户拜访技能包

化工品通用的「拜访前研究」技能：输入一家目标客户 + 我方产品，输出一张 5 分钟看完的拜访背景卡
（**Excel 8 表 + 单文件 HTML 一页卡**，每个事实带日期与可点开来源，历史沟通只认用户上传的记录）。

## 安装到不同 agent

### Claude Code / DSH 系（含 ChemClaw、WorkBuddy 等 DSH 技能目录宿主）

把整个 `customer-visit-brief/` 文件夹放进宿主的用户技能目录（skill 被扫描的根目录，通常在用户配置目录或工作区约定位置），
重启会话后即出现在技能列表。这些宿主读取 `SKILL.md` 的 YAML frontmatter（`name` + `description`，内含中英文触发词）自动注册。

没有技能目录机制的 DSH 宿主：直接对 bot 说——
> 读取 `<路径>/customer-visit-brief/SKILL.md`，按其六步工作流为我准备客户拜访。

### Codex / AGENTS.md 系

把包内 `AGENTS.md` 的内容合并进项目根或 `~/.codex/AGENTS.md`，或只加一行指针：

```markdown
- 准备客户拜访/拜访背景卡：先读 <包路径>/customer-visit-brief/SKILL.md，按其六步工作流执行。
```

Codex 无技能注册表时同样可用上述指针；无子代理能力不影响本 skill（单代理串行即可完成）。

### 自研 agent（只有系统提示词）

把 `SKILL.md` + `references/workflow.md` 拼进系统提示词或任务模板；`scripts/`、`templates/`、`examples/` 放工作目录，用
`python scripts/build_visit_workbook.py --data visit_data.json --out out.xlsx` 调用。

## 依赖

| 能力 | 用途 | 缺失时降级 |
|---|---|---|
| 联网搜索/抓取 | 取证研究（客户、大事、行情） | 用用户提供的资料，卡内注明"未联网核实" |
| Python 3.8+ | 运行出表脚本 | 按 `references/output-spec.md` 手工建 8 表 |
| `openpyxl` | 出 Excel | `pip install -r requirements.txt`；或先交付 HTML+CSV |
| 写文件 | 落盘 visit_data.json 与交付物 | 至少要能把 Excel/HTML 写到磁盘，否则本 skill 无法交付 |

## 验证环境（新机器第一步）

```bash
pip install -r requirements.txt
python scripts/build_visit_workbook.py \
  --data examples/soda-ash-flat-glass/visit_data.json \
  --out examples/soda-ash-flat-glass/福莱特拜访工作簿_纯碱_20261015.xlsx
```

生成的 xlsx 能打开、8 表齐全，即环境就绪。

## 打包分发

```powershell
# Windows
Compress-Archive -Path customer-visit-brief -DestinationPath customer-visit-brief.zip
# macOS / Linux
zip -r customer-visit-brief.zip customer-visit-brief -x "*__pycache__*"
```

接收方解压后先跑一遍上面的验证命令。`examples/` 约 0.1 MB，建议保留作为开箱自检与母版。
