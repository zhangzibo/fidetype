"""P11-20: shift-robust calibration for the EMG L-FL guard (margin from sessions a -> b). CPU only.

Pre-registration: plan.md (this folder, commit 20b5993). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0.
Per-prompt files and log-probs stay in C:/Users/zhang/bci-data/derived/p11-20/. The P11-01, P11-09, P11-11, P11-14,
P11-17 and P11-18 files are read only. The repo gets aggregates and per-draw counts only (no per-user value, no
text, no id).

    run.py infer            (torch venv) log-probs of personal-val sessions a, b; C2 check on track-val u0
    run.py prompts          prompt rows of sessions a, b; C1 check on the 16 track sessions
    run.py worker 1 <w> <n> phase 1: R01 (X5), M01..M40, P41..P80 (interleaved)
    run.py margin           m and alpha' from the M draws
    run.py worker 2 <w> <n> phase 2: S01..S40 (only S01 if m = 0)
    run.py analyse          metrics, decision rules and intervals -> results/results.json

Only pure helpers of the P11-17 / P11-18 runners are used; their own(), log(), run_draw() and memos are never called.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ.setdefault("HIP_VISIBLE_DEVICES", "")  # CPU only
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p11-20"  # the only place this task writes per-prompt files
P1118D = DER / "p11-18"  # READ ONLY (feat-w*.pkl memos, draw-P*.json)
P1109D = DER / "p11-09"  # READ ONLY (lp/u0-s0-real.npy for C2)
P1101 = DER / "p11-01-emg-decoder"  # READ ONLY (splits, feature cache, labels, personal weights)
E2Q_DATA = Path("C:/Users/zhang/bci-data/raw/emg2qwerty/extracted/emg2qwerty-data-2021-08")  # READ ONLY
EXP1101 = REPO / "experiments" / "2026-11-16-p11-01-emg-decoder"
EXP1118 = REPO / "experiments" / "2026-11-21-p11-18-emg-above-alpha"
OUT = Path(os.environ.get("P1120_OUT", str(HERE / "results")))

# --- pre-registered constants (plan.md) ------------------------------------------------------------
ALPHA = 0.05  # the claim
DELTA = 0.1
K = 40
K2 = 80
J = 40
N_NULL = 300
CTL_MAX = 0.05
NO_BCI = 3.09
TAIL_FRAMES = 20
MIN_GUARD_DRAWS = 30
B_BOOT_FAIL = 9  # P11-17: 9 of 40 bootstrap draws above alpha
C2_PROB_TOL = 1e-3


def log(*a: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def own(*parts: str) -> Path:
    p = OWN.joinpath(*parts)
    assert OWN in p.parents or p == OWN
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def save_json(obj: object, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def keep_awake(on: bool) -> None:
    if os.name != "nt":
        return
    import ctypes

    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def seed_of(tag: str) -> int:
    return int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)


def p18():
    """The P11-18 runner as a module (pure helpers only)."""
    if "p1118run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("p1118run", EXP1118 / "run.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["p1118run"] = m
        spec.loader.exec_module(m)
    return sys.modules["p1118run"]


def p17():
    return p18().p17()


# --- pure helpers (tested on synthetic data) --------------------------------------------------------


def jobs(phase: int, m_zero: bool = False) -> list[dict]:
    if phase == 1:
        js = [{"name": "R01", "arm": "R", "k": 1, "seed": seed_of("p11-18|emg|cal|1"), "ltt_alpha": ALPHA}]
        for k in range(1, K + 1):
            js.append({"name": f"M{k:02d}", "arm": "M", "k": k, "seed": seed_of(f"p11-20|emg|m|{k}"),
                       "ltt_alpha": ALPHA})
            js.append({"name": f"P{K + k:02d}", "arm": "P", "k": K + k, "seed": seed_of(f"p11-18|emg|cal|{K + k}"),
                       "ltt_alpha": ALPHA})
        return js
    n = 1 if m_zero else K
    return [{"name": f"S{k:02d}", "arm": "S", "k": k, "seed": seed_of(f"p11-18|emg|cal|{k}"), "ltt_alpha": None}
            for k in range(1, n + 1)]


def margin_rule(gaps: list[float], n_draws: int = J, alpha: float = ALPHA) -> dict:
    """Plan stage 1: m = max(0, mean gap); alpha' = floor((alpha - m) * 1e4) / 1e4; run arm S or not."""
    g = np.asarray(gaps, float)
    out: dict = {"n_guard": int(len(g)), "n_draws": n_draws}
    if len(g) < MIN_GUARD_DRAWS:
        return {**out, "run_arm_s": False, "reason": f"only {len(g)} of {n_draws} margin draws produced a guard"}
    m = max(0.0, float(g.mean()))
    out.update(mean_gap=float(g.mean()), m=m)
    if m >= alpha:
        return {**out, "run_arm_s": False, "reason": f"m = {m:.4f} >= alpha"}
    ap = math.floor((alpha - m) * 1e4 + 1e-9) / 1e4
    return {**out, "alpha_prime": ap, "m_zero": m == 0.0, "run_arm_s": True}


