"""P6-02 baselines: v0.2 submissions + score cards for b2t24-t12, willett-hw, kt-semg, emg2qwerty. CPU only.

Stages (run from the repo root, heavy ones through the CPU isolation wrapper):

  truth-<track>   rebuild the local truth file (derived/p6-02-scorer/truth/<track>.jsonl; text: never commit)
  t12             T12 v2 decoder log-probs (read only) + drop-in guard (P14-03 recipe) calibrated on the track cal
                  split (880), decisions on the 880 test trials; controls = frames shuffled / uniform log-probs
  willett         published real-time RNN output (81 test trials) + drop-in guard calibrated on the closed-loop
                  trials of the earlier sessions (train + val splits); controls = frames shuffled / uniform rows
  kt              shrinkage-LDA key decoder (adapter reference decoder, oracle key timing) trained on the train runs,
                  drop-in guard calibrated on the cal bursts; controls = key windows shuffled in the run / zero EMG
  e2q             emg2qwerty (RESEARCH ONLY): per user, LDA fit on the last train session, guard calibrated on the
                  val-session prompts (pooled), decisions on the test-session prompts; controls as kt
  score           score every submission with `fidetype.benchmark.scorecard` -> benchmark/results/v0.2/*.json

  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- \\
      .venv\\Scripts\\python.exe -I experiments/2026-11-16-p6-02-scorer/run.py truth-b2t24-t12 t12 score

Per-unit files (submissions with text, truth): C:/Users/zhang/bci-data/derived/p6-02-scorer/ only.
Repo: score cards (aggregates, no text) in benchmark/results/v0.2/ and results/*.json.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.benchmark import scorecard as SC  # noqa: E402
from fidetype.benchmark import tracks as TR  # noqa: E402
from fidetype.benchmark.scoring import to_jsonable  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p6-02-scorer"  # the only place this task writes per-unit files
assert OWN.name == "p6-02-scorer"
OWN.mkdir(parents=True, exist_ok=True)
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
BOARD = REPO / "benchmark" / "results" / "v0.2"
LOGF = OWN / "run.log"
SEED = 0
ALPHA, DELTA = 0.05, 0.1
DATA = {
    "b2t24-t12": Path("C:/Users/zhang/bci-data/raw/b2t24/extracted/competitionData"),
    "willett-hw": Path("C:/Users/zhang/bci-data/raw/willett-handwriting/extracted/handwritingBCIData"),
    "kt-semg": Path("C:/Users/zhang/bci-data/raw/kt-semg"),
    "emg2qwerty": Path("C:/Users/zhang/bci-data/raw/emg2qwerty/extracted/emg2qwerty-data-2021-08"),
}


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def truth_path(track: str) -> Path:
    return OWN / "truth" / f"{track}.jsonl"


def load_truth(track: str) -> dict:
    return SC.read_truth(truth_path(track), track)


def save_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(obj), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def stage_truth(track: str) -> dict:
    t0 = time.time()
    rows = SC.build_truth(track, DATA[track])
    n = SC.write_truth(truth_path(track), track, rows)
    ns = [r["neural_s"] for r in rows if r.get("neural_s") is not None]
    nk = [len(r["text"].split()) for r in rows] if SC.SCORE_SPECS[track].key_track else []
    info = {"track": track, "n_units": n, "n_neural_s": len(ns), "seconds": round(time.time() - t0, 1)}
    if ns:
        info["neural_s_total"] = float(sum(ns))
        info["neural_s_median"] = float(sorted(ns)[len(ns) // 2])
    if nk:
        # keys per minute over the scored units (measured timing): context for the rate model
        info["keys_total"] = int(sum(nk))
        info["keys_per_min_measured"] = 60.0 * sum(nk) / sum(ns) if ns else None
    else:
        chars = [len(" ".join(r["text"].split())) for r in rows]
        info["chars_per_min_measured"] = 60.0 * sum(chars) / sum(ns) if ns else None
    log(f"truth {track}: {info}")
    return info


# ---------------------------------------------------------------------------
# Shared: guard results -> unit rows
# ---------------------------------------------------------------------------


def decide(guard, x, uid: str):
    """``guard.decide(x)`` plus the decoder n-best of the same events: (TrustResult, [n-best texts])."""
    events, _ = guard._codec.events(x)
    r = guard._result(*guard._final_gated(events))
    guard._log(r, events, uid)
    hyps = [e for e in events if e.get("type") == "hypothesis"]
    nbest = [str(c.get("text", "")) for c in (hyps[-1].get("nbest", []) if hyps else [])]
    return r, nbest


def guard_row(unit: str, rn, to_text=lambda s: s) -> dict:
    """(TrustResult, n-best) -> one units.jsonl row. ``to_text`` maps guard text to the track text space.

    nbest[0] is always the decoder top-1 (so CER is the decoder CER for every action); an OFFER lists its
    shown choices first.
    """
    r, nb = rn
    if r.action == "commit":
        texts, act = [r.text or ""], "commit"
    elif r.action == "offer":
        texts, act = list(r.choices) or nb[:1] or [""], "offer"
    else:
        texts, act = nb[:3] or [""], "abstain"
    texts = [to_text(t) for t in texts]
    return SC.unit_row(unit, texts, [float(r.p_top1)] + [None] * (len(texts) - 1), action=act,
                       score_semantics="calibrated_prob", offer_k=3)


def summarize_guard(name: str, guard) -> dict:
    sh = guard.sheet.to_dict()
    return {"config_id": guard.config_id, "sheet": {k: sh.get(k) for k in (
        "alpha", "delta", "n_items", "n_fit", "n_policy", "n_ltt", "feasible", "commit_threshold", "controls",
        "warnings")}}


def guarantee_of(guard, scope: str, calibration_split: str) -> dict:
    sh = guard.sheet.to_dict()
    return {"method": "ltt", "alpha": sh.get("alpha"), "delta": sh.get("delta"), "n_cal": int(sh.get("n_ltt") or 0),
            "scope": scope, "calibration_split": calibration_split, "config_id": guard.config_id,
            "feasible": sh.get("feasible", True)}


def shuffled_frames(x: np.ndarray, key: str) -> np.ndarray:
    rng = np.random.default_rng(int(hashlib.sha256(key.encode()).hexdigest()[:8], 16))
    return x[rng.permutation(len(x))]


# ---------------------------------------------------------------------------
# T12
# ---------------------------------------------------------------------------


def stage_t12() -> dict:
    import fidetype.trust as ft
    from fidetype.adapters import b2t25 as B

    t0 = time.time()
    p1403 = load_module("p1403run", REPO / "experiments/2026-11-16-p14-03-replay-validation/run.py")
    exp = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
    cfg = json.loads((exp / "config.json").read_text(encoding="utf-8"))
    d_in = Path(cfg["derived_dir"])
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    meta = json.loads((d_in / "logprobs-meta.json").read_text(encoding="utf-8"))
    assert meta["checkpoint_sha256"] == cfg["decoder_checkpoint_sha256"]
    z = np.load(d_in / "logprobs.npz")
    split = TR.load_split("b2t24-t12")
    truth = load_truth("b2t24-t12")
    # Track units -> decoder keys. Test unit "<session>|test|<i>" = decoder "pool" trial i of that session.
    # Cal = the last train block of each session = decoder "val" part (same rule; checked by text + count).
    units = TR.select_units(split, TR.local_units("b2t24-t12", DATA["b2t24-t12"]), "test")
    cal_units = TR.select_units(split, TR.local_units("b2t24-t12", DATA["b2t24-t12"]), "cal")
    npz: dict = {}
    cx, ct, cph = [], [], []
    cal_texts_track = sorted(u.payload for u in cal_units)
    for s in sorted(texts):
        for j, w in enumerate(texts[s]["val"]):
            cx.append(z[f"{s}|val|{j}"].astype(np.float32))
            ct.append(w)
            cph.append(p1403.ph_symbols(npz, d_in, s, "val", j))
    assert sorted(ct) == cal_texts_track, "decoder val part != track cal split"
    hx, hkeys = [], []
    for u in units:
        s, part, i = u.id.split("|")
        assert part == "test"
        k = TR.id_hash("b2t24-t12", u.id)
        assert texts[s]["pool"][int(i)] == truth[k]["text"], "pool text != track truth"
        hx.append(z[f"{s}|pool|{i}"].astype(np.float32))
        hkeys.append(k)
    log(f"t12: cal {len(cx)}, test {len(hx)}")
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    dec = bt.Decoders([], cfg["word_decoder_tuned"])
    sys.path.insert(0, str(exp))
    import wordlm  # noqa: E402

    beta = cfg["word_lm"]["beta"]
    cache = Path(cfg["word_lm"]["cache"])
    assert cache.exists(), "word LM cache missing (would be rebuilt)"
    wm = wordlm.load_or_build(bt.CONFIG["tatoeba_eng"], cache, B.normalize_words)
    char = dec.lm.score_sentence
    dec.wdec.sentence_lm = lambda t: char(t) + beta * wm.score_sentence(t)
    dec.wdec.clear_caches()
    dec._wcache.clear()
    fn = p1403.make_decode_fn(dec)
    guard = ft.calibrate(cx, ct, alpha=ALPHA, delta=DELTA, vocab=list(B.SYMBOL_VOCAB), blank=0,
                         input_scale="log_probs", frame_period=0.08, decode_fn=fn, stream_texts=cph,
                         decoder_name="t12-v2-final", modality="intracortical", name="p6-02-t12", seed=SEED)
    log(f"t12: guard {guard.config_id} in {time.time() - t0:.0f}s\n{guard.sheet}")
    guard.save(OUT / "guard-t12.json")
    rows = [guard_row(k, decide(guard, x, f"t12-{n}")) for n, (k, x) in enumerate(zip(hkeys, hx))]
    log(f"t12: real decisions done {time.time() - t0:.0f}s")
    uni = math.log(1.0 / len(B.SYMBOL_VOCAB))
    shuf = [guard_row(k, decide(guard, shuffled_frames(x, k), f"t12-s{n}")) for n, (k, x) in enumerate(zip(hkeys, hx))]
    zer = [guard_row(k, decide(guard, np.full_like(x, uni), f"t12-z{n}")) for n, (k, x) in enumerate(zip(hkeys, hx))]
    log(f"t12: controls done {time.time() - t0:.0f}s")
    man = SC.manifest_dict(
        "b2t24-t12",
        {"name": "t12-v2 GRU + word LM (ours)", "version": meta["checkpoint_sha256"][:12],
         "url": "experiments/2026-11-13-confirmatory-t12-v2", "weights_licence": "not released",
         "training_data": ["b2t24-t12 train split (train blocks of the train partition)"],
         "training_regime": "cross-session (one participant; test sessions are also train sessions)"},
        policy={"name": "drop-in guard (P14-03 recipe)", "description": "fidetype.trust.calibrate, alpha 0.05, "
                "delta 0.1, user decode_fn = the T12 v2 phoneme-to-word decoder with the Tatoeba word LM"},
        guarantee=guarantee_of(guard, "marginal over test trials; exchangeable cal / test (cal = last train "
                               "block per session)", "cal"),
        regime="cross-session",
        controls={"shuffled": "decoder output level: the frames of each test log-prob matrix permuted in time "
                  "(seeded by the unit hash); the neural input was not re-decoded",
                  "zeros": "decoder output level: uniform log-probs of the same length (no-signal stand-in); "
                  "the GRU was not run on zero input"},
        notes="Checkpoint chosen by early stopping on the decoder val part = this track's cal split (open). "
              "Decisions use the same guard as P14-03 but calibrated on the track cal split, not on test-partition "
              "trials.")
    sub = SC.write_submission(OWN / "submissions" / "b2t24-t12__t12v2__guard", man, rows,
                              {"shuffled": shuf, "zeros": zer})
    info = {"n_cal": len(cx), "n_test": len(hx), **summarize_guard("t12", guard), "submission": str(sub),
            "seconds": round(time.time() - t0, 1)}
    write_always_commit(OWN / "submissions" / "b2t24-t12__t12v2__always-commit", man, rows, shuf, zer)
    save_json(info, OUT / "t12.json")
    return info


def write_always_commit(folder: Path, man: dict, rows, shuf, zer) -> None:
    """A second entry from the same decoder output: always commit the decoder top-1 (no guarantee)."""
    def ac(rs):
        return [dict(r, action="commit", nbest=r["nbest"][:1]) for r in rs]

    man2 = dict(man, policy={"name": "always commit top-1"}, guarantee={"method": "none"})
    SC.write_submission(folder, man2, ac(rows), {"shuffled": ac(shuf), "zeros": ac(zer)})


# ---------------------------------------------------------------------------
# Willett handwriting
# ---------------------------------------------------------------------------


def tatoeba_tokens(n: int = 50_000, allowed: str = "abcdefghijklmnopqrstuvwxyz ,'.?") -> list[str]:
    """The n most frequent lower-case tokens of the Tatoeba English export (punctuation kept as typed)."""
    import bz2
    from collections import Counter

    bt = json.loads((REPO / "experiments/2026-11-10-b2t25-trust/config.json").read_text(encoding="utf-8"))
    c: Counter = Counter()
    ok = set(allowed)
    with bz2.open(bt["tatoeba_eng"], "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            t = parts[2].lower()
            if set(t) <= ok:
                c.update(t.split())
    return [w for w, _ in c.most_common(n)]


def stage_willett() -> dict:
    import fidetype.trust as ft
    from fidetype.adapters import willett_handwriting as W

    t0 = time.time()
    track = "willett-hw"
    split = TR.load_split(track)
    units = TR.local_units(track, DATA[track])
    load_truth(track)  # checks the truth file against the split
    sess_cache: dict = {}

    def sess(f):
        if f not in sess_cache:
            sess_cache[f] = W.load_sentences(f)
        return sess_cache[f]

    def stream_of(u, rows_fn=None, greedy=False):
        s = sess(u.ref["file"])
        st = W.trial_stream(s, int(u.ref["index"]), int(u.ref["session_index"]))
        if rows_fn is not None:
            p = rows_fn(np.exp(st.log_probs.astype(np.float64)))
            st = W.char_stream(p, st.frame_times, dict(st.meta))
        lp = W.to_ctc_stream(st).log_probs.astype(np.float32)
        return (lp, " ".join(W.greedy_text(st).split())) if greedy else lp

    def row(k, u, rows_fn, uid):
        """Guard decision; n-best[0] falls back to the real-time RNN text (per-frame argmax) when the word-list
        beam keeps no candidate, so CER is the CER of the decoder output, not of an empty string."""
        lp, g = stream_of(u, rows_fn, greedy=True)
        r = guard_row(k, decide(guard, lp, uid))
        if not r["nbest"][0]["text"]:
            r["nbest"] = [{"text": g}] + [x for x in r["nbest"][1:] if x["text"]]
            r["x-top1-source"] = "real-time RNN text (word-list beam kept no candidate)"
        return r, g

    test = [u for u in TR.select_units(split, units, "test") if u.ref["rnn"]]
    cal = [u for u in units if u.set == "trial" and u.split in ("train", "val") and u.ref["rnn"]]
    cal_texts = [u.payload.rsplit("|", 1)[0] for u in cal]
    cx = [stream_of(u) for u in cal]
    lex = sorted(set(tatoeba_tokens()) | {w for t in cal_texts for w in t.split()})
    log(f"willett: cal {len(cx)} closed-loop train/val trials, test {len(test)} of 254 (RNN output), "
        f"lexicon {len(lex)}")
    guard = ft.calibrate(cx, cal_texts, alpha=ALPHA, delta=DELTA, vocab=list(W.CTC_VOCAB), blank=0,
                         input_scale="log_probs", frame_period=0.1, lexicon=lex, decoder_name="willett2021-rnn",
                         modality="intracortical", name="p6-02-willett", seed=SEED)
    log(f"willett: guard {guard.config_id} in {time.time() - t0:.0f}s\n{guard.sheet}")
    guard.save(OWN / "guard-willett.json")  # holds the word list: kept out of the repo

    def uni(p):
        return np.full_like(p, 1.0 / p.shape[1])

    rows, shuf, zer, greedy = [], [], [], {"real": [], "shuffled": [], "zeros": []}
    for n, u in enumerate(test):
        k = TR.id_hash(track, u.id)
        for lst, kind, fn in ((rows, "real", None), (shuf, "shuffled", lambda p, k=k: shuffled_frames(p, k)),
                              (zer, "zeros", uni)):
            r, g = row(k, u, fn, f"w-{kind[0]}{n}")
            lst.append(r)
            greedy[kind].append(SC.unit_row(k, [g], action="commit"))
    man = SC.manifest_dict(
        track,
        {"name": "Willett 2021 real-time RNN (published output) + CTC beam with word list", "version": "dataset",
         "url": "https://doi.org/10.5061/dryad.wh70rxwmv", "weights_licence": "not released (output in the CC0 data)",
         "training_data": ["Willett et al. 2021 own training (earlier sessions)"],
         "training_regime": "as published (real-time decoder of the study)"},
        policy={"name": "drop-in guard (built-in CTC beam + word list)", "description": "fidetype.trust.calibrate, "
                "alpha 0.05, delta 0.1; word list = 50k Tatoeba tokens + calibration-text tokens"},
        guarantee=guarantee_of(guard, "marginal over the 81 test trials with RNN output; exchangeable with the "
                               "earlier-session closed-loop trials (a session shift breaks this)",
                               "train+val (closed-loop trials of the earlier sessions)"),
        regime="other",
        controls={"shuffled": "decoder output level: the character rows of each trial permuted in time",
                  "zeros": "decoder output level: uniform character rows (no-signal stand-in)"},
        coverage={"subset": "the published RNN output exists only for the 81 closed-loop test trials; the other "
                  "173 test trials are open-loop (no decoder output)"},
        notes="Calibration on the closed-loop trials of the train + val splits of the 7 earlier sessions (the docs "
              "name the val trials; train trials are open as well and the RNN output is fixed).")
    sub = SC.write_submission(OWN / "submissions" / "willett-hw__rnn-published__guard", man, rows,
                              {"shuffled": shuf, "zeros": zer})
    man2 = dict(man, policy={"name": "always commit the real-time RNN text (as typed on screen in the study)"},
                guarantee={"method": "none"})
    SC.write_submission(OWN / "submissions" / "willett-hw__rnn-published__always-commit", man2, greedy["real"],
                        {"shuffled": greedy["shuffled"], "zeros": greedy["zeros"]})
    info = {"n_cal": len(cx), "n_test": len(test), "lexicon": len(lex), **summarize_guard("willett", guard),
            "submission": str(sub), "seconds": round(time.time() - t0, 1)}
    save_json(info, OUT / "willett.json")
    return info


# ---------------------------------------------------------------------------
# EMG key tracks: features, LDA, CTC form, guard
# ---------------------------------------------------------------------------

KEY_SPACE_GUARD = "_"  # the guard sees Space as '_' so that its text stays one token (no whitespace collapse)


def key_chars() -> list[str]:
    from fidetype.adapters import kt_semg as K
    from fidetype.benchmark.registry import keycodes_to_chars

    ch = [keycodes_to_chars(c) for c in K.KEY_VOCAB]
    ch = [KEY_SPACE_GUARD if c == " " else c for c in ch]
    assert len(set(ch)) == len(ch) and all(len(c) == 1 for c in ch)
    return ch


def codes_to_guard_text(codes: str) -> str:
    from fidetype.benchmark.registry import keycodes_to_chars

    return keycodes_to_chars(codes).replace(" ", KEY_SPACE_GUARD)


def guard_text_to_codes(text: str) -> str:
    from fidetype.adapters import kt_semg as K

    inv = dict(zip(key_chars(), K.KEY_VOCAB))
    return " ".join(inv.get(c, "?") for c in text)


def key_ctc(lp: np.ndarray, char_blank: float = 1e-3, gap_nonblank: float = 1e-4) -> np.ndarray:
    """(K, 32) key log-probs -> (2K-1, 33) CTC form (blank first, a blank frame between keys), as the Willett adapter."""
    lp = np.asarray(lp, np.float64)
    K_, V = lp.shape[0], lp.shape[1] + 1
    out = np.empty((max(0, 2 * K_ - 1), V))
    lp = lp - np.logaddexp.reduce(lp, axis=1, keepdims=True)
    out[0::2, 0] = math.log(char_blank)
    out[0::2, 1:] = lp + math.log1p(-char_blank)
    if K_ > 1:
        out[1::2, 0] = math.log1p(-gap_nonblank)
        out[1::2, 1:] = math.log(gap_nonblank / (V - 1))
    return out.astype(np.float32)


def key_guard(cal_lp, cal_codes, name):
    import fidetype.trust as ft

    vocab = ["<blank>"] + key_chars()
    return ft.calibrate([key_ctc(x) for x in cal_lp], [codes_to_guard_text(c) for c in cal_codes], alpha=ALPHA,
                        delta=DELTA, vocab=vocab, blank=0, input_scale="log_probs", frame_period=0.1,
                        decoder_name="fidetype-lda-key-baseline", modality="emg", name=name, seed=SEED)


def kt_run_features(run, pad_s: float = 0.3, chunk_bytes: int = 32 << 20):
    """Streamed log-RMS key-window features of one KT-sEMG run (all key presses; memory: a few chunks).

    Returns (key times from the first sample (s), features (K, 64) standardised in the run,
    labels (K,) with -1 = not a class).
    """
    from fidetype.adapters import kt_semg as K

    keys = K.parse_keys(Path(run.ref["keys"]).read_bytes())
    start = K.read_start_time(Path(run.ref["ts"]))
    with open(run.ref["csv"], "rb") as f:
        f.readline()
        n = 0
        while True:
            b = f.read(chunk_bytes)
            if not b:
                break
            n += b.count(b"\n")
    dur = n / K.SAMPLE_RATE_HZ
    off = K.infer_utc_offset_hours(start, [k.unix_s for k in keys], dur)
    s0 = K.start_unix(start, off)
    t = np.array([k.unix_s - s0 for k in keys])
    samp = np.round(t * K.SAMPLE_RATE_HZ).astype(np.int64)
    pad = int(pad_s * K.SAMPLE_RATE_HZ)
    X = np.zeros((len(keys), 2 * K.N_CHANNELS))
    order = np.argsort(samp, kind="stable")
    nxt = 0
    buf = np.zeros((0, K.N_CHANNELS), np.float32)
    buf0 = 0
    with open(run.ref["csv"], "rb") as f:
        f.readline()
        rest = b""
        done = False
        while not done:
            b = f.read(chunk_bytes)
            if not b:
                done = True
                blk, rest = rest, b""
            else:
                blk = rest + b
                cut = blk.rfind(b"\n")
                blk, rest = blk[: cut + 1], blk[cut + 1:]
            if blk.strip():
                rows = K._parse_rows(blk, K.N_CHANNELS + 1)[:, 1:]
                buf = np.concatenate([buf, rows])
            end = buf0 + len(buf)
            sel = []
            while nxt < len(order) and (samp[order[nxt]] + pad < end or done):
                sel.append(order[nxt])
                nxt += 1
            if sel:
                sel = np.array(sel)
                tl = (samp[sel] - buf0) / K.SAMPLE_RATE_HZ
                X[sel] = K.window_features(buf, tl, K.SAMPLE_RATE_HZ)
            keep = max(0, len(buf) - 2 * pad)
            buf0 += keep
            buf = buf[keep:]
    y = np.array([-1 if K.key_class(k.char) is None else K.key_class(k.char) for k in keys])
    return t, K.standardize_run(X), y


def stage_kt() -> dict:
    from fidetype.adapters import kt_semg as K

    t0 = time.time()
    track = "kt-semg"
    split = TR.load_split(track)
    units = TR.local_units(track, DATA[track])
    truth = load_truth(track)
    runs = {u.id: u for u in units if u.set == "run"}
    feats = {}
    for rid, u in runs.items():
        cache = OWN / "kt-cache" / f"{rid}.npz"
        if cache.exists():
            z = np.load(cache)
            feats[rid] = (z["t"], z["X"], z["y"])
        else:
            feats[rid] = kt_run_features(u)
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.savez(cache, t=feats[rid][0], X=feats[rid][1], y=feats[rid][2])
        log(f"kt: {rid} ({u.split}) {len(feats[rid][2])} keys, {time.time() - t0:.0f}s")
    tr = [rid for rid, u in runs.items() if u.split == "train"]
    Xf = np.concatenate([feats[r][1][feats[r][2] >= 0] for r in tr])
    yf = np.concatenate([feats[r][2][feats[r][2] >= 0] for r in tr])
    dec = K.LdaKeyDecoder.fit(Xf, yf, shrinkage=0.1)
    sha = dec.save(OWN / "kt-lda.npz")
    segs = {s: TR.select_units(split, units, s, "segment") for s in ("cal", "test")}

    def seg_lp(u, kind="real"):
        a, b = u.ref["key_range"]
        X = feats[u.ref["run"]][1]
        if kind == "shuffled":
            rng = np.random.default_rng(int(hashlib.sha256(u.id.encode()).hexdigest()[:8], 16))
            Z = X[rng.integers(0, len(X), b - a)]
        elif kind == "zeros":
            Z = np.zeros((b - a, X.shape[1]))  # zero EMG -> constant log-RMS -> 0 after per-run standardisation
        else:
            Z = X[a:b]
        return dec.predict_log_proba(Z)

    hit = tot = 0
    for u in segs["test"]:
        a, b = u.ref["key_range"]
        y = feats[u.ref["run"]][2][a:b]
        p = seg_lp(u).argmax(1)
        hit += int(np.sum((p == y) & (y >= 0)))
        tot += int(np.sum(y >= 0))
    key_acc = hit / max(1, tot)
    guard = key_guard([seg_lp(u) for u in segs["cal"]], [u.payload for u in segs["cal"]], "p6-02-kt")
    log(f"kt: LDA test key accuracy {key_acc:.3f}; guard {guard.config_id}\n{guard.sheet}")
    guard.save(OUT / "guard-kt.json")
    rows, shuf, zer = [], [], []
    for n, u in enumerate(segs["test"]):
        k = TR.id_hash(track, u.id)
        assert k in truth
        rows.append(guard_row(k, decide(guard, key_ctc(seg_lp(u)), f"kt-{n}"), guard_text_to_codes))
        shuf.append(guard_row(k, decide(guard, key_ctc(seg_lp(u, "shuffled")), f"kt-s{n}"), guard_text_to_codes))
        zer.append(guard_row(k, decide(guard, key_ctc(seg_lp(u, "zeros")), f"kt-z{n}"), guard_text_to_codes))
    man = SC.manifest_dict(
        track,
        {"name": "shrinkage-LDA key decoder (adapter reference, oracle key timing)", "version": sha[:12],
         "url": "src/fidetype/adapters/kt_semg.py (LdaKeyDecoder)", "weights_licence": "not released",
         "training_data": ["kt-semg train split (20 runs)"], "training_regime": "cross-session (one typist)"},
        policy={"name": "drop-in guard (built-in CTC beam, no LM)", "description": "fidetype.trust.calibrate on the "
                "89 cal bursts, alpha 0.05, delta 0.1; key frames in CTC form (blank between keys)"},
        guarantee=guarantee_of(guard, "marginal over the test bursts; exchangeable cal / test runs", "cal"),
        regime="cross-session",
        controls={"shuffled": "input level: each key window replaced by a random key window of the same run",
                  "zeros": "input level: all-zero EMG (constant log-RMS, 0 after the per-run standardisation)"},
        notes="Oracle key timing from the key log (the decoder is told when a key is pressed). Not a track-"
              "conformant key detector; reference only.")
    sub = SC.write_submission(OWN / "submissions" / "kt-semg__lda-oracle__guard", man, rows,
                              {"shuffled": shuf, "zeros": zer})
    write_always_commit(OWN / "submissions" / "kt-semg__lda-oracle__always-commit", man, rows, shuf, zer)
    info = {"n_train_keys": int(len(yf)), "test_key_accuracy": key_acc, "n_cal": len(segs["cal"]),
            "n_test": len(segs["test"]), **summarize_guard("kt", guard), "submission": str(sub),
            "seconds": round(time.time() - t0, 1)}
    save_json(info, OUT / "kt.json")
    return info


# ---------------------------------------------------------------------------
# emg2qwerty (RESEARCH ONLY)
# ---------------------------------------------------------------------------


def e2q_session_keys(path: str):
    """Features (standardised in the session), labels and prompt index lists of one emg2qwerty session."""
    from fidetype.adapters import emg2qwerty as E
    from fidetype.adapters import kt_semg as K

    with E.Session(path) as s:
        ev = [e for e in E.key_events(s) if E.key_class(e.key) is not None]
        X = K.standardize_run(E.session_features(s, [e.sample for e in ev]))
        y = np.array([E.key_class(e.key) for e in ev], dtype=np.int64)
        pos = {id(e): i for i, e in enumerate(ev)}
        prompts = [(int(pr.index), [pos[id(e)] for e in E.prompt_events(s, pr, ev)]) for pr in s.prompts]
    return X, y, prompts


def stage_e2q() -> dict:
    from fidetype.adapters import kt_semg as K

    t0 = time.time()
    track = "emg2qwerty"
    units = TR.local_units(track, DATA[track])
    truth = load_truth(track)
    by_user: dict = {}
    for u in units:
        by_user.setdefault(u.group, []).append(u)
    cache_dir = OWN / "e2q-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    users = sorted(g for g, us in by_user.items() if any(u.split == "test" for u in us))

    def cfile(g: str) -> Path:
        return cache_dir / f"{hashlib.sha256(g.encode()).hexdigest()[:12]}.json"

    for j, g in enumerate(users):
        if cfile(g).exists():
            continue
        us = sorted(by_user[g], key=lambda u: u.id)
        te = [u for u in us if u.split == "test"][0]
        va = [u for u in us if u.split == "val"][0]
        fit = [u for u in us if u.split == "train"][-1]
        Xf, yf, _ = e2q_session_keys(fit.ref["file"])
        dec = K.LdaKeyDecoder.fit(Xf, yf, shrinkage=0.1)
        out: dict = {"val": [], "test": []}
        for part, u in (("val", va), ("test", te)):
            X, y, prompts = e2q_session_keys(u.ref["file"])
            h = TR.id_hash(track, u.id)
            for k, idx in prompts:
                key = f"{h}#{k}"
                if len(idx) < SC.E2Q_MIN_KEYS or (part == "test" and key not in truth):
                    continue
                Z = X[idx]
                lp = dec.predict_log_proba(Z)
                rng = np.random.default_rng(int(hashlib.sha256(key.encode()).hexdigest()[:8], 16))
                out[part].append({
                    "key": key, "codes": " ".join(K.KEY_VOCAB[c] for c in y[idx]),
                    "lp": lp.round(4).tolist(),
                    "lp_shuffled": dec.predict_log_proba(X[rng.integers(0, len(X), len(idx))]).round(4).tolist(),
                    "lp_zeros": dec.predict_log_proba(np.zeros_like(Z)).round(4).tolist(),
                    "acc": [int(np.sum(lp.argmax(1) == y[idx])), len(idx)]})
        cfile(g).write_text(json.dumps(out), encoding="utf-8")
        log(f"e2q: user {j + 1}/{len(users)} ({len(out['val'])} val, {len(out['test'])} test prompts), "
            f"{time.time() - t0:.0f}s")
    val, test = [], []
    for g in users:
        d = json.loads(cfile(g).read_text(encoding="utf-8"))
        val += d["val"]
        test += d["test"]
    have = {t["key"] for t in test}
    missing = [k for k in truth if k not in have]
    rng = np.random.default_rng(SEED)
    cal = [val[i] for i in sorted(rng.choice(len(val), min(len(val), 3000), replace=False))]
    guard = key_guard([np.array(c["lp"]) for c in cal], [c["codes"] for c in cal], "p6-02-e2q")
    log(f"e2q: guard {guard.config_id} on {len(cal)} val prompts\n{guard.sheet}")
    guard.save(OUT / "guard-e2q.json")
    rows, shuf, zer = [], [], []
    for n, t in enumerate(test):
        rows.append(guard_row(t["key"], decide(guard, key_ctc(np.array(t["lp"])), f"e-{n}"), guard_text_to_codes))
        shuf.append(guard_row(t["key"], decide(guard, key_ctc(np.array(t["lp_shuffled"])), f"e-s{n}"),
                              guard_text_to_codes))
        zer.append(guard_row(t["key"], decide(guard, key_ctc(np.array(t["lp_zeros"])), f"e-z{n}"),
                             guard_text_to_codes))
    acc = sum(t["acc"][0] for t in test) / max(1, sum(t["acc"][1] for t in test))
    cov = ({"subset": f"{len(missing)} test prompts have no key window inside the session"} if missing else None)
    man = SC.manifest_dict(
        track,
        {"name": "shrinkage-LDA key decoder per user (adapter reference, oracle key timing)", "version": "0",
         "url": "src/fidetype/adapters/emg2qwerty.py", "weights_licence": "not released (would be CC BY-NC-SA: "
         "research only)", "training_data": ["emg2qwerty: the last train session of each test user"],
         "training_regime": "personalised (fit on one earlier session of the same user)"},
        policy={"name": "drop-in guard (built-in CTC beam, no LM)", "description": f"fidetype.trust.calibrate on "
                f"{len(cal)} val-session prompts pooled over users, alpha 0.05, delta 0.1"},
        guarantee=guarantee_of(guard, "marginal over test prompts pooled over users; exchangeable val / test "
                               "sessions", "val"),
        regime="personalised",
        controls={"shuffled": "input level: each key window replaced by a random key window of the same session",
                  "zeros": "input level: all-zero features (zero-EMG stand-in after the per-session "
                  "standardisation)"},
        coverage=cov,
        notes="RESEARCH ONLY (CC BY-NC-SA 4.0 data). Oracle key timing from the key log; not a track-conformant "
              "continuous decoder (P11-01 is). Reference only.")
    sub = SC.write_submission(OWN / "submissions" / "emg2qwerty__lda-oracle__guard", man, rows,
                              {"shuffled": shuf, "zeros": zer})
    write_always_commit(OWN / "submissions" / "emg2qwerty__lda-oracle__always-commit", man, rows, shuf, zer)
    info = {"n_users": len(users), "n_val_prompts": len(val), "n_cal": len(cal), "n_test": len(test),
            "missing_test_prompts": len(missing), "test_key_accuracy": acc, **summarize_guard("e2q", guard),
            "submission": str(sub), "seconds": round(time.time() - t0, 1)}
    save_json(info, OUT / "e2q.json")
    return info


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def stage_score() -> dict:
    out = {}
    for sub in sorted((OWN / "submissions").iterdir()):
        if not (sub / "submission.json").is_file():
            continue
        track = json.loads((sub / "submission.json").read_text(encoding="utf-8"))["track"]
        if not truth_path(track).exists():
            log(f"score {sub.name}: no truth yet")
            continue
        res = SC.score(track, sub, load_truth(track), B=2000, seed=0)
        res["sources"] = [sub.name]
        save_json(res, BOARD / f"{sub.name}.json")
        out[sub.name] = {"status": res["status"], "certification": res["certification"]}
        log(SC.score_card_text(res))
    save_json(out, OUT / "score.json")
    return out


def stage_table() -> str:
    """results/tables.md from the committed score cards (aggregates only)."""
    def f(m, k, nd=3):
        x = (m.get(k) or {}).get("value")
        ci = (m.get(k) or {}).get("ci")
        if x is None:
            return "n/a"
        s = f"{x:.{nd}f}"
        if ci and None not in ci:
            s += f" [{ci[0]:.{nd}f}, {ci[1]:.{nd}f}]"
        return s

    L = ["| Entry | Units | CER (key err.) | eWPM [CI] | no-BCI | Safe WPM @ 0.05 | Wrong-commit [CI] | "
         "Error among commits | Commit rate | Controls (shuf / zeros / null) | Status |", "|" + "---|" * 11]
    for p in sorted(BOARD.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        m, sw, c, cov = r["metrics"], r.get("safe_wpm") or {}, r["controls"], r["coverage"]
        swv = "n/a" if sw.get("value") is None else f"{sw['value']:.2f}"
        nc = c["null_commit"].get("commit_rate_zeros")
        L.append(f"| `{p.stem}` | {cov['n_covered']}/{cov['n_scored_units']} | {f(m, 'cer')} | {f(m, 'ewpm', 2)} | "
                 f"{f(m, 'gaze_ewpm', 2).split(' ')[0]} | {swv} ({sw.get('status')}; {sw.get('n_commits')} commits, "
                 f"{sw.get('n_wrong_commits')} wrong) | {f(m, 'wrong_commit_rate')} | {f(m, 'error_among_commits')} | "
                 f"{f(m, 'commit_rate')} | {c['shuffled']['status']} / {c['zeros']['status']} / "
                 f"{c['null_commit']['status']}" + (f" ({nc:.3f})" if nc is not None else "") + f" | {r['status']} |")
    txt = "\n".join(L) + "\n"
    (OUT / "tables.md").write_text("# P6-02 baseline score cards (generated by run.py table)\n\n" + txt, encoding="utf-8")
    print(txt)
    return txt


STAGES = {"table": stage_table, "t12": stage_t12, "willett": stage_willett, "kt": stage_kt, "e2q": stage_e2q, "score": stage_score}


def main() -> None:
    for st in sys.argv[1:]:
        log(f"stage {st} start")
        if st.startswith("truth-"):
            info = stage_truth(st[len("truth-"):])
            allt = json.loads((OUT / "truth.json").read_text(encoding="utf-8")) if (OUT / "truth.json").exists() else {}
            allt[info["track"]] = info
            save_json(allt, OUT / "truth.json")
        else:
            STAGES[st]()
        log(f"stage {st} done")


if __name__ == "__main__":
    main()
