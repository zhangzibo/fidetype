"""P11-12: an acoustic no-signal gate for the P11-11 EMG intended-text guard. CPU only.

Pre-registration: plan.md (this folder). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0. Per-prompt files stay
in C:/Users/zhang/bci-data/derived/p11-12/. The P11-09 and P11-11 files are read only (prompts, log-probs, beam
cache, LM, lexicon, tuned (w, c)). The repo gets aggregates only (no per-user value, no text, no id).

Stages (repo root):

  gate      fit K_MIN, R_MIN, R_MAX on the calibration tuning part (first 765 of calibrate's order).
  guards    fidetype.trust.calibrate per arm (S primary, SL, X) with decode_fn = gate + P11-11 decoder.
  decide    decisions on the evaluation prompts (real, time-shuffled, zero EMG).
  score     safe WPM v0.1 / proposed v0.2, verdicts, aggregates.
  all       every stage in this order.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
os.environ.setdefault("HIP_VISIBLE_DEVICES", "")  # CPU only
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import argparse  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p11-12"  # the only place this task writes per-prompt files
OUT = HERE / "results"
EXP1111 = REPO / "experiments" / "2026-11-19-p11-11-emg-nonvacuous"

# --- pre-registered constants (plan.md) ------------------------------------------------------------
FIT_SHARE = 0.01  # at most floor(0.01 * n_fit) real fit windows below K_MIN / R_MIN
R_MAX_FACTOR = 2.0
ARMS = ("S", "SL", "X")
GATE: dict = {"k_min": None, "r_min": None, "r_max": None}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def p1111():
    """The P11-11 runner as a module. Read-only use: never call its stage functions, log or save_cache."""
    if "p1111run" not in sys.modules:
        load_module("p1111run", EXP1111 / "run.py")
    return sys.modules["p1111run"]


def log(*a: object) -> None:
    OUT.mkdir(exist_ok=True)
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


# --- gate ------------------------------------------------------------------------------------------------


def n_keys(x: np.ndarray) -> int:
    """Greedy CTC emissions: per-frame argmax, runs of one index joined, blank (0) removed."""
    am = np.asarray(x).argmax(1)
    if len(am) == 0:
        return 0
    starts = np.concatenate([[True], am[1:] != am[:-1]])
    return int(((am != 0) & starts).sum())


def kps(x: np.ndarray, frame_s: float = 0.01) -> float:
    T = len(x)
    return n_keys(x) / (frame_s * T) if T else 0.0


def gate_pass(x: np.ndarray, g: dict | None = None) -> bool:
    g = g or GATE
    k = n_keys(x)
    r = k / (0.01 * len(x)) if len(x) else 0.0
    return k >= g["k_min"] and g["r_min"] <= r <= g["r_max"]


def fit_gate(real_k: list[int], real_r: list[float]) -> dict:
    """Plan rule: K_MIN = largest k with #(real < k) <= m; R_MIN = (m+1)-th smallest rate; R_MAX = 2 x max rate."""
    m = int(np.floor(FIT_SHARE * len(real_k)))
    ks = np.asarray(real_k)
    k_min = 0
    for k in range(0, int(ks.max()) + 2):
        if int((ks < k).sum()) <= m:
            k_min = k
        else:
            break
    rs = np.sort(np.asarray(real_r, float))
    return {"k_min": int(k_min), "r_min": float(rs[m]), "r_max": float(R_MAX_FACTOR * rs[-1]), "m": m}


def decode_gated(log_probs: np.ndarray) -> list[tuple[str, float]]:
    """``decode_fn`` of all arms: empty n-best (the guard withholds) if the gate fails, else the P11-11 decoder."""
    if not gate_pass(log_probs):
        return []
    return p1111().decode_intended(log_probs)


# --- stages ----------------------------------------------------------------------------------------------


def setup() -> tuple[list[dict], list[dict], dict]:
    R = p1111()
    rows = R.prompts()
    R.p1109().check_track_splits(R.p1109().sessions())
    tune = load_json(R.OWN / "tune.json")
    R.set_decoder(tune)  # loads the P11-11 beam cache, LM and lexicon (read only)
    cal, ev = R.split_rows(rows)
    return cal, ev, tune


