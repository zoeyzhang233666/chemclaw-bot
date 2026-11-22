# 电脑版即时通讯

「设置 → 即时通讯」连接微信、QQ、飞书 / Lark、企业微信、钉钉、Telegram、Discord 和 Slack。微信用手机扫码，其他平台需在对应平台开通机器人并填入凭据。连接后可查看状态、变更绑定、停用、重试或移除。设置页使用 ChemClaw 的主题变量、表单控件和卡片样式。

消息进入已有的专家会话。除扫码配对的微信账号外，首次发送消息需要在设置中批准。支持群聊的平台只有在已配对账号提及机器人时才接收群消息，群可单独绑定专家或 ChemClaw 群聊。凭据保存在 ChemClaw 密钥库里，默认对所有专家关闭。

只有持有团队写锁的进程连接平台。回复跟随当前轮次的来源。其他消息加入同一轮后，该轮的新回复留在 ChemClaw。群回复在当前轮次完成持久化后发送。退出当前轮次、无法确认来源的后台结果、连接停用或取消配对等情况下，后续回复不会发给原 IM 会话。专家自己的原生审批由桌面端处理，正在运行的 ChemClaw 群聊审批可从对应 IM 会话回答。

平台适配器及消息队列来自 DS Bot v0.3.9。微信和 QQ 的回复受平台会话时限及额度限制。应用退出或电脑休眠期间的消息由平台决定是否保留。平台连接使用长连接或轮询，无需配置公网回调。

微信等支持图片上传的平台将只读图表、指标卡和表格作为图片发送。工作区图片可通过 `present` 或 Markdown 图片发送，也支持将内嵌的静态 SVG 转成图片。图片发送失败时会给出文字提示，交互表单在桌面端打开。回复去重以当前轮次为范围，微信轮询重放也会按消息 ID 去重。

微信也支持发送工作区中的 SVG、HTML 等交付件。专家通过 `present` 交付或在回复中链接文件后，ChemClaw 以微信文件消息发送原文件名和内容。单个附件最大 50 MB。[微信 iLink 协议文档](https://github.com/Tencent/openclaw-weixin/blob/main/docs/protocol_zh_CN.md#消息模型)

本地图片可通过微信、QQ、飞书 / Lark、钉钉、Telegram、Discord 和 Slack 发送。企业微信收到只读卡片的文字摘要。微信和 QQ 可发送文件原件，其他通道会提示到电脑版查看。分段回复在重试时从已确认送达的位置继续。

QQ 使用原消息 ID 和固定的回复序号重试，重复推送按原消息 ID 忽略。图片以 PNG 或 JPEG 发送。文件和图片通过官方 SDK 所用的直传接口上传，单个附件最大 20 MB。QQ 的账号权限、文件格式和会话限制由服务端校验。[QQ 消息接口](https://github.com/tencent-connect/bot-docs/blob/main/docs/develop/api-v2/server-inter/message/send-receive/send.md) · [腾讯 QQ SDK 媒体说明](https://github.com/tencent-connect/qqbot-nodejs/blob/main/USAGE.md#10-媒体上传与发送)
