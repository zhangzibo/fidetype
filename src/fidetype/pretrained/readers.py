"""Readers of the public data files that the pretrained decoders take (P14-01). Our own code (Apache-2.0).

Each reader returns :class:`Item` objects: one decodable unit (a trial, a text prompt, a typing
burst) with its input array and a pseudonymous key. The ground truth (``truth``) is for evaluation
only; it never goes into a stream.

- Brain-to-Text '25 (T15, CC0): ``data_*.hdf5`` of one session folder (``t15.YYYY.MM.DD``); one
  HDF5 group per trial with ``input_features`` (T x 512) and the attribute ``sentence_label``.
  Needs ``h5py`` (``pip install fidetype[hdf5]``; the old extra name ``emg2qwerty`` also works).
- Brain-to-Text '24 (T12, CC0): ``competitionData/{train,test}/t12.YYYY.MM.DD.mat``. The decoder
  input is ``tx1`` + ``spikePow`` (T x 512), z-scored per trial with the statistics of the 20
  previous trials of the session (train file first, then test file; T12 v2 recipe). So a test file
  needs its train file (found next to it). Needs ``scipy`` (``pip install fidetype[data]``).
- emg2qwerty (CC BY-NC-SA 4.0, research only): one ``*.hdf5`` session; one item per text prompt.
  Needs ``h5py`` (``pip install fidetype[hdf5]``).
- Willett handwriting 2021 (T5, CC0): ``Datasets/t5.YYYY.MM.DD/sentences.mat``; one item per
  sentence: threshold crossings (T x 192, 10 ms bins) from the go cue to the sentence end plus up to
  1 s of tail. Needs ``scipy`` (``pip install fidetype[data]``).
- KT-sEMG (CC BY 4.0, Nokia): ``runN.csv`` + ``runN_keys.txt`` + ``runN_ts.txt``; one item per
  typing burst (key times from the key log, as the ``kt-semg`` benchmark track).

These readers treat every file as untrusted data: no pickle, read-only access.

:func:`count_items` gives the number of items of a file without decoding it (P14-44).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any

import numpy as np

__all__ = ["Item", "count_items", "count_b2t25_hdf5", "check_indices", "read_b2t25_hdf5", "read_b2t24_session", "b2t24_normalise", "read_emg2qwerty_session",
           "read_kt_run", "read_willett_session", "willett_test_block", "T15_SESSION", "T12_SESSION",
           "T5_SESSION"]

T15_SESSION = re.compile(r"^t15\.\d{4}\.\d{2}\.\d{2}$")
T12_SESSION = re.compile(r"^t12\.\d{4}\.\d{2}\.\d{2}$")
T5_SESSION = re.compile(r"^t5\.\d{4}\.\d{2}\.\d{2}$")


@dataclass
class Item:
    """One decodable unit of a file."""

    key: str  # pseudonymous: session folder / file name + index; no text
    x: Any  # the decoder input (array), or None when the runtime reads the file itself
    session: str | None = None
    truth: str | None = None  # evaluation only; never written to a stream
    extra: dict[str, Any] = field(default_factory=dict)


def _h5py() -> Any:
    try:
        import h5py  # optional dependency
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise ImportError("reading HDF5 files needs h5py: pip install \"fidetype[hdf5]\"") from e
    return h5py


def check_indices(indices: Any, n: int, where: str) -> None:
    """Raise a clear ``IndexError`` if an index is outside ``-n .. n-1`` (P14-44)."""
    bad = [i for i in indices if not -n <= int(i) < n]
    if bad:
        raise IndexError(f"{where}: index {bad[0]} is out of range: the file has {n} items (indices 0..{n - 1}); "
                         f"count them with n_items()")


def count_b2t25_hdf5(path: str | PathLike[str]) -> int:
    """The number of trials of one B2T '25 HDF5 file (no data is read)."""
    with _h5py().File(Path(path), "r") as f:
        return len(f.keys())


