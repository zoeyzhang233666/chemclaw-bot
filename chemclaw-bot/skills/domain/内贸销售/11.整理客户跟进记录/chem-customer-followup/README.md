# chem-customer-followup

把散落的微信截图、邮件、会议纪要、报价单，整理成一张**可执行的客户跟进卡**。
适用于任何化工品（纯碱、甲醇、钛白粉、树脂、助剂……），也适用于其他工业品内贸。

产出固定两件套：**Excel 工作簿（10 表）+ 自包含 HTML 卡**，另可加一份 Markdown 摘要。

---

## 一分钟上手

```bash
# 1. 拿一个最接近的案例，复制成自己的
cp -R examples/example-1-soda-ash-glass my-case

# 2. 只留 input.json，改写里面的内容（保留结构，改 meta.slug）
rm my-case/*.xlsx my-case/*.html my-case/*.md

# 3. 生成
python scripts/build_followup.py my-case/input.json -o my-case --md

# 4. 交付前自检
python scripts/selfcheck.py my-case/input.json --outdir my-case
```

## 环境要求

| 依赖 | 说明 |
|---|---|
| Python ≥ 3.10 | 3.10–3.14 均可用 |
| openpyxl | 生成 Excel 需要：`pip install openpyxl`；没有它时 HTML 仍可生成 |

Windows 上如果终端中文乱码，先设 `$env:PYTHONIOENCODING="utf-8"`。

---

## 它会做什么

| 步骤 | 产出 |
|---|---|
| 素材清点 | 每份素材一个证据编号（截图1…、邮件1…、纪要1…） |
| 时间线 | 正序逐条，七类标签，每条带出处 |
| **四类分层** | ① 客户明确需求 ② 客户异议 ③ 我方承诺 ④ 待确认（严禁混层） |
| 阶段判定 | 六阶段 + 停滞天数（as_of − 最后客户实质回复）+ 停滞分型 |
| 承诺闭环 | 逾期由截止日自动算，逾期项置顶提醒 |
| 字段确认 | 字段 / 提取值 / 出处 / 置信度 / 标记，逐条核对 |
| 下一步 | P0/P1/P2 动作 + 闭环标准 + 联动草稿（微信话术、通话提纲、拜访大纲、补传清单） |

**三条不可谈判的约束**：客户没说过的需求一个字不补；无法辨认的单独列；AI 摘要与事实物理隔离。

---

## 目录

```text
chem-customer-followup/
├── SKILL.md                 方法本体（Agent 读这个）
├── README.md                本文件
├── references/
│   ├── schema.md            数据契约：followup.json 全部字段
│   ├── extraction.md        素材解析规则 + 四类边界判定（20 个易混案例）
│   ├── stages.md            六阶段判定 + 停滞分型 + 化工原因库
│   ├── portability.md       装到其他电脑/Agent、跨平台坑
│   ├── qa.md                交付前 43 项自检清单
│   └── failure-log.md       失败模式：症状 → 病因 → 处方
├── scripts/
│   ├── build_followup.py    一条命令出全套（推荐入口）
│   ├── build_xlsx.py        生成 Excel（10 表）
│   ├── build_html.py        生成自包含 HTML
│   ├── validate.py          只校验数据
│   ├── selfcheck.py         交付前自检（数据+Excel+HTML）
│   └── _common.py           公共函数（配色、日期、停滞/逾期计算、校验）
└── examples/
    ├── example-1-soda-ash-glass/   纯碱 → 浮法玻璃（报价谈判 + 逾期承诺）
    ├── example-2-tio2-coatings/    钛白粉 → 涂料（合同条款僵持）
    ├── example-3-methanol-stalled/ 甲醇 → 甲醛（危化品，结构性停滞）
    └── _skeleton/                  最小可运行样例（复制它开始填）
```

每个 example 目录里都有：`input.json`（数据）+ `.xlsx` + `.html` + `.md`（成品），可直接对照。

---

## 安装到其他机器 / Agent

把**整个文件夹**放到平台的 skill 目录，名字保持 `chem-customer-followup`，`SKILL.md` 在根目录。

```powershell
# Windows
Copy-Item -Recurse -Force .\chem-customer-followup "$env:USERPROFILE\.agents\skills\"
```

```bash
# macOS / Linux
cp -R ./chem-customer-followup ~/.agents/skills/
```

| 平台 | 位置 |
|---|---|
| Codex / 通用 Agent Skills | `~/.agents/skills/chem-customer-followup/` |
| Claude Code | `~/.claude/skills/chem-customer-followup/` |
| 项目级（只给某项目用） | `<项目根>/.agents/skills/chem-customer-followup/` |
| chemclaw / workbuddy 等无 skills 目录 | 把 `SKILL.md` 导入系统提示或知识库，`scripts/` 留本机调用 |

装完验收：

```bash
cd ~/.agents/skills/chem-customer-followup
python scripts/build_followup.py examples/example-1-soda-ash-glass/input.json -o /tmp/verify --md
python scripts/selfcheck.py  examples/example-1-soda-ash-glass/input.json --outdir /tmp/verify
```

看到两个 `[ok]` 和 `[pass] 全部检查通过` 就装好了。

详细说明见 [`references/portability.md`](references/portability.md)。

---

## 三个示例演示什么

| 案例 | 产品 | 阶段 / 停滞 | 演示重点 |
|---|---|---|---|
| example-1 | 纯碱 → 浮法玻璃 | 报价谈判 / 5 天 | 价格差 70 元 + 账期卡点；**我方承诺逾期 5 天**；客户比价表被遮挡 |
| example-2 | 钛白粉 → 涂料 | 合同 / 2 天 | 只剩质量罚则与账期起算点；履约记录良好；年框量≠客户承诺 |
| example-3 | 甲醇 → 甲醛（危化品） | 停滞 / 7 天 | 客户长约未到期（结构性）；运输资质未闭环；**两条我方逾期** |

---

## 常见问题

**Q：能用在非化工品上吗？**
能。方法（素材 → 时间线 → 四类 → 阶段 → 动作）与行业无关，只有「该抓哪些字段」需要按品类调整，见 `SKILL.md` 里的化工品适配表。

**Q：客户/产品换了，要改脚本吗？**
不用。所有文案都在 `input.json`，脚本不硬编码任何产品信息。

**Q：Excel 和 HTML 数字不一致怎么办？**
说明有人手改了产物。只改 JSON，两个都重新生成。

**Q：停滞天数怎么算的？**
`as_of_date − 最后一次客户实质回复`。`as_of` 填今天，不是素材最后一天。催办不算推进，详见 `references/stages.md`。

**Q：可以只出 HTML 吗？**
可以：`python scripts/build_html.py input.json -o out.html`。但默认建议两个都给，Excel 便于筛选和内部流转。
