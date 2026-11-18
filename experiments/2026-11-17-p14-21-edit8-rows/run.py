"""P14-21: downstream T15 rows with the B2T '25 word decoder at edit penalty 8 (plan.md, pre-registered).

Each stage runs in its own process with ``--edit 12`` (reference) or ``--edit 8``. The edit penalty is set by
a wrapper on ``PhonemeWordDecoder.__init__`` that changes only the B2T '25 paper point (lm 1.0, edit 12,
bonus 3) to the requested edit penalty, and counts every change. The original experiment scripts are loaded
read only; their output paths are redirected to our folder before any call.

Stages:
  r1 --model m4-13|m4-12   P14-05 safe WPM (drop-in guard on val_select, decide val_eval)
  r3                       M2-19 fit / eval / controls (refit with the given decoder)
  r2                       M4-13 eval trust rows (frozen M2-19 configs; + secondary edit-8 chain config)
  r4 --model m4-13|m4-12   P6-02b partial v0.2 entry + scorer CLI
  r5                       P5-02 precision guarantee, T15
  r6 --model m4-13|m4-12 [--replay]   P3-08 prep (+ real-time collector replay)
  compare                  reference checks, CI half-widths, decisions -> results/*.json
  queue                    all of the above in the plan order, one child process each

Local outputs only: C:/Users/zhang/bci-data/derived/p14-21/. Repo: counts, rates and metrics only.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import argparse  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pickle  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP = REPO / "experiments"
sys.path.insert(0, str(REPO / "src"))
DER = Path("C:/Users/zhang/bci-data/derived/p14-21")
assert DER.name == "p14-21"
DER.mkdir(parents=True, exist_ok=True)
OUT = HERE / "results"
LOGF = DER / "run.log"
PY = str(REPO / ".venv/Scripts/python.exe")
SEED, NBOOT = 0, 2000
PATCH = {"edit": None, "changed": 0, "constructed": 0}


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        o = float(o)
    if isinstance(o, float) and not math.isfinite(o):
        return str(o)
    return o


def dump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(clean(obj), indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def load(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def patch_edit(edit: float) -> None:
    """Set the edit penalty of the B2T '25 word decoder (paper point lm 1.0 / edit 12 / bonus 3 only)."""
    from fidetype.lm import phoneme_words as PW

    orig = PW.PhonemeWordDecoder.__init__
    PATCH["edit"] = float(edit)

    def init(self, *a, **kw):
        PATCH["constructed"] += 1
        if (float(kw.get("lm_weight", -1)) == 1.0 and float(kw.get("edit_penalty", -1)) == 12.0
                and float(kw.get("word_bonus", -1)) == 3.0):
            kw["edit_penalty"] = float(edit)
            PATCH["changed"] += 1
        orig(self, *a, **kw)

    PW.PhonemeWordDecoder.__init__ = init


def patch_info(dec=None) -> dict:
    out = dict(PATCH)
    if dec is not None:
        out["decoder_edit_penalty"] = float(dec.wdec.edit_penalty)
        out["decoder_lm_weight"] = float(dec.wdec.lm_weight)
        out["decoder_word_bonus"] = float(dec.wdec.word_bonus)
        assert out["decoder_edit_penalty"] == PATCH["edit"], out
    return out


def norm(t) -> str:
    return " ".join((t or "").split())


# ---------------------------------------------------------------------------
# bootstrap helpers (per-trial values of the reference run)
# ---------------------------------------------------------------------------

def boot_idx(n: int):
    rng = np.random.default_rng(SEED)
    for _ in range(NBOOT):
        yield rng.integers(0, n, n)


def hw_ratio(num, den) -> float:
    num, den = np.asarray(num, float), np.asarray(den, float)
    v = [num[i].sum() / max(den[i].sum(), 1e-12) for i in boot_idx(len(num))]
    lo, hi = np.percentile(v, [2.5, 97.5])
    return float((hi - lo) / 2)


def hw_ewpm(recs) -> float:
    from fidetype.eval.ewpm import summarize

    v = [summarize([recs[j] for j in i])["ewpm"] for i in boot_idx(len(recs))]
    lo, hi = np.percentile(v, [2.5, 97.5])
    return float((hi - lo) / 2)


def safe_arrays(committed, correct, nw, nc, ns) -> dict:
    return {"committed": [bool(x) for x in committed], "correct": [bool(x) for x in correct],
            "nw": [float(x) for x in nw], "nc": [float(x) for x in nc], "ns": [float(x) for x in ns]}


def hw_safe(arr: dict) -> float:
    from fidetype.benchmark.safe_wpm import CorrectionRule, _arrays, _point

    a = _arrays(arr["committed"], arr["correct"], arr["nw"], arr["nc"], arr["ns"])
    pen = CorrectionRule().penalty(a["nc"])
    n = len(a["cm"])
    v = [_point(a, pen, np.bincount(i, minlength=n).astype(float))["wpm"] for i in boot_idx(n)]
    lo, hi = np.percentile(v, [2.5, 97.5])
    return float((hi - lo) / 2)


def wilson_hw(p: float, n: int) -> float:
    if n <= 0 or p is None:
        return math.nan
    z = 1.959963984540054
    den = 1 + z * z / n
    return float(z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den)


# ---------------------------------------------------------------------------
# R1: P14-05 safe WPM (stage_t15_compute, outputs redirected)
# ---------------------------------------------------------------------------

