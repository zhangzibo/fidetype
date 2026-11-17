"""P15-02 replay smoke test: the TrustGuard update hook and the update ledger on recorded T12 pilot outputs.

Input (read only): the per-trial records of the P15-01 F1/E2 pilot,
``C:/Users/zhang/bci-data/derived/f1-e2-pilot/replay/{frozen,feedback-p0.9}/records-SXX.pkl``
(16 T12 days, S08-S23; our own small CPU decoder). No decoder runs here: the records already hold each
trial's top-1 sentence posterior (``score``) and its 5-best sentence list (``offered``).

What it does (per day, in time order):
1. Live guard: ``fidetype.trust.calibrate`` (n-best input) on the frozen arm's first ``--init-days`` days.
2. Each later day d: a candidate guard is calibrated on the feedback-p0.9 arm's records of day d-1 (the
   adapted decoder). :class:`~fidetype.trust.update_hooks.TrustGuardUpdater` checks it on the phase-B items
   of day d (48 items that no decoder trained on in the pilot): block LTT, uniform + null controls through
   the commit gate, champion / challenger sign test against the live guard's decoder outputs on the same
   items. Accepted: the config is swapped into the live guard. Rejected: the guard stays.
3. The live guard then decides the phase-C items of day d (its decoder's records). Counts only.
4. Every proposal / decision goes to an append-only, hash-chained ledger; ``verify`` runs at the end.
5. Negative controls (last day, after step 3): a candidate whose decoder output on null input is
   confident (the LM-only failure of the pilot, S5). (a) Calibrated with those null inputs: ``calibrate``
   refuses. (b) Calibrated with quiet null inputs, then checked by the loop with the confident ones: the
   per-update null control refuses. Both must be rejected and the guard must not change.

Stand-ins (this is a plumbing smoke test, not an evaluation):
- n-best scores: top-1 ``log(score)``, the other 4 share ``1 - score`` equally (the records keep only the
  top-1 posterior).
- truth: the label when the pilot marks it correct, else the top-1 when it was right, else unknown
  (calibration skips the item; a check item with unknown truth counts as wrong: pessimistic).
- null input (the n-best null control): near-flat random scores over the day's 5-best texts, like
  ``tests/test_trust_dropin.noise_nbest``. The pilot did not store decoder outputs on null input.

    python smoke.py [--days N] [--out DIR] [--init-days K]

Outputs: ``DIR/ledger.jsonl`` and ``DIR/smoke.json`` (aggregates only; default
``C:/Users/zhang/bci-data/derived/p15-02-hooks``). The repo copy of ``smoke.json`` is written by hand.
"""

from __future__ import annotations

import argparse
import json
import math
import pickle
import sys
import time
from pathlib import Path

import numpy as np

import fidetype.trust as ft
from fidetype.trust.adaptive import GuardedUpdateLoop
from fidetype.trust.provenance import ProvenanceLedger, verify
from fidetype.trust.update_hooks import TrustGuardUpdater

SRC = Path("C:/Users/zhang/bci-data/derived/f1-e2-pilot/replay")
OUT = Path("C:/Users/zhang/bci-data/derived/p15-02-hooks")
DAYS = [f"S{d:02d}" for d in range(8, 24)]


def load(arm: str, day: str) -> list[dict]:
    with open(SRC / arm / f"records-{day}.pkl", "rb") as f:
        return pickle.load(f)


def nbest(r: dict) -> list[tuple[str, float]]:
    top = " ".join(r["top1"].split())
    others = []
    for t in r["offered"]:
        t = " ".join(t.split())
        if t and t != top and t not in others:
            others.append(t)
    s = min(max(float(r["score"]), 1e-6), 1.0)
    rest = max((1.0 - s) / max(len(others), 1), 1e-6)
    return [(top, math.log(s))] + [(t, math.log(rest)) for t in others]


def truth(r: dict) -> str | None:
    if r.get("label_correct") is True and r.get("label"):
        return " ".join(r["label"].split())
    if r.get("right"):
        return " ".join(r["top1"].split())
    return None


def null_lists(recs: list[dict], n: int, rng: np.random.Generator) -> list[list[tuple[str, float]]]:
    out = []
    for i in rng.integers(0, len(recs), size=n):
        texts = [x for x, _ in nbest(recs[i])]
        out.append([(t, float(-rng.uniform(0.0, 0.5))) for t in texts])
    return out


