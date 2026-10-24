# 化工品采购商机雷达（chemical-procurement-radar）

把一个化工品的「最近有哪些公开采购信号」变成一份**每条都能追溯到原文**的商机清单，
交付 **Excel + HTML**。

**产品无关**：换产品只改一个 config 文件，脚本一行都不用动。
**跨 agent**：同一个目录支持三种装载形态 —— `SKILL.md`（Agent Skills 标准）、`AGENTS.md`（Codex 等）、`PROMPT.md`（无机制平台）。
**跨机器**：只用 Python 标准库取数（出 Excel 需 `openpyxl`），中文 Windows 的编码坑已在代码里处理。

---

## 目录结构

```
chem-radar/
├── SKILL.md                     # 主入口（Agent Skills 标准：YAML frontmatter + 正文）
├── AGENTS.md                    # Codex / 读 AGENTS.md 的 agent 用（与 SKILL.md 同源）
├── PROMPT.md                    # 无 skill 机制的平台：贴系统提示词
├── README.md                    # 本文件
├── references/
│   ├── method.md                # 六步法与六条铁律；换产品时到底改什么
│   ├── gates.md                 # 六道闸门的判定逻辑、命中后怎么处理、换产品怎么改
│   ├── channels.md              # 取数通道手册：接口、参数、实测陷阱、死通道清单
│   ├── product-profiling.md     # 怎么为一个新化工品建产品画像（唯一需要行业知识的一步）
│   └── outputs.md               # 字段契约、Excel/HTML 结构、report_notes.json 结构
├── config/
│   ├── product.template.json    # 空白模板（带逐项说明）
│   └── soda-ash-east.json       # 实例：纯碱·华东·近90天
├── scripts/
│   ├── radarlib.py              # 公共库：配置、取数、六道闸门、去重、优先级
│   ├── fetch_cninfo.py          # cninfo 标题/全文检索取数
│   ├── fetch_pdftext.py         # PDF 正文抽取（纯标准库）
│   ├── merge_leads.py           # 套闸门 + 去重
│   ├── consolidate.py           # 同主体合并成一张卡
│   ├── qa_links.py              # 链接抽检
│   ├── build_workbook.py        # 出 Excel
│   ├── build_html.py            # 出单文件 HTML
│   ├── explain.py               # 排查闸门误杀（某条为什么被剔除）
│   ├── compare_runs.py          # 对比两次运行
│   └── run_all.py               # 一键跑完整条流水线
└── examples/soda-ash-east/      # 跑通的完整样例（config、93 条原始线索、report_notes、产物）
```

---

## 安装（按目标 agent 选一种）

### 1. Claude / DeepSeek Harness / 任何读 Agent Skills 的平台

这类平台扫描 `<家目录>/.agents/skills/<name>/`（也有用项目内 `.agents/skills/` 的）。把 `chem-radar` 目录整个拷成 `chemical-procurement-radar`：

```powershell
# Windows PowerShell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.agents\skills" | Out-Null
Copy-Item -Recurse -Force ".\chem-radar" "$env:USERPROFILE\.agents\skills\chemical-procurement-radar"
```

```bash
# macOS / Linux
mkdir -p ~/.agents/skills
cp -r ./chem-radar ~/.agents/skills/chemical-procurement-radar
```

**目录名要与 `SKILL.md` frontmatter 里的 `name` 一致**，否则有些平台不认。
装好后重启该 agent，或让它重新扫描技能目录，就能在技能列表里看到「化工品采购商机雷达」。

### 2. Codex

Codex 读工作目录下的 `AGENTS.md`。把 `chem-radar` 放进你的工作目录（或任意目录），
在**该目录下**启动 Codex，它就会读到 `AGENTS.md`。

如果希望全局生效，在你的全局 `AGENTS.md`（`~/.codex/AGENTS.md`）里加一行指针：

```markdown
化工品采购商机研究请遵循 `~/chem-radar/AGENTS.md`。
```

### 3. chemclaw / workbuddy / 其他平台

分两种情况：

- **支持「技能目录 / 知识库」**：把整个 `chem-radar` 目录导入，让它以 `SKILL.md`（或 `AGENTS.md`）为入口。`references/` 里的细节文档要一起导入，它们不是可选附件——`channels.md` 里有可直接照抄的接口与参数。
- **只能配系统提示词**：把 `PROMPT.md` 里「PROMPT 块」整段贴进系统提示词，并把 `references/*.md`、`config/product.template.json` 作为知识文件一起上传。

> 这两个平台的具体装载方式我无法实测（不在本机）。如果你告诉我它们认什么格式（目录结构？单个提示词？插件清单？），我可以再出一个针对性的装载文件。

### 4. 没有文件系统、只接受一段提示词

用 `PROMPT.md` 的 PROMPT 块。注意这种情况下该 agent 可能也**不能执行命令**，那它应该只产出 `leads.json` 与 `report_notes.json`（契约见 `references/outputs.md`），再由能跑脚本的环境出 Excel/HTML。

---

## 快速验证（跑实例，约 2 分钟）

```bash
cd chem-radar
python examples/soda-ash-east/../../scripts/run_all.py \
    --config examples/soda-ash-east/product.json \
    --dir    examples/soda-ash-east --skip-qa
```

或直接：

