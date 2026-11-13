"""M4-09: exact fast lexicon fallback + time-budgeted prewarm.

Follow-up of M4-08. Two changes, no change to any decision:

1. ``PronLexicon.nearest`` is now a NumPy Levenshtein over all fallback
   pronunciations of one length at once. ``nearest_bruteforce`` keeps the old
   Python loop as the reference.
2. ``CTCBeamSpec(prewarm_budget_s=...)`` runs the speculative end work in small
   steps under a time budget per push (``PhonemeWordDecoder.warm`` gives the
   word-decoder steps).

Stages:

- ``b2t``: the 816 B2T '25 test streams of M4-06 (T15, CC0) through the
  streaming layer: batch and incremental conditions, old and new ``nearest``.
  Final decisions are compared (``==``) with the M4-06 batch harness, for our
  decoder and the published gate. Every ``nearest`` query is recorded (outside
  the repo).
- ``nearest``: the fast and the brute-force ``nearest`` on every recorded B2T
  query and on synthetic queries (random strings, edited lexicon words).
- ``tables``: ``results/tables.md``.

Run (repo root): ``.venv\\Scripts\\python.exe -I experiments/2026-11-13-m4-09-fast-lexicon/run.py [stages]``
CPU only. Per-trial outputs and the query list go to ``derived_dir`` (not in the repo).
"""

from __future__ import annotations

import gc
import importlib.util
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
DER = Path(CONFIG["derived_dir"])
DER.mkdir(parents=True, exist_ok=True)

# The M4-08 harness (replay, timing, equality); its outputs are redirected here.
_spec = importlib.util.spec_from_file_location("m408run", REPO / CONFIG["m408_run"])
M8 = importlib.util.module_from_spec(_spec)
sys.modules["m408run"] = M8
_spec.loader.exec_module(M8)
C = M8.C
C.Log.path = OUT / "run.log"
M8.DER = DER

from fidetype.trust.frozen import FrozenTrustConfig  # noqa: E402
from fidetype.trust.incremental import CTCBeamSpec  # noqa: E402


