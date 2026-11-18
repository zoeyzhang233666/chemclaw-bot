---
name: benchmark-lead-sourcing
description: Use when a sales rep has one or more benchmark customers and wants a second batch of look-alike prospects for a chemical product — extract the benchmark's business features (product mix, process route, downstream market, scale, value-chain position, site/cluster), then find factories that are similar on those features and explain, per company, which feature matches and why that match implies the same raw-material demand. Triggers 标杆客户 / 相似客户 / 复制成功客户 / 潜客池 / 内贸销售找客户 / 化工品下游客户 / lead list for a chemical. Delivers a 5-sheet Excel workbook plus a self-contained single-file HTML benchmark-profile & replication report (filterable, print-to-PDF ready), every lead carrying a clickable evidence trace.
---

# 标杆客户复制 · 下游潜客池（化工品通用版）

把一个成功的标杆客户，复制成一批**业务特征相似、因而会产生同类原料需求**的新客户。
整个 skill 围绕两个词：**trace（每条线索有可点开、可在电话里复述的出处）** 和 **similarity（每条线索说清相似点落在哪一项、为什么这会导致相似的原料需求）**。

产品可以是任何化工品（纯碱、烧碱、钛白粉、柠檬酸、环氧乙烷、DMC、磷酸铁锂前驱体……）。研究思路与结果结构固定，**只有配置是产品的**：产品名、别名、标杆客户、区域、lane 划分、用量强度规则、品类归并、证据话术。

## 0. 适用与不适用

- 适用：有明确标杆客户（或一段成功成交经验）的 B2B 化工原料内贸销售；目标是「下一批该打谁」。
- 不适用：纯陌生开发（无标杆）、面向消费者的产品、需要联系人与电话的数据（本 skill 不产出联系人，见 `references/output-structure.md` 边界说明）。

## 1. 四件输入（缺一不可）

| 输入 | 说明 | 示例 |
|---|---|---|
| 所售产品 | 化工品名称 + 规格/级别（有几个级别就写几个） | 纯碱（重质/轻质、食品级、药用级） |
| 标杆客户 | 一家（或几家）真实成交客户，尽量选上市公司或公开资料多的 | 旗滨集团（601636，浮法+光伏玻璃） |
| 目标区域 | 具体国家/区域/省份，不要「全球」 | 华东：鲁/苏/浙/皖/沪 |
| 交付物 | 默认 Excel + HTML；可只出 Excel | Excel 潜客表 + HTML 画像与方法论报告（单文件，浏览器打开，可打印成 PDF） |

用户没给全就用 `ask_user_question` 一次问全，带推荐项。若用户上传了历史成交客户表，把它当作**多标杆输入**（分别画像，取相似性判据的交集）。

## 2. 九步工作流（主 agent 只做编排，重活交给 lane 子代理）

```bash
# ① 建档：把输入写成 project.json（唯一事实来源）
python scripts/new_project.py --dir work/<项目> --product "纯碱" --benchmark "旗滨集团" --region "华东:山东,江苏,浙江,安徽,上海"

# ② 画像：研究标杆客户六要素，写入 benchmark_profile.json（含证据 URL）
# ③ 画图：在 project.json 里写 8–12 条 lane（用碱工序 / 用量强度 / 候选企业 / 集聚地 / 检索关键词）
# ④ 生成 lane brief：把六件套模板批量实例化，省掉每条 brief 的重复文字
python scripts/make_lane_briefs.py --dir work/<项目>

# ⑤ 铺 lane：每个 brief 起一个子代理（并发 ≤8），产出 leads_raw/NN_*.json
# ⑥ 体检：结构、缺字段、区域越界、置信度枚举
python scripts/validate.py --dir work/<项目>

# ⑦ 抽检：先生成抽检清单，再核链接（≥40 条），结论写 leads_raw/_qa_report.json
python scripts/merge_leads.py      --dir work/<项目> --make-qa-todo
python scripts/fetch.py check --file work/<项目>/leads_raw/_qa_todo.json \
       --out work/<项目>/leads_raw/_qa_report.json

# ⑧ 合并 + 出表 + 出报告
python scripts/merge_leads.py       --dir work/<项目>
python scripts/build_workbook.py    --dir work/<项目>
python scripts/make_html_report.py  --dir work/<项目>

# ⑨ 交付体检：条数守恒、gate 结论、四块报告内容是否齐全
python scripts/check_project.py --dir work/<项目>
```

每一步的完成判据、失败修法与并行纪律见 [`references/workflow.md`](references/workflow.md)。

## 3. 相似性框架（本 skill 与「工商行业门类匹配」的根本区别）

标杆客户的业务特征拆成**五个可判定维度**，每家候选企业逐一判定命中哪几项，并解释该维度为何决定原料需求：

