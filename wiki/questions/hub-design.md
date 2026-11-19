---
title: Benchmark hub design (P13-01)
type: question
tags: [benchmark, hub, registry, datasets, replay, licence, governance, planning]
sources: [brain-to-text-25-copytask]
updated: 2026-11-18
---

# Benchmark hub design: dataset registry and replay adapters (P13-01)

**Question (roadmap P13-01):** how does the P6 leaderboard become a reproducible hub? We need a versioned dataset registry, replay adapters for SpanishBCBL MEG, Brain-to-Text '25 and one clean EMG dataset, and one-command reruns.

**Answer:** the full design is [docs/hub-design.md](../../docs/hub-design.md). Diagram: [18. Benchmark hub](../diagrams/index.html). This page gives the summary and the user's decisions (2026-11-18).

## Summary
| Part | Decision |
|---|---|
| Registry | One JSON entry per dataset version (`fidetype.hub.dataset/0.1`): id, upstream version, revision, licence + `research_only`, citation, forms with SHA-256, download and verify commands, adapters, tracks. File: `src/fidetype/benchmark/hub/datasets-0.1.json`; checker `python -m fidetype.benchmark.hub`; test `tests/test_hub_registry.py` |
| No re-hosting | The hub holds metadata only. The checker refuses `personal_data.rehost` other than `false` |
| Hub v0.1 datasets | `spanishbcbl` (MEG, research only), `brain-to-text-25` (implant, CC0), `toronto-semg` (EMG, CC BY 4.0; decided: Q1) |
| Replay contract | Ten rules RA-1 … RA-10: split unit in, one NTS stream out, licence keys, neural time, deterministic, same decisions over file / LSL / WebSocket, controls, adapter hash, no text out. Seven are met today; RA-4, RA-7, RA-9 are P13-06 |
| Reruns | A rerun recipe in each result card (dataset, split, adapter hash, decoder, policy, scorer, command) and three levels: `rescore`, `replay`, `full` |
| Versioning | Five versions: dataset, entry revision, split, scorer, metric. A table says which change bumps which ([section 6](../../docs/hub-design.md#6-versioning-rules)) |
| Governance | `candidate` → `registered` → `deprecated` / `withdrawn`; eight criteria for `registered`; licence and consent review as a separate step |
| Later | P13-02 guarantee and control columns, P13-03 pull-request submissions (outlines in the design) |

> **Our take:** the hard part of P13-03 is not CI. It is the truth text: the scorer needs it, and the repo must never hold it. Decision Q2 (2026-11-18): a private truth store for CC0 / CC BY tracks; a maintainer scores the research-only tracks.

> **Our take:** the B2T '25 pkl and HDF5 forms hold the same trials ([T15 split audit](t15-split-audit.md)). The registry records this as `same_units`, so the overlap check of P6-10 has one place to read it.

## Decisions (2026-11-18)
The user answered: "i would like to have a site but the rest you can decide". So Q6 is the user's choice, and the other six questions take our proposals. Full text: [docs/hub-design.md, Decisions](../../docs/hub-design.md#decisions-2026-11-18).

| # | Question | Decision |
|---|---|---|
| Q1 | Hub EMG dataset: Toronto sEMG or KT-sEMG? | **Decided:** Toronto sEMG. KT-sEMG later as a second EMG track |
| Q2 | How does CI score a pull request without the truth in the repo? | **Decided:** a private truth store for CC0 / CC BY tracks; a maintainer scores the research-only tracks. Implementation: P13-03 |
| Q3 | Where do submitted outputs (decoded text) live? | **Decided:** outside git. The PR holds only a pointer and a SHA-256 |
| Q4 | Research-only tracks on the same board? | **Decided:** yes, in a separate section with the `RESEARCH ONLY` mark |
| Q5 | May `rescore`-only entries rank? | **Decided:** yes, with the rerun level shown |
| Q6 | A project site? | **Decided (user):** yes. `node tools/site/build.js` builds it from repo files into `_site/`; the manual-only `.github/workflows/pages.yml` deploys it. Built locally on 2026-11-18 (P13-08); not published until the user's publishing weekend |
| Q7 | Who signs the licence and consent review? | **Decided:** the founder now; a second reviewer later |

## New gaps
- Gap 78 = [P13-06](roadmap-standard.md#p13-06-hub-command-line-and-rerun-recipe): hub command line, rerun recipe in the card, unit key, adapter hash, 3-way transport test. **Closed 2026-11-18:** the hub command line (`list`, `show`, `instructions`, `verify`, `check`, `recipe`, `rerun`) and the rerun recipe with the adapter hash are in every card ([design section 12](../../docs/hub-design.md#12-hub-command-line-and-rerun-recipes-p13-06)). The rest is gap 82 = [P13-10](roadmap-standard.md#p13-10-hub-replay-command-unit-key-transport-test-and-replay-level-rerun) (replay, unit key, 3-way transport test) and gap 83 = [P13-11](roadmap-standard.md#p13-11-complete-rerun-recipes-weights-hash-policy-config-id-hallucination-cards) (weights hash, policy config id, hallucination cards).
- Gap 79 = [P13-07](roadmap-standard.md#p13-07-registry-entries-for-the-other-v02-datasets-and-missing-checksums): registry entries for the other four v0.2 datasets; checksums for the B2T '25 HDF5 zip and the SpanishBCBL files.

## Related pages
- [Open benchmark](../concepts/open-benchmark.md)
- [Long-term roadmap](roadmap-standard.md) (P13)
- [Open gaps](open-gaps.md)
- [T15 split audit](t15-split-audit.md)
- [Error metrics](../concepts/error-metrics.md)
