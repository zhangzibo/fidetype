"""M4-10: LRU bounds on the word-decoder caches (bounded memory in long live sessions).

The memos of ``PhonemeWordDecoder`` (segment -> lexicon candidates, word sentence ->
sentence-LM score) and of ``CharNgramLM`` (context -> next-symbol row) are now
``fidetype.lm.cache.LRUCache`` objects with an entry bound (``cache_size``; None = no
bound). A memo stores only pure function values, so a bound must change no decision.

Stages:

- ``session <size|none>``: one long synthetic session (``n_utterances`` synthetic
  phoneme streams, built from Tatoeba sentences and CMUdict pronunciations with random
  phoneme edits) through the streaming layer with the B2T '25 word route and a 1 ms
  prewarm budget. One process per cache setting, so the RSS values are clean.
  Logs cache sizes and RSS every ``checkpoint_every`` utterances, the push / end
  latency and the idle ``gc.collect()`` time. Decisions go to ``derived_dir``.
- ``compare``: decisions of all session runs ``==`` the unbounded run.
- ``b2t``: the 816 B2T '25 test streams of M4-06 (T15, CC0) as in M4-09 (budget 1 ms),
  with the word caches unbounded, at the default bound and at a small bound. Final
  decisions are compared (``==``) with the M4-06 batch harness.
- ``tables``: ``results/tables.md``.

Run (repo root): ``.venv\\Scripts\\python.exe -I experiments/2026-11-13-m4-10-bounded-caches/run.py <stage> [arg]``
CPU only. Per-utterance outputs go to ``derived_dir`` (not in the repo).
"""

from __future__ import annotations

import ctypes
import gc
import importlib.util
import json
import math
import random
import sys
import time
from ctypes import wintypes
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
DER = Path(CONFIG["derived_dir"])
DER.mkdir(parents=True, exist_ok=True)

_spec = importlib.util.spec_from_file_location("m408run", REPO / CONFIG["m408_run"])
M8 = importlib.util.module_from_spec(_spec)
sys.modules["m408run"] = M8
_spec.loader.exec_module(M8)
C = M8.C
C.Log.path = OUT / "run.log"
M8.DER = DER

from fidetype.lm.cache import LRUCache  # noqa: E402
from fidetype.lm.phoneme_words import DEFAULT_CAND_CACHE_SIZE, DEFAULT_LM_CACHE_SIZE  # noqa: E402
from fidetype.trust.frozen import FrozenTrustConfig  # noqa: E402
from fidetype.trust.incremental import CTCBeamSpec  # noqa: E402


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]


def mem_mb() -> dict:
    """Working set (RSS) and private bytes of this process, MB (Windows)."""
    c = _PMC()
    c.cb = ctypes.sizeof(c)
    k = ctypes.WinDLL("kernel32")
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
    k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return {"rss_mb": c.WorkingSetSize / 2**20, "private_mb": c.PrivateUsage / 2**20,
            "peak_rss_mb": c.PeakWorkingSetSize / 2**20}


def cache_mb(cache, kind: str) -> float:
    """Approximate size of a memo in MB: the container, keys and values (shared word strings excluded)."""
    n = sys.getsizeof(cache)
    for k, v in dict.items(cache):
        n += sys.getsizeof(k)
        if kind == "cand":
            n += sys.getsizeof(v) + sum(sys.getsizeof(t) for t in v)
        elif kind == "lm":
            n += sys.getsizeof(v)
        else:  # numpy row
            n += v.nbytes + 112
    return n / 2**20


# ---------------------------------------------------------------------------
# Shared setup
# ---------------------------------------------------------------------------


def parse_size(s: str | None) -> tuple:
    """-> (word-candidate bound, sentence-LM bound, char-LM bound, tag).

    "none": all unbounded; "default": the library defaults; an int n: n for both word
    memos and min(n, 200000) for the char-LM memo."""
    if s is None or s == "default":
        return DEFAULT_CAND_CACHE_SIZE, DEFAULT_LM_CACHE_SIZE, 200_000, "default"
    if s.lower() == "none":
        return None, None, None, "none"
    n = int(s)
    return n, n, min(n, 200_000), str(n)


def word_route(bt):
    """The B2T '25 word decoder of M4-06/M4-09 without loading the trials."""
    best = bt.load_json("tune.json")["best"]
    return bt.Decoders([], {k: best[k] for k in ("lm_weight", "edit_penalty", "word_bonus")})


