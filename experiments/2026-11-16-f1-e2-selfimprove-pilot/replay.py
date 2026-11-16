"""P15-01 replay: 16 T12 days in time order, per arm, with the guarded update loop (plan.md). CPU only.

    replay.py ARM [ARM ...]      arms: frozen feedback-p0.5 feedback-p0.9 feedback-p1.0 oracle selftrain
                                       shuffled-labels feedback-p0.9-naive
State is saved after each day (derived/f1-e2-pilot/replay/<arm>/state.pkl); a restart resumes at the next day.
Per-trial records stay in derived/. The repo gets results/arms/<arm>.json (aggregates per day and in total).
Stop: create derived/f1-e2-pilot/replay/stop (clean stop after the current day).
"""

from __future__ import annotations

import json
import math
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import torch

import common as C
from fidetype.eval.ewpm import SentenceRecord, summarize
from fidetype.interact.simulated_user import SimulatedUser, UserConfig
from fidetype.trust import FeedbackUser, GuardedUpdateLoop
from fidetype.trust.policy import Action, Decision

ROOT = Path(os.environ.get("F1E2_ROOT", str(C.OWN / "replay")))  # override: smoke tests only
ROOT.mkdir(parents=True, exist_ok=True)
ARMS_OUT = Path(os.environ.get("F1E2_ARMS", str(C.RESULTS / "arms")))
ARMS_OUT.mkdir(exist_ok=True)
L = C.CONFIG["loop"]
U = C.CONFIG["user"]
TUNE = json.loads(Path(os.environ.get("F1E2_TUNE", str(C.RESULTS / "tuning.json"))).read_text(encoding="utf-8"))
ARMS = ("frozen", "feedback-p0.5", "feedback-p0.9", "feedback-p1.0", "oracle", "selftrain", "shuffled-labels",
        "feedback-p0.9-naive")


def arm_settings(arm: str) -> dict:
    p = {"feedback-p0.5": 0.5, "feedback-p0.9": 0.9, "feedback-p1.0": 1.0, "feedback-p0.9-naive": 0.9}.get(arm, 0.9)
    src = {"frozen": None, "oracle": "truth", "selftrain": "self", "shuffled-labels": "shuffled"}.get(arm, "feedback")
    return {"p_notice": p, "labels": src, "naive": arm.endswith("-naive")}


def word_errors(hyp: str, ref: str) -> tuple[int, int]:
    return C.edit(hyp.split(), ref.split()), len(ref.split())


class Decoder:
    def __init__(self, trunk, route, T: float) -> None:
        self.trunk, self.route, self.T = trunk, route, T

    def run(self, items, W, b) -> list[dict]:
        lps = C.log_probs(self.trunk, W, b, items)
        out = []
        for lp, it in zip(lps, items):
            nb = self.route.nbest(lp)
            top1 = nb[0][0] if nb else ""
            ok = bool(top1.strip())
            score = C.p_top1([s for _, s in nb], self.T) if ok else -math.inf
            ed, n = (C.edit(list(it["ph"]), C.greedy(lp)), len(it["ph"])) if it["ph"] is not None else (0, 0)
            we, wn = word_errors(top1, it["text"])
            out.append({"top1": top1, "text_ok": ok, "score": score, "offered": [t for t, _ in nb[: L["offer_k"]]],
                        "ph_ed": ed, "ph_n": n, "w_ed": we, "w_n": wn, "right": top1 == it["text"]})
        return out


def labels_for(arm_src: str, items, recs, rng: np.random.Generator, route) -> None:
    """Set it['lab'] (phoneme ids or None) for adaptation, by label source."""
    if arm_src == "truth":
        for it in items:
            it["lab"] = it["ph"]
    elif arm_src == "self":
        for it, r in zip(items, recs):
            it["lab"] = route.phonemes(r["top1"])
    elif arm_src == "feedback":
        for it, r in zip(items, recs):
            it["lab"] = route.phonemes(r["label"])
    elif arm_src == "shuffled":
        known = [it["ph"] for it in items if it["ph"] is not None]
        perm = rng.permutation(len(known))
        k = 0
        for it in items:
            if it["ph"] is not None:
                it["lab"] = known[perm[k]]
                k += 1
            else:
                it["lab"] = None
    else:
        raise ValueError(arm_src)


def null_commits(dec: Decoder, items, W, b, thr: float, rng: np.random.Generator) -> dict:
    """Uniform log-prob streams and frame-shuffled real trials through the current version and threshold."""
    nu, ns = C.CONFIG["null_inputs"]["uniform"], C.CONFIG["null_inputs"]["shuffled"]
    pick = rng.choice(len(items), size=nu + ns, replace=len(items) < nu + ns)
    commits = {"uniform": 0, "shuffled": 0, "n_uniform": nu, "n_shuffled": ns}
    for j in pick[:nu]:
        T = max(2, C.n_frames_np(items[j]["X"].shape[0]))
        nb = dec.route.nbest(np.full((T, C.N_OUT), -math.log(C.N_OUT), np.float32))
        if nb and nb[0][0].strip() and C.p_top1([s for _, s in nb], dec.T) >= thr:
            commits["uniform"] += 1
    sh = []
    for j in pick[nu:]:
        X = items[j]["X"]
        sh.append({"X": X[rng.permutation(X.shape[0])], "ph": None, "text": items[j]["text"], "id": "null"})
    for r in dec.run(sh, W, b):
        if r["text_ok"] and r["score"] >= thr:
            commits["shuffled"] += 1
    return commits