def stage_r1(model: str, edit: int) -> None:
    import fidetype.trust as ft

    p1405 = load_module("p1405run", EXP / "2026-11-16-p14-05-safe-wpm/run.py")
    p1405.LOGF = DER / "r1-module.log"
    p1403 = load_module("p1403run", EXP / "2026-11-16-p14-03-replay-validation/run.py")
    p1403.LOGF = DER / "r1-module.log"
    Bm = p1403.B
    d_in = p1405.DER / "m4-01-02-lookahead"
    sessions = load(d_in / "sessions.json")
    texts = load(d_in / "texts.json")
    D = p1405.DER
    if model == "m4-13":
        cal_p = D / "trust-reruns-m4-13" / "logprobs-m4-13-long0-val_select.npz"
        held_p = D / "m4-13" / "logprobs-m4-13-long0-val_eval.npz"
    else:
        cal_p = D / "m2-19-trust-retune" / "logprobs-m2-19-m4-12-fixed0.npz"
        held_p = d_in / "logprobs-m4-12-fixed0.npz"
    npz: dict = {}

    def part(path: Path, name: str):
        z = np.load(path)
        keys = p1405.t15_keys(path, sessions, name)
        xs, ts, ph = [], [], []
        for k in keys:
            s, p, i, _ = k.split("|")
            xs.append(z[k].astype(np.float32))
            ts.append(texts[s][p][int(i)])
            ph.append(p1403.ph_symbols(npz, d_in, s, p, int(i)))
        return keys, xs, ts, ph

    _, cx, ct, cph = part(cal_p, "val_select")
    hkeys, hx, ht, _ = part(held_p, "val_eval")
    bt = load_module("b2t25run", EXP / "2026-11-10-b2t25-trust/run.py")
    tune = bt.load_json("tune.json")
    dec = bt.Decoders([], {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    pinfo = patch_info(dec)
    fn = p1403.make_decode_fn(dec)
    t0 = time.time()
    guard = ft.calibrate(cx, ct, alpha=p1405.ALPHA, delta=p1405.DELTA, vocab=list(Bm.SYMBOL_VOCAB), blank=0,
                         input_scale="log_probs", frame_period=0.08, decode_fn=fn, stream_texts=cph,
                         decoder_name=f"p14-05-t15-{model}", modality="intracortical", name=f"p14-05-t15-{model}",
                         seed=p1405.SEED)
    res = [guard.decide(x, utterance_id=f"t15-{model}-{i}") for i, x in enumerate(hx)]
    decisions = [{"i": i, "key": k, "action": r.action, "raw": r.raw_action, "p_top1": r.p_top1, "text": r.text,
                  "truth": norm(t)} for i, (k, r, t) in enumerate(zip(hkeys, res, ht))]
    tag = f"r1-{model}-e{edit}"
    dump(decisions, DER / f"{tag}-decisions.json")
    guard.save(DER / f"{tag}-guard.json")
    sheet = guard.sheet.to_dict()
    durs = p1405.t15_durations(hkeys)
    blk = p1405.replay_block(decisions, durs, sheet, f"T15 {model} val_eval + drop-in guard, edit {edit}",
                             "measured trial duration: 20 ms neural bins per val_eval trial (B2T '25)")
    truths = [d["truth"] for d in decisions]
    com = [d["action"] == "commit" for d in decisions]
    arr = safe_arrays(com, [c and norm(d["text"]) == t for c, d, t in zip(com, decisions, truths)],
                      [len(t.split()) for t in truths], [len(t) for t in truths], durs)
    dump({"block": blk, "arrays": arr, "patch": pinfo, "seconds": round(time.time() - t0, 1),
          "sheet": {k: sheet.get(k) for k in ("config_id", "commit_threshold", "feasible", "n_items", "n_ltt")}},
         DER / f"{tag}.json")
    log(f"{tag}: safe WPM {blk.get('value')} ({blk.get('status')}), commits {blk['n_commits']}, wrong "
        f"{blk['n_wrong_commits']}; patch {pinfo}")


# ---------------------------------------------------------------------------
# R3: M2-19 (module stages with redirected paths)
# ---------------------------------------------------------------------------

def stage_r3(edit: int) -> None:
    M = load_module("m219run", EXP / "2026-11-15-m2-19-trust-retune/run.py")
    own_in = M.OWN
    tag = f"r3-e{edit}"
    out = DER / tag
    out.mkdir(exist_ok=True)
    M.LOGF = DER / f"{tag}-module.log"
    M.OUT = out
    M.CFG_DIR = out / "configs"
    M.CFG_DIR.mkdir(exist_ok=True)
    orig_dump = M.T.dump

    def redirect_dump(obj, path):
        path = Path(path)
        if path.parent.resolve() == own_in.resolve():
            path = out / path.name
        assert DER in path.parents, path
        return orig_dump(obj, path)

    M.T.dump = redirect_dump
    stats = {"cache_misses": 0}
    Base = M.Ctx

    class Ctx(Base):
        def __init__(self) -> None:
            super().__init__()  # reads the committed cache (read only)
            if edit != 12:
                self.cache = {}
            self.cache_path = out / "word-decode-cache.pkl"
            if self.cache_path.exists():
                self.cache.update(pickle.loads(self.cache_path.read_bytes()))
            self.info = patch_info(self.dec)

        def words_fn(self, stream):
            k = hashlib.sha1(np.ascontiguousarray(stream.log_probs, dtype=np.float32).tobytes()).hexdigest()
            if k not in self.cache:
                stats["cache_misses"] += 1
            return super().words_fn(stream)

    M.Ctx = Ctx
    cap: list = []
    state = {"tag": None}
    orig_sum, orig_eval = M.summarize, M.evaluate

    def summ(recs):
        cap.append((state["tag"], list(recs)))
        return orig_sum(recs)

    def evaluate(ctx, fz, items):
        state["tag"] = fz.config_id
        try:
            return orig_eval(ctx, fz, items)
        finally:
            state["tag"] = None

    M.summarize, M.evaluate = summ, evaluate
    t0 = time.time()
    M.stage_fit()
    M.stage_eval()
    M.stage_controls()
    per = {}
    n_always = 0
    order = list(M.DECODERS)
    for tg, recs in cap:
        if tg is None:
            tg = f"always_commit/{order[n_always]}"
            n_always += 1
        while tg in per:  # the old frozen config is evaluated once per decoder: second one gets '#2'
            tg += "#2"
        per[tg] = {"wrong": [bool(r.wrong_commit) for r in recs]}
        if edit == 12:
            per[tg]["ewpm_hw"] = hw_ewpm(recs)
    dump({"patch": dict(PATCH), "cache_misses": stats["cache_misses"], "per": per,
          "seconds": round(time.time() - t0, 1)}, DER / f"{tag}.json")
    log(f"{tag}: done, cache misses {stats['cache_misses']}, patch {PATCH}")


# ---------------------------------------------------------------------------
# R2: M4-13 eval trust rows (module functions, outputs redirected)
# ---------------------------------------------------------------------------

def word_quality_pt(fn, items, scale_T: float) -> dict:
    from fidetype.eval.metrics import edit_distance
    from fidetype.trust.calibration import TemperatureScaler

    sc = TemperatureScaler()
    sc.temperature = scale_T
    ew, nw, ex, inb, ec, nc = [], [], [], [], [], []
    for it in items:
        st = it.stream(0)
        nb = fn(sc.transform_stream(st) if scale_T != 1.0 else st)
        top = nb.texts[0] if len(nb) else ""
        ec.append(edit_distance(it.text, top))
        nc.append(len(it.text))
        ew.append(edit_distance(it.text.split(), top.split()))
        nw.append(len(it.text.split()))
        ex.append(top == it.text)
        inb.append(it.text in nb.texts)
    n = len(items)
    return {"cer": sum(ec) / max(1, sum(nc)), "wer": sum(ew) / max(1, sum(nw)), "sentence_exact": sum(ex) / n,
            "n_exact": int(sum(ex)), "truth_in_nbest": sum(inb) / n, "_ew": ew, "_nw": nw}


def stage_r2(edit: int) -> None:
    from fidetype.eval.ewpm import summarize
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.trust.frozen import FrozenTrustConfig
    from fidetype.trust.guard import shuffle_stream, uniform_stream

    E = load_module("m413eval", EXP / "2026-11-15-m4-13-long-train/eval.py")
    tag = f"r2-e{edit}"
    E.LOGF = DER / f"{tag}-module.log"
    stats = {"cache_misses": 0}

    class Ctx(E.Ctx):
        def __init__(self) -> None:
            super().__init__("word-decode-cache.pkl" if edit == 12 else "__p14-21-no-such-cache__.pkl")
            self.cache_path = DER / f"{tag}-word-decode-cache.pkl"
            if self.cache_path.exists():
                self.cache.update(pickle.loads(self.cache_path.read_bytes()))
            self.info = patch_info(self.dec)

        def words_fn(self, stream):
            k = hashlib.sha1(np.ascontiguousarray(stream.log_probs, dtype=np.float32).tobytes()).hexdigest()
            if k not in self.cache:
                stats["cache_misses"] += 1
            return super().words_fn(stream)

    CFG = E.CFG
    meta = load(E.OWN / f"decode-{E.RUN}-val_eval.json")
    ctx = Ctx()
    items, keys = ctx.items(E.OWN / f"logprobs-{E.RUN}-val_eval.npz", meta["model_config"])
    n = len(items)
    base = FrozenTrustConfig.load(REPO / CFG["trust"]["m2_19_config"])
    assert base.config_id == CFG["trust"]["m2_19_config_id"], base.config_id
    g = CFG["trust"]["commit_gate"]
    gated = base.with_commit_gate(g["min_chars"], g["min_words"], g["max_guard_risk"])
    assert gated.config_id == CFG["trust"]["gated_config_id_expected"], gated.config_id
    configs = {"gated": gated, "ungated": base}
    chain = DER / "r3-e8" / "configs" / "trust-config-t15-m4-12-dedicated_0-ltt.json"
    if edit == 8 and chain.exists():
        c8 = FrozenTrustConfig.load(chain)
        configs["chain_e8_gated"] = c8.with_commit_gate(g["min_chars"], g["min_words"], g["max_guard_risk"])
    t0 = time.time()
    res: dict = {"n": n, "patch": ctx.info, "configs": {k: v.config_id for k, v in configs.items()}}
    per: dict = {}
    for wt, T in (("words_T1", 1.0), ("words_cfgT", base.frame_temperature)):
        q = word_quality_pt(ctx.words_fn, items, T)
        per[wt] = {"ew": q.pop("_ew"), "nw": q.pop("_nw")}
        res[wt] = q
    ctx.save()
    log(f"{tag}: WER T1 {res['words_T1']['wer']:.4f} cfgT {res['words_cfgT']['wer']:.4f}")
    res["trust"] = {}
    for name, fz in configs.items():
        r, decs = E.trust_eval(ctx, fz, items)
        recs = ctx.pipe_from(fz).run_items(items, E.ReplayPolicy(decs))
        assert summarize(recs)["ewpm"] == r["ewpm"]
        res["trust"][name] = r
        per[name] = {"ewpm_hw": hw_ewpm(recs) if edit == 12 else None}
        dump({"keys": keys, "decisions": [d.to_event(include_text=True) for d in decs]}, DER / f"{tag}-decisions-{name}.json")
        ctx.save()
        log(f"{tag} trust {name}: commit {r['n_commit']}/{n} wrong {r['n_wrong_commit']} eWPM {r['ewpm']:.2f}")
    allc = TrustPipeline(ctx.words_fn, HarnessConfig(seed=E.SEED, user_config=ctx.user, max_attempts=1,
                                                     policy="always_commit"), {})
    allc.frame_scaler = ctx.pipe_from(base).frame_scaler
    ar = allc.run_items(items)
    nwr = sum(bool(x.wrong_commit) for x in ar)
    res["baselines"] = {"always_commit": {"ewpm": summarize(ar)["ewpm"], "n_wrong_commit": nwr, "wrong_commit": nwr / n}}
    per["always_commit"] = {"ewpm_hw": hw_ewpm(ar) if edit == 12 else None}
    rng = np.random.default_rng(E.SEED)
    idx = sorted(rng.choice(n, CFG["trust"]["controls_n"], replace=False).tolist())
    sub = [items[i] for i in idx]
    variants = {"real": [it.stream(0) for it in sub],
                "frame_shuffled": [shuffle_stream(it.stream(0), rng) for it in sub],
                "uniform": [uniform_stream(it.stream(0), rng, 0.05) for it in sub]}
    res["controls"] = {"n": len(sub), "conditions": {}}
    for vn, streams in variants.items():
        for name in ("gated", "ungated"):
            recs = ctx.pipe_from(configs[name]).run_items([Item(s, it.text, stream_text=it.stream_text)
                                                           for s, it in zip(streams, sub)])
            com = [x for x in recs if x.actions[-1:] == ["COMMIT"]]
            res["controls"]["conditions"][f"{vn}/{name}"] = {
                "n_commit": len(com), "n_wrong_commit": sum(bool(x.wrong_commit) for x in recs)}
        ctx.save()
    c = res["controls"]["conditions"]
    res["controls_pass_gated"] = c["uniform/gated"]["n_commit"] == 0 and c["frame_shuffled/gated"]["n_commit"] == 0
    res["cache_misses"] = stats["cache_misses"]
    res["seconds"] = round(time.time() - t0, 1)
    dump({"res": res, "per": per}, DER / f"{tag}.json")
    log(f"{tag}: done in {res['seconds']:.0f} s; cache misses {stats['cache_misses']}; controls pass "
        f"{res['controls_pass_gated']}")


# ---------------------------------------------------------------------------
# R4: P6-02b partial v0.2 entry (+ scorer CLI)
# ---------------------------------------------------------------------------

def stage_r4(model: str, edit: int) -> None:
    M = load_module("p602brun", EXP / "2026-11-17-p6-02b-v02-entries/run.py")
    tag = f"r4-{model}-e{edit}"
    out = DER / tag
    out.mkdir(exist_ok=True)
    M.SUBS = out / "submissions"
    M.OUT = out
    M.LOGF = DER / f"{tag}-module.log"
    t0 = time.time()
    info = M.stage_t15_model(model)
    name = f"b2t25-t15__{model}__guard"
    card = out / f"{name}.json"
    cmd = [PY, "-m", "fidetype.benchmark", "score", "b2t25-t15", str(M.SUBS / name), "--truth",
           str(M.truth_path("b2t25-t15")), "--out", str(card)]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(REPO / "src")})
    log(f"{tag}: score exit {r.returncode}\n{r.stdout.strip()[-600:]}\n{r.stderr.strip()[-400:]}")
    if not card.exists():
        raise SystemExit(f"{tag}: score failed")
    dump({"info": info, "patch": dict(PATCH), "score_exit": r.returncode, "seconds": round(time.time() - t0, 1)},
         DER / f"{tag}.json")


