param(
  [string]$CatalogJson = '',
  [string]$CatalogPath = '',
  [string]$ResultPath = ''
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Windows PowerShell 5 defaults to the system ANSI code page. Catalog JSON is UTF-8.
if ($CatalogPath) {
  $catalogText = [System.IO.File]::ReadAllText($CatalogPath, [System.Text.UTF8Encoding]::new($false))
  $catalog = $catalogText | ConvertFrom-Json
} else {
  $catalog = $CatalogJson | ConvertFrom-Json
}
$form = New-Object System.Windows.Forms.Form
$form.Text = 'ChemClaw GUI Preview'
$form.Size = New-Object System.Drawing.Size(720, 560)
$form.StartPosition = 'CenterScreen'
$form.MinimizeBox = $false
$form.MaximizeBox = $false
$form.FormBorderStyle = 'FixedDialog'

$label = New-Object System.Windows.Forms.Label
$label.Text = 'Select a preview source. Integration reuses a single PR worktree when possible.'
$label.Location = New-Object System.Drawing.Point(16, 12)
$label.Size = New-Object System.Drawing.Size(680, 32)
$form.Controls.Add($label)

$list = New-Object System.Windows.Forms.ListBox
$list.Location = New-Object System.Drawing.Point(16, 48)
$list.Size = New-Object System.Drawing.Size(680, 220)
$list.IntegralHeight = $false
foreach ($item in $catalog.items) {
  [void]$list.Items.Add($item.label)
}
if ($catalog.selectedIndex -ge 0 -and $catalog.selectedIndex -lt $list.Items.Count) {
  $list.SelectedIndex = $catalog.selectedIndex
} elseif ($list.Items.Count -gt 0) {
  $list.SelectedIndex = 0
}
$form.Controls.Add($list)

$prLabel = New-Object System.Windows.Forms.Label
$prLabel.Text = 'Include open PRs in integration (uncheck to exclude):'
$prLabel.Location = New-Object System.Drawing.Point(16, 280)
$prLabel.Size = New-Object System.Drawing.Size(680, 20)
$form.Controls.Add($prLabel)

$prList = New-Object System.Windows.Forms.CheckedListBox
$prList.Location = New-Object System.Drawing.Point(16, 304)
$prList.Size = New-Object System.Drawing.Size(680, 120)
$prList.CheckOnClick = $true
foreach ($pr in $catalog.prs) {
  $idx = $prList.Items.Add($pr.label)
  if ($pr.included) { $prList.SetItemChecked($idx, $true) }
}
$form.Controls.Add($prList)

$cred = New-Object System.Windows.Forms.CheckBox
$cred.Text = 'Copy API credentials into this isolated profile (off by default)'
$cred.Location = New-Object System.Drawing.Point(16, 432)
$cred.Size = New-Object System.Drawing.Size(500, 24)
$cred.Checked = [bool]$catalog.copyCredentials
$form.Controls.Add($cred)

$status = New-Object System.Windows.Forms.Label
$status.Text = $catalog.status
$status.Location = New-Object System.Drawing.Point(16, 460)
$status.Size = New-Object System.Drawing.Size(680, 20)
$form.Controls.Add($status)

$ok = New-Object System.Windows.Forms.Button
$ok.Text = 'Launch'
$ok.Location = New-Object System.Drawing.Point(500, 488)
$ok.Size = New-Object System.Drawing.Size(90, 28)
$ok.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.AcceptButton = $ok
$form.Controls.Add($ok)

$cancel = New-Object System.Windows.Forms.Button
$cancel.Text = 'Cancel'
$cancel.Location = New-Object System.Drawing.Point(600, 488)
$cancel.Size = New-Object System.Drawing.Size(90, 28)
$cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.CancelButton = $cancel
$form.Controls.Add($cancel)

function Write-Result($object) {
  $json = ($object | ConvertTo-Json -Compress)
  if ($ResultPath) {
    # No BOM: Node JSON.parse rejects the UTF-8 BOM that Set-Content -Encoding utf8 writes.
    [System.IO.File]::WriteAllText($ResultPath, $json, [System.Text.UTF8Encoding]::new($false))
  } else {
    Write-Output $json
  }
}

$result = $form.ShowDialog()
if ($result -ne [System.Windows.Forms.DialogResult]::OK -or $list.SelectedIndex -lt 0) {
  Write-Result ([ordered]@{ cancelled = $true })
  exit 0
}

$included = @()
for ($i = 0; $i -lt $prList.Items.Count; $i++) {
  if ($prList.GetItemChecked($i)) {
    $included += [int]$catalog.prs[$i].number
  }
}

Write-Result ([ordered]@{
  cancelled = $false
  id = $catalog.items[$list.SelectedIndex].id
  copyCredentials = [bool]$cred.Checked
  includedPrs = @($included)
})
exit 0
