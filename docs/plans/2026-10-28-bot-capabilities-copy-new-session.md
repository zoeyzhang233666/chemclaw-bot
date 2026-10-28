# Bot 能力设置 / 复制 / 新对话 — 源码审计与改造方案（dry run）

> **部分 superseded（2026-10-28）：** 产品已改为「一 Bot 多独立对话 + 侧栏两级」，并**取消**复制时间戳命名。Batch 2 与命名以 [`2026-10-28-bot-multi-session-sidebar.md`](2026-10-28-bot-multi-session-sidebar.md) 为准。本文 Batch 1（能力折叠 + capabilities 继承）仍有效，但复制命名保持 `原名 copy`，不做时间戳。

日期：2026-10-28。
性质：**审计 + 分阶段改造方案**。本阶段**不改产品代码、不合 main、不打包、不发 Release**。

## 基准与工作树保护

| 侧 | Revision / 状态 |
| --- | --- |
| 上游 `origin/main`（Fei2411/DeepSeek-Bot ≈ DS-Bot） | `4a7b5506`（tag / 包 **0.2.3**） |
| ChemClaw `chemclaw/main` tip | `e0160fef`（包版本仍标 **0.2.2**） |
| 本工作区 `HEAD`（`main`） | `fe1c15bb`，**落后 chemclaw/main 约 60 commits** |
| 对齐 tip 的 worktree | `D:/cursor-chembot-parity` @ `e0160fef`（另有 Batch A 未提交草稿，**不得当本需求基线**） |
| 上游 Issue | [Fei2411/DS-Bot#122](https://github.com/Fei2411/DS-Bot/issues/122) — **OPEN**，带 `maintainer` 标签；社区补丁基于 **0.1.5**（`2b10c70`），**未合入上游 main** |

### 本地未提交修改（必须保护，实施时勿覆盖）

当前工作区与本需求**无关**的脏文件（图表调色、providers、launch 脚本等）：

- 已改：`chemclaw-bot/src/client/inks.js`、`widget-chart.js`、`host/providers.js`、`shared/model-providers.js`、`client.js`、`test/providers.test.js`、`scripts/launch-chemclaw.mjs`
- 未跟踪：若干日志、`series-palette.test.js`、`docs/plans/2026-10-28-upstream-parity-audit.md` 等

**实施约束：**

1. 从最新 **`chemclaw/main`** 新开分支（例如 `feat/<issue>-bot-capabilities-session`），**不要**从落后的本地 `main` 起步。
2. 用独立 worktree 或先 stash/另存当前脏改；parity worktree 上的 Batch A 草稿与本需求分叉。
3. 本 dry run **未**改 `main`、未合 PR、未打包。

---

## 三部分现状结论

### 第一部分：能力设置 UI — **部分具备，缺折叠/滚动**

| 字段 | 结论 |
| --- | --- |
| **位置** | `chemclaw-bot/src/client/capability-settings.js` → `BotCapabilitiesCard`；挂在 `bot-settings.js` 的 Instructions 与 Memory 之间 |
| **已有** | 搜索框（`Search tasks, skills, or keywords`）；启停走 `actions.setBotCapability` → `bot-capability`；状态文案 Ready / Needs approval / Connecting / error |
| **缺口** | **无默认折叠**；**无独立滚动**；匹配结果即全量展开 SwitchRow。ChemClaw 种子约 **118+ skills**，另有 MCP/pack，会把 Memory、定时任务、Main Bot、Manage **挤到页底** |
| **上游** | 上游 `capability-settings.js` 是库管理表单为主；Bot 侧同类列表同样无 ChemClaw 所需的折叠滚动；**无可直接套用的成品 UI** |
| **风险** | 低。纯客户端布局；不改启停/搜索/保存契约即可 |

### 第二部分：复制 Bot — **入口弱 + capabilities 不复制（上游同病）**

| 字段 | 结论 |
| --- | --- |
| **入口** | 设置页底部 Manage → Duplicate；侧栏右键 Duplicate。**无**设置页顶部醒目「复制为新 Bot」 |
| **宿主** | `roster.js` `duplicateBot`：复制 name/role/instructions/color/avatar/model/effort/workDir + `copyOf`；`buildBot` **硬编码 `capabilities: []`** |
| **命名** | `freshName(\`${bot.name} copy\`)`，stem 截到 34 + 可选 ` 2`…；**不是**「原名-本地时间戳」 |
| **敏感项** | **不**复制 `browserGrants`（正确，应保持）；不复制聊天/segments/记忆/群成员资格（正确） |
| **上游** | `ds-bot` `duplicateBot` **同样不抄 capabilities**；Issue #122 把 duplicate 标为「太重且仍不够」的 workaround |
| **风险** | 低–中。需在 create 后原子写入 capabilities（或扩展 `buildBot`/`createBot` 可选 `capabilities`），并触发既有 reconcile；命名规则要过 `nameProblem`（禁 `@` `` ` `` 换行）与 40 字、重名、Windows 标题安全字符 |

### 第三部分：真正的新对话 — **ChemClaw 与上游 main 均缺失；社区补丁可参考不可盲贴**

| 字段 | 结论 |
| --- | --- |
| **现状** | 每 Bot 一个当前 `sessionId`；上下文满时 `parts.js` `startSwitch` **换部并带 handoff/摘要** ≠ 干净换代。侧栏「新对话」是选 Bot/建 Bot 发起器，不是换 Session。DSH Agent 菜单有 New session，Bot 菜单没有 |
| **API** | `channel.js` **无** `bot-new-session`；`parts.js` 未暴露 `newBotSession` |
| **社区补丁**（Issue #122，SHA256 `a0bcdc6b…`） | 在 **0.1.5** 上：右键 New session + `bot-new-session`；复用 switch slot + `runMaintenance`；`segments` 标 `clean: true`；零 kickoff/旧消息/handoff；保留身份/设置/能力/长期记忆/工作目录；群 Session 不动；忙碌/收件箱/审批/问题卡/secret/kickoff/并发/stale id 拒绝；`moveSchedules` 后再 archive 旧 Session。社区在 Windows+真实模型验收过 0.1.5；**0.2.x 未官方合入**；评论指出 **agent_teams captain 血缘** 与现有换部同样有缝 |
| **与 ChemClaw tip 机械兼容性（探针）** | `startSwitch` / `runSwitch` / `switches` / `checking` / `moveSchedules` / `renewMemory` / `createSession` / `applyPermission` / `desiredModel` / `desiredEffort` / `splitRef` / `waitsForApproval` / `secretRequests` **均仍存在**；`parts.js` 行数与上游接近（~1328 vs ~1334）。**仍须**在 tip 上做 apply-check + 单测移植，不能直接对 0.1.5 diff 盲贴（`chemclaw-bot` 前缀、ChemClaw channel 形态、侧聊/群聊/技能库分叉） |
| **风险** | **高**。Session 生命周期、并发路由、定时任务、群聊、多智能体/agent_teams、历史 `earlier`/`read_own_chat`、Desktop/Windows |

---

## 能力分层（必须分清）

| 层 | 新对话后 | 复制 Bot 后 |
| --- | --- | --- |
| 会话消息 / kickoff / handoff 摘要 | **不注入**新 Session | 新 Bot **新 Session**，无旧聊 |
| Bot 配置（名/角/指令/模型/effort/folder/capabilities 列表） | **保留** | **继承**（本需求修复后含 capabilities） |
| 长期记忆（remember/recall） | **保留**（可主动 recall；≠ 自动注入对话） | **不继承**（新身份，记忆从零） |
| 工作目录文件 | **保留**（同一 folder） | **可共用同一 folder**（现状如此）；不复制磁盘树 |
| `browserGrants` / Secrets 授权 | 保留（同 Bot） | **不复制** |
| 群聊 Session | **不重置** | 新 Bot **不进**原群 |
| 定时任务 | 补丁语义：**迁到新 Session** | 不复制到新 Bot |
| agent_teams captain | **缺口**：见方案选项 | 无关（新 Bot 无旧 team） |

「零继承」= **不自动注入**；旧部仍可能被 `read_own_chat` / earlier **主动翻到**（Issue 提出方已实测）。产品文案需写清。

---

## 推荐分批（先快后难）

### Batch 1 — 快速：能力 UI + 复制修复（可独立合入）

**目标：** 设置页可扫、复制即用，不碰 Session 架构。

#### 1A. 能力设置折叠 + 滚动

- 改 `BotCapabilitiesCard`（`capability-settings.js` + 少量 CSS）：
  - 默认**折叠**；标题行显示 `Capabilities` + **已启用数量**（`attached.size`）。
  - 保留搜索框；**有查询时自动展开并只渲染匹配项**。
  - 展开后列表容器 `max-height` + `overflow: auto`（建议约 240–320px），不把后续卡片顶出视口；可选按 kind（pack / mcp / skill）二级折叠，但**第一版用整表滚动即可**（YAGNI）。
- **不改** `setBotCapability` / host / 状态提示逻辑。
- i18n：中英同步短文案（如 “{count} enabled”）。

#### 1B. 复制入口 + capabilities 继承 + 命名

- UI：`BotSettingsForm` **hero 下方或 Profile 卡上方**增加主按钮「复制为新 Bot」；**保留** Manage 与右键入口。
- Host：`duplicateBot` 在 `createBot` 成功后，把原 `bot.capabilities` 中**仍存在于库**的名字写入副本并 `save`，走现有 reconcile（可复用 `setAttached` 批量或一次性赋值 + `capabilitiesStateSaved`/`scheduleReconcile`）。
- **禁止**复制：`browserGrants`、secret 请求、segments、sessionId、群成员、记忆库条目、Main 身份（现状 duplicate 也不变 Main，保持）。
- 命名：`原名去后缀` + `-` + 本地 `YYYY年MM月DD日HH时mm分ss秒`；去后缀匹配末尾已有时间戳与旧式 ` copy` / ` copy N`；总长 ≤ 40；冲突则在秒级上重试或截断 stem；过滤 Windows 非法字符 `<>:"/\|?*` 与尾部 `.`/` `（`nameProblem` 之外再加一层 sanitize，因 Session 标题会 `sessionTitle.rename`）。
- 测：扩展 `roster.test.js` — 原 Bot 挂 skill+mcp+pack 后 duplicate，断言副本 `capabilities` 深等、无 `browserGrants`、新 id/session、名称匹配时间戳规则、并发三份不撞名。

#### Batch 1 回滚

- 单 PR；回滚 = revert 该 PR。无状态迁移。UI 回退不影响已复制 Bot 的已写入 capabilities。

#### Batch 1 测试清单

- `npm test`（含新增/扩展 roster + 可选 capability-settings 客户端测）
- `node scripts/build-client.mjs --check` + `npm run lint`
- 手工：设置页折叠/搜索/启停/保存；复制后新 Bot 打开即可用技能、无旧聊、无 grants

---

### Batch 2 — Session 架构：真正的「开启新对话」（需单独设计验收）

**目标：** 同一 Bot 多部独立聊天；入口在**聊天顶栏 + 侧栏**清晰可见，不只高级设置。

#### 推荐实现路径（三选一）

| 方案 | 做法 | 利 | 弊 | 推荐 |
| --- | --- | --- | --- | --- |
| **A. 适配社区补丁语义** | 在 ChemClaw tip 重写/移植 `newBotSession` + channel + 菜单/顶栏/侧栏入口 + 单测（参考 #122，**不**盲 apply 0.1.5 整包） | 语义已被社区与 Windows 真模型验证；复用 parts switch 槽 | 需适配 ChemClaw 分叉；agent_teams 仍需策略 | **推荐** |
| **B. 仅暴露 DSH session.new** | 藏掉的 chrome 解开 | 看似简单 | 不进 `chatOwners`/segments，**孤儿 Session**；Issue 已否 | 否 |
| **C. 继续用 duplicate 冒充** | 强化 Batch 1 | 快 | 新身份、胀名册、非「同 Bot 新对话」 | 仅作过渡，**不**当终态 |

#### 方案 A 关键设计要点（实施前仍须在 tip 上做 apply-check）

1. **API**：`bot-new-session` + `rt.newBotSession(botId, expectedSessionId)`；stale id → `bot/stale`。
2. **干净度**：不写 kickoff、不带 handoff note；`segments[].clean = true`。
3. **守卫**：idle、无 inbox、无 approval/question/secret/kickoff、非 switch/check 中、准备期配置指纹不变。
4. **并发**：占用同一 `switches` 槽；换代中输入 forward 到最终当前聊天。
5. **群聊**：不碰 `room.sessions`。
6. **定时任务**：`moveSchedules(old, fresh)` **先于** archive。
7. **失败**：回滚 `sessionId`/`segments`；archive 未采用的 fresh Session。
8. **agent_teams（ChemClaw/DSH 若启用）**：第一版建议 **有活跃 captain team 时拒绝换代并提示收尾**（或文档标明已知限制）；完整迁移 captain/parentSession 作 follow-up（Issue 评论证实 header 血缘难改）。
9. **入口（相对补丁加码）**：
   - 聊天顶栏（`header.js`）Bot 私聊：「开启新对话」
   - 侧栏右键 +（可选）侧栏行内图标
   - **不**只放在高级设置
10. **文案**：明确旧聊可回查；长期记忆与工作目录仍在；主动检索旧部仍可能。

#### Batch 2 回滚

- 独立 PR。回滚代码后：已写入的 `segments` 仍可读；无强制数据迁移脚本。若需禁用入口可 feature-flag（默认不必，保持简单）。

#### Batch 2 测试清单

- 移植/改写 `new-session.test.js`、`new-session-menu.test.js`（前缀、home、品牌）
- 守卫矩阵：忙碌 / stale / 并发 / save 失败 / 删 Bot 竞态 / schedules 顺序
- 群聊 Session 不变；记忆 recall 仍可用；首轮请求无旧消息
- Desktop Windows 手工：顶栏 + 侧栏入口；旧部 earlier；快速回复/深度探索/侧聊不受影响
- 回归：Skills/MCP/群聊/DSH 插件/独立 EXE 启动路径冒烟（mock，不用用户 `~/.dsh`）

---

## 影响范围（文件级预估）

### Batch 1

| 文件 | 变更 |
| --- | --- |
| `src/client/capability-settings.js` | 折叠、计数、滚动 |
| `src/client/bot-settings.js` | 顶部复制入口 |
| `src/client/i18n.js`（及生成 `client.js`） | 文案 |
| `src/client/styles.js` 或 `BOT_SETTINGS_CSS` | 列表滚动样式 |
| `src/host/roster.js` | `duplicateBot` 命名 + capabilities |
| `test/roster.test.js`（+ 可选客户端测） | 回归 |

### Batch 2

| 文件 | 变更 |
| --- | --- |
| `src/host/parts.js` | `newBotSession` |
| `src/host/channel.js` | endpoint |
| `src/client/context-menu.js` / `header.js` / `sidebar.js` / `team-actions.js` / `index.js` | 入口与 action |
| `src/client/i18n.js` + `client.js` | 文案 |
| `test/new-session*.js` | 新测 |
| 可能：`roster.js` `createSession` 失败归档（补丁小改进，可选顺带） | 稳健性 |

**明确不动：** DSH 本体、用户 `~/.dsh`、桌面生产 `DSH_HOME`、快速回复/深度探索协议、Skills/MCP 安装管线（仅消费既有 attach）、独立 EXE 打包脚本（本阶段不发版）。

---

## Dry-run 边界声明

本审计期间：

- 未修改 `chemclaw/main` / 本地 `main` 产品交付意图。
- 未创建或合并本需求 PR。
- 未打包、未发 Release。
- 未对 0.1.5 社区补丁做 apply 到 ChemClaw tip（仅阅读 Issue 与结构探针）。
- 未触碰用户真实 DSH 数据。

对照手段：`git show` / `git grep` 对 `chemclaw/main` 与 `origin/main`；`gh issue view` #122；parity worktree 只读源码。

---

## 待你确认后再实施

请确认以下决策（回复编号即可）：

1. **是否批准先做 Batch 1**（能力 UI + 复制修复），Batch 2 另开 PR？
2. **Batch 2** 是否采用方案 **A**（适配 #122 语义），且 agent_teams 第一版 **有活跃 team 则拒绝**？
3. **复制命名**是否严格采用「原名-YYYY年MM月DD日HH时mm分ss秒」本地时区（同意超长时优先截断原名保留完整时间戳）？
4. 实施起点：从 **`chemclaw/main` 新 worktree/分支**，当前工作区脏改继续保留不动？