def read_b2t25_hdf5(path: str | PathLike[str], limit: int | None = None, indices: list[int] | None = None) -> list[Item]:
    """Trials of one B2T '25 HDF5 file. ``indices``: trial positions in sorted group order (default all).

    An index outside ``-n .. n-1`` raises ``IndexError`` with the trial count of the file.
    """
    h5py = _h5py()

    p = Path(path)
    sess = p.parent.name
    out: list[Item] = []
    with h5py.File(p, "r") as f:
        keys = sorted(f.keys())
        if indices is not None:
            check_indices(indices, len(keys), p.name)
        sel = range(len(keys)) if indices is None else indices
        for i in sel:
            g = f[keys[i]]
            x = np.asarray(g["input_features"][()], dtype=np.float32)
            if x.ndim != 2:
                raise ValueError(f"{p.name}/{keys[i]}: input_features is not 2-D")
            lab = g.attrs.get("sentence_label", None)
            if isinstance(lab, bytes):
                lab = lab.decode("utf-8")
            out.append(Item(key=f"{sess}|{p.stem}|{i}", x=x, session=sess, truth=None if lab is None else str(lab),
                            extra={"block": int(g.attrs.get("block_num", -1)), "trial": int(g.attrs.get("trial_num", -1))}))
            if limit is not None and len(out) >= limit:
                break
    return out


def _load_mat(p: Path) -> tuple[list[np.ndarray], list[str]]:
    import scipy.io  # optional dependency

    m = scipy.io.loadmat(str(p))
    n = m["sentenceText"].shape[0]
    texts = [str(m["sentenceText"][i]).rstrip() for i in range(n)]
    feats = []
    for i in range(n):
        tx = np.asarray(m["tx1"][0, i] if m["tx1"].shape[0] == 1 else m["tx1"][i, 0], dtype=np.float32)
        sp = np.asarray(m["spikePow"][0, i] if m["spikePow"].shape[0] == 1 else m["spikePow"][i, 0], dtype=np.float32)
        feats.append(np.concatenate([tx, sp], axis=1))
    return feats, texts


def b2t24_normalise(seq: list[np.ndarray], window: int = 20, clip: float = 10.0) -> list[np.ndarray]:
    """Causal rolling z-score of the T12 v2 recipe (float16-rounded, as in training)."""
    sums = [(x.astype(np.float64).sum(0), (x.astype(np.float64) ** 2).sum(0), x.shape[0]) for x in seq]

    def stats(lo: int, hi: int) -> tuple[np.ndarray, np.ndarray]:
        s1 = sum(sums[k][0] for k in range(lo, hi))
        s2 = sum(sums[k][1] for k in range(lo, hi))
        n = sum(sums[k][2] for k in range(lo, hi))
        mu = s1 / n
        sd = np.sqrt(np.maximum(s2 / n - mu ** 2, 0.0))
        sd[sd < 1e-6] = 1.0
        return mu, sd

    first = stats(0, min(window, len(seq)))
    out = []
    for j, x in enumerate(seq):
        mu, sd = first if j < window else stats(j - window, j)
        out.append(np.clip((x - mu) / sd, -clip, clip).astype(np.float16).astype(np.float32))
    return out


def read_b2t24_session(path: str | PathLike[str], *, window: int = 20, clip: float = 10.0,
                       limit: int | None = None) -> list[Item]:
    """Trials of one B2T '24 ``.mat`` file, normalised with the session history.

    ``path`` in ``test/`` (or ``competitionHoldOut/``): the train file of the same session
    (``../train/<name>.mat``) gives the history. ``path`` in ``train/``: its own trials only.
    """
    p = Path(path)
    sess = p.stem
    if not T12_SESSION.match(sess):
        raise ValueError(f"{p.name}: expected a session file t12.YYYY.MM.DD.mat")
    feats, texts = _load_mat(p)
    hist: list[np.ndarray] = []
    if p.parent.name != "train":
        tr = p.parent.parent / "train" / p.name
        if not tr.is_file():
            raise FileNotFoundError(f"the T12 recipe needs the train file of the session for the rolling "
                                    f"normalisation: {tr} is missing")
        hist, _ = _load_mat(tr)
    Z = b2t24_normalise(hist + feats, window, clip)[len(hist):]
    out = []
    for i, (z, t) in enumerate(zip(Z, texts)):
        out.append(Item(key=f"{sess}|{p.parent.name}|{i}", x=z, session=sess, truth=t))
        if limit is not None and len(out) >= limit:
            break
    return out


