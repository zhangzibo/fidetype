"""P15-25: re-score the E1a runs with the same character LM (CPU stages; main venv, NumPy only).

Stages (``all`` runs them in order; finished units are skipped):
  overlap   share of Willett test / val sentences that occur in the Tatoeba English export (LM contamination)
  lmonly    what the LM decoder F emits on all-blank and on uniform log-probs
  tune      Fv: (w, beta) grid on the val sentences of the 16 tuning runs (descriptive)
  test      G, B0, F, FL, Fv on the test log-probs of all 41 runs; F on the 12 time-shuffled C1 sets
  summary   C0, verdicts per decoder, L1, L2 -> results/summary.json

Needs the ``logits`` stage (``logits.py``, ROCm venv) first. Our own code (Apache-2.0). It imports the P11-07
decoder ``lmbeam.py`` (unchanged) and reads P15-08 / P11-11 files only.

    .venv/Scripts/python.exe -I experiments/2026-11-20-p15-25-e1-same-lm/run.py all [--smoke]
"""

from __future__ import annotations

import os
import sys

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import importlib.util  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

LMBEAM = REPO / "experiments" / "2026-11-20-p11-07-emg-beam-lm" / "lmbeam.py"
DECODERS = ("G", "B0", "F", "FL", "Fv")
SMOKE = "--smoke" in sys.argv
LP = C.OWN / ("smoke-lp" if SMOKE else "lp")
DEC = C.OWN / ("smoke-dec" if SMOKE else "dec")

_LB = None
_LM = None
_LEX = None
_META = None


def lb():
    global _LB
    if _LB is None:
        spec = importlib.util.spec_from_file_location("lmbeam_p1107", LMBEAM)
        m = importlib.util.module_from_spec(spec)
        sys.modules["lmbeam_p1107"] = m
        spec.loader.exec_module(m)
        _LB = m
    return _LB


def lm():
    global _LM
    if _LM is None:
        from fidetype.lm.ngram import CharNgramLM

        _LM = CharNgramLM.load(C.config()["lm"])
    return _LM


def lexicon() -> frozenset[str]:
    """P11-11 lexicon, normalised as the LM text and split (the P11-07 ``lex_norm`` rule)."""
    global _LEX
    if _LEX is None:
        from fidetype.streams.vocab import normalize_text

        ws = C.load_json(Path(C.config()["lexicon"]))["words"]  # type: ignore[index]
        _LEX = frozenset(p for w in ws for p in normalize_text(w).split())
    return _LEX


def meta() -> list[dict]:
    global _META
    if _META is None:
        _META = C.load_json(C.E1A_OUT / "willett" / "meta.json")  # type: ignore[assignment]
    return _META  # type: ignore[return-value]


def decode(x: np.ndarray, cfg: dict) -> list[int]:
    if cfg.get("greedy"):
        return C.greedy_tokens(x)
    L = lb()
    use_lm = cfg.get("w", 0) > 0
    d = L.LMBeam(C.VOCAB, 0, lm=lm() if use_lm else None, lm_weight=cfg.get("w", 0.0), bonus=cfg.get("beta", 0.0),
                 beam=int(cfg["B"]), prune_logp=float(C.config()["prune_logp"]),
                 lexicon=lexicon() if cfg.get("lam", 0) > 0 else None, lam=cfg.get("lam", 0.0))
    d.push(x)
    hs = d.nbest(1)
    return hs[0].tokens if hs else []


def load_split(run: str, split: str) -> tuple[np.ndarray, dict]:
    ix = C.load_json(LP / run / f"{split}.json")
    arr = np.load(LP / run / f"{split}.npy", mmap_mode="r")
    return arr, ix  # type: ignore[return-value]


def cfg_tag(cfg: dict) -> str:
    if cfg.get("greedy"):
        return "G"
    return f"w{cfg['w']}-b{cfg['beta']}-l{cfg['lam']}-B{cfg['B']}"


def unit_path(dec: str, split: str, run: str) -> Path:
    return DEC / dec / split / f"{run}.json"


