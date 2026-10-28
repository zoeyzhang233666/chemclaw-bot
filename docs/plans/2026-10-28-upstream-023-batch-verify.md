# 上游 0.2.3 整批验收

日期：2026-10-28。工作树：`upstream-capabilities` → 分支 `feat/57-model-defaults`（含 #50/#51/#54/#55/#57 栈）。
上游固定 `4a7b55069a`（v0.2.3）。原始 `D:/cursor-chembot` 未改；真实用户 `~/.dsh` 未触碰。

## 本批覆盖的草稿 PR

| PR | 主题 |
| --- | --- |
| #52 | 截图附件与旧历史可读 |
| #53 | 浏览器交接卡 |
| #56 | 插话未读与角色指令通知 |
| #58 | 桌面托盘后台运行 |
| #60 | 默认思考强度继承与 `list_bot_models` |

依赖链上更早的 #24/#27/#29/#43/#45/#47/#49 仍各自保留，不因本记录合入 main。

## 门禁结果

| 门禁 | 结果 |
| --- | --- |
| `chemclaw-bot` `npm test` | 1178 pass / 0 fail / 1 skip（Windows 尾空格既有跳过） |
| `node scripts/build-client.mjs --check` | 通过 |
| `npm run lint` | 通过（仅既有 warning） |
| `app` `npm test` | 199 pass / 0 fail / 1 skip |
| 隔离 mock smoke（`dev/bench-windows.mjs batch-023-1028`） | 51/51 通过 |
| `app/scripts/check-lifecycle.mjs` | 托盘隐藏/重开/重建/退出通过 |
| `check-packed --source --xlsx-preview-only` | 聊天交付卡侧栏网格渲染；应用正常退出 |

日志：`.chemclaw-tools/batch-*.log`。测试数据仅在 `.dsh-test-batch-023-1028` 与脚本自建隔离目录。

## 边界（未做 / 不做冒称）

- 不合 `main`、不发 Release、不生成新 EXE。
- 未做头像素材库（#59）；仍为计划中的低优先级项。
- 未重跑真实业务矩阵（甲醇等）；合成 mock / 平台门禁不冒称实源业务通过。
- DSH 对部分 openpyxl xlsx 的解析兼容问题沿用公开预览路径结论，不通过改写用户原文件或 patch DSH 绕过。

## 结论

平台与隔离路径门禁在 `feat/57-model-defaults` 尖端通过。整批仍以草稿 PR 形式等待人工验收与合入决策。