def read_emg2qwerty_session(path: str | PathLike[str]) -> tuple[Any, list[Item]]:
    """Open one emg2qwerty session (``fidetype.adapters.emg2qwerty.Session``). Items = text prompts.

    Returns ``(session, items)``; the caller closes the session. ``item.extra`` holds the sample range
    ``lo``, ``hi`` of the prompt. ``item.truth`` is the typed text of the prompt keys.
    """
    from fidetype.adapters import emg2qwerty as e2q

    sess = e2q.Session(path)
    try:
        events = e2q.key_events(sess)
        items = []
        t0 = sess.t0
        for p in sess.prompts:
            if p.end - t0 < 0 or p.start - t0 > sess.duration_s:
                continue
            lo, hi = (int(v) for v in sess.sample_index([p.start, p.end]))
            if hi - lo < 64:
                continue
            ev = e2q.prompt_events(sess, p, events)
            items.append(Item(key=f"{Path(path).stem}|prompt|{p.index}", x=None, truth=e2q.typed_text(ev),
                              extra={"lo": lo, "hi": hi, "n_keys": len(ev)}))
    except Exception:
        sess.close()
        raise
    return sess, items


def read_kt_run(csv: str | PathLike[str], max_gap_s: float = 2.0, min_keys: int = 5) -> tuple[np.ndarray, list[Item]]:
    """One KT-sEMG run: the EMG (n, 32) and one item per typing burst (key times in ``extra['times']``)."""
    from fidetype.adapters import kt_semg as K
    from fidetype.live.build import kt_run_events, kt_segments, kt_text

    c = Path(csv)
    if not re.fullmatch(r"run\d+", c.stem):
        raise ValueError(f"{c.name}: expected runN.csv")
    keys, ts = c.with_name(f"{c.stem}_keys.txt"), c.with_name(f"{c.stem}_ts.txt")
    rec = K.read_emg_csv(c)
    events = kt_run_events(str(c), str(keys), str(ts), rec.n_samples)
    items = []
    for j, (a, b) in enumerate(kt_segments(events, max_gap_s=max_gap_s, min_keys=min_keys)):
        ev = events[a:b]
        items.append(Item(key=f"{c.stem}|segment|{j}", x=None, truth=kt_text(ev),
                          extra={"times": [float(e.t) for e in ev], "codes": [K.key_code(e.char) for e in ev],
                                 "run": int(c.stem[3:]), "segment": j}))
    return rec.emg, items


#: Variables read from a Willett ``sentences.mat`` (MATLAB 5 file: plain arrays, no code).
WILLETT_VARS = ("intendedText", "numTimeBinsPerSentence", "sentenceCondition", "sentenceBlockNums",
                "excludedSentences", "neuralActivityTimeSeries", "blockNumsTimeSeries", "goCueOnsetTimeBin")
WILLETT_TAIL = 100  # frames kept after the sentence end (the causal decoder emits late; P15-08 recipe)


