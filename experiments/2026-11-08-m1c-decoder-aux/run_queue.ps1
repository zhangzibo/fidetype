# Run M1-C training runs ONE AFTER ANOTHER, each followed by inference with the MEG control.
# Start it DETACHED (it outlives the shell and the Claude session):
#
#   Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',
#       'experiments\2026-11-08-m1c-decoder-aux\run_queue.ps1','-Runs','r0-baseline,r1-small'
#
# Each name <n> uses config-<n>.json in this folder and run dir C:\Users\zhang\bci-data\runs\<run_name>.
# Restart-safe: a run whose status.json says done/early_stopped is not trained again; a run with a
# latest.pt is resumed. Inference is skipped when <streams>\<run_name>\metrics.json exists.
# Queue log: C:\Users\zhang\bci-data\runs\m1c-queue.log ; PID: C:\Users\zhang\bci-data\runs\m1c-queue.pid
param(
    [Parameter(Mandatory = $true)][string]$Runs,
    [string]$RunsDir = "C:\Users\zhang\bci-data\runs",
    [string]$StreamsDir = "C:\Users\zhang\bci-data\streams",
    [string]$Python = "C:\venvs\fidetype-rocm\Scripts\python.exe"
)
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here "..\..")).Path
Set-Location $repo
$qlog = Join-Path $RunsDir "m1c-queue.log"
$PID | Out-File -Encoding ascii (Join-Path $RunsDir "m1c-queue.pid")
$env:TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL = "1"
$env:MIOPEN_FIND_MODE = "FAST"
$env:PYTHONUNBUFFERED = "1"
$env:OMP_NUM_THREADS = "4"
function Log($m) { "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $m" | Out-File -Append -Encoding utf8 $qlog }

foreach ($n in $Runs.Split(",")) {
    $n = $n.Trim()
    $cfgPath = Join-Path $here "config-$n.json"
    $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
    $rn = $cfg.run_name
    $runDir = Join-Path $RunsDir $rn
    New-Item -ItemType Directory -Force $runDir | Out-Null
    $status = $null
    if (Test-Path (Join-Path $runDir "status.json")) { $status = (Get-Content (Join-Path $runDir "status.json") -Raw | ConvertFrom-Json).status }
    if ($status -in @("done", "early_stopped")) {
        Log "$rn already $status; skip training"
    } else {
        $a = @("-m", "fidetype.decoders.train", "--run-dir", $runDir, "--run-name", $rn, "--config", $cfgPath)
        if (Test-Path (Join-Path $runDir "latest.pt")) { $a += "--resume" }
        Log "train $rn : $($a -join ' ')"
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        & $Python @a > (Join-Path $runDir "stdout-$stamp.log") 2> (Join-Path $runDir "stderr-$stamp.log")
        Log "train $rn exit $LASTEXITCODE"
    }
    $status = (Get-Content (Join-Path $runDir "status.json") -Raw | ConvertFrom-Json).status
    if ($status -eq "stopped") {
        Log "$rn stopped by max_minutes (still improving?). Inference on best.pt anyway; resume with run_queue.ps1 -Runs $n"
    }
    if (Test-Path (Join-Path $StreamsDir "$rn\metrics.json")) {
        if ((Get-Item (Join-Path $StreamsDir "$rn\metrics.json")).LastWriteTime -gt (Get-Item (Join-Path $runDir "best.pt")).LastWriteTime) {
            Log "$rn inference up to date; skip"
            continue
        }
    }
    Log "infer $rn"
    & $Python -m fidetype.decoders.infer --run-dir $runDir --control > (Join-Path $runDir "infer-stdout.log") 2> (Join-Path $runDir "infer-stderr.log")
    Log "infer $rn exit $LASTEXITCODE"
}
Log "queue finished: $Runs"
