---
title: P14-48 willett-hw with the same-LM readout and a no-signal gate - pre-registration
type: experiment
task: P14-48
updated: 2026-11-20
---

# P14-48: `willett-hw` with the same-LM readout and a no-signal gate (pre-registration)

We wrote and committed this plan **before** any result of the packaged LM readout, the gate or the new guard on real data (val or test). Gap 144 of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P14-48](../../wiki/questions/roadmap-standard.md#p14-48-willett-hw-with-the-same-lm-readout-and-a-no-signal-gate). Follow-up of [P15-25](../2026-11-20-p15-25-e1-same-lm/results.md) (decoder F), [P14-41](../2026-11-20-p14-41-willett-guard/results.md) (the guard) and [P11-12](../2026-11-20-p11-12-emg-nosignal-gate/results.md) (the gate pattern). It feeds gap 138 (P14-47) and gap 136 (P5-31).

Data: Willett handwriting 2021 (T5), CC0 1.0. LM text: Tatoeba English sentences, CC BY 2.0 FR (attribution: the Tatoeba contributors). CPU only (isolation runner, class `background`, 4 threads); no GPU. Per-sentence records (decoded text, truth, decisions), log-probs and the guard file stay in `C:\Users\zhang\bci-data\derived\p14-48\`. The repo gets aggregates only. No weights and no LM file in git.

## 1. Done criterion (from the roadmap text)
Roadmap P14-48, "Done when": *`willett-hw` offers the F readout with a no-signal gate (null controls pass), the card states the LM licence (CC BY 2.0 FR, attribution) and the test overlap, and the P14-41 guard is re-calibrated on the new readout with its numbers reported.*

We read it as three parts. **Gap 144 closes only if all three hold:**
- **D1** the package has the F readout as an opt-in readout with the gate (`load("willett-hw")`, NumPy core), and the readout null controls **N1 and N2 pass** (section 6);
- **D2** the manifest card states the LM licence (CC BY 2.0 FR, attribution) and the test overlap (13 of 80 test sentences, 5 of 47 unique texts, are in the Tatoeba English export: P15-25);
- **D3** the guard is re-calibrated on the gated F readout and its numbers are reported (V1-V8). A guard that is **not certified** still meets D3: the roadmap asks for the numbers, not for a certified guard. A certified, non-vacuous guard stays gap 138 (P14-47).

If N1 or N2 fails, gap 144 stays open with the numbers, and the failing control becomes a new gap.

## 2. What is known before the run (from earlier work, not from this run)
| Fact | Source |
|---|---|
| F on the GPU log-probs of R-ball-s0 (the `willett-hw` checkpoint): test CER **0.1734**; greedy 0.3051 | P15-25 `summary.json` |
| The NumPy runtime of `willett-hw` gives greedy test CER 0.3051 (equal to the GPU run) | P14-33 |
| F on uniform log-probs, 4,100 frames: 4,100 tokens (one per frame); on all-blank frames: 0 tokens | P15-25 `lmonly` |
| The P14-41 guard: 106 val sentences -> 26 fit + 40 policy-grid + **40 LTT** items; LTT at alpha 0.05, delta 0.1 needs >= 45 items | P14-41 |

**Prediction:** the guard is returned but **not certified** (the 40 < 45 LTT limit does not depend on the decoder), it never commits, and safe WPM v0.1 is vacuous (0.00). A better readout cannot change this on the 106-sentence val split.

## 3. Readout F (fixed; equal to P15-25)
- Search: the P11-07 decoder `LMBeam` (CTC prefix beam search with shallow character-LM fusion over the 98 P11-01 key tokens). Our own code (Apache-2.0). We copy it **unchanged in method** into the package as `fidetype.pretrained.lmreadout` (NumPy only). A test checks that the packaged copy gives the same tokens and scores as `experiments/2026-11-20-p11-07-emg-beam-lm/lmbeam.py` on random inputs.
- LM: `eng_tatoeba_6gram_mkn_noE2Q.npz` (P11-11 build: Tatoeba English, 6-gram MKN, emg2qwerty prompts removed), SHA-256 `7c4f133c1eb5b46d67d185eb61b6ec282b009b652112591274c3c865757a06b8`, 3,348,165 bytes.
- Settings: `lm_weight` w = 0.5, `bonus` beta = 1.0, `lam` = 0 (no lexicon), `beam` = 8, `prune_logp` = -8.0, end terms on (`nbest(eos=True)`). Text = the top-1 tokens as characters (P15-25 rule).
- Input: the log-probs (T, 98) of `load("willett-hw").decode(...)`, float64.
- No other weight, beam or LM is tried (no selection).

## 4. No-signal gate (fixed; the P11-12 design)
For a log-prob matrix `x` (T frames, 10 ms):
- `n_keys(x)` = the number of greedy CTC emissions (per-frame argmax, runs of the same index joined, blank removed);
- `kps(x)` = `n_keys / (0.01 T)` (emissions per second).
- **The gate passes** iff `n_keys >= K_MIN` and `R_MIN <= kps <= R_MAX`. If it fails, the readout returns the empty text, and the guard's decoder returns an empty n-best list (the guard **withholds**).

**Fit rule (val only).** Fit set F = the 66 val sentences at the first `n_fit + n_pol` = 26 + 40 positions of the order that `calibrate` uses (`numpy.random.default_rng(0).permutation(106)`), real input only. The 40 LTT positions, the test blocks and every null input are never used to fit.
- `K_MIN` = the largest integer k with `#{F sentences with n_keys < k} <= floor(0.01 x 66) = 0` (so `K_MIN` = the smallest `n_keys` of F);
- `R_MIN` = the smallest `kps` of F (the `floor(0.01 x 66) + 1` = 1st smallest);
- `R_MAX` = 2 x the largest `kps` of F.
- Check, not used to choose: the share of the 66 time-shuffled val inputs of F that pass the gate.
One gate only. No classifier, entropy rule or other variant.

## 5. Data and split (fixed; as P14-41)
- Model: `fidetype.pretrained.load("willett-hw")` (NumPy runtime, weights SHA-256 `66ac6590...`).
- Split: the P15-08 split recomputed from the public files (test = last block of each session, 80 sentences; val = one other block per session, 106 sentences). The script checks it against `derived/p15-08/willett/splits.json`.
- Null inputs (the P14-41 generators, same seeds, so they equal the P14-41 inputs):

| Name | How |
|---|---|
| time-shuffled | the 10 ms bins of the neural input in a random order, then the decoder |
| zero | an all-zero neural input of the same length, then the decoder |
| frame-shuffled | the decoder frames of the real input in a random order |
| uniform | near-uniform frames, log(1/98) + 0.05 N(0, 1), the same length, log-softmax |

- Check: the val / test log-probs (real, time-shuffled, zero) equal the P14-41 files (`derived/p14-41/lp_*.npz`, read only) to max abs diff <= 1e-5.

## 6. Measures and verdicts
### Readout (80 test sentences)
| Id | Measure | Rule |
|---|---|---|
| **R0 reproduction** | ungated F test CER through `load("willett-hw")` | pass iff |CER − 0.1734| <= 0.005 (NumPy vs GPU log-probs); the count of sentences with the same text as P15-25 (`derived/p15-25/dec/F/test/R-ball-s0.json`, read only) is reported |
| **R1 test CER** | gated F test CER (a gated sentence counts as the empty text) | reported; also greedy CER |
| **R2 gate cost** | real test sentences gated | reported; **H-cost**: <= 4 / 80 (5 %) |
| **N1 no-signal controls** | on the uniform, time-shuffled and zero test inputs: the number of inputs where the gated readout emits a non-empty text | **pass iff <= floor(0.05 x 80) = 4 of 80 for each of the three** |
| **N2 order control** | on the frame-shuffled test inputs: the pooled CER of the gated readout | **pass iff CER >= 0.85** (the P15-25 C1 level: without the signal order the readout must not give the text). The emission count is reported |

Prediction for N2 (from the method): a count gate cannot see the frame order, so frame-shuffled inputs pass the gate about as often as real inputs; N2 then depends only on the CER of F on shuffled frames.

### Guard (re-calibrated on the gated F readout)
`fidetype.trust.calibrate(lp_val, truths, alpha=0.05, delta=0.1, input_kind="logits", vocab=98 key tokens, blank=0, input_scale="log_probs", frame_period=0.01, decode_fn=<gate + F, 8-best as dicts: text, score, logp_acoustic, logp_lm>, null_inputs=<time-shuffled val input>, seed=0, audit_text=False, decoder_name="fidetype-willett-hw-lm-f", decoder_version="1", modality="intracortical", language="en")`. No `stream_texts`: the frame temperature stays 1.0, so the guard's decoder sees exactly the log-probs that the readout sees. Confidence `p_top1`, commit unit sentence. Automatic controls: uniform and frame-shuffled (300 each, allowed 15 commits each); user control: the time-shuffled val input (106, allowed 5).

| Id | Verdict | Rule (as P14-41) |
|---|---|---|
| **V1 guard** | refused / returned, not certified / certified | refused = `NullControlError`; certified = returned and LTT `feasible` |
| **V2 safety** | holds / fails / clear violation | wrong commits / 80 <= 0.05 -> holds; Clopper-Pearson 95 % lower end > 0.05 -> clear violation |
| **V3 value** | non-vacuous / vacuous | certified, at least one test commit, safe WPM v0.1 > 0 |
| **V6 controls** | pass / fail | all `calibrate` controls pass, and on the 80 test sentences the time-shuffled and the zero input each give a commit rate <= 0.05 |
| V7 offers | reported | real test: offers, withholds; exact rate and CER of the offered top-1 |
| **V8 offer null (gap 136)** | reported, descriptive | the offer rate on each test null input (uniform, time-shuffled, zero, frame-shuffled) next to the real offer rate. Flag "offer null passes" for an input iff its offer rate <= 0.05. P5-31 sets the final rule; this flag decides nothing here |

Safe WPM v0.1: `fidetype.benchmark.safe_wpm.safe_wpm`, guarantee and controls from the sheet, neural time = 10 ms bins of the sentence window, no CI (one participant).

## 7. Packaging rules (fixed here)
- **Readout:** the LM file goes into the local cache folder (`C:\Users\zhang\bci-data\pretrained\text\`), never into git, and gets a manifest row (role `text`, SHA-256, size, `url: null`), as the T15 text files. The manifest gets a `readouts.lm` block (decoder id, LM file, settings, gate values, licence, overlap, limits). The readout is **opt-in**: `m.text(stream)` stays greedy; `m.text(stream, readout="lm")` gives gated F. The code and the manifest block are written before the run; the gate values enter the manifest only after the `gate` stage. If N1 or N2 fails, the readout still ships with the measured numbers and a plain warning in the card (it is opt-in and the guard never commits), and gap 144 stays open.
- **Guard:** if V1 returns a guard and V6 passes, the guard is a second release file `willett-hw.lm.guard.json` (local only; a `guard` file row with SHA-256 and size; `readouts.lm.trust` names it; `commits: never` if not certified). `m.guard()` keeps the P14-41 guard; `m.guard(readout="lm")` gives the new one. If V1 is refused or V6 fails, the guard is not packaged; the numbers are written.
- Docs: `docs/pretrained-decoders.md` gets the readout and the guard numbers.

## 8. Run
Detached (`launch.py`): `python -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I run.py all`. Stages `lp`, `gate`, `readout`, `guard`, `decide`, `score`, each with a checkpoint in `derived\p14-48\`. A watcher stops the run (exit 3) on a `STOP` file or above **5,500 MB** working set (peak target < 6 GB). A run stopped for memory is **not** restarted; we report. DONE file: `C:\Users\zhang\bci-data\derived\p14-48\DONE`. Resume: delete `STOP`, run the launcher again.

No change of the readout, gate rule, split, guard call or verdict rules after this commit. Any variant is a new item. Write-up: `results.md` in this folder with the verdicts as computed, including failures.
