---
title: Provenance ledger
type: concept
tags: [provenance, audit, traceability, trust, privacy, hash-chain, regulatory]
sources: [brain-to-text-25-copytask]
updated: 2026-11-11
---

# Provenance ledger

## What it is
A **provenance ledger** is an append-only record of where each output of the trust layer came from. For each decision (COMMIT, OFFER, ASK, ABSTAIN, OFFER_WORDS), it records the device and adapter, the decoder (name, version, weights hash), the calibration, the LM, the policy version, the input stream segment, the action and its scores. A later user correction is a new entry that links to the decision it corrects. So any wrong commit can be traced to the exact models and settings that produced it.

The ledger is task **M2-09** of the [project plan](../questions/project-plan.md) (M2 "Trust core v0"). The [architecture](../questions/architecture.md) and the [standard roadmap](../questions/roadmap-standard.md) (trust layer item 3) call for it.

## Design (`fidetype.trust.provenance`)

| Property | How |
|---|---|
| Format | JSON Lines, UTF-8, one entry per line. Schema `fidetype.provenance/0.1` |
| Entry | `schema`, `seq` (0, 1, 2, ...), `ts` (UTC), `kind`, `prev_hash`, `body`, `hash` |
| Hash chain | `hash` = SHA-256 of the canonical JSON (sorted keys, no spaces, no NaN) of the entry without `hash`. The entry holds `prev_hash`, so each hash covers all history before it |
| Entry kinds | `genesis` (entry 0: ledger id, text mode, hash algorithm), `context` (content-addressed: id = SHA-256 of the context, written once), `decision`, `correction`, `note` |
| Verification | `verify(path, expected_head=None)`: schema, contiguous `seq`, `prev_hash` links, recomputed hashes, genesis first, context and decision references, `decision_hash` of each correction |
| Truncation | The chain alone cannot see a cut at the end. Store `ledger.anchor()` (head seq + hash) in a second place and pass it as `expected_head` |
| Corrections | `record_correction(decision_id, text, source)` stores `decision_hash`, `changed`, character and word edit distance, `relation` (correction / confirmation / rejection). The latest correction wins |
| Hooks | `TrustPipeline.attach_ledger(ledger, context, corrections="user" or "oracle" or "none")` writes one decision per attempt in `evaluate()`; the policy fit writes nothing. `run_harness(..., ledger=)`. `LedgeredPolicy(policy, ledger, context_id)` for a live loop |
| Queries | `LedgerView(path).wrong_commits()` (each with its context and corrections), `.summary(keys)` per decoder / calibration / policy version, `audit_report(path)` (Markdown), CLI `python -m fidetype.trust.provenance verify | report <file>` |

What a context holds (from `pipeline_context`):

| Block | Fields |
|---|---|
| `adapter` | name, version (commit id), source dataset, source file SHA-256 |
| `decoder` | name, version, `weights_sha256`, settings, `training_data` (dataset + licence: the "which data trained which weights" link of the [licence rule](../questions/project-plan.md#licence-rule)) |
| `lm` | name, file SHA-256s, training data + licences |
| `stream_meta` | only the spec section 4.2 provenance keys (`device.*`, `decoder.*`, `lm.*`, `adapter.*`, `calibration.*`, `data.derived`, `consent.ref`, `language`) |
| `calibration` | frame and sentence temperatures, conformal α / score / q, `max_wrong_commit`, risk control (method, α, δ, threshold, n, bound; see [CRC](conformal-risk-control.md)), calibration set id, and `id` (hash of these values) |
| `policy` | class, full config, guard config, `version` (hash of class + config) |

## Privacy by design

| Rule | How |
|---|---|
| No raw signals | A decision stores only the SHA-256 of the NeuralTextStream (a derived product), the frame range and the time range. `check_no_raw` rejects any numeric array or numeric list longer than 64 values |
| Text | `text_mode`: `store` (plain text), `hash` (default: hash + lengths), `omit` (nothing) |
| Keyed hash | With a secret `hash_key`, text hashes are HMAC-SHA256. Short sentences then cannot be found by a dictionary attack. Keep the key outside the ledger |
| Ids | `id_mode` for `subject.id` / `session.id`: `hash` (default), `store`, `omit`. Free-text `meta` (notes) is never copied |
| Corrections in hash mode | The ledger keeps the shown text of this session in memory only, so a correction can still store `changed` and the edit distance |

## Spec link
NeuralTextStream v0.1 has an optional, non-breaking extension for provenance (2026-11-11): new `meta` keys `decoder.weights_sha256`, `adapter.name`, `adapter.version`, `stream.id`, and informative section 4.3 (how a consumer should keep provenance records). No required field changed; all v0.1 streams stay valid ([spec](../../spec/neuraltextstream-v0.1.md#43-provenance-informative)).

## Demo on Brain-to-Text '25
The M6-06 trust pipeline replayed the B2T '25 test half (816 trials) with a ledger attached, for two gates: the plug-in gate and a [CRC](conformal-risk-control.md) gate ([experiment](../../experiments/2026-11-11-m2-09-provenance/results.md); data: [Brain-to-Text '25](../sources/brain-to-text-25-copytask.md), CC0).

| | plug-in gate | CRC gate |
|---|---|---|
| eWPM / wrong-commit (harness) | 11.546 / 0.0588 | 11.516 / 0.0478 |
| wrong commits: ledger / harness | 48 / 48 | 39 / 39 |
| silent (user did not notice) | 2 | 1 |

- 1,723 entries; `verify` passes. Edit, edit with re-hash, delete and reorder are all detected; a cut at the end is detected with the head anchor.
- The audit report lists each wrong commit with the text, the correction, the scores, the stream hash and frame range, and the decoder / LM / calibration / policy versions. Most are one-word errors ("who you never expect to when" for "... win").
- Cost: about 0.1 ms per decision (in memory, hash mode); about 1.1 kB per decision entry.

## Limits
- **Tamper-evident, not tamper-proof.** A person who can rewrite the whole file can recompute the chain. An external anchor (a second copy of the head, a signature, or a timestamping service) closes this gap. Signing is not in v0.
- **Wrong commits are known only after a correction.** In live use, a silent error has no correction, so the ledger undercounts wrong commits. A replay with ground truth (`corrections="oracle"`) gives the full count.
- **Single writer.** The file is appended by one process. There is no locking or rotation yet.
- **Training lineage is free-form.** `decoder.training_data` is recorded, but no code checks licences (for example, that NC data cannot reach product weights). That is later work.

> **Our take:** The record format follows the IEC 62304 idea of traceability (each output traces to a versioned software item and its configuration) and the "audit trail" idea of medical device software. This is our interpretation. We did not check the standards' text. The ledger supports such a story; it is not a compliance claim.

## Related
- [Conformal risk control](conformal-risk-control.md): its threshold, α and δ go into the calibration block.
- [Brain-to-Text '25 trust result](../questions/b2t25-trust-result.md): the replay of the demo.
- [Standard roadmap](../questions/roadmap-standard.md), [architecture](../questions/architecture.md), [project plan](../questions/project-plan.md).
- Experiment: [M2-09 provenance demo](../../experiments/2026-11-11-m2-09-provenance/results.md).
