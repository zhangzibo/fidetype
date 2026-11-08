# Launch (or resume) a ConvCTC training run as a DETACHED, hidden process.
# The process outlives this shell and the Claude session.
#
#   .\launch.ps1 -Config experiments\2026-11-08-m1b-decoder\config-real.json -RunName m1-baseline-2026-11-08-1subj
#   .\launch.ps1 -RunName m1-baseline-2026-11-08-1subj -Resume
#
# Output: C:\Users\zhang\bci-data\runs\<RunName>\ (train.log, metrics.jsonl, status.json,
# latest.pt, best.pt, stdout.log, stderr.log, pid.txt).
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
$argList = @("-m", "fidetype.decoders.train", "--run-dir", "`"$runDir`"", "--run-name", $RunName)
if ($Config -ne "") { $argList += @("--config", "`"$((Resolve-Path $Config).Path)`"") }
if ($Resume) { $argList += "--resume" }
if ($MaxMinutes -gt 0) { $argList += @("--max-minutes", "$MaxMinutes") }
$env:TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL = "1"
$env:PYTHONUNBUFFERED = "1"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$p = Start-Process -FilePath $Python -ArgumentList $argList -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runDir "stdout-$stamp.log") `
    -RedirectStandardError (Join-Path $runDir "stderr-$stamp.log")
$p.Id | Out-File -Encoding ascii (Join-Path $runDir "pid.txt")
Write-Output "PID $($p.Id) -> $runDir"
