# M4-12 GPU queue: retrain the lookahead decoders one at a time, decode val_eval after each, then the CPU stages.
# Order: dedicated_0, dedicated_25, shared, dedicated_10 (200 ms), [CPU stages start in parallel], dedicated_15 (300 ms, addendum),
#        then the CPU stages again (new conditions only for accuracy), then m4-12-queue.DONE.
# Start:  .venv\Scripts\python.exe experiments\2026-11-14-m4-12-decoder-retrain\launch_queue.py
#         (CREATE_NO_WINDOW + new process group + job breakaway; all children share that one hidden console via -NoNewWindow.
#          Do not use Start-Process -WindowStyle Hidden: Windows Terminal ignores it and closing its window kills the run.)
# Check:  Get-Content C:\Users\zhang\bci-data\runs\m4-12-queue.log -Tail 5 ; Get-Content C:\Users\zhang\bci-data\runs\<run>\train.log -Tail 3
# Stop:   New-Item C:\Users\zhang\bci-data\runs\m4-12-queue.stop ; New-Item C:\Users\zhang\bci-data\runs\<run>\stop (clean, at the next validation)
#         hard: taskkill /T /F /PID (Get-Content C:\Users\zhang\bci-data\runs\m4-12-queue.pid)
# Resume: remove m4-12-queue.stop and start again (an unfinished run resumes from latest.pt; finished and decoded runs are skipped).
# Done:   C:\Users\zhang\bci-data\runs\m4-12-queue.DONE is written only when the queue reaches its end ("ok=True") or a step fails
#         ("ok=False"; read the log). A stop file (pause) does NOT write it.
# Keep-awake: this powershell holds SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) while it runs (no window).
$Repo='C:\Users\zhang\OneDrive\Documents\GitHub\stealth-project'
$Py='C:\venvs\fidetype-rocm\Scripts\python.exe'
$VPy="$Repo\.venv\Scripts\python.exe"  # runs fidetype.utils.isolation (background class, below normal)
$Exp='experiments\2026-11-14-m4-12-decoder-retrain'
$Root='C:\Users\zhang\bci-data\runs'
$Log="$Root\m4-12-queue.log"
Remove-Item "$Root\m4-12-queue.DONE" -ErrorAction SilentlyContinue
$PID | Out-File "$Root\m4-12-queue.pid" -Encoding ascii
function L($m) { Add-Content $Log ("{0} {1}" -f (Get-Date -Format s), $m) -Encoding utf8 }
$env:PYTHONUNBUFFERED='1'; $env:OMP_NUM_THREADS='4'; $env:MKL_NUM_THREADS='4'; $env:OPENBLAS_NUM_THREADS='4'
Set-Location $Repo
Add-Type -Namespace M412 -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
$ka = [M412.Power]::SetThreadExecutionState([uint32]2147483649)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
L "queue start (keep-awake previous state $ka)"
$runs = [ordered]@{dedicated_0='m4-12-fixed0'; dedicated_25='m4-12-fixed25'; shared='m4-12-shared'; dedicated_10='m4-12-fixed10'; dedicated_15='m4-12-fixed15'}
$ok = $true
$paused = $false
$cpu = $null
function Decode($w, $run) {
  $d = @('-m','fidetype.utils.isolation','run','--class','background','--threads','4','--',$Py,'-u',"$Exp\decode.py",'--which',$w,'--gpu')
  L "decode start $w"
  $q = Start-Process -FilePath $VPy -ArgumentList $d -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$Root\$run\decode-stdout.log" -RedirectStandardError "$Root\$run\decode-stderr.log"
  L "decode exit $w code $($q.ExitCode)"
  if ($q.ExitCode -ne 0) { $script:ok = $false }
}
function CpuStages($tag, $wait) {
  # accuracy (skips conditions already done) + emission + tables + figure, on the background CPU class
  $c = @('-m','fidetype.utils.isolation','run','--class','background','--threads','4','--',$VPy,'-I',"$Exp\run.py",'accuracy','emission','tables','figure')
  L "cpu stages start ($tag)"
  if ($wait) {
    $r = Start-Process -FilePath $VPy -ArgumentList $c -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$Root\m4-12-cpu-$tag.out" -RedirectStandardError "$Root\m4-12-cpu-$tag.err"
    L "cpu stages exit ($tag) code $($r.ExitCode)"
    if ($r.ExitCode -ne 0) { $script:ok = $false }
    return $null
  }
  return (Start-Process -FilePath $VPy -ArgumentList $c -NoNewWindow -PassThru -RedirectStandardOutput "$Root\m4-12-cpu-$tag.out" -RedirectStandardError "$Root\m4-12-cpu-$tag.err")
}
foreach ($w in $runs.Keys) {
  if (Test-Path "$Root\m4-12-queue.stop") { L "queue stop file (pause)"; $paused = $true; break }
  if ($w -eq 'dedicated_15' -and $cpu -eq $null) { $cpu = CpuStages 'a' $false }  # first CPU pass runs while dedicated_15 trains
  $run = $runs[$w]
  $sf = "$Root\$run\status.json"
  $st = if (Test-Path $sf) { (Get-Content $sf | ConvertFrom-Json).status } else { '' }
  if ($st -in @('done','early_stopped')) {
    $dm = "C:\Users\zhang\bci-data\derived\m4-01-02-lookahead\decode-$run.json"
    if ((Test-Path $dm) -and ((Get-Content $dm -Raw) -match '"limit": null')) { L "skip $w ($st, decoded)"; continue }
    L "skip training $w ($st)"; Decode $w $run; continue
  }
  New-Item -ItemType Directory -Force "$Root\$run" | Out-Null
  $a = @('-m','fidetype.utils.isolation','run','--class','background','--threads','4','--',$Py,'-u',"$Exp\train.py",'--which',$w)
  if (Test-Path "$Root\$run\latest.pt") { $a += '--resume' }
  L "train start $w args: $($a -join ' ')"
  $p = Start-Process -FilePath $VPy -ArgumentList $a -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$Root\$run\stdout.log" -RedirectStandardError "$Root\$run\stderr.log"
  L "train exit $w code $($p.ExitCode)"
  if ($p.ExitCode -ne 0) { L "nonzero exit: queue ends (check stderr.log)"; $ok = $false; break }
  $st = (Get-Content $sf | ConvertFrom-Json).status
  if ($st -eq 'stopped') { L "run $w stopped by stop file (pause)"; $paused = $true; break }
  Decode $w $run
}
if ($cpu -ne $null) { $cpu.WaitForExit(); L "cpu stages exit (a) code $($cpu.ExitCode)"; if ($cpu.ExitCode -ne 0) { $ok = $false } }
if ($paused) {
  L "QUEUE PAUSED (no DONE file)"
} else {
  if ($ok) { CpuStages 'b' $true | Out-Null }
  L "QUEUE DONE ok=$ok"
  "ok=$ok $(Get-Date -Format s)" | Out-File "$Root\m4-12-queue.DONE" -Encoding ascii
}
[M412.Power]::SetThreadExecutionState([uint32]2147483648) | Out-Null  # ES_CONTINUOUS: clear
