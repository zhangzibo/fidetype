# Personalisation: one trust profile per user, drift detection, gated re-calibration

A guard from [`calibrate`](trust-quickstart.md) is fitted to one person, one decoder and one period of time. Neural signals drift from day to day. This page shows how to keep one guard per user up to date **without** a weaker guarantee. Module: `fidetype.trust.personal` (profiles and the live controller) and `fidetype.trust.drift` (the drift tests). Roadmap item P5-01.

Fidetype is research software, not a medical device. Nothing on this page is a medical or legal claim.

## 1. Quick use

```python
from fidetype.trust.personal import PersonalTrust

pt = PersonalTrust.from_calibration(
    "user-17", cal_x, cal_y,                 # your labelled calibration data (logits or n-best)
    salt=SECRET_SALT,                        # the user id is stored only as an HMAC-SHA256 hash
    null_inputs=nulls,                       # your decoder's output on null input (needed for n-best)
    calibrate_kwargs={"vocab": VOCAB},       # anything calibrate() needs
    profile_path="profiles/user-17.json")

r = pt.decide(x)                 # the same TrustResult as TrustGuard.decide
pt.feedback(r, truth)            # what the user meant (None: no label)
out = pt.maybe_recalibrate()     # None, or the outcome of a gated proposal

pt = PersonalTrust.load("profiles/user-17.json", null_inputs=nulls)   # next session
```

## 2. The profile file

`UserProfile` (schema `fidetype.user-profile/0.1`) is one JSON file per user.

| Field | What it holds |
|---|---|
| `user_hash` | `u:` + HMAC-SHA256(salt, user id), 32 hex digits. Never the raw id. Without a salt: plain SHA-256 (`id_hash: "sha256"`), which anyone can recompute from a guessed id |
| `guard` | `TrustGuard.to_dict()`: frozen configuration, input settings, guarantee sheet |
| `calibration` | Counts, rates (commit, top-1 right, wrong commit), `p_top1` quantiles, and up to 2,000 rounded reference scores for the drift test |
| `history` | One entry per change: `calibrate`, `drift_alarm`, `tighten`, `recalibrate_accepted`, `recalibrate_rejected`, each with its `config_id`. `profile.config_ids` lists every configuration the user had |
| `drift` | The last summary of the drift tests (e-values, alarms; no scores) |
| `consent_ref` | Placeholder for the consent record of P5-04. Stored as given, not checked |
| `profile_version` | Goes up by one at each change |

**No text and no signal.** `save()` refuses a profile with a text-like key (`text`, `truth`, `choices`, `label`, `signal`, `samples`, `raw`, `inputs`, `user_id`, ...). The decoder's own word list (`lexicon`, `vocab`) inside the guard configuration is allowed. The re-calibration labels stay in memory only.

## 3. The rules of a change

```
decision ──► p_top1 ──► score test (conformal martingale) ──┐
feedback ──► loss   ──► risk test (betting e-process)  ─────┤
                                                             ▼
            risk alarm: tighten NOW (offer / withhold only; needs no evidence)
            score alarm: ask for a re-calibration (guard unchanged)
                                                             ▼
   n_recal + n_check NEW labels ──► TrustGuardUpdater.propose_calibration
        calibrate() + its null controls  ──►  GuardedUpdateLoop checks:
        block LTT on the check block, evidence gate, uniform + shuffled
        null controls, champion / challenger sign test
                                                             ▼
        accepted: new guard (ends a tightening), tests restart
        rejected: nothing changes; the proposal stays open
```

1. A higher commit threshold only removes commits, so tightening needs no evidence. Every other change goes through the existing gated update path (P15-02). There is no other way to change a live guard.
2. A proposal uses only items labelled **after** the trigger: the old ones may come from the old distribution.
3. `recalibrate_every=N` also proposes after N new labels (a schedule, without drift).

## 4. The drift tests and their guarantee

| Test | Watches | Null hypothesis | Method |
|---|---|---|---|
| `ConformalDriftTest` | `p_top1` of every decision (any score works, for example the guard risk) | live scores exchangeable with the reference scores | smoothed conformal p-values + Simple Jumper betting martingale (Vovk, Nouretdinov, Gammerman 2003; Vovk 2021; Vovk et al. 2021) |
| `RiskDriftTest` | observed per-item loss (1 = wrong commit the user corrected) | `E[L_t | past] <= alpha` at every step | betting e-process with a grid of bets (Waudby-Smith and Ramdas 2024) |

Both are **anytime valid**: under the null hypothesis, `P(an alarm ever, over the whole stream) <= level` (Ville's inequality). You may look after every item. `PersonalTrust` defaults: score level 0.005, risk level 0.005, so `P(any false alarm) <= 0.01` per test period. After an accepted re-calibration (or `PersonalTrust.load`), new tests start with a new budget.

Measured on synthetic data and on a 16-day T12 replay: see the [results](../experiments/2026-11-16-p5-01-personal/results.md).

## 5. What is not covered

- The live guard's guarantee is that of its sheet. It holds while the live data are exchangeable with the check block of the last accepted update. The drift tests watch this assumption; they do not prove it.
- **Silent errors**: a wrong commit that the user does not correct has observed loss 0. The risk test does not see it.
- Wrong labels from the user make a wrong check block.
- The detection delay depends on the size of the change. Ville's inequality bounds false alarms, not the delay.
- A rejected proposal after a risk alarm leaves the guard in offer-only mode until a later proposal passes.
- `consent_ref` is a reference only; deletion on request and the consent record are P5-04.
