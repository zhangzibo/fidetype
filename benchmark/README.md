# Fidetype open benchmark v0.1

This benchmark scores neural text entry from **NeuralTextStream (NTS) files**. The scorer does not need your decoder code. The benchmark ships **no data and no weights**. You download every dataset from its original source.

- Leaderboard (generated): [`site/index.html`](site/index.html), [`site/leaderboard.md`](site/leaderboard.md)
- Results (one JSON file per entry): [`results/v0.1/`](results/v0.1/)
- Code: [`src/fidetype/benchmark/`](../src/fidetype/benchmark/)
- Concept page: [`wiki/concepts/open-benchmark.md`](../wiki/concepts/open-benchmark.md)
- Data licences: [`LICENSES/DATA.md`](../LICENSES/DATA.md)

## Tracks

| Track | Data | Licence | Scored split | CI unit |
|---|---|---|---|---|
| `spanishbcbl-meg-async` | SpanishBCBL typing MEG | CC BY-NC 4.0 (**research only**) | test: 637 trials, 17 sentences, 19 participants | sentence x participant (two-way) |
| `b2t25-t15-copytask` | Brain-to-Text '25, T15 copy task | CC0 1.0 | test: 816 trials, 14 days | day |
| `toronto-semg-composed` | Toronto forearm sEMG | CC BY 4.0 | test: 551 composed sentences, 19 participants | participant |

`python -m fidetype.benchmark info <track>` prints the source URL, version, checksum and download steps.

## How to submit

1. **Download the data** from the source in `info <track>`. Do not ask us for a copy: we do not redistribute it.
2. **Rebuild the truth** locally and check it against the committed split:
   ```bash
   python -m fidetype.benchmark prepare b2t25-t15-copytask --data t15_copyTask.pkl --out truth.jsonl
   ```
   The command stops if your data do not match the split hashes. Keep `truth.jsonl` local. Never commit it.
3. **Run your decoder** on the trials of the scored split (`test`). Train only on the open splits (`train`, `val`, `cal`; see the split file).
4. **Write one NTS stream per trial** to `streams/<trial id>.jsonl` (or `.npz`). Add one final `hypothesis` event:
   - `nbest[0].text` is your output text; more n-best items are the OFFER candidates.
   - `"fidetype.action"`: `"commit"`, `"offer"` or `"abstain"` (default `"commit"`). `"fidetype.offer_k"` caps the shown candidates (default 3).
   - Helper: `fidetype.benchmark.submission.write_trial(path, stream, texts, scores, action=...)`.
   - A stream with frames only is scored as "always commit the CTC greedy text".
5. **Run the controls**: the same decoder on time-shuffled input (`controls/shuffled/`) and on all-zero input (`controls/zeros/`). Without them, the entry shows "controls: no".
6. **Write `submission.json`** (schema `fidetype.benchmark.submission/0.1`): `track`, `decoder` (`name`, `version`, `url`, **`weights_licence`**, `training_data`, `training_regime`), `policy`, `guarantee` (`method`: `none`, `crc`, `ltt` or `aci`; `alpha`, `delta` for LTT, `n_cal`, `scope`, `calibration_split`), `submitter`.
7. **Check and score**:
   ```bash
   python -m fidetype.benchmark check my-submission --truth truth.jsonl
   python -m fidetype.benchmark score my-submission --truth truth.jsonl --out result.json
   ```
   Entry gate: every stream must reach the conformance level **trust-ready** (`python -m fidetype.conformance`).
8. **Open a pull request** that adds `benchmark/results/v0.1/<your entry>.json` and a link to your stream files (host them yourself; do not put them in this repository). A maintainer reruns the score command. Scoring in CI is planned for roadmap phase P13.

Reference submission: `tools/benchmark/make_b2t25_published.py` builds a full stream submission for the B2T '25 track from the published decoder output. It scores with one command.

## Rules

- No truth text, labels or anything derived from them in a stream (NTS spec 5.3). The scorer checks the headers.
- Report every eWPM next to the no-BCI reference (gaze typing). The board does this for you.
- State the licence of your weights. Weights trained on CC BY-NC data are research-only.
- Do not upload raw or participant data anywhere in this repository.

## What the metrics mean

| Column | Definition |
|---|---|
| CER | Character edit distance of the top-1 text / truth length, pooled over trials |
| eWPM [95% CI] | Effective words per minute with the documented simulated user (`aac-gaze-v1`, word model); a sentence counts only if it ends exactly right |
| Wrong-commit | Wrong commits / all trials (the marginal rate that CRC and LTT control) |
| Error among commits | Wrong commits / commits |
| Commit rate | Commits / all trials |
| Controls | Shuffled and zeros input give a higher CER (paired CI above 0), and the zeros input commits on at most 5% of trials |
| Guarantee | The declared CRC / LTT bound (alpha, delta, n_cal) and the measured test wrong-commit rate |
| Conformance | The weakest NTS conformance level over the stream files |
| Scored from | `stream-submission` (scored end to end), `committed-per-trial` or `committed-aggregate` (our baselines, scored from committed experiment results) |

## Rebuild the board

```bash
python -m fidetype.benchmark leaderboard --results benchmark/results/v0.1 --out benchmark/site
```

Never edit `site/` by hand. The folder can be served as a static site (GitHub Pages) later.
