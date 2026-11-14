"""P12-03 evaluation on NLB MC_RTT (plan.md, pre-declared). Writes aggregate numbers only.

    python -m fidetype.utils.isolation run --class background --threads 4 -- \
        .venv/Scripts/python.exe experiments/2026-11-14-p12-03-control/run_control.py \
        C:/Users/zhang/bci-data/derived/nlb-mc-rtt/mc_rtt_20ms.npz experiments/2026-11-14-p12-03-control/results
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from fidetype.decoders.velocity import (ResidualScale, StreamingVelocityDecoder, WienerVelocityDecoder, pearson,
                                        r2_score, window_total)
from fidetype.trust.control import (CONTROL, CONTROL_ENABLE, DECLARATION_KEY, ControlTrustLayer, conformal_quantile,
                                    conformal_scores, fit_control_config, gate_batch)

HIST = 10
LEVELS = (0.8, 0.9, 0.95)
PRIMARY = 0.9
TARGET_R = 7.5  # mm, half the grid spacing


def blocks(T: int):
    """Main split and 5 rotations: dicts of index arrays (fit, scale, cal, test)."""
    out = {}
    e = lambda f: int(round(f * T))  # noqa: E731
    out["main"] = dict(fit=np.arange(0, e(.4)), scale=np.arange(e(.4), e(.5)), cal=np.arange(e(.5), e(.7)),
                       test=np.arange(e(.7), T))
    edges = [e(k / 5) for k in range(6)]
    folds = [np.arange(edges[k], edges[k + 1]) for k in range(5)]
    for k in range(5):
        rest = np.concatenate([folds[j] for j in range(5) if j not in (k, (k - 1) % 5)])
        n_sc = int(round(0.2 * len(rest)))
        out[f"rot{k}"] = dict(fit=rest[:-n_sc], scale=rest[-n_sc:], cal=folds[(k - 1) % 5], test=folds[k])
    return out


def header(units="mm/s", rate=50.0):
    return {"type": "header", "spec_version": "0.1", "vocab": ["_"], "vocab_type": "command", "blank_id": None,
            "source": "p12-03-wiener", "clock_domain": "trial",
            DECLARATION_KEY: {"dims": 2, "quantity": "velocity", "units": units, "frame": "workspace", "rate_hz": rate,
                              "uncertainty": "std", "axes": ["x", "y"], "window_s": HIST / rate}}


def run_layer(cfg, t, vh, sig, qual, timing=None):
    """Replay one block through the streaming layer. Returns (velocity T x 2, states, reasons counts)."""
    lay = ControlTrustLayer(cfg)
    lay.push(header())
    lay.push({"type": CONTROL_ENABLE, "t": float(t[0]) - 1e-3, "enabled": True, "source": "ui"})
    out = np.zeros_like(vh)
    states, reasons = {}, {}
    for i in range(len(vh)):
        lay.push({"type": "signal_quality", "t": float(t[i]), "value": float(qual[i]), "unit": "index"})
        ev = {"type": CONTROL, "t": float(t[i]), "tick": i, "values": [float(vh[i, 0]), float(vh[i, 1])],
              "std": [float(sig[i])] * 2}
        d = lay.push(ev)[0]
        out[i] = d.velocity
        states[d.state] = states.get(d.state, 0) + 1
        for r in d.reasons:
            reasons[r] = reasons.get(r, 0) + 1
    return out, states, reasons


def motion_stats(v_true, v_out, v_raw):
    sp_t, sp_o, sp_r = (np.linalg.norm(x, axis=1) for x in (v_true, v_out, v_raw))
    moving = sp_o > 0
    sel = moving & (sp_t > 20.0)
    cos = (np.sum(v_out[sel] * v_true[sel], 1) / (sp_o[sel] * sp_t[sel])) if sel.any() else None
    return {"motion_frac": float(moving.mean()), "overspeed_rate": float(np.mean(sp_o > sp_t + 1e-9)),
            "mean_speed_out": float(sp_o.mean()), "mean_speed_raw": float(sp_r.mean()), "mean_speed_true": float(sp_t.mean()),
            "mean_cos_moving": None if cos is None else float(np.mean(cos)),
            "mean_gain": float(np.mean(np.where(sp_r > 0, sp_o / np.maximum(sp_r, 1e-12), 0.0)))}


def path_metrics(idx, target, pos, vel_sets, dt):
    """Open-loop replay per target segment. vel_sets: name -> T_block x 2 velocities aligned with idx."""
    tg = target[idx]
    ch = np.flatnonzero(np.any(np.diff(tg, axis=0) != 0, axis=1)) + 1
    segs = [(a, b) for a, b in zip(ch[:-1], ch[1:]) if 0.2 <= (b - a) * dt <= 5.0]
    res = {"segments": len(segs)}
    for name, v in vel_sets.items():
        eff, err, reached, ttt = [], [], [], []
        for a, b in segs:
            p0 = pos[idx[a - 1]] if a > 0 else pos[idx[a]]
            path = p0 + np.cumsum(v[a:b] * dt, axis=0)
            true_path = p0 + np.cumsum(vel_sets["true"][a:b] * dt, axis=0)
            L = float(np.sum(np.linalg.norm(np.diff(np.vstack([p0, path]), axis=0), axis=1)))
            eff.append(float(np.linalg.norm(path[-1] - p0) / L) if L > 1e-9 else 0.0)
            err.append(float(np.linalg.norm(path[-1] - true_path[-1])))
            dist = np.linalg.norm(path - tg[a], axis=1)
            hit = np.flatnonzero(dist <= TARGET_R)
            reached.append(bool(len(hit)))
            if len(hit):
                ttt.append(float((hit[0] + 1) * dt))
        res[name] = {"path_efficiency": float(np.mean(eff)), "endpoint_error_mm": float(np.median(err)),
                     "reached_frac": float(np.mean(reached)), "time_to_target_s_median": float(np.median(ttt)) if ttt else None}
    return res


def _ffill(x):
    x = np.array(x, float)
    for i in range(1, len(x)):
        bad = ~np.isfinite(x[i])
        x[i, bad] = x[i - 1, bad]
    return x


def evaluate(d, split, name, latency=False):
    C, V, P, G, t, dt = d["counts"], d["vel"], d["pos"], d["target"], d["t"], float(d["bin_s"])
    V = np.nan_to_num(V)
    P, G = _ffill(P), _ffill(G)  # 15 bins have NaN behaviour; carry the last valid position forward
    fit, sc, cal, te = split["fit"], split["scale"], split["cal"], split["test"]
    dec = WienerVelocityDecoder(history=HIST).fit(C[fit], V[fit])
    vh = dec.predict(C)
    tot = window_total(C, HIST)
    scale = ResidualScale().fit(V[sc], vh[sc], tot[sc])
    sig = scale.sigma(vh, tot)
    med = float(np.median(tot[cal]))
    qual = np.clip(tot / med, 0.0, 1.0)
    min_q = 0.5 * float(np.percentile(tot[cal], 0.1)) / med
    sp_fit = np.linalg.norm(V[fit], axis=1)
    acc_fit = np.linalg.norm(np.diff(V[fit], axis=0), axis=1) / dt
    v_max, a_max = float(np.percentile(sp_fit, 99.5)), float(np.percentile(acc_fit, 99.5))
    v_ns = dec.zero_input_output()
    out = {"split": name, "n": {k: int(len(v)) for k, v in split.items()}, "lambda": dec.lam,
           "v_max": v_max, "a_max": a_max, "min_quality": min_q, "no_signal_output": [float(x) for x in v_ns],
           "no_signal_speed": float(np.linalg.norm(v_ns))}
    out["raw"] = {"r2": r2_score(V[te], vh[te]), "pearson": pearson(V[te], vh[te])}
    # coverage (normalised and plain) at each level
    cov = {}
    for lv in LEVELS:
        qn = conformal_quantile(conformal_scores(V[cal], vh[cal], sig[cal]), lv)
        qp = conformal_quantile(conformal_scores(V[cal], vh[cal], None), lv)
        res = np.linalg.norm(V[te] - vh[te], axis=1)
        cov[str(lv)] = {"normalised": float(np.mean(res <= qn * sig[te])), "plain": float(np.mean(res <= qp)),
                        "mean_radius_normalised": float(np.mean(qn * sig[te])), "radius_plain": float(qp)}
        cfg_l = fit_control_config(V[cal], vh[cal], sig[cal], level=lv, no_signal_output=v_ns, min_quality=min_q)
        g, _ = gate_batch(cfg_l, vh[te], sig[te], qual[te])
        cov[str(lv)]["gate_only"] = {"r2": r2_score(V[te], g), **motion_stats(V[te], g, vh[te])}
    out["coverage"] = cov
    cfg = fit_control_config(V[cal], vh[cal], sig[cal], level=PRIMARY, v_max=v_max, a_max=a_max, min_quality=min_q,
                             no_signal_output=v_ns, name=f"p12-03-{name}")
    out["config_id"] = cfg.config_id
    vo, states, reasons = run_layer(cfg, t[te], vh[te], sig[te], qual[te])
    out["gated"] = {"r2": r2_score(V[te], vo), "pearson": pearson(V[te], vo), **motion_stats(V[te], vo, vh[te]),
                    "states": states, "reasons": reasons}
    out["paths"] = path_metrics(te, G, P, {"true": V[te], "raw": vh[te], "gated": vo}, dt)
    # controls
    rng = np.random.default_rng(0)
    ctrl_counts = {"shuffled": C[te][rng.permutation(len(te))], "zero": np.zeros_like(C[te]), "reversed": C[te][::-1]}
    cfg_nogate = fit_control_config(V[cal], vh[cal], sig[cal], level=PRIMARY, v_max=v_max, a_max=a_max,
                                    name="no-signal gates off")
    ctl = {}
    for cname, cc in ctrl_counts.items():
        vh_c = dec.predict(cc)
        tot_c = window_total(cc, HIST)
        sig_c = scale.sigma(vh_c, tot_c)
        q_c = np.clip(tot_c / med, 0.0, 1.0)
        vo_c, st_c, rs_c = run_layer(cfg, t[te], vh_c, sig_c, q_c)
        ctl[cname] = {"r2_raw": r2_score(V[te], vh_c), "r2_gated": r2_score(V[te], vo_c),
                      **motion_stats(V[te], vo_c, vh_c), "states": st_c}
        if cname == "zero":
            vo_n, st_n, _ = run_layer(cfg_nogate, t[te], vh_c, sig_c, q_c)
            ctl["zero_without_gates"] = {"r2_gated": r2_score(V[te], vo_n), **motion_stats(V[te], vo_n, vh_c), "states": st_n}
    out["controls"] = ctl
    if latency:
        sd = StreamingVelocityDecoder(dec, scale)
        lay = ControlTrustLayer(cfg)
        lay.push(header())
        lay.push({"type": CONTROL_ENABLE, "t": float(t[te[0]]) - 1e-3, "enabled": True})
        lat = []
        for i in te:
            t0 = time.perf_counter()
            v, s, total = sd.step(C[i])
            lay.push({"type": "signal_quality", "t": float(t[i]), "value": min(1.0, total / med), "unit": "index"})
            lay.push({"type": CONTROL, "t": float(t[i]), "tick": int(i), "values": [float(v[0]), float(v[1])], "std": [s, s]})
            lat.append(time.perf_counter() - t0)
        lat = np.array(lat) * 1e3
        out["latency_ms"] = {"median": float(np.median(lat)), "p99": float(np.percentile(lat, 99)), "max": float(lat.max())}
    return out


def main() -> None:
    d = dict(np.load(sys.argv[1]))
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    T = len(d["t"])
    res = {"data": "NLB MC_RTT train file (DANDI 000129 v0.241017.1444, CC-BY-4.0)", "bins": int(T),
           "units": int(d["counts"].shape[1]), "bin_s": float(d["bin_s"]), "history_bins": HIST, "splits": {}}
    for name, split in blocks(T).items():
        t0 = time.time()
        r = evaluate(d, split, name, latency=name == "main")
        res["splits"][name] = r
        print(f"{name}: R2 raw {r['raw']['r2']:.3f} gated {r['gated']['r2']:.3f}; cov0.9 "
              f"{r['coverage']['0.9']['normalised']:.3f} (plain {r['coverage']['0.9']['plain']:.3f}); overspeed "
              f"{r['gated']['overspeed_rate']:.3f}; zero speed {r['controls']['zero']['mean_speed_out']:.4f} "
              f"(no gates {r['controls']['zero_without_gates']['mean_speed_out']:.2f}); shuffled R2 "
              f"{r['controls']['shuffled']['r2_raw']:.3f}; reversed R2 {r['controls']['reversed']['r2_raw']:.3f} "
              f"[{time.time() - t0:.1f} s]", flush=True)
    (outdir / "metrics.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
