# M1-15: sentence-context keystroke decoder (planned run)

**Status:** r1, r2, full-r1 and r3 done (2026-11-10). Current results: [results-full-r1-r3.md](results-full-r1-r3.md) (full cache + causal, leakage checks). r1 and r2: [results.md](results.md).

## Question
Does a Transformer over the key embeddings of one sentence lower the CER of the
synchronous keystroke decoder? Brain2Qwerty v1 reports MEG CER 0.67 (Conv) → 0.36
(Conv + Trans) → 0.29 (+ LM) ([v1](../../wiki/sources/brain2qwerty-v1.md), Fig. 2).
Our per-key logistic regression gets greedy CER 0.590 and beam + LM CER 0.531 (M2-10).
The true sentence is never in the n-best (0/209).

## Setting
- Synchronous, oracle key timing from the keyboard log (the v1 setting). This is **not** a real-time device setting.
- One window per key press: −0.2 … +0.3 s, 306 channels, 100 Hz (50 samples).
- Keys that are not a–z or space are dropped (as in M2-10). Labels are the typed keys.
- Data: the same 20 pinned blocks and 11 subject IDs (10 participants) as M1-C and M2-10.

## Model (code: `src/fidetype/decoders/sentence_context.py`)
| step | output |
|---|---|
| spatial 1×1 conv 306 → 128, participant affine layer, 4 dilated residual conv blocks (width 256) | [K, 256, 50] |
| time pooling: 10 bins of 50 ms, linear → key embedding | [K, 192] |
| per-key "conv" head (loss weight 0.3; the v1 "Conv only" ablation) | [K, 27] |
| + sinusoidal key-index position, Transformer encoder (4 layers, 4 heads, FFN 512) | [K, 192] |
| final head | [K, 27] |

- 3.70 M parameters with 10 participants.
- `lookahead_keys: null` = non-causal (v1). Set `0` for the online (causal) variant: the output at key i then uses keys 0..i only.
- Output: CTC-form keystroke streams (key frame, blank frame, …), the same format as M2-10. The beam + char LM and the trust core read them unchanged.

## Planned runs
| run | change | why |
|---|---|---|
| r1 | `config.json` as is (non-causal) | main result |
| r2 | `config-r2.json`: r1 config, `optim.schedule: plateau` (constant LR, halved on a val plateau), stop on the smoothed val CER trend, `epochs` 2000 (no fixed limit), `max_minutes` 300 (active-time safety cap) | r1 was undertrained (9 epochs, PC sleep) |
| r3 | `lookahead_keys: 0` | online variant; cost of causality |
| r4 (optional) | `use_key_intervals: true` | do key intervals help? (timing only, no MEG) |
| r5 (optional) | `train.init_from` = M1-C r4a `best.pt` (only weights with matching names and shapes load) | conv pretraining |

## Controls
`--control` in `infer_sentence.py` decodes each sentence three times:
- **real**: its own MEG windows;
- **shuffled MEG**: the windows of another sentence of the same split (seed-0 derangement), cycled to the same key count;
- **zeros**: all windows zero.

The script reports the paired bootstrap 95% CI (10,000 resamples) of "shuffled CER − real CER". With sentence context the model can learn a text prior. Thus the gap is the evidence that it uses the MEG.

## Metrics
- **CER greedy**: argmax per key, against the target and the typed text.
- **CER beam + LM**: the `RETUNED` CTC prefix beam with the Spanish char 6-gram LM. The LM weight is picked on real val from the `--lm-weights` grid.
- **Per-participant means** (each person counts once: S1/S18 = P01) and per-subject means, with the sentence distribution.
- Key accuracy of the final head and of the per-key conv head (val, during training): the Conv vs Conv + Trans ablation.
- Compare with M2-10 (logistic regression): greedy 0.590, beam + LM 0.531 (test).

## Commands (GPU env; run from the repo root)
```powershell
# train (detached; checkpoints every 5 min; resume with -Resume)
.\experiments\2026-11-09-m1-15-sentence-context\launch.ps1 -Config experiments\2026-11-09-m1-15-sentence-context\config.json -RunName m1-15-sentence-context-r1

# streams + metrics + controls + beam/LM (after training)
C:\venvs\fidetype-rocm\Scripts\python.exe -m fidetype.decoders.infer_sentence --run-dir C:/Users/zhang/bci-data/runs/m1-15-sentence-context-r1 --control --lm C:/Users/zhang/bci-data/lm/spa_tatoeba_6gram_mkn.npz --lm-weights 0.25 0.5 1.0 1.25 2.0
```
Check: `Get-Content C:\Users\zhang\bci-data\runs\m1-15-sentence-context-r1\status.json`.
Stop: `Stop-Process -Id (Get-Content C:\Users\zhang\bci-data\runs\m1-15-sentence-context-r1\pid.txt)`.

### r2 additions (2026-11-10)
- Training keeps Windows awake (`SetThreadExecutionState`, `src/fidetype/utils/power.py`). `max_minutes` counts active compute time only: a gap longer than 5 min between steps is logged as "suspend gap detected" and not counted. The total (`active_s`) is in the checkpoint, so a resume keeps the budget.
- Watch the trend: `Get-Content C:\Users\zhang\bci-data\runs\m1-15-sentence-context-r2\train.log -Wait | Select-String "trend|plateau|finished|suspend"`. Each eval line shows val CER, smoothed val CER, LR, evals since improvement and LR reductions. `status.json` has the same fields.
- Conv-only head CER: `infer_sentence ... --head conv` (outputs in `<streams>/<run_name>_head-conv/`).

## Tests
`tests/test_sentence_context_decoder.py` (CPU, synthetic): shapes, causal mask, padding, tiny overfit, stream export, participant layer, train/resume/infer wiring. `tests/test_power_budget.py`: sleep prevention, active-time budget, plateau schedule, `--head conv`.
