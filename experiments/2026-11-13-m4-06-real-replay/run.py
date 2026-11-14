"""M4-06: a real-data frozen trust configuration, replayed through the streaming layer.

1. Fit the Paper 1 frozen recipe (git tag ``paper1-v4-frozen-config``; guard
   on, policy grid on fit-A, LTT max rule alpha 0.05 / delta 0.1 on the clean
   calibration half) on Brain-to-Text '25 fixed split A, for our decoder and
   for the published-sentence gate. Freeze each fitted pipeline with
   ``FrozenTrustConfig.from_pipeline`` and save the JSON (numbers only).
2. Write the 816 test trials as full-precision NTS JSON Lines (frames) and as
   hypothesis streams (the decoder n-best after the frozen frame temperature).
3. Replay them through ``StreamingTrustLayer`` on the frames route (with the
   matching decode_fn) and on the hypothesis route, with a provenance ledger.
4. Compare every final decision with the batch harness (action, shown texts,
   p_top1, guard risk), compute the test metrics from the streaming decisions,
   and compare them with the Paper 1 split A row (R4 result files).
5. Latency per decision (cached and uncached decode), memory, provenance.
6. The 300-trial control streams (real, other trial, frame-shuffled, uniform)
   through the streaming path.
7. Extra: the benchmark v0.1 NTS files (log-probs rounded to 6 decimals)
   through the frames route, to show what rounding does.

Per-trial outputs (decisions with texts, ledgers, streams) go to
``C:/Users/zhang/bci-data/derived/m4-06-real-replay`` (never into the repo).
The repo gets the two frozen configs (numbers only) and aggregate results.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-13-m4-06-real-replay/run.py [stage ...] [--workers N] [--out DIR]
Stages: fit streams replay uncached rounded controls memory tables (default: all).
``--workers N`` (M0-24): the ``uncached`` replay runs one session (post-implant day) per task
in a fidetype.utils.parallel.pmap pool. Decisions are the same as serial; the latency values
are then measured under parallel load (use serial + the timing CPU class for latency).
``--out DIR`` writes results and per-trial outputs to DIR (for checks; inputs stay in place).
"""

from __future__ import annotations

import json
import math
import pickle
import sys
import time
import tracemalloc
from dataclasses import replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments/2026-11-12-paper1-r1-analyses"))
import common as C  # noqa: E402  (sets the thread env vars, adds src/ to sys.path)

from fidetype.trust.frozen import PAPER1_V4_RECIPE, FrozenTrustConfig, paper1_v4_harness_config  # noqa: E402
from fidetype.trust.policy import Action  # noqa: E402
from fidetype.trust.provenance import ProvenanceLedger, stream_fingerprint, verify  # noqa: E402
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, _sha, iter_events  # noqa: E402
from fidetype.utils.parallel import pmap  # noqa: E402

CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
CFG_DIR = HERE / "configs"
CFG_DIR.mkdir(exist_ok=True)
DER = Path("C:/Users/zhang/bci-data/derived/m4-06-real-replay")
DER.mkdir(parents=True, exist_ok=True)
STREAMS = DER / "streams"
ROUNDED = Path(CONFIG["rounded_streams"])
R4_REF = REPO / "experiments/2026-11-12-paper1-r4-analyses/v4-derived/results/guard_controls.json"
C.Log.path = OUT / "run.log"
WHICH = ("ours", "published")
DER_OUT = DER  # per-trial outputs (``--out`` moves them)
WORKERS: int | None = None  # ``--workers``: parallel uncached replay (None = serial)


# ---------------------------------------------------------------------------
# Context (decoders, split A, fitted pipelines)
# ---------------------------------------------------------------------------


class Ctx:
    def __init__(self) -> None:
        ctx = C.b2t_ctx()
        cd = ctx.cached[0]
        cd.path = DER / "cache" / "decode-b2t-words-main.pkl"
        if cd.path.exists():
            cd.d.update(pickle.loads(cd.path.read_bytes()))
        self.ctx = ctx
        self.cd = cd
        by_day: dict = {}
        for i, t in enumerate(ctx.fit):
            by_day.setdefault(t.post_implant_day, []).append(i)
        ia, ib = [], []
        for _, idx in sorted(by_day.items()):
            ia += idx[0::2]
            ib += idx[1::2]
        self.fitA = [ctx.fit[i] for i in sorted(ia)]
        self.cal = [ctx.fit[i] for i in sorted(ib)]
        self.test = list(ctx.test)
        self.T = ctx.items(self.test)
        self.sym = {t.index: ctx.bt.B.to_symbol_stream(ctx.bt.B.trial_stream(t)) for t in self.test}
        self.pipes: dict = {}

    def fn(self, which: str):
        return self.ctx.dec.words_fn if which == "ours" else self.ctx.dec.published_plus_fn

    def fit(self, which: str):
        """The paper's split-A procedure with the frozen v4 harness settings."""
        if which in self.pipes:
            return self.pipes[which]
        v4 = paper1_v4_harness_config(seed=C.SEED, user_config=self.ctx.user)
        pipe = C.TrustPipeline(self.fn(which), replace(v4, risk_control="none"), {})
        pipe.fit(self.ctx.items(self.fitA), self.ctx.items(self.fitA))  # temperatures, conformal, guard, grid on fit-A
        pipe.config = v4
        pipe.calibrate_commit(self.ctx.items(self.cal))  # LTT, alpha 0.05, delta 0.1, combine max
        self.pipes[which] = pipe
        return pipe

    def save(self) -> None:
        self.cd.save()


