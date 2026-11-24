"""P14-60 (gap 190): re-checks before the `lm_beam_direction >= 0` offer gate ships in both willett-hw guards.

Usage (repo root; CPU only)::

    C:\\venvs\\fidetype-rocm\\Scripts\\python.exe experiments/2026-11-23-p14-60-ship-direction-gate/launch.py

Stages (``all`` = recheck wiring):

- ``recheck``: the P14-56 offer-control re-check (``fidetype.trust.recheck_offer_control``, the P5-31 rule) of each
  shipped guard, built from the packaged manifest (``load("willett-hw").guard()`` and ``guard(readout="lm")``):
  gate list = the shipped ``coherence`` gate, then ``lm_beam_direction >= 0`` with the packaged LM readout
  (``readout=`` wiring). Same inputs as P14-54 / P14-59: the 106 val log-probs and the 106 time-shuffled val inputs
  of P14-41 (read only). Output: ``results/recheck-<guard>-gated.json``.
- ``wiring`` (information only, no rule): the 80 test sentences, real and time-reversed after the decoder
  (``rev_out`` = ``lp[::-1]``), with the shipped gate list and with the coherence gate only. It shows that the
  packaged guards apply the direction gate. The test set was already used (P5-36b), so these counts are not
  evidence for the rule. Output: ``results/wiring.json``.

Log, DONE / FAILED / STOP: C:/Users/zhang/bci-data/derived/p14-60. Our own code (Apache-2.0).
"""
from __future__ import annotations

import os

os.environ.setdefault("FIDETYPE_PRETRAINED_DIR", "C:/Users/zhang/bci-data/pretrained")
os.environ["HIP_VISIBLE_DEVICES"] = ""
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import json  # noqa: E402
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
OWN = Path("C:/Users/zhang/bci-data/derived/p14-60")
LP = Path("C:/Users/zhang/bci-data/derived/p14-41")  # read only
CFG = {"builtin": "tcfg-39aac48688b8bd12", "lm": "tcfg-f498c0637536daec"}
COH = {"builtin": 0.004183090472992479, "lm": 0.003485725778021531}
BEFORE = {"builtin": "experiments/2026-11-21-p14-54-willett-order-gate/results/recheck-builtin-gated.json",
          "lm": "experiments/2026-11-22-p14-59-ship-lo/results/recheck-lm-gated.json"}


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(OWN / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def watcher() -> None:
    while True:
        time.sleep(2.0)
        if (OWN / "STOP").exists():
            log("STOP file found: exit 3")
            os._exit(3)


def save_json(obj, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    tmp.replace(p)


def load_lps(split: str, kind: str) -> list[np.ndarray]:
    with np.load(LP / f"lp_{split}_{kind}.npz") as z:
        return [np.asarray(z[f"arr_{i}"], np.float32) for i in range(len(z.files))]


def guards():
    import fidetype.pretrained as ftp

    m = ftp.load("willett-hw")
    g = {"builtin": m.guard(), "lm": m.guard(readout="lm")}
    for k, x in g.items():
        assert x.config_id == CFG[k], (k, x.config_id)
        labels = [y.label() for y in x.offer_gates]
        assert len(x.offer_gates) == 2, (k, labels)
        assert x.offer_gates[0].feature == "coherence" and x.offer_gates[0].threshold == COH[k], (k, labels)
        assert x.offer_gates[1].feature == "lm_beam_direction" and x.offer_gates[1].threshold == 0.0, (k, labels)
        assert x.offer_gates[1].readout is not None, k
    return m, g


def stage_recheck(m, G) -> None:
    import fidetype.trust as ft

    lp_val, lp_ts = load_lps("val", "real"), load_lps("val", "timeshuf")
    for k in ("lm", "builtin"):  # the LM guard is fast; the built-in uniform controls take about 1.5 h
        out = RES / f"recheck-{k}-gated.json"
        if out.exists():
            log(f"recheck {k}: done before, skipped")
            continue
        t0 = time.time()
        g = G[k]
        rc = ft.recheck_offer_control(g, lp_val, null_inputs=lp_ts)
        rc.update(guard=k, config_id=g.config_id, offer_gate=[x.to_dict() for x in g.offer_gates],
                  built_from="fidetype.pretrained.load('willett-hw').guard(" + ("readout='lm'" if k == "lm" else "")
                  + ") with the packaged manifest gate list", previous_recheck=BEFORE[k],
                  seconds=round(time.time() - t0, 1))
        save_json(rc, out)
        log(f"recheck {k}: passed {rc['passed']}: {[(c['name'], c['n_offer'], c['n']) for c in rc['controls']]}, "
            f"real {rc['real']}, commits match sheet {rc['commits_match_sheet']} ({rc['seconds']} s)")


def act(r) -> str:
    return str(getattr(r.action, "value", r.action)).lower()


def stage_wiring(m, G) -> None:
    out = RES / "wiring.json"
    if out.exists():
        log("wiring: done before, skipped")
        return
    lp_test = load_lps("test", "real")
    res = {}
    for k in ("builtin", "lm"):
        t0 = time.time()
        g = G[k]
        both = list(g.offer_gates)
        rows = {}
        for kind in ("real", "rev_out"):
            n_both = n_coh = removed = 0
            for lp in lp_test:
                x = lp if kind == "real" else np.ascontiguousarray(lp[::-1])
                g.set_offer_gate(both[:1])
                a_coh = act(g._decide_quiet(x))
                g.set_offer_gate(both)
                a_both = act(g._decide_quiet(x))
                n_coh += a_coh == "offer"
                n_both += a_both == "offer"
                removed += (a_coh == "offer") and (a_both != "offer")
                assert a_both == a_coh or (a_coh == "offer" and a_both in ("withhold", "abstain")), (k, kind, a_coh, a_both)
            rows[kind] = {"n": len(lp_test), "offers_coherence_only": n_coh, "offers_shipped_gates": n_both,
                          "removed_by_direction_gate": removed}
        g.set_offer_gate(both)
        res[k] = {"config_id": g.config_id, **rows, "seconds": round(time.time() - t0, 1)}
        log(f"wiring {k}: {res[k]}")
    save_json({"note": "information only: the 80 test sentences were used before (P5-36b post hoc), so these counts "
                       "are not evidence for the rule; they show that the packaged guards apply the gate", **res}, out)


def main() -> int:
    stages = sys.argv[1:] or ["all"]
    if "all" in stages:
        stages = ["recheck", "wiring"]
    OWN.mkdir(parents=True, exist_ok=True)
    for p in (OWN / "DONE", OWN / "FAILED"):
        p.unlink(missing_ok=True)
    threading.Thread(target=watcher, daemon=True).start()
    from fidetype.utils.power import keep_awake

    t0 = time.time()
    try:
        with keep_awake(log):
            m, G = guards()
            log(f"start {stages}; gates {[(k, [x.label() for x in g.offer_gates]) for k, g in G.items()]}")
            for s in stages:
                {"recheck": stage_recheck, "wiring": stage_wiring}[s](m, G)
    except Exception:
        log("FAILED\n" + traceback.format_exc())
        (OWN / "FAILED").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    log(f"end of {stages} ({time.time() - t0:.0f} s)")
    (OWN / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