# ---------------------------------------------------------------------------
# R5: P5-02 T15
# ---------------------------------------------------------------------------

def stage_r5(edit: int) -> None:
    M = load_module("p502run", EXP / "2026-11-16-p5-02-precision/run.py")
    tag = f"r5-e{edit}"
    M.OWN = DER / tag
    M.OWN.mkdir(exist_ok=True)
    M.LOGF = DER / f"{tag}-module.log"
    P = M.load_p14_03()
    P.LOGF = DER / f"{tag}-module.log"
    t0 = time.time()
    out = M.run_set("t15", P)
    dump({"t15": out, "patch": dict(PATCH), "seconds": round(time.time() - t0, 1)}, DER / f"{tag}.json")
    log(f"{tag}: done; patch {PATCH}")


# ---------------------------------------------------------------------------
# R6: P3-08 prep (+ replay)
# ---------------------------------------------------------------------------

def stage_r6(model: str, edit: int, replay: bool) -> None:
    M = load_module("p308run", EXP / "2026-11-17-p3-08-b2t25-collector-replay/run.py")
    committed = M.OWN_ROOT / model
    root = DER / f"r6-e{edit}"
    M.OWN_ROOT = root / "p3-08-collector-replay"
    M.OUT = root / "results"
    o = M.own(model)
    tag = f"r6-{model}-e{edit}"
    t0 = time.time()
    if not (o / "profile.json").exists():
        M.prep(model)
    chk = {}
    for f in ("nbest-val_select.json", "nbest-val_eval.json", "nbest-null-shuffled.json"):
        a, b = load(o / f), load(committed / f)
        chk[f] = {"n": len(a), "same_keys": sorted(a) == sorted(b),
                  "n_equal_lists": sum(a[k] == b.get(k) for k in a)}
    sa, sb = load(o / "guard-sheet.json"), load(committed / "guard-sheet.json")
    chk["guard_sheet"] = {"commit_threshold": [sa.get("commit_threshold"), sb.get("commit_threshold")],
                          "config_id": [sa.get("config_id"), sb.get("config_id")],
                          "controls_passed": [[c.get("passed") for c in sa.get("controls", [])],
                                              [c.get("passed") for c in sb.get("controls", [])]]}
    res = {"check_vs_committed_prep": chk, "patch": dict(PATCH), "prep_seconds": round(time.time() - t0, 1)}
    if replay:
        M.replay(model, M.DEFAULT_TRIALS, "websocket")
        res["summary"] = load(M.OUT / f"{model}-summary.json")
    dump(res, DER / f"{tag}{'-replay' if replay else ''}.json")
    log(f"{tag}: {json.dumps(chk)[:600]}")


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------

