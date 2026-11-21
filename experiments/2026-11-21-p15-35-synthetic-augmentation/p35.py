r"""P15-35 runner: Willett-style synthetic sentences for the minutes-scale E1 recipe - our own code, Apache-2.0.

Plan: plan.md (pre-registered, committed before any result of this task). Reuses the P15-33 code (p33.py, which
imports the P15-08 e1.py / run.py), the P15-08 Willett cache and the P15-33 recipe-A weights READ-ONLY.
Writes only to C:\Users\zhang\bci-data\derived\p15-35\.

Stages (``all`` runs them in order and skips finished parts; every training run resumes exactly):
  textpool  Tatoeba English (CC BY 2.0 FR) -> filtered, blocked text pool (local only) + aggregate report
  search    candidates U50, F50, F80 x arms R, E at 30 min, seed 0 (val only); a label-deranged run for every
            eligible (candidate, arm). No test-block number is computed.
  select    pre-registered rule with a val margin -> selection.json (val numbers only)
  test      selected candidate, every arm that passed: test readout of the seed-0 normal and deranged runs (C2)
  seed1     descriptive: the same arms at seed 1 (normal + deranged), only if GPU time allows
  summary   summary.json (aggregates only)

Run (repo root, GPU venv):
  C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-21-p15-35-synthetic-augmentation\p35.py all
A file ``pause`` or ``stop`` in --out saves latest.pt after the current step and exits with code 3.
Re-run the same command to resume.
"""

from __future__ import annotations

import argparse
import bz2
import dataclasses
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
P33_DIR = HERE.parent / "2026-11-20-p15-33-low-data-recipe"
sys.path.insert(0, str(P33_DIR))
import p33  # noqa: E402

e1, R8 = p33.e1, p33.R8

OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-35")
FORBIDDEN = [Path(r"C:\Users\zhang\bci-data\derived\p15-08"), Path(r"C:\Users\zhang\bci-data\derived\p15-33")]
PAUSED = 3
NEG = -1e30


class CapReached(Exception):
    pass


# --- context ---------------------------------------------------------------------------------------------------


@dataclasses.dataclass
class Ctx35:
    out: Path
    cfg: dict
    c33: p33.Ctx  # P15-33 context (its config, trunks, cache) with out = our folder
    rec: p33.Recipe  # recipe A of P15-33
    repo_results: Path | None = None
    clock_t0: float = 0.0
    clock_base: float = 0.0


def make_ctx(cfg_path: Path, out: Path, device: str, repo_results: Path | None = HERE / "results") -> Ctx35:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    root = HERE.parents[1]
    c33 = p33.ctx_from_config(root / cfg["p15_33_config"], out, device)
    c33.repo_results = None
    rec = p33.recipe_from(c33.raw, cfg["base_recipe"])
    return Ctx35(out=out, cfg=cfg, c33=c33, rec=rec, repo_results=repo_results)


def log(ctx: Ctx35, msg: str) -> None:
    p33.log(ctx.c33, msg)


def stop_requested(ctx: Ctx35) -> bool:
    return (ctx.out / "pause").exists() or (ctx.out / "stop").exists()


# --- GPU clock (sum of wall time of all launches; persisted) -----------------------------------------------------


def clock_start(ctx: Ctx35) -> None:
    p = ctx.out / "gpu_clock.json"
    ctx.clock_base = float(json.loads(p.read_text(encoding="utf-8"))["seconds"]) if p.exists() else 0.0
    ctx.clock_t0 = time.time()


def clock_hours(ctx: Ctx35) -> float:
    return (ctx.clock_base + time.time() - ctx.clock_t0) / 3600.0


def clock_save(ctx: Ctx35) -> None:
    e1.save_json({"seconds": round(ctx.clock_base + time.time() - ctx.clock_t0, 1),
                  "time": time.strftime("%Y-%m-%dT%H:%M:%S")}, ctx.out / "gpu_clock.json")


def check_cap(ctx: Ctx35) -> None:
    if clock_hours(ctx) >= float(ctx.cfg["gpu_cap_hours"]):
        raise CapReached()


# --- text pool -------------------------------------------------------------------------------------------------


def norm_text(s: str) -> str:
    """Lower case, typographic apostrophes -> ', runs of spaces -> one space, strip."""
    s = s.lower().replace("\u2019", "'").replace("\u2018", "'")
    return " ".join(s.split())


def word_ngrams(s: str, n: int) -> set[tuple[str, ...]]:
    w = s.split()
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


class Blocker:
    """Reject a text if it equals a blocked text, shares a word n-gram with one, contains a short blocked text
    (fewer than n words, >= contain_min_len chars), or (>= contain_min_len chars) is contained in one."""

    def __init__(self, blocked: list[str], n: int, contain_min_len: int):
        self.exact = set(blocked)
        self.ngrams: set[tuple[str, ...]] = set()
        for t in blocked:
            self.ngrams |= word_ngrams(t, n)
        self.short = [t for t in self.exact if len(t.split()) < n and len(t) >= contain_min_len]
        self.joined = "\n".join(sorted(self.exact))
        self.n, self.cmin = n, contain_min_len

    def blocked(self, s: str) -> bool:
        if s in self.exact:
            return True
        if word_ngrams(s, self.n) & self.ngrams:
            return True
        if any(t in s for t in self.short):
            return True
        return len(s) >= self.cmin and s in self.joined


