$ErrorActionPreference = "Stop"

$port = 9225
$endpoint = "http://127.0.0.1:$port/json/version"

try {
    $response = Invoke-WebRequest -UseBasicParsing $endpoint -TimeoutSec 2
    if ($response.StatusCode -eq 200) {
        Write-Host "Cline browser is already running at $endpoint"
        exit 0
    }
} catch {
    # Browser is not accepting DevTools connections yet; start it below.
}

$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chrome)) {
    $chromeCommand = Get-Command chrome -ErrorAction SilentlyContinue
    if ($chromeCommand) {
        $chrome = $chromeCommand.Source
    }
}

if (-not (Test-Path $chrome)) {
    throw "Chrome was not found. Install Chrome or update this script with your browser path."
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$profileDir = Join-Path $repoRoot "data\flow-browser-profile"
New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

$arguments = @(
    "--remote-debugging-port=$port",
    "--user-data-dir=$profileDir",
    "--no-first-run",
    "--no-default-browser-check",
    "about:blank"
)

Start-Process -FilePath $chrome -ArgumentList $arguments

for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $response = Invoke-WebRequest -UseBasicParsing $endpoint -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            Write-Host "Cline browser started at $endpoint"
            exit 0
        }
    } catch {
    }
}

throw "Chrome started, but DevTools endpoint did not become ready at $endpoint"