def read_willett_session(path: str | PathLike[str], *, include_excluded: bool = False,
                         blocks: list[int] | None = None, limit: int | None = None,
                         max_bytes: int = 400_000_000) -> list[Item]:
    """Sentences of one Willett handwriting session (``t5.YYYY.MM.DD`` folder or its ``sentences.mat``).

    ``item.x``: uint8 threshold crossings (T, 192) from the go cue to the sentence end, plus up to
    ``WILLETT_TAIL`` frames while the block goes on (same cut as P15-08). ``item.truth``: the
    intended text ('>' -> space, '~' -> period, '#' dropped). ``item.extra``: ``trial``, ``block``,
    ``excluded``, ``n_write`` (bins of writing time), ``cond``. Excluded sentences and sentences
    with empty text are skipped unless ``include_excluded``. ``blocks``: keep only these blocks.
    ``max_bytes`` limits the file size (untrusted input; the public files are under 50 MB).
    """
    import scipy.io  # optional dependency

    from fidetype.pretrained._xbody import willett_text

    p = Path(path)
    if p.is_dir():
        p = p / "sentences.mat"
    sess = p.parent.name
    if not T5_SESSION.match(sess):
        raise ValueError(f"{p}: expected <t5.YYYY.MM.DD>/sentences.mat")
    if p.stat().st_size > max_bytes:
        raise ValueError(f"{p.name}: file too large ({p.stat().st_size} bytes)")
    m = scipy.io.loadmat(str(p), variable_names=list(WILLETT_VARS))
    ts = m["neuralActivityTimeSeries"]
    bts = m["blockNumsTimeSeries"].ravel()
    go = m["goCueOnsetTimeBin"].ravel().astype(np.int64) - 1  # MATLAB 1-based -> 0-based
    nb = m["numTimeBinsPerSentence"].ravel().astype(np.int64)
    blk = m["sentenceBlockNums"].ravel().astype(np.int64)
    exc = m["excludedSentences"].ravel().astype(bool)
    txt = [str(q[0][0]) if q[0].size else "" for q in m["intendedText"]]
    cond = [str(q[0][0]) if q[0].size else "" for q in m["sentenceCondition"]]
    out: list[Item] = []
    for i in range(len(nb)):
        text = willett_text(txt[i])
        if not include_excluded and (exc[i] or not text):
            continue
        if blocks is not None and int(blk[i]) not in blocks:
            continue
        a, b = int(go[i]), int(go[i] + nb[i])
        c = b
        while c < min(len(ts), b + WILLETT_TAIL) and bts[c] == bts[a]:
            c += 1
        x = np.clip(np.asarray(ts[a:c], np.float64), 0, 255).astype(np.uint8)
        out.append(Item(key=f"{sess}|sentences|{i}", x=x, session=sess, truth=text,
                        extra={"trial": i, "block": int(blk[i]), "excluded": bool(exc[i]), "n_write": int(nb[i]),
                               "cond": cond[i]}))
        if limit is not None and len(out) >= limit:
            break
    return out


def willett_test_block(items: list[Item]) -> int:
    """The held-out block of a session in the ``willett-hw`` split: the last block with a usable sentence."""
    ok = [it.extra["block"] for it in items if not it.extra["excluded"] and it.truth]
    if not ok:
        raise ValueError("no usable sentence in these items")
    return max(ok)


def count_items(file_format: str, path: str | PathLike[str], **kw: Any) -> int:
    """The number of decodable items (trials, prompts, typing bursts) of one data file (P14-44).

    ``file_format`` is the ``input.file_format`` of a model manifest. ``kw`` are the reader options
    that change the count (``blocks=`` for Willett files). B2T '25 counts the HDF5 groups without
    reading data. The other formats run the reader (the KT-sEMG reader also reads the EMG file).
    """
    if file_format == "b2t25-hdf5":
        return count_b2t25_hdf5(path)
    if file_format == "b2t24-mat":
        import scipy.io  # optional dependency

        return int(scipy.io.loadmat(str(path), variable_names=["sentenceText"])["sentenceText"].shape[0])
    if file_format == "willett-hw-mat":
        return len(read_willett_session(path, blocks=kw.get("blocks")))
    if file_format == "emg2qwerty-hdf5":
        sess, items = read_emg2qwerty_session(path)
        sess.close()
        return len(items)
    if file_format == "kt-semg-run":
        return len(read_kt_run(path)[1])
    raise ValueError(f"unknown input file format {file_format!r}")
