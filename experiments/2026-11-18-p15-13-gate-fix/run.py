"""P15-13: replay of the P15-03a champion / challenger design with the default-deny gate (plan: plan.md). Our own code.

Same design as experiments/2026-11-17-p15-03-f1-m4-13/run.py (P15-03a): T15 val_eval in (session, index) order,
7 contiguous blocks; block b = 48 offer-only check items (proposal b) + phase C (the live guard decides). The
decoders are the recorded log-probs of M4-12 fixed0 (weaker), M4-13 long0 best.pt (stronger) and the broken
decoder (time-reversed M4-13). Changes against P15-03a (fixed in plan.md):

- the loop uses the P15-13 default gate (``challenger_test="noninferiority"``, level 0.05, margins 0.1 / 0.1);
- the simulated user's unknown truth is passed as unknown (``None``) and the rejected offer list as
  ``check_rejected`` (before: a sentinel text that counted as wrong for both sides);
- a weak-champion probe W per run: the broken decoder proposed against the start guard (M4-12 live) on the
  B3 check block, once through the new gate and once through the P15-02 sign test (two separate loops on
  copies of the start guard; the main run is not changed by it);
- the per-item PER test (descriptive) is also computed for the broken decoder and on known-truth items only.

    run.py [--seeds 0 1] [--users oracle feedback-r0.3] [--gate noninferiority|sign]

Per-run JSON in results/results.json (resumable per run). Ledgers: C:/Users/zhang/bci-data/derived/p15-13-gate-fix/.
Dry run (plumbing only; both "decoders" are M4-12, labels mean nothing): TRUST_RERUN_DRY=1 TRUST_RERUN_SOURCE=m4-12
TRUST_RERUN_NCAL=160 TRUST_RERUN_NHELD=360 run.py --seeds 0 --users feedback-r0.3 --max-blocks 3
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
from fidetype.trust.dropin import TrustGuard  # noqa: E402
from fidetype.trust.provenance import ProvenanceLedger, verify  # noqa: E402
from fidetype.trust.update_hooks import TrustGuardUpdater  # noqa: E402
from fidetype.utils.binomial import clopper_pearson  # noqa: E402

DRY = K.is_dry()
SRC = K.source_name()
if not DRY:
    assert SRC == "m4-13", "a real run uses the M4-13 outputs"
OWN = K.DER / "p15-13-gate-fix" / ("dryrun" if DRY else "")
assert not any(f == OWN or f in OWN.parents for f in K.FOREIGN + list(K.OWN_ROOTS.values())), OWN
OWN.mkdir(parents=True, exist_ok=True)
OUT = HERE / ("results/dryrun-" + SRC if DRY else "results")
OUT.mkdir(parents=True, exist_ok=True)
log = K.Logger(OUT / "run.log")

ALPHA, DELTA = 0.05, 0.1
N_BLOCKS = 7
N_CHECK = 48
NULL_INIT, NULL_CAND, NULL_LOOP = 300, 100, 100
LEVEL, MARGIN, MARGIN_ABS = 0.05, 0.1, 0.1  # fixed in plan.md before any run
USERS = {"oracle": FeedbackUser(p_retype=1.0), "feedback-r0.3": FeedbackUser(p_retype=0.3)}
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
    """{name: (cal (xs, texts, ph, keys), held (xs, texts, ph, keys))}; same items and order for every decoder."""
    dec = {}
    if DRY:
        a = K.load_t15("m4-12", norm_text=False, with_keys=True)
        dec["m4-12"] = a
        dec["m4-13"] = a
    else:
        dec["m4-12"] = K.load_t15("m4-12", norm_text=False, with_keys=True)
        dec["m4-13"] = K.load_t15("m4-13", norm_text=False, with_keys=True)
    for p in (0, 1):
        assert dec["m4-12"][p][3] == dec["m4-13"][p][3], "the two decoders must cover the same items in the same order"
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


def per_test(ch_lp, champ_lp, ph, mask=None) -> dict:
    """Descriptive paired test: per-item greedy PER, challenger minus champion (one-sided Wilcoxon)."""
    from scipy.stats import wilcoxon

    idx = [i for i in range(len(ph)) if mask is None or mask[i]]
    a = np.array([char_error_rate(greedy_symbols(ch_lp[i]), ph[i]) for i in idx])
    b = np.array([char_error_rate(greedy_symbols(champ_lp[i]), ph[i]) for i in idx])
    d = a - b
    nz = d[d != 0]
    p_worse = float(wilcoxon(nz, alternative="greater").pvalue) if nz.size >= 10 else None
    p_better = float(wilcoxon(nz, alternative="less").pvalue) if nz.size >= 10 else None
    return {"n": len(idx), "per_challenger": float(a.mean()) if len(idx) else None,
            "per_champion": float(b.mean()) if len(idx) else None, "n_nonzero": int(nz.size),
            "p_worse": p_worse, "p_better": p_better}


def copy_guard(g: TrustGuard) -> TrustGuard:
    return TrustGuard(g.config, g._codec, g.sheet, g._user_decode, g.audit_text)


def make_loop(gate: str, ledger, chain: str) -> GuardedUpdateLoop:
    return GuardedUpdateLoop(alpha=ALPHA, delta=DELTA, n_check=N_CHECK, ledger=ledger, ledger_chain=chain,
                             challenger_test=gate, challenger_level=LEVEL, challenger_margin=MARGIN,
                             challenger_margin_abs=MARGIN_ABS)


def feedback(user, guard, cand_x, texts, rng):
    """The simulated user on the candidate's top-5 offers: (truth or None, rejected list or None, source)."""
    truths, rejected, sources = [], [], []
    for x, t in zip(cand_x, texts):
        offered = [norm(c) for c in guard._decide_quiet(x).choices]
        fb = user.respond_offer(offered, t, rng)
        known = fb.truth_known
        truths.append(t if known else None)
        rejected.append(None if known else offered)
        sources.append(fb.source)
    return truths, rejected, sources


