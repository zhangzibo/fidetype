# M4-13 GPU job: long training run (dedicated L 0) -> decode val_eval on the GPU -> eval.py on the CPU (once) -> DONE.
# Start / resume: .venv\Scripts\python.exe experiments\2026-11-15-m4-13-long-train\launch.py
#         (CREATE_NO_WINDOW + new process group + job breakaway; children share the hidden console via -NoNewWindow.
#          Never Start-Process -WindowStyle Hidden: it opens a visible window and closing it kills the run.)
# Check:  Get-Content C:\Users\zhang\bci-data\runs\m4-13-queue.log -Tail 5
#         Get-Content C:\Users\zhang\bci-data\runs\m4-13-long0\train.log -Tail 3 ; Get-Content C:\Users\zhang\bci-data\runs\m4-13-long0\metrics.jsonl
# Pause:  New-Item C:\Users\zhang\bci-data\runs\m4-13-long0\pause   (latest.pt written after the current step, then exit; GPU free in seconds)
# Resume: Remove-Item C:\Users\zhang\bci-data\runs\m4-13-long0\pause ; then the Start command (continues from latest.pt, exact step)
# Stop:   New-Item C:\Users\zhang\bci-data\runs\m4-13-long0\stop    (same as pause, but status "stopped"; remove it to resume later)
#         hard: taskkill /T /F /PID (Get-Content C:\Users\zhang\bci-data\runs\m4-13-queue.pid)  (loses at most 4 min)
# Done:   C:\Users\zhang\bci-data\runs\m4-13-queue.DONE ("ok=True" / "ok=False"). Pause or stop does NOT write it.
# Keep-awake: this powershell holds SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) while it runs.
$Repo='C:\Users\zhang\OneDrive\Documents\GitHub\stealth-project'
$Py='C:\venvs\fidetype-rocm\Scripts\python.exe'
$VPy="$Repo\.venv\Scripts\python.exe"
$Exp='experiments\2026-11-15-m4-13-long-train'
$Root='C:\Users\zhang\bci-data\runs'
$Run="$Root\m4-13-long0"
$Own='C:\Users\zhang\bci-data\derived\m4-13'
$Log="$Root\m4-13-queue.log"
Remove-Item "$Root\m4-13-queue.DONE" -ErrorAction SilentlyContinue
$PID | Out-File "$Root\m4-13-queue.pid" -Encoding ascii
function L($m) { Add-Content $Log ("{0} {1}" -f (Get-Date -Format s), $m) -Encoding utf8 }
$env:PYTHONUNBUFFERED='1'; $env:OMP_NUM_THREADS='4'; $env:MKL_NUM_THREADS='4'; $env:OPENBLAS_NUM_THREADS='4'
Set-Location $Repo
New-Item -ItemType Directory -Force $Run | Out-Null
New-Item -ItemType Directory -Force $Own | Out-Null
Add-Type -Namespace M413 -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
$ka = [M413.Power]::SetThreadExecutionState([uint32]2147483649)
L "queue start (keep-awake previous state $ka)"
$ok = $true; $paused = $false
$st = if (Test-Path "$Run\status.json") { (Get-Content "$Run\status.json" | ConvertFrom-Json).status } else { '' }
if ($st -ne 'done') {
  $a = @('-m','fidetype.utils.isolation','run','--class','background','--threads','4','--',$Py,'-u',"$Exp\train.py",'--which','dedicated_0')
  if (Test-Path "$Run\latest.pt") { $a += '--resume' }
  L "train start args: $($a -join ' ')"
  $p = Start-Process -FilePath $VPy -ArgumentList $a -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$Run\stdout.log" -RedirectStandardError "$Run\stderr.log"
  L "train exit code $($p.ExitCode)"
  if ($p.ExitCode -ne 0) { $ok = $false }
  $st = (Get-Content "$Run\status.json" | ConvertFrom-Json).status
  if ($st -in @('paused','stopped')) { L "train $st (no DONE file)"; $paused = $true }
}
if (-not $paused -and $ok) {
  if (-not (Test-Path "$Own\decode-m4-13-long0-val_eval.json")) {
    $d = @('-m','fidetype.utils.isolation','run','--class','background','--threads','4','--',$Py,'-u',"$Exp\decode.py",'--which','dedicated_0','--part','val_eval','--gpu')
    L "decode start"
    $q = Start-Process -FilePath $VPy -ArgumentList $d -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$Run\decode-stdout.log" -RedirectStandardError "$Run\decode-stderr.log"
    L "decode exit code $($q.ExitCode)"
    if ($q.ExitCode -ne 0) { $ok = $false }
  }
  if ($ok -and -not (Test-Path "$Repo\$Exp\results\eval.json")) {
    $c = @('-m','fidetype.utils.isolation','run','--class','background','--threads','4','--',$VPy,'-I',"$Exp\eval.py")
    L "eval start"
    $r = Start-Process -FilePath $VPy -ArgumentList $c -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$Root\m4-13-eval.out" -RedirectStandardError "$Root\m4-13-eval.err"
    L "eval exit code $($r.ExitCode)"
    if ($r.ExitCode -ne 0) { $ok = $false }
  }
}
if ($paused) { L "QUEUE PAUSED (no DONE file)" } else {
  L "QUEUE DONE ok=$ok"
  "ok=$ok $(Get-Date -Format s)" | Out-File "$Root\m4-13-queue.DONE" -Encoding ascii
}
[M413.Power]::SetThreadExecutionState([uint32]2147483648) | Out-Null
