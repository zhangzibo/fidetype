# P5-33 results: an offer gate that withholds on no-evidence input (2026-11-21)

Plan: [plan.md](plan.md), pre-registered in `a7abc11` before any feature value was computed. Script: `run.py` (stages `kt-select`, `t15-select`, `select`, `t15-eval`, `kt-eval`). Code: `fidetype.trust.offer_gate` (`OfferGate`), `TrustGuard(offer_gate=...)`, `ft.load(..., offer_gate=)`. Outputs: `results/*.json` (counts and thresholds only). Per-item files are local only, in `bci-data/derived/p5-33/`.

## Verdict

| Guard | Selection | E1 offer control | E2 commits | E3 real offers (LTT) | E4 val_eval | Result |
|---|---|---|---|---|---|---|
| `t15-m4-13` (`tcfg-1016759f08a3f9a1`) | tier 1: `coherence >= 0.186975` | **PASS**: uniform 0 / 300, frame-shuffled 0 / 300 (p 2.1e-102 each) | match the sheet; 54 LTT commits (unchanged) | 212 / 271 (limit >= 185; ungated 217) | PASS (see below) | **all rules pass: gate wired in** |
| `kt-semg-lda` (`tcfg-d8a73194fe539e72`) | **no candidate passes** (tier 1 and tier 2) | FAIL (information only, `char_lm_best >= -4.3987`): uniform 289 / 300, user nulls 165 / 173 | match the sheet; 0 LTT commits | 63 / 65 | - | **negative: no gate** |

E4 for `t15-m4-13` on val_eval (701 trials, not used in the selection):

| Check | Value | Rule |
|---|---|---|
| Commits | 104, the same items and texts as the P14-05 decisions without the gate (`same_commits_as_p14_05: true`) | identical (margin 0): pass |
| Offers | 568 gated, 597 ungated (95.1 % kept) | >= ceil(0.85 x 597) = 508: pass |
| Null offers (made from val_eval, seed 3306) | uniform 0 / 300, frame-shuffled 0 / 300 (p 5.2e-150 each; real 568 / 701) | P5-31 rule: pass |

## Selection (S = non-LTT calibration items; nulls seed 3305)

`t15-m4-13`: S has 451 items and 380 real offers. With each threshold set to keep about 95 % of them, 361 offers stay.

| Feature | Threshold | uniform | frame-shuffled | P5-31 rule on S |
|---|---|---|---|---|
| `coherence` | 0.1870 | 0 / 300 | 0 / 300 | pass (chosen: first in order at the lowest null rate) |
| `coherence_ratio` | 0.2876 | 0 / 300 | 0 / 300 | pass |
| `p_top1` | 0.2035 | 295 / 300 | 220 / 300 | fail |
| `safety` | 0.2 | 0 / 300 | 27 / 300 | pass |
| `peak` | 0.748 | 0 / 300 | 275 / 300 | fail |
| `neg_entropy` | -0.8174 | 0 / 300 | 276 / 300 | fail |
| `nb_share` | 0.181 | 300 / 300 | 287 / 300 | fail |

`kt-semg-lda`: S has 108 items and 108 real offers.

| Feature | Threshold | real offers kept | uniform (equal scores) | user nulls (random key windows) | P5-31 rule on S |
|---|---|---|---|---|---|
| `p_top1` | 0.125 | 103 | 0 / 300 | 104 / 108 | fail |
| `safety` | 0.0 | 108 | 300 / 300 | 108 / 108 | fail |
| `margin` | 0.0 | 103 | 0 / 300 | 103 / 108 | fail |
| `conf_mean` | 0.2914 | 103 | 0 / 300 | 107 / 108 | fail |
| `char_lm` | -5.193 | 103 | 283 / 300 | 105 / 108 | fail |
| `char_lm_best` | -4.399 | 103 | 282 / 300 | 100 / 108 | fail |
| tier 2: `char_lm_best` AND `margin` | -4.667, 3.1e-7 | 104 | 0 / 300 | 100 / 108 | fail |

## What the numbers say

- **`t15-m4-13`.** The frame-order feature `coherence` separates real input from both nulls completely (0 / 300 null offers in S, in the LTT re-check and on val_eval). The per-frame features (`peak`, `neg_entropy`, `nb_share`) stop uniform input but not frame-shuffled input (275-287 / 300). This agrees with P14-49 on `willett-hw`. The gate removes 5 of 217 real LTT offers and 29 of 597 val_eval offers. It changes no commit.
- **`kt-semg-lda`.** No feature separates real bursts from the user nulls (best: 100 / 108 null offers vs 103 / 108 real). The user nulls are real key windows taken at random times of the same runs. So every feature of the signal (`p_top1`, `margin`, `conf_mean`) has the same distribution on null and real input. Only the order and the language of the keys differ. The decoder key accuracy is 0.248 (manifest), so the decoded text of real bursts is not much closer to English than the text of random windows: `char_lm` does not separate them. The equal-score uniform control is easy to stop (`p_top1`, `margin`: 0 / 300), but this does not help: the guard must pass all controls.

> **Our take:** a passing offer gate for `kt-semg-lda` needs more evidence than this decoder gives. Possible routes: a decoder with a much higher key accuracy, or a feature that reads the key order in the signal (for example, the same coherence idea on the key posteriors across keys). Until then, the `kt-semg-lda` offer list is not evidence that the signal was read. The model card already says so (FAIL). `coherence` reads the frame order, so it is also a candidate for `willett-hw` (gap 150). That needs its own pre-registered selection.

## What changed in the package

- `src/fidetype/pretrained/manifests/t15-m4-13.json`:
  - New `trust.offer_gate`: `coherence >= 0.1869751254594959`.
  - `trust.offer_control` now shows the gated re-check (`results/recheck-t15-gated.json`, verdict PASS). The counts without the gate are kept in `before_gate`.
- `PretrainedDecoder.guard(offer_gate=None)` uses the manifest gate. `offer_gate=False` gives the old behaviour.
- The packaged guard file `guards/t15-m4-13.guard.json` does not change (same bytes, same `config_id`).
- The model card has a new line `offer gate: ...`.
- `kt-semg-lda` and `willett-hw`: no change (offer control FAIL, warn mode).

## Recommendation on the `offer_control` default (decision for the user)

Keep the default `"warn"` for now. After this work, 1 of the 4 packaged guards passes the offer null control: `t15-m4-13`, with the gate. With `"refuse"`, a re-calibration of `kt-semg-lda` and of both `willett-hw` guards would raise `NullControlError`. Consider `"refuse"` after gap 150 (`willett-hw`) has a passing gate. At that time, `kt-semg-lda` could be released as "offers not shown", or with an explicit `offer_control="warn"`.

## Run record

CPU only: isolation class background, 2 threads, below-normal priority. kt-select 319 s, t15-select 337 s, t15-eval 641 s, kt-eval 316 s (2026-11-21, 01:26-01:54).
