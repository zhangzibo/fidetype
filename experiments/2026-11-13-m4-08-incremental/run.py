"""M4-08: decode as the frames arrive in the streaming trust layer.

Compares the default frame route (decode the whole utterance at its end)
with the opt-in incremental route (``StreamingTrustLayer(incremental=...)``)
on:

1. B2T '25 test streams (T15, CC0; the 816 full-precision NTS files of
   M4-06) with our phoneme beam -> lexicon word decoder and the frozen
   split-A configs of M4-06 (ours, published gate).
2. Synthetic simulator streams with three decoders: CTC greedy, the
   demo segment beam (ReferenceDecoder + char 5-gram) and the CTC prefix
   beam (RETUNED, Tatoeba char 6-gram LM).

Measured: final-decision equality with the batch path, end-of-utterance
latency (push of the end event -> final decision), per-frame push cost,
total CPU per utterance, and the stability of the provisional top-1.
CPU only. Per-trial outputs go to ``derived_dir`` (outside the repo).

Run (repo root): ``.venv\\Scripts\\python.exe -I experiments/2026-11-13-m4-08-incremental/run.py [stages]``
Stages: synthetic b2t tables (default: all).
"""

from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments/2026-11-12-paper1-r1-analyses"))
import common as C  # noqa: E402  (sets the thread env vars, adds src/ to sys.path)

from fidetype.trust.frozen import FrozenTrustConfig  # noqa: E402
from fidetype.trust.incremental import (  # noqa: E402
    CTCBeamSpec,
    IncrementalGreedy,
    IncrementalReferenceDecoder,
    stability_metrics,
)
from fidetype.trust.policy import Action  # noqa: E402
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, iter_events  # noqa: E402

CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
DER = Path(CONFIG["derived_dir"])
DER.mkdir(parents=True, exist_ok=True)
M406 = Path(CONFIG["m406_derived"])
C.Log.path = OUT / "run.log"


def pct(xs, q):
    return float(np.percentile(np.asarray(xs, dtype=np.float64) * 1e3, q)) if len(xs) else None


def summ(xs) -> dict:
    """p50 / p95 / max / mean in ms."""
    if not len(xs):
        return {"n": 0}
    return {"p50": pct(xs, 50), "p95": pct(xs, 95), "max": pct(xs, 100), "mean": float(np.mean(xs) * 1e3), "n": len(xs)}


# ---------------------------------------------------------------------------
# Replay with timings
# ---------------------------------------------------------------------------


def replay_timed(layer: StreamingTrustLayer, files, events_of=iter_events) -> list[dict]:
    """Push each file (session, path-or-events) through the layer. One record per utterance."""
    recs = []
    for sid, src in files:
        evs = list(events_of(src)) if not isinstance(src, list) else src
        pushes, previews, final, t_last = [], [], None, None
        for ev in evs:
            t0 = time.perf_counter()
            out = layer.push(ev, sid)
            dt = time.perf_counter() - t0
            if ev.get("type") == "frame":
                pushes.append(dt)
                t_last = float(ev["t"])
            for d in out:
                if d.final:
                    final = (d, dt)
                else:
                    previews.append(d)
        if final is None:
            out = layer.end_of_utterance(sid)
            final = (out[0], out[0].provenance["latency_s"])
        recs.append({"session": sid, "final": final[0], "end_push_s": final[1], "latency_s": final[0].provenance["latency_s"],
                     "pushes": pushes, "previews": previews, "t_end": t_last})
    return recs


def decision_row(d) -> dict:
    return {"action": d.action.value, "shown": list(d.shown), "p_top1": float(d.inputs.p_top1),
            "guard_risk": float(d.guard.risk) if d.guard is not None else None, "set": list(d.inputs.set_indices),
            "top": d.inputs.texts[0] if d.inputs.texts else ""}


def compare_rows(a: list[dict], b: list[dict]) -> dict:
    """Exact comparison of final decisions (action, shown, p_top1, guard risk, prediction set)."""
    fields = ("action", "shown", "p_top1", "guard_risk", "set")
    n_eq = sum(all(x[f] == y[f] for f in fields) for x, y in zip(a, b))
    return {"n": len(a), "n_equal": n_eq, "action_agree": sum(x["action"] == y["action"] for x, y in zip(a, b)),
            "shown_agree": sum(x["shown"] == y["shown"] for x, y in zip(a, b)),
            "max_abs_dp_top1": max((abs(x["p_top1"] - y["p_top1"]) for x, y in zip(a, b)), default=0.0)}


