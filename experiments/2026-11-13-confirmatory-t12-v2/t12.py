"""Shared code for the confirmatory T12 test v2 (M3-28; copied from M3-27). Our own code.

Data: Willett et al. 2023 / Brain-to-Text '24 ``competitionData`` (CC0).
Each ``.mat`` file holds one session (``t12.YYYY.MM.DD.mat``) with the
fields ``sentenceText``, ``spikePow``, ``tx1``..``tx4`` and ``blockIdx``
(see ``competitionData_readme.txt``). This module never writes text or
signals into the repo: derived files go to ``DERIVED`` (outside the repo).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
RAW = Path(CONFIG["raw_dir"])
EXTRACT = Path(CONFIG["extract_dir"])
DERIVED = Path(CONFIG["derived_dir"])
RESULTS = HERE / "results"

from fidetype.adapters import b2t25 as B  # noqa: E402

PH_ID = {p: i for i, p in enumerate(B.VOCAB)}  # 0 blank, 1 SIL, 2..40 phonemes


def load_cmudict(path: str) -> dict[str, list[str]]:
    """word -> first pronunciation (phonemes without stress)."""
    out: dict[str, list[str]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split("#")[0].split()
            if len(parts) < 2:
                continue
            w = re.sub(r"\(\d+\)$", "", parts[0].lower())
            if w in out:
                continue
            out[w] = [re.sub(r"\d", "", p) for p in parts[1:]]
    return out


def phonemize(words: str, cmu: dict[str, list[str]]) -> tuple[list[str], bool]:
    """Phonemes with SIL between words; second value = all words known."""
    ph: list[str] = []
    ok = True
    for w in words.split():
        p = cmu.get(w)
        if p is None:
            ok = False
            continue
        if ph:
            ph.append("SIL")
        ph.extend(p)
    return ph, ok


def session_files(part: str) -> list[Path]:
    d = EXTRACT / "competitionData" / part
    return sorted(d.glob("*.mat"))


def session_name(p: Path) -> str:
    return p.stem


def load_session(p: Path) -> dict:
    """Return dict with features (list of T x 512 float32), texts, blocks."""
    import scipy.io

    m = scipy.io.loadmat(str(p))
    n = m["sentenceText"].shape[0]
    texts = [str(m["sentenceText"][i]).rstrip() for i in range(n)]
    feats = []
    for i in range(n):
        tx = np.asarray(m["tx1"][0, i] if m["tx1"].shape[0] == 1 else m["tx1"][i, 0], dtype=np.float32)
        sp = np.asarray(m["spikePow"][0, i] if m["spikePow"].shape[0] == 1 else m["spikePow"][i, 0], dtype=np.float32)
        feats.append(np.concatenate([tx, sp], axis=1))
    blocks = np.asarray(m["blockIdx"]).reshape(-1).astype(int)
    return {"features": feats, "texts": texts, "blocks": blocks}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def dump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (np.floating,)):
            o = float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, float) and not np.isfinite(o):
            return str(o)
        return o

    path.write_text(json.dumps(clean(obj), indent=1), encoding="utf-8")
