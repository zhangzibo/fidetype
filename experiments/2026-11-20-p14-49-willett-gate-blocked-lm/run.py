r"""P14-49 + P14-50: a no-signal gate for time-shuffled input, on the Willett-blocked LM (CPU only). Plan: plan.md.

Our own code (Apache-2.0). Stages (each one writes a checkpoint in the derived folder and skips work that is done):
  check    the P14-48 log-probs (read only; SHA-256 logged), the split, and the manifest LM (the new LM file).
  lmval    val (106 sentences) x real, time-shuffled, zero, frame-shuffled, uniform: posterior features and the
           ungated LM top-1 (new LM). Val only.
  select   candidates C0-C5 on the 66 non-LTT val positions: 2-fold inner split, selection rule, re-fit -> gate.json.
  readout  test (80) x the five inputs: features, ungated LM text, chosen-gate and P14-48-count-gate decisions.
  guard    ``fidetype.trust.calibrate`` with decode_fn = chosen gate + F (new LM, 8-best).
  decide   ``guard.decide`` on the 80 test sentences x five inputs.
  score    R0, R1, H-cost, N1', N2, V1-V8, safe WPM v0.1 -> ``results/results.json`` (no text).
  all      every stage, then the DONE file.
  guard_count (only if the plan's last packaging case happens): the guard with the count gate.

Safety: a watcher thread stops the process (exit 3) on the file ``STOP`` in the derived folder or a working set
above ``RSS_LIMIT_MB``. Text, truth and features stay in ``C:\Users\zhang\bci-data\derived\p14-49``.

Run (repo root; the detached form is launch.py)::

    .venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- ^
        .venv\Scripts\python.exe -I experiments/2026-11-20-p14-49-willett-gate-blocked-lm/run.py all
"""

from __future__ import annotations

import ctypes
import gc
import hashlib
import json
import math
import os
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

os.environ.setdefault("FIDETYPE_PRETRAINED_DIR", r"C:\Users\zhang\bci-data\pretrained")
os.environ["HIP_VISIBLE_DEVICES"] = "-1"  # CPU only
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DATA = Path(r"C:\Users\zhang\bci-data")
P15 = DATA / "derived/p15-08"  # read only (splits.json, meta.json)
P1448 = DATA / "derived/p14-48"  # read only (log-probs, items.json, gate.json)
P1538 = DATA / "derived/p15-38"  # read only (F hyps of R-ball-s0 with the new LM)
P1525 = DATA / "derived/p15-25"  # read only (lp index of R-ball-s0)
OWN = DATA / "derived/p14-49"
OUT = HERE / "results"
ALPHA, DELTA, SEED = 0.05, 0.1, 0
KINDS = ("real", "timeshuf", "zero")
ALL_KINDS = ("real", "timeshuf", "zero", "frameshuf", "uniform")
NULL_KINDS = ("timeshuf", "zero", "frameshuf", "uniform")
CANDS = ("C0", "C1", "C2", "C3", "C4", "C5")
CAND_FEATURE = {"C1": "nb_share", "C2": "peak", "C3": "neg_entropy", "C4": "lm_ratio", "C5": "logit"}
LM_FILE = "eng_tatoeba_6gram_mkn_noE2Q_noWillett.npz"
LM_SHA = "d7f6e829b827d1f7d09f5927eb51ec33fd79df29201d7e722a0878a503059261"
RSS_LIMIT_MB = 5500.0
V6_LIMIT = 0.05
F_P1538 = 0.17430394431554525
R0_TOL = 0.005
N2_MIN_CER = 0.85
ELIG_MAX = 3  # floor(0.05 x 66)


# --- logging, memory, stop -----------------------------------------------------------------------------

