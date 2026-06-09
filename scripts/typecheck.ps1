$ErrorActionPreference = "Stop"

$pythonExe = & "$PSScriptRoot\resolve_omnivoice_python.ps1"

npx tsc -p tsconfig.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $pythonExe -m mypy app
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $pythonExe scripts/check_encoding.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
