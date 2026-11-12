r"""M2-16: per-trial commit items for the Toronto sEMG composed sentences (CPU, about 5 min).

M6-07 (experiments/2026-11-11-emg-toronto/trust.py) saved only aggregates.
This script rebuilds the same plan (same seed and config), fits the same
``c_trust`` pipeline per condition (A -> calibration, B -> policy grid) and
saves, per fit-B and test sentence, the commit score, the commit / fallback
loss and the eWPM terms of both outcomes (no text). Output:
``results/items-emg-<condition>.json``. The test order is participant by
participant, each participant's sentences in plan order (a "session").

Run (repo root): .venv\Scripts\python.exe -I experiments/2026-11-11-m2-16-online-recal/emg_items.py
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "2"

import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> None:
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig
    from fidetype.lm import CharNgramLM, ctc_prefix_beam_search
    from fidetype.trust.types import from_lm_hypotheses

    E = load_module("emgtrust", REPO / "experiments/2026-11-11-emg-toronto/trust.py")
    M = load_module("m213run", REPO / "experiments/2026-11-11-m2-13-conformal/run.py")
    old = json.loads((REPO / "experiments/2026-11-11-emg-toronto/results/trust.json").read_text(encoding="utf-8"))
    t0 = time.time()
    y, file_idx, files, info = E.load_meta()
    period = float(info["inter_key_interval_s"]["median"])
    user = UserConfig.aac_gaze(chars_per_min=60.0 / period)
    lm = CharNgramLM.load(E.CONFIG["char_lm"])
    texts = E.sentences()
    nfit, ntest = E.CONFIG["sentences_per_participant"]["fit"], E.CONFIG["sentences_per_participant"]["test"]
    P = E.pools(y, file_idx, files)
    pids = sorted(P, key=lambda s: int(s[1:]))
    half = len(texts) // 2
    fit_texts, test_texts = texts[:half], texts[half:]
    per_p = len(fit_texts) // len(pids)
    rng = np.random.default_rng(E.SEED)
    plan = {}
    for k, p in enumerate(pids):
        plan[p] = {"fit": E.compose(fit_texts[k * per_p : (k + 1) * per_p], P[p]["fit"], rng, nfit),
                   "test": E.compose(test_texts[k * per_p : (k + 1) * per_p], P[p]["test"], rng, ntest)}
    for cond, (fit_run, test_run, _desc) in E.CONDITIONS.items():
        ts = time.time()
        lg_fit, _, _ = E.load_logits(fit_run, len(y))
        lg_test, _, _ = E.load_logits(test_run, len(y))

        def items_of(which, lg):
            its, who = [], []
            for p in pids:
                for t, idx in plan[p][which]:
                    its.append(Item(E.make_stream(lg[idx], period, p, cond), t))
                    who.append(p)
            return its, who

        fit_items, fit_who = items_of("fit", lg_fit)
        test_items, test_who = items_of("test", lg_test)
        order = np.random.default_rng(E.SEED + 7).permutation(len(fit_items))
        fit_items = [fit_items[i] for i in order]
        fit_who = [fit_who[i] for i in order]
        h = len(fit_items) // 2
        A, Bv = fit_items[:h], fit_items[h:]
        w = old["conditions"][cond]["lm_weight"]
        kw = {**E.CONFIG["beam"], "lm_weight": w}

        def decode_fn(s):
            return from_lm_hypotheses(ctc_prefix_beam_search(s, lm, **kw), s.meta, confidence_variant="frame")

        pipe = TrustPipeline(decode_fn, HarnessConfig(seed=E.SEED, user_config=user, max_wrong_commit=E.CONFIG["max_wrong_commit"]))
        pipe.fit(A, Bv)
        res = {"condition": cond, "lm_weight": w, "fit": M.item_table(pipe, Bv), "test": M.item_table(pipe, test_items),
               "participants_fit": fit_who[h:], "participants_test": test_who}
        t = res["test"]
        s = np.array([float(x) for x in t["score"]])
        on = s >= t["lam_old"]
        wc = float(np.where(on, t["wc_c"], t["wc_f"]).mean())
        ew = 60 * np.where(on, t["words_c"], t["words_f"]).sum() / np.where(on, t["time_c"], t["time_f"]).sum()
        print(f"{cond}: lm_weight {w}, old gate {t['lam_old']}, test wrong-commit {wc:.4f} eWPM {ew:.3f} "
              f"(M6-07 c_trust {old['conditions'][cond]['policies']['c_trust']['wrong_commit_rate']:.4f} / "
              f"{old['conditions'][cond]['policies']['c_trust']['ewpm']:.3f}); eligible {np.isfinite(s).mean():.3f} "
              f"({time.time() - ts:.0f}s)", flush=True)
        (HERE / "results" / f"items-emg-{cond}.json").write_text(json.dumps(res), encoding="utf-8")
    print(f"done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
