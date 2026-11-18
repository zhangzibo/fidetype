---
title: Provenance ledger
type: concept
tags: [provenance, audit, traceability, trust, privacy, hash-chain, regulatory, licence, consent, deletion]
sources: [brain-to-text-25-copytask]
updated: 2026-11-17
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
| Entry kinds | `genesis` (entry 0: ledger id, text mode, hash algorithm), `context` (content-addressed: id = SHA-256 of the context, written once), `decision`, `correction`, `note`, `update` (P15-02: one decoder / trust-config update step, stage `proposed` / `accepted` / `rejected`; a decision links to its proposal by hash; `parent_config_id` -> `config_id` chain per `chain`; written by `GuardedUpdateLoop(ledger=)`) |
| Verification | `verify(path, expected_head=None)`: schema, contiguous `seq`, `prev_hash` links, recomputed hashes, genesis first, context and decision references, `decision_hash` of each correction; for `update` entries: each decision has an earlier proposal (`proposal_hash`), no update is decided twice, an accepted update starts from the last accepted `config_id` of its chain and gives a new one, a rejected update keeps it |
| Lineage + licences (P5-03) | Kinds `source` (dataset, SPDX licence, digest; consented data names its consent ref and scope) and `artifact` (weights, LM, calibration, ...; `derived_from` earlier ids; `purpose` research / product). A context with `lineage` carries the combined licence flags; each decision carries `licence` (`research_only`, `commercial_ok`, `product_ok`). A product artifact with an NC input is refused (`LicenceError`); `verify` recomputes every flag |
| Hash rule `salted-body` (P5-04) | New ledgers: each entry holds `salt` and `body_sha256`; the entry hash covers the digest, not the body. Old ledgers keep rule `v0` and still verify |
| Redaction (P5-04) | Kind `redaction` names removed entries (decisions, their corrections, notes) by seq + hash, with a reason code and an opaque request ref. The bodies are then removed (tombstones); the chain still verifies. `redact_subject`, `redact_decisions`, CLI `redact`, `fidetype.trust.privacy.erase` |
| Truncation | The chain alone cannot see a cut at the end. Store `ledger.anchor()` (head seq + hash) in a second place and pass it as `expected_head` |
| Signed anchor (P5-14) | `anchor --sign-key-file` signs the head with Ed25519 (`fidetype.trust.anchor`, extra `[sign]`); `verify --anchor --public-key` checks the signature, the ledger id, the anchored entry and the chain. A rewritten ledger with a recomputed chain fails. Option: RFC 3161 timestamp or a second host ([docs](../../docs/provenance-and-privacy.md) section 4) |
| Automatic signed anchors (P5-16) | `AutoAnchor(ledger, key, dir, every_n=, every_s=)` writes `anchor-<seq>.json` (Ed25519) every N entries, every T seconds with new entries, and at stop; Collector option `ledger.anchor` (key from `key_env` or `key_file`, never in the config). `verify --anchor <dir> --allow-growth` checks the newest. A rewrite after the last manual anchor fails against the automatic one ([docs](../../docs/provenance-and-privacy.md) section 4.1a) |
| Stream licence (P5-13, FEP-0010) | A stream with `data.licence` / `data.research_only` becomes a `source` entry; its context lists it in `stream_sources` and combines it with the artifact lineage; `verify` recomputes the flags. The trust layers copy `research_only` into `trust_decision.input` |
| Corrections | `record_correction(decision_id, text, source)` stores `decision_hash`, `changed`, character and word edit distance, `relation` (correction / confirmation / rejection). The latest correction wins |
| Hooks | `TrustPipeline.attach_ledger(ledger, context, corrections="user" or "oracle" or "none")` writes one decision per attempt in `evaluate()`; the policy fit writes nothing. `run_harness(..., ledger=)`. `LedgeredPolicy(policy, ledger, context_id)` for a live loop |
| Queries | `LedgerView(path).wrong_commits()` (each with its context and corrections), `.summary(keys)` per decoder / calibration / policy version, `audit_report(path)` (Markdown), CLI `python -m fidetype.trust.provenance verify | report | anchor | lineage | redact <file>`; `LedgerView.lineage(decision_id)` and `lineage_report` (P5-03) |

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

## Lineage of one committed word (P5-03, 2026-11-17)
On a B2T '25 subset replay (203 fit / 68 replay trials; CC0), the ledger gave the full lineage of the first confirmed COMMIT ("they live with us"): 3 sources (CC0-1.0, CC-BY-2.0-FR, BSD-2-Clause) -> 3 artifacts (weights, LM, calibration) -> context -> decision, 8 entries, `verify` PASS. All 68 decisions carry licence flags (research_only 0; product_ok under the project rule false, because of the CC BY corpus). An erasure of the decision kept `verify` PASS ([experiment](../../experiments/2026-11-17-p5-03-lineage/results.md), [report](../../experiments/2026-11-17-p5-03-lineage/results/lineage-report.md); docs: [provenance and privacy](../../docs/provenance-and-privacy.md)).

> **Our take:** The project rule (product weights only from CC0 or our consented data) already excludes the Tatoeba LM (CC BY 2.0 FR) from product use. A product LM needs a CC0 corpus or the `commercial` policy with attribution.

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
- **Tamper-evident, not tamper-proof.** A person who can rewrite the whole file can recompute the chain. An external anchor (a second copy of the head, a signature, or a timestamping service) closes this gap. P5-14 (2026-11-17) adds signed anchors (Ed25519); the private key stays with the operator.
- **Wrong commits are known only after a correction.** In live use, a silent error has no correction, so the ledger undercounts wrong commits. A replay with ground truth (`corrections="oracle"`) gives the full count.
- **Single writer.** The file is appended by one process. There is no locking or rotation yet.
- **Training lineage is free-form** in the context's `decoder.training_data`. **Closed by P5-03 (2026-11-17):** `source` / `artifact` entries carry checked licence flags; a product artifact with NC inputs is refused. The flags are only as good as the declared inputs: the ledger cannot see an input that nobody records.
- **Redaction removes bodies, not copies.** Backups and synced folders are outside the ledger (P5-04). P5-15 (2026-11-17): `erase` also removes the subject from Collector output files (decision logs, NTS stream files, `os_text` log) through a subject index and per-session files ([docs](../../docs/provenance-and-privacy.md) section 8).

> **Our take:** The record format follows the IEC 62304 idea of traceability (each output traces to a versioned software item and its configuration) and the "audit trail" idea of medical device software. This is our interpretation. We did not check the standards' text. The ledger supports such a story; it is not a compliance claim.

## Related
- [Conformance suite](conformance-suite.md): its level "provenance" checks that producers emit the keys this ledger copies (`stream.id`, `decoder.weights_sha256`, `adapter.*`).
- [Conformal risk control](conformal-risk-control.md): its threshold, α and δ go into the calibration block.
- [Brain-to-Text '25 trust result](../questions/b2t25-trust-result.md): the replay of the demo.
- [Neural-data law table](../questions/neural-data-law.md): why deletion and consent references matter (not legal advice).
- [Standard roadmap](../questions/roadmap-standard.md), [architecture](../questions/architecture.md), [project plan](../questions/project-plan.md).
- Experiment: [M2-09 provenance demo](../../experiments/2026-11-11-m2-09-provenance/results.md).

> **Streaming (M4-03):** the [streaming trust layer](streaming-trust-layer.md) runs this part live, per session, from a frozen configuration.
