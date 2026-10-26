# 中文技能入口、模型设置与文件打开

按用户 2026-10-26 的截图反馈修复，基于 ChemClaw main `da4f95ec`。

斜杠菜单复用 DSH 原生组件与 source/index 选择路由。公开的 StoredEntry
将 locale 存在 entry.locale，而不是 entry.options.locale；修正定位和重新注册。
展示投影同时覆盖原生 skill 与 chemclaw-skills source，按稳定 ID 或 originalName
关联技能库元数据。原始 ID 不进入行标题；已知宿主工程技能提供中文名称与用途。
标题和用途分两行，长文换行。投影不修改控制器中的候选或实际提交的技能 ID。
用户自定义的中文名称优先于预置说明；未知外部技能仍保留作者元数据。

模型页补齐原来使用但未定义的布局样式：密钥与获取按钮之间保留间距，
服务商名称与 ID 分开，展开区分成密钥、模型标签和删除操作区域。
窄窗口自动换行，不依赖已移除的凭据设置页面提供样式。

APIHub、芯化和云数据中台、侧栏品牌和应用图标共用现有原创空心云路径。
桌面 PNG 和所有 ICO 尺寸使用透明背景、橙色描边；小尺寸增加线宽，
去除白底和原来额外的图标外边距。重新安装或重启新版本后才能更新桌面图标。

chem_deliver 成功后，ToolCell 从真实工具结果中的绝对路径显示文件打开按钮，
使用当前 Session 提供的 openFile 进入 DSH 预览。失败、未完成、非法路径和
重复路径不产生按钮。支持 PTC 子调用与历史记录，不要求模型另写一个链接。
原有 present 交付、Markdown 链接和原生文件预览继续由 DSH 处理。
终端创建的其他文件仍应由 Bot 调用 present，或提供标准 Markdown 文件链接。
本次不重新实现文件读取、应用关联或 HTML 沙箱，也不修改 DSH。

验证：插件测试 888 通过、1 跳过；应用测试 85 通过；客户端一致性、lint 和
51 步 mock smoke 通过。Chrome 中使用独立 mock home 验证中文搜索、点击插入、
HTML/XLSX 文件生成、HTML 预览与 Excel 表格预览；模型设置在普通宽度和 540px 宽度无横向溢出。
截图位于 docs/images/chat-experience/。本轮仅修改源码和图标，不生成 EXE。
