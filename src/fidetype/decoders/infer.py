"""Run a ConvCTC checkpoint and write NeuralTextStreams.

Usage (GPU env)::

    python -m fidetype.decoders.infer --run-dir C:/Users/zhang/bci-data/runs/<run_name>

For each segment of each split, the script writes one stream to
``<out_root>/<run_name>/<split>/<subject>_<session>_<block>_<trial>.npz``.

- ``log_probs`` holds the per-frame log-softmax (40 ms frames).
- ``frame_times`` is relative to the segment start, in seconds.
- ``meta`` has run, subject, split and position data. It does NOT hold
  the target text.

The labels for evaluation go to a separate ``labels.jsonl`` in each
split directory. The script then computes greedy-CTC CER and WER
against the target and the typed text. It writes ``metrics.json`` and
``per_sentence_<split>.jsonl`` to ``<out_root>/<run_name>/``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

os.environ.setdefault("MIOPEN_FIND_MODE", "FAST")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

import torch  # noqa: E402

from fidetype.decoders.conv_ctc import ConvCTC, ModelConfig
from fidetype.decoders.dataset import MEGSegments
from fidetype.eval.metrics import cer, ctc_greedy_decode, wer
from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import BLANK_ID, VOCAB

DEFAULT_OUT_ROOT = "C:/Users/zhang/bci-data/streams"
SOURCE = "spanishbcbl-convctc"


def load_checkpoint(path: str | Path, device: torch.device) -> tuple[ConvCTC, dict[str, Any]]:
    ck = torch.load(path, map_location="cpu", weights_only=False)
    model = ConvCTC(ModelConfig.from_dict(ck["model_config"]))
    model.load_state_dict(ck["model"])
    return model.to(device).eval(), ck


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return per-subject means, the mean across subjects, and the
    distribution over sentences."""
    keys = ["cer_target", "cer_typed", "wer_target", "wer_typed"]
    by_subj: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_subj.setdefault(r["subject"], []).append(r)
    per_subject = {s: {k: float(np.mean([r[k] for r in rs])) for k in keys} | {"n": len(rs)}
                   for s, rs in sorted(by_subj.items())}
    out: dict[str, Any] = {"n_sentences": len(rows), "per_subject": per_subject}
    if rows:
        out["mean_over_subjects"] = {k: float(np.mean([v[k] for v in per_subject.values()])) for k in keys}
        out["mean_over_sentences"] = {k: float(np.mean([r[k] for r in rows])) for k in keys}
        out["sentence_distribution"] = {
            k: {q: float(np.percentile([r[k] for r in rows], p))
                for q, p in (("p10", 10), ("p25", 25), ("median", 50), ("p75", 75), ("p90", 90))}
            for k in keys
        }
        out["frac_sentences_cer_target_0"] = float(np.mean([r["cer_target"] == 0 for r in rows]))
    return out


