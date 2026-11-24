r"""P14-48: ``willett-hw`` with the same-LM readout (P15-25 decoder F) and a no-signal gate (CPU only). Plan: plan.md.

Our own code (Apache-2.0). Stages (each one writes a checkpoint in the derived folder and skips work that is done):
  lp       ``load("willett-hw")`` (NumPy runtime) on the P15-08 val and test blocks: log-probs of the real,
           time-shuffled and zero input (the P14-41 generators), one npz per (split, kind). Check: equal to the
           P14-41 files (read only).
  gate     the P11-12 gate rule on the 66 non-LTT val positions of calibrate's order (real input only).
  readout  gated and ungated F on val (real) and test (real and the four null inputs); per-sentence JSONL.
  guard    ``fidetype.trust.calibrate`` with decode_fn = gate + F (8-best), the P14-41 call otherwise.
  decide   ``guard.decide`` on the 80 test sentences: real, time-shuffled, zero, frame-shuffled, uniform.
  score    R0-R2, N1, N2, V1-V8 of plan.md, safe WPM v0.1 -> ``results/results.json`` (no text).
  all      every stage, then the DONE file.

Safety: a watcher thread stops the process (exit 3) on the file ``STOP`` in the derived folder or a working set
above ``RSS_LIMIT_MB``. Text, truth and log-probs stay in ``C:\Users\zhang\bci-data\derived\p14-48``.

Run (repo root; the detached form is launch.py)::

    .venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- ^
        .venv\Scripts\python.exe -I experiments/2026-11-20-p14-48-willett-lm-readout/run.py all
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
RAW = DATA / "raw/willett-handwriting/extracted/handwritingBCIData/Datasets"
P15 = DATA / "derived/p15-08"  # read only (splits.json)
P1441 = DATA / "derived/p14-41"  # read only (log-probs for the check)
P1525 = DATA / "derived/p15-25"  # read only (F hyps of R-ball-s0, meta)
OWN = DATA / "derived/p14-48"
OUT = HERE / "results"
SALT = "fidetype-p15-08-2026-11-19"
ALPHA, DELTA, SEED = 0.05, 0.1, 0
KINDS = ("real", "timeshuf", "zero")
TEST_KINDS = ("real", "timeshuf", "zero", "frameshuf", "uniform")
NULL_KINDS = ("timeshuf", "zero", "frameshuf", "uniform")
RSS_LIMIT_MB = 5500.0
V6_LIMIT = 0.05
F_P1525 = 0.1734338747099768
R0_TOL = 0.005
N2_MIN_CER = 0.85


# --- logging, memory, stop -----------------------------------------------------------------------------

class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QPPPU", ctypes.c_size_t), ("QPPU", ctypes.c_size_t),
                ("QPNPPU", ctypes.c_size_t), ("QNPPU", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def mem_mb() -> tuple[float, float]:
    """(working set, peak working set) of this process in MB (Windows; (nan, nan) elsewhere)."""
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


def item_rng(split: str, i: int, kind: str) -> np.random.Generator:
    """The P14-41 generator per (split, sentence, control): the null inputs equal the P14-41 inputs."""
    h = hashlib.sha256(f"p14-41|{SEED}|{split}|{i}|{kind}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def val_block(si: int, blocks: list[int], test_b: int) -> int:
    rest = sorted(b for b in set(blocks) if b != test_b)
    return min(rest, key=lambda b: hashlib.sha256("|".join([SALT, "val", str(si), str(b)]).encode()).hexdigest())


def model():
    import fidetype.pretrained as ftp

    return ftp.load("willett-hw")


# --- lp ----------------------------------------------------------------------------------------------------

def stage_lp() -> None:
    from fidetype.pretrained import readers as R
    from fidetype.pretrained._xbody import VOCAB

    if (OWN / "items.json").exists() and all((OWN / f"lp_{s}_{k}.npz").exists() for s in ("val", "test") for k in KINDS):
        log("lp: checkpoint found, skipped")
        return
    t0 = time.time()
    vocab = set(VOCAB[1:])
    m = model()
    sessions = m.manifest.architecture["sessions"]
    meta: dict = {"val": [], "test": [], "test_blocks": {}, "val_blocks": {}}
    lps: dict = {(s, k): [] for s in ("val", "test") for k in KINDS}
    for si, sess in enumerate(sessions):
        items = [it for it in R.read_willett_session(RAW / sess) if it.truth and all(c in vocab for c in it.truth)]
        tb = R.willett_test_block(items)
        vb = val_block(si, [it.extra["block"] for it in items], tb)
        meta["test_blocks"][str(si)], meta["val_blocks"][str(si)] = tb, vb
        keep = {"test": [it for it in items if it.extra["block"] == tb], "val": [it for it in items if it.extra["block"] == vb]}
        del items
        for split, its in keep.items():
            for it in its:
                i = len(meta[split])
                x = np.asarray(it.x)
                lps[(split, "real")].append(m.log_probs(x, it.session).astype(np.float32))
                xs = x[item_rng(split, i, "timeshuf").permutation(len(x))]
                lps[(split, "timeshuf")].append(m.log_probs(xs, it.session).astype(np.float32))
                lps[(split, "zero")].append(m.log_probs(np.zeros_like(x), it.session).astype(np.float32))
                meta[split].append({"key": it.key, "session": it.session, "truth": it.truth, "T": int(len(x)),
                                    "block": int(it.extra["block"])})
        del keep
        gc.collect()
        log(f"lp: session {si + 1}/{len(sessions)} {sess}: {len(meta['val'])} val, {len(meta['test'])} test so far")
    ref = json.loads((P15 / "willett/splits.json").read_text(encoding="utf-8"))
    meta["split_equal_p15_08"] = (meta["test_blocks"] == {k: int(v) for k, v in ref["test_blocks"].items()}
                                  and meta["val_blocks"] == ref["val_blocks"])
    for (split, kind), arrs in lps.items():
        np.savez(OWN / f"lp_{split}_{kind}.npz", *arrs)
    save_json(meta, OWN / "items.json")
    # check against the P14-41 files (read only)
    diffs = {}
    for split in ("val", "test"):
        for kind in KINDS:
            p = P1441 / f"lp_{split}_{kind}.npz"
            if not p.exists():
                diffs[f"{split}_{kind}"] = None
                continue
            with np.load(p) as z:
                old = [np.asarray(z[f"arr_{i}"], np.float32) for i in range(len(z.files))]
            new = lps[(split, kind)]
            diffs[f"{split}_{kind}"] = (float(max(np.abs(a - b).max() for a, b in zip(old, new)))
                                        if len(old) == len(new) and all(a.shape == b.shape for a, b in zip(old, new))
                                        else "shape mismatch")
    log(f"lp: {len(meta['val'])} val, {len(meta['test'])} test; split equal to P15-08: {meta['split_equal_p15_08']}; "
        f"max abs diff vs P14-41 {diffs} ({time.time() - t0:.0f} s)")
    update_results("lp", {"n_val": len(meta["val"]), "n_test": len(meta["test"]),
                          "val_frames": int(sum(r["T"] for r in meta["val"])),
                          "test_frames": int(sum(r["T"] for r in meta["test"])),
                          "split_equal_p15_08": bool(meta["split_equal_p15_08"]), "max_abs_diff_vs_p14_41": diffs,
                          "seconds": round(time.time() - t0, 1), "peak_rss_mb": round(mem_mb()[1])})


def load_lps(split: str, kind: str) -> list[np.ndarray]:
    with np.load(OWN / f"lp_{split}_{kind}.npz") as z:
        return [np.asarray(z[f"arr_{i}"], np.float32) for i in range(len(z.files))]


def test_input(kind: str, i: int, lp_real: np.ndarray, cache: dict) -> np.ndarray:
    """The P14-41 test inputs (same generators)."""
    if kind in ("real", "timeshuf", "zero"):
        return cache[kind][i]
    if kind == "frameshuf":
        return lp_real[item_rng("test", i, "frameshuf").permutation(len(lp_real))]
    T, V = lp_real.shape
    z = np.full((T, V), -math.log(V)) + 0.05 * item_rng("test", i, "uniform").standard_normal((T, V))
    return z - np.log(np.exp(z).sum(1, keepdims=True))


# --- gate --------------------------------------------------------------------------------------------------

def fit_positions(n: int) -> list[int]:
    from fidetype.trust.dropin import _split

    n_fit, n_pol, _ = _split(n)
    return [int(i) for i in np.random.default_rng(SEED).permutation(n)[: n_fit + n_pol]]


def stage_gate() -> None:
    from fidetype.pretrained._xbody import BIN_S
    from fidetype.pretrained.lmreadout import NoSignalGate, gate_features

    if (OWN / "gate.json").exists():
        log("gate: checkpoint found, skipped")
        return
    real, ts = load_lps("val", "real"), load_lps("val", "timeshuf")
    pos = fit_positions(len(real))
    g = NoSignalGate.fit([real[i] for i in pos], BIN_S)
    fr = [gate_features(real[i], BIN_S) for i in pos]
    ft_ = [gate_features(ts[i], BIN_S) for i in pos]
    rec = {"gate": g.to_dict(), "n_fit": len(pos), "fit_positions_digest": hashlib.sha256(json.dumps(pos).encode()).hexdigest()[:16],
           "fit_real_gated": sum(not g.passes(real[i]) for i in pos),
           "check_timeshuf_fit_pass": sum(g.passes(ts[i]) for i in pos),
           "fit_real_n_keys_min_med_max": [min(f[0] for f in fr), float(np.median([f[0] for f in fr])), max(f[0] for f in fr)],
           "fit_real_kps_min_med_max": [min(f[1] for f in fr), float(np.median([f[1] for f in fr])), max(f[1] for f in fr)],
           "fit_timeshuf_n_keys_min_med_max": [min(f[0] for f in ft_), float(np.median([f[0] for f in ft_])), max(f[0] for f in ft_)],
           "fit_timeshuf_kps_min_med_max": [min(f[1] for f in ft_), float(np.median([f[1] for f in ft_])), max(f[1] for f in ft_)]}
    save_json(rec, OWN / "gate.json")
    update_results("gate", rec)
    log(f"gate: {rec}")


def readout(gate: bool = True):
    from fidetype.pretrained.lmreadout import NoSignalGate

    m = model()
    if not gate:
        return m.lm_readout(gate=False)
    g = NoSignalGate.from_dict(json.loads((OWN / "gate.json").read_text(encoding="utf-8"))["gate"])
    return m.lm_readout(gate=g)


# --- readout -----------------------------------------------------------------------------------------------

def stage_readout() -> None:
    from fidetype.pretrained._xbody import BIN_S
    from fidetype.pretrained.lmreadout import gate_features, greedy_tokens

    out = OWN / "readout.jsonl"
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                done.add((d["split"], d["kind"], d["i"]))
    t0 = time.time()
    rg = readout(gate=True)
    meta = json.loads((OWN / "items.json").read_text(encoding="utf-8"))
    jobs = [("test", k) for k in TEST_KINDS] + [("val", "real")]
    with open(out, "a", encoding="utf-8") as fh:
        for split, kind in jobs:
            cache = {k: load_lps(split, k) for k in KINDS}
            for i, r in enumerate(meta[split]):
                if (split, kind, i) in done:
                    continue
                x = np.asarray(test_input(kind, i, cache["real"][i], cache), np.float64)
                n, kps = gate_features(x, BIN_S)
                gated = rg.gated(x)
                t1 = time.time()
                raw = rg.text(x, use_gate=False)
                sec = time.time() - t1
                vocab = rg.vocab
                greedy = "".join(vocab[t] for t in greedy_tokens(x))
                fh.write(json.dumps({"split": split, "kind": kind, "i": i, "key": r["key"], "n_keys": n, "kps": kps,
                                     "gated": bool(gated), "text_raw": raw, "text": "" if gated else raw,
                                     "greedy": greedy, "truth": r["truth"], "seconds": round(sec, 3)},
                                    ensure_ascii=False) + "\n")
                fh.flush()
            log(f"readout: {split} {kind} done ({time.time() - t0:.0f} s)")
            del cache
            gc.collect()


# --- guard -------------------------------------------------------------------------------------------------

def vocab_obj():
    from fidetype.adapters.ctc_logits import vocab_from_list
    from fidetype.pretrained import _xbody

    m = model()
    return vocab_from_list(list(_xbody.VOCAB), blank=0, vocab_type="char", vocab_id=m.manifest.output["vocab_id"])


def stage_guard() -> None:
    import fidetype.trust as ft
    from fidetype.pretrained import _xbody, sha256_file

    if (OWN / "guard_record.json").exists():
        log("guard: checkpoint found, skipped")
        return
    t0 = time.time()
    meta = json.loads((OWN / "items.json").read_text(encoding="utf-8"))
    lp_val, nulls = load_lps("val", "real"), load_lps("val", "timeshuf")
    texts = [r["truth"] for r in meta["val"]]
    rg = readout(gate=True)
    rec: dict = {"alpha": ALPHA, "delta": DELTA, "n_cal": len(lp_val), "n_null": len(nulls), "cal": "val blocks",
                 "null": "time-shuffled input of the val sentences (decoder run on the shuffled bins)",
                 "decode": "gate + F (fidetype.pretrained.lmreadout, 8-best)", "gate": rg.gate.to_dict()}
    log(f"guard: calibrate on {len(lp_val)} val sentences, {len(nulls)} time-shuffled nulls, decode_fn = gate + F")
    try:
        g = ft.calibrate(lp_val, texts, alpha=ALPHA, delta=DELTA, input_kind="logits", vocab=vocab_obj(), blank=0,
                         input_scale="log_probs", frame_period=_xbody.BIN_S, decode_fn=rg.decode_fn(),
                         null_inputs=nulls, decoder_name="fidetype-willett-hw-lm-f", decoder_version="1",
                         modality="intracortical", name="p14-48-willett-hw-lm", seed=SEED, audit_text=False,
                         language="en")
    except ft.NullControlError as e:
        rec.update(status="refused", reason=str(e)[:2000], controls=[c.to_dict() for c in e.report],
                   seconds=round(time.time() - t0, 1), peak_rss_mb=round(mem_mb()[1]))
        log(f"guard: REFUSED ({time.time() - t0:.0f} s): {e}")
        save_json(rec, OWN / "guard_record.json")
        update_results("guard", rec)
        return
    gp = OWN / "willett-hw.lm.guard.json"
    g.save(gp)
    log(f"guard: {g.config_id} ({time.time() - t0:.0f} s)\n{g.sheet}")
    rec.update(status="guard", config_id=g.config_id, guard_sha256=sha256_file(gp), guard_size=gp.stat().st_size,
               sheet=g.sheet.to_dict(), seconds=round(time.time() - t0, 1), peak_rss_mb=round(mem_mb()[1]))
    save_json(rec, OWN / "guard_record.json")
    update_results("guard", rec)


def stage_decide() -> None:
    import fidetype.trust as ft

    rec = json.loads((OWN / "guard_record.json").read_text(encoding="utf-8"))
    if rec["status"] != "guard":
        log("decide: no guard (refused), skipped")
        return
    t0 = time.time()
    g = ft.load(OWN / "willett-hw.lm.guard.json", decode_fn=readout(gate=True).decode_fn())
    meta = json.loads((OWN / "items.json").read_text(encoding="utf-8"))
    out = OWN / "decisions.jsonl"
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                done.add((d["kind"], d["i"]))
    cache = {k: load_lps("test", k) for k in KINDS}
    n_new = 0
    with open(out, "a", encoding="utf-8") as fh:
        for kind in TEST_KINDS:
            for i, r in enumerate(meta["test"]):
                if (kind, i) in done:
                    continue
                x = test_input(kind, i, cache["real"][i], cache)
                d = g.decide(x)
                top = d.choices[0] if d.choices else ""
                fh.write(json.dumps({"kind": kind, "i": i, "key": r["key"], "action": d.action,
                                     "right": bool(d.action == "commit" and g.is_right(d, r["truth"])),
                                     "top1": top, "p_top1": float(d.p_top1), "guard_risk": float(d.guard_risk),
                                     "reason": d.reason, "truth": r["truth"]}, ensure_ascii=False) + "\n")
                fh.flush()
                n_new += 1
            log(f"decide: {kind} done ({time.time() - t0:.0f} s)")
    log(f"decide: {n_new} new decisions ({time.time() - t0:.0f} s)")
    update_results("decide_run", {"seconds": round(time.time() - t0, 1), "new_decisions": n_new,
                                  "peak_rss_mb": round(mem_mb()[1])})


# --- score -------------------------------------------------------------------------------------------------

def _cer(rows: list[dict], field: str) -> float:
    from fidetype.eval.metrics import edit_distance

    return sum(edit_distance(r["truth"], r[field]) for r in rows) / max(1, sum(len(r["truth"]) for r in rows))


def p1525_hyps(meta: dict) -> list[str] | None:
    """The P15-25 F hyps of R-ball-s0 in our test order (by session and row), or None."""
    try:
        rec = json.loads((P1525 / "dec/F/test/R-ball-s0.json").read_text(encoding="utf-8"))
        ix = json.loads((P1525 / "lp/R-ball-s0/test.json").read_text(encoding="utf-8"))
        m8 = json.loads((P15 / "willett/meta.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    by = {}
    for j, i in enumerate(ix["idx"]):
        e = m8[i]
        by[(e["session_name"], int(e["row"]))] = (rec["hyp_local"][j], e["text"])
    out = []
    for r in meta["test"]:
        sess, _, row = r["key"].split("|")
        hit = by.get((sess, int(row)))
        if hit is None or hit[1] != r["truth"]:
            return None
        out.append(hit[0])
    return out


def score_readout(meta: dict) -> dict:
    rows = [json.loads(x) for x in (OWN / "readout.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    by: dict = {}
    for r in rows:
        by.setdefault((r["split"], r["kind"]), {})[r["i"]] = r
    res: dict = {}
    for (split, kind), d in sorted(by.items()):
        rs = [d[i] for i in sorted(d)]
        n = len(rs)
        res[f"{split}_{kind}"] = {
            "n": n, "gated": sum(r["gated"] for r in rs), "emit_nonempty_gated": sum(bool(r["text"]) for r in rs),
            "emit_nonempty_raw": sum(bool(r["text_raw"]) for r in rs),
            "chars_gated": sum(len(r["text"]) for r in rs), "chars_raw": sum(len(r["text_raw"]) for r in rs),
            "chars_truth": sum(len(r["truth"]) for r in rs),
            "cer_gated": round(_cer(rs, "text"), 4), "cer_raw": round(_cer(rs, "text_raw"), 4),
            "cer_greedy": round(_cer(rs, "greedy"), 4),
            "exact_gated": sum(r["text"] == r["truth"] for r in rs),
            "n_keys_min_med_max": [min(r["n_keys"] for r in rs), float(np.median([r["n_keys"] for r in rs])),
                                   max(r["n_keys"] for r in rs)],
            "kps_min_med_max": [round(min(r["kps"] for r in rs), 3), round(float(np.median([r["kps"] for r in rs])), 3),
                                round(max(r["kps"] for r in rs), 3)],
            "decode_seconds_p50_p95": [round(float(np.percentile([r["seconds"] for r in rs], q)), 3) for q in (50, 95)]}
    tr = res["test_real"]
    hy = p1525_hyps(meta)
    real = [by[("test", "real")][i] for i in sorted(by[("test", "real")])]
    r0 = {"cer_raw": tr["cer_raw"], "p15_25": round(F_P1525, 4), "abs_diff": round(abs(tr["cer_raw"] - F_P1525), 4),
          "pass": abs(tr["cer_raw"] - F_P1525) <= R0_TOL,
          "same_text_as_p15_25": (sum(a["text_raw"] == b for a, b in zip(real, hy)) if hy else None)}
    lim = int(math.floor(0.05 * tr["n"] + 1e-9))
    n1 = {k: {"emit": res[f"test_{k}"]["emit_nonempty_gated"], "allowed": lim,
              "pass": res[f"test_{k}"]["emit_nonempty_gated"] <= lim} for k in ("uniform", "timeshuf", "zero")}
    n1["pass"] = all(v["pass"] for v in n1.values())
    fs = res["test_frameshuf"]
    n2 = {"cer_gated": fs["cer_gated"], "min": N2_MIN_CER, "pass": fs["cer_gated"] >= N2_MIN_CER,
          "emit_gated": fs["emit_nonempty_gated"], "gated": fs["gated"]}
    return {"by_input": res, "R0": r0, "R1_cer_gated": tr["cer_gated"], "R1_cer_greedy": tr["cer_greedy"],
            "R2_gated_real": tr["gated"], "H_cost_pass": tr["gated"] <= lim, "N1": n1, "N2": n2,
            "D1_controls_pass": bool(n1["pass"] and n2["pass"])}


def stage_score() -> None:
    from fidetype.benchmark.safe_wpm import controls_from_sheet, format_line, guarantee_from_sheet, safe_wpm
    from fidetype.eval.metrics import edit_distance
    from fidetype.utils.binomial import clopper_pearson

    meta = json.loads((OWN / "items.json").read_text(encoding="utf-8"))
    ro = score_readout(meta)
    update_results("readout", ro)
    log(f"score: readout R0 {ro['R0']}; R1 gated CER {ro['R1_cer_gated']}; gated real {ro['R2_gated_real']}; "
        f"N1 {ro['N1']}; N2 {ro['N2']}")
    rec = json.loads((OWN / "guard_record.json").read_text(encoding="utf-8"))
    res: dict = {"guard_status": rec["status"]}
    if rec["status"] != "guard":
        res["V1"] = "refused"
        res["controls"] = rec.get("controls")
        update_results("score", res)
        log(f"score: V1 refused; controls {rec.get('controls')}")
        return
    sheet = rec["sheet"]
    dec = [json.loads(x) for x in (OWN / "decisions.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    by = {k: sorted((d for d in dec if d["kind"] == k), key=lambda d: d["i"]) for k in TEST_KINDS}
    n = len(meta["test"])
    assert all(len(by[k]) == n for k in TEST_KINDS), {k: len(v) for k, v in by.items()}
    counts = {}
    for k in TEST_KINDS:
        c = sum(d["action"] == "commit" for d in by[k])
        w = sum(d["action"] == "commit" and not d["right"] for d in by[k])
        o = sum(d["action"] == "offer" for d in by[k])
        counts[k] = {"n": n, "commit": c, "wrong_commit": w, "offer": o,
                     "withhold": sum(d["action"] == "withhold" for d in by[k]), "commit_rate": round(c / n, 4),
                     "offer_rate": round(o / n, 4), "wrong_commit_rate": round(w / n, 4),
                     "wrong_commit_cp95": clopper_pearson(w, n)}
    real = by["real"]
    truths = [r["truth"] for r in meta["test"]]
    committed = [d["action"] == "commit" for d in real]
    correct = [d["right"] for d in real]
    durations = [r["T"] * 0.01 for r in meta["test"]]
    blk = safe_wpm(committed, correct, [len(t.split()) for t in truths], [len(t) for t in truths], durations,
                   guarantee=guarantee_from_sheet(sheet), timing="neural time = 10 ms bins of the sentence window "
                   "(go cue to sentence end + up to 1 s tail, P15-08 cut)", controls=controls_from_sheet(sheet),
                   B=2000, seed=SEED, metric_version="0.1")
    blk["ci_note"] = "no CI: one participant (T5)"
    offered = [(t, d) for t, d in zip(truths, real) if d["action"] == "offer"]
    ed = [edit_distance(t, d["top1"]) for t, d in offered]
    feasible = bool(sheet.get("feasible"))
    certified = feasible
    ctl = {c["name"]: c for c in sheet.get("controls", [])}
    cal_ok = all(c.get("passed") for c in sheet.get("controls", []))
    v6 = {k: counts[k]["commit_rate"] <= V6_LIMIT for k in ("timeshuf", "zero")}
    w_real = counts["real"]["wrong_commit"]
    cp = clopper_pearson(w_real, n)
    v8 = {k: {"offer_rate": counts[k]["offer_rate"], "real_offer_rate": counts["real"]["offer_rate"],
              "offer_null_passes": counts[k]["offer_rate"] <= 0.05} for k in NULL_KINDS}
    res.update({
        "V1": "certified" if certified else "guard returned, LTT not feasible (no certified commit threshold)",
        "V1_detail": {"feasible": feasible, "n_ltt": sheet.get("n_ltt"), "n_ltt_min": sheet.get("n_ltt_min"),
                      "commit_threshold": sheet.get("commit_threshold"), "lambda_hat": sheet.get("lambda_hat"),
                      "ltt_commits": sheet.get("ltt_commits"), "ltt_wrong_commits": sheet.get("ltt_wrong_commits"),
                      "warnings": sheet.get("warnings")},
        "V2": ("clear violation" if cp[0] is not None and cp[0] > ALPHA else
               "holds" if w_real / n <= ALPHA else "fails"),
        "V3": "non-vacuous" if (certified and counts["real"]["commit"] > 0 and (blk.get("value") or 0) > 0) else "vacuous",
        "V6": {"calibrate_controls": {k: {"n": c["n"], "n_commit": c["n_commit"], "allowed": c["allowed"],
                                          "passed": c["passed"]} for k, c in ctl.items()},
               "calibrate_controls_pass": cal_ok,
               "test_timeshuf_commit_rate": counts["timeshuf"]["commit_rate"],
               "test_zero_commit_rate": counts["zero"]["commit_rate"],
               "pass": bool(cal_ok and all(v6.values()))},
        "V7_offer_top1": {"offers": counts["real"]["offer"], "exact": sum(e == 0 for e in ed),
                          "cer": round(sum(ed) / max(1, sum(len(t) for t, _ in offered)), 4) if offered else None},
        "V8_offer_null": v8, "test": counts, "safe_wpm": blk})
    update_results("score", res)
    log(f"score: V1 {res['V1']}; V2 {res['V2']}; V3 {res['V3']}; V6 pass {res['V6']['pass']}; "
        f"counts {counts}; V8 {v8}; {format_line(blk)}")


def main(argv: list[str]) -> int:
    from fidetype.utils.power import keep_awake

    stages = {"lp": stage_lp, "gate": stage_gate, "readout": stage_readout, "guard": stage_guard,
              "decide": stage_decide, "score": stage_score}
    want = argv or ["all"]
    run_all = "all" in want
    order = list(stages) if run_all else want
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / "DONE").unlink(missing_ok=True)
    threading.Thread(target=watcher, daemon=True).start()
    with keep_awake(log):
        log(f"start {order} (pid {os.getpid()})")
        for s in order:
            stages[s]()
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