def test_dict(rec):
    return None if rec is None or rec.challenger_test is None else rec.challenger_test.to_dict()


def weak_champion_probe(seed, user, dec, guard0, kw, tag, bounds, rng_seed) -> dict:
    """W: the broken decoder against the start guard (M4-12 live) on the B3 check items, new gate and sign test."""
    b = 2  # B3
    lo, hi = int(bounds[b]), int(bounds[b + 1])
    chk = list(range(lo, min(lo + N_CHECK, hi)))
    (ccx, cct, ccph, ckeys), (chx, cht, _, _) = dec["m4-13-rev"]
    hk = dec["m4-12"][1][3]
    ht = [norm(t) for t in cht]
    cand_x = [chx[i] for i in chk]
    champ_x = [dec["m4-12"][1][0][i] for i in chk]
    cand = ft.calibrate(ccx, cct, alpha=ALPHA, delta=DELTA, stream_texts=ccph, decoder_name="m4-13-rev",
                        name=f"p15-13-{tag}-W", seed=seed + 1000, null_trials=NULL_CAND, **kw)
    truths, rejected, sources = feedback(user, cand, cand_x, [ht[i] for i in chk], np.random.default_rng(rng_seed))
    out = {"check_truth_known": int(sum(t is not None for t in truths)),
           "check_sources": {s: sources.count(s) for s in sorted(set(sources))}}
    for gate in ("noninferiority", "sign"):
        led = ProvenanceLedger(OWN / f"ledger-{tag}-W-{gate}.jsonl")
        g = copy_guard(guard0)
        up = TrustGuardUpdater(g, make_loop(gate, led, f"p15-13-{tag}-W-{gate}"), null_trials=NULL_LOOP,
                               seed=seed + 2, champion_version="m4-12")
        before = g.config_id
        o = up.propose(cand, cand_x, truths, champion_inputs=champ_x, check_rejected=rejected,
                       check_ids=[("val_eval", hk[i]) for i in chk], trained_on=[("val_select", k) for k in ckeys],
                       version="W-m4-13-rev", session="W")
        out[gate] = {"accepted": o.accepted, "reasons": list(o.reasons), "config_changed": g.config_id != before,
                     "challenger_test": test_dict(o.record),
                     "controls": [] if o.record is None else [c.to_dict() for c in o.record.controls],
                     "ledger_verify_ok": verify(led.path, expected_head=led.anchor()).ok}
    out["per_test"] = per_test(cand_x, champ_x, [dec["m4-12"][1][2][i] for i in chk])
    return out