def cfg_path(which: str) -> Path:
    return CFG_DIR / f"trust-config-b2t25-{which}-splitA.json"


def dump(obj, path: Path) -> None:
    C.dump(obj, path)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# NTS writing
# ---------------------------------------------------------------------------


def _f(v) -> float | None:
    v = float(v)
    return None if v == -math.inf else v


def header_event(stream) -> dict:
    h = {"type": "header", "spec_version": stream.version, "vocab": list(stream.vocab), "vocab_type": stream.vocab_type,
         "blank_id": stream.blank_id, "source": stream.source}
    if stream.frame_period is not None:
        h["frame_period"] = stream.frame_period
    if stream.latency is not None:
        h["latency"] = stream.latency
    h["meta"] = stream.meta
    return h


def frame_events(stream) -> list[dict]:
    return [{"type": "frame", "t": float(t), "log_probs": [_f(v) for v in row]}
            for t, row in zip(stream.frame_times, stream.log_probs)]


def hypothesis_event(nb, stream) -> dict:
    items = []
    for c in nb.candidates:
        it = {"text": c.text, "score": float(c.score)}
        for k in ("logp_acoustic", "logp_lm"):
            v = float(getattr(c, k))
            if math.isfinite(v):
                it[k] = v
        cc = list(c.char_confidences)
        if cc:
            it["char_confidences"] = [float(x) for x in cc]
        items.append(it)
    ev = {"type": "hypothesis", "id": "final", "is_final": True, "score_semantics": "log", "nbest": items}
    if len(stream.frame_times):
        ev["t_start"], ev["t_end"] = float(stream.frame_times[0]), float(stream.frame_times[-1])
    return ev


def write_events(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False, allow_nan=False) for e in events) + "\n", encoding="utf-8")


def nb_equal(a, b) -> bool:
    if len(a.candidates) != len(b.candidates):
        return False
    for x, y in zip(a.candidates, b.candidates):
        if x.text != y.text or float(x.score) != float(y.score):
            return False
        if tuple(float(v) for v in x.char_confidences) != tuple(float(v) for v in y.char_confidences):
            return False
    return True


# ---------------------------------------------------------------------------
# Stage: fit + freeze + batch reference
# ---------------------------------------------------------------------------


def batch_decisions(pipe, items) -> list[dict]:
    """The batch harness: TrustPipeline.analyze + policy.decide (final attempt), per item."""
    out = []
    for it in items:
        an = pipe.analyze(pipe.decode(it, 0))
        d = pipe.policy.decide(an.inputs, final_attempt=True)
        out.append({"action": d.action.value, "shown": list(d.shown_candidates), "p_top1": an.inputs.p_top1,
                    "guard_risk": an.guard.risk, "set": list(an.inputs.set_indices), "top": an.inputs.texts[0] if an.inputs.texts else ""})
    return out


def stage_fit(X: Ctx) -> dict:
    res: dict = {"recipe": PAPER1_V4_RECIPE, "n_fitA": len(X.fitA), "n_cal": len(X.cal), "n_test": len(X.test), "conditions": {}}
    for which in WHICH:
        t0 = time.time()
        pipe = X.fit(which)
        fz = FrozenTrustConfig.from_pipeline(pipe, name=f"b2t25-t15-{which}-splitA-v4", recipe={
            **PAPER1_V4_RECIPE,
            "fitted_on": "Brain-to-Text '25 T15 copy task, fixed split A: fit-A = alternate fit-half trials per day (411), "
                         "clean calibration = the other fit-half trials (401)",
            "decoder": CONFIG["decoders"][which],
            "experiment": "experiments/2026-11-13-m4-06-real-replay"})
        fz.save(cfg_path(which))
        fz2 = FrozenTrustConfig.load(cfg_path(which))
        assert fz2.config_id == fz.config_id, "config round trip changed the id"
        bd = batch_decisions(pipe, X.T)
        dump({"trials": [t.index for t in X.test], "decisions": bd}, DER / f"batch-{which}.json")
        recs = pipe.run_items(X.T)
        m = C.metrics(C.rec_arrays(recs))
        res["conditions"][which] = {
            "config_id": fz.config_id, "commit_p": fz.policy["commit_p"], "policy": fz.policy,
            "frame_T": fz.frame_temperature, "sentence_T": fz.sentence_temperature, "conformal_q": fz.conformal_q,
            "risk_control": fz.risk_control, "fit_report": C.clean(pipe.fit_report), "batch_test": m,
            "batch_n_commit": int(sum(d["action"] == "COMMIT" for d in bd)), "seconds": time.time() - t0}
        C.log(f"fit {which}: {fz.config_id} commit_p {fz.policy['commit_p']} (LTT {fz.risk_control.get('threshold')}); "
              f"batch test wrong-commit {m['wrong_commit']:.4f} commit {m['commit_rate']:.3f} eWPM {m['ewpm']:.2f}")
        X.save()
    dump(res, OUT / "fit.json")
    return res


