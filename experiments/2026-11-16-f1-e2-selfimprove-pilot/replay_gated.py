"""P15-02 gated re-run of the P15-01 replay: the same days, arms and settings, with the safe GuardedUpdateLoop.

Changes against replay.py (P15-01), and nothing else:
1. Evidence commit gate on (the loop default ``CommitGate(min_chars=1, max_guard_risk=1.0)``, M2-18). The guard
   risk of each item is ``HallucinationGuard().score(nbest)`` on the word n-best of the M3-28 v2 route (character
   confidences = acoustic frame posteriors; sentence posteriors at the tuned ``T_s``).
2. Per-update null refusal: after the check block, the uniform and frame-shuffled null inputs of the day (same
   inputs as replay.py) go through the new version; a control with commits > floor(alpha * n) rejects the update.
3. Champion / challenger: the champion is the day-start decoder (``<day>-u0``, the weights of phase A); the
   challenger is the phase-A update (``<day>-u1``). Sign test on the check block. A rejected challenger rolls back
   to the champion, which must pass its own null controls; else the day is offer-only. Phase C and the nightly
   update use the active version. Audit records go to the arm JSON (``updates``).

    replay_gated.py ARM [ARM ...]       (frozen, feedback-p0.9, ...; one arm per worker is the plan for P15-02)
    replay_gated.py --probe             (guard risks on a few items of S8 + uniform; no state written)

Outputs: derived  C:/Users/zhang/bci-data/derived/f1-e2-pilot-gated/replay/<arm>/  (state, per-trial records);
repo  results/rerun-gated/arms/<arm>.json. The P15-01 outputs are not touched. Resumable per day.
"""

from __future__ import annotations

import json
import math
import os
import pickle
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATED_OWN = Path("C:/Users/zhang/bci-data/derived/f1-e2-pilot-gated")
os.environ.setdefault("F1E2_ROOT", str(GATED_OWN / "replay"))
os.environ.setdefault("F1E2_ARMS", str(HERE / "results" / "rerun-gated" / "arms"))
(HERE / "results" / "rerun-gated").mkdir(exist_ok=True)

import numpy as np  # noqa: E402
import torch  # noqa: E402

import common as C  # noqa: E402
import replay as R  # noqa: E402  (ROOT / ARMS_OUT now point to the gated folders)
from fidetype.eval.ewpm import SentenceRecord  # noqa: E402
from fidetype.interact.simulated_user import SimulatedUser, UserConfig  # noqa: E402
from fidetype.trust import FeedbackUser  # noqa: E402
from fidetype.trust.adaptive import GuardedUpdateLoop  # noqa: E402
from fidetype.trust.guard import HallucinationGuard  # noqa: E402
from fidetype.trust.policy import Action, Decision  # noqa: E402

L, U, TUNE = R.L, R.U, R.TUNE
GUARD = HallucinationGuard()


class GatedDecoder(R.Decoder):
    """replay.Decoder plus the guard risk of the top-1 sentence."""

    def nbest_risk(self, lp: np.ndarray) -> tuple[list[tuple[str, float]], float]:
        route = self.route
        st = route.NTS(log_probs=np.ascontiguousarray(lp, dtype=np.float32), frame_times=np.arange(lp.shape[0]) * 0.08,
                       vocab=list(route.B.SYMBOL_VOCAB), blank_id=0, vocab_type="phoneme")
        route.dec._wcache = {}
        nb = route.dec.words_fn(st)
        out, seen = [], set()
        for c in nb.candidates:
            t = " ".join(c.text.split())
            if t in seen:
                continue
            seen.add(t)
            out.append((t, float(c.score)))
        if len(nb) == 0:
            return out, 1.0
        s = np.asarray(nb.scores, np.float64) / self.T
        p = np.exp(s - s.max())
        return out, float(GUARD.score(nb, p / p.sum()).risk)

    def run(self, items, W, b) -> list[dict]:
        lps = C.log_probs(self.trunk, W, b, items)
        out = []
        for lp, it in zip(lps, items):
            nb, risk = self.nbest_risk(lp)
            top1 = nb[0][0] if nb else ""
            ok = bool(top1.strip())
            score = C.p_top1([s for _, s in nb], self.T) if ok else -math.inf
            ed, n = (C.edit(list(it["ph"]), C.greedy(lp)), len(it["ph"])) if it["ph"] is not None else (0, 0)
            we, wn = R.word_errors(top1, it["text"])
            out.append({"top1": top1, "text_ok": ok, "score": score, "guard_risk": risk,
                        "offered": [t for t, _ in nb[: L["offer_k"]]],
                        "ph_ed": ed, "ph_n": n, "w_ed": we, "w_n": wn, "right": top1 == it["text"]})
        return out


