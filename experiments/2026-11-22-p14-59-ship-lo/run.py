"""P14-59: three re-checks before `lo_new` ships in the willett-hw LM readout (plan.md, pre-registered).

Usage (repo root; CPU only)::

    C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 2 -- ^
        C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -I experiments/2026-11-22-p14-59-ship-lo/run.py all

Stages: ``cal`` (re-check 1: calibrate the LM guard with lo_new), ``select`` (re-check 2: coherence threshold on S),
``eval`` (re-check 3: recheck_offer_control; test 80 x 5 inputs), ``score`` (rules -> results/results.json), ``all``.
Each stage writes a checkpoint in C:/Users/zhang/bci-data/derived/p14-59 and is skipped when it is done.
Stop: create derived/p14-59/STOP. Our own code (Apache-2.0).
"""
from __future__ import annotations

import os

os.environ.setdefault("FIDETYPE_PRETRAINED_DIR", "C:/Users/zhang/bci-data/pretrained")
os.environ["HIP_VISIBLE_DEVICES"] = ""
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
RES = HERE / "results"
DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p14-59"
P1441 = DER / "p14-41"  # read only
LO_NEW = 0.5659314232741417  # P14-58 results/p58-rule.json
P58_RULE = REPO / "experiments/2026-11-21-p14-57-direction-aware-offer/results/p58-rule.json"
SHIPPED_LO = -1.1697116125105564
SHIPPED_LM_ID = "tcfg-26ae951a20a0cddd"
GUARD_NAME = "willett-hw.lm3.guard.json"
ALPHA, DELTA, SEED = 0.05, 0.1, 0
TEST_KINDS = ("real", "timeshuf", "zero", "frameshuf", "uniform")
FEAT = "coherence"
MAX4, R3_MIN = 4, 36

# reuse the P14-54 helpers (decide, Uniform fast path, control_counts, item_rng, load_lps)
_spec = importlib.util.spec_from_file_location(
    "p1454", REPO / "experiments/2026-11-21-p14-54-willett-order-gate/run.py")
P54 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P54)
P54.OWN, P54.WHICH = OWN, "p59"  # its log() writes to derived/p14-59/run-p59.log


def log(msg: str) -> None:
    P54.log(msg)


def watcher() -> None:
    while True:
        time.sleep(2.0)
        if (OWN / "STOP").exists():
            log("STOP file found: exit 3")
            os._exit(3)


def save_json(obj, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)),
                   encoding="utf-8")
    tmp.replace(p)


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


_MODEL = None


def model():
    global _MODEL
    if _MODEL is None:
        import fidetype.pretrained as ftp

        _MODEL = ftp.load("willett-hw")
    return _MODEL


def new_gate():
    from fidetype.pretrained.lmreadout import gate_from_dict

    rule = load_json(P58_RULE)
    assert rule["lo_new"] == LO_NEW and rule["shipped_lo"] == SHIPPED_LO, "P14-58 rule file differs"
    shipped = gate_from_dict(model().manifest.raw["readouts"]["lm"]["gate"])
    assert shipped.lo == SHIPPED_LO, "manifest gate differs from the shipped lo"
    return shipped, shipped.with_lo(LO_NEW)


def readout():
    return model().lm_readout(gate=new_gate()[1])


def vocab_obj():
    from fidetype.adapters.ctc_logits import vocab_from_list
    from fidetype.pretrained import _xbody

    return vocab_from_list(list(_xbody.VOCAB), blank=0, vocab_type="char",
                           vocab_id=model().manifest.output["vocab_id"])


def load_new_guard(with_gate: bool):
    import fidetype.trust as ft
    from fidetype.trust.offer_gate import OfferGate

    rec = load_json(OWN / "cal.json")
    gp = OWN / GUARD_NAME
    assert sha256(gp) == rec["guard_sha256"], "guard file changed"
    g = ft.load(gp, decode_fn=readout().decode_fn(), offer_gate=False)
    if with_gate:
        sel = load_json(OWN / "select.json")
        g.set_offer_gate([OfferGate(FEAT, float(sel["tau"]), note="P14-59: P14-54 tier-1 rule on S, new guard")])
    return g


def truths(split: str) -> list[str]:
    return [r["truth"] for r in load_json(P1441 / "items.json")[split]]


def test_input(kind: str, i: int, cache) -> np.ndarray:
    lp = cache["real"][i]
    if kind in ("real", "timeshuf", "zero"):
        return cache[kind][i]
    if kind == "frameshuf":
        return lp[P54.item_rng("test", i, "frameshuf").permutation(len(lp))]
    T, V = lp.shape
    z = np.full((T, V), -math.log(V)) + 0.05 * P54.item_rng("test", i, "uniform").standard_normal((T, V))
    return z - np.log(np.exp(z).sum(1, keepdims=True))