| 维度 | 判据 | 为什么相似 → 相似原料需求 |
|---|---|---|
| 产品结构 | 最终产品是同一化学体系/同一配方骨架（如钠钙硅玻璃、硅酸盐、钠盐） | 配方里必须有该组分，产品不变则原料需求结构不变 |
| 工艺路线 | 该原料以「助熔剂 / 化学计量反应物 / 中和成盐剂 / 脱硫剂」身份进入主流程 | 替代会造成质量或收率损失，属刚性消耗 |
| 下游市场 | 下游行业对原料无替代，且决定开工率 | 开工率决定消耗节奏与补库周期 |
| 规模 | 单厂年用量数百吨以上，有自有窑炉/反应装置 | 用量规模决定其必然走厂家直采 + 长协 |
| 产业链位置 | 中游加工制造厂，对该原料是纯采购方（不是贸易商，更不是同行） | 决策在工厂端、用量可预测，成功打法可复制 |

维度得分按项目实例化（产品不同，判据措辞不同）：见 [`references/similarity-framework.md`](references/similarity-framework.md)。
**只用单一弱维度（例如仅下游市场相同、自己并不消耗该原料）的企业，剔除或降为低优先级。**

## 4. 五道 gate（每一道都能否决一条线索）

1. **trace gate**：抓不到出处的，`来源` 写 `未核实`、`置信度` 写 `低`。猜一个像样的官网域名比留空有害得多。
2. **subject gate**：写入 URL 前确认页面内容与公司名一致；302 到反诈页/影视站/博彩站的域名一律弃用。
3. **peer gate**：**自己也生产该产品的公司是同行，不是客户**，必须剔除并在报告里列名。
4. **link gate**：抽检链接可达性与主体一致性，不删除、只标注（反爬 ≠ 坏链）。
5. **dedup gate**：归一化公司名跨 lane 去重，保留置信度更高的一条。

公式与阈值（优先级 = 用量强度 × 证据置信度）见 [`references/gates.md`](references/gates.md)。

## 5. 交付物结构（固定）

- **Excel**：① 标杆客户画像与复制逻辑 ② 说明与行业地图 ③ 客户线索总表 ④ 重点客户TOP ⑤ 分布统计。
  总表列：序号/行业板块/细分行业/公司名称/所在地/用量强度/需求点（用料工序）/**相似维度（相似点落在哪一项）**/**为什么会产生相似原料需求**/规模线索/优先级/置信度/线索来源。
- **Word/HTML 报告**：0 摘要 → 1 标杆画像（六要素表 + 证据）→ 2 相似性判据（五维表）→ 3 应用地图与 lane 设计 → 4 潜客池与重点客户 → 5 证据与置信度分级 → 6 被剔除名单（同行/工艺不符/弱相似三类）→ 7 缺口与负结果 → 8 可复制动作清单（SOP）。
  **报告格式固定为单文件 HTML**（内联 CSS/JS、零外链、离线可开）：带关键词搜索与板块/省份/优先级/置信度/相似维度筛选、行数实时统计、打印样式（浏览器「打印为 PDF」即得分发包）。

字段级定义与文件清单见 [`references/output-structure.md`](references/output-structure.md)。

## 6. 三条不可谈判的纪律

1. **先落盘、再汇报**：子代理上下文是易耗品，一次读入大 JSON 就会杀死一个 lane。lane 必须每 5 条增量落盘，回复只给一句概况。
2. **不许编造**：公司名、产能数字、URL 三者任一编造，整张表就废了。核不到就如实写「未核实/低」。
3. **同行名单必须出现在报告里**：用户需要知道「已经排掉了谁」，否则他会自己再查一遍。

## 7. 环境适配

- 宿主 agent 有原生联网工具（web_search / web_fetch / browser）→ **优先用它发现企业、打开官网**（这是发现新企业的主要来源）。
- 结构化取证（上市公司公告全文检索、交易所资料页、批量链接抽检）→ 用自带 `scripts/fetch.py`（**仅依赖 Python 标准库**，Windows/macOS/Linux 通用），命令见 [`references/evidence-channels.md`](references/evidence-channels.md)。
- 宿主没有联网工具、也没有 Python → 退化为「模型产业知识 + 用户在浏览器里代抓」，仍可产出带置信度分级的名单，但报告里必须写明这一限制。
- 各 agent（chemclaw / workbuddy / Codex / Claude Code / DSH）的安装与能力映射见 [`README.md`](README.md) 与 [`references/porting-to-other-agents.md`](references/porting-to-other-agents.md)。

## 8. 环境依赖

| 步骤 | 依赖 |
|---|---|
| fetch / validate / merge / new_project / make_lane_briefs / check_project | 仅 Python 3.8+ 标准库 |
| build_workbook | `openpyxl` |
| make_html_report | 无（纯标准库生成单文件 HTML） |
| install.py | 无（纯文件复制） |

缺 `openpyxl` 时先跑其余步骤，或 `pip install -r requirements.txt`。HTML 报告无第三方依赖，任何机器都能出。
