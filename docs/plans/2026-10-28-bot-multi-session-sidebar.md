# Bot 多会话架构 + 可折叠侧栏 — 架构设计（已确认方向）

日期：2026-10-28（确认修订）。  
性质：架构 / UI 契约 / 群聊 P0 / 分批计划。  
**Batch 1 已批准实施；Batch 2 **实施前必须先定稿 Session 路由**（本文「路由铁律」）。不合 main、不打包、不发版，直至人工确认。

相关历史：[`2026-10-28-bot-capabilities-copy-new-session.md`](2026-10-28-bot-capabilities-copy-new-session.md)。

## 确认摘要

| 项 | 决定 |
| --- | --- |
| Batch 1 | **立即实施**：能力折叠/滚动/计数、复制入口、capabilities 继承；命名保留 `原名 copy` |
| Batch 2 模型 | `chats[]` 同意；**否决**「仅靠 activeChatId 镜像驱动执行/换部/路由」 |
| agent_teams | 新建对话永远允许；归档/删除在不安全 captain 依赖时拒绝并说明 |
| 自动标题 | v1 有意义启发式；可手改；异步模型标题后置且不挡首轮 |
| Git | 从 `chemclaw/main` 干净 worktree；保留本地脏改 |
| 群聊 | **Batch 2 P0 验收**；不过回归不得合 |

实施 worktree：`D:/cursor-chembot-cap-batch1`，分支 `feat/bot-capabilities-copy`。

---

## 产品目标

Bot = 长期专家配置。Chat = 可多开的独立私聊。侧栏「Bot → 对话」。`+` = 新建对话（不建 Bot）。「复制 Bot」仅管理菜单。用户无需理解 Session/tip/segments。

---

## Batch 2 路由铁律（相对初稿的修正）

### 问题：纯激活镜像为何危险

若 `parts.js` / 投递 / 审批只读「当前 `activeChatId` 镜像到的 `bot.sessionId`」，则：

- Chat A running 时用户打开/创建 B → A 的换部或回报可能写到 B；
- 群成员 `message_bot` / handoff 可能误投激活私聊；
- 重启后若误把旧 tip 重定向到新 Chat，历史串话。

### 正确模型：Session 主键 + Chat 容器；active 仅 UI

```text
sessionId  ──index──►  { botId, chatId?, roomId? }
chatId     ──owns───►  tip sessionId + segments[]（本对话换部链）
activeChatId          仅：侧栏高亮、openSession(botId) 默认打开哪条、顶栏标题
room.sessions[botId]  与私聊 chats 完全分立，永不随 activeChatId 改写
```

**硬规则：**

1. **发送、工具、审批、secret、问题卡、换部、schedules、side-chat、子代理回报**一律按 **触发时的 `sessionId`** 解析归属 Chat/群，**禁止**回落为「写到 activeChat」。
2. **自动换部**只改写 **该 session 所属 Chat** 的 tip/segments；不得改其它 Chat，不得改 `room.sessions`。
3. **切换/新建私聊**只改 UI 焦点与 `activeChatId`；**不得**停止或改写其它 Chat 的 running Session；**不得**把旧 Chat 的 sessionId 改写成新 tip。
4. **`chatOf(botId)` / `partFor(botId)`** 语义收窄为「UI 默认打开的私聊 tip」；**群聊与后台执行路径不得依赖它们选目标**（投递 API 必须带具体 session 或 room）。
5. **顶层 `bot.sessionId`/`bot.segments`**：若保留，只能是 **activeChat 的只读镜像（派生）**；**权威数据在 `chats[i]`**。任何 host 写路径先定位 Chat，再写该 Chat 字段，最后可选刷新镜像。若实现上无法保证派生不反向污染，则 **删除热路径对顶层字段的写入**，只保留迁移期读取。
6. **多窗口 / 重启**：索引重建必须从全部 `chats[].(sessionId|segments)` + `room.sessions|segments` 生成；禁止「只索引 active」。
7. **旧版迁移**：无 `chats` → 一条 Chat（`id = bot.id`，承接原 tip/segments）；**不**重映射历史 sessionId。

