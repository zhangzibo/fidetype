"""P11-07: character LM inside the CTC beam for the P11-01 emg2qwerty personalised decoders.

Pre-registration: plan.md (this folder). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0. Per-prompt and
per-session files stay in C:/Users/zhang/bci-data/derived/p11-07/. The P11-01, P11-09, P11-11 and P11-12 files
are read only. The repo gets aggregates only (no per-user value, no text, no id).

Stages (repo root; launch.py runs them detached):

  tune      grid (w, beta, lam) at B 32 on the 765 tuning prompts (98-token windows), pooled raw-key CER.
  beam      B in {4, 8, 16, 32, 64} with F's (w, beta) on the tuning prompts; chosen B.
  test      session CER (G, B0, F, FL, F at every B), per-prompt intended CER, window top-1, control C1.
  guards    P11-12 protocol, decode_fn = no-signal gate + FL + OOV gate (arms S, SL).
  decide    decisions on the evaluation prompts (real, time-shuffled, zero EMG).
  latency   offline and streaming decision time (CPU, 1 thread, isolation class timing).
  modellat  acoustic model chunk forward, CPU and GPU (needs the ROCm venv: run it with that python).
  score     aggregates, verdicts -> results/results.json.
  all       tune beam test guards decide latency score (modellat is separate: other venv).
"""

from __future__ import annotations

import os
import sys

_MODELLAT = len(sys.argv) > 1 and sys.argv[1] == "modellat"  # GPU stage (ROCm venv)
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
if not _MODELLAT:
    os.environ.setdefault("HIP_VISIBLE_DEVICES", "")  # CPU only except modellat
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

import lmbeam as LB  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p11-07"  # the only place this task writes per-prompt / per-session files
P1101 = DER / "p11-01-emg-decoder"  # READ ONLY
P1109 = DER / "p11-09"  # READ ONLY
P1111 = DER / "p11-11"  # READ ONLY (LM, lexicon)
P1112 = DER / "p11-12"  # READ ONLY (gate.json)
EXP1101 = REPO / "experiments" / "2026-11-16-p11-01-emg-decoder"
EXP1111 = REPO / "experiments" / "2026-11-19-p11-11-emg-nonvacuous"
EXP1112 = REPO / "experiments" / "2026-11-20-p11-12-emg-nosignal-gate"
OUT = HERE / "results"

# --- pre-registered constants (plan.md) ------------------------------------------------------------
PRUNE = -8.0
B_TUNE = 32
W_GRID = (0.25, 0.5, 0.75, 1.0, 1.5)
BETA_GRID = (0.0, 0.5, 1.0, 2.0, 3.0)
LAM_GRID = (0.0, 1.0, 2.0, 4.0, 8.0)
B_GRID = (4, 8, 16, 32, 64)
B_TOL = 0.002
NBEST_OUT = 20
CHUNK = 4  # frames per streaming chunk (40 ms)
N_MODEL_CHUNKS = 500
PUB = {"no_lm": 11.28, "lm": 6.95}  # Table 3, fine-tuned, test, % (mean over users)
ARMS = ("S", "SL")
WORKERS = 6