# ---------------------------------------------------------------------------
# Stage: streams
# ---------------------------------------------------------------------------


def stage_streams(X: Ctx) -> dict:
    info: dict = {"frames": 0, "hypothesis": {}, "nbest_roundtrip_equal": {}}
    for t in X.test:
        s = X.sym[t.index]
        p = STREAMS / "frames" / f"trial-{t.index:04d}.jsonl"
        if not p.exists():
            write_events(p, [header_event(s)] + frame_events(s) + [{"type": "end"}])
        info["frames"] += 1
    from fidetype.trust.streaming import nbest_from_hypothesis
    for which in WHICH:
        pipe = X.fit(which)
        ok = 0
        for t, it in zip(X.test, X.T):
            s = X.sym[t.index]
            nb = pipe.decode(it, 0)  # the decoder's n-best after the frozen frame temperature (upstream)
            ev = hypothesis_event(nb, s)
            ok += nb_equal(nbest_from_hypothesis(ev), nb)
            write_events(STREAMS / f"hyp-{which}" / f"trial-{t.index:04d}.jsonl", [header_event(s), ev, {"type": "end"}])
        info["hypothesis"][which] = len(X.test)
        info["nbest_roundtrip_equal"][which] = ok
        C.log(f"streams {which}: hypothesis files {len(X.test)}, n-best round trip equal {ok}/{len(X.test)}")
    X.save()
    dump(info, OUT / "streams.json")
    return info


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


def replay_files(layer: StreamingTrustLayer, files: list[tuple[str, Path]]) -> tuple[list, dict]:
    """Push the files (session, path) in order. Return the final decisions and push timings."""
    decs = []
    tm: dict = {"frame": [], "hypothesis": [], "final_push": [], "other": []}
    for sid, p in files:
        got = []
        for ev in iter_events(p):
            t0 = time.perf_counter()
            out = layer.push(ev, sid)
            dt = time.perf_counter() - t0
            typ = ev.get("type")
            if out:
                tm["final_push"].append(dt)
            elif typ in ("frame", "hypothesis"):
                tm[typ].append(dt)
            else:
                tm["other"].append(dt)
            got += out
        got += layer.end_of_utterance(sid)  # no-op when the end event closed it
        fin = [d for d in got if d.final]
        assert len(fin) == 1, f"{p.name}: {len(fin)} final decisions"
        decs.append(fin[0])
    return decs, tm


def pct(xs, q) -> float | None:
    return float(np.percentile(np.asarray(xs) * 1e3, q)) if len(xs) else None


def timing_summary(decs, tm) -> dict:
    lat = [d.provenance["latency_s"] for d in decs]
    out = {"decision_ms": {"p50": pct(lat, 50), "p95": pct(lat, 95), "max": pct(lat, 100), "n": len(lat)}}
    for k in ("frame", "hypothesis", "final_push"):
        if tm[k]:
            out[f"push_{k}_ms"] = {"p50": pct(tm[k], 50), "p95": pct(tm[k], 95), "max": pct(tm[k], 100), "n": len(tm[k])}
    return out


class ReplayPolicy:
    """Feeds the streaming decisions, in order, into the harness user simulation (for eWPM)."""

    def __init__(self, decs) -> None:
        self.it = iter(decs)

    def decide(self, inputs, final_attempt=False):
        d = next(self.it)
        assert tuple(d.inputs.texts) == tuple(inputs.texts), "replayed decision belongs to another n-best"
        return d.decision


def compare(decs, batch: list[dict]) -> dict:
    mism = []
    for i, (d, b) in enumerate(zip(decs, batch["decisions"])):
        diff = []
        if d.action.value != b["action"]:
            diff.append("action")
        if list(d.shown) != b["shown"]:
            diff.append("shown")
        if float(d.inputs.p_top1) != float(b["p_top1"]):
            diff.append("p_top1")
        gr = float(d.guard.risk) if d.guard is not None else float("nan")
        if gr != float(b["guard_risk"]):
            diff.append("guard_risk")
        if list(d.inputs.set_indices) != b["set"]:
            diff.append("prediction_set")
        if diff:
            mism.append({"trial": batch["trials"][i], "fields": diff, "stream_action": d.action.value, "batch_action": b["action"],
                         "dp_top1": float(d.inputs.p_top1) - float(b["p_top1"]), "dguard": gr - float(b["guard_risk"])})
    return {"n": len(decs), "n_equal": len(decs) - len(mism), "mismatches": mism,
            "max_abs_dp_top1": max((abs(m["dp_top1"]) for m in mism), default=0.0),
            "max_abs_dguard": max((abs(m["dguard"]) for m in mism if math.isfinite(m["dguard"])), default=0.0)}