class Rule:
    def __init__(self) -> None:
        self.rows: list = []

    def add(self, row: str, metric: str, old, ref, new, hw, kind: str) -> None:
        """old = committed, ref = edit-12 rerun, new = edit 8."""
        def f(x):
            return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else float(x)
        old, ref, new = f(old), f(ref), f(new)
        repro = (old is None and ref is None) or (old is not None and ref is not None and abs(old - ref) < 1e-6)
        delta = None if old is None or new is None else new - old
        # a change of exactly 0 is never an effect (a zero-width bootstrap CI, e.g. safe WPM 0 -> 0, gave a false hit)
        eff = None if delta is None or hw is None or not math.isfinite(hw) else (abs(delta) > 1e-12 and abs(delta) >= hw - 1e-12)
        self.rows.append({"row": row, "metric": metric, "committed": old, "ref_e12": ref, "e8": new,
                          "delta": delta, "half_width": hw, "hw_kind": kind,
                          "ratio": (abs(delta) / hw) if (delta is not None and hw) else None,
                          "effect": eff, "reproduced": repro})

    def summary(self, prefix: str) -> dict:
        rs = [r for r in self.rows if r["row"].startswith(prefix)]
        bad = {r["row"] for r in rs if not r["reproduced"]} | {r["row"] for r in rs if r.get("not_used")}
        for r in rs:  # plan: no edit-8 result of a row whose reference did not reproduce is used
            if r["row"] in bad:
                r["effect"] = None
                r["not_used"] = True
        eff = [r for r in rs if r["effect"]]
        return {"n_metrics": len(rs), "n_decided": sum(r["effect"] is not None for r in rs), "n_effects": len(eff),
                "all_reproduced": all(r["reproduced"] for r in rs), "rows_not_used": sorted(bad),
                "not_reproduced": [f"{r['row']}:{r['metric']}" for r in rs if not r["reproduced"]],
                "effects": [f"{r['row']}:{r['metric']} {r['committed']} -> {r['e8']} (hw {r['half_width']:.4g})"
                            for r in eff]}


