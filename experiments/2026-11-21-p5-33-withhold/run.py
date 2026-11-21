"""P5-33: offer gate that withholds on no-evidence input (plan.md, pre-registered in a7abc11).

Stages (CPU only; run through ``python -m fidetype.utils.isolation run --class background --threads 2 --``):

  t15-select   decide the selection set S (non-LTT items) and the selection nulls; save features
  kt-select    the same for kt-semg-lda (rebuilds the n-best lists as in recheck_kt.py)
  select       apply the selection rule of plan.md to the saved features -> results/selection.json
  t15-eval     re-check the gated t15 guard (recheck_offer_control) and decide val_eval (+ nulls)
  kt-eval      re-check the gated kt guard

Per-item files go to C:/Users/zhang/bci-data/derived/p5-33/ (local only). results/ holds counts only.
"""
from __future__ import annotations

import ctypes
import gc
import json
import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("FIDETYPE_PRETRAINED_DIR", "C:/Users/zhang/bci-data/pretrained")
import numpy as np  # noqa: E402

if sys.platform == "win32":
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)  # keep awake: ES_CONTINUOUS | ES_SYSTEM_REQUIRED

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
REPO = HERE.parents[1]
DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p5-33"
PRE = Path("C:/Users/zhang/bci-data/pretrained")
LM_PATH = PRE / "text" / "eng_tatoeba_6gram_mkn.npz"
LM_NAME = "eng_tatoeba_6gram_mkn.npz"
SEL_SEED, EVAL_SEED = 3305, 3306
N_NULL = 300
KEEP1, KEEP2 = 0.95, 0.975
T15_FEATS = ("coherence", "coherence_ratio", "p_top1", "safety", "peak", "neg_entropy", "nb_share")
KT_FEATS = ("p_top1", "safety", "margin", "conf_mean", "char_lm", "char_lm_best")


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(OWN / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_module(name: str, path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def jdump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, allow_nan=False, default=_clean), encoding="utf-8")