def stage_b2t() -> dict:
    from fidetype.trust.types import from_lm_hypotheses

    bc = CONFIG["b2t"]
    ctx = C.b2t_ctx()
    if bc.get("gc_freeze"):
        # Real-time practice: move the static heap (lexicon, LMs, cached streams) out of
        # the cyclic GC, so a full collection does not scan millions of objects inside a push.
        gc.collect()
        gc.freeze()
        C.log(f"gc.freeze() after setup: {gc.get_freeze_count()} objects (again before each condition)")
    dec = ctx.dec
    lex = dec.lex
    raw_words = ctx.cached[0].fn
    cached_words = dec.words_fn
    wdec = dec.wdec
    test = list(ctx.test)
    if bc.get("limit"):
        test = test[: bc["limit"]]
    truths = [t.truth_words for t in test]
    M406 = Path(CONFIG["m406_derived"])
    files = [(f"day{t.post_implant_day:03d}", M406 / "streams" / "frames" / f"trial-{t.index:04d}.jsonl") for t in test]
    cfgs = {w: FrozenTrustConfig.load(REPO / CONFIG["m406_configs"][w]) for w in ("ours", "published")}
    ref = {}
    for w in cfgs:
        b = json.loads((M406 / f"batch-{w}.json").read_text(encoding="utf-8"))
        assert b["trials"][: len(test)] == [t.index for t in test]
        ref[w] = [{k: d[k] for k in ("action", "shown", "p_top1", "guard_risk", "set", "top")} for d in b["decisions"][: len(test)]]

    queries: set[str] = set()
    fast, brute = lex.nearest, lex.nearest_bruteforce

    def use(fn):
        def rec(seg, *a, **k):
            queries.add(seg)
            return fn(seg, *a, **k)

        lex.nearest = rec

    def fresh(fn):
        def before():
            use(fn)
            wdec._cand_cache.clear()
            wdec._lm_cache.clear()
            dec._wcache = {}
            if bc.get("gc_freeze"):  # each condition starts like a fresh session: survivors of setup and of earlier conditions frozen
                in_idle[0] = True
                gc.collect()
                gc.freeze()
                in_idle[0] = False

        return before

    def fresh_words(stream):
        dec._wcache = {}
        return raw_words(stream)

    def post_ours(hyps, stream):
        return from_lm_hypotheses(wdec.decode(hyps), stream.meta, confidence_variant=None)

    def post_published(hyps, stream):
        ours = post_ours(hyps, stream)
        dec.words_fn = lambda s: ours
        try:
            return dec.published_plus_fn(stream)
        finally:
            dec.words_fn = cached_words

    K = bc["prewarm_top_k"]

    def warm_full(texts):  # the M4-08 "full" prewarm, as steps
        return wdec.warm(texts[:K])

    kw = dict(dec.beam_kw)
    pw = dict(prewarm_every=bc["prewarm_every"], prewarm_max_new=bc["prewarm_max_new"])
    specs = {
        "search": CTCBeamSpec(kw, post=post_ours),
        "full": CTCBeamSpec(kw, post=post_ours, on_prewarm=warm_full, **pw),
        "published": CTCBeamSpec(kw, post=post_published),
    }
    for b in bc["budgets_ms"]:
        specs[f"budget{b:g}"] = CTCBeamSpec(kw, post=post_ours, on_prewarm=warm_full, prewarm_budget_s=b / 1e3, **pw)

    res: dict = {"n": len(test), "frame_period_s": 0.08, "config_ids": {w: c.config_id for w, c in cfgs.items()},
                 "beam": kw, "settings": bc, "conditions": {}}
    cond = res["conditions"]
    T = cfgs["ours"]
    plan = [
        ("batch-bruteforce", "b2t-batch-bf", dict(decode_fn=fresh_words), brute, "ours"),
        ("incremental-bruteforce", "b2t-inc-bf", dict(incremental=specs["search"].factory), brute, "ours"),
        ("incremental+full-prewarm-bruteforce", "b2t-inc-full-bf", dict(incremental=specs["full"].factory), brute, "ours"),
        ("batch", "b2t-batch", dict(decode_fn=fresh_words), fast, "ours"),
        ("incremental", "b2t-inc", dict(incremental=specs["search"].factory), fast, "ours"),
        ("incremental+full-prewarm", "b2t-inc-full", dict(incremental=specs["full"].factory), fast, "ours"),
    ]
    for b in bc["budgets_ms"]:
        plan.append((f"incremental+full-prewarm-budget-{b:g}ms", f"b2t-inc-budget{b:g}",
                     dict(incremental=specs[f"budget{b:g}"].factory), fast, "ours"))
    plan += [
        ("published-batch", "b2t-pub-batch", dict(decode_fn=specs["published"].decode_fn), fast, "published"),
        ("published-incremental", "b2t-pub-inc", dict(incremental=specs["published"].factory), fast, "published"),
    ]
    only = set(bc.get("only") or [])
    pauses: list[tuple[int, float]] = []
    t_gc = [0.0]

    in_idle = [False]

    def gc_cb(phase, info):  # automatic GC pauses, to explain push spikes (idle collections excluded)
        if in_idle[0]:
            return
        if phase == "start":
            t_gc[0] = time.perf_counter()
        else:
            pauses.append((info["generation"], (time.perf_counter() - t_gc[0]) * 1e3))

    gc.callbacks.append(gc_cb)
    for name, tag, kwargs, fn, which in plan:
        if only and name not in only:
            continue
        pauses.clear()
        idle: list[float] = []
        if bc.get("gc_idle"):
            # Automatic GC off while frames arrive; one full collection before each utterance
            # (an idle point, outside every timed push). Memory stays bounded per utterance.
            def events_of(src):
                t = time.perf_counter()
                in_idle[0] = True
                gc.collect()
                in_idle[0] = False
                idle.append(time.perf_counter() - t)
                return M8.iter_events(src)

            kwargs = dict(kwargs, events_of=events_of)
            gc.disable()
        try:
            cond[name], _, _ = M8.run_condition(tag, cfgs[which], files, truths, ref_rows=ref[which], before=fresh(fn), **kwargs)
        finally:
            gc.enable()
        if idle:
            cond[name]["gc_idle_collect_ms"] = M8.summ(idle)
        cond[name]["gc_pauses"] = {"n": len(pauses), "n_over_5ms": sum(d > 5 for _, d in pauses),
                                   "max_ms": max((d for _, d in pauses), default=0.0),
                                   "n_gen2": sum(g == 2 for g, _ in pauses)}
        cond[name]["nearest"] = "bruteforce" if fn is brute else "fast"
        cond[name]["decoder"] = which
    gc.callbacks.remove(gc_cb)
    res["gc_freeze"] = bool(bc.get("gc_freeze"))
    lex.nearest = fast
    C.dump(res, OUT / "b2t.json")
    C.dump({"queries": sorted(queries)}, DER / "nearest-queries.json")
    C.log(f"recorded {len(queries)} distinct nearest() queries")
    return res