def blocklist_texts(cfg: dict) -> tuple[list[str], dict]:
    b = cfg["blocklists"]
    meta = json.loads(Path(b["willett_meta"]).read_text(encoding="utf-8"))
    w = [norm_text(r["text"]) for r in meta]  # all 1,000 trials (train, val, test, excluded)
    t15: list[str] = []
    p = Path(b["t15_copytask_pkl"])
    if p.exists():
        import pickle  # local Dryad file (CC0), already used by earlier tasks; read-only

        with open(p, "rb") as fh:
            d = pickle.load(fh)
        t15 = [norm_text(str(s)) for s in d["cue_sentence"]]
    texts = sorted({t for t in w + t15 if t})
    return texts, {"willett_texts": len(w), "t15_cue_texts": len(t15), "unique_blocked": len(texts)}


def build_text_pool(cfg: dict, lines, blocked: list[str]) -> tuple[list[str], dict]:
    """``lines``: iterable of raw Tatoeba sentences. Returns (pool, counts)."""
    t = cfg["text"]
    chars = set(t["chars"])
    seen: set[str] = set()
    cand: list[str] = []
    n_raw = 0
    for s in lines:
        n_raw += 1
        s = norm_text(s)
        if not (t["min_len"] <= len(s) <= t["max_len"]) or s in seen or not set(s) <= chars:
            continue
        seen.add(s)
        cand.append(s)
    perm = np.random.default_rng(int(t["shuffle_seed"])).permutation(len(cand))
    blk = Blocker(blocked, int(t["ngram_block"]), int(t["contain_min_len"]))
    pool, n_blocked = [], 0
    for j in perm:
        s = cand[int(j)]
        if blk.blocked(s):
            n_blocked += 1
            continue
        pool.append(s)
        if len(pool) >= int(t["n_pool"]):
            break
    return pool, {"raw_lines": n_raw, "candidates_after_charset_length_dedupe": len(cand),
                  "blocked_while_sampling": n_blocked, "pool": len(pool)}


def read_tatoeba(path: Path):
    with bz2.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                yield parts[2]


def stage_textpool(ctx: Ctx35) -> list[str]:
    p = ctx.out / "text_pool.txt"
    if p.exists() and (ctx.out / "text_pool_report.json").exists():
        return p.read_text(encoding="utf-8").splitlines()
    blocked, bcounts = blocklist_texts(ctx.cfg)
    pool, counts = build_text_pool(ctx.cfg, read_tatoeba(Path(ctx.cfg["text"]["tatoeba"])), blocked)
    tmp = p.with_suffix(".tmp")
    tmp.write_text("".join(s + "\n" for s in pool), encoding="utf-8")
    os.replace(tmp, p)
    rep = {"note": "aggregate counts only; the text stays local (Tatoeba, CC BY 2.0 FR, Tatoeba contributors)",
           **counts, **bcounts, "sha256_pool": hashlib.sha256(p.read_bytes()).hexdigest(),
           "mean_len": round(float(np.mean([len(s) for s in pool])), 2)}
    e1.save_json(rep, ctx.out / "text_pool_report.json")
    if ctx.repo_results is not None:
        ctx.repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(rep, ctx.repo_results / "text_pool_report.json")
    log(ctx, f"[textpool] {rep}")
    return pool


# --- alignment and snippet library ------------------------------------------------------------------------------


def uniform_bounds(n_write: int, L: int) -> list[tuple[int, int]]:
    """Writing frames [0, n_write) split into L equal parts (rounded)."""
    b = [int(round(k * n_write / L)) for k in range(L + 1)]
    return [(b[k], b[k + 1]) for k in range(L)]


