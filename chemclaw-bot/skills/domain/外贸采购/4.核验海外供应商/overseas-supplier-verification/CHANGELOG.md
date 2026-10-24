# CHANGELOG

## v1.0.0 — 2026-10-20

首个版本。

### 新增
- `SKILL.md`：七步法总纲 + 五态口径 + 质量闸门。
- `references/`：10 篇方法文档
  - `method.md` 七步法详版
  - `entity-mapping.md` 四层主体拆解、六类交易结构、收款不一致三件套
  - `evidence-grading.md` 五态门槛、证据分级、冲突处理、时效规则
  - `country-registries.md` 30+ 国家官方登记入口与编号格式
  - `manufacturing-evidence.md` 制造关系取证、产能三口径
  - `document-checks.md` PI/CR/SDS/COA/BANK 逐项核对表
  - `risk-screening.md` 制裁/司法/供应/贸易救济检索法
  - `rfi-standard.md` 14 条英文询证标准条款 + 评价表
  - `data-contract.md` project.json 字段规范
  - `qa-checklist.md` 交付前自检
- `scripts/`
  - `ovslib.py` 五态词汇、证据分级、状态采集
  - `validate.py` 13 类规则校验（F01–F08、W01–W05、RFI）
  - `build_html.py` 单文件交互式报告（状态筛选、页内搜索、证据抽屉、打印）
  - `build_xlsx.py` 8 工作表工作簿（条件着色、数据验证、公式计数）
  - `build_all.py` 一键构建（校验 → HTML → Excel）
- `templates/project.template.json` 可运行空模板
- `assets/report-template.html` HTML 样式样板（无 Python 时可直接改）
- `examples/`
  - `example-01-saudi-meg` 沙特 MEG 生产商完整案例（23 条证据、5 份模拟件）
  - `example-02-saudi-tradeco-mock` 贸易商自称生产商反例

### 设计约束（不可改变的部分）
- **不输出风险分数、信用评级或低/中/高风险标签。** validate 会把评分字段判为阻断项。
- **模拟件永远不得进入「已核实」。**
- **收款主体与合同主体不一致只标注"需进一步验证"，不认定为欺诈。**

### 已验证
- 两个案例 `validate.py --strict` 全通过
- HTML DOM 测试 36 项、布局一致性 24 项、Excel 结构 28 项全部通过
- 校验器反向测试 9 项（悬空证据、无证据已核实、引用模拟件、评分字段、中文询证、缺矩阵、未知无缺口、缺摘录、正常项目）全部按预期拦截