def primary_conclusion(f_s: int) -> str:
    if f_s <= 1:
        return "margin removes the excess"
    if f_s <= int(np.floor(DELTA * K + 1e-9)):
        return "within delta, excess not removed"
    return "margin not enough"


def assumption_check(mean_test_rate: float, f_s: int) -> str:
    ok = mean_test_rate <= ALPHA and f_s <= int(np.floor(DELTA * K + 1e-9))
    return "(A) not contradicted on test" if ok else "(A) fails on test"


def k80_conclusion(x80: int, n: int = K2) -> dict:
    from scipy.stats import fisher_exact

    p = float(fisher_exact([[B_BOOT_FAIL, K - B_BOOT_FAIL], [x80, n - x80]], alternative="greater")[1])
    lim = int(np.floor(DELTA * n + 1e-9))
    if x80 <= lim and p < 0.05:
        c = "duplicates"
    elif x80 <= lim:
        c = "partly duplicates"
    else:
        c = "noise + shift"
    return {"x80": int(x80), "n": n, "fisher_b40_gt_p80": p, "conclusion": c}


def mcnemar_exact(a: list[bool], b: list[bool]) -> dict:
    """Exact McNemar test (two-sided binomial on the discordant pairs)."""
    from scipy.stats import binomtest

    n01 = int(sum((not x) and y for x, y in zip(a, b)))
    n10 = int(sum(x and (not y) for x, y in zip(a, b)))
    p = float(binomtest(n10, n01 + n10, 0.5).pvalue) if n01 + n10 else 1.0
    return {"a_only": n10, "b_only": n01, "p_two_sided": p}


def session_ab(splits: dict) -> list[dict]:
    """Personal-val sessions a (earlier) and b (later) of each P11-01 test user."""
    out = []
    for i, u in enumerate(splits["test_users"]):
        v = sorted(splits["personal"][u]["val"])
        t = sorted(splits["personal"][u]["test"])
        assert len(v) == 2 and v[1] < t[0], u
        for j, s in zip(("a", "b"), v):
            out.append({"i": i, "j": j, "session": s, "user": u, "split": j})
    return out


# --- stage infer (torch venv) ------------------------------------------------------------------------