def null_outputs(dec: GatedDecoder, items, W, b, rng: np.random.Generator) -> tuple[list, list]:
    """The null inputs of replay.null_commits (same RNG use), as (score, text, guard_risk) for the loop."""
    nu, ns = C.CONFIG["null_inputs"]["uniform"], C.CONFIG["null_inputs"]["shuffled"]
    pick = rng.choice(len(items), size=nu + ns, replace=len(items) < nu + ns)
    uni = []
    for j in pick[:nu]:
        T = max(2, C.n_frames_np(items[j]["X"].shape[0]))
        nb, risk = dec.nbest_risk(np.full((T, C.N_OUT), -math.log(C.N_OUT), np.float32))
        top1 = nb[0][0] if nb else ""
        uni.append((C.p_top1([s for _, s in nb], dec.T) if top1.strip() else -math.inf, top1, risk))
    sh = []
    for j in pick[nu:]:
        X = items[j]["X"]
        sh.append({"X": X[rng.permutation(X.shape[0])], "ph": None, "text": items[j]["text"], "id": "null"})
    shuf = [(r["score"], r["top1"], r["guard_risk"]) for r in dec.run(sh, W, b)]
    return uni, shuf


def run_arm(arm: str, trunk, ck, route) -> None:
    st_dir = R.ROOT / arm
    st_dir.mkdir(parents=True, exist_ok=True)
    logf = st_dir / "replay.log"
    cfg = R.arm_settings(arm)
    if cfg["naive"]:
        raise SystemExit("the naive arm has no loop; not part of the gated re-run")
    ch = TUNE["chosen"]
    k_last = len(C.CONFIG["base_sessions"]) - 1
    dec = GatedDecoder(trunk, route, TUNE["sentence_temperature"])
    user = FeedbackUser(p_notice=cfg["p_notice"], p_retype=U["p_retype"], p_sloppy=U["p_sloppy"])
    euser = SimulatedUser(UserConfig.aac_gaze(chars_per_min=C.CONFIG["ewpm"]["chars_per_min"],
                                              p_detect_error=cfg["p_notice"]), seed=U["seed"])
    sf = st_dir / "state.pkl"
    if sf.exists():
        with open(sf, "rb") as f:
            S = pickle.load(f)
        C.log(logf, f"{arm}: resumed after {len(S['days'])} days")
    else:
        S = {"arm": arm, "W": ck["dayW"][k_last].clone(), "b": ck["dayb"][k_last].clone(), "days": [],
             "loop": GuardedUpdateLoop(alpha=L["alpha"], delta=L["delta"], gamma=L["gamma"], eta=L["eta"],
                                       n_check=L["n_check"], lam_init=TUNE["lambda_1"]),  # safe defaults
             "ewpm_records": [], "obs_c": []}
    loop: GuardedUpdateLoop = S["loop"]
    for si in C.CONFIG["replay_sessions"]:
        if any(d["session"] == si for d in S["days"]):
            continue
        if (R.ROOT / "stop").exists():
            C.log(logf, "stop file found")
            return
        t0 = time.time()
        items = C.load_day(si)
        nA, nB = L["n_phase_a"], L["n_check"]
        A, B, Cc = items[:nA], items[nA: nA + nB], items[nA + nB:]
        W_prev, b_prev = S["W"], S["b"]
        recs: list[dict] = []
        extra: dict = {"session": si}
        loop.start_session(si)
        v0, v1 = f"{si}-u0", f"{si}-u1"
        loop.set_champion(v0, trained_on=[])  # day-start weights: trained on earlier days only

        def respond(it, r, idx, phase, can_commit_fn):
            rng = np.random.default_rng([U["seed"], si, idx])
            d = can_commit_fn(r)
            if d is not None and d["commit"]:
                o = user.respond_commit(r["top1"], it["text"], rng)
                action = "commit"
            else:
                o = user.respond_offer(r["offered"], it["text"], rng)
                action = "offer"
            rec = {**r, "id": it["id"], "phase": phase, "action": action, "label": o.label, "source": o.source,
                   "label_correct": o.label_correct, "true_loss": o.true_loss, "silent": o.silent_error,
                   "observed_loss": o.observed_commit_loss, "truth_known": o.truth_known,
                   "text_in_offer": it["text"] in r["offered"]}
            dd = Decision(Action.COMMIT, (r["top1"],), "") if action == "commit" else \
                Decision(Action.OFFER, tuple(r["offered"]) or ("",), "")
            eo = euser.respond(dd, it["text"], can_repeat=False, rng=np.random.default_rng([U["seed"], si, idx, 1]))
            S["ewpm_records"].append(SentenceRecord(it["text"], eo.final_text, eo.communicated,
                                                    euser.typing_time(it["text"]) + eo.time_s, [dd.action.value],
                                                    r["top1"] if action == "commit" else None,
                                                    eo.wrong_commit, eo.silent_error))
            return rec, d

        ra = dec.run(A, W_prev, b_prev)
        for i, (it, r) in enumerate(zip(A, ra)):
            recs.append(respond(it, r, i, "A", lambda r: None)[0])
        # --- update 1 on phase-A labels (the challenger) -------------------------
        if cfg["labels"] is None:
            W1, b1 = W_prev, b_prev
        else:
            labels_rng = np.random.default_rng([si, 1])
            R.labels_for(cfg["labels"], A, recs[:nA], labels_rng, route)
            for it, rec in zip(A, recs):
                rec["lab_used"] = it["lab"] is not None
                if cfg["labels"] == "self" and it["lab"] is not None:
                    rec["label_correct"] = rec["top1"] == it["text"]
            W1, b1 = C.fit_day_layer(trunk, W_prev, b_prev, A, lr=ch["lr"], l2=ch["l2"], steps=ch["steps"],
                                     batch=nA, seed=si)
        loop.new_version(v1, trained_on=[it["id"] for it in A])
        # --- phase B: check block (offer-only), challenger and champion outputs ----
        rb = dec.run(B, W1, b1)
        rb0 = rb if cfg["labels"] is None else dec.run(B, W_prev, b_prev)
        for i, (it, r, r0) in enumerate(zip(B, rb, rb0)):
            rec, _ = respond(it, r, nA + i, "B", lambda r: None)
            recs.append(rec)
            c = None if not rec["truth_known"] else float(r["top1"] != rec["label"])
            c0 = None if not rec["truth_known"] else float(r0["top1"] != rec["label"])
            loop.add_check_item(it["id"], r["score"], c, text=r["top1"], text_ok=r["text_ok"],
                                guard_risk=r["guard_risk"], champion=(r0["score"], c0, r0["guard_risk"], r0["top1"]))
        stt = loop.recalibrate()
        nrng = [C.CONFIG["null_inputs"]["seed"], si]
        uni, shuf = null_outputs(dec, items, W1, b1, np.random.default_rng(nrng))
        loop.check_null_controls(uniform=uni, shuffled=shuf)
        rec1 = loop.finish_update()
        updates = [rec1.to_dict()]
        if not rec1.accepted and loop.version == v0:  # rollback: the champion's own null controls
            uni0, shuf0 = null_outputs(dec, items, W_prev, b_prev, np.random.default_rng(nrng))
            loop.check_null_controls(uniform=uni0, shuffled=shuf0)
            updates.append(loop.finish_update().to_dict())
        active = loop.version
        Wa, ba = (W1, b1) if active == v1 else (W_prev, b_prev)
        ctl = {c.name: c for c in loop.controls}
        live = loop.can_commit
        extra.update({
            "lambda_session": stt.threshold, "lambda_active": loop.lambda_session, "feasible": live,
            "active_version": active, "accepted_challenger": rec1.accepted, "updates": updates,
            "n_block_commits": loop.n_block_commits, "block_wrong_among_commits": loop.block_wrong_among_commits,
            "null_controls": {k: v.to_dict() for k, v in ctl.items()},
            # commits the deployed rule would make on the null inputs (0 when the day cannot commit)
            "null": {"uniform": ctl["uniform"].n_commit if live else 0,
                     "shuffled": ctl["shuffled"].n_commit if live else 0,
                     "n_uniform": ctl["uniform"].n, "n_shuffled": ctl["shuffled"].n},
            "null_raw": {"uniform": ctl["uniform"].n_commit, "shuffled": ctl["shuffled"].n_commit},
            "uniform_guard_risk_min": float(min(x[2] for x in uni)),
            "check_guard_risk_mean": float(np.mean([r["guard_risk"] for r in rb])),
        })
        # --- phase C (active version) -------------------------------------------
        rc = dec.run(Cc, Wa, ba)
        alarms_before = loop.n_alarms
        gated = 0
        for i, (it, r) in enumerate(zip(Cc, rc)):
            def guarded(r):
                d = loop.decide(r["score"], text_ok=r["text_ok"], text=r["top1"], guard_risk=r["guard_risk"])
                return {"commit": d.commit, "d": d}
            rec, d = respond(it, r, nA + nB + i, "C", guarded)
            gated += d["d"].reason == "gate"
            lo = loop.observe(d["d"], rec["observed_loss"] if rec["action"] == "commit" else None)
            if lo is not None:
                S["obs_c"].append(lo)
            recs.append(rec)
        extra["alarm"] = loop.n_alarms > alarms_before
        extra["gate_refusals_c"] = gated
        # --- nightly update on all labels of the day (from the active version) ----
        if cfg["labels"] is not None:
            R.labels_for(cfg["labels"], items, recs, np.random.default_rng([si, 2]), route)
            for it, rec in zip(items, recs):
                rec["lab_used"] = it["lab"] is not None
                if cfg["labels"] == "self" and it["lab"] is not None:
                    rec["label_correct"] = rec["top1"] == it["text"]
            Wn, bn = C.fit_day_layer(trunk, Wa, ba, items, lr=ch["lr"], l2=ch["l2"],
                                     epochs=C.CONFIG["nightly"]["epochs"], batch=C.CONFIG["nightly"]["batch"], seed=si)
            S["W"], S["b"] = Wn, bn
        summ = R.day_summary(recs, extra)
        summ["seconds"] = round(time.time() - t0, 1)
        S["days"].append(summ)
        with open(st_dir / f"records-S{si:02d}.pkl", "wb") as f:  # per-trial: derived only
            pickle.dump(recs, f)
        tmp = st_dir / "state.tmp"
        with open(tmp, "wb") as f:
            pickle.dump(S, f)
        tmp.replace(sf)
        C.log(logf, f"{arm} S{si}: n {summ['n']} PER_C {summ['ph_ed_c'] / max(1, summ['ph_n_c']):.4f} "
                    f"commits {summ['commits']} wrong {summ['wrong_commits']:.0f} lam {extra['lambda_active']} "
                    f"active {active} accepted {rec1.accepted} live {live} null {extra['null_raw']} "
                    f"gate_c {gated} ({summ['seconds']:.0f}s)")
    R.write_arm(arm, S)
    p = R.ARMS_OUT / f"{arm}.json"
    out = json.loads(p.read_text(encoding="utf-8"))
    out["gated_rerun"] = {"commit_gate": loop.commit_gate.to_dict(), "unsafe": loop.unsafe,
                          "report": loop.report(), "updates": loop.audit_records()}
    p.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")


