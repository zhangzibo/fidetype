# R4 item 6: published-gate bonus sensitivity and "published stream alone"

Review: editor M2. Tables: [results/tables.md](results/tables.md). Data: [results/bonus.json](results/bonus.json).

## Where the +2.0 came from
- `Decoders.published_plus_fn` (`experiments/2026-11-10-b2t25-trust/run.py`) puts the published sentence on top of our phoneme-to-word n-best with score = our best score + `published_margin`, and gives each published word the acoustic confidence of the aligned word in our top-1.
- `published_margin: 2.0` is in `experiments/2026-11-10-b2t25-trust/config.json`. It came in with the first commit of that experiment (3fb8154, 2026-11-10, M6-06) and never changed (`git log -S published_margin`: one commit). No grid, tuning stage or selection record exists in the code, the results or the wiki. It was set by hand, not tuned on test or fit data.

## Results (guard on; fixed test set, 816 trials; unified day-cluster CIs)

| margin | full-fit plug-in: wrong-commit [CI], commit, eWPM | split A LTT max | split B LTT max | repeated (R 50) LTT max: mean, > α, commit |
|---|---|---|---|---|
| 0 | 0.0233 [0.013, 0.037], 0.350, 17.46 | 0.0245, 0.373 | 0.0233, 0.349 | 0.0224, 0/50, 0.338 |
| 0.5 | 0.0453 [0.028, 0.069], 0.473, 18.77 | 0.0233, 0.333 | 0.0221, 0.332 | 0.0277, 1/50, 0.379 |
| 1 | 0.0319 [0.019, 0.046], 0.409, 18.66 | 0.0221, 0.331 | 0.0319, 0.409 | 0.0292, 1/50, 0.388 |
| **2 (paper)** | 0.0441 [0.027, 0.068], 0.473, 18.77 | 0.0294, 0.403 | 0.0306, 0.415 | 0.0307, 1/50, 0.392 |
| 4 | 0.0466 [0.028, 0.070], 0.484, 18.78 | 0.0392, 0.468 | 0.0306, 0.402 | 0.0328, 1/50, 0.401 |
| published alone | 0 commits (= always offer), 18.11 | 0 commits | 0 commits | — |

- Margin 2 reproduces the paper (Tab. 1: 0.044 / 0.47; 0.029 / 0.031; R3 Tab. 2 0.031).
- From 0.5 to 4, the main rows move little: LTT max 0.022-0.039 on the fixed splits, 0.028-0.033 over splits; eWPM 18.55-18.78. Plug-in and CRC max exceed α more often as the margin grows (plug-in > α in 20 % → 32 % of splits).
- Margin 0 differs in kind: the published sentence then ties with our top candidate; the layer commits less (0.35) and is 1.3 eWPM slower (17.46 vs 18.77), but its wrong-commit rate is lower (0.023).
- Joint LTT β = 0.10: 0 commits on both fixed splits at every margin; 4-7 % commits over splits.

## "Published stream alone"
`Decoders.published_fn` gives one candidate (the published sentence, score 0, no character confidences). The pickle holds the published sentence but no scores or logits of the published decoder, so no confidence independent of our decoder exists. The layer then has no signal to rank trials: the fitted policy never commits (commit threshold 1.01), and every rule equals always offer (18.11 eWPM). So every published-gate result in the paper depends on agreement with our decoder; the gate is a two-decoder agreement signal, not a stream-only confidence of the published decoder.
