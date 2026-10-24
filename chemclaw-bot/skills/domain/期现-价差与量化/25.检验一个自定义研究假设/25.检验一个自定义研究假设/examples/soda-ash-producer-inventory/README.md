# 案例二：纯碱厂库连续累库两周 → 基差走弱（设计就绪，待数据）

## 状态

`DESIGN_READY` —— 研究设计已完成并可一键导出，**数据未接入**，因此没有任何结果数字。
本案例刻意不预填"看起来像真的"结果：没有可核验的完整厂库周度序列时，唯一诚实的输出就是
「设计已就绪，等待数据」。

## 假设

> 纯碱生产企业库存连续两周上升时，随后一个月纯碱基差更容易走弱。

## 设计要点

| 项目 | 取值 | 为什么 |
|---|---|---|
| 品种 | 纯碱（郑商所 SA） | 有期货、有主产区现货报价 |
| X | 生产企业库存（万吨，周度） | 与港口库存不同：厂库直接反映销售压力 |
| Y | Δbasis_20（重碱华东现货 − SA 主力） | 「一个月」比「两周」更贴合厂库传导节奏 |
| 信号 | UP2：ΔI>0 且 ΔI₋₁>0 | 与案例一镜像 |
| 窗口 | 20 个交易日（敏感性 10 日） | 需事前写死 |
| 入场 | 报告日收盘；发布时点不明则用次日 | 前视控制 |
| 对照组 | 非 UP2 周，且按库存分位带过滤 | 避免"库存高位时基差本来就在动"的混淆 |

## 这个案例的三个坑

1. **纯碱厂库与交易所仓单强相关**：厂库数据的边际变化常被仓单注册/注销反向抵消，
   只做均值差容易得到互相矛盾的结论 → 建议同时检验"厂库 + 仓单"的组合指标。
2. **2023 年后巨量新增产能**：供给结构断点明显，全样本合并会把两段完全不同的市场混在一起
   → 必须分年/分产能阶段呈现。
3. **重碱 vs 轻碱价差**：期货对标重碱，但不少报价是轻碱；混用会让基差系统性偏移。

## 导出设计

```bash
python examples/run_examples.py --example soda_ash --show-design
python examples/run_examples.py --example soda_ash --write /tmp/design_soda_ash.json
```

## 数据到手后的流程

```bash
python scripts/map_user_data.py --file 纯碱厂库.xlsx --out build/user_mapping.json
python scripts/run_hypothesis_test.py audit --design /tmp/design_soda_ash.json   # 改 data 段先
python scripts/approve_design.py --design /tmp/design_soda_ash.json --by 我 --data 纯碱厂库.csv SA.csv
python scripts/study_engine.py --design /tmp/design_soda_ash.json --inventory 纯碱厂库.csv --price SA.csv \
       --out build/results_soda.json --samples build/samples_soda.csv --status REAL
```