def _job(args: tuple[str, str, str, dict]) -> dict:
    """Worker: decode one (decoder, split, run); per-sentence edits (and local hyp text)."""
    dec, split, run, cfg = args
    f = unit_path(dec, split, run)
    if f.exists():
        return C.load_json(f)  # type: ignore[return-value]
    if C.stop_requested():
        return {"stopped": True}
    t0 = time.time()
    arr, ix = load_split(run, split)
    off = ix["offsets"]
    m = meta()
    edits, refs, hyps = [], [], []
    for j, i in enumerate(ix["idx"]):
        x = np.asarray(arr[off[j]:off[j + 1]], np.float64)
        h = decode(x, cfg)
        r = C.encode(m[i]["text"])
        edits.append(C.levenshtein(r, h))
        refs.append(len(r))
        hyps.append("".join(C.VOCAB[t] for t in h))
    rec = {"decoder": dec, "split": split, "run": run, "cfg": cfg, "cfg_tag": cfg_tag(cfg),
           "cer": sum(edits) / max(1, sum(refs)), "edits": edits, "ref": refs, "hyp_len": sum(len(h) for h in hyps),
           "seconds": round(time.time() - t0, 2), "peak_mb": round(C.peak_mb(), 1),
           "hyp_local": hyps}  # text stays in derived/p15-25 (never committed)
    C.save_json(rec, f)
    return rec


def run_pool(jobs: list[tuple[str, str, str, dict]], label: str) -> list[dict]:
    todo = [j for j in jobs if not unit_path(j[0], j[1], j[2]).exists()]
    C.log(f"{label}: {len(jobs)} units, {len(todo)} to do")
    peak = 0.0
    if todo:
        import multiprocessing as mp

        n = min(int(C.config()["workers"]), len(todo))
        t0 = time.time()
        with mp.get_context("spawn").Pool(n) as pool:
            for k, rec in enumerate(pool.imap_unordered(_job, todo), 1):
                if rec.get("stopped"):
                    continue
                peak = max(peak, rec.get("peak_mb", 0.0))
                if k % 10 == 0 or k == len(todo):
                    C.log(f"{label}: {k}/{len(todo)} (last {rec['decoder']} {rec['split']} {rec['run']} "
                          f"cer {rec['cer']:.4f}, {rec['seconds']} s; worker peak {peak:.0f} MB; "
                          f"{time.time() - t0:.0f} s)")
    if C.stop_requested():
        C.log(f"{label}: STOP file seen; exit")
        raise SystemExit(3)
    return [C.load_json(unit_path(*j[:3])) for j in jobs]  # type: ignore[misc]


# --- stages -------------------------------------------------------------------------------------------------


def stage_overlap() -> dict:
    f = C.OWN / "overlap.json"
    if f.exists():
        return C.load_json(f)  # type: ignore[return-value]
    import bz2

    from fidetype.streams.vocab import normalize_text

    corpora = Path("C:/Users/zhang/bci-data")
    bl = importlib.util.spec_from_file_location("build_lms_p1525", REPO / "experiments" / "2026-11-08-lm-beam" /
                                                "build_lms.py")
    B = importlib.util.module_from_spec(bl)
    bl.loader.exec_module(B)
    path = B.CORPORA / "eng_sentences.tsv.bz2"
    tat: set[str] = set()
    with bz2.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                s = normalize_text(parts[2])
                if s:
                    tat.add(s)
    sp = C.load_json(C.E1A_OUT / "willett" / "splits.json")
    m = meta()
    rec: dict = {"tatoeba_sentences": len(tat), "source": str(path.relative_to(corpora)) if corpora in path.parents
                 else path.name}
    for split in ("test", "val", "pool"):
        idx = sp[split]  # type: ignore[index]
        txt = [normalize_text(m[i]["text"]) for i in idx]
        uniq = sorted(set(txt))
        rec[split] = {"sentences": len(txt), "in_tatoeba": sum(t in tat for t in txt),
                      "unique": len(uniq), "unique_in_tatoeba": sum(t in tat for t in uniq)}
    C.save_json(rec, f)
    C.log(f"overlap: {rec}")
    return rec


def stage_lmonly() -> dict:
    f = C.OWN / "lmonly.json"
    if f.exists():
        return C.load_json(f)  # type: ignore[return-value]
    cfg = C.config()["decoders"]["F"]
    T = 4100
    blank = np.full((T, 98), -1e9)
    blank[:, 0] = 0.0
    uni = np.full((T, 98), -np.log(98.0))
    rec = {}
    for name, x in (("all_blank", blank), ("uniform", uni)):
        h = decode(x, cfg)
        rec[name] = {"frames": T, "n_tokens": len(h), "text_local": "".join(C.VOCAB[t] for t in h)[:200]}
    C.save_json(rec, f)
    C.log(f"lmonly: all_blank {rec['all_blank']['n_tokens']} tokens, uniform {rec['uniform']['n_tokens']} tokens")
    return rec


