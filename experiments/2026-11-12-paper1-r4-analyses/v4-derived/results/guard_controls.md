# v4-derived: frozen v4 configuration (guard + LTT max) on the B2T control streams

Split A fit-A pipeline, guard on, clean calibration; 300 control trials (same draw as R4 no-guard). Commits / n (one-sided 95 % CP upper bound of the commit rate).

| condition | policy | split-A test wrong-commit | controls |
|---|---|---|---|
| b2t-ours | split A guard plug-in | 0.0245 (commit 0.100) | real: 29/300 (<= 0.1295); other_trial: 29/300 (<= 0.1295); frame_shuffled: 0/300 (<= 0.0099); uniform: 0/300 (<= 0.0099) |
| b2t-ours | split A guard LTT max | 0.0245 (commit 0.100) | real: 29/300 (<= 0.1295); other_trial: 29/300 (<= 0.1295); frame_shuffled: 0/300 (<= 0.0099); uniform: 0/300 (<= 0.0099) |
| b2t-ours | split A guard CRC max | 0.0245 (commit 0.100) | real: 29/300 (<= 0.1295); other_trial: 29/300 (<= 0.1295); frame_shuffled: 0/300 (<= 0.0099); uniform: 0/300 (<= 0.0099) |
| b2t-ours | split A guard joint LTT b0.10 | 0.0000 (commit 0.000) | real: 0/300 (<= 0.0099); other_trial: 0/300 (<= 0.0099); frame_shuffled: 0/300 (<= 0.0099); uniform: 0/300 (<= 0.0099) |
| b2t-ours | split A guard joint LTT b0.20 | 0.0000 (commit 0.000) | real: 0/300 (<= 0.0099); other_trial: 0/300 (<= 0.0099); frame_shuffled: 0/300 (<= 0.0099); uniform: 0/300 (<= 0.0099) |
| b2t-published | split A guard plug-in | 0.0478 (commit 0.491) | real: 146/300 (<= 0.5357); other_trial: 0/300 (<= 0.0099); frame_shuffled: 0/300 (<= 0.0099); uniform: 0/300 (<= 0.0099) |
| b2t-published | split A guard LTT max | 0.0294 (commit 0.403) | real: 115/300 (<= 0.4319); other_trial: 0/300 (<= 0.0099); frame_shuffled: 0/300 (<= 0.0099); uniform: 0/300 (<= 0.0099) |
| b2t-published | split A guard CRC max | 0.0478 (commit 0.491) | real: 146/300 (<= 0.5357); other_trial: 0/300 (<= 0.0099); frame_shuffled: 0/300 (<= 0.0099); uniform: 0/300 (<= 0.0099) |
| b2t-published | split A guard joint LTT b0.10 | 0.0000 (commit 0.000) | real: 0/300 (<= 0.0099); other_trial: 0/300 (<= 0.0099); frame_shuffled: 0/300 (<= 0.0099); uniform: 0/300 (<= 0.0099) |
| b2t-published | split A guard joint LTT b0.20 | 0.0184 (commit 0.321) | real: 87/300 (<= 0.3362); other_trial: 0/300 (<= 0.0099); frame_shuffled: 0/300 (<= 0.0099); uniform: 0/300 (<= 0.0099) |
