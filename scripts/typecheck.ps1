$ErrorActionPreference = "Stop"

$pythonExe = & "$PSScriptRoot\resolve_omnivoice_python.ps1"

npx tsc -p tsconfig.json
& $pythonExe -m mypy app tests scripts
& $pythonExe scripts/check_encoding.py
