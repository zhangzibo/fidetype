---
title: P5-42 - a multi-user safety check and a per-user bound in calibrate - design note and pre-registration
type: experiment-plan
task: P5-42 (gap 221)
updated: 2026-11-25
---

# P5-42: multi-user safety check and per-user bound in `calibrate` (design note + pre-registration)

Written and committed **alone**, before any library code and before any run of the new check. CPU only. No GPU. No shipped guard, card or published number changes.

## Why
- B1 (`994212f`): a gate pooled over subjects with different base rates certified on permuted labels and on noise. The score had learned each subject's base rate.
- Pooled-guard check (`74a21f8`), F1: in two emg2qwerty guards (E-S, E-SL), labels permuted **inside** each user (NW) certify more commits than labels permuted over the pool (NP) (MWU p 0.0086, 0.0028). F2: one of 8 users has a wrong-commit rate of about 0.065 while the pool meets alpha 0.05.
- Done-when (gap 221): `calibrate` takes user groups and (a) runs the NW-vs-NP label null and warns or refuses when NW certifies more than NP, (b) offers a per-user / stratified LTT when each user has enough items; tests cover a synthetic B1-type leak; `docs/trust-guarantee.md` states the scope.

## Design
New keyword arguments of `fidetype.trust.calibrate` (all opt-in):

| argument | default | meaning |
|---|---|---|
| `users` | `None` | one user (or session) id per input. Not the same as `groups=` (sentence groups for the split, `d0a6a29`). `users=` does **not** change the split |
| `user_check` | `"warn"` | the user-identity label null (below). `"warn"`: result on the sheet, a failure adds a sheet warning. `"refuse"`: a failure raises `NullControlError`. `"off"`: not run |
| `user_bound` | `"pooled"` | `"pooled"`: the bound on the pool (unchanged). `"each"`: the commit threshold is raised so that the bound also holds for **each** calibration user (each at level delta). `"all"`: for all calibration users **together** (Bonferroni, each user at delta / K) |

Without `users=` the code path is the old one: bit-identical guard file and the same `config_id`. `user_check` or `user_bound` other than the defaults without `users=` is a `ValueError`. In this version `users=` is for sentence commits (`confidence="p_top1"` or `"learned"`); it is a `ValueError` with `commit_unit="prefix"`, `grounding=`, `llm=` or `target_precision=`.

### (a) The user-identity label null (score level, on the LTT items)
The certificate comes from the LTT step on the LTT items. The commit score of each LTT item is fixed before that step (it is fitted on the other parts). So a label null on the LTT items alone is a valid conditional test, and it is cheap (no new decoding).

Per LTT item i of the final guard: score `s_i` (the value that the commit threshold is compared with: `p_top1` for the default score, the learned score for `confidence="learned"`; `-inf` if the guard cannot commit the item at any threshold: commit gate, empty n-best, other policy rules), `w_i` = top-1 is wrong, and (default score only) `o_i` = the item is OFFER_WORDS at `commit_p = inf` (the fallback loss of the LTT step). Loss at threshold t: as in `ltt_threshold`. k(labels) = number of LTT items with `s_i >= lambda(labels)` (0 if no threshold is certified), with lambda the same LTT step (alpha, delta, grid 1.00 -> 0.00 step 0.01, exact binomial p-values).

- `k_real`: real labels.
- NW: `w` permuted inside each user, B = 200 runs. NP: `w` permuted over all LTT items, B = 200 runs. Own generator (`seed`, fixed tag): the controls and the split do not change.
- `p_user = (1 + #{b: k_NW[b] >= k_real}) / (B + 1)`: the p-value of "the certificate is not larger than what each user's base rate alone gives".
- `p_leak`: one-sided Mann-Whitney U of k_NW > k_NP.

Verdict (on the sheet, key `users`):

| verdict | rule | `"warn"` | `"refuse"` |
|---|---|---|---|
| `no commits` | `k_real = 0` | none | none |
| `fail` (explained by who the user is) | `k_real >= 1` and `p_user > 0.05` | warning | `NullControlError` |
| `partial` (part of the certificate is the user) | not `fail`, and `p_leak < 0.01` | warning | warning |
| `pass` | otherwise | none | none |

The check never changes the guard: the same `config_id`, threshold and decisions as without `users=`. The sheet gets a `users` block (counts, the verdict, both p-values, medians of k) and, with `"warn"`, a warning line. A sheet without `users=` keeps its bytes.

Limits (to be stated in the docs): it tests the LTT step, at the score level (the temperatures and the learned score are not refitted on permuted labels, unlike the pooled-guard check); a user with one LTT item adds nothing to NW; a `fail` is also the result when the score has no signal at all inside users (the certificate is then not above the NW null).

