"""Train the ConvCTC decoder on the MEG cache.

Usage (GPU env)::

    python -m fidetype.decoders.train --config experiments/<exp>/config.json
    python -m fidetype.decoders.train --run-dir <runs>/<run_name> --resume

The run directory (``<runs_dir>/<run_name>``) gets:

- ``config.json``: the full config (and the subject map).
- ``latest.pt``: model, optimizer, scheduler, epoch/step, RNG states.
  It is written every ``ckpt_every_min`` minutes and at each epoch end.
- ``best.pt``: the model with the best validation metric.
- ``metrics.jsonl``: one JSON object per log event.
- ``train.log``: human-readable log.
- ``status.json``: state, PID, epoch, step and best metric.

Config keys added for M1-C:

- ``data.blocks``: list of block ids (``"S1/ses1_block2"``). It pins a run
  to a fixed set of blocks while the cache still grows.
- ``model.aux_keystroke_weight`` (and the other ``aux_key_*`` keys): the
  keystroke auxiliary loss (see :mod:`fidetype.decoders.conv_ctc`).
- ``train.init_from``: a checkpoint. Its weights (with matching names and
  shapes) initialise a new run, for example after keystroke pretraining.
- ``train.early_stop_metric`` can also be ``"val_key_err"`` (1 - keystroke
  head accuracy on val).

Long runs must be detached (see ``experiments/2026-11-08-m1b-decoder/launch.ps1``).
"""

from __future__ import annotations

import argparse
import copy
import functools
import json
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

# MIOpen (ROCm) searches conv kernels for each new shape. FAST mode skips
# the long search. Set it before the first conv runs.
os.environ.setdefault("MIOPEN_FIND_MODE", "FAST")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

import torch  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402

from fidetype.decoders.conv_ctc import ConvCTC, ModelConfig, format_param_report, greedy_decode_batch
from fidetype.decoders.dataset import BucketBatchSampler, MEGSegments, augment_from_dict, collate
from fidetype.eval.metrics import cer, wer
from fidetype.utils.power import ActiveTimer, keep_awake

DEFAULT_RUNS_DIR = "C:/Users/zhang/bci-data/runs"
SUSPEND_GAP_S = 300.0  # a gap between steps longer than this is a suspend: not counted in max_minutes

DEFAULT_CONFIG: dict[str, Any] = {
    "run_name": "debug",
    "runs_dir": DEFAULT_RUNS_DIR,
    "data": {
        "root": "C:/Users/zhang/bci-data/cache/spanishbcbl/v1",
        "subjects": None,
        "blocks": None,
        "mmap_dir": None,
        "train_splits": ["train"],
        "val_splits": ["val"],
        "batch_size": 16,
        "eval_batch_size": 16,
        "num_workers": 0,
        "pad_multiple": 100,
        "augment": {},
        "max_train_segments": None,
    },
    "model": {},
    "optim": {
        "lr": 5e-4,
        "weight_decay": 0.05,
        "betas": [0.9, 0.98],
        "warmup_steps": 300,
        "min_lr_ratio": 0.02,
        "grad_clip": 1.0,
        "epochs": 100,
    },
    "train": {
        "seed": 0,
        "device": "cuda",
        "bf16": True,
        "ckpt_every_min": 5.0,
        "eval_every_epochs": 1,
        "patience_evals": 15,
        "early_stop_metric": "val_cer_typed",
        "log_every_steps": 25,
        "max_minutes": None,
        "deterministic": False,
        "torch_threads": 4,
        "init_from": None,
    },
}


def merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k != "model" and k != "augment":
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def rng_state() -> dict[str, Any]:
    st = {"python": random.getstate(), "numpy": np.random.get_state(), "torch": torch.get_rng_state()}
    if torch.cuda.is_available():
        st["cuda"] = torch.cuda.get_rng_state_all()
    return st


