# R1 item 8: two more seeds of the Paper 1 MEG decoder (GPU, detached)

Review items: methods review Major 7; domain review M11 (gap G2). Started 2026-11-11 22:09 (queue PID 40300).

- Recipe: `experiments/2026-11-11-m1-09-async-full/config-r4a-full-medium.json` → `config-r4b-full-medium.json` (the Paper 1 async decoder, seed 0). Here seeds 1 and 2; only `train.seed`, `run_name` and `init_from` differ (`config-r4[ab]-full-medium-s[12].json`). Same data and hash split (101 / 11 / 17 sentences).
- Per seed: train r4a (keystroke pretraining) → train r4b (CTC + keystroke aux 0.5, init from that seed's r4a) → `fidetype.decoders.infer --control` (greedy; real / shuffled / zeros) → beam + char LM (`experiments/2026-11-08-m1c2-beam-lm/run.py`, stages controls, grid, eval; val grid then test once).
- Queue: [queue.ps1](queue.ps1) (copy that runs: `C:\Users\zhang\bci-data\runs\queue-2026-11-12-m1-09-seeds\queue.ps1`). Max 1 heavy job at a time; checkpoints every 5 min (`latest.pt`); AC sleep never + `SetThreadExecutionState` keep-awake while it runs, restored to 30 min in `finally`; it does not put the PC to sleep. Hard stop 2026-11-12 14:00. Restartable: finished runs are skipped, unfinished runs resume from `latest.pt`.
- Outputs: runs `C:\Users\zhang\bci-data\runs\m1-09-r4[ab]-full-medium-s[12]`; streams `C:\Users\zhang\bci-data\streams\m1-09-r4b-full-medium-s[12]`; beam tables `results/beam-m1-09-r4b-full-medium-s[12]/tables.md` (this folder, written by the queue).
- ETA: seed 1 about 00:30, seed 2 about 03:00 on 2026-11-12 (r4a took 45 active min for seed 1).

## Commands
- Check: `Get-Content C:\Users\zhang\bci-data\runs\queue-2026-11-12-m1-09-seeds\queue.log -Tail 10`
- Stop: `Stop-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\queue-2026-11-12-m1-09-seeds\queue.pid)`; then `taskkill /T /F /PID (Get-Content C:\Users\zhang\bci-data\runs\<run>\pid.txt)` (or the infer / beam python); then `powercfg /change standby-timeout-ac 30` (a hard kill skips the `finally` block).
- Resume: start the queue again (`Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\zhang\bci-data\runs\queue-2026-11-12-m1-09-seeds\queue.ps1'`), or resume one run: `.\experiments\2026-11-08-m1b-decoder\launch.ps1 -RunName <run> -Resume`.

## Next (when done)
Report greedy and beam + LM test CER per seed and the seed SD next to seed 0 (0.506 / 0.475); re-run the G1 trust harness (`experiments/2026-11-11-g1-async-meg-trust/run.py`, with `CONFIG["streams"]` pointed at each seed's streams) to give the MEG trust numbers per seed.
