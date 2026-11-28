# Data, weights and third-party code: licence note

The Fidetype code is Apache-2.0 ([`LICENSE`](../LICENSE)). This note says what the repository does **not** contain, and the terms of the data that our experiments and the benchmark use. Audit date: 2026-11-11 (task M5-03).

## Rules

1. The repository ships **no dataset files, no raw recordings, no participant data and no trained weights**. Trained weights of our clean models may be published only as separate GitHub release assets, never in the repository or the wheel (user decisions D10 and D11, 2026-11-22; licences: CC0-1.0 for `t15-m4-13`, `t12-v2`, `willett-hw`; CC-BY-4.0 for `kt-semg-lda`). Research-only weights (`emg2qwerty-p11-01`) are never hosted (D12). No weights are released yet: the upload waits for a final user yes (roadmap P14-02).
2. Every dataset is **download-only**: the user fetches it from the original source. No loader mirrors, vendors or redistributes data.
3. No third-party code under a non-commercial or copyleft licence is copied into `src/`. Third-party repositories live only in the git-ignored `references/repos/`.
4. Anything derived from non-commercial data (caches, streams, weights, results) is for **non-commercial research only**.

## Datasets

| Dataset | Licence | Commercial use | How Fidetype uses it | Loader / adapter |
|---|---|---|---|---|
| SpanishBCBL MEG (Brain2Qwerty v1/v2 data) | CC BY-NC 4.0 | **No** | Research and the `spanishbcbl-meg-async` benchmark track (marked research only) | `src/fidetype/data/spanishbcbl.py` (reads a local copy; `LICENCE`, `SOURCE_URL`, `licence_notice()`), `src/fidetype/adapters/spanishbcbl_meg.py` (streams carry `data.licence` = `CC-BY-NC-4.0` and `data.research_only` = `true`, FEP-0010) |
| Brain-to-Text '25 (Card et al. 2024) | CC0 1.0 | Yes | Benchmark track `b2t25-t15-copytask` | `src/fidetype/adapters/b2t25.py` (safe unpickler, Dryad SHA-256 check) |
| Toronto sEMG typing (Achituve et al. 2025) | CC BY 4.0 (attribution) | Yes | Benchmark track `toronto-semg-composed` | `src/fidetype/adapters/toronto_semg.py` |
| Tatoeba (en, es) | CC BY 2.0 FR (attribution) | Yes | Char and word LMs; held-out sentences of the EMG track | `src/fidetype/lm/corpora.md` |
| CMUdict | BSD-2-Clause style | Yes | Pronunciation lexicon (B2T word decoder) | `src/fidetype/lm/phoneme_words.py` |
| emg2qwerty (Meta) | CC BY-NC-SA 4.0 (repo `LICENSE` file; the README says CC BY-NC 4.0; we follow the stricter one) | **No** | Research only: replay streams and a session-calibrated LDA baseline (P4-01). Download-only; derived streams, weights and results stay outside the repository and keep the share-alike terms. Only aggregate numbers are committed | `src/fidetype/adapters/emg2qwerty.py` (read-only h5py, extra `[emg2qwerty]`; streams carry `fidetype.replay.licence` and `research_only`) |
| LibriBrain | CC BY-NC 4.0 | **No** | Not used | none |

Attribution: "Sentences from Tatoeba (https://tatoeba.org), by the Tatoeba contributors, CC BY 2.0 FR." Toronto sEMG: Achituve, Beutel, Eby, Fetaya, Koivisto, Zariffa, Sci Data 12:440 (2025), doi:10.5683/SP3/KV65VI, CC BY 4.0.

## Third-party code

| Code | Licence | Status in this repository |
|---|---|---|
| Meta Brain2Qwerty (`facebookresearch/brain2qwerty`) | CC BY-NC 4.0 | Not vendored. Read only to learn the dataset quirks. A line-by-line scan on 2026-11-11 found no shared lines of 45+ characters between `src/` and the clone, except 7 generic signatures (`def forward(self, x: torch.Tensor) -> torch.Tensor:`, `def main(argv: ...)`) |
| `Neuroprosthetics-Lab/nejm-brain-to-text` | no licence | Not copied. Values read for timing only |
| `ANSLab-UHN/sEMG-TypingDatabase` | CC BY-SA 4.0 | Not copied |
| draw.io viewer (`tools/drawio/viewer-static.min.js`) | Apache-2.0 | Vendored with its licence (`tools/drawio/LICENSE`) |
| Site fonts Inter, Space Grotesk, JetBrains Mono (`tools/site/assets/fonts/`, Latin WOFF2 subsets from Fontsource 5.1.0) | SIL OFL 1.1 | Vendored with their licence ([`OFL-1.1-fonts.txt`](OFL-1.1-fonts.txt)). The site build copies the licence next to the fonts. The site loads no fonts from other servers |