def ctc_last_frames(lp: np.ndarray, ids: np.ndarray, blank: int = 0) -> list[int] | None:
    """CTC Viterbi forced alignment. Returns the last frame of each label on the best path (None if T < L)."""
    T, L = lp.shape[0], len(ids)
    if L == 0 or T < L:
        return None
    ext = np.full(2 * L + 1, blank, np.int64)
    ext[1::2] = ids
    S = len(ext)
    skip = np.zeros(S, bool)
    skip[3::2] = ext[3::2] != ext[1:-2:2]
    lpd = np.asarray(lp, np.float64)
    delta = np.full(S, NEG)
    delta[0] = lpd[0, ext[0]]
    delta[1] = lpd[0, ext[1]]
    bp = np.zeros((T, S), np.int8)
    for t in range(1, T):
        c1 = np.concatenate(([NEG], delta[:-1]))
        c2 = np.where(skip, np.concatenate(([NEG, NEG], delta[:-2])), NEG)
        st = np.stack([delta, c1, c2])
        a = np.argmax(st, axis=0)
        bp[t] = a
        delta = st[a, np.arange(S)] + lpd[t, ext]
    s = S - 1 if delta[S - 1] >= delta[S - 2] else S - 2
    path = np.empty(T, np.int64)
    for t in range(T - 1, -1, -1):
        path[t] = s
        s -= int(bp[t, s])
    last = [-1] * L
    for t in range(T):
        if path[t] % 2 == 1:
            last[path[t] // 2] = t
    if min(last) < 0:
        return None
    return last


def duration_bounds(lp: np.ndarray, ids: np.ndarray, n_write: int, lag: int, sd_frac: float = 0.4,
                    dmin_frac: float = 0.25, dmax_frac: float = 3.0) -> list[tuple[int, int]] | None:
    """Forced alignment with a duration prior (segmental DP). Writing frames [0, n_write) are cut into L
    contiguous segments. Score of segment k = (b_{k-1}, b_k]: the aligner's non-blank log-posterior of character
    k at frame b_k - 1 + lag (a causal model emits a character after its end) + log N(d_k; mu, (sd_frac mu)^2),
    mu = n_write / L, d_k in [dmin_frac mu, dmax_frac mu]. Returns the maximum-score segmentation (None if L > n_write)."""
    T, L, N = lp.shape[0], len(ids), int(n_write)
    if L == 0 or N < L:
        return None
    x = np.asarray(lp[:, 1:], np.float64)
    m = x.max(axis=1, keepdims=True)
    lpn = x - (m + np.log(np.exp(x - m).sum(axis=1, keepdims=True)))
    mu = N / L
    sd = sd_frac * mu
    dmin = max(1, int(np.ceil(dmin_frac * mu)))
    dmax = max(dmin, int(np.floor(dmax_frac * mu)))
    dmin = min(dmin, N // L)
    dmax = max(dmax, int(np.ceil(N / L)))
    ds = np.arange(dmin, dmax + 1)
    dur = -0.5 * ((ds - mu) / sd) ** 2
    tix = np.minimum(np.arange(N) + int(lag), T - 1)
    prev = np.full(N + 1, NEG)
    prev[0] = 0.0
    bp = np.zeros((L, N + 1), np.int32)
    for k in range(L):
        best = np.full(N + 1, NEG)
        arg = np.zeros(N + 1, np.int32)
        for d, w in zip(ds.tolist(), dur.tolist()):
            if d > N:
                break
            cand = np.full(N + 1, NEG)
            cand[d:] = prev[:-d] + w
            upd = cand > best
            best[upd] = cand[upd]
            arg[upd] = d
        em = np.full(N + 1, NEG)
        em[1:] = lpn[tix, int(ids[k]) - 1]
        prev = np.where(best > NEG / 2, best + em, NEG)
        bp[k] = arg
    if prev[N] <= NEG / 2:
        return None
    out, b = [], N
    for k in range(L - 1, -1, -1):
        d = int(bp[k, b])
        out.append((b - d, b))
        b -= d
    assert b == 0
    return out[::-1]


def aligner_lag(lps: dict, store, sub: list[int], tgt: dict, tail: int = 100) -> int:
    """Median (CTC Viterbi last-character frame - n_write) over the budget sentences, clipped to [0, tail]."""
    lags = []
    for i in sub:
        last = ctc_last_frames(lps[i], np.asarray(tgt[i], np.int64))
        if last is not None:
            lags.append(last[-1] - int(store.meta[i]["n_write"]))
    return int(np.clip(np.median(lags), 0, tail)) if lags else 0


@dataclasses.dataclass
class Library:
    snips: dict  # token id -> list of float32 (n, 192) arrays, z-scored with the source session's stats
    tails: list  # float32 (n, 192) post-writing frames of the budget sentences, z-scored
    sessions: list  # sessions present in the budget subset
    stats: dict


def z_of(store, i: int, a: int, b: int) -> np.ndarray:
    s = store.meta[i]["session"]
    return ((np.asarray(store.x[i][a:b], np.float32) - store.mean[s]) / store.std[s]).astype(np.float32)


def build_library(store, sub: list[int], tgt: dict, align: str, lps: dict | None) -> Library:
    """Cut every budget sentence into character snippets. ``tgt`` = the training targets (deranged for C2).
    ``lps`` (forced only): sentence -> aligner log-probs (T, V)."""
    snips: dict[int, list] = {}
    tails, lens, n_fail = [], [], 0
    lag = aligner_lag(lps, store, sub, tgt) if align == "forced" else None
    for i in sub:
        ids = np.asarray(tgt[i], np.int64)
        nw = int(store.meta[i]["n_write"])
        if align == "uniform":
            bounds = uniform_bounds(nw, len(ids)) if len(ids) <= nw else None
        else:
            bounds = duration_bounds(lps[i], ids, nw, lag)
        if bounds is None:
            n_fail += 1
            continue
        for tok, (a, b) in zip(ids.tolist(), bounds):
            if b > a:
                snips.setdefault(int(tok), []).append(z_of(store, i, a, b))
                lens.append(b - a)
        if len(store.x[i]) > nw:
            tails.append(z_of(store, i, nw, len(store.x[i])))
    stats = {"align": align, "lag": lag, "n_sentences": len(sub), "n_failed": n_fail, "n_snippets": len(lens),
             "snippet_len_median": float(np.median(lens)) if lens else None,
             "snippet_len_p10_p90": [float(np.percentile(lens, 10)), float(np.percentile(lens, 90))] if lens else None,
             "chars_covered": "".join(sorted(e1.VOCAB[t] for t in snips)), "n_tails": len(tails)}
    sessions = sorted({int(store.meta[i]["session"]) for i in sub})
    return Library(snips=snips, tails=tails, sessions=sessions, stats=stats)


def usable_texts(pool: list[str], lib: Library) -> list[np.ndarray]:
    ok = {e1.VOCAB[t] for t in lib.snips}
    return [e1.encode(s) for s in pool if set(s) <= ok]


def render(lib: Library, ids: np.ndarray, store, rng: np.random.Generator, tail_frames: int) -> tuple[np.ndarray, int]:
    """One synthetic sentence: a random snippet per character + a random tail, in the raw space of a random
    budget session s0 (z * std[s0] + mean[s0]); the model's own normalisation with s0 gives back the z values."""
    parts = []
    for t in ids.tolist():
        cands = lib.snips[int(t)]
        parts.append(cands[int(rng.integers(len(cands)))])
    if lib.tails:
        parts.append(lib.tails[int(rng.integers(len(lib.tails)))][:tail_frames])
    z = np.concatenate(parts, axis=0)
    s0 = int(lib.sessions[int(rng.integers(len(lib.sessions)))])
    return (z * store.std[s0] + store.mean[s0]).astype(np.float32), s0


# --- aligners --------------------------------------------------------------------------------------------------


def subset_targets(ctx: Ctx35, store, seed: int, ls: bool) -> tuple[list[int], dict]:
    budget = ctx.cfg["budget"]
    sub = e1.budget_subset(store.meta, store.splits["pool"], float(budget), ctx.c33.raw["salt"], seed)
    tgt = {i: store.tgt[i] for i in sub}
    if ls:
        perm = e1.derangement(len(sub), np.random.default_rng([seed, 77]))
        tgt = {sub[j]: store.tgt[sub[int(perm[j])]] for j in range(len(sub))}
    return sub, tgt


def aligner_weights(ctx: Ctx35, store, arm: str, seed: int, ls: bool) -> Path:
    """Recipe-A weights for (arm, 30 min, seed, labels): from P15-33 (read-only) or trained here with p33 code."""
    name = R8.run_name(arm, ctx.cfg["budget"], seed, ls)
    src = ctx.cfg["aligner_sources"].get(name)
    if src and Path(src).exists():
        return Path(src)
    d = ctx.out / "aligners" / name
    if not (d / "DONE.json").exists():
        check_cap(ctx)
        log(ctx, f"[aligner] train recipe A {name} (budget data only)")
        r = p33.train_run(ctx.c33, store, ctx.rec, arm, ctx.cfg["budget"], seed, ls, d, False)
        clock_save(ctx)
        if r.get("partial"):
            raise p33.Paused()
    return d / "final.pt"


def get_library(ctx: Ctx35, store, align: str, arm: str, seed: int, ls: bool) -> Library:
    """Build once, save to disk (exact resume), load afterwards."""
    key = "uniform" if align == "uniform" else f"forced-{R8.run_name(arm, ctx.cfg['budget'], seed, ls)}"
    if align == "uniform":
        key += f"-s{seed}" + ("-labelshuf" if ls else "")
    p = ctx.out / "libraries" / f"{key}.npz"
    sub, tgt = subset_targets(ctx, store, seed, ls)
    if p.exists():
        z = np.load(p, allow_pickle=False)
        stats = json.loads(str(z["stats"]))
        frames = z["frames"]  # read once (each NpzFile lookup reads the file again)
        snips: dict[int, list] = {}
        for tok, a, b in z["index"]:
            snips.setdefault(int(tok), []).append(frames[a:b])
        tails = [frames[a:b] for a, b in z["tail_index"]]
        return Library(snips=snips, tails=tails, sessions=[int(s) for s in z["sessions"]], stats=stats)
    lps = None
    if align == "forced":
        wpath = aligner_weights(ctx, store, arm, seed, ls)
        model = p33.init_model(ctx.c33, store, ctx.rec, arm, seed)
        model.load_state_dict(torch.load(wpath, map_location=ctx.c33.device, weights_only=True)["model"])
        lps = {i: e1.sentence_log_probs(model, store.x[i], store.meta[i]["session"], ctx.c33.device) for i in sub}
        del model
    lib = build_library(store, sub, tgt, align, lps)
    lib.stats["aligner"] = str(wpath) if align == "forced" else None
    frames, index, tidx, off = [], [], [], 0
    for tok, lst in sorted(lib.snips.items()):
        for a in lst:
            frames.append(a); index.append((tok, off, off + len(a))); off += len(a)
    for a in lib.tails:
        frames.append(a); tidx.append((off, off + len(a))); off += len(a)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.stem + ".tmp.npz")
    np.savez(tmp, frames=np.concatenate(frames, 0).astype(np.float32), index=np.array(index, np.int64),
             tail_index=np.array(tidx, np.int64).reshape(-1, 2), sessions=np.array(lib.sessions, np.int64),
             stats=json.dumps(lib.stats))
    os.replace(tmp, p)
    log(ctx, f"[library] {key}: {lib.stats}")
    return get_library(ctx, store, align, arm, seed, ls)  # reload: same object on resume as on first build


# --- one training run with synthetic sentences -----------------------------------------------------------------


def run_name(cand: str, arm: str, seed: int, ls: bool, budget: str = "30") -> str:
    return f"{cand}/{R8.run_name(arm, budget, seed, ls)}"


def build_batch(ctx: Ctx35, store, sub, tgt, lib, texts, frac, rng, rec):
    bi = e1.pack_batch(sub, store.length, rec.max_frames, rng)
    syn = rng.random(len(bi)) < frac
    items, is_syn = [], []
    for i, s in zip(bi, syn):
        if s:
            ids = texts[int(rng.integers(len(texts)))]
            x, s0 = render(lib, ids, store, rng, int(ctx.cfg["synth"]["tail_frames"]))
            items.append((x, ids, s0)); is_syn.append(True)
        else:
            items.append((store.x[i], tgt[i], store.meta[i]["session"])); is_syn.append(False)
    rs = rng.uniform(rec.stretch_lo, rec.stretch_hi, len(items)) if rec.stretch_hi > rec.stretch_lo else None
    if rs is not None:
        items = [(p33.stretch(x, float(r)), t, s) for (x, t, s), r in zip(items, rs)]

    def padded(its):
        return max(len(x) for x, _, _ in its) * len(its)

    while len(items) > 1 and padded(items) > rec.max_frames and any(is_syn):
        j = max((k for k in range(len(items)) if is_syn[k]), key=lambda k: len(items[k][0]))
        items.pop(j); is_syn.pop(j)
    return items, int(sum(is_syn))


def train_syn(ctx: Ctx35, store, pool, cand: str, arm: str, seed: int, ls: bool, d: Path, do_test: bool,
              max_steps: int | None = None) -> dict:
    """P15-33 train_run with synthetic sentences mixed into each batch. Batch k depends only on
    (seed, budget, label_shuffle, k, candidate) and the saved library: exact resume."""
    c = ctx.cfg["candidates"][cand]
    rec = dataclasses.replace(ctx.rec, name=f"A+{cand}")
    budget = ctx.cfg["budget"]
    name = run_name(cand, arm, seed, ls, budget)
    d.mkdir(parents=True, exist_ok=True)
    if (d / "DONE.json").exists():
        return json.loads((d / "result.json").read_text(encoding="utf-8"))
    check_cap(ctx)
    sub, tgt = subset_targets(ctx, store, seed, ls)
    lib = get_library(ctx, store, c["align"], arm, seed, ls)
    texts = usable_texts(pool, lib)
    total = int(rec.steps[budget])
    bc = R8.budget_code(budget)
    model = p33.init_model(ctx.c33, store, rec, arm, seed)
    opt = p33.make_optim(model, rec)
    step, best = 0, {"cer": float("inf"), "step": -1}
    if (d / "latest.pt").exists():
        ck = torch.load(d / "latest.pt", map_location=ctx.c33.device, weights_only=True)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"])
        step, best = int(ck["step"]), {"cer": float(ck["best_cer"]), "step": int(ck["best_step"])}
        log(ctx, f"[{name}] resume at step {step} (best val {best['cer']:.4f} @ {best['step']})")
        mp = d / "metrics.jsonl"
        if mp.exists():
            keep = [ln for ln in mp.read_text(encoding="utf-8").splitlines() if ln and json.loads(ln)["step"] <= step]
            mp.write_text("".join(k + "\n" for k in keep), encoding="utf-8")
    e1.save_json({**R8.LICENCE[arm], "arm": arm, "label_shuffle": ls, "recipe": rec.name,
                  "synthetic_text": "Tatoeba English, CC BY 2.0 FR (Tatoeba contributors); local only"}, d / "licence.json")
    e1.save_json({"recipe": rec.__dict__, "candidate": c, "library": lib.stats, "n_texts": len(texts),
                  "trainable_params": p33.n_trainable(model)}, d / "config.json")

    def save_latest() -> None:
        R8.atomic_save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step,
                        "best_cer": best["cer"], "best_step": best["step"]}, d / "latest.pt")
        clock_save(ctx)

    ectx = p33._ectx(ctx.c33, rec)
    end = total if max_steps is None else min(total, step + max_steps)
    t_ck = t_log = time.time(); s_log = step; losses: list[float] = []; skipped = 0; n_syn = 0; n_all = 0
    val_idx = store.splits["val"]
    dev = ctx.c33.device
    while step < end:
        rng = np.random.default_rng([seed, bc, int(ls), step, int(c["code"])])
        gen = torch.Generator().manual_seed(int(rng.integers(2 ** 62)))
        torch.manual_seed(int(rng.integers(2 ** 62)))
        items, k_syn = build_batch(ctx, store, sub, tgt, lib, texts, float(c["synth_frac"]), rng, rec)
        n_syn += k_syn; n_all += len(items)
        b = e1.collate(items)
        b["x"] = p33.pad_time(b["x"], p33.PAD_MULT)
        p33.set_train(model, rec)
        for g in opt.param_groups:
            g["lr"] = e1.lr_at(step, total, rec.lr, rec.lr_min, rec.warmup)
        x = torch.from_numpy(b["x"]).to(dev)
        sess = torch.from_numpy(b["sess"]).to(dev)
        lengths = torch.from_numpy(b["lengths"])
        xn = p33.augment(model.normalise(x, sess), lengths, rec, gen)
        pad = (torch.arange(xn.shape[1])[None, :] >= lengths[:, None]).to(xn.device)
        xn = xn.masked_fill(pad[:, :, None], 0.0)
        lp = model(xn, sess, normalised=True)
        loss = F.ctc_loss(lp.transpose(0, 1), torch.from_numpy(b["targets"]).to(dev), lengths,
                          torch.from_numpy(b["target_lengths"]), blank=e1.BLANK, reduction="mean", zero_infinity=True)
        opt.zero_grad(set_to_none=True)
        if torch.isfinite(loss):
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], rec.clip)
            opt.step()
            losses.append(float(loss.detach()))
        else:
            skipped += 1
        step += 1
        if step % 100 == 0 or step == end:
            dt = (time.time() - t_log) / max(1, step - s_log); t_log = time.time(); s_log = step
            log(ctx, f"[{name}] step {step}/{total} loss {np.mean(losses) if losses else float('nan'):.4f} "
                     f"{dt:.3f} s/step skipped {skipped} synth {n_syn}/{n_all} gpu_h {clock_hours(ctx):.2f}")
            losses = []; n_syn = 0; n_all = 0
        if step % rec.val_every == 0 or step == total:
            v = R8.eval_set(ectx, model, store, val_idx)
            with open(d / "metrics.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"step": step, "val_cer": v["cer"]}) + "\n")
            if v["cer"] < best["cer"]:
                best = {"cer": v["cer"], "step": step}
                R8.atomic_save({"model": model.state_dict(), "step": step, "val_cer": v["cer"]}, d / "best.pt")
            save_latest(); t_ck = time.time()
        elif time.time() - t_ck > 60 * rec.ckpt_minutes:
            save_latest(); t_ck = time.time()
        if stop_requested(ctx):
            save_latest()
            log(ctx, f"[{name}] pause/stop file: saved latest.pt at step {step}, exit")
            raise p33.Paused()
        if step % 100 == 0 and clock_hours(ctx) >= float(ctx.cfg["gpu_cap_hours"]):
            save_latest()
            raise CapReached()
    if step < total:
        save_latest()
        return {"partial": True, "step": step}
    R8.atomic_save({"model": model.state_dict(), "step": step}, d / "final.pt")
    res = p33.finish_run(ctx.c33, store, rec, arm, budget, seed, ls, d, do_test, model, best, skipped, sub)
    clock_save(ctx)
    return res


# --- search, selection, test ------------------------------------------------------------------------------------


def sdir(ctx: Ctx35, cand: str, arm: str, seed: int, ls: bool, part: str = "search") -> Path:
    return ctx.out / part / cand / R8.run_name(arm, ctx.cfg["budget"], seed, ls)


def stage_search(ctx: Ctx35, store, pool, max_steps: int | None = None) -> bool:
    seed, rules = int(ctx.cfg["search_seed"]), ctx.cfg["rules"]
    for cand in ctx.cfg["candidates"]:
        for arm in ctx.cfg["search_arms"]:
            r = train_syn(ctx, store, pool, cand, arm, seed, False, sdir(ctx, cand, arm, seed, False), False, max_steps)
            if r.get("partial"):
                return False
            if r["val_cer_final"] < float(rules["eligible_max_val_cer"]):
                r2 = train_syn(ctx, store, pool, cand, arm, seed, True, sdir(ctx, cand, arm, seed, True), False, max_steps)
                if r2.get("partial"):
                    return False
    return True


def c2_need(rules: dict, normal: float) -> float:
    return max(float(rules["c2_min_cer"]), normal + float(rules["c2_min_gap"]))


def select(ctx: Ctx35) -> dict:
    """plan.md rule: an arm passes val-C2-with-margin if it is eligible (normal final val CER < 0.80) and its
    deranged final val CER >= max(0.75, normal + 0.10) + 0.03. A candidate passes if >= 1 arm passes. Pick the
    passing candidate with the lowest normal final val CER over its passing arms; tie -> config order."""
    seed, rules = int(ctx.cfg["search_seed"]), ctx.cfg["rules"]
    rows, passing = [], []
    for k, cand in enumerate(ctx.cfg["candidates"]):
        arms_pass = []
        for arm in ctx.cfg["search_arms"]:
            r = json.loads((sdir(ctx, cand, arm, seed, False) / "result.json").read_text(encoding="utf-8"))
            row = {"candidate": cand, "arm": arm, "val_cer": r["val_cer_final"],
                   "val_shuffled_cer": r["val_shuffled_cer_final"], "best_val_cer": r["best_val_cer"],
                   "eligible": r["val_cer_final"] < float(rules["eligible_max_val_cer"])}
            p2 = sdir(ctx, cand, arm, seed, True) / "result.json"
            if row["eligible"] and p2.exists():
                r2 = json.loads(p2.read_text(encoding="utf-8"))
                need = c2_need(rules, r["val_cer_final"]) + float(rules["val_margin"])
                ln = json.loads((sdir(ctx, cand, arm, seed, False) / "config.json").read_text(encoding="utf-8"))
                ld = json.loads((sdir(ctx, cand, arm, seed, True) / "config.json").read_text(encoding="utf-8"))
                mn, md = ln["library"]["snippet_len_median"], ld["library"]["snippet_len_median"]
                ratio = md / mn if mn else float("inf")
                guard = abs(ratio - 1.0) <= float(rules["length_guard"])
                row.update({"deranged_val_cer": r2["val_cer_final"], "needed_with_margin": need,
                            "snippet_median_normal": mn, "snippet_median_deranged": md,
                            "length_ratio": round(ratio, 4), "length_guard_pass": bool(guard),
                            "c2_val_pass": bool(r2["val_cer_final"] >= need and guard)})
            else:
                row["c2_val_pass"] = False
            rows.append(row)
            if row["c2_val_pass"]:
                arms_pass.append(row)
        if arms_pass:
            passing.append((min(a["val_cer"] for a in arms_pass), k, cand, [a["arm"] for a in arms_pass]))
    passing.sort()
    return {"note": "val block only (no test-block number); plan.md rule", "rows": rows,
            "selected": passing[0][2] if passing else None, "passing_arms": passing[0][3] if passing else [],
            "time": time.strftime("%Y-%m-%dT%H:%M:%S")}


def stage_select(ctx: Ctx35) -> dict:
    p = ctx.out / "selection.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    sel = select(ctx)
    e1.save_json(sel, p)
    if ctx.repo_results is not None:
        ctx.repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(sel, ctx.repo_results / "selection.json")
    log(ctx, f"[select] selected {sel['selected']} (arms {sel['passing_arms']})")
    return sel


def test_readout(ctx: Ctx35, store, cand: str, arm: str, seed: int, ls: bool) -> dict:
    """Reuse the search weights (same run), add the P15-08 test readout."""
    d = sdir(ctx, cand, arm, seed, ls, "test")
    if (d / "DONE.json").exists():
        return json.loads((d / "result.json").read_text(encoding="utf-8"))
    src = sdir(ctx, cand, arm, seed, ls)
    d.mkdir(parents=True, exist_ok=True)
    for f in ("final.pt", "best.pt", "metrics.jsonl", "licence.json", "config.json"):
        if (src / f).exists():
            shutil.copy(src / f, d / f)
    sr = json.loads((src / "result.json").read_text(encoding="utf-8"))
    rec = dataclasses.replace(ctx.rec, name=f"A+{cand}")
    model = p33.init_model(ctx.c33, store, rec, arm, seed)
    model.load_state_dict(torch.load(d / "final.pt", map_location=ctx.c33.device, weights_only=True)["model"])
    sub, _ = subset_targets(ctx, store, seed, ls)
    log(ctx, f"[{run_name(cand, arm, seed, ls)}] reuse search weights for the test readout")
    res = p33.finish_run(ctx.c33, store, rec, arm, ctx.cfg["budget"], seed, ls, d, True, model,
                         {"cer": sr["best_val_cer"], "step": sr["best_val_step"]}, sr["skipped"], sub)
    res["val_shuffled_cer_final"] = sr.get("val_shuffled_cer_final")
    e1.save_json(res, d / "result.json")
    return res


def stage_test(ctx: Ctx35, store, sel: dict) -> None:
    seed = int(ctx.cfg["search_seed"])
    for arm in sel["passing_arms"]:
        for ls in (False, True):
            test_readout(ctx, store, sel["selected"], arm, seed, ls)


def stage_seed1(ctx: Ctx35, store, pool, sel: dict) -> str:
    seed = int(ctx.cfg["descriptive_seed"])
    if clock_hours(ctx) > float(ctx.cfg["seed1_start_max_hours"]) and not (ctx.out / "seed1").exists():
        log(ctx, f"[seed1] skipped: GPU clock {clock_hours(ctx):.2f} h > {ctx.cfg['seed1_start_max_hours']} h")
        return "skipped"
    for arm in sel["passing_arms"]:
        for ls in (False, True):
            r = train_syn(ctx, store, pool, sel["selected"], arm, seed, ls, sdir(ctx, sel["selected"], arm, seed, ls,
                                                                                  "seed1"), True)
            if r.get("partial"):
                return "partial"
    return "done"


def stage_summary(ctx: Ctx35, sel: dict, seed1_status: str) -> dict:
    rules = ctx.cfg["rules"]
    keys = ("run", "recipe", "arm", "budget", "seed", "label_shuffle", "steps", "skipped", "n_train", "minutes",
            "trainable_params", "val_cer_final", "val_shuffled_cer_final", "best_val_step", "best_val_cer",
            "test_cer_final", "test_cer_bestval", "c1_shuffled_cer")

    def load(part: str, cand: str, arm: str, seed: int, ls: bool) -> dict | None:
        p = sdir(ctx, cand, arm, seed, ls, part) / "result.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def c2_rows(part: str, seed: int) -> list[dict]:
        out = []
        for arm in sel["passing_arms"]:
            n, dr = load(part, sel["selected"], arm, seed, False), load(part, sel["selected"], arm, seed, True)
            if n and dr:
                need = c2_need(rules, n["test_cer_final"])
                out.append({"arm": arm, "seed": seed, "normal_test_cer": n["test_cer_final"],
                            "deranged_test_cer": dr["test_cer_final"], "needed": need,
                            "pass": bool(dr["test_cer_final"] >= need),
                            "time_shuffled_test_cer": n.get("c1_shuffled_cer")})
        return out

    search_runs = []
    for cand in ctx.cfg["candidates"]:
        for arm in ctx.cfg["search_arms"]:
            for ls in (False, True):
                r = load("search", cand, arm, int(ctx.cfg["search_seed"]), ls)
                if r:
                    search_runs.append({k: r[k] for k in keys if k in r})
    libs = {}
    for p in sorted((ctx.out / "libraries").glob("*.npz")):
        libs[p.stem] = json.loads(str(np.load(p, allow_pickle=False)["stats"]))
        libs[p.stem].pop("aligner", None)
    c2_test = c2_rows("test", int(ctx.cfg["search_seed"]))
    agg = {"note": "aggregate only; CER = total edits / total reference characters; val = 106 val sentences, test = 80 "
                   "test sentences (last block of each session); greedy CTC, no LM, final step; plan.md",
           "selection": sel, "search_runs": search_runs, "libraries": libs,
           "C2_test": c2_test, "C2_test_any_pass": bool(any(r["pass"] for r in c2_test)),
           "seed1_status": seed1_status, "C2_seed1_descriptive": c2_rows("seed1", int(ctx.cfg["descriptive_seed"])),
           "gpu_hours": round(clock_hours(ctx), 3), "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    rep = ctx.out / "text_pool_report.json"
    if rep.exists():
        agg["text_pool"] = json.loads(rep.read_text(encoding="utf-8"))
    e1.save_json(agg, ctx.out / "summary.json")
    if ctx.repo_results is not None:
        ctx.repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(agg, ctx.repo_results / "summary.json")
    log(ctx, f"[summary] C2 test {[(r['arm'], r['pass']) for r in c2_test]} gpu_h {agg['gpu_hours']}")
    return agg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P15-35 runner")
    ap.add_argument("stage", choices=("all", "textpool", "summary"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    for f in FORBIDDEN:
        if out == f.resolve() or f.resolve() in out.parents:
            print(f"never write into {f}", file=sys.stderr)
            return 2
    out.mkdir(parents=True, exist_ok=True)
    ctx = make_ctx(Path(a.config), out, a.device)
    torch.set_num_threads(2)
    log(ctx, f"start stage={a.stage} device={a.device} torch={torch.__version__} pid={os.getpid()}")
    clock_start(ctx)
    R8.keep_awake(True)
    try:
        pool = stage_textpool(ctx)
        if a.stage == "textpool":
            return 0
        store = R8.WillettStore(ctx.c33.cache)
        if a.stage == "summary":
            sel = stage_select(ctx)
            stage_summary(ctx, sel, "unknown")
            return 0
        if not stage_search(ctx, store, pool):
            return 0
        sel = stage_select(ctx)
        if sel["selected"] is None:
            log(ctx, "[select] no candidate passes val-C2 with the margin: stop (no test readout; plan.md)")
            stage_summary(ctx, sel, "not_run")
            (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " no_recipe", encoding="utf-8")
            return 0
        stage_test(ctx, store, sel)
        s1 = stage_seed1(ctx, store, pool, sel)
        if s1 == "partial":
            return 0
        stage_summary(ctx, sel, s1)
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
        log(ctx, "ALL DONE")
    except p33.Paused:
        clock_save(ctx)
        return PAUSED
    except CapReached:
        clock_save(ctx)
        log(ctx, f"GPU cap {ctx.cfg['gpu_cap_hours']} h reached: stop (plan.md)")
        try:
            sel = stage_select(ctx) if (ctx.out / "selection.json").exists() else {"selected": None, "passing_arms": []}
            stage_summary(ctx, sel, "cap")
        except Exception as ex:  # noqa: BLE001 - summary is best effort at the cap
            log(ctx, f"summary at cap failed: {ex!r}")
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " cap", encoding="utf-8")
        return 0
    finally:
        clock_save(ctx)
        R8.keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
