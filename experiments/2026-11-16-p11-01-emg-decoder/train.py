r"""P11-01 training, evaluation and NTS export (our own code, Apache-2.0).

Stages (``all`` runs them in order and skips finished ones; every stage resumes exactly):
  budget    GPU pilot (200 steps, not kept) -> budget.json (generic step count; rule in plan.md)
  generic   user-generic model on the 100 generic-train users; selection on generic_val (CER)
  personal  for each of the 8 test users: fine-tune the best generic model on the user's train
            sessions; selection on the user's 2 val sessions
  eval      generic and personalised models on the test sessions (once), time-shuffle control,
            emission delay -> results.json (aggregate only) + per_user_local.json (never commit)
  nts       personalised test log-probs -> one NTS stream per text prompt, conformance check

Run (repo root, GPU venv):
  C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-16-p11-01-emg-decoder\train.py all
Files: --out (default C:\Users\zhang\bci-data\derived\p11-01-emg-decoder\train). A file ``pause``
or ``stop`` in --out makes the job save ``latest.pt`` after the current step and exit (code 3).
Checkpoints: every ``ckpt_minutes`` and at each validation. Batch k and all random draws of step k
depend only on (seed, k), so a resume from ``latest.pt`` repeats the same run.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import emgdec as E  # noqa: E402

CACHE = Path(r"C:\Users\zhang\bci-data\derived\p11-01-emg-decoder")
PAUSED = 3


class Paused(Exception):
    pass


def keep_awake(on: bool) -> None:
    if os.name == "nt":
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def log(out: Path, msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(out / "train.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def atomic_save(obj: dict, path: Path) -> None:
    tmp = path.with_suffix(".tmp")
    torch.save(obj, tmp)
    os.replace(tmp, path)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def lr_at(step: int, c: E.TrainCfg) -> float:
    if step < c.warmup:
        return c.lr * (step + 1) / c.warmup
    p = min(1.0, (step - c.warmup) / max(1, c.steps - c.warmup))
    return c.lr_min + 0.5 * (c.lr - c.lr_min) * (1 + math.cos(math.pi * p))


def make_optim(model: torch.nn.Module, c: E.TrainCfg) -> torch.optim.Optimizer:
    decay, no_decay = [], []
    for n, p in model.named_parameters():
        (no_decay if p.ndim < 2 or "norm" in n else decay).append(p)
    return torch.optim.AdamW([{"params": decay, "weight_decay": c.weight_decay},
                              {"params": no_decay, "weight_decay": 0.0}], lr=c.lr)


def stop_requested(out: Path) -> bool:
    return (out / "pause").exists() or (out / "stop").exists()


def evaluate(model: E.CRT, store: E.SessionStore, sessions: list[str], device: str) -> dict:
    errs = [E.session_errors(E.session_log_probs(model, store.feat(s), device), store.lab(s)) for s in sessions]
    return {"cer": E.cer(errs), "prompt_cer": E.cer(errs, "prompt_"), "ref": sum(e["ref"] for e in errs)}


def train_stage(name: str, out: Path, store: E.SessionStore, c: E.TrainCfg, train_s: list[str], val_s: list[str],
                device: str, init: Path | None = None, max_steps: int | None = None) -> dict:
    """Train one stage to ``c.steps`` (or pause). Returns the DONE record."""
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    if (d / "DONE.json").exists():
        return json.loads((d / "DONE.json").read_text(encoding="utf-8"))
    torch.manual_seed(c.seed)
    model = E.CRT(c.model, store.mean, store.std).to(device)
    opt = make_optim(model, c)
    step, best = 0, {"cer": float("inf"), "step": -1}
    if (d / "latest.pt").exists():
        ck = torch.load(d / "latest.pt", map_location=device, weights_only=True)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"])
        step, best = int(ck["step"]), {"cer": float(ck["best_cer"]), "step": int(ck["best_step"])}
        log(out, f"[{name}] resume at step {step} (best cer {best['cer']:.4f} at {best['step']})")
    elif init is not None:
        model.load_state_dict(torch.load(init, map_location=device, weights_only=True)["model"])
        log(out, f"[{name}] init from {init}")
    (d / "config.json").write_text(json.dumps(c.to_json(), indent=1), encoding="utf-8")

    def save_latest() -> None:
        atomic_save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step,
                     "best_cer": best["cer"], "best_step": best["step"]}, d / "latest.pt")

    sampler = E.WindowSampler(store, train_s, c.window, c.batch, c.aug.jitter, c.seed)
    pf = E.Prefetcher(sampler, step)
    amp = torch.autocast(device_type="cuda", dtype=torch.bfloat16) if (c.amp == "bf16" and device != "cpu") else None
    t_ck = time.time(); t_log = time.time(); s_log = step; losses: list[float] = []; skipped = 0
    end = c.steps if max_steps is None else min(c.steps, step + max_steps)
    try:
        while step < end:
            torch.manual_seed(c.seed * 1_000_003 + step)
            gen = torch.Generator().manual_seed(c.seed * 1_000_003 + step)
            b = pf.get(step)
            model.train()
            for g in opt.param_groups:
                g["lr"] = lr_at(step, c)
            x = torch.from_numpy(b["x"]).to(device, non_blocking=True)
            x = E.augment(model.normalise(x), c.aug, gen)
            if amp is not None:
                with amp:
                    lp = model(x, normalised=True)
            else:
                lp = model(x, normalised=True)
            B, T = lp.shape[:2]
            loss = F.ctc_loss(lp.transpose(0, 1).float(), torch.from_numpy(b["targets"]).to(device),
                              torch.full((B,), T, dtype=torch.long),  # lengths stay on the CPU (ROCm bug)
                              torch.from_numpy(b["target_lengths"]), blank=E.BLANK, reduction="mean",
                              zero_infinity=True)
            opt.zero_grad(set_to_none=True)
            if torch.isfinite(loss):
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), c.clip)
                opt.step()
                losses.append(float(loss.detach()))
            else:
                skipped += 1
            step += 1
            if step % 100 == 0 or step == end:
                dt = (time.time() - t_log) / max(1, step - s_log); t_log = time.time(); s_log = step
                log(out, f"[{name}] step {step}/{c.steps} loss {np.mean(losses) if losses else float('nan'):.4f} "
                         f"lr {lr_at(step - 1, c):.2e} {dt:.3f} s/step skipped {skipped}")
                losses = []
            if step % c.val_every == 0 or step == c.steps:
                v = evaluate(model, store, val_s, device)
                rec = {"stage": name, "step": step, **v, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
                with open(d / "metrics.jsonl", "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec) + "\n")
                if v["cer"] < best["cer"]:
                    best = {"cer": v["cer"], "step": step}
                    atomic_save({"model": model.state_dict(), "step": step, "val_cer": v["cer"]}, d / "best.pt")
                log(out, f"[{name}] val step {step}: cer {v['cer']:.4f} prompt_cer {v['prompt_cer']:.4f} (best {best['cer']:.4f} @ {best['step']})")
                save_latest(); t_ck = time.time()
            elif time.time() - t_ck > 60 * c.ckpt_minutes:
                save_latest(); t_ck = time.time()
            if stop_requested(out):
                save_latest()
                log(out, f"[{name}] pause/stop file: saved latest.pt at step {step}, exit")
                raise Paused()
    finally:
        pf.close()
    if step < c.steps:  # max_steps reached (pilot / smoke)
        save_latest()
        return {"stage": name, "partial": True, "step": step}
    rec = {"stage": name, "steps": step, "best_step": best["step"], "best_val_cer": best["cer"], "skipped": skipped}
    (d / "DONE.json").write_text(json.dumps(rec), encoding="utf-8")
    log(out, f"[{name}] DONE {rec}")
    return rec


def load_cfgs(path: Path) -> tuple[dict, E.TrainCfg, E.TrainCfg]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw, E.TrainCfg.from_json(raw["generic"]), E.TrainCfg.from_json(raw["personal"])


def stage_budget(out: Path, store: E.SessionStore, raw: dict, g: E.TrainCfg, splits: dict, device: str,
                 pilot_steps: int = 200, warm_steps: int = 20) -> dict:
    """Fix the generic step count and the conv implementation once (plan.md rule). Stored in budget.json.

    Both conv implementations compute the same function with the same parameters; the faster one is used.
    """
    bp = out / "budget.json"
    if bp.exists():
        return json.loads(bp.read_text(encoding="utf-8"))
    import shutil
    pilot_dir = out / "pilot"
    timing = {}
    for impl in ("torch", "shift"):
        pc = E.TrainCfg.from_json(g.to_json()); pc.val_every = 10 ** 9; pc.ckpt_minutes = 10 ** 6
        pc.model.conv_impl = impl
        shutil.rmtree(pilot_dir, ignore_errors=True)
        train_stage("pilot", out, store, pc, splits["generic_train"], [], device, max_steps=warm_steps)  # warm-up
        shutil.rmtree(pilot_dir, ignore_errors=True)
        if device != "cpu":
            torch.cuda.synchronize()
        t = time.time()
        train_stage("pilot", out, store, pc, splits["generic_train"], [], device, max_steps=pilot_steps)
        timing[impl] = (time.time() - t) / pilot_steps
        shutil.rmtree(pilot_dir, ignore_errors=True)
    impl = min(timing, key=timing.get)
    sps = timing[impl]
    hours = float(raw.get("budget_hours_generic", 26.0))
    steps = max(1000, min(g.steps, int(hours * 3600 / sps) // 1000 * 1000))
    rec = {"s_per_step": sps, "s_per_step_by_impl": timing, "conv_impl": impl, "budget_hours": hours,
           "generic_steps": steps, "max_steps": g.steps, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    bp.write_text(json.dumps(rec), encoding="utf-8")
    log(out, f"[budget] {rec}")
    return rec


def emission_delay_ms(lp: np.ndarray, lab: dict) -> list[float]:
    """Per reference key: frames from key-down to the first argmax of the same token within [-0.5 s, +1 s]."""
    a = lp.argmax(axis=1)
    out = []
    for f, t in zip(lab["key_frame"], lab["key_tok"]):
        lo, hi = max(0, int(f) - 50), min(len(a), int(f) + 100)
        hit = np.nonzero(a[lo:hi] == int(t))[0]
        if len(hit):
            out.append((lo + int(hit[0]) - int(f)) * 10.0)
    return out


def stage_eval(out: Path, store: E.SessionStore, splits: dict, device: str, cfg_g: E.TrainCfg, cfg_p: E.TrainCfg) -> dict:
    if (out / "results.json").exists():
        return json.loads((out / "results.json").read_text(encoding="utf-8"))
    res: dict = {"note": "aggregate only; CER = total edits / total reference keys, greedy CTC, no LM"}
    gm = E.CRT(cfg_g.model, store.mean, store.std).to(device)
    gm.load_state_dict(torch.load(out / "generic" / "best.pt", map_location=device, weights_only=True)["model"])
    for part in ("generic_val", "generic_test"):
        res[part] = evaluate(gm, store, splits[part], device)
    per_user, pooled, delays, shuffled = {}, [], [], []
    rng = np.random.default_rng(12345)
    for i, u in enumerate(splits["test_users"]):
        pm = E.CRT(cfg_p.model, store.mean, store.std).to(device)
        pm.load_state_dict(torch.load(out / f"personal-u{i}" / "best.pt", map_location=device, weights_only=True)["model"])
        errs = []
        for s in splits["personal"][u]["test"]:
            lp = E.session_log_probs(pm, store.feat(s), device)
            errs.append(E.session_errors(lp, store.lab(s)))
            delays += emission_delay_ms(lp, store.lab(s))
            f = np.asarray(store.feat(s))
            lp_sh = E.session_log_probs(pm, f[rng.permutation(len(f))], device)
            shuffled.append(E.session_errors(lp_sh, store.lab(s)))
        pooled += errs
        per_user[f"u{i}"] = {"cer": E.cer(errs), "prompt_cer": E.cer(errs, "prompt_")}
    res["personal_test"] = {"cer_pooled": E.cer(pooled), "prompt_cer_pooled": E.cer(pooled, "prompt_"),
                            "cer_mean_over_users": float(np.mean([v["cer"] for v in per_user.values()])),
                            "ref": sum(e["ref"] for e in pooled)}
    res["control_time_shuffled"] = {"cer_pooled": E.cer(shuffled)}
    res["emission_delay_ms"] = {"median": float(np.median(delays)) if delays else None,
                                "p90": float(np.percentile(delays, 90)) if delays else None, "n": len(delays)}
    gm_errs_by_user = {}
    for i, u in enumerate(splits["test_users"]):
        e = [E.session_errors(E.session_log_probs(gm, store.feat(s), device), store.lab(s)) for s in splits["personal"][u]["test"]]
        gm_errs_by_user[f"u{i}"] = E.cer(e)
    res["generic_test"]["cer_mean_over_users"] = float(np.mean(list(gm_errs_by_user.values())))
    (out / "per_user_local.json").write_text(json.dumps({"personal": per_user, "generic": gm_errs_by_user}, indent=1),
                                             encoding="utf-8")
    (out / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    log(out, f"[eval] {json.dumps(res)}")
    return res


def stage_nts(out: Path, store: E.SessionStore, splits: dict, device: str, cfg_p: E.TrainCfg, level: str = "trust-ready") -> dict:
    if (out / "nts" / "DONE.json").exists():
        return json.loads((out / "nts" / "DONE.json").read_text(encoding="utf-8"))
    from fidetype.conformance import check_file
    from fidetype.conformance.io import write_jsonl
    n = ok = 0
    for i, u in enumerate(splits["test_users"]):
        w = out / f"personal-u{i}" / "best.pt"
        pm = E.CRT(cfg_p.model, store.mean, store.std).to(device)
        pm.load_state_dict(torch.load(w, map_location=device, weights_only=True)["model"])
        sha = sha256_file(w)
        for j, s in enumerate(splits["personal"][u]["test"]):
            lp = E.session_log_probs(pm, store.feat(s), device)
            d = out / "nts" / f"u{i}-s{j}"
            d.mkdir(parents=True, exist_ok=True)
            for k, st in E.prompt_streams(lp, store.lab(s), store.vocab, sha, "1", f"{s}|u{i}"):
                p = d / f"p{k:03d}.jsonl"
                write_jsonl(st, p)
                n += 1
                ok += not check_file(p).failures(level)
    rec = {"streams": n, "level": level, "pass": ok}
    (out / "nts" / "DONE.json").write_text(json.dumps(rec), encoding="utf-8")
    log(out, f"[nts] {rec}")
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P11-01 EMG decoder training")
    ap.add_argument("stage", choices=("all", "budget", "generic", "personal", "eval", "nts"))
    ap.add_argument("--cache", default=str(CACHE))
    ap.add_argument("--out", default=str(CACHE / "train"))
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--max-steps", type=int, default=None, help="smoke tests only: stop a stage after N steps")
    ap.add_argument("--no-budget", action="store_true", help="skip the GPU pilot; use config steps (smoke tests)")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    store = E.SessionStore(a.cache)
    splits = json.loads((Path(a.cache) / "splits.json").read_text(encoding="utf-8"))
    raw, g, p = load_cfgs(Path(a.config))
    log(out, f"start stage={a.stage} device={a.device} torch={torch.__version__}")
    keep_awake(True)
    try:
        if a.stage in ("all", "budget", "generic", "personal", "eval", "nts") and not a.no_budget:
            if a.stage in ("all", "budget", "generic") or (out / "budget.json").exists():
                b = stage_budget(out, store, raw, g, splits, a.device)
                g.steps = int(b["generic_steps"])
                g.model.conv_impl = p.model.conv_impl = b.get("conv_impl", "torch")
        if a.stage == "budget":
            return 0
        if a.stage in ("all", "generic"):
            r = train_stage("generic", out, store, g, splits["generic_train"], splits["generic_val"], a.device,
                            max_steps=a.max_steps)
            if r.get("partial"):
                return 0
        if a.stage in ("all", "personal"):
            for i, u in enumerate(splits["test_users"]):
                ps = splits["personal"][u]
                r = train_stage(f"personal-u{i}", out, store, p, ps["train"], ps["val"], a.device,
                                init=out / "generic" / "best.pt", max_steps=a.max_steps)
                if r.get("partial"):
                    return 0
        if a.stage in ("all", "eval"):
            stage_eval(out, store, splits, a.device, g, p)
        if a.stage in ("all", "nts"):
            stage_nts(out, store, splits, a.device, p)
        if a.stage == "all":
            (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
            log(out, "ALL DONE")
    except Paused:
        return PAUSED
    finally:
        keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
