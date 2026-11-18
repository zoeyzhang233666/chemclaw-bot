# 示例索引（examples/）

| 案例 | 国家 | 产品 | 性质 | 目录 |
|---|---|---|---|---|
| **A** | 沙特阿拉伯 | 乙二醇（MEG） | **真实调查**，公开资料取证，含真实来源链接与访问状态 | `A_saudi_meg/` |
| **B** | 印度尼西亚 | 纯碱（Na₂CO₃） | **方法演示骨架**，故意保持"未取证"状态，企业为示意 | `B_indonesia_soda_ash/` |

## 案例 A：真实的完整链路

```
A_saudi_meg/
├── case_input.json                        # 采购口径与限定条件
├── case_output.json                       # 10 家主体 / 31 条证据 / 28 个来源 / 27 条问题
├── README.md                              # 真实检索过程、判断依据、踩坑记录
└── output/
    ├── 沙特乙二醇MEG海外生产商调查报告.html      # 交互式报告
    └── 沙特MEG海外供应商寻源工作簿.xlsx          # 12 个工作表
```

**结论概要**：A 级 6 家（SHARQ、JUPC、Yansab、Petro Rabigh、Yanpet、Saudi Kayan），B 级 1 家（Sipchem），C 级 2 家（Sadara、Petrokemya 为近似品/无 MEG 证据），D 级 1 家（SPDC 为销售主体）。

## 案例 B：证明通用性

```
B_indonesia_soda_ash/
├── case_output.json                       # 4 家示意主体，无 A 级
├── README.md                              # 迁移时需改什么、为什么"没有 A 级"是合法结果
└── output/
    ├── 印尼纯碱海外生产商调查报告_方法演示.html
    └── 印尼纯碱供应商寻源工作簿_方法演示.xlsx
```

**关键教学点**：全部为 B/C/D，**没有任何 A**——因为没做真实取证。这是正确状态，而不是"报告不合格"。

## 如何复制成新案例

```bash
python scripts/new_case.py "越南" "VNM" "钛白粉" "TiO2" "rutile 级，TiO2 ≥ 93%" examples/C_vietnam_tio2
# 然后填写 examples/C_vietnam_tio2/case_output.json，再运行：
python scripts/build_report.py  examples/C_vietnam_tio2/case_output.json   examples/C_vietnam_tio2/output/report.html
python scripts/build_workbook.py examples/C_vietnam_tio2/case_output.json  examples/C_vietnam_tio2/output/workbook.xlsx
python scripts/self_check.py    examples/C_vietnam_tio2/case_output.json
```

## 重要声明

- **案例 A 是真实调查**，但仍是"公开资料调查"，不是验厂；产能、认证、联系方式必须由企业书面确认。
- **案例 B 中的企业为示意**，不得用于真实采购。
- **不要**把案例 A 的企业清单当作"沙特 MEG 固定供应商库"。用户问别的国家/产品时，必须重新执行六步流程；问同一产品时，也必须重新核验证据（装置可能停车、股权可能变化）。