def provenance_check(decs, fz: FrozenTrustConfig, ledger: ProvenanceLedger, route: str, X: Ctx, expected: list) -> dict:
    ok_cfg = sum(d.provenance.get("config_id") == fz.config_id for d in decs)
    ok_ledger = sum(bool(d.provenance.get("ledger_decision_id")) for d in decs)
    if route == "frames":
        ok_hash = sum(d.provenance["input"].get("stream_sha256") == e for d, e in zip(decs, expected))
    else:
        ok_hash = sum(d.provenance["input"].get("hypothesis_sha256") == e for d, e in zip(decs, expected))
    v = verify(ledger.entries)
    kinds: dict = {}
    for e in ledger.entries:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    ctx_cfg = [e["body"].get("trust_config", {}).get("id") for e in ledger.entries if e["kind"] == "context"]
    return {"decisions": len(decs), "config_id_ok": ok_cfg, "input_hash_ok": ok_hash, "ledger_id_ok": ok_ledger,
            "ledger_verify_ok": bool(v.ok), "ledger_errors": list(v.errors)[:5], "ledger_entries": kinds,
            "ledger_contexts_cite_config": all(c == fz.config_id for c in ctx_cfg) and bool(ctx_cfg)}


def test_files(X: Ctx, route: str, which: str) -> list[tuple[str, Path]]:
    d = STREAMS / ("frames" if route == "frames" else f"hyp-{which}")
    return [(f"day{t.post_implant_day:03d}", d / f"trial-{t.index:04d}.jsonl") for t in X.test]


_W: dict = {}  # per-process state of pmap workers


def init_replay_worker() -> None:
    """pmap initializer: the decoders (loaded once per worker process)."""
    _W["ctx"] = C.b2t_ctx()


def replay_task(task: tuple) -> tuple[list, dict]:
    """Replay the files of one session with a fresh layer (the session state stays in one process)."""
    which, route, kind, files = task
    ctx = _W["ctx"]
    fz = FrozenTrustConfig.load(cfg_path(which))
    if kind != "uncached":
        raise ValueError(f"parallel replay supports the uncached decode only, not {kind!r}")
    raw = ctx.cached[0].fn  # the bound Decoders.words_fn, below the disk cache (as stage_uncached)
    ctx.dec._wcache = {}

    def fresh(stream):
        ctx.dec._wcache = {}
        return raw(stream)

    layer = StreamingTrustLayer(fz, decode_fn=fresh if route == "frames" else None,
                                streaming=StreamingConfig(route=route, max_attempts=1), ledger=None)
    return replay_files(layer, [(sid, Path(fp)) for sid, fp in files])


def replay_parallel(which: str, route: str, kind: str, files: list[tuple[str, Path]], workers: int | None) -> tuple[list, dict]:
    """``replay_files`` with one pmap task per session; decisions and timings in file order."""
    groups: dict = {}
    for sid, fp in files:
        groups.setdefault(sid, []).append((sid, str(fp)))
    order = list(groups)
    assert [f for sid in order for f in groups[sid]] == [(sid, str(fp)) for sid, fp in files], "sessions are not contiguous"
    big_first = sorted(order, key=lambda sid: -len(groups[sid]))  # longest sessions start first
    info: dict = {}
    got = pmap(replay_task, [(which, route, kind, groups[sid]) for sid in big_first], workers=workers,
               initializer=init_replay_worker, label=f"replay {which}/{route}", log=C.log, mem_per_worker_gb=1.6, info=info)
    by_sid = dict(zip(big_first, got))
    decs: list = []
    tm: dict = {"frame": [], "hypothesis": [], "final_push": [], "other": []}
    for sid in order:
        d, t = by_sid[sid]
        decs += d
        for k in tm:
            tm[k] += t[k]
    tm["_parallel"] = info
    return decs, tm


