# 验收收口（Excel 预览 / PPT / Linux / 业务）

日期：2026-10-28。工作树：`release-speed-next` → 分支 `fix/48-ppt-preview`。CMD `source.json` 已指向该树；验收基线备份为 `.chemclaw-dev/source.json.acceptance-backup`。

## Excel 聊天内预览（2026-10-28 修订：保留上游路径）

| 项 | 结果 |
| --- | --- |
| 根因 | openpyxl 等写出的 xlsx 含绝对 `Target="/xl/..."` 与空 `<patternFill/>`，DSH 侧栏 Excel 预览拒绝 |
| 处理 | 撤销额外的原地 ExcelJS round-trip 及三个调用入口，直接交给 DSH 原生只读预览 |
| 上游依据 | DSH `dsh-v0.2.1-rc.3` 的 `packages/client/ui-sidebar-documentpreview/src/client/excel/xlsx.ts` 与 `xlsx-archive.ts` 只在浏览器内存中处理预览字节，不重新保存源文件；Bot 上游无此原地规范化模块 |
| 回归 | `present` 中间件及精确路径/嵌套文件名解析后，带公式和模拟图表、绘图、VBA 载荷的合成 XLSX 与原始字节完全一致 |
| 限制 | 当前 DSH 对部分 openpyxl 文件仍有解析兼容问题；不再以有损转换声称修复。需由 DSH 正式修复后升级，不修改 DSH 安装源码；原文件可在外部应用打开 |

本次验证：插件测试 1148 通过、1 项既有 Windows 跳过；生成客户端一致性及 lint 通过（仅既有 warning）；fresh mock smoke 全部 51 步通过。`check-packed --source --xlsx-preview-only` 从实际聊天卡片打开侧栏网格并检查源文件字节未变，应用正常退出。移除依赖未跟踪本地样本的 openpyxl 专用验收标志，避免用不可复现的样例声称兼容性已修复。

## PPT 预览（部分）

| 项 | 结果 |
| --- | --- |
| 合成 PPTX + LibreOffice / OfficeToPdf | 此前已能得到有效 PDF（见 `2026-10-27-ppt-preview.md`） |
| 对话 present 卡 → 侧栏真页 | 有 `--office-preview-only` 隔离路径；完整业务原报错文件仍缺脱敏样本 |
| 结论 | 不把“合成样例转换成功”当成用户原文件已验收通过 |

## Linux 打包门禁（已通过）

见 `2026-10-28-linux-sharp-gate.md`。官方 sharp WASM 后端已修复 Electron/Linux 原生 GLib 冲突；PR #47 的 Ubuntu x64 任务已通过打包、图像处理、deb 安装/更新、AppImage 自动更新哈希与卸载。仅记录平台验收，不合并整批功能或发版。

## 真实业务（甲醇等）

按 `2026-10-27-cursor-acceptance.md`：业务数值只能来自实源；本批未重新跑完整真实业务矩阵。不以现有文件经过有损转换后的预览作为验收依据；本记录不附带聊天原文或密钥。

## 未做

- 不合 `main`、不发 Release、不 push 强行合 #47
- 不恢复用户生产 `~/.dsh`；不碰 `D:\cursor-chembot` 技能库脏树
