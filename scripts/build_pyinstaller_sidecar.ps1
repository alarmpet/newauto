$ErrorActionPreference = "Stop"

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$pythonExe = & "$PSScriptRoot\resolve_omnivoice_python.ps1"
$distDir = Join-Path $root "dist\newauto-sidecar"
$workDir = Join-Path $root "dist\pyinstaller-work"

$excludedModules = @(
  "accelerate",
  "diffusers",
  "gradio",
  "joblib",
  "llvmlite",
  "matplotlib",
  "numba",
  "nvidia",
  "pandas",
  "scipy",
  "sklearn",
  "tensorboardX",
  "torch",
  "torchaudio",
  "torchvision",
  "transformers"
)

Write-Host "[1/3] Ensure PyInstaller"
& $pythonExe -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[2/3] Build FastAPI sidecar"
$excludeArgs = @()
foreach ($module in $excludedModules) {
  $excludeArgs += @("--exclude-module", $module)
}

& $pythonExe -m PyInstaller `
  --noconfirm `
  --onedir `
  --name newauto-sidecar `
  --distpath (Join-Path $root "dist") `
  --workpath $workDir `
  --specpath $workDir `
  --collect-data app `
  --hidden-import uvicorn `
  --hidden-import uvicorn.logging `
  --hidden-import uvicorn.loops `
  --hidden-import uvicorn.loops.auto `
  --hidden-import uvicorn.protocols `
  --hidden-import uvicorn.protocols.http `
  --hidden-import uvicorn.protocols.http.auto `
  --hidden-import uvicorn.protocols.websockets `
  --hidden-import uvicorn.protocols.websockets.auto `
  --hidden-import uvicorn.lifespan `
  --hidden-import uvicorn.lifespan.on `
  @excludeArgs `
  "$root\scripts\pyinstaller_entry.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[3/3] Smoke sidecar command"
$exe = Join-Path $distDir "newauto-sidecar.exe"
if (-not (Test-Path -LiteralPath $exe)) {
  Write-Error "Missing sidecar executable: $exe"
}

Write-Host "Built sidecar: $exe"
Write-Host "Run for Tauri handshake smoke:"
Write-Host "  $exe --serve --host 127.0.0.1 --port 0"
