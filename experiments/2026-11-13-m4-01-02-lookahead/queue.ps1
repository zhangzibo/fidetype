# M4-01 GPU queue: train the lookahead decoders one at a time (shared, dedicated_0, dedicated_25).
# Start:  Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','experiments\2026-11-13-m4-01-02-lookahead\queue.ps1'
# Check:  Get-Content C:\Users\zhang\bci-data\runs\m4-01-queue.log -Tail 5 ; Get-Content C:\Users\zhang\bci-data\runs\<run>\train.log -Tail 3
# Stop:   New-Item C:\Users\zhang\bci-data\runs\m4-01-queue.stop ; New-Item C:\Users\zhang\bci-data\runs\<run>\stop (clean, after the epoch)
#         hard: taskkill /T /F /PID (Get-Content C:\Users\zhang\bci-data\runs\m4-01-queue.pid)
# Resume: remove m4-01-queue.stop and start again (an unfinished run resumes from latest.pt; finished runs are skipped).
$Repo='C:\Users\zhang\OneDrive\Documents\GitHub\stealth-project'
$Py='C:\venvs\fidetype-rocm\Scripts\python.exe'
$VPy="$Repo\.venv\Scripts\python.exe"  # runs fidetype.utils.isolation (background class: CPUs 0-7, below normal)
$Root='C:\Users\zhang\bci-data\runs'
$Log="$Root\m4-01-queue.log"
$PID | Out-File "$Root\m4-01-queue.pid" -Encoding ascii
function L($m) { Add-Content $Log ("{0} {1}" -f (Get-Date -Format s), $m) -Encoding utf8 }
$env:PYTHONUNBUFFERED='1'; $env:OMP_NUM_THREADS='4'; $env:MKL_NUM_THREADS='4'; $env:OPENBLAS_NUM_THREADS='4'
Set-Location $Repo
L "queue start"
function Decode($w, $run) {
  # decode val_eval at every lookahead on the GPU (no training runs at that moment)
  $d = @('-m','fidetype.utils.isolation','run','--class','background','--threads','4','--',$Py,'-u','experiments\2026-11-13-m4-01-02-lookahead\decode.py','--which',$w,'--gpu')
  L "decode start $w"
  $q = Start-Process -FilePath $VPy -ArgumentList $d -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$Root\$run\decode-stdout.log" -RedirectStandardError "$Root\$run\decode-stderr.log"
  L "decode exit $w code $($q.ExitCode)"
}
foreach ($w in @('shared','dedicated_0','dedicated_25')) {
  if (Test-Path "$Root\m4-01-queue.stop") { L "queue stop file"; break }
  $run = @{shared='m4-01-la-shared'; dedicated_0='m4-01-la-fixed0'; dedicated_25='m4-01-la-fixed25'}[$w]
  $sf = "$Root\$run\status.json"
  $st = if (Test-Path $sf) { (Get-Content $sf | ConvertFrom-Json).status } else { '' }
  if ($st -in @('done','early_stopped','stopped')) {
    $dm = "C:\Users\zhang\bci-data\derived\m4-01-02-lookahead\decode-$run.json"
    if ((Test-Path $dm) -and ((Get-Content $dm -Raw) -match 'best\.pt') -and ((Get-Content $dm -Raw) -match '"limit": null')) { L "skip $w ($st, decoded)"; continue }
    L "skip training $w ($st)"; Decode $w $run; continue
  }
  New-Item -ItemType Directory -Force "$Root\$run" | Out-Null
  $a = @('-m','fidetype.utils.isolation','run','--class','background','--threads','4','--',$Py,'-u','experiments\2026-11-13-m4-01-02-lookahead\train.py','--which',$w)
  if (Test-Path "$Root\$run\latest.pt") { $a += '--resume' }
  L "train start $w args: $($a -join ' ')"
  $p = Start-Process -FilePath $VPy -ArgumentList $a -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$Root\$run\stdout.log" -RedirectStandardError "$Root\$run\stderr.log"
  L "train exit $w code $($p.ExitCode)"
  if ($p.ExitCode -ne 0) { L "nonzero exit: queue ends (check stderr.log)"; break }
  Decode $w $run
}
L "QUEUE DONE"