# --- stages ----------------------------------------------------------------------------------------------

def stage_cal() -> None:
    import fidetype.trust as ft
    from fidetype.pretrained import _xbody

    if (OWN / "cal.json").exists():
        log("cal: checkpoint found, skipped")
        return
    t0 = time.time()
    lp_val, nulls = P54.load_lps("val", "real"), P54.load_lps("val", "timeshuf")
    texts = truths("val")
    assert len(lp_val) == len(texts) == len(nulls) == 106
    rec: dict = {"alpha": ALPHA, "delta": DELTA, "n_cal": 106, "n_null": 106, "seed": SEED,
                 "gate": new_gate()[1].to_dict(), "decoder_version": "3"}
    log("cal: calibrate the LM guard with lo_new on 106 val sentences")
    try:
        g = ft.calibrate(lp_val, texts, alpha=ALPHA, delta=DELTA, input_kind="logits", vocab=vocab_obj(), blank=0,
                         input_scale="log_probs", frame_period=_xbody.BIN_S, decode_fn=readout().decode_fn(),
                         null_inputs=nulls, decoder_name="fidetype-willett-hw-lm-f", decoder_version="3",
                         modality="intracortical", name="p14-59-willett-hw-lm", seed=SEED, audit_text=False,
                         language="en")
    except ft.NullControlError as e:
        rec.update(status="refused", reason=str(e)[:2000], controls=[c.to_dict() for c in e.report],
                   seconds=round(time.time() - t0, 1))
        save_json(rec, OWN / "cal.json")
        log(f"cal: REFUSED: {e}")
        return
    gp = OWN / GUARD_NAME
    g.save(gp)
    sh = g.sheet.to_dict()
    rec.update(status="guard", config_id=g.config_id, guard_sha256=sha256(gp), guard_size=gp.stat().st_size,
               feasible=sh.get("feasible"), ltt_commits=sh.get("ltt_commits"), n_ltt=sh.get("n_ltt"),
               controls=sh.get("controls"), offers=sh.get("offers"), seconds=round(time.time() - t0, 1))
    save_json(rec, OWN / "cal.json")
    log(f"cal: {g.config_id} ({rec['seconds']} s)")


def stage_select() -> None:
    from fidetype.adapters.ctc_logits import to_log_probs

    if (OWN / "select.json").exists():
        log("select: checkpoint found, skipped")
        return
    if load_json(OWN / "cal.json")["status"] != "guard":
        log("select: no guard (refused), skipped")
        return
    t0 = time.time()
    g = load_new_guard(False)
    sh = g.sheet
    lp_val, lp_ts = P54.load_lps("val", "real"), P54.load_lps("val", "timeshuf")
    S = np.random.default_rng(sh.seed).permutation(sh.n_items)[: sh.n_fit + sh.n_policy]
    real = [P54.decide(g, lp_val[int(i)]) for i in S]
    offers = [r for r in real if r["action"] == "offer"]
    tau = min(r["f"][FEAT] for r in offers)
    log(f"select: S real offers {len(offers)} / {len(S)}; tau {tau:.6g} ({time.time() - t0:.0f} s)")
    rng = np.random.default_rng(P54.SEL_SEED)
    idx = S[rng.integers(0, len(S), size=P54.N_NULL)]
    V, scale = len(g._codec.vocab), g._codec.input_scale
    uni = P54.Uniform(g, "logits")
    could = lambda f: f[FEAT] >= tau  # noqa: E731
    nulls: dict[str, list[dict]] = {"uniform": [], "shuffled": [], "user": []}
    for i in idx:
        T = to_log_probs(lp_val[int(i)], scale).shape[0]
        nulls["uniform"].append(uni(np.full((T, V), -math.log(V)) + 0.05 * rng.standard_normal((T, V)), could))
    for i in idx:
        lp = to_log_probs(lp_val[int(i)], scale)
        nulls["shuffled"].append(P54.decide(g, lp[rng.permutation(lp.shape[0])], "log_probs"))
    nulls["user"] = [P54.decide(g, lp_ts[int(i)]) for i in S]
    oc = P54.control_counts(real, nulls, [(FEAT, tau)], float(sh.null_max_commit_rate))
    out = {"config_id": g.config_id, "S_n": len(S), "S_real_offers": len(offers), "tau": tau,
           "shipped_tau": model().manifest.raw["readouts"]["lm"]["trust"]["offer_gate"]["threshold"],
           "uniform_fast_path": uni.record(),
           "ungated_null_offers": {k: sum(r["action"] == "offer" for r in v if r["decided"]) for k, v in nulls.items()},
           "coherence_min_median_max": {"real_offers": P54.summary(r["f"][FEAT] for r in offers),
                                        **{n: P54.summary(r["f"][FEAT] for r in v) for n, v in nulls.items()}},
           "S_rule": oc, "seconds": round(time.time() - t0, 1)}
    with open(OWN / "select.jsonl", "w", encoding="utf-8") as f:
        for name, recs in [("real", real)] + list(nulls.items()):
            for k, r in enumerate(recs):
                f.write(json.dumps({"set": name, "k": k, **r}) + "\n")
    save_json(out, OWN / "select.json")
    log(f"select: S rule passed {oc['passed']} ({out['seconds']} s)")


