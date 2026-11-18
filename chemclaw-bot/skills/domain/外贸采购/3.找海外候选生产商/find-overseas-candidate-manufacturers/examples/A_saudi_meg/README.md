# 案例 A（真实）：寻找沙特阿拉伯乙二醇（MEG）实际生产企业

> 这是一次**真实执行**的调查，不是编造的样例。所有证据均来自公开网页，并记录了访问状态（已核验全文 / 索引命中 / 直连失败）。
> 调查日期：2026-10-20。案例数据：`case_input.json`、`case_output.json`；交付物：`output/`。

---

## 一、输入（采购方原话）

> 我们准备从**沙特阿拉伯**进口**乙二醇（MEG）**到中国，请寻找公开资料显示可能实际生产该产品的海外企业。优先核验当地大型石化集团及其实际生产子公司，识别具体生产基地与产品能力，并区分集团销售主体与工厂主体。不得虚构产能、认证或企业联系方式，缺乏证据的字段保留待核验。

采购方未提供：批量、规格等级、认证要求、包装形式、到岸港 → 报告中全部标"未提供 — 需采购方补充"，并转成 QS-00。

## 二、执行过程（真实检索路径）

### Step 1 候选池：用工艺链条反推

MEG 必须有 **乙烯 → EO/EG 装置**。于是候选 = "沙特拥有乙烯或 EO 装置的综合石化企业"：

| 候选 | 为什么被列为候选 |
|---|---|
| SABIC 及附属（Sharq、United/JUPC、Yansab、Yanpet、Petrokemya、Saudi Kayan、SADAF） | 沙特最大石化集团，多套乙烯裂解 |
| Petro Rabigh | Aramco/住友化学炼化一体化 |
| Sipchem | Jubail 烯烃与衍生品综合体 |
| Sadara | Aramco/Dow 合资，标榜"首家生产 glycol 产品" |
| 平台挂牌卖家（ECHEMI、LookChem、Petrochemical.com 等） | 搜索结果中出现 |

### Step 2 取证：哪些证据真的说明了问题

| 企业 | 关键证据 | 来源与状态 | 判级 |
|---|---|---|---|
| **SHARQ**（东方石化） | 官网页面写明 MEG 名义产能 **1.38 Mt/a**，且"全部产品由 SPDC 和 SABIC 接收并营销"；另有 MEG 典型物性表（APHA≤5、水分≤0.1%、铁≤0.1ppm） | SPDC 官方页，**已核验全文** | A |
| SHARQ 装置级 | Sharq1 450 kt/a、Sharq2 450 kt/a、Sharq4 700 kt/a，2023-10 停车、2024 年复产 | CCFGroup/ChinaTexnet，已核验 | A（补强） |
| **United / JUPC** | 三星 E&A 项目页：Client = JUPC，EO/EG **700,000 MTPA**，EPC 完工 2021 | 承包商官网，已核验 | A |
| United / JUPC | SABIC 新闻稿（经 EOG Asia 转述）：EG-3 于 **2022-10 商业运营**，700,000 t/y | 媒体转述官方 Tadawul 文件，已核验 | A（补强） |
| **Yansab** | 企业官网 Products 表：MEG **700 KTA**、DEG 65、TEG 5 | 官网，**已核验全文** | A |
| Yansab | 东洋工程公告：700,000 MTPA EG 装置，Scientific Design 技术 | EPC 承包商公告，已核验 | A（补强） |
| **Petro Rabigh** | 产品页原文 "Petro Rabigh produces **600 KTA** of MEG" | 官网（WAF 403，**索引原文命中**） | A（标注需截图存档） |
| **Yanpet** | 东洋工程：420,000 MTPA（2000 年建成）；ICIS：520,000 t/y 装置；CCFGroup：Yanpet1 380 kt/a | 三来源**口径冲突** | A（产能标冲突） |
| **Saudi Kayan** | Industrial Info：设计 550 kt/a EO → **700 kt/a MEG** + 58 DEG + 3 TEG，Scientific Design 工艺，CTCI EPC | 项目报道，已核验 | A（置信中等） |
| **Sipchem** | Affiliates 页只列甲醇/BDO/醋酸/VAM/EVA/PBT，**无 MEG**；2006 年综合体公告也未列 MEG | Sipchem 站 403 + Arab News 已核验 | **B** |
| **Sadara** | 官网称首家生产"Glycol Products"，但产品实为 **丙二醇/丁基乙二醇醚/聚醚多元醇**，26 套装置无 MEG | 官网已核验 | **C** |
| **Petrokemya** | 产品为乙烯/PE/丁烯-1/丙烯/VCM/PVC/ABS，乙烯装置与 Sharq 共建，**无 MEG** | 装置汇编 + 综合体概况 | **C** |
| **SPDC** | 日方联合体，"接收并营销 SHARQ 约 1/3 产品，主要销往中国、印度、日本、东南亚"，**自身无装置** | 官网已核验 | **D**（销售主体） |

