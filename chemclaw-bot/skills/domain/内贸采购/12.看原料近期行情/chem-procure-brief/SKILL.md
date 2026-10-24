---
name: chem-procure-brief
description: Use when a domestic chemical buyer needs a defensible read on where a raw material's price actually is before negotiating, approving a purchase, or explaining cost movement upward — 看原料近期行情 / 原料价格趋势 / 现在能不能下单 / 这个价贵不贵 / 上游煤价天然气涨了多少 / 区域调货划不划算 / 进口货合不合算 / 供应商说涨了是真的吗. Works for bulk chemicals, fine chemicals and intermediates of any chain (甲醇、纯碱、烧碱、尿素、钛白粉、丙烯酸、双氧水、苯酐、DOP、环氧乙烷、氯化石蜡、对苯二酚…). Delivers a self-contained interactive HTML dossier plus a 12-sheet Excel workbook in which every price carries point + spec + tax basis + delivery term + date + source, upstream/downstream links are proved by process route, verified events are separated from rumor, and every missing number is written out as a gap instead of estimated.
---

# 看原料近期行情（采购侧 · 通用技能）

> 这份底稿回答一个问题：**"这个价，我现在买的到底是贵还是便宜？凭什么这么说？"**
> 不回答"明天会涨还是跌"。任何预测性表述都是缺陷，不是加分项。

## 0. 30 秒决定用不用

| 触发场景 | 典型原话 |
|---|---|
| 询价前要一个底 | "甲醇华东现在什么价？我先摸一下底再谈" |
| 审批/汇报要出处 | "为什么这个月采购额涨了 30%？" |
| 供应商报涨价 | "供应商说煤涨了要提价，是真涨还是借口？" |
| 判断调货 | "内蒙比太仓便宜 800，是不是该从那边拉？" |
| 判断进口 | "进口 CFR 便宜，能不能用进口货替代？" |
| 复盘 | "9 月那波涨是我们买贵了，还是市场就这样？" |

**不适用**：要价格预测、要买点建议、要期货交易策略 → 明确拒绝并说明本技能只做事实陈述（见 `references/no-forecast-policy.md`）。

## 1. 铁律（违反任何一条，产出即作废）

1. **不预测。** 不写"预计""看涨/看跌""建议买入/观望""底部/顶部"。事后描述价格变化可以，前瞻判断不可以。
2. **六项口径。** 每条现货报价必须具备：**采购点 · 规格 · 价格区间 · 含税与否 · 提货方式（厂提/送到/库提）· 数据日期 · 来源**。缺项即在报告中列出缺失项，不得默认补齐。
3. **缺数就写缺口。** 拿不到＝写"缺口＋影响＋补齐路径"。不插值、不估算、不拿相邻品种顶替、不把缺值当 0。
4. **口径不同不相减。** 含税 vs 不含税、罐区 vs 出厂、现货 vs 期货、隆众 vs 金联创、人民币 vs 美元，一律分列并在文中说明换算条件；不换算就不做减法。
5. **产业链靠工艺自证。** 上下游必须能说出"哪条反应路线、单耗多少、占多少需求"。说不出来的，不能放进上下游（先放"待证"并标红）。
6. **传闻不进时间线。** 事件分四级：公开报道 > 机构观点 > 传闻 > 待确认。后两级只进"未采纳消息"区，且必须写明为什么没采纳。
7. **先后不是因果。** 事件日期早于价格变化，只能说"同期发生"。报告同时给出"事件日"与"首个报价响应日"，让读者自己判断。
8. **数据不分叉。** HTML 与 Excel 的所有数字都来自同一个 `data.json`，由脚本一次算出。手写数字＝错误。

## 2. 工作流（五步，每步都有可交付检查点）

```
① 定题  →  ② 采数  →  ③ 建链  →  ④ 核事件  →  ⑤ 出稿
   ↓          ↓          ↓            ↓            ↓
 一句话需求  六项口径表  工艺路线图   事件证据表   HTML+Excel+缺口清单
```