```bash
python scripts/run_all.py --config examples/soda-ash-east/product.json --dir examples/soda-ash-east
```

跑完在 `examples/soda-ash-east/out/` 下会得到：
- `纯碱华东_采购商机卡.xlsx`（9 个工作表）
- `纯碱华东_采购商机卡.html`（单文件自包含，双击即可看）

去掉 `--skip-qa` 会真的去探测链接（较慢），产出 `leads_raw/_qa_report.json`。

## 换个产品怎么用

```bash
# 1. 复制模板，填成你的产品
cp config/product.template.json config/my-product.json

# 2. 新建任务目录，把 config 放进去，把各 lane 的原始线索放进 leads_raw/
mkdir -p work/my-product/leads_raw

# 3. 一键出表
python scripts/run_all.py --config config/my-product.json --dir work/my-product
```

**要重建的只有四样**（都在 config 里，照 `references/product-profiling.md` 填）：
产品标识与检索词、下游应用地图与吨耗系数、同行名单、误配清单。
窗口、区域、最小订单规模、打分权重也都是 config 字段。

写代码时最容易做错的一步是**同行名单**——必须逐条核验年报业务分部，不能看名字。
`config/soda-ash-east.json` 里的 `peers.role_reversal` 记着两个方向相反的陷阱实例。

---

## 依赖

- **Python 3.7+**（用到了 `sys.stdout.reconfigure`）
- **出 Excel 需要 `openpyxl`**：`pip install openpyxl`
- 取数只用标准库（`urllib` / `zlib` / `json` / `re`），不需要 requests、pdfminer、pandas
- 不需要 Node.js、不需要 LibreOffice

## 跨机器可移植性（已处理的两类坑）

1. **中文 Windows 的控制台是 GBK**，Python 打印「↳」「≈」这类字符会直接抛
   `UnicodeEncodeError` 打断脚本 —— 这是「换台电脑就废」的头号原因。
   `radarlib` 在 import 时统一把 stdout/stderr 切成 UTF-8，所有脚本自动受益。
   控制台里中文仍可能乱码，所以**所有中文产出都落 UTF-8 文件**。
2. **HTTPS 不是到处都可用**（某些沙箱/代理环境没有 TLS 凭据）。`radarlib.http_get`
   会先试 https、失败自动回退 http，并记住「本环境无 TLS」不再反复重试。
   若你的环境 TLS 正常，它会直接用 https；若完全没有，就要在交付报告里如实写覆盖缺口。

另外：路径全部由命令行参数给出，脚本里**没有任何硬编码的机器路径**。

## 已知边界（诚实说明）

- **商业招标聚合平台与多数政府采购平台够不着**：国家政采网有反爬；部分省级政采强制图形验证码
  （模型没有图像输入能力，无法识别）；部分省市用前端渲染、服务端不吐数据；聚合平台多为仅 https。
  **这意味着一定还有招标没被找到**，尤其在地市级平台。详见 `references/channels.md` 的死通道清单。
- **价格与库存数据缺失**：在没有可用行情接口的环境里拿不到，报告里的价格判断是从公告口径推出的。
- **只覆盖上市公司**：cninfo 只能看见上市公司披露；中小买方不发公告，用量只能电话核实。
- **吨耗系数是估算**：来自化学计量与行业单耗经验值，条目里已标「（估算）」。
- **本 skill 不替你打客户电话**。它给的是「谁在买、大概买多少、找谁」+ 可追溯的出处。

## 实例验收状态（纯碱·华东·2026-07-15~2026-10-13）

用 93 条真实原始线索跑通，与手工版交付逐条比对：

| 项 | 结果 |
|---|---|
| 商机卡 | **58 条**（明确采购/招标 13 ｜ 扩产或复产需求 22 ｜ 其他潜在需求信号 23，其中 9 条同行动态与市场信号） |
| 被剔除 | 25 条，逐条留了命中的闸门与原因 |
| 区域 | 华东内 46 ｜ 区外 12（标注并灰置，未删除） |
| 链接抽检 | **60/60 可达** |
| Excel | 9 个工作表；超链接 57 条全部落在「证据来源」列；分组底色 13/22/23；区外灰置 12 行 = 区外 12 条；`check_office.py` verdict **pass** |
| HTML | 174 KB 单文件、零外部资源、九节齐全、58 张卡、71 个外链、可筛选 |
| 与手工版比对 | 手工版 57 条 → 流水线 58 条，差异全部可解释：4 条是同一公司的不同写法被合并、+1 条是跨分组条目被正确保留（同一公司在「明确采购」和「扩产」各有一条，本就该分别进两个工作表） |

跑这一遍的过程中修掉了三个真 bug，都已写进代码注释防复发：
1. **R2 错配闸门扫到了「与我产品的关系」栏** —— 那一栏是分析人员的解释文字，常写
   「本工序主耗烧碱而非纯碱」来排除干扰，导致把最好的线索（亚星化学的纯碱招标）误杀。
   现在 R2 只看事件标的字段，且事件标的里同时出现目标产品时不算错配（混合标的公告）。
2. **去重键没带分组** —— 同一家公司在两个分组里各有条目时会被误杀一条。
3. **R5 强制关系栏含数字过于严苛** —— 误杀了 16 条质量不错但没有数字的推断线索，已改为默认关闭。