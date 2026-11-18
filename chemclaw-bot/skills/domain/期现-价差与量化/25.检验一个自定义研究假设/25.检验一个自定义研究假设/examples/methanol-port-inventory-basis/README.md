# 案例一：甲醇港口库存连降两周 → 基差走强（已完成）

## 假设原文

> 甲醇港口库存连续两周下降时，随后两周基差更容易走强。

## 结论

**样本不足，无法判断**（主口径）；**四个口径一致，均无正向显著证据**。

| 指标 | 数值 |
|---|---|
| 库存样本 | 228 周（2022-04-06 → 2026-10-14），逐条回源核验 228/228 通过 |
| 价格样本 | 1119 个交易日，0 缺失 |
| 主口径信号 | 10 个（状态转变去重 + 剔除窗口内换月） |
| 主口径对照 | 44 个 |
| 主检验 | 触发最小样本规则（信号≥12）→ 不报告显著性 |
| AM-1（每周计一次） | 24 个信号，均值差 −0.9 元/吨，p=0.9625 |
| AM-2（允许换月） | 19 个信号，均值差 +8.2 元/吨，p=0.8235 |
| AM-3（最宽松） | 48 个信号，均值差 +7.2 元/吨，p=0.6895，CI [−28.6, +42.9] |
| 事件研究 | 信号组 T−20…T−1 均值 +10.6，对照组 +3.3 → **选择效应明显** |

## 为什么样本只剩 10 个信号

| 剔除原因 | 条数 |
|---|---|
| 观察间隔不在 5–10 天 | 24 |
| 同一状态内连续周（去重） | 106 |
| 主窗口内发生近月换月 | 41 |
| 未来窗口不完整 | 1 |

228 周 → 95 个可评估状态 → 去重后 54 个事件 → 剔除换月后剩 54 个观测（10 信号 + 44 对照）。

## 怎么读这个结论

1. **不是「假设错」**，是「这批数据回答不了」。要回答，至少需要 12–20 个独立信号。
2. **放宽口径也没救**：把口径放到最松（48 个信号），效应量依然只有 +7 元/吨、CI 横跨 0。
3. **最值得注意的发现**：信号组在 T0 **之前**基差就已经比对照组高 7 元/吨。
   这说明「连降两周」往往出现在基差已经走强的阶段——它是**伴生特征**，不是原因。
   要检验因果，得换设计（例如用装置意外停车、进口到港延误做外生冲击）。

## 文件

```
data/port_inventory_weekly.csv     228 周真实库存（含 URL / provenance / verified_at）
data/100ppi_sf.csv                 1119 日真实现货/近月/基差
data/port_inventory_live.csv       本次实时爬到的 3 周（交叉校验用）
data/demo_weekly.csv               SIMULATED 演示数据（208 周）
build/research_design.formal.json  研究设计（v2.1，已确认冻结，含数据指纹）
build/research_design.formal.v2.0.prev.json  修订前版本（留档）
build/design_draft.json            假设解析草稿（含 8 个待确认问题）
build/data_audit.json              数据可用性审计
build/verification_full.json       228 条回源核验明细
build/results_real.json            正式检验结果（全量检验登记）
build/amendment.json               修订口径 AM-1..AM-3
build/event_study.json             事件研究路径
build/results_demo.json            模拟结果（SIMULATED）
out/研究假设检验_甲醇库存与基差.html   交互式研究页（单文件离线可开）
out/研究假设检验_甲醇库存与基差.xlsx   15-sheet 工作簿
```

## 复现

```bash
cd <skill>/scripts
python selftest_stats.py
python study_engine.py --design ../examples/methanol-port-inventory-basis/build/research_design.formal.json \
  --inventory ../examples/methanol-port-inventory-basis/data/port_inventory_weekly.csv \
  --price ../examples/methanol-port-inventory-basis/data/100ppi_sf.csv \
  --minute ../examples/methanol-port-inventory-basis/data/MA0_60min.csv \
  --out /tmp/results_real.json --samples /tmp/samples.csv --status REAL
```
