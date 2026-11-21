---
title: P14-49 + P14-50 willett-hw no-signal gate for time-shuffled input, with the Willett-blocked LM - pre-registration
type: experiment
task: P14-49, P14-50
updated: 2026-11-20
---

# P14-49 + P14-50: a no-signal gate that stops time-shuffled input, on the Willett-blocked LM (pre-registration)

We wrote and committed this plan **before** any result of the new gate or the new LM readout on real data (val or test). Gaps 145 (P14-49) and 146 (P14-50) of the [open-gap list](../../wiki/questions/open-gaps.md); roadmap [P14-49](../../wiki/questions/roadmap-standard.md#p14-49-no-signal-gate-for-willett-hw-that-stops-time-shuffled-input) and [P14-50](../../wiki/questions/roadmap-standard.md#p14-50-willett-blocked-tatoeba-lm-as-the-willett-hw-lm-readout). Follow-up of [P14-48](../2026-11-20-p14-48-willett-lm-readout/results.md) (the count gate lets 13 / 80 time-shuffled test inputs emit text; limit 4) and [P15-38](../2026-11-20-p15-38-e1-lm-willett-blocked/results.md) (the Willett-blocked LM). It feeds gap 144 (P14-48), gap 138 (P14-47) and gap 136 (P5-31).

Data: Willett handwriting 2021 (T5), CC0 1.0. LM text: Tatoeba English, CC BY 2.0 FR (attribution: the Tatoeba contributors). CPU only (isolation runner, class `background`, 4 threads); **no GPU**. Per-sentence records (text, truth, decisions), features and the guard file stay in `C:\Users\zhang\bci-data\derived\p14-49\`. The P14-48 log-probs (`derived\p14-48\lp_*.npz`, equal to P14-41) are read only. The repo gets aggregates only. No weights, no LM file and no text in git.

## 1. Done criteria (from the roadmap text)
- **P14-50 (gap 146)**, "Done when": *the Willett-blocked LM is the `willett-hw` LM readout (local release file with a SHA-256 row, no test overlap), and the CER, the null controls and the guard are re-measured.* We read it as: **B1** the manifest `readouts.lm.lm_file` is `eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz` (SHA-256 `d7f6e829b827d1f7d09f5927eb51ec33fd79df29201d7e722a0878a503059261`, 3,348,904 bytes) with a `text` file row, the file is in `C:\Users\zhang\bci-data\pretrained\text\` (read-only copy); **B2** test CER (ungated, gated), N1, N2 and the guard (V1-V8) are measured on it and reported. Gap 146 closes iff B1 and B2 hold. It does not depend on the gate verdict.
- **P14-49 (gap 145)**, "Done when": *a separately pre-registered, val-only gate gets time-shuffled, zero and uniform input each to at most 4 / 80 emitting, with real input gated at most 5 %.* Gap 145 closes iff, on the 80 test sentences with the new LM, **N1'** the gated readout emits non-empty text on **<= 4 / 80** time-shuffled, **<= 4 / 80** zero and **<= 4 / 80** uniform inputs, and **H-cost** the gate stops **<= 4 / 80** real inputs. One gate is tested. No second try on test.
- **Gap 144 (P14-48)**: its D1 needs N1 and N2 to pass on the packaged readout. If N1' and N2 pass here and the gate is packaged, we report D1 as met (D2, D3 were met in P14-48; D2 is re-stated on the card for the new LM).

## 2. Known before this run (from earlier work)
| Fact | Source |
|---|---|
| New LM: no Willett text in train or held-out (LMa 0, LMb 0); R-ball-s0 F test CER **0.1743** on the GPU log-probs (old LM 0.1734); on uniform frames F emits one token per frame | P15-38 |
| The NumPy log-probs of `load("willett-hw")` equal P14-41 (max abs diff 0.0) | P14-48 |
| Count gate (P11-12 rule, 66 non-LTT val): `n_keys >= 7`, `0.425 <= kps <= 2.834`. Test: real gated 3 / 80; emits on time-shuffled 13 / 80, zero 0, uniform 0; frame-shuffled CER 0.883 | P14-48 |
| On the 66 fit sentences: real n_keys 7 / 44 / 72 (min / med / max), kps 0.425 / 1.067 / 1.417; time-shuffled n_keys 0 / 12 / 30, kps 0 / 0.308 / 0.588; 4 / 66 time-shuffled pass the count gate | P14-48 (val only) |
| Guard: 106 val -> 26 fit + 40 policy + 40 LTT; LTT needs >= 45 items | P14-41, P14-48 |

We have **not** looked at any posterior feature (peak, entropy, non-blank share, LM length) on val or test before this commit.

**Predictions:** (a) the guard is returned but **not certified** (40 < 45, independent of the readout), 0 commits, safe WPM 0.00; (b) a posterior-confidence feature (peak or entropy) separates time-shuffled input better than the counts, because shuffled bins give weak, spread posteriors; (c) the new LM changes the test CER by < 0.005 (P15-38).

## 3. Readout (fixed; P15-25 decoder F with the new LM)
- `fidetype.pretrained.lmreadout.LmReadout` (the P11-07 `LMBeam`, unchanged): `lm_weight` 0.5, `bonus` 1.0, `beam` 8, `prune_logp` -8.0, no lexicon, 8-best, end terms on. Text = top-1 tokens as characters.
- LM: `eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz` (P15-38), loaded through the manifest (`load("willett-hw").lm_readout(gate=...)`).
- Input: the `willett-hw` log-probs (T, 98) from `derived\p14-48\lp_{val,test}_{real,timeshuf,zero}.npz` (read only; their SHA-256 is logged). Frame-shuffled and near-uniform inputs: the P14-41 / P14-48 generators (`item_rng(split, i, kind)`, same seeds; val inputs use split `"val"`).

## 4. Gate candidates (all written in `fidetype.pretrained.lmreadout` before the run)
Features of a log-prob matrix x (T frames of 10 ms; `posterior_features`):
- `n_keys`, `kps`: greedy CTC emissions and emissions per second (as P14-48);
- `nb_share`: the share of frames whose argmax is not blank;
- `peak`: the mean, over greedy emissions, of the largest probability of the emitted token in its run;
- `neg_entropy`: minus the mean entropy of the non-blank-argmax frames;
- `lm_ratio`: tokens of the ungated LM top-1 / max(1, n_keys);
- `logit`: L2 logistic regression (ridge 1.0 on the coefficients, Newton steps) of real (1) vs time-shuffled (0) fit inputs on the standardised (peak, neg_entropy, nb_share, kps, log(1 + n_keys)).

| Id | Gate (pass iff) | Fit rule (real fit inputs; m = floor(0.01 n)) |
|---|---|---|
| C0 | count gate: `n_keys >= k_min` and `r_min <= kps <= r_max` | P11-12 / P14-48 rule (`NoSignalGate.fit`) |
| C1 | `n_keys >= 1`, `kps <= r_max`, `nb_share >= lo` | `r_max` = 2 x largest real kps; `lo` = (m + 1)-th smallest real score |
| C2 | same with `peak >= lo` | same |
| C3 | same with `neg_entropy >= lo` | same |
| C4 | same with `lo <= lm_ratio <= hi` | `lo`, `hi` = (m + 1)-th smallest and largest real ratio |
| C5 | same with `logit >= lo` | logistic fit on real + time-shuffled fit inputs, then `lo` as C1 |

(`ScoreGate.fit` for C1-C5.) Time-shuffled inputs are used to fit only C5. Zero, uniform and frame-shuffled inputs are never used to fit.

## 5. Selection (val only; rule fixed here)
- Gate set S = the 66 non-LTT val positions of calibrate's order (`default_rng(0).permutation(106)[:66]`, as P14-48). The 40 LTT positions and all test inputs are never used to fit or select.
- Inner split: A = the first 33 of S (in permutation order), B = the last 33. For each candidate: fit on A, count on B; fit on B, count on A. Sum the two counts (66 evaluations each):
  - G = real inputs gated; E_ts, E_zero, E_uni = time-shuffled, zero and uniform val inputs that pass the gate (and so emit text; an input that passes with an empty LM text also counts, a conservative rule).
- **Eligible** iff G <= 3, E_zero <= 3 and E_uni <= 3 (each <= floor(0.05 x 66)).
- **Choose** the eligible candidate with the smallest E_ts; ties: smaller G, then the order C0 < C1 < ... < C5. If no candidate is eligible: the smallest E_ts + G, then the same ties.
- The chosen candidate is re-fitted on all 66 positions of S (same rule) and is **the** gate. Frame-shuffled pass counts are reported, not used.
- Check, not used to choose: the re-fitted gate on the 66 S positions (real gated, time-shuffled passing).

## 6. Measures and verdicts (80 test sentences, 3,448 characters)
| Id | Measure | Rule |
|---|---|---|
| **R0** | ungated test CER with the new LM | pass iff |CER − 0.1743| <= 0.005 (P15-38 R-ball-s0); the number of sentences with the same text as `derived\p15-38\dec\F\test\R-ball-s0.json` is reported |
| R1 | gated test CER (gated = empty text); greedy CER | reported |
| **H-cost** | real test inputs gated | **pass iff <= 4 / 80** |
| **N1'** | uniform, time-shuffled, zero test inputs where the gated readout emits non-empty text | **pass iff <= 4 / 80 for each** |
| **N2** | frame-shuffled test inputs: pooled CER of the gated readout | **pass iff >= 0.85** (as P14-48); emission count reported |
| ref | the P14-48 count gate (C0 values of P14-48) on the new LM, same inputs | reported, for comparison only |

### Guard (re-calibrated on the new LM + the chosen gate)
The P14-48 call, unchanged except `decode_fn` = chosen gate + F with the new LM (8-best dicts) and `name="p14-49-willett-hw-lm"`: `fidetype.trust.calibrate(lp_val, truths, alpha=0.05, delta=0.1, input_kind="logits", vocab=<98 key tokens>, blank=0, input_scale="log_probs", frame_period=0.01, decode_fn=..., null_inputs=<time-shuffled val>, seed=0, audit_text=False, decoder_name="fidetype-willett-hw-lm-f", decoder_version="2", modality="intracortical", language="en")`. Verdicts V1, V2, V3, V6, V7 and **V8 (offer rates on the four null test inputs, gap 136)**: the P14-48 rules (P14-48 plan section 6). Safe WPM v0.1 as P14-48.

## 7. Packaging rules (fixed here)
- **LM (P14-50):** before the run, the manifest gets the new `text` row (SHA-256 `d7f6e829...059261`, 3,348,904 bytes, `url: null`) and `readouts.lm.lm_file` = the new file. The old LM row (`eng_tatoeba_6gram_mkn_noE2Q.npz`) is removed: the API reads only `readouts.lm.lm_file`, so it does not need it; the new LM is the only and default LM of the readout. The P14-48 guard row (`willett-hw.lm.guard.json`, calibrated on the old LM) and the `readouts.lm.trust` block are removed before the run, because they no longer match the readout. The card states: the file stays local because its blocklist holds research-only emg2qwerty texts (CC BY-NC-SA 4.0); the LM text itself is CC BY 2.0 FR. Until the run ends, `readouts.lm.gate` keeps the P14-48 count gate.
- **Gate (P14-49):** if N1' and H-cost pass, the chosen gate becomes `readouts.lm.gate` (the default gate of `m.lm_readout()` and `m.text(stream, readout="lm")`), with targeted tests. If it fails but it is no worse than the P14-48 count gate on each N1 input and on H-cost (measured on the new LM, same test inputs), it is still packaged, with a plain warning and gap 145 open. Otherwise the count gate stays, with its measured numbers.
- **Guard:** if V1 returns a guard and V6 passes and the guard's gate is the packaged gate, it is packaged as `willett-hw.lm2.guard.json` (local only, `guard` row with SHA-256, `readouts.lm.trust`; `commits: never` if not certified). If the count gate stays (last case above), a second calibration with the count gate (stage `guard_count`, same call) gives the packaged guard instead.
- `docs/pretrained-decoders.md` gets the new numbers.

## 8. Run
Detached (`launch.py`): `python -m fidetype.utils.isolation run --class background --threads 4 -- .venv\Scripts\python.exe -I run.py all`. Stages `check`, `lmval`, `select`, `readout`, `guard`, `decide`, `score`, each with a checkpoint in `derived\p14-49\`. A watcher stops the run (exit 3) on a `STOP` file or above **5,500 MB** working set (target < 6 GB). A run stopped for memory is **not** restarted. DONE file: `C:\Users\zhang\bci-data\derived\p14-49\DONE`. Order: `select` reads only val records; test inputs are read first in `readout`.

No change of the candidates, fit rules, selection rule, verdict rules or guard call after this commit. Any variant is a new item. Write-up: `results.md` in this folder, with every verdict as computed, including failures.
