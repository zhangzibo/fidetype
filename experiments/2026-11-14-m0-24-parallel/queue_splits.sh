#!/usr/bin/env bash
# M0-24 check: Paper 1 R4 split tables (the repeated-split harness), serial vs pmap.
# 1. subset r 50-53, all four B2T jobs: serial (--workers 1) and parallel (auto workers);
# 2. full rebuild in parallel: guard on r 50-199 (ours, published) + guard off r 0-199;
# 3. compare with each other and with the R4 cache; M3-02 repeated-split rows from the rebuild.
# Outputs: C:/Users/zhang/bci-data/runs/m0-24-parallel (outside the repo). A rerun skips finished tables.
cd "$(dirname "$0")/../.." || exit 1
R=C:/Users/zhang/bci-data/runs/m0-24-parallel
PY=.venv/Scripts/python.exe
ISO="$PY -m fidetype.utils.isolation run --class background --threads 1"
ST=experiments/2026-11-12-paper1-r4-analyses/split-tables/run.py
E=experiments/2026-11-14-m0-24-parallel/check_equal.py
CACHE=C:/Users/zhang/bci-data/cache/paper1-r4/splits
JOBS=ours-g1,published-g1,ours-g0,published-g0
log() { echo "$(date +%T) $*" >> $R/queue-splits.log; }
log "subset serial start"
$ISO --label "M0-24 split tables subset serial" -- $PY -I $ST --stage b2t --workers 1 --out $R/st-sub-serial --jobs $JOBS --r-from 50 --r-to 53 > $R/st-sub-serial.stdout 2>&1
log "subset serial exit $?; subset parallel start"
$ISO --label "M0-24 split tables subset parallel" -- $PY -I $ST --stage b2t --workers 8 --out $R/st-sub-par --jobs $JOBS --r-from 50 --r-to 53 > $R/st-sub-par.stdout 2>&1
log "subset parallel exit $?"
$PY -I $E dir $R/st-sub-par $R/st-sub-serial --pattern "b2t-*.json" >> $R/queue-splits.log 2>&1
$PY -I $E dir $R/st-sub-serial $CACHE --pattern "b2t-*.json" >> $R/queue-splits.log 2>&1
log "full parallel start"
$ISO --label "M0-24 split tables full parallel" -- $PY -I $ST --stage b2t --workers 8 --out $R/st-full --jobs ours-g1,published-g1 --r-from 50 --r-to 199 > $R/st-full-g1.stdout 2>&1
log "full g1 exit $?"
$ISO --label "M0-24 split tables full parallel g0" -- $PY -I $ST --stage b2t --workers 8 --out $R/st-full --jobs ours-g0,published-g0 > $R/st-full-g0.stdout 2>&1
log "full g0 exit $?"
$PY -I $E dir $R/st-full $CACHE --pattern "b2t-*.json" >> $R/queue-splits.log 2>&1
$PY -I experiments/2026-11-14-m0-24-parallel/m302_rows.py $R/st-full >> $R/queue-splits.log 2>&1
log "QUEUE DONE"
