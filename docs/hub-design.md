# Benchmark hub design: versioned dataset registry and replay adapters

Status: **design v0.1** (roadmap item P13-01, 2026-11-18). The user decided the seven open questions on 2026-11-18 ([Decisions](#decisions-2026-11-18)). Code that exists: the registry file and its checker (P13-01), the hub command line and the rerun recipe in every score card (P13-06, 2026-11-18; [section 12](#12-hub-command-line-and-rerun-recipes-p13-06)). Later items: guarantee columns (P13-02), the pull-request flow (P13-03), the replay command and the transport test (P13-10).

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
| `src/fidetype/benchmark/hub/cli.py` | The hub command line (P13-06, [section 12](#12-hub-command-line-and-rerun-recipes-p13-06)) |
| `src/fidetype/benchmark/hub/recipe.py` | Rerun recipes of score cards (P13-06) |
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
| RA-4 Unit key | The header meta carries the track and the unit hash `h` of the split file, not the plain local id. So a stream file says which unit it is without leaking the id | **No** (P13-10) |
| RA-5 Timing | Frame times are neural time from the data (speech duration, bins, key times). LSL and WebSocket replays pace on these times (`speed` 1.0 = real time, 0 = no pacing) | Yes (`replay_to_lsl`, `replay_to_ws`) |
| RA-6 Determinism | Same input bytes + same adapter version = byte-identical stream. Any random step takes a fixed seed in the call | Yes for the three hub adapters (no random step) |
| RA-7 Transport neutrality | File, LSL and WebSocket give the same decisions for the same stream. A test replays one stream over all three and compares the decisions | Partly (LSL and WS round-trip tests); a 3-way test is P13-10 |
| RA-8 Controls | The adapter can make the shuffled and zeros inputs at the **input level** where the form has signals. Else the entry says that the control is a decoder-output stand-in (submission field `controls`) | Partly (P6-06 for T12 and Willett) |
| RA-9 Adapter hash | The result records the adapter id: module name, package version and SHA-256 of the module source | **Yes** (P13-06: the `adapter` block of the rerun recipe) |
| RA-10 No text out | Committed outputs of a replay hold no text from the data. Truth and hypotheses stay local | Yes (scorer cards hold no text) |

### 4.3 What an adapter emits per hub dataset

| Dataset | Form | Emits | Note |
|---|---|---|---|
| `brain-to-text-25` | pkl | Phoneme CTC log-probabilities of the published RNN | A decoder that uses the HDF5 neural features must declare its training partitions (P6-10) |
| `spanishbcbl` | local cache | Character CTC log-probabilities of **your** decoder | The dataset has no published decoder output. The adapter wraps your logits |
| `toronto-semg` | zip | Key-press frames and their CTC character form | The sentence set needs the window cache and the Tatoeba held-out list |

## 5. One-command reruns

Each entry gets a **rerun recipe**: a small JSON block (key `rerun`, schema `fidetype.hub.recipe/0.1`) in the result card. It names every versioned input. Since P13-06 every committed card has one, and the scorer writes one into every new card ([section 12](#12-hub-command-line-and-rerun-recipes-p13-06)):

```bash
fidetype hub recipe benchmark/results/v0.2/<card>.json                     # print the recipe
fidetype hub rerun <card> --submission <dir> --truth <truth.jsonl>          # level rescore: rerun and compare
```

### 5.1 Rerun recipe fields

| Field | Content |
|---|---|
| `dataset` | `id`, `version`, `revision` of the registry entry |
| `track` | slug + `split_version` + split `digest` |
| `adapter` | module, package version, SHA-256 of the source (RA-9) |
| `decoder` | name, URL, commit or tag, SHA-256 of the weights **or** `weights_sha256_reason` (exactly one, P13-11), optional `weights_files` (`<runs>/...` + SHA-256 each), `training_data` (dataset + partitions, P6-10) |
| `policy` | trust config id (the frozen config hash of the guard, `tcfg-` + 16 hex) **or** `config_id_reason` (exactly one, P13-11); `config_id_source` = the committed file that holds it |
| `scorer` | `SCORER_VERSION`, metric versions (`safe-wpm/0.1`, `fidetype.halluc/0.2`) |
| `command` | The exact command line, with `<path>` placeholders for local data |
| `level` | `rescore`, `replay` or `full` (5.2) |
| `steps` (optional) | The full pipeline when one command is not enough: `truth`, `build`, `score` |
| `versions` | `fidetype` package version, benchmark version, Python version |
| `inputs` (optional) | What each local input is and where it comes from. Never a local path |
| `code_ref` (optional) | The git commit that made the card (backfilled cards) |

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

The user decided all seven questions on 2026-11-18 and re-confirmed them on 2026-11-22 ("all recommended"). The decisions are in the next section.

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
| P13-06 (gap 78) | **Done 2026-11-18** ([section 12](#12-hub-command-line-and-rerun-recipes-p13-06)): hub command line `list / show / instructions / verify / check / recipe / rerun`, rerun recipe with the RA-9 adapter hash in every card, the leaderboard shows it |
| P13-10 (gap 82) | The rest of the P13-06 scope: `fidetype hub replay`, RA-4 unit key in the adapter headers, RA-7 3-way transport test, a `replay`-level rerun of one `b2t25-t15` card byte for byte, the dataset fields of `tracks.py` read from the registry |
| P13-11 (gap 83) | **Done 2026-11-19** ([section 12.6](#126-weights-hash-config-id-and-hallucination-recipes-p13-11)): weights SHA-256 and policy `config_id` filled where an artifact exists, else an explicit reason; every hallucination card has a recipe |
| P13-12 (gap 84) | **Done 2026-11-19** ([section 12.7](#127-leaderboard-freshness-check-p13-12)): CI regenerates `benchmark/site/` and fails on a difference; history rows for cards committed together with their pages |
| P13-13 (gap 85) | **Done 2026-11-21** ([section 12.8](#128-frozen-configs-for-the-pre-p5-23-trust-cards-p13-13)): the 30 pre-P5-23 trust cards (CRC / LTT / plug-in) were refit and frozen; all 30 give the same decisions as the card and carry a `config_id` |
| P13-07 (gap 79) | Registry entries for B2T '24, Willett handwriting, KT-sEMG and emg2qwerty; checksums for the B2T '25 HDF5 zip and a per-file manifest for SpanishBCBL |
| P6-10 | Training-data declaration and the pkl / HDF5 overlap map (the `same_units.map` of the B2T '25 entry) |

## 12. Hub command line and rerun recipes (P13-06)

Status: **built** 2026-11-18. Code: `src/fidetype/benchmark/hub/cli.py`, `src/fidetype/benchmark/hub/recipe.py`. Tests: `tests/test_hub_cli.py`.

### 12.1 Commands

Run them as `python -m fidetype.benchmark.hub <command>` or `fidetype hub <command>`. No command puts participant data in git. No command downloads data.

| Command | What it does | Exit code |
|---|---|---|
| `list [--all] [--json]` | One line per dataset version: id, version, revision, status, role, modality, licence, tracks, `RESEARCH ONLY` | 0 |
| `show DATASET [--version V] [--json]` | One entry: source, citation, licence, attribution, forms, files and checksums, verify commands, adapters, tracks | 0 |
| `instructions DATASET [--version V]` | The download and verify steps. It prints the **official source only**. It never downloads, mirrors or re-hosts data (rule 1) | 0 |
| `verify DATASET --data PATH [--form F] [--json]` | Size and SHA-256 of the local files (one file, or the folder that holds them) against the registry. Then it prints the unit-level command (`verify.units`) | 0 = all found files match; 1 = a mismatch; 2 = no registered file found |
| `check [--registry FILE] [--entry FILE]` | Checks the committed registry, another registry file, or one dataset entry (for example from a pull request). Give one option at most | 1 on a problem |
| `recipe CARD [--json]` | Prints the rerun recipe of a score card and checks it | 1 if the recipe is not valid |
| `rerun CARD --submission DIR --truth FILE [--out FILE]` | Level `rescore`: scores the local submission with the recorded scorer settings. Then it compares the new card with CARD, byte for byte, without the `rerun` block | 0 = same card; 1 = different |

With no command, `python -m fidetype.benchmark.hub` checks the committed registry (the P13-01 behaviour). The benchmark CLI (`python -m fidetype.benchmark`) has no `hub` subcommand. The hub is a separate module entry point, and `fidetype hub` calls it.

`verify` reads files in 1 MiB chunks, so a 2.8 GB archive needs little memory. A file pattern (SpanishBCBL: 316 FIF files) shows `not-checkable` until a per-file manifest exists (gap 79, P13-07). A form without a SHA-256 shows `no-checksum`.

### 12.2 Recipe in every card

| Card | Where the recipe comes from | Level |
|---|---|---|
| New v0.2 cards | `fidetype.benchmark.scorecard.score` adds it. `command` = `python -m fidetype.benchmark score <track> <submission> --truth <truth.jsonl> --B <B> --seed <seed>` | `rescore` |
| The 31 committed v0.2 cards | `tools/benchmark/add_rerun_recipes.py` (backfill). Steps `truth`, `build` (the experiment stage that wrote the submission), `score`. `code_ref` = the last commit that changed the card | `rescore` |
| The 21 committed v0.1 cards | The same tool. Steps `truth` (`prepare`), `build` (`tools/benchmark/import_baselines.py`), `controls`, `safe-wpm`. For `committed-aggregate` cards the command rebuilds the card but does not recompute the numbers. `inputs.how` says so | `rescore` |

The split digest of a v0.2 card is the entries digest of its split file (`digest_kind: entries`). A v0.1 split file has no digest, so a v0.1 recipe holds the SHA-256 of the split file with LF line ends (`digest_kind: file-sha256`). A v0.1 card has no `scorer_version` field, so its recipe names the scorer `benchmark-0.1`.

The backfill changed no other field of a card (checked key by key). The adapter hash (RA-9) is the SHA-256 of the adapter module source with LF line ends. So Windows and Linux checkouts give the same hash. A card whose dataset is not yet in the registry (`b2t24-t12`, `willett-hw`, `kt-semg`, `emg2qwerty`) has `dataset: null` and a `dataset_note` (gap 79).

The checker (`check_recipe`) refuses a recipe without the required fields, with an unknown level, or with a local path in a command. Local paths are `<placeholders>`: `<data>`, `<derived>`, `<submission>`, `<truth.jsonl>`.

Example (`benchmark/results/v0.2/b2t25-t15__published__ltt.json`, shortened):

```json
"rerun": {
 "schema": "fidetype.hub.recipe/0.1",
 "level": "rescore",
 "dataset": {"id": "brain-to-text-25", "version": "dryad-2025-07-03", "revision": 1},
 "track": {"track": "b2t25-t15", "split_version": "tracks-v0.2", "digest": "1120f8195e50...b1ceeb"},
 "adapter": {"module": "fidetype.adapters.b2t25", "package_version": "0.0.1", "sha256": "44c9ae95fa2f...569128"},
 "policy": {"name": "trust gate + LTT", "config_id": null, "guarantee": "ltt"},
 "scorer": {"scorer_version": "0.2", "metrics": {"safe_wpm": "safe-wpm/0.1"}, "B": 2000, "seed": 0},
 "command": "python -m fidetype.benchmark score b2t25-t15 <derived>/p6-02b-v02-entries/submissions/b2t25-t15__published__ltt --truth <derived>/p6-02b-v02-entries/truth/b2t25-t15.jsonl --B 2000 --seed 0 --out benchmark/results/v0.2/b2t25-t15__published__ltt.json",
 "steps": [{"step": "truth"}, {"step": "build", "command": "python -I experiments/2026-11-17-p6-02b-v02-entries/run.py b2t"}, {"step": "score"}],
 "code_ref": "git b9fa645 (last commit that changed this card before P13-06)"
}
```

### 12.3 Leaderboard

The leaderboard (`python -m fidetype.benchmark leaderboard`) has a `Rerun` column with the level (`rescore`, `replay`, `full` or `no`). Below each track table, a "Rerun recipes" block lists the facts and the commands of every entry. `leaderboard.json` holds the full recipe of each row. The project site (`node tools/site/build.js`) shows the same page.

### 12.4 Checked reruns

On 2026-11-18, `fidetype hub rerun` gave the same card (byte for byte, without the `rerun` block) for three committed cards from the local submissions: `b2t25-t15__published__ltt`, `b2t24-t12__t12v2__guard` and `toronto-semg__cnn-calib__crc`. This is level `rescore`. A `replay`-level rerun (adapter, trust policy and scorer) is P13-10.

### 12.5 Not done here

| Item | Gap |
|---|---|
| `fidetype hub replay`; RA-4 unit key in the adapter headers; RA-7 3-way transport test; a `replay`-level rerun of one `b2t25-t15` card; `tracks.py` dataset fields read from the registry | 82 = P13-10 |
| The decoder weights SHA-256 and the frozen policy `config_id` in the recipes; recipes for the hallucination cards | 83 = P13-11 (done 2026-11-19, section 12.6) |
| An outputs pointer (URL + SHA-256), so outside people can rescore | P13-03 |

### 12.6 Weights hash, config id and hallucination recipes (P13-11)

A recipe now holds a value **or** a reason for two fields, never a bare null. `check_recipe` accepts exactly one of the two.

| Field | Value | Reason (when no value exists) |
|---|---|---|
| `decoder.weights_sha256` | SHA-256 of the local weights file (one file), or of the sorted `sha256sum` manifest of `weights_files` (several files, `weights_sha256_kind`) | `weights_sha256_reason` |
| `policy.config_id` | `tcfg-` + 16 hex, from the committed guard file (its id is recomputed from the content) or the logged id; `config_id_source` names the file | `config_id_reason` |

The weights stay outside the repository. `tools/benchmark/add_rerun_recipes.py --fill` records their SHA-256 (hashed read only on 2026-11-19); `--runs <runs>` hashes them again and stops on a difference. Cross-checks: the T12 v2 pre-registration and logprobs meta, and the `checkpoint_sha256` of the M4-12 / M4-13 decode records.

| 52 leaderboard cards | Value | Reason |
|---|---|---|
| Weights SHA-256 | 30 (ConvCTC-M async, Toronto CNN calib / xsession / xsubject, T12 v2, M4-12, M4-13) | 22: no trained part (8, phoneme beam over the published logits), not released by the authors (10, Card et al. 2024 and Willett et al. 2021), LDA fitted in memory by the build step (4) |
| Policy `config_id` | 6 (every drop-in guard card) | 46: always-commit has no trust config (16); the TrustPipeline was fitted in memory and not frozen (30, gap 85 = P13-13; filled on 2026-11-21, section 12.8) |

Hallucination cards (`benchmark/results/halluc-v0.*/*.card.json`, 32 cards): every card has a recipe at level `rescore`. The command `python -m fidetype.benchmark.hallucination rescore <outcomes> --protocol <p> --alpha-wrong <a> --alpha-fluent <b> --check <card>` uses committed files only, and all 32 commands reproduce their card. `--check` leaves out the `rerun` block, accepts the `meta.outcomes_file` pointer of the protocol 0.2 cards, and compares floats with a relative tolerance of 1e-9 (the Clopper-Pearson bisection gives other last bits on Linux). All 32 carry the guard `config_id` and the decoder weights SHA-256 (T12 v2, M4-12 fixed0 or M4-13 long0). The track block names the split file `splits/halluc-v0.1/<dataset>.json` (split version `halluc-v0.1`, file SHA-256). Tests: `tests/test_hub_cli.py`.

### 12.7 Leaderboard freshness check (P13-12)

A page cannot name the commit that holds it: the hash exists only after the commit. So the entry history of the leaderboard pages is read up to the **parent of the commit that holds the pages** (the newest commit that changed `benchmark/site/`). Card changes in that commit get a row "this commit / with this page". The rows are fixed for a committed page set.

| Step | What happens |
|---|---|
| `python -m fidetype.benchmark leaderboard ...` (build) | Try base = the parent of the newest commit that changed the output folder. If the result equals the committed pages, nothing changes. Else the pages go into a new commit on top of `HEAD`, so build with base = `HEAD` |
| Commit | Commit the pages together with the cards, or in a later commit. Commit them directly on top of the `HEAD` that you built on |
| CI job `leaderboard` | `actions/checkout` with `fetch-depth: 0`, then `python -m fidetype.benchmark.leaderboard --check`: regenerate with base = the parent of the commit that holds the pages, and fail on any difference. `all-green` needs this job |

If the check fails, run the build command again and commit `benchmark/site/`. Without git history (a shallow clone) the check fails with a message; the other CI jobs keep the shallow checkout, and there the full-history tests skip. Tests: `tests/test_leaderboard_track_pages.py`.

### 12.8 Frozen configs for the pre-P5-23 trust cards (P13-13)

Status: **done** 2026-11-21. Results: [experiments/2026-11-21-p13-13-refreeze-cards](../experiments/2026-11-21-p13-13-refreeze-cards/results.md).

The 30 trust cards of `b2t25-t15`, `b2t25-t15-copytask`, `spanishbcbl-meg`, `spanishbcbl-meg-async`, `toronto-semg` and `toronto-semg-composed` (plug-in, CRC and LTT policies) were made before the frozen `config_id`. Their build steps fitted a TrustPipeline in memory. P13-13 refit each pipeline with the build-step settings and froze it with `FrozenTrustConfig.from_pipeline`. A new pipeline built from the loaded file gives the same decisions as every card (real input and both controls). Each v0.1 card and its v0.2 card share one config (15 configs).

| Field | Value |
|---|---|
| `policy.config_id` | `tcfg-` + 16 hex of the frozen config |
| `policy.config_id_source` | `experiments/2026-11-21-p13-13-refreeze-cards/results/configs/<name>.json`: `config_id`, `cards` (the `v0.x/<stem>` cards it backs) and `config` (numbers and settings only) |
| `rerun.amended` | adds the P13-13 note |

CRC and LTT cards of `b2t25-t15` and `spanishbcbl-meg`: the threshold was chosen outside the pipeline fit (M2-13), so the config holds `commit_p` = the CRC or LTT lambda and a `risk_control` record with `combine: replace`. `toronto-semg` CRC cards: CRC is inside the fit (`combine: max`).

Tool: `tools/benchmark/add_rerun_recipes.py --refrozen --write` writes the ids; it recomputes each id from the file and writes a card only when `results.json` says "decisions equal". A card whose refit does not reproduce keeps a reason that starts with "refit does not reproduce the card". `--fill` reads the same files.

Check (future cards): `fidetype.benchmark.hub.recipe.config_id_problems(card, root, card_key)`. A trust card (any policy other than always-commit) needs a `config_id`, or a reason from `TRUST_CARD_REASONS` (a new submission that names no config, or a failed refit). A `config_id` needs a committed `config_id_source`; if that file holds the frozen `config`, its recomputed id must be equal, and if it lists `cards`, the card must be in the list. `tests/test_hub_cli.py` runs it on every committed card (CI) and on synthetic cards.
