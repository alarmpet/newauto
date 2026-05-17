param(
  [string]$Token = "",
  [string]$DestinationPath = "C:\Users\petbl\autotube\ComfyUI\models\loras\Stickfigures-000005.safetensors",
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$modelVersionApi = "https://civitai.green/api/v1/model-versions/784131"
$downloadUrl = "https://civitai.com/api/download/models/784131"
$minimumBytes = 50MB

if (-not $Token) {
  $Token = $env:CIVITAI_API_TOKEN
}

Write-Output "Fetching Stickfigures model metadata..."
$metadata = Invoke-RestMethod -Uri $modelVersionApi -Method Get
$trainedWords = @($metadata.trainedWords)
Write-Output "Model: $($metadata.model.name) / Version: $($metadata.name)"
Write-Output "Trigger words: $($trainedWords -join ', ')"

$destination = [System.IO.Path]::GetFullPath($DestinationPath)
$destinationDir = Split-Path -Parent $destination
New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null

if ((Test-Path $destination) -and -not $Force) {
  $existing = Get-Item $destination
  if ($existing.Length -ge $minimumBytes) {
    Write-Output "LoRA already exists:"
    $existing | Select-Object FullName, Length, LastWriteTime
    exit 0
  }
  Remove-Item $destination -Force
}

if (-not $Token) {
  throw "Civitai login is required for this asset. Set CIVITAI_API_TOKEN or pass -Token before running this installer."
}

$headers = @{
  "Authorization" = "Bearer $Token"
}

Write-Output "Downloading Stickfigures LoRA..."
Invoke-WebRequest -Uri $downloadUrl -Headers $headers -OutFile $destination

$downloaded = Get-Item $destination
if ($downloaded.Length -lt 1024) {
  $body = Get-Content -Path $destination -Raw -ErrorAction SilentlyContinue
  Remove-Item $destination -Force -ErrorAction SilentlyContinue
  throw "Download failed or returned an error payload: $body"
}
if ($downloaded.Length -lt $minimumBytes) {
  Remove-Item $destination -Force -ErrorAction SilentlyContinue
  throw "Downloaded file is too small to be the LoRA ($($downloaded.Length) bytes)."
}

Write-Output "Installed Stickfigures LoRA:"
$downloaded | Select-Object FullName, Length, LastWriteTime
Write-Output "Recommended prompt hints: Flipchartvisu, Stick figure"