def outcome(rows: list[dict], truths: list[str]) -> dict:
    n = len(rows)
    commit = [r["action"] == "COMMIT" for r in rows]
    wrong = [c and (r["shown"][:1] != [t]) for c, r, t in zip(commit, rows, truths)]
    return {"n": n, "n_commit": int(sum(commit)), "n_wrong_commit": int(sum(wrong)),
            "commit_rate": sum(commit) / n if n else None, "wrong_commit": sum(wrong) / n if n else None,
            "actions": {a.value: sum(r["action"] == a.value for r in rows) for a in Action}}


def stability(recs) -> dict:
    per = []
    for r in recs:
        if not r["previews"]:
            continue
        pv = [(d.provenance["input"]["t_range"][1], d.inputs.texts[0] if d.inputs.texts else "") for d in r["previews"]]
        fin = r["final"].inputs.texts[0] if r["final"].inputs.texts else ""
        m = stability_metrics(pv, fin, r["t_end"])
        dur = r["t_end"] - r["previews"][0].provenance["input"]["t_range"][0] if r["t_end"] is not None else None
        m["utterance_s"] = dur
        per.append(m)
    if not per:
        return {"n": 0}
    stable = [m for m in per if m["stable_at"] is not None]
    tts = [m["time_to_stable_before_end"] for m in stable]
    frac = [m["time_to_stable_before_end"] / m["utterance_s"] for m in stable if m["utterance_s"]]
    return {
        "n_utterances": len(per),
        "previews_per_utterance_median": float(np.median([m["n_previews"] for m in per])),
        "top1_change_rate_mean": float(np.nanmean([m["change_rate"] for m in per])),
        "top1_changes_per_utterance_median": float(np.median([m["n_changes"] for m in per])),
        "rewrites_per_utterance_median": float(np.median([m["n_rewrites"] for m in per])),
        "rewrites_per_utterance_mean": float(np.mean([m["n_rewrites"] for m in per])),
        "last_preview_equals_final": sum(m["last_preview_equals_final"] for m in per) / len(per),
        "stable_before_end_fraction": len(stable) / len(per),
        "time_to_stable_before_end_s_median": float(np.median(tts)) if tts else None,
        "time_to_stable_before_end_s_p10": float(np.percentile(tts, 10)) if tts else None,
        "stable_share_of_utterance_median": float(np.median(frac)) if frac else None,
        "prefix_ok_fraction_mean": float(np.mean([m["prefix_ok_fraction"] for m in per])),
    }


def timing(recs) -> dict:
    pushes = [x for r in recs for x in r["pushes"]]
    total = [sum(r["pushes"]) + r["end_push_s"] for r in recs]
    return {"end_of_utterance_ms": summ([r["end_push_s"] for r in recs]),
            "decision_latency_ms": summ([r["latency_s"] for r in recs]),
            "push_frame_ms": summ(pushes),
            "push_frame_max_per_utterance_ms": summ([max(r["pushes"]) for r in recs if r["pushes"]]),
            "total_cpu_per_utterance_ms": summ(total)}


def dump_trials(name: str, recs, extra=None) -> None:
    C.dump({"trials": [{"session": r["session"], **decision_row(r["final"]), "end_push_s": r["end_push_s"],
                        "n_previews": len(r["previews"]),
                        "previews": [[d.provenance["input"]["t_range"][1], d.inputs.texts[0] if d.inputs.texts else ""]
                                     for d in r["previews"]]} for r in recs], **(extra or {})}, DER / f"{name}.json")


def run_condition(name, cfg, files, truths, *, decode_fn=None, incremental=None, partial_every=None, chunk=1, ref_rows=None,
                  events_of=iter_events, before=None) -> dict:
    if before is not None:
        before()
    layer = StreamingTrustLayer(cfg, decode_fn=decode_fn, incremental=incremental,
                                streaming=StreamingConfig(route="frames", max_attempts=1, partial_every_frames=partial_every,
                                                          incremental_chunk_frames=chunk))
    t0 = time.time()
    recs = replay_timed(layer, files, events_of)
    rows = [decision_row(r["final"]) for r in recs]
    res = {"condition": name, "wall_s": time.time() - t0, "timing": timing(recs), "outcome": outcome(rows, truths)}
    if ref_rows is not None:
        res["equivalence"] = compare_rows(rows, ref_rows)
    if partial_every is not None:
        res["stability"] = stability(recs)
    dump_trials(name, recs)
    t = res["timing"]
    C.log(f"{name}: end p50/p95/max {t['end_of_utterance_ms']['p50']:.2f}/{t['end_of_utterance_ms']['p95']:.2f}/"
          f"{t['end_of_utterance_ms']['max']:.1f} ms; push p95 {t['push_frame_ms']['p95']:.3f} max {t['push_frame_ms']['max']:.1f} ms; "
          f"equal {res.get('equivalence', {}).get('n_equal')}/{len(rows)} ({res['wall_s']:.0f}s)")
    return res, rows, recs


