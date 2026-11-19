# Benchmark hub design: versioned dataset registry and replay adapters

Status: **design v0.1** (roadmap item P13-01, 2026-11-18). The user decided the seven open questions on 2026-11-18 ([Decisions](#decisions-2026-11-18)). This page is a design. Only the registry file and its checker exist as code. The hub command line, the rerun recipe and the pull-request flow are later items (P13-02, P13-03, P13-06).

The hub **extends** the P6 leaderboard. It does not replace it. Everything below reuses what exists:

| Exists (P6, P14, P15) | Where | The hub adds |
|---|---|---|
| Benchmark tracks v0.2: 7 tracks, hash-only split files, `verify` / `select` | [benchmark-tracks.md](benchmark-tracks.md), `src/fidetype/benchmark/tracks.py` | A dataset registry above the tracks: one entry per dataset version |
| Submission format and scorer v0.2, required controls | [benchmark-submission.md](benchmark-submission.md), `scorecard.py` | A rerun recipe per entry; a training-data overlap flag (P6-10) |
| Safe WPM `safe-wpm/0.1` (v0.2 proposed) | [safe-wpm.md](safe-wpm.md) | Shown with its guarantee fields (P13-02) |
| Hallucination benchmark, protocol 0.2 | [hallucination-benchmark.md](hallucination-benchmark.md) | Optional control columns per entry |
| Static leaderboard | `benchmark/site/`, `python -m fidetype.benchmark leaderboard`, `tools/site/build.js` | Per-track pages, history, a rerun command per entry |
| Licence flags `data.licence` / `data.research_only` | FEP-0010, `src/fidetype/trust/licence.py` | Licence fields in the registry; the same flags in every replayed stream |
| Adapters, LSL and WebSocket replay | `src/fidetype/adapters/`, `fidetype lsl replay-to-lsl`, `fidetype ws replay-to-ws` | One replay contract for all registered datasets |
| Conformance levels (Core, Full, Trust-ready) | [conformance.md](conformance.md) | Replayed streams must pass NTS Core |

Diagram: [18. Benchmark hub](../wiki/diagrams/index.html) (`wiki/diagrams/18-hub-design.drawio`).

## 1. Design rules

1. **The hub hosts metadata only.** It never hosts, mirrors or re-publishes participant data, not even CC0 data. Every user downloads every file from the original source. The registry checker refuses an entry with `personal_data.rehost` other than `false`.
2. **Split files hold only salted hashes.** This is the tracks v0.2 rule. It does not change.
3. **Licence flags travel with the data.** A research-only dataset gives research-only streams, results and weights. The flags come from the registry entry and go into the stream header (FEP-0010).
4. **Our own adapters only.** An adapter is Apache-2.0 code in `fidetype.*`. We never copy dataset companion code (for example the CC BY-NC Brain2Qwerty code).
5. **Every number reruns from one command.** A result that cannot rerun is marked.
6. **Versions never change in place.** A change gives a new version. Old files stay, so old results stay comparable.

## 2. Hub scope v0.1

The roadmap asks for three tracks: MEG, implant, EMG.

| Hub role | Dataset (registry id) | Licence | Track (split version) | Adapter |
|---|---|---|---|---|
| MEG | `spanishbcbl` | CC BY-NC 4.0, **research only** | `spanishbcbl-meg` (`tracks-v0.2`) | `fidetype.adapters.spanishbcbl_meg` |
| implant | `brain-to-text-25` | CC0 1.0 | `b2t25-t15` (`tracks-v0.2`) | `fidetype.adapters.b2t25` |
| EMG | `toronto-semg` | CC BY 4.0 | `toronto-semg` (`tracks-v0.2`) | `fidetype.adapters.toronto_semg` |

The EMG choice is Toronto sEMG (decision Q1, 2026-11-18). KT-sEMG (CC BY 4.0) becomes a second EMG track later. The other four v0.2 datasets (B2T '24, Willett handwriting, KT-sEMG, emg2qwerty) get registry entries later (P13-07). Their tracks stay valid on the P6 leaderboard in the meantime.

## 3. Dataset registry

### 3.1 Files

| File | Content |
|---|---|
| `src/fidetype/benchmark/hub/datasets-0.1.json` | The registry: schema `fidetype.hub.registry/0.1`, a list of dataset entries |
| `src/fidetype/benchmark/hub/__init__.py` | Loader and checker (standard library only). `python -m fidetype.benchmark.hub` checks the file; exit code 1 on a problem |
| `tests/test_hub_registry.py` | The committed file is valid; tracks and licence flags agree with `tracks.py`; bad entries are refused |

The older `src/fidetype/benchmark/registry.py` (v0.1 tracks) and the dataset fields in `tracks.py` stay. The hub registry is the one place for **dataset** facts. Tracks point to it by `dataset` id. Moving the old fields onto the registry is part of P13-06; it must not change a split file.

### 3.2 Dataset entry (schema `fidetype.hub.dataset/0.1`)

One entry per **dataset version**. Key = `id` + `version`.

| Field | Required | Content |
|---|---|---|
| `schema` | yes | `fidetype.hub.dataset/0.1` |
| `id` | yes | kebab-case, stable for all versions (`brain-to-text-25`) |
| `version` | yes | The **upstream** version as the source names it (`dryad-2025-07-03`, `hf-snapshot-2026-11-08`) |
| `revision` | yes | Integer, starts at 1. It counts metadata fixes of this entry (a moved URL, a typo). A revision never changes a split or a score |
| `status` | yes | `candidate`, `registered`, `deprecated` or `withdrawn` (section 7) |
| `title`, `modality`, `language`, `participants` | yes (`participants` may be null) | Description. `modality` uses the semconv modality names |
| `citation` | yes | `text` (required), `doi` (paper), `data_doi` (dataset) |
| `url` | yes | Landing page of the original source. Must equal the track `url` |
| `licence` | yes | `spdx`, `source_text` (as the source writes it), `research_only`, `share_alike`, `attribution`. Checker: an `-NC` licence forces `research_only: true`; an `-SA` licence forces `share_alike: true` |
| `personal_data` | yes | `participant_data` (bool), `rehost` (must be `false`), `note` |
| `forms` | yes | The physical forms of the dataset. Each: `form`, `description`, `files` (`name`, `bytes`, `sha256` or null + `note`, optional `md5`) |
| `same_units` | no | Forms that hold the **same** units in two shapes, with an optional hash-only `map` file. Example: the B2T '25 pkl and HDF5 forms (T15 split audit) |
| `download` | yes | `instructions` (from the original source only), `login_required` |
| `verify` | yes | `files` (a checksum command) and / or `units` (the `tracks verify` command). At least one |
| `prepare` | no | The command that builds a local cache, if the adapter needs one. Never committed output |
| `adapters` | yes for `registered` | Each: `form`, `module` (`fidetype.*`), `call`, `emits`, `transports` (must hold `file`; may hold `lsl`, `ws`) |
| `tracks` | yes | Each: `track` slug + `split_version` (`tracks-vX.Y`) |
| `hub_role` | no | `meg`, `implant`, `emg`, ... (the hub page groups by it) |
| `steward` | yes | Who answers for the entry |

### 3.3 Two levels of verification

| Level | Command | When it is enough |
|---|---|---|
| File checksum | `verify.files` (SHA-256 of the archive) | The source ships one archive or file (B2T '25 pkl, Toronto zip) |
| Unit fingerprints | `verify.units` = `python -m fidetype.benchmark.tracks verify <track> --data <path>` | Always. It is the only check for SpanishBCBL (316 files, no archive) |

A file without a SHA-256 must carry a `note` that says how to check it. Today two forms have no checksum: the B2T '25 HDF5 zip and the SpanishBCBL FIF files (gap 79, P13-07).

## 4. Replay adapter contract

A replay adapter turns **one split unit of a registered form** into **one NeuralTextStream**. The same events then go to a file, to LSL or to WebSocket. The trust layer and the scorer see the same input on every transport.

### 4.1 Pipeline

```
download (original source) -> verify -> [prepare] -> tracks select <track> --split test
  -> adapter(unit.ref) -> NTS stream (JSON Lines file)
       -> file:  fidetype trust --config <policy> stream.jsonl
       -> LSL:   fidetype lsl replay-to-lsl stream.jsonl   + fidetype lsl run ...
       -> WS:    fidetype ws replay-to-ws stream.jsonl      + fidetype ws run ...
  -> decisions -> units.jsonl (+ shuffled, zeros) -> python -m fidetype.benchmark score <track> ...
```

### 4.2 Rules

| Rule | Requirement | Exists today |
|---|---|---|
| RA-1 Input | The adapter input is `LocalUnit.ref` from `tracks.select` (a file plus an index or key). The adapter never needs plain text from the repo | Yes (`select`) |
| RA-2 Output | One NTS stream per unit. It passes NTS Core conformance (`fidetype validate --level core`) | Yes for the three hub adapters |
| RA-3 Licence keys | The header carries `data.licence` and `data.research_only` from the registry entry (FEP-0010, MET-12) | Yes (`_licence_meta` in each adapter) |
| RA-4 Unit key | The header meta carries the track and the unit hash `h` of the split file, not the plain local id. So a stream file says which unit it is without leaking the id | **No** (P13-06) |
| RA-5 Timing | Frame times are neural time from the data (speech duration, bins, key times). LSL and WebSocket replays pace on these times (`speed` 1.0 = real time, 0 = no pacing) | Yes (`replay_to_lsl`, `replay_to_ws`) |
| RA-6 Determinism | Same input bytes + same adapter version = byte-identical stream. Any random step takes a fixed seed in the call | Yes for the three hub adapters (no random step) |
| RA-7 Transport neutrality | File, LSL and WebSocket give the same decisions for the same stream. A test replays one stream over all three and compares the decisions | Partly (LSL and WS round-trip tests); a 3-way test is P13-06 |
| RA-8 Controls | The adapter can make the shuffled and zeros inputs at the **input level** where the form has signals. Else the entry says that the control is a decoder-output stand-in (submission field `controls`) | Partly (P6-06 for T12 and Willett) |
| RA-9 Adapter hash | The result records the adapter id: module name, package version and SHA-256 of the module source | **No** (P13-06) |
| RA-10 No text out | Committed outputs of a replay hold no text from the data. Truth and hypotheses stay local | Yes (scorer cards hold no text) |

### 4.3 What an adapter emits per hub dataset

| Dataset | Form | Emits | Note |
|---|---|---|---|
| `brain-to-text-25` | pkl | Phoneme CTC log-probabilities of the published RNN | A decoder that uses the HDF5 neural features must declare its training partitions (P6-10) |
| `spanishbcbl` | local cache | Character CTC log-probabilities of **your** decoder | The dataset has no published decoder output. The adapter wraps your logits |
| `toronto-semg` | zip | Key-press frames and their CTC character form | The sentence set needs the window cache and the Tatoeba held-out list |

## 5. One-command reruns

Each entry gets a **rerun recipe**: a small JSON block in the result card. It names every versioned input. A future command reads it:

```bash
fidetype hub rerun <entry-id> --data <path>        # P13-06; today: the per-entry run.py of experiments/
```

### 5.1 Rerun recipe fields

| Field | Content |
|---|---|
| `dataset` | `id`, `version`, `revision` of the registry entry |
| `track` | slug + `split_version` + split `digest` |
| `adapter` | module, package version, SHA-256 of the source (RA-9) |
| `decoder` | name, URL, commit or tag, SHA-256 of the weights, `training_data` (dataset + partitions, P6-10) |
| `policy` | trust config id (the frozen config hash of the guard) |
| `scorer` | `SCORER_VERSION`, metric versions (`safe-wpm/0.1`, `fidetype.halluc/0.2`) |
| `command` | The exact command line, with `<path>` placeholders for local data |
| `level` | `rescore`, `replay` or `full` (5.2) |

### 5.2 Rerun levels

| Level | What reruns | Input needed | Who can do it |
|---|---|---|---|
| `rescore` | Scorer only | The submitted outputs + local truth | Anyone with the dataset |
| `replay` | Trust policy + scorer | NTS streams from the adapter + the frozen policy config | Anyone with the dataset |
| `full` | Decoder + trust policy + scorer | Public weights or training code | Anyone with the dataset and the compute |

The board shows the level next to each entry. An entry with no recipe shows `rerun: no`. `rescore`-only entries may rank, with the level shown (decision Q5).

## 6. Versioning rules

Five version numbers exist. Each changes for its own reasons. A result card records all five, and the board compares entries only when the split, scorer and metric versions match.

| Change | Dataset `version` | Entry `revision` | Split version (`tracks-vX.Y`) | Scorer version | Metric version |
|---|---|---|---|---|---|
| Upstream publishes new or changed files | **new** | 1 | **new** if any fingerprint changes; else same | same | same |
| Moved URL, typo, new citation, better download text | same | **+1** | same | same | same |
| Checksum added for a form that had none | same | **+1** | same | same | same |
| New split rule, new unit set, fixed split bug | same | same | **new** | same | same |
| New track on a registered dataset | same | same | **new** (adds a file) | same | same |
| New normaliser, CI rule, rate model, control rule | same | same | same | **new** | same |
| New metric definition (for example safe WPM v0.2) | same | same | same | same | **new** |
| Licence change at the source | **new** (the old version keeps its old licence) | 1 | new only if the data changed | same | same |
| Adapter code change | — | — | — | — | — (the adapter hash in the card changes; RA-6 output must stay byte-identical, else it is a new split version) |

A split file never changes inside a version (tracks v0.2 rule). A `deprecated` dataset version keeps its results on the board, with a note.

## 7. Governance of datasets

### 7.1 Life cycle

| Status | Meaning | Board |
|---|---|---|
| `candidate` | Proposed; under review; may have no adapter yet | Not shown |
| `registered` | Meets every criterion of 7.2 | Shown |
| `deprecated` | A newer version or a better dataset exists | Shown, with a note; no new entries |
| `withdrawn` | The source removed the data, or the consent or licence no longer allows the use | Results hidden from the board; files stay in git history; no new entries |

### 7.2 Criteria for `registered`

1. A public licence that allows research benchmarking. NC and SA terms are allowed; they set `research_only` / `share_alike`.
2. A persistent source (DOI or a stable dataset page) that the hub links to. No re-hosting.
3. The source states that participants consented to public sharing (or the data is from a public competition with the same statement).
4. A way to verify a local copy: a file checksum or split fingerprints.
5. An adapter of our own (Apache-2.0) that meets section 4.
6. A split rule written down, with test data later in time than training data where the data allows (tracks v0.2 practice), and a training-data warning if two forms hold the same units.
7. At least one baseline entry with the required controls.
8. A named steward.

### 7.3 Process

1. Open an issue "Hub dataset proposal" with the facts of 7.2. The entry enters the registry as `candidate`.
2. A pull request adds the registry entry, the adapter, the split file, the docs row and tests.
3. Review: today the founder (GOVERNANCE.md section 1); later two maintainers. The licence and consent check (7.2 items 1 and 3) is a separate review step.
4. Merge sets `registered`. The log and the board show the date.

A dataset is not a spec change, so it needs no FEP. A new **metric** or a new **track type** (for example the intent tracks of P13-04) does need a design note like this one. Datasets from outside people are P13-05 (externally blocked).

## 8. Submission by pull request (outline for P13-03)

```
fork -> add benchmark/submissions/<track>/<entry>/submission.json (+ outputs pointer) -> open PR
  -> CI: check (no data) -> score (needs truth) -> card JSON -> leaderboard rebuild -> review -> merge
```

| Step | Today | Problem to solve in P13-03 |
|---|---|---|
| `check <track> <submission>` | Needs no data. CI can run it now | — |
| `score` | Needs the truth (`--data` or `--truth`). The truth holds the sentences | CI has no data and the repo never holds truth text. Decided (Q2): a private truth store for CC0 / CC BY tracks; a maintainer scores research-only tracks |
| Outputs | `units.jsonl` holds the decoded text (n-best) | Decoded text must not land in git. Decided (Q3): the PR holds only a pointer and a SHA-256 |
| Card | Holds no text | Committed as `benchmark/results/v0.2/<track>__<entry>.json` (as today) |
| Site | `python -m fidetype.benchmark leaderboard` + `node tools/site/build.js` | CI rebuilds and commits or publishes it |

## 9. Guarantee and control reporting (outline for P13-02)

The score card v0.2 already holds the guarantee block (`method`, `alpha`, `delta`, `n_cal`, `scope`, `calibration_split`) and the three control results. P13-02 shows them on every hub row:

| Column | Source | Mark |
|---|---|---|
| Bound | `guarantee.method`, `alpha`, `delta` | `not-certified` if no CRC / LTT |
| Calibration | `n_cal`, `scope`, `calibration_split` | Warn if the calibration items are in a test split |
| Measured wrong-commit [95 % CI] | card | `above-alpha` if the point value is above `alpha` (safe WPM rule) |
| Safe WPM @ alpha | card, with the metric version | Status `certified` / `above-alpha` / `vacuous` / `not-certified` |
| Shuffled, zeros, null-commit | card controls | pass / fail / missing; input-level or stand-in |
| Hallucination (optional) | protocol 0.2 outcomes | null / scrambled / swapped commit counts |
| Training overlap | `decoder.training_data` vs the split (P6-10) | `overlap` mark |
| Rerun | recipe `level` | `rescore` / `replay` / `full` / `no` |
| Licence | registry `research_only` | `RESEARCH ONLY` |

## 10. Questions for the user (all decided 2026-11-18)

The user decided all seven questions on 2026-11-18. The decisions are in the next section.

| # | Question | Our proposal | State |
|---|---|---|---|
| Q1 | Which EMG dataset is the hub EMG track: Toronto sEMG or KT-sEMG? | Toronto: 19 participants, same trials as v0.1, one checksummed archive. KT-sEMG has one typist and its cal split is too small for a certified guard (P6-05). Register KT-sEMG later as a second EMG track | Decided ([Q1](#decisions-2026-11-18)) |
| Q2 | How does CI get the truth to score a pull request without a manual step? | Option A: a private truth store (a GitHub Actions secret or a private repo) only for CC0 and CC BY tracks; research-only tracks scored by a maintainer and marked. Option B: a maintainer scores every PR locally (not "no manual step"). We propose A; it keeps text out of the public repo but is a private copy of truth text, so it needs your decision | Decided ([Q2](#decisions-2026-11-18)) |
| Q3 | Where do the submitted outputs (decoded text) live? | The PR holds only the manifest and a pointer (URL + SHA-256) to the outputs. CI downloads, scores and commits the card. The outputs never enter git | Decided ([Q3](#decisions-2026-11-18)) |
| Q4 | Do research-only tracks share one board with commercial-clean tracks? | Same board, separate section, `RESEARCH ONLY` mark (as today) | Decided ([Q4](#decisions-2026-11-18)) |
| Q5 | May an entry rank with rerun level `rescore` only (no public decoder)? | Yes, but the board shows the level; `full` entries get a mark | Decided ([Q5](#decisions-2026-11-18)) |
| Q6 | Hub site: GitHub Pages of this repo, or a separate repo? | This repo until outside submissions exist (P13-05), so CI and the scorer stay in one place | Decided ([Q6](#decisions-2026-11-18)) |
| Q7 | Steward: who signs the licence and consent review of a new dataset? | The founder now; a second reviewer when one exists (GOVERNANCE.md section 2) | Decided ([Q7](#decisions-2026-11-18)) |

## Decisions (2026-11-18)

The user answered the questions of section 10 on 2026-11-18: "i would like to have a site but the rest you can decide". So Q6 is the user's own choice, and Q1-Q5 and Q7 take our proposals.

| # | Decision | What it changes |
|---|---|---|
| Q1 | **Toronto sEMG** is the hub EMG track. KT-sEMG becomes a second EMG track later (P13-07) | Hub scope v0.1 stays as in section 2 |
| Q2 | **A private truth store** gives CI the truth for the CC0 and CC BY tracks. A **maintainer scores the research-only tracks** locally, and the board marks these entries | The implementation stays tracked under P13-03. The truth store is a private copy of truth text: it never enters this repo, a public artifact or a log |
| Q3 | **Decoded text stays out of git.** The pull request holds only the manifest, a pointer (URL) and the SHA-256 of the outputs. CI downloads, checks the hash, scores and commits only the card | P13-03 builds this flow |
| Q4 | **Research-only tracks go in a separate, marked section** of the same board (`RESEARCH ONLY`) | The leaderboard and the site keep separate sections |
| Q5 | **`rescore`-only entries may rank.** The board shows the rerun level of every entry | P13-02 adds the rerun column (section 9) |
| Q6 | **Yes, a project site**, in this repo. `node tools/site/build.js` builds it from repository files into `_site/` (git-ignored). The manual-only workflow `.github/workflows/pages.yml` deploys it | The site exists locally (P13-08). It is not published. The maintainer publishes it with [publishing-checklist.md](publishing-checklist.md) section G |
| Q7 | **The founder signs the licence and consent review now.** A second reviewer joins when one exists (GOVERNANCE.md section 2) | Section 7.3 step 3 stays as written |

## 11. Follow-up items

| Item | Content |
|---|---|
| P13-02 | Guarantee and control columns (section 9) |
| P13-03 | Submission by pull request (section 8; Q2 and Q3 decided 2026-11-18: private truth store for CC0 / CC BY tracks, maintainer scoring for research-only tracks, outputs outside git) |
| P13-06 (gap 78) | Hub command line `fidetype hub list / info / verify / replay / rerun`, rerun recipe in the card, RA-4 unit key, RA-9 adapter hash, RA-7 3-way transport test |
| P13-07 (gap 79) | Registry entries for B2T '24, Willett handwriting, KT-sEMG and emg2qwerty; checksums for the B2T '25 HDF5 zip and a per-file manifest for SpanishBCBL |
| P6-10 | Training-data declaration and the pkl / HDF5 overlap map (the `same_units.map` of the B2T '25 entry) |
