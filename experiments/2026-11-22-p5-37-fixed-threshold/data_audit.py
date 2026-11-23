r"""P5-37 (gap 189): data audit before any number. Which Willett handwriting sentences are not yet used?

Our own code (Apache-2.0). CPU only. Reads only the sentence metadata of the public ``sentences.mat`` files
(block numbers, the excluded flag, the intended text) and the P14-41 split record (read only). It computes no
log-prob, no guard decision and no gate value. Output: results/data-audit.json (counts only).

    C:\venvs\fidetype-rocm\Scripts\python.exe -I experiments/2026-11-22-p5-37-fixed-threshold/data_audit.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

RAW = Path(r"C:\Users\zhang\bci-data\raw\willett-handwriting\extracted\handwritingBCIData\Datasets")
P1441 = Path(r"C:\Users\zhang\bci-data\derived\p14-41")  # read only


def main() -> int:
    import scipy.io

    from fidetype.pretrained._xbody import VOCAB, willett_text

    mt = json.loads((P1441 / "items.json").read_text(encoding="utf-8"))
    tb = {s: int(b) for s, b in mt["test_blocks"].items()}
    vb = {s: int(b) for s, b in mt["val_blocks"].items()}
    vocab = set(VOCAB[1:])
    sess = [p for p in sorted(RAW.iterdir()) if p.is_dir() and (p / "sentences.mat").exists()]
    no_sent = [p.name for p in sorted(RAW.iterdir()) if p.is_dir() and not (p / "sentences.mat").exists()]
    keys = ("test_ok", "val_ok", "pool_ok", "excluded_test", "excluded_val", "excluded_pool", "empty_not_excluded",
            "out_of_vocab_not_excluded")
    tot = dict.fromkeys(keys, 0)
    per = {}
    for si, p in enumerate(sess):
        m = scipy.io.loadmat(str(p / "sentences.mat"),
                             variable_names=["excludedSentences", "sentenceBlockNums", "intendedText"])
        exc = m["excludedSentences"].ravel().astype(bool)
        blk = m["sentenceBlockNums"].ravel().astype(int)
        txt = [willett_text(str(q[0][0]) if q[0].size else "") for q in m["intendedText"]]
        c = dict.fromkeys(keys, 0)
        for i in range(len(exc)):
            where = "test" if blk[i] == tb[str(si)] else "val" if blk[i] == vb[str(si)] else "pool"
            if exc[i]:
                c["excluded_" + where] += 1
            elif not txt[i]:
                c["empty_not_excluded"] += 1
            elif not all(ch in vocab for ch in txt[i]):
                c["out_of_vocab_not_excluded"] += 1
            else:
                c[where + "_ok"] += 1
        c["n"] = len(exc)
        per[p.name] = c
        for k in keys:
            tot[k] += c[k]
    tot["n"] = sum(c["n"] for c in per.values())
    out = {"sessions_with_sentences": len(sess), "sessions_without_sentences": no_sent,
           "p14_41_n_test": len(mt["test"]), "p14_41_n_val": len(mt["val"]),
           "single_letters_files": sum((p / "singleLetters.mat").exists() for p in sess),
           "total": tot, "per_session": per}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "data-audit.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out["total"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