def eam(k, n):
    return (k / n) if n else None


def counts_rows(R: Rule, row: str, n: int, old: dict, ref: dict, new: dict, hw_extra: dict | None = None) -> None:
    """old/ref/new: {'commits', 'wrong'}; rates of n trials + error among commits."""
    for m, key in (("commit_rate", "commits"), ("wrong_commit_rate", "wrong")):
        po = old[key] / n
        R.add(row, m, po, ref[key] / n, new[key] / n, wilson_hw(po, n), f"Wilson n={n}")
    oc, nc = old["commits"], new["commits"]
    if oc and nc:
        R.add(row, "error_among_commits", eam(old["wrong"], oc), eam(ref["wrong"], ref["commits"]),
              eam(new["wrong"], nc), wilson_hw(old["wrong"] / oc, oc), f"Wilson n={oc}")
    else:
        R.add(row, "error_among_commits (0 commits: commit rate decides)", eam(old["wrong"], oc),
              eam(ref["wrong"], ref["commits"]), eam(new["wrong"], nc), None, "not compared")


def compare_r1(R: Rule, out: dict) -> None:
    sw = load(EXP / "2026-11-16-p14-05-safe-wpm/results/safe-wpm.json")["stages"]
    for model, st in (("m4-13", "t15-m4-13"), ("m4-12", "t15-m4-12-recompute")):
        pr, p12, p8 = DER / f"r1-{model}-e12.json", DER / f"r1-{model}-e12.json", DER / f"r1-{model}-e8.json"
        if not (p12.exists() and p8.exists()):
            out[f"R1/{model}"] = "not run"
            continue
        old, ref, new = sw[st]["result"], load(pr), load(p8)
        rb, nb = ref["block"], new["block"]
        row = f"R1/{model}"
        n = old["n_trials"]
        counts_rows(R, row, n, {"commits": old["n_commits"], "wrong": old["n_wrong_commits"]},
                    {"commits": rb["n_commits"], "wrong": rb["n_wrong_commits"]},
                    {"commits": nb["n_commits"], "wrong": nb["n_wrong_commits"]})
        R.add(row, "safe_wpm", old["value"], rb["value"], nb["value"], hw_safe(ref["arrays"]), "trial bootstrap")
        out[row] = {"committed": {k: old.get(k) for k in ("value", "status", "n_commits", "n_wrong_commits",
                                                          "unguarded_wpm", "no_bci_wpm", "config_id")},
                    "ref_e12": {k: rb.get(k) for k in ("value", "status", "n_commits", "n_wrong_commits",
                                                       "unguarded_wpm", "config_id")},
                    "e8": {k: nb.get(k) for k in ("value", "status", "n_commits", "n_wrong_commits", "unguarded_wpm",
                                                  "wpm_no_penalty", "error_among_commits", "measured_wrong_commit",
                                                  "measured_wrong_commit_cp95", "no_bci_wpm", "config_id",
                                                  "committed_correct_words", "total_words")},
                    "e8_sheet": new["sheet"], "ref_sheet": ref["sheet"], "patch_e8": new["patch"],
                    "patch_ref": ref["patch"],
                    "e8_above_no_bci": (nb["value"] or 0) > (nb.get("no_bci_wpm") or math.inf)}


