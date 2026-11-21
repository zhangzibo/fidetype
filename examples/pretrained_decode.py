"""Decode a few public test items with a pretrained decoder, end to end (P14-01).

load (SHA-256 checked) -> decode a public data file -> NTS streams -> conformance level
-> committed trust guard -> one line per item, plus an aggregate error rate against the truth of the file.

The weights are not in the package. Put the release files in the cache folder
(``fidetype decoders path``) or pass ``--weights <folder>``. Examples (data files from the original
sources; see docs/pretrained-decoders.md)::

    python examples/pretrained_decode.py t15-m4-13 <b2t25>/t15.2023.08.13/data_val.hdf5 --n 5 --odd
    python examples/pretrained_decode.py t12-v2 <competitionData>/test/t12.2022.08.25.mat --n 5
    python examples/pretrained_decode.py kt-semg-lda <kt-semg>/run28.csv --n 3
    python examples/pretrained_decode.py emg2qwerty-p11-01 <session>.hdf5 --n 3 --accept-research-only

The script prints no decoded text unless ``--show-text`` is given.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

import fidetype.conformance as C
import fidetype.pretrained as ftp
from fidetype.eval.metrics import edit_distance


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("model")
    ap.add_argument("file")
    ap.add_argument("--n", type=int, default=3, help="number of items")
    ap.add_argument("--odd", action="store_true", help="B2T '25 only: take the odd trials (the val_eval half)")
    ap.add_argument("--weights")
    ap.add_argument("--accept-research-only", action="store_true")
    ap.add_argument("--no-guard", action="store_true")
    ap.add_argument("--show-text", action="store_true")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        m = ftp.load(a.model, weights=a.weights, accept_research_only=a.accept_research_only)
    except ftp.PretrainedError as e:  # research-only gate, missing or damaged weights, planned model
        print(f"cannot load {a.model}: {e}", file=sys.stderr)
        return 2
    print(m.card(), "\n")
    kw = {"indices": [2 * i + 1 for i in range(a.n)]} if a.odd else {"limit": a.n}
    pairs = m.decode_file(a.file, with_items=True, **kw)
    guard = None
    if not a.no_guard:
        try:
            guard = m.guard()
        except ftp.NoTrustConfig as e:
            print(f"(no guard: {e})\n")
    edits = total = 0
    for it, st in pairs:
        rep = C.check(st)
        line = f"{it.key}: {st.n_frames} frames, NTS level {rep.level}"
        r = None
        if guard is not None:
            r = m.decide(st, guard=guard)  # the right guard input for each model (m.guard_input)
            line += f", guard {r.action} (p_top1 {r.p_top1:.2f})"
        hyp = m.text(st)
        if isinstance(m, ftp.KeyLdaDecoder):  # key accuracy: argmax key per press vs the logged key
            from fidetype.adapters.kt_semg import KEY_VOCAB

            pred = [KEY_VOCAB[i] for i in np.argmax(st.log_probs, axis=1)]
            e = sum(p != c for p, c in zip(pred, it.extra["codes"]))
            n = len(pred)
        elif isinstance(m, ftp.CrtCtcDecoder):  # CER against the typed text (Backspace / Enter as symbols)
            ref = (it.truth or "").replace("\b", "⌫").replace("\r", "⏎")
            e, n = edit_distance(ref, hyp), len(ref)
        elif r is not None and it.truth is not None:  # phoneme decoders: WER of the guard's top-1 words
            from fidetype.adapters.b2t25 import normalize_words

            ref_w = normalize_words(it.truth).split()
            top = r.text or (r.choices[0] if r.choices else "")  # committed text, or the first offered choice
            e, n = edit_distance(ref_w, top.split()), len(ref_w)
        else:  # no word decoder: frames only
            e = n = 0
        edits, total = edits + e, total + n
        if n:
            line += f", errors {e}/{n}"
        print(line)
        if a.show_text:
            print(f"    decoded: {hyp}\n    truth:   {it.truth}")
    if total:
        print(f"\naggregate error rate: {edits / total:.3f} ({edits}/{total})")
    print(f"{len(pairs)} streams; weights sha256 {m.weights_sha256[:16]}...; data licence {m.manifest.data_licence}; "
          f"research_only {str(m.research_only).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