def _clean(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    raise TypeError(type(o))


def fin(v: float) -> float | None:
    return float(v) if math.isfinite(float(v)) else None


# --- data ----------------------------------------------------------------------------------------------------------

def t15_data():
    """(guard, val_select inputs, val_eval keys, inputs) exactly as recheck_t15.py / P14-05."""
    import fidetype.trust as ft

    r05 = load_module("p1405run", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
    p1403 = r05.load_module("p1403run", REPO / "experiments/2026-11-16-p14-03-replay-validation/run.py")
    sessions = json.loads((DER / "m4-01-02-lookahead" / "sessions.json").read_text(encoding="utf-8"))
    cal_p = DER / "trust-reruns-m4-13" / "logprobs-m4-13-long0-val_select.npz"
    held_p = DER / "m4-13" / "logprobs-m4-13-long0-val_eval.npz"
    z = np.load(cal_p)
    cx = [z[k].astype(np.float32) for k in r05.t15_keys(cal_p, sessions, "val_select")]
    zh = np.load(held_p)
    hkeys = r05.t15_keys(held_p, sessions, "val_eval")
    hx = [zh[k].astype(np.float32) for k in hkeys]
    bt = r05.load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    tune = bt.load_json("tune.json")
    dec = bt.Decoders([], {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    fn = p1403.make_decode_fn(dec)
    guard = ft.load(REPO / "src/fidetype/pretrained/guards/t15-m4-13.guard.json", decode_fn=fn, offer_gate=False)
    return guard, cx, hkeys, hx


def kt_data():
    """(guard, n-best lists, P5-31 user nulls, key-window pool, truth lengths), as recheck_kt.py."""
    import fidetype.trust as ft
    from fidetype.adapters import kt_semg as K
    from fidetype.live import build as Bd
    from fidetype.live.model import load_model
    from fidetype.live.runner import nbest_of_frames
    from fidetype.live.sources import ArraySource

    model = load_model(PRE / "kt-semg-lda" / "kt-semg-lda.model.json")
    runs = Bd._kt_runs("C:/Users/zhang/bci-data/raw/kt-semg")
    by_id = {r["id"]: r for rs in runs.values() for r in rs}
    nbs, texts, pools = [], [], []
    for rid in ["run14", "run15", "run16", "run19", "run22", "run23"]:
        r = by_id[rid]
        rec = K.read_emg_csv(r["csv"])
        ev = Bd.kt_run_events(r["csv"], r["keys"], r["ts"], rec.n_samples)
        segs = Bd.kt_segments(ev)
        src = ArraySource(rec.emg, K.SAMPLE_RATE_HZ, Bd.kt_markers(ev, segs), speed=0, chunk_s=0.5)
        nbs += Bd.collect_nbests(model, src)
        texts += [Bd.kt_text(ev[a:b]) for a, b in segs]
        times = [ev[i].t for a, b in segs for i in range(a, b)]
        sc = model.new_scaler()
        pools.append(model.log_proba(sc.update_transform(model.features(rec.emg, times))))
        log(f"kt {rid}: {len(segs)} bursts")
        del rec, src
        gc.collect()
    pool = np.concatenate(pools)

    def nulls_for(lengths, seed):
        rng = np.random.default_rng(seed)
        out = []
        for k in lengths:
            k = max(1, k)
            idx = rng.integers(0, len(pool), size=k)
            out.append(nbest_of_frames(pool[idx], np.arange(k) * 0.25))
        return out

    lengths = [len(t) for t in texts]
    p531_nulls = nulls_for(lengths, 0)  # the P5-31 user nulls (same draw order as recheck_kt.py)
    guard = ft.load(PRE / "kt-semg-lda" / "kt-semg-lda.guard.json", offer_gate=False)
    return guard, nbs, p531_nulls, nulls_for, lengths


def split_of(guard, n: int):
    sh = guard.sheet
    order = np.random.default_rng(sh.seed).permutation(n)
    return [int(i) for i in order[:sh.n_fit + sh.n_policy]], [int(i) for i in order[sh.n_fit + sh.n_policy:]]


def decide_rows(guard, xs, scale=None, tag=""):
    guard.collect_offer_features = True
    rows = []
    t0 = time.time()
    for j, x in enumerate(xs):
        r = guard._decide_quiet(x, scale)
        rows.append({"action": r.action, "f": {k: fin(v) for k, v in (guard.last_offer_features or {}).items()}})
        if j and j % 100 == 0:
            log(f"  {tag} {j}/{len(xs)} ({time.time() - t0:.0f} s)")
    return rows


def t15_nulls(guard, inputs, idx_pool, seed):
    """300 uniform and 300 frame-shuffled inputs, recipe of dropin._run_controls, indices from idx_pool."""
    from fidetype.adapters.ctc_logits import to_log_probs

    rng = np.random.default_rng(seed)
    V = len(guard._codec.vocab)
    scale = guard._codec.input_scale
    pick = [idx_pool[int(i)] for i in rng.integers(0, len(idx_pool), size=N_NULL)]
    uni = []
    for i in pick:
        T = to_log_probs(inputs[i], scale).shape[0]
        uni.append(np.full((T, V), -math.log(V)) + 0.05 * rng.standard_normal((T, V)))
    shu = []
    for i in pick:
        lp = to_log_probs(inputs[i], scale)
        shu.append(lp[rng.permutation(lp.shape[0])])
    return uni, shu


def kt_uniform(inputs, idx_pool, seed):
    from fidetype.adapters.text_nbest import normalise_item
    from fidetype.trust.dropin import _nbest_items

    rng = np.random.default_rng(seed)
    pick = [idx_pool[int(i)] for i in rng.integers(0, len(idx_pool), size=N_NULL)]
    return [[{"text": it["text"], "score": 0.0} for it in (normalise_item(x) for x in _nbest_items(inputs[i]))]
            for i in pick]


# --- stages --------------------------------------------------------------------------------------------------------

def stage_t15_select() -> None:
    guard, cx, _, _ = t15_data()
    S, _ = split_of(guard, len(cx))
    log(f"t15 select: S = {len(S)} items")
    real = decide_rows(guard, [cx[i] for i in S], tag="t15 S real")
    uni, shu = t15_nulls(guard, cx, S, SEL_SEED)
    ru = decide_rows(guard, uni, "logits", tag="t15 S uniform")
    rs = decide_rows(guard, shu, "log_probs", tag="t15 S shuffled")
    jdump({"real": real, "nulls": {"uniform": ru, "shuffled": rs}}, OWN / "t15-select.json")
    log("t15 select done")


def stage_kt_select() -> None:
    from fidetype.lm import CharNgramLM

    guard, nbs, _, nulls_for, lengths = kt_data()
    guard.offer_lm = CharNgramLM.load(LM_PATH)
    S, _ = split_of(guard, len(nbs))
    log(f"kt select: S = {len(S)} items")
    real = decide_rows(guard, [nbs[i] for i in S], tag="kt S real")
    ru = decide_rows(guard, kt_uniform(nbs, S, SEL_SEED), tag="kt S uniform")
    user = decide_rows(guard, nulls_for([lengths[i] for i in S], SEL_SEED), tag="kt S user")
    jdump({"real": real, "nulls": {"uniform": ru, "shuffled": user}}, OWN / "kt-select.json")
    log("kt select done")


def gated_counts(rows, gates):
    """Number of OFFERs that pass every (feature, threshold) gate."""
    n = 0
    for r in rows:
        if r["action"] != "offer":
            continue
        ok = True
        for f, t in gates:
            v = r["f"].get(f)
            v = -math.inf if v is None else v
            ok &= v >= t
        n += ok
    return n


def evaluate_gates(data, gates):
    from fidetype.trust.dropin import ControlResult, offer_control

    real = data["real"]
    k_real = gated_counts(real, gates)
    ctr = [ControlResult(name, "", len(rows), 0, 0, gated_counts(rows, gates)) for name, rows in data["nulls"].items()]
    oc = offer_control(len(real), k_real, ctr, rate=0.05)
    worst = max(c["offer_rate"] for c in oc["controls"])
    return oc, worst


def threshold(rows, feat, keep):
    vals = sorted(-math.inf if r["f"].get(feat) is None else r["f"][feat] for r in rows if r["action"] == "offer")
    vals = [v for v in vals if math.isfinite(v)] or [-math.inf]
    i = int(math.floor((1 - keep) * len(vals) + 1e-9))
    return vals[min(i, len(vals) - 1)]


def stage_select() -> None:
    out = {}
    for name, feats in (("t15-m4-13", T15_FEATS), ("kt-semg-lda", KT_FEATS)):
        data = json.loads((OWN / f"{name.split('-')[0]}-select.json").read_text(encoding="utf-8"))
        n_off = sum(r["action"] == "offer" for r in data["real"])
        tier1 = []
        for f in feats:
            t = threshold(data["real"], f, KEEP1)
            oc, worst = evaluate_gates(data, [(f, t)])
            tier1.append({"feature": f, "threshold": t, "passed": oc["passed"], "worst_null_rate": worst,
                          "real_offers": oc["real"]["n_offer"],
                          "nulls": {c["name"]: f"{c['n_offer']}/{c['n']}" for c in oc["controls"]}})
        ok = [c for c in tier1 if c["passed"]]
        choice, tier2 = None, None
        if ok:
            best = min(ok, key=lambda c: (c["worst_null_rate"], feats.index(c["feature"])))
            choice = {"tier": 1, "gates": [[best["feature"], best["threshold"]]]}
        else:
            two = sorted(tier1, key=lambda c: (c["worst_null_rate"], feats.index(c["feature"])))[:2]
            g2 = [(c["feature"], threshold(data["real"], c["feature"], KEEP2)) for c in two]
            oc, worst = evaluate_gates(data, g2)
            tier2 = {"gates": g2, "passed": oc["passed"], "worst_null_rate": worst,
                     "real_offers": oc["real"]["n_offer"],
                     "nulls": {c["name"]: f"{c['n_offer']}/{c['n']}" for c in oc["controls"]}}
            if oc["passed"]:
                choice = {"tier": 2, "gates": [list(g) for g in g2]}
        info = None
        if choice is None:
            b = min(tier1, key=lambda c: (c["worst_null_rate"], feats.index(c["feature"])))
            info = {"tier": 1, "gates": [[b["feature"], b["threshold"]]], "note": "for information only"}
        out[name] = {"n_real": len(data["real"]), "n_real_offer": n_off, "tier1": tier1, "tier2": tier2,
                     "choice": choice, "info_only": info}
        log(f"{name}: choice {choice} (info {info})")
    jdump(out, RES / "selection.json")


def gates_for(name: str, lm=None):
    from fidetype.trust.offer_gate import OfferGate

    sel = json.loads((RES / "selection.json").read_text(encoding="utf-8"))[name]
    ch = sel["choice"] or sel["info_only"]
    note = f"P5-33 tier {ch['tier']}" + ("" if sel["choice"] else " (failed selection; information only)")
    gs = []
    for f, t in ch["gates"]:
        kw = {"lm_name": LM_NAME, "lm": lm} if f in ("char_lm", "char_lm_best") else {}
        gs.append(OfferGate(f, t, note=note, **kw))
    return gs, sel["choice"] is not None


def stage_t15_eval() -> None:
    import fidetype.trust as ft
    from fidetype.trust.dropin import ControlResult, offer_control

    guard, cx, hkeys, hx = t15_data()
    gs, selected = gates_for("t15-m4-13")
    guard.set_offer_gate(gs)
    log(f"t15 eval: gates {[g.label() for g in gs]} (selected {selected})")
    rc = ft.recheck_offer_control(guard, cx)
    rc.update(guard="t15-m4-13", config_id=guard.config_id, offer_gate=[g.to_dict() for g in gs])
    jdump(rc, RES / "recheck-t15-gated.json")
    log(f"t15 recheck: passed {rc['passed']} real {rc['real']} controls "
        f"{[(c['name'], c['n_offer'], c['n']) for c in rc['controls']]}")
    # val_eval (E4): gated decisions; the ungated action is known (a gate withhold was an offer)
    guard.collect_offer_features = True
    ref = json.loads((DER / "p14-05-safe-wpm" / "decisions-t15-m4-13.json").read_text(encoding="utf-8"))
    rows = []
    for i, x in enumerate(hx):
        r = guard._decide_quiet(x)
        ungated = "offer" if guard._offer_gate_why is not None else r.action
        rows.append({"key": hkeys[i], "action": r.action, "ungated": ungated, "text": r.text})
        if i and i % 100 == 0:
            log(f"  val_eval {i}/{len(hx)}")
    jdump(rows, OWN / "t15-val_eval-gated.json")
    same_commits = all(((a["action"] == "commit") == (b["action"] == "commit")) and
                       (a["action"] != "commit" or a["text"] == b["text"]) and a["key"] == b["key"]
                       for a, b in zip(rows, ref)) and len(rows) == len(ref)
    ungated_ref_offers = sum(b["action"] == "offer" for b in ref)
    n_off = sum(r["action"] == "offer" for r in rows)
    n_com = sum(r["action"] == "commit" for r in rows)
    uni, shu = t15_nulls(guard, hx, list(range(len(hx))), EVAL_SEED)
    cnt = {}
    for name, xs, sc in (("uniform", uni, "logits"), ("shuffled", shu, "log_probs")):
        cnt[name] = sum(guard._decide_quiet(x, sc).action == "offer" for x in xs)
        log(f"  val_eval null {name}: {cnt[name]}/{len(xs)} offers")
    oc = offer_control(len(rows), n_off, [ControlResult(k, "", N_NULL, 0, 0, v) for k, v in cnt.items()], rate=0.05)
    out = {"n": len(rows), "commits": n_com, "ref_commits": sum(b["action"] == "commit" for b in ref),
           "same_commits_as_p14_05": same_commits, "offers_gated": n_off,
           "offers_ungated_p14_05": ungated_ref_offers,
           "offers_ungated_this_run": sum(r["ungated"] == "offer" for r in rows),
           "offer_control": oc}
    jdump(out, RES / "val_eval-t15-gated.json")
    log(f"t15 val_eval: {json.dumps({k: v for k, v in out.items() if k != 'offer_control'})} "
        f"null pass {oc['passed']}")


def stage_kt_eval() -> None:
    import fidetype.trust as ft
    from fidetype.lm import CharNgramLM

    guard, nbs, nulls, _, _ = kt_data()
    lm = CharNgramLM.load(LM_PATH)
    gs, selected = gates_for("kt-semg-lda", lm)
    guard.set_offer_gate(gs)
    log(f"kt eval: gates {[g.label() for g in gs]} (selected {selected})")
    rc = ft.recheck_offer_control(guard, nbs, null_inputs=nulls)
    rc.update(guard="kt-semg-lda", config_id=guard.config_id, offer_gate=[g.to_dict() for g in gs])
    jdump(rc, RES / "recheck-kt-gated.json")
    log(f"kt recheck: passed {rc['passed']} real {rc['real']} controls "
        f"{[(c['name'], c['n_offer'], c['n']) for c in rc['controls']]}")


STAGES = {"t15-select": stage_t15_select, "kt-select": stage_kt_select, "select": stage_select,
          "t15-eval": stage_t15_eval, "kt-eval": stage_kt_eval}

if __name__ == "__main__":
    OWN.mkdir(parents=True, exist_ok=True)
    for st in sys.argv[1:]:
        t0 = time.time()
        log(f"stage {st} start")
        STAGES[st]()
        log(f"stage {st} done in {time.time() - t0:.0f} s")
        (OWN / f"{st}.DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