def compare_r2(R: Rule, out: dict) -> None:
    p12, p8 = DER / "r2-e12.json", DER / "r2-e8.json"
    if not (p12.exists() and p8.exists()):
        out["R2"] = "not run"
        return
    old = load(EXP / "2026-11-15-m4-13-long-train/results/eval.json")
    ref, new = load(p12), load(p8)
    rr, nr, per = ref["res"], new["res"], ref["per"]
    n = old["n"]
    for wt in ("words_T1", "words_cfgT"):
        R.add(f"R2/{wt}", "wer", old[wt]["wer"], rr[wt]["wer"], nr[wt]["wer"],
              hw_ratio(per[wt]["ew"], per[wt]["nw"]), "trial bootstrap")
        for m in ("sentence_exact", "truth_in_nbest"):
            R.add(f"R2/{wt}", m, old[wt][m], rr[wt][m], nr[wt][m], wilson_hw(old[wt][m], n), f"Wilson n={n}")
    for name in ("gated", "ungated"):
        o, r_, w = old["trust"][name], rr["trust"][name], nr["trust"][name]
        row = f"R2/trust_{name}"
        counts_rows(R, row, n, {"commits": o["n_commit"], "wrong": o["n_wrong_commit"]},
                    {"commits": r_["n_commit"], "wrong": r_["n_wrong_commit"]},
                    {"commits": w["n_commit"], "wrong": w["n_wrong_commit"]})
        R.add(row, "ewpm", o["ewpm"], r_["ewpm"], w["ewpm"], per[name]["ewpm_hw"], "trial bootstrap")
    o, r_, w = old["baselines"]["always_commit"], rr["baselines"]["always_commit"], nr["baselines"]["always_commit"]
    R.add("R2/always_commit", "wrong_commit_rate", o["wrong_commit"], r_["wrong_commit"], w["wrong_commit"],
          wilson_hw(o["wrong_commit"], n), f"Wilson n={n}")
    R.add("R2/always_commit", "ewpm", o["ewpm"], r_["ewpm"], w["ewpm"], per["always_commit"]["ewpm_hw"],
          "trial bootstrap")
    ctl = {k: [old["controls"]["conditions"][k]["n_commit"], rr["controls"]["conditions"][k]["n_commit"],
               nr["controls"]["conditions"][k]["n_commit"]] for k in nr["controls"]["conditions"]}
    out["R2"] = {"controls_commits_committed_ref_e8": ctl, "controls_pass_gated_e8": nr["controls_pass_gated"],
                 "cache_misses": {"ref": rr["cache_misses"], "e8": nr["cache_misses"]},
                 "patch": {"ref": rr["patch"], "e8": nr["patch"]}, "configs": nr["configs"],
                 "secondary_chain_e8_gated": nr["trust"].get("chain_e8_gated")}


def compare_r3(R: Rule, out: dict) -> None:
    d12, d8 = DER / "r3-e12", DER / "r3-e8"
    if not ((DER / "r3-e12.json").exists() and (DER / "r3-e8.json").exists()):
        out["R3"] = "not run"
        return
    C = EXP / "2026-11-15-m2-19-trust-retune/results"
    of, oe, oc = load(C / "fit.json"), load(C / "eval.json"), load(C / "controls.json")
    rf, re_, rc = load(d12 / "fit.json"), load(d12 / "eval.json"), load(d12 / "controls.json")
    nf, ne, nc = load(d8 / "fit.json"), load(d8 / "eval.json"), load(d8 / "controls.json")
    per = load(DER / "r3-e12.json")["per"]
    fitinfo = {}
    for k in of["conditions"]:
        fitinfo[k] = {f: [of["conditions"][k][f], rf["conditions"][k][f], nf["conditions"][k][f]]
                      for f in ("config_id", "lambda_hat", "feasible", "final_commit_p", "frame_T", "sentence_T")}
    for k, o in oe["conditions"].items():
        r_, w = re_["conditions"][k], ne["conditions"][k]
        row = f"R3/{k}"
        n = o["n"]
        counts_rows(R, row, n, {"commits": o["n_commit"], "wrong": o["n_wrong_commit"]},
                    {"commits": r_["n_commit"], "wrong": r_["n_wrong_commit"]},
                    {"commits": w["n_commit"], "wrong": w["n_wrong_commit"]})
        R.add(row, "ewpm", o["ewpm"], r_["ewpm"], w["ewpm"], per.get(r_["config_id"], {}).get("ewpm_hw"),
              "trial bootstrap")
    for k, ob in oe["baselines"].items():
        rb, nb = re_["baselines"][k], ne["baselines"][k]
        n = ob["old_frozen"]["n"]
        row = f"R3/{k}/always_commit"
        R.add(row, "wrong_commit_rate", ob["always_commit"]["wrong_commit"], rb["always_commit"]["wrong_commit"],
              nb["always_commit"]["wrong_commit"], wilson_hw(ob["always_commit"]["wrong_commit"], n), f"Wilson n={n}")
        R.add(row, "ewpm", ob["always_commit"]["ewpm"], rb["always_commit"]["ewpm"], nb["always_commit"]["ewpm"],
              per.get(f"always_commit/{k}", {}).get("ewpm_hw"), "trial bootstrap")
        o, r_, w = ob["old_frozen"], rb["old_frozen"], nb["old_frozen"]
        row = f"R3/{k}/old_frozen"
        counts_rows(R, row, n, {"commits": o["n_commit"], "wrong": o["n_wrong_commit"]},
                    {"commits": r_["n_commit"], "wrong": r_["n_wrong_commit"]},
                    {"commits": w["n_commit"], "wrong": w["n_wrong_commit"]})
        okey = r_["config_id"] + ("" if k == list(oe["baselines"])[0] else "#2")
        R.add(row, "ewpm", o["ewpm"], r_["ewpm"], w["ewpm"], per.get(okey, {}).get("ewpm_hw"), "trial bootstrap")
    ctl = {k: [oc["conditions"][k]["n_commit"], rc["conditions"][k]["n_commit"], nc["conditions"][k]["n_commit"]]
           for k in oc["conditions"]}
    out["R3"] = {"fit_committed_ref_e8": fitinfo, "controls_commits_committed_ref_e8": ctl,
                 "cache_misses": {"ref": load(DER / "r3-e12.json")["cache_misses"],
                                  "e8": load(DER / "r3-e8.json")["cache_misses"]},
                 "eval_e8": {k: {f: v.get(f) for f in ("n_commit", "n_wrong_commit", "ewpm", "error_among_commits",
                                                       "wrong_commit_cp95")} for k, v in ne["conditions"].items()}}