def day_summary(recs: list[dict], extra: dict) -> dict:
    n = len(recs)
    com = [r for r in recs if r["action"] == "commit"]
    pc = [r for r in recs if r["phase"] == "C"]
    pcc = [r for r in pc if r["action"] == "commit"]
    labs = [r for r in recs if r.get("lab_used")]
    s = {
        "n": n, "n_phase_c": len(pc),
        "ph_ed": sum(r["ph_ed"] for r in recs), "ph_n": sum(r["ph_n"] for r in recs),
        "ph_ed_c": sum(r["ph_ed"] for r in pc), "ph_n_c": sum(r["ph_n"] for r in pc),
        "w_ed": sum(r["w_ed"] for r in recs), "w_n": sum(r["w_n"] for r in recs),
        "top1_right": sum(r["right"] for r in recs), "offer_hit": sum(r["text_in_offer"] for r in recs),
        "commits": len(com), "wrong_commits": sum(r["true_loss"] for r in com),
        "observed_wrong": sum(r["observed_loss"] or 0 for r in com), "silent": sum(r["silent"] for r in com),
        "commits_c": len(pcc), "wrong_commits_c": sum(r["true_loss"] for r in pcc),
        "labels": len(labs), "wrong_labels": sum(1 for r in labs if r["label_correct"] is False),
        "label_sources": {},
    }
    for r in recs:
        s["label_sources"][r["source"]] = s["label_sources"].get(r["source"], 0) + 1
    s.update(extra)
    return s


def run_arm(arm: str, trunk, ck, route) -> None:
    st_dir = ROOT / arm
    st_dir.mkdir(parents=True, exist_ok=True)
    logf = st_dir / "replay.log"
    cfg = arm_settings(arm)
    ch = TUNE["chosen"]
    k_last = len(C.CONFIG["base_sessions"]) - 1
    dec = Decoder(trunk, route, TUNE["sentence_temperature"])
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
                                       n_check=L["n_check"], lam_init=TUNE["lambda_1"],
                                       commit_gate=None, unsafe=True),  # P15-01 behaviour (pre-P15-02 loop)
             "ewpm_records": [], "obs_c": []}
    loop: GuardedUpdateLoop = S["loop"]
    for si in C.CONFIG["replay_sessions"]:
        if any(d["session"] == si for d in S["days"]):
            continue
        if (ROOT / "stop").exists():
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

        if cfg["naive"]:
            lam = TUNE["lambda_1"]

            def naive(r):
                return {"commit": r["text_ok"] and r["score"] >= lam}
            ra = dec.run(A, W_prev, b_prev)
            for i, (it, r) in enumerate(zip(A, ra)):
                recs.append(respond(it, r, i, "A", naive)[0])
        else:
            ra = dec.run(A, W_prev, b_prev)
            for i, (it, r) in enumerate(zip(A, ra)):
                recs.append(respond(it, r, i, "A", lambda r: None)[0])
        # --- update 1 on phase-A labels -----------------------------------------
        if cfg["labels"] is None:
            W1, b1 = W_prev, b_prev
        else:
            labels_for(cfg["labels"], A, recs[:nA], np.random.default_rng([si, 1]), route)
            for it, rec in zip(A, recs):
                rec["lab_used"] = it["lab"] is not None
                if cfg["labels"] == "self" and it["lab"] is not None:
                    rec["label_correct"] = rec["top1"] == it["text"]
            W1, b1 = C.fit_day_layer(trunk, W_prev, b_prev, A, lr=ch["lr"], l2=ch["l2"], steps=ch["steps"],
                                     batch=nA, seed=si)
        loop.new_version(f"{si}-u1", trained_on=[it["id"] for it in A])
        # --- phase B: check block (offer-only, new version) -----------------------
        rb = dec.run(B, W1, b1)
        for i, (it, r) in enumerate(zip(B, rb)):
            rec, _ = respond(it, r, nA + i, "B", naive if cfg["naive"] else (lambda r: None))
            recs.append(rec)
            if not cfg["naive"]:
                c = None if not rec["truth_known"] else float(r["top1"] != rec["label"])
                loop.add_check_item(it["id"], r["score"], c)
        if cfg["naive"]:
            thr = TUNE["lambda_1"]
            extra.update({"lambda_session": thr, "feasible": True})
        else:
            stt = loop.recalibrate()
            extra.update({"lambda_session": stt.threshold, "feasible": loop.can_commit})
            thr = loop.threshold
        extra["null"] = null_commits(dec, items, W1, b1, thr, np.random.default_rng(
            [C.CONFIG["null_inputs"]["seed"], si])) if math.isfinite(thr) else \
            {"uniform": 0, "shuffled": 0, "n_uniform": 0, "n_shuffled": 0}
        # --- phase C ------------------------------------------------------------
        rc = dec.run(Cc, W1, b1)
        alarms_before = loop.n_alarms
        for i, (it, r) in enumerate(zip(Cc, rc)):
            if cfg["naive"]:
                rec, _ = respond(it, r, nA + nB + i, "C", naive)
            else:
                def guarded(r):
                    d = loop.decide(r["score"], text_ok=r["text_ok"])
                    return {"commit": d.commit, "d": d}
                rec, d = respond(it, r, nA + nB + i, "C", guarded)
                lo = loop.observe(d["d"], rec["observed_loss"] if rec["action"] == "commit" else None)
                if lo is not None:
                    S["obs_c"].append(lo)
            recs.append(rec)
        extra["alarm"] = loop.n_alarms > alarms_before
        # --- nightly update on all labels of the day ----------------------------
        if cfg["labels"] is not None:
            labels_for(cfg["labels"], items, recs, np.random.default_rng([si, 2]), route)
            for it, rec in zip(items, recs):
                rec["lab_used"] = it["lab"] is not None
                if cfg["labels"] == "self" and it["lab"] is not None:
                    rec["label_correct"] = rec["top1"] == it["text"]
            Wn, bn = C.fit_day_layer(trunk, W1, b1, items, lr=ch["lr"], l2=ch["l2"],
                                     epochs=C.CONFIG["nightly"]["epochs"], batch=C.CONFIG["nightly"]["batch"], seed=si)
            S["W"], S["b"] = Wn, bn
        summ = day_summary(recs, extra)
        summ["seconds"] = round(time.time() - t0, 1)
        S["days"].append(summ)
        with open(st_dir / f"records-S{si:02d}.pkl", "wb") as f:  # per-trial: derived only
            pickle.dump(recs, f)
        tmp = st_dir / "state.tmp"
        with open(tmp, "wb") as f:
            pickle.dump(S, f)
        tmp.replace(sf)
        C.log(logf, f"{arm} S{si}: n {summ['n']} PER_C {summ['ph_ed_c'] / max(1, summ['ph_n_c']):.4f} "
                    f"commits {summ['commits']} wrong {summ['wrong_commits']:.0f} silent {summ['silent']} "
                    f"lam {extra['lambda_session']} alarm {extra['alarm']} null {extra['null']} ({summ['seconds']:.0f}s)")
    write_arm(arm, S)


