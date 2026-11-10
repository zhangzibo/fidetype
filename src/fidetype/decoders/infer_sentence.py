"""Run a sentence-context keystroke checkpoint and write NeuralTextStreams (M1-15).

Usage (GPU env, after training)::

    python -m fidetype.decoders.infer_sentence --run-dir C:/Users/zhang/bci-data/runs/<run_name> \
        --control --lm C:/Users/zhang/bci-data/lm/spa_tatoeba_6gram_mkn.npz

For each split the script writes one CTC-form keystroke stream per sentence
(:func:`fidetype.decoders.sentence_context.sentence_streams`) to
``<out_root>/<run_name>/<split>/<subject>_<session>_<block>_<trial>.npz``,
and the labels to a separate ``labels.jsonl``. The streams hold no text.

Metrics (``<out_root>/<run_name>/metrics.json``), per input condition:

- ``greedy``: argmax per key, CER/WER vs target and typed text, with
  per-subject and per-participant means (:func:`fidetype.decoders.infer.summarize`).
- ``beam_lm`` (with ``--lm``): the ``RETUNED`` CTC prefix beam + char LM on the
  streams. With several ``--lm-weights``, the weight with the lowest real val
  CER (mean over participants) is used for every split and condition.
- ``--control``: the same for "shuffled" (the windows of another sentence of
  the split, a seed-0 derangement, cycled to the same key count) and "zeros".
  ``gap_*`` holds the paired bootstrap 95% CI of "shuffled CER - real CER".
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Sequence

import numpy as np

os.environ.setdefault("MIOPEN_FIND_MODE", "FAST")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

import torch  # noqa: E402

from fidetype.decoders.infer import bootstrap_mean_ci, summarize  # noqa: E402
from fidetype.decoders.sentence_context import (  # noqa: E402
    KeySentences,
    SentenceContextDecoder,
    SentenceModelConfig,
    collate_sentences,
    greedy_text,
    sentence_stream_meta,
    sentence_streams,
)
from fidetype.eval.metrics import cer, wer  # noqa: E402

DEFAULT_OUT_ROOT = "C:/Users/zhang/bci-data/streams"
CONDITIONS = ("real", "shuffled", "zeros")


def load_checkpoint(path: str | Path, device: torch.device) -> tuple[SentenceContextDecoder, dict[str, Any]]:
    ck = torch.load(path, map_location="cpu", weights_only=False)
    model = SentenceContextDecoder(SentenceModelConfig.from_dict(ck["model_config"]))
    model.load_state_dict(ck["model"])
    return model.to(device).eval(), ck


def derangement(n: int, seed: int = 0) -> np.ndarray:
    """A seeded permutation with no fixed point (as ``infer.meg_control``)."""
    perm = np.random.default_rng(seed).permutation(n)
    return np.where(perm == np.arange(n), (np.arange(n) + 1) % n, perm)


def condition_item(ds: KeySentences, i: int, condition: str, perm: np.ndarray | None) -> dict[str, Any]:
    """Item ``i`` with its own windows ("real"), another sentence's windows
    cycled to the same key count ("shuffled"), or zeros ("zeros")."""
    item = ds[i]
    if condition == "shuffled":
        other = ds[int(perm[i])]["x"]
        idx = torch.arange(item["x"].shape[0]) % max(1, other.shape[0])
        item["x"] = other[idx].clone()
    elif condition == "zeros":
        item["x"] = torch.zeros_like(item["x"])
    elif condition != "real":
        raise ValueError(condition)
    return item


@torch.no_grad()
def decode_split(model: SentenceContextDecoder, ds: KeySentences, device: torch.device, use_bf16: bool,
                 condition: str = "real", batch_size: int = 16, seed: int = 0) -> list[dict[str, Any]]:
    """Return per-sentence ``log_probs`` [K, 27] (float64), ``key_times`` and ids."""
    perm = derangement(len(ds), seed) if condition == "shuffled" and len(ds) > 1 else None
    if condition == "shuffled" and perm is None:
        return []
    out: list[dict[str, Any]] = []
    for b0 in range(0, len(ds), batch_size):
        items = [condition_item(ds, i, condition, perm) for i in range(b0, min(len(ds), b0 + batch_size))]
        batch = collate_sentences(items)
        km = batch["key_mask"].to(device)
        with torch.autocast(device.type, dtype=torch.bfloat16, enabled=use_bf16):
            res = model(batch["x"].to(device), km, batch["subjects"].to(device), batch["key_times"].to(device))
        lp = res["logits"].float().log_softmax(-1).cpu().numpy().astype(np.float64)
        for j, it in enumerate(items):
            n = int(km[j].sum())
            out.append({"index": it["index"], "log_probs": lp[j, :n], "key_times": it["key_time"].numpy()})
    return out


def _rows(ds: KeySentences, decoded: list[dict[str, Any]], hyps: Sequence[str]) -> list[dict[str, Any]]:
    rows = []
    for d, hyp in zip(decoded, hyps):
        seg = ds.segments[d["index"]]
        rows.append({"file": f"{seg.subject}_{seg.session}_{seg.block}_{seg.trial_idx}.npz",
                     "subject": seg.subject, "participant": seg.participant, "hyp": hyp,
                     "target_text": seg.target_text, "typed_text": seg.typed_text,
                     "cer_target": cer(seg.target_text, hyp), "cer_typed": cer(seg.typed_text, hyp),
                     "wer_target": wer(seg.target_text, hyp), "wer_typed": wer(seg.typed_text, hyp)})
    return rows


def _streams(model: SentenceContextDecoder, ds: KeySentences, decoded: list[dict[str, Any]], run_name: str,
             split: str, condition: str):
    metas = []
    for d in decoded:
        seg = ds.segments[d["index"]]
        metas.append(sentence_stream_meta(model, seg.subject, seg.session, {
            "subject.participant": seg.participant, "run_name": run_name, "split": split,
            "block": seg.block, "trial_idx": seg.trial_idx, "input.condition": condition}))
    out = []
    for d, m in zip(decoded, metas):
        lp = torch.from_numpy(d["log_probs"])[None]
        km = torch.ones(1, lp.shape[1], dtype=torch.bool)
        out += sentence_streams(lp, km, torch.from_numpy(d["key_times"])[None], [m])
    return out


def beam_hyps(streams, lm, lm_weight: float) -> list[str]:
    from fidetype.lm import RETUNED, ctc_prefix_beam_search

    kw = {**dict(RETUNED), "lm_weight": lm_weight}
    out = []
    for s in streams:
        h = ctc_prefix_beam_search(s, lm, align=False, **kw)
        out.append(" ".join(h[0].text.split()) if h else "")
    return out


@torch.no_grad()
def run_inference(run_dir: str | Path, ckpt_name: str = "best.pt", splits: tuple[str, ...] = ("val", "test"),
                  out_root: str | Path = DEFAULT_OUT_ROOT, device: str = "cuda", data_root: str | None = None,
                  control: bool = False, lm_path: str | None = None, lm_weights: Sequence[float] = (0.5,),
                  echo: bool = True) -> dict[str, Any]:
    run_dir = Path(run_dir)
    dev = torch.device(device if (device != "cuda" or torch.cuda.is_available()) else "cpu")
    model, ck = load_checkpoint(run_dir / ckpt_name, dev)
    cfg = ck["config"]
    d = cfg["data"]
    run_name = run_dir.name
    use_bf16 = bool(cfg["train"].get("bf16")) and dev.type == "cuda"
    out_dir = Path(out_root) / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    conds = CONDITIONS if control else ("real",)
    lm = None
    if lm_path:
        from fidetype.lm import CharNgramLM

        lm = CharNgramLM.load(lm_path)
    results: dict[str, Any] = {"run_name": run_name, "checkpoint": ckpt_name, "kind": "sentence_context",
                               "lookahead_keys": model.cfg.lookahead_keys,
                               "checkpoint_state": ck.get("state", {}), "splits": {}}
    cache: dict[tuple[str, str], tuple[KeySentences, list, list]] = {}
    for split in splits:
        ds = KeySentences(data_root or d["root"], (split,), d.get("subjects"), ck["subject_map"], None,
                          mmap_dir=d.get("mmap_dir"), window_s=tuple(d.get("window_s", [-0.2, 0.3])),
                          blocks=d.get("blocks"))
        for c in conds:
            dec = decode_split(model, ds, dev, use_bf16, c)
            cache[(split, c)] = (ds, dec, _streams(model, ds, dec, run_name, split, c))
    # LM weight: the lowest real val CER (mean over participants).
    lm_weight = None
    if lm is not None:
        lm_weight = float(lm_weights[0])
        if len(lm_weights) > 1 and ("val", "real") in cache:
            ds, dec, st = cache[("val", "real")]
            scores = {}
            for w in lm_weights:
                s = summarize(_rows(ds, dec, beam_hyps(st, lm, float(w))))
                scores[float(w)] = s["mean_over_participants"]["cer_target"]
            lm_weight = min(scores, key=scores.get)
            results["lm_weight_val_scores"] = scores
        results["lm_weight"] = lm_weight
    for split in splits:
        sres: dict[str, Any] = {}
        per_sent: dict[str, dict[str, list[float]]] = {}
        for c in conds:
            ds, dec, st = cache[(split, c)]
            if not dec:
                continue
            if c == "real":
                sdir = out_dir / split
                sdir.mkdir(parents=True, exist_ok=True)
                with open(sdir / "labels.jsonl", "w", encoding="utf-8") as lab:
                    for dd, s in zip(dec, st):
                        seg = ds.segments[dd["index"]]
                        name = f"{seg.subject}_{seg.session}_{seg.block}_{seg.trial_idx}.npz"
                        s.to_npz(sdir / name)
                        lab.write(json.dumps({"file": name, "subject": seg.subject, "participant": seg.participant,
                                              "target_text": seg.target_text, "typed_text": seg.typed_text}) + "\n")
            decs = {"greedy": [greedy_text(torch.from_numpy(dd["log_probs"]), len(dd["log_probs"])) for dd in dec]}
            if lm is not None:
                decs["beam_lm"] = beam_hyps(st, lm, lm_weight)
            for dname, hyps in decs.items():
                rows = _rows(ds, dec, hyps)
                sres[f"{dname}_{c}"] = summarize(rows)
                per_sent[f"{dname}_{c}"] = {m: [r[m] for r in rows] for m in ("cer_target", "cer_typed")}
                if c == "real":
                    with open(out_dir / f"per_sentence_{dname}_{split}.jsonl", "w", encoding="utf-8") as f:
                        for r in rows:
                            f.write(json.dumps(r) + "\n")
        for dname in ("greedy", "beam_lm"):
            a, b = per_sent.get(f"{dname}_real"), per_sent.get(f"{dname}_shuffled")
            if a and b:
                sres[f"gap_{dname}"] = {m: bootstrap_mean_ci(np.array(b[m]) - np.array(a[m]))
                                        for m in ("cer_target", "cer_typed")}
        results["splits"][split] = sres
        if echo:
            for k, v in sres.items():
                if k.startswith("gap_"):
                    g = v["cer_target"]
                    print(f"[{split}] {k} CER target {g['mean']:+.4f} [{g['ci95_lo']:+.4f}, {g['ci95_hi']:+.4f}]")
                else:
                    m = v.get("mean_over_participants", {})
                    print(f"[{split}] {k}: n={v['n_sentences']} " + " ".join(f"{a}={b:.4f}" for a, b in m.items()),
                          flush=True)
    (out_dir / "metrics.json").write_text(json.dumps(results, indent=2))
    return results


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Write keystroke NeuralTextStreams from a sentence-context checkpoint.")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--ckpt", default="best.pt")
    p.add_argument("--splits", nargs="+", default=["val", "test"])
    p.add_argument("--out-root", default=DEFAULT_OUT_ROOT)
    p.add_argument("--device", default="cuda")
    p.add_argument("--data-root", default=None)
    p.add_argument("--control", action="store_true", help="also decode shuffled-sentence MEG and zeros")
    p.add_argument("--lm", default=None, help="char n-gram LM (.npz) for the RETUNED beam")
    p.add_argument("--lm-weights", nargs="+", type=float, default=[0.5],
                   help="LM weights; with several, pick the best on real val")
    a = p.parse_args(argv)
    res = run_inference(a.run_dir, a.ckpt, tuple(a.splits), a.out_root, a.device, a.data_root, a.control,
                        a.lm, a.lm_weights)
    print(json.dumps({s: {k: v.get("mean_over_participants") for k, v in r.items() if not k.startswith("gap_")}
                      for s, r in res["splits"].items()}, indent=2))
    from fidetype.decoders.train import hard_exit

    hard_exit(0)


if __name__ == "__main__":
    main()
