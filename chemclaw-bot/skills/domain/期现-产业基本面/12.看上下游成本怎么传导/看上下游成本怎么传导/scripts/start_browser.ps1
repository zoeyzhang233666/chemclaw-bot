# 启动带调试端口的无头 Chrome，供 qa_render.py 实测 HTML
# 用法：powershell -ExecutionPolicy Bypass -File scripts/start_browser.ps1 [-Port 9333]
param([int]$Port = 9333)

$candidates = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)
$exe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $exe) {
  Write-Host "未找到 Chrome/Edge，跳过浏览器实测（静态检查仍可用）"
  exit 1
}

$profile = Join-Path $env:TEMP "dsh_qa_profile_$Port"
$args = @(
  "--headless=new",
  "--remote-debugging-port=$Port",
  "--disable-gpu",
  "--no-first-run",
  "--no-default-browser-check",
  "--user-data-dir=$profile",
  "about:blank"
)
Start-Process -FilePath $exe -ArgumentList $args | Out-Null

for ($i = 0; $i -lt 20; $i++) {
  Start-Sleep -Milliseconds 400
  try {
    $v = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/json/version" -UseBasicParsing -TimeoutSec 3
    Write-Host "浏览器已就绪：$exe  (端口 $Port)"
    ($v.Content | ConvertFrom-Json).Browser
    exit 0
  } catch { }
}
Write-Host "浏览器启动超时"
exit 1