def stage_tune() -> dict:
    f = C.OWN / ("smoke-tune.json" if SMOKE else "tune.json")
    if f.exists():
        return C.load_json(f)  # type: ignore[return-value]
    cfg = C.config()
    t = cfg["fv_tuning"]
    grid = [{"w": w, "beta": b, "lam": t["lam"], "B": t["B"]} for w in t["w"] for b in t["beta"]]
    runs = ["E-ball-s0"] if SMOKE else C.tune_runs(cfg)
    if SMOKE:
        grid = grid[:2]
    jobs = [(f"tune-{cfg_tag(g)}", "val", r, g) for g in grid for r in runs]
    recs = run_pool(jobs, "tune")
    rows = []
    for g in grid:
        rr = [x for x in recs if x["cfg_tag"] == cfg_tag(g)]
        e = sum(sum(x["edits"]) for x in rr)
        n = sum(sum(x["ref"]) for x in rr)
        rows.append({**g, "edits": e, "ref": n, "cer": e / max(1, n)})
    best = sorted(rows, key=lambda r: (r["cer"], r["w"], r["beta"]))[0]
    rec = {"grid": rows, "Fv": {k: best[k] for k in ("w", "beta", "lam", "B")}, "Fv_val_cer": best["cer"],
           "runs": runs}
    C.save_json(rec, f)
    C.log(f"tune: Fv {rec['Fv']} val CER {best['cer']:.4f}")
    return rec


def decoder_cfgs(tune: dict) -> dict[str, dict]:
    d = dict(C.config()["decoders"])
    d["Fv"] = tune["Fv"]
    return d


def stage_test(tune: dict) -> None:
    cfgs = decoder_cfgs(tune)
    runs = ["E-ball-s0"] if SMOKE else C.all_runs()
    jobs = [(dec, "test", r, cfgs[dec]) for r in runs for dec in DECODERS]
    c1 = ["E-ball-s0"] if SMOKE else C.c1_runs()
    jobs += [("F", "shuf", r, cfgs["F"]) for r in c1]
    # slow units first (FL / F on the weak runs) so the pool ends together
    run_pool(jobs, "test")


