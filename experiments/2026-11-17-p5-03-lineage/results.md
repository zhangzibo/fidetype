# P5-03 / P5-04: lineage of one committed word on Brain-to-Text '25 (2026-11-17)

**Question.** Does the ledger reproduce the full lineage of one committed word (roadmap P5 exit criterion), with licence flags on the output, and does an erasure keep the chain verifiable?

**Data.** Brain-to-Text '25, participant T15 copy task (CC0 1.0; track `b2t25-t15`); the M6-06 / M2-09 pipeline (published online RNN logits, our phoneme -> word decoder, Tatoeba char 6-gram LM + CMUdict). Subset: every 4th fit-half trial for the fit (203), every 12th test-half trial for the replay (68). The subset is for the ledger demo only; the metrics are not a result. CPU only, isolation runner (background, 4 threads), 57 s.

**Run.** `.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I experiments/2026-11-17-p5-03-lineage/run.py`

## Results

| Check | Result |
|---|---|
| Ledger entries | 80: genesis 1, note 1, source 3, artifact 3, context 1, decision 68, correction 3 |
| `verify` with the head anchor (plain and gzip) | PASS |
| Lineage of the first confirmed COMMIT ("they live with us", word 0 "they") | 8 entries: 3 sources (CC0-1.0, CC-BY-2.0-FR, BSD-2-Clause) -> 3 artifacts (weights, LM, calibration) -> context -> decision. [Report](results/lineage-report.md) |
| Licence flags on decisions | 68 of 68 carry flags; research_only 0 (no NC input); product_ok project **false** (CC BY and BSD inputs), commercial true |
| Product LM from Tatoeba + CMUdict under the project rule | Refused (`LicenceError`): the project rule allows only CC0 / own / consented data in product weights |
| Erasure of the picked decision (copy of the ledger) | 1 entry redacted (redaction entry seq 80); `verify` PASS; the decision is gone from `LedgerView` |
| Subset metrics (not a result) | eWPM 10.449, wrong-commit 0.0441, commit rate 0.206 |
| Size | 100,970 bytes JSON Lines (22,777 gzip) for 80 entries |

Files: [summary.json](results/summary.json), [lineage-report.md](results/lineage-report.md), `results/ledger.jsonl.gz` (text stored: B2T '25 is CC0; verify with `python -m fidetype.trust.provenance verify results/ledger.jsonl.gz`).

## Limits
- The "weights" artifact of the published RNN has the dataset file's SHA-256: the logits come with the data, and no weights file exists here.
- Each decision of this pipeline is per sentence. A word's lineage is the lineage of the decision that committed it (word choices are listed when the policy made them).
- The demo uses the B2T '25 lineage only; an NC lineage (SpanishBCBL, emg2qwerty) is covered by the unit tests (`tests/test_trust_lineage_privacy.py`), where each decision is flagged `research_only` and a product artifact is refused.
