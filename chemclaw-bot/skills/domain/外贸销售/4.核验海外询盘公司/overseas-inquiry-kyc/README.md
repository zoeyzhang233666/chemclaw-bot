# overseas-inquiry-kyc · 核验海外询盘公司

一个给**外贸销售**用的 skill：收到海外询盘后，判断对方公司能不能往下推——
把"这家公司是真的吗"拆成可以逐条回答的核验项，输出一份能拿给老板看的交互报告和一份能直接干活的 Excel。

> 核心主张：**证据不混层，缺失不越界。**
> "对方说了什么""官方登记的""互相矛盾的",是三种不同的东西，永远写成三种状态：
> **已核实 / 存在疑点 / 未核实**。

## 它解决什么

| 你的困境 | 这个 skill 给你 |
|---|---|
| 客户自称"我们做了 20 年、有两座窑" | 每一句自述都有对应核验项，能印证的写已核实，算不通的写疑点 |
| 只有一封邮件、一个手机号 | 生成 P0/P1/P2 资料清单 + 可直接复制发送的英文话术 |
| 不想得罪客户，又想知道底细 | 把要求写成"所有新客户的入档流程"，并给 NDA 并行方案 |
| 老板问"这客户靠谱吗" | 一句话结论 + 三分统计 + 每个疑点的边界说明 |
| 查不到外国公司注册资料 | 明确写"未核实（入口已知/未付费/需对方提供）"，**不写"虚假"** |
| 怕同名企业混进来 | 强制同名排查项 + "只有唯一标识相同才合并"规则 |

## 交付物

```
out/
├── 印尼重质纯碱询盘_模拟_核验报告.html    # 单文件交互报告，双击就开，离线可用
├── 印尼重质纯碱询盘_模拟_核验工作簿.xlsx  # 14 个表的工作簿
└── build_report.json                      # 构建回执（校验结果 + sha256）
```

**HTML**：封面结论 → 询盘原件（模拟数据带水印）→ 字段提取 → 注册主体识别 →
业务相关性 → 联系方式一致性矩阵 → 24 条可筛选核验结论 → 公开风险 → 资料索取清单 →
英文话术（可一键复制）→ 三分结论 → 来源库。
状态筛选、区块筛选、搜索、来源抽屉、打印样式全部内置。

**Excel**：`00_封面` `01_询盘原文` `02_字段提取` `03_注册主体` `04_业务相关性`
`05_联系方式一致性` `06_核验结论` `07_公开风险` `08_待索取资料` `09_行动清单`
`10_状态透视` `11_来源库` `12_英文话术` `13_方法与边界`。
带筛选、冻结窗格、状态底色、下拉选项。

## 快速开始

```bash
pip install -r requirements.txt

# 跑通示例
python scripts/validate.py   examples/id-soda-ash-demo/inquiry.json
python scripts/build_all.py  examples/id-soda-ash-demo/inquiry.json examples/id-soda-ash-demo/output --name 印尼重质纯碱询盘_模拟
python scripts/selfcheck.py  examples/id-soda-ash-demo/inquiry.json --outdir examples/id-soda-ash-demo/output

# 做自己的
cp templates/inquiry.skeleton.json my/inquiry.json
# 编辑 my/inquiry.json，然后重复上面三步
```

## 五区块核验框架

| 区块 | 回答什么 |
|---|---|
| **A 身份** | 是否真实存在？名称与登记是否一致？有无同名企业？自述背景能否印证？ |
| **B 业务** | 主营/产品目录/业务分类是否与询价产品相关？规模能否用产能反算通？ |
| **C 联系方式** | 官网、域名、邮箱、地址、电话五项是否自洽？发信渠道是否可核？ |
| **D 风险** | 经营异常、诉讼、制裁、负面报道、收款路径。 |
| **E 缺口** | 现有资料能否支撑正式报价？缺什么、按什么顺序要？ |

## 与其他同类工具的区别

- **不给概率。** 没有"诈骗风险 37%"这种东西。
- **查不到不判假。** 公开渠道未覆盖是常态，"未核实"是合格结论，不是失败。
- **疑点要有边界。** 每条疑点都必须写清"为什么它还不算致命"。
- **同名严格隔离。** 只有登记号/NIB/税号相同才允许合并信息。
- **自述永远是 D 级。** 邮件、名片、公司介绍不能进结论。
- **模拟数据必须打标。** 不把虚构主体包装成真实注册企业，也不让真实企业"被询盘"。

## 目录

```
overseas-inquiry-kyc/
├── SKILL.md                    # 入口：约束 / 流程 / 数据契约
├── AGENTS.md                   # 给通用 Agent 的执行约定
├── README.md
├── LICENSE  VERSION  CHANGELOG.md  requirements.txt
├── templates/
│   └── inquiry.skeleton.json   # 空白骨架
├── references/
│   ├── 00-quickstart.md        # 30 分钟上手
│   ├── research-playbook.md    # 检索式与多语种关键词
│   ├── evidence-grading.md     # A/B/C/D 证据分级
│   ├── verdicts.md             # 三分法边界案例
│   ├── mismatch-rules.md       # 12 类联系方式矛盾
│   ├── request-materials.md    # 索取清单与话术骨架
│   ├── product-fit-rules.md    # 纯碱/钛白/溶剂/树脂/化肥/锂电口径
│   ├── data-schema.md          # inquiry.json 字段说明
│   ├── portability.md          # 装到别的 Agent
│   ├── qa.md                   # 交付前清单
│   ├── failure-log.md          # 症状 → 处方
│   └── country-playbook/
│       ├── idn.md              # 印尼（AHU / OSS / NIB / KBLI / NPWP）
│       └── generic.md          # 20 国索引 + 通用五步法
├── examples/
│   ├── README.md
│   ├── _skeleton/              # 空白案例
│   └── id-soda-ash-demo/       # 印尼重质纯碱模拟询盘（完整）
└── scripts/
    ├── _common.py  validate.py  build_all.py  selfcheck.py
    ├── build_html.py  build_xlsx.py
    ├── check_xlsx.py  check_render.py
    ├── pack_skill.py
    └── templates/  report.html  style.css  app.js
```

## 换国家 / 换产品

- **换国家**：只改登记入口、官方链接、要哪份证照。见 `references/country-playbook/generic.md`。
- **换产品**：只改 `business_fit`（谁买、买来干什么、怎么反算、什么规格是惯例）。见 `references/product-fit-rules.md`。

核验框架、矩阵结构、三分法、话术结构**全部不变**。

## 边界

本工具输出**公开信息核验辅助材料**，不是法律尽调、资信评级或反洗钱最终结论。
所有"未核实"须以对方证照、银行资料、第三方核验或现场审核为准。
最终是否交易、是否给账期，由业务与风控决定。

## 许可

MIT。示例中的询盘企业为虚构主体，仅用于演示方法。
