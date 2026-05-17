$python = "C:\Users\petbl\AppData\Local\Programs\Python\Python310\python.exe"
$workdir = "C:\Users\petbl\autotube\ComfyUI"
$logDir = Join-Path $PSScriptRoot "..\storage\logs"
$stdout = Join-Path $logDir "comfyui_stdout.log"
$stderr = Join-Path $logDir "comfyui_stderr.log"
$port = if ($env:COMFYUI_PORT) { $env:COMFYUI_PORT } else { "8188" }

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$existing = Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -like "*main.py*--port $port*"
}
if ($existing) {
  Write-Output "ComfyUI already running on port $port"
  $existing | Select-Object ProcessId, Name, CommandLine
  exit 0
}

Remove-Item $stdout, $stderr -ErrorAction SilentlyContinue

$process = Start-Process `
  -FilePath $python `
  -ArgumentList @("main.py", "--listen", "--port", $port) `
  -WorkingDirectory $workdir `
  -RedirectStandardOutput $stdout `
  -RedirectStandardError $stderr `
  -WindowStyle Hidden `
  -PassThru

Start-Sleep -Seconds 8

Write-Output "Started ComfyUI"
Write-Output "PID=$($process.Id)"
Write-Output "PORT=$port"
Write-Output "STDOUT=$stdout"
Write-Output "STDERR=$stderr"
