# Linux 打包门禁：sharp / Electron SIGSEGV（已修复）

## 结论

原始 PR #47 能打包，但 `check-packed` 在 packaged sharp 步骤以 SIGSEGV 失败。Ubuntu 26.04 复现确认是 Electron 系统 GLib 与原生 libvips 的符号冲突。仅解包原生库不能解决。

修复提交 `40129ea8` 在 Linux 包排除原生 sharp/libvips，让 sharp 原有加载器使用匹配版本的官方 `@img/sharp-wasm32`；Windows/macOS 保持原生后端，无 DSH 源码修改。`7e9d05eb` 修正隔离更新源的 JSON/YAML 协议；`0c7e5003` 为无桌面 runner 注册临时 XDG 处理程序并断言准确的 open/reveal 路径，避免真实文件管理器等待不退出。

**Linux x64 门禁已通过**：[PR #47 Ubuntu 验收](https://github.com/zoeyzhang233666/chemclaw-bot/actions/runs/40606640902/job/122547879539)。包括真实打包图像处理、Bot 浏览器、聊天/图表/侧聊、deb 安装后复查与手动更新、AppImage 自动更新后的 SHA512 一致性、卸载。WASM 的实验性状态与限制见 Linux 设计记录。整批功能仍保持草稿，不因单个平台通过而合并或发版。

## 复现（GitHub Actions）

- 工作流：`Test` / `Desktop app package (Linux x64)`  
  例：`https://github.com/zoeyzhang233666/chemclaw-bot/actions/runs/40529683403/job/122279674067`
- 失败点：`xvfb-run -a node scripts/check-packed.mjs` → `checkSharp` 用打包后的 Electron（`ELECTRON_RUN_AS_NODE=1`）加载 asar 内 `sharp` 并做最小缩放。
- 现象：`exit null, signal SIGSEGV`，伴随 `[SharpElectronLinux] Warning`。

## 已排除

- deb 缺少 `homepage`：已由 `33bfc2c9` 补项目主页元数据，打包产物检查通过。
- asar 未解开 libvips：`electron-builder.yml` 已 `asarUnpack: node_modules/@img/sharp*/**`，`package.test.mjs` 覆盖版本化 `.so` / `.node`。

## 验证边界

- Windows 桌面单元测试：147 通过、1 项 Linux 专用跳过；Ubuntu：147 通过、1 项平台相关跳过。
- 本地 WSL 已验证真实打包 sharp 和聊天交互；其原生文件打开走 Windows 桌面，不代替 Ubuntu runner 的原生打开、安装和更新证据。
- DSH Host 仍使用公开启动入口与 Electron Node 模式，未替换运行时或修改依赖源码。
