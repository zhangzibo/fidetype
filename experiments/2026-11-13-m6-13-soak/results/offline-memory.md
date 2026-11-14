# Offline memory check (offline_memory.py logic, 4,400 utterances, no LSL, no shadow)

Columns: utterances, private MB, RSS MB, guard edit-distance memo, RefCharLM memo entries.

## Before the fix (guard uses the shared `cached_edit_distance`, maxsize 200,000; code of commit 6a2250d)

| utt | private MB | RSS MB | memo entries (hits / misses) | RefCharLM |
|---|---|---|---|---|
| 0 | 508.1 | 38.9 | 33 (0 / 33) | 7,503 |
| 400 | 518.9 | 50.2 | 12,341 (496 / 12,341) | 17,269 |
| 800 | 528.2 | 58.8 | 24,218 | 18,002 |
| 1,200 | 536.2 | 66.5 | 35,985 | 18,712 |
| 2,000 | 552.5 | 83.3 | 59,713 | 19,204 |
| 2,800 | 568.4 | 98.6 | 83,279 | 19,916 |
| 3,600 | 585.9 | 116.4 | 106,701 | 20,220 |
| 4,000 | 593.9 | 123.8 | 118,036 (10,025 / 118,036) | 20,518 |

## After the fix (`guard_edit_distance`, maxsize 4,096)

| utt | private MB | RSS MB | memo entries (hits / misses) | RefCharLM |
|---|---|---|---|---|
| 0 | 508.6 | 39.2 | 33 | 7,503 |
| 400 | 513.8 | 44.9 | 4,096 (337 / 12,500) | 17,269 |
| 800 | 513.8 | 45.1 | 4,096 | 18,002 |
| 1,200 | 515.1 | 45.4 | 4,096 | 18,712 |
| 2,000 | 515.1 | 45.6 | 4,096 | 19,204 |
| 2,800 | 515.0 | 45.7 | 4,096 | 19,916 |
| 3,600 | 515.0 | 45.7 | 4,096 | 20,220 |
| 4,000 | 515.0 | 45.7 | 4,096 (4,146 / 123,915) | 20,518 |