## Weights

No weights are in the repository or in any release. The benchmark asks every entry to state the licence of its weights. Our own baselines:

| Decoder | Trained on | Weights status |
|---|---|---|
| ConvCTC-M async (MEG) | SpanishBCBL (CC BY-NC 4.0) | Not released. Research only, even if released later |
| Phoneme -> word decoder (B2T) | nothing (decoding only) | No trained weights |
| Key-press CNN (EMG) | Toronto sEMG (CC BY 4.0) | Not released |
| LDA key baseline (EMG) | emg2qwerty, per session (CC BY-NC-SA 4.0) | Not released. Research only; local files in `~/bci-data/derived/p4-01-emg2qwerty/` |

## Committed results that quote non-commercial data (judgement call)

Some committed experiment results contain short texts from SpanishBCBL. A check on 2026-11-11 found no other committed file with per-participant typed text; the rest hold only a few target (stimulus) sentences as examples. CC BY-NC 4.0 allows non-commercial sharing with attribution, so this is not a licence breach. But these files are **not** covered by Apache-2.0 as data; they keep the CC BY-NC 4.0 terms of the source:

- `experiments/2026-11-08-m2-real-keystroke/results/trials.json`: per-trial target **and typed** texts plus key labels of 20 test blocks. This is per-participant behavioural data. **Removed from the tip of the tree on 2026-11-11** (task M5-12). The file now lives outside the repository, at `~/bci-data/derived/2026-11-08-m2-real-keystroke/trials.json`. `run.py` reads and writes it there; the environment variable `FIDETYPE_DERIVED` overrides the root. A `.gitignore` rule (`experiments/**/results/trials.json`) blocks it from coming back. **History note:** we did not rewrite git history. Older commits (first added in `074c3b0`, 2026-11-08) still contain the file.
- Example sentences in `results.md` files and in `examples` fields of `experiments/2026-11-11-g1-async-meg-trust/results/harness-async.json` (a few target sentences each).
- **Example decoded texts (R-23 audit, decision R-24 on 2026-11-15).** Nine committed result files hold example pairs of a stimulus (target) sentence and the decoder's top-1 text. They are model outputs on public datasets, not typed text. They stay in the tree. Each file keeps the licence of its source dataset:

  | File | Pairs | Source data |
  |---|---|---|
  | `experiments/2026-11-08-m1c2-beam-lm/results/results.json` | 30 | SpanishBCBL MEG (CC BY-NC 4.0) |
  | `experiments/2026-11-11-m1-09-async-full/results/beam-m1-09-r4b-full/results.json` | 30 | SpanishBCBL MEG (CC BY-NC 4.0) |
  | `experiments/2026-11-11-m1-09-async-full/results/beam-m1-09-r4b-full-medium/results.json` | 30 | SpanishBCBL MEG (CC BY-NC 4.0) |
  | `experiments/2026-11-11-m1-09-async-full/results/beam-m1-09-r5-medium/results.json` | 30 | SpanishBCBL MEG (CC BY-NC 4.0) |
  | `experiments/2026-11-12-paper1-r1-analyses/gpu-seeds/results/beam-m1-09-r4b-full-medium-s1/results.json` | 30 | SpanishBCBL MEG (CC BY-NC 4.0) |
  | `experiments/2026-11-12-paper1-r1-analyses/gpu-seeds/results/beam-m1-09-r4b-full-medium-s2/results.json` | 30 | SpanishBCBL MEG (CC BY-NC 4.0) |
  | `experiments/2026-11-08-m2-real-keystroke/results/lm.json` | 180 (15 configurations x the same 12 sentences) | SpanishBCBL MEG (CC BY-NC 4.0) |
  | `experiments/2026-11-08-m2-real-keystroke/results/run1-uncalibrated-b/lm.json` | 96 | SpanishBCBL MEG (CC BY-NC 4.0) |
  | `experiments/2026-11-11-emg-toronto/results/trust.json` | 36 | Toronto sEMG (CC BY 4.0) |

## Rule for new experiments (R-24, 2026-11-15)

New experiments must **not** commit per-trial decoded text or stimulus text. Write per-trial outputs to `~/bci-data/derived/<experiment>/` (or the root that `FIDETYPE_DERIVED` names). Commit only `plan.md`, `results.md` and **aggregate numbers** (rates, counts, intervals). The nine files above are the last exceptions. The same rule is in [CONTRIBUTING.md](../CONTRIBUTING.md) and in the [repository hygiene checklist](../wiki/questions/repo-hygiene.md).

The benchmark split files (`src/fidetype/benchmark/splits/v0.1/`) hold only trial ids, cluster labels and SHA-256 hashes of the truth texts. No text.
