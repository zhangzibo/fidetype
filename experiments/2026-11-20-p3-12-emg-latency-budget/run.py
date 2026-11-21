"""P3-12: the P11-07 in-beam LM EMG decoder plus the arm S guard inside the 50 ms CPU budget.

Pre-registration: plan.md (this folder). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0. Per-window files stay
in C:/Users/zhang/bci-data/derived/p3-12/. The P11-01, P11-07, P11-09, P11-11 and P11-12 files are read only.

Stages (repo root; launch.py runs them detached, each under the isolation runner):

  check     exactness: streaming CRT vs batch; streaming pipeline (guard session + beam on the session rows) vs
            the offline guard on all 1,221 evaluation windows x (real, shuffled, zeros); accuracy rule A2.
  latency   timed run (class timing, 1 thread): baseline B (P11-07 path) and new path N, FL@B8 and F@B8.
  latency4  model chunk only, 4 threads (class timing): batch with receptive field vs streaming.
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
import importlib.util  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p3-12"  # the only place this task writes per-window files
P1101 = DER / "p11-01-emg-decoder"  # READ ONLY
P1107 = DER / "p11-07"  # READ ONLY
EXP1107 = REPO / "experiments" / "2026-11-20-p11-07-emg-beam-lm"
OUT = HERE / "results"
STOP = OWN / "STOP"

CHUNK = 4
WARMUP = 20
N_MODEL_CHUNKS = 500
CONFIGS = ("FL@B8", "F@B8")  # FL@B8 = the arm S decoder (primary)
BUDGET_MS = 50.0
CHUNK_BUDGET_MS = 40.0
P1107_REF = {"safe_v01": 3.3710198389920367, "n_wrong": 43, "fl_window_int_cer": 0.08995037220843673,
             "added_p95_FL@B8": 67.18460004776716, "added_p95_F@B8": 67.61029991321266,
             "model_p95_4thr": 47.07715002004983}
TOL = {"safe_wpm": 0.05, "wrong": 1, "cer": 0.001}


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


def p1107():
    """The P11-07 runner as a module. Read-only use: never call its stage functions, own(), log or save."""
    if "p1107run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("p1107run", EXP1107 / "run.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["p1107run"] = m
        argv, sys.argv = sys.argv, [str(EXP1107 / "run.py")]
        try:
            spec.loader.exec_module(m)
        finally:
            sys.argv = argv
    return sys.modules["p1107run"]


class Ctx:
    """Shared read-only inputs."""

    def __init__(self) -> None:
        P = p1107()
        self.P = P
        self.R, _, self.cal, self.ev = P.rows_split()
        tune, beam = P.load_json(P1107 / "tune.json"), P.load_json(P1107 / "beam.json")
        self.cf = P.configs(tune, beam)
        self.KV = P.key_vocab()
        self.W = self.R.p1109().Windows()
        self.gate = P.p1112()
        self.st_S = P.load_json(P1107 / "guard-S.status.json")
        assert self.st_S["status"] == "guard"
        # Amendment 3 (bug fix): GuardDecoder.__init__ loads the P11-12 gate thresholds (GATE) and the P11-11 OOV
        # lexicon (DEC.lex). Build one here so every stage has them (the latency stage built none: k_min None).
        self.fresh_decoder()
        g = self.gate.GATE
        assert all(g[k] is not None for k in ("k_min", "r_min", "r_max")), g
        assert self.R.DEC.lex, "OOV lexicon not loaded"

    def fresh_decoder(self):
        """An un-memoised FL GuardDecoder that never writes (the P11-07 class saves its memo to derived/p11-07)."""
        P = self.P

        class Fresh(P.GuardDecoder):
            def load(self) -> None:
                pass

            def save(self) -> None:
                self.dirty = 0

            def __call__(self, x):
                if not P.p1112().gate_pass(x):
                    return []
                return self.post(self.nbest_intended(x))

        return Fresh(self.cf["FL"])

    def guard(self, decode_fn):
        from fidetype.trust.dropin import load as load_guard

        return load_guard(P1107 / "guard-S.json", decode_fn=decode_fn)

    def merged(self, d) -> list[tuple[str, float]]:
        """FL n-best -> intended texts merged (log-sum-exp), best first, top 20 (GuardDecoder.nbest_intended)."""
        R, KV = self.R, self.KV
        m: dict[str, float] = {}
        for h in d.nbest(None, eos=True):
            t = R.resolve("".join(KV[k] for k in h.tokens))
            m[t] = float(np.logaddexp(m.get(t, -np.inf), h.score))
        return sorted(m.items(), key=lambda kv: (-kv[1], kv[0]))[:self.P.NBEST_OUT]


def decision_record(r, nb: list[tuple[str, float]], gate: bool) -> dict:
    """The P11-11 decide_one form (without the time field), plus the gate flag."""
    return {"action": r.action, "text": r.text, "choices": list(r.choices)[:3], "p_top1": float(r.p_top1),
            "n_words_committed": r.n_words_committed, "complete": r.complete,
            "top1": nb[0][0].strip() if nb else "", "gate": bool(gate),
            "s": 0.0}  # the P11-11 scorer reads "s" (decision time); timing is the latency stage's job


def model_inputs():
    """u0 weights and model config of the P11-07 model timing (read only)."""
    g = load_json(P1107 / "modellat-gpu.json")
    with np.load(P1107 / "modellat-params-u0.npz") as z:
        p = {k: np.asarray(z[k]) for k in z.files}
    mc = g["model_cfg"]
    kw = dict(ring_k=mc["ring_k"], kernel=mc["kernel"], dilations=tuple(mc["dilations"]))
    return p, kw, int(g["receptive_field_frames"])


_FEAT: dict[str, np.ndarray] = {}


def session_feat(session: str) -> np.ndarray:
    if session not in _FEAT:
        _FEAT[session] = np.load(P1101 / "sessions" / f"{session}.feat.npy", mmap_mode="r", allow_pickle=False)
    return _FEAT[session]


def window_feat(r: dict, n: int) -> np.ndarray:
    f = session_feat(r["session"])
    a = np.asarray(f[r["lo"]:r["lo"] + n], np.float32)
    if len(a) < n:  # pad at the session end (cost stand-in only)
        a = np.concatenate([a, np.repeat(a[-1:], n - len(a), 0)])
    return a


# --- stage check ---------------------------------------------------------------------------------------


def stage_check(cx: Ctx) -> dict:
    f = own("check.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    import fidetype.pretrained._crt as C

    t0 = time.time()
    res: dict = {"n_eval": len(cx.ev)}
    # (1) streaming CRT vs batch
    p, kw, _ = model_inputs()
    diffs, pdiffs, agree = [], [], []
    for r in cx.ev[::25]:
        x = window_feat(r, r["end"] - r["lo"])
        ref = C._forward(p, x, **kw)
        s = C.CRTStream(p, **kw)
        out = np.concatenate([s.push(x[a:a + CHUNK]) for a in range(0, len(x), CHUNK)])
        diffs.append(float(np.abs(out - ref).max()))
        pdiffs.append(float(np.abs(np.exp(out.astype(np.float64)) - np.exp(ref.astype(np.float64))).max()))
        agree.append(float((out.argmax(1) == ref.argmax(1)).mean()))
    res["crt_stream"] = {"n_windows": len(diffs), "max_abs_logp_diff": max(diffs), "max_abs_prob_diff": max(pdiffs),
                         "min_argmax_agreement": min(agree), "pass": max(pdiffs) <= 1e-5 and min(agree) == 1.0}
    log(f"check crt: {res['crt_stream']}")
    # (2) streaming pipeline vs offline guard
    FL = cx.cf["FL@B8"]
    assert FL == {**cx.cf["FL"]}, (FL, cx.cf["FL"])
    off_dec = cx.fresh_decoder()
    g_off = cx.guard(off_dec)
    holder: dict = {"nb": []}
    g_str = cx.guard(lambda x: holder["nb"])
    stored = cx.P.load_json(P1107 / "decisions-S.json")
    out: dict = {"status": "guard", "units": [r["unit"] for r in cx.ev]}
    offl: dict = {"status": "guard", "units": out["units"]}
    cmp: dict = {}
    top1_int: list[str] = []
    for kind in ("real", "shuffled", "zeros"):
        ds, do = [], []
        same_off = same_nb = same_stored = 0
        for i, r in enumerate(cx.ev):
            if stopped():
                log("check: STOP file seen; exit")
                raise SystemExit(3)
            x = cx.W.get(r, kind)
            # offline guard (fresh decode on the guard's stream)
            ro = g_off.decide(x)
            nb_off = off_dec(np.asarray(g_off._last_lp, np.float64)) if g_off._last_lp is not None else []
            # streaming: session rows -> beam, chunk by chunk
            s = g_str.session()
            d = cx.P.make_dec(cx.KV, FL)
            n = len(x)
            last_a = ((n - 1) // CHUNK) * CHUNK
            seen = []
            for a in range(0, last_a, CHUNK):
                rows = s.push(x[a:a + CHUNK])
                seen.append(rows)
                d.push(rows)
            rows = s.push(x[last_a:])
            seen.append(rows)
            d.push(rows)
            nb = cx.merged(d)
            if kind == "real":
                top1_int.append(nb[0][0] if nb else "")
            gp = bool(cx.gate.gate_pass(np.concatenate(seen)))
            nb = cx.P.GuardDecoder.post(None, nb) if gp else []  # post() does not use self
            holder["nb"] = nb
            rs = s.end()
            a_rec, o_rec = decision_record(rs, nb, gp), decision_record(ro, nb_off, gp)
            ds.append(a_rec)
            do.append(o_rec)
            same_off += all(a_rec[k] == o_rec[k] for k in ("action", "text", "choices", "p_top1"))
            same_nb += nb == nb_off
            sd = stored[kind][i]
            same_stored += all(a_rec[k] == sd[k] for k in ("action", "text", "choices")) and \
                abs(a_rec["p_top1"] - sd["p_top1"]) <= 1e-12
            if (i + 1) % 300 == 0:
                log(f"check {kind}: {i + 1} windows ({time.time() - t0:.0f} s); same as offline {same_off}")
        out[kind], offl[kind] = ds, do
        cmp[kind] = {"n": len(cx.ev), "same_as_offline_guard": same_off, "same_nbest_as_offline": same_nb,
                     "same_as_p1107_stored": same_stored}
        log(f"check {kind}: {cmp[kind]}")
    save_json(out, own("decisions-stream-S.json"))
    save_json(offl, own("decisions-offline-S.json"))
    res["decisions"] = cmp
    res["A1_pass"] = all(c["same_as_offline_guard"] == c["n"] for c in cmp.values())
    # (3) accuracy rule A2
    R = cx.R
    truths = [R.intended_truth(r) for r in cx.ev]
    cer = sum(cx.P.char_lev(t, o) for t, o in zip(truths, top1_int)) / sum(len(t) for t in truths)
    sh = cx.st_S["sheet"]
    sc_new = R.score_arm("S", out, cx.ev, sh)
    sc_old = R.score_arm("S", stored, cx.ev, sh)
    keep = ("n_commits", "n_wrong_commits", "commit_rate", "wrong_commit_rate", "wrong_commit_cp95", "top1_exact",
            "actions", "control_shuffled_commits", "control_zeros_commits")
    res["accuracy"] = {
        "window_top1_intended_cer_pooled_stream_FL@B8": cer,
        "p1107_FL_window_intended_cer_pooled": P1107_REF["fl_window_int_cer"],
        "stream": {**{k: sc_new.get(k) for k in keep}, "safe_v01": sc_new["safe_v01"]},
        "p1107_stored_rescored": {**{k: sc_old.get(k) for k in keep}, "safe_v01": sc_old["safe_v01"]},
    }
    sv = sc_new["safe_v01"]
    res["A2_pass"] = bool(sv["status"] == "certified" and sv["value"] >= P1107_REF["safe_v01"] - TOL["safe_wpm"]
                          and sc_new["n_wrong_commits"] <= P1107_REF["n_wrong"] + TOL["wrong"]
                          and sc_new["control_shuffled_commits"] == 0 and sc_new["control_zeros_commits"] == 0
                          and cer <= P1107_REF["fl_window_int_cer"] + TOL["cer"])
    res["seconds"] = round(time.time() - t0, 1)
    log(f"check: A1 {res['A1_pass']}, A2 {res['A2_pass']}; accuracy {json.dumps(res['accuracy'], default=str)[:600]}")
    save_json(res, f)
    save_json({k: v for k, v in res.items()}, OUT / "check.json")
    return res


# --- stage latency (run under: isolation run --class timing --threads 1) ----------------------------------------


def q(v: list[float], pct: float) -> float:
    return float(np.percentile(np.asarray(v) * 1e3, pct))


def summ(v: list[float]) -> dict:
    return {"n": len(v), "p50": q(v, 50), "p95": q(v, 95), "max": float(np.max(v) * 1e3)}


def stage_latency(cx: Ctx, tag: str = "latency") -> dict:
    f = own(f"{tag}.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    import fidetype.pretrained._crt as C

    t_start = time.time()
    holder: dict = {"nb": []}
    g = cx.guard(lambda x: holder["nb"])
    p, kw, rf = model_inputs()
    rng = np.random.default_rng(0)
    raw = rng.standard_normal((C.WIN + (CHUNK - 1) * C.HOP, C.N_CH)).astype(np.float32)  # 124 samples -> 4 frames
    assert C.frames_from_block(raw).shape[0] == CHUNK
    xs = [np.asarray(cx.W.get(r), np.float64) for r in cx.ev]
    res: dict = {"chunk_frames": CHUNK, "n_windows": len(xs), "warmup_windows": WARMUP,
                 "threads_env": os.environ.get("OMP_NUM_THREADS"),
                 "isolation_class_env": os.environ.get("FIDETYPE_ISOLATION_CLASS"),
                 "isolation_cpus_env": os.environ.get("FIDETYPE_ISOLATION_CPUS"), "paths": {}}
    order = list(range(WARMUP)) + list(range(len(xs)))  # warm-up windows first (not counted)

    def check_stop() -> None:
        if stopped():
            log(f"{tag}: STOP file seen; exit")
            raise SystemExit(3)

    # --- baseline B: the P11-07 path (raw rows into the beam; guard.decide at the end) ---
    for name in CONFIGS:
        c = cx.cf[name]
        chunk_t, add = [], []
        for k, wi in enumerate(order):
            if k % 100 == 0:
                check_stop()
            x = xs[wi]
            d = cx.P.make_dec(cx.KV, c)
            n = len(x)
            last_a = ((n - 1) // CHUNK) * CHUNK
            ct = []
            for a in range(0, last_a, CHUNK):
                t1 = time.perf_counter()
                d.push(x[a:a + CHUNK])
                ct.append(time.perf_counter() - t1)
            t1 = time.perf_counter()
            d.push(x[last_a:])
            nb = cx.merged(d)
            nb = cx.P.GuardDecoder.post(None, nb) if cx.gate.gate_pass(x) else []
            holder["nb"] = nb
            g.decide(x)
            dt = time.perf_counter() - t1
            if k >= WARMUP:
                add.append(dt)
                chunk_t += ct
        g.audit_log.clear()
        res["paths"][f"B:{name}"] = {**c, "beam_chunk_push": summ(chunk_t), "added_end": summ(add)}
        log(f"{tag} B:{name}: added p50 {q(add, 50):.2f} p95 {q(add, 95):.2f} ms")
    # --- model chunks alone: batch with the receptive field (P11-07 form) and streaming (C1) ---
    feat0 = window_feat(cx.ev[0], rf + CHUNK + N_MODEL_CHUNKS + 60)
    tb, ts = [], []
    for k in range(N_MODEL_CHUNKS + 50):
        xk = np.ascontiguousarray(feat0[k:k + rf + CHUNK])
        t1 = time.perf_counter()
        C._forward(p, xk, **kw)[-CHUNK:]
        tb.append(time.perf_counter() - t1)
    s = C.CRTStream(p, **kw)
    s.push(feat0[:rf])
    for k in range(N_MODEL_CHUNKS + 50):
        xk = feat0[rf + 4 * (k % 15):rf + 4 * (k % 15) + CHUNK]
        t1 = time.perf_counter()
        s.push(xk)
        ts.append(time.perf_counter() - t1)
    tf = []
    for k in range(N_MODEL_CHUNKS + 50):
        t1 = time.perf_counter()
        C.frames_from_block(raw)
        tf.append(time.perf_counter() - t1)
    res["model_alone"] = {"batch_rf_chunk": summ(tb[50:]), "stream_chunk": summ(ts[50:]),
                          "features_chunk": summ(tf[50:]), "receptive_field_frames": rf}
    log(f"{tag} model alone: {res['model_alone']}")
    # --- new path N: features + streaming model + guard session + beam on the session rows ---
    for name in CONFIGS:
        c = cx.cf[name]
        chunk_t, dec_t, end_t, last_t = [], [], [], []
        parts = {k: [] for k in ("feat", "model", "session_push", "beam_push")}
        for k, wi in enumerate(order):
            if k % 100 == 0:
                check_stop()
            x = xs[wi]
            r = cx.ev[wi]
            n = len(x)
            fx = window_feat(r, n)
            m = C.CRTStream(p, **kw)
            sess = g.session()
            d = cx.P.make_dec(cx.KV, c)
            last_a = ((n - 1) // CHUNK) * CHUNK
            seen = []
            ct, pf, pm, ps, pb = [], [], [], [], []
            for a in range(0, last_a, CHUNK):
                t1 = time.perf_counter()
                C.frames_from_block(raw)
                t2 = time.perf_counter()
                m.push(fx[a:a + CHUNK])
                t3 = time.perf_counter()
                rows = sess.push(x[a:a + CHUNK])
                seen.append(rows)
                t4 = time.perf_counter()
                d.push(rows)
                t5 = time.perf_counter()
                ct.append(t5 - t1)
                pf.append(t2 - t1)
                pm.append(t3 - t2)
                ps.append(t4 - t3)
                pb.append(t5 - t4)
            t1 = time.perf_counter()
            C.frames_from_block(raw)
            m.push(fx[last_a:])
            rows = sess.push(x[last_a:])
            seen.append(rows)
            d.push(rows)
            t2 = time.perf_counter()
            nb = cx.merged(d)
            gp = cx.gate.gate_pass(np.concatenate(seen))
            nb = cx.P.GuardDecoder.post(None, nb) if gp else []
            holder["nb"] = nb
            sess.end()
            t3 = time.perf_counter()
            if k >= WARMUP:
                dec_t.append(t3 - t1)
                end_t.append(t3 - t2)
                last_t.append(t2 - t1)
                chunk_t += ct
                parts["feat"] += pf
                parts["model"] += pm
                parts["session_push"] += ps
                parts["beam_push"] += pb
        g.audit_log.clear()
        res["paths"][f"N:{name}"] = {**c, "decision": summ(dec_t), "end_work": summ(end_t), "last_chunk": summ(last_t),
                                     "chunk": summ(chunk_t), "chunk_parts": {k: summ(v) for k, v in parts.items()}}
        np.save(own(f"{tag}-N-{name.replace('@', '_')}-decision-s.npy"), np.asarray(dec_t))
        log(f"{tag} N:{name}: decision p50 {q(dec_t, 50):.2f} p95 {q(dec_t, 95):.2f} max {np.max(dec_t) * 1e3:.1f} ms; "
            f"chunk p95 {q(chunk_t, 95):.2f} ms")
    res["seconds"] = round(time.time() - t_start, 1)
    save_json(res, f)
    return res


def stage_latency4() -> dict:
    """Model chunk only, at the process thread count (run with --threads 4)."""
    f = own("latency4.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    import fidetype.pretrained._crt as C

    p, kw, rf = model_inputs()
    feat0 = np.asarray(session_feat(_first_session())[:rf + 700], np.float32)
    tb, ts = [], []
    for k in range(N_MODEL_CHUNKS + 50):
        xk = np.ascontiguousarray(feat0[k:k + rf + CHUNK])
        t1 = time.perf_counter()
        C._forward(p, xk, **kw)[-CHUNK:]
        tb.append(time.perf_counter() - t1)
    s = C.CRTStream(p, **kw)
    s.push(feat0[:rf])
    for k in range(N_MODEL_CHUNKS + 50):
        xk = feat0[rf + 4 * (k % 15):rf + 4 * (k % 15) + CHUNK]
        t1 = time.perf_counter()
        s.push(xk)
        ts.append(time.perf_counter() - t1)
    res = {"threads_env": os.environ.get("OMP_NUM_THREADS"), "batch_rf_chunk": summ(tb[50:]),
           "stream_chunk": summ(ts[50:])}
    log(f"latency4: {res}")
    save_json(res, f)
    return res


def _first_session() -> str:
    return sorted(Path(P1101 / "sessions").glob("*.feat.npy"))[0].name[:-len(".feat.npy")]


# --- stage score -------------------------------------------------------------------------------------------------


def stage_score() -> dict:
    ck = load_json(own("check.json"))
    lat_files = sorted(OWN.glob("latency*.json"))
    lat = {p.stem: load_json(p) for p in lat_files}
    iso = {p.stem: load_json(p) for p in sorted(OWN.glob("iso-*.json"))}
    res: dict = {"task": "P3-12", "date": time.strftime("%Y-%m-%d %H:%M"), "data.licence": "CC-BY-NC-SA-4.0",
                 "data.research_only": True, "note": "aggregates only (no per-user value, no text, no id)",
                 "p1107_reference": P1107_REF, "tolerance": TOL, "check": ck, "latency": lat, "isolation": iso}
    clean1 = bool(iso.get("iso-latency", {}).get("clean"))
    use = "latency2" if ("latency2" in lat and not clean1) else "latency"
    res["latency_run_used"] = use
    main = lat.get(use)
    v: dict = {}
    if main is not None:
        for name in CONFIGS:
            n = main["paths"][f"N:{name}"]
            ok_lat = n["decision"]["p95"] <= BUDGET_MS and n["chunk"]["p95"] <= CHUNK_BUDGET_MS
            v[name] = {"decision_p95_ms": n["decision"]["p95"], "chunk_p95_ms": n["chunk"]["p95"],
                       "latency_rule": ok_lat,
                       "h5_form_ms": n["end_work"]["p95"] + main["model_alone"]["stream_chunk"]["p95"]
                       + main["model_alone"]["features_chunk"]["p95"]}
        v["V1_primary_FL@B8"] = bool(v["FL@B8"]["latency_rule"] and ck["A1_pass"] and ck["A2_pass"])
        v["V3_F@B8"] = bool(v["F@B8"]["latency_rule"])
    if "latency4" in lat and main is not None:
        v["V4_4thr_faster_stream"] = lat["latency4"]["stream_chunk"]["p95"] < main["model_alone"]["stream_chunk"]["p95"]
    res["verdicts"] = v
    save_json(res, OUT / "results.json")
    log(f"score: {v}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("check", "latency", "latency4", "score"))
    ap.add_argument("--tag", default="latency")
    ap.add_argument("--smoke", type=int, default=0,
                    help="dry run on the first N windows into derived/p3-12/smoke/ (not counted; amendment 3)")
    a = ap.parse_args()
    global OWN, WARMUP, N_MODEL_CHUNKS
    if a.smoke:
        OWN, WARMUP, N_MODEL_CHUNKS = OWN / "smoke", 2, 20
        for f in OWN.glob("*.json"):
            f.unlink()
    OWN.mkdir(parents=True, exist_ok=True)
    keep_awake(True)
    try:
        log(f"start {a.stage}{' SMOKE ' + str(a.smoke) + ' windows (not counted)' if a.smoke else ''} "
            f"(OMP_NUM_THREADS={os.environ.get('OMP_NUM_THREADS')})")
        if a.stage == "check":
            stage_check(Ctx())
        elif a.stage == "latency":
            cx = Ctx()
            if a.smoke:
                cx.ev = cx.ev[:a.smoke]
            stage_latency(cx, a.tag)
        elif a.stage == "latency4":
            stage_latency4()
        else:
            stage_score()
        log(f"end {a.stage}")
    finally:
        keep_awake(False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
