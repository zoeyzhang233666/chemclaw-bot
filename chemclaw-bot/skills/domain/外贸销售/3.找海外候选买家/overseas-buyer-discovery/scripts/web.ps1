param(
  [string]$Mode = "search",
  [string]$Q = "",
  [string]$Url = "",
  [int]$N = 12,
  [int]$Max = 6000
)
$ProgressPreference='SilentlyContinue'
$ua='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Clean([string]$s) {
  if (-not $s) { return "" }
  $s = $s -replace '<script[\s\S]*?</script>',' ' -replace '<style[\s\S]*?</style>',' '
  $s = $s -replace '<[^>]+>',' '
  $s = [System.Net.WebUtility]::HtmlDecode($s)
  return ($s -replace '\s+',' ').Trim()
}

function GetPage([string]$u) {
  for ($i=0; $i -lt 2; $i++) {
    try { return Invoke-WebRequest -Uri $u -TimeoutSec 25 -UseBasicParsing -UserAgent $ua -MaximumRedirection 6 }
    catch { Start-Sleep -Milliseconds 900 }
  }
  return $null
}

function DecodeBing([string]$href) {
  if ($href -notmatch 'u=a1') { return $href }
  $m = [regex]::Match($href, 'u=a1([A-Za-z0-9_\-]+)')
  if (-not $m.Success) { return $href }
  $v = $m.Groups[1].Value.Substring(2)
  $v = $v.Replace('-','+').Replace('_','/')
  while ($v.Length % 4 -ne 0) { $v += '=' }
  try { return [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($v)) } catch { return $href }
}

function RunBrave([string]$q) {
  $enc = [uri]::EscapeDataString($q)
  $r = GetPage "https://search.brave.com/search?q=$enc"
  if (-not $r -or -not $r.Content) { return @() }
  $c = $r.Content
  if ($c -match 'suspicious|captcha') { return @() }
  $hits = @()
  $blocks = [regex]::Split($c, 'data-type="web"')
  foreach ($b in $blocks) {
    $sn = [regex]::Match($b, '<div class="snippet[^"]*"[^>]*>([\s\S]*?)</div>')
    $u  = [regex]::Match($b, 'href="(https?://[^"]+)"')
    $t  = [regex]::Match($b, '<div class="title[^"]*"[^>]*>([\s\S]*?)</div>')
    if ($u.Success -and $t.Success) {
      $ttl = Clean $t.Groups[1].Value
      if ($ttl.Length -gt 0) { $hits += [pscustomobject]@{Title=$ttl; URL=$u.Groups[1].Value; Snippet=(Clean $sn.Groups[1].Value); Engine='brave'} }
    }
  }
  return $hits
}

function RunBing([string]$q) {
  $enc = [uri]::EscapeDataString($q)
  $r = GetPage "https://www.bing.com/search?q=$enc&count=20&setlang=en&cc=US"
  if (-not $r -or -not $r.Content) { return @() }
  $c = $r.Content
  $hits = @()
  $blocks = [regex]::Split($c, '<li class="b_algo"')
  foreach ($b in $blocks[1..($blocks.Count-1)]) {
    $a = [regex]::Match($b, '<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>')
    if (-not $a.Success) { continue }
    $u = DecodeBing ($a.Groups[1].Value -replace '&amp;','&')
    $t = Clean $a.Groups[2].Value
    $p = [regex]::Match($b, '<p[^>]*>([\s\S]*?)</p>')
    $hits += [pscustomobject]@{Title=$t; URL=$u; Snippet=(Clean $p.Groups[1].Value); Engine='bing'}
  }
  return $hits
}

if ($Mode -eq "search") {
  $hits = RunBrave $Q
  if ($hits.Count -eq 0) {
    $hits = RunBing $Q
  }
  if ($hits.Count -eq 0) { "NO_RESULTS" } else {
    $i=0
    foreach ($h in ($hits | Select-Object -First $N)) {
      $i++
      $sn = if($h.Snippet.Length -gt 300){$h.Snippet.Substring(0,300)}else{$h.Snippet}
      "[$i] ($($h.Engine)) $($h.Title)`n    $($h.URL)`n    $sn"
    }
  }
}
elseif ($Mode -eq "bing") {
  $hits = RunBing $Q
  $i=0; foreach ($h in ($hits | Select-Object -First $N)) { $i++; $sn = if($h.Snippet.Length -gt 300){$h.Snippet.Substring(0,300)}else{$h.Snippet}; "[$i] $($h.Title)`n    $($h.URL)`n    $sn" }
}
elseif ($Mode -eq "fetch") {
  $r = GetPage $Url
  if (-not $r) { "FETCH_FAIL $Url" } else {
    $txt = Clean ([string]$r.Content)
    "URL: $Url  STATUS: $($r.StatusCode)  LEN: $($txt.Length)"
    if ($txt.Length -gt $Max) { $txt.Substring(0,$Max) } else { $txt }
  }
}
elseif ($Mode -eq "grep") {
  $r = GetPage $Url
  if (-not $r) { "FETCH_FAIL $Url" } else {
    $txt = Clean ([string]$r.Content)
    $hits = [regex]::Matches($txt, "(.{0,200}" + [regex]::Escape($Q) + ".{0,200})", 'IgnoreCase')
    "URL: $Url  LEN: $($txt.Length)  matches: $($hits.Count)"
    $hits | Select-Object -First $N | ForEach-Object { "  ... " + $_.Groups[1].Value }
  }
}