class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QPPPU", ctypes.c_size_t), ("QPPU", ctypes.c_size_t),
                ("QPNPPU", ctypes.c_size_t), ("QNPPU", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def mem_mb() -> tuple[float, float]:
    if os.name != "nt":
        return math.nan, math.nan
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    c = _PMC()
    c.cb = ctypes.sizeof(_PMC)
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 2**20, c.PeakWorkingSetSize / 2**20


def log(msg: str) -> None:
    w, p = mem_mb()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] (rss {w:.0f} MB, peak {p:.0f} MB) {msg}"
    print(line, flush=True)
    OUT.mkdir(exist_ok=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def watcher() -> None:
    last = time.time()
    while True:
        time.sleep(2.0)
        w, _ = mem_mb()
        if (OWN / "STOP").exists():
            log("STOP file found: exit 3")
            os._exit(3)
        if w > RSS_LIMIT_MB:
            log(f"working set {w:.0f} MB > limit {RSS_LIMIT_MB:.0f} MB: exit 3 (not restarted; see plan.md)")
            os._exit(3)
        if time.time() - last > 600:
            log("heartbeat")
            last = time.time()


def save_json(obj, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def update_results(key: str, val) -> None:
    p = OUT / "results.json"
    r = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    r[key] = val
    save_json(r, p)


def sha256_path(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def item_rng(split: str, i: int, kind: str) -> np.random.Generator:
    """The P14-41 generator per (split, sentence, control)."""
    h = hashlib.sha256(f"p14-41|{SEED}|{split}|{i}|{kind}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


_MODEL = None


def model():
    global _MODEL
    if _MODEL is None:
        import fidetype.pretrained as ftp

        _MODEL = ftp.load("willett-hw")
    return _MODEL


def load_lps(split: str, kind: str) -> list[np.ndarray]:
    with np.load(P1448 / f"lp_{split}_{kind}.npz") as z:
        return [np.asarray(z[f"arr_{i}"], np.float32) for i in range(len(z.files))]


def make_input(split: str, kind: str, i: int, cache: dict) -> np.ndarray:
    """The P14-41 / P14-48 inputs (same generators); val null inputs use split "val"."""
    if kind in KINDS:
        return np.asarray(cache[kind][i], np.float64)
    lp_real = np.asarray(cache["real"][i], np.float64)
    if kind == "frameshuf":
        return lp_real[item_rng(split, i, "frameshuf").permutation(len(lp_real))]
    T, V = lp_real.shape
    z = np.full((T, V), -math.log(V)) + 0.05 * item_rng(split, i, "uniform").standard_normal((T, V))
    return z - np.log(np.exp(z).sum(1, keepdims=True))


def meta() -> dict:
    return json.loads((P1448 / "items.json").read_text(encoding="utf-8"))


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


# --- check -------------------------------------------------------------------------------------------------

def stage_check() -> None:
    if (OWN / "check.json").exists():
        log("check: checkpoint found, skipped")
        return
    mt = meta()
    ref = json.loads((P15 / "willett/splits.json").read_text(encoding="utf-8"))
    split_ok = (mt["test_blocks"] == {k: int(v) for k, v in ref["test_blocks"].items()}
                and mt["val_blocks"] == ref["val_blocks"])
    shas = {f"lp_{s}_{k}": sha256_path(P1448 / f"lp_{s}_{k}.npz") for s in ("val", "test") for k in KINDS}
    m = model()
    cfg = m.manifest.raw["readouts"]["lm"]
    row = next(f for f in m.manifest.files if f.name == cfg["lm_file"])
    r = m.lm_readout(gate=False)
    lm_path = DATA / "pretrained/text" / LM_FILE
    rec = {"split_equal_p15_08": bool(split_ok), "n_val": len(mt["val"]), "n_test": len(mt["test"]),
           "p14_48_lp_sha256": shas, "manifest_lm_file": cfg["lm_file"], "manifest_lm_sha256": row.sha256,
           "lm_file_sha256": sha256_path(lm_path), "lm_file_size": lm_path.stat().st_size,
           "lm_file_readonly": not os.access(lm_path, os.W_OK), "lm_order": int(r.lm.order),
           "settings": r.settings}
    assert rec["manifest_lm_file"] == LM_FILE and rec["manifest_lm_sha256"] == LM_SHA == rec["lm_file_sha256"], rec
    assert split_ok
    save_json(rec, OWN / "check.json")
    update_results("check", rec)
    log(f"check: {rec}")


# --- features + ungated LM text ------------------------------------------------------------------------------

def run_split(split: str, out: Path, extra=None) -> None:
    from fidetype.pretrained._xbody import BIN_S
    from fidetype.pretrained.lmreadout import greedy_tokens, posterior_features

    done = {(d["kind"], d["i"]) for d in read_jsonl(out)}
    mt = meta()
    raw = model().lm_readout(gate=False)
    t0 = time.time()
    cache = {k: load_lps(split, k) for k in KINDS}
    with open(out, "a", encoding="utf-8") as fh:
        for kind in ALL_KINDS:
            for i, r in enumerate(mt[split]):
                if (kind, i) in done:
                    continue
                x = make_input(split, kind, i, cache)
                f = posterior_features(x, BIN_S)
                t1 = time.time()
                hs = raw.hyps(x, 1, use_gate=False)
                sec = time.time() - t1
                toks = hs[0].tokens if hs else []
                rec = {"split": split, "kind": kind, "i": i, "key": r["key"], "T": int(len(x)), **f,
                       "lm_tokens": len(toks), "text_raw": raw.tokens_text(toks),
                       "greedy": raw.tokens_text(greedy_tokens(x)), "truth": r["truth"], "seconds": round(sec, 3)}
                if extra is not None:
                    rec.update(extra(x, len(toks)))
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
            log(f"{split}: {kind} done ({time.time() - t0:.0f} s)")
    del cache
    gc.collect()


def stage_lmval() -> None:
    run_split("val", OWN / "val_raw.jsonl")


# --- select ------------------------------------------------------------------------------------------------

def fit_positions(n: int) -> list[int]:
    from fidetype.trust.dropin import _split

    n_fit, n_pol, _ = _split(n)
    return [int(i) for i in np.random.default_rng(SEED).permutation(n)[: n_fit + n_pol]]


def fit_cand(c: str, pos: list[int], cache: dict, rows: dict):
    from fidetype.pretrained._xbody import BIN_S
    from fidetype.pretrained.lmreadout import NoSignalGate, ScoreGate

    real = [cache["real"][i] for i in pos]
    if c == "C0":
        return NoSignalGate.fit(real, BIN_S)
    f = CAND_FEATURE[c]
    null = [cache["timeshuf"][i] for i in pos] if f == "logit" else ()
    toks = [rows[("real", i)]["lm_tokens"] for i in pos] if f == "lm_ratio" else None
    return ScoreGate.fit(f, real, BIN_S, null=null, real_lm_tokens=toks)


def gate_pass(g, x: np.ndarray, lm_tokens: int) -> bool:
    if getattr(g, "needs_lm", False):
        return bool(g.passes(x, lm_tokens=lm_tokens))
    return bool(g.passes(x))


def stage_select() -> None:
    if (OWN / "gate.json").exists():
        log("select: checkpoint found, skipped")
        return
    t0 = time.time()
    rows = {(d["kind"], d["i"]): d for d in read_jsonl(OWN / "val_raw.jsonl")}
    n = len(meta()["val"])
    assert len(rows) == n * len(ALL_KINDS), len(rows)
    cache0 = {k: load_lps("val", k) for k in KINDS}
    S = fit_positions(n)
    A, B = S[:33], S[33:]
    # all val inputs of S (the nulls are rebuilt with the same generators)
    X = {(k, i): make_input("val", k, i, cache0) for k in ALL_KINDS for i in S}
    cache = {"real": {i: X[("real", i)] for i in S}, "timeshuf": {i: X[("timeshuf", i)] for i in S}}
    table = {}
    for c in CANDS:
        cnt = {k: 0 for k in ALL_KINDS}
        folds = []
        for fit, ev in ((A, B), (B, A)):
            g = fit_cand(c, fit, cache, rows)
            fc = {k: sum(gate_pass(g, X[(k, i)], rows[(k, i)]["lm_tokens"]) for i in ev) for k in ALL_KINDS}
            for k in ALL_KINDS:
                cnt[k] += fc[k]
            folds.append({"gate": g.to_dict(), "pass_counts": fc})
        G = len(S) - cnt["real"]
        rec = {"G_real_gated": G, "E_ts": cnt["timeshuf"], "E_zero": cnt["zero"], "E_uni": cnt["uniform"],
               "E_frameshuf_report": cnt["frameshuf"], "n_eval": len(S), "folds": folds}
        rec["eligible"] = bool(G <= ELIG_MAX and cnt["zero"] <= ELIG_MAX and cnt["uniform"] <= ELIG_MAX)
        table[c] = rec
        log(f"select: {c}: G {G}, E_ts {cnt['timeshuf']}, E_zero {cnt['zero']}, E_uni {cnt['uniform']}, "
            f"frameshuf {cnt['frameshuf']}, eligible {rec['eligible']}")
    elig = [c for c in CANDS if table[c]["eligible"]]
    if elig:
        chosen = min(elig, key=lambda c: (table[c]["E_ts"], table[c]["G_real_gated"], CANDS.index(c)))
        rule = "eligible, smallest E_ts, then G, then order"
    else:
        chosen = min(CANDS, key=lambda c: (table[c]["E_ts"] + table[c]["G_real_gated"], table[c]["G_real_gated"],
                                           CANDS.index(c)))
        rule = "no candidate eligible: smallest E_ts + G, then G, then order"
    g = fit_cand(chosen, S, cache, rows)
    chk = {k: sum(gate_pass(g, X[(k, i)], rows[(k, i)]["lm_tokens"]) for i in S) for k in ALL_KINDS}
    # P14-48 count gate (reference; its values from derived/p14-48/gate.json)
    from fidetype.pretrained.lmreadout import NoSignalGate

    ref = NoSignalGate.from_dict(json.loads((P1448 / "gate.json").read_text(encoding="utf-8"))["gate"])
    out = {"chosen": chosen, "rule": rule, "eligible": elig, "gate": g.to_dict(), "gate_p14_48": ref.to_dict(),
           "n_S": len(S), "S_digest": hashlib.sha256(json.dumps(S).encode()).hexdigest()[:16],
           "A_digest": hashlib.sha256(json.dumps(A).encode()).hexdigest()[:16],
           "refit_check_pass_counts_on_S": chk, "refit_check_real_gated_on_S": len(S) - chk["real"],
           "table": table, "seconds": round(time.time() - t0, 1)}
    # descriptive feature summaries on S (val only)
    from fidetype.pretrained.lmreadout import SCORE_FEATURES  # noqa: F401

    summ = {}
    for k in ALL_KINDS:
        summ[k] = {f: [round(float(np.percentile([rows[(k, i)][f] for i in S], q)), 4) for q in (0, 5, 50, 95, 100)]
                   for f in ("n_keys", "kps", "nb_share", "peak", "neg_entropy")}
        summ[k]["lm_ratio"] = [round(float(np.percentile([rows[(k, i)]["lm_tokens"] / max(1, rows[(k, i)]["n_keys"])
                                                          for i in S], q)), 4) for q in (0, 5, 50, 95, 100)]
    out["feature_percentiles_0_5_50_95_100_on_S"] = summ
    save_json(out, OWN / "gate.json")
    update_results("select", out)
    log(f"select: chosen {chosen} ({rule}); gate {g.to_dict()}; refit check on S {chk}")


def chosen_gate():
    from fidetype.pretrained.lmreadout import gate_from_dict

    return gate_from_dict(json.loads((OWN / "gate.json").read_text(encoding="utf-8"))["gate"])


def count_gate():
    from fidetype.pretrained.lmreadout import NoSignalGate

    return NoSignalGate.from_dict(json.loads((P1448 / "gate.json").read_text(encoding="utf-8"))["gate"])


# --- readout (test) ----------------------------------------------------------------------------------------

def stage_readout() -> None:
    g, c0 = chosen_gate(), count_gate()

    def extra(x, lm_tokens):
        return {"passes": gate_pass(g, x, lm_tokens), "passes_count_gate": gate_pass(c0, x, lm_tokens)}

    run_split("test", OWN / "test_raw.jsonl", extra)
    # the packaged path gives the same decision and text (first 10 real and time-shuffled test inputs)
    rg = model().lm_readout(gate=g)
    rows = {(d["kind"], d["i"]): d for d in read_jsonl(OWN / "test_raw.jsonl")}
    cache = {k: load_lps("test", k) for k in KINDS}
    same = {}
    for kind in ("real", "timeshuf"):
        same[kind] = sum((rg.text(make_input("test", kind, i, cache)) ==
                          (rows[(kind, i)]["text_raw"] if rows[(kind, i)]["passes"] else "")) for i in range(10))
    update_results("readout_path_check_10", same)
    log(f"readout: packaged path equal on first 10: {same}")


# --- guard -------------------------------------------------------------------------------------------------

def vocab_obj():
    from fidetype.adapters.ctc_logits import vocab_from_list
    from fidetype.pretrained import _xbody

    return vocab_from_list(list(_xbody.VOCAB), blank=0, vocab_type="char",
                           vocab_id=model().manifest.output["vocab_id"])


def _guard(gate, tag: str) -> None:
    import fidetype.trust as ft
    from fidetype.pretrained import _xbody, sha256_file

    recp = OWN / f"guard_record{tag}.json"
    if recp.exists():
        log(f"guard{tag}: checkpoint found, skipped")
        return
    t0 = time.time()
    mt = meta()
    lp_val, nulls = load_lps("val", "real"), load_lps("val", "timeshuf")
    texts = [r["truth"] for r in mt["val"]]
    rg = model().lm_readout(gate=gate)
    rec: dict = {"alpha": ALPHA, "delta": DELTA, "n_cal": len(lp_val), "n_null": len(nulls), "cal": "val blocks",
                 "null": "time-shuffled input of the val sentences", "lm_file": LM_FILE,
                 "decode": "gate + F (new LM, 8-best)", "gate": gate.to_dict()}
    log(f"guard{tag}: calibrate on {len(lp_val)} val sentences, {len(nulls)} nulls")
    try:
        g = ft.calibrate(lp_val, texts, alpha=ALPHA, delta=DELTA, input_kind="logits", vocab=vocab_obj(), blank=0,
                         input_scale="log_probs", frame_period=_xbody.BIN_S, decode_fn=rg.decode_fn(),
                         null_inputs=nulls, decoder_name="fidetype-willett-hw-lm-f", decoder_version="2",
                         modality="intracortical", name="p14-49-willett-hw-lm", seed=SEED, audit_text=False,
                         language="en")
    except ft.NullControlError as e:
        rec.update(status="refused", reason=str(e)[:2000], controls=[c.to_dict() for c in e.report],
                   seconds=round(time.time() - t0, 1))
        log(f"guard{tag}: REFUSED: {e}")
        save_json(rec, recp)
        update_results(f"guard{tag}", rec)
        return
    gp = OWN / f"willett-hw.lm2{tag}.guard.json"
    g.save(gp)
    log(f"guard{tag}: {g.config_id} ({time.time() - t0:.0f} s)\n{g.sheet}")
    rec.update(status="guard", config_id=g.config_id, guard_file=gp.name, guard_sha256=sha256_file(gp),
               guard_size=gp.stat().st_size, sheet=g.sheet.to_dict(), seconds=round(time.time() - t0, 1),
               peak_rss_mb=round(mem_mb()[1]))
    save_json(rec, recp)
    update_results(f"guard{tag}", rec)


def stage_guard() -> None:
    _guard(chosen_gate(), "")


def stage_guard_count() -> None:
    _guard(count_gate(), "_count")


def stage_decide(tag: str = "") -> None:
    import fidetype.trust as ft

    rec = json.loads((OWN / f"guard_record{tag}.json").read_text(encoding="utf-8"))
    if rec["status"] != "guard":
        log("decide: no guard (refused), skipped")
        return
    t0 = time.time()
    gate = chosen_gate() if tag == "" else count_gate()
    g = ft.load(OWN / rec["guard_file"], decode_fn=model().lm_readout(gate=gate).decode_fn())
    mt = meta()
    out = OWN / f"decisions{tag}.jsonl"
    done = {(d["kind"], d["i"]) for d in read_jsonl(out)}
    cache = {k: load_lps("test", k) for k in KINDS}
    with open(out, "a", encoding="utf-8") as fh:
        for kind in ALL_KINDS:
            for i, r in enumerate(mt["test"]):
                if (kind, i) in done:
                    continue
                d = g.decide(make_input("test", kind, i, cache))
                top = d.choices[0] if d.choices else ""
                fh.write(json.dumps({"kind": kind, "i": i, "key": r["key"], "action": d.action,
                                     "right": bool(d.action == "commit" and g.is_right(d, r["truth"])),
                                     "top1": top, "p_top1": float(d.p_top1), "guard_risk": float(d.guard_risk),
                                     "reason": d.reason, "truth": r["truth"]}, ensure_ascii=False) + "\n")
                fh.flush()
            log(f"decide{tag}: {kind} done ({time.time() - t0:.0f} s)")
    update_results(f"decide_run{tag}", {"seconds": round(time.time() - t0, 1)})


# --- score -------------------------------------------------------------------------------------------------

def _cer(rows: list[dict], field: str) -> float:
    from fidetype.eval.metrics import edit_distance

    return sum(edit_distance(r["truth"], r[field]) for r in rows) / max(1, sum(len(r["truth"]) for r in rows))


def p1538_hyps(mt: dict) -> list[str] | None:
    try:
        rec = json.loads((P1538 / "dec/F/test/R-ball-s0.json").read_text(encoding="utf-8"))
        m8 = json.loads((P15 / "willett/meta.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    by = {}
    for j, i in enumerate(rec["idx"]):
        e = m8[i]
        by[(e["session_name"], int(e["row"]))] = (rec["hyp_local"][j], e["text"])
    out = []
    for r in mt["test"]:
        sess, _, row = r["key"].split("|")
        hit = by.get((sess, int(row)))
        if hit is None or hit[1] != r["truth"]:
            return None
        out.append(hit[0])
    return out


def score_readout(mt: dict) -> dict:
    rows = read_jsonl(OWN / "test_raw.jsonl")
    n = len(mt["test"])
    lim = int(math.floor(0.05 * n + 1e-9))
    res: dict = {}
    for gname, fld in (("chosen", "passes"), ("count_p14_48", "passes_count_gate")):
        by = {}
        for kind in ALL_KINDS:
            rs = sorted((dict(r, text=(r["text_raw"] if r[fld] else "")) for r in rows if r["kind"] == kind),
                        key=lambda r: r["i"])
            assert len(rs) == n, (kind, len(rs))
            by[kind] = {"n": n, "gated": sum(not r[fld] for r in rs),
                        "emit_nonempty_gated": sum(bool(r["text"]) for r in rs),
                        "emit_nonempty_raw": sum(bool(r["text_raw"]) for r in rs),
                        "chars_gated": sum(len(r["text"]) for r in rs), "chars_raw": sum(len(r["text_raw"]) for r in rs),
                        "cer_gated": round(_cer(rs, "text"), 4), "cer_raw": round(_cer(rs, "text_raw"), 4),
                        "cer_greedy": round(_cer(rs, "greedy"), 4), "exact_gated": sum(r["text"] == r["truth"] for r in rs)}
            if gname == "chosen":
                by[kind]["feature_min_med_max"] = {
                    f: [round(float(np.percentile([r[f] for r in rs], q)), 4) for q in (0, 50, 100)]
                    for f in ("n_keys", "kps", "nb_share", "peak", "neg_entropy")}
                by[kind]["decode_seconds_p50_p95"] = [round(float(np.percentile([r["seconds"] for r in rs], q)), 3)
                                                      for q in (50, 95)]
        n1 = {k: {"emit": by[k]["emit_nonempty_gated"], "allowed": lim, "pass": by[k]["emit_nonempty_gated"] <= lim}
              for k in ("uniform", "timeshuf", "zero")}
        n1["pass"] = all(v["pass"] for v in n1.values())
        n2 = {"cer_gated": by["frameshuf"]["cer_gated"], "min": N2_MIN_CER,
              "pass": by["frameshuf"]["cer_gated"] >= N2_MIN_CER, "emit_gated": by["frameshuf"]["emit_nonempty_gated"]}
        res[gname] = {"by_input": by, "N1": n1, "N2": n2, "real_gated": by["real"]["gated"],
                      "H_cost_pass": by["real"]["gated"] <= lim, "cer_gated": by["real"]["cer_gated"]}
    real = sorted((r for r in rows if r["kind"] == "real"), key=lambda r: r["i"])
    hy = p1538_hyps(mt)
    cr = res["chosen"]["by_input"]["real"]["cer_raw"]
    res["R0"] = {"cer_raw": cr, "p15_38": round(F_P1538, 4), "abs_diff": round(abs(cr - F_P1538), 4),
                 "pass": abs(cr - F_P1538) <= R0_TOL,
                 "same_text_as_p15_38": (sum(a["text_raw"] == b for a, b in zip(real, hy)) if hy else None)}
    ch = res["chosen"]
    res["P14_49_pass"] = bool(ch["N1"]["pass"] and ch["H_cost_pass"])
    rf = res["count_p14_48"]
    res["chosen_no_worse_than_count"] = bool(all(ch["N1"][k]["emit"] <= rf["N1"][k]["emit"]
                                                 for k in ("uniform", "timeshuf", "zero"))
                                             and ch["real_gated"] <= rf["real_gated"])
    return res


def score_guard(mt: dict, tag: str = "") -> dict:
    from fidetype.benchmark.safe_wpm import controls_from_sheet, format_line, guarantee_from_sheet, safe_wpm
    from fidetype.eval.metrics import edit_distance
    from fidetype.utils.binomial import clopper_pearson

    rec = json.loads((OWN / f"guard_record{tag}.json").read_text(encoding="utf-8"))
    res: dict = {"guard_status": rec["status"]}
    if rec["status"] != "guard":
        res["V1"] = "refused"
        res["controls"] = rec.get("controls")
        return res
    sheet = rec["sheet"]
    dec = read_jsonl(OWN / f"decisions{tag}.jsonl")
    by = {k: sorted((d for d in dec if d["kind"] == k), key=lambda d: d["i"]) for k in ALL_KINDS}
    n = len(mt["test"])
    assert all(len(by[k]) == n for k in ALL_KINDS), {k: len(v) for k, v in by.items()}
    counts = {}
    for k in ALL_KINDS:
        c = sum(d["action"] == "commit" for d in by[k])
        w = sum(d["action"] == "commit" and not d["right"] for d in by[k])
        o = sum(d["action"] == "offer" for d in by[k])
        counts[k] = {"n": n, "commit": c, "wrong_commit": w, "offer": o,
                     "withhold": sum(d["action"] == "withhold" for d in by[k]), "commit_rate": round(c / n, 4),
                     "offer_rate": round(o / n, 4), "wrong_commit_cp95": clopper_pearson(w, n)}
    real = by["real"]
    truths = [r["truth"] for r in mt["test"]]
    blk = safe_wpm([d["action"] == "commit" for d in real], [d["right"] for d in real],
                   [len(t.split()) for t in truths], [len(t) for t in truths], [r["T"] * 0.01 for r in mt["test"]],
                   guarantee=guarantee_from_sheet(sheet), timing="neural time = 10 ms bins of the sentence window "
                   "(go cue to sentence end + up to 1 s tail, P15-08 cut)", controls=controls_from_sheet(sheet),
                   B=2000, seed=SEED)
    blk["ci_note"] = "no CI: one participant (T5)"
    offered = [(t, d) for t, d in zip(truths, real) if d["action"] == "offer"]
    ed = [edit_distance(t, d["top1"]) for t, d in offered]
    feasible = bool(sheet.get("feasible"))
    ctl = {c["name"]: c for c in sheet.get("controls", [])}
    cal_ok = all(c.get("passed") for c in sheet.get("controls", []))
    v6 = {k: counts[k]["commit_rate"] <= V6_LIMIT for k in ("timeshuf", "zero")}
    w_real = counts["real"]["wrong_commit"]
    cp = clopper_pearson(w_real, n)
    res.update({
        "config_id": rec["config_id"], "guard_file": rec["guard_file"], "guard_sha256": rec["guard_sha256"],
        "guard_size": rec["guard_size"],
        "V1": "certified" if feasible else "guard returned, LTT not feasible (no certified commit threshold)",
        "V1_detail": {k: sheet.get(k) for k in ("feasible", "n_ltt", "n_ltt_min", "commit_threshold", "lambda_hat",
                                                 "ltt_commits", "ltt_wrong_commits", "warnings")},
        "V2": ("clear violation" if cp[0] is not None and cp[0] > ALPHA else
               "holds" if w_real / n <= ALPHA else "fails"),
        "V3": "non-vacuous" if (feasible and counts["real"]["commit"] > 0 and (blk.get("value") or 0) > 0) else "vacuous",
        "V6": {"calibrate_controls": {k: {"n": c["n"], "n_commit": c["n_commit"], "allowed": c["allowed"],
                                          "passed": c["passed"]} for k, c in ctl.items()},
               "calibrate_controls_pass": cal_ok, "test_timeshuf_commit_rate": counts["timeshuf"]["commit_rate"],
               "test_zero_commit_rate": counts["zero"]["commit_rate"], "pass": bool(cal_ok and all(v6.values()))},
        "V7_offer_top1": {"offers": counts["real"]["offer"], "exact": sum(e == 0 for e in ed),
                          "cer": round(sum(ed) / max(1, sum(len(t) for t, _ in offered)), 4) if offered else None},
        "V8_offer_null": {k: {"offer_rate": counts[k]["offer_rate"], "real_offer_rate": counts["real"]["offer_rate"],
                              "offer_null_passes": counts[k]["offer_rate"] <= 0.05} for k in NULL_KINDS},
        "test": counts, "safe_wpm": blk, "safe_wpm_line": format_line(blk)})
    return res


def stage_score() -> None:
    mt = meta()
    ro = score_readout(mt)
    vrows = read_jsonl(OWN / "val_raw.jsonl")
    g = chosen_gate()
    vreal = [r for r in vrows if r["kind"] == "real"]
    ro["val_real_cer_raw"] = round(_cer(vreal, "text_raw"), 4)
    ro["val_real_cer_greedy"] = round(_cer(vreal, "greedy"), 4)
    update_results("readout", ro)
    log(f"score: R0 {ro['R0']}; chosen {ro['chosen']['N1']} H {ro['chosen']['real_gated']} N2 {ro['chosen']['N2']}; "
        f"P14-49 pass {ro['P14_49_pass']}; count gate {ro['count_p14_48']['N1']} H {ro['count_p14_48']['real_gated']}")
    gr = score_guard(mt, "")
    update_results("score", gr)
    log(f"score: guard {gr.get('config_id')} V1 {gr['V1']}; V2 {gr.get('V2')}; V3 {gr.get('V3')}; "
        f"V6 {gr.get('V6', {}).get('pass')}; V8 {gr.get('V8_offer_null')}; {gr.get('safe_wpm_line')}")
    if (OWN / "guard_record_count.json").exists() and (OWN / "decisions_count.jsonl").exists():
        update_results("score_count", score_guard(mt, "_count"))
    del g


def main(argv: list[str]) -> int:
    from fidetype.utils.power import keep_awake

    stages = {"check": stage_check, "lmval": stage_lmval, "select": stage_select, "readout": stage_readout,
              "guard": stage_guard, "decide": stage_decide, "score": stage_score}
    extra = {"guard_count": stage_guard_count, "decide_count": lambda: stage_decide("_count")}
    want = argv or ["all"]
    run_all = "all" in want
    order = list(stages) if run_all else want
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / "DONE").unlink(missing_ok=True)
    threading.Thread(target=watcher, daemon=True).start()
    with keep_awake(log):
        log(f"start {order} (pid {os.getpid()})")
        for s in order:
            (stages.get(s) or extra[s])()
            gc.collect()
            log(f"stage {s} finished")
    peak = mem_mb()[1]
    update_results("peak_rss_mb_last_run", round(peak))
    log(f"end; peak RSS of this run {peak:.0f} MB")
    if run_all:
        (OWN / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