def stage_summary(tune: dict) -> dict:
    cfg = C.config()
    e1a = C.e1a_config()
    k = int(cfg["secondary_k"])
    runs = C.all_runs()
    e1a_res = {r: C.load_json(C.E1A_OUT / "runs" / r / "result.json") for r in runs}
    minutes = {r: float(e1a_res[r]["minutes"]) for r in runs}  # type: ignore[index]
    res = {dec: {r: C.load_json(unit_path(dec, "test", r)) for r in runs} for dec in DECODERS}
    shuf = {r: C.load_json(unit_path("F", "shuf", r))["cer"] for r in C.c1_runs()}  # type: ignore[index]
    out: dict = {"task": "P15-25", "lm_sha256": cfg["lm_sha256"], "decoders": decoder_cfgs(tune),
                 "primary": cfg["primary_decoder"], "secondary_k": k,
                 "data": {"licence": "Willett CC0-1.0; T/E/S runs and FL lexicon CC-BY-NC-SA-4.0 (research only)",
                          "research_only_parts": ["T", "E", "S", "FL"]}}
    # C0: greedy reproduction
    c0 = []
    for r in runs:
        mine = res["G"][r]["cer"]
        theirs = float(e1a_res[r]["test_cer_final"])  # type: ignore[index]
        same = int(np.sum(np.asarray(res["G"][r]["edits"]) == np.asarray(e1a_res[r]["test_edits_final"])))  # type: ignore[index]
        c0.append({"run": r, "ours": mine, "e1a": theirs, "abs_diff": abs(mine - theirs), "same_sentences": same})
    out["C0"] = {"max_abs_diff": max(x["abs_diff"] for x in c0), "pass": all(x["abs_diff"] <= cfg["c0_max_abs_diff"]
                                                                            for x in c0), "runs": c0}
    out["verdicts"] = {}
    for dec in DECODERS:
        out["verdicts"][dec] = C.verdict(res[dec], minutes, e1a, k, shuf=shuf if dec == "F" else None)
    # E1a C1 (greedy, from E1a) for the L2 table
    g_shuf = {r: float(e1a_res[r]["c1_shuffled_cer"]) for r in C.c1_runs() if "c1_shuffled_cer" in e1a_res[r]}  # type: ignore[index]
    out["verdicts"]["G"]["C1"] = C.verdict(res["G"], minutes, e1a, k, shuf=g_shuf)["C1"]
    # per-run table (CER only; no text)
    out["runs"] = {r: {dec: res[dec][r]["cer"] for dec in DECODERS} | {"F_shuf": shuf.get(r)} for r in runs}
    out["hyp_ref_ratio"] = {dec: {r: res[dec][r]["hyp_len"] / max(1, sum(res[dec][r]["ref"])) for r in runs}
                            for dec in DECODERS}
    # L1: F vs G on both E-ball runs (per run, paired bootstrap seed 0)
    rules = e1a["rules"]
    l1 = []
    for r in ("E-ball-s0", "E-ball-s1"):
        eg = np.asarray(res["G"][r]["edits"], float)
        ef = np.asarray(res["F"][r]["edits"], float)
        ref = np.asarray(res["F"][r]["ref"], float)
        bs = C.bootstrap(eg, ef, ref, int(rules["bootstrap_n"]), int(rules["bootstrap_seed"]), k)
        l1.append({"run": r, "cer_G": res["G"][r]["cer"], "cer_F": res["F"][r]["cer"], "delta": bs["delta"],
                   "ci95": [bs["lo"], bs["hi"]], "ci_bonf": [bs["lo_bonf"], bs["hi_bonf"]],
                   "win": bool(bs["delta"] > 0 and bs["lo"] > 0), "robust": bool(bs["delta"] > 0 and bs["lo_bonf"] > 0)})
    out["L1"] = {"runs": l1, "pass": all(x["win"] for x in l1), "robust": all(x["robust"] for x in l1)}
    # L2: verdict on G next to F
    keys = ("V1", "H1", "H2", "H3", "H4", "H5", "H6", "roadmap_rule", "C1", "C2")

    def st(v: dict, key: str) -> str:
        x = v.get(key)
        if x is None:
            return "-"
        if "status" in x:
            return x["status"]
        return "pass" if x.get("pass") else "fail"

    rows = [{"id": key, "G": st(out["verdicts"]["G"], key), "F": st(out["verdicts"]["F"], key)} for key in keys]
    hs = [r for r in rows if r["id"].startswith("H")]
    out["L2"] = {"rows": rows, "holds": all(r["G"] == r["F"] for r in hs),
                 "changed": [r["id"] for r in rows if r["G"] != r["F"]]}
    for extra in ("overlap.json", "lmonly.json"):
        if (C.OWN / extra).exists():
            d = C.load_json(C.OWN / extra)
            if extra == "lmonly.json":
                d = {kk: {"frames": vv["frames"], "n_tokens": vv["n_tokens"]} for kk, vv in d.items()}  # type: ignore[union-attr]
            out[extra.split(".")[0]] = d
    out["tune"] = {"grid": tune["grid"], "Fv": tune["Fv"], "Fv_val_cer": tune["Fv_val_cer"]}
    out["timing"] = {dec: round(sum(res[dec][r]["seconds"] for r in runs), 1) for dec in DECODERS}
    out["worker_peak_mb"] = max(res[dec][r]["peak_mb"] for dec in DECODERS for r in runs)
    C.save_json(out, C.OUT / "summary.json")
    C.log(f"summary: C0 {out['C0']['pass']} (max diff {out['C0']['max_abs_diff']:.4f}); "
          f"F: V1 {out['verdicts']['F']['V1']}, H1 {out['verdicts']['F']['H1']['status']}, "
          f"L1 {out['L1']['pass']}, L2 holds {out['L2']['holds']} changed {out['L2']['changed']}")
    return out


def main(argv: list[str]) -> int:
    stages = [a for a in argv if not a.startswith("--")] or ["all"]
    if stages == ["all"]:
        stages = ["overlap", "lmonly", "tune", "test", "summary"]
    if not SMOKE and not (LP / "DONE.json").exists():
        C.log("run.py: lp/DONE.json missing (run logits.py first)")
        return 2
    C.keep_awake(True)
    t0 = time.time()
    try:
        tune = None
        for s in stages:
            C.log(f"start {s}" + (" (smoke)" if SMOKE else ""))
            if s == "overlap":
                stage_overlap()
            elif s == "lmonly":
                stage_lmonly()
            elif s == "tune":
                tune = stage_tune()
            elif s == "test":
                stage_test(tune or stage_tune())
            elif s == "summary" and not SMOKE:
                stage_summary(tune or stage_tune())
            C.log(f"end {s} (main peak {C.peak_mb():.0f} MB)")
    finally:
        C.keep_awake(False)
    if not SMOKE and stages[-1] == "summary":
        (C.OWN / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
        C.log(f"ALL DONE ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