def stage_infer() -> int:
    import torch

    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
    keep_awake(True)
    try:
        sys.path.insert(0, str(EXP1101))
        spec = importlib.util.spec_from_file_location("emgdec", EXP1101 / "emgdec.py")
        E = importlib.util.module_from_spec(spec)
        sys.modules["emgdec"] = E
        spec.loader.exec_module(E)
        cfg = load_json(EXP1101 / "config.json")["personal"]["model"]  # type: ignore[index]
        mc = E.ModelCfg(**{**cfg, "dilations": tuple(cfg["dilations"])})
        store = E.SessionStore(P1101)
        sp = load_json(P1101 / "splits.json")
        info = load_json(own("infer.json")) if own("infer.json").exists() else {"sessions": {}}

        def model(i: int):
            m = E.CRT(mc, store.mean, store.std)
            m.load_state_dict(torch.load(P1101 / "train" / f"personal-u{i}" / "best.pt", map_location="cpu",
                                         weights_only=True)["model"])
            m.eval()
            return m

        t_all = time.time()
        if "c2" not in info:  # C2: track-val session of u0 must equal the P11-09 file
            u0 = sp["test_users"][0]  # type: ignore[index]
            s0 = sorted(sp["personal"][u0]["test"])[0]  # type: ignore[index]
            t0 = time.time()
            with torch.no_grad():
                lp = E.session_log_probs(model(0), np.asarray(store.feat(s0)), "cpu")
            ref = np.load(P1109D / "lp" / "u0-s0-real.npy", mmap_mode="r")
            same_shape = tuple(ref.shape) == tuple(lp.shape)
            pd = float(np.abs(np.exp(lp) - np.exp(np.asarray(ref))).max()) if same_shape else float("inf")
            ag = float((lp.argmax(1) == np.asarray(ref).argmax(1)).mean()) if same_shape else 0.0
            info["c2"] = {"frames": int(len(lp)), "same_shape": same_shape, "max_abs_prob_diff": pd,
                          "argmax_agreement": ag, "pass": bool(same_shape and pd <= C2_PROB_TOL and ag == 1.0),
                          "seconds": round(time.time() - t0, 1)}
            save_json(info, own("infer.json"))
            log(f"infer C2: {info['c2']}")
            del lp, ref
        if not info["c2"]["pass"]:
            log("infer: C2 failed; no margin and no arm S result (plan)")
            return 2
        for s in session_ab(sp):  # type: ignore[arg-type]
            tag = f"u{s['i']}-{s['j']}"
            f = own("lp", f"{tag}-real.npy")
            if f.exists():
                continue
            t0 = time.time()
            with torch.no_grad():
                lp = E.session_log_probs(model(s["i"]), np.asarray(store.feat(s["session"])), "cpu")
            tmp = f.with_name(f.stem + ".tmp.npy")
            np.save(tmp, lp.astype(np.float32))
            os.replace(tmp, f)
            info["sessions"][tag] = {"frames": int(len(lp)), "seconds": round(time.time() - t0, 1)}
            save_json(info, own("infer.json"))
            log(f"infer {tag}: {len(lp)} frames ({time.time() - t0:.0f} s)")
            del lp
        info["vocab"] = list(store.vocab)
        save_json(info, own("infer.json"))
        log(f"infer: done ({time.time() - t_all:.0f} s)")
        return 0
    finally:
        keep_awake(False)


# --- stage prompts --------------------------------------------------------------------------------------


def build_rows(ss: list[dict]) -> list[dict]:
    """P11-09 ``stage_prompts`` rule for any list of sessions (no truth-file step)."""
    from fidetype.adapters import emg2qwerty as A
    from fidetype.benchmark import scorecard as SC

    index = load_json(P1101 / "index.json")
    nfr = {r["session"]: int(r["n_frames"]) for r in index["sessions"]}  # type: ignore[index]
    rows: list[dict] = []
    for s in ss:
        with np.load(P1101 / "sessions" / f"{s['session']}.lab.npz", allow_pickle=False) as z:
            plo, phi = z["prompt_lo"].astype(np.int64), z["prompt_hi"].astype(np.int64)
        with A.Session(E2Q_DATA / f"{s['session']}.hdf5") as sess:
            t0, dur = sess.t0, sess.duration_s
            kept = [p for p in sess.prompts if not (p.end - t0 < 0 or p.start - t0 > dur)]
            if len(kept) != len(plo):
                raise SystemExit(f"p11-20: prompt count of u{s['i']}-{s['j']} differs from the P11-01 cache")
            ev = A.key_events(sess)
            for k, pr in enumerate(kept):
                pe = [e for e in A.prompt_events(sess, pr, ev) if A.key_class(e.key) is not None]
                if len(pe) < SC.E2Q_MIN_KEYS:
                    continue
                lo, hi = int(plo[k]), int(phi[k])
                if hi - lo < 2:
                    continue
                rows.append({"i": s["i"], "j": s["j"], "split": s["split"], "session": s["session"],
                             "prompt_index": int(pr.index), "k": k, "lo": lo, "hi": hi,
                             "end": min(hi + TAIL_FRAMES, nfr[s["session"]]),
                             "codes": " ".join(A.key_code(e.key) for e in pe),
                             "neural_s": float(pe[-1].t - pe[0].t)})
    return rows


C1_FIELDS = ("i", "j", "session", "k", "lo", "hi", "end", "codes")


def stage_prompts() -> int:
    R = p17().m14().p1111()
    ref = R.prompts()
    mine = build_rows(R.p1109().sessions())
    same = len(mine) == len(ref) and all(all(a[f] == b[f] for f in C1_FIELDS) for a, b in zip(mine, ref))
    info = load_json(own("infer.json"))
    rows = build_rows(session_ab(load_json(P1101 / "splits.json")))  # type: ignore[arg-type]
    save_json(rows, own("prompts-ab.json"))
    chk = {"c1": {"n_ref": len(ref), "n_mine": len(mine), "pass": bool(same)}, "c2": info["c2"],  # type: ignore[index]
           "n_a": sum(r["j"] == "a" for r in rows), "n_b": sum(r["j"] == "b" for r in rows)}
    chk["pass"] = bool(chk["c1"]["pass"] and chk["c2"]["pass"])
    save_json(chk, own("checks.json"))
    log(f"prompts: {chk}")
    return 0 if chk["pass"] else 2


