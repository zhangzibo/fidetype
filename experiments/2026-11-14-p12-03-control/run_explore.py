"""POST-HOC exploration (not pre-declared; written after the plan.md run showed no motion at level 0.90).

Question: how does the conformal level trade motion against the speed bound? Same data, splits,
decoder, scale model and clamps as run_control.py. Variants per level:

- ``full``: the declared layer (quality gate + no-signal reference gate + shrinkage + clamps + hand-off);
- ``no_ref``: the same without the no-signal reference gate (the quality gate still stops zero input).

Aggregate numbers only.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

from fidetype.decoders.velocity import ResidualScale, WienerVelocityDecoder, pearson, r2_score, window_total
from fidetype.trust.control import fit_control_config

_spec = importlib.util.spec_from_file_location("run_control", Path(__file__).with_name("run_control.py"))
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)  # type: ignore[union-attr]

LEVELS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def explore(d, split):
    C, V, t, dt = d["counts"], np.nan_to_num(d["vel"]), d["t"], float(d["bin_s"])
    P, G = rc._ffill(d["pos"]), rc._ffill(d["target"])
    fit, sc, cal, te = split["fit"], split["scale"], split["cal"], split["test"]
    dec = WienerVelocityDecoder(history=rc.HIST).fit(C[fit], V[fit])
    vh = dec.predict(C)
    tot = window_total(C, rc.HIST)
    scale = ResidualScale().fit(V[sc], vh[sc], tot[sc])
    sig = scale.sigma(vh, tot)
    med = float(np.median(tot[cal]))
    qual = np.clip(tot / med, 0.0, 1.0)
    min_q = 0.5 * float(np.percentile(tot[cal], 0.1)) / med
    v_max = float(np.percentile(np.linalg.norm(V[fit], axis=1), 99.5))
    a_max = float(np.percentile(np.linalg.norm(np.diff(V[fit], axis=0), axis=1) / dt, 99.5))
    v_ns = dec.zero_input_output()
    rng = np.random.default_rng(0)
    ctrl = {"shuffled": C[te][rng.permutation(len(te))], "zero": np.zeros_like(C[te]), "reversed": C[te][::-1]}
    cpred = {}
    for k, cc in ctrl.items():
        vc = dec.predict(cc)
        tc = window_total(cc, rc.HIST)
        cpred[k] = (vc, scale.sigma(vc, tc), np.clip(tc / med, 0.0, 1.0))
    out = {}
    for variant in ("full", "no_ref"):
        for lv in LEVELS:
            cfg = fit_control_config(V[cal], vh[cal], sig[cal], level=lv, v_max=v_max, a_max=a_max, min_quality=min_q,
                                     no_signal_output=v_ns if variant == "full" else None)
            vo, states, _ = rc.run_layer(cfg, t[te], vh[te], sig[te], qual[te])
            ms = rc.motion_stats(V[te], vo, vh[te])
            paths = rc.path_metrics(te, G, P, {"true": V[te], "gated": vo}, dt)
            row = {"r2": r2_score(V[te], vo), "pearson": pearson(V[te], vo), **ms,
                   "reached_frac": paths["gated"]["reached_frac"], "path_efficiency": paths["gated"]["path_efficiency"],
                   "endpoint_error_mm": paths["gated"]["endpoint_error_mm"]}
            for k, (vc, sgc, qc) in cpred.items():
                voc, _, _ = rc.run_layer(cfg, t[te], vc, sgc, qc)
                m = rc.motion_stats(V[te], voc, vc)
                row[f"{k}_motion_frac"] = m["motion_frac"]
                row[f"{k}_mean_speed_out"] = m["mean_speed_out"]
                row[f"{k}_overspeed_rate"] = m["overspeed_rate"]
            out[f"{variant}@{lv}"] = row
    return out


def main() -> None:
    d = dict(np.load(sys.argv[1]))
    outdir = Path(sys.argv[2])
    T = len(d["t"])
    res = {"note": "POST-HOC exploration, not pre-declared", "splits": {}}
    for name, split in rc.blocks(T).items():
        res["splits"][name] = explore(d, split)
        m = res["splits"][name]
        print(name, " ".join(f"{lv}:{m[f'no_ref@{lv}']['motion_frac']:.2f}/{m[f'no_ref@{lv}']['r2']:.2f}/"
                             f"{m[f'no_ref@{lv}']['overspeed_rate']:.2f}" for lv in LEVELS), flush=True)
    (outdir / "explore.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")


def zero_input_no_gates(npz: str, out: str) -> None:
    """POST-HOC: zero input through shrinkage + clamps only (no quality gate, no reference gate), main split."""
    d = dict(np.load(npz))
    C, V, t = d["counts"], np.nan_to_num(d["vel"]), d["t"]
    sp = rc.blocks(len(t))["main"]
    dec = WienerVelocityDecoder(history=rc.HIST).fit(C[sp["fit"]], V[sp["fit"]])
    vh = dec.predict(C)
    tot = window_total(C, rc.HIST)
    scale = ResidualScale().fit(V[sp["scale"]], vh[sp["scale"]], tot[sp["scale"]])
    sig = scale.sigma(vh, tot)
    te = sp["test"]
    z = np.zeros_like(C[te])
    vz = dec.predict(z)
    sz = scale.sigma(vz, window_total(z, rc.HIST))
    res = {"note": "POST-HOC", "zero_raw_speed": float(np.linalg.norm(vz, axis=1).mean()), "zero_sigma": float(sz.mean()), "levels": {}}
    for lv in LEVELS:
        cfg = fit_control_config(V[sp["cal"]], vh[sp["cal"]], sig[sp["cal"]], level=lv, v_max=1e6)
        vo, _, _ = rc.run_layer(cfg, t[te], vz, sz, np.ones(len(te)))
        s = np.linalg.norm(vo, axis=1)
        res["levels"][str(lv)] = {"motion_frac": float((s > 0).mean()), "mean_speed": float(s.mean()),
                                  "drift_mm_per_10s": float(s.mean() * 10.0), "radius": float(cfg.q * sz.mean())}
    Path(out).joinpath("zero_no_gates.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res))


if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[3] == "--zero-no-gates":
        zero_input_no_gates(sys.argv[1], sys.argv[2])
    else:
        main()
