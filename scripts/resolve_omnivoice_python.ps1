$ErrorActionPreference = "Stop"

$candidates = @()

if ($env:OMNIVOICE_PYTHON) {
    $candidates += $env:OMNIVOICE_PYTHON
}

if ($env:OMNIVOICE_ENV_DIR) {
    $candidates += Join-Path $env:OMNIVOICE_ENV_DIR "Scripts\python.exe"
}

$candidates += @(
    (Join-Path $PSScriptRoot "..\omnivoice_env\Scripts\python.exe"),
    "C:\Users\petbl\music-auto\.venv_omnivoice\Scripts\python.exe"
)

$seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

foreach ($candidate in $candidates) {
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        continue
    }

    if (-not $seen.Add($candidate)) {
        continue
    }

    if (-not (Test-Path -LiteralPath $candidate)) {
        continue
    }

    $venvRoot = Split-Path -Parent (Split-Path -Parent $candidate)
    $sitePackages = Join-Path $venvRoot "Lib\site-packages"
    $requiredPackages = @(
        "omnivoice",
        "fastapi",
        "uvicorn",
        "multipart",
        "googleapiclient"
    )

    $missingPackage = $false
    foreach ($packageName in $requiredPackages) {
        if (-not (Test-Path -LiteralPath (Join-Path $sitePackages $packageName))) {
            $missingPackage = $true
            break
        }
    }

    if (-not $missingPackage) {
        (Resolve-Path -LiteralPath $candidate).Path
        exit 0
    }
}

Write-Error "No usable OmniVoice Python environment found. Set OMNIVOICE_PYTHON or OMNIVOICE_ENV_DIR first."
exit 1
