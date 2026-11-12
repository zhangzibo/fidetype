# Queue (2026-11-12, Paper 1 R1 / Major 7 / G2): 2 more seeds of the async MEG decoder recipe r4a -> r4b full-medium.
# Per seed s in 1, 2:  train m1-09-r4a-full-medium-s<s> -> train m1-09-r4b-full-medium-s<s> (init from r4a-s<s>)
#                      -> infer.py --control (greedy, real / shuffled / zeros) -> beam + char LM (m1c2 run.py, stages
#                      controls,grid,eval: val grid, then test once; beam controls).
# Same recipe and data split as m1-09-r4b-full-medium (seed 0). Only the seed differs.
# Rule: at most 1 heavy job at a time (GPU training, GPU inference and the CPU beam run one after the other).
# Sleep: at start the queue saves the AC sleep timeout and sets it to 0 (never) and calls
#        SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) (keep awake); the finally block clears it and
#        restores the AC sleep timeout (30 min). The queue does NOT put the PC to sleep at the end.
#        train.py also runs inside fidetype.utils.power.keep_awake(); checkpoints every 5 min (latest.pt).
# Hard stop: $HardStop.
#
# Start (detached, hidden):
#   Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\zhang\bci-data\runs\queue-2026-11-12-m1-09-seeds\queue.ps1'
# Dry run (checks only): powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\zhang\bci-data\runs\queue-2026-11-12-m1-09-seeds\queue.ps1 -DryRun
# Check: Get-Content C:\Users\zhang\bci-data\runs\queue-2026-11-12-m1-09-seeds\queue.log -Tail 10
# Stop:  Stop-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\queue-2026-11-12-m1-09-seeds\queue.pid); then stop the job
#        (taskkill /T /F /PID (Get-Content C:\Users\zhang\bci-data\runs\<run>\pid.txt), or the infer/beam python); then
#        powercfg /change standby-timeout-ac 30   (a hard kill skips the finally block)
# Resume training only: .\experiments\2026-11-08-m1b-decoder\launch.ps1 -RunName <run> -Resume
# Resume the queue: start it again. Finished runs (status done / early_stopped / stopped) are skipped;
#                   an unfinished run is resumed from latest.pt; infer / beam are skipped if their done file exists.
param([switch]$DryRun)

$ErrorActionPreference = "Continue"
$QDir      = "C:\Users\zhang\bci-data\runs\queue-2026-11-12-m1-09-seeds"
$QLog      = Join-Path $QDir "queue.log"
$Repo      = "C:\Users\zhang\OneDrive\Documents\GitHub\stealth-project"
$ExpDir    = "experiments\2026-11-12-paper1-r1-analyses\gpu-seeds"
$Launch    = Join-Path $Repo "experiments\2026-11-08-m1b-decoder\launch.ps1"
$BeamPy    = Join-Path $Repo "experiments\2026-11-08-m1c2-beam-lm\run.py"
$Python    = "C:\venvs\fidetype-rocm\Scripts\python.exe"
$RunsRoot  = "C:\Users\zhang\bci-data\runs"
$StreamsRoot = "C:\Users\zhang\bci-data\streams"
$SleepFile = Join-Path $QDir "sleep-ac-seconds.txt"
$HardStop  = [datetime]"2026-11-12 14:00:00"
$BeamLatest  = [datetime]"2026-11-12 13:00:00"
$Finished  = @("done", "early_stopped", "stopped")
$Stages = @(
    @{ Name = "s1"; A = "m1-09-r4a-full-medium-s1"; B = "m1-09-r4b-full-medium-s1";
       CA = "$ExpDir\config-r4a-full-medium-s1.json"; CB = "$ExpDir\config-r4b-full-medium-s1.json" },
    @{ Name = "s2"; A = "m1-09-r4a-full-medium-s2"; B = "m1-09-r4b-full-medium-s2";
       CA = "$ExpDir\config-r4a-full-medium-s2.json"; CB = "$ExpDir\config-r4b-full-medium-s2.json" }
)
$script:Stage = "init"
$script:ActivePid = 0
$script:HardStopped = $false

Add-Type -Namespace Fidetype -Name Power -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
$ES_CONTINUOUS = [uint32]2147483648
$ES_SYSTEM_REQUIRED = [uint32]1