def run_route(X: Ctx, which: str, route: str, decode_fn=None, files=None, tag: str = "", ledger_on: bool = True,
              parallel_kind: str | None = None) -> dict:
    fz = FrozenTrustConfig.load(cfg_path(which))
    lp = DER_OUT / f"ledger-{which}-{route}{tag}.jsonl"
    if lp.exists():
        lp.unlink()
    ledger = ProvenanceLedger(lp, text_mode="hash") if ledger_on else None
    layer = StreamingTrustLayer(fz, decode_fn=decode_fn if route == "frames" else None,
                                streaming=StreamingConfig(route=route, max_attempts=1), ledger=ledger)
    files = files or test_files(X, route, which)
    t0 = time.time()
    if parallel_kind and WORKERS != 1 and WORKERS is not None and ledger is None:
        decs, tm = replay_parallel(which, route, parallel_kind, files, WORKERS)
    else:
        decs, tm = replay_files(layer, files)
    wall = time.time() - t0
    batch = load(DER / f"batch-{which}.json")
    cmp_ = compare(decs, batch)
    pipe = X.fit(which)
    recs = pipe.run_items(X.T, ReplayPolicy(decs))
    m = C.metrics(C.rec_arrays(recs))
    m["n_commit"] = int(sum(d.action == Action.COMMIT for d in decs))
    m["n_wrong_commit"] = int(sum(bool(r.wrong_commit) for r in recs))
    if route == "frames":
        expected = [stream_fingerprint(X.sym[t.index]) for t in X.test]
    else:
        expected = [_sha(json.loads((STREAMS / f"hyp-{which}" / f"trial-{t.index:04d}.jsonl").read_text(encoding="utf-8").splitlines()[1]))
                    for t in X.test]
    prov = provenance_check(decs, fz, ledger, route, X, expected) if ledger is not None else None
    dump({"trials": [t.index for t in X.test],
          "decisions": [{**d.to_event(include_text=True), "guard_risk_exact": float(d.guard.risk) if d.guard else None,
                         "p_top1_exact": float(d.inputs.p_top1)} for d in decs]},
         DER_OUT / f"stream-{which}-{route}{tag}.json")
    r = {"which": which, "route": route, "tag": tag, "config_id": fz.config_id, "wall_s": wall, "equivalence": cmp_,
         "metrics": m, "timing": timing_summary(decs, tm), "provenance": prov}
    if "_parallel" in tm:
        r["parallel"] = {**tm["_parallel"], "note": "latency measured under parallel load; not a latency result"}
    C.log(f"replay {which}/{route}{tag}: equal {cmp_['n_equal']}/{cmp_['n']}; wrong-commit {m['wrong_commit']:.4f} "
          f"({m['n_wrong_commit']}) commit {m['commit_rate']:.3f} ({m['n_commit']}) eWPM {m['ewpm']:.2f}; decision p50/p95 "
          f"{r['timing']['decision_ms']['p50']:.3f}/{r['timing']['decision_ms']['p95']:.3f} ms; ledger "
          f"{None if prov is None else prov['ledger_verify_ok']} ({wall:.0f}s)")
    return r


def stage_replay(X: Ctx) -> dict:
    res = {}
    for which in WHICH:
        res[f"{which}/frames"] = run_route(X, which, "frames", decode_fn=X.fn(which))
        res[f"{which}/hypothesis"] = run_route(X, which, "hypothesis")
        X.save()
    dump(res, OUT / "replay.json")
    return res


def stage_uncached(X: Ctx) -> dict:
    """Frames route, ours, with a fresh decode per trial (no disk or memory cache): real decision latency."""
    raw = X.cd.fn  # the bound Decoders.words_fn, below the disk cache
    X.ctx.dec._wcache = {}

    def fresh(stream):
        X.ctx.dec._wcache = {}
        return raw(stream)

    r = run_route(X, "ours", "frames", decode_fn=fresh, tag="-uncached", ledger_on=False, parallel_kind="uncached")
    dump(r, OUT / "uncached.json")
    return r


def stage_rounded(X: Ctx) -> dict:
    """Benchmark v0.1 NTS files (6-decimal log-probs, phoneme vocab) through the frames route."""
    B = X.ctx.bt.B
    res = {}
    files = [(f"day{t.post_implant_day:03d}", ROUNDED / f"t15-copytask-{t.index:04d}.jsonl") for t in X.test]
    missing = [str(p) for _, p in files if not p.exists()]
    if missing:
        res["error"] = f"{len(missing)} benchmark files missing"
        dump(res, OUT / "rounded.json")
        return res
    for which in WHICH:
        fn = X.fn(which)
        r = run_route(X, which, "frames", decode_fn=lambda s, fn=fn: fn(B.to_symbol_stream(s)), files=files, tag="-rounded6",
                      ledger_on=False)
        # Cause of each mismatch: the top text differs (decoder) or only the scores moved.
        sd = load(DER / f"stream-{which}-frames-rounded6.json")["decisions"]
        bd = load(DER / f"batch-{which}.json")["decisions"]
        top_diff = sum(1 for m in r["equivalence"]["mismatches"]
                       for i in [load(DER / f"batch-{which}.json")["trials"].index(m["trial"])]
                       if (sd[i].get("shown") or [None])[0] != (bd[i]["shown"] or [None])[0])
        r["equivalence"]["mismatches_with_other_shown_top"] = top_diff
        res[which] = r
        X.save()
    dump(res, OUT / "rounded.json")
    return res


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------


def control_streams(X: Ctx):
    """The 300-trial audit draw of the R4 guard_controls run (same seed, same order of RNG use)."""
    from fidetype.trust.guard import shuffle_stream, uniform_stream
    ctx = X.ctx
    bt = ctx.bt
    rng = np.random.default_rng(bt.SEED)
    na = min(len(ctx.test), bt.CONFIG["audit_n"])
    aud_idx = sorted(rng.choice(len(ctx.test), na, replace=False).tolist())
    atest = [ctx.test[i] for i in aud_idx]
    base = [bt.B.to_symbol_stream(bt.B.trial_stream(t)) for t in atest]
    perm = rng.permutation(len(base))
    for i in range(len(perm)):
        if atest[perm[i]].truth_words == atest[i].truth_words:
            perm[i], perm[(i + 1) % len(perm)] = perm[(i + 1) % len(perm)], perm[i]
    nulls = {"real": base, "other_trial": [base[j] for j in perm],
             "frame_shuffled": [shuffle_stream(s, rng) for s in base], "uniform": [uniform_stream(s, rng, 0.05) for s in base]}
    return atest, nulls


