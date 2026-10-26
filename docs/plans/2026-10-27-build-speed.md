# 高频更新的构建耗时

v0.2.2 的 Intel Mac Release 任务耗时 19m50s，npm 安装 2m50s、打包 14m19s；
其中 ZIP 生成约 7m37s。Apple 芯片任务耗时 7m06s。基准来自 Actions 40372100098。

日常 PR/main 的 Mac 检查改为签名 .app 的架构、独立启动、更新路径验收；
避免每次生成 ZIP 并重复启动同一个成品。正式 Release 和 dry run 仍生成 ZIP，
并对解压后的应用验签、核对架构、运行 mock 启动和更新检查，成功后才上传发布。
不改变完整发布的资产门禁、不降级签名，也不删除技能与运行资源。

Mac jobs 缓存 npm 下载，以及按 OS、架构、app lockfile 区分的 Electron/Builder
下载缓存。原生依赖仍在当前 runner 安装；不跨架构复用 node_modules。
缓存路径也传给 npm ci；Electron 的安装脚本使用 electron_config_cache，
打包器使用 ELECTRON_CACHE，两者指向同一个已恢复的目录。
缓存键升级为 desktop-tools-v2：首代缓存只保存了打包器（约 9 MB），
GitHub 同名精确命中的缓存不能追加内容；换代后才能保存完整 Electron 下载。

可选 dry-run 输入 benchmark_mac_zip 调用 benchmark-mac-zip.mjs，比较同一个
签名 .app 用 ditto 的 1/6/9 级压缩耗时和体积，每份都解压验签，记录 Actions
summary 与 JSON。它是压缩候选实验，不等同于 electron-builder 默认压缩器，
不自动替换正式压缩方案；未经实测不承诺新的正式 Release 用时。

桌面壳/插件独立升级和包内容瘦身另行设计；本次保留完整运行资源。
