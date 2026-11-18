param([string]$InFile = "urls.txt", [string]$Max = "2500", [string]$OutDir = "fetchout")
$ProgressPreference='SilentlyContinue'
$ua='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
[Net.ServicePointManager]::DefaultConnectionLimit = 32

$urls = Get-Content $InFile | Where-Object { $_ -match '^https?://' } | Select-Object -Unique
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function DoFetch($u, $max, $outDir, $ua) {
  try {
    $r = Invoke-WebRequest -Uri $u -TimeoutSec 30 -UseBasicParsing -UserAgent $ua -MaximumRedirection 6
    $t = [string]$r.Content -replace '<script[\s\S]*?</script>',' ' -replace '<style[\s\S]*?</style>',' ' -replace '<[^>]+>',' '
    $t = [System.Net.WebUtility]::HtmlDecode($t) -replace '\s+',' '
    $t = $t.Trim()
    $name = ($u -replace '[^A-Za-z0-9]+','_')
    if ($name.Length -gt 120) { $name = $name.Substring(0,120) }
    if ($t.Length -gt [int]$max) { $body = $t.Substring(0,[int]$max) + " ...[TRUNCATED]" } else { $body = $t }
    Set-Content -Path (Join-Path $outDir ($name + ".txt")) -Value ("URL: $u`nSTATUS: $($r.StatusCode)`nLEN: $($t.Length)`n`n" + $body) -Encoding UTF8
    "OK   $($r.StatusCode) len=$($t.Length)  $u"
  } catch {
    "FAIL $u :: $($_.Exception.Message)"
  }
}

$jobs = @()
foreach ($u in $urls) {
  $jobs += Start-Job -ScriptBlock ${function:DoFetch} -ArgumentList $u, $Max, (Resolve-Path $OutDir).Path, $ua
}
$done = $jobs | Wait-Job -Timeout 600
$jobs | Receive-Job
$jobs | Remove-Job -Force -ErrorAction SilentlyContinue