# ---------------------------------------------------------------------------
# Synthetic streams
# ---------------------------------------------------------------------------


def stage_synthetic() -> dict:
    from fidetype.conformance.io import write_jsonl  # noqa: F401  (events below are built in memory)
    from fidetype.demo import build_decoder
    from fidetype.lm import RETUNED, CharNgramLM
    from fidetype.streams.corpus import sentences
    from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
    from fidetype.trust.testing import greedy_nbest

    sc = CONFIG["synthetic"]
    cfg = FrozenTrustConfig.load(REPO / "src/fidetype/demo/trust-config-demo.json")
    sents = sentences(sc["n"], seed=sc["seed"])
    sim = NoisyDecoderSimulator(SimConfig.preset(sc["preset"], confidence_temperature=0.5), seed=sc["seed"])
    streams = [sim.simulate(s, seed=1000 + i).stream for i, s in enumerate(sents)]

    def events(st):
        h = {"type": "header", "spec_version": st.version, "vocab": list(st.vocab), "vocab_type": st.vocab_type,
             "blank_id": st.blank_id, "source": st.source, "meta": dict(st.meta)}
        ev = [h] + [{"type": "frame", "t": float(t), "log_probs": [None if v == -math.inf else float(v) for v in row]}
                    for t, row in zip(st.frame_times, st.log_probs)]
        return ev + [{"type": "end"}]

    files = [(f"syn{i:03d}", events(st)) for i, st in enumerate(streams)]
    ref = build_decoder()
    lm = CharNgramLM.load(CONFIG["char_lm"])
    spec = CTCBeamSpec(dict(RETUNED), lm=lm, prewarm_every=sc["prewarm_every"], prewarm_max_new=sc["prewarm_max_new"])
    spec_np = CTCBeamSpec(dict(RETUNED), lm=lm)
    res: dict = {"config_id": cfg.config_id, "frame_temperature": cfg.frame_temperature, "n": len(streams),
                 "frames": {"median": float(np.median([s.n_frames for s in streams])), "max": int(max(s.n_frames for s in streams))},
                 "frame_period_s": 1.0 / SimConfig().frame_rate_hz, "decoders": {}}
    decs = {
        "greedy": (greedy_nbest, {"incremental": IncrementalGreedy.factory}),
        "demo-segment-beam": (ref, {"incremental": IncrementalReferenceDecoder.factory_for(ref)}),
        "ctc-beam-retuned-lm": (spec.decode_fn, {"incremental": spec_np.factory, "incremental+prewarm": spec.factory}),
    }
    for name, (fn, incs) in decs.items():
        r: dict = {}
        base, base_rows, _ = run_condition(f"syn-{name}-batch", cfg, files, sents, decode_fn=fn, events_of=None)
        r["batch"] = base
        for tag, fac in incs.items():
            inc, _, _ = run_condition(f"syn-{name}-{tag}", cfg, files, sents, incremental=fac, ref_rows=base_rows, events_of=None)
            r[tag] = inc
        last = list(incs.values())[-1]
        pv, _, _ = run_condition(f"syn-{name}-previews", cfg, files, sents, incremental=last, ref_rows=base_rows,
                                 partial_every=sc["partial_every_frames"], events_of=None)
        r["previews"] = pv
        res["decoders"][name] = r
    C.dump(res, OUT / "synthetic.json")
    return res


# ---------------------------------------------------------------------------
# B2T '25
# ---------------------------------------------------------------------------