def write_arm(arm: str, S: dict) -> None:
    days = S["days"]
    tot = {k: sum(d[k] for d in days) for k in ("n", "n_phase_c", "ph_ed", "ph_n", "ph_ed_c", "ph_n_c", "w_ed", "w_n",
                                                 "top1_right", "offer_hit", "commits", "wrong_commits",
                                                 "observed_wrong", "silent", "commits_c", "wrong_commits_c", "labels",
                                                 "wrong_labels")}
    nul = {k: sum(d["null"][k] for d in days) for k in ("uniform", "shuffled", "n_uniform", "n_shuffled")}
    rep = S["loop"].report()
    obs = S["obs_c"]
    es = summarize(S["ewpm_records"])
    out = {
        "arm": arm, "settings": arm_settings(arm), "n_days": len(days), "totals": tot, "null": nul,
        "per_all": tot["ph_ed"] / max(1, tot["ph_n"]), "per_phase_c": tot["ph_ed_c"] / max(1, tot["ph_n_c"]),
        "wer_all": tot["w_ed"] / max(1, tot["w_n"]),
        "true_wrong_commit_rate": tot["wrong_commits"] / tot["n"],
        "true_wrong_commit_cp95": C.cp(int(tot["wrong_commits"]), tot["n"]),
        "observed_wrong_commit_rate": tot["observed_wrong"] / tot["n"],
        "error_among_commits": (tot["wrong_commits"] / tot["commits"]) if tot["commits"] else None,
        "aci": rep["aci"], "observed_mean_loss_c": (float(np.mean(obs)) if obs else None),
        "n_alarms": rep["n_alarms"], "n_feasible_days": sum(bool(d["feasible"]) for d in days),
        "ewpm": es.get("ewpm"), "ewpm_partial": es.get("ewpm_partial"),
        "days": [{k: v for k, v in d.items() if k != "label_sources"} | {"label_sources": d["label_sources"]}
                 for d in days],
    }
    (ARMS_OUT / f"{arm}.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")


def main() -> None:
    arms = sys.argv[1:] or list(ARMS)
    for a in arms:
        if a not in ARMS:
            raise SystemExit(f"unknown arm {a}")
    trunk, ck = C.load_base()
    assert C.sha256_file(C.OWN / "base" / "best.pt") == TUNE["base_checkpoint_sha256"]
    route = C.WordRoute()
    torch.manual_seed(0)
    for a in arms:
        run_arm(a, trunk, ck, route)
        C.log(ROOT / "replay.log", f"arm {a} done")


if __name__ == "__main__":
    main()