def stage_eval() -> None:
    import fidetype.trust as ft
    from fidetype.eval.metrics import edit_distance

    if (OWN / "eval.json").exists():
        log("eval: checkpoint found, skipped")
        return
    if not (OWN / "select.json").exists():
        log("eval: no selection, skipped")
        return
    t0 = time.time()
    g = load_new_guard(True)
    lp_val, lp_ts = P54.load_lps("val", "real"), P54.load_lps("val", "timeshuf")
    rc = ft.recheck_offer_control(g, lp_val, null_inputs=lp_ts)
    rc.update(config_id=g.config_id, offer_gate=[x.to_dict() for x in g.offer_gates],
              seconds=round(time.time() - t0, 1))
    save_json(rc, OWN / "recheck.json")
    log(f"eval: V passed {rc['passed']}: {[(c['name'], c['n_offer'], c['n']) for c in rc['controls']]}, "
        f"real {rc['real']} ({rc['seconds']} s)")
    del lp_val, lp_ts

    t1 = time.time()
    rg = readout()
    tau = float(load_json(OWN / "select.json")["tau"])
    cache = {k: P54.load_lps("test", k) for k in ("real", "timeshuf", "zero")}
    tt = truths("test")
    uni = P54.Uniform(g, None)
    could = lambda f: f[FEAT] >= tau  # noqa: E731
    rows, per = {}, []
    ed = chars = exact = 0
    for kind in TEST_KINDS:
        recs = []
        for i in range(len(cache["real"])):
            x = test_input(kind, i, cache)
            text = rg.text(x)
            r = uni(x, could) if kind == "uniform" else P54.decide(g, x)
            if not r["decided"]:  # fast path: coherence below tau, so not a gated offer
                r["action"], r["gated"] = "withhold", None
            r["readout_gated"] = text == ""
            if kind == "real":
                ed += edit_distance(tt[i], text)
                chars += len(tt[i])
                exact += int(text == tt[i])
            recs.append(r)
            per.append({"kind": kind, "i": i, **r})
        rows[kind] = {"n": len(recs), "commit": sum(r["action"] == "commit" for r in recs),
                      "offer": sum(r["action"] == "offer" for r in recs),
                      "withhold": sum(r["action"] == "withhold" for r in recs),
                      "gated_by_offer_gate": sum(bool(r["gated"]) for r in recs),
                      "readout_gated": sum(r["readout_gated"] for r in recs),
                      "readout_emits": sum(not r["readout_gated"] for r in recs),
                      "decided": sum(r["decided"] for r in recs)}
        rows[kind]["emit"] = rows[kind]["commit"] + rows[kind]["offer"]
        log(f"eval: test {kind}: {rows[kind]} ({time.time() - t1:.0f} s)")
    with open(OWN / "test.jsonl", "w", encoding="utf-8") as f:
        for p in per:
            f.write(json.dumps(p) + "\n")
    out = {"config_id": g.config_id, "test": rows, "uniform_fast_path": uni.record(),
           "real_readout_cer_gated": round(ed / max(1, chars), 4), "real_readout_exact": exact,
           "real_chars": chars, "seconds_test": round(time.time() - t1, 1)}
    save_json(out, OWN / "eval.json")


