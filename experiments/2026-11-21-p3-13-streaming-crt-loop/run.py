"""P3-13: the streaming CRT model (per-user weights) in the decision loop gives the same decisions as the batch
log-probs.

Pre-registration: plan.md (this folder). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0. Per-window files stay
in C:/Users/zhang/bci-data/derived/p3-13/. The P11-01, P11-07, P11-09, P11-11, P11-12 and P3-12 files are read
only. CPU only (NumPy; no torch here).

Stages (repo root; launch.py runs them detached, each under the isolation runner):

  check     for each of the 1,221 evaluation windows x (real, shuffled, zeros): (B) the P3-12 streaming pipeline on
            the batch log-probs of P11-09 (reference decisions) and (S) the same pipeline fed chunk by chunk by
            the streaming CRT model (fidetype.pretrained._crt.CRTStream, the window's own user weights) ->
            merge_to_key_ctc -> GuardSession.push -> beam; log-prob and decision comparison; safe WPM rule.
  latency   timed (class timing, 1 thread): decision latency D of path S on the real windows (FL@B8).
  score     aggregates and verdicts -> results/results.json.
"""

from __future__ import annotations

import os
import sys

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ["HIP_VISIBLE_DEVICES"] = ""  # CPU only
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import argparse  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p3-13"  # the only place this task writes per-window files
P1101 = DER / "p11-01-emg-decoder"  # READ ONLY
P1107 = DER / "p11-07"  # READ ONLY
P1109 = DER / "p11-09"  # READ ONLY
P312 = DER / "p3-12"  # READ ONLY
EXP312 = REPO / "experiments" / "2026-11-20-p3-12-emg-latency-budget"
OUT = HERE / "results"
STOP = OWN / "STOP"

CHUNK = 4
WARMUP = 20
KINDS = ("real", "shuffled", "zeros")
SHUF_SALT = "fidetype-p11-09-2026-11-19"  # P11-09 HASH_SALT (its time-shuffle seed per session)
CKPT_EVERY = 100
# pre-registered rules (plan.md)
PTOP1_TOL = 1e-3  # |p_top1 stream - p_top1 batch| for a "same decision"
PROB_TOL = 1e-3  # secondary: max abs probability diff of the 33-class guard rows, stream vs batch
SAFE_MIN = 3.32  # P3-12 tolerance: 3.37 - 0.05
BUDGET_MS, CHUNK_BUDGET_MS = 50.0, 40.0