# --- windows and memo -------------------------------------------------------------------------------------


class Windows:
    """Track windows from P11-09 (read only); session a / b windows from this item's log-probs (real only)."""

    def __init__(self, R) -> None:
        self.base = R.p1109().Windows()
        self._mm: dict[str, np.ndarray] = {}

    def get(self, r: dict, kind: str = "real") -> np.ndarray:
        if r["j"] in ("a", "b"):
            from fidetype.adapters import emg2qwerty as A

            if kind != "real":
                raise ValueError("sessions a / b: real windows only")
            name = f"u{r['i']}-{r['j']}-real.npy"
            if name not in self._mm:
                self._mm[name] = np.load(own("lp", name), mmap_mode="r", allow_pickle=False)
            return A.merge_to_key_ctc(np.asarray(self._mm[name][r["lo"]:r["end"]]), self.base.vocab)
        return self.base.get(r, kind)


def make_analyser(w: int):
    M = p17().m14()

    class Memo(M.Analyser):  # type: ignore[misc, name-defined]
        def load(self) -> None:
            for src in (own(f"feat-w{w}.pkl"), P1118D / f"feat-w{w}.pkl"):
                if src.exists():
                    with open(src, "rb") as fh:
                        self.memo.update(pickle.load(fh))
                    return

        def save(self) -> None:
            f = own(f"feat-w{w}.pkl")
            tmp = f.with_suffix(".tmp")
            with open(tmp, "wb") as fh:
                pickle.dump(self.memo, fh, protocol=4)
            os.replace(tmp, f)
            self.dirty = 0

    an = Memo()
    an.load()
    return an


# --- one draw -----------------------------------------------------------------------------------------


def wrong_on(g, W, R, rows: list[dict]) -> tuple[int, int]:
    com = wrong = 0
    for r in rows:
        d = g.decide(W.get(r))
        if d.action == "commit":
            com += 1
            wrong += int(not R.same(d.text, R.intended_truth(r)))
    return com, wrong


