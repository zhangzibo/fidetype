"""P11-21 check X2' (plan amendment 1): fresh analyses of session a / b windows equal this item's memo. CPU only.

    python -I x2_fresh.py <code_root> <tag>

<code_root> holds the code to test (``src/`` and the P11-16 / P11-14 runners), for example the run snapshot or the
P11-20 snapshot. The analyser is the P11-16 ``A16`` class with an EMPTY memo (no load, no save): every window is
decoded again. Windows: the 203 a / b windows where this item's memo and the P11-23 memo differ, plus 100 other a / b
windows (``default_rng(2121).choice``). Output: C:/Users/zhang/bci-data/derived/p11-21/x2-fresh-<tag>.json
(counts only). The P11-20 and P11-23 files are read only.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pickle
import sys
import time
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ.setdefault("HIP_VISIBLE_DEVICES", "")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import numpy as np  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p11-21"
TOL = 1e-9


def same_analysis(a: dict | None, b: dict | None, signals, with_fu: bool = True) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if a["status"] != b["status"]:
        return False
    if a["status"] != "ok":
        return True
    if a["top"] != b["top"] or len(a["native"]) != len(b["native"]):
        return False
    if any(t1 != t2 or abs(s1 - s2) > TOL for (t1, s1), (t2, s2) in zip(a["native"], b["native"])):
        return False
    if any(abs(float(a["sig"][s]) - float(b["sig"][s])) > TOL for s in signals):
        return False
    if with_fu:
        fa, fb = a.get("fU") or [], b.get("fU") or []
        if len(fa) != len(fb) or any(t1 != t2 or abs(s1 - s2) > TOL for (t1, s1), (t2, s2) in zip(fa, fb)):
            return False
    return True


def main() -> int:
    root, tag = Path(sys.argv[1]), sys.argv[2]
    sys.path.insert(0, str(root / "src"))
    spec = importlib.util.spec_from_file_location(
        "p1116run", root / "experiments" / "2026-11-21-p11-16-emg-prefix-confidence" / "run.py")
    P = importlib.util.module_from_spec(spec)
    sys.modules["p1116run"] = P
    spec.loader.exec_module(P)
    P.OWN = OWN / "x2-empty-memo"  # make_analyser() loads <OWN>/feat.pkl: absent -> empty memo; never saved
    P.OUT = OWN / "x2-empty-memo"
    import fidetype

    M = P.m14()
    R, cal, ev = M.setup()
    from fidetype.adapters import emg2qwerty as A

    ab = json.loads((DER / "p11-20" / "prompts-ab.json").read_text(encoding="utf-8"))
    base = R.p1109().Windows()
    mm: dict = {}

    def win(r: dict) -> np.ndarray:
        name = f"u{r['i']}-{r['j']}-real.npy"
        if name not in mm:
            mm[name] = np.load(DER / "p11-20" / "lp" / name, mmap_mode="r", allow_pickle=False)
        return A.merge_to_key_ctc(np.asarray(mm[name][r["lo"]:r["end"]]), base.vocab)

    xs = [win(r) for r in ab]
    keys = [R.window_key(x) + "|FL" for x in xs]
    ks = set(keys)
    with open(OWN / "feat-w0.pkl", "rb") as fh:
        d = pickle.load(fh)
    mine = {k: d[k] for k in ks}
    del d
    ref: dict = {}
    for w in range(2):
        with open(DER / "p11-23" / f"feat-w{w}.pkl", "rb") as fh:
            d = pickle.load(fh)
        ref.update({k: d[k] for k in ks if k in d})
        del d
    diff = [i for i, k in enumerate(keys) if not same_analysis(mine[k], ref[k], M.SIGNALS, with_fu=False)]
    maxd = 0.0
    for i in diff:
        a, b = mine[keys[i]], ref[keys[i]]
        if a and b and a["status"] == "ok" and len(a["native"]) == len(b["native"]):
            maxd = max(maxd, max(abs(s1 - s2) for (_, s1), (_, s2) in zip(a["native"], b["native"])))
    rest = sorted(set(range(len(ab))) - set(diff))
    extra = sorted(np.random.default_rng(2121).choice(rest, size=100, replace=False).tolist())
    an = P.make_analyser()
    assert not an.memo, "the memo must be empty"
    t0 = time.time()
    bad_d = sum(not same_analysis(an.analyse(np.asarray(xs[i], np.float64), "FL"), mine[keys[i]], M.SIGNALS)
                for i in diff)
    bad_e = sum(not same_analysis(an.analyse(np.asarray(xs[i], np.float64), "FL"), mine[keys[i]], M.SIGNALS)
                for i in extra)
    out = {"tag": tag, "code_root": str(root), "fidetype": fidetype.__file__,
           "revision": (root / "REVISION").read_text().strip() if (root / "REVISION").exists() else "working tree",
           "descriptive_vs_p11_23_memo": {"windows": len(keys), "mismatch": len(diff), "max_native_diff": maxd},
           "fresh_vs_this_item": {"mismatch_windows": len(diff), "mismatch_windows_fail": int(bad_d),
                                  "other_windows": len(extra), "other_windows_fail": int(bad_e)},
           "seconds": round(time.time() - t0, 1)}
    out["pass"] = bool(bad_d == 0 and bad_e == 0 and len(extra) == 100)
    (OWN / f"x2-fresh-{tag}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