### message_bot / 跨对话

- 群内 @Bot / `message_bot`：**进入该 Bot 的群 Session**（`room.sessions[botId]`），与 `activeChatId` 无关。
- 私聊场景的 bot 投递：进入 **显式目标 session**；若 API 仅给 botId，文档定义为 active 私聊 tip，并在测试中锁定，避免静默改语义。
- `read_own_chat`：默认当前 session 的 parts 链；跨 Chat 检索若保留，必须显式，不得因 active 切换而改锚点。

### agent_teams vs 群管理员

| | 群聊 admin | agent_teams captain |
| --- | --- | --- |
| 绑定 | room + botId | captain **sessionId** |
| 新建私聊 | 允许 | **允许**（新 Chat 无 team） |
| 普通切换焦点 | 允许 | 允许（不迁移 team） |
| 归档/删除该 Chat | 与群无关 | 若仍为 captain 且团队依赖不可安全结束 → **拒绝并说明** |

不得因 Bot「曾经/长期」有 team 就禁止新建对话；仅约束**该 Chat 的归档/删除**。

---

## Session 路由 / 并发 / 换部 — 技术方案（Batch 2 实施前定稿）

### 索引与解析（唯一权威）

```text
sessionIndex: Map<sessionId, Owner>
Owner =
  | { kind: 'private', botId, chatId }
  | { kind: 'room', roomId, botId }
```

- 启动 / 每次 chats|rooms 变更后重建：遍历全部 `chats[].sessionId` + `chats[].segments[]` + `room.sessions` + `room.segments`。
- `ownerOf(sessionId)`：**找不到则失败或落 orphan 日志，禁止回落到 activeChatId**。
- `activeChatId` / 派生的 `bot.sessionId`：**只读 UI**；host 写路径禁止 `owner = botOf(id).sessionId`。

### 并发证明（串话否定）

| 步骤 | 操作 | 断言 |
| --- | --- | --- |
| C1 | Chat A 开始 turn（记 `sidA`） | `ownerOf(sidA).chatId === A` |
| C2 | UI 切到 Chat B / 新建 B | `activeChatId === B`；`sidA` 仍属 A |
| C3 | A 的工具结果 / 审批 / 换部完成 | 写入 A 的 tip/segments；B 的 tip 不变 |
| C4 | 群 Session `sidR` 同时 running | `ownerOf(sidR).kind === 'room'`；与 A/B 无关 |
| C5 | `message_bot` / handoff 目标为群 | 投递 `sidR`，不读 `activeChatId` |

实现检查清单（code review 门禁）：

1. `parts.js` 换部：入参必须是 **具体 sessionId**；更新的 segments 挂在 `ownerOf(sessionId)` 对应容器。
2. `deliver` / `api/bot` / schedules / side：事件携带 `sessionId` 或 `(roomId, botId)`，解析后投递。
3. 任何 `chatOf(botId)` 调用点标注：仅 UI / 「无显式目标时的私聊默认 tip」；群路径零使用。

### 旧历史迁移与失败回滚

**迁移（幂等）：**

1. 若 `bot.chats` 已存在 → skip。
2. 否则写入单条 Chat：`{ id: bot.id, title: bot.name, titleSource: 'default', sessionId: bot.sessionId, segments: bot.segments ?? [], createdAt, updatedAt }`，`activeChatId = bot.id`。
3. **不**改写任何历史 sessionId；不 archive 旧 Session。
4. 迁移后立即重建 `sessionIndex`；缺索引的 session 记 warn，不静默并入 active。

**回滚：**

- 迁移函数纯数据变换 + 单次 `save`；失败则不写盘（或写盘前校验）。
- 保留 `bot.sessionId`/`segments` 一版只读镜像至 Batch 3 稳定后删除，便于紧急回退到「单 tip」读路径。
- 禁止「把旧 Chat sessionId 改成新 tip」的修复脚本。

