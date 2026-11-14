"""M2-18: does the empty-commit failure touch Paper 1's T15 (Brain-to-Text '25) numbers?

Re-runs the frozen v4 configuration (guard on, fit-A policy grid, LTT max on the clean
calibration half; ``paper1-v4-frozen-config``) on the two fixed splits of Paper 1 Tab. 1
(``alternate`` = split A, ``chrono`` = split B; our word decoder and the published-gate
decoder), plus the full-fit plug-in rows. Same code path as
``experiments/2026-11-12-paper1-r1-analyses/clean-drift/run.py`` and
``experiments/2026-11-12-paper1-r4-analyses/v4-derived/guard_controls.py``.

For each fit it counts, on the 816 test trials and on the 300-trial control streams
(same draw and seed as the R4 no-guard / v4-derived audits: real, other trial,
frame-shuffled, uniform):
commits, wrong commits, commits of an empty text, of a one-word text and of a text with
at most 3 characters; then the same with the opt-in commit gate (M2-18; variants A, B, C).

Checks: the refitted test wrong-commit rates must equal Paper 1 Tab. 1
(ours A 0.0245, ours B 0.0515, published A 0.0294, published B 0.0306).

Writes results/t15.json and results/t15.md (counts only; no text, no signals). Decodes
are read from the Paper 1 caches; new decodes go to C:/Users/zhang/bci-data/cache/m2-18.
Run (repo root, CPU, about 10 min):
  .venv\\Scripts\\python.exe -I experiments/2026-11-13-m2-18-empty-commits/t15_eval.py
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "2"

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments/2026-11-12-paper1-r3-analyses"))
import common3 as K  # noqa: E402

C = K.C
from fidetype.streams.spec import NeuralTextStream  # noqa: E402
from fidetype.trust.content import CommitGate, GatedPolicy  # noqa: E402
from fidetype.trust.guard import shuffle_stream, uniform_stream  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
CACHE = Path("C:/Users/zhang/bci-data/cache/m2-18")
CACHE.mkdir(parents=True, exist_ok=True)
R4_MAIN = Path("C:/Users/zhang/bci-data/cache/paper1-r4/decode-b2t-words-main.pkl")
LOGF = OUT / "t15.log"
PAPER_TAB1 = {("ours", "alternate"): 0.0245, ("ours", "chrono"): 0.0515,
              ("published", "alternate"): 0.0294, ("published", "chrono"): 0.0306}
RULES = {"gate A": CommitGate(1, 0), "gate B": CommitGate(1, 0, 1.0), "gate C": CommitGate(1, 2)}


def log(*a) -> None:
    line = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def count(records, truths=None) -> dict:
    com = [r for r in records if r.committed_text is not None]
    txt = [r.committed_text or "" for r in com]
    nch = [sum(not c.isspace() for c in t) for t in txt]
    return {"n": len(records), "n_commit": len(com), "n_wrong_commit": sum(bool(r.wrong_commit) for r in records),
            "n_commit_empty": sum(n == 0 for n in nch), "n_commit_1word": sum(len(t.split()) == 1 for t in txt),
            "n_commit_le3chars": sum(0 < n <= 3 for n in nch),
            "wrong_commit": sum(bool(r.wrong_commit) for r in records) / max(1, len(records)),
            "commit_rate": len(com) / max(1, len(records)),
            "ewpm": C.summarize(records)["ewpm"] if hasattr(C, "summarize") else None}


def policies(pipe) -> dict:
    out = {"v4": pipe.policy}
    for k, r in RULES.items():
        out[k] = GatedPolicy.wrap(pipe.policy, r)
    return out


def main() -> None:
    from fidetype.eval.ewpm import summarize
    from fidetype.eval.harness import Item

    C.summarize = summarize
    t_all = time.time()
    ctx = C.b2t_ctx()
    dc = ctx.cached[0]
    if R4_MAIN.exists():  # the R4 / v4-derived control decodes
        dc.d.update(pickle.loads(R4_MAIN.read_bytes()))
    dc.path = CACHE / dc.path.name
    by_day: dict = {}
    for i, t in enumerate(ctx.fit):
        by_day.setdefault(t.post_implant_day, []).append(i)
    splits = {}
    for name in ("alternate", "chrono"):
        A, Bi = [], []
        for d, idx in sorted(by_day.items()):
            if name == "alternate":
                A += idx[0::2]
                Bi += idx[1::2]
            else:
                h = (len(idx) + 1) // 2
                A += idx[:h]
                Bi += idx[h:]
        splits[name] = (sorted(A), sorted(Bi))
    T = ctx.items(ctx.test)
    # control streams: same draw as R4 no-guard / v4-derived guard_controls
    bt = ctx.bt
    rng = np.random.default_rng(bt.SEED)
    na = min(len(ctx.test), bt.CONFIG["audit_n"])
    aud_idx = sorted(rng.choice(len(ctx.test), na, replace=False).tolist())
    atest = [ctx.test[i] for i in aud_idx]
    streams = {t.index: bt.B.to_symbol_stream(bt.B.trial_stream(t)) for t in atest}
    base = [streams[t.index] for t in atest]
    perm = rng.permutation(len(base))
    for i in range(len(perm)):
        if atest[perm[i]].truth_words == atest[i].truth_words:
            perm[i], perm[(i + 1) % len(perm)] = perm[(i + 1) % len(perm)], perm[i]
    nulls = {"real": base, "other_trial": [base[j] for j in perm],
             "frame_shuffled": [shuffle_stream(s, rng) for s in base], "uniform": [uniform_stream(s, rng, 0.05) for s in base]}
    truths = [t.truth_words for t in atest]

    def ctl_items(which: str) -> dict:
        out = {}
        for cond, ss in nulls.items():
            its = []
            for i, s in enumerate(ss):
                if which == "published":  # the published sentence is looked up by the trial index of the target trial
                    s = NeuralTextStream(s.log_probs, s.frame_times, s.vocab, s.blank_id, s.source,
                                         {**s.meta, "fidetype.trial_index": atest[i].index}, vocab_type=s.vocab_type)
                its.append(Item(s, truths[i]))
            out[cond] = its
        return out

    res: dict = {"description": __doc__.strip().splitlines()[0], "rules": {k: v.to_dict() for k, v in RULES.items()},
                 "n_test": len(T), "n_control": na, "fits": {}}
    fits = [("ours", "alternate"), ("ours", "chrono"), ("published", "alternate"), ("published", "chrono"),
            ("ours", "full-fit"), ("published", "full-fit")]
    for which, sname in fits:
        t0 = time.time()
        fn = ctx.dec.words_fn if which == "ours" else ctx.dec.published_plus_fn
        pipe = C.TrustPipeline(fn, C.HarnessConfig(seed=C.SEED, user_config=ctx.user, max_wrong_commit=C.ALPHA, use_guard=True), {})
        if sname == "full-fit":  # Tab. 1 "full fit, plug-in" (fit(fit, fit), no risk control)
            F = ctx.items(ctx.fit)
            pipe.fit(F, F)
            ltt = None
        else:
            ia, ib = splits[sname]
            A = ctx.items([ctx.fit[i] for i in ia])
            Bc = ctx.items([ctx.fit[i] for i in ib])
            pipe.fit(A, A)
            r = pipe.calibrate_commit(Bc, method="ltt", alpha=C.ALPHA, delta=C.DELTA, combine="max")
            ltt = {"threshold": r.threshold, "feasible": r.feasible, "n": r.n}
        pols = policies(pipe)
        cache: dict = {}
        test_rows = {k: count(pipe.run_items(T, p, cache)) for k, p in pols.items()}
        ctl = {}
        for cond, its in ctl_items(which).items():
            cc: dict = {}
            ctl[cond] = {k: count(pipe.run_items(its, p, cc)) for k, p in pols.items()}
        C.save_caches(ctx)
        key = f"b2t-{which}/{sname}"
        exp = PAPER_TAB1.get((which, sname))
        got = test_rows["v4"]["wrong_commit"]
        res["fits"][key] = {"policy_config": C.clean(pipe.policy.config.__dict__), "frame_temperature": pipe.frame_scaler.temperature,
                            "ltt": ltt, "paper_tab1_wrong_commit": exp,
                            "reproduces_paper": None if exp is None else abs(round(got, 4) - exp) < 1e-9,
                            "test": test_rows, "controls": ctl, "seconds": round(time.time() - t0, 1)}
        log(key, "cmr", pipe.policy.config.commit_max_risk, "commit_p", pipe.policy.config.commit_p,
            "test v4", json.dumps({k: test_rows["v4"][k] for k in ("n_commit", "n_wrong_commit", "n_commit_empty", "n_commit_1word")}),
            f"wc {got:.4f} (paper {exp})",
            "uniform v4", ctl["uniform"]["v4"]["n_commit"], f"({time.time() - t0:.0f}s)")
        C.dump(res, OUT / "t15.json")
    res["seconds"] = round(time.time() - t_all, 1)
    C.dump(res, OUT / "t15.json")
    write_md(res)


def write_md(res: dict) -> None:
    L = ["# M2-18: Paper 1 T15 fits, committed empty / short texts", "",
         "Counts of commits on the 816 test trials and on the 300-trial control streams. "
         "`v4` = frozen v4 configuration. Gate A = no empty commit; gate B = gate A + guard risk < 1; gate C = at least 2 words (M2-18 commit gate on the same fitted configuration).", "",
         "| fit | commit_max_risk | set | policy | commits | wrong | empty | 1 word | <= 3 chars | wrong-commit rate |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for key, f in res["fits"].items():
        cmr = f["policy_config"]["commit_max_risk"]
        for sname, rows in [("test", f["test"])] + [(c, v) for c, v in f["controls"].items()]:
            for p, m in rows.items():
                L.append(f"| {key} | {cmr} | {sname} | {p} | {m['n_commit']} | {m['n_wrong_commit']} | {m['n_commit_empty']} | "
                         f"{m['n_commit_1word']} | {m['n_commit_le3chars']} | {m['wrong_commit']:.4f} |")
    L += ["", "Reproduction of Paper 1 Tab. 1 (test wrong-commit, v4): " +
          "; ".join(f"{k} {f['test']['v4']['wrong_commit']:.4f} vs {f['paper_tab1_wrong_commit']}"
                    for k, f in res["fits"].items() if f["paper_tab1_wrong_commit"] is not None)]
    (OUT / "t15.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