def log(*a: object) -> None:
    OUT.mkdir(exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def own(*parts: str) -> Path:
    p = OWN.joinpath(*parts)
    assert OWN in p.parents
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def save_json(obj: object, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def stopped() -> bool:
    return STOP.exists()


def keep_awake(on: bool) -> None:
    if os.name != "nt":
        return
    import ctypes

    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def p312():
    """The P3-12 runner as a module. Read-only use: Ctx, decision_record, model_inputs, session_feat only."""
    if "p312run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("p312run", EXP312 / "run.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["p312run"] = m
        argv, sys.argv = sys.argv, [str(EXP312 / "run.py")]
        try:
            spec.loader.exec_module(m)
        finally:
            sys.argv = argv
    return sys.modules["p312run"]


_PARAMS: dict[int, dict] = {}


def user_params(i: int) -> dict:
    """Per-user P11-01 weights as NumPy arrays (export_params.py; local only)."""
    if i not in _PARAMS:
        with np.load(own(f"params-u{i}.npz")) as z:
            _PARAMS[i] = {k: np.asarray(z[k]) for k in z.files}
    return _PARAMS[i]


_PERM: dict[str, np.ndarray] = {}


def shuffle_perm(session: str, n: int) -> np.ndarray:
    """The P11-09 time-shuffle permutation of one session (same seed rule as its infer stage)."""
    if session not in _PERM:
        seed = int(hashlib.sha256(f"{SHUF_SALT}|shuffle|{session}".encode()).hexdigest()[:8], 16)
        _PERM[session] = np.random.default_rng(seed).permutation(n)
    return _PERM[session]


class Feed:
    """The model input of one window and one kind: feature frames from ``a0`` (receptive-field warm-up) to ``end``.

    Real: the session features. Shuffled: the same frames of the P11-09 time-shuffled session. Zeros: the zero-EMG
    feature (every band log(0 + log_eps)), as the P11-09 zero control.
    """

    def __init__(self, r: dict, kind: str, rf: int) -> None:
        P = p312()
        f = P.session_feat(r["session"])
        self.lo, self.end = int(r["lo"]), int(r["end"])
        self.a0 = max(0, self.lo - (rf - 1))
        n = self.end - self.a0
        if kind == "real":
            self.x = np.asarray(f[self.a0:self.end], np.float32)
        elif kind == "shuffled":
            perm = shuffle_perm(r["session"], len(f))
            self.x = np.asarray(f[perm[self.a0:self.end]], np.float32)
        elif kind == "zeros":
            eps = float(load_json(P1101 / "index.json")["log_eps"])  # type: ignore[index]
            self.x = np.full((n, f.shape[1], f.shape[2]), np.log(eps), np.float32)
        else:
            raise ValueError(kind)
        assert len(self.x) == n


def warm_model(p: dict, kw: dict, feed: Feed):
    """A fresh CRTStream fed the warm-up frames [a0, lo) in 4-frame chunks (outputs dropped)."""
    import fidetype.pretrained._crt as C

    m = C.CRTStream(p, **kw)
    w = feed.lo - feed.a0
    for a in range(0, w, CHUNK):
        m.push(feed.x[a:min(a + CHUNK, w)])
    return m


def run_pipeline(cx, cfg: dict, holder: dict, sess, chunks):
    """P3-12 path: chunks of guard rows -> GuardSession.push -> beam; n-best, gates, end(). Returns (result, nb, gp)."""
    d = cx.P.make_dec(cx.KV, cfg)
    seen = []
    for xc in chunks:
        rows = sess.push(xc)
        seen.append(rows)
        d.push(rows)
    nb = cx.merged(d)
    gp = bool(cx.gate.gate_pass(np.concatenate(seen)))
    nb = cx.P.GuardDecoder.post(None, nb) if gp else []
    holder["nb"] = nb
    return sess.end(), nb, gp, np.concatenate(seen)


def chunk_bounds(n: int) -> list[tuple[int, int]]:
    """The P3-12 chunking: 4-frame chunks, the last one 1-4 frames."""
    last_a = ((n - 1) // CHUNK) * CHUNK
    return [(a, a + CHUNK) for a in range(0, last_a, CHUNK)] + [(last_a, n)]


def prob_diff(u: np.ndarray, v: np.ndarray) -> float:
    return float(np.abs(np.exp(np.asarray(u, np.float64)) - np.exp(np.asarray(v, np.float64))).max())


# --- stage check ---------------------------------------------------------------------------------------


def stage_check(cx, smoke: int = 0) -> dict:
    f = own("check.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    from fidetype.adapters import emg2qwerty as A

    P = p312()
    _, kw, rf = P.model_inputs()
    vocab = cx.W.vocab
    FL = cx.cf["FL@B8"]
    holder: dict = {"nb": []}
    g = cx.guard(lambda x: holder["nb"])
    ev = cx.ev[:smoke] if smoke else cx.ev
    stored312 = load_json(P312 / "decisions-stream-S.json")
    t0 = time.time()
    res: dict = {"n_eval": len(ev), "receptive_field_frames": rf, "kinds": {}}
    out_s: dict = {"status": "guard", "units": [r["unit"] for r in ev]}
    out_b: dict = {"status": "guard", "units": out_s["units"]}
    top1_int: list[str] = []
    for kind in KINDS:
        ck = own(f"check-{kind}.partial.json")
        st = load_json(ck) if ck.exists() else {"i": 0, "S": [], "B": [], "rows": []}
        for i in range(st["i"], len(ev)):
            if stopped():
                save_json(st, ck)
                log("check: STOP file seen; exit")
                raise SystemExit(3)
            r = ev[i]
            xb = cx.W.get(r, kind)  # batch log-probs (P11-09), 33-class guard input
            n = len(xb)
            bounds = chunk_bounds(n)
            # (B) reference: the P3-12 streaming pipeline on the batch log-probs
            rb, nb_b, gp_b, _ = run_pipeline(cx, FL, holder, g.session(), (xb[a:b] for a, b in bounds))
            # (S) the streaming model feeds the loop chunk by chunk
            feed = Feed(r, kind, rf)
            m = warm_model(user_params(int(r["i"])), kw, feed)
            off = feed.lo - feed.a0
            got: list[np.ndarray] = []

            def model_chunks():
                for a, b in bounds:
                    lp = m.push(feed.x[off + a:off + b])
                    xc = A.merge_to_key_ctc(lp, vocab)
                    got.append(xc)
                    yield xc

            rs, nb_s, gp_s, _ = run_pipeline(cx, FL, holder, g.session(), model_chunks())
            xs = np.concatenate(got)
            assert xs.shape == xb.shape, (xs.shape, xb.shape)
            a_rec, b_rec = P.decision_record(rs, nb_s, gp_s), P.decision_record(rb, nb_b, gp_b)
            st["S"].append(a_rec)
            st["B"].append(b_rec)
            st["rows"].append({"prob": prob_diff(xs, xb), "logp": float(np.abs(xs - xb).max()),
                               "argmax": float((xs.argmax(1) == xb.argmax(1)).mean()),
                               "same_nb": nb_s == nb_b,
                               "same_nb_text": [t for t, _ in nb_s] == [t for t, _ in nb_b], "same_gate": gp_s == gp_b,
                               "same_312": all(b_rec[k] == stored312[kind][i][k] for k in ("action", "text", "choices"))
                               and abs(b_rec["p_top1"] - stored312[kind][i]["p_top1"]) <= 1e-12})
            st["i"] = i + 1
            if (i + 1) % CKPT_EVERY == 0:
                save_json(st, ck)
                log(f"check {kind}: {i + 1} windows ({time.time() - t0:.0f} s)")
        save_json(st, ck)
        S, B, rows = st["S"], st["B"], st["rows"]
        same_dec = [all(s[k] == b[k] for k in ("action", "text", "choices")) for s, b in zip(S, B)]
        dp = [abs(s["p_top1"] - b["p_top1"]) for s, b in zip(S, B)]
        same_full = [sd and d <= PTOP1_TOL for sd, d in zip(same_dec, dp)]
        res["kinds"][kind] = {
            "n": len(S), "same_action_text_choices": int(sum(same_dec)), "same_decision_rule": int(sum(same_full)),
            "same_action": int(sum(s["action"] == b["action"] for s, b in zip(S, B))),
            "max_abs_p_top1_diff": float(max(dp)), "exact_p_top1": int(sum(d == 0.0 for d in dp)),
            "same_nbest_exact": int(sum(x["same_nb"] for x in rows)),
            "same_nbest_texts": int(sum(x["same_nb_text"] for x in rows)), "same_gate": int(sum(x["same_gate"] for x in rows)),
            "batch_ref_same_as_p3_12_stored": int(sum(x["same_312"] for x in rows)),
            "max_abs_prob_diff": float(max(x["prob"] for x in rows)),
            "max_abs_logp_diff": float(max(x["logp"] for x in rows)),
            "min_argmax_agreement": float(min(x["argmax"] for x in rows)),
            "mean_argmax_agreement": float(np.mean([x["argmax"] for x in rows])),
            "commits_stream": int(sum(s["action"] == "commit" for s in S)),
            "commits_batch": int(sum(b["action"] == "commit" for b in B)),
            "diff_windows_actions": sorted({f"{b['action']}->{s['action']}" for s, b, sd in zip(S, B, same_dec)
                                            if not sd}),
        }
        out_s[kind], out_b[kind] = S, B
        if kind == "real":
            top1_int = [s["top1"] for s in S]
        log(f"check {kind}: {res['kinds'][kind]}")
    save_json(out_s, own("decisions-stream-model-S.json"))
    save_json(out_b, own("decisions-batch-lp-S.json"))
    # safe WPM rule (computed always)
    R = cx.R
    sh = cx.st_S["sheet"]
    keep = ("n_commits", "n_wrong_commits", "commit_rate", "wrong_commit_rate", "wrong_commit_cp95", "top1_exact",
            "actions", "control_shuffled_commits", "control_zeros_commits")
    acc: dict = {}
    if not smoke:
        truths = [R.intended_truth(r) for r in ev]
        sc_s, sc_b = R.score_arm("S", out_s, ev, sh), R.score_arm("S", out_b, ev, sh)
        acc = {"stream_model": {**{k: sc_s.get(k) for k in keep}, "safe_v01": sc_s["safe_v01"]},
               "batch_lp": {**{k: sc_b.get(k) for k in keep}, "safe_v01": sc_b["safe_v01"]},
               "window_top1_intended_cer_pooled_stream_model": sum(cx.P.char_lev(t, o) for t, o in
                                                                    zip(truths, top1_int)) / sum(len(t) for t in truths)}
        sv = sc_s["safe_v01"]
        res["safe_rule_pass"] = bool(sv["status"] == "certified" and sv["value"] >= SAFE_MIN
                                     and sc_s["control_shuffled_commits"] == 0 and sc_s["control_zeros_commits"] == 0)
    res["accuracy"] = acc
    tot = sum(k["n"] for k in res["kinds"].values())
    res["same_decisions_total"] = sum(k["same_decision_rule"] for k in res["kinds"].values())
    res["n_total"] = tot
    res["M1_same_decisions"] = res["same_decisions_total"] == tot
    res["C2_prob_tol_pass"] = all(k["max_abs_prob_diff"] <= PROB_TOL for k in res["kinds"].values())
    res["seconds"] = round(time.time() - t0, 1)
    log(f"check: same decisions {res['same_decisions_total']} / {tot}; M1 {res['M1_same_decisions']}; "
        f"safe rule {res.get('safe_rule_pass')}; prob tol {res['C2_prob_tol_pass']}")
    save_json(res, f)
    if not smoke:
        save_json(res, OUT / "check.json")
    return res


# --- stage latency (run under: isolation run --class timing --threads 1) ----------------------------------------


def q(v: list[float], pct: float) -> float:
    return float(np.percentile(np.asarray(v) * 1e3, pct))


def summ(v: list[float]) -> dict:
    return {"n": len(v), "p50": q(v, 50), "p95": q(v, 95), "max": float(np.max(v) * 1e3)}


def stage_latency(cx, tag: str = "latency", smoke: int = 0) -> dict:
    f = own(f"{tag}.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    import fidetype.pretrained._crt as C
    from fidetype.adapters import emg2qwerty as A

    P = p312()
    _, kw, rf = P.model_inputs()
    vocab = cx.W.vocab
    c = cx.cf["FL@B8"]
    holder: dict = {"nb": []}
    g = cx.guard(lambda x: holder["nb"])
    rng = np.random.default_rng(0)
    raw = rng.standard_normal((C.WIN + (CHUNK - 1) * C.HOP, C.N_CH)).astype(np.float32)  # 124 samples -> 4 frames
    ev = cx.ev[:smoke] if smoke else cx.ev
    order = list(range(min(WARMUP, len(ev)))) + list(range(len(ev)))
    t_start = time.time()
    dec_t, end_t, last_t, chunk_t = [], [], [], []
    parts = {k: [] for k in ("feat", "model", "merge", "session_push", "beam_push")}
    for k, wi in enumerate(order):
        if k % 100 == 0 and stopped():
            log(f"{tag}: STOP file seen; exit")
            raise SystemExit(3)
        r = ev[wi]
        feed = Feed(r, "real", rf)
        m = warm_model(user_params(int(r["i"])), kw, feed)
        off = feed.lo - feed.a0
        n = feed.end - feed.lo
        sess = g.session()
        d = cx.P.make_dec(cx.KV, c)
        bounds = chunk_bounds(n)
        seen = []
        ct, pf, pm, pg, ps, pb = [], [], [], [], [], []
        for a, b in bounds[:-1]:
            t1 = time.perf_counter()
            C.frames_from_block(raw)
            t2 = time.perf_counter()
            lp = m.push(feed.x[off + a:off + b])
            t3 = time.perf_counter()
            xc = A.merge_to_key_ctc(lp, vocab)
            t4 = time.perf_counter()
            rows = sess.push(xc)
            seen.append(rows)
            t5 = time.perf_counter()
            d.push(rows)
            t6 = time.perf_counter()
            ct.append(t6 - t1)
            pf.append(t2 - t1)
            pm.append(t3 - t2)
            pg.append(t4 - t3)
            ps.append(t5 - t4)
            pb.append(t6 - t5)
        a, b = bounds[-1]
        t1 = time.perf_counter()
        C.frames_from_block(raw)
        lp = m.push(feed.x[off + a:off + b])
        rows = sess.push(A.merge_to_key_ctc(lp, vocab))
        seen.append(rows)
        d.push(rows)
        t2 = time.perf_counter()
        nb = cx.merged(d)
        gp = cx.gate.gate_pass(np.concatenate(seen))
        nb = cx.P.GuardDecoder.post(None, nb) if gp else []
        holder["nb"] = nb
        sess.end()
        t3 = time.perf_counter()
        if k >= min(WARMUP, len(ev)):
            dec_t.append(t3 - t1)
            end_t.append(t3 - t2)
            last_t.append(t2 - t1)
            chunk_t += ct
            for name, v in zip(parts, (pf, pm, pg, ps, pb)):
                parts[name] += v
    g.audit_log.clear()
    res = {"path": "S FL@B8 (streaming per-user CRT -> merge -> session -> beam)", "n_windows": len(dec_t),
           "warmup_windows": min(WARMUP, len(ev)), "threads_env": os.environ.get("OMP_NUM_THREADS"),
           "isolation_class_env": os.environ.get("FIDETYPE_ISOLATION_CLASS"),
           "isolation_cpus_env": os.environ.get("FIDETYPE_ISOLATION_CPUS"),
           "decision": summ(dec_t), "end_work": summ(end_t), "last_chunk": summ(last_t), "chunk": summ(chunk_t),
           "chunk_parts": {k: summ(v) for k, v in parts.items()}, "seconds": round(time.time() - t_start, 1)}
    np.save(own(f"{tag}-S-FL_B8-decision-s.npy"), np.asarray(dec_t))
    log(f"{tag}: decision p50 {q(dec_t, 50):.2f} p95 {q(dec_t, 95):.2f} max {np.max(dec_t) * 1e3:.1f} ms; "
        f"chunk p95 {q(chunk_t, 95):.2f} ms")
    save_json(res, f)
    return res


# --- stage score -------------------------------------------------------------------------------------------------


def stage_score() -> dict:
    ck = load_json(own("check.json"))
    lat = {p.stem: load_json(p) for p in sorted(OWN.glob("latency*.json"))}
    iso = {p.stem: load_json(p) for p in sorted(OWN.glob("iso-*.json"))}
    res: dict = {"task": "P3-13", "date": time.strftime("%Y-%m-%d %H:%M"), "data.licence": "CC-BY-NC-SA-4.0",
                 "data.research_only": True, "note": "aggregates only (no per-user value, no text, no id)",
                 "rules": {"ptop1_tol": PTOP1_TOL, "prob_tol": PROB_TOL, "safe_min": SAFE_MIN,
                           "budget_ms": BUDGET_MS, "chunk_budget_ms": CHUNK_BUDGET_MS},
                 "check": ck, "latency": lat, "isolation": iso}
    clean1 = bool(iso.get("iso-latency", {}).get("clean"))
    use = "latency2" if ("latency2" in lat and not clean1) else "latency"
    res["latency_run_used"] = use
    v: dict = {"M1_same_decisions": ck["M1_same_decisions"], "safe_rule_pass": ck.get("safe_rule_pass"),
               "C2_prob_tol": ck["C2_prob_tol_pass"]}
    v["V1_primary"] = bool(ck["M1_same_decisions"] or ck.get("safe_rule_pass"))
    main = lat.get(use)
    if main is not None:
        v["L1_latency"] = bool(main["decision"]["p95"] <= BUDGET_MS and main["chunk"]["p95"] <= CHUNK_BUDGET_MS)
        v["decision_p95_ms"] = main["decision"]["p95"]
        v["chunk_p95_ms"] = main["chunk"]["p95"]
    res["verdicts"] = v
    save_json(res, OUT / "results.json")
    log(f"score: {v}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("check", "latency", "score"))
    ap.add_argument("--tag", default="latency")
    ap.add_argument("--smoke", type=int, default=0, help="dry run on the first N windows into derived/p3-13/smoke/")
    a = ap.parse_args()
    global OWN, STOP, OUT
    if a.smoke:
        OUT = OWN / "smoke" / "results"
        params = OWN
        OWN = OWN / "smoke"
        OWN.mkdir(parents=True, exist_ok=True)
        for f in list(OWN.glob("*.json")) + list(OWN.glob("*.npy")):
            f.unlink()
        for i in range(8):  # the smoke folder reads the exported weights in place
            src, dst = params / f"params-u{i}.npz", OWN / f"params-u{i}.npz"
            if not dst.exists():
                os.link(src, dst)
    OWN.mkdir(parents=True, exist_ok=True)
    keep_awake(True)
    try:
        log(f"start {a.stage}{' SMOKE ' + str(a.smoke) + ' windows (not counted)' if a.smoke else ''} "
            f"(OMP_NUM_THREADS={os.environ.get('OMP_NUM_THREADS')})")
        if a.stage == "score":
            stage_score()
        else:
            cx = p312().Ctx()
            if a.stage == "check":
                stage_check(cx, a.smoke)
            else:
                stage_latency(cx, a.tag, a.smoke)
        log(f"end {a.stage}")
    finally:
        keep_awake(False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