def log(*a: object) -> None:
    OUT.mkdir(exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def own(*parts: str) -> Path:
    p = OWN.joinpath(*parts)
    assert OWN in p.parents or p == OWN
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def save_json(obj: object, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def keep_awake(on: bool) -> None:
    if os.name != "nt":
        return
    import ctypes

    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def p1111():
    """The P11-11 runner as a module. Read-only use: never call its stage functions, own(), log or caches."""
    if "p1111run" not in sys.modules:
        load_module("p1111run", EXP1111 / "run.py")
    return sys.modules["p1111run"]


def p1112():
    """The P11-12 runner as a module (gate functions only)."""
    if "p1112run" not in sys.modules:
        load_module("p1112run", EXP1112 / "run.py")
    return sys.modules["p1112run"]


# --- shared data ------------------------------------------------------------------------------------


def vocab98() -> list[str]:
    return load_json(P1101 / "index.json")["vocab"]  # type: ignore[index]


def key_vocab() -> list[str]:
    from fidetype.adapters import emg2qwerty as A

    return A.key_ctc_vocab()


_LP: dict[str, np.ndarray] = {}


def lp_arr(name: str) -> np.ndarray:
    if name not in _LP:
        _LP[name] = np.load(P1109 / "lp" / name, mmap_mode="r", allow_pickle=False)
    return _LP[name]


_LAB: dict[str, dict] = {}


def lab(session: str) -> dict:
    if session not in _LAB:
        with np.load(P1101 / "sessions" / f"{session}.lab.npz", allow_pickle=False) as z:
            _LAB[session] = {k: np.asarray(z[k]) for k in ("key_tok", "key_frame", "prompt_lo", "prompt_hi")}
    return _LAB[session]


def win98(r: dict) -> np.ndarray:
    return np.asarray(lp_arr(f"u{r['i']}-s{r['j']}-real.npy")[r["lo"]:r["end"]], np.float64)


def ref98(r: dict) -> list[int]:
    lb = lab(r["session"])
    m = (lb["key_frame"] >= r["lo"]) & (lb["key_frame"] < r["hi"])
    return [int(t) for t in lb["key_tok"][m]]


_LM = None
_LEX_NORM: frozenset[str] | None = None


def lm():
    global _LM
    if _LM is None:
        from fidetype.lm.ngram import CharNgramLM

        _LM = CharNgramLM.load(P1111 / "eng_tatoeba_6gram_mkn_noE2Q.npz")
    return _LM


def lex_norm() -> frozenset[str]:
    """P11-11 lexicon, each word normalised as the LM text (lower case, non-letters to space) and split."""
    global _LEX_NORM
    if _LEX_NORM is None:
        from fidetype.streams.vocab import normalize_text

        ws = load_json(P1111 / "lexicon.json")["words"]  # type: ignore[index]
        _LEX_NORM = frozenset(p for w in ws for p in normalize_text(w).split())
    return _LEX_NORM


def make_dec(vocab: list[str], cfg: dict) -> LB.LMBeam:
    use_lm = cfg.get("w", 0) > 0
    return LB.LMBeam(vocab, 0, lm=lm() if use_lm else None, lm_weight=cfg.get("w", 0.0), bonus=cfg.get("beta", 0.0),
                     beam=int(cfg["B"]), prune_logp=PRUNE, lexicon=lex_norm() if cfg.get("lam", 0) > 0 else None,
                     lam=cfg.get("lam", 0.0))


def decode_top(x: np.ndarray, vocab: list[str], cfg: dict) -> LB.Hyp:
    if cfg.get("greedy"):
        return LB.Hyp(LB.greedy_tokens(x), [], 0.0, 0.0, 0.0)
    d = make_dec(vocab, cfg)
    d.push(x)
    hs = d.nbest(1)
    return hs[0] if hs else LB.Hyp([], [], 0.0, 0.0, 0.0)


def levenshtein(ref, hyp) -> int:
    """Edit distance (unit costs); row-wise numpy DP (the P11-01 algorithm, our own code)."""
    r, h = np.asarray(ref), np.asarray(hyp)
    if len(r) == 0:
        return int(len(h))
    if len(h) == 0:
        return int(len(r))
    ar =np.arange(len(h) + 1)
    prev = ar.copy()
    for i in range(1, len(r) + 1):
        tmp = np.empty_like(prev)
        tmp[0] = i
        tmp[1:] = np.minimum(prev[1:] + 1, prev[:-1] + (h != r[i - 1]))
        prev = np.minimum.accumulate(tmp - ar) + ar
    return int(prev[-1])


def char_lev(a: str, b: str) -> int:
    return levenshtein(np.frombuffer(a.encode("utf-32-le"), np.uint32), np.frombuffer(b.encode("utf-32-le"), np.uint32))


def rows_split():
    R = p1111()
    rows = R.prompts()
    cal, ev = R.split_rows(rows)
    return R, rows, cal, ev


def tune_rows(cal: list[dict]) -> list[dict]:
    pos = p1111().tune_items(len(cal))
    return [cal[i] for i in pos]


def tune_digest(cal: list[dict]) -> str:
    pos = p1111().tune_items(len(cal))
    return hashlib.sha256(",".join(map(str, pos)).encode()).hexdigest()[:16]


# --- stage tune / beam (parallel over configs) ------------------------------------------------------


def cfg_name(c: dict) -> str:
    return f"w{c['w']}-b{c['beta']}-l{c['lam']}-B{c['B']}"


def _eval_cfg(c: dict) -> dict:
    """Worker: pooled raw-key CER of one config over the tuning prompts (98-token windows)."""
    f = own("tune", cfg_name(c) + ".json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    _, _, cal, _ = rows_split()
    V = vocab98()
    e = n = 0
    t0 = time.time()
    for r in tune_rows(cal):
        h = decode_top(win98(r), V, c)
        ref = ref98(r)
        e += levenshtein(ref, h.tokens)
        n += len(ref)
    rec = {**c, "edits": e, "ref": n, "cer": e / max(n, 1), "seconds": round(time.time() - t0, 1)}
    save_json(rec, f)
    return rec


def run_pool(cfgs: list[dict]) -> list[dict]:
    todo = [c for c in cfgs if not own("tune", cfg_name(c) + ".json").exists()]
    if todo:
        import multiprocessing as mp

        ctx = mp.get_context("spawn")
        with ctx.Pool(min(WORKERS, len(todo))) as pool:
            for i, rec in enumerate(pool.imap_unordered(_eval_cfg, todo), 1):
                if i % 10 == 0 or i == len(todo):
                    log(f"pool: {i}/{len(todo)} configs (last {cfg_name(rec)} cer {rec['cer']:.4f})")
    return [load_json(own("tune", cfg_name(c) + ".json")) for c in cfgs]  # type: ignore[misc]


def stage_tune(cal: list[dict]) -> dict:
    f = own("tune.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    cfgs = [{"w": w, "beta": b, "lam": la, "B": B_TUNE} for w in W_GRID for b in BETA_GRID for la in LAM_GRID]
    recs = run_pool(cfgs)
    key = lambda g: (g["cer"], g["w"], g["beta"], g["lam"])  # noqa: E731
    F = sorted([g for g in recs if g["lam"] == 0], key=key)[0]
    FL = sorted([g for g in recs if g["lam"] > 0], key=key)[0]
    b0 = _eval_cfg({"w": 0.0, "beta": 0.0, "lam": 0.0, "B": B_TUNE})
    g0 = _eval_cfg({"greedy": True, "w": 0.0, "beta": 0.0, "lam": 0.0, "B": 0})
    rec = {"n_tune": len(tune_rows(cal)), "tune_digest": tune_digest(cal), "grid": recs,
           "F": {k: F[k] for k in ("w", "beta", "lam", "cer")}, "FL": {k: FL[k] for k in ("w", "beta", "lam", "cer")},
           "B0_cer": b0["cer"], "G_cer": g0["cer"]}
    save_json(rec, f)
    log(f"tune: F {rec['F']}, FL {rec['FL']}, B0 {b0['cer']:.4f}, G {g0['cer']:.4f}")
    return rec


def stage_beam(tune: dict) -> dict:
    f = own("beam.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    F = tune["F"]
    recs = run_pool([{"w": F["w"], "beta": F["beta"], "lam": 0.0, "B": B} for B in B_GRID])
    c64 = [r for r in recs if r["B"] == 64][0]["cer"]
    chosen = min(r["B"] for r in recs if r["cer"] <= c64 + B_TOL)
    rec = {"sweep": [{"B": r["B"], "cer": r["cer"]} for r in recs], "chosen_B": chosen, "tol": B_TOL}
    save_json(rec, f)
    log(f"beam: {rec}")
    return rec


def configs(tune: dict, beam: dict) -> dict[str, dict]:
    B = beam["chosen_B"]
    F, FL = tune["F"], tune["FL"]
    c = {"G": {"greedy": True, "w": 0.0, "beta": 0.0, "lam": 0.0, "B": 0},
         "B0": {"w": 0.0, "beta": 0.0, "lam": 0.0, "B": B},
         "F": {"w": F["w"], "beta": F["beta"], "lam": 0.0, "B": B},
         "FL": {"w": FL["w"], "beta": FL["beta"], "lam": FL["lam"], "B": B}}
    for b in B_GRID:
        c[f"F@B{b}"] = {"w": F["w"], "beta": F["beta"], "lam": 0.0, "B": b}
        c[f"FL@B{b}"] = {"w": FL["w"], "beta": FL["beta"], "lam": FL["lam"], "B": b}
    return c


# --- stage test --------------------------------------------------------------------------------------


def _session_job(args: tuple[str, dict, dict]) -> dict:
    """Worker: one decoder over one whole track-test session (98 tokens) + per-prompt pieces."""
    name, s, c = args
    f = own("test", f"{name}-u{s['i']}.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    from fidetype.adapters import emg2qwerty as A
    from fidetype.benchmark.registry import keycodes_to_intended_text

    V = vocab98()
    t0 = time.time()
    x = np.asarray(lp_arr(f"u{s['i']}-s1-real.npy"), np.float64)
    if c.get("greedy"):
        am = x.argmax(1)
        keep = np.concatenate([[True], am[1:] != am[:-1]])
        idx = np.nonzero(keep & (am != 0))[0]
        toks, frs = am[idx].tolist(), idx.tolist()
    else:
        d = make_dec(V, c)
        for a in range(0, len(x), 4096):
            d.push(x[a:a + 4096])
        h = d.nbest(1, eos=False)[0]
        toks, frs = h.tokens, h.frames
    del x
    ref = [int(t) for t in lab(s["session"])["key_tok"]]
    e = levenshtein(ref, toks)
    # per-prompt pieces (evaluation prompts of this session)
    _, _, _, ev = rows_split()
    frs_a = np.asarray(frs, np.int64)
    toks_a = np.asarray(toks, np.int64)
    pe = pn = ie = in_ = 0
    for r in ev:
        if r["i"] != s["i"]:
            continue
        m = (frs_a >= r["lo"]) & (frs_a < r["end"])
        codes_h = " ".join(cc for cc in (A.token_key_code(V[t]) for t in toks_a[m].tolist()) if cc)
        rc, hc = r["codes"].split(), codes_h.split()
        pe += levenshtein(np.array([hash(t) for t in rc]), np.array([hash(t) for t in hc]))
        pn += len(rc)
        ti, hi_ = keycodes_to_intended_text(r["codes"]), keycodes_to_intended_text(codes_h)
        ie += char_lev(ti, hi_)
        in_ += len(ti)
    rec = {"decoder": name, "i": s["i"], "edits": e, "ref": len(ref), "hyp": len(toks),
           "prompt_key_edits": pe, "prompt_key_ref": pn, "prompt_int_edits": ie, "prompt_int_ref": in_,
           "seconds": round(time.time() - t0, 1)}
    save_json(rec, f)
    return rec


def _shuffle_job(args: tuple[dict, dict]) -> dict:
    """Worker: control C1 (decoder F, 33-class key form) on one time-shuffled test session."""
    s, c = args
    f = own("test", f"C1-u{s['i']}.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    from fidetype.adapters import emg2qwerty as A

    V98, KV = vocab98(), key_vocab()
    cols = A.token_columns(V98)
    x = np.asarray(lp_arr(f"u{s['i']}-s1-shuf33.npy"), np.float64)
    d = make_dec(KV, c)
    for a in range(0, len(x), 4096):
        d.push(x[a:a + 4096])
    h = d.nbest(1, eos=False)[0]
    ref = [int(cols[t]) for t in lab(s["session"])["key_tok"] if cols[t] > 0]
    rec = {"i": s["i"], "edits": levenshtein(ref, h.tokens), "ref": len(ref), "hyp": len(h.tokens)}
    save_json(rec, f)
    return rec


def _window_job(args: tuple[str, dict, int, int]) -> dict:
    """Worker: top-1 of each evaluation window (33-class key form) for one decoder, a slice of prompts."""
    name, c, a, b = args
    f = own("test", f"win-{name}-{a}.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    R, _, _, ev = rows_split()
    W = R.p1109().Windows()
    KV = key_vocab()
    out = []
    for r in ev[a:b]:
        h = decode_top(W.get(r), KV, c)
        kt = "".join(KV[t] for t in h.tokens)
        out.append({"key": kt, "int": R.resolve(kt)})
    save_json(out, f)
    return {"name": name, "a": a, "n": len(out)}


def stage_test(tune: dict, beam: dict) -> dict:
    import multiprocessing as mp

    R, _, _, ev = rows_split()
    ss = [s for s in R.p1109().sessions() if s["split"] == "test"]
    cf = configs(tune, beam)
    jobs = [(n, s, c) for n, c in cf.items() if not n.startswith("FL@") or n == f"FL@B{beam['chosen_B']}" for s in ss]
    jobs = [j for j in jobs if not own("test", f"{j[0]}-u{j[1]['i']}.json").exists()]
    ctx = mp.get_context("spawn")
    if jobs:
        with ctx.Pool(WORKERS) as pool:
            for i, rec in enumerate(pool.imap_unordered(_session_job, jobs), 1):
                log(f"test session: {i}/{len(jobs)} ({rec['decoder']}, {rec['seconds']} s)")
    cj = [(s, cf["F"]) for s in ss if not own("test", f"C1-u{s['i']}.json").exists()]
    if cj:
        with ctx.Pool(WORKERS) as pool:
            list(pool.imap_unordered(_shuffle_job, cj))
        log("test C1: done")
    step = 160
    wj = [(n, cf[n], a, min(a + step, len(ev))) for n in ("B0", "F", "FL") for a in range(0, len(ev), step)]
    wj = [j for j in wj if not own("test", f"win-{j[0]}-{j[2]}.json").exists()]
    if wj:
        with ctx.Pool(WORKERS) as pool:
            list(pool.imap_unordered(_window_job, wj))
        log("test windows: done")
    own("test", "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
    return {"n_session_jobs": len(jobs)}


# --- guard decoder (safe-WPM re-run) ------------------------------------------------------------------


class GuardDecoder:
    """decode_fn of the arms: P11-12 no-signal gate -> FL (33-class window) -> intended merge -> OOV gate."""

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.KV = key_vocab()
        self.memo: dict[str, list[tuple[str, float]]] = {}
        self.dirty = 0
        g = load_json(P1112 / "gate.json")
        p1112().GATE.update({k: g[k] for k in ("k_min", "r_min", "r_max")})
        R = p1111()
        R.DEC.lex = frozenset(load_json(P1111 / "lexicon.json")["words"])  # type: ignore[index]  # OOV gate only

    def load(self) -> None:
        f = own("guard-memo.pkl")
        if f.exists():
            with open(f, "rb") as fh:
                self.memo.update(pickle.load(fh))

    def save(self) -> None:
        f = own("guard-memo.pkl")
        tmp = f.with_suffix(".tmp")
        with open(tmp, "wb") as fh:
            pickle.dump(self.memo, fh, protocol=4)
        os.replace(tmp, f)
        self.dirty = 0

    def nbest_intended(self, x: np.ndarray) -> list[tuple[str, float]]:
        """FL n-best -> intended texts merged (log-sum-exp of scores), best first, top NBEST_OUT."""
        R = p1111()
        d = make_dec(self.KV, self.cfg)
        d.push(np.asarray(x, np.float64))
        merged: dict[str, float] = {}
        for h in d.nbest(None, eos=True):
            t = R.resolve("".join(self.KV[k] for k in h.tokens))
            merged[t] = float(np.logaddexp(merged.get(t, -np.inf), h.score))
        return sorted(merged.items(), key=lambda kv: (-kv[1], kv[0]))[:NBEST_OUT]

    def post(self, out: list[tuple[str, float]]) -> list[tuple[str, float]]:
        R = p1111()
        if not out or R.oov_gate(out[0][0]):
            return []
        return [(t, s) for t, s in out if t]

    def __call__(self, x: np.ndarray) -> list[tuple[str, float]]:
        if not p1112().gate_pass(x):
            return []
        k = p1111().window_key(x)
        hit = self.memo.get(k)
        if hit is None:
            hit = self.nbest_intended(x)
            self.memo[k] = hit
            self.dirty += 1
            if self.dirty >= 500:
                self.save()
        return self.post(hit)


def guard_decoder(tune: dict, beam: dict) -> GuardDecoder:
    gd = GuardDecoder(configs(tune, beam)["FL"])
    gd.load()
    return gd


def stage_guards(cal: list[dict], ev: list[dict], gd: GuardDecoder, tune: dict, beam: dict) -> dict:
    import fidetype.trust as ft

    R = p1111()
    W = R.p1109().Windows()
    FL = configs(tune, beam)["FL"]
    out = {}
    for arm in ARMS:
        rec_f = own(f"guard-{arm}.status.json")
        if rec_f.exists():
            out[arm] = load_json(rec_f)
            continue
        t0 = time.time()
        rec: dict = {"arm": arm, "n_cal": len(cal), "n_eval": len(ev), "cal_digest": R.p1109().split_digest(cal),
                     "eval_digest": R.p1109().split_digest(ev), "gate": dict(p1112().GATE), "decoder": FL}
        xs = [W.get(r) for r in cal]
        texts = [R.intended_truth(r) for r in cal]
        nulls = [W.get(cal[i], "shuffled") for i in R.null_pick(len(cal))]
        try:
            g = ft.calibrate(xs, texts, alpha=R.ALPHA, delta=R.DELTA, input_kind="logits", vocab=key_vocab(),
                             blank=0, input_scale="log_probs", frame_period=R.FRAME_S, decode_fn=gd,
                             null_inputs=nulls,
                             decoder_name="fidetype-p11-01-crt+e2q-keys+inbeam-tatoeba-noE2Q-6gram+lexicon"
                                          "+intended-text+nosignal-gate",
                             decoder_version=f"p11-07-w{FL['w']}-b{FL['beta']}-l{FL['lam']}-B{FL['B']}",
                             modality="emg", name=f"p11-07-{arm}", seed=R.SEED, audit_text=False, **R.arm_kw(arm))
        except ft.NullControlError as e:
            rec.update(status="refused", reason=str(e)[:2000])
            log(f"guards {arm}: REFUSED ({time.time() - t0:.0f} s): {e}")
        else:
            g.save(own(f"guard-{arm}.json"))
            sh = g.sheet.to_dict()
            rec.update(status="guard", config_id=g.config_id, sheet=sh)
            save_json({"config_id": g.config_id, "sheet": sh, **R.RESEARCH}, OUT / f"guard-{arm}.json")
            log(f"guards {arm}: {g.config_id} ({time.time() - t0:.0f} s)\n{g.sheet}")
        gd.save()
        rec["seconds"] = round(time.time() - t0, 1)
        save_json(rec, rec_f)
        out[arm] = rec
    return out


def stage_decide(ev: list[dict], gd: GuardDecoder) -> dict:
    from fidetype.trust.dropin import load as load_guard

    R = p1111()
    W = R.p1109().Windows()
    out = {}
    for arm in ARMS:
        f = own(f"decisions-{arm}.json")
        if f.exists():
            out[arm] = load_json(f)
            continue
        st = load_json(own(f"guard-{arm}.status.json"))
        if st["status"] != "guard":  # type: ignore[index]
            out[arm] = {"status": "refused"}
            save_json(out[arm], f)
            continue
        g = load_guard(own(f"guard-{arm}.json"), decode_fn=gd)
        rec: dict = {"status": "guard", "units": [r["unit"] for r in ev]}
        t0 = time.time()
        for kind in ("real", "shuffled", "zeros"):
            ds = []
            for r in ev:
                x = W.get(r, kind)
                d = R.decide_one(g, x, gd)
                d["gate"] = bool(p1112().gate_pass(x))
                ds.append(d)
            rec[kind] = ds
            log(f"decide {arm} {kind}: {len(ev)} prompts ({time.time() - t0:.0f} s)")
        gd.save()
        save_json(rec, f)
        out[arm] = rec
    return out


# --- stage latency (CPU, timing class) --------------------------------------------------------------


def stage_latency(ev: list[dict], gd: GuardDecoder, tune: dict, beam: dict) -> dict:
    f = own("latency.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    from fidetype.trust.dropin import load as load_guard
    from fidetype.utils.isolation import isolated

    R = p1111()
    W = R.p1109().Windows()
    cf = configs(tune, beam)
    KV = key_vocab()
    st = load_json(own("guard-S.status.json"))
    holder: dict = {"nb": []}
    guard = load_guard(own("guard-S.json"), decode_fn=lambda x: holder["nb"]) if st["status"] == "guard" else None
    xs = [np.asarray(W.get(r), np.float64) for r in ev]
    res: dict = {"chunk_frames": CHUNK, "n_windows": len(xs), "threads": 1, "configs": {}}
    with isolated("timing") as iso:
        for name in [f"F@B{b}" for b in B_GRID] + [f"FL@B{b}" for b in B_GRID]:
            c = cf[name]
            off, add, chunk_t = [], [], []
            for x in xs:
                # offline: whole window
                t0 = time.perf_counter()
                d = make_dec(KV, c)
                d.push(x)
                hs = d.nbest(None, eos=True)
                off.append(time.perf_counter() - t0)
                # streaming: 4-frame chunks; added latency at the end
                d = make_dec(KV, c)
                n = len(x)
                last_a = ((n - 1) // CHUNK) * CHUNK
                for a in range(0, last_a, CHUNK):
                    t1 = time.perf_counter()
                    d.push(x[a:a + CHUNK])
                    chunk_t.append(time.perf_counter() - t1)
                t1 = time.perf_counter()
                d.push(x[last_a:])
                merged: dict[str, float] = {}
                for h in d.nbest(None, eos=True):
                    t = R.resolve("".join(KV[k] for k in h.tokens))
                    merged[t] = float(np.logaddexp(merged.get(t, -np.inf), h.score))
                nb = sorted(merged.items(), key=lambda kv: (-kv[1], kv[0]))[:NBEST_OUT]
                nb = gd.post(nb) if p1112().gate_pass(x) else []
                if guard is not None:
                    holder["nb"] = nb
                    guard.decide(x)
                add.append(time.perf_counter() - t1)
            q = lambda v, p: float(np.percentile(np.asarray(v) * 1e3, p))  # noqa: E731
            res["configs"][name] = {
                **c, "offline_ms": {"p50": q(off, 50), "p95": q(off, 95)},
                "chunk_push_ms": {"p50": q(chunk_t, 50), "p95": q(chunk_t, 95), "max": float(np.max(chunk_t) * 1e3)},
                "added_ms": {"p50": q(add, 50), "p95": q(add, 95), "max": float(np.max(add) * 1e3)}}
            log(f"latency {name}: {res['configs'][name]}")
        res["measurement_env"] = iso.record
    save_json(res, f)
    return res


# --- stage modellat (ROCm venv) ---------------------------------------------------------------------


N_TORCH_CPU = 30  # amendment 1: the ROCm torch CPU build is BLAS-bound (about 0.7 s per call); a short reference


def stage_modellat() -> dict:
    """ROCm venv: GPU chunk forward (500), torch-CPU reference (30), params + reference output for modellat_np."""
    f = own("modellat-gpu.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    import torch

    E = load_module("emgdec", EXP1101 / "emgdec.py")
    cfg = load_json(EXP1101 / "config.json")["personal"]["model"]  # type: ignore[index]
    mc = E.ModelCfg(**{**cfg, "dilations": tuple(cfg["dilations"])})
    store = E.SessionStore(P1101)
    sp = load_json(P1101 / "splits.json")
    sess = sp["personal"][sp["test_users"][0]]["test"][1]  # type: ignore[index]
    feat = np.asarray(store.feat(sess)[:20000], np.float32)
    rf = mc.receptive_field()
    w = P1101 / "train" / "personal-u0" / "best.pt"
    res: dict = {"receptive_field_frames": rf, "chunk_frames": CHUNK, "n_chunks": N_MODEL_CHUNKS}
    sd = torch.load(w, map_location="cpu", weights_only=True)["model"]
    m0 = E.CRT(mc, store.mean, store.std)
    m0.load_state_dict(sd)
    m0.eval()
    params = {k: v.detach().cpu().numpy().astype(np.float32) for k, v in m0.state_dict().items()}
    with torch.no_grad():
        ref = m0(torch.from_numpy(feat[:rf + CHUNK]).unsqueeze(0))[0].float().numpy()
    np.savez(own("modellat-params-u0.npz"), **params)  # local only (research-only weights)
    np.savez(own("modellat-ref.npz"), feat=feat[:rf + CHUNK], ref=ref)
    res["param_keys"] = sorted(params)
    res["model_cfg"] = {"ring_k": mc.ring_k, "kernel": mc.kernel, "dilations": list(mc.dilations)}
    for dev in ("cuda", "cpu"):
        if dev == "cuda" and not torch.cuda.is_available():
            res[dev] = {"available": False}
            continue
        if dev == "cpu":
            torch.set_num_threads(4)
        m = E.CRT(mc, store.mean, store.std)
        m.load_state_dict(sd)
        m.eval().to(dev)
        ts = []
        n_rep = N_MODEL_CHUNKS if dev == "cuda" else N_TORCH_CPU
        with torch.no_grad():
            for k in range(n_rep + (50 if dev == "cuda" else 3)):
                a = rf + 4 * k
                xx = torch.from_numpy(feat[a - rf:a + CHUNK]).unsqueeze(0).to(dev)
                if dev == "cuda":
                    torch.cuda.synchronize()
                t0 = time.perf_counter()
                y = m(xx)[0, -CHUNK:].float().cpu().numpy()
                ts.append(time.perf_counter() - t0)
        ts = np.asarray(ts[(50 if dev == "cuda" else 3):]) * 1e3
        res[dev] = {"available": True, "n": int(len(ts)), "threads": torch.get_num_threads() if dev == "cpu" else None,
                    "torch": torch.__version__,
                    "p50_ms": float(np.percentile(ts, 50)), "p95_ms": float(np.percentile(ts, 95)),
                    "max_ms": float(ts.max()), "device_name": torch.cuda.get_device_name(0) if dev == "cuda" else
                    "cpu", "out_shape": list(y.shape)}
        log(f"modellat {dev}: {res[dev]}")
    save_json(res, f)
    return res


def stage_modellat_np() -> dict:
    """.venv, isolation class timing, 4 threads: NumPy CRT chunk forward (committed fidetype.pretrained._crt).

    Amendment 1: the CPU number of the gap-37 rule comes from this stage (same maths as the torch model; the
    output is checked against the torch reference chunk).
    """
    f = own("modellat.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    import fidetype.pretrained._crt as C
    from fidetype.utils.isolation import isolated

    g = load_json(own("modellat-gpu.json"))
    with np.load(own("modellat-params-u0.npz")) as z:
        p = {k: np.asarray(z[k]) for k in z.files}
    with np.load(own("modellat-ref.npz")) as z:
        feat, ref = np.asarray(z["feat"]), np.asarray(z["ref"])
    mc = g["model_cfg"]
    kw = dict(ring_k=mc["ring_k"], kernel=mc["kernel"], dilations=tuple(mc["dilations"]))
    out = C._forward(p, feat, **kw)
    diff = float(np.abs(np.exp(out) - np.exp(ref)).max())
    agree = float((out.argmax(1) == ref.argmax(1)).mean())
    rf = g["receptive_field_frames"]
    ts = []
    with isolated("timing") as iso:
        for k in range(N_MODEL_CHUNKS + 50):
            x = np.ascontiguousarray(np.roll(feat, k, axis=0)[:rf + CHUNK])
            t0 = time.perf_counter()
            C._forward(p, x, **kw)[-CHUNK:]
            ts.append(time.perf_counter() - t0)
        env = iso.record
    ts = np.asarray(ts[50:]) * 1e3
    res = {**g, "cpu_torch_rocm_build": g.get("cpu"),
           "cpu": {"impl": "numpy fidetype.pretrained._crt (committed)", "n": int(len(ts)),
                   "threads_env": os.environ.get("OMP_NUM_THREADS"), "p50_ms": float(np.percentile(ts, 50)),
                   "p95_ms": float(np.percentile(ts, 95)), "max_ms": float(ts.max()),
                   "check_max_prob_diff_vs_torch": diff, "check_argmax_agreement": agree},
           "measurement_env_cpu": env}
    log(f"modellat_np: cpu {res['cpu']}")
    save_json(res, f)
    return res


# --- stage score -------------------------------------------------------------------------------------


def stage_score(tune: dict, beam: dict, cal: list[dict], ev: list[dict]) -> dict:
    from fidetype.benchmark.registry import keycodes_to_intended_text

    R = p1111()
    cf = configs(tune, beam)
    ss = [s for s in R.p1109().sessions() if s["split"] == "test"]
    res: dict = {"task": "P11-07", "date": time.strftime("%Y-%m-%d %H:%M"), **R.RESEARCH,
                 "note": "aggregates only (no per-user value, no text, no id)",
                 "tune": {k: tune[k] for k in ("n_tune", "tune_digest", "F", "FL", "B0_cer", "G_cer")},
                 "beam": beam, "published_table3_test_pct": PUB, "p1101_greedy_mean_pct": 15.09,
                 "session_cer": {}, "prompt_pieces": {}}
    per_user: dict = {}
    for name in cf:
        fs = [own("test", f"{name}-u{s['i']}.json") for s in ss]
        if not all(f.exists() for f in fs):
            continue
        rs = [load_json(f) for f in fs]
        cer_u = [r["edits"] / r["ref"] for r in rs]
        per_user[name] = cer_u
        res["session_cer"][name] = {
            "mean_pct": 100 * float(np.mean(cer_u)), "sd_pct": 100 * float(np.std(cer_u, ddof=1)),
            "pooled_pct": 100 * sum(r["edits"] for r in rs) / sum(r["ref"] for r in rs),
            "hyp_over_ref": sum(r["hyp"] for r in rs) / sum(r["ref"] for r in rs), **cf[name]}
        pk = [r["prompt_key_edits"] / r["prompt_key_ref"] for r in rs]
        pi = [r["prompt_int_edits"] / r["prompt_int_ref"] for r in rs]
        res["prompt_pieces"][name] = {
            "key_cer_pooled": sum(r["prompt_key_edits"] for r in rs) / sum(r["prompt_key_ref"] for r in rs),
            "key_cer_mean_users": float(np.mean(pk)),
            "intended_cer_pooled": sum(r["prompt_int_edits"] for r in rs) / sum(r["prompt_int_ref"] for r in rs),
            "intended_cer_mean_users": float(np.mean(pi))}
        if name in ("G", "F"):
            per_user[name + "_int"] = pi
    c1 = [load_json(own("test", f"C1-u{s['i']}.json")) for s in ss]
    res["C1_time_shuffled_key_cer_pooled"] = sum(r["edits"] for r in c1) / sum(r["ref"] for r in c1)
    # windows (guard view)
    truths_i = [R.intended_truth(r) for r in ev]
    truths_k = [R.key_truth(r) for r in ev]
    res["window_top1"] = {}
    for name in ("B0", "F", "FL"):
        out = []
        for a in range(0, len(ev), 160):
            out += load_json(own("test", f"win-{name}-{a}.json"))  # type: ignore[operator]
        ie = sum(char_lev(t, o["int"]) for t, o in zip(truths_i, out))
        ke = sum(char_lev(t, o["key"]) for t, o in zip(truths_k, out))
        res["window_top1"][name] = {"intended_cer_pooled": ie / sum(len(t) for t in truths_i),
                                    "key_cer_pooled": ke / sum(len(t) for t in truths_k),
                                    "intended_exact": sum(R.same(o["int"], t) for t, o in zip(truths_i, out)) / len(ev)}
    assert all(keycodes_to_intended_text(r["codes"]) == R.intended_truth(r) for r in ev[:200])
    # verdicts
    G, F, FL = per_user["G"], per_user["F"], per_user["FL"]
    sc = res["session_cer"]
    v = {"H1": {"F_mean_lt_G": sc["F"]["mean_pct"] < sc["G"]["mean_pct"],
                "users_F_lt_G": int(sum(f < g for f, g in zip(F, G)))},
         "H2_F_le_11.28": sc["F"]["mean_pct"] <= PUB["no_lm"],
         "H3_FL_lt_F": sc["FL"]["mean_pct"] < sc["F"]["mean_pct"],
         "H4_F_int_lt_G": res["prompt_pieces"]["F"]["intended_cer_pooled"] < res["prompt_pieces"]["G"][
             "intended_cer_pooled"],
         "C0_G_within_0.1": abs(sc["G"]["mean_pct"] - 15.09) <= 0.1,
         "C1_ge_0.90": res["C1_time_shuffled_key_cer_pooled"] >= 0.90}
    v["H1"]["pass"] = v["H1"]["F_mean_lt_G"] and v["H1"]["users_F_lt_G"] >= 7
    res["users_FL_lt_F"] = int(sum(a < b for a, b in zip(FL, F)))
    # latency
    if own("latency.json").exists():
        lat = load_json(own("latency.json"))
        res["latency"] = lat
        ml = load_json(own("modellat.json")) if own("modellat.json").exists() else None
        res["modellat"] = ml
        if ml is not None:
            cpu = ml["cpu"]["p95_ms"]
            h5 = {}
            for name, c in lat["configs"].items():
                tot = c["added_ms"]["p95"] + cpu
                h5[name] = {"added_p95_ms": c["added_ms"]["p95"], "plus_cpu_model_p95_ms": tot, "meets_50ms": tot <= 50.0,
                            "chunk_realtime": c["chunk_push_ms"]["p95"] + ml["cpu"]["p95_ms"] < 10.0 * CHUNK}
            res["H5"] = h5
            v["H5_chosen_FL"] = h5[f"FL@B{beam['chosen_B']}"]["meets_50ms"]
            v["H5_chosen_F"] = h5[f"F@B{beam['chosen_B']}"]["meets_50ms"]
    # safe WPM
    res["arms"] = {}
    for arm in ARMS:
        if not own(f"guard-{arm}.status.json").exists():
            continue
        st = load_json(own(f"guard-{arm}.status.json"))
        a: dict = {"status": st["status"], "cal_digest": st["cal_digest"], "eval_digest": st["eval_digest"]}
        if st["status"] == "guard" and own(f"decisions-{arm}.json").exists():
            sh = st["sheet"]
            a["config_id"] = st["config_id"]
            a["sheet"] = {k: sh.get(k) for k in ("alpha", "delta", "n_items", "n_fit", "n_policy", "n_ltt",
                                                 "feasible", "commit_threshold", "controls", "warnings", "confidence")}
            d = load_json(own(f"decisions-{arm}.json"))
            a.update(R.score_arm(arm, d, ev, sh))
            a["verdicts"] = R.verdicts(a, sh, arm)
            real = d["real"]
            a["gate_cost"] = {"real_eval_gated": sum(not x["gate"] for x in real) / len(ev)}
            log(f"score {arm}: commits {a['n_commits']} wrong {a['n_wrong_commits']}; {a['verdicts']}")
        else:
            a["reason"] = st.get("reason")
        res["arms"][arm] = a
    p9 = load_json(P1109 / "guard-P.status.json")
    res["digests_match_p1109"] = all(a["cal_digest"] == p9["cal_digest"] and a["eval_digest"] == p9["eval_digest"]
                                     for a in res["arms"].values())
    res["verdicts"] = v
    save_json(res, OUT / "results.json")
    log(f"score: verdicts {v}")
    return res


# --- main --------------------------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stages", nargs="+", choices=("tune", "beam", "test", "guards", "decide", "latency",
                                                  "modellat", "modellat_np", "score", "all"))
    a = ap.parse_args()
    st = set(a.stages)
    if "modellat" in st:
        stage_modellat()
        return 0
    if "modellat_np" in st:
        stage_modellat_np()
        return 0
    if "all" in st:
        st |= {"tune", "beam", "test", "guards", "decide", "latency", "score"}
    keep_awake(True)
    try:
        R, rows, cal, ev = rows_split()
        R.p1109().check_track_splits(R.p1109().sessions())
        tune = stage_tune(cal) if st & {"tune", "beam", "test", "guards", "decide", "latency", "score"} else None
        beam = stage_beam(tune) if tune is not None else None
        if "test" in st:
            stage_test(tune, beam)
        gd = None
        if st & {"guards", "decide", "latency"}:
            gd = guard_decoder(tune, beam)
        if "guards" in st:
            stage_guards(cal, ev, gd, tune, beam)
        if "decide" in st:
            stage_decide(ev, gd)
        if "latency" in st:
            stage_latency(ev, gd, tune, beam)
        if "score" in st:
            stage_score(tune, beam, cal, ev)
        if "all" in a.stages:
            own("DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
            log("all: DONE")
    finally:
        keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
