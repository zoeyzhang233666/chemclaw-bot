# chem-topic-research ｜ 化工品专题研究报告生成器

输入一个专题问题，输出一套**可被追问**的研究材料：交互式 HTML 报告 + 13 页 Excel 数据底稿 + 已确认提纲 + 执行记录。

产品无关、主题无关。纯碱能用，尿素、甲醇、PVC、钛白粉、碳酸锂也能用。

## 30 秒上手

```bash
# 1) 生成空白 case（也可以直接改 examples/soda-ash-2026/case.json）
python scripts/new_case.py --title "中国X行业新增产能对未来供应格局的影响" \
    --product X --audience industry-researcher --out case.json

# 2) 填提纲 → 出给用户确认
python scripts/build_md.py outline case.json --out 提纲_待确认.md

# 3) 取证、填数据后校验
python scripts/common.py validate case.json

# 4) 一键生成（可多受众）
python scripts/build_all.py case.json --audiences "产业研究员,管理层,销售,采购,研发" --outdir 交付物

# 5) 自检
python scripts/qa.py 交付物/
node   scripts/qa_dom.mjs 交付物/xxx.html
python scripts/qa_xlsx.py 交付物/xxx_数据底稿.xlsx
```

## 产出长什么样

| 文件 | 内容 |
| --- | --- |
| `*_<受众>.html` | 单文件离线报告。首屏 KPI + 核心结论；点结论→证据/计算/反证条件；点图表→原始数据表（可复制成 TSV）；章节可拖动排序；可导出 Markdown / 打印 PDF；三个视图（报告 / 研究框架 / 证据总表） |
| `*_<受众>_数据底稿.xlsx` | 13 页：使用说明、证据索引、原始数据、企业产能、项目台账、价格、产业指标、计算结果、结论、关键变量、资料缺口、章节大纲、质量自检 |
| `*_研究提纲_已确认.md` | 归档的提纲，逐章写着为什么存在 |
| `*_执行记录.md` | 研究流程、口径冲突处理、每条判断的形成过程、未取得的数据、自检、下一步 |
| `*_报告全文.md` | 纯文字稿，便于转发或粘贴进文档 |
| `build_report.json` | 构建清单与自检结果 |

## 目录

```
chem-topic-research/
├── SKILL.md                  # 技能入口：流程与硬性规则
├── references/               # 12 篇方法论（受众、取证、核验、分级、验收、反例…）
├── examples/
│   ├── soda-ash-2026/        # 纯碱完整案例（case.json + 五受众交付物 + README）
│   └── templates/            # 四类受众的提纲样例
└── scripts/
    ├── common.py             # 校验、索引、payload 组装（核心库）
    ├── new_case.py           # 空白 case 脚手架
    ├── build_all.py          # 一键生成
    ├── build_html.py         # HTML
    ├── build_xlsx.py         # Excel
    ├── build_md.py           # 提纲 / 执行记录 / 全文
    ├── qa.py                 # 交付物静态自检
    ├── qa_dom.mjs            # 页面运行时 QA（无头浏览器）
    ├── qa_xlsx.py            # 工作簿 QA
    └── templates/report.html # HTML 模板
```

## 这个工具的核心主张

1. **提纲必须先确认。** 章节按受众与问题定，不套固定目录；每章要能说清"为什么存在"。
2. **预计投产不等于新增供给。** 项目必须三态核验（已投产/在建/规划），净新增要扣置换，供给要乘爬坡率与时间权重。
3. **结论必须分级。** 事实 / 计算 / 解释 / 判断，判断必须有可观测的反证条件。
4. **缺口必须显式。** 拿不到的数据标出来、量化影响、写出下一步，不用"行业普遍认为"补位。
5. **一份数据，多种读者。** 管理层要判断与决策含义，研究员要推导与可复算口径。

## 依赖

- Python 3.9+，`openpyxl`
- Node.js（仅 HTML 运行时 QA 需要）
- Edge / Chrome（仅 QA 需要）
- 报告本身**零依赖**：无 CDN、无 echarts、无网络请求

## 验收

```bash
python scripts/qa.py examples/soda-ash-2026/交付物/
node   scripts/qa_dom.mjs examples/soda-ash-2026/交付物/纯碱_产业研究员_*.html
```

期望：`RESULT PASS`、`QA PASS`、图表全部渲染、0 JS 异常。

## 边界

产出研究结论与决策参考，不产出投资建议、价格承诺或生产计划保证。涉及交易策略、套利头寸时应明确说明不在范围内。
