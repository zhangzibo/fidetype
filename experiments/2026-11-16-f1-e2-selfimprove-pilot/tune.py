"""P15-01 tuning on S7 only (plan.md, "Adaptation settings"): day-layer settings, sentence temperature, ACI start.

Writes results/tuning.json (aggregates only). CPU only.
"""

from __future__ import annotations

import itertools
import json
import math
import time

import numpy as np

import common as C
from fidetype.trust import crc_threshold

LOG = C.OWN / "tune.log"


def main() -> None:
    t0 = time.time()
    trunk, ck = C.load_base()
    k_last = len(C.CONFIG["base_sessions"]) - 1
    W0, b0 = ck["dayW"][k_last].clone(), ck["dayb"][k_last].clone()
    L = C.CONFIG["loop"]
    si = C.CONFIG["tuning_session"]
    items = C.load_day(si)
    for it in items:
        it["lab"] = it["ph"]
    A, B, Cc = items[: L["n_phase_a"]], items[L["n_phase_a"]: L["n_phase_a"] + L["n_check"]], \
        items[L["n_phase_a"] + L["n_check"]:]
    C.log(LOG, f"S{si}: {len(items)} items (A {len(A)}, B {len(B)}, C {len(Cc)}); base val PER {ck['val_per']:.4f}")
    lps = C.log_probs(trunk, W0, b0, Cc)
    e, n = C.per_counts(lps, Cc)
    frozen_per = e / n
    C.log(LOG, f"frozen (S6 layer) PER on S7 phase C: {frozen_per:.4f}")
    grid = C.CONFIG["adapt_grid"]
    rows = []
    for steps, lr, l2 in itertools.product(sorted(grid["steps"]), grid["lr"], grid["l2"]):
        ta = time.time()
        W, b = C.fit_day_layer(trunk, W0, b0, A, lr=lr, l2=l2, steps=steps, batch=L["n_phase_a"], seed=0)
        e, n = C.per_counts(C.log_probs(trunk, W, b, Cc), Cc)
        rows.append({"steps": steps, "lr": lr, "l2": l2, "per_phase_c": e / n, "seconds": round(time.time() - ta, 1)})
        C.log(LOG, f"steps {steps} lr {lr} l2 {l2}: PER {e / n:.4f} ({time.time() - ta:.0f}s)")
    best = min(rows, key=lambda r: (round(r["per_phase_c"], 6), r["steps"]))
    W, b = C.fit_day_layer(trunk, W0, b0, A, lr=best["lr"], l2=best["l2"], steps=best["steps"],
                           batch=L["n_phase_a"], seed=0)
    route = C.WordRoute()
    td = time.time()
    lps = C.log_probs(trunk, W, b, Cc)
    nbs = [route.nbest(lp) for lp in lps]
    dec_s = (time.time() - td) / max(1, len(Cc))
    right = np.array([bool(nb) and nb[0][0] == it["text"] for nb, it in zip(nbs, Cc)], float)
    hit = np.mean([it["text"] in [t for t, _ in nb[: L["offer_k"]]] for nb, it in zip(nbs, Cc)])
    lo, hi, step = C.CONFIG["temperature_grid"]
    best_T, best_brier = None, math.inf
    for T in np.arange(lo, hi + 1e-9, step):
        p = np.array([C.p_top1([s for _, s in nb], float(T)) if nb else 0.0 for nb in nbs])
        br = float(np.mean((p - right) ** 2))
        if br < best_brier - 1e-12:
            best_T, best_brier = float(T), br
    scores = [C.p_top1([s for _, s in nb], best_T) if nb and nb[0][0].strip() else -math.inf for nb in nbs]
    res = crc_threshold([s if math.isfinite(s) else -1.0 for s in scores], 1.0 - right, L["alpha"])
    lam1 = float(res.threshold) if math.isfinite(res.threshold) and res.threshold <= 1.0 else 1.0
    out = {
        "tuning_session": si, "n_items": len(items), "base_val_per": ck["val_per"], "base_epoch": ck["epoch"],
        "frozen_per_phase_c": frozen_per, "grid": rows,
        "chosen": {"lr": best["lr"], "l2": best["l2"], "steps": best["steps"], "per_phase_c": best["per_phase_c"]},
        "nightly": C.CONFIG["nightly"],
        "sentence_temperature": best_T, "brier": best_brier,
        "top1_exact_phase_c": float(right.mean()), "offer_hit_phase_c": float(hit),
        "lambda_1": lam1, "crc_feasible": bool(math.isfinite(res.threshold) and res.threshold <= 1.0),
        "word_decode_s_per_item": round(dec_s, 3),
        "base_checkpoint_sha256": C.sha256_file(C.OWN / "base" / "best.pt"),
        "seconds": round(time.time() - t0, 1),
    }
    (C.RESULTS / "tuning.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    C.log(LOG, "tuning: " + json.dumps({k: v for k, v in out.items() if k != "grid"}))


if __name__ == "__main__":
    main()
