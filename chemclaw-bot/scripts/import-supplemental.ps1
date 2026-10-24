param([string]$Source)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$packageRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$destination = Join-Path $packageRoot 'skills\supplemental'
$selected = @('rdkit', 'networkx', 'scientific-visualization', 'statistical-analysis', 'sympy')
$records = @()
foreach ($file in (Get-ChildItem -LiteralPath $Source -Recurse -Filter '*.zip' | Where-Object BaseName -In $selected)) {
  $archive = [IO.Compression.ZipFile]::OpenRead($file.FullName)
  try {
    foreach ($entry in $archive.Entries) {
      if ($entry.FullName -match '(^|/)(\.git|__pycache__|node_modules|\.venv)/|\.(zip|exe|pyc)$' -or $entry.FullName.EndsWith('/')) { continue }
      $target = [IO.Path]::GetFullPath((Join-Path (Join-Path $destination $file.BaseName) $entry.FullName))
      if (!$target.StartsWith($destination + [IO.Path]::DirectorySeparatorChar)) { throw 'Archive entry escaped destination' }
      [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
      [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
    }
    $records += @{name=$file.BaseName; archiveSha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash; origin='User-provided chemical/scientific skill collection'; license='See SKILL.md license declaration and bundled license notices'}
  } finally { $archive.Dispose() }
}
[IO.File]::WriteAllText((Join-Path $packageRoot 'seed\supplemental-sources.json'), ($records | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
