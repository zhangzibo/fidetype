---
title: P14-01 pretrained decoders - model-card metrics rerun with the packaged runtimes
type: experiment
task: P14-01
updated: 2026-11-19
---

# P14-01: model-card metrics, rerun with `fidetype.pretrained`

Code: [run.py](run.py). Numbers: `results/results.json`; log: `results/run.log`. Per-trial records (decoded text, truth): `C:\Users\zhang\bci-data\derived\p14-01-pretrained\` only (R-24). CPU only (background class, 4 threads), no GPU.

Each stage loads the model with `fidetype.pretrained.load` (release files from the local cache, SHA-256 and size checked), decodes the **public data files** with `decode_file` (NumPy runtimes, no PyTorch) and recomputes the metric of the model card.

## Outcome: every model-card metric reproduces

| Model | Set | Rerun | Model card | Log-probs vs the training run (PyTorch) | NTS `provenance` | Time |
|---|---|---|---|---|---|---|
| `t15-m4-13` | val_eval, 701 trials (B2T '25 `data_val.hdf5`, odd trials) | greedy PER **0.1210** (2,392 / 19,765) | 0.1210 (2,392 / 19,765) | max abs diff 6.9e-5 | 701 / 701 | 416 s (incl. guard) |
| `t15-m4-13` + `guard()` | same | 104 commits, 17 wrong; actions and texts equal to P14-05 on **701 / 701** | P14-05: 104 commits, 17 wrong (`tcfg-1016759f08a3f9a1`) | — | — | (same) |
| `t12-v2` | test blocks of the 10 test sessions, 400 trials (B2T '24 `.mat`, rolling normalisation) | greedy PER **0.2695** (2,641 / 9,800) | 0.269 | max abs diff 1.3e-3 | 400 / 400 | 140 s |
| `emg2qwerty-p11-01` (generic, research only, opt-in) | 16 generic-test sessions, 2,445 prompts | prompt CER **0.5831** (41,598 / 71,342) | prompt CER 0.5832 | — (not stored) | 2,445 / 2,445 | 967 s |
| `kt-semg-lda` | run28, 22 typing bursts | key accuracy **0.242** (786 keys; majority class 0.137); guard 22 offers, 0 commits | 0.248 (799 keys); 22 offers, 0 commits | — | 22 / 22 | 27 s |

- The NumPy runtimes equal the PyTorch modules: on random input, CRT (P11-01) max abs diff 3.8e-5, T12 GRU 1.2e-5 (scratch check against the training code on CPU). The diffs in the table are against the stored GPU outputs.
- KT-sEMG: the small difference (0.242 vs 0.248, about half a binomial standard error) comes from the timing path. P14-04 measured through the live LSL loop (799 keys); `decode_file` uses the key log directly and keeps the keys of the kept bursts (786 keys). Over all 808 keys of the run the file path gives 0.244. The guard behaviour is the same.
- emg2qwerty: the session-level CER of the card (0.5375) needs whole-session decoding; the package decodes prompts, so the rerun checks the prompt CER.

## Limits

- Offline replay on the same machine that trained the models. The clean-machine test from the README (done criterion of P14-01) needs hosted weights (P14-02): open gap 98 (P14-30).
- One draw each; the numbers are reproductions, not new results.
