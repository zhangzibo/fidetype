"""M1-C2: the RETUNED CTC prefix beam + Spanish char LM on the M1-C r4b streams.

Stages (each stage saves its output; a re-run skips finished work):

1. ``controls``: CPU only. Load the r4b ``best.pt`` and decode every val/test
   segment with its own MEG ("real_cpu"), the MEG of another segment
   ("shuffled", the same seed-0 derangement as ``infer.meg_control``), and
   zeros. Save the per-frame log-probs outside the repo
   (``DATA_DIR/logprobs_<split>.npz``). The "real" condition uses the GPU
   streams that ``infer.py`` wrote in M1-C (the official r4b streams).
2. ``grid``: lm_weight x insertion_bonus x (raw | frame-calibrated) on REAL
   VAL only. Pick the cell with the lowest val CER (mean over sentences).
3. ``eval``: greedy, beam without LM, beam + LM (RETUNED as is), beam + LM
   (val-tuned cell) for real / shuffled / zeros, val and test. Bootstrap
   95% CIs over sentences (10,000 resamples, as M1-C), paired gaps.

Run (repo root, CPU only; see results.md):

    C:\\venvs\\fidetype-rocm\\Scripts\\python.exe experiments/2026-11-08-m1c2-beam-lm/run.py

Other runs (added for M1-09): ``--run-name <run>`` reads
``runs/<run>/best.pt`` and ``streams/<run>/``; ``--out`` and ``--data-dir`` set
the output folders; ``--grid-w`` / ``--grid-b`` set the val grid;
``--no-calibrated`` drops the frame-calibrated grid half. The defaults
reproduce M1-C2. ``score`` also reports the mean over participants.
"""

from __future__ import annotations

import os

os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse
import itertools
import json
import math
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
RUN_DIR = Path("C:/Users/zhang/bci-data/runs/m1c-r4-small-aux0.5-pretrained")
STREAM_DIR = Path("C:/Users/zhang/bci-data/streams/m1c-r4-small-aux0.5-pretrained")
DATA_DIR = Path("C:/Users/zhang/bci-data/streams/m1c2-r4b-controls")
LM_PATH = "C:/Users/zhang/bci-data/lm/spa_tatoeba_6gram_mkn.npz"
SPLITS = ("val", "test")
KINDS = ("real", "shuffled", "zeros")
N_WORKERS = 3
N_BOOT = 10000
GRID_W = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
GRID_B = (0.0, 0.5, 1.0, 1.5, 2.0)
NO_CAL = False


