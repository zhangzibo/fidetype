# M4-12 GPU queue: retrain the lookahead decoders one at a time, decode val_eval after each, then the CPU stages.
# Order: dedicated_0, dedicated_25, shared, dedicated_10 (optional; skipped if m4-12-queue.skip10 exists).
# Start:  Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','experiments\2026-11-14-m4-12-decoder-retrain\queue.ps1'
# Check:  Get-Content C:\Users\zhang\bci-data\runs\m4-12-queue.log -Tail 5 ; Get-Content C:\Users\zhang\bci-data\runs\<run>\train.log -Tail 3
# Stop:   New-Item C:\Users\zhang\bci-data\runs\m4-12-queue.stop ; New-Item C:\Users\zhang\bci-data\runs\<run>\stop (clean, at the next validation)
#         hard: taskkill /T /F /PID (Get-Content C:\Users\zhang\bci-data\runs\m4-12-queue.pid)
# Resume: remove m4-12-queue.stop and start again (an unfinished run resumes from latest.pt; finished and decoded runs are skipped).
# Done:   C:\Users\zhang\bci-data\runs\m4-12-queue.DONE is written at the end (also after a stop or an error; read the log).
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
L "queue start"
$runs = [ordered]@{dedicated_0='m4-12-fixed0'; dedicated_25='m4-12-fixed25'; shared='m4-12-shared'; dedicated_10='m4-12-fixed10'}
$ok = $true
function Decode($w, $run) {
  $d = @('-m','fidetype.utils.isolation','run','--class','background','--threads','4','--',$Py,'-u',"$Exp\decode.py",'--which',$w,'--gpu')
  L "decode start $w"
  $q = Start-Process -FilePath $VPy -ArgumentList $d -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput "$Root\$run\decode-stdout.log" -RedirectStandardError "$Root\$run\decode-stderr.log"
  L "decode exit $w code $($q.ExitCode)"
}
foreach ($w in $runs.Keys) {
  if (Test-Path "$Root\m4-12-queue.stop") { L "queue stop file"; $ok = $false; break }
  if ($w -eq 'dedicated_10' -and (Test-Path "$Root\m4-12-queue.skip10")) { L "skip dedicated_10 (skip10 file)"; continue }
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
  $p = Start-Process -FilePath $VPy -ArgumentList $a -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput "$Root\$run\stdout.log" -RedirectStandardError "$Root\$run\stderr.log"
  L "train exit $w code $($p.ExitCode)"
  if ($p.ExitCode -ne 0) { L "nonzero exit: queue ends (check stderr.log)"; $ok = $false; break }
  $st = (Get-Content $sf | ConvertFrom-Json).status
  if ($st -eq 'stopped') { L "run $w stopped by stop file: queue ends"; $ok = $false; break }
  Decode $w $run
}
L "QUEUE DONE ok=$ok"
"ok=$ok $(Get-Date -Format s)" | Out-File "$Root\m4-12-queue.DONE" -Encoding ascii