@torch.no_grad()
def meg_control(model: ConvCTC, ds: MEGSegments, dev: torch.device, use_bf16: bool, pad_multiple: int = 1,
                seed: int = 0) -> dict[str, dict[str, float]]:
    """Check that the decoder uses the MEG.

    The function decodes each segment three times: with its own MEG
    ("real"), with the MEG of another segment of the same split cut or
    zero-padded to the same length ("shuffled"), and with zeros. It
    returns the mean CER (vs target and typed text) for each input. If
    "real" is not lower than "shuffled", the model uses only a text prior.
    """
    from fidetype.decoders.conv_ctc import greedy_decode_batch

    n = len(ds)
    if n < 2:
        return {}
    perm = np.random.default_rng(seed).permutation(n)
    perm = np.where(perm == np.arange(n), (np.arange(n) + 1) % n, perm)
    res: dict[str, dict[str, list[float]]] = {k: {"cer_target": [], "cer_typed": []}
                                             for k in ("real", "shuffled", "zeros")}
    for i in range(n):
        item, other = ds[i], ds[int(perm[i])]["x"]
        T = item["x"].shape[1]
        sh = other[:, :T] if other.shape[1] >= T else torch.nn.functional.pad(other, (0, T - other.shape[1]))
        for name, x in (("real", item["x"]), ("shuffled", sh), ("zeros", torch.zeros_like(item["x"]))):
            T_pad = -(-T // pad_multiple) * pad_multiple
            xx = torch.nn.functional.pad(x[None], (0, T_pad - T)).to(dev)
            with torch.autocast(dev.type, dtype=torch.bfloat16, enabled=use_bf16):
                out = model(xx, torch.tensor([T], device=dev), torch.tensor([item["subject"]], device=dev))
            hyp = greedy_decode_batch(out["logits"].float(), out["out_lengths"])[0]
            res[name]["cer_target"].append(cer(item["target_text"], hyp))
            res[name]["cer_typed"].append(cer(item["typed_text"], hyp))
    return {k: {m: float(np.mean(v)) for m, v in d.items()} for k, d in res.items()}


@torch.no_grad()
def run_inference(run_dir: str | Path, ckpt_name: str = "best.pt", splits: tuple[str, ...] = ("val", "test"),
                  out_root: str | Path = DEFAULT_OUT_ROOT, device: str = "cuda",
                  data_root: str | None = None, echo: bool = True, control: bool = False) -> dict[str, Any]:
    run_dir = Path(run_dir)
    dev = torch.device(device if (device != "cuda" or torch.cuda.is_available()) else "cpu")
    model, ck = load_checkpoint(run_dir / ckpt_name, dev)
    cfg = ck["config"]
    run_name = run_dir.name
    root = data_root or cfg["data"]["root"]
    use_bf16 = bool(cfg["train"].get("bf16")) and dev.type == "cuda"
    out_dir = Path(out_root) / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    period = model.frame_period_s()
    pad_multiple = max(1, int(cfg["data"].get("pad_multiple", 1)))
    results: dict[str, Any] = {"run_name": run_name, "checkpoint": ckpt_name,
                               "checkpoint_state": ck.get("state", {}), "splits": {}}
    for split in splits:
        ds = MEGSegments(root, (split,), cfg["data"].get("subjects"), ck["subject_map"], None,
                         mmap_dir=cfg["data"].get("mmap_dir"))
        sdir = out_dir / split
        sdir.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, Any]] = []
        with open(sdir / "labels.jsonl", "w", encoding="utf-8") as lab:
            for i in range(len(ds)):
                item = ds[i]
                seg = ds.segments[i]
                T = item["x"].shape[-1]
                T_pad = -(-T // pad_multiple) * pad_multiple  # few shapes: fast MIOpen
                x = torch.nn.functional.pad(item["x"][None], (0, T_pad - T)).to(dev)
                L = torch.tensor([T], device=dev)
                s = torch.tensor([item["subject"]], device=dev)
                with torch.autocast(dev.type, dtype=torch.bfloat16, enabled=use_bf16):
                    out = model(x, L, s)
                n = int(out["out_lengths"][0])
                lp = out["logits"][0, :n].float().log_softmax(-1).cpu().numpy()
                name = f"{seg.subject}_{seg.session}_{seg.block}_{seg.trial_idx}"
                stream = NeuralTextStream(
                    log_probs=lp,
                    frame_times=np.arange(n) * period,
                    vocab=list(VOCAB),
                    blank_id=BLANK_ID,
                    source=SOURCE,
                    meta={
                        "run_name": run_name,
                        "checkpoint": ckpt_name,
                        "subject": seg.subject,
                        "participant": seg.participant,
                        "session": seg.session,
                        "block": seg.block,
                        "trial_idx": seg.trial_idx,
                        "split": split,
                        "segment_start_s": seg.start / item["sfreq"],
                        "frame_period_s": period,
                        "lookahead_frames": model.cfg.lookahead_frames,
                        "model": "conv_ctc",
                    },
                )
                stream.to_npz(sdir / f"{name}.npz")
                hyp = ctc_greedy_decode(stream)
                lab.write(json.dumps({"file": f"{name}.npz", "subject": seg.subject,
                                      "target_text": seg.target_text, "typed_text": seg.typed_text}) + "\n")
                rows.append({"file": f"{name}.npz", "subject": seg.subject, "hyp": hyp,
                             "target_text": seg.target_text, "typed_text": seg.typed_text,
                             "cer_target": cer(seg.target_text, hyp), "cer_typed": cer(seg.typed_text, hyp),
                             "wer_target": wer(seg.target_text, hyp), "wer_typed": wer(seg.typed_text, hyp)})
        with open(out_dir / f"per_sentence_{split}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        results["splits"][split] = summarize(rows)
        if control:
            ctl = meg_control(model, ds, dev, use_bf16, pad_multiple)
            results["splits"][split]["meg_control"] = ctl
            if echo and ctl:
                print(f"[{split}] control CER target: " + " ".join(
                    f"{k}={v['cer_target']:.4f}" for k, v in ctl.items()), flush=True)
        if echo:
            m = results["splits"][split].get("mean_over_subjects", {})
            print(f"[{split}] n={len(rows)} " + " ".join(f"{k}={v:.4f}" for k, v in m.items()), flush=True)
    (out_dir / "metrics.json").write_text(json.dumps(results, indent=2))
    return results


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Write NeuralTextStreams from a ConvCTC checkpoint.")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--ckpt", default="best.pt")
    p.add_argument("--splits", nargs="+", default=["val", "test"])
    p.add_argument("--out-root", default=DEFAULT_OUT_ROOT)
    p.add_argument("--device", default="cuda")
    p.add_argument("--data-root", default=None)
    p.add_argument("--control", action="store_true",
                   help="also decode with shuffled-trial MEG and zeros (does the model use the MEG?)")
    a = p.parse_args(argv)
    res = run_inference(a.run_dir, a.ckpt, tuple(a.splits), a.out_root, a.device, a.data_root,
                        control=a.control)
    print(json.dumps({s: v.get("mean_over_subjects") for s, v in res["splits"].items()}, indent=2))


if __name__ == "__main__":
    main()
