# P14-54 results: a frame-order-aware offer gate for both `willett-hw` guards (2026-11-21)

Plan: [plan.md](plan.md), pre-registered in `09def1e` (with [run.py](run.py) and the new feature `nb_coherence`) before any feature value was computed on the `willett-hw` data. Code: the P5-33 `fidetype.trust.offer_gate.OfferGate` (reused). Outputs: `results/*.json` (counts and thresholds only). Per-item files and logs stay in `C:\Users\zhang\bci-data\derived\p14-54\` only.

## Verdict

**All pre-registered rules pass for both guards. Gap 150 meets its done-when.** The val-only selection chose the same feature for both guards: `coherence` (P5-33), with a threshold per guard.

| Guard | Gate | R1 offer control (V) | R2 commits | R3 real LTT offers | R4 test nulls emit | R5 real gated (test) | R6 frame-shuffled (test) | R7 test commits | Result |
|---|---|---|---|---|---|---|---|---|---|
| built-in readout `tcfg-39aac48688b8bd12` | `coherence >= 0.004183` | **PASS**: uniform 0 / 300, frame-shuffled **0 / 300** (was 297), time-shuffled 0 / 106 | match the sheet; 0 LTT commits | 40 / 40 (limit >= 36) | time-shuffled 1, zero 0, uniform 0 of 80 (limit 4) | 0 / 80 (limit 4) | 0 / 80 vs real 77 / 80: pass (p 1.0e-42) | 0 on every input | **pass: gate wired in** |
| LM readout `tcfg-26ae951a20a0cddd` | `coherence >= 0.002821` | **PASS**: uniform 0 / 300, frame-shuffled **0 / 300** (was 289), time-shuffled 0 / 106 | match the sheet; 0 LTT commits | 40 / 40 (limit >= 36) | time-shuffled 1, zero 0, uniform 0 of 80 (limit 4) | 0 / 80 (limit 4) | 0 / 80 vs real 77 / 80: pass (p 1.0e-42) | 0 on every input | **pass: gate wired in** |

V p-values (one-sided Fisher, real 40 / 40): uniform and frame-shuffled 4.9e-53, time-shuffled 8.0e-37, for both guards.

## 1. Selection (val only: S = the 66 non-LTT val sentences; nulls from S, seed 5454)

Both guards offer on all 66 real S sentences. Tier 1 threshold = the smallest feature value of the 66 real S offers (every real S offer stays). Counts are gated offers.

**LM readout guard** (`tcfg-26ae951a20a0cddd`). Without a gate: uniform 0 / 300, frame-shuffled 291 / 300, time-shuffled 0 / 66.

| Feature | Threshold | uniform | frame-shuffled | time-shuffled | P5-31 rule on S |
|---|---|---|---|---|---|
| `coherence` | 0.002821 | 0 / 300 | 1 / 300 | 0 / 66 | pass (**chosen**: first at the lowest null rate) |
| `coherence_ratio` | 0.002872 | 0 / 300 | 1 / 300 | 0 / 66 | pass |
| `nb_coherence` | 0.001168 | 0 / 300 | 1 / 300 | 0 / 66 | pass |
| `peak` | 0.7308 | 0 / 300 | 291 / 300 | 0 / 66 | fail |
| `neg_entropy` | -0.8226 | 0 / 300 | 291 / 300 | 0 / 66 | fail |
| `nb_share` | 0.00485 | 0 / 300 | 291 / 300 | 0 / 66 | fail |

**Built-in readout guard** (`tcfg-39aac48688b8bd12`). Without a gate: uniform 0 / 300, frame-shuffled 299 / 300, time-shuffled 4 / 66.

| Feature | Threshold | uniform | frame-shuffled | time-shuffled | P5-31 rule on S |
|---|---|---|---|---|---|
| `coherence` | 0.004183 | 0 / 300 | 0 / 300 | 0 / 66 | pass (**chosen**: first at the lowest null rate) |
| `coherence_ratio` | 0.004343 | 0 / 300 | 0 / 300 | 0 / 66 | pass |
| `nb_coherence` | 0.001290 | 0 / 300 | 1 / 300 | 0 / 66 | pass |
| `peak` | 0.5722 | 0 / 300 | 299 / 300 | 2 / 66 | fail |
| `neg_entropy` | -1.4362 | 0 / 300 | 299 / 300 | 2 / 66 | fail |
| `nb_share` | 0.00485 | 0 / 300 | 299 / 300 | 3 / 66 | fail |

`coherence` on S (min / median / max), descriptive:

| Guard | real offers | frame-shuffled | time-shuffled | uniform |
|---|---|---|---|---|
| LM | 0.0028 / 0.0119 / 0.0180 | -0.0006 / -0.0001 / 0.0028 | 0.0002 / 0.0012 / 0.0037 | about 0 |
| built-in | 0.0042 / 0.0125 / 0.0182 | -0.0006 / 0.0000 / 0.0023 | 0.0014 / 0.0028 / 0.0047 | about 0 |

The two guards see different frame probabilities: the built-in guard applies its frame temperature 1.49 before the decoder, the LM guard does not (1.0). So the thresholds differ.

## 2. Evaluation

### Test (80 sentences; inputs of P14-41 / P14-49; the gated guards)

| Input | Built-in: offers with gate | without gate | gated by the offer gate | LM: offers with gate | without gate | gated by the offer gate |
|---|---|---|---|---|---|---|
| real | **77** | 77 | **0** | **77** | 77 | **0** |
| time-shuffled input | 1 | 4 | 3 | 1 | 2 | 1 |
| zero input | 0 | 0 | 0 | 0 | 0 | 0 |
| frame-shuffled frames | **0** | 77 | 77 | **0** | 77 | 77 |
| near-uniform frames | 0 | 0 | 0 | 0 | 0 | 0 |

No input gets a commit, with or without the gate (both guards are offer-only).

`coherence` on test (min / median / max; number of inputs at or above the threshold):

| Input | Built-in (threshold 0.004183) | LM (threshold 0.002821) |
|---|---|---|
| real | 0.00139 / 0.0110 / 0.0158; 77 / 80 | 0.00094 / 0.0102 / 0.0158; 79 / 80 |
| time-shuffled | 0.00048 / 0.0024 / 0.0061; 9 / 80 | 0.00005 / 0.0009 / 0.0042; 3 / 80 |
| frame-shuffled | -0.00047 / 0.0000 / 0.0007; 0 / 80 | -0.00045 / 0.0000 / 0.0008; 0 / 80 |

The real test inputs below the threshold (3 built-in, 1 LM) were already WITHHOLDs without the gate, so the gate removed no real offer.

## 3. What the numbers say

- **Frame order is the missing evidence.** `coherence` (and `coherence_ratio`, `nb_coherence`) separates real input from frame-shuffled input on val and on test. The largest frame-shuffled value on test (0.0008) is far below both thresholds; on S, one frame-shuffled input reached the LM threshold (1 / 300). The per-frame features (`peak`, `neg_entropy`, `nb_share`) let 291-299 / 300 frame-shuffled inputs through on S, the same as P14-49 and P5-33. So the result of P5-33 on `t15-m4-13` repeats on a second modality (handwriting, intracortical) and on a guard with a gated LM readout.
- **Real offers cost nothing.** The threshold is the smallest real S value, and no real test offer fell below it (0 / 77 for each guard). The LTT offers stay 40 / 40.
- **Time-shuffled input stays low.** Time-shuffled input is shuffled before the decoder. The decoder (a TCN with a receptive field of many bins) smooths its output over time, so the output frames still have some order, and their `coherence` lies between the frame-shuffled values and the real values. The gate still lowers its offers (built-in 4 -> 1, LM 2 -> 1 of 80).
- **Commits and `config_id` do not change.** The guards stay offer-only (gap 138 = P14-47).

> **Our take:** with this gate, the `willett-hw` offer list now depends on the signal in the same three ways the P5-31 control can test: amplitude (uniform), presence (zero, time-shuffled) and order (frame-shuffled). It is still not evidence that the offered text is right: the offered top-1 is exact on 12 / 77 test sentences (LM readout, P14-49). After this work, 3 of the 4 packaged guards pass the offer null control; only `kt-semg-lda` fails (gap 152). That is the condition P5-33 named for a decision on the `offer_control="refuse"` default (a user decision).

## 4. Checks and deviations

- Uniform fast path (plan section 5 step 2): the check passed on both guards (5 / 5 uniform inputs: the guard's features equal the fast-path features). But `nb_share` is about 0.99 on uniform input, above its threshold, so every uniform selection input was decided in full anyway (the plan rule "decide if one candidate reaches its threshold"). On test, the gate has one feature (`coherence`, about 0 on uniform input), so only the 5 check inputs were decided in full; the other 75 are below the threshold, so they cannot be gated offers. The guards never commit (no certified threshold), so this is exact for commits too. The recorded P14-41 / P14-49 test decisions agree (80 / 80 per input kind).
- The ungated test actions recovered from the gated run (gated WITHHOLD with the offer-gate reason = ungated OFFER) equal the recorded P14-41 / P14-49 decisions on every test input (80 / 80 for each of the 5 input kinds and both guards).
- No deviation from the plan.

## 6. What changed in the package

- `src/fidetype/pretrained/manifests/willett-hw.json`: new `trust.offer_gate` (`coherence >= 0.004183090472992479`) and `readouts.lm.trust.offer_gate` (`coherence >= 0.002820748898623049`). Both `offer_control` blocks now show the gated re-check (`results/recheck-builtin-gated.json`, `results/recheck-lm-gated.json`, verdict PASS); the P5-31 counts stay in `before_gate`. `trust_note`, `null_controls` and the LM `limits` line state the new counts.
- `PretrainedDecoder.guard(readout="lm", offer_gate=None)` applies the readout gate by default; `offer_gate=False` switches it off. The parser checks `readouts.<r>.trust.offer_gate`. The model card prints one `offer gate` line per guard.
- `fidetype.trust.offer_gate`: new feature `nb_coherence` and `FRAME_FEATURES` (committed with the plan, `09def1e`).
- The guard files do not change (same bytes, same `config_id`).
- Tests: `tests/test_pretrained_offer_control.py` (manifest = gated re-check, `before_gate` counts, gate on by default and off with `False` for both guards), `tests/test_trust_offer_gate.py` (`nb_coherence`).
- Docs: `docs/pretrained-decoders.md`, `docs/trust-guarantee.md` section 5b, `CHANGELOG.md`.

## Run record

CPU only, isolation class background, 2 threads, below-normal priority; two detached processes (one per guard). LM: select 196 s, re-check 192 s, test 93 s (02:06-02:14). Built-in: select 5,219 s (300 uniform inputs decided in full: 5,010 s), re-check 5,083 s, test 220 s (02:06-05:02). Peak working set 575 MB (LM) and 704 MB (built-in). No stop, no restart.

## 5. Limits

- One participant (T5), one checkpoint, one draw of each null input; no CI.
- The threshold is the smallest real S value, fitted on 66 sentences. A new session, participant or decoder needs a new fit.
- `coherence` tests only "is there a frame order". It does not test "is this the right person or task": real neural data of another task, or a time-reversed stream, keep a frame order and are not tested here.
- The guards stay offer-only (40 LTT items < 45, gap 138 = P14-47). The gate makes the offer list depend on the signal; it does not make the offers correct.

## Rerun

| Step | Command (repo root) |
|---|---|
| Tests (CPU, seconds) | `.venv\Scripts\python.exe -m pytest -q tests/test_trust_offer_gate.py tests/test_pretrained_offer_control.py` |
| LM guard (about 8 min CPU) | `.venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 2 -- .venv\Scripts\python.exe experiments/2026-11-21-p14-54-willett-order-gate/run.py all lm` |
| Built-in guard (about 3.5 h CPU with 2 threads; the uniform inputs are slow) | the same with `all builtin` |
| Check / done | tail `derived\p14-54\run-<g>.log`; done when `derived\p14-54\DONE-<g>` exists (`FAILED-<g>` on an error) |

## Licence

Willett data CC0 1.0. LM text CC BY 2.0 FR (Tatoeba contributors); the LM file stays local. Our code Apache-2.0. This commit holds aggregates only: no weights, LM file, log-probabilities or text.
