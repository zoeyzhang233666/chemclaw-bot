# 真实业务交付验收记录（第 1 项 P0）

- 记录时间：2026-10-27
- 固定基准：`fix/40-remove-answer-budget` / `1221af14` / [PR #41](https://github.com/zoeyzhang233666/chemclaw-bot/pull/41)
- 验收工作树：`D:\OpenWorker\openworker\.worktrees\cursor-acceptance\cursor-chembot`（分支 `test/40-acceptance-baseline`）
- 环境类型：CMD 开发预览（`scripts/launch-chemclaw.mjs --source <验收工作树>`）
- 开发数据：`D:\cursor-chembot\.chemclaw-dev`（隔离于用户 `~/.dsh` / 安装版）
- 产品版本号：bot/app `0.2.2`（与安装包同号不代表同一构建；以 revision 为准）
- 连接器：`chem-data-hub`（已配置；本记录不写密钥）
- Computer Use：不可用；改为人工操作 + 助手观测工作区产物（模式 B）
- `source.json` 已指向验收 worktree；需重启窗口后关于页应显示 `1221af14`

## 用例结果

| # | 路径 | 提交 | 开始 | 首个有效数据 | 最终交付 | 派活 | 产物/链接 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 单 Bot 私聊（跟进「做一份产业链.html」；此前有回答+图） | 1221af14 | ~21:56 | 有图/有文字 | ~22:01 停在「梳理细节」未见链接 | 否 | 盘上有 `methanol/甲醇产业链_20261027.html`(≈1.0MB) 与 `methanol/甲醇产业链数据底稿_20261027.xlsx`(≈20KB)；聊天未出现可点链接；根目录另有 54B 空壳 html | **失败（交付可见性）**：承诺写 HTML，工作区已生成，对话未交付链接 |
| 2 | 主 Bot 派活同题 | 1221af14 | ~22:04 | 研究员侧已写复核 HTML | 主 Bot 未收回 | 是→产业链研究员 | 盘上有 `methanol/甲醇产业链_20261027_复核版.html`（≈1.1MB）；`works.results=[]`；聊天无图/无链接 | **失败（派活不归队）**：outbound 成功，return/面向用户交付失败 |
| 3 | 管理员群聊：行情供需研讨群 | 1221af14 | ~22:08 | 有图/有文字 | 用户可见最终回答 | 群内协作 | 盘上新增 `methanol/甲醇产业链_复核版_20261027.html`、`…数据底稿_复核版_….xlsx`；聊天无文件链接；无 PASS/暂停报告 | **部分失败**：有答有图，**无文件链接**（再次落盘不挂链） |
| 4 | 群内插话 @基差研究员（行情供需研讨群） | 1221af14 | ~22:12 | 有文字缺口说明 | 有结果、无图 | 插话命中基差岗 | 无新文件；期货 MA 取不到（`chem_futures_history` 需 managed market-data；资讯无 MA 日行情）→ 基差算不出，未编造 | **通过（缺口诚实）**：有对应回答、不编图；旧任务是否保持原路由待你确认一句 |
| 5 | 停止 / 继续 / 专用测试进程重启 | 1221af14 | | | | | | **阻塞**：需 UI 操作；Computer Use sidecar 不可用（CDN HTTP 400） |
| 6 | 文件打开（正文链接 / 中文文件名 / 交付卡） | 1221af14 | 22:17 探测 | | | | 工作区 4 个 html/xlsx 文件头合法（html DOCTYPE / xlsx PK）；**聊天链接仍缺失**（见例 1–3） | **部分通过**：盘上文件可解析；对话入口/交付卡链接未通过 |

## 环境准备进度

- [x] 独立 worktree 检出 `1221af14`，未改动 Codex 的 `release-speed-next` worktree
- [x] `chemclaw-bot` / `app` 依赖安装；Electron 二进制已就绪
- [x] `--info` 确认：branch `test/40-acceptance-baseline`，revision `1221af14`，modified false；经主入口 `--source` 时数据仍在 `D:\cursor-chembot\.chemclaw-dev`
- [x] 确认基准无 `answer-runs.js`（硬预算已撤回）
- [x] `source.json` 已指向验收 worktree；人工重启后继续（模式 B）
- [x] 第 1 例已跑并记录

## 失败 / 阻塞备注

1. Cursor Computer Use 不可用；改为人工操作 + 工作区观测。
2. **第 1 例 P0 失败（交付可见性）**：Bot 说「开始写甲醇产业链 HTML」，回合停在「梳理细节」约 4m34s；用户侧可见回答与图，但**无 HTML/Excel 链接**。工作区在 22:00–22:01 已生成完整 HTML（约 1MB，含 title「甲醇现货价格与上下游产业链」）与 xlsx 底稿；另有根目录 54B 残缺 html。符合清单「承诺文件实际存在并有可打开链接」中链接缺失。不以此用 mock 补过。
3. **第 2 例 P0 失败（派活不归队）**：ChemClaw→产业链研究员 outbound 成功（`requests.outcome=delivered`）；研究员约 22:07 在工作区写出复核版 HTML；`works.results` 仍为空，主 Bot 聊天无收回、无图、无文件链接。与「成员结果回到派活者并面向用户交付」不符。
4. **第 3 例部分失败（群聊文件链接）**：行情供需研讨群有最终回答与图；22:09–22:10 工作区再写 html/xlsx，聊天仍无文件入口。诊断里成员自述「点开不显示，问题在交付方式而不是文件本身」。未出现 PASS/审批/接力暂停。
5. **第 4 例通过（缺口诚实）**：`@基差研究员` 有对应文字结果；因期货 MA 环境/数据缺口明确不编基差、不出图（符合「无数据不编造图表」）。插话期间工作区无新文件。旧产业链任务是否保持原路由需用户口头确认。
6. **自动化受阻**：Cursor Computer Use 再次 `sidecar_unavailable`（release host HTTP 400）。本机 Electron 源码已是验收基准，本地 `127.0.0.1:50991/api/bot` 需会话鉴权（401），验收约束下不读取/打印 token。文件打开已用文件头探测完成；停止/继续仍缺 UI 驱动。
7. **第 6 例部分通过**：工作区甲醇 html/xlsx 文件头合法可解析；聊天内链接/交付卡仍失败（与例 1–3 同一根因）。
