"""Tutorial 1: decode text with a pretrained decoder (10 minutes, CPU, no hardware).

Walk-through: docs/tutorials-01-decode.md

Two modes:

    python tutorials/01_decode_pretrained.py                     # synthetic: no download, about 5 s
    python tutorials/01_decode_pretrained.py --model t15-m4-13 \
        --weights <folder with the release files> \
        --data <b2t25>/t15.2023.08.13/data_val.hdf5 --n 5         # real public data

The synthetic mode makes a tiny random decoder and random "neural" input at run
time. It shows every API step, but its text is noise: the model has learned nothing.

Licence: Apache-2.0. Synthetic data only, unless you pass --data.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

import fidetype.conformance as conformance
import fidetype.pretrained as ftp


def step(n: int, text: str) -> None:
    print(f"\n--- step {n}: {text}")


# ------------------------------------------------------------------------------------------
# Synthetic mode: a tiny random GRU-CTC model in a temporary folder.
# The packaged models need weights that are not hosted yet, so this mode uses
# ftp.make_toy_manifest(): it writes random weights and a manifest that lists their SHA-256.
# ------------------------------------------------------------------------------------------


def run_synthetic(out: Path) -> dict:
    step(1, "list the registry (no weights needed)")
    for m in ftp.list_models():
        print(f"  {m.name:<20} {m.status:<10} research_only={str(m.research_only).lower()}")

    step(2, "make a toy model (the real weights are not hosted yet)")
    manifest = ftp.make_toy_manifest(out)  # or in one line: model = ftp.toy_model()
    print(f"  wrote {manifest.name} and its weights file into {out}")

    step(3, "load it: load() checks the size and the SHA-256 of every file")
    model = ftp.load(str(manifest), weights=out)
    print(f"  {model!r}")

    step(4, "decode: one (T, channels) array of 20 ms bins -> one NTS stream")
    rng = np.random.default_rng(1)
    streams = []
    for i in range(3):
        x = rng.standard_normal((200, 16)).astype(np.float32)  # 4 s of fake neural features
        streams.append(model.decode(x, session=model.sessions[0]))
    s = streams[0]
    print(f"  log_probs {s.log_probs.shape} (frames x tokens), vocab_type {s.vocab_type}, "
          f"frame period {s.frame_period} s")

    step(5, "check each stream with the conformance suite")
    levels = []
    for st in streams:
        rep = conformance.check(st)
        levels.append("provenance" if rep.passes("provenance") else "below provenance")
    print(f"  levels: {levels}")

    step(6, "read the greedy text (no language model)")
    print(f"  greedy phonemes of stream 0: {model.text(s)[:60]!r}")
    print("  (noise: the toy model is random)")

    step(7, "save the streams as NTS JSON Lines")
    paths = model.save(streams, out / "streams")
    print(f"  wrote {len(paths)} files, e.g. {paths[0].name}")

    step(8, "the trust guard: model.decide(stream) is the same call for every model")
    try:
        model.decide(s)
    except ftp.NoTrustConfig as e:
        print(f"  NoTrustConfig: {e}")
        print("  (expected: the toy model has no trust config; tutorial 2 calibrates one)")
    return {"mode": "synthetic", "streams": len(streams), "levels": levels}


# ------------------------------------------------------------------------------------------
# Real mode: a packaged model + a public data file.
# ------------------------------------------------------------------------------------------


def run_real(a: argparse.Namespace, out: Path) -> dict:
    step(1, f"read the model card of {a.model}")
    print("  " + ftp.info(a.model).card().replace("\n", "\n  ")[:1500])

    step(2, "load the model (weights from --weights, $FIDETYPE_PRETRAINED_DIR or the cache)")
    model = ftp.load(a.model, weights=a.weights, accept_research_only=a.accept_research_only)
    print(f"  {model!r}")

    step(3, f"decode {a.n} items of {Path(a.data).name}")
    if a.model.startswith("t15"):  # the odd trials (val_eval half); n_items() counts them without decoding
        n = model.n_items(a.data)
        kw = {"indices": list(range(1, n, 2))[: a.n]}
        print(f"  the file has {n} trials")
    else:
        kw = {"limit": a.n}
    pairs = model.decode_file(a.data, with_items=True, **kw)
    print(f"  {len(pairs)} streams")

    step(4, "conformance level and greedy text of each stream")
    levels = []
    for item, st in pairs:
        ok = conformance.check(st).passes("provenance")
        levels.append("provenance" if ok else "below provenance")
        print(f"  {item.key}: {st.log_probs.shape[0]} frames, {levels[-1]}")
        if a.show_text:
            print(f"    greedy: {model.text(st)[:80]}\n    truth:  {item.truth}")

    step(5, "save the streams")
    paths = model.save([st for _, st in pairs], out / "streams")
    print(f"  wrote {len(paths)} files to {out / 'streams'}")

    step(6, "the trust guard of the model (if one is packaged)")
    try:
        acts = [model.decide(st, utterance_id=it.key).action for it, st in pairs]  # the right guard input per model
        print(f"  actions: {acts}")
    except ftp.NoTrustConfig as e:
        print(f"  NoTrustConfig: {e}")
    return {"mode": "real", "model": a.model, "streams": len(pairs), "levels": levels}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Tutorial 1: decode text with a pretrained decoder.")
    ap.add_argument("--model", help="a packaged model name (fidetype decoders list); omit for the synthetic mode")
    ap.add_argument("--data", help="a public data file for --model")
    ap.add_argument("--weights", help="folder with the release files of --model")
    ap.add_argument("--n", type=int, default=5, help="number of items to decode (real mode)")
    ap.add_argument("--accept-research-only", action="store_true")
    ap.add_argument("--show-text", action="store_true", help="real mode: print greedy text and truth")
    ap.add_argument("--out", type=Path, help="output folder (default: a temporary folder)")
    a = ap.parse_args(argv)
    if bool(a.model) != bool(a.data):
        ap.error("give --model and --data together (or neither, for the synthetic mode)")
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="fidetype-tut1-") as tmp:
        out = a.out or Path(tmp)
        out.mkdir(parents=True, exist_ok=True)
        res = run_real(a, out) if a.model else run_synthetic(out)
        ok = all(lv == "provenance" for lv in res["levels"])
    print(f"\nTUTORIAL 1 {'PASS' if ok else 'FAIL'} ({res['mode']}): {res['streams']} streams, "
          f"{time.perf_counter() - t0:.1f} s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
