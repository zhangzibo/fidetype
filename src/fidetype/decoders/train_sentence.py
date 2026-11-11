"""Train the sentence-context keystroke decoder (M1-15).

Usage (GPU env)::

    python -m fidetype.decoders.train_sentence --config experiments/2026-11-09-m1-15-sentence-context/config.json
    python -m fidetype.decoders.train_sentence --run-dir <runs>/<run_name> --resume

The run directory gets the same files as :mod:`fidetype.decoders.train`:
``config.json``, ``latest.pt`` (every ``ckpt_every_min`` minutes and at each
epoch end; full resume state), ``best.pt``, ``metrics.jsonl``, ``train.log``
and ``status.json``. Long runs must be detached (see the experiment
``launch.ps1``).

Validation metrics (greedy: argmax per key, one key = one character):

- ``val_cer_typed`` / ``val_cer_target``: CER of the greedy key string, mean
  over participants (each person counts once).
- ``val_key_acc`` (final head) and ``val_key_acc_conv`` (per-key head before
  the Transformer: the "Conv only" ablation of Brain2Qwerty v1).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np

os.environ.setdefault("MIOPEN_FIND_MODE", "FAST")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

import torch  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402

from fidetype.decoders.dataset import BucketBatchSampler  # noqa: E402
from fidetype.decoders.sentence_context import (  # noqa: E402
    KeyAugmentConfig,
    KeySentences,
    SentenceContextDecoder,
    SentenceModelConfig,
    collate_sentences,
    greedy_text,
    init_from_convctc,
)
from fidetype.decoders.train import (  # noqa: E402
    DEFAULT_RUNS_DIR,
    SUSPEND_GAP_S,
    Logger,
    atomic_save,
    hard_exit,
    lr_lambda,
    merge,
    rng_state,
    set_rng_state,
    set_seed,
)
from fidetype.eval.metrics import cer, wer  # noqa: E402
from fidetype.utils.power import ActiveTimer, keep_awake  # noqa: E402

DEFAULT_CONFIG: dict[str, Any] = {
    "run_name": "debug-sentence",
    "runs_dir": DEFAULT_RUNS_DIR,
    "data": {
        "root": "C:/Users/zhang/bci-data/cache/spanishbcbl/v1",
        "subjects": None,
        "blocks": None,
        "mmap_dir": None,
        "train_splits": ["train"],
        "val_splits": ["val"],
        "window_s": [-0.2, 0.3],
        "batch_size": 16,
        "eval_batch_size": 32,
        "num_workers": 0,
        "augment": {},
        "max_train_segments": None,
    },
    "model": {},
    "optim": {
        "lr": 3e-4,
        "weight_decay": 0.1,
        "betas": [0.9, 0.98],
        "warmup_steps": 300,
        "min_lr_ratio": 0.02,
        "grad_clip": 1.0,
        "epochs": 150,
        # "cosine" (r1, default): cosine decay over ``epochs``, stop after patience_evals bad evals.
        # "plateau" (opt-in): warm-up, then constant LR, halved on a val plateau; stop on the val trend
        # (see plateau_update). Set ``epochs`` very large to make it effectively unlimited.
        "schedule": "cosine",
        "plateau_patience": 5,
        "plateau_factor": 0.5,
        "min_lr": 1e-5,
        "max_lr_reductions": 3,
    },
    "train": {
        "seed": 0,
        "device": "cuda",
        "bf16": True,
        "ckpt_every_min": 5.0,
        "eval_every_epochs": 1,
        "patience_evals": 20,
        "early_stop_metric": "val_cer_typed",
        "smooth_alpha": 0.3,  # plateau schedule: EMA weight of the newest val value
        "min_delta": 0.002,  # plateau schedule: smallest drop of the smoothed val metric that counts
        "log_every_steps": 25,
        "max_minutes": None,
        "deterministic": False,
        "torch_threads": 4,
        "init_from": None,
    },
}


def build_datasets(cfg: dict[str, Any], subject_map: dict[str, int] | None) -> tuple[KeySentences, KeySentences]:
    d = cfg["data"]
    seed = cfg["train"]["seed"]
    win = tuple(d.get("window_s", [-0.2, 0.3]))
    tr = KeySentences(d["root"], d["train_splits"], d["subjects"], subject_map,
                      KeyAugmentConfig.from_dict(d.get("augment", {})), seed, d.get("mmap_dir"), win,
                      d.get("blocks"), d.get("max_train_segments"))
    va = KeySentences(d["root"], d["val_splits"], d["subjects"], tr.subject_map, None, seed, d.get("mmap_dir"),
                      win, d.get("blocks"))
    return tr, va


def to_device(batch: dict[str, Any], device: torch.device) -> tuple[torch.Tensor, ...]:
    return (batch["x"].to(device, non_blocking=True), batch["key_mask"].to(device),
            batch["subjects"].to(device), batch["key_times"].to(device))


def participant_means(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[str, float]:
    """Mean over participants of the per-participant mean of each key."""
    g: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        g.setdefault(r["participant"], []).append(r)
    return {k: float(np.mean([np.mean([r[k] for r in rs]) for rs in g.values()])) for k in keys}


def plateau_init_state() -> dict[str, Any]:
    """Checkpoint state keys of the "plateau" schedule (also present, unused, for "cosine")."""
    return {"lr_scale": 1.0, "lr_reductions": 0, "plateau_count": 0, "since_improve": 0,
            "smooth": None, "best_smooth": float("inf"), "last_val": None}


def plateau_lr_lambda(warmup: int, state: dict[str, Any]):
    """LR multiplier: linear warm-up, then constant times ``state["lr_scale"]``
    (reduced on a plateau). It reads ``state`` at each step, so a resume that
    restores ``state`` also restores the LR."""

    def f(step: int) -> float:
        w = (step + 1) / max(1, warmup) if step < warmup else 1.0
        return w * float(state["lr_scale"])

    return f


def plateau_update(state: dict[str, Any], metric: float, ocfg: dict[str, Any],
                   tcfg: dict[str, Any]) -> dict[str, Any]:
    """One validation step of the "plateau" schedule (training stops on the val trend).

    - ``smooth``: EMA of the val metric (``train.smooth_alpha``, default 0.3, about a
      5-eval window).
    - An improvement is ``smooth < best_smooth - train.min_delta``. It resets
      ``since_improve`` and ``plateau_count``.
    - After ``optim.plateau_patience`` evals without improvement, the LR scale is
      multiplied by ``optim.plateau_factor`` (floor ``optim.min_lr``). At most
      ``optim.max_lr_reductions`` reductions occur (a cap): after that the LR stays.
    - Stop when ``since_improve >= train.patience_evals`` AND (the LR is at
      ``min_lr`` OR ``lr_reductions >= optim.max_lr_reductions``).

    Mutates ``state``; returns the trend values to log."""
    alpha = float(tcfg.get("smooth_alpha", 0.3))
    min_delta = float(tcfg.get("min_delta", 0.002))
    base_lr = float(ocfg["lr"])
    min_lr = float(ocfg.get("min_lr", 1e-5))
    prev = state["smooth"]
    state["smooth"] = float(metric) if prev is None else alpha * float(metric) + (1 - alpha) * prev
    state["last_val"] = float(metric)
    if state["smooth"] < state["best_smooth"] - min_delta:
        state["best_smooth"], state["since_improve"], state["plateau_count"] = state["smooth"], 0, 0
    else:
        state["since_improve"] += 1
        state["plateau_count"] += 1
    reduced = False
    max_red = int(ocfg.get("max_lr_reductions", 3))
    at_floor = base_lr * state["lr_scale"] <= min_lr * (1 + 1e-9)
    if (state["plateau_count"] >= int(ocfg.get("plateau_patience", 5)) and not at_floor
            and state["lr_reductions"] < max_red):
        state["lr_scale"] = max(state["lr_scale"] * float(ocfg.get("plateau_factor", 0.5)), min_lr / base_lr)
        state["lr_reductions"] += 1
        state["plateau_count"] = 0
        reduced = True
        at_floor = base_lr * state["lr_scale"] <= min_lr * (1 + 1e-9)
    stop = state["since_improve"] >= int(tcfg["patience_evals"]) and (
        at_floor or state["lr_reductions"] >= max_red)
    return {"val_smooth": state["smooth"], "lr_now": base_lr * state["lr_scale"], "lr_reduced": reduced,
            "since_improve": state["since_improve"], "lr_reductions": state["lr_reductions"], "stop": stop}


@torch.no_grad()
def evaluate(model: SentenceContextDecoder, ds: KeySentences, cfg: dict[str, Any], device: torch.device,
             use_bf16: bool) -> dict[str, Any]:
    model.eval()
    sampler = BucketBatchSampler(ds.lengths(), cfg["data"]["eval_batch_size"], shuffle=False)
    dl = DataLoader(ds, batch_sampler=sampler, collate_fn=collate_sentences, num_workers=0,
                    generator=torch.Generator().manual_seed(0))
    rows: list[dict[str, Any]] = []
    tot_ce, n_keys, hit, hit_conv = 0.0, 0, 0, 0
    for batch in dl:
        x, km, s, kt = to_device(batch, device)
        with torch.autocast(device.type, dtype=torch.bfloat16, enabled=use_bf16):
            out = model(x, km, s, kt)
        ls = model.loss(out, batch["key_labels"].to(device))
        n = int(ls["n"])
        tot_ce += float(ls["ce"]) * n
        n_keys += n
        hit += int(ls["correct"])
        hit_conv += int(ls.get("correct_conv", 0))
        lengths = km.sum(1).tolist()
        for b, L in enumerate(lengths):
            hyp = greedy_text(out["logits"][b].float(), int(L))
            tg, ty = batch["target_text"][b], batch["typed_text"][b]
            rows.append({"participant": batch["participant"][b], "cer_typed": cer(ty, hyp),
                         "cer_target": cer(tg, hyp), "wer_typed": wer(ty, hyp), "wer_target": wer(tg, hyp)})
    model.train()
    if not rows:
        return {}
    keys = ("cer_typed", "cer_target", "wer_typed", "wer_target")
    res: dict[str, Any] = {"val_ce": tot_ce / max(1, n_keys), "val_key_n": n_keys, "n": len(rows),
                           "val_key_acc": hit / max(1, n_keys)}
    res["val_key_err"] = 1.0 - res["val_key_acc"]
    if model.has_key_head:
        res["val_key_acc_conv"] = hit_conv / max(1, n_keys)
    res.update({f"val_{k}": v for k, v in participant_means(rows, keys).items()})
    res.update({f"val_{k}_micro": float(np.mean([r[k] for r in rows])) for k in keys})
    return res


def _train(keep_awake_on: bool, cfg: dict[str, Any], run_dir: str | Path | None = None, resume: bool = False,
          max_steps: int | None = None, echo: bool = True) -> dict[str, Any]:
    """Train (or resume) a run. Returns a summary dict."""
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
    if tcfg.get("torch_threads"):
        torch.set_num_threads(int(tcfg["torch_threads"]))

    subject_map = ckpt["subject_map"] if ckpt is not None else None
    train_ds, val_ds = build_datasets(cfg, subject_map)
    subject_map = train_ds.subject_map
    mcfg = SentenceModelConfig.from_dict({**cfg["model"], "n_subjects": max(1, len(subject_map)),
                                          "window_samples": train_ds.window_samples()})
    model = SentenceContextDecoder(mcfg).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=ocfg["lr"], betas=tuple(ocfg["betas"]),
                            weight_decay=ocfg["weight_decay"])
    sampler = BucketBatchSampler(train_ds.lengths(), cfg["data"]["batch_size"], seed=tcfg["seed"])
    steps_per_epoch = len(sampler.batches())
    state = {"epoch": 0, "step_in_epoch": 0, "global_step": 0, "best": float("inf"), "best_epoch": -1,
             "bad_evals": 0, "done": False, "active_s": 0.0, **plateau_init_state()}
    schedule = ocfg.get("schedule", "cosine")
    if schedule == "plateau":
        sched = torch.optim.lr_scheduler.LambdaLR(opt, plateau_lr_lambda(ocfg["warmup_steps"], state))
    elif schedule == "cosine":
        sched = torch.optim.lr_scheduler.LambdaLR(
            opt, lr_lambda(ocfg["warmup_steps"], steps_per_epoch * ocfg["epochs"], ocfg["min_lr_ratio"]))
    else:
        raise ValueError(f"optim.schedule must be 'cosine' or 'plateau', got {schedule!r}")
    if ckpt is None and tcfg.get("init_from"):
        loaded, skipped = init_from_convctc(model, tcfg["init_from"])
        log.log(f"init_from {tcfg['init_from']}: {len(loaded)} tensors loaded {loaded}, skipped {len(skipped)}")
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
        log.log("model parameters: " + json.dumps(model.param_count()))
    log.log(f"device={device} bf16={use_bf16} train={len(train_ds)} val={len(val_ds)} "
            f"participants={len(subject_map)} steps/epoch={steps_per_epoch}")
    log.metrics({"type": "setup", "n_train": len(train_ds), "n_val": len(val_ds), "subjects": subject_map,
                 "params": model.param_count(), "steps_per_epoch": steps_per_epoch, "model": mcfg.to_dict()})

    def save(path: Path, full: bool = True) -> None:
        obj: dict[str, Any] = {"model": model.state_dict(), "config": cfg, "model_config": mcfg.to_dict(),
                               "subject_map": subject_map, "state": dict(state), "kind": "sentence_context"}
        if full:
            obj.update(optimizer=opt.state_dict(), scheduler=sched.state_dict(), rng=rng_state())
        atomic_save(obj, path)

    def write_status(status: str) -> None:
        st = {"status": status, "pid": os.getpid(), "run_dir": str(run_dir),
              "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
              **{k: state[k] for k in ("epoch", "global_step", "best", "best_epoch", "bad_evals")},
              "active_min": round(state.get("active_s", 0.0) / 60, 2),
              "metric": tcfg["early_stop_metric"], "schedule": schedule,
              "lr": sched.get_last_lr()[0] if schedule == "cosine" else ocfg["lr"] * state["lr_scale"]}
        if schedule == "plateau":
            st.update({k: state[k] for k in ("last_val", "smooth", "best_smooth", "since_improve",
                                             "lr_reductions")})
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
    while not state["done"] and state["epoch"] < ocfg["epochs"]:
        ep = state["epoch"]
        train_ds.set_epoch(ep)
        sampler.set_epoch(ep, skip=state["step_in_epoch"])
        dl = DataLoader(train_ds, batch_sampler=sampler, collate_fn=collate_sentences,
                        num_workers=cfg["data"]["num_workers"], pin_memory=device.type == "cuda",
                        generator=torch.Generator().manual_seed(tcfg["seed"] * 100003 + ep))
        t_ep = time.time()
        run_loss, run_n = 0.0, 0
        for batch in dl:
            x, km, s, kt = to_device(batch, device)
            with torch.autocast(device.type, dtype=torch.bfloat16, enabled=use_bf16):
                out = model(x, km, s, kt)
            ls = model.loss(out, batch["key_labels"].to(device))
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
                n_k = max(1, int(ls["n"]))
                rec = {"type": "train", "epoch": ep, "step": state["global_step"], "loss": run_loss / run_n,
                       "ce": float(ls["ce"]), "key_acc": int(ls["correct"]) / n_k,
                       "grad_norm": float(gnorm), "lr": sched.get_last_lr()[0]}
                if "ce_conv" in ls:
                    rec.update(ce_conv=float(ls["ce_conv"]), key_acc_conv=int(ls["correct_conv"]) / n_k)
                log.metrics(rec)
                log.log(f"ep {ep} step {state['global_step']} loss {rec['loss']:.4f} acc {rec['key_acc']:.3f} "
                        f"lr {rec['lr']:.2e}")
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
        ep_time = time.time() - t_ep
        state["epoch"] += 1
        state["step_in_epoch"] = 0
        rec2: dict[str, Any] = {"type": "epoch", "epoch": ep, "step": state["global_step"],
                                "train_loss": run_loss / max(1, run_n), "epoch_s": ep_time}
        if len(val_ds) and (ep + 1) % tcfg["eval_every_epochs"] == 0:
            ev = evaluate(model, val_ds, cfg, device, use_bf16)
            rec2.update(ev)
            metric = ev[tcfg["early_stop_metric"]]
            if metric < state["best"] - 1e-4:
                state["best"], state["best_epoch"], state["bad_evals"] = metric, ep, 0
                save(run_dir / "best.pt", full=False)
            else:
                state["bad_evals"] += 1
            if schedule == "plateau":
                tr = plateau_update(state, metric, ocfg, tcfg)
                rec2.update(tr)
                if tr["lr_reduced"]:
                    log.log(f"plateau: LR scale reduced to {state['lr_scale']:.4g} "
                            f"(reduction {state['lr_reductions']}, lr {ocfg['lr'] * state['lr_scale']:.2e})")
                if tr["stop"]:
                    state["done"] = True
                    stop_reason = "early_stop"
            elif state["bad_evals"] >= tcfg["patience_evals"]:
                state["done"] = True
                stop_reason = "early_stop"
        log.metrics(rec2)
        msg = f"epoch {ep} done in {ep_time:.1f}s train_loss {rec2['train_loss']:.4f}"
        if "val_cer_typed" in rec2:
            msg += (f" val CER typed {rec2['val_cer_typed']:.4f} target {rec2['val_cer_target']:.4f}"
                    f" key acc {rec2['val_key_acc']:.3f}")
            if "val_key_acc_conv" in rec2:
                msg += f" (conv only {rec2['val_key_acc_conv']:.3f})"
            msg += f" (best {state['best']:.4f} @ {state['best_epoch']})"
            if "val_smooth" in rec2:
                msg += (f" | trend: smoothed {rec2['val_smooth']:.4f} (best {state['best_smooth']:.4f})"
                        f" lr {rec2['lr_now']:.2e} evals_since_improve {state['since_improve']}"
                        f" lr_reductions {state['lr_reductions']}")
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
    write_status({"max_steps": "stopped", "max_minutes": "stopped", "early_stop": "early_stopped",
                  "epochs_done": "done"}[stop_reason])
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
    p = argparse.ArgumentParser(description="Train the sentence-context keystroke decoder.")
    p.add_argument("--config", help="JSON config file (merged over the defaults)")
    p.add_argument("--run-dir", help="run directory (default <runs_dir>/<run_name>)")
    p.add_argument("--run-name", help="override run_name")
    p.add_argument("--resume", action="store_true", help="continue from <run_dir>/latest.pt")
    p.add_argument("--max-minutes", type=float)
    p.add_argument("--max-steps", type=int)
    a = p.parse_args(argv)
    cfg: dict[str, Any] = {}
    if a.config:
        cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    elif a.run_dir and (Path(a.run_dir) / "config.json").exists():
        cfg = json.loads((Path(a.run_dir) / "config.json").read_text(encoding="utf-8"))
        cfg.pop("subject_map", None)
    cfg = {k: v for k, v in cfg.items() if not k.startswith("_")}  # "_comment" keys
    cfg = merge(DEFAULT_CONFIG, copy.deepcopy(cfg))
    if a.run_name:
        cfg["run_name"] = a.run_name
    if a.max_minutes is not None:
        cfg["train"]["max_minutes"] = a.max_minutes
    res = train(cfg, a.run_dir, resume=a.resume, max_steps=a.max_steps)
    print(json.dumps(res, indent=2, default=str))
    hard_exit(0)


if __name__ == "__main__":
    main()