def probe(trunk, ck, route) -> None:
    """Print guard risks and scores on 12 items of S8 and 5 uniform streams (no state written)."""
    k_last = len(C.CONFIG["base_sessions"]) - 1
    dec = GatedDecoder(trunk, route, TUNE["sentence_temperature"])
    items = C.load_day(8)[:12]
    for r in dec.run(items, ck["dayW"][k_last], ck["dayb"][k_last]):
        print(f"real  score {r['score']:.3f} risk {r['guard_risk']:.3f} right {r['right']} top1 {r['top1'][:50]!r}")
    uni, _ = null_outputs(dec, items, ck["dayW"][k_last], ck["dayb"][k_last], np.random.default_rng(0))
    for s, t, rk in uni[:5]:
        print(f"unif  score {s:.3f} risk {rk:.3f} top1 {t[:50]!r}")


def main() -> None:
    args = sys.argv[1:]
    trunk, ck = C.load_base()
    assert C.sha256_file(C.OWN / "base" / "best.pt") == TUNE["base_checkpoint_sha256"]
    route = C.WordRoute()
    torch.manual_seed(0)
    if args == ["--probe"]:
        probe(trunk, ck, route)
        return
    for a in args:
        if a not in R.ARMS or a.endswith("-naive"):
            raise SystemExit(f"unknown or ungated arm {a}")
    for a in args:
        run_arm(a, trunk, ck, route)
        C.log(R.ROOT / "replay.log", f"arm {a} done")


if __name__ == "__main__":
    main()
