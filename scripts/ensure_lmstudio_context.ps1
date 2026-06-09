param(
    [string]$Model = "qwen/qwen3.5-9b",
    [int]$ContextLength = 131072,
    [int]$Parallel = 1
)

$ErrorActionPreference = "Stop"

$lms = Join-Path $env:USERPROFILE ".lmstudio\bin\lms.exe"
if (-not (Test-Path $lms)) {
    throw "LM Studio CLI not found: $lms"
}

try {
    $models = Invoke-RestMethod -Uri "http://127.0.0.1:1234/api/v0/models" -TimeoutSec 5
} catch {
    & $lms server start | Out-Host
    Start-Sleep -Seconds 3
    $models = Invoke-RestMethod -Uri "http://127.0.0.1:1234/api/v0/models" -TimeoutSec 5
}

$loaded = $models.data | Where-Object { $_.id -eq $Model -and $_.state -eq "loaded" } | Select-Object -First 1
$loadedParallel = if ($loaded -and $null -ne $loaded.parallel) { [int]$loaded.parallel } else { 0 }
if ($loaded -and [int]$loaded.loaded_context_length -ge $ContextLength -and ($loadedParallel -eq 0 -or $loadedParallel -eq $Parallel)) {
    Write-Host "LM Studio context OK: $Model loaded_context_length=$($loaded.loaded_context_length) parallel=$loadedParallel"
    exit 0
}

if ($loaded) {
    Write-Host "Reloading $Model from context $($loaded.loaded_context_length), parallel=$loadedParallel to context $ContextLength, parallel=$Parallel"
    & $lms unload $Model | Out-Host
} else {
    Write-Host "Loading $Model with context $ContextLength, parallel=$Parallel"
}

& $lms load $Model --context-length $ContextLength --parallel $Parallel --gpu max --identifier $Model -y | Out-Host

$models = Invoke-RestMethod -Uri "http://127.0.0.1:1234/api/v0/models" -TimeoutSec 5
$loaded = $models.data | Where-Object { $_.id -eq $Model -and $_.state -eq "loaded" } | Select-Object -First 1
$loadedParallel = if ($loaded -and $null -ne $loaded.parallel) { [int]$loaded.parallel } else { 0 }
if (-not $loaded -or [int]$loaded.loaded_context_length -lt $ContextLength -or ($loadedParallel -ne 0 -and $loadedParallel -ne $Parallel)) {
    $actual = if ($loaded) { $loaded.loaded_context_length } else { "not-loaded" }
    $actualParallel = if ($loaded) { $loadedParallel } else { "not-loaded" }
    throw "LM Studio context check failed: expected context >= $ContextLength and parallel=$Parallel, actual_context=$actual actual_parallel=$actualParallel"
}

Write-Host "LM Studio context OK: $Model loaded_context_length=$($loaded.loaded_context_length) parallel=$loadedParallel"
