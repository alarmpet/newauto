param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$PythonExe = "",
    [string]$VenvPath = "",
    [string]$LmStudioModel = "qwen/qwen3.5-9b",
    [int]$LmStudioContext = 131072,
    [switch]$InstallTools,
    [switch]$PersistUserEnv,
    [switch]$UpdateClineMcpSettings,
    [switch]$StartLmStudioServer,
    [switch]$SkipPythonDeps
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-WarnLine {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Require-Command {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "Required command not found: $Name"
    }
    return $cmd.Source
}

function Set-UserEnv {
    param([string]$Name, [string]$Value)
    [Environment]::SetEnvironmentVariable($Name, $Value, "User")
    Set-Item -Path "Env:$Name" -Value $Value
    Write-Ok "User environment set: $Name=$Value"
}

function Add-UserPathEntry {
    param([string]$PathEntry)
    if (-not (Test-Path $PathEntry)) {
        Write-WarnLine "PATH entry does not exist yet: $PathEntry"
    }

    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($current) {
        $parts = $current -split ";" | Where-Object { $_ -and $_.Trim() }
    }
    $already = $parts | Where-Object { $_.TrimEnd("\") -ieq $PathEntry.TrimEnd("\") }
    if ($already) {
        Write-Ok "User PATH already contains: $PathEntry"
        return
    }

    $newPath = if ($current) { "$current;$PathEntry" } else { $PathEntry }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $env:Path = "$env:Path;$PathEntry"
    Write-Ok "Added to user PATH: $PathEntry"
}

function Install-WithWinget {
    param([string]$Id, [string]$Name)
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget is not available. Install App Installer from Microsoft Store or install tools manually."
    }
    Write-Step "Installing $Name with winget"
    winget install --id $Id --exact --accept-package-agreements --accept-source-agreements
}

function ConvertTo-JsonDepth {
    param($Value)
    return ($Value | ConvertTo-Json -Depth 20)
}

Write-Step "Resolving project paths"
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
if (-not $VenvPath) {
    $localRagVenvPython = Join-Path $env:USERPROFILE "local-rag\.venv\Scripts\python.exe"
    if (Test-Path $localRagVenvPython) {
        $VenvPath = Join-Path $env:USERPROFILE "local-rag\.venv"
    } else {
        $VenvPath = Join-Path $ProjectRoot ".venv"
    }
}
$VenvPath = [System.IO.Path]::GetFullPath($VenvPath)
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$VenvPip = Join-Path $VenvPath "Scripts\pip.exe"
$RequirementsPath = Join-Path $ProjectRoot "requirements.txt"
$ClineSettingsPath = Join-Path $env:APPDATA "Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json"
$LmStudioCli = Join-Path $env:USERPROFILE ".lmstudio\bin\lms.exe"

Write-Ok "ProjectRoot: $ProjectRoot"
Write-Ok "VenvPath: $VenvPath"

if ($InstallTools) {
    Write-Step "Checking optional tool installs"
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Install-WithWinget -Id "Git.Git" -Name "Git"
    } else {
        Write-Ok "Git is already available"
    }

    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Install-WithWinget -Id "OpenJS.NodeJS.LTS" -Name "Node.js LTS"
    } else {
        Write-Ok "Node.js is already available"
    }

    if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not $PythonExe) {
        Install-WithWinget -Id "Python.Python.3.12" -Name "Python 3.12"
    } else {
        Write-Ok "Python is already available"
    }

    if (-not (Test-Path $LmStudioCli)) {
        Install-WithWinget -Id "LMStudio.LMStudio" -Name "LM Studio"
    } else {
        Write-Ok "LM Studio CLI is already available"
    }
}

Write-Step "Resolving Python"
if (-not $PythonExe) {
    if (Test-Path $VenvPython) {
        $PythonExe = $VenvPython
    } else {
        $PythonExe = Require-Command "python"
    }
}
Write-Ok "PythonExe: $PythonExe"

