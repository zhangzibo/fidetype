# M6-07: train the Toronto sEMG key-press classifiers (one GPU job, all runs in order).
# Saves the AC sleep timeout, sets it to never, runs train.py, restores it in the finally block.
# Each run checkpoints every epoch (latest.pt) and resumes; finished runs are skipped.
#
# Start (detached, hidden):
#   Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\zhang\OneDrive\Documents\GitHub\stealth-project\experiments\2026-11-11-emg-toronto\launch.ps1'
# Check:  Get-Content C:\Users\zhang\bci-data\runs\emg-toronto\train.log -Tail 5   (ALL_DONE file = finished)
# Stop:   Stop-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\emg-toronto\launch.pid); Stop-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\emg-toronto\pid.txt)
#         then: powercfg /change standby-timeout-ac 30   (a hard kill skips the finally block)
# Resume: start again (same command); runs resume from latest.pt.
$ErrorActionPreference = "Continue"
$Repo   = "C:\Users\zhang\OneDrive\Documents\GitHub\stealth-project"
$RunDir = "C:\Users\zhang\bci-data\runs\emg-toronto"
$Python = "C:\venvs\fidetype-rocm\Scripts\python.exe"
$Log    = Join-Path $RunDir "launch.log"
$SleepFile = Join-Path $RunDir "sleep-ac-seconds.txt"
New-Item -ItemType Directory -Force $RunDir | Out-Null

function Log([string]$m) { Add-Content -Path $Log -Value ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m) -Encoding utf8 }
function Get-AcSleepSeconds {
    $line = (powercfg.exe /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String "Current AC Power Setting Index").Line
    return [Convert]::ToInt32(($line -split ":")[-1].Trim(), 16)
}
function Get-VenvProcs {
    @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -like "C:\venvs\fidetype-rocm\*" })
}

$PID | Out-File -Encoding ascii (Join-Path $RunDir "launch.pid")
$busy = @(Get-VenvProcs)
if ($busy.Count -gt 0) { Log "fidetype-rocm python already running (PIDs $(($busy | ForEach-Object { $_.ProcessId }) -join ',')) -> no start"; exit 1 }
try {
    $cur = Get-AcSleepSeconds
    if ($cur -eq 0 -and (Test-Path $SleepFile)) { Log "AC sleep already 0; keep saved $(Get-Content $SleepFile)" }
    else { "$cur" | Out-File -Encoding ascii $SleepFile; Log "saved AC sleep $cur s" }
    & powercfg.exe /change standby-timeout-ac 0
    Log "AC sleep never; now $(Get-AcSleepSeconds) s"
    foreach ($v in @("HIP_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES")) { if (Test-Path "Env:$v") { Remove-Item "Env:$v" } }
    $env:TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL = "1"
    Set-Location $Repo
    $p = Start-Process -FilePath $Python -ArgumentList @('-I', 'experiments/2026-11-11-emg-toronto/train.py') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $RunDir "train.out.log") -RedirectStandardError (Join-Path $RunDir "train.err.log")
    Log "train.py PID $($p.Id)"
    $p.WaitForExit()
    Log "train.py exited, code $($p.ExitCode)"
}
catch { Log "ERROR: $_" }
finally {
    $sec = 1800
    try { $sec = [int](Get-Content $SleepFile -ErrorAction Stop | Select-Object -First 1) } catch {}
    if ($sec -le 0) { $sec = 1800 }
    $min = [math]::Max(1, [int][math]::Round($sec / 60))
    & powercfg.exe /change standby-timeout-ac $min
    Log "AC sleep restored: $min min; now $(Get-AcSleepSeconds) s"
    Log "LAUNCH DONE"
}
