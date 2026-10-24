# 样例：重质纯碱 → 印度尼西亚，CIF

> ⚠️ **本合同为模拟文本（SIMULATED）**，公司名、地址、账号、签字人均为虚构。
> 仅用于演示与测试本 Skill，不可作为真实交易文件使用。

## 场景

| 项目 | 内容 |
|---|---|
| 合同编号 | `ZJSA-2026-0417-SIM` |
| 日期 | 2026-04-17 |
| 我方身份 | **卖方（seller）** — 江苏海盐化工进出口有限公司（虚构） |
| 交易对手 | **买方** — PT Nusantara Soda Prima，印度尼西亚雅加达（虚构） |
| 产品 | 重质纯碱 Heavy Soda Ash (Dense Sodium Carbonate) |
| HS 编码 | 2836.20.00 |
| 数量 | 1,000 MT，±10% |
| 单价 / 总额 | USD 268.00 / MT ・ USD 268,000.00 |
| 贸易术语 | **CIF Jakarta (Incoterms 2020)** |
| 装运港 | 天津新港 |
| 付款 | 即期不可撤销信用证 |
| 结构 | 16 章 + 附件 A/B/C |

## 这份合同「坏」在哪

不是随便写的坏，是**照着真实外贸合同的高频坑**写的。主要埋伏：

| 类型 | 例子 |
|---|---|
| 日期不自洽 | 6.1(B) 要求信用证不晚于 4 月 15 日开出，但合同 4 月 17 日才签 |
| 救济被掏空 | 逾期付款只按 5% 年息计，且明文放弃中止履行、扣单、解约 |
| 责任不对等 | 卖方责任封顶 5%，买方无上限 |
| 检验失衡 | 以卖方自有实验室报告为最终依据，同时禁止买方委托第三方检验 |
| 异议期过短 | 提单日后 7 天，而航程约 3 周 |
| 质量标准开口 | 「并入买方装运前另行通知的要求」，且「装运后规格可单方修改」 |
| 术语自相矛盾 | 写 CIF，又声明卖方「无须在装运港以外任何地点交货」 |
| 单方延期 | 「因任何原因延误，买方应接受卖方自行确定的延展期」 |
| 举证不可能 | 要求买方证明「装船时即不符」，同时剥夺装船前检验权 |
| 争议解决单边 | CIETAC / 北京 / 中文 / 独任仲裁员由秘书长指定 |
| 议价权单边 | 成本上涨 15% 卖方即可要求重新议价，谈不成可无责解约 |
| 语言版本 | 仅英文，且声明无需印尼语版本（印尼有本地语言要求） |
| 危险货物 | 单方声明「双方确认非危险货物」，无任何依据文件 |
| 缺失条款 | 迟延交付违约金、产品责任、出口管制/制裁/反倾销、争议期间付款、保密、留样、包装性能等 |

## 产出

审阅共识别 **38 条问题**（R-01 … R-38），其中：

- 按等级：高风险 / 中风险 / 低风险
- 按主题：付款 / 交付与运输 / 质量与检验 / 索赔与责任 / 合规与单证 / 争议解决与效力 / 条款缺失
- **69 处原文锚点**，全部逐字校验通过
- **144 条确认事项**，可直接分工

## 文件说明

| 文件 | 说明 |
|---|---|
| `contract_source.txt` | 模拟合同原文（带标记语法，可直接编辑） |
| `contract_parsed.json` | 解析结果（221 个块，每块有稳定 id） |
| `data_meta.json` | 元信息（我方身份=卖方、产品、术语、金额等） |
| `data_issues_01..04.json` | 38 条问题的完整数据 |
| `review.html` | **交互报告**（双击打开）：双栏对照、点击定位、主题筛选、填写与导出 |
| `review.xlsx` | **审阅工作簿**（9 页）：条款索引、问题清单、确认事项、缺失条款等 |

## 复现

```bash
cd examples/soda-ash-indonesia-cif

python ../../scripts/parse_contract.py contract_source.txt contract_parsed.json

python ../../scripts/qa_report.py --parsed contract_parsed.json \
    --issues "data_issues_0*.json"

python ../../scripts/build_report.py contract_parsed.json data_meta.json \
    data_issues_0*.json --out review.html

python ../../scripts/build_workbook.py contract_parsed.json data_meta.json \
    data_issues_0*.json --out review.xlsx
```

## 换成自己的合同

1. 复制本目录为 `examples/<你的项目>/`
2. 用 `templates/contract_markup.md` 的语法把合同抄成 `contract_source.txt`
3. 改 `data_meta.json`（**`our_role` 必填**：`seller` 或 `buyer`）
4. 重写 `data_issues_*.json`（旧锚点会失效，必须重做）
5. 跑上面的四条命令，`qa_report.py` 全绿后再交付

> 改了合同文本就必须重新 `parse_contract.py`——
> 块 id 里含序号，段数一变，后面全部位移。这是刻意设计：逼你重跑校验。