function Log([string]$msg) {
    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $script:Stage, $msg
    Add-Content -Path $QLog -Value $line -Encoding utf8
}

function Get-VenvProcs {
    @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -like "C:\venvs\fidetype-rocm\*" })
}

function Stop-Tree([int]$procId) {
    & taskkill.exe /PID $procId /T /F 2>&1 | ForEach-Object { Log "taskkill: $_" }
}

function Test-HardStop {
    if ($script:HardStopped) { return $true }
    if ((Get-Date) -ge $HardStop) {
        $script:HardStopped = $true
        Log "HARD STOP: $($HardStop.ToString('yyyy-MM-dd HH:mm')) reached"
        if ($script:ActivePid -gt 0 -and (Get-Process -Id $script:ActivePid -ErrorAction SilentlyContinue)) {
            Log "kill pending job PID $($script:ActivePid) (training: latest.pt is at most 5 min old; resume with launch.ps1 -RunName <run> -Resume)"
            Stop-Tree $script:ActivePid
        }
        return $true
    }
    return $false
}

function Get-RunStatus([string]$RunName) {
    try { return (Get-Content (Join-Path $RunsRoot "$RunName\status.json") -Raw -ErrorAction Stop | ConvertFrom-Json).status } catch { return $null }
}

function Clear-CpuOnlyEnv {
    foreach ($v in @("HIP_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES")) {
        if (Test-Path "Env:$v") { Log "removing env $v=$((Get-Item "Env:$v").Value) (GPU run)"; Remove-Item "Env:$v" }
    }
    $env:TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL = "1"
    $env:PYTHONUNBUFFERED = "1"
}

# Start training via launch.ps1; wait until it ends. Returns the final status string ("hard_stop" on hard stop).
function Invoke-Train([string]$RunName, [string]$Config, [switch]$Resume) {
    Set-Location $Repo
    Clear-CpuOnlyEnv
    $RunDir = Join-Path $RunsRoot $RunName
    $pidFile = Join-Path $RunDir "pid.txt"
    if (Test-Path $pidFile) { Remove-Item $pidFile -Force }
    if ($Resume) { $out = @(& $Launch -RunName $RunName -Resume 2>&1) }
    else { $out = @(& $Launch -Config $Config -RunName $RunName 2>&1) }
    Log "launch.ps1: $($out -join ' ')"
    $procId = 0
    try { $procId = [int](Get-Content $pidFile -ErrorAction Stop | Select-Object -First 1) } catch {}
    if ($procId -le 0) { Log "no PID in pid.txt"; return "no_pid" }
    $script:ActivePid = $procId
    Log "training $RunName PID $procId (resume=$Resume)"
    $finishedAt = $null
    while ($true) {
        Start-Sleep -Seconds 60
        if (Test-HardStop) { return "hard_stop" }
        $alive = [bool](Get-Process -Id $procId -ErrorAction SilentlyContinue)
        $st = Get-RunStatus $RunName
        $tail = ""
        try { $tail = (Get-Content (Join-Path $RunDir "train.log") -Tail 1 -ErrorAction Stop) } catch {}
        Log "training alive=$alive status=$st | $tail"
        if (-not $alive) { $script:ActivePid = 0; return $st }
        if ($Finished -contains $st) {
            if ($null -eq $finishedAt) { $finishedAt = Get-Date }
            elseif (((Get-Date) - $finishedAt).TotalMinutes -ge 5) {
                Log "status '$st' but process still alive after 5 min (ROCm exit hang) -> kill"
                Stop-Tree $procId
                $script:ActivePid = 0
                return $st
            }
        }
    }
}

# Train (skip if finished; resume if a checkpoint exists), with ONE extra -Resume on unexpected death.
function Invoke-TrainWithRetry([string]$RunName, [string]$Config) {
    $st0 = Get-RunStatus $RunName
    if ($Finished -contains $st0) { Log "training $RunName already finished (status=$st0) -> skip"; return $true }
    $hasCkpt = Test-Path (Join-Path $RunsRoot "$RunName\latest.pt")
    if ($hasCkpt) { Log "training $RunName has latest.pt (status=$st0) -> resume"; $st = Invoke-Train $RunName "" -Resume }
    else { $st = Invoke-Train $RunName $Config }
    if ($st -eq "hard_stop") { return $false }
    if ($Finished -notcontains $st) {
        Log "training $RunName ended without finished status (status=$st) -> ONE resume"
        $st = Invoke-Train $RunName "" -Resume
        if ($st -eq "hard_stop") { return $false }
    }
    Log "training $RunName final status=$st"
    return ($Finished -contains $st)
}