def stage_controls(X: Ctx) -> dict:
    from fidetype.streams.spec import NeuralTextStream
    atest, nulls = control_streams(X)
    ref = load(R4_REF)["conditions"]
    res: dict = {"n": len(atest), "conditions": {}}
    for which in WHICH:
        pipe = X.fit(which)
        fz = FrozenTrustConfig.load(cfg_path(which))
        T = pipe.frame_scaler.temperature
        fn = X.fn(which)
        rw: dict = {}
        for cond, ss in nulls.items():
            # Header meta: the published gate looks up the intended trial's published sentence (as in the paper).
            streams = []
            for i, s in enumerate(ss):
                if which == "published":
                    s = NeuralTextStream(s.log_probs, s.frame_times, s.vocab, s.blank_id, s.source,
                                         {**s.meta, "fidetype.trial_index": atest[i].index}, vocab_type=s.vocab_type)
                streams.append(s)
            # Batch reference (the paper's audit path) and the streams.
            bcom, files_f, files_h = [], [], []
            for i, s in enumerate(streams):
                s2 = pipe.frame_scaler.transform_stream(s) if T != 1.0 else s
                nb = fn(s2)
                an = pipe.analyze(nb)
                d = pipe.policy.decide(an.inputs, final_attempt=True)
                bcom.append({"action": d.action.value, "shown": list(d.shown_candidates), "p_top1": an.inputs.p_top1,
                             "guard_risk": an.guard.risk, "set": list(an.inputs.set_indices)})
                pf = STREAMS / f"ctl-{which}" / cond / f"c{i:03d}-frames.jsonl"
                ph = STREAMS / f"ctl-{which}" / cond / f"c{i:03d}-hyp.jsonl"
                write_events(pf, [header_event(s)] + frame_events(s) + [{"type": "end"}])
                write_events(ph, [header_event(s), hypothesis_event(nb, s), {"type": "end"}])
                files_f.append((f"ctl-{cond}", pf))
                files_h.append((f"ctl-{cond}", ph))
            batch = {"trials": list(range(len(streams))), "decisions": bcom}
            out = {"batch_n_commit": sum(b["action"] == "COMMIT" for b in bcom)}
            for route, files in (("frames", files_f), ("hypothesis", files_h)):
                layer = StreamingTrustLayer(fz, decode_fn=fn if route == "frames" else None,
                                            streaming=StreamingConfig(route=route, max_attempts=1))
                decs, _ = replay_files(layer, files)
                cm = compare(decs, batch)
                k = int(sum(d.action == Action.COMMIT for d in decs))
                out[route] = {"n_commit": k, "n": len(decs), "equal_to_batch": cm["n_equal"],
                              "commit_cp95_one_sided_upper": cp_upper(k, len(decs))}
            out["paper_n_commit"] = ref[f"b2t-{which}"]["controls"]["split A guard LTT max"][cond]["n_commit"]
            rw[cond] = out
            C.log(f"controls {which}/{cond}: paper {out['paper_n_commit']}, batch {out['batch_n_commit']}, "
                  f"stream frames {out['frames']['n_commit']} (equal {out['frames']['equal_to_batch']}), "
                  f"hypothesis {out['hypothesis']['n_commit']} (equal {out['hypothesis']['equal_to_batch']})")
            X.save()
        res["conditions"][which] = rw
    dump(res, OUT / "controls.json")
    return res


def cp_upper(k: int, n: int, conf: float = 0.95) -> float:
    """Exact one-sided Clopper-Pearson upper bound."""
    from scipy.stats import beta
    return 1.0 if k >= n else float(beta.ppf(conf, k + 1, n - k))


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


