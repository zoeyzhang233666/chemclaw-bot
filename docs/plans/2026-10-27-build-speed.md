# 高频更新的构建耗时

v0.2.2 的 Intel Mac Release 任务耗时 19m50s，npm 安装 2m50s、打包 14m19s；
其中 ZIP 生成约 7m37s。Apple 芯片任务耗时 7m06s。基准来自 Actions 40372100098。

日常 PR/main 的 Mac 检查改为签名 .app 的架构、独立启动、更新路径验收；
避免每次生成 ZIP 并重复启动同一个成品。正式 Release 和 dry run 仍生成 ZIP，
并对解压后的应用验签、核对架构、运行 mock 启动和更新检查，成功后才上传发布。
不改变完整发布的资产门禁、不降级签名，也不删除技能与运行资源。

Mac jobs 缓存 npm 下载，以及按 OS、架构、app lockfile 区分的 Electron/Builder
下载缓存。Electron 使用当前下载器的默认目录 ~/Library/Caches/electron，
Builder 工具使用 ELECTRON_BUILDER_CACHE 指定的目录。
原生依赖仍在当前 runner 安装；不跨架构复用 node_modules。
缓存键升级为 desktop-tools-v3：旧缓存只保存了打包器（约 9 MB），
GitHub 同名精确命中的缓存不能追加内容；换代后才能保存完整 Electron 下载。
CI 在打包后检查对应架构的 Electron ZIP 确实位于缓存目录，防止再次保存空目录。

可选 dry-run 输入 benchmark_mac_zip 调用 benchmark-mac-zip.mjs，比较同一个
签名 .app 用 ditto 的 1/6/9 级压缩耗时和体积，每份都解压验签，记录 Actions
summary 与 JSON。它是压缩候选实验，不等同于 electron-builder 默认压缩器，
该次基准仍生成原方案的安装包；正式方案依据下方的两架构实测选择。

桌面壳/插件独立升级和包内容瘦身另行设计；本次保留完整运行资源。

## 原生 ZIP 选择与验证

基准演练为 [Actions 40409174068](https://github.com/zoeyzhang233666/chemclaw-bot/actions/runs/40409174068)，
代码固定为 39196be9。每份 ditto 压缩包均解压并通过严格签名验证。

| 架构 | ditto 级别 | 压缩秒数 | MiB |
| --- | ---: | ---: | ---: |
| arm64 | 1 | 13.35 | 473.6 |
| arm64 | 6 | 35.63 | 422.9 |
| arm64 | 9 | 81.87 | 420.6 |
| x64 | 1 | 20.29 | 487.9 |
| x64 | 6 | 81.06 | 434.6 |
| x64 | 9 | 138.75 | 432.1 |

原压缩阶段 arm64 约 170 秒、x64 约 399 秒，原包分别约 405、417 MiB。
6 级相对 9 级只多约 2～3 MiB，相对原方案约大 4%，压缩步骤约快 80%，
因此采用 6 级。原包大小取 Actions 上传的单文件产物大小，含极少量外层封装。

仅修改 Release 工作流中的 Mac 打包：先用 electron-builder 生成签名应用，
再用系统 ditto 创建同名 ZIP，保留资源属性、父目录和符号链接。
解压后的架构、严格验签、mock 启动、文件预览和更新检查全部保留，
所有平台通过后才允许正式发布。Windows 打包和应用更新接口不变。

实际新流程通过 [Actions 40413063180](https://github.com/zoeyzhang233666/chemclaw-bot/actions/runs/40413063180)
完成验证，代码为 0016d5f6。Windows 和两种 Mac 架构全部成功，发布步骤按 dry run 跳过。

| 架构 | 打包与签名步骤 | ZIP 步骤 | ditto 实际压缩 | 解压及应用检查 | Mac 任务总耗时 |
| --- | ---: | ---: | ---: | ---: | ---: |
| arm64 | 1m04s | 37s | 36.34s | 31s | 3m16s |
| x64 | 6m15s | 1m14s | 65.73s | 2m21s | 13m59s |

任务总耗时还包括检出、依赖安装、缓存和产物上传；ZIP 步骤包含压缩前的验签。
这是指定 runner 上的一次实测，网络和机器负载会影响后续完整任务用时。
保留所有技能、运行资源和原有签名要求，没有修改 DSH 或发布新版本。
