param(
  [string]$SidecarExe = "",
  [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
if ([string]::IsNullOrWhiteSpace($SidecarExe)) {
  $SidecarExe = Join-Path $root "dist\newauto-sidecar\newauto-sidecar.exe"
}

if (-not (Test-Path -LiteralPath $SidecarExe)) {
  Write-Error "Missing sidecar executable: $SidecarExe"
}

$smokeDir = Join-Path $env:TEMP ("newauto-sidecar-smoke-" + [guid]::NewGuid().ToString("N"))
$stdoutPath = Join-Path $smokeDir "stdout.log"
$stderrPath = Join-Path $smokeDir "stderr.log"
$dataDir = Join-Path $smokeDir "data"
New-Item -ItemType Directory -Force -Path $smokeDir, $dataDir | Out-Null

$previousDisableWorkers = $env:NEWAUTO_DISABLE_BACKGROUND_WORKERS
$previousDataDir = $env:NEWAUTO_DATA_DIR
$process = $null

try {
  $env:NEWAUTO_DISABLE_BACKGROUND_WORKERS = "1"
  $env:NEWAUTO_DATA_DIR = $dataDir

  $process = Start-Process `
    -FilePath $SidecarExe `
    -ArgumentList @("--serve", "--host", "127.0.0.1", "--port", "0") `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru `
    -WindowStyle Hidden

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $port = $null
  while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) {
      $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { "" }
      $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { "" }
      Write-Error "Sidecar exited before handshake. ExitCode=$($process.ExitCode)`nSTDOUT:`n$stdout`nSTDERR:`n$stderr"
    }

    if (Test-Path -LiteralPath $stdoutPath) {
      $match = Select-String -LiteralPath $stdoutPath -Pattern "NEWAUTO_LISTEN_PORT=(\d+)" | Select-Object -First 1
      if ($match) {
        $port = [int]$match.Matches[0].Groups[1].Value
        break
      }
    }

    Start-Sleep -Milliseconds 250
  }

  if (-not $port) {
    $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { "" }
    $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { "" }
    Write-Error "Timed out waiting for NEWAUTO_LISTEN_PORT after $TimeoutSeconds seconds.`nSTDOUT:`n$stdout`nSTDERR:`n$stderr"
  }

  $healthUrl = "http://127.0.0.1:$port/health"
  $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 10
  if (-not $health.ok) {
    $healthJson = $health | ConvertTo-Json -Depth 8
    Write-Error "Health endpoint did not report ok=true: $healthJson"
  }

  [pscustomobject]@{
    ok = $true
    port = $port
    health = $health
    sidecar = $SidecarExe
    data_dir = $dataDir
    stdout = $stdoutPath
    stderr = $stderrPath
  } | ConvertTo-Json -Depth 8
}
finally {
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
    $process.WaitForExit(5000) | Out-Null
  }
  $env:NEWAUTO_DISABLE_BACKGROUND_WORKERS = $previousDisableWorkers
  $env:NEWAUTO_DATA_DIR = $previousDataDir
}
