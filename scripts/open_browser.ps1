Start-Sleep -Seconds 2
$base = $env:NEWAUTO_BASE_URL
if (-not $base) { $base = "http://127.0.0.1:9002" }
Start-Process $base