### Step 3 关键判断（这次调查最有价值的部分）

1. **SPDC 不是工厂，但可能正是对华的实际窗口。** 这是最容易误判的一环：它在英文资料里和 SHARQ 高度绑定，中文采购名单里常被当成"日本某生产商"。结论是：识别为**销售主体**（D），同时提示采购方"若要发询盘，SPDC 与 SABIC 都是真实可用的通道"。
2. **Sadara 是关键词陷阱**：自称 glycol producer，实际是 PG / 丁基乙二醇醚 / 聚醚多元醇。判 C，并保留在报告右栏作为防误判记录。
3. **Petrokemya 的迷惑性来自反倾销名单口径**：欧盟/沙特相关 MEG 名单里会把它一并列名（集团关联方混列），但产品清单里没有 MEG。判 C。
4. **Sipchem 只能到 B**：它是真实的大型石化企业，但公开资料里找不到 MEG 装置。**不能因为"它很大、它在 Jubail、它做石化"就判 A**——这正是本 Skill 要阻止的推理。
5. **Yanpet 产能自相矛盾**（380 / 420 / 520 / 660 kt/a）。正确处理：**不取平均值，不选"最合理"的那个**，而是把四个数字并列写进"口径冲突"，并转成 QS-18。
6. **公开产能 ≠ 可供货**：CCFGroup 记录了 2024 年 Sharq1/2/4、Yanpet1、JUPC2 的多次停车与复产。所以每家都必须回答"现在能不能供货"，不能拿 700 kt 的设计值当可售量。

### Step 4 结果

| 等级 | 数量 | 企业 |
|---|---|---|
| A | 6 | SHARQ、JUPC、Yansab、Petro Rabigh、Yanpet、Saudi Kayan |
| B | 1 | Sipchem（身份待核验） |
| C | 2 | Sadara、Petrokemya（近似品/无 MEG 证据） |
| D | 1 | SPDC（销售主体） |

生产商栏 7 家（A+B），贸易/销售栏 3 家（C+D，均带"为什么不能当工厂"说明）。

### Step 5 市场背景（用于说明为什么要找工厂）

- 2024 年中国 MEG 进口 655.4 万吨，**沙特 338.2 万吨占 52%**，为第一大来源国（CCFGroup）。
- 同年沙特多套装置因负现金流减产停车（Yanpet1、JUPC2），说明"产能大≠供货稳"。

## 三、产出

- `output/沙特乙二醇MEG海外生产商调查报告.html` —— 交互式报告（筛选、分栏、证据链、询证按钮）
- `output/沙特MEG海外供应商寻源工作簿.xlsx` —— 12 个工作表
- `case_output.json` —— 28 个来源、31 条证据、27 条询证问题

## 四、这次调查暴露的方法论要点（已写回 Skill）

1. **抓取失败是常态**：sabic.com 重定向、petrorabigh.com / sipchem.com 被 WAF 拦。必须记录"索引原文命中，需二次存档"，并在判级说明里标注。
2. **数字是最好的检索词**：`700,000 t/y`、`600 KTA` 这类具体数字比产品词更容易命中装置页/EPC 页。
3. **EPC 承包商名录是金矿**：三星 E&A、东洋工程的项目页直接给出"客户 + 产能 + 工艺 + 完工年"，是本案例 A 级证据的主干。
4. **官网 affiliates 列表可用于证伪**：Sipchem 的 affiliates 列表没有 MEG 附属，本身就是强证据。
5. **口径冲突要保留**：Yanpet 的四个数字，是后续谈判中最有用的问询点。
