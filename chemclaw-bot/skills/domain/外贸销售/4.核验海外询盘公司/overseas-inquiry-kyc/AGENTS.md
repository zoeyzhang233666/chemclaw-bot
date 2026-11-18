# AGENTS.md · overseas-inquiry-kyc

本目录是一个可移植 skill。任何 agent（Codex / Claude Code / ChemClaw / WorkBuddy / 通用 CLI agent）按下面执行。

## 入口顺序

1. 读 `SKILL.md` 的「六条不可谈判的约束」「七步流程」「数据契约」。
2. 需要判断边界时读 `references/verdicts.md`；找来源读 `references/research-playbook.md`；
   不熟悉某国登记口径读 `references/country-playbook/`。
3. 研究结论只写进 `inquiry.json`。**不要手改 HTML / Excel**，它们由脚本生成。
4. 生成产物：

```bash
python scripts/validate.py   inquiry.json                 # 结构 + 纪律校验
python scripts/build_all.py  inquiry.json outdir --name 前缀  # 产出 HTML + XLSX + 回执
python scripts/selfcheck.py  inquiry.json --outdir outdir   # 交付前自检
KYC_RENDER_QA=1 python scripts/build_all.py ...            # 可选：带渲染 QA（需 playwright）
python scripts/pack_skill.py --skill-dir .                 # 打包 ZIP
```

## 硬约束（违反任何一条都算交付失败）

- **三分法**：每条结论必须是 `verified` / `discrepancy` / `unverified` 之一，不许只写一种。
- **查不到 ≠ 虚假**：公开渠道没覆盖，一律写「未核实」，禁止写「虚假 / 空壳 / 骗子」。
- **疑点要有具体矛盾**：`discrepancy` 必须写清 `doubts`（哪个字段和哪个字段对不上）+ `boundary`（为什么不算致命）+ `next_ids`（要哪份材料）。
- **已核实要有来源**：`verified` 必须挂 `source_ids`，且来源库里该条有 id。
- **同名隔离**：只有登记号 / NIB / SWIFT / LEI 等唯一标识相同才允许合并信息。`linkage` 里必须有 `name_collision` 条目。
- **不给概率**：不出现「诈骗概率 xx%」「大概率是骗子」；不以域名注册时间、网站新旧、邮箱后缀单独判真伪。
- **自述标 D 级**：邮件、名片、公司介绍 PDF 只能是 D 级线索，不能进结论。
- **模拟数据必须打标**：`meta.synthetic=true` 时必须有 `synthetic_note`，页面顶部会出现横幅。

## 最小工作流

1. 收料：邮件原文 / 名片 / 网站截图 / 证照 / 产品信息；缺什么先跑、别停下来问五个问题。
2. 提取字段写 `extraction`（照抄 + 标注出处），不确定的标 `confidence`。
3. 五区块核验写 `checks`（建议 16–30 条，A–D 区块各 3–8 条，E 区块写缺口汇总）。
4. 联系方式一致性写 `matrix` + `email_auth`；同名排查写 `linkage`。
5. 风险写 `risks`（事实 / 影响 / 动作分开）；资料清单写 `requests`（P0/P1/P2 + 英文表述）。
6. 行动写 `actions`；话术写 `messages`（英文，带 Subject）。
7. 边界写 `boundaries`；结论由脚本按规则生成 `verdict_line`。
8. `validate.py` → `build_all.py` → `selfcheck.py` → 人工复核来源链接。

## 产物

- 单文件 HTML：离线可开、可筛选（状态 / 区块）、可搜索、来源可点开抽屉、话术可复制、可打印。
- 14 表 Excel：封面 / 询盘原文 / 字段提取 / 注册主体 / 业务相关性 / 联系方式一致性 / 核验结论 / 公开风险 / 待索取资料 / 行动清单 / 状态透视 / 来源库 / 英文话术 / 方法与边界。
- `build_report.json`：校验结果、两个产物的 sha256、汇总统计。

## 不要做

- 不要用 CSV / 空文件冒充 xlsx；`openpyxl` 缺失就装或明确报错。
- 不要为了「看起来有结论」把未核实写成已核实。
- 不要把某个示例的研究结论套到另一个国家或另一个产品上（`examples/` 只演示方法）。
- 不要把真实企业包装成「曾向我方询盘」。示例里的询盘主体必须虚构。
- 不要在构建阶段联网；构建只读 `inquiry.json`。
