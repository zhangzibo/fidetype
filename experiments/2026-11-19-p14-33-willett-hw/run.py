r"""P14-33: the Willett handwriting decoder ``willett-hw`` in the pretrained registry (CPU only). Our own code.

Stages:
  numpy  ``fidetype.pretrained.load("willett-hw")`` (NumPy runtime, no PyTorch) decodes the public
         ``sentences.mat`` of the 10 sessions; greedy test CER on the P15-08 test blocks, compared
         with the stored PyTorch result of run R-all-s0 (per-sentence edits). Saves the test and
         val log-probs to the local folder (for the next stages).
  torch  PyTorch on CPU (the P15-08 ``XBody`` class, the original checkpoint ``final.pt``) on the
         same test sentences: max abs log-prob difference to the NumPy runtime and its CER.
         Needs the torch venv; the GPU is hidden (HIP/CUDA_VISIBLE_DEVICES=-1).
  guard  ``fidetype.trust.calibrate`` on the val blocks (106 sentences; nulls = time-shuffled val
         sentences), then decisions on the test blocks (real and time-shuffled).

Aggregates go to ``results/results.json`` (no text). Per-sentence records (decoded text, truth) and
the guard file stay in ``C:\Users\zhang\bci-data\derived\p14-33-willett-hw`` (R-24).

Run (repo root)::

    .venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- ^
        .venv\Scripts\python.exe -I experiments/2026-11-19-p14-33-willett-hw/run.py numpy guard
    .venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- ^
        C:\venvs\fidetype-rocm\Scripts\python.exe -I experiments/2026-11-19-p14-33-willett-hw/run.py torch
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("FIDETYPE_PRETRAINED_DIR", r"C:\Users\zhang\bci-data\pretrained")
os.environ["HIP_VISIBLE_DEVICES"] = "-1"  # CPU only: the GPU belongs to another job
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DATA = Path(r"C:\Users\zhang\bci-data")
RAW = DATA / "raw/willett-handwriting/extracted/handwritingBCIData/Datasets"
P15 = DATA / "derived/p15-08"
RUN = P15 / "runs/R-ball-s0"
OWN = DATA / "derived/p14-33-willett-hw"
OUT = HERE / "results"
SALT = "fidetype-p15-08-2026-11-19"
ALPHA, DELTA, SEED = 0.05, 0.1, 0


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    OUT.mkdir(exist_ok=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def save_json(obj, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def results() -> dict:
    p = OUT / "results.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def update_results(key: str, val) -> None:
    r = results()
    r[key] = val
    save_json(r, OUT / "results.json")


def val_block(si: int, blocks: list[int], test_b: int) -> int:
    """The P15-08 val block of session index ``si``: salted SHA-256 over the non-test blocks."""
    rest = sorted(b for b in set(blocks) if b != test_b)
    return min(rest, key=lambda b: hashlib.sha256("|".join([SALT, "val", str(si), str(b)]).encode()).hexdigest())


def split_items(m) -> dict:
    """Session index, items of the test and val blocks of every session (P15-08 split, recomputed)."""
    from fidetype.pretrained import readers as R

    sessions = m.manifest.architecture["sessions"]
    out = {"test": [], "val": [], "test_blocks": {}, "val_blocks": {}}
    for si, s in enumerate(sessions):
        items = [it for it in R.read_willett_session(RAW / s) if it.truth and all(c in m_vocab() for c in it.truth)]
        tb = R.willett_test_block(items)
        vb = val_block(si, [it.extra["block"] for it in items], tb)
        out["test"] += [it for it in items if it.extra["block"] == tb]
        out["val"] += [it for it in items if it.extra["block"] == vb]
        out["test_blocks"][str(si)], out["val_blocks"][str(si)] = tb, vb
    return out


def m_vocab() -> set[str]:
    from fidetype.pretrained._xbody import VOCAB

    return set(VOCAB[1:])


def cer_records(m, items, lps) -> tuple[list[int], list[int], list[str]]:
    from fidetype.eval.metrics import edit_distance

    ed, ref, hyp = [], [], []
    for it, lp in zip(items, lps):
        h = m.text(m._stream(lp, it.key))
        ed.append(edit_distance(it.truth, h))
        ref.append(len(it.truth))
        hyp.append(h)
    return ed, ref, hyp


def stage_numpy() -> None:
    import fidetype.conformance as C
    import fidetype.pretrained as ftp

    t0 = time.time()
    m = ftp.load("willett-hw")
    sp = split_items(m)
    ref_splits = json.loads((P15 / "willett/splits.json").read_text(encoding="utf-8"))
    same_split = (sp["test_blocks"] == {k: int(v) for k, v in ref_splits["test_blocks"].items()}
                  and sp["val_blocks"] == ref_splits["val_blocks"])
    log(f"numpy: {len(sp['test'])} test, {len(sp['val'])} val sentences; split equal to P15-08: {same_split}")
    lp_test = [m.log_probs(it.x, it.session) for it in sp["test"]]
    t_test = time.time() - t0
    ed, ref, hyp = cer_records(m, sp["test"], lp_test)
    stored = json.loads((RUN / "result.json").read_text(encoding="utf-8"))
    cer = sum(ed) / sum(ref)
    n_eq = int(sum(a == b for a, b in zip(ed, stored["test_edits_final"])))
    log(f"numpy: test greedy CER {cer:.4f} ({sum(ed)} / {sum(ref)}); stored PyTorch (GPU) {stored['test_cer_final']:.4f}; "
        f"per-sentence edits equal {n_eq} / {len(ed)} ({time.time() - t0:.0f} s)")
    # NTS level of every test stream (the decode_file path)
    n_prov = 0
    for it, lp in zip(sp["test"], lp_test):
        n_prov += C.check(m._stream(lp, it.key)).passes("provenance")
    # decode_file equals the direct path (one session)
    s0 = m.manifest.architecture["sessions"][1]
    pairs = m.decode_file(RAW / s0, with_items=True, blocks=[sp["test_blocks"]["1"]])
    k = [i for i, it in enumerate(sp["test"]) if it.session == s0]
    df_diff = max(float(np.abs(st.log_probs - lp_test[i]).max()) for (_, st), i in zip(pairs, k))
    df_equal = len(pairs) == len(k) and df_diff <= 1e-5  # the stream re-normalises the rows (float32 rounding)
    lp_val = [m.log_probs(it.x, it.session) for it in sp["val"]]
    ved, vref, _ = cer_records(m, sp["val"], lp_val)
    OWN.mkdir(parents=True, exist_ok=True)
    np.savez(OWN / "lp_test.npz", *lp_test)
    np.savez(OWN / "lp_val.npz", *lp_val)
    save_json({"test": [{"key": it.key, "truth": it.truth, "hyp": h, "edits": e} for it, h, e in zip(sp["test"], hyp, ed)]},
              OWN / "test_records.json")
    update_results("numpy", {
        "model": "willett-hw", "weights_sha256": m.weights_sha256, "split_equal_p15_08": same_split,
        "n_test": len(ed), "n_chars": int(sum(ref)), "test_edits": int(sum(ed)), "test_cer": round(cer, 4),
        "stored_pytorch_gpu_cer": round(stored["test_cer_final"], 4), "per_sentence_edits_equal": n_eq,
        "max_abs_edit_diff": int(max(abs(a - b) for a, b in zip(ed, stored["test_edits_final"]))),
        "nts_provenance": f"{n_prov} / {len(ed)}", "decode_file_equal_direct": bool(df_equal),
        "decode_file_max_abs_diff": float(f"{df_diff:.3g}"),
        "val_cer_final_checkpoint": round(sum(ved) / sum(vref), 4), "n_val": len(ved),
        "seconds_test_decode": round(t_test, 1), "seconds": round(time.time() - t0, 1)})


def stage_torch() -> None:
    import torch

    torch.set_num_threads(4)
    sys.path.insert(0, str(REPO / "experiments/2026-11-19-p15-08-e1-cross-body"))
    import e1  # noqa: E402

    import fidetype.pretrained as ftp

    t0 = time.time()
    cfg = json.loads((REPO / "experiments/2026-11-19-p15-08-e1-cross-body/config.json").read_text(encoding="utf-8"))
    tr = dict(cfg["trunk"])
    tr["dilations"] = tuple(tr["dilations"])
    model = e1.XBody(e1.TrunkCfg(**tr), "willett", 10)
    model.load_state_dict(torch.load(RUN / "final.pt", map_location="cpu", weights_only=True)["model"])
    model.eval()
    m = ftp.load("willett-hw")
    sp = split_items(m)
    sessions = m.manifest.architecture["sessions"]
    z = np.load(OWN / "lp_test.npz")
    lp_np = [z[f"arr_{i}"] for i in range(len(sp["test"]))]
    diffs, lp_t = [], []
    with torch.no_grad():
        for it, lpn in zip(sp["test"], lp_np):
            x = torch.from_numpy(np.asarray(it.x, np.float32))[None]
            lpt = model(x, torch.tensor([sessions.index(it.session)]))[0].numpy()
            lp_t.append(lpt)
            diffs.append(float(np.abs(lpt - lpn).max()))
    ed, ref, _ = cer_records(m, sp["test"], lp_t)
    edn, _, _ = cer_records(m, sp["test"], lp_np)
    argmax_diff = int(sum(int((a.argmax(1) != b.argmax(1)).sum()) for a, b in zip(lp_t, lp_np)))
    n_frames = int(sum(len(a) for a in lp_t))
    log(f"torch (CPU): test CER {sum(ed) / sum(ref):.4f}; max abs log-prob diff to NumPy {max(diffs):.2e}; "
        f"argmax differs on {argmax_diff} / {n_frames} frames; per-sentence edits equal {sum(a == b for a, b in zip(ed, edn))} "
        f"/ {len(ed)} ({time.time() - t0:.0f} s)")
    update_results("torch_cpu", {
        "torch": torch.__version__, "test_cer": round(sum(ed) / sum(ref), 4), "test_edits": int(sum(ed)),
        "max_abs_logprob_diff_vs_numpy": float(f"{max(diffs):.3g}"), "argmax_frames_differ": argmax_diff,
        "n_frames": n_frames, "per_sentence_edits_equal_numpy": int(sum(a == b for a, b in zip(ed, edn))),
        "seconds": round(time.time() - t0, 1)})


def stage_guard() -> None:
    import fidetype.pretrained as ftp
    import fidetype.trust as ft
    from fidetype.adapters.ctc_logits import vocab_from_list
    from fidetype.pretrained import _xbody

    t0 = time.time()
    m = ftp.load("willett-hw")
    sp = split_items(m)
    zt, zv = np.load(OWN / "lp_test.npz"), np.load(OWN / "lp_val.npz")
    lp_test = [zt[f"arr_{i}"] for i in range(len(sp["test"]))]
    lp_val = [zv[f"arr_{i}"] for i in range(len(sp["val"]))]
    rng = np.random.default_rng(SEED)

    def shuffled(it):  # time-shuffled input (C1 control of P15-08): the signal order is destroyed
        x = np.asarray(it.x)
        return m.log_probs(x[rng.permutation(len(x))], it.session)

    nulls = [shuffled(it) for it in sp["val"]]
    vocab = vocab_from_list(list(_xbody.VOCAB), blank=0, vocab_type="char", vocab_id=m.manifest.output["vocab_id"])
    rec: dict = {"alpha": ALPHA, "delta": DELTA, "n_cal": len(lp_val), "n_null": len(nulls), "cal": "val blocks",
                 "null": "time-shuffled val sentences"}
    try:
        g = ft.calibrate(lp_val, [it.truth for it in sp["val"]], alpha=ALPHA, delta=DELTA, input_kind="logits",
                         vocab=vocab, blank=0, input_scale="log_probs", frame_period=_xbody.BIN_S, null_inputs=nulls,
                         decoder_name="fidetype-willett-hw", decoder_version="1", modality="intracortical",
                         name="p14-33-willett-hw", seed=SEED, audit_text=False, language="en")
    except ft.NullControlError as e:
        rec.update(status="refused", reason=str(e)[:2000])
        log(f"guard: REFUSED ({time.time() - t0:.0f} s): {e}")
        update_results("guard", rec)
        return
    gp = OWN / "willett-hw.guard.json"
    g.save(gp)
    log(f"guard: {g.config_id} ({time.time() - t0:.0f} s)\n{g.sheet}")
    test_shuf = [shuffled(it) for it in sp["test"]]
    out = {}
    for kind, xs in (("real", lp_test), ("shuffled", test_shuf)):
        acts = []
        for it, x in zip(sp["test"], xs):
            r = g.decide(x)
            acts.append({"action": r.action, "correct": bool(r.action == "commit" and r.text == it.truth)})
        n_c = sum(a["action"] == "commit" for a in acts)
        out[kind] = {"commit": n_c, "wrong_commit": int(sum(a["action"] == "commit" and not a["correct"] for a in acts)),
                     "offer": sum(a["action"] == "offer" for a in acts),
                     "withhold": sum(a["action"] == "withhold" for a in acts), "n": len(acts)}
        log(f"guard decisions on test ({kind}): {out[kind]}")
    from fidetype.pretrained import sha256_file

    rec.update(status="guard", config_id=g.config_id, guard_sha256=sha256_file(gp), guard_size=gp.stat().st_size,
               sheet=g.sheet.to_dict(), test=out, seconds=round(time.time() - t0, 1))
    update_results("guard", rec)


def main(argv: list[str]) -> int:
    stages = {"numpy": stage_numpy, "torch": stage_torch, "guard": stage_guard}
    for s in argv or ["numpy", "guard"]:
        stages[s]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