def set_rng_state(st: dict[str, Any]) -> None:
    random.setstate(st["python"])
    np.random.set_state(st["numpy"])
    torch.set_rng_state(st["torch"])
    if "cuda" in st and torch.cuda.is_available():
        try:
            torch.cuda.set_rng_state_all(st["cuda"])
        except Exception:  # noqa: BLE001 - other GPU count; not fatal
            pass


def lr_lambda(warmup: int, total: int, min_ratio: float):
    def f(step: int) -> float:
        if step < warmup:
            return (step + 1) / max(1, warmup)
        p = min(1.0, (step - warmup) / max(1, total - warmup))
        return min_ratio + (1 - min_ratio) * 0.5 * (1 + math.cos(math.pi * p))

    return f


def atomic_save(obj: Any, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save(obj, tmp)
    os.replace(tmp, path)


class Logger:
    def __init__(self, run_dir: Path, echo: bool = True) -> None:
        self.text = open(run_dir / "train.log", "a", encoding="utf-8")
        self.jsonl = open(run_dir / "metrics.jsonl", "a", encoding="utf-8")
        self.echo = echo

    def log(self, msg: str) -> None:
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        self.text.write(line + "\n")
        self.text.flush()
        if self.echo:
            print(line, flush=True)

    def metrics(self, rec: dict[str, Any]) -> None:
        rec = {"time": time.time(), **rec}
        self.jsonl.write(json.dumps(rec) + "\n")
        self.jsonl.flush()

    def close(self) -> None:
        self.text.close()
        self.jsonl.close()


@torch.no_grad()
def evaluate(model: ConvCTC, ds: MEGSegments, cfg: dict[str, Any], device: torch.device,
             use_bf16: bool) -> dict[str, Any]:
    """Greedy-CTC CER/WER on ``ds``: mean over subjects and over sentences."""
    model.eval()
    sampler = BucketBatchSampler(ds.lengths(), cfg["data"]["eval_batch_size"], shuffle=False)
    # Own generator: building a DataLoader iterator must not use the global RNG.
    coll = functools.partial(collate, pad_multiple=cfg["data"].get("pad_multiple", 1))
    dl = DataLoader(ds, batch_sampler=sampler, collate_fn=coll, num_workers=0,
                    generator=torch.Generator().manual_seed(0))
    per_subj: dict[int, list[tuple[float, float, float, float]]] = {}
    losses, ctc_losses = [], []
    key_hits: dict[str, float] = {}
    key_n, key_ce = 0.0, []
    for batch in dl:
        x = batch["x"].to(device, non_blocking=True)
        lengths = batch["lengths"].to(device)
        subj = batch["subjects"].to(device)
        with torch.autocast(device.type, dtype=torch.bfloat16, enabled=use_bf16):
            out = model(x, lengths, subj)
        ls = model.loss(out, batch["targets"].to(device), batch["target_lengths"].to(device),
                        *key_args(batch, device))
        losses.append(float(ls["loss"]))
        w = model.cfg.aux_weight
        ctc_losses.append(float((1 - w) * ls["ctc_final"] + w * ls["ctc_aux"]))
        if "key_n" in ls:
            key_n += float(ls["key_n"])
            key_ce.append(float(ls["key_ce"]) * float(ls["key_n"]))
            for k, v in ls.items():
                if k.startswith("key_correct_"):
                    key_hits[k[len("key_correct_"):]] = key_hits.get(k[len("key_correct_"):], 0.0) + float(v)
        hyps = greedy_decode_batch(out["logits"].float(), out["out_lengths"])
        for s, h, tgt, typ in zip(batch["subjects"].tolist(), hyps, batch["target_text"], batch["typed_text"]):
            per_subj.setdefault(s, []).append((cer(typ, h), cer(tgt, h), wer(typ, h), wer(tgt, h)))
    model.train()
    if not per_subj:
        return {}
    keys = ["cer_typed", "cer_target", "wer_typed", "wer_target"]
    subj_means = {s: np.mean(np.array(v), axis=0) for s, v in per_subj.items()}
    allv = np.concatenate([np.array(v) for v in per_subj.values()])
    res: dict[str, Any] = {"val_loss": float(np.mean(losses)), "val_ctc": float(np.mean(ctc_losses)),
                           "n": int(len(allv))}
    if key_n > 0:
        res["val_key_n"] = int(key_n)
        res["val_key_ce"] = float(sum(key_ce) / key_n)
        for name, h in key_hits.items():
            res[f"val_key_acc_{name}"] = h / key_n
        res["val_key_acc"] = max(h / key_n for h in key_hits.values())
        res["val_key_err"] = 1.0 - res["val_key_acc"]
    for i, k in enumerate(keys):
        res[f"val_{k}"] = float(np.mean([m[i] for m in subj_means.values()]))
        res[f"val_{k}_micro"] = float(allv[:, i].mean())
    res["val_cer_typed_per_subject"] = {int(s): float(m[0]) for s, m in subj_means.items()}
    return res


def key_args(batch: dict[str, Any], device: torch.device) -> tuple[torch.Tensor, ...]:
    """Return (key_samples, key_labels) on ``device``, or () if the batch has none."""
    if "key_samples" not in batch:
        return ()
    return batch["key_samples"].to(device), batch["key_labels"].to(device)


def build_datasets(cfg: dict[str, Any], subject_map: dict[str, int] | None):
    d = cfg["data"]
    seed = cfg["train"]["seed"]
    train_ds = MEGSegments(d["root"], d["train_splits"], d["subjects"], subject_map,
                           augment_from_dict(d.get("augment", {})), seed, d.get("mmap_dir"),
                           max_segments=d.get("max_train_segments"), blocks=d.get("blocks"))
    val_ds = MEGSegments(d["root"], d["val_splits"], d["subjects"], train_ds.subject_map, None, seed,
                         d.get("mmap_dir"), blocks=d.get("blocks"))
    return train_ds, val_ds


def init_weights_from(model: ConvCTC, path: str | Path) -> tuple[list[str], list[str]]:
    """Copy the weights with the same name and shape from checkpoint ``path``.

    Returns (loaded names, skipped names).
    """
    src = torch.load(path, map_location="cpu", weights_only=False)["model"]
    own = model.state_dict()
    ok = {k: v for k, v in src.items() if k in own and own[k].shape == v.shape}
    own.update(ok)
    model.load_state_dict(own)
    return sorted(ok), sorted(k for k in own if k not in ok)


def _train(keep_awake_on: bool, cfg: dict[str, Any], run_dir: str | Path | None = None, resume: bool = False,
          max_steps: int | None = None, echo: bool = True) -> dict[str, Any]:
    """Train (or resume) a run. Returns a summary dict.

    ``max_steps`` stops after that global step (a checkpoint is saved).
    Tests use it to check the resume.
    """
    run_dir = Path(run_dir) if run_dir is not None else Path(cfg["runs_dir"]) / cfg["run_name"]
    run_dir.mkdir(parents=True, exist_ok=True)
    latest = run_dir / "latest.pt"
    ckpt = None
    if resume and latest.exists():
        ckpt = torch.load(latest, map_location="cpu", weights_only=False)
        cfg = merge(ckpt["config"], {"train": {k: v for k, v in cfg["train"].items()
                                               if k in ("max_minutes", "device")}})
    cfg = merge(DEFAULT_CONFIG, cfg)
    log = Logger(run_dir, echo)
    tcfg, ocfg = cfg["train"], cfg["optim"]
    set_seed(tcfg["seed"])
    if tcfg.get("deterministic"):
        torch.use_deterministic_algorithms(True, warn_only=True)
    device = torch.device(tcfg["device"] if (tcfg["device"] != "cuda" or torch.cuda.is_available()) else "cpu")
    use_bf16 = bool(tcfg["bf16"]) and device.type == "cuda"
    if device.type == "cuda" and tcfg.get("torch_threads"):
        torch.set_num_threads(int(tcfg["torch_threads"]))  # GPU runs need little CPU

    subject_map = ckpt["subject_map"] if ckpt is not None else None
    train_ds, val_ds = build_datasets(cfg, subject_map)
    subject_map = train_ds.subject_map
    mcfg = ModelConfig.from_dict({**cfg["model"], "n_subjects": max(1, len(subject_map))})
    model = ConvCTC(mcfg).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=ocfg["lr"], betas=tuple(ocfg["betas"]),
                            weight_decay=ocfg["weight_decay"])
    sampler = BucketBatchSampler(train_ds.lengths(), cfg["data"]["batch_size"], seed=tcfg["seed"])
    steps_per_epoch = len(sampler.batches())
    total_steps = steps_per_epoch * ocfg["epochs"]
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lr_lambda(ocfg["warmup_steps"], total_steps, ocfg["min_lr_ratio"]))

    state = {"epoch": 0, "step_in_epoch": 0, "global_step": 0, "best": float("inf"), "best_epoch": -1,
             "bad_evals": 0, "done": False, "active_s": 0.0}
    if ckpt is None and tcfg.get("init_from"):
        loaded, skipped = init_weights_from(model, tcfg["init_from"])
        log.log(f"init_from {tcfg['init_from']}: {len(loaded)} tensors loaded, skipped {skipped}")
    if ckpt is not None:
        model.load_state_dict(ckpt["model"])
        opt.load_state_dict(ckpt["optimizer"])
        sched.load_state_dict(ckpt["scheduler"])
        state.update(ckpt["state"])
        set_rng_state(ckpt["rng"])
        log.log(f"resumed from {latest} at epoch {state['epoch']} step {state['global_step']}")
    else:
        (run_dir / "config.json").write_text(json.dumps({**cfg, "subject_map": subject_map}, indent=2))
        log.log(f"new run {run_dir}")
        log.log("model parameters:\n" + format_param_report(model))
    log.log(f"device={device} bf16={use_bf16} train={len(train_ds)} val={len(val_ds)} "
            f"subjects={len(subject_map)} steps/epoch={steps_per_epoch}")
    log.metrics({"type": "setup", "n_train": len(train_ds), "n_val": len(val_ds),
                 "subjects": subject_map, "params": model.param_count(), "steps_per_epoch": steps_per_epoch})

    def save(path: Path, full: bool = True) -> None:
        obj: dict[str, Any] = {"model": model.state_dict(), "config": cfg, "model_config": mcfg.to_dict(),
                               "subject_map": subject_map, "state": dict(state)}
        if full:
            obj.update(optimizer=opt.state_dict(), scheduler=sched.state_dict(), rng=rng_state())
        atomic_save(obj, path)

    def write_status(status: str) -> None:
        st = {"status": status, "pid": os.getpid(), "run_dir": str(run_dir), "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
              **{k: state[k] for k in ("epoch", "global_step", "best", "best_epoch", "bad_evals")},
              "active_min": round(state.get("active_s", 0.0) / 60, 2),
              "metric": tcfg["early_stop_metric"]}
        (run_dir / "status.json").write_text(json.dumps(st, indent=2))

    last_ckpt = time.time()
    timer = ActiveTimer(state.get("active_s", 0.0), SUSPEND_GAP_S,
                        on_gap=lambda dt: log.log(f"suspend gap detected: {dt:.0f} s not counted "
                                                  f"(gap > {SUSPEND_GAP_S:.0f} s)"))
    log.log(f"keep_awake={'on' if keep_awake_on else 'off'}; active time so far {timer.active_s:.0f} s; "
            f"max_minutes={tcfg.get('max_minutes')} (active compute time)")
    stop_reason = None
    write_status("running")
    model.train()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    while not state["done"] and state["epoch"] < ocfg["epochs"]:
        ep = state["epoch"]
        train_ds.set_epoch(ep)
        sampler.set_epoch(ep, skip=state["step_in_epoch"])
        dl = DataLoader(train_ds, batch_sampler=sampler,
                        collate_fn=functools.partial(collate, pad_multiple=cfg["data"].get("pad_multiple", 1)),
                        num_workers=cfg["data"]["num_workers"], pin_memory=device.type == "cuda",
                        persistent_workers=False,
                        generator=torch.Generator().manual_seed(tcfg["seed"] * 100003 + ep))
        t_ep = time.time()
        run_loss, run_n = 0.0, 0
        for batch in dl:
            x = batch["x"].to(device, non_blocking=True)
            lengths = batch["lengths"].to(device)
            subj = batch["subjects"].to(device)
            with torch.autocast(device.type, dtype=torch.bfloat16, enabled=use_bf16):
                out = model(x, lengths, subj)
            ls = model.loss(out, batch["targets"].to(device), batch["target_lengths"].to(device),
                            *key_args(batch, device))
            opt.zero_grad(set_to_none=True)
            ls["loss"].backward()
            gnorm = torch.nn.utils.clip_grad_norm_(model.parameters(), ocfg["grad_clip"])
            opt.step()
            sched.step()
            state["step_in_epoch"] += 1
            state["global_step"] += 1
            run_loss += float(ls["loss"].detach())
            run_n += 1
            if state["global_step"] % tcfg["log_every_steps"] == 0:
                rec = {"type": "train", "epoch": ep, "step": state["global_step"], "loss": run_loss / run_n,
                       "ctc_final": float(ls["ctc_final"].detach()), "ctc_aux": float(ls["ctc_aux"].detach()),
                       "grad_norm": float(gnorm), "lr": sched.get_last_lr()[0]}
                if "key_ce" in ls:
                    rec["key_ce"] = float(ls["key_ce"].detach())
                    n_k = max(1.0, float(ls["key_n"]))
                    for k, v in ls.items():
                        if k.startswith("key_correct_"):
                            rec["key_acc_" + k[len("key_correct_"):]] = float(v) / n_k
                log.metrics(rec)
                msg = (f"ep {ep} step {state['global_step']} loss {rec['loss']:.4f} "
                       f"(final {rec['ctc_final']:.3f} aux {rec['ctc_aux']:.3f}")
                if "key_ce" in rec:
                    msg += f" key {rec['key_ce']:.3f}"
                log.log(msg + f") lr {rec['lr']:.2e}")
            state["active_s"] = timer.tick()
            if time.time() - last_ckpt > tcfg["ckpt_every_min"] * 60:
                save(latest)
                write_status("running")
                last_ckpt = time.time()
                log.log(f"checkpoint (timer) at step {state['global_step']}")
            if max_steps is not None and state["global_step"] >= max_steps:
                stop_reason = "max_steps"
                break
            mm = tcfg.get("max_minutes")
            if timer.exceeded(mm):
                stop_reason = "max_minutes"
                break
        if stop_reason is not None:
            break
        # End of epoch.
        ep_time = time.time() - t_ep
        state["epoch"] += 1
        state["step_in_epoch"] = 0
        rec: dict[str, Any] = {"type": "epoch", "epoch": ep, "step": state["global_step"],
                               "train_loss": run_loss / max(1, run_n), "epoch_s": ep_time}
        if device.type == "cuda":
            rec["max_mem_gb"] = torch.cuda.max_memory_allocated() / 2**30
        if len(val_ds) and (ep + 1) % tcfg["eval_every_epochs"] == 0:
            ev = evaluate(model, val_ds, cfg, device, use_bf16)
            rec.update(ev)
            metric = ev[tcfg["early_stop_metric"]]
            if metric < state["best"] - 1e-4:
                state["best"], state["best_epoch"], state["bad_evals"] = metric, ep, 0
                save(run_dir / "best.pt", full=False)
            else:
                state["bad_evals"] += 1
            if state["bad_evals"] >= tcfg["patience_evals"]:
                state["done"] = True
                stop_reason = "early_stop"
        log.metrics(rec)
        msg = f"epoch {ep} done in {ep_time:.1f}s train_loss {rec['train_loss']:.4f}"
        if "val_cer_typed" in rec:
            msg += (f" val_loss {rec['val_loss']:.4f} val CER typed {rec['val_cer_typed']:.4f} "
                    f"target {rec['val_cer_target']:.4f} WER typed {rec['val_wer_typed']:.4f} "
                    f"(best {state['best']:.4f} @ {state['best_epoch']})")
        if "val_key_acc" in rec:
            msg += f" val key acc {rec['val_key_acc']:.3f}"
        if "max_mem_gb" in rec:
            msg += f" mem {rec['max_mem_gb']:.2f} GB"
        log.log(msg)
        state["active_s"] = timer.tick()
        save(latest)
        last_ckpt = time.time()
        write_status("running")
    if stop_reason is None:
        stop_reason = "epochs_done"
    if stop_reason in ("max_steps", "max_minutes"):
        save(latest)
    if not (run_dir / "best.pt").exists():
        save(run_dir / "best.pt", full=False)
    final_status = {"max_steps": "stopped", "max_minutes": "stopped", "early_stop": "early_stopped",
                    "epochs_done": "done"}[stop_reason]
    write_status(final_status)
    log.log(f"finished: {stop_reason} at epoch {state['epoch']} step {state['global_step']} "
            f"best {tcfg['early_stop_metric']}={state['best']:.4f} @ epoch {state['best_epoch']}")
    log.close()
    return {"run_dir": str(run_dir), "stop_reason": stop_reason, **state}