def stage_nearest() -> dict:
    nc = CONFIG["nearest"]
    bt = C.load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    lex = bt.build_lexicon()
    wc = bt.word_counts()
    lex.set_fallback_words(w for w in lex.words if wc.get(w, 0) >= bt.CONFIG["fallback_min_count"])
    real = json.loads((DER / "nearest-queries.json").read_text(encoding="utf-8"))["queries"]
    alpha = sorted({c for ps in lex.prons.values() for p in ps for c in p})
    fb = sorted({p for ps in lex._fallback.values() for p in ps})
    rng = random.Random(nc["seed"])
    syn = []
    for _ in range(nc["n_random"]):
        syn.append("".join(rng.choice(alpha) for _ in range(rng.randint(1, nc["max_len"]))))
    for _ in range(nc["n_edited"]):
        p = list(rng.choice(fb))
        for _ in range(rng.randint(0, nc["max_edits"])):
            k, op = rng.randrange(len(p) + 1), rng.random()
            if op < 1 / 3 and len(p) > 1:
                p.pop(min(k, len(p) - 1))
            elif op < 2 / 3:
                p.insert(k, rng.choice(alpha))
            else:
                p[min(k, len(p) - 1)] = rng.choice(alpha)
        syn.append("".join(p))
    res: dict = {"fallback_prons": sum(len(v) for v in lex._fallback.values()), "alphabet": len(alpha), "sets": {}}
    for name, qs in (("b2t-test-queries", real), ("synthetic", syn)):
        tb, tf, n_eq, n_empty, mism = [], [], 0, 0, 0
        for mld in nc["max_len_diffs"]:
            for s in qs:
                t0 = time.perf_counter()
                a = lex.nearest_bruteforce(s, mld)
                t1 = time.perf_counter()
                b = lex.nearest(s, mld)
                t2 = time.perf_counter()
                tb.append(t1 - t0)
                tf.append(t2 - t1)
                if a == b:
                    n_eq += 1
                else:
                    mism += 1
                n_empty += not a
        res["sets"][name] = {"n_queries": len(qs), "max_len_diffs": nc["max_len_diffs"], "n_calls": len(tb), "n_equal": n_eq,
                             "n_mismatch": mism, "n_empty": n_empty,
                             "bruteforce_ms": M8.summ(tb), "fast_ms": M8.summ(tf),
                             "speedup_total": float(sum(tb) / sum(tf)) if sum(tf) else None}
        C.log(f"nearest {name}: {n_eq}/{len(tb)} equal; brute p50/p95/max {res['sets'][name]['bruteforce_ms']['p50']:.1f}/"
              f"{res['sets'][name]['bruteforce_ms']['p95']:.1f}/{res['sets'][name]['bruteforce_ms']['max']:.1f} ms; fast "
              f"{res['sets'][name]['fast_ms']['p50']:.2f}/{res['sets'][name]['fast_ms']['p95']:.2f}/{res['sets'][name]['fast_ms']['max']:.2f} ms")
    C.dump(res, OUT / "nearest.json")
    return res


