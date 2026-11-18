# 检验库存和价格的关系 · Skill 包

跨 Agent 通用的研究技能包：判断某品种的**库存指标**是否对之后的**价格或基差变化**具有稳定的历史统计关系。

## 目录

```
inventory-price-relationship/
├── SKILL.md                          # 主入口：原则、流程、质量门、默认参数
├── references/
│   ├── 01-data-and-release-calendar.md       # 口径八问、真实发布时点、回填识别、缺口处理
│   ├── 02-inventory-series-construction.md   # 三种构建路径、周度归位、质检清单、口径变更
│   ├── 03-factor-construction.md             # 6 个因子、expanding 分位、基期后移、单位约定
│   ├── 04-grouping-and-inference.md          # 固定分组、9 个必报数字、块 bootstrap、HAC
│   ├── 05-stability-placebo-multiple-testing.md  # 分年度、regime、年度内置换、BH-FDR、共线性
│   ├── 06-report-and-workbook-spec.md        # 报告 12 节与工作簿 12 表规范
│   └── 07-pitfalls-checklist.md              # 6 大类陷阱 + 交付前自检清单
├── scripts/
│   ├── pipeline.py                   # 可配置全流程：因子→收益→检验→安慰剂→导出
│   └── build_outputs.py              # 通用 Excel 工作簿 + 交互式 HTML 报告生成器
├── templates/
│   ├── report_template_methanol_case.html    # 报告模板（甲醇真实结果填充）
│   ├── workbook_template_methanol_case.xlsx  # 工作簿模板
│   └── README.md                     # 如何换成别的品种
└── examples/methanol-port-inventory/
    ├── README.md                     # 完整案例：全部数字、方法、产业解释、限制
    ├── config.json                   # 品种参数（窗口、分位切点、变化阈值）
    ├── narrative.json                # 文字部分（结论、产业解释、限制）
    ├── build_outputs.py              # 一键出报告与工作簿
    ├── data/inventory_weekly.csv     # 228 周库存（asof, pub_ts, value, url）
    ├── data/prices_daily.csv         # 2614 日现货/期货/基差
    ├── result_panel.csv              # 因子与未来收益主表（可逐行核对）
    └── output/                       # pipeline 产物 + 生成好的报告与工作簿
```

## 快速开始

```bash
pip install pandas numpy scipy openpyxl

# 1) 全流程统计（约 1-2 分钟，含 2000 次安慰剂）
python scripts/pipeline.py --config examples/methanol-port-inventory/config.json

# 2) 出报告与工作簿
cd examples/methanol-port-inventory && python build_outputs.py
```

## 这套方法的核心承诺

1. **每个因子都能回答"当天算得出来吗"** —— expanding 分位、去年同 ISO 周、公布后首个交易日为基期
2. **每个显著性都给三层** —— 原始 p / HAC p / BH q，外加年度分层安慰剂 p
3. **每个结论都带失效区间** —— 分年度表与样本外检验，反向年份必须写出来
4. **每个数据缺口都留白** —— 不拼接不同口径、不插值伪造连续序列

## 参考案例结论（甲醇港口库存，2022-04 → 2026-10，228 周）

- 库存**绝对水平**对未来 1/2/4 周现货、期货、基差：|ρ|<0.12，p>0.11 → **几乎无预测力**
- 同期关系很强：时点分位 vs 基差率 **ρ=−0.781**（高库存 ⇔ 期货升水），但这是同期均衡，不是预测
- 唯一扛住三重检验：**连续 ≥2 周去库 → 之后 1 周现货 +1.11%**（安慰剂 p=0.0005），且仅在高库存区显著
- 但：2023 年方向相反、2026 年主导效应、BH-FDR 后 **0/54 组**显著、控制基差率后 |t| 降至 1.46
- 定性：**存在局部统计关系，未达稳定规律标准；不提供交易信号**

详见 `examples/methanol-port-inventory/README.md`。