# Run a python child (hidden) and wait. $Done = a file that marks success. Returns $true if $Done was written.
function Invoke-Py([string]$Tag, [string[]]$PyArgs, [string]$Done, [double]$MaxHours, [switch]$Cpu) {
    Clear-CpuOnlyEnv
    if ($Cpu) { $env:HIP_VISIBLE_DEVICES = "-1" }
    $t0 = Get-Date
    $p = Start-Process -FilePath $Python -ArgumentList $PyArgs -WorkingDirectory $Repo -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $QDir "$Tag.log") -RedirectStandardError (Join-Path $QDir "$Tag.err.log")
    $null = $p.Handle
    if ($Cpu) { Remove-Item Env:HIP_VISIBLE_DEVICES -ErrorAction SilentlyContinue }
    $script:ActivePid = $p.Id
    Log "$Tag PID $($p.Id) -> $Done"
    $doneAt = $null
    while ($true) {
        Start-Sleep -Seconds 60
        if (Test-HardStop) { return $false }
        $alive = -not $p.HasExited
        $ok = (Test-Path $Done) -and ((Get-Item $Done).LastWriteTime -gt $t0)
        Log "$Tag alive=$alive done_file=$ok"
        if (-not $alive) { Log "$Tag exited, code=$($p.ExitCode)"; break }
        if ($ok) {
            if ($null -eq $doneAt) { $doneAt = Get-Date }
            elseif (((Get-Date) - $doneAt).TotalMinutes -ge 5) { Log "$Tag done file written, no exit after 5 min (ROCm exit hang) -> kill"; Stop-Tree $p.Id; break }
        }
        if (((Get-Date) - $t0).TotalHours -ge $MaxHours) { Log "$Tag timeout $MaxHours h -> kill"; Stop-Tree $p.Id; break }
    }
    $script:ActivePid = 0
    $ok = (Test-Path $Done) -and ((Get-Item $Done).LastWriteTime -gt $t0)
    Log "$Tag done_file written=$ok"
    return $ok
}

function Invoke-Stage($s) {
    $script:Stage = "$($s.Name)-train-a"
    if (-not (Invoke-TrainWithRetry $s.A $s.CA)) { Log "r4a $($s.A) did not finish -> skip the rest of stage $($s.Name)"; return }
    Start-Sleep -Seconds 20
    $script:Stage = "$($s.Name)-train-b"
    if (-not (Invoke-TrainWithRetry $s.B $s.CB)) { Log "r4b $($s.B) did not finish -> skip inference"; return }
    Start-Sleep -Seconds 20
    $script:Stage = "$($s.Name)-infer"
    $metrics = Join-Path $StreamsRoot "$($s.B)\metrics.json"
    if (Test-Path $metrics) { Log "infer: $metrics exists -> skip" }
    else { $null = Invoke-Py "infer-$($s.B)" @("-m", "fidetype.decoders.infer", "--run-dir", "C:/Users/zhang/bci-data/runs/$($s.B)", "--control") $metrics 1.5 }
    if (Test-HardStop) { return }
    if (-not (Test-Path (Join-Path $StreamsRoot "$($s.B)\test\labels.jsonl"))) { Log "no streams -> skip beam"; return }
    if ((Get-Date) -ge $BeamLatest) { Log "after $($BeamLatest.ToString('HH:mm')) -> skip beam for $($s.B)"; return }
    $script:Stage = "$($s.Name)-beam"
    $out = Join-Path $Repo "$ExpDir\results\beam-$($s.B)"
    if (Test-Path (Join-Path $out "tables.md")) { Log "beam: $out\tables.md exists -> skip"; return }
    $beamArgs = @($BeamPy, "--run-name", $s.B, "--out", $out, "--workers", "10",
        "--grid-w", "0", "0.05", "0.1", "0.15", "0.25", "0.5", "0.75", "1.0", "--grid-b", "0", "0.5", "1.0", "1.5")
    $null = Invoke-Py "beam-$($s.B)" $beamArgs (Join-Path $out "tables.md") 2.5 -Cpu
}

