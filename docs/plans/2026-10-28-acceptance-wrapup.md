# 验收收口（Excel 预览 / PPT / Linux / 业务）

日期：2026-10-28。工作树：`release-speed-next` → 分支 `fix/48-ppt-preview`。CMD `source.json` 已指向该树；验收基线备份为 `.chemclaw-dev/source.json.acceptance-backup`。

## Excel 聊天内预览（已修）

| 项 | 结果 |
| --- | --- |
| 根因 | openpyxl 等写出的 xlsx 含绝对 `Target="/xl/..."` 与空 `<patternFill/>`，DSH 侧栏 Excel 预览拒绝 |
| 修复 | `chemclaw-bot/runtime/normalize-xlsx.mjs`：需要时 ExcelJS 原地 round-trip；挂在 `present`、`chem_deliver`、artifact 打开路径 |
| 隔离验收 | `check-packed --source --xlsx-preview-only` 与 `--xlsx-openpyxl-preview-only` 均渲染侧栏网格 |
| 代价 | 规范化会丢掉图表/绘图/宏；数值与表名保留；失败时仍交付原文件 |

## PPT 预览（部分）

| 项 | 结果 |
| --- | --- |
| 合成 PPTX + LibreOffice / OfficeToPdf | 此前已能得到有效 PDF（见 `2026-10-27-ppt-preview.md`） |
| 对话 present 卡 → 侧栏真页 | 有 `--office-preview-only` 隔离路径；完整业务原报错文件仍缺脱敏样本 |
| 结论 | 不把“合成样例转换成功”当成用户原文件已验收通过 |

## Linux 打包门禁（阻塞）

见 `2026-10-28-linux-sharp-gate.md`。AppImage/deb 能打出；`checkSharp` 在 Electron+Linux 上 SIGSEGV。**不宣称 Linux 平台验收通过；不发版。**

## 真实业务（甲醇等）

按 `2026-10-27-cursor-acceptance.md`：业务数值只能来自实源；本批未重新跑完整派活/群聊矩阵。Excel 预览修复后，工作区已有甲醇交付 xlsx 可再点开验证侧栏；本记录不附带聊天原文或密钥。

## 未做

- 不合 `main`、不发 Release、不 push 强行合 #47
- 不恢复用户生产 `~/.dsh`；不碰 `D:\cursor-chembot` 技能库脏树