def compare_r4(R: Rule, out: dict) -> None:
    for model in ("m4-13", "m4-12"):
        name = f"b2t25-t15__{model}__guard"
        p12, p8 = DER / f"r4-{model}-e12" / f"{name}.json", DER / f"r4-{model}-e8" / f"{name}.json"
        if not (p12.exists() and p8.exists()):
            out[f"R4/{model}"] = "not run"
            continue
        old = load(REPO / "benchmark/results/v0.2" / f"{name}.json")
        ref, new = load(p12), load(p8)
        row = f"R4/{model}"
        nu = old["n_trials"] if isinstance(old.get("n_trials"), int) else 103
        for m, v in old["metrics"].items():
            if m == "gaze_ewpm":
                continue
            ci = v.get("ci") or [None, None]
            hw, kind = None, "no CI"
            if ci[0] is not None and ci[1] is not None and ci[1] > ci[0]:
                hw, kind = (ci[1] - ci[0]) / 2, "committed card CI"
            elif m.endswith("rate") and v.get("value") is not None:
                hw, kind = wilson_hw(v["value"], nu), f"Wilson n={nu} (zero-width card CI)"
            R.add(row, m, v.get("value"), ref["metrics"][m].get("value"), new["metrics"][m].get("value"), hw, kind)
        so, sr, sn = old.get("safe_wpm") or {}, ref.get("safe_wpm") or {}, new.get("safe_wpm") or {}
        ci = so.get("ci") or [None, None]
        hw = (ci[1] - ci[0]) / 2 if ci[0] is not None and ci[1] is not None else None
        R.add(row, "safe_wpm", so.get("value"), sr.get("value"), sn.get("value"), hw, "committed card CI")
        out[row] = {"status": [old.get("status"), ref.get("status"), new.get("status")],
                    "safe_wpm_e8": {k: sn.get(k) for k in ("value", "ci", "status", "n_commits", "n_wrong_commits",
                                                           "no_bci_wpm")},
                    "safe_wpm_committed": {k: so.get(k) for k in ("value", "ci", "status", "n_commits",
                                                                  "n_wrong_commits", "no_bci_wpm")},
                    "stage_info_e8": load(DER / f"r4-{model}-e8.json")["info"],
                    "stage_info_ref": load(DER / f"r4-{model}-e12.json")["info"]}


def compare_r5(R: Rule, out: dict) -> None:
    p12, p8 = DER / "r5-e12.json", DER / "r5-e8.json"
    if not (p12.exists() and p8.exists()):
        out["R5"] = "not run"
        return
    old = load(EXP / "2026-11-16-p5-02-precision/results/results.json")["t15"]
    ref, new = load(p12)["t15"], load(p8)["t15"]
    n = old["n_held_out"]
    for m in ("held_out_top1_right", "held_out_can_commit"):
        po = old["base"][m] / n
        R.add("R5/base", m + "_rate", po, ref["base"][m] / n, new["base"][m] / n, wilson_hw(po, n), f"Wilson n={n}")
    for tp, o in old["targets"].items():
        r_, w = ref["targets"][tp], new["targets"][tp]
        row = f"R5/target_{tp}"
        counts_rows(R, row, n, {"commits": o["commits"], "wrong": o["wrong"]},
                    {"commits": r_["commits"], "wrong": r_["wrong"]}, {"commits": w["commits"], "wrong": w["wrong"]})
    out["R5"] = {"targets": {tp: {f: [old["targets"][tp][f], ref["targets"][tp][f], new["targets"][tp][f]]
                                  for f in ("commit_p", "feasible", "commits", "wrong", "precision", "controls_pass")}
                             for tp in old["targets"]},
                 "base_commit_p": [old["base"]["commit_p"], ref["base"]["commit_p"], new["base"]["commit_p"]],
                 "resampling_e8": new.get("resampling")}


