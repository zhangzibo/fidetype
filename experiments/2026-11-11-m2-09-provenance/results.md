---
title: "M2-09: provenance ledger v0"
type: experiment
updated: 2026-11-11
---

# M2-09: provenance ledger v0

Goal: for each piece of text that the trust layer shows to the user, keep a record of where it came from. Any wrong commit must be traceable and auditable. The record must not hold raw neural data.

- Code (our own): `src/fidetype/trust/provenance.py`. Harness hooks in `src/fidetype/eval/harness.py` (`TrustPipeline.attach_ledger`, `run_items(..., ledger=)`, `evaluate(test, ledger=)`, `run_harness(..., ledger=)`). `LedgeredPolicy` wraps any policy for a live loop. CLI: `python -m fidetype.trust.provenance verify|report <ledger>`.
- Tests: `tests/test_trust_provenance.py` (25 tests: round trip, chain verification, tamper detection for edit / edit with re-hash / delete / reorder / truncation with anchor, correction linking, the three privacy modes, keyed hashes, no-raw-data guard, policy hook, report and CLI, integration through `TrustPipeline` with and without CRC). Full CPU suite: **294 passed, 4 skipped** (this includes the tests of a parallel task).
- Script: [run.py](run.py). Outputs in `results/`: `ledger-store.jsonl.gz` (the ledger, text stored), `audit-report.md`, `summary.json`, `ledger-hash-head.json`, `run.log`.
- Run: `.venv\Scripts\python.exe -I experiments/2026-11-11-m2-09-provenance/run.py` (9–19 min on CPU, 2 threads, no GPU, depending on other load; the decoding takes almost all of it).
- Concept page: [provenance ledger](../../wiki/concepts/provenance-ledger.md).

## Design in short
| Item | Choice |
|---|---|
| Format | JSON Lines; schema `fidetype.provenance/0.1`; entry = `schema, seq, ts, kind, prev_hash, body, hash` |
| Chain | `hash` = SHA-256 of the canonical JSON of the entry without `hash` (it includes `prev_hash`). Genesis `prev_hash` = 64 zeros |
| Kinds | `genesis`, `context` (content-addressed, written once), `decision`, `correction` (links `decision_id` + `decision_hash`), `note` |
| Decision body | context id; input (stream SHA-256, `stream.id` if any, source, frame range, time range, attempt, item ref, hashed subject / session); action; reason; scores (`p_top1`, set size, `includes_other`, guard risk, word confidence); top-1 and shown texts (by text mode) |
| Context | adapter (name, commit, source file SHA-256), decoder (name, version, weights SHA-256, settings, training data + licence), LM (file SHA-256s, training data + licences), spec 4.2 provenance meta keys, calibration (temperatures, conformal α / q, CRC / LTT method, α, δ, threshold, n, bound, calibration set id, `cal-` id), policy (class, config, guard config, `pol-` version) |
| Privacy | no arrays (guard rejects numeric lists > 64 values); `text_mode` store / hash (default; HMAC-SHA256 with a secret key) / omit; `id_mode` the same for subject and session ids; free-text meta never copied |

## Demo: Brain-to-Text '25 replay
Setting: the M6-06 trust pipeline on B2T '25 (our phoneme → word decoder over the published online RNN logits), fitted on the fit half (812 trials) exactly as in M6-06 and M2-13. Two gates evaluate the same test half (816 trials, 14 days): the plug-in gate of M6-06 and a CRC gate (`risk_control="crc"`, α 0.05, half of the fit half held out for the CRC step). Both write into one ledger (`text_mode="store"`: B2T '25 is CC0 and M6-06 already uses its sentences; `id_mode="hash"`). The oracle (ground truth) writes a correction for each wrong commit; the entry notes if the simulated user noticed it.

| | plug-in gate (M6-06) | CRC gate |
|---|---|---|
| eWPM | 11.546 | 11.516 |
| wrong-commit rate (harness) | 0.0588 | 0.0478 |
| commit rate | 0.232 | 0.196 |
| `commit_p` | 0.50 | 0.536 |
| decisions in the ledger | 816 | 816 |
| wrong commits in the ledger / in the harness | 48 / 48 | 39 / 39 |
| of these, silent (user did not notice) | 2 | 1 |
| commit precision (ledger) | 0.746 | 0.756 |
| calibration id / policy version | `cal-692fb52a73417552` / `pol-2eaa4ff51919527a` | `cal-e6a13a7844c815a6` / `pol-92a5150a77905417` |

- The plug-in numbers reproduce M6-06 and M2-13 exactly (0.0588, 11.546 eWPM). The ledger counts equal the harness counts, so the hooks lose no decision and add none (the policy fit writes nothing).
- **Ledger:** 1,723 entries (1 genesis, 1 note, 2 contexts, 1,632 decisions, 87 corrections). `verify` passes on the file and on the `.gz`, also with the external head anchor.
- **Tamper checks** on the real ledger: an edited score → "hash mismatch" at that entry; an edited action with a recomputed hash → the next entry's `prev_hash` breaks; a deleted correction and a swapped pair → `seq` and `prev_hash` errors; a cut of the last 3 entries passes the chain check alone, and the head anchor catches it. All detected.
- **Audit report** (`results/audit-report.md`): the summary per decoder / calibration / policy version, then each wrong commit with the committed text, the correction, the edit distance, the scores, the stream hash and frame range, the decoder, LM, calibration (temperatures, risk control) and the policy thresholds. Typical wrong commits are one-word errors: "who you never expect to **when**" (truth "win"), "every major city has a" (truth adds "theater"), "it's not like **him** going home" ("i'm").
- **Cost:** 0.10 ms per decision (0.14 ms in a first run) for an in-memory ledger in `hash` mode (stream hash + HMAC + JSON; 816 decisions). About 1.1 kB per decision entry (store or hash mode). The stored ledger is 1.80 MB, 0.30 MB gzipped.

## What this shows and what it does not
- It shows that every decision of the trust layer can carry a complete, verifiable provenance record with no raw signal, at a negligible time cost, and that the record answers "which models and settings produced this wrong commit".
- In a replay the oracle knows every wrong commit. In live use, only noticed errors get a correction (`corrections="user"`), so silent errors are missing from the ledger (here 2 of 48 and 1 of 39).
- The chain is tamper-evident, not tamper-proof: a person who can rewrite the whole file can recompute it. An external anchor or a signature closes this; signing is not in v0.
- `weights_sha256` is `None` in this demo: the RNN logits come from the dataset file, so the context records the file's SHA-256 instead. Our own decoders can fill it with `file_sha256(checkpoint)`.

## Spec
NeuralTextStream v0.1 gets an optional, non-breaking extension: `meta` keys `decoder.weights_sha256`, `adapter.name`, `adapter.version`, `stream.id`, and an informative section 4.3 on provenance records. No required field changed; the spec tests pass unchanged (all v0.1 streams stay valid).
