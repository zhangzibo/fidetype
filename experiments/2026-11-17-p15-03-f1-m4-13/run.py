"""P15-03a (F1, CPU part): champion / challenger replay on T15 with real decoders (plan: plan.md). Our own code.

The live trust layer is a ``fidetype.trust.calibrate`` guard (P14-03 word route, logits input). Every decoder or
configuration change goes through ``TrustGuardUpdater`` + ``GuardedUpdateLoop`` (P15-02: block LTT on a fresh check
block, uniform + shuffled null controls through the evidence gate, champion / challenger sign test) and is written
to a hash-chained ``ProvenanceLedger``. The decoders are the recorded log-probs of M4-12 fixed0 (weaker,
val_select PER 0.256) and M4-13 long0 (stronger), plus a broken decoder (time-reversed M4-13 log-probs).

Held-out stream: val_eval in (session, index) order, cut into 7 contiguous blocks. Block b: the first N_CHECK items
are the check block of proposal b (offer-only, truth from the simulated user), the rest is phase C (the live guard
decides). Calibration of every candidate: val_select of that candidate's decoder.

    run.py [--seeds 0 1] [--users oracle feedback-r0.3]     one JSON per (seed, user) run; resumable per run

Per-trial outputs and ledgers: C:/Users/zhang/bci-data/derived/p15-03-f1-m4-13/ only. Repo: aggregates only.
Dry run (plumbing only): TRUST_RERUN_DRY=1 TRUST_RERUN_SOURCE=m4-12 (both "decoders" then come from M4-12 files,
so the better / worse labels mean nothing in a dry run).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "2026-11-17-trust-reruns-m4-13"))
import common as K  # noqa: E402

import fidetype.trust as ft  # noqa: E402
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.adapters import b2t25 as B  # noqa: E402
from fidetype.trust.adaptive import FeedbackUser, GuardedUpdateLoop, char_error_rate  # noqa: E402
from fidetype.trust.provenance import ProvenanceLedger, verify  # noqa: E402
from fidetype.trust.update_hooks import TrustGuardUpdater  # noqa: E402
from fidetype.utils.binomial import clopper_pearson  # noqa: E402

DRY = K.is_dry()
SRC = K.source_name()
if not DRY:
    assert SRC == "m4-13", "a real run uses the M4-13 outputs"
OWN = K.own("p15-03", DRY)
OUT = HERE / ("results/dryrun-" + SRC if DRY else "results")
OUT.mkdir(parents=True, exist_ok=True)
log = K.Logger(OUT / "run.log")

ALPHA, DELTA = 0.05, 0.1
N_BLOCKS = 7
N_CHECK = 48  # >= min_ltt_items(0.05, 0.1) = 45; the P15-01 / P15-02 check size
NULL_INIT, NULL_CAND, NULL_LOOP = 300, 100, 100
USERS = {"oracle": FeedbackUser(p_retype=1.0), "feedback-r0.3": FeedbackUser(p_retype=0.3)}
UNKNOWN = "\x00unknown-truth\x00"  # a check item with unknown truth never matches: pessimistic (wrong)
# Proposal schedule (fixed in plan.md). kind: "decoder" (another decoder's logits), "recal" (same live decoder,
# another seed), "broken" (time-reversed M4-13 logits). "worse" = the decoder that is NOT live (expected worse when
# M4-13 is live).
SCHEDULE = [
    ("B1", "decoder", "m4-13", "better challenger: M4-13 vs live M4-12"),
    ("B2", "decoder", "other", "worse challenger: the decoder that is not live (M4-12 if M4-13 is live)"),
    ("B3", "broken", "m4-13-rev", "broken challenger: time-reversed M4-13 log-probs"),
    ("B4", "recal", "live", "re-calibration of the live decoder (seed + 100)"),
    ("B5", "decoder", "other", "worse challenger, replication on new items"),
    ("B6", "recal", "live", "re-calibration of the live decoder (seed + 200)"),
    ("B7", "decoder", "other", "worse challenger, second replication"),
]


def load_decoders():
    """{name: (cal (xs, texts, ph), held (xs, texts, ph))}; same items and order for every decoder."""
    dec = {}
    if DRY:  # plumbing only: M4-12 files under both names
        a = K.load_t15("m4-12", norm_text=False, with_keys=True)
        dec["m4-12"] = a
        dec["m4-13"] = a
    else:
        dec["m4-12"] = K.load_t15("m4-12", norm_text=False, with_keys=True)
        dec["m4-13"] = K.load_t15("m4-13", norm_text=False, with_keys=True)
    k12, k13 = dec["m4-12"], dec["m4-13"]
    for p in (0, 1):
        assert k12[p][3] == k13[p][3], "the two decoders must cover the same items in the same order"
    m = dec["m4-13"]
    rev = lambda xs: [x[::-1].copy() for x in xs]  # noqa: E731
    dec["m4-13-rev"] = ((rev(m[0][0]), *m[0][1:]), (rev(m[1][0]), *m[1][1:]))
    return dec


def greedy_symbols(lp: np.ndarray) -> str:
    ids = lp.argmax(1)
    out, prev = [], -1
    for i in ids:
        if i != prev and i != 0:
            out.append(B.SYMBOL_VOCAB[int(i)])
        prev = i
    return "".join(out).strip()


def norm(t: str) -> str:
    return " ".join(str(t).split())


def per_test(ch_lp, champ_lp, ph) -> dict:
    """Secondary paired test (plan H7): per-item greedy phoneme error rate, challenger minus champion."""
    from scipy.stats import wilcoxon

    a = np.array([char_error_rate(greedy_symbols(x), p) for x, p in zip(ch_lp, ph)])
    b = np.array([char_error_rate(greedy_symbols(x), p) for x, p in zip(champ_lp, ph)])
    d = a - b
    nz = d[d != 0]
    p_worse = float(wilcoxon(nz, alternative="greater").pvalue) if nz.size >= 10 else None
    p_better = float(wilcoxon(nz, alternative="less").pvalue) if nz.size >= 10 else None
    return {"per_challenger": float(a.mean()), "per_champion": float(b.mean()), "mean_diff": float(d.mean()),
            "n_nonzero": int(nz.size), "p_worse": p_worse, "p_better": p_better}


def run_one(seed: int, user_name: str, dec: dict, fn) -> dict:
    t0 = time.time()
    tag = f"s{seed}-{user_name}"
    rng_user = np.random.default_rng([seed, 1503])
    user = USERS[user_name]
    led_path = OWN / f"ledger-{tag}.jsonl"
    if led_path.exists():
        led_path.unlink()  # one fresh ledger per run (a run is redone as a whole)
    kw = dict(vocab=list(B.SYMBOL_VOCAB), blank=0, input_scale="log_probs", frame_period=0.08, decode_fn=fn,
              modality="intracortical")
    (cx, ct, cph, _), _ = dec["m4-12"]
    guard = ft.calibrate(cx, ct, alpha=ALPHA, delta=DELTA, stream_texts=cph, decoder_name="m4-12-fixed0",
                         name=f"p15-03a-{tag}-init", seed=seed, null_trials=NULL_INIT, **kw)
    ledger = ProvenanceLedger(led_path)
    loop = GuardedUpdateLoop(alpha=ALPHA, delta=DELTA, n_check=N_CHECK, ledger=ledger, ledger_chain=f"p15-03a-{tag}")
    up = TrustGuardUpdater(guard, loop, null_trials=NULL_LOOP, seed=seed + 1, champion_version="m4-12")
    live = "m4-12"
    hx_keys = dec["m4-12"][1][3]
    n = len(hx_keys)
    bounds = np.linspace(0, n, N_BLOCKS + 1).round().astype(int)
    rows = []
    for b, (bid, kind, target, what) in enumerate(SCHEDULE):
        lo, hi = int(bounds[b]), int(bounds[b + 1])
        chk = list(range(lo, min(lo + N_CHECK, hi)))
        phc = list(range(lo + N_CHECK, hi))
        if kind == "decoder":
            cand = ("m4-12" if live == "m4-13" else "m4-13") if target == "other" else target
        elif kind == "recal":
            cand = live
        else:
            cand = target
        (ccx, cct, ccph, _), (chx, cht, chph, _) = dec[cand]
        ht = [norm(t) for t in cht]
        # simulated user on the check block: the candidate runs offer-only; truth if accepted or retyped
        truths, sources = [], []
        cand_x = [chx[i] for i in chk]
        champ_x = [dec[live][1][0][i] for i in chk]
        offers = [guard._decide_quiet(x) for x in cand_x]  # top-5 of the candidate route (live config; offer only)
        for i, r in zip(chk, offers):
            fb = user.respond_offer([norm(c) for c in r.choices], ht[i], rng_user)
            truths.append(ht[i] if fb.truth_known else UNKNOWN)
            sources.append(fb.source)
        version = f"{bid}-{cand}" + (f"-recal{b}" if kind == "recal" else "")
        cfg_before = guard.config_id
        out = up.propose_calibration(
            ccx, cct, cand_x, truths, champion_inputs=None if kind == "recal" else champ_x,
            check_ids=[("val_eval", hx_keys[i]) for i in chk], cal_ids=[("val_select", k) for k in dec[cand][0][3]],
            version=version, session=bid, stream_texts=ccph, decoder_name=cand,
            name=f"p15-03a-{tag}-{bid}", seed=seed + 100 * (b + 1), null_trials=NULL_CAND, **kw)
        accepted = out.accepted
        if accepted and kind != "recal":
            live = cand
        rec = out.record
        ptest = per_test(cand_x, champ_x, [dec["m4-12"][1][2][i] for i in chk]) if kind == "decoder" else None
        # phase C: the live guard decides on the live decoder's logits
        lx = dec[live][1][0]
        res = [guard._decide_quiet(lx[i]) for i in phc]
        com = [(r, ht_i) for r, ht_i in zip(res, [norm(dec[live][1][1][i]) for i in phc]) if r.action == "commit"]
        wrong = sum(norm(r.text) != t for r, t in com)
        rows.append({
            "block": bid, "what": what, "kind": kind, "candidate": cand, "live_after": live, "accepted": accepted,
            "reasons": list(out.reasons), "config_changed": guard.config_id != cfg_before,
            "commit_p_before": out.to_dict()["commit_p_before"], "commit_p_after": out.to_dict()["commit_p_after"],
            "lambda_session": None if rec is None or not math.isfinite(rec.lambda_session) else rec.lambda_session,
            "controls": [] if rec is None else [c.to_dict() for c in rec.controls],
            "challenger_test": None if rec is None or rec.challenger_test is None else rec.challenger_test.to_dict(),
            "per_test": ptest, "check_items": len(chk),
            "check_truth_known": int(sum(t != UNKNOWN for t in truths)),
            "check_sources": {s: sources.count(s) for s in sorted(set(sources))},
            "phase_c_items": len(phc), "phase_c_commits": len(com), "phase_c_wrong_commits": int(wrong),
        })
        log(f"{tag} {bid} {kind} {cand}: accepted={accepted} live={live} commits {len(com)}/{len(phc)} wrong {wrong} "
            f"reasons={list(out.reasons)} challenger={rows[-1]['challenger_test']} per={ptest}")
    ver = verify(led_path, expected_head=ledger.anchor())
    stages = [e["body"]["stage"] for e in ledger.entries if e["kind"] == "update"]
    nc = sum(r["phase_c_items"] for r in rows)
    k = sum(r["phase_c_commits"] for r in rows)
    w = sum(r["phase_c_wrong_commits"] for r in rows)
    return {
        "seed": seed, "user": user_name, "rows": rows, "initial_config_id": up.outcomes[0].config_id_before,
        "final_config_id": guard.config_id, "final_live": live,
        "n_proposed": stages.count("proposed"), "n_accepted": stages.count("accepted"),
        "n_rejected": stages.count("rejected"), "ledger_verify_ok": ver.ok, "ledger_errors": ver.errors[:5],
        "every_proposal_decided": stages.count("proposed") == stages.count("accepted") + stages.count("rejected"),
        "guard_unchanged_on_reject": all(not r["config_changed"] for r in rows if not r["accepted"]),
        "phase_c_items": nc, "phase_c_commits": k, "phase_c_wrong_commits": w,
        "phase_c_wrong_commit_rate": w / nc if nc else None, "phase_c_wrong_commit_cp95": clopper_pearson(w, nc, 0.95),
        "phase_c_precision": (k - w) / k if k else None, "seconds": round(time.time() - t0, 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1])
    ap.add_argument("--users", nargs="+", default=list(USERS))
    a = ap.parse_args()
    t0 = time.time()
    dec = load_decoders()
    m14 = K.load_module("p14_03_run", REPO / "experiments/2026-11-16-p14-03-replay-validation/run.py")
    wdec, _ = K.word_decoder()
    fn = m14.make_decode_fn(wdec)
    path = OUT / "results.json"
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr.update(fidetype_version=FT_VERSION, dry_run=DRY, provenance=K.provenance("m4-12") | {"m4-13": None if DRY else K.provenance("m4-13")},
                n_cal=len(dec["m4-12"][0][0]), n_held=len(dec["m4-12"][1][0]), schedule=SCHEDULE)
    allr.setdefault("runs", {})
    log(f"start: seeds {a.seeds}, users {a.users}, cal {allr['n_cal']}, held {allr['n_held']}, dry {DRY}")
    for s in a.seeds:
        for u in a.users:
            tag = f"s{s}-{u}"
            if tag in allr["runs"]:
                log(f"{tag}: done before, skip")
                continue
            allr["runs"][tag] = run_one(s, u, dec, fn)
            path.write_text(json.dumps(allr, indent=1, default=str), encoding="utf-8")
            r = allr["runs"][tag]
            log(f"{tag}: done {json.dumps({k: r[k] for k in ('final_live', 'n_accepted', 'n_rejected', 'ledger_verify_ok', 'phase_c_commits', 'phase_c_wrong_commits', 'seconds')})}")
    log(f"all done in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
