---
title: SpanishBCBL repeated participants (are S1 and S18 one person?)
type: question
tags: [spanishbcbl, meg, dataset, participants, evaluation, leakage]
sources: [brain2qwerty-v1, brain2qwerty-code]
updated: 2026-11-10
---

# SpanishBCBL repeated participants

**Question:** Our data index maps subject S1 and subject S18 of the [SpanishBCBL](../entities/spanishbcbl-dataset.md) MEG data to one participant, P01. Is this one person, or an index bug? Does it cause train/test leakage in our past results?

**Answer:** S1 and S18 are **one person**. The index is correct. Our splits are by sentence, not by subject, so there is **no leakage** from this merge. The only effect on past results is how "mean over subjects" weights this person. That effect is at most 0.003 CER.

## Evidence

| Evidence | What it says |
|---|---|
| Dataset card (`SpanishBCBL/README.md`, section "Repeated participants (MEG)") | "The following IDs belong to the **same person**": `S1`, `S18` (person 1); `S4`, `S14` (person 4); `S5`, `S10`, `S21` (person 5). With `S23` excluded (metallic implant) this gives "19 unique MEG participants". |
| [Brain2Qwerty code](../sources/brain2qwerty-code.md) (`brain2qwerty_v1/utils.py`, `SUBJECT_MERGE`; `scripts/extract_predictions.py`, `SUBJECT_MERGES`) | Merges `S18 -> S1`, `S14 -> S4`, `S10 -> S5`, `S21 -> S5` before per-participant scoring. |
| Recording folder names | `MEG/FIF/01_9228/` and `MEG/FIF/18_9228/`. The second number (the recording code) is the same: 9228. The other merged groups also share codes (S5/S10/S21: 3660; S4/S14: 9876/9875). |
| Session dates | S1: 2022-04-04 and 2022-04-11. S18: 2023-11-16 and 2023-11-21. The person came back about 19 months later. |
| Sentences | S1 and S18 typed the same 128 sentences (our cache sidecars: 129 distinct targets, 128 shared). |
| Demographics | The release has no `participants.tsv` and no per-person demographics. We cannot check age or sex. |

The merge rule is in our code as `PARTICIPANT_GROUPS` in `src/fidetype/data/spanishbcbl.py`. A unit test (`tests/test_data_spanishbcbl.py::test_participant_groups_match_dataset_card`) checks it against the card.

> **Contradiction:** The card says the merge gives 19 unique participants. By arithmetic, 25 IDs − 4 merged IDs − S23 = **20** people. The release has **no behavioural logs for S13**, so only 19 people have usable typing data. Our discovery finds the same 19 (P01–P09, P11, P12, P15–P17, P19, P20, P22, P24, P25). The [v1 paper](../sources/brain2qwerty-v1.md) says 20 MEG participants, one excluded for metal. We think S13 is the 20th person and its logs are missing from the public release. We have not confirmed this.

## Leakage check

- **Split rule:** `assign_split` in `src/fidetype/data/preprocess.py` hashes the normalised sentence text (SHA-1, 80/10/10). Every repetition of a sentence, in any subject, gets the same split.
- So a test sentence of S18 is also a test sentence of S1. The same person never trains on a sentence that they are tested on.
- Every participant is in train, val and test. This is a **within-subject** design by intent (the same as [Brain2Qwerty v1](../sources/brain2qwerty-v1.md)). The S1/S18 merge does not change this.
- Check on the real cache: S1 + S18 have 129 distinct target sentences, and 0 sentences have more than one split.

> **Update (2026-11-10):** the sentence split was re-checked on all 80 cached blocks (0 split mismatches, 0 shared sentences). But SpanishBCBL has close sentence variants (short / long, singular / plural) that can fall in different splits. See [M1-15 full-r1 and r3 result](m1-15-full-r1-r3-result.md#leakage-checks).

## Effect on past results

| Result | Uses S1 and S18? | Effect |
|---|---|---|
| M1-B (`m1-baseline-…-1subj`, `…-5subj`) | No S18 | None. |
| M1-C (r0–r4b, 11 subject IDs) | Yes | The model already gives S1 and S18 one subject layer (10 layers; `MEGSegments` keys on `participant`). But `infer.summarize` averaged over 11 subject IDs, so P01 counted twice. Recomputed from the saved per-sentence files, test mean CER changes by at most 0.003 (r4b: 0.6237 over subjects, 0.6210 over participants; r0: 0.6686 vs 0.6685). The pooled mean over sentences does not change. |
| Keystroke decoder + M2 real-MEG (`2026-11-08-m2-real-keystroke`) | Yes | Per-subject-ID logistic regression: S1 and S18 get two separate decoders, each trained on its own data only. No leakage. The headline numbers pool all trials, so they do not change. "11 subjects" in that report is 10 people. A P01 decoder trained on both IDs might be a little better (S1 test key acc 0.424, S18 0.304). |

Raw numbers: `C:\Users\zhang\bci-data\streams\<run>\per_sentence_{val,test}.jsonl` (not in the repo).

> **Our take:** Keep separate decoders per subject ID when the sessions are far apart in time. S18 was recorded about 19 months after S1, with a new head position. But report per-person numbers over participants, not over subject IDs. For the paper count, say "10 participants (11 recording IDs)" for M1-C and M2.

## What we changed (2026-11-08)

- `fidetype.decoders.infer.summarize` now also reports `per_participant` and `mean_over_participants`. Rows from `run_inference` now carry `participant`. Old rows without it fall back to the subject ID.
- Tests: `test_participant_groups_match_dataset_card`, `test_one_person_two_subject_ids_share_a_subject_layer`, `test_summarize_counts_each_participant_once`.

Related: [SpanishBCBL](../entities/spanishbcbl-dataset.md) · [Decoder M1 results](decoder-m1-results.md) · [Brain2Qwerty v1](../sources/brain2qwerty-v1.md)
