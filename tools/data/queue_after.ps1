# Wait until a running process exits, then run the SpanishBCBL preprocessing again.
#
# Use: run only ONE heavy preprocessing job at a time (one block peaks at 16-18 GB RAM;
# the machine has 31 GB). This script waits for the current job, then starts the next
# pass. The next pass skips cached blocks, so it adds only the blocks not done yet.
#
# Launch detached (hidden window) from the repo root:
#   Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','tools\data\queue_after.ps1','-WaitPid','49364'
#
# Log: the preprocessing writes its own log to <cache>\_preprocess.log.
# This script writes its wait/start lines to <cache>\_queue_after.log, and the
# child's stdout/stderr to <cache>\_queue_after.out.log / _queue_after.err.log.

param(
    [int]$WaitPid = 49364,
    [int]$PollSeconds = 60,
    [string]$Python = 'C:\venvs\fidetype-rocm\Scripts\python.exe',
    [string]$Cache = 'C:\Users\zhang\bci-data\cache\spanishbcbl\v1',
    [int]$Workers = 1,
    [double]$MemBudgetGb = 14
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$log = Join-Path $Cache '_queue_after.log'

function Write-Log([string]$msg) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $log -Value $line -Encoding utf8
}

Write-Log "queue_after start: own PID $PID, waiting for PID $WaitPid (poll $PollSeconds s)"
while ($null -ne (Get-Process -Id $WaitPid -ErrorAction SilentlyContinue)) {
    Start-Sleep -Seconds $PollSeconds
}
Write-Log "PID $WaitPid has exited; starting preprocessing (workers $Workers, mem budget $MemBudgetGb GB)"

$argList = @('tools\data\preprocess_spanishbcbl.py', '--workers', "$Workers", '--mem-budget-gb', "$MemBudgetGb")
$p = Start-Process -FilePath $Python -ArgumentList $argList -WorkingDirectory $repo `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $Cache '_queue_after.out.log') `
    -RedirectStandardError (Join-Path $Cache '_queue_after.err.log')
Set-Content -Path (Join-Path $Cache '_queue_after.pid') -Value $p.Id -Encoding ascii
Write-Log "preprocessing started: PID $($p.Id)"
$p.WaitForExit()
Write-Log "preprocessing exited: code $($p.ExitCode)"