if (-not (Test-Path $VenvPython)) {
    Write-Step "Creating virtual environment"
    & $PythonExe -m venv $VenvPath
    Write-Ok "Created venv: $VenvPath"
}

if (-not $SkipPythonDeps) {
    Write-Step "Installing Python dependencies"
    & $VenvPython -m pip install --upgrade pip
    if (Test-Path $RequirementsPath) {
        & $VenvPip install -r $RequirementsPath
        Write-Ok "Installed requirements.txt"
    } else {
        Write-WarnLine "requirements.txt not found: $RequirementsPath"
    }
}

Write-Step "Installing Node dependencies"
if (Test-Path (Join-Path $ProjectRoot "package.json")) {
    Push-Location $ProjectRoot
    try {
        if (Test-Path (Join-Path $ProjectRoot "package-lock.json")) {
            npm ci
        } else {
            npm install
        }
        Write-Ok "Node dependencies ready"
    } finally {
        Pop-Location
    }
} else {
    Write-WarnLine "package.json not found; skipping npm install"
}

Write-Step "Preparing runtime directories"
@(
    "storage",
    "storage\projects",
    "storage\oauth",
    "storage\usage",
    "storage\source_cache",
    "storage\source_research_cache",
    ".mcp"
) | ForEach-Object {
    $dir = Join-Path $ProjectRoot $_
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
Write-Ok "Runtime directories ready"

if ($PersistUserEnv) {
    Write-Step "Persisting user environment variables"
    Set-UserEnv -Name "PYTHONIOENCODING" -Value "utf-8"
    Set-UserEnv -Name "LLM_PROVIDER" -Value "lmstudio"
    Set-UserEnv -Name "LMSTUDIO_BASE_URL" -Value "http://127.0.0.1:1234"
    Set-UserEnv -Name "SCRIPT_LLM_MODEL" -Value $LmStudioModel
    Set-UserEnv -Name "LMSTUDIO_CONTEXT_TARGET" -Value ([string]$LmStudioContext)
    Set-UserEnv -Name "NEWAUTO_USE_EXISTING_LMSTUDIO_MODEL" -Value "1"
    Set-UserEnv -Name "NEWAUTO_API_PORT" -Value "9002"
    Set-UserEnv -Name "NEWAUTO_BASE_URL" -Value "http://127.0.0.1:9002"
    Set-UserEnv -Name "FLOW_AUTOMATION_BACKEND" -Value "playwright"
    Set-UserEnv -Name "FLOW_MODE" -Value "playwright"
    Set-UserEnv -Name "FLOW_BROWSER" -Value "edge"

    $lmStudioBin = Join-Path $env:USERPROFILE ".lmstudio\bin"
    Add-UserPathEntry -PathEntry $lmStudioBin
}

if ($UpdateClineMcpSettings) {
    Write-Step "Updating Cline MCP settings"
    $settingsDir = Split-Path -Parent $ClineSettingsPath
    New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null

    if (Test-Path $ClineSettingsPath) {
        Copy-Item $ClineSettingsPath "$ClineSettingsPath.bak" -Force
        $settings = Get-Content $ClineSettingsPath -Raw | ConvertFrom-Json
    } else {
        $settings = [pscustomobject]@{ mcpServers = [pscustomobject]@{} }
    }

    if (-not $settings.PSObject.Properties.Name.Contains("mcpServers") -or -not $settings.mcpServers) {
        $settings | Add-Member -NotePropertyName "mcpServers" -NotePropertyValue ([pscustomobject]@{}) -Force
    }

    $servers = [ordered]@{}
    foreach ($prop in $settings.mcpServers.PSObject.Properties) {
        $servers[$prop.Name] = $prop.Value
    }

    $servers["git"] = [ordered]@{
        command = (Join-Path $VenvPath "Scripts\mcp-server-git.exe")
        args = @("--repository", $ProjectRoot)
    }
    $servers["playwright"] = [ordered]@{
        command = "npx"
        args = @("-y", "@playwright/mcp@latest", "--browser", "chrome", "--isolated", "--shared-browser-context")
        env = [ordered]@{ PLAYWRIGHT_BROWSERS_PATH = "0" }
    }
    $servers["browser-use"] = [ordered]@{
        command = "uv"
        args = @("tool", "run", "--from", "browser-use[cli]", "browser-use", "--mcp", "--headed")
        env = [ordered]@{
            BROWSER_USE_HEADLESS = "false"
            PYTHONIOENCODING = "utf-8"
        }
        disabled = $false
        autoApprove = @()
    }
    $servers["context7"] = [ordered]@{
        command = "npx"
        args = @("-y", "@upstash/context7-mcp@latest")
    }
    $servers["sequential-thinking"] = [ordered]@{
        command = "npx"
        args = @("-y", "@modelcontextprotocol/server-sequential-thinking@latest")
    }
    $servers["memory"] = [ordered]@{
        command = "npx"
        args = @("-y", "@modelcontextprotocol/server-memory@latest")
        env = [ordered]@{ MEMORY_FILE_PATH = (Join-Path $ProjectRoot ".mcp\memory.jsonl") }
    }
    $servers["newauto-stepwise"] = [ordered]@{
        command = (Join-Path $ProjectRoot "run-newauto-stepwise-mcp.cmd")
        args = @()
        env = [ordered]@{
            PYTHONIOENCODING = "utf-8"
            LLM_PROVIDER = "lmstudio"
            LMSTUDIO_BASE_URL = "http://127.0.0.1:1234"
            SCRIPT_LLM_MODEL = $LmStudioModel
            NEWAUTO_USE_EXISTING_LMSTUDIO_MODEL = "1"
        }
    }
    $servers["lmstudio-openclaw-operator"] = [ordered]@{
        command = (Join-Path $ProjectRoot "run-lmstudio-openclaw-operator-mcp.cmd")
        args = @()
        env = [ordered]@{
            PYTHONIOENCODING = "utf-8"
            LLM_PROVIDER = "lmstudio"
            LMSTUDIO_BASE_URL = "http://127.0.0.1:1234"
            SCRIPT_LLM_MODEL = $LmStudioModel
            NEWAUTO_USE_EXISTING_LMSTUDIO_MODEL = "1"
        }
        disabled = $false
        autoApprove = @()
    }

    $settings.mcpServers = [pscustomobject]$servers
    ConvertTo-JsonDepth $settings | Set-Content -Path $ClineSettingsPath -Encoding UTF8
    Write-Ok "Updated Cline MCP settings: $ClineSettingsPath"
    Write-Ok "Backup written: $ClineSettingsPath.bak"
}

if ($StartLmStudioServer) {
    Write-Step "Starting and checking LM Studio server"
    if (-not (Test-Path $LmStudioCli)) {
        throw "LM Studio CLI not found: $LmStudioCli"
    }

    & $LmStudioCli server start | Out-Host
    Start-Sleep -Seconds 3

    $ensureScript = Join-Path $ProjectRoot "scripts\ensure_lmstudio_context.ps1"
    if (Test-Path $ensureScript) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $ensureScript -Model $LmStudioModel -ContextLength $LmStudioContext
    } else {
        Write-WarnLine "Context helper not found: $ensureScript"
    }
}

Write-Step "Final checks"
& $VenvPython --version
if (Get-Command node -ErrorAction SilentlyContinue) { node --version }
if (Get-Command npm -ErrorAction SilentlyContinue) { npm --version }
if (Test-Path $LmStudioCli) { & $LmStudioCli --version }

Write-Host ""
Write-Host "Master setup complete." -ForegroundColor Green
Write-Host "Recommended next command:"
Write-Host "  .\run-newauto-stepwise-mcp.cmd"
Write-Host ""
Write-Host "Note: restart VS Code/Cline after updating user environment variables or MCP settings."