def run_draw(jb: dict, M, R, an, W, cal0: list[dict], ev0: list[dict], ab: list[dict], E: dict) -> dict:
    import fidetype.trust as ft
    from fidetype.benchmark import safe_wpm as SW

    P = p17()
    path = own(f"draw-{jb['name']}.json")
    if path.exists():
        return load_json(path)  # type: ignore[return-value]
    t0 = time.time()
    if jb["arm"] == "M":
        cal = [r for r in ab if r["j"] == "a"]
        ev = [r for r in ab if r["j"] == "b"]
    else:
        cal, ev = cal0, ev0
    n = len(cal)
    L, desired, info = P.draw_order(n, jb["seed"], None)
    n_tune = info["split"][0] + info["split"][1]
    model, n_fit_model = P.fit_model(M, R, an, W, cal, [int(i) for i in desired[:n_tune]])
    fn = M.GuardFn(an, "L-FL", model)
    c = M.DECODERS["FL"]
    name = ("fidetype-p11-01-crt+e2q-keys+inbeam-tatoeba-noE2Q-6gram+lexicon+intended-text+nosignal-gate+conf-L")
    ver = f"p11-14-w{c['w']}-b{c['beta']}-l{c['lam']}-B{c['B']}-L{model.digest()}"
    xs = [W.get(cal[i]) for i in L]
    texts = [R.intended_truth(cal[i]) for i in L]
    if jb["arm"] == "M":
        nulls = None
    else:
        pick = sorted(np.random.default_rng(jb["seed"]).choice(n, size=min(N_NULL, n), replace=False).tolist())
        nulls = [W.get(cal[i], "shuffled") for i in pick]
    res: dict = {**jb, "n_cal": n, "n_eval": len(ev), "draw_info": info,
                 "model": {**model.to_dict(), "digest": model.digest(), "n_fit": n_fit_model,
                           "n_kept": int(np.sum(np.asarray(model.coef) != 0))}}
    try:
        g = ft.calibrate(xs, texts, alpha=jb["ltt_alpha"], delta=DELTA, input_kind="logits", vocab=an.KV, blank=0,
                         input_scale="log_probs", frame_period=R.FRAME_S, decode_fn=fn, null_inputs=nulls,
                         decoder_name=name, decoder_version=ver, modality="emg", name=f"p11-20-{jb['name']}",
                         seed=jb["seed"], audit_text=False)
    except ft.NullControlError as e:
        res.update(status="refused", reason=str(e)[:2000], credited=False, value=0.0,
                   seconds=round(time.time() - t0, 1))
        an.save()
        save_json(res, path)
        log(f"draw {jb['name']}: REFUSED ({res['seconds']} s): {str(e)[:300]}")
        return res
    del xs, nulls
    sh = g.sheet.to_dict()
    ltt_rows = [cal[int(i)] for i in desired[n_tune:]]
    ltt_com, ltt_wrong = wrong_on(g, W, R, ltt_rows)
    common = dict(status="guard", config_id=g.config_id, threshold=sh.get("commit_threshold"),
                  feasible=sh.get("feasible"), sheet_alpha=sh.get("alpha"),
                  ltt_n=len(ltt_rows), ltt_commits=ltt_com, ltt_wrong=ltt_wrong, ltt_rate=ltt_wrong / len(ltt_rows),
                  sheet_ltt_commits=sh.get("ltt_commits"), sheet_ltt_wrong=sh.get("ltt_wrong_commits"),
                  cal_controls=[{k: x.get(k) for k in ("name", "n", "n_commit", "allowed", "passed")}
                                for x in sh.get("controls", [])])
    if jb["arm"] == "M":
        com_b, wrong_b = wrong_on(g, W, R, ev)
        com_v, wrong_v = wrong_on(g, W, R, cal0)  # descriptive only (two-step gap a -> track val)
        res.update(**common, n_commits=com_b, n_wrong=wrong_b, test_rate=wrong_b / len(ev),
                   gap=wrong_b / len(ev) - ltt_wrong / len(ltt_rows), val_commits=com_v, val_wrong=wrong_v,
                   val_rate=wrong_v / len(cal0), seconds=round(time.time() - t0, 1))
        an.save()
        save_json(res, path)
        log(f"draw {jb['name']}: n_a {n} thr {res['threshold']} ltt {ltt_wrong}/{len(ltt_rows)} b {wrong_b}/{len(ev)} "
            f"(commits {com_b}) gap {res['gap']:+.4f} val {wrong_v}/{len(cal0)} "
            f"cal ctl {[x['n_commit'] for x in res['cal_controls']]} ({res['seconds']} s)")
        return res
    dec: dict = {}
    for kind in ("real", "shuffled", "zeros"):
        dec[kind] = []
        for r in ev:
            d = g.decide(W.get(r, kind))
            dec[kind].append({"action": d.action, "text": d.text})
    com = [x["action"] == "commit" for x in dec["real"]]
    cor = [cm and bool(R.same(x["text"], t)) for cm, x, t in zip(com, dec["real"], E["truths"])]
    gu = SW.guarantee_from_sheet(sh)
    gu["alpha"] = ALPHA  # the claim (plan: the margin is part of the method)
    gu["ltt_alpha"] = jb["ltt_alpha"]
    sw = SW.safe_wpm(com, cor, E["nw"], E["nch"], E["ns"], guarantee=gu, controls=SW.controls_from_sheet(sh),
                     gaze_chars_per_min=None)
    ctl = {k: int(sum(x["action"] == "commit" for x in dec[k])) for k in ("shuffled", "zeros")}
    v6 = all(ctl[k] / len(ev) <= CTL_MAX for k in ctl)
    credited = bool(sw["status"] == "certified" and sw["value"] is not None and v6)
    n_wrong = int(sum(cm and not k for cm, k in zip(com, cor)))
    res.update(**common, safe_status=sw["status"], value=float(sw["value"]) if credited else 0.0,
               raw_value=float(sw["value"]) if sw["value"] is not None else None, credited=credited, v6_eval=v6,
               eval_controls=ctl, n_commits=int(sum(com)), n_wrong=n_wrong, test_rate=n_wrong / len(ev),
               above_alpha=bool(n_wrong / len(ev) > ALPHA),
               above_ltt_alpha=bool(n_wrong / len(ev) > jb["ltt_alpha"]), guarantee=gu, committed=com,
               correct=cor, decisions=dec, seconds=round(time.time() - t0, 1))
    an.save()
    save_json(res, path)
    log(f"draw {jb['name']}: alpha' {jb['ltt_alpha']} thr {res['threshold']} commits {res['n_commits']} wrong {n_wrong} "
        f"rate {res['test_rate']:.4f} ltt {ltt_wrong}/{len(ltt_rows)} (sheet {res['sheet_ltt_wrong']}) "
        f"status {sw['status']} credited {credited} eval ctl {ctl} "
        f"cal ctl {[x['n_commit'] for x in res['cal_controls']]} ({res['seconds']} s)")
    return res