def run_one(seed: int, user_name: str, dec: dict, fn, gate: str, max_blocks: int) -> dict:
    t0 = time.time()
    tag = f"s{seed}-{user_name}"
    rng_user = np.random.default_rng([seed, 1503])
    user = USERS[user_name]
    led_path = OWN / f"ledger-{tag}.jsonl"
    for p in OWN.glob(f"ledger-{tag}*.jsonl"):
        p.unlink()  # one fresh set of ledgers per run (a run is redone as a whole)
    kw = dict(vocab=list(B.SYMBOL_VOCAB), blank=0, input_scale="log_probs", frame_period=0.08, decode_fn=fn,
              modality="intracortical")
    (cx, ct, cph, _), _ = dec["m4-12"]
    guard = ft.calibrate(cx, ct, alpha=ALPHA, delta=DELTA, stream_texts=cph, decoder_name="m4-12-fixed0",
                         name=f"p15-13-{tag}-init", seed=seed, null_trials=NULL_INIT, **kw)
    hx_keys = dec["m4-12"][1][3]
    n = len(hx_keys)
    bounds = np.linspace(0, n, N_BLOCKS + 1).round().astype(int)
    probe = weak_champion_probe(seed, user, dec, guard, kw, tag, bounds, [seed, 1513])
    log(f"{tag} W (broken vs weak champion M4-12): new gate accepted={probe['noninferiority']['accepted']} "
        f"sign accepted={probe['sign']['accepted']} known={probe['check_truth_known']} "
        f"ni={probe['noninferiority']['challenger_test']} sign={probe['sign']['challenger_test']}")
    ledger = ProvenanceLedger(led_path)
    loop = make_loop(gate, ledger, f"p15-13-{tag}")
    up = TrustGuardUpdater(guard, loop, null_trials=NULL_LOOP, seed=seed + 1, champion_version="m4-12")
    live = "m4-12"
    rows = []
    for b, (bid, kind, target, what) in enumerate(SCHEDULE[:max_blocks]):
        lo, hi = int(bounds[b]), int(bounds[b + 1])
        chk = list(range(lo, min(lo + N_CHECK, hi)))
        phc = list(range(lo + N_CHECK, hi))
        if kind == "decoder":
            cand = ("m4-12" if live == "m4-13" else "m4-13") if target == "other" else target
        elif kind == "recal":
            cand = live
        else:
            cand = target
        (ccx, cct, ccph, _), (chx, cht, _, _) = dec[cand]
        ht = [norm(t) for t in cht]
        cand_x = [chx[i] for i in chk]
        champ_x = [dec[live][1][0][i] for i in chk]
        # the user sees the candidate route's top-5 (live config; offer only), as in P15-03a
        truths, rejected, sources = feedback(user, guard, cand_x, [ht[i] for i in chk], rng_user)
        version = f"{bid}-{cand}" + (f"-recal{b}" if kind == "recal" else "")
        cfg_before = guard.config_id
        out = up.propose_calibration(
            ccx, cct, cand_x, truths, champion_inputs=None if kind == "recal" else champ_x,
            check_rejected=rejected,
            check_ids=[("val_eval", hx_keys[i]) for i in chk], cal_ids=[("val_select", k) for k in dec[cand][0][3]],
            version=version, session=bid, stream_texts=ccph, decoder_name=cand,
            name=f"p15-13-{tag}-{bid}", seed=seed + 100 * (b + 1), null_trials=NULL_CAND, **kw)
        accepted = out.accepted
        if accepted and kind != "recal":
            live_before, live = live, cand
        else:
            live_before = live
        rec = out.record
        ph = [dec["m4-12"][1][2][i] for i in chk]
        known = [t is not None for t in truths]
        ptest = ptest_known = None
        if kind in ("decoder", "broken"):
            champ_lp = [dec[live_before][1][0][i] for i in chk]
            ptest = per_test(cand_x, champ_lp, ph)
            ptest_known = per_test(cand_x, champ_lp, ph, known)
        lx = dec[live][1][0]
        res = [guard._decide_quiet(lx[i]) for i in phc]
        com = [(r, t) for r, t in zip(res, [norm(dec[live][1][1][i]) for i in phc]) if r.action == "commit"]
        wrong = sum(norm(r.text) != t for r, t in com)
        rows.append({
            "block": bid, "what": what, "kind": kind, "candidate": cand, "live_before": live_before,
            "live_after": live, "accepted": accepted, "reasons": list(out.reasons),
            "config_changed": guard.config_id != cfg_before,
            "commit_p_before": out.to_dict()["commit_p_before"], "commit_p_after": out.to_dict()["commit_p_after"],
            "lambda_session": None if rec is None or not math.isfinite(rec.lambda_session) else rec.lambda_session,
            "controls": [] if rec is None else [c.to_dict() for c in rec.controls],
            "challenger_test": test_dict(rec), "per_test": ptest, "per_test_known_only": ptest_known,
            "check_items": len(chk), "check_truth_known": int(sum(known)),
            "check_sources": {s: sources.count(s) for s in sorted(set(sources))},
            "phase_c_items": len(phc), "phase_c_commits": len(com), "phase_c_wrong_commits": int(wrong),
        })
        log(f"{tag} {bid} {kind} {cand}: accepted={accepted} live={live} commits {len(com)}/{len(phc)} wrong {wrong} "
            f"known {sum(known)}/{len(chk)} reasons={list(out.reasons)} test={rows[-1]['challenger_test']} "
            f"per={ptest}")
    ver = verify(led_path, expected_head=ledger.anchor())
    stages = [e["body"]["stage"] for e in ledger.entries if e["kind"] == "update"]
    nc = sum(r["phase_c_items"] for r in rows)
    k = sum(r["phase_c_commits"] for r in rows)
    w = sum(r["phase_c_wrong_commits"] for r in rows)
    return {
        "seed": seed, "user": user_name, "gate": gate, "weak_champion_probe": probe, "rows": rows,
        "initial_config_id": up.outcomes[0].config_id_before, "final_config_id": guard.config_id, "final_live": live,
        "loop_config_id": loop.config_id,
        "n_proposed": stages.count("proposed"), "n_accepted": stages.count("accepted"),
        "n_rejected": stages.count("rejected"), "ledger_verify_ok": ver.ok, "ledger_errors": ver.errors[:5],
        "every_proposal_decided": stages.count("proposed") == stages.count("accepted") + stages.count("rejected"),
        "guard_unchanged_on_reject": all(not r["config_changed"] for r in rows if not r["accepted"]),
        "phase_c_items": nc, "phase_c_commits": k, "phase_c_wrong_commits": w,
        "phase_c_wrong_commit_rate": w / nc if nc else None, "phase_c_wrong_commit_cp95": clopper_pearson(w, nc, 0.95),
        "phase_c_precision": (k - w) / k if k else None, "seconds": round(time.time() - t0, 1),
        "peak_mb": K.peak_mb(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1])
    ap.add_argument("--users", nargs="+", default=list(USERS))
    ap.add_argument("--gate", choices=("noninferiority", "sign"), default="noninferiority")
    ap.add_argument("--max-blocks", type=int, default=N_BLOCKS, help="dry runs only")
    a = ap.parse_args()
    if a.max_blocks != N_BLOCKS:
        assert DRY, "--max-blocks is for dry runs only"
    t0 = time.time()
    dec = load_decoders()
    m14 = K.load_module("p14_03_run", REPO / "experiments/2026-11-16-p14-03-replay-validation/run.py")
    wdec, _ = K.word_decoder()
    fn = m14.make_decode_fn(wdec)
    path = OUT / ("results.json" if a.gate == "noninferiority" else f"results-{a.gate}.json")
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr.update(fidetype_version=FT_VERSION, dry_run=DRY, gate=a.gate,
                gate_settings={"level": LEVEL, "margin": MARGIN, "margin_abs": MARGIN_ABS},
                provenance=K.provenance("m4-12") | {"m4-13": None if DRY else K.provenance("m4-13")},
                n_cal=len(dec["m4-12"][0][0]), n_held=len(dec["m4-12"][1][0]), schedule=SCHEDULE)
    allr.setdefault("runs", {})
    log(f"start: seeds {a.seeds}, users {a.users}, gate {a.gate}, cal {allr['n_cal']}, held {allr['n_held']}, "
        f"dry {DRY}")
    for s in a.seeds:
        for u in a.users:
            tag = f"s{s}-{u}"
            if tag in allr["runs"]:
                log(f"{tag}: done before, skip")
                continue
            allr["runs"][tag] = run_one(s, u, dec, fn, a.gate, a.max_blocks)
            path.write_text(json.dumps(allr, indent=1, default=str), encoding="utf-8")
            r = allr["runs"][tag]
            log(f"{tag}: done {json.dumps({k: r[k] for k in ('final_live', 'n_accepted', 'n_rejected', 'ledger_verify_ok', 'phase_c_commits', 'phase_c_wrong_commits', 'seconds', 'peak_mb')})}")
    (OWN / ("DONE-dry" if DRY else "DONE")).write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    log(f"all done in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
