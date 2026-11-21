"""P5-31: offer null control re-check of the packaged willett-hw guards (no new calibration).

Usage: python recheck_willett.py lm|builtin  -> writes recheck-<which>.json next to this script.
"""
import ctypes
import os
os.environ.setdefault("FIDETYPE_PRETRAINED_DIR", "C:/Users/zhang/bci-data/pretrained")
import json
import sys
import time
from pathlib import Path

import numpy as np

ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL

HERE = Path(__file__).resolve().parent / "results"
DER = Path("C:/Users/zhang/bci-data/derived")


def load_lps(own: Path, split: str, kind: str):
    with np.load(own / f"lp_{split}_{kind}.npz") as z:
        return [np.asarray(z[f"arr_{i}"], np.float32) for i in range(len(z.files))]


def main(which: str) -> None:
    import fidetype.trust as ft

    t0 = time.time()
    if which == "lm":
        # The packaged LM-readout guard (P14-49: lm2, blocked LM, score gate), its calibration inputs from P14-48.
        import fidetype.pretrained as ftp

        rg = ftp.load("willett-hw").lm_readout()
        guard = ft.load(DER / "p14-49" / "willett-hw.lm2.guard.json", decode_fn=rg.decode_fn())
        own = DER / "p14-48"
    else:
        own = DER / "p14-41"
        guard = ft.load(own / "willett-hw.guard.json")
    lp_val, nulls = load_lps(own, "val", "real"), load_lps(own, "val", "timeshuf")
    out = ft.recheck_offer_control(guard, lp_val, null_inputs=nulls)
    out.update(guard=which, config_id=guard.config_id, seconds=round(time.time() - t0, 1))
    (HERE / f"recheck-{which}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
