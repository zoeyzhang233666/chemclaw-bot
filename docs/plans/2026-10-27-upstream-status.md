# 上游能力与实际同步状态

核对日期：2026-10-27。与 Issue #25、#40 关联。此文是代码与 PR 状态审计，不是全部功能已通过真实业务验收的声明。

## 基准

- ChemClaw 远端 main：`30a1fa20ae48efa1fd81594df4d2782752b231ae`，版本 0.2.2。
- 本地预览由 `feat/38-sidebar-organization:85cc8799` 继续，包含尚未合入 main 的功能。用户在额度耗尽后提交的 #37、#39 均已核实，不按旧对话推断。
- 上游正式 main：[`de55888a93983fc51c94f7d22bc94b4f8293205d`](https://github.com/Fei2411/DS-Bot/tree/de55888a93983fc51c94f7d22bc94b4f8293205d)，版本 0.2.2。
- 上游开发 dev：[`3fc8aa438eb725b1ee1fda520e078ef8d9ac0b6c`](https://github.com/Fei2411/DS-Bot/tree/3fc8aa438eb725b1ee1fda520e078ef8d9ac0b6c)。部分 PR 已合入 dev，尚未合入正式 main。
- 上游 [0.2.3 发布 PR #620](https://github.com/Fei2411/DS-Bot/pull/620) 核查时仍 open，未合并。其 [候选更新说明](https://github.com/Fei2411/DS-Bot/blob/98bafc9ce6ebf5296ba90b326b68d80398048d12/CHANGELOG.md) 可用于列待核对项，不能当成正式发布保证。

## 上游 0.2.1 / 0.2.2 对齐

| 能力 | ChemClaw 实际状态 | 可检查的实现 / 证据 |
| --- | --- | --- |
| 接力暂停继续、请求去重、完整结果与重启恢复 | main 已有 | `groups.js`、`requests.js`、`handoffs.js`、`resume.js`，#7、#16 |
| 记忆事务与失败提示、不可读凭据保护、插件更新回滚 | main 已有 | `memory-pending.js`、`memory.js`、`secrets.js`、`update.js`，#7、#13、#15 |
| 原生图表、计算器、沙箱 HTML、历史视图 | main 已有 | `views.js`、`widget-*`，#7；主动展示与密集时间轴在待合并 #33 |
| 自主浏览器、Bot 独立登录分区、审批、接管 | 开发预览已有；#24 待合并 | `src/host/browser/`、`app/src/bot-views.mjs`；原有 Windows 隔离验收记录，不等于所有平台已验收 |
| `/side` 侧聊、追问、持久化与取消 | 开发预览已有；#27 待合并 | `side.js`、`side-chat.js` |
| 消息布局、正文/气泡宽度、思考开关、手机触屏 | 开发预览已有；#29 待合并 | `settings.js`、`styles.js`、`turn-reasoning.js`；已有隔离截图 |
| 工作目录切换状态、账号退出 | 开发预览已有；#29 待合并 | `parts.js` 与设置、账号入口 |
| 关于页更新状态、手动检查 | main 已有独立实现 | `app/src/updates.mjs`、`about.js`，#6；发布源保持 ChemClaw |
| Cookie 文件、Chrome / Edge / Firefox 登录导入 | **尚未实现完整入口与桌面桥接** | 本地缺上游 `cookie-import.mjs`、`cookie-parse.mjs`、`browser-sources.mjs`。有持久化分区或翻译字符串不等于有导入 |
| 用户普通下载另存为 | **尚未补齐** | 缺上游 `downloads.mjs`；Bot 工具下载审批路径已经存在，不能代替用户窗口下载 |
| Linux AppImage / deb、更新与发布资产门禁 | **尚未补齐** | `app/electron-builder.yml` 只有 Windows/macOS，工作流无 Linux 包构建与附件门禁 |
| 不替换密钥值即可修改/清空用途 | **尚未对齐** | 当前 `secret-update` 仅改 scope；`secret-set` 空用途保留旧值，客户端也未提供等效用途编辑 |
| 浏览器多步模式设置 | 后端 refs/task 存在，完整设置体验待补齐 | `browser-plugins.js`、`browser/task.js`；存在工具接口不等于面向用户的配置路径完整 |

结论：既不是“之前什么都没做”，也不是“全部已经同步”。待合并功能不会自动进入已安装的 0.2.2；CMD 选择了预览源码也只影响重启后的开发窗口。

## 上游 dev 新增项

| 上游 PR | 内容 | 当前核查结论 |
| --- | --- | --- |
| [#605](https://github.com/Fei2411/DS-Bot/pull/605) | 管理员作为唯一开场成员却 PASS 时，明确提示用户 @成员 | 本地缺失，直接关系到静默无回答；已合 dev，尚未进入正式 main |
| [#549](https://github.com/Fei2411/DS-Bot/pull/549) | 关闭窗口留系统托盘，Bot 后台继续工作 | 本地无等效托盘生命周期；已合 dev |
| [#491](https://github.com/Fei2411/DS-Bot/pull/491) | 可复用头像库与批量导入 | 本地只有单 Bot 头像，没有头像库；已合 dev |
| [#591](https://github.com/Fei2411/DS-Bot/pull/591) | 对话内浏览器交接卡，完成/跳过后通知 Bot | 本地有浏览器面板接管，缺对话内完整交接流程；已合 dev |
| [#598](https://github.com/Fei2411/DS-Bot/pull/598)、[#587](https://github.com/Fei2411/DS-Bot/pull/587) | 中途插话的未读标识、活动计时更新 | 待核对并适配；不把已有插话支持当成全部覆盖 |
| [#584](https://github.com/Fei2411/DS-Bot/pull/584)、[#586](https://github.com/Fei2411/DS-Bot/pull/586) | 角色指令变化通知、默认思考级别继承 | 待核对，须保留 ChemClaw 模型路由与角色定制 |
| [#567](https://github.com/Fei2411/DS-Bot/pull/567) | 首次导入包含群自己的 Session | 本地 `sessionIdsOf` 目前只收成员及成员历史段，漏群自己的 id；应优先适配 |
| [#604](https://github.com/Fei2411/DS-Bot/pull/604)、[#573](https://github.com/Fei2411/DS-Bot/pull/573) | 换段定时任务不重复、旧段停止活动 | 本地部分归档使用 `stopActivity`，部分路径未使用；尚不能宣称完整覆盖 |
| [#578](https://github.com/Fei2411/DS-Bot/pull/578)、[#583](https://github.com/Fei2411/DS-Bot/pull/583)、[#582](https://github.com/Fei2411/DS-Bot/pull/582) | 截图附件、旧段读取、子 Agent 识别修复 | 需逐项复现核对，现有截图与旧段支持不代表已继承所有修复 |
| [#575](https://github.com/Fei2411/DS-Bot/pull/575) | `list_models` 改名避免插件冲突 | 本地仍用旧名，尚未对齐 |
| [#555](https://github.com/Fei2411/DS-Bot/pull/555)、[#566](https://github.com/Fei2411/DS-Bot/pull/566)、[#607](https://github.com/Fei2411/DS-Bot/pull/607)、[#579](https://github.com/Fei2411/DS-Bot/pull/579) | 旧侧聊卡删除、附件独立行、长文与代码折叠排版 | 需逐项验证，不能按客户端同名文件认定完成 |
| [#569](https://github.com/Fei2411/DS-Bot/pull/569)、[#585](https://github.com/Fei2411/DS-Bot/pull/585)、[#576](https://github.com/Fei2411/DS-Bot/pull/576) | 漏消息、忙碌成员插话、压缩后群回复恢复 | 已选择性适配到 ChemClaw #16，并有回归；复用现有实现，不重复覆盖 |
| [#616](https://github.com/Fei2411/DS-Bot/pull/616) | 一键停止群内全部任务 | 核查时仍 open，未合并且报告完整测试有失败、未跑 live smoke；不能当成成熟稳定方案直接移植 |

## 本次故障与后续取舍

PR #37 的硬预算是 ChemClaw 自行新增的方案，不来自上游正式任务执行机制。本次完整撤回，不通过放大额度、增加开关或再加一层终止逻辑掩盖问题。上游现有机制也不保证避免所有模型循环；其群接力暂停仅保留待继续调用，不能冒称“自动完成报告”。

先验证撤回后的完整单聊、派活、群聊交付；随后优先补正式版遗漏及与丢回复、导入和换段相关的修复。复杂模块优先采用许可兼容、来源固定且有测试的上游完整实现，保留 ChemClaw 的 DSH rc.3、APIHub、化工角色、技能和品牌；高星数量不能替代兼容性与实际验收。不直接引入第二套 Agent 运行时。

PPT 预览转换失败仍属于未完成的用户问题，本次没有宣称解决。全批功能及各平台验证未完成前，不统一合并 main，不发版。