### (b) Per-user bound
`user_bound="each"` / `"all"`: on the LTT items of each user u, the same LTT step at level `delta_u` (`delta` for `"each"`, `delta / K` for `"all"`, K = number of users) gives `lambda_u`. Final threshold = max(the pooled threshold, max_u lambda_u). A higher threshold only removes commits, so the pooled bound and each per-user bound hold at the final threshold. Each user needs at least `min_ltt_items(alpha, delta_u)` LTT items (45 for 0.05 / 0.1); else `calibrate` raises `ValueError` with the counts. The new threshold enters the frozen configuration (`commit_p`, or the learned score's threshold) and a `recipe["user_bound"]` block, so `config_id` changes **only** when `user_bound` is not `"pooled"`. The in-sample LTT counts and the null controls are run again on the final guard. Scope: the calibration users only (a new user has no per-user guarantee).

## Pass rules (pre-registered)
**Opt-in / no change (unit tests, must all hold):**
- O1: guards of three reference calls (n-best p_top1, n-best learned, logits with lexicon) keep their `config_id` from the parent commit `83da5d1`: `tcfg-e2c493219795d790`, `tcfg-d1895d8b176cdc20`, `tcfg-320799cb7f75e253`; `users=None` gives the same guard file (sha256, without `created_utc`) as a call without it.
- O2: with `users=` and `user_bound="pooled"`, the `config_id`, the threshold and the decisions equal those without `users=`.
- O3: `calibrate(groups=)` behaves as before (its tests pass unchanged).

**Synthetic validation (`synth.py`, 20 replicates per case, seeds 1-20, n-best input, alpha 0.05, delta 0.1, 4 users x 300 items):**

| case | data | rule |
|---|---|---|
| A: pure base-rate leak (B1 type) | user base rates 0.2 / 0.45 / 0.7 / 0.95; the top-1 margin depends on the user only (plus noise that does not depend on the label) | `k_real >= 1` in >= 15 of 20 (validity); among those, verdict `fail` in >= 90 % |
| B: real within-user signal | all users base rate 0.6 on average; the margin follows a per-item latent z, right with probability z; no user effect | verdict `pass` (not `fail`, not `partial`) in >= 18 of 20 |
| C: signal + base-rate difference | per-user mean of z 0.35 / 0.55 / 0.75 / 0.9; right with probability z | verdict not `fail` in >= 18 of 20 (descriptive: number of `partial`) |
| D: one user overconfident | as B, but for one user right with probability 0.6 z | validity: the pooled guard's test wrong-commit rate of that user > alpha in >= 10 of 20. Rule: with `user_bound="all"`, all 4 users have test wrong-commit rate <= alpha + 0.01 in >= 16 of 20 |

Test set (case D): 3,000 new items per user from the same generator. A `refuse`-mode unit test on one fixed case-A seed must raise `NullControlError`.

**emg2qwerty (descriptive; one rule):** the three pooled-guard-check arms E-S, E-SL, E-LFL (P11-12 S / SL, P11-14 L-FL), the same calibration recipe, data and seed as the pooled-guard check (read only from `derived/` and the sources that check names), `users=` = the emg2qwerty user of each calibration prompt.
- E0 (rule): with `users=` and `user_bound="pooled"`, each arm gives the pooled-guard check's reproduction `config_id` (`tcfg-3875f995e4c256fb`, `tcfg-0cd6e9578e965f42`, `tcfg-4b2192820e68660b`) and LTT commits / wrong (71 / 16, 80 / 16, 108 / 16).
- E1 (report): the verdict, `p_user`, `p_leak` and the median k of NW / NP per arm, next to the pooled-guard check's full-recipe nulls. Expectation (not a rule): E-S and E-SL `partial`, E-LFL `pass`, none `fail`.
- E2 (report): `user_bound="each"` and `"all"` per arm: refused for too few items, or the certified threshold, LTT commits, and on the 1,221 test prompts the commits, wrong commits and the number of users (of 8) with a point rate > alpha and with a CP 95 % upper bound > 2 alpha (the pooled-guard check's R3). Expectation: `"all"` needs 86 LTT items per user (about 57 exist): refused.

## Data, privacy and compute
- Read only: `C:/Users/zhang/bci-data/derived/pooled-guard-check/` and the `derived/` sources it names (P11-11, P11-12, P11-14 files). Never `derived/p15-50`.
- Write only: `C:/Users/zhang/bci-data/derived/p5-42/` (and the repo files of this folder).
- The repo gets aggregates only: no per-user value for emg2qwerty (research-only data), no text, no id.
- CPU only (`HIP_VISIBLE_DEVICES=-1`), at most 3 threads, below-normal priority. The library code for the emg2qwerty run is a clean copy of `src/` at the code commit.