### ① 定题（10 分钟）
- 明确四件事：**品种 · 采购点（我到底在哪买）· 规格 · 时间窗**。
- 采购点决定一切：华东罐区买货的人关心太仓，西北煤化工企业关心坑口，华南关心广东；**不要用"全国均价"糊弄**。
- 写进 `meta`：`product / spec / region / unit / asof`。`asof` 是数据截止日，不是写作日。
- 参考 `references/price-data-standard.md` 的"采购点画像"清单。

### ② 采数（占 60% 时间）
按来源优先级取数（详见 `references/data-sources.md`）：

| 优先级 | 来源类型 | 拿什么 | 可信度标注 |
|---|---|---|---|
| A | 交易所/官方 | 期货日线、进出口海关、政策公告 | 高 |
| B | 专业资讯商日评（隆众/卓创/金联创/Mysteel/生意社） | 分区域现货区间、港口库存、开工率 | 中 |
| C | 期货公司日报/月报 | 现货表格（含基差）、成本模型、产业链开工 | 中 |
| D | 厂商公开报价/竞拍成交 | 出厂挂牌价、竞拍成交价 | 高（但只代表该厂） |
| E | 综合媒体报道 | 事件、检修、投产 | 按证据级别 |

- **抓数必带日期**：同一篇文章里引用"上周"的价，日期要落到具体某天，落不实就标"待更新"。
- **竞拍成交价 > 厂商挂牌价 > 媒体转述**。能用成交价校准挂价的，一定要用。
- 缺口当场登记，别等写报告时再回忆。

### ③ 建链（工艺路线自证）
只看这个品种**真实存在的工艺**，见 `references/chain-mapping.md`：
1. 先列**所有主流工艺路线**（例如某产品可能有煤基/油基/气基/生物基多条路线）；
2. 每条路线写清：主原料 → 关键中间体 → 产品，以及**单耗**（吨原料/吨产品）；
3. 再往下游：产品 → 直接下游（必须是它作为原料参与的反应），标注单耗与需求占比；
4. 逐条核对能否拿出证据；拿不出的标 `checked:false`，报告里标红并禁止外引。
5. **禁止机械罗列**：把"关联品种""同一板块的其他产品""同装置副产但无消耗关系"的品种塞进上下游，是本技能最常见的错误。

### ④ 核事件（四级证据）
见 `references/event-verification.md`。每条事件必须回答五问：
1. 什么时候发生（事件日）？
2. 谁说的（原始出处，能不能点开）？
3. 影响供给还是需求，量大不大（吨/年、占产能比）？
4. 同期价格往哪动、幅度多少（不带因果断言）？
5. 有没有相反证据或口径冲突？

### ⑤ 出稿
```
python scripts/build_all.py research.json --out out --name <品种>-<地区> --shots shots
```
一条命令完成：校验 → 装配 → HTML → Excel → 四项自检。四项全部 0 error 才可交付。

## 3. 交付物

| 文件 | 内容 | 谁看 |
|---|---|---|
| `<品种>-<地区>_原料行情底稿_采购.html` | 单文件离线看板（零外链，微信/邮件可直接发）：KPI 卡、区间带走势图（可点事件点）、区间涨跌与分位、六项口径报价表、区域价差、成本拆解、产业链自证、库存开工、事件时间线、可用事实与沟通话术、缺口清单 | 采购本人、老板、供应商沟通时截屏 |
| `<品种>-<地区>_原料行情底稿_采购.xlsx` | 12 表工作簿：封面结论 / 现货明细 / 报价序列 / 涨跌分位 / 区域价差 / 上游成本 / 下游需求 / 库存开工 / 事件时间线 / 可用事实与话术 / 缺口与来源 / 方法与字段口径 | 归档、审阅、二次加工 |
| `build/data.json` | 唯一数据源，HTML 与 Excel 都从这里生成 | 复核、改数后重出 |

