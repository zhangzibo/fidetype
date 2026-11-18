"""P15-15: add the M4-13 (T15) entries to the hallucination benchmark and score them under protocol 0.2.

Why a separate step: the trust rerun queue (experiments/2026-11-17-f2-m4-13) writes per-trial decisions of the
real track and only aggregate swapped counts. The paired 0.2 rule needs per-item swapped decisions. This script runs
the P15-07 benchmark recipe (experiments/2026-11-16-p15-07-halluc-bench/run.py, imported, not changed) on the M4-13
rerun outputs: the saved guards and the decoder / LLM caches (read only, cache-only as P15-07; no decoder or LLM
is loaded, so RAM stays low). A cache miss skips that system and is reported.

    add_m4_13.py --check     list the M4-13 inputs and exit 0 if all exist (no other output)
    add_m4_13.py             run, write outcomes to benchmark/results/halluc-v0.2/, then run rescore.py
    add_m4_13.py --dry       plumbing test on the queue's dry-run outputs (M4-12 subset, stub LLM);
                             writes to C:/Users/zhang/bci-data/derived/p15-15-halluc-0.2/dryrun/ only

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-17-p15-15-halluc-0.2/add_m4_13.py
Per-trial records (texts): C:/Users/zhang/bci-data/derived/p15-15-halluc-0.2/ only. Our own code (Apache-2.0).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments" / "2026-11-17-trust-reruns-m4-13"))

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p15-15-halluc-0.2"  # the only derived folder this task writes
RERUN = DER / "f2-reruns-m4-13"  # READ ONLY
M413_RES = REPO / "experiments/2026-11-17-f2-m4-13/results"  # READ ONLY (results-t15.json of the P15-05 rerun)
V02 = REPO / "benchmark/results/halluc-v0.2"
SPLIT_V01 = REPO / "src/fidetype/benchmark/splits/halluc-v0.1/b2t25-t15-val-eval.json"
DATASET = "b2t25-t15-val-eval"


def systems(p5: Path, p6: Path) -> dict:
    return {
        "m4-13-p15-05-A0_ngram": {"arm": "A0_ngram", "guard": p5 / "guard-t15-A0_ngram.json", "grounded": False,
                                  "desc": "M4-13 rerun of P15-05 arm A0 (n-gram word decoder, no LLM; P14-03-type guard)"},
        "m4-13-p15-05-B0_rescore": {"arm": "B0_rescore", "guard": p5 / "guard-t15-B0_rescore.json", "grounded": False,
                                    "desc": "M4-13 rerun of P15-05 LLM rescoring, no grounding"},
        "m4-13-p15-06-B1_rescore_G": {"arm": "B1_rescore_G", "guard": p6 / "guard-B1_rescore_G.json", "grounded": True,
                                      "desc": "M4-13 rerun of the P15-06 guard (rescoring + grounding + fluent-wrong bound)"},
        "m4-13-p15-06-B1_rescore_G@single": {"arm": "B1_rescore_G", "guard": p6 / "guard-B1_rescore_G-single.json",
                                             "grounded": True,
                                             "desc": "M4-13 P15-06 variant V-single (pre-registered; one LTT test set)"},
    }


def inputs(dry: bool) -> dict:
    import common as K

    sub = "dryrun" if dry else ""
    p5, p6 = RERUN / "p15-05" / sub, RERUN / "p15-06" / sub
    src = "m4-12" if dry else "m4-13"
    p5res = M413_RES / ("dryrun-m4-12/results-t15.json" if dry else "results-t15.json")
    need = {"held-out log-probs": K.SOURCES[src]["held"], "P15-05 rerun results": p5res,
            "base n-best cache": p5 / "base-nbest-t15.pkl", "LLM cache (P15-05)": p5 / "llm-cache.sqlite",
            "LLM cache (P15-06)": p6 / "llm-cache.sqlite"}
    sy = systems(p5, p6)
    if dry:  # the dry run has arms A0 and B1 only
        sy = {k: v for k, v in sy.items() if v["arm"] in ("A0_ngram", "B1_rescore_G")}
    for k, v in sy.items():
        need[f"guard {k}"] = v["guard"]
    return {"p5": p5, "p6": p6, "src": src, "p5res": p5res, "need": need, "systems": sy}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    inp = inputs(a.dry)
    missing = [f"{k}: {p}" for k, p in inp["need"].items() if not Path(p).exists()]
    if a.check or missing:
        for k, p in inp["need"].items():
            print(f"{'ok     ' if Path(p).exists() else 'MISSING'} {k}: {p}")
        if missing:
            print(f"{len(missing)} M4-13 input(s) missing: the rerun queue is not done. Run this script again later.")
            return 2
        return 0

    import common as K
    import numpy as np

    from fidetype.adapters import b2t25 as B
    from fidetype.benchmark import hallucination as HB

    R = K.load_module("p1507_run", REPO / "experiments/2026-11-16-p15-07-halluc-bench/run.py")
    own = OWN / ("dryrun" if a.dry else "m4-13")
    own.mkdir(parents=True, exist_ok=True)
    out_dir = own if a.dry else V02
    out_dir.mkdir(parents=True, exist_ok=True)
    logf = (own if a.dry else HERE / "results") / "add_m4_13.log"
    R.OWN, R.LOGF = own, logf  # never write into the P15-07 folders
    R.P5_ROOT, R.P6_ROOT = inp["p5"], inp["p6"]  # FrozenPipeline reads base-nbest-t15.pkl / base-nbest-extra.pkl here
    R.SYSTEMS = {k: {**v, "guard": (lambda s, g=v["guard"]: g)} for k, v in inp["systems"].items()}
    log = R.log
    t0 = time.time()
    limit = K.dry_limits()[1] if a.dry else 0
    if a.dry and not limit:
        limit = 60
    xs, ts, _, keys = K.load_part(K.SOURCES[inp["src"]]["held"], "val_eval", limit, True, True)
    ids = [f"{k.split('|')[0]}|val|{k.split('|')[2]}" for k in keys]
    n_null = 20 if a.dry else R.N_NULL
    ctl = HB.make_controls(xs, ts, seed=R.SEED, n_null=n_null, vocab_size=len(B.SYMBOL_VOCAB))
    split = HB.split_definition(DATASET, ids, ts, ctl, licence="CC0 1.0",
                                rule=f"M4-13 long0 val_eval log-probs ({inp['src']}); same trials as the v0.1 T15 split",
                                n_null=n_null)
    if not a.dry:  # same trials, same control indices and permutation as the committed v0.1 split
        probs = [p for p in HB.verify_split(json.loads(SPLIT_V01.read_text(encoding="utf-8")), ids, ts, ctl)
                 if not p.startswith("warning")]
        assert not probs, f"M4-13 held-out set differs from the v0.1 T15 split: {probs}"
    (own / "split-m4-13.json").write_text(json.dumps(split, indent=0) + "\n", encoding="utf-8")
    log(f"P15-15 add_m4_13: source {inp['src']}, dry {a.dry}, {len(xs)} held out, n_null {n_null}")
    p5res = json.loads(inp["p5res"].read_text(encoding="utf-8"))
    thr = p5res["prep"]["fluent_logp_per_word"]
    llm = {}
    for f in (inp["p5"] / "llm-cache.sqlite", inp["p6"] / "llm-cache.sqlite"):
        llm.update(R.ro_table(f, "scores"))
    bt = R.load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    pipe = R.FrozenPipeline("t15", bt.build_lexicon(), p5res, R.FrozenScorer(llm))
    summary = {"source": inp["src"], "dry": a.dry, "n_real": len(xs), "n_null": n_null, "systems": {}}
    for name in inp["systems"]:
        try:
            recs, cfg_id = R.run_system("t15", name, pipe, ids, xs, ts, ctl)
        except R.CacheMiss as e:
            log(f"{name}: CACHE MISS ({e}); system skipped")
            summary["systems"][name] = {"status": "cache miss", "message": str(e)}
            continue
        with open(own / f"records-{name}.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps({"track": r.track, "item": r.item, "signal": r.signal_trial,
                                    "language": r.language_trial, "action": r.action, "text": r.text,
                                    "truth": r.truth}) + "\n")
        row = {"status": "ok", "guard_config_id": cfg_id}
        for mode, fl in (("llm", HB.TableFluency(llm, thr, name="Qwen2.5-1.5B-Instruct Q4_K_M (M4-13 rerun caches)")),
                         ("conservative", HB.ConservativeFluency())):
            oc = HB.to_outcomes(recs, fl, dataset=DATASET, system=name,
                                meta={"guard_config_id": cfg_id, "description": inp["systems"][name]["desc"],
                                      "decoder": "M4-13 long0", "seed": R.SEED})
            stem = f"{DATASET}--{name.replace('@', '-at-')}--{mode}"
            (out_dir / f"{stem}.outcomes.json").write_text(json.dumps(oc, indent=0) + "\n", encoding="utf-8")
            card = HB.score_outcomes(oc, alpha_wrong=0.05, alpha_fluent=0.01)
            row[mode] = HB.summary_line(card)
            log(f"{name} [{mode}]: {row[mode]}")
        summary["systems"][name] = row
    summary["seconds"] = round(time.time() - t0, 1)
    (own / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    if a.dry:
        log(f"dry run done in {summary['seconds']} s; outputs in {own}")
        return 0
    import importlib.util

    spec = importlib.util.spec_from_file_location("p1515_rescore", HERE / "rescore.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.main()


if __name__ == "__main__":
    raise SystemExit(main())