def synthetic_session(bt, lex, n: int, seed: int, sc: dict):
    """``n`` synthetic sentences (Tatoeba, all words in CMUdict) and a function that builds the
    events of utterance ``i`` on demand (deterministic; the streams are not all kept in memory)."""
    B = bt.B
    rng = random.Random(seed)
    sents = sorted(s for s in bt.tatoeba_sentences() if sc["min_words"] <= len(s.split()) <= sc["max_words"]
                   and all(w in lex.prons for w in s.split()))
    picked = rng.sample(sents, n)
    del sents
    syms = list(B._SYMBOL_CHARS)
    vocab = list(B.SYMBOL_VOCAB)
    V = len(vocab)
    sid = {c: i for i, c in enumerate(vocab)}

    def events(i: int) -> list:
        rng = random.Random(seed * 100_003 + i)
        nprng = np.random.default_rng([seed, i])
        words = []
        for w in picked[i].split():
            q = []
            for ch in rng.choice(lex.prons[w]):
                r = rng.random()
                if r < sc["p_sub"]:
                    q.append(rng.choice(syms))
                elif r < sc["p_sub"] + sc["p_del"]:
                    continue
                else:
                    q.append(ch)
                if rng.random() < sc["p_ins"]:
                    q.append(rng.choice(syms))
            words.append("".join(q) or rng.choice(syms))
        frames = []
        prev = None
        for ch in " ".join(words):
            if ch == prev or rng.random() < 0.5:
                frames.append((0, None))  # blank (needed between repeats)
            alt = sid[rng.choice(syms)] if ch != " " else 0
            for _ in range(rng.randint(1, 2)):
                frames.append((sid[ch], alt))
            prev = ch
        frames.append((0, None))
        T = len(frames)
        logits = nprng.normal(0.0, 1.0, size=(T, V))
        for t, (k, alt) in enumerate(frames):
            logits[t, k] += sc["peak"] + nprng.normal(0.0, sc["peak_sd"])
            if alt is not None:
                logits[t, alt] += sc["alt"] + nprng.normal(0.0, sc["peak_sd"])
        lp = logits - np.logaddexp.reduce(logits, axis=1, keepdims=True)
        h = {"type": "header", "spec_version": "0.1", "vocab": vocab, "vocab_type": "phoneme", "blank_id": 0,
             "source": "m4-10-synthetic", "meta": {"fidetype.vocab_id": B.SYMBOL_VOCAB_ID, "utt": i}}
        ev = [h] + [{"type": "frame", "t": 0.08 * t, "log_probs": [float(v) for v in row]} for t, row in enumerate(lp)]
        return ev + [{"type": "end"}]

    return picked, events


def make_specs(dec, sc):
    from fidetype.trust.types import from_lm_hypotheses

    wdec = dec.wdec

    def post_ours(hyps, stream):
        return from_lm_hypotheses(wdec.decode(hyps), stream.meta, confidence_variant=None)

    K = sc["prewarm_top_k"]
    pw = dict(prewarm_every=sc["prewarm_every"], prewarm_max_new=sc["prewarm_max_new"])
    return CTCBeamSpec(dict(dec.beam_kw), post=post_ours, on_prewarm=lambda texts: wdec.warm(texts[:K]),
                       prewarm_budget_s=sc["budget_ms"] / 1e3, **pw)


def snapshot(dec, k: int, deep: bool) -> dict:
    wdec, lm = dec.wdec, dec.lm
    r = {"utt": k, **mem_mb(), "word_candidates": len(wdec._cand_cache), "word_sentence_lm": len(wdec._lm_cache),
         "char_lm_rows": len(lm._cache)}
    if deep:
        r["word_candidates_mb"] = cache_mb(wdec._cand_cache, "cand")
        r["word_sentence_lm_mb"] = cache_mb(wdec._lm_cache, "lm")
        r["char_lm_rows_mb"] = cache_mb(lm._cache, "row")
    return r


# ---------------------------------------------------------------------------
# Stage: long synthetic session
# ---------------------------------------------------------------------------


