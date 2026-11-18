# 化工品客户沟通润色（chem-message-polish）

把销售写不下去的一条微信／邮件，改写成**可直接复制发送**的版本——同时保证：
**一个没提供的价格、折扣、交期、库存、账期、承诺、客户需求都不新增**；拿不准的地方留成
`【待填】` 并登记责任人；最后交付一份 Excel 工作簿 + 一个可离线打开、可一键复制的 HTML。

适用于各类化工品（固体/液体/危化品/大宗农化/精细助剂/工业气体），换产品只换 `case.json`，
**方法和结果结构不变**。

---

## 它到底解决什么问题

销售的原话通常有三个毛病，而 AI 帮忙润色时最容易犯的是第四个：

| 毛病 | 例子 | 这套方法怎么处理 |
|---|---|---|
| 一次塞多个请求 | “样收到没？价格看了吗？什么时候能定？” | 一条消息只留一个请求，其余降级为陈述 |
| 越权承诺 | “价格可以再谈”“有什么要求都能提，我们一定配合” | 标红 → 改成“我先记下，核实后给您准话” |
| 无据施压／背书 | “货源紧张尽快定”“很多玻璃厂都在用” | 删除，替换为可核验表述（试烧结果、质检单） |
| **AI 自己编** | 补一个“合理”的价格、交期、账期 | **脚本级拦截**：任何未登记的“数字+单位”“承诺词”“稀缺话术”直接判 ERROR，不许生成产物 |

一句话：**润色是重新包装，不是补写。**

---

## 目录结构

```
chem-message-polish/
├── SKILL.md                    技能主文件（YAML frontmatter，含中文触发词）
├── AGENTS.md                   Codex 等读 AGENTS.md 的 agent 用
├── PROMPT.md                   不读文件的 agent：整段粘贴即可
├── README.md                   本文件：安装、移植、排错
├── config/
│   └── case.template.json      case.json 骨架（带逐字段说明）
├── references/
│   ├── 01-method.md            五步法、事实三分类、六个改写算子
│   ├── 02-boundary-rules.md    十类越界 + 合法替代 + 授权层级
│   ├── 03-product-profile.md   产品档案四问法 + 六大品类族速查
│   ├── 04-channel-tone.md      微信/邮件/电话/当面的硬约束
│   ├── 05-scenarios.md         九个高频场景骨架
│   ├── 06-audit-rubric.md      审计符号与举证标准
│   └── 07-qa.md                14 个校验码 + 人工复核 + 交付清单
├── scripts/
│   ├── caselib.py              读取/规整/边界守卫（纯标准库）
│   ├── validate_case.py        只校验，不出产物
│   ├── selftest.py             边界守卫自证：把好案例改坏 13 处，确认全被拦下
│   ├── build_workbook.py       case.json → 11 张表 xlsx
│   ├── build_html.py           case.json → 单文件 HTML
│   ├── check_outputs.py        产物自检
│   └── run_all.py              校验 → 生成 → 自检（一条命令）
└── examples/
    ├── 01-纯碱-浮法玻璃-报价跟进/    case.json + out/ + notes.md
    ├── 02-液碱-印染-催款/
    └── 03-尿素-复合肥-解释涨价/
```

---

## 环境要求

| 用途 | 要求 |
|---|---|
| 校验、HTML | Python 3.8+，**纯标准库**，零依赖 |
| Excel 产物 | 额外装 `openpyxl`：`pip install openpyxl` |
| 打开产物 | Excel / WPS / LibreOffice；HTML 任意浏览器，**无需联网** |

Windows 控制台若出现中文乱码，先执行 `set PYTHONIOENCODING=utf-8`（PowerShell：`$env:PYTHONIOENCODING="utf-8"`）。
脚本本身已尝试自纠 UTF-8 输出。

---

## 三十秒上手

```bash
cd chem-message-polish

# 0) 先自证：故意改坏 13 处，确认每一种越界都会被拦下
python scripts/selftest.py

# 1) 拿现成示例跑一遍，看产物长什么样
python scripts/run_all.py --case examples/01-纯碱-浮法玻璃-报价跟进/case.json \
                          --out  examples/01-纯碱-浮法玻璃-报价跟进/out

# 2) 复制骨架，开一个新案例
cp config/case.template.json my-case.json
#    改 meta / product_profile / facts / versions / audit …（见 SKILL.md 五步）

# 3) 校验（不出产物，改到 0 ERROR 为止）
python scripts/validate_case.py --case my-case.json

# 4) 一次出齐
python scripts/run_all.py --case my-case.json --out out
```

