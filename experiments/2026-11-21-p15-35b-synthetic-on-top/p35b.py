r"""P15-35b runner: synthetic sentences ADDED ON TOP of the real batch, longer schedule - our own code, Apache-2.0.

Plan: plan.md (pre-registered, committed before any result of this attempt). Attempt 2 of gap 139.
``p35_lib.py`` is a verbatim copy of the attempt-1 runner (experiments/2026-11-21-p15-35-synthetic-augmentation/
p35.py at 218d889). This file imports it as a library (text blocker, alignment, snippet library, rendering,
aligners, selection rule). Attempt-1 files are never edited. P15-33 / P15-08 code, the Willett cache, the
P15-33 recipe-A weights (aligners) and the attempt-1 text pool are read-only.
Writes only to C:\Users\zhang\bci-data\derived\p15-35b\.

Stages (``all`` runs them in order and skips finished parts; every training run resumes exactly):
  textpool  verify the attempt-1 text pool (SHA-256) and copy its aggregate report (no text)
  search    candidates (arm E, 30 min, seed 0, 4,000 steps): normal runs first, then a label-deranged run for
            every eligible candidate. Val only.
  select    pre-registered rule (attempt-1 rule, margin 0.03, length guard) -> selection.json (val numbers only)
  test      selected candidate: test readout of the seed-0 normal and deranged runs (C2)
  control   descriptive: recipe A at 4,000 steps without synthetic items (val only; deranged if eligible)
  seed1     descriptive: the selected candidate at seed 1 (normal + deranged), only if GPU time allows
  summary   summary.json (aggregates only)

Run (repo root, GPU venv):
  C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-21-p15-35b-synthetic-on-top\p35b.py all
A file ``pause`` or ``stop`` in --out saves latest.pt after the current step and exits with code 3.
Re-run the same command to resume.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p35_lib as L  # noqa: E402  (verbatim copy of attempt-1 p35.py)

p33, e1, R8 = L.p33, L.e1, L.R8

OUT = Path(r"C:\Users\zhang\bci-data\derived\p15-35b")
FORBIDDEN = [Path(r"C:\Users\zhang\bci-data\derived\p15-08"), Path(r"C:\Users\zhang\bci-data\derived\p15-33"),
             Path(r"C:\Users\zhang\bci-data\derived\p15-35")]
PAUSED = 3


# --- context ---------------------------------------------------------------------------------------------------


def make_ctx(cfg_path: Path, out: Path, device: str, repo_results: Path | None = HERE / "results") -> L.Ctx35:
    return L.make_ctx(cfg_path, out, device, repo_results)


def all_specs(cfg: dict) -> dict:
    """Candidates + control, by id."""
    return {**cfg["candidates"], **cfg["control"]}


def run_recipe(ctx: L.Ctx35, spec_id: str) -> p33.Recipe:
    """Recipe A with this spec's step count (warmup 100, cosine over the new total). max_frames stays 24,000
    (the real-sentence packing and the eval batching are those of P15-33)."""
    spec = all_specs(ctx.cfg)[spec_id]
    steps = dict(ctx.rec.steps)
    steps[ctx.cfg["budget"]] = int(spec["steps"])
    return dataclasses.replace(ctx.rec, name=f"A+{spec_id}", steps=steps)


# --- text pool (reuse attempt 1, read-only) -------------------------------------------------------------------


def stage_textpool(ctx: L.Ctx35) -> list[str]:
    t = ctx.cfg["text_pool"]
    p = Path(t["path"])
    raw = p.read_bytes()
    h = hashlib.sha256(raw).hexdigest()
    if h != t["sha256"]:
        raise RuntimeError(f"text pool hash mismatch: {h} != {t['sha256']}")
    pool = raw.decode("utf-8").splitlines()
    rep = json.loads(Path(t["report"]).read_text(encoding="utf-8"))
    rep["reused_from"] = "P15-35 attempt 1 (derived/p15-35/text_pool.txt, read-only); SHA-256 verified"
    rep_path = ctx.out / "text_pool_report.json"
    if not rep_path.exists():
        e1.save_json(rep, rep_path)
        if ctx.repo_results is not None:
            ctx.repo_results.mkdir(parents=True, exist_ok=True)
            e1.save_json(rep, ctx.repo_results / "text_pool_report.json")
        L.log(ctx, f"[textpool] reused attempt-1 pool: {len(pool)} texts, sha256 ok")
    return pool


# --- batches ---------------------------------------------------------------------------------------------------


def n_extra(extra: float, n_real: int, rng: np.random.Generator) -> int:
    """Number of synthetic items added on top: floor(extra * n_real) + Bernoulli(fractional part)."""
    v = extra * n_real
    k = int(math.floor(v))
    return k + int(rng.random() < (v - k))


def build_batch_b(ctx, store, sub, tgt, lib, texts, spec: dict, rng, rec):
    """Batch for one step. The real part is packed exactly as P15-33 (pack_batch, 24,000 frames).
    mode 'ontop':   all real items stay; n_extra synthetic items are added; frame cap 24,000 * (1 + extra);
                    above the cap synthetic items are dropped (longest first). Real items are never dropped.
    mode 'replace': each real slot becomes synthetic with probability synth_frac (attempt-1 rule); cap 24,000.
    mode 'none':    real items only (recipe A).
    Returns (items, number of synthetic items, number of real items)."""
    bi = e1.pack_batch(sub, store.length, rec.max_frames, rng)
    mode = spec["mode"]
    tail = int(ctx.cfg["synth"]["tail_frames"])
    items, is_syn = [], []
    if mode == "replace":
        syn = rng.random(len(bi)) < float(spec["synth_frac"])
    else:
        syn = np.zeros(len(bi), bool)
    for i, s in zip(bi, syn):
        if s:
            ids = texts[int(rng.integers(len(texts)))]
            x, s0 = L.render(lib, ids, store, rng, tail)
            items.append((x, ids, s0)); is_syn.append(True)
        else:
            items.append((store.x[i], tgt[i], store.meta[i]["session"])); is_syn.append(False)
    cap = rec.max_frames
    if mode == "ontop":
        extra = float(spec["extra"])
        for _ in range(n_extra(extra, len(bi), rng)):
            ids = texts[int(rng.integers(len(texts)))]
            x, s0 = L.render(lib, ids, store, rng, tail)
            items.append((x, ids, s0)); is_syn.append(True)
        cap = int(round(rec.max_frames * (1.0 + extra)))
    rs = rng.uniform(rec.stretch_lo, rec.stretch_hi, len(items)) if rec.stretch_hi > rec.stretch_lo else None
    if rs is not None:
        items = [(p33.stretch(x, float(r)), t, s) for (x, t, s), r in zip(items, rs)]

    def padded(its):
        return max(len(x) for x, _, _ in its) * len(its)

    while len(items) > 1 and padded(items) > cap and any(is_syn):
        j = max((k for k in range(len(items)) if is_syn[k]), key=lambda k: len(items[k][0]))
        items.pop(j); is_syn.pop(j)
    k_syn = int(sum(is_syn))
    return items, k_syn, len(items) - k_syn


# --- one training run ------------------------------------------------------------------------------------------


def sdir(ctx: L.Ctx35, spec_id: str, arm: str, seed: int, ls: bool, part: str = "search") -> Path:
    return ctx.out / part / spec_id / R8.run_name(arm, ctx.cfg["budget"], seed, ls)


def train_b(ctx: L.Ctx35, store, pool, spec_id: str, arm: str, seed: int, ls: bool, d: Path, do_test: bool,
            max_steps: int | None = None) -> dict:
    """P15-35 train_syn with the attempt-2 batch rule and the spec's step count. Batch k depends only on
    (seed, budget, label_shuffle, k, spec code) and the saved library: exact resume."""
    spec = all_specs(ctx.cfg)[spec_id]
    rec = run_recipe(ctx, spec_id)
    budget = ctx.cfg["budget"]
    name = f"{spec_id}/{R8.run_name(arm, budget, seed, ls)}"
    d.mkdir(parents=True, exist_ok=True)
    if (d / "DONE.json").exists():
        return json.loads((d / "result.json").read_text(encoding="utf-8"))
    L.check_cap(ctx)
    sub, tgt = L.subset_targets(ctx, store, seed, ls)
    if spec["mode"] == "none":
        lib, texts, lib_stats = None, [], None
    else:
        lib = L.get_library(ctx, store, spec["align"], arm, seed, ls)
        texts = L.usable_texts(pool, lib)
        lib_stats = lib.stats
    total = int(rec.steps[budget])
    bc = R8.budget_code(budget)
    model = p33.init_model(ctx.c33, store, rec, arm, seed)
    opt = p33.make_optim(model, rec)
    step, best = 0, {"cer": float("inf"), "step": -1}
    if (d / "latest.pt").exists():
        ck = torch.load(d / "latest.pt", map_location=ctx.c33.device, weights_only=True)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"])
        step, best = int(ck["step"]), {"cer": float(ck["best_cer"]), "step": int(ck["best_step"])}
        L.log(ctx, f"[{name}] resume at step {step} (best val {best['cer']:.4f} @ {best['step']})")
        mp = d / "metrics.jsonl"
        if mp.exists():
            keep = [ln for ln in mp.read_text(encoding="utf-8").splitlines() if ln and json.loads(ln)["step"] <= step]
            mp.write_text("".join(k + "\n" for k in keep), encoding="utf-8")
    e1.save_json({**R8.LICENCE[arm], "arm": arm, "label_shuffle": ls, "recipe": rec.name,
                  "synthetic_text": "Tatoeba English, CC BY 2.0 FR (Tatoeba contributors); local only"}, d / "licence.json")
    e1.save_json({"recipe": rec.__dict__, "candidate": spec, "library": lib_stats, "n_texts": len(texts),
                  "trainable_params": p33.n_trainable(model)}, d / "config.json")

    def save_latest() -> None:
        R8.atomic_save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step,
                        "best_cer": best["cer"], "best_step": best["step"]}, d / "latest.pt")
        L.clock_save(ctx)

    ectx = p33._ectx(ctx.c33, rec)
    end = total if max_steps is None else min(total, step + max_steps)
    t_ck = t_log = time.time(); s_log = step; losses: list[float] = []; skipped = 0; n_syn = 0; n_real = 0
    val_idx = store.splits["val"]
    dev = ctx.c33.device
    while step < end:
        rng = np.random.default_rng([seed, bc, int(ls), step, int(spec["code"])])
        gen = torch.Generator().manual_seed(int(rng.integers(2 ** 62)))
        torch.manual_seed(int(rng.integers(2 ** 62)))
        items, k_syn, k_real = build_batch_b(ctx, store, sub, tgt, lib, texts, spec, rng, rec)
        n_syn += k_syn; n_real += k_real
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
        del x, xn, lp, loss
        step += 1
        if step % 100 == 0 or step == end:
            dt = (time.time() - t_log) / max(1, step - s_log); t_log = time.time(); s_log = step
            L.log(ctx, f"[{name}] step {step}/{total} loss {np.mean(losses) if losses else float('nan'):.4f} "
                       f"{dt:.3f} s/step skipped {skipped} real {n_real} synth {n_syn} gpu_h {L.clock_hours(ctx):.2f}")
            losses = []; n_syn = 0; n_real = 0
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
        if L.stop_requested(ctx):
            save_latest()
            L.log(ctx, f"[{name}] pause/stop file: saved latest.pt at step {step}, exit")
            raise p33.Paused()
        if step % 100 == 0 and L.clock_hours(ctx) >= float(ctx.cfg["gpu_cap_hours"]):
            save_latest()
            raise L.CapReached()
    if step < total:
        save_latest()
        return {"partial": True, "step": step}
    R8.atomic_save({"model": model.state_dict(), "step": step}, d / "final.pt")
    res = p33.finish_run(ctx.c33, store, rec, arm, budget, seed, ls, d, do_test, model, best, skipped, sub)
    L.clock_save(ctx)
    return res


# --- stages ----------------------------------------------------------------------------------------------------


def eligible(ctx: L.Ctx35, r: dict) -> bool:
    return r["val_cer_final"] < float(ctx.cfg["rules"]["eligible_max_val_cer"])


def stage_search(ctx: L.Ctx35, store, pool, max_steps: int | None = None) -> bool:
    """Normal runs of all candidates first, then the deranged run of every eligible candidate."""
    seed = int(ctx.cfg["search_seed"])
    normal = {}
    for cand in ctx.cfg["candidates"]:
        for arm in ctx.cfg["search_arms"]:
            r = train_b(ctx, store, pool, cand, arm, seed, False, sdir(ctx, cand, arm, seed, False), False, max_steps)
            if r.get("partial"):
                return False
            normal[(cand, arm)] = r
    for (cand, arm), r in normal.items():
        if eligible(ctx, r):
            r2 = train_b(ctx, store, pool, cand, arm, seed, True, sdir(ctx, cand, arm, seed, True), False, max_steps)
            if r2.get("partial"):
                return False
    return True


def stage_select(ctx: L.Ctx35) -> dict:
    """Attempt-1 selection function (p35_lib.select) on our search folder. It reads <out>/search/<cand>/<run>
    and the config keys candidates, search_arms, search_seed, rules - the control is not a candidate."""
    return L.stage_select(ctx)


def test_readout(ctx: L.Ctx35, store, cand: str, arm: str, seed: int, ls: bool) -> dict:
    """Reuse the search weights (same run, final step), add the P15-08 test readout."""
    d = sdir(ctx, cand, arm, seed, ls, "test")
    if (d / "DONE.json").exists():
        return json.loads((d / "result.json").read_text(encoding="utf-8"))
    src = sdir(ctx, cand, arm, seed, ls)
    d.mkdir(parents=True, exist_ok=True)
    for f in ("final.pt", "best.pt", "metrics.jsonl", "licence.json", "config.json"):
        if (src / f).exists():
            shutil.copy(src / f, d / f)
    sr = json.loads((src / "result.json").read_text(encoding="utf-8"))
    rec = run_recipe(ctx, cand)
    model = p33.init_model(ctx.c33, store, rec, arm, seed)
    model.load_state_dict(torch.load(d / "final.pt", map_location=ctx.c33.device, weights_only=True)["model"])
    sub, _ = L.subset_targets(ctx, store, seed, ls)
    L.log(ctx, f"[{cand}/{R8.run_name(arm, ctx.cfg['budget'], seed, ls)}] reuse search weights for the test readout")
    res = p33.finish_run(ctx.c33, store, rec, arm, ctx.cfg["budget"], seed, ls, d, True, model,
                         {"cer": sr["best_val_cer"], "step": sr["best_val_step"]}, sr["skipped"], sub)
    res["val_shuffled_cer_final"] = sr.get("val_shuffled_cer_final")
    res["val_cer_final"] = sr["val_cer_final"]
    e1.save_json(res, d / "result.json")
    return res


def stage_test(ctx: L.Ctx35, store, sel: dict) -> None:
    seed = int(ctx.cfg["search_seed"])
    for arm in sel["passing_arms"]:
        for ls in (False, True):
            test_readout(ctx, store, sel["selected"], arm, seed, ls)


def stage_control(ctx: L.Ctx35, store, pool) -> str:
    """Descriptive: recipe A at the long schedule, no synthetic items. Val only; deranged run if eligible.
    Never selectable; no test readout."""
    seed = int(ctx.cfg["search_seed"])
    for cid in ctx.cfg["control"]:
        for arm in ctx.cfg["search_arms"]:
            r = train_b(ctx, store, pool, cid, arm, seed, False, sdir(ctx, cid, arm, seed, False, "control"), False)
            if r.get("partial"):
                return "partial"
            if eligible(ctx, r):
                r2 = train_b(ctx, store, pool, cid, arm, seed, True, sdir(ctx, cid, arm, seed, True, "control"), False)
                if r2.get("partial"):
                    return "partial"
    return "done"


def stage_seed1(ctx: L.Ctx35, store, pool, sel: dict) -> str:
    seed = int(ctx.cfg["descriptive_seed"])
    if L.clock_hours(ctx) > float(ctx.cfg["seed1_start_max_hours"]) and not (ctx.out / "seed1").exists():
        L.log(ctx, f"[seed1] skipped: GPU clock {L.clock_hours(ctx):.2f} h > {ctx.cfg['seed1_start_max_hours']} h")
        return "skipped"
    for arm in sel["passing_arms"]:
        for ls in (False, True):
            r = train_b(ctx, store, pool, sel["selected"], arm, seed, ls,
                        sdir(ctx, sel["selected"], arm, seed, ls, "seed1"), True)
            if r.get("partial"):
                return "partial"
    return "done"


def val_curve(d: Path, every: int = 500) -> dict:
    p = d / "metrics.jsonl"
    if not p.exists():
        return {}
    out = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln:
            m = json.loads(ln)
            if m["step"] % every == 0:
                out[str(m["step"])] = m["val_cer"]
    return out


def stage_summary(ctx: L.Ctx35, sel: dict, control_status: str, seed1_status: str) -> dict:
    rules = ctx.cfg["rules"]
    keys = ("run", "recipe", "arm", "budget", "seed", "label_shuffle", "steps", "skipped", "n_train", "minutes",
            "trainable_params", "val_cer_final", "val_shuffled_cer_final", "best_val_step", "best_val_cer",
            "test_cer_final", "test_cer_bestval", "c1_shuffled_cer")

    def load(part: str, sid: str, arm: str, seed: int, ls: bool) -> dict | None:
        p = sdir(ctx, sid, arm, seed, ls, part) / "result.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def c2_rows(part: str, seed: int) -> list[dict]:
        out = []
        for arm in sel.get("passing_arms", []):
            n, dr = load(part, sel["selected"], arm, seed, False), load(part, sel["selected"], arm, seed, True)
            if n and dr:
                need = L.c2_need(rules, n["test_cer_final"])
                out.append({"arm": arm, "seed": seed, "normal_test_cer": n["test_cer_final"],
                            "deranged_test_cer": dr["test_cer_final"], "needed": need,
                            "pass": bool(dr["test_cer_final"] >= need),
                            "normal_test_cer_bestval": n.get("test_cer_bestval"),
                            "time_shuffled_test_cer": n.get("c1_shuffled_cer")})
        return out

    def runs(part: str, ids) -> list[dict]:
        rows = []
        for sid in ids:
            for arm in ctx.cfg["search_arms"]:
                for ls in (False, True):
                    r = load(part, sid, arm, int(ctx.cfg["search_seed"]), ls)
                    if r:
                        row = {k: r[k] for k in keys if k in r}
                        row["spec"] = sid
                        row["val_curve_every_500"] = val_curve(sdir(ctx, sid, arm, int(ctx.cfg["search_seed"]), ls, part))
                        rows.append(row)
        return rows

    libs = {}
    for p in sorted((ctx.out / "libraries").glob("*.npz")):
        libs[p.stem] = json.loads(str(np.load(p, allow_pickle=False)["stats"]))
        libs[p.stem].pop("aligner", None)
    c2_test = c2_rows("test", int(ctx.cfg["search_seed"]))
    agg = {"note": "aggregate only; CER = total edits / total reference characters; val = 106 val sentences, test = 80 "
                   "test sentences (last block of each session); greedy CTC, no LM, final step; plan.md",
           "selection": sel, "search_runs": runs("search", ctx.cfg["candidates"]),
           "control_status": control_status, "control_runs": runs("control", ctx.cfg["control"]),
           "libraries": libs, "C2_test": c2_test, "C2_test_any_pass": bool(any(r["pass"] for r in c2_test)),
           "seed1_status": seed1_status, "C2_seed1_descriptive": c2_rows("seed1", int(ctx.cfg["descriptive_seed"])),
           "gpu_hours": round(L.clock_hours(ctx), 3), "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    e1.save_json(agg, ctx.out / "summary.json")
    if ctx.repo_results is not None:
        ctx.repo_results.mkdir(parents=True, exist_ok=True)
        e1.save_json(agg, ctx.repo_results / "summary.json")
    L.log(ctx, f"[summary] C2 test {[(r['arm'], r['pass']) for r in c2_test]} gpu_h {agg['gpu_hours']}")
    return agg


def smoke(ctx: L.Ctx35, store, pool, steps: int) -> None:
    """Code and speed check only: ``steps`` training steps per candidate and the control, no val, no test, no
    CER. Writes to <out>/smoke and deletes the run folders afterwards (libraries are kept)."""
    seed = int(ctx.cfg["search_seed"])
    for sid in all_specs(ctx.cfg):
        d = ctx.out / "smoke" / sid
        t0 = time.time()
        r = train_b(ctx, store, pool, sid, "E", seed, False, d, False, max_steps=steps)
        torch.cuda.synchronize() if torch.cuda.is_available() else None
        mem = torch.cuda.max_memory_allocated() / 2 ** 30 if torch.cuda.is_available() else 0.0
        L.log(ctx, f"[smoke] {sid}: {steps} steps in {time.time() - t0:.1f} s (incl. setup) partial={r.get('partial')} "
                   f"peak GPU mem {mem:.2f} GiB")
        torch.cuda.reset_peak_memory_stats() if torch.cuda.is_available() else None
    shutil.rmtree(ctx.out / "smoke", ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P15-35b runner")
    ap.add_argument("stage", choices=("all", "textpool", "summary", "smoke"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--smoke-steps", type=int, default=30)
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    for f in FORBIDDEN:
        if out == f.resolve() or f.resolve() in out.parents:
            print(f"never write into {f}", file=sys.stderr)
            return 2
    out.mkdir(parents=True, exist_ok=True)
    ctx = make_ctx(Path(a.config), out, a.device)
    torch.set_num_threads(2)
    L.log(ctx, f"start stage={a.stage} device={a.device} torch={torch.__version__} pid={os.getpid()}")
    L.clock_start(ctx)
    R8.keep_awake(True)
    try:
        pool = stage_textpool(ctx)
        if a.stage == "textpool":
            return 0
        store = R8.WillettStore(ctx.c33.cache)
        if a.stage == "smoke":
            smoke(ctx, store, pool, a.smoke_steps)
            return 0
        if a.stage == "summary":
            sel = stage_select(ctx)
            stage_summary(ctx, sel, "unknown", "unknown")
            return 0
        if not stage_search(ctx, store, pool):
            return 0
        sel = stage_select(ctx)
        if sel["selected"] is not None:
            stage_test(ctx, store, sel)
        else:
            L.log(ctx, "[select] no candidate passes val-C2 with the margin: no test readout (plan.md)")
        cs = stage_control(ctx, store, pool)
        if cs == "partial":
            return 0
        if sel["selected"] is None:
            stage_summary(ctx, sel, cs, "not_run")
            (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " no_recipe", encoding="utf-8")
            L.log(ctx, "ALL DONE (no_recipe)")
            return 0
        s1 = stage_seed1(ctx, store, pool, sel)
        if s1 == "partial":
            return 0
        stage_summary(ctx, sel, cs, s1)
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
        L.log(ctx, "ALL DONE")
    except p33.Paused:
        L.clock_save(ctx)
        return PAUSED
    except L.CapReached:
        L.clock_save(ctx)
        L.log(ctx, f"GPU cap {ctx.cfg['gpu_cap_hours']} h reached: stop (plan.md)")
        try:
            sel = stage_select(ctx) if (ctx.out / "selection.json").exists() else {"selected": None, "passing_arms": []}
            stage_summary(ctx, sel, "cap", "cap")
        except Exception as ex:  # noqa: BLE001 - summary is best effort at the cap
            L.log(ctx, f"summary at cap failed: {ex!r}")
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " cap", encoding="utf-8")
        return 0
    finally:
        L.clock_save(ctx)
        R8.keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
