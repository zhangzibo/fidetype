---
title: Open gaps (registered as roadmap items)
type: question
tags: [planning, roadmap, gaps, trust, benchmark, spec]
sources: []
updated: 2026-11-16
---

# Open gaps (registered as roadmap items)

**Question (user, 2026-11-16):** "make sure we do indeed fix the gap later."

**Answer:** each known gap of 2026-11-16 is now a tracked item in the [roadmap](roadmap-standard.md) and in the [progress tracker](../progress/index.html). An item closes only when its "done when" is met and the fix is committed.

**Convention:** a new item gets the next free number of its phase (for example P15-13). The field "follow-up of" names the existing item that it extends. No existing item moved, changed its id or was removed.

**Rule for new gaps:** when an agent report names a new gap, the orchestrator adds an item here and in the roadmap, with the same fields.

## Open items
| Gap | New id | Item | Status | Follow-up of | Depends on | Found in |
|---|---|---|---|---|---|---|
| 1 | [P15-13](roadmap-standard.md#p15-13-update-gate-per-based-non-inferiority-challenger-test) | Update gate: PER-based non-inferiority challenger test | `todo` | P15-02, P15-03 | M4-13 rerun result H3 ([plan](../../experiments/2026-11-17-p15-03-f1-m4-13/plan.md)); P15-02 | Commit `97a2fc4` (trust reruns on M4-13, dry run): the gate accepted the reversed decoder (2 discordant pairs, p 0.25). |
| 2 | [P15-14](roadmap-standard.md#p15-14-certified-hallucination-bound-on-t12-or-proof-that-none-is-possible) | Certified hallucination bound on T12 (or proof that none is possible) | `todo` | P15-06 | M4-13; pre-registered V-single variant ([plan](../../experiments/2026-11-17-f2-m4-13/plan.md)); P15-06 | Commit `958040a` (P15-06 T12: 180 LTT test items < 230 needed at α 0.01, δ 0.1). |
| 3 | [P5-08](roadmap-standard.md#p5-08-non-vacuous-precision-bound-when-it-types-it-is-right) | Non-vacuous precision bound ("when it types, it is right") | `todo` | P5-02 | M4-13 rerun ([plan](../../experiments/2026-11-17-p5-02-precision-m4-13/plan.md)) or a per-word commit; P11-01 | Commits `13f1853` (precision replay vacuous on T15 + T12) and `3dc84bf` (P5-02 done, open point). |
| 4 | [P15-15](roadmap-standard.md#p15-15-hallucination-benchmark-protocol-02-paired-swapped--real-commit-ratio-pass-rule) | Hallucination benchmark protocol 0.2: paired swapped / real commit-ratio pass rule | `todo` | P15-07 | P15-07 | Commit `bdefe45` (P15-07 done; fixed rule lets rarely-committing systems pass). |
| 4 | [P15-16](roadmap-standard.md#p15-16-hallucination-benchmark-baseline-that-commits-often-and-checks-the-signal) | Hallucination benchmark baseline that commits often and checks the signal | `todo` | P15-07 | P15-15; M4-13 / P11 decoders; P15-06 | Commit `bdefe45` (P15-07 open point). |
| 7 | [P1-15](roadmap-standard.md#p1-15-sc-9-eeg-and-fnirs-semconv-keys-from-a-real-producer) | SC-9: `eeg.*` and `fnirs.*` semconv keys from a real producer | `externally_blocked` | P1-04 | An EEG or fNIRS adapter (P4) or dataset that emits the keys | Commit `de2f242` (FEP-0009: `eeg` and `fnirs` stay planned, SC-9). |
| 8 | [P14-10](roadmap-standard.md#p14-10-safe-wpm-on-the-remaining-tracks-b2t24-t12-willett-hw-kt-semg-emg2qwerty-p11-01) | Safe WPM on the remaining tracks (b2t24-t12, willett-hw, kt-semg, emg2qwerty, P11-01) | `todo` (partly closed, see below) | P14-05 | P14-05, P6-01 (done), P6-02, P11-01 | Commit `7d74c0f` (P14-05 safe WPM baselines; missing tracks and controls); partly closed by `1d4ff8c` (P6-01). |
| 11 | [P5-09](roadmap-standard.md#p5-09-drift-test-that-detects-a-spread-change-at-the-same-centre) | Drift test that detects a spread change at the same centre | `todo` | P5-01 | P5-01 | Commit `9cb7a81` (P5-01 done; scale changes not detected). |
| 12 | [P5-10](roadmap-standard.md#p5-10-personaltrust-watches-the-guard-risk) | PersonalTrust watches the guard risk | `todo` | P5-01 | P5-01 | Commit `9cb7a81` (P5-01: on T12 the guard risk drifts, `p_top1` does not; test not wired into `PersonalTrust`). |
| 13 | [P15-18](roadmap-standard.md#p15-18-pilots-store-per-item-null-control-outputs) | Pilots store per-item null-control outputs | `todo` | P15-12 | — | Commit `9cb7a81` (P5-01 replay used conservative proxies from the P15-02 counts). |
| 14 | [P15-19](roadmap-standard.md#p15-19-show-usefulness-on-stronger-decoders-p5-01-p15-02-p5-02-p15-06) | Show usefulness on stronger decoders (P5-01, P15-02, P5-02, P15-06) | `todo` | P5-01, P15-02, P5-02, P15-06 | M4-13 rerun queue, P11-01 | Commits `9cb7a81`, `4355946`, `3dc84bf`, `958040a` (open points: weak decoder). |
| 15 | [P5-11](roadmap-standard.md#p5-11-replay-the-online-guards-on-t12--t15-through-the-drop-in-api) | Replay the online guards on T12 / T15 through the drop-in API | `todo` | P5-02 | P5-02, P15-04 | Commit `3dc84bf` (P5-02 done; online guards not yet replayed via the drop-in API). |

## Closed gaps
| Gap | Item | How it closed |
|---|---|---|
| 10 | `target_precision` cannot combine with the hallucination bound (joint LTT) | Fixed by P5-02, commit `3dc84bf`: `halluc_bound.joint_ltt(target_precision=)` tests the precision risk as a third risk of the same joint LTT. No new item. |
| 6 (part) | P15-17: G3 audit: independent proof review and its fixes | Review part done, commit `4cd9cb5`: [G3 audit review](g3-audit-review.md), verdict "sound with fixes" (H1 high: delayed / out-of-order feedback can break the bound; M1 fixed public seed; M2 low-power tests; L1-L5). The rest stays open as P15-17. |
| 5 | P1-14: Gap G-13 part (a): apply option A2 (dense + sparse in one frame, sparse keys type-checked) | Done, commit `18713f9`: RC4 amendment 2 (FRM-2). A dense frame MAY carry sparse keys; the dense form wins; the keys keep their types (GEN-11). Python, TypeScript and Rust refuse a wrong type; schema unchanged. Vectors V88 … V92 (341 in all); parity 341/341 and 27,497 fuzz mutants; schema 210/210. G-13 closed in RC4 C.2. |
| 9 | P4-09: BrainFlow bridge: move `device.board_id` / `device.board_name` out of the reserved namespace | Done, commit `18713f9`: vendor keys `brainflow.board_id`, `brainflow.board_name` (MET-3). A BrainFlow board id has a meaning only inside BrainFlow, so the registry evidence rule (SC-1, SC-9) does not support a `device.*` key. ExG now maps `device.modality` to `other`. A test checks: no NTS-NAMESPACE warning. |
| 6 | P15-17: G3 audit: independent proof review and its fixes | Done: review `4cd9cb5`; fixes in commits `98daec3` (code, tests, docs: decision-time accounting, `seed=None`, stronger tests) and `2e4e38d` (review section "Fixes applied"). All findings fixed except the optional L5 (V still uses 1/π), written down as a limit. |
| 8 (part) | P14-10: Safe WPM on the remaining tracks (b2t24-t12, willett-hw, kt-semg, emg2qwerty, P11-01) | P6-01, commit `1d4ff8c`: exact Toronto safe WPM (participant CI) and null-commit audits at the CRC / LTT thresholds for B2T ours, B2T published and MEG. The rest stays open as P14-10. |

## Notes
- Gap 8 (P14-10): partly closed by P6-01 (commit `1d4ff8c`). The rest (scorer, baselines and safe WPM of the new tracks) runs with P6-02.
- Gaps 1, 2, 3 and 14 (P15-13, P15-14, P5-08, P15-19) wait for the M4-13 rerun queue ([plan](../../experiments/2026-11-17-trust-reruns-m4-13/plan.md)). Their pre-registrations exist; read their results first.
- Gap 7 (P1-15) is `externally_blocked`: it needs an EEG or fNIRS producer that fills the keys.
- Gap 6 (P15-17): closed (review `4cd9cb5`, fixes `98daec3`, `2e4e38d`). An outside human review would be a separate, externally blocked step.

> **Our take:** most open gaps have one root cause: the current decoders are weak (top-1 almost never right). The safety results hold, but usefulness is not shown. M4-13 and P11 decoders are the main lever (P15-19).

## Related pages
- [Long-term roadmap](roadmap-standard.md)
- [North star](north-star.md)
- [F1 guarantee scope](f1-guarantee-scope.md)
- [G3 audit review](g3-audit-review.md)
- [Trust personalisation](../concepts/trust-personalisation.md)
- [Open benchmark](../concepts/open-benchmark.md)
- [NTS specification](../concepts/nts-spec.md)