def stage_gate(cal: list[dict]) -> dict:
    f = own("gate.json")
    if f.exists():
        g = load_json(f)
        GATE.update({k: g[k] for k in ("k_min", "r_min", "r_max")})
        return g
    R = p1111()
    W = R.p1109().Windows()
    pos = R.tune_items(len(cal))
    null = set(R.null_pick(len(cal)))
    real = [W.get(cal[i]) for i in pos]
    g = fit_gate([n_keys(x) for x in real], [kps(x) for x in real])
    GATE.update({k: g[k] for k in ("k_min", "r_min", "r_max")})
    shuf = [W.get(cal[i], "shuffled") for i in pos if i not in null]
    g.update(n_fit_real=len(real), n_fit_shuffled_check=len(shuf),
             real_fit_gated=sum(not gate_pass(x) for x in real) / len(real),
             shuffled_fit_pass=sum(gate_pass(x) for x in shuf) / len(shuf),
             tune_digest=R.hashlib.sha256(",".join(map(str, pos)).encode()).hexdigest()[:16])
    save_json(g, f)
    log(f"gate: {g}")
    return g


def stage_guards(cal: list[dict], ev: list[dict], tune: dict, arms: tuple[str, ...]) -> dict:
    import fidetype.trust as ft

    R = p1111()
    W = R.p1109().Windows()
    out = {}
    for arm in arms:
        rec_f = own(f"guard-{arm}.status.json")
        if rec_f.exists():
            out[arm] = load_json(rec_f)
            continue
        t0 = time.time()
        rec: dict = {"arm": arm, "n_cal": len(cal), "n_eval": len(ev), "cal_digest": R.p1109().split_digest(cal),
                     "eval_digest": R.p1109().split_digest(ev), "gate": dict(GATE)}
        xs = [W.get(r) for r in cal]
        texts = [R.intended_truth(r) for r in cal]
        nulls = [W.get(cal[i], "shuffled") for i in R.null_pick(len(cal))]
        try:
            g = ft.calibrate(xs, texts, alpha=R.ALPHA, delta=R.DELTA, input_kind="logits", vocab=R.A.key_ctc_vocab(),
                             blank=0, input_scale="log_probs", frame_period=R.FRAME_S, decode_fn=decode_gated,
                             null_inputs=nulls, decoder_name=R.DECODER_NAME + "+intended-text+nosignal-gate",
                             decoder_version=(f"1-w{tune['w']}-c{tune['c']}-k{GATE['k_min']}-r{GATE['r_min']:.4f}-"
                                              f"{GATE['r_max']:.4f}"),
                             modality="emg", name=f"p11-12-{arm}", seed=R.SEED, audit_text=False, **R.arm_kw(arm))
        except ft.NullControlError as e:
            rec.update(status="refused", reason=str(e)[:2000])
            log(f"guards {arm}: REFUSED ({time.time() - t0:.0f} s): {e}")
        else:
            g.save(own(f"guard-{arm}.json"))
            sh = g.sheet.to_dict()
            rec.update(status="guard", config_id=g.config_id, sheet=sh)
            save_json({"config_id": g.config_id, "sheet": sh, **R.RESEARCH}, OUT / f"guard-{arm}.json")
            log(f"guards {arm}: {g.config_id} ({time.time() - t0:.0f} s)\n{g.sheet}")
        rec["seconds"] = round(time.time() - t0, 1)
        save_json(rec, rec_f)
        out[arm] = rec
    return out


def stage_decide(ev: list[dict], arms: tuple[str, ...]) -> dict:
    from fidetype.trust.dropin import load as load_guard

    R = p1111()
    W = R.p1109().Windows()
    out = {}
    for arm in arms:
        f = own(f"decisions-{arm}.json")
        if f.exists():
            out[arm] = load_json(f)
            continue
        st = load_json(own(f"guard-{arm}.status.json"))
        if st["status"] != "guard":  # type: ignore[index]
            out[arm] = {"status": "refused"}
            save_json(out[arm], f)
            continue
        g = load_guard(own(f"guard-{arm}.json"), decode_fn=decode_gated)
        rec: dict = {"status": "guard", "units": [r["unit"] for r in ev]}
        t0 = time.time()
        for kind in ("real", "shuffled", "zeros"):
            ds = []
            for r in ev:
                x = W.get(r, kind)
                d = R.decide_one(g, x, decode_gated)
                d["gate"] = bool(gate_pass(x))
                if kind == "real":  # top-1 of the ungated decoder (for the gate-cost report)
                    nb = R.decode_intended(x)
                    d["top1_nogate"] = nb[0][0].strip() if nb else ""
                ds.append(d)
            rec[kind] = ds
            log(f"decide {arm} {kind}: {len(ev)} prompts ({time.time() - t0:.0f} s)")
        save_json(rec, f)
        out[arm] = rec
    return out


