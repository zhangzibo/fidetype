"""Choose the word-trigram weight beta of the sentence LM on decoder-validation data only (M3-28).
Writes results/lm-tune.json (aggregate numbers only).
Run (repo root): .venv\Scripts\python.exe -I experiments/2026-11-13-confirmatory-t12-v2/lm_tune.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as R  # noqa: E402


def main() -> None:
    D = R.Data("logprobs-val")
    bt = R.load_b2t25()
    val, _ = D.items("val", D.sessions)
    out = {"checkpoint_sha256": D.lpmeta["checkpoint_sha256"], "epoch": D.lpmeta["epoch"], "grid": {}}
    for beta in R.CFG["word_lm"]["grid"]:
        t0 = time.time()
        dec = R.decoders(bt, beta)
        q = R.quality(dec.words_fn, val)
        q["seconds"] = round(time.time() - t0, 1)
        out["grid"][str(beta)] = q
        R.log("lm-tune beta", beta, json.dumps(q))
    R.T.dump(out, R.OUT / "lm-tune.json")


if __name__ == "__main__":
    main()
