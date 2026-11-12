# R3 item 5: MEG CRC split by sentence and by participant

Review item: stats review M4(a). Script: [run.py](run.py). Config: [config.json](config.json). Numbers: [results/meg_grouped.json](results/meg_grouped.json), [results/tables.md](results/tables.md).

## What we did
- Input: the committed G1 item table (`experiments/2026-11-11-g1-async-meg-trust/results/items-meg-async.json`): trust gate fitted on val; 637 test instances of 17 sentences typed by 19 participants.
- Guarantee status: we checked whether a CRC with the sentence (or the participant) as the exchangeable unit is feasible.
- Splits: 1,000 random splits per row. Calibration = all instances of k sentences (k = 5, 8, 11) or of k participants (k = 6, 12). Test = all other instances. For each split: instance-level CRC, CRC max-rule, LTT, and group-level CRC (one loss per sentence or participant).

## Results
- **No guarantee is possible for new sentences on this data set.** Group-level CRC needs at least 1/α − 1 = 19 calibration groups (LTT needs 45). The clean calibration set has 5 sentences, val 11, the whole test pool 17, and there are 19 participants in all. Group-level CRC was infeasible in 100 % of the splits, so it never commits.
- **Instance-level CRC with disjoint sentences behaved like random instance splits.** Sentence-grouped, 5 / 8 / 11 calibration sentences: mean test wrong-commit 0.016 / 0.018 / 0.019, 95th percentile 0.025 / 0.031 / 0.038, never above α in 1,000 splits. Random instance splits of the same size: 0.017 / 0.019 / 0.019. Participant-grouped 6 / 12: 0.015 / 0.019 (12 of 19: 0.3 % of splits above α).
- These low rates come from the decoder, not from the guarantee: only 2.4 % of instances are eligible, and the error among commits is 0.91–0.94. The plug-in max rule (λ = 0.5) commits nothing in every split.

## Interpretation
> **Our take:** For MEG the paper should report only sentence-grouped splits and say plainly: "instance-level CRC on 5 calibration sentences carries no guarantee for new sentences; a sentence-level guarantee needs ≥ 19 calibration sentences, which this data set does not have." Empirically, the instance-level rate stayed below α also when calibration and test sentences were disjoint, but this is a property of this decoder (it almost never has an eligible, confident candidate), not a guarantee.