def stage_score(cal: list[dict], ev: list[dict], tune: dict, gate: dict, arms: tuple[str, ...]) -> dict:
    R = p1111()
    res: dict = {"task": "P11-12", "date": time.strftime("%Y-%m-%d %H:%M"), **R.RESEARCH,
                 "note": "aggregates only (no per-user value, no text, no id)",
                 "tune": {k: tune[k] for k in ("w", "c", "rate", "n_tune", "tune_digest")}, "gate": gate,
                 "eval": {"n_prompts": len(ev), "n_words_intended": sum(len(R.intended_truth(r).split()) for r in ev),
                          "minutes_neural": sum(r["neural_s"] for r in ev) / 60.0}, "arms": {}}
    p9 = load_json(R.P1109 / "guard-P.status.json")
    for arm in arms:
        st = load_json(own(f"guard-{arm}.status.json"))
        a: dict = {"status": st["status"], "cal_digest": st["cal_digest"], "eval_digest": st["eval_digest"]}
        if st["status"] != "guard":
            a["reason"] = st.get("reason")
            res["arms"][arm] = a
            continue
        sh = st["sheet"]
        a["config_id"] = st["config_id"]
        a["sheet"] = {k: sh.get(k) for k in ("alpha", "delta", "n_items", "n_fit", "n_policy", "n_ltt", "feasible",
                                             "commit_threshold", "controls", "warnings", "confidence")}
        d = load_json(own(f"decisions-{arm}.json"))
        a.update(R.score_arm(arm, d, ev, sh))  # P11-11 scoring (CP95 at level 0.95 there, fixed)
        a["verdicts"] = R.verdicts(a, sh, arm)
        truths = [R.intended_truth(r) for r in ev]
        real = d["real"]
        a["gate_cost"] = {
            "real_eval_gated": sum(not x["gate"] for x in real) / len(ev),
            "shuffled_eval_gated": sum(not x["gate"] for x in d["shuffled"]) / len(ev),
            "zeros_eval_gated": sum(not x["gate"] for x in d["zeros"]) / len(ev),
            "top1_exact_nogate": sum(R.same(x["top1_nogate"], t) for x, t in zip(real, truths)) / len(ev),
            "top1_exact_gated": sum(x["gate"] and R.same(x["top1_nogate"], t) for x, t in zip(real, truths)) / len(ev)}
        res["arms"][arm] = a
        log(f"score {arm}: commits {a['n_commits']} wrong {a['n_wrong_commits']} of {len(ev)}; {a['verdicts']}")
    res["digests_match_p1109"] = all(res["arms"][a]["cal_digest"] == p9["cal_digest"] and
                                     res["arms"][a]["eval_digest"] == p9["eval_digest"] for a in arms)
    save_json(res, OUT / "results.json")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stages", nargs="+", choices=("gate", "guards", "decide", "score", "all"))
    ap.add_argument("--arms", default=",".join(ARMS))
    a = ap.parse_args()
    arms = tuple(x for x in a.arms.split(",") if x)
    st = set(a.stages)
    if "all" in st:
        st |= {"gate", "guards", "decide", "score"}
    R = p1111()
    R.keep_awake(True)
    try:
        cal, ev, tune = setup()
        gate = stage_gate(cal)  # always (loads GATE)
        if "guards" in st:
            stage_guards(cal, ev, tune, arms)
        if "decide" in st:
            stage_decide(ev, arms)
        if "score" in st:
            stage_score(cal, ev, tune, gate, arms)
        if "all" in a.stages:
            own("DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
            log("all: DONE")
    finally:
        R.keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