def x5_check(d: dict) -> dict:
    ref = load_json(P1118D / "draw-P01.json")
    same = {k: sum(a["action"] == b["action"] and (a["text"] or "") == (b["text"] or "")
                   for a, b in zip(d["decisions"][k], ref["decisions"][k])) for k in ("real", "shuffled", "zeros")}  # type: ignore[index]
    n = d["n_eval"]
    out = {"threshold": d.get("threshold"), "ref_threshold": ref.get("threshold"),  # type: ignore[union-attr]
           "commits": d.get("n_commits"), "ref_commits": ref.get("n_commits"),  # type: ignore[union-attr]
           "wrong": d.get("n_wrong"), "ref_wrong": ref.get("n_wrong"), "same_decisions": same, "n_eval": n}  # type: ignore[union-attr]
    out["pass"] = bool(d.get("status") == "guard" and out["threshold"] == out["ref_threshold"]
                       and out["commits"] == out["ref_commits"] and out["wrong"] == out["ref_wrong"]
                       and all(v == n for v in same.values()))
    return out


def worker(phase: int, w: int, nw: int) -> int:
    keep_awake(True)
    try:
        chk = load_json(own("checks.json"))
        if not chk["pass"]:  # type: ignore[index]
            log("worker: C1 / C2 failed; stop (plan)")
            return 2
        M = p17().m14()
        R, cal, ev = M.setup()
        E = p17().eval_arrays(R, ev)
        ab = load_json(own("prompts-ab.json"))
        W = Windows(R)
        an = make_analyser(w)
        if phase == 1:
            js = jobs(1)
        else:
            mg = load_json(own("margin.json"))
            if not mg["run_arm_s"]:  # type: ignore[index]
                log(f"worker phase 2: arm S not run ({mg.get('reason')})")  # type: ignore[union-attr]
                return 0
            js = [{**jb, "ltt_alpha": mg["alpha_prime"]} for jb in jobs(2, mg["m_zero"])]  # type: ignore[index]
        for i, jb in enumerate(js):
            if i % nw != w:
                continue
            d = run_draw(jb, M, R, an, W, cal, ev, ab, E)  # type: ignore[arg-type]
            if jb["name"] == "R01":
                x5 = x5_check(d)
                save_json(x5, own("x5.json"))
                log(f"X5: {'PASS' if x5['pass'] else 'FAIL'} {x5}")
        return 0
    finally:
        keep_awake(False)


def margin() -> int:
    ds = [load_json(own(f"draw-M{k:02d}.json")) for k in range(1, J + 1)]
    gaps = [d["gap"] for d in ds if d.get("status") == "guard"]  # type: ignore[index, union-attr]
    mg = margin_rule(gaps)
    save_json(mg, own("margin.json"))
    log(f"margin: {mg}")
    return 0


# --- analysis -----------------------------------------------------------------------------------------


