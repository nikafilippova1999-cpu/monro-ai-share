param(
  [string]$Date = "2026-07-27",
  [string]$OutDir = "C:\Users\Менеджер\nika-bot\data"
)

$ErrorActionPreference = "Stop"
$token = 'EQWbTNEJUxWHXB13W$402QVLvf8@$#Rb'
$url = 'https://crm.easy-mo.ru/external/v1/customers/dialogs/export'
$headers = @{ Authorization = "Bearer $token" }

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$all = New-Object System.Collections.ArrayList
$page = 1
$lastPage = 1

while ($page -le $lastPage) {
  $body = "{`"date_from`":`"$Date`",`"date_to`":`"$Date`",`"department_ids`":[122],`"page`":$page,`"per_page`":100}"
  $ok = $false
  for ($try = 1; $try -le 3 -and -not $ok; $try++) {
    try {
      $r = Invoke-RestMethod -Uri $url -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 300
      $ok = $true
    } catch {
      Write-Host "page $page try $try failed: $($_.Exception.Message)"
      if ($try -eq 3) { throw }
      Start-Sleep -Seconds 5
    }
  }
  $lastPage = $r.pagination.last_page
  foreach ($d in $r.dialogs) { [void]$all.Add($d) }
  Write-Host "page $page/$lastPage -> +$($r.dialogs.Count) (total collected: $($all.Count))"
  $page++
}

$outFile = Join-Path $OutDir "dialogs_$Date.json"
$all | ConvertTo-Json -Depth 12 | Out-File -FilePath $outFile -Encoding utf8
Write-Host "SAVED: $outFile ; dialogs=$($all.Count)"
