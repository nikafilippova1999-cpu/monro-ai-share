param(
  [string]$DataFile = "C:\Users\67A9~1\nika-bot\data\dialogs_2026-07-27.json",
  [int]$PingMinutes = 10
)
$ErrorActionPreference = 'Stop'

$d = Get-Content $DataFile -Raw -Encoding utf8 | ConvertFrom-Json

$OUR = @('manager','arthur_ai','bot')

function Is-PaymentRequest($m) {
  if ($m.sender_type -notin $OUR) { return $false }
  if ($m.text -match 'pay=\d+') { return $true }
  if ($m.text -match '\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}') { return $true }
  return $false
}

$events = New-Object System.Collections.ArrayList

foreach ($dlg in $d) {
  $ms = @($dlg.messages | Sort-Object { [datetime]$_.sent_at })
  for ($i = 0; $i -lt $ms.Count; $i++) {
    $m = $ms[$i]
    if (-not (Is-PaymentRequest $m)) { continue }
    $T = [datetime]$m.sent_at
    $deadline = $T.AddMinutes($PingMinutes)

    $followAny = $null; $followMgr = $null; $clientReply = $null
    for ($j = $i + 1; $j -lt $ms.Count; $j++) {
      $n = $ms[$j]
      $tn = [datetime]$n.sent_at
      if ($tn -le $T) { continue }
      if ($tn -gt $deadline) { break }
      if ($n.sender_type -eq 'client') { if (-not $clientReply) { $clientReply = $n } ; continue }
      if ($n.sender_type -in $OUR) {
        if (-not $followAny) { $followAny = $n }
        if ($n.sender_type -eq 'manager' -and -not $followMgr) { $followMgr = $n }
      }
    }
    # next our-side message at any time (to measure real delay)
    $nextOur = $null
    for ($j = $i + 1; $j -lt $ms.Count; $j++) {
      $n = $ms[$j]
      if ($n.sender_type -in $OUR -and ([datetime]$n.sent_at) -gt $T) { $nextOur = $n; break }
    }
    $delayMin = $null
    if ($nextOur) { $delayMin = [math]::Round(((([datetime]$nextOur.sent_at) - $T).TotalMinutes), 1) }

    [void]$events.Add([pscustomobject]@{
      customer_id   = $dlg.customer_id
      dialog_id     = $m.dialog_id
      message_id    = $m.message_id
      sent_at       = $m.sent_at
      req_sender    = $m.sender_type
      req_name      = $m.sender_name
      manager       = $(if ($dlg.manager) { $dlg.manager.name } else { $null })
      has_order     = ($dlg.orders.Count -gt 0)
      followAny     = [bool]$followAny
      followMgr     = [bool]$followMgr
      clientReply   = [bool]$clientReply
      next_our_delay_min = $delayMin
      text          = $m.text
    })
  }
}

"=== PAYMENT REQUEST EVENTS: $($events.Count) ==="
"by sender of request:"
$events | Group-Object req_sender | ForEach-Object { "  {0,-12} {1}" -f $_.Name, $_.Count }
""
"=== VARIANT 1: ping = ANY our-side message (manager/AI/bot) within $PingMinutes min ==="
$v1 = $events | Where-Object { -not $_.followAny }
"  no ping: $($v1.Count) of $($events.Count)"
"  of them, client replied in window: $(($v1 | Where-Object { $_.clientReply }).Count)"
"  of them, dialog has order:         $(($v1 | Where-Object { $_.has_order }).Count)"
""
"=== VARIANT 2: ping = HUMAN manager message only within $PingMinutes min ==="
$v2 = $events | Where-Object { -not $_.followMgr }
"  no manager ping: $($v2.Count) of $($events.Count)"
""
"=== VARIANT 3 (recommended): no our-side ping AND client silent AND no order ==="
$v3 = $events | Where-Object { -not $_.followAny -and -not $_.clientReply -and -not $_.has_order }
"  flagged: $($v3.Count)"
$v3 | Sort-Object sent_at | ForEach-Object {
  $delay = if ($_.next_our_delay_min -eq $null) { "нет ответа вообще" } else { "$($_.next_our_delay_min) мин" }
  "  cid=$($_.customer_id) $($_.sent_at) req=$($_.req_sender)/$($_.req_name) mgr=$($_.manager) next_our=$delay"
}
