# Linux 打包门禁：sharp / Electron SIGSEGV

## 结论

PR #47 能打出 Linux x64 AppImage、deb 与 `latest-linux.yml`，单元测试与浏览器隔离检查也通过。`check-packed` 在 Linux 上于 **packaged sharp** 步骤以 `SIGSEGV` 失败，并打印 sharp 官方警告：`Binaries provided by Electron for use on Linux may be incompatible with sharp`。

因此：**不能把 Linux 包当作平台验收通过**。Windows / macOS 打包门禁在同一次 CI 中已通过。

## 复现（GitHub Actions）

- 工作流：`Test` / `Desktop app package (Linux x64)`  
  例：`https://github.com/zoeyzhang233666/chemclaw-bot/actions/runs/40529683403/job/122279674067`
- 失败点：`xvfb-run -a node scripts/check-packed.mjs` → `checkSharp` 用打包后的 Electron（`ELECTRON_RUN_AS_NODE=1`）加载 asar 内 `sharp` 并做最小缩放。
- 现象：`exit null, signal SIGSEGV`，伴随 `[SharpElectronLinux] Warning`。

## 已排除

- deb 缺少 `homepage`：已由 `33bfc2c9` 补项目主页元数据，打包产物检查通过。
- asar 未解开 libvips：`electron-builder.yml` 已 `asarUnpack: node_modules/@img/sharp*/**`，`package.test.mjs` 覆盖版本化 `.so` / `.node`。

## 后续方向（未在本批合入）

- 对照 sharp 文档为 Electron Linux 选用兼容预编译或 wasm 回退，再在真实 Electron 主进程（非仅 `ELECTRON_RUN_AS_NODE`）复验图像处理。
- 在修复前保持 Linux 打包 job 失败，避免发版。
