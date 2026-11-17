# ChemClaw P0 — 对齐 DS-Bot 上游消息 Ledger 的安全分阶段切换（测试实现，未发布）

> 日期：2026-11-17 · 关联：#137、#128、#133、#150  
> 对照的上游：[`Fei2411/DS-Bot@5e9b7da`](https://github.com/Fei2411/DS-Bot/commit/5e9b7da8882da3b68d8a0624342708c2150a9156)（检索时 `main`）。  
> ChemClaw 对照基线：[`main@4269879`](https://github.com/zoeyzhang233666/chemclaw-bot/commit/42698794301d9ce13d5439de82f40a1aab9369bf)。  
> **#154 已增加显式测试开关的生产代码适配，但默认仍使用旧群聊实现；不应在真实用户配置开启测试开关、不自动迁移真实历史、不发布安装包；不能据此宣称 P0 完成。**

## 1. 上游来源与对应能力（先看源码，不另造一套）

| 阶段 | 上游已合并 PR | 上游实现 | 对应源码 |
| --- | --- | --- | --- |
| A. 统一群聊账本/读取 | [#1317](https://github.com/Fei2411/DS-Bot/pull/1317) | 每群 JSONL；群消息统一由 `say()` 写入，旧 `group-logs`/`group-lines` 导入；最近 60 行为缓存；聊天从账本读 | [ledger.js](https://github.com/Fei2411/DS-Bot/blob/5e9b7da8882da3b68d8a0624342708c2150a9156/ds-bot/src/host/ledger.js)、[groups.js](https://github.com/Fei2411/DS-Bot/blob/5e9b7da8882da3b68d8a0624342708c2150a9156/ds-bot/src/host/groups.js)、[group-replies.js](https://github.com/Fei2411/DS-Bot/blob/5e9b7da8882da3b68d8a0624342708c2150a9156/ds-bot/src/shared/group-replies.js) |
| B. 群聊调用批次 | [#1351](https://github.com/Fei2411/DS-Bot/pull/1351) | `state.roomBatches` 持久化待执行成员、完成结果，重启后判断是否唤醒派活 Bot | [groups.js](https://github.com/Fei2411/DS-Bot/blob/5e9b7da8882da3b68d8a0624342708c2150a9156/ds-bot/src/host/groups.js) |
| C. Bot 对话账本 | [#1358](https://github.com/Fei2411/DS-Bot/pull/1358) | `pair-<id>-<id>.jsonl`，发送之前先记录；等待 `written()`，收到 DSH Session flush 再追加 `delivered` | [delivery.js](https://github.com/Fei2411/DS-Bot/blob/5e9b7da8882da3b68d8a0624342708c2150a9156/ds-bot/src/host/delivery.js) |
| D. 群轮次独立执行 | [#1364](https://github.com/Fei2411/DS-Bot/pull/1364) | `group_relay` 只生成 anchor 并快速返回；同一群单轮运行，期间新消息加入/排队；Stop 与最终展示从账本恢复 | [groups.js](https://github.com/Fei2411/DS-Bot/blob/5e9b7da8882da3b68d8a0624342708c2150a9156/ds-bot/src/host/groups.js) |

上游解释：[消息账本设计](https://github.com/Fei2411/DS-Bot/blob/5e9b7da8882da3b68d8a0624342708c2150a9156/docs/plans/2026-11-10-message-ledger.md)。

**关键实现差别不可忽略**：上游群消息 `ledger.append()` 先更新内存、后异步 `appendFile`，其 `written(book)` 提供磁盘完成/失败反馈，Bot-to-Bot 发送前显式等待；ChemClaw 已有更严格的独占锁、`fsync`、确认后投递组件。应以**上游的数据模型、接口、调度和 UI 语义为依据**，保留 ChemClaw 的更严格磁盘失败处理，不得盲目替换为上游异步写入并误称完全持久化。

## 2. ChemClaw 当前具备什么、还缺什么（main）

**已合并但独立、尚未接入生产群聊：**
- `src/host/ledger-foundation.js`、`ledger-import.js`：旧数据读取、导入计划与初始完整账本原子发布。
- `ledger-append.js`、`ledger-room-commit.js`：独占写者验证、尾部校验、`fsync`、`room.seq/log` 提交；#154 在 `groups.js` 加入显式 `experimentalGroupLedger` 测试分支，走严格写入器，**默认关闭且尚未完成 UI 与调度切换**。
- `ledger-recovery.js`、`ledger-delivery.js`：只读崩溃恢复诊断、attempt→DSH→api-returned 交付回执；并未启用生产恢复/重发。
- `group-post-queue.js`、`group-persistence-gate.js`：当前旧路径的保存顺序与失败阻断。
- #138–#149 为分阶段基础或旧写入安全修复，**不代表 Ledger 已经启用**。

**尚未完成的核心接入：**
- `chemclaw-bot/index.js` 尚未安装上游等价的完整 Ledger 运行模块；#154 仅从群聊 `groups.js` 内接入经过测试的持久化提交器，不能直接照抄上游模块顺序和文件。
- #154 将 `src/host/groups.js` 各 `appendRoom` 调用改为等待提交成功，且新增严格写锁/失败阻断；仍由测试开关激活，`group_relay` 长期等待 DSH 的调度结构尚未迁移。
- 群聊可视化（`group-stream`、对话历史、对应前端）、`read_group_chat`、记忆与引用读取尚需核对是否全部切到单一账本数据源。
- `delivery.js` 与私聊 `works`、`handoffs`、晚到结果需要一起审查；不可用上游完整文件覆盖 ChemClaw 定制业务。

## 3. #150 的决策：暂保持 Draft，先不合并

[ChemClaw #150](https://github.com/zoeyzhang233666/chemclaw-bot/pull/150) 的严格旧写入阻断逻辑现已纳入统一 #154，并与显式 opt-in Ledger writer 组合；仍不得将该安全闸门误当作完成上游 #1317 的全部生产迁移。

- #150 与 #154 的重复逻辑应收敛，统一以 #154 完整通过的最新 CI 和写入/恢复/界面验收为依据，未验证前不得合并并宣称迁移完成。
- 验证在“旧群被意外创建账本”“运行中出现账本”“已有账本但迁移未完成”时确实不丢数据；同时评估其可用性代价（被阻断的群不能工作）。
- 后续 cutover 必须接管已阻断群，不能以简单删除账本或恢复旧写入口处理；在确认不再存在旧写入路径后再决定是否撤掉临时闸门。
- 当前 #150 分支落后 main 的 #151 浏览器安全修复；任何进一步修改都必须用最新 main 做新一轮检查。

## 4. 实施分解：每个 PR 一个可验证边界

### PR-A：上游 #1317 — 非破坏性群聊切换（先做）

1. **先只读验证**：使用 ChemClaw 旧版合成数据夹（含群名、成员、60+ 行、2,000/20,000/60,000 字消息、`group-logs`、`group-lines`、旧 Session、没有账本/残缺账本/账本领先状态），运行导入预检。预检有缺口则停，绝不自动补齐或删除真实旧文件。
2. **唯一写入入口**：在 `groups.js` 将所有用户消息、成员消息、notice、Stop/Continue/late reply 的旧同步 `appendRoom` 和散落的保存/显示入口收敛。优先重用已合并的 `createGroupLedgerCommitter`；必须完整传播 Promise 与错误，不允许留一条旧 writer 写 `state.json`。
3. **唯一读取来源**：借鉴上游 `group-rows`、`GroupReplies` 的 range/anchor 和旧版带 `replies` 的工具结果兼容。保留原始化工视图和 GenUI 卡片，核对 `group-stream` / `parts` / `read_group_chat` / 记忆 / 群成员全文读取是否一致。
4. **切换与恢复**：严格独占写锁；Ledger 比 `state.json` 领先时停派活并走只读恢复+人工/显式裁决，不自动重放 DSH 调用。回滚方案区分“只创建了导入账本”和“新写入已发生”；后者不得宣称可以无损直接降级。
5. **特意检查**：`updateRoom`、`deleteRoom`、`deleteBot` 中的 `await` 间隙与删除顺序。只能在确认目标群已经完成切换且无未确认交付时执行破坏性操作；不得依赖每次简单的 `lstat` 代替持有写锁。

验收：旧群首条消息、跨 60 行滚动、长文显示/重启全文、文件写失败/锁丢失、重复 seq/sidecar 冲突、Group 工具、旧工具结果历史、跨 Windows/macOS/Linux 的自动化全过；**不能触发真实用户数据的自动迁移**。

### PR-B：上游 #1351 — roomBatches

参照上游批次状态而不是重新发明成员等待关系；验证多成员同批、改名/离群、运行中热重载、Host 崩溃、未完成结果只通知一次，与现有 ChemClaw 放弃等待/晚到结果兼容。

### PR-C：上游 #1358 — pair Ledger 与交付回执

复用 ChemClaw `ledger-delivery.js` 中明确的“写入 attempt→等待确认→DSH→记录 api-returned”协议，依上游区分 `request/reply/stopped` 和已送达展示；验证网络异常与不确定结果时**不自动重发**。保留 `works` 历史、权限范围与现有工具。

### PR-D：上游 #1364 — 解耦 group_relay

依据上游 anchor/from 范围、单群只运行一轮、running/finalizing/laterPosts、群 Stop 语义移植。旧 Session tool result 必须仍可读取；不要把“快速返回”误判为业务任务已完成。与 PR-A 的渲染策略协同，不要单独提前更改工具结果格式。

## 5. 统一验收门槛（GitHub CI 优先）

- **状态一致**：旧 `state.json`、`group-logs`、`group-lines`、Session/聊天都在；新 Ledger 和缓存/长文读回可比对；恢复不重复调用 Bot。
- **故障注入**：写入中断、截断尾行、ENOSPC/EACCES、锁丢失、两写者争用、账本 ahead/behind、保存失败、热重载与真实 DSH Host 重启、取消/停止。
- **任务语义**：并发用户消息、长轮次、成员 @、全群 Stop、Bot 晚到、授权审批、旧 Session 历史展示；不能无限等待或错把部分结果当完成。
- **ChemClaw 兼容**：化工专家团 / 主 Bot、APIHub、芯化和云 MCP、行情 K 线/GenUI、Office 文件/预览、中文/纸张主题、权限限制不回退。
- **跨平台**：Ubuntu/Windows Node、macOS arm64/x64、Windows/Linux 打包、GenUI、Docker、真实 DSH 热重载；全绿仅证明该覆盖的自动化结果，不替代最终整合实机验收。
- **发版冻结**：P0/P1 未结束前不打正式 Release、不更新版本号、不发布 auto-update；不要要求每个 PR 都安装测试包。

## 6. 下一步执行规则

统一 #154 已包括只读历史检索、长文/旧数据兼容、严格旧 writer 阻断、显式 opt-in 写入适配和 Host 回归测试。该测试开关禁止用于真实用户数据；下一步须在**同一 #154** 中完成群聊界面/成员读取的 Ledger 数据源切换、崩溃恢复与交付回执核对、长轮次/晚到结果回归，再决定取消开关和合并时机。每次改动列出“上游来源/复用/偏离原因”，不新建竞争 Ledger。
