# DS-Bot 更新核实与分批同步建议

核对日期：2026-10-26。结论：可以采用“逐模块核实、适配、回归”的方式同步，
不应把网页 ChatGPT 的文件数量和优先级结论直接当作迁移依据。
本轮修复用户提出的体验问题，并做静态核查；没有移植以下可靠性模块。

## 基准与已核实事实

- 本地实际起点为 ChemClaw main `da4f95ec`，插件和应用均为 **0.2.1**，
  已合入技能库和桌面发布修复。贴文的 `feat/3-skill-library:c1b6aaef`、0.2.0
  不是本轮代码基准，151/211/104 的文件数量没有沿用或重新背书。
- 上游固定核查 [de55888a](https://github.com/Fei2411/DS-Bot/tree/de55888a)，
  并读取了核查时 main 的 [Changelog](https://github.com/Fei2411/DS-Bot/blob/main/CHANGELOG.md)。
  两者不能作为以后自动跟随 main 的授权。
- ChemClaw 应用的 DSH pin 为 **0.2.1-rc.3**，保持不变；不因上游插件更新降级。
- 不覆盖 50 Bot、15 群、技能资源、MCP 认证、APIHub、品牌和独立更新流程。

## 产物打开：已有底层能力，不等于升级上游即可解决

固定上游和本地的 `cells.js/useFileMentions` 均依赖 DSH 的关闭轮次文件引用，
没有发现一段上游新代码可以直接解决所有“文件生成后没有入口”的情况。
DSH rc.3 已提供 present、交付卡片、Markdown 文件导航、工作区预览和应用打开。
ChemClaw 当前 `app/src/profile.mjs` 也已保留 workspaceChanges 服务并将 Git
命令超时设为 1000ms；不能再照旧版思路禁用它，否则会阻塞原生交付界面依赖。

终端创建的文件需要 present 或明确的 Markdown 文件链接，不能只说“已生成”。
本轮让 ChemClaw 自有 chem_deliver 的成功结果直接提供打开按钮，已经在真实
mock 对话中点击 HTML 并确认预览。该增强不需要替换 DSH 或引入 Playwright。

## 首批值得单独迁移的模块

| 模块 | 本地证据 | 上游机制 | 迁移与验收边界 |
| --- | --- | --- | --- |
| 群聊暂停与继续 | `groups.js` 的轮数/总轮次限制仍会跳过后续调用，没有新版 paused 队列 | [#433](https://github.com/Fei2411/DS-Bot/pull/433)：记录待继续调用，用户继续或新消息恢复 | 成组处理群状态、队列、持久化、API、Continue UI；验证新用户消息、重启和用户停止后的恢复，不重复回复 |
| message_bot 请求去重 | 没有新版 `requests.js`；不能将现有未读消息合并视为持久请求去重 | [#488](https://github.com/Fei2411/DS-Bot/pull/488)：调用方与会话范围的 request_id、指纹、派发前收据 | 同 ID 同内容重试只派发一次；不同内容冲突明确报错；接收结果不确定时不能重复副作用 |
| 完整交接结果与重启恢复 | `handoffs.js` 完整长结果仍放在内存 Map，持久状态保留截断开头，重启后提示被截断 | [#487](https://github.com/Fei2411/DS-Bot/pull/487)、[#497](https://github.com/Fei2411/DS-Bot/pull/497)：独立结果文件与遗漏回复恢复 | 一起处理存储、交接生命周期和消息投递；验证多层委派、大结果、重启和删除 Bot；保留 ChemClaw 的技能选择元数据 |
| 记忆事务与失败反馈 | 已有顺序写入和原子单文件替换，不等于正文、索引、journal 的多文件事务；没有新版 `memory-pending.js` | [#492](https://github.com/Fei2411/DS-Bot/pull/492)、[#495](https://github.com/Fei2411/DS-Bot/pull/495)：预写事务记录、恢复、聊天失败提示 | 验证写入各阶段故障、再次重启、只读/损坏数据和 UI 反馈；幂等恢复且不覆盖用户原文 |

建议先按这四组分别建立提交/PR。每组包括实现、数据兼容和上游相关回归测试，
通过后才进入下一组。不能仅复制三个新增文件就宣布同步完成。
上游代码如有实际移植，需固定来源 revision 并在 NOTICE 记录许可与来源。

## 后续功能

上游 `src/shared/views.js` 已有 chart、html、sources、callout、输入控件和表达式，
本地组件协议仍是基础 stack/text/metric/table/options/confirm/form/progress。
[原生视图 #471](https://github.com/Fei2411/DS-Bot/pull/471) 值得整体适配，
与现有 ECharts 和离线 HTML 文件交付互补；不宜只扩展类型表而漏掉验证与沙箱。

自主浏览器的发布说明和 [#417](https://github.com/Fei2411/DS-Bot/pull/417)、
[#528](https://github.com/Fei2411/DS-Bot/pull/528) 支持贴文的方向判断，
但本轮未完整审计浏览器执行和审批实现，不能承诺直接复制就可用。
需另评估桌面/插件环境、配置隔离、接管、中断和依赖；SaaS 的用户隔离需要独立设计。
Side chat、触屏布局和更新显示按产品需求排序，避免覆盖现有 ChemClaw 定制。

这些是静态代码差异与迁移验收方案，不是已完成迁移或已验证故障恢复的声明。

后续执行记录：上述四组可靠性模块已在独立分支适配，具体实现、回归与界面验收
见 [上游可靠性更新适配](2026-10-26-upstream-reliability.md)。本审计保留初始核查时点的结论。