def train(cfg: dict[str, Any], run_dir: str | Path | None = None, resume: bool = False,
          max_steps: int | None = None, echo: bool = True) -> dict[str, Any]:
    """Train (or resume) a run while Windows is kept awake. Returns a summary dict.

    ``max_minutes`` counts active compute time (:class:`fidetype.utils.power.ActiveTimer`):
    a gap longer than ``SUSPEND_GAP_S`` between steps (PC sleep) is not counted.
    The total is stored in the checkpoint state (``active_s``), so a resume keeps the budget.
    """
    with keep_awake() as on:
        return _train(on, cfg, run_dir, resume, max_steps, echo)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Train the ConvCTC MEG decoder.")
    p.add_argument("--config", help="JSON config file (merged over the defaults)")
    p.add_argument("--run-dir", help="run directory (default <runs_dir>/<run_name>)")
    p.add_argument("--run-name", help="override run_name")
    p.add_argument("--resume", action="store_true", help="continue from <run_dir>/latest.pt")
    p.add_argument("--max-minutes", type=float, help="stop (with a checkpoint) after this many minutes")
    p.add_argument("--max-steps", type=int)
    a = p.parse_args(argv)
    cfg: dict[str, Any] = {}
    if a.config:
        cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    elif a.run_dir and (Path(a.run_dir) / "config.json").exists():
        cfg = json.loads((Path(a.run_dir) / "config.json").read_text(encoding="utf-8"))
        cfg.pop("subject_map", None)
    cfg = merge(DEFAULT_CONFIG, cfg)
    if a.run_name:
        cfg["run_name"] = a.run_name
    if a.max_minutes is not None:
        cfg["train"]["max_minutes"] = a.max_minutes
    res = train(cfg, a.run_dir, resume=a.resume, max_steps=a.max_steps)
    print(json.dumps(res, indent=2, default=str))
    hard_exit(0)


def hard_exit(code: int = 0) -> None:
    """End the process at once, after flushing stdout and stderr.

    On ROCm/Windows the process can hang at exit and spin one CPU core
    (seen 2026-11-08: finished runs stayed alive for hours). ``sys.exit``
    and ``os._exit`` both call ``ExitProcess``, which runs the DLL detach
    code of the HIP runtime, where the hang is. ``TerminateProcess`` skips
    the DLL detach. Call this only when all files are closed.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
        k32.TerminateProcess.restype = wintypes.BOOL
        k32.TerminateProcess(k32.GetCurrentProcess(), code)
    os._exit(code)


if __name__ == "__main__":
    main()
