# 标杆客户复制 · 下游潜客池（化工品通用版）

把一个成功成交的标杆客户，复制成一批**业务特征相似、因而会产生同类原料需求**的潜在客户，
并给每条线索留下可点开、可在电话里复述的出处。

- **产品无关**：纯碱、烧碱、钛白粉、柠檬酸、环氧乙烷、MDI、磷酸铁锂前驱体……换产品只换 `project.json`。
- **agent 无关**：Markdown 指令 + 纯 Python 标准库脚本，Claude Code / DSH / Codex / chemclaw / workbuddy 都能用。
- **交付固定**：Excel（5 表）+ **单文件 HTML 报告**（9 节，带筛选与打印样式），结构不随产品变化。

---

## 1. 安装（按你的 agent 选一种）

### 1.1 Claude Code / DSH 系（`.claude/skills` 或 `.agents/skills`）

```bash
python scripts/install.py --target claude     # 装到 ~/.claude/skills/benchmark-lead-sourcing
python scripts/install.py --target dsh        # 装到 ~/.agents/skills/benchmark-lead-sourcing
python scripts/install.py --target /path/to/skills   # 装到自定义技能目录
python scripts/install.py --target all        # 以上都装（默认）
```

装完重启 agent。它们会自动读取 `SKILL.md` 的 YAML frontmatter（`name` + `description`）并把本技能加入技能目录。

### 1.2 Codex / 任何读 `AGENTS.md` 的 agent

把包放到任意目录（例如 `~/skills/benchmark-lead-sourcing`），然后在你项目的 `AGENTS.md`（或 `~/.codex/AGENTS.md`）里加一行：

```markdown
## 技能
- 标杆客户复制找客户：见 ~/skills/benchmark-lead-sourcing/SKILL.md —— 当用户要求「从标杆客户找相似客户 / 做潜客池 / 化工品下游客户名单」时，先完整读取该文件并按其九步工作流执行。
```

包内也附了一份可直接照抄的 [`AGENTS.md`](AGENTS.md)。

### 1.3 chemclaw / workbuddy / 自研 agent

- 若有「工具/技能注册表」：把 `SKILL.md` 注册为一个 skill，把 `scripts/` 注册为可执行工具集。
- 若没有：把 `SKILL.md` 作为系统提示词的一段（或让 agent 在开始任务时 `read` 它），把 `scripts/` 放在工作目录下用 `python scripts/xxx.py` 调用。
- 能力映射表（哪些步骤需要「子代理」「文件写入」「联网」）见 [`references/porting-to-other-agents.md`](references/porting-to-other-agents.md)。

### 1.4 依赖

```bash
pip install -r requirements.txt      # 仅 openpyxl（出 Excel 用）
```
`fetch.py` / `merge_leads.py` / `validate.py` / `new_project.py` / `make_lane_briefs.py` / `check_project.py` / `make_html_report.py` **只用 Python 标准库**（3.8+），不需要任何第三方包；HTML 报告在任何机器上都能出，Excel 需要 `openpyxl`。

---

## 2. 60 秒上手

```bash
# 1) 建档（产品、标杆客户、区域）
python scripts/new_project.py --dir work/soda-ash --product "纯碱" \
       --benchmark "旗滨集团（601636）" --region "华东:山东,江苏,浙江,安徽,上海"

# 2) 让 agent 做三件事：研究标杆画像、写 8–12 条 lane、填 project.json
#    （参考 examples/soda-ash-huadong/ 里已填好的同名文件）

# 3) 批量生成 lane 作业书（每条含六件套 + 防上下文耗尽纪律）
python scripts/make_lane_briefs.py --dir work/soda-ash

# 4) 每个 brief 起一个子代理，产出 work/soda-ash/leads_raw/NN_*.json

# 5) 体检 → 抽检 → 合并 → 出表 → 出报告 → 交付体检
python scripts/validate.py        --dir work/soda-ash
python scripts/fetch.py check --file work/soda-ash/leads_raw/_qa_todo.json \
       --out work/soda-ash/leads_raw/_qa_report.json
python scripts/merge_leads.py       --dir work/soda-ash
python scripts/build_workbook.py    --dir work/soda-ash
python scripts/make_html_report.py  --dir work/soda-ash
python scripts/check_project.py     --dir work/soda-ash
```

