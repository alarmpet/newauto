param(
  [string]$AppExe = "",
  [int]$TimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
if ([string]::IsNullOrWhiteSpace($AppExe)) {
  $AppExe = Join-Path $root "src-tauri\target\debug\newauto-studio.exe"
}

if (-not (Test-Path -LiteralPath $AppExe)) {
  Write-Error "Missing Tauri executable: $AppExe"
}

$smokeDir = Join-Path $env:TEMP ("newauto-tauri-smoke-" + [guid]::NewGuid().ToString("N"))
$stdoutPath = Join-Path $smokeDir "stdout.log"
$stderrPath = Join-Path $smokeDir "stderr.log"
$portFile = Join-Path $smokeDir "port.txt"
New-Item -ItemType Directory -Force -Path $smokeDir | Out-Null

$previousPortFile = $env:NEWAUTO_STUDIO_PORT_FILE
$previousDisableWorkers = $env:NEWAUTO_DISABLE_BACKGROUND_WORKERS
$process = $null
$port = $null

try {
  $env:NEWAUTO_STUDIO_PORT_FILE = $portFile
  $env:NEWAUTO_DISABLE_BACKGROUND_WORKERS = "1"

  $process = Start-Process `
    -FilePath $AppExe `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) {
      $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { "" }
      $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { "" }
      Write-Error "Tauri app exited before writing port file. ExitCode=$($process.ExitCode)`nSTDOUT:`n$stdout`nSTDERR:`n$stderr"
    }

    if (Test-Path -LiteralPath $portFile) {
      $portText = (Get-Content -LiteralPath $portFile -Raw).Trim()
      if ($portText -match "^\d+$") {
        $port = [int]$portText
        break
      }
    }

    Start-Sleep -Milliseconds 250
  }

  if (-not $port) {
    $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { "" }
    $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { "" }
    Write-Error "Timed out waiting for Tauri port file after $TimeoutSeconds seconds.`nSTDOUT:`n$stdout`nSTDERR:`n$stderr"
  }

  $healthUrl = "http://127.0.0.1:$port/health"
  $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 10
  if (-not $health.ok) {
    $healthJson = $health | ConvertTo-Json -Depth 8
    Write-Error "Health endpoint did not report ok=true: $healthJson"
  }

  $result = [pscustomobject]@{
    ok = $true
    port = $port
    health = $health
    app = $AppExe
    port_file = $portFile
    stdout = $stdoutPath
    stderr = $stderrPath
  } | ConvertTo-Json -Depth 8
  Write-Output $result
}
finally {
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
    $process.WaitForExit(5000) | Out-Null
  }
  if ($port) {
    Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $port -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique |
      ForEach-Object {
        if ($_ -and $_ -ne $PID) {
          Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
        }
      }
  }
  $env:NEWAUTO_STUDIO_PORT_FILE = $previousPortFile
  $env:NEWAUTO_DISABLE_BACKGROUND_WORKERS = $previousDisableWorkers
}
