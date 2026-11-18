# AGENTS.md

本目录是一个可移植 skill。任何 agent（Codex、Claude Code、ChemClaw、WorkBuddy、通用 CLI agent）按下面执行。

## 入口

1. 先读 `SKILL.md` 的“八条原则”“十步流程”“数据契约”。
2. 需要检索/核实方法，读 `references/research-playbook.md`；字段细节读 `references/data-contract.md`。
3. 研究结果只写进 `data.json`，不要手改 HTML/Excel。
4. 用脚本生成产物：

```bash
python scripts/validate.py <data.json>
python scripts/build_all.py <data.json> <outdir> --prefix <产品简称>
python scripts/qa.py <outdir>              # 可选，--node 可用时更完整
```

## 硬约束

- 不写“建议换成 X”“X 是最佳供应商”；输出排序、差异、风险、下一步。
- 候选必须是**生产企业**；贸易商/代理商不占第二源名额。
- 同集团/母子公司/同一实控人/纵向竞争必须写进 `same_source`，显著提示。
- 每个关键数字有 `sources[].id`；`待核实` 不能写成事实。
- 新装置/新工艺/非准入必须 `sample = 必须`，对应 `spec_status` 至少部分为 `试样`。
- 不把产能当产量、不把距离当运费、不把“全流程贯通”当“质量稳定”。
- 不编数据；查不到就写“未披露/待核实”，并在 `verify` 里列下一步。

## 最小工作流

1. 锁定产品/规格/现有供应商/收货地/月量/数据截止日。
2. 拆 9–15 项规格；建现有供应商基线。
3. 拉 15–30 家长名单，留 5–15 家；做身份/同源穿透。
4. 补运距/运费/产能/资质/公开风险（A/B/C）。
5. 填 `spec_status`；新装置/新工艺/非准入标“必须试样”。
6. 写 30/60/90 天动作。
7. `validate.py` → `build_all.py` → 打开 HTML/Excel 检查 → `qa.py`。
8. 交付时说明数据截止日、证据等级、缺口和“不替采购决策”。

## 产物

- 单文件 HTML：离线、可筛选、勾选 2–5 家对比、打印。
- 10-sheet Excel：说明/备选池/图表/横向对比/试样/同源/风险/行动/来源/尽调。
- `build_report.json`：数量、哈希、警告。

## 不要做

- 不要用 CSV/空文件冒充 xlsx；`openpyxl` 缺失就安装或明确报错。
- 不要改 `scripts/templates/` 来硬编码某个产品；产品差异只放 `data.json` / `meta`。
- 不要把示例 01 的研究结论套到别的产品；示例 02 是合成模板，不是研究。
- 不要联网构建；构建阶段不需要网络。