def stage_memory(X: Ctx) -> dict:
    """Per-session buffer and traced Python allocation of the layer (cached decode, so the decoder is not counted)."""
    res = {}
    for which in WHICH:
        fz = FrozenTrustConfig.load(cfg_path(which))
        for route in ("frames", "hypothesis"):
            layer = StreamingTrustLayer(fz, decode_fn=X.fn(which) if route == "frames" else None,
                                        streaming=StreamingConfig(route=route, max_attempts=1))
            files = test_files(X, route, which)
            max_buf, max_frames = 0, 0
            for sid, p in files:  # warm (cache hits), and the largest buffer
                for ev in iter_events(p):
                    if ev.get("type") == "end":
                        st = layer.session_state(sid)
                        max_buf, max_frames = max(max_buf, st["buffered_bytes"]), max(max_frames, st["buffered_frames"])
                    layer.push(ev, sid)
            n_frames = [sum(1 for _ in iter_events(p)) - 2 for _, p in files[:1]]
            layer2 = StreamingTrustLayer(fz, decode_fn=X.fn(which) if route == "frames" else None,
                                         streaming=StreamingConfig(route=route, max_attempts=1))
            evs = [(sid, list(iter_events(p))) for sid, p in files[:100]]
            tracemalloc.start()
            for sid, el in evs:
                for ev in el:
                    layer2.push(ev, sid)
            cur, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            res[f"{which}/{route}"] = {"max_buffered_bytes_per_session": max_buf, "max_buffered_frames": max_frames,
                                       "traced_peak_bytes_100_trials": peak, "traced_retained_bytes_100_trials": cur,
                                       "sessions": len(layer.sessions), "first_file_events": n_frames}
            C.log(f"memory {which}/{route}: max buffer {max_buf / 1024:.1f} KiB ({max_frames} frames); traced peak "
                  f"{peak / 1024:.1f} KiB, retained {cur / 1024:.1f} KiB over 100 trials")
    dump(res, OUT / "memory.json")
    return res


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def stage_tables() -> None:
    fit = load(OUT / "fit.json")
    rep = load(OUT / "replay.json")
    ref = load(R4_REF)["conditions"]
    unc = load(OUT / "uncached.json") if (OUT / "uncached.json").exists() else None
    rnd = load(OUT / "rounded.json") if (OUT / "rounded.json").exists() else {}
    ctl = load(OUT / "controls.json") if (OUT / "controls.json").exists() else None
    mem = load(OUT / "memory.json") if (OUT / "memory.json").exists() else None
    stm = load(OUT / "streams.json") if (OUT / "streams.json").exists() else None
    L = ["# M4-06 tables: real-data frozen config through the streaming trust layer", "",
         "B2T '25 T15, fixed split A, Paper 1 frozen recipe (guard + LTT max, alpha 0.05, delta 0.1). Test = 816 trials.", "",
         "## Frozen configurations", "",
         "| decoder | config_id | frame T | sentence T | conformal q | grid commit_p | LTT threshold (n, feasible) | final commit_p | commit_max_risk | paper λ (LTT max) |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for w in WHICH:
        c = fit["conditions"][w]
        rc = c["risk_control"]
        grid_p = c["fit_report"].get("policy_config", {}).get("commit_p")
        lam = ref[f"b2t-{w}"]["split A (guard on, refitted)"]["lambda"]["LTT max"]
        L.append(f"| {w} | `{c['config_id']}` | {c['frame_T']:.4f} | {c['sentence_T']:.4f} | {C.fnum(c['conformal_q']):.4f} | {grid_p} | "
                 f"{rc.get('threshold')} ({rc.get('n')}, {rc.get('feasible')}) | {c['commit_p']} | {c['policy'].get('commit_max_risk')} | {lam} |")
    L += ["", "## Equivalence: streaming final decision vs batch harness (per test trial)", "",
          "Fields compared exactly (==): action, shown texts, p_top1, guard risk, prediction set.", "",
          "| decoder / route | input | equal / n | mismatches |", "|---|---|---|---|"]
    rows = [(k, "full-precision NTS", v) for k, v in rep.items()]
    if unc:
        rows.append(("ours/frames (fresh decode)", "full-precision NTS", unc))
    for w in WHICH:
        if w in rnd:
            rows.append((f"{w}/frames", "benchmark v0.1 NTS (6 decimals)", rnd[w]))
    for k, inp, v in rows:
        e = v["equivalence"]
        extra = ""
        if e["mismatches"]:
            acts = sum(1 for m in e["mismatches"] if "action" in m["fields"])
            extra = f"{len(e['mismatches'])} (action differs in {acts}; max abs Δp_top1 {e['max_abs_dp_top1']:.2e})"
            if "mismatches_with_other_shown_top" in e:
                extra += f"; other top text in {e['mismatches_with_other_shown_top']}"
        L.append(f"| {k} | {inp} | {e['n_equal']} / {e['n']} | {extra or '0'} |")
    L += ["", "## Test metrics from the streaming decisions vs Paper 1 (Tab. 3, guaranteed rule, split A)", "",
          "| decoder / route | wrong-commit (n) | commit rate (n) | eWPM | silent error | paper wrong-commit (n) | paper commit (n) | paper eWPM |",
          "|---|---|---|---|---|---|---|---|"]
    for k, v in rep.items():
        w = k.split("/")[0]
        m = v["metrics"]
        p = ref[f"b2t-{w}"]["split A (guard on, refitted)"]["point"]["LTT max"]
        L.append(f"| {k} | {m['wrong_commit']:.4f} ({m['n_wrong_commit']}) | {m['commit_rate']:.3f} ({m['n_commit']}) | {m['ewpm']:.2f} | "
                 f"{m['silent_error']:.4f} | {p['wrong_commit']:.4f} ({p['n_wrong_commit']}) | {p['commit_rate']:.3f} ({p['n_commit']}) | {p['ewpm']:.2f} |")
    for w in WHICH:
        if w in rnd:
            m = rnd[w]["metrics"]
            L.append(f"| {w}/frames, 6-decimal files | {m['wrong_commit']:.4f} ({m['n_wrong_commit']}) | {m['commit_rate']:.3f} ({m['n_commit']}) | "
                     f"{m['ewpm']:.2f} | {m['silent_error']:.4f} | | | |")
    L += ["", "## Latency per decision (one CPU process, perf_counter)", "",
          "Decision = push of the event that closes the utterance -> final decision (frames route: includes building the stream, "
          "frame temperature, decode, trust core; hypothesis route: trust core only).", "",
          "| decoder / route | decode | decision p50 ms | p95 ms | max ms | push(frame) p50 / p95 ms | push(hypothesis, final) p50 ms |",
          "|---|---|---|---|---|---|---|"]
    lrows = [(k, "disk cache (paper decodes)", v) for k, v in rep.items()]
    if unc:
        lrows.append(("ours/frames", "fresh decode", unc))
    for w in WHICH:
        if w in rnd:
            lrows.append((f"{w}/frames, 6-decimal files", "fresh decode (cache miss)" if w == "ours" else "fresh decode of ours + lookup", rnd[w]))
    for k, dec, v in lrows:
        t = v["timing"]
        dm = t["decision_ms"]
        pf = t.get("push_frame_ms")
        pfs = "—" if not pf else "{:.4f} / {:.4f}".format(pf["p50"], pf["p95"])
        hs = "{:.3f}".format(dm["p50"]) if v["route"] == "hypothesis" else "—"
        L.append(f"| {k} | {dec} | {dm['p50']:.3f} | {dm['p95']:.3f} | {dm['max']:.3f} | {pfs} | {hs} |")
    if mem:
        L += ["", "## Memory", "", "| decoder / route | max buffer per session | max frames buffered | traced peak (100 trials, cached decode) | retained after 100 trials |",
              "|---|---|---|---|---|"]
        for k, v in mem.items():
            L.append(f"| {k} | {v['max_buffered_bytes_per_session'] / 1024:.1f} KiB | {v['max_buffered_frames']} | "
                     f"{v['traced_peak_bytes_100_trials'] / 1024:.1f} KiB | {v['traced_retained_bytes_100_trials'] / 1024:.1f} KiB |")
    L += ["", "## Provenance", "", "| decoder / route | decisions | config_id ok | input hash ok | ledger id ok | ledger verifies | ledger entries |",
          "|---|---|---|---|---|---|---|"]
    for k, v in rep.items():
        p = v["provenance"]
        L.append(f"| {k} | {p['decisions']} | {p['config_id_ok']} | {p['input_hash_ok']} | {p['ledger_id_ok']} | {p['ledger_verify_ok']} | "
                 f"{', '.join(f'{a} {b}' for a, b in p['ledger_entries'].items())} |")
    if ctl:
        L += ["", f"## Controls ({ctl['n']} streams each; commits, one-sided 95 % CP upper bound)", "",
              "| decoder | control | paper (split A, guard, LTT max) | batch (this run) | streaming frames (equal to batch) | streaming hypothesis (equal to batch) |",
              "|---|---|---|---|---|---|"]
        for w, rw in ctl["conditions"].items():
            for cond, o in rw.items():
                f, h = o["frames"], o["hypothesis"]
                L.append(f"| {w} | {cond} | {o['paper_n_commit']}/{f['n']} | {o['batch_n_commit']}/{f['n']} | "
                         f"{f['n_commit']}/{f['n']} (<= {f['commit_cp95_one_sided_upper']:.4f}; {f['equal_to_batch']}) | "
                         f"{h['n_commit']}/{h['n']} ({h['equal_to_batch']}) |")
    if stm:
        L += ["", f"Streams: {stm['frames']} frame files; hypothesis n-best JSON round trip equal: "
              + ", ".join(f"{k} {v}/{stm['hypothesis'][k]}" for k, v in stm["nbest_roundtrip_equal"].items()) + "."]
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv: list[str]) -> None:
    global WORKERS, OUT, DER_OUT
    argv = list(argv)
    if "--workers" in argv:
        i = argv.index("--workers")
        WORKERS = int(argv[i + 1])
        del argv[i:i + 2]
    if "--out" in argv:
        i = argv.index("--out")
        OUT = DER_OUT = Path(argv[i + 1])
        OUT.mkdir(parents=True, exist_ok=True)
        C.Log.path = OUT / "run.log"
        del argv[i:i + 2]
    stages = argv or ["fit", "streams", "replay", "uncached", "rounded", "controls", "memory", "tables"]
    X = None
    for st in stages:
        if st != "tables" and X is None:
            X = Ctx()
        t0 = time.time()
        C.log(f"stage {st} start")
        {"fit": lambda: stage_fit(X), "streams": lambda: stage_streams(X), "replay": lambda: stage_replay(X),
         "uncached": lambda: stage_uncached(X), "rounded": lambda: stage_rounded(X), "controls": lambda: stage_controls(X),
         "memory": lambda: stage_memory(X), "tables": stage_tables}[st]()
        C.log(f"stage {st} done ({time.time() - t0:.0f}s)")
    if X is not None:
        X.save()


if __name__ == "__main__":
    main(sys.argv[1:])