def load_pre_m408_beam():
    """The beam module as of git ``pre_m408_commit`` (before the M4-08 refactor), for the 'before' timing."""
    src = subprocess.run(["git", "show", f"{CONFIG['pre_m408_commit']}:src/fidetype/lm/beam.py"], cwd=REPO,
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    p = DER / "beam_pre_m408.py"
    p.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("beam_pre_m408", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["beam_pre_m408"] = mod
    spec.loader.exec_module(mod)
    return mod


def stage_b2t() -> dict:
    from fidetype.trust.types import from_lm_hypotheses

    bc = CONFIG["b2t"]
    ctx = C.b2t_ctx()
    dec = ctx.dec
    raw_words = ctx.cached[0].fn  # the bound Decoders.words_fn below the disk cache
    cached_words = dec.words_fn
    wdec = dec.wdec
    test = list(ctx.test)
    if bc.get("limit"):
        test = test[: bc["limit"]]
    truths = [t.truth_words for t in test]
    files = [(f"day{t.post_implant_day:03d}", M406 / "streams" / "frames" / f"trial-{t.index:04d}.jsonl") for t in test]
    cfgs = {w: FrozenTrustConfig.load(REPO / CONFIG["m406_configs"][w]) for w in ("ours", "published")}
    batch_ref = {}
    for w in cfgs:
        b = json.loads((M406 / f"batch-{w}.json").read_text(encoding="utf-8"))
        assert b["trials"][: len(test)] == [t.index for t in test]
        batch_ref[w] = [{k: d[k] for k in ("action", "shown", "p_top1", "guard_risk", "set", "top")} for d in b["decisions"][: len(test)]]

    def fresh_caches():
        wdec._cand_cache.clear()
        wdec._lm_cache.clear()
        dec._wcache = {}

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

    class _Text:  # a phoneme text without confidences (they do not change the word scores)
        def __init__(self, text):
            self.text, self.logp_acoustic = text, 0.0

    def warm_full(texts):
        # Word decoder caches (lexicon candidates, sentence LM) for the current end candidates.
        wdec.decode([_Text(t) for t in texts[:K]])

    KL = bc["prewarm_light_top_k"]

    def warm_light(texts):
        # Lexicon candidates of the complete words only (not the last, maybe unfinished, segment).
        for t in texts[:KL]:
            for seg in t.split()[:-1]:
                wdec._slot(seg)

    P = bc["preview_hyps"]

    def preview_words(hyps):
        return from_lm_hypotheses(wdec.decode(hyps[:P]), None, confidence_variant=None)

    kw = dict(dec.beam_kw)
    pw = dict(prewarm_every=bc["prewarm_every"], prewarm_max_new=bc["prewarm_max_new"])
    spec = {
        "ours": CTCBeamSpec(kw, post=post_ours),
        "ours+prewarm-light": CTCBeamSpec(kw, post=post_ours, on_prewarm=warm_light, **pw),
        "ours+prewarm-full": CTCBeamSpec(kw, post=post_ours, on_prewarm=warm_full, **pw),
        "ours+prewarm-light+previews": CTCBeamSpec(kw, post=post_ours, on_prewarm=warm_light, preview=preview_words, **pw),
        "published": CTCBeamSpec(kw, post=post_published),
    }
    res: dict = {"n": len(test), "frame_period_s": 0.08, "config_ids": {w: c.config_id for w, c in cfgs.items()},
                 "beam": kw, "settings": bc, "conditions": {}}
    cond = res["conditions"]
    T = cfgs["ours"]

    # Before: the default frame route, fresh decode (as M4-06 stage "uncached").
    pre = load_pre_m408_beam()
    bt = ctx.bt
    cur = bt.ctc_prefix_beam_search
    bt.ctc_prefix_beam_search = pre.ctc_prefix_beam_search
    try:
        cond["batch-pre-m4-08-code"], _, _ = run_condition("b2t-ours-batch-pre", T, files, truths, decode_fn=fresh_words,
                                                           ref_rows=batch_ref["ours"], before=fresh_caches)
    finally:
        bt.ctc_prefix_beam_search = cur
    cond["batch"], _, _ = run_condition("b2t-ours-batch", T, files, truths, decode_fn=fresh_words, ref_rows=batch_ref["ours"],
                                        before=fresh_caches)
    for tag in ("ours", "ours+prewarm-light", "ours+prewarm-full"):
        cond[f"incremental-{tag}"], _, _ = run_condition(f"b2t-inc-{tag}", T, files, truths, incremental=spec[tag].factory,
                                                         ref_rows=batch_ref["ours"], before=fresh_caches)
    cond["incremental-ours+prewarm-light+previews"], _, _ = run_condition(
        "b2t-inc-ours-previews", T, files, truths, incremental=spec["ours+prewarm-light+previews"].factory,
        ref_rows=batch_ref["ours"], partial_every=bc["partial_every_frames"], before=fresh_caches)
    cond["incremental-published"], _, _ = run_condition(
        "b2t-inc-published", cfgs["published"], files, truths, incremental=spec["published"].factory,
        ref_rows=batch_ref["published"], before=fresh_caches)
    C.dump(res, OUT / "b2t.json")
    return res


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def f(x, nd=1):
    return "-" if x is None else f"{x:.{nd}f}"


def stage_tables() -> None:
    L = ["# M4-08 tables", "", "Generated by `run.py tables`. Times in ms, one CPU process (perf_counter).", ""]

    def trow(name, r, eq=True):
        t = r["timing"]
        e = r.get("equivalence")
        eqs = f"{e['n_equal']}/{e['n']}" if e else "(reference)"
        return (f"| {name} | {eqs} | {f(t['end_of_utterance_ms']['p50'], 2)} | {f(t['end_of_utterance_ms']['p95'], 2)} | "
                f"{f(t['end_of_utterance_ms']['max'])} | {f(t['push_frame_ms']['p50'], 3)} | {f(t['push_frame_ms']['p95'], 3)} | "
                f"{f(t['push_frame_ms']['max'])} | {f(t['total_cpu_per_utterance_ms']['p50'])} |")

    head = ["| condition | final decisions equal | end p50 | end p95 | end max | push p50 | push p95 | push max | CPU/utt p50 |",
            "|---|---|---|---|---|---|---|---|---|"]
    if (OUT / "b2t.json").exists():
        b = json.loads((OUT / "b2t.json").read_text(encoding="utf-8"))
        L += [f"## B2T '25 test streams ({b['n']} utterances, frame period 80 ms)", "",
              "End = `push(end event)` -> final decision (stream build, frame T, decode or finalize, trust core). "
              "Push = one `push(frame)`. Equal = action, shown texts, p_top1, guard risk and prediction set equal (`==`) "
              "to the M4-06 batch harness decisions.", ""] + head
        for k, r in b["conditions"].items():
            L.append(trow(k, r))
        L += ["", "### Outcomes (test split A)", "", "| condition | commits | wrong commits | ABSTAIN | OFFER |", "|---|---|---|---|---|"]
        for k, r in b["conditions"].items():
            o = r["outcome"]
            L.append(f"| {k} | {o['n_commit']} | {o['n_wrong_commit']} | {o['actions'].get('ABSTAIN', 0)} | {o['actions'].get('OFFER', 0)} |")
        pv = b["conditions"].get("incremental-ours+prewarm-light+previews", {}).get("stability")
        if pv:
            L += ["", "### Provisional top-1 stability (word previews)", ""] + stab_table({"B2T ours": pv})
    if (OUT / "synthetic.json").exists():
        s = json.loads((OUT / "synthetic.json").read_text(encoding="utf-8"))
        L += ["", f"## Synthetic simulator streams ({s['n']} utterances, median {s['frames']['median']:.0f} frames, "
              f"frame period {s['frame_period_s'] * 1e3:.0f} ms)", ""] + head
        for name, r in s["decoders"].items():
            for tag, rr in r.items():
                L.append(trow(f"{name} / {tag}", rr))
        L += ["", "### Provisional top-1 stability", ""] + stab_table({n: r["previews"]["stability"] for n, r in s["decoders"].items()})
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def stab_table(d: dict) -> list[str]:
    out = ["| decoder | previews/utt | top-1 change rate | changes/utt (median) | rewrites/utt (mean) | last preview = final | "
           "stable before end | time stable before end (median s) | share of utterance stable (median) | preview is prefix of final |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for k, m in d.items():
        out.append(f"| {k} | {f(m['previews_per_utterance_median'], 0)} | {f(m['top1_change_rate_mean'], 3)} | "
                   f"{f(m['top1_changes_per_utterance_median'], 0)} | {f(m['rewrites_per_utterance_mean'], 2)} | "
                   f"{f(m['last_preview_equals_final'], 3)} | {f(m['stable_before_end_fraction'], 3)} | "
                   f"{f(m['time_to_stable_before_end_s_median'], 2)} | {f(m['stable_share_of_utterance_median'], 3)} | "
                   f"{f(m['prefix_ok_fraction_mean'], 3)} |")
    return out


def main(argv: list[str]) -> None:
    stages = argv or ["synthetic", "b2t", "tables"]
    fns = {"synthetic": stage_synthetic, "b2t": stage_b2t, "tables": stage_tables}
    for s in stages:
        C.log(f"stage {s}")
        fns[s]()


if __name__ == "__main__":
    main(sys.argv[1:])
