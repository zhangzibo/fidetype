<#
.SYNOPSIS
    Creates the Fidetype GPU Python environment (native Windows ROCm + PyTorch).

.DESCRIPTION
    This script is idempotent. You can run it again at any time. It:
      1. creates a Python 3.12 venv with uv (if the venv does not exist);
      2. installs the AMD ROCm SDK wheels, then torch and torchaudio;
      3. installs numpy, mne, scipy and pytest;
      4. installs this repo in editable mode;
      5. runs tools/env/gpu_smoke.py.

    Source of the wheels (AMD, ROCm 7.2.1 for Windows, Python 3.12):
      https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/
    AMD install guide:
      https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/windows/install-pytorch.html

    WHY THE VENV IS AT A SHORT PATH:
      Windows limits file paths to 260 characters (MAX_PATH). rocBLAS loads
      kernel files from <venv>\Lib\site-packages\_rocm_sdk_libraries_custom\...
      If the venv path is long, these kernel paths go over the limit and
      rocBLAS crashes with 0xC0000005 (access violation) during GEMM.
      Thus keep the venv at a short path such as C:\venvs\fidetype-rocm.
      Do not put the venv inside OneDrive or inside the repo.

.PARAMETER VenvPath
    The venv folder. Default: C:\venvs\fidetype-rocm.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools\env\setup_rocm.ps1
    powershell -ExecutionPolicy Bypass -File tools\env\setup_rocm.ps1 -VenvPath C:\Users\me\venvs\fidetype-rocm
#>
param(
    [string]$VenvPath = "C:\venvs\fidetype-rocm"
)

$ErrorActionPreference = "Stop"

# The repo root is two levels above this script (tools\env\).
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $VenvPath "Scripts\python.exe"

# AMD wheel source. The "+" in the torch version is URL-encoded as %2B.
$RocmBase = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1"
$RocmSdk = @(
    "$RocmBase/rocm_sdk_core-7.2.1-py3-none-win_amd64.whl",
    "$RocmBase/rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl",
    "$RocmBase/rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl",
    "$RocmBase/rocm-7.2.1.tar.gz"
)
$TorchWheels = @(
    "$RocmBase/torch-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl",
    "$RocmBase/torchaudio-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl"
)
$ExtraPackages = @("numpy", "mne", "scipy", "pytest")

# uv hardlinks files from its cache by default. On this machine a hardlink
# failed with "os error 396" (the cloud operation cannot be performed on a
# file with incompatible hardlinks). Copy mode avoids this problem.
$env:UV_LINK_MODE = "copy"

function Invoke-Step {
    param([string]$Title, [scriptblock]$Body)
    Write-Host ""
    Write-Host "==> $Title" -ForegroundColor Cyan
    # uv writes progress to stderr. Do not treat stderr as an error;
    # check the exit code instead.
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Body } finally { $ErrorActionPreference = $old }
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed (exit code $LASTEXITCODE): $Title"
    }
}

# Find uv. It is on PATH, or in the default install folder.
$Uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $Uv) {
    $Uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (-not (Test-Path $Uv)) {
        throw "uv not found. Install it from https://docs.astral.sh/uv/"
    }
}

# Refuse paths that are inside OneDrive or that are too long.
$FullVenv = [System.IO.Path]::GetFullPath($VenvPath)
if ($FullVenv -match "OneDrive") {
    throw "Do not put the venv inside OneDrive: $FullVenv"
}
if ($FullVenv.Length -gt 40) {
    Write-Warning ("Venv path is $($FullVenv.Length) characters. rocBLAS kernel " +
        "paths can go over MAX_PATH (260). Use a shorter path.")
}

Write-Host "Repo: $RepoRoot"
Write-Host "Venv: $FullVenv"
Write-Host "uv:   $Uv"

if (Test-Path $Python) {
    Write-Host ""
    Write-Host "==> Venv exists. Skipping creation." -ForegroundColor Cyan
} else {
    $Parent = Split-Path $FullVenv -Parent
    if (-not (Test-Path $Parent)) {
        New-Item -ItemType Directory -Path $Parent | Out-Null
    }
    Invoke-Step "Create venv (Python 3.12)" {
        & $Uv venv --python 3.12 $FullVenv
    }
}

Invoke-Step "Install ROCm SDK wheels (ROCm 7.2.1)" {
    & $Uv pip install --python $Python @RocmSdk
}

Invoke-Step "Install torch 2.9.1 and torchaudio 2.9.1 (ROCm builds)" {
    & $Uv pip install --python $Python @TorchWheels
}

Invoke-Step "Install numpy, mne, scipy, pytest" {
    & $Uv pip install --python $Python @ExtraPackages
}

Invoke-Step "Install the repo package (editable)" {
    & $Uv pip install --python $Python -e $RepoRoot
}

# Report the longest file path under the venv. It must stay below 260.
$Longest = Get-ChildItem -Path $FullVenv -Recurse -File -ErrorAction SilentlyContinue |
    Sort-Object { $_.FullName.Length } -Descending | Select-Object -First 1
if ($Longest) {
    Write-Host ""
    Write-Host "Longest path under venv: $($Longest.FullName.Length) characters"
    if ($Longest.FullName.Length -gt 240) {
        Write-Warning "Longest path is near MAX_PATH (260): $($Longest.FullName)"
    }
}

Invoke-Step "Run GPU smoke test" {
    & $Python (Join-Path $RepoRoot "tools\env\gpu_smoke.py")
}

Write-Host ""
Write-Host "Done. Use: $Python" -ForegroundColor Green