function Get-AcSleepSeconds {
    $line = (powercfg.exe /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String "Current AC Power Setting Index").Line
    return [Convert]::ToInt32(($line -split ":")[-1].Trim(), 16)
}

function Save-And-DisableSleep {
    $cur = Get-AcSleepSeconds
    if ($cur -eq 0 -and (Test-Path $SleepFile)) { Log "AC sleep already 0; keep saved value $(Get-Content $SleepFile)" }
    else { "$cur" | Out-File -Encoding ascii $SleepFile; Log "saved AC sleep $cur s to $SleepFile" }
    & powercfg.exe /change standby-timeout-ac 0
    Log "AC sleep set to never; now $(Get-AcSleepSeconds) s"
    $prev = [Fidetype.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
    Log "keep_awake on (SetThreadExecutionState, previous state 0x$('{0:X}' -f $prev))"
}

function Restore-Sleep([switch]$WhatIf) {
    $sec = 1800
    try { $sec = [int](Get-Content $SleepFile -ErrorAction Stop | Select-Object -First 1) } catch { Log "no $SleepFile -> use 1800 s" }
    if ($sec -le 0) { Log "saved value is $sec -> use 1800 s"; $sec = 1800 }
    $min = [math]::Max(1, [int][math]::Round($sec / 60))
    if ($WhatIf) { Log "dry-run: would clear keep_awake and run powercfg /change standby-timeout-ac $min"; return }
    $null = [Fidetype.Power]::SetThreadExecutionState($ES_CONTINUOUS)
    Log "keep_awake off"
    & powercfg.exe /change standby-timeout-ac $min
    Log "AC sleep restored: standby-timeout-ac $min min ($sec s); now $(Get-AcSleepSeconds) s"
}

New-Item -ItemType Directory -Force $QDir | Out-Null

# ---------------------------------------------------------------- dry run
if ($DryRun) {
    $script:Stage = "dry-run"
    Log "dry-run start; hard stop $($HardStop.ToString('yyyy-MM-dd HH:mm')); AC sleep now $(Get-AcSleepSeconds) s"
    foreach ($p in @($Launch, $BeamPy, $Python)) { Log "exists=$(Test-Path $p) $p" }
    foreach ($s in $Stages) {
        foreach ($c in @($s.CA, $s.CB)) { Log "exists=$(Test-Path (Join-Path $Repo $c)) $c" }
        Log "status $($s.A)=$(Get-RunStatus $s.A) $($s.B)=$(Get-RunStatus $s.B)"
    }
    Log "rocm-venv python procs now: $(@(Get-VenvProcs).Count)"
    Log "hard-stop test now: $(Test-HardStop)"
    try { throw "simulated failure" } catch { Log "caught: $_" } finally { Restore-Sleep -WhatIf; Log "dry-run done (finally ran)" }
    exit 0
}

# ---------------------------------------------------------------- main
$PID | Out-File -Encoding ascii (Join-Path $QDir "queue.pid")
try {
    $script:Stage = "start"
    Log "queue started, PID $PID; hard stop $($HardStop.ToString('yyyy-MM-dd HH:mm'))"
    $busy = @(Get-VenvProcs)
    if ($busy.Count -gt 0) {
        Log "fidetype-rocm python already running (PIDs $(($busy | ForEach-Object { $_.ProcessId }) -join ',')) -> no start (max 1 heavy job)"
        return
    }
    Save-And-DisableSleep
    foreach ($s in $Stages) {
        Invoke-Stage $s
        if (Test-HardStop) { break }
    }
}
catch {
    Log "ERROR: $_"
}
finally {
    $script:Stage = "end"
    if ($script:ActivePid -gt 0 -and (Get-Process -Id $script:ActivePid -ErrorAction SilentlyContinue)) {
        Log "job PID $($script:ActivePid) still alive at queue end -> kill"
        Stop-Tree $script:ActivePid
    }
    Restore-Sleep
    Log "QUEUE DONE"
}