HTML 首屏必须同时出现：**当前价（带日期与口径）+ 历史位置 + 一句话现状 + 最大缺口提示**。缺任何一个都是不合格的首屏。

## 4. 目录

```
chem-procure-brief/
├─ SKILL.md                        ← 本文件
├─ README.md                       ← 安装与快速上手
├─ references/
│  ├─ price-data-standard.md       六项口径、采购点画像、口径冲突处理
│  ├─ time-series-analysis.md      区间涨跌/分位/异常点/样本量纪律
│  ├─ chain-mapping.md             工艺路线自证法（通用，不含任何具体品种表）
│  ├─ event-verification.md        四级证据、事件五问、传闻处置
│  ├─ presentation-spec.md         HTML 与 Excel 的信息结构规范
│  ├─ data-contract.md             research.json 字段手册（唯一真源）
│  ├─ qa-checklist.md              交付前 40 项自检
│  ├─ no-forecast-policy.md        禁用词表与改写对照
│  └─ adapters.md                  各资讯源的抓取适配与解析要点
├─ examples/
│  ├─ README.md
│  ├─ research.template.json       空白模板（含注释性说明）
│  └─ 01-meoh-huadong/             完整跑通的实例（数据+产物+截图）
└─ scripts/
   ├─ build_all.py                 一键流水线
   ├─ validate.py                  契约校验（error / warn / info）
   ├─ assemble.py                  派生指标计算（唯一计算入口）
   ├─ build_html.py / build_xlsx.py
   ├─ check_html.py / check_xlsx.py / qa_render.py
   ├─ fetch_futures.py             期货日线（可选）
   ├─ common.py
   ├─ templates/dashboard.html     可改样式，不改结构
   └─ assets/echarts.min.js        内联用，保证离线
```

## 5. 换品种时改什么、不改什么

| 必须改 | 绝不能改 |
|---|---|
| `research.json` 全部内容（价格、链、事件、缺口） | `scripts/` 下的任何 `.py` |
| 输出文件名前缀（`--name`） | `data.json` 的字段名（HTML/Excel 依赖它） |
| 缺口清单（每个品种缺口都不一样） | 六项口径字段的语义 |
| 采购点列表 | "不预测"约束 |

**判断是否写死了某个品种**：搜索 `scripts/` 与 `templates/` 里是否出现具体品种名、具体区域名、具体工艺名。出现即为缺陷——链必须由 `research.json` 提供，工具只做校验与呈现。

## 6. 常见失败模式

| 现象 | 根因 | 修法 |
|---|---|---|
| 首屏价格和供应商报价差很多 | 口径不同（指数/成交/挂牌） | 保留数字，把口径写进同一条卡片的脚注 |
| 分位看起来很高/很低但样本只有 3 个 | 把稀疏报价当连续序列 | 报告里强制显示样本数；样本 <8 时加"样本很薄"说明 |
| 产业链被塞进无关品种 | 没做工艺自证 | 每条链路必须填 `evidence`；填不出就删 |
| 时间线像新闻聚合 | 没做证据分级 | 检修/复产/投产/库存/物流/政策/需求七类之外不放 |
| 报告被质疑"你怎么知道会涨" | 混入前瞻表述 | 跑 `validate.py`，禁用词会直接报 error |
| HTML 打开空白 | 数据里有引号或换行破坏 JSON | 只通过 `build_all.py` 生成，不手改 HTML |

## 7. 质量门（交付前必须全绿）

```bash
python scripts/build_all.py research.json --out out --name 品种-地区
# 期望输出末段：
# --- 静态自检：0 error --- / --- 工作簿自检：0 error --- / == 0 项失败
```
再对照 `references/qa-checklist.md` 逐条人工过一遍——脚本只能保证"没说错"，不能保证"说全了"。
