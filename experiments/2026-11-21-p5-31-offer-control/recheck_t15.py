"""P5-31: offer null control re-check of the packaged t15-m4-13 guard (no new calibration).

The calibration inputs and decode_fn are rebuilt exactly as in experiments/2026-11-16-p14-05-safe-wpm/run.py
(stage_t15_compute, model m4-13). Writes recheck-t15.json next to this script.
"""
import ctypes
import os
os.environ.setdefault("FIDETYPE_PRETRAINED_DIR", "C:/Users/zhang/bci-data/pretrained")
import json
import time
from pathlib import Path

import numpy as np

ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL

HERE = Path(__file__).resolve().parent / "results"
REPO = Path(r"C:\Users\zhang\OneDrive\Documents\GitHub\stealth-project")


def main() -> None:
    t0 = time.time()
    import importlib.util

    def load_module(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    r05 = load_module("p1405run", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
    import fidetype.trust as ft

    p1403 = r05.load_module("p1403run", REPO / "experiments/2026-11-16-p14-03-replay-validation/run.py")
    d_in = r05.DER / "m4-01-02-lookahead"
    sessions = json.loads((d_in / "sessions.json").read_text(encoding="utf-8"))
    cal_p = r05.DER / "trust-reruns-m4-13" / "logprobs-m4-13-long0-val_select.npz"
    z = np.load(cal_p)
    keys = r05.t15_keys(cal_p, sessions, "val_select")
    cx = [z[k].astype(np.float32) for k in keys]
    bt = r05.load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    tune = bt.load_json("tune.json")
    dec = bt.Decoders([], {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    fn = p1403.make_decode_fn(dec)
    guard = ft.load(REPO / "src/fidetype/pretrained/guards/t15-m4-13.guard.json", decode_fn=fn)
    print("loaded", guard.config_id, len(cx), f"{time.time() - t0:.0f} s", flush=True)
    out = ft.recheck_offer_control(guard, cx)
    out.update(guard="t15-m4-13", config_id=guard.config_id, seconds=round(time.time() - t0, 1))
    (HERE / "recheck-t15.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
