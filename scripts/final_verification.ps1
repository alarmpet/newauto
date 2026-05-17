$ErrorActionPreference = "Stop"

$pythonExe = & "$PSScriptRoot\resolve_omnivoice_python.ps1"

Write-Host "[1/5] Py compile"
& $pythonExe -m compileall app scripts tests

Write-Host "[2/5] Typecheck"
powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\typecheck.ps1"

Write-Host "[3/5] Node syntax check"
node --check app/static/app.js

Write-Host "[4/5] Pytest baseline"
& $pythonExe -m pytest -q

Write-Host "[5/5] Agent smoke"
& $pythonExe "$PSScriptRoot\agent_eval_smoke.py" --skip-web

Write-Host "Final verification passed."
