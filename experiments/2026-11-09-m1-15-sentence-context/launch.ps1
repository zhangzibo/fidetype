# Launch (or resume) an M1-15 sentence-context training run as a DETACHED, hidden process.
# The process outlives this shell and the Claude session. It checkpoints latest.pt every 5 min.
#
#   .\experiments\2026-11-09-m1-15-sentence-context\launch.ps1 -Config experiments\2026-11-09-m1-15-sentence-context\config.json -RunName m1-15-sentence-context-r1
#   .\experiments\2026-11-09-m1-15-sentence-context\launch.ps1 -RunName m1-15-sentence-context-r1 -Resume
#
# Check:  Get-Content C:\Users\zhang\bci-data\runs\<RunName>\status.json ; Get-Content ...\train.log -Tail 5
# Stop:   Stop-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\<RunName>\pid.txt)
param(
    [string]$Config = "",
    [Parameter(Mandatory = $true)][string]$RunName,
    [switch]$Resume,
    [double]$MaxMinutes = -1,
    [string]$RunsDir = "C:\Users\zhang\bci-data\runs",
    [string]$Python = "C:\venvs\fidetype-rocm\Scripts\python.exe"
)
$ErrorActionPreference = "Stop"
$runDir = Join-Path $RunsDir $RunName
New-Item -ItemType Directory -Force $runDir | Out-Null
$argList = @("-m", "fidetype.decoders.train_sentence", "--run-dir", "`"$runDir`"", "--run-name", $RunName)
if ($Config -ne "") { $argList += @("--config", "`"$((Resolve-Path $Config).Path)`"") }
if ($Resume) { $argList += "--resume" }
if ($MaxMinutes -gt 0) { $argList += @("--max-minutes", "$MaxMinutes") }
# GPU run: never inherit a CPU-only test setting.
Remove-Item Env:HIP_VISIBLE_DEVICES, Env:CUDA_VISIBLE_DEVICES -ErrorAction SilentlyContinue
$env:TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL = "1"
$env:PYTHONUNBUFFERED = "1"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$p = Start-Process -FilePath $Python -ArgumentList $argList -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runDir "stdout-$stamp.log") `
    -RedirectStandardError (Join-Path $runDir "stderr-$stamp.log")
$p.Id | Out-File -Encoding ascii (Join-Path $runDir "pid.txt")
Write-Output "PID $($p.Id) -> $runDir"
