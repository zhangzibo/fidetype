"""Synthetic SpanishBCBL-style cache for pipeline tests.

The generator writes the same file format as the real preprocessed cache
(``cache/spanishbcbl/v1``):

- ``<subject>/<session>_<block>.npz`` with ``data`` (float16, [306, T],
  100 Hz), ``sfreq``, ``ch_names``, ``ch_types`` and ``ch_pos``.
- ``<subject>/<session>_<block>.json`` with ``subject``, ``participant``
  and ``segments``.
- ``_index.json`` in the root. It lists the blocks.

The signal is coloured noise plus a weak response at each key press.
Each character has its own spatial pattern. Each subject adds a small
change to the patterns. A model can learn the mapping, so a falling loss
proves that the pipeline works end to end. The numbers say nothing about
real MEG.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from fidetype.streams.corpus import sentences
from fidetype.streams.vocab import VOCAB, normalize_text

N_CH = 306
SFREQ = 100.0
_CHARS = [c for c in VOCAB[1:]]  # a-z and space


def hash_split(text: str) -> str:
    """Return "train", "val" or "test" from a hash of the text (80/10/10)."""
    h = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % 10
    return "train" if h < 8 else ("val" if h == 8 else "test")


def _coloured_noise(rng: np.random.Generator, n_ch: int, T: int, alpha: float = 0.9) -> np.ndarray:
    """Return AR(1) noise with unit variance, shape [n_ch, T]."""
    white = rng.standard_normal((n_ch, T)).astype(np.float32)
    out = np.empty_like(white)
    out[:, 0] = white[:, 0]
    scale = np.sqrt(1 - alpha**2)
    for t in range(1, T):
        out[:, t] = alpha * out[:, t - 1] + scale * white[:, t]
    return out


def write_synthetic_cache(
    root: str | Path,
    n_subjects: int = 2,
    blocks_per_subject: int = 2,
    trials_per_block: int = 24,
    amplitude: float = 1.5,
    seed: int = 0,
    typo_rate: float = 0.03,
) -> Path:
    """Write a synthetic cache under ``root`` and return the root path.

    Trials 0 and 1 of each block have ``is_training=True``, as in the real
    data.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    n_sent = n_subjects * blocks_per_subject * trials_per_block
    pool = [normalize_text(s) for s in sentences(max(n_sent, 64), seed=seed)]

    # Character patterns: shared part plus a subject-specific part.
    base_pat = rng.standard_normal((len(_CHARS), N_CH)).astype(np.float32)
    base_pat /= np.linalg.norm(base_pat, axis=1, keepdims=True) / np.sqrt(N_CH) * 4
    t_kernel = np.arange(-10, 31) / SFREQ  # -100 ms .. +300 ms
    kernel = np.exp(-0.5 * ((t_kernel - 0.1) / 0.05) ** 2).astype(np.float32)

    ch_names = [f"MEG{i:04d}" for i in range(N_CH)]
    ch_types = ["mag" if i % 3 == 0 else "grad" for i in range(N_CH)]
    ch_pos = rng.uniform(-0.1, 0.1, size=(N_CH, 3)).astype(np.float32)

    index = []
    sent_i = 0
    for s in range(n_subjects):
        subject = f"S{90 + s}"
        sub_pat = base_pat + 0.3 * rng.standard_normal(base_pat.shape).astype(np.float32)
        (root / subject).mkdir(exist_ok=True)
        for b in range(blocks_per_subject):
            session, block = f"ses{b // 2 + 1}", f"block{b % 2 + 1}"
            events = []  # (sample, char_index)
            segments = []
            cursor = int(2.0 * SFREQ)
            for tr in range(trials_per_block):
                target = pool[sent_i % len(pool)]
                sent_i += 1
                typed_chars = []
                for c in target:
                    if c != " " and rng.random() < typo_rate:
                        typed_chars.append(_CHARS[rng.integers(0, 26)])
                    else:
                        typed_chars.append(c)
                typed = "".join(typed_chars)
                start = cursor
                t = start + int(0.4 * SFREQ)
                key_samples = []
                for c in typed_chars:
                    key_samples.append(t)
                    events.append((t, _CHARS.index(c)))
                    t += int(rng.gamma(6.0, 0.045) * SFREQ) + 8
                end = key_samples[-1] + int(0.5 * SFREQ)
                segments.append(
                    {
                        "trial_idx": tr,
                        "is_training": tr < 2,
                        "start_sample": int(start),
                        "end_sample": int(end),
                        "target_text": target,
                        "typed_text": typed,
                        "key_samples": [int(k - start) for k in key_samples],  # relative, as in the real cache
                        "key_chars": typed_chars,
                        "key_target_chars": list(target),
                        "split": hash_split(target),
                    }
                )
                cursor = end + int(rng.uniform(1.5, 3.0) * SFREQ)
            T = cursor + int(1.0 * SFREQ)
            data = _coloured_noise(rng, N_CH, T)
            for k, ci in events:
                lo, hi = k - 10, k + 31
                data[:, lo:hi] += amplitude * np.outer(sub_pat[ci], kernel) / 4
            data = np.clip(data, -5, 5).astype(np.float16)
            stem = f"{session}_{block}"
            np.savez(
                root / subject / f"{stem}.npz",
                data=data,
                sfreq=np.array(SFREQ),
                ch_names=np.array(ch_names),
                ch_types=np.array(ch_types),
                ch_pos=ch_pos,
            )
            sidecar = {"subject": subject, "participant": f"synth-{s}", "session": session,
                       "block": block, "sfreq": SFREQ, "n_samples": int(T), "segments": segments}
            (root / subject / f"{stem}.json").write_text(json.dumps(sidecar, indent=1))
            index.append({"subject": subject, "session": session, "block": block,
                          "npz": f"{subject}/{stem}.npz", "json": f"{subject}/{stem}.json"})
    (root / "_index.json").write_text(json.dumps({"blocks": index, "synthetic": True}, indent=1))
    return root


def main() -> None:
    p = argparse.ArgumentParser(description="Write a synthetic SpanishBCBL-style cache.")
    p.add_argument("root")
    p.add_argument("--subjects", type=int, default=2)
    p.add_argument("--blocks", type=int, default=2)
    p.add_argument("--trials", type=int, default=24)
    p.add_argument("--amplitude", type=float, default=1.5)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    write_synthetic_cache(a.root, a.subjects, a.blocks, a.trials, a.amplitude, a.seed)
    print(f"wrote synthetic cache to {a.root}")


if __name__ == "__main__":
    main()
