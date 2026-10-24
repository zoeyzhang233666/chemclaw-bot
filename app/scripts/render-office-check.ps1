param([string]$Folder = "$PSScriptRoot/../../chemclaw/verification/deliverables")
$ErrorActionPreference = 'Stop'
$folderPath = (Resolve-Path -LiteralPath $Folder).Path
$deck = (Get-ChildItem -LiteralPath $folderPath -Filter '*sample.pptx' | Select-Object -First 1).FullName
$document = (Get-ChildItem -LiteralPath $folderPath -Filter '*sample.docx' | Select-Object -First 1).FullName
$powerpoint = $null
$word = $null
try {
  $powerpoint = New-Object -ComObject PowerPoint.Application
  $presentation = $powerpoint.Presentations.Open($deck, -1, 0, 0)
  $presentation.SaveAs((Join-Path $folderPath 'ppt-rendered.pdf'), 32)
  $presentation.Export((Join-Path $folderPath 'ppt-pages'), 'PNG', 1600, 900)
  Write-Output "PPT slides: $($presentation.Slides.Count)"
  $presentation.Close()
} finally {
  if ($powerpoint) { $powerpoint.Quit(); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($powerpoint) }
}
try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $word.DisplayAlerts = 0
  $opened = $word.Documents.Open($document, $false, $true)
  $opened.ExportAsFixedFormat((Join-Path $folderPath 'docx-rendered.pdf'), 17)
  Write-Output "Word pages: $($opened.ComputeStatistics(2))"
  $opened.Close(0)
} finally {
  if ($word) { $word.Quit(); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) }
}