def confident_nulls(recs: list[dict], n: int, rng: np.random.Generator) -> list[list[tuple[str, float]]]:
    """Null-input output of a decoder that writes fluent text without evidence: one sure sentence."""
    out = []
    for i in rng.integers(0, len(recs), size=n):
        texts = [x for x, _ in nbest(recs[i])]
        out.append([(texts[0], 0.0)] + [(t, -30.0) for t in texts[1:]])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=len(DAYS))
    ap.add_argument("--init-days", type=int, default=3)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--null-trials", type=int, default=60)
    a = ap.parse_args(argv)
    days = DAYS[: a.days]
    if a.init_days >= len(days):
        raise SystemExit("--days must be > --init-days")
    a.out.mkdir(parents=True, exist_ok=True)
    led_path = a.out / "ledger.jsonl"
    if led_path.exists():
        led_path.unlink()  # one fresh ledger per smoke run (append-only within the run)
    t0 = time.time()
    rng = np.random.default_rng(20261116)

    init = [r for d in days[: a.init_days] for r in load("frozen", d) if truth(r) is not None]
    guard = ft.calibrate([nbest(r) for r in init], [truth(r) for r in init], input_kind="nbest",
                         null_inputs=null_lists(init, a.null_trials, rng), null_trials=a.null_trials,
                         decoder_name="f1-pilot-frozen", decoder_version=days[a.init_days - 1], seed=0)
    ledger = ProvenanceLedger(led_path)
    loop = GuardedUpdateLoop(alpha=guard.alpha, delta=guard.delta, ledger=ledger, ledger_chain="p15-02-smoke")
    up = TrustGuardUpdater(guard, loop, null_trials=a.null_trials, seed=1,
                           champion_version=f"frozen-{days[a.init_days - 1]}")
    live_arm = "frozen"
    rows = []
    for k in range(a.init_days, len(days)):
        d, prev = days[k], days[k - 1]
        cal = [r for r in load("feedback-p0.9", prev) if truth(r) is not None]
        ch = load("feedback-p0.9", d)
        champ = load(live_arm, d)
        idx_b = [i for i, r in enumerate(ch) if r["phase"] == "B"]
        assert [ch[i]["id"] for i in idx_b] == [champ[i]["id"] for i in idx_b]
        cfg_before = guard.config_id
        out = up.propose_calibration(
            [nbest(r) for r in cal], [truth(r) for r in cal],
            [nbest(ch[i]) for i in idx_b], [truth(ch[i]) for i in idx_b],
            champion_inputs=[nbest(champ[i]) for i in idx_b], check_ids=[ch[i]["id"] for i in idx_b],
            cal_ids=[r["id"] for r in cal], version=f"feedback-{d}", session=d,
            null_inputs=null_lists(ch, a.null_trials, rng), null_trials=a.null_trials,
            decoder_name="f1-pilot-feedback-p0.9", decoder_version=prev, seed=k)
        if out.accepted:
            live_arm = "feedback-p0.9"
        live = load(live_arm, d)
        c = [r for r in live if r["phase"] == "C"]
        res = [guard._decide_quiet(nbest(r)) for r in c]
        commits = [(x, r) for x, r in zip(res, c) if x.action == "commit"]
        wrong = sum(1 for x, r in commits if truth(r) is None or " ".join((x.text or "").split()) != truth(r))
        rec = out.record
        rows.append({
            "day": d, "accepted": out.accepted, "reasons": list(out.reasons), "live_arm_after": live_arm,
            "config_changed": guard.config_id != cfg_before,
            "commit_p_before": out.to_dict()["commit_p_before"], "commit_p_after": out.to_dict()["commit_p_after"],
            "lambda_session": None if rec is None or not math.isfinite(rec.lambda_session) else rec.lambda_session,
            "controls": [] if rec is None else [cr.to_dict() for cr in rec.controls],
            "challenger_test": None if rec is None or rec.challenger_test is None else rec.challenger_test.to_dict(),
            "phase_c_items": len(c), "phase_c_commits": len(commits), "phase_c_wrong_commits": wrong,
        })
        print(f"{d}: accepted={out.accepted} live={live_arm} commit_p {rows[-1]['commit_p_after']} "
              f"commits {len(commits)}/{len(c)} wrong {wrong} reasons={list(out.reasons)}", flush=True)
    # negative control on the last day: a candidate that commits on null input
    d = days[-1]
    cal = [r for r in load("feedback-p0.9", days[-2]) if truth(r) is not None]
    ch = load("feedback-p0.9", d)
    idx_b = [i for i, r in enumerate(ch) if r["phase"] == "B"]
    cfg_before, log_before = guard.config_id, len(guard.audit_log)
    neg = up.propose_calibration(
        [nbest(r) for r in cal], [truth(r) for r in cal], [nbest(ch[i]) for i in idx_b],
        [truth(ch[i]) for i in idx_b], champion_inputs=[nbest(load(live_arm, d)[i]) for i in idx_b],
        check_ids=[("neg",) + (ch[i]["id"],) for i in idx_b], cal_ids=[("neg", r["id"]) for r in cal],
        version=f"negative-{d}", session=f"{d}-negative", null_inputs=confident_nulls(ch, a.null_trials, rng),
        null_trials=a.null_trials, decoder_name="f1-pilot-feedback-p0.9-lm-only", decoder_version=d, seed=99)
    negative = {"day": d, "accepted": neg.accepted, "reasons": list(neg.reasons),
                "guard_unchanged": guard.config_id == cfg_before and len(guard.audit_log) == log_before}
    cand = ft.calibrate([nbest(r) for r in cal], [truth(r) for r in cal], input_kind="nbest",
                        null_inputs=null_lists(cal, a.null_trials, rng), null_trials=a.null_trials,
                        decoder_name="f1-pilot-feedback-p0.9-lm-only-b", decoder_version=d, seed=98)
    neg_b = up.propose(cand, [nbest(ch[i]) for i in idx_b], [truth(ch[i]) for i in idx_b],
                       champion_inputs=[nbest(load(live_arm, d)[i]) for i in idx_b],
                       check_ids=[("neg-b", ch[i]["id"]) for i in idx_b], trained_on=[("neg-b", r["id"]) for r in cal],
                       version=f"negative-b-{d}", null_inputs=confident_nulls(ch, a.null_trials, rng))
    negative_b = {"day": d, "accepted": neg_b.accepted, "reasons": list(neg_b.reasons),
                  "guard_unchanged": guard.config_id == cfg_before and len(guard.audit_log) == log_before}
    print(f"negative control b {d}: accepted={neg_b.accepted} unchanged={negative_b['guard_unchanged']} "
          f"reasons={list(neg_b.reasons)}", flush=True)
    print(f"negative control {d}: accepted={neg.accepted} unchanged={negative['guard_unchanged']} "
          f"reasons={list(neg.reasons)}", flush=True)
    ver = verify(led_path, expected_head=ledger.anchor())
    stages = [e["body"]["stage"] for e in ledger.entries if e["kind"] == "update"]
    summary = {
        "task": "P15-02", "what": "replay smoke test of TrustGuardUpdater + update ledger on T12 pilot records",
        "source": str(SRC), "days": days, "init_days": days[: a.init_days], "n_init_items": len(init),
        "initial_config_id": up.outcomes[0].config_id_before if up.outcomes else guard.config_id,
        "final_config_id": guard.config_id,
        "n_proposed": stages.count("proposed"), "n_accepted": stages.count("accepted"),
        "n_rejected": stages.count("rejected"),
        "ledger_verify_ok": ver.ok, "ledger_errors": ver.errors[:5], "ledger_entries": ver.n_entries,
        "every_proposal_decided": stages.count("proposed") == stages.count("accepted") + stages.count("rejected"),
        "guard_unchanged_on_reject": all(not r["config_changed"] for r in rows if not r["accepted"]),
        "guard_changed_on_accept": all(r["config_changed"] for r in rows if r["accepted"]),
        "phase_c_items": sum(r["phase_c_items"] for r in rows),
        "phase_c_commits": sum(r["phase_c_commits"] for r in rows),
        "phase_c_wrong_commits": sum(r["phase_c_wrong_commits"] for r in rows),
        "negative_control": negative, "negative_control_loop": negative_b,
        "per_day": rows, "seconds": round(time.time() - t0, 1),
        "stand_ins": ["n-best scores from the top-1 posterior only", "null input = near-flat random scores",
                      "truth unknown -> skipped in calibration, wrong in the check block"],
    }
    (a.out / "smoke.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "per_day"}, indent=1))
    ok = (summary["ledger_verify_ok"] and summary["every_proposal_decided"] and summary["guard_unchanged_on_reject"]
          and summary["guard_changed_on_accept"] and not negative["accepted"] and negative["guard_unchanged"]
          and not negative_b["accepted"] and negative_b["guard_unchanged"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