def stage_session(arg: str | None) -> dict:
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer

    sc = CONFIG["session"]
    cand, lmb, clm, tag = parse_size(arg)
    size = {"candidates": cand, "sentence_lm": lmb, "char_lm": clm}
    m0 = mem_mb()
    bt = C.load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    dec = word_route(bt)
    dec.wdec.set_cache_sizes(cand, lmb)
    dec.lm._cache.resize(clm)
    n_utt = int(sys.argv[3]) if len(sys.argv) > 3 else sc["n_utterances"]  # smoke runs only
    truths, events = synthetic_session(bt, dec.lex, n_utt, sc["seed"], sc)
    cfg = FrozenTrustConfig.load(REPO / CONFIG["m406_configs"]["ours"])
    spec = make_specs(dec, sc)
    layer = StreamingTrustLayer(cfg, incremental=spec.factory,
                                streaming=StreamingConfig(route="frames", max_attempts=1, incremental_chunk_frames=1))
    gc.collect()
    gc.freeze()
    base = snapshot(dec, 0, True)
    C.log(f"session cache={tag}: setup done, {len(truths)} utterances; mem {base['rss_mb']:.0f} MB RSS "
          f"(process start {m0['rss_mb']:.0f} MB); char LM bound {dec.lm._cache.maxsize}")
    snaps = [base]
    recs, idle = [], []
    gc.disable()
    t0 = time.time()
    try:
        for k in range(1, len(truths) + 1):
            r = M8.replay_timed(layer, [("s", events(k - 1))], None)[0]
            # Keep only small per-utterance records (no decision objects), so RSS growth = decoder state.
            recs.append({"pushes": r["pushes"], "end_push_s": r["end_push_s"], "latency_s": r["latency_s"],
                         "row": M8.decision_row(r["final"])})
            del r
            t = time.perf_counter()
            gc.collect()  # idle point: after the final decision, before the next utterance
            idle.append(time.perf_counter() - t)
            if k % sc["checkpoint_every"] == 0:
                snaps.append(snapshot(dec, k, k % sc["deep_every"] == 0 or k == len(truths)))
                s = snaps[-1]
                C.log(f"  {k}: RSS {s['rss_mb']:.0f} MB, private {s['private_mb']:.0f} MB; caches cand {s['word_candidates']} "
                      f"lm {s['word_sentence_lm']} charlm {s['char_lm_rows']}; idle gc last-100 p50 "
                      f"{np.median(idle[-100:]) * 1e3:.1f} ms ({time.time() - t0:.0f}s)")
    finally:
        gc.enable()
    rows = [r["row"] for r in recs]
    C.dump({"cache_size": size, "rows": rows}, DER / f"session-{tag}.json")
    n = len(recs)
    q = max(1, n // 10)
    res = {"cache_size": size, "char_lm_bound": dec.lm._cache.maxsize, "n": n, "settings": sc, "wall_s": time.time() - t0,
           "frames": {"median": float(np.median([len(r["pushes"]) for r in recs])), "total": sum(len(r["pushes"]) for r in recs)},
           "timing": M8.timing(recs), "timing_first_10pct": M8.timing(recs[:q]), "timing_last_10pct": M8.timing(recs[-q:]),
           "idle_gc_ms": M8.summ(idle), "idle_gc_first_10pct_ms": M8.summ(idle[:q]), "idle_gc_last_10pct_ms": M8.summ(idle[-q:]),
           "outcome": M8.outcome(rows, truths), "snapshots": snaps, "process_start_mem": m0,
           "word_cache_info": dec.wdec.cache_info(), "char_lm_cache_info": dec.lm._cache.info()}
    C.dump(res, OUT / f"session-{tag}.json")
    t = res["timing"]
    C.log(f"session cache={tag}: push p95 {t['push_frame_ms']['p95']:.2f} max {t['push_frame_ms']['max']:.1f} ms; end p50/p95 "
          f"{t['end_of_utterance_ms']['p50']:.1f}/{t['end_of_utterance_ms']['p95']:.1f} ms; RSS {base['rss_mb']:.0f} -> "
          f"{snaps[-1]['rss_mb']:.0f} MB")
    return res


def stage_compare(_arg=None) -> dict:
    runs = {}
    for p in sorted(DER.glob("session-*.json")):
        runs[p.stem.split("-", 1)[1]] = json.loads(p.read_text(encoding="utf-8"))["rows"]
    ref = runs.get("none")
    res = {}
    for k, rows in runs.items():
        res[k] = M8.compare_rows(rows, ref) if ref is not None and len(rows) == len(ref) else {"n": len(rows), "n_equal": None}
        C.log(f"compare session-{k} vs none: {res[k].get('n_equal')}/{res[k]['n']}")
    C.dump(res, OUT / "session-compare.json")
    return res


# ---------------------------------------------------------------------------
# Stage: B2T '25 replay (as M4-09, budget 1 ms)
# ---------------------------------------------------------------------------


def stage_b2t(_arg=None) -> dict:
    from fidetype.trust.types import from_lm_hypotheses

    bc = CONFIG["b2t"]
    ctx = C.b2t_ctx()
    gc.collect()
    gc.freeze()
    dec = ctx.dec
    wdec = dec.wdec
    test = list(ctx.test)
    if bc.get("limit"):
        test = test[: bc["limit"]]
    truths = [t.truth_words for t in test]
    M406 = Path(CONFIG["m406_derived"])
    files = [(f"day{t.post_implant_day:03d}", M406 / "streams" / "frames" / f"trial-{t.index:04d}.jsonl") for t in test]
    cfg = FrozenTrustConfig.load(REPO / CONFIG["m406_configs"]["ours"])
    b = json.loads((M406 / "batch-ours.json").read_text(encoding="utf-8"))
    assert b["trials"][: len(test)] == [t.index for t in test]
    ref = [{k: d[k] for k in ("action", "shown", "p_top1", "guard_risk", "set", "top")} for d in b["decisions"][: len(test)]]

    def post_ours(hyps, stream):
        return from_lm_hypotheses(wdec.decode(hyps), stream.meta, confidence_variant=None)

    K = bc["prewarm_top_k"]
    spec = CTCBeamSpec(dict(dec.beam_kw), post=post_ours, on_prewarm=lambda texts: wdec.warm(texts[:K]),
                       prewarm_budget_s=bc["budget_ms"] / 1e3, prewarm_every=bc["prewarm_every"],
                       prewarm_max_new=bc["prewarm_max_new"])
    res: dict = {"n": len(test), "settings": bc, "conditions": {}}
    for label in bc["cache_sizes"]:
        cand, lmb, clm, tag = parse_size(label)

        def before(cand=cand, lmb=lmb, clm=clm):
            wdec._cand_cache = LRUCache(cand)  # fresh memos and counters
            wdec._lm_cache = LRUCache(lmb)
            wdec.cand_cache_size, wdec.lm_cache_size = cand, lmb
            dec.lm._cache = LRUCache(clm)
            gc.collect()
            gc.freeze()

        idle: list[float] = []

        def events_of(src):
            t = time.perf_counter()
            gc.collect()
            idle.append(time.perf_counter() - t)
            return M8.iter_events(src)

        name = f"budget-{bc['budget_ms']:g}ms-cache-{tag}"
        gc.disable()
        try:
            r, _, _ = M8.run_condition(f"b2t-{name}", cfg, files, truths, ref_rows=ref, before=before,
                                       incremental=spec.factory, events_of=events_of)
        finally:
            gc.enable()
        r["idle_gc_ms"] = M8.summ(idle)
        r["cache_size"] = {"candidates": cand, "sentence_lm": lmb, "char_lm": clm}
        r["word_cache_info"] = wdec.cache_info()
        r["char_lm_cache_info"] = dec.lm._cache.info()
        r["mem_end"] = mem_mb()
        cond = res["conditions"][name] = r
        C.log(f"  {name}: equal {cond['equivalence']['n_equal']}/{len(test)}; caches {r['word_cache_info']}; "
              f"char LM {r['char_lm_cache_info']}")
    C.dump(res, OUT / "b2t.json")
    return res


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def f(x, nd=1):
    return "-" if x is None else f"{x:.{nd}f}"


def stage_tables(_arg=None) -> None:
    L = ["# M4-10 tables", "", "Generated by `run.py tables`. Times in ms (perf_counter), memory in MB (Windows working set = RSS).", ""]
    sess = {p.stem.split("-", 1)[1]: json.loads(p.read_text(encoding="utf-8")) for p in sorted(OUT.glob("session-*.json"))
            if p.stem != "session-compare"}
    cmp_ = json.loads((OUT / "session-compare.json").read_text(encoding="utf-8")) if (OUT / "session-compare.json").exists() else {}
    if sess:
        any_ = next(iter(sess.values()))
        L += [f"## Long synthetic session ({any_['n']} utterances, {any_['frames']['total']} frames, budget "
              f"{any_['settings']['budget_ms']} ms)", "",
              "Equal = decisions `==` the unbounded run. Caches = entries at the end (word candidates / sentence-LM scores / "
              "char-LM rows). RSS: after setup -> end.", "",
              "| run | bounds (cand / lm / char-LM) | equal | caches at end | memo MB at end (cand / lm / char) | RSS after setup | "
              "RSS end | private end | push p50 | push p95 | push max | end p50 | end p95 | idle GC p50 first / last 10 % |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, r in sorted(sess.items(), key=lambda kv: (kv[0] != "none", kv[0] != "default", kv[0])):
            s0, s1 = r["snapshots"][0], r["snapshots"][-1]
            cs = r["cache_size"]
            if not isinstance(cs, dict):  # runs before the split of the bound: one bound for both word memos
                cs = {"candidates": cs, "sentence_lm": cs, "char_lm": r["char_lm_bound"]}
            bounds = f"{cs['candidates']} / {cs['sentence_lm']} / {cs['char_lm']}"
            t = r["timing"]
            e = cmp_.get(k, {})
            L.append(f"| {k} | {bounds} | {e.get('n_equal')}/{r['n']} | {s1['word_candidates']} / {s1['word_sentence_lm']} / "
                     f"{s1['char_lm_rows']} | {f(s1.get('word_candidates_mb'))} / {f(s1.get('word_sentence_lm_mb'))} / "
                     f"{f(s1.get('char_lm_rows_mb'))} | {f(s0['rss_mb'], 0)} | {f(s1['rss_mb'], 0)} | {f(s1['private_mb'], 0)} | "
                     f"{f(t['push_frame_ms']['p50'], 3)} | {f(t['push_frame_ms']['p95'], 2)} | {f(t['push_frame_ms']['max'])} | "
                     f"{f(t['end_of_utterance_ms']['p50'])} | {f(t['end_of_utterance_ms']['p95'])} | "
                     f"{f(r['idle_gc_first_10pct_ms']['p50'])} / {f(r['idle_gc_last_10pct_ms']['p50'])} |")
        L.append("")
        L += ["### Growth (RSS MB / word-candidate entries / sentence-LM entries)", "",
              "| utterances | " + " | ".join(sorted(sess)) + " |", "|---|" + "---|" * len(sess)]
        utts = [s["utt"] for s in any_["snapshots"]]
        for i, u in enumerate(utts):
            if u % 250 and u != utts[-1] and u:
                continue
            cells = []
            for k in sorted(sess):
                sn = sess[k]["snapshots"]
                if i < len(sn):
                    cells.append(f"{sn[i]['rss_mb']:.0f} / {sn[i]['word_candidates']} / {sn[i]['word_sentence_lm']}")
                else:
                    cells.append("-")
            L.append(f"| {u} | " + " | ".join(cells) + " |")
        L.append("")
    if (OUT / "b2t.json").exists():
        b = json.loads((OUT / "b2t.json").read_text(encoding="utf-8"))
        L += [f"## B2T '25 test streams ({b['n']} utterances, our decoder, budget {b['settings']['budget_ms']} ms)", "",
              "Equal = action, shown texts, p_top1, guard risk and prediction set `==` the M4-06 batch harness.", "",
              "| condition | equal | word caches at end (cand / lm) | evictions (cand / lm) | char-LM rows / evictions | "
              "end p50 | end p95 | end max | push p50 | push p95 | push max | CPU/utt p50 | idle GC p50 / max |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, r in b["conditions"].items():
            t, e, w, cl = r["timing"], r["equivalence"], r["word_cache_info"], r["char_lm_cache_info"]
            L.append(f"| {k} | {e['n_equal']}/{e['n']} | {w['candidates']['size']} / {w['sentence_lm']['size']} | "
                     f"{w['candidates'].get('evictions', 0)} / {w['sentence_lm'].get('evictions', 0)} | {cl['size']} / {cl['evictions']} | "
                     f"{f(t['end_of_utterance_ms']['p50'])} | {f(t['end_of_utterance_ms']['p95'])} | {f(t['end_of_utterance_ms']['max'])} | "
                     f"{f(t['push_frame_ms']['p50'], 3)} | {f(t['push_frame_ms']['p95'], 2)} | {f(t['push_frame_ms']['max'])} | "
                     f"{f(t['total_cpu_per_utterance_ms']['p50'])} | {f(r['idle_gc_ms']['p50'])} / {f(r['idle_gc_ms']['max'])} |")
        L.append("")
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv: list[str]) -> None:
    fns = {"session": stage_session, "compare": stage_compare, "b2t": stage_b2t, "tables": stage_tables}
    stage = argv[0] if argv else "tables"
    arg = argv[1] if len(argv) > 1 else None
    C.log(f"stage {stage} {arg or ''}")
    fns[stage](arg)


if __name__ == "__main__":
    main(sys.argv[1:])
