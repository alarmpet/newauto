param(
  [Alias("positive-prompt")]
  [string]$PositivePrompt = "",

  [Alias("negative-prompt")]
  [string]$NegativePrompt = "",

  [Alias("positive-prompt-file")]
  [string]$PositivePromptFile = "",

  [Alias("negative-prompt-file")]
  [string]$NegativePromptFile = "",

  [string]$Checkpoint = "",
  [string]$TemplateId = "txt2img_sdxl_basic",
  [int]$Width = 1024,
  [int]$Height = 576,
  [int]$Seed = 101,
  [string]$FilenamePrefix = "newauto_comfyui",
  [int]$TimeoutSec = 300,
  [string]$GenerationProfile = "",
  [string]$LoraName = "",
  [double]$LoraStrength = 0.8,
  [string]$StyleReferenceImage = "",
  [double]$StyleReferenceStrength = 0.65,
  [string]$ControlImage = "",
  [double]$ControlStrength = 0.75
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $root "omnivoice_env\Scripts\python.exe"
$comfyDir = if ($env:COMFYUI_INSTALL_DIR) { $env:COMFYUI_INSTALL_DIR } else { "C:\Users\petbl\autotube\ComfyUI" }
$checkpointDir = Join-Path $comfyDir "models\checkpoints"
$loraDir = Join-Path $comfyDir "models\loras"

function Read-PromptValue {
  param(
    [string]$InlineValue,
    [string]$FilePath,
    [string]$Label
  )

  if ($FilePath.Trim()) {
    $resolved = Resolve-Path -LiteralPath $FilePath
    return (Get-Content -LiteralPath $resolved -Raw -Encoding UTF8).Trim()
  }
  if ($InlineValue.Trim()) {
    return $InlineValue.Trim()
  }
  throw "$Label is required. Use -$Label or -${Label}File."
}

function Resolve-CheckpointName {
  param([string]$Requested)

  if ($Requested.Trim()) {
    return $Requested.Trim()
  }

  if (-not (Test-Path -LiteralPath $checkpointDir)) {
    throw "ComfyUI checkpoint directory not found: $checkpointDir"
  }

  $preferred = @(
    "sd_xl_base_1.0.safetensors",
    "DreamShaper_8_pruned.safetensors"
  )
  foreach ($name in $preferred) {
    if (Test-Path -LiteralPath (Join-Path $checkpointDir $name)) {
      return $name
    }
  }

  $first = Get-ChildItem -LiteralPath $checkpointDir -File -Filter "*.safetensors" |
    Select-Object -First 1
  if ($null -eq $first) {
    throw "No .safetensors checkpoint found in $checkpointDir"
  }
  return $first.Name
}

function Resolve-LoraName {
  param([string]$Requested)

  $cleaned = $Requested.Trim()
  if (-not $cleaned) {
    return ""
  }
  if (-not (Test-Path -LiteralPath $loraDir)) {
    throw "ComfyUI LoRA directory not found: $loraDir"
  }
  if (Test-Path -LiteralPath (Join-Path $loraDir $cleaned)) {
    return $cleaned
  }
  $matches = Get-ChildItem -LiteralPath $loraDir -File -Filter "*.safetensors" |
    Where-Object { $_.Name -like "*$cleaned*" }
  $count = @($matches).Count
  if ($count -eq 1) {
    return @($matches)[0].Name
  }
  if ($count -gt 1) {
    $names = (@($matches) | Select-Object -ExpandProperty Name) -join ", "
    throw "LoRA name is ambiguous: $cleaned. Matches: $names"
  }
  throw "LoRA not found in ${loraDir}: $cleaned"
}

function Resolve-TemplateId {
  param(
    [string]$Requested,
    [string]$ResolvedLoraName,
    [string]$ResolvedStyleReferenceImage
  )

  $cleaned = $Requested.Trim()
  if (-not $ResolvedLoraName.Trim()) {
    return $cleaned
  }
  if ($cleaned -eq "txt2img_sdxl_ipadapter_style" -or $ResolvedStyleReferenceImage.Trim()) {
    return "txt2img_sdxl_ipadapter_style_lora"
  }
  if ($cleaned -eq "txt2img_sdxl_basic" -or $cleaned -eq "txt2img_sdxl_lightning") {
    return "txt2img_sdxl_lora"
  }
  return $cleaned
}

if (-not (Test-Path -LiteralPath $venvPython)) {
  throw "Project Python not found: $venvPython"
}

$positive = Read-PromptValue -InlineValue $PositivePrompt -FilePath $PositivePromptFile -Label "PositivePrompt"
$negative = Read-PromptValue -InlineValue $NegativePrompt -FilePath $NegativePromptFile -Label "NegativePrompt"
$checkpointName = Resolve-CheckpointName -Requested $Checkpoint
$loraResolvedName = Resolve-LoraName -Requested $LoraName
$templateResolvedId = Resolve-TemplateId -Requested $TemplateId -ResolvedLoraName $loraResolvedName -ResolvedStyleReferenceImage $StyleReferenceImage

& (Join-Path $PSScriptRoot "run_comfyui_detached.ps1") | Out-Host

$argsList = @(
  (Join-Path $PSScriptRoot "check_comfyui_smoke.py"),
  "--checkpoint", $checkpointName,
  "--template-id", $templateResolvedId,
  "--positive-prompt", $positive,
  "--negative-prompt", $negative,
  "--width", $Width,
  "--height", $Height,
  "--seed", $Seed,
  "--filename-prefix", $FilenamePrefix,
  "--timeout-sec", $TimeoutSec
)

if ($GenerationProfile.Trim()) {
  $argsList += @("--generation-profile", $GenerationProfile.Trim())
}
if ($loraResolvedName.Trim()) {
  $argsList += @("--lora-name", $loraResolvedName, "--lora-strength", $LoraStrength)
}
if ($StyleReferenceImage.Trim()) {
  $argsList += @("--style-reference-image", $StyleReferenceImage.Trim(), "--style-reference-strength", $StyleReferenceStrength)
}
if ($ControlImage.Trim()) {
  $argsList += @("--control-image", $ControlImage.Trim(), "--control-strength", $ControlStrength)
}

& $venvPython @argsList
