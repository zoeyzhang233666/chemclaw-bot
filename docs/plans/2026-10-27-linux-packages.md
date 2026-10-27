# Linux 桌面包与发布门禁

Issue #46，属于 #25。移植上游正式 main `de55888a93983fc51c94f7d22bc94b4f8293205d` 的 Linux x64 AppImage/deb、更新路由、Ubuntu 安装/更新/卸载验收与附件门禁。另适配已合 dev 的 #544 `9262b3e64103ac2cf0d1a67aacf5ea068d93d759`，将 sharp 原生模块及版本化 libvips 一起解包，并在真正的打包应用中检查图像处理。

AppImage 通过 electron-updater 自动更新；deb 检查对应架构的发行包并提示用户下载。普通 Windows 与 macOS 行为保持不变。安装包、执行文件、桌面入口、更新源与附件名称使用 ChemClaw。保留 Mac 原生 ZIP 与缓存优化，不扩大到尚未测试的 Linux arm64。

CI 在隔离 Ubuntu runner 检查打包启动、deb 安装与卸载、AppImage 更新替换及图像依赖；只在临时 runner 上准备 FUSE/Xvfb 和 Chromium 运行环境，不修改用户机器。最终 Release 必须同时有插件包、Windows 文件与元数据、两种 Mac ZIP、Linux AppImage/deb/latest-linux.yml，缺一则保持草稿。

本地 Windows 只验证代码、更新选择、工作流和打包配置。Linux 真实运行结论以对应 Ubuntu CI 为准，不用静态测试代替平台验收；全部模块与各平台通过后再统一合并和发布。

本地验证：桌面完整 145/145；Linux 更新资产选择、sharp 解包和工作流门禁等针对性 42/42；插件完整 1146 通过、1 项既有 Windows 跳过；生成客户端、lint（仅既有警告）、diff 与校验过 SHA256 的 actionlint 1.7.12 均通过。Linux 原生运行、deb 安装和 AppImage 更新以 PR 中新增的 Ubuntu job 为后续门禁。