def compare_r6(R: Rule, out: dict) -> None:
    for model in ("m4-13", "m4-12"):
        old = load(EXP / "2026-11-17-p3-08-b2t25-collector-replay/results" / f"{model}-summary.json")
        pref = DER / f"r6-{model}-e12.json"
        pref_r = DER / f"r6-{model}-e12-replay.json"
        p8 = DER / f"r6-{model}-e8-replay.json"
        if not (pref.exists() and p8.exists()):
            out[f"R6/{model}"] = "not run"
            continue
        chk = load(pref)["check_vs_committed_prep"]
        new = load(p8)["summary"]
        ref_s = load(pref_r)["summary"] if pref_r.exists() else None
        n = old["replay"]["trials"]
        oc = old["actions"].get("COMMIT", 0)
        nc = new["actions"].get("COMMIT", 0)
        rc = ref_s["actions"].get("COMMIT", 0) if ref_s else oc
        rw = ref_s["wrong_commits"] if ref_s else old["wrong_commits"]
        k0 = len(R.rows)
        counts_rows(R, f"R6/{model}", n, {"commits": oc, "wrong": old["wrong_commits"]}, {"commits": rc, "wrong": rw},
                    {"commits": nc, "wrong": new["wrong_commits"]})
        if model == "m4-12" and not out.get("_r6_m413_ref_ok", False):  # plan: m4-12 read only if the M4-13 ref replay passed
            for r in R.rows[k0:]:
                r["not_used"] = True
        if model == "m4-13":
            out["_r6_m413_ref_ok"] = bool(ref_s) and rc == oc and rw == old["wrong_commits"]                 and ref_s.get("actions") == old["actions"]
        out[f"R6/{model}"] = {"prep_check_ref": chk, "reference_replay": bool(ref_s),
                              "actions": [old["actions"], ref_s["actions"] if ref_s else None, new["actions"]],
                              "added_p95_ms": [old["latency_ms"].get("added", {}).get("p95"),
                                               ref_s["latency_ms"].get("added", {}).get("p95") if ref_s else None,
                                               new["latency_ms"].get("added", {}).get("p95")],
                              "producer_level_e8": new["conformance"].get("producer_level")}


def stage_compare() -> None:
    R = Rule()
    out: dict = {}
    for f in (compare_r1, compare_r2, compare_r3, compare_r4, compare_r5, compare_r6):
        try:
            f(R, out)
        except Exception as e:  # report, do not hide
            out[f.__name__] = f"error: {type(e).__name__}: {e}"
            log(f"compare {f.__name__}: {type(e).__name__}: {e}")
    summ = {p: R.summary(p) for p in ("R1", "R2", "R3", "R4", "R5", "R6")}
    allrows = R.summary("R")
    OUT.mkdir(exist_ok=True)
    dump({"plan": "experiments/2026-11-17-p14-21-edit8-rows/plan.md (commit 095150c)",
          "setting": {"reference": "lm 1.0 / edit 12 / bonus 3", "new": "lm 1.0 / edit 8 / bonus 3"},
          "summary": summ, "all": allrows, "details": out, "metrics": R.rows}, OUT / "p14-21.json")
    log("compare: " + json.dumps({k: (v["n_effects"], v["n_metrics"], v["all_reproduced"]) for k, v in summ.items()}))


# ---------------------------------------------------------------------------
# queue
# ---------------------------------------------------------------------------

QUEUE = [("r1", "m4-13", 12), ("r1", "m4-13", 8), ("r1", "m4-12", 12), ("r1", "m4-12", 8),
         ("r3", None, 12), ("r3", None, 8), ("r2", None, 12), ("r2", None, 8),
         ("r4", "m4-13", 12), ("r4", "m4-13", 8), ("r4", "m4-12", 12), ("r4", "m4-12", 8),
         ("r5", None, 12), ("r5", None, 8),
         ("r6", "m4-13", 12), ("r6", "m4-12", 12), ("r6", "m4-13", 8), ("r6", "m4-12", 8),
         ("r6r", "m4-13", 12), ("r6r", "m4-13", 8), ("r6r", "m4-12", 8)]


def done_marker(stage: str, model: str | None, edit: int) -> Path:
    return DER / "done" / f"{stage}-{model or 'all'}-e{edit}.done"


def stage_queue() -> None:
    (DER / "done").mkdir(exist_ok=True)
    (DER / "queue.pid").write_text(str(os.getpid()))
    for stage, model, edit in QUEUE:
        mk = done_marker(stage, model, edit)
        if mk.exists():
            continue
        if (DER / "stop").exists():
            log("queue: stop file found")
            return
        cmd = [PY, "-I", str(HERE / "run.py"), "--stage", stage, "--edit", str(edit)] + (["--model", model] if model else [])
        log(f"queue: start {' '.join(cmd[3:])}")
        t0 = time.time()
        with open(DER / "logs" / f"{stage}-{model or 'all'}-e{edit}.log", "a", encoding="utf-8") as lf:
            rc = subprocess.run(cmd, cwd=REPO, stdout=lf, stderr=subprocess.STDOUT).returncode
        log(f"queue: {stage} {model} e{edit} exit {rc} after {time.time() - t0:.0f} s")
        if rc == 0:
            mk.write_text("ok")
    subprocess.run([PY, "-I", str(HERE / "run.py"), "--stage", "compare"], cwd=REPO)
    (DER / "queue.DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
    log("queue: done")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--edit", type=int, default=8, choices=(8, 12))
    ap.add_argument("--model", default="m4-13", choices=("m4-13", "m4-12"))
    a = ap.parse_args()
    (DER / "logs").mkdir(exist_ok=True)
    if a.stage in ("queue", "compare"):
        {"queue": stage_queue, "compare": stage_compare}[a.stage]()
        return
    patch_edit(a.edit)
    log(f"stage {a.stage} model {a.model} edit {a.edit}: start")
    if a.stage == "r1":
        stage_r1(a.model, a.edit)
    elif a.stage == "r2":
        stage_r2(a.edit)
    elif a.stage == "r3":
        stage_r3(a.edit)
    elif a.stage == "r4":
        stage_r4(a.model, a.edit)
    elif a.stage == "r5":
        stage_r5(a.edit)
    elif a.stage in ("r6", "r6r"):
        stage_r6(a.model, a.edit, a.stage == "r6r")
    else:
        raise SystemExit(f"unknown stage {a.stage}")
    if a.stage != "r6r":  # the replay reads the prep n-best lists; it builds no decoder
        assert PATCH["changed"] >= 1, f"the word decoder was never built with the paper point: {PATCH}"
    log(f"stage {a.stage} model {a.model} edit {a.edit}: done; patch {PATCH}")


if __name__ == "__main__":
    main()
