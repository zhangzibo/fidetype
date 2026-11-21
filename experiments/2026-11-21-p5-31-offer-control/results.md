# P5-31 offer null control: re-check of the packaged guards (2026-11-21)

Roadmap: [P5-31](../../wiki/questions/roadmap-standard.md#p5-31-null-control-for-offers) (gap 136). Code: `fidetype.trust.offer_control`, `fidetype.trust.recheck_offer_control`, `calibrate(offer_control=...)` (commit `534feae`). Rule and mode: [docs/trust-guarantee.md](../../docs/trust-guarantee.md) section 5a.

## Method

- No new calibration. Each packaged guard is loaded as it is.
- `recheck_offer_control(guard, inputs, null_inputs=...)` makes the same split and the same control inputs as `calibrate` (from `sheet.seed`). It counts COMMITs and OFFERs on the LTT items and on each null control.
- Check of the method: the commit counts must equal the stored sheet (`commits_match_sheet`). They do for all four guards.
- Calibration inputs (local only, not committed):
  - `willett-hw` (P14-41 offer-only guard, `tcfg-39aac48688b8bd12`): `bci-data/derived/p14-41/lp_val_real.npz`, nulls `lp_val_timeshuf.npz` (106 val sentences).
  - `willett-hw` LM readout (P14-49 guard `tcfg-26ae951a20a0cddd`, the packaged `readouts.lm` guard): the same val inputs (`derived/p14-48`), `decode_fn` = the packaged gated LM readout.
  - `t15-m4-13` (`tcfg-1016759f08a3f9a1`): `derived/trust-reruns-m4-13/logprobs-m4-13-long0-val_select.npz` (722 val_select trials) and the P14-05 phoneme-words `decode_fn`, rebuilt as in `experiments/2026-11-16-p14-05-safe-wpm/run.py`.
  - `kt-semg-lda` (`tcfg-d8a73194fe539e72`): the 173 key n-best lists and 173 shuffled null inputs, rebuilt from the raw KT-sEMG guard runs 14, 15, 16, 19, 22, 23 with the packaged model, as in `fidetype.live.build.train_kt` (no training).
- Pre-stated rule (`OFFER_NULL_MAX_RATIO` 0.5, `OFFER_NULL_P` 0.05): a control passes if null offer rate <= 0.5 x real offer rate, and (null offers <= floor(0.05 n) or one-sided Fisher exact p <= 0.05). Real = the LTT items.

Scripts: `recheck_willett.py` (`lm` | `builtin`), `recheck_t15.py`, `recheck_kt.py`. Outputs: `results/recheck-*.json` (counts only).

## Results

| Guard | Real offers (LTT) | uniform | frame-shuffled / shuffled | user nulls (time-shuffled input) | Verdict | Commits match the sheet |
|---|---|---|---|---|---|---|
| `willett-hw` (P14-41, offer-only, `tcfg-39aac48688b8bd12`) | 40 / 40 | 0 / 300 (PASS, p 4.9e-53) | 297 / 300 (FAIL, p 0.686) | 6 / 106 (PASS, p 7.46e-30) | **FAIL** | True (LTT commits 0) |
| `willett-hw` LM readout (P14-49, offer-only, `tcfg-26ae951a20a0cddd`) | 40 / 40 | 0 / 300 (PASS, p 4.9e-53) | 289 / 300 (FAIL, p 0.247) | 0 / 106 (PASS, p 7.96e-37) | **FAIL** | True (LTT commits 0) |
| `t15-m4-13` (certified, `tcfg-1016759f08a3f9a1`) | 217 / 271 | 300 / 300 (FAIL, p 1) | 300 / 300 (FAIL, p 1) | - | **FAIL** | True (LTT commits 54) |
| `kt-semg-lda` (never commits, `tcfg-d8a73194fe539e72`) | 65 / 65 | 300 / 300 (FAIL, p 1) | - | 173 / 173 (FAIL, p 1) (key windows drawn at random) | **FAIL** | True (LTT commits 0) |

Run time (CPU, one process, below-normal priority): `willett-hw` 3,768 s, LM readout 145 s, `t15-m4-13` 240 s, `kt-semg-lda` about 300 s. The `willett-hw` run used the built-in decoder (`search="vector"`) with the P5-32 cache cut (`5a44e1b`). Its commit counts equal the sheet, which was made before P5-32.

- Every packaged guard fails the offer null control. No guard, `config_id` or certified status changes (mode `"warn"`).
- `t15-m4-13` and `kt-semg-lda` offer on every null input (300 / 300 uniform; shuffled 300 / 300 and 173 / 173). Their real offer rates are 217 / 271 and 65 / 65.
- Both `willett-hw` guards pass the uniform control (0 / 300) and the time-shuffled user control (6 / 106 and 0 / 106). They fail only on frame-shuffled frames (297 / 300 and 289 / 300), with real 40 / 40. This agrees with the P14-41 / P14-48 test counts (77 / 80 frame-shuffled).

> **Our take:** the policy offers when it is not sure, and null input is the least sure input. So the offer list of these guards is not evidence that the signal was read. `t15-m4-13` stays certified for commits: the offer control does not touch the commit bound. A guard that passes needs a policy that WITHHOLDs on no-evidence input, for example a no-signal gate before the offer list. The `willett-hw` gates already stop flat and time-shuffled input. Frame-shuffled frames keep their per-frame statistics, so a gate on per-frame statistics cannot stop them (P14-49).