def f(x, nd=1):
    return "-" if x is None else f"{x:.{nd}f}"


def stage_tables() -> None:
    L = ["# M4-09 tables", "", "Generated by `run.py tables`. Times in ms, one CPU process (perf_counter).", ""]
    if (OUT / "nearest.json").exists():
        n = json.loads((OUT / "nearest.json").read_text(encoding="utf-8"))
        L += [f"## nearest(): fast vs brute force ({n['fallback_prons']} fallback pronunciations)", "",
              "| query set | queries | calls (x max_len_diff) | equal | empty results | brute p50 | brute p95 | brute max | "
              "fast p50 | fast p95 | fast max | total speed-up |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, r in n["sets"].items():
            b, q = r["bruteforce_ms"], r["fast_ms"]
            L.append(f"| {k} | {r['n_queries']} | {r['n_calls']} | {r['n_equal']}/{r['n_calls']} | {r['n_empty']} | "
                     f"{f(b['p50'])} | {f(b['p95'])} | {f(b['max'])} | {f(q['p50'], 2)} | {f(q['p95'], 2)} | {f(q['max'], 2)} | "
                     f"{f(r['speedup_total'])}x |")
        L.append("")
    runs = [("b2t.json", "main run: gc.freeze(), automatic GC off in the utterance, gc.collect() between utterances"),
            ("b2t-gc-freeze-once.json", "second run: gc.freeze() once after setup only"),
            ("b2t-gc-default.json", "first run: default Python GC (budgets 1/2/3 ms)")]
    for fname, label in runs:
        if not (OUT / fname).exists():
            continue
        b = json.loads((OUT / fname).read_text(encoding="utf-8"))
        L += [f"## B2T '25 test streams ({b['n']} utterances, frame period 80 ms): {label}", "",
              "End = `push(end event)` -> final decision. Push = one `push(frame)`. CPU/utt = sum of all push times of one "
              "utterance. Equal = action, shown texts, p_top1, guard risk and prediction set equal (`==`) to the M4-06 batch "
              "harness decisions of the same decoder. GC > 5 ms = automatic cyclic-GC pauses longer than 5 ms during the condition. "
              "Idle GC = the untimed gc.collect() before each utterance (main run only).", "",
              "| condition | decoder | nearest | equal | end p50 | end p95 | end max | push p50 | push p95 | push max | "
              "CPU/utt p50 | CPU/utt p95 | GC > 5 ms (max ms) | idle GC p50 / max | commits / wrong |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, r in b["conditions"].items():
            t, e, o = r["timing"], r["equivalence"], r["outcome"]
            g = r.get("gc_pauses")
            gs = f"{g['n_over_5ms']} ({g['max_ms']:.0f})" if g else "-"
            cpu = t["total_cpu_per_utterance_ms"]
            ig = r.get("gc_idle_collect_ms")
            igs = f"{ig['p50']:.1f} / {ig['max']:.1f}" if ig else "-"
            L.append(f"| {k} | {r['decoder']} | {r['nearest']} | {e['n_equal']}/{e['n']} | "
                     f"{f(t['end_of_utterance_ms']['p50'])} | {f(t['end_of_utterance_ms']['p95'])} | {f(t['end_of_utterance_ms']['max'])} | "
                     f"{f(t['push_frame_ms']['p50'], 3)} | {f(t['push_frame_ms']['p95'], 2)} | {f(t['push_frame_ms']['max'])} | "
                     f"{f(cpu['p50'])} | {f(cpu.get('p95'))} | {gs} | {igs} | {o['n_commit']} / {o['n_wrong_commit']} |")
        L.append("")
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv: list[str]) -> None:
    stages = argv or ["b2t", "nearest", "tables"]
    fns = {"b2t": stage_b2t, "nearest": stage_nearest, "tables": stage_tables}
    for s in stages:
        C.log(f"stage {s}")
        fns[s]()


if __name__ == "__main__":
    main(sys.argv[1:])