产物：`<项目>/下游潜客池.xlsx`、`<项目>/标杆客户复制与潜客池报告.html`、`<项目>/leads.json`。
HTML 是自包含单文件（内联 CSS/JS、零外链），双击即可在浏览器打开；需要发 PDF 时用浏览器「打印 → 另存为 PDF」。

---

## 3. 目录结构

```
benchmark-lead-sourcing/
├── SKILL.md                     技能主文件（frontmatter + 九步工作流 + gate + 结构）
├── AGENTS.md                    Codex/AGENTS 系的照抄片段
├── README.md                    本文件：安装、上手、排错
├── requirements.txt
├── references/
│   ├── workflow.md              九步详解、完成判据、并行纪律、失败修法
│   ├── evidence-channels.md     通道阶梯；原生联网工具优先；fetch.py 命令手册
│   ├── gates.md                 五道 gate + 打分公式 + 品类归并
│   ├── similarity-framework.md  五维相似性框架与按产品实例化方法
│   ├── lane-brief-template.md   lane 作业书模板（六件套）+ 崩溃后的枚举式 brief
│   ├── config-schema.md         project.json 逐字段说明
│   ├── output-structure.md      leads 字段、Excel 5 表、Word 9 节、使用边界
│   ├── failure-log.md           实测踩过的坑与修法（含沙箱/编码/上下文）
│   └── porting-to-other-agents.md  各 agent 能力映射与降级路径
├── scripts/
│   ├── fetch.py                 联网取证 CLI（cninfo 公告全文检索 / 网页正文 / 交易所资料页 / 批量查链）
│   ├── new_project.py           从模板建项目目录与 project.json
│   ├── make_lane_briefs.py      批量生成 lane 作业书
│   ├── validate.py              lane 文件结构体检
│   ├── merge_leads.py           去重、打分、区域与同行过滤、注入抽检结论
│   ├── build_workbook.py        出 Excel（5 表）
│   ├── make_html_report.py      出 HTML 报告（单文件，9 节 + 筛选 + 打印样式）
│   ├── check_project.py         交付前总检
│   └── install.py               安装到各 agent 的技能目录
├── templates/                   project.json / benchmark_profile.json / report_notes.json 模板
└── examples/soda-ash-huadong/   完整实战示例（纯碱·华东，含成品 Excel + HTML）
```

---

## 4. 排错

| 症状 | 原因 | 修法 |
|---|---|---|
| `fetch.py` 全部超时 | 机器出网需要代理 | 设 `HTTPS_PROXY`/`HTTP_PROXY` 环境变量后重试；或改用宿主原生联网工具 |
| Excel 打不开/缺 openpyxl | 未安装依赖 | `pip install openpyxl`；HTML 报告与其余步骤不受影响 |
| cninfo 返回 0 条 | 关键词太窄或用了别名 | 改用**产品正式名**（学名/别名索引很差）；或换「公司名 + 产品名」定域检索 |
| 子代理崩溃、零产出 | 一次读入大 JSON / 页数开太大 | 用 `make_lane_briefs.py` 生成的 brief（已内置抓取上限与增量落盘）；崩溃后改用模板里的**枚举式 brief** 重开 |
| Excel 少列/串味 | 品类归并关键词同时匹配了「需求点」 | `buckets` 只匹配「细分行业」字段（脚本已强制） |
| 名单里混进同行 | 该产品的同行没写进 `peer_keywords` | 在 `project.json` 的 `peer_keywords` 补关键词，重跑 merge |
| 区域外企业没被过滤 | `region.provinces` 没填全 | 补齐省份名单，重跑 merge |

更多真实故障案例见 [`references/failure-log.md`](references/failure-log.md)。

---

## 5. 搬运与版本

- 本包零硬编码路径、零机器特定依赖；整个目录复制到另一台机器即可（`examples/` 可删以减小体积）。
- 建议随包分发时保留 `examples/soda-ash-huadong/`：新机器上先跑一遍示例的 `merge_leads → build_workbook → make_html_report`，几秒内即可确认环境就绪（示例含完整成品 Excel + HTML，可对照校验）。
- 打 zip：`python scripts/install.py --pack benchmark-lead-sourcing.zip`