### 若激活镜像无法满足

放弃「写路径依赖顶层 `bot.sessionId`」；改为：

- 权威只在 `chats[i]` / `rooms`；
- 顶层字段若保留，仅 `syncMirror(bot)` 从 activeChat **单向**刷新；
- 宁可多改 `parts.js` / deliver，**不得**为少改代码保留 active 回落。

---

## 侧栏交互契约（Batch 3 前锁定；Batch 2 API 对齐）

| 用户动作 | 行为 |
| --- | --- |
| 点击 **Bot 名称/行主体** | **仅**展开/折叠其下对话列表（当前主视图 Bot 默认展开；prefs 记住） |
| 点击 Bot 旁 **`+`** | `bot-chat-create` → 立即打开新 Chat；无命名/模型/能力向导 |
| 点击某 **对话行** | 打开该 Chat tip；可继续提问 |
| 对话右键 | 重命名 / 归档 /（条件允许时）删除 |
| **复制 Bot** | 仅管理/右键菜单；设置页可保留管理区入口；**不**放在 `+` 上 |
| 群聊 | 侧栏一级行；**不是**某 Bot 的子对话 |

数据接口（Batch 2 产出，供 Batch 3）：

- `state.bots[].chats[]`：`{ id, title, titleSource, createdAt, updatedAt, archived?, sessionId?, segments? }`
- `state.bots[].activeChatId`
- `bot-chat-create | open | rename | archive | delete`
- 侧栏所需：每 Chat 的 `running` / `needsInput` / `unread`（按 **该 tip sessionId** 聚合，非 active）

自动标题 v1：启发式生成**有意义**短标题（去填充语、取主名词组/首句意图，非整段盲切到 N 字）；`titleSource: 'auto'|'user'|'default'`。

---

## 群聊兼容性测试矩阵（Batch 2 P0）

| # | 场景 | 期望 |
| --- | --- | --- |
| G1 | 既有 room id / members / admin / 历史 | 迁移后不变 |
| G2 | `room.sessions[botId]` | 新建/切换/重命名私聊后 **字节级同 id** |
| G3 | 群 running 时建私聊 B、切私聊 | 群消息/工具/审批仍进群 Session |
| G4 | 群内 @成员 / message_bot | 不进 active 私聊 |
| G5 | 成员互相委派与回传 | 回报原群 Session |
| G6 | 群记忆 vs Bot 私聊记忆 | scope 不串 |
| G7 | 群内自动换部 | 只动 `room.segments[botId]` |
| G8 | 私聊 A running + 群 running + 开私聊 B | 三路 session 结果各归各 |
| G9 | 重启 / 多窗口 | 索引恢复；无 tip 重定向 |
| G10 | 群聊侧栏入口 | 仍为一级；不挂到 Bot 子树 |
| G11 | 群 admin ≠ agent_teams captain | 分别用例 |
| G12 | read_own_chat / handoff 在群 | 锚点不因 activeChatId 变 |

**合并门禁：** 上表自动化 + 抽样手工通过后，Batch 2 才可合。

---

## 复制 Bot（Batch 1）

顶部醒目「复制为新 Bot」+ Manage/右键；继承 capabilities；不抄 grants/记忆/历史；命名 `freshName(name + ' copy')`。

---

## 分批

1. **Batch 1**（本 worktree）：能力 UI + 复制修复 → 独立 PR，**不合 main**。  
2. **Batch 2**：按本文路由铁律实现 `chats[]` + API + **群聊矩阵**；技术方案在编码前再开短 PR/文档确认。  
3. **Batch 3**：侧栏/顶栏 UI（参考 Agent 信息架构，**不**照搬视觉）。

---

## Dry-run / 实施边界

- 本地原工作区脏改保留。  
- 各批独立 PR；未经确认不合 `main`、不打包、不发 Release。