def log(*a) -> None:
    msg = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(msg, flush=True)
    with open(OUT / "run_log.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def norm_spaces(t: str) -> str:
    return " ".join(t.split())


# ---------------------------------------------------------------------------
# Stage 1: control log-probs on CPU
# ---------------------------------------------------------------------------


def stage_controls() -> None:
    import torch

    torch.set_num_threads(3)
    from fidetype.decoders.dataset import MEGSegments
    from fidetype.decoders.infer import load_checkpoint

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dev = torch.device("cpu")
    model, ck = load_checkpoint(RUN_DIR / "best.pt", dev)
    cfg = ck["config"]
    pad_multiple = max(1, int(cfg["data"].get("pad_multiple", 1)))
    for split in SPLITS:
        path = DATA_DIR / f"logprobs_{split}.npz"
        if path.exists():
            log("controls: skip", split)
            continue
        t0 = time.time()
        ds = MEGSegments(cfg["data"]["root"], (split,), cfg["data"].get("subjects"), ck["subject_map"], None,
                         mmap_dir=cfg["data"].get("mmap_dir"), blocks=cfg["data"].get("blocks"))
        labels = [json.loads(x) for x in (STREAM_DIR / split / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
        n = len(ds)
        names = [f"{s.subject}_{s.session}_{s.block}_{s.trial_idx}.npz" for s in ds.segments]
        assert names == [r["file"] for r in labels], "segment order differs from the M1-C streams"
        # The same derangement as infer.meg_control (seed 0).
        perm = np.random.default_rng(0).permutation(n)
        perm = np.where(perm == np.arange(n), (np.arange(n) + 1) % n, perm)
        arrays: dict[str, np.ndarray] = {}
        with torch.no_grad():
            for i in range(n):
                item = ds[i]
                other = ds[int(perm[i])]["x"]
                T = item["x"].shape[1]
                sh = other[:, :T] if other.shape[1] >= T else torch.nn.functional.pad(other, (0, T - other.shape[1]))
                for kind, x in (("real_cpu", item["x"]), ("shuffled", sh), ("zeros", torch.zeros_like(item["x"]))):
                    T_pad = -(-T // pad_multiple) * pad_multiple
                    xx = torch.nn.functional.pad(x[None], (0, T_pad - T))
                    out = model(xx, torch.tensor([T]), torch.tensor([item["subject"]]))
                    m = int(out["out_lengths"][0])
                    arrays[f"{kind}__{names[i]}"] = out["logits"][0, :m].float().log_softmax(-1).numpy().astype(np.float32)
        np.savez(path, **arrays)
        log(f"controls: {split} n={n} in {time.time() - t0:.0f} s")


# ---------------------------------------------------------------------------
# Streams
# ---------------------------------------------------------------------------


def load_split(split: str) -> tuple[list[dict], dict[str, dict[str, np.ndarray]]]:
    """Labels and log-probs per kind: {kind: {file: (T, V) array}}."""
    from fidetype.streams.spec import NeuralTextStream

    labels = [json.loads(x) for x in (STREAM_DIR / split / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
    lp: dict[str, dict[str, np.ndarray]] = {"real": {}, "real_cpu": {}, "shuffled": {}, "zeros": {}}
    for r in labels:
        lp["real"][r["file"]] = NeuralTextStream.from_npz(STREAM_DIR / split / r["file"]).log_probs.astype(np.float32)
    with np.load(DATA_DIR / f"logprobs_{split}.npz") as z:
        for k in z.files:
            kind, name = k.split("__", 1)
            lp[kind][name] = z[k]
    return labels, lp


def make_stream(lp: np.ndarray):
    from fidetype.streams.spec import NeuralTextStream
    from fidetype.streams.vocab import BLANK_ID, VOCAB

    return NeuralTextStream(log_probs=lp, frame_times=np.arange(len(lp)) * 0.04, vocab=list(VOCAB),
                            blank_id=BLANK_ID, source="spanishbcbl-convctc", meta={})


# ---------------------------------------------------------------------------
# Beam worker
# ---------------------------------------------------------------------------

_LM = None


def _init_worker() -> None:
    global _LM
    from fidetype.lm import CharNgramLM

    _LM = CharNgramLM.load(LM_PATH)


def _decode(job: tuple) -> tuple:
    """job = (key, log_probs, temperature, use_lm, kwargs). Returns (key, top1, n-best texts)."""
    from fidetype.lm import ctc_prefix_beam_search

    key, lp, temp, use_lm, kw = job
    if temp != 1.0:
        z = lp.astype(np.float64) / temp
        lp = (z - np.logaddexp.reduce(z, axis=1, keepdims=True)).astype(np.float32)
    hyps = ctc_prefix_beam_search(make_stream(lp), _LM if use_lm else None, align=False, **kw)
    texts = [norm_spaces(h.text) for h in hyps]
    return key, (texts[0] if texts else ""), texts


def setting_kwargs(name: str, grid_choice: dict | None = None) -> tuple[float, bool, dict]:
    """(temperature, use_lm, beam kwargs) of a named decoder setting."""
    from fidetype.lm.beam import RETUNED

    base = dict(RETUNED)
    if name == "beam_nolm":
        return 1.0, False, {**base, "lm_weight": 0.0, "insertion_bonus": 0.0}
    if name == "beam_lm_retuned":
        return 1.0, True, base
    if name == "beam_lm_valtuned":
        g = grid_choice
        return float(g["temperature"]), True, {**base, "lm_weight": g["lm_weight"], "insertion_bonus": g["insertion_bonus"]}
    raise KeyError(name)


def run_jobs(pool: Pool, jobs: list[tuple], cache_path: Path) -> dict[str, tuple[str, list[str]]]:
    """Decode the jobs not in the cache (a jsonl), append them, return all."""
    done: dict[str, tuple[str, list[str]]] = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done[r["key"]] = (r["top1"], r["nbest"])
    todo = [j for j in jobs if j[0] not in done]
    if todo:
        with open(cache_path, "a", encoding="utf-8") as f:
            for key, top1, texts in pool.imap_unordered(_decode, todo, chunksize=4):
                f.write(json.dumps({"key": key, "top1": top1, "nbest": texts}) + "\n")
                f.flush()
                done[key] = (top1, texts)
    return done


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def bootstrap_mean_ci(d, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """Same as fidetype.decoders.infer.bootstrap_mean_ci (sentences resampled)."""
    d = np.asarray(d, dtype=np.float64)
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, len(d), size=(n_boot, len(d)))].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"mean": float(d.mean()), "ci95_lo": float(lo), "ci95_hi": float(hi), "n": int(len(d))}


def _mean_over(labels: list[dict], vals: list[float], key: str) -> float:
    """Mean of the group means; a row without ``key`` is its own group (its subject)."""
    g: dict[str, list[float]] = {}
    for r, v in zip(labels, vals):
        g.setdefault(str(r.get(key) or r["subject"]), []).append(v)
    return float(np.mean([np.mean(v) for v in g.values()]))


def score(labels: list[dict], tops: list[str], nbests: list[list[str]] | None = None) -> dict:
    from fidetype.eval.metrics import cer, edit_distance, wer

    tg = [r["target_text"] for r in labels]
    c = [cer(t, h) for t, h in zip(tg, tops)]
    subj: dict[str, list[float]] = {}
    for r, v in zip(labels, c):
        subj.setdefault(r["subject"], []).append(v)
    out = {
        "cer_target": bootstrap_mean_ci(c),
        "cer_typed": float(np.mean([cer(r["typed_text"], h) for r, h in zip(labels, tops)])),
        "wer_target": float(np.mean([wer(t, h) for t, h in zip(tg, tops)])),
        "cer_target_pooled": sum(edit_distance(t, h) for t, h in zip(tg, tops)) / sum(len(t) for t in tg),
        "cer_target_mean_over_subjects": float(np.mean([np.mean(v) for v in subj.values()])),
        "cer_target_mean_over_participants": _mean_over(labels, c, "participant"),
        "sentence_acc": float(np.mean([t == h for t, h in zip(tg, tops)])),
        "per_sentence_cer": c,
    }
    if nbests is not None:
        out["target_in_nbest"] = float(np.mean([t in nb for t, nb in zip(tg, nbests)]))
    return out


# ---------------------------------------------------------------------------
# Stage 2: val grid (real MEG only)
# ---------------------------------------------------------------------------


def stage_grid(pool: Pool) -> dict:
    from fidetype.trust.calibration import fit_frame_temperature

    labels, lp = load_split("val")
    scaler = fit_frame_temperature([make_stream(lp["real"][r["file"]]) for r in labels],
                                   [r["target_text"] for r in labels])
    T_cal = float(scaler.temperature)
    log(f"grid: frame temperature fitted on real val = {T_cal:.3f}")
    from fidetype.lm.beam import RETUNED

    cells = list(itertools.product((1.0,) if NO_CAL else (1.0, T_cal), GRID_W, GRID_B))
    jobs = []
    for T, w, b in cells:
        kw = {**dict(RETUNED), "lm_weight": w, "insertion_bonus": b}
        for r in labels:
            jobs.append((f"grid|T={T:.4f}|w={w}|b={b}|{r['file']}", lp["real"][r["file"]], T, True, kw))
    t0 = time.time()
    done = run_jobs(pool, jobs, DATA_DIR / "cache_grid.jsonl")
    rows = []
    for T, w, b in cells:
        tops = [done[f"grid|T={T:.4f}|w={w}|b={b}|{r['file']}"][0] for r in labels]
        s = score(labels, tops)
        rows.append({"temperature": T, "calibrated": T != 1.0, "lm_weight": w, "insertion_bonus": b,
                     "val_cer_target": s["cer_target"]["mean"], "val_wer_target": s["wer_target"]})
    best = min(rows, key=lambda r: (r["val_cer_target"], r["val_wer_target"]))
    res = {"frame_temperature_val": T_cal, "rows": rows, "best": best, "seconds": round(time.time() - t0, 1)}
    (OUT / "grid_val.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    log("grid: best on val", best)
    return res


# ---------------------------------------------------------------------------
# Stage 3: evaluation
# ---------------------------------------------------------------------------


def stage_eval(pool: Pool, grid: dict) -> dict:
    from fidetype.eval.metrics import ctc_greedy_decode

    settings = ["beam_nolm", "beam_lm_retuned", "beam_lm_valtuned"]
    res: dict = {"grid_choice": grid["best"], "frame_temperature_val": grid["frame_temperature_val"], "splits": {}}
    t0 = time.time()
    for split in SPLITS:
        labels, lp = load_split(split)
        jobs = []
        for kind in KINDS:
            for sname in settings:
                T, use_lm, kw = setting_kwargs(sname, grid["best"])
                for r in labels:
                    jobs.append((f"{split}|{kind}|{sname}|T={T:.4f}|w={kw['lm_weight']}|b={kw['insertion_bonus']}|{r['file']}",
                                 lp[kind][r["file"]], T, use_lm, kw))
        done = run_jobs(pool, jobs, DATA_DIR / "cache_eval.jsonl")
        sres: dict = {}
        for kind in KINDS + ("real_cpu",):
            kres = {"greedy": score(labels, [ctc_greedy_decode(make_stream(lp[kind][r["file"]])) for r in labels])}
            if kind != "real_cpu":
                for sname in settings:
                    T, use_lm, kw = setting_kwargs(sname, grid["best"])
                    keys = [f"{split}|{kind}|{sname}|T={T:.4f}|w={kw['lm_weight']}|b={kw['insertion_bonus']}|{r['file']}"
                            for r in labels]
                    kres[sname] = score(labels, [done[k][0] for k in keys], [done[k][1] for k in keys])
                    if kind == "real" and split == "test":
                        kres[sname]["examples"] = [{"subject": r["subject"], "target": r["target_text"], "top1": done[k][0]}
                                                   for r, k in list(zip(labels, keys))[:10]]
            sres[kind] = kres
        # Paired gaps (bootstrap over sentences).
        gaps: dict = {}
        for d in ["greedy"] + settings:
            real = np.array(sres["real"][d]["per_sentence_cer"])
            gaps[f"shuffled_minus_real/{d}"] = bootstrap_mean_ci(np.array(sres["shuffled"][d]["per_sentence_cer"]) - real)
            if d != "greedy":
                gaps[f"{d}_minus_greedy/real"] = bootstrap_mean_ci(real - np.array(sres["real"]["greedy"]["per_sentence_cer"]))
        res["splits"][split] = {"n": len(labels), "results": sres, "gaps": gaps}
        log(f"eval: {split} done")
    res["seconds"] = round(time.time() - t0, 1)
    return res


def write_tables(res: dict, grid: dict) -> str:
    f3 = lambda v: f"{v:.3f}"  # noqa: E731
    ci = lambda d: f"{d['mean']:.3f} [{d['ci95_lo']:.3f}, {d['ci95_hi']:.3f}]"  # noqa: E731
    gci = lambda d: f"{d['mean']:+.3f} [{d['ci95_lo']:+.3f}, {d['ci95_hi']:+.3f}]"  # noqa: E731
    names = {"greedy": "greedy", "beam_nolm": "beam, no LM", "beam_lm_retuned": "beam + LM, RETUNED as is",
             "beam_lm_valtuned": "beam + LM, val-tuned"}
    L = []
    for split in SPLITS:
        s = res["splits"][split]
        L += [f"### {split} (n = {s['n']} sentences)", "",
              "| decoder | real MEG | shuffled MEG | zeros | gap shuffled - real | WER real | pooled CER real | mean over subjects real | mean over participants real | true sentence in n-best (real) |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for d, label in names.items():
            r = s["results"]
            L.append(f"| {label} | {ci(r['real'][d]['cer_target'])} | {f3(r['shuffled'][d]['cer_target']['mean'])} | "
                     f"{f3(r['zeros'][d]['cer_target']['mean'])} | {gci(s['gaps'][f'shuffled_minus_real/{d}'])} | "
                     f"{f3(r['real'][d]['wer_target'])} | {f3(r['real'][d]['cer_target_pooled'])} | "
                     f"{f3(r['real'][d]['cer_target_mean_over_subjects'])} | "
                     f"{f3(r['real'][d]['cer_target_mean_over_participants'])} | "
                     f"{f3(r['real'][d]['target_in_nbest']) if 'target_in_nbest' in r['real'][d] else '-'} |")
        L.append("")
        L.append("Beam minus greedy (real MEG, paired): " + "; ".join(
            f"{names[d]} {gci(s['gaps'][f'{d}_minus_greedy/real'])}" for d in names if d != "greedy"))
        L.append(f"CPU fp32 re-run of real MEG, greedy: {ci(s['results']['real_cpu']['greedy']['cer_target'])}")
        L.append("")
    L += ["### Val grid (real MEG, CER vs target, mean over sentences)", "",
          f"Frame temperature fitted on real val: {grid['frame_temperature_val']:.3f}.", ""]
    for cal in (False, True):
        rows = [r for r in grid["rows"] if r["calibrated"] == cal]
        if not rows:
            continue
        L += [f"{'calibrated' if cal else 'raw'} streams", "", "| w \\ bonus | " + " | ".join(str(b) for b in GRID_B) + " |",
              "|---" * (len(GRID_B) + 1) + "|"]
        for w in GRID_W:
            L.append(f"| {w} | " + " | ".join(
                f3(next(r["val_cer_target"] for r in rows if r["lm_weight"] == w and r["insertion_bonus"] == b))
                for b in GRID_B) + " |")
        L.append("")
    return "\n".join(L)


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if k != "per_sentence_cer"}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="controls,grid,eval")
    ap.add_argument("--run-name", default=None, help="run name (runs/<run>/best.pt, streams/<run>/)")
    ap.add_argument("--out", default=None, help="results folder (default: this folder's results/)")
    ap.add_argument("--data-dir", default=None, help="folder for control log-probs and decode caches")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--grid-w", type=float, nargs="+", default=None)
    ap.add_argument("--grid-b", type=float, nargs="+", default=None)
    ap.add_argument("--no-calibrated", action="store_true")
    args = ap.parse_args()
    global RUN_DIR, STREAM_DIR, DATA_DIR, OUT, N_WORKERS, GRID_W, GRID_B, NO_CAL
    if args.run_name:
        RUN_DIR = Path("C:/Users/zhang/bci-data/runs") / args.run_name
        STREAM_DIR = Path("C:/Users/zhang/bci-data/streams") / args.run_name
        DATA_DIR = Path("C:/Users/zhang/bci-data/streams") / f"{args.run_name}_beam-controls"
    if args.out:
        OUT = Path(args.out)
    if args.data_dir:
        DATA_DIR = Path(args.data_dir)
    if args.workers:
        N_WORKERS = args.workers
    if args.grid_w:
        GRID_W = tuple(args.grid_w)
    if args.grid_b:
        GRID_B = tuple(args.grid_b)
    NO_CAL = bool(args.no_calibrated)
    OUT.mkdir(parents=True, exist_ok=True)
    log(f"run_dir={RUN_DIR} streams={STREAM_DIR} data={DATA_DIR} out={OUT} workers={N_WORKERS} "
        f"grid_w={GRID_W} grid_b={GRID_B} calibrated={not NO_CAL}")
    t0 = time.time()
    stages = args.stages.split(",")
    if "controls" in stages:
        stage_controls()
    with Pool(N_WORKERS, initializer=_init_worker) as pool:
        if "grid" in stages or not (OUT / "grid_val.json").exists():
            grid = stage_grid(pool)
        else:
            grid = json.loads((OUT / "grid_val.json").read_text(encoding="utf-8"))
        if "eval" in stages:
            res = stage_eval(pool, grid)
            res["total_seconds"] = round(time.time() - t0, 1)
            (OUT / "results.json").write_text(json.dumps(strip(res), indent=1), encoding="utf-8")
            per = {sp: {k: {d: v["per_sentence_cer"] for d, v in kv.items()} for k, kv in s["results"].items()}
                   for sp, s in res["splits"].items()}
            (OUT / "per_sentence_cer.json").write_text(json.dumps(per), encoding="utf-8")
            (OUT / "tables.md").write_text(write_tables(res, grid) + "\n", encoding="utf-8")
            log("eval: wrote results.json, tables.md")
    log(f"total {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