`run_all.py` 打印 `边界校验通过` + `自检：通过` 才算完成。

---

## 脱离本机，装到别的 agent 上

这个 skill 是**普通文件夹 + 标准库脚本**，没有平台绑定。四种搬法：

### A. 搬到 DSH / Claude Code（认 `SKILL.md` 的环境）

把整个 `chem-message-polish/` 目录放进该环境的 skills 目录即可。触发词已写在
`SKILL.md` 的 frontmatter 里：

> 客户微信润色 / 邮件润色 / 帮我把这段话改得体面点 / 客户不回消息怎么问 /
> 报价跟进的话术 / 涨价怎么通知客户 / 催款怎么说不得罪人 / 内贸销售话术

### B. 搬到 Codex 或任何读 `AGENTS.md` 的工具

把目录放进工作区，`AGENTS.md` 会被自动读取。它只描述“怎么做”，不依赖任何平台 API。

### C. 搬到 chemclaw / workbuddy 等只吃提示词的平台

1. 打开 `PROMPT.md`，把中间那段 **PROMPT 块**整段贴进该平台的系统提示词／自定义指令；
2. 同时把整个目录作为知识库／附件上传（让它能读 `references/` 和 `examples/`）。
3. 该平台若不能跑 Python，仍能产出完整文本：`PROMPT.md` 里规定了 Markdown 章节结构，
   与 Excel 的 11 张表一一对应。**不要让它跳过结构。**

### D. 直接给人用（不改任何代码）

把 `examples/01/out/` 里的 `.html` 发给同事：双击就能看，能复制、能打印，不联网。

---

## 产物里有什么

**Excel（11 张表）**
`00 使用说明`（含可复制的提示词框架）· `01 客户档案 + 产品档案 + 决策链` ·
`02 事实台账` · `03 版本横向对照` · `04 边界审计`（逐格判定 + 新增项必须为 0）·
`05 场景矩阵` · `06 占位符清单` · `07 快速调整指令库` · `08 发送前清单`（带下拉与自动计数）·
`09 追问应对` · `10 复盘看板`（含评分图）

**HTML（单文件）**
10 个章节，含微信气泡模拟、四版标签切换、指令点选即出结果、一键复制、清单勾选进度条、
打印样式。无 CDN、无外链、无追踪，可脱网、可内网转发。

---

## 换产品怎么改

只动 `case.json` 的两处：

1. `product_profile` —— 照 `references/03-product-profile.md` 的六大品类族速查填：
   形态、是否危化品、包装运输、验收指标、价格口径、下游痛点、**本品类禁语**（`ban_phrases`）。
2. `facts` —— 把这次的原话重新拆一遍。

`versions / audit / scenarios` 的结构一个都不用改，脚本会自动套用。

---

## 排错

| 现象 | 处理 |
|---|---|
| 控制台中文乱码 | 设 `PYTHONIOENCODING=utf-8` |
| `ModuleNotFoundError: openpyxl` | `pip install openpyxl`；只想出 HTML 时用 `build_html.py` 单独跑 |
| `UNSOURCED_NUMBER` | 正文有未登记的数字+单位。改 `【待填】`，或在 `facts` 里补上真实出处 |
| `BANNED_PROMISE` / `FAKE_SCARCITY` | 命中承诺词／稀缺话术黑名单，见 `references/07-qa.md` 的替换建议 |
| `PLACEHOLDER_MISMATCH` | 正文 `【待填】` 比 `placeholders` 条目多，补登记（含确认人） |
| `AUDIT_INCOMPLETE` | 有 fact 没进 `audit`，或某格判定为空 |
| `EMAIL_NO_SUBJECT` | 邮件版没写 `email.subject` |
| 自检报 `html id 重复` | `case.json` 里某字段被复用成了固定 id，检查 `versions.*.label` 是否含引号等特殊字符 |

**永远改 `case.json`，不要改脚本去迁就一份越界的稿子。**

---

## 不接的活

客户投诉／质量事故的正式回复、招投标文件、合同条款起草。这三类是责任文书，应走客诉流程或法务，
不要用润色工具硬套——`PROMPT.md` 与 `AGENTS.md` 都写明了这一点。

---

## 版本与免责

- 方法、模板、脚本：`chem-message-polish` v1.0
- 示例中的客户、联系人、金额、日期**均为虚构**，仅用于演示流程；唯一引用的真实信息为
  国家标准号与公开行业经验值，已在各示例 `notes.md` 中标注出处与适用范围。
- 商业条款一律以双方正式文件为准。本工具不产生、也不替代任何对外承诺。