def stage_score() -> None:
    from fidetype.trust.dropin import ControlResult, offer_control

    cal = load_json(OWN / "cal.json")
    res: dict = {"lo_new": LO_NEW, "shipped_lo": SHIPPED_LO, "shipped_lm_config_id": SHIPPED_LM_ID,
                 "calibration": {k: v for k, v in cal.items() if k != "reason"}}
    if cal["status"] != "guard":
        res["rechecks"] = {"RC1": {"pass": False, "why": "calibrate refused"}, "RC2": {"pass": False},
                           "RC3": {"pass": False}}
        res["ship"] = False
        save_json(res, RES / "results.json")
        log("score: calibrate refused; ship false")
        return
    sel, rc, ev = load_json(OWN / "select.json"), load_json(OWN / "recheck.json"), load_json(OWN / "eval.json")
    T = ev["test"]
    ctrl_ok = all(c["passed"] for c in cal["controls"])
    G1 = {"pass": bool(ctrl_ok and cal["ltt_commits"] == 0),
          "value": {"controls": [(c["name"], c["n_commit"], c["n"], c["passed"]) for c in cal["controls"]],
                    "ltt_commits": cal["ltt_commits"], "feasible": cal["feasible"]}}
    G2 = {"pass": all(T[k]["commit"] == 0 for k in TEST_KINDS), "value": {k: T[k]["commit"] for k in TEST_KINDS}}
    G3 = {"pass": bool(T["real"]["readout_gated"] <= MAX4
                       and all(T[k]["readout_emits"] <= MAX4 for k in ("timeshuf", "zero", "uniform"))),
          "value": {"real_gated": T["real"]["readout_gated"],
                    **{f"{k}_emits": T[k]["readout_emits"] for k in ("timeshuf", "zero", "uniform")}}}
    fs = T["frameshuf"]
    r6 = offer_control(T["real"]["n"], T["real"]["offer"],
                       [ControlResult("shuffled", "test frame-shuffled", fs["n"], fs["commit"],
                                      int(math.floor(0.05 * fs["n"] + 1e-9)), fs["offer"])], rate=0.05)
    S = {"pass": bool(sel["S_rule"]["passed"]),
         "value": [(c["name"], c["n_offer"], c["n"], c["passed"]) for c in sel["S_rule"]["controls"]]}
    R3 = {"pass": rc["real"]["n_offer"] >= R3_MIN, "value": f"{rc['real']['n_offer']} / {rc['real']['n']}"}
    R4 = {"pass": all(T[k]["emit"] <= MAX4 for k in ("timeshuf", "zero", "uniform")),
          "value": {k: T[k]["emit"] for k in ("timeshuf", "zero", "uniform")}}
    R5 = {"pass": T["real"]["gated_by_offer_gate"] <= MAX4, "value": T["real"]["gated_by_offer_gate"]}
    R6 = {"pass": bool(r6["passed"]), "value": {"frameshuf_offers": fs["offer"], "real_offers": T["real"]["offer"],
                                                "p_value": r6["controls"][0]["p_value"]}}
    V1 = {"pass": bool(rc["passed"]), "value": [(c["name"], c["n_offer"], c["n"], c["passed"]) for c in rc["controls"]]}
    V2 = {"pass": bool(rc["commits_match_sheet"] and rc["ltt_commits"] == 0),
          "value": {"commits_match_sheet": rc["commits_match_sheet"], "ltt_commits": rc["ltt_commits"]}}
    rcs = {"RC1": {"rules": {"G1": G1, "G2": G2, "G3": G3}},
           "RC2": {"rules": {"S": S, "R3": R3, "R4": R4, "R5": R5, "R6": R6}, "tau": sel["tau"],
                   "shipped_tau": sel["shipped_tau"]},
           "RC3": {"rules": {"V1": V1, "V2": V2}}}
    for v in rcs.values():
        v["pass"] = all(r["pass"] for r in v["rules"].values())
    res.update(rechecks=rcs, select={k: v for k, v in sel.items() if k != "S_rule"}, recheck=rc, eval=ev,
               new_config_id=cal["config_id"], config_id_changed=cal["config_id"] != SHIPPED_LM_ID,
               ship=all(v["pass"] for v in rcs.values()))
    save_json(res, RES / "results.json")
    log(f"score: RC1 {rcs['RC1']['pass']} RC2 {rcs['RC2']['pass']} RC3 {rcs['RC3']['pass']}; ship {res['ship']}")


def main(argv: list[str]) -> int:
    stage = argv[1] if len(argv) > 1 else "all"
    OWN.mkdir(parents=True, exist_ok=True)
    for p in (OWN / "DONE", OWN / "FAILED"):
        p.unlink(missing_ok=True)
    threading.Thread(target=watcher, daemon=True).start()
    steps = {"cal": [stage_cal], "select": [stage_select], "eval": [stage_eval], "score": [stage_score],
             "all": [stage_cal, stage_select, stage_eval, stage_score]}[stage]
    try:
        for s in steps:
            s()
    except Exception:
        log("FAILED\n" + traceback.format_exc())
        (OWN / "FAILED").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    log(f"end of {stage}; peak {P54.mem_mb()[1]:.0f} MB")
    (OWN / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