def analyse() -> int:
    from fidetype.benchmark import safe_wpm as SW

    P18, P = p18(), p17()
    M = P.m14()
    R, cal, ev = M.setup()
    E = P.eval_arrays(R, ev)
    chk = load_json(own("checks.json"))
    x5 = load_json(own("x5.json"))
    mg = load_json(own("margin.json"))
    rs = lambda xs: P18.rate_stats(xs) if len(xs) else None  # noqa: E731
    dm = [load_json(own(f"draw-M{k:02d}.json")) for k in range(1, J + 1)]
    gm = [d for d in dm if d.get("status") == "guard"]
    st_m: dict[str, int] = {}
    for d in dm:
        st_m[d["status"]] = st_m.get(d["status"], 0) + 1
    stage1 = {"margin": mg, "statuses": st_m, "n_a": dm[0]["n_cal"], "n_b": dm[0]["n_eval"],
              "gap_one_step": rs([d["gap"] for d in gm]), "ltt_rate": rs([d["ltt_rate"] for d in gm]),
              "b_rate": rs([d["test_rate"] for d in gm]), "b_commits": rs([d["n_commits"] for d in gm]),
              "ltt_recount_equals_sheet": sum(d["ltt_wrong"] == d["sheet_ltt_wrong"] for d in gm),
              "threshold_range": [min(d["threshold"] for d in gm), max(d["threshold"] for d in gm)] if gm else None,
              "descriptive_two_step_gap_a_to_val": rs([d["val_rate"] - d["ltt_rate"] for d in gm]),
              "descriptive_val_rate": rs([d["val_rate"] for d in gm]),
              "max_cal_control_commits": max((max(x["n_commit"] for x in d["cal_controls"]) for d in gm), default=None)}
    sig = P18.binom_sig_bound()
    # P11-18 arm P draws (read only)
    p18res = load_json(EXP1118 / "results" / "results.json")
    p18p = {d["name"]: d for d in p18res["draws"] if d["arm"] == "P"}  # type: ignore[index]
    dp_old = [load_json(P1118D / f"draw-P{k:02d}.json") for k in range(1, K + 1)]
    assert all(d["n_wrong"] == p18p[d["name"]]["n_wrong"] for d in dp_old)
    dp_new = [load_json(own(f"draw-P{k:02d}.json")) for k in range(K + 1, K2 + 1)]
    dp80 = dp_old + dp_new
    g80 = [d for d in dp80 if d.get("status") == "guard"]
    x80 = sum(bool(d["above_alpha"]) for d in g80)
    Wt = P.cluster_weights(E["clusters"])

    def interval_block(dd: list[dict]) -> dict:
        prim = P.combined_interval(dd, E["nw"], E["nch"], E["ns"], Wt)
        for d in dd:
            d["keep_above_alpha"] = bool(d.get("status") == "guard" and d.get("v6_eval") and (
                d.get("safe_status") in ("certified", "above-alpha")) and d.get("raw_value") is not None)
        va = P.combined_interval([{**d, "value": d["raw_value"] if d["keep_above_alpha"] else d["value"]}
                                  for d in dd], E["nw"], E["nch"], E["ns"], Wt, credit_key="keep_above_alpha")
        vb = (P.combined_interval([d for d in dd if d.get("credited")], E["nw"], E["nch"], E["ns"], Wt)
              if any(d.get("credited") for d in dd) else None)
        lib_draws = [{"refused": True} if d.get("status") != "guard" or not d.get("v6_eval") else
                     {"committed": d["committed"], "correct": d["correct"], "guarantee": d["guarantee"]} for d in dd]
        lib = SW.calibration_draw_interval(lib_draws, E["nw"], E["nch"], E["ns"], B=2000, seed=0, level=0.95,
                                           reference=NO_BCI)
        lib.pop("draws", None)
        return {"primary": prim, "variant_a_keep_above_alpha": va, "variant_b_credited_only": vb,
                "secondary_library": lib}

    def arm_summary(dd: list[dict]) -> dict:
        g = [d for d in dd if d.get("status") == "guard"]
        st: dict[str, int] = {}
        for d in dd:
            s = d["status"] if d["status"] != "guard" else d["safe_status"]
            st[s] = st.get(s, 0) + 1
        return {"n_draws": len(dd), "n_guard": len(g), "statuses": st,
                "above_alpha": sum(bool(d["above_alpha"]) for d in g),
                "significant_exceedances": sum(d["n_wrong"] >= sig for d in g),
                "test_rate": rs([d["test_rate"] for d in g]), "ltt_rate": rs([d["ltt_rate"] for d in g]),
                "gap": rs([d["test_rate"] - d["ltt_rate"] for d in g]),
                "commits": rs([d["n_commits"] for d in g]), "wrong": rs([d["n_wrong"] for d in g]),
                "threshold_range": [min(d["threshold"] for d in g), max(d["threshold"] for d in g)] if g else None,
                "above_alpha_wrong": sorted(d["n_wrong"] for d in g if d["above_alpha"]),
                "max_eval_control_commits": max((max(d["eval_controls"].values()) for d in g), default=None),
                "max_cal_control_commits": max((max(x["n_commit"] for x in d["cal_controls"]) for d in g),
                                               default=None),
                "v6_fail": sum(not d["v6_eval"] for d in g),
                "ltt_recount_equals_sheet": sum(d["ltt_wrong"] == d["sheet_ltt_wrong"] for d in g)}

    res: dict = {"task": "P11-20", "date": time.strftime("%Y-%m-%d %H:%M"), **M.p1111().RESEARCH,
                 "note": "aggregates and per-draw counts only (no per-user value, no text, no id)",
                 "alpha_claim": ALPHA, "delta": DELTA, "reference_no_bci": NO_BCI, "checks": chk, "x5": x5,
                 "binom_sig_bound_wrong": sig, "stage1": stage1}
    ok = chk["pass"] and x5["pass"]  # type: ignore[index]
    res["checks_pass"] = bool(ok)
    if not ok:
        log("analyse: a must-pass check failed; no arm S / P2 result (plan)")
    # arm S
    if ok and mg["run_arm_s"]:  # type: ignore[index]
        if mg["m_zero"]:  # type: ignore[index]
            s1 = load_json(own("draw-S01.json"))
            res["arm_S_identity_check_S01_equals_P01"] = bool(s1["decisions"] == dp_old[0]["decisions"])  # type: ignore[index]
            ds = dp_old
        else:
            ds = [load_json(own(f"draw-S{k:02d}.json")) for k in range(1, K + 1)]
        ss = arm_summary(ds)
        ss["above_ltt_alpha"] = sum(bool(d.get("above_ltt_alpha", d.get("above_alpha"))) for d in ds
                                    if d.get("status") == "guard")
        f_s = ss["above_alpha"]
        pair = [(d["n_wrong"], o["n_wrong"]) for d, o in zip(ds, dp_old)
                if d.get("status") == "guard" and o.get("status") == "guard"]
        ss["paired_vs_p11_18"] = {
            "n_pairs": len(pair), "wrong_down": sum(a < b for a, b in pair), "wrong_same": sum(a == b for a, b in pair),
            "wrong_up": sum(a > b for a, b in pair),
            "mcnemar_above_alpha_S_vs_P": mcnemar_exact([bool(d["above_alpha"]) for d in ds],
                                                        [bool(o["above_alpha"]) for o in dp_old])}
        res["arm_S"] = ss
        res["interval_S"] = interval_block(ds)
        res["primary_conclusion"] = primary_conclusion(f_s)
        res["assumption_check"] = assumption_check(ss["test_rate"]["mean"], f_s)
        res["verdict_vs_no_bci"] = res["interval_S"]["primary"]["verdict"]
        res["draws_S"] = [{k: d.get(k) for k in ("name", "k", "ltt_alpha", "status", "safe_status", "credited",
                                                 "value", "raw_value", "n_commits", "n_wrong", "test_rate",
                                                 "above_alpha", "above_ltt_alpha", "ltt_wrong", "ltt_rate",
                                                 "threshold", "eval_controls", "seconds")} for d in ds]
    if ok:
        res["arm_P80"] = arm_summary(dp80)
        res["k80"] = k80_conclusion(x80, len(dp80))
        res["interval_P80"] = interval_block(dp80)
        res["draws_P41_80"] = [{k: d.get(k) for k in ("name", "k", "status", "safe_status", "credited", "value",
                                                      "raw_value", "n_commits", "n_wrong", "test_rate", "above_alpha",
                                                      "ltt_wrong", "ltt_rate", "threshold", "eval_controls",
                                                      "seconds")} for d in dp_new]
    res["draws_M"] = [{k: d.get(k) for k in ("name", "k", "status", "n_cal", "n_eval", "threshold", "ltt_n",
                                             "ltt_wrong", "ltt_rate", "n_commits", "n_wrong", "test_rate", "gap",
                                             "val_wrong", "val_rate", "seconds")}
                      | {"cal_controls": [x["n_commit"] for x in d.get("cal_controls", [])]} for d in dm]
    save_json(res, OUT / "results.json")
    log(f"analyse: m {mg.get('m')} alpha' {mg.get('alpha_prime')}; f_S {res.get('arm_S', {}).get('above_alpha')}/40 "  # type: ignore[union-attr]
        f"'{res.get('primary_conclusion')}' '{res.get('assumption_check')}' verdict '{res.get('verdict_vs_no_bci')}'; "
        f"K80 {res.get('k80')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=("infer", "prompts", "worker", "margin", "analyse"))
    ap.add_argument("args", nargs="*", type=int)
    a = ap.parse_args()
    if a.stage == "infer":
        return stage_infer()
    if a.stage == "prompts":
        return stage_prompts()
    if a.stage == "worker":
        phase, w, nw = (list(a.args) + [1, 0, 1][len(a.args):])[:3]
        return worker(phase, w, nw)
    if a.stage == "margin":
        return margin()
    return analyse()


if __name__ == "__main__":
    sys.exit(main())
