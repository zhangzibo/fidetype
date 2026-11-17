"""P3-08: Brain-to-Text '25 (T15, CC0) replay through the collector with the latency budget. CPU only.

Two stages (repo root; heavy stage through the isolation runner):

  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-17-p3-08-b2t25-collector-replay/run.py prep --decoder m4-12
  .venv\\Scripts\\python.exe -I experiments/2026-11-17-p3-08-b2t25-collector-replay/run.py replay --decoder m4-12

``prep``: the decoder side, before the collector. Phoneme log-probs (41 symbols, 80 ms frames) of the T15
``val_select`` (calibration) and ``val_eval`` (replay) trials -> word n-best lists with the B2T '25 word
decoder of P14-03 (phoneme beam + lexicon + character 6-gram LM). Null control: the same decoder on
time-shuffled ``val_select`` trials. Then ``fidetype.trust.calibrate`` (n-best input, alpha 0.05, delta 0.1,
seed 0) -> guard -> per-user profile (``UserProfile``, as the bench). Cached; a second run reuses the files.

``replay``: an NTS stream of the replay trials (header with provenance meta; per trial: the frames at 80 ms,
the decoder's final n-best ``hypothesis``, a ``segment_end``; a 0.5 s pause between trials) is sent at real
time over the WebSocket binding (``/nts``, 127.0.0.1) into one collector (``fidetype.collector.bench.run``):
validate (provenance) -> segment (no rule fires: the source has the boundaries) -> guard (the profile, online
ACI) -> exporters: JSON Lines NTS stream, JSON Lines decision log, os_text stub, WebSocket ``/decisions``.
The outputs go through ``nts-conform`` (producer level); the bench records the per-stage latency.

Trials: ``val_eval`` only (no M4 decoder trained on them; wiki/questions/t15-split-audit.md). Default: 120
trials spread evenly over the 701 (about 37 min at real time); ``--trials 0`` = all 701 (about 3.6 h).

Decoders: ``m4-12`` (M4-12 fixed0, read only) or ``m4-13`` (M4-13 long0; needs the M4-13 queue's val_eval
log-probs and the CPU decode of val_select by the trust-reruns queue: see
experiments/2026-11-17-trust-reruns-m4-13/common.py).

Writes per-trial files (n-best texts, truths, decisions, collector outputs) only to
``C:/Users/zhang/bci-data/derived/p3-08-collector-replay/<decoder>/``. The repo gets aggregates only:
``results/<decoder>-summary.json`` (latency, decision counts, conformance levels; no text, no trial id).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import argparse  # noqa: E402
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

from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.adapters import b2t25 as B  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN_ROOT = DER / "p3-08-collector-replay"  # the only place this task writes per-trial files
D_IN = DER / "m4-01-02-lookahead"  # READ ONLY: texts, sessions
OUT = HERE / "results"
FRAME_PERIOD = 0.08
PAUSE_S = 0.5
ALPHA, DELTA, SEED = 0.05, 0.1, 0
N_NULL = 200
DEFAULT_TRIALS = 120

SOURCES = {
    "m4-12": {"cal": DER / "m2-19-trust-retune" / "logprobs-m2-19-m4-12-fixed0.npz",
              "held": D_IN / "logprobs-m4-12-fixed0.npz", "held_meta": D_IN / "decode-m4-12-fixed0.json"},
    "m4-13": {"cal": DER / "trust-reruns-m4-13" / "logprobs-m4-13-long0-val_select.npz",
              "held": DER / "m4-13" / "logprobs-m4-13-long0-val_eval.npz",
              "held_meta": DER / "m4-13" / "decode-m4-13-long0-val_eval.json",
              "held_fallback": DER / "trust-reruns-m4-13" / "logprobs-m4-13-long0-val_eval.npz",
              "held_meta_fallback": DER / "trust-reruns-m4-13" / "decode-m4-13-long0-val_eval.json"},
}


def log(*a: object) -> None:
    OUT.mkdir(exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def own(decoder: str) -> Path:
    p = OWN_ROOT / decoder
    assert p.parent.name == "p3-08-collector-replay"
    p.mkdir(parents=True, exist_ok=True)
    return p


def source(decoder: str) -> dict[str, Path]:
    s = dict(SOURCES[decoder])
    if not s["held"].exists() and "held_fallback" in s:
        s["held"], s["held_meta"] = s["held_fallback"], s["held_meta_fallback"]
    for k in ("cal", "held", "held_meta"):
        if not s[k].exists():
            raise SystemExit(f"p3-08: missing input {s[k]} for decoder {decoder} (run its decode first)")
    return s


def load_part(path: Path, part: str) -> tuple[list[str], list[np.ndarray], list[str]]:
    """(keys, log-probs, true texts) of one partition, in (session order, index) order (as P14-03)."""
    texts = json.loads((D_IN / "texts.json").read_text(encoding="utf-8"))
    order = {s: j for j, s in enumerate(json.loads((D_IN / "sessions.json").read_text(encoding="utf-8")))}
    z = np.load(path, allow_pickle=False)
    keys = sorted((k for k in z.files if f"|{part}|" in k), key=lambda k: (order[k.split("|")[0]], int(k.split("|")[2])))
    xs = [np.ascontiguousarray(z[k], dtype=np.float32) for k in keys]
    ts = [" ".join(texts[k.split("|")[0]][part][int(k.split("|")[2])].split()) for k in keys]
    return keys, xs, ts


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def word_decoder():
    """The P14-03 T15 word decoder: (T, 41) log-probs -> n-best [{"text", "score"}] (best first)."""
    from fidetype.streams.spec import NeuralTextStream

    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    tune = bt.load_json("tune.json")
    dec = bt.Decoders([], {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")})

    def decode(lp: np.ndarray) -> list[dict]:
        st = NeuralTextStream(log_probs=lp, frame_times=np.arange(lp.shape[0]) * FRAME_PERIOD,
                              vocab=list(B.SYMBOL_VOCAB), blank_id=0, vocab_type="phoneme")
        dec._wcache = {}
        nb = dec.words_fn(st)
        return [{"text": c.text, "score": round(float(c.score), 4)} for c in nb.candidates
                if math.isfinite(float(c.score))]

    return decode


def nbest_cached(path: Path, keys: list[str], xs: list[np.ndarray], decode, tag: str) -> list[list[dict]]:
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    t0, n0 = time.time(), len(cache)
    for i, (k, x) in enumerate(zip(keys, xs)):
        if k not in cache:
            cache[k] = decode(x)
            if (len(cache) - n0) % 100 == 0:
                path.write_text(json.dumps(cache), encoding="utf-8")  # checkpoint
                log(f"{tag}: {i + 1}/{len(keys)} decoded ({time.time() - t0:.0f} s)")
    path.write_text(json.dumps(cache), encoding="utf-8")
    log(f"{tag}: {len(keys)} n-best lists ({len(cache) - n0} new, {time.time() - t0:.0f} s)")
    return [cache[k] for k in keys]


def prep(decoder: str) -> None:
    import fidetype.trust as ft
    from fidetype.trust.personal import UserProfile, calibration_stats

    src, o = source(decoder), own(decoder)
    ck, cx, ct = load_part(src["cal"], "val_select")
    hk, hx, ht = load_part(src["held"], "val_eval")
    log(f"prep {decoder}: calibration val_select {len(cx)}, replay val_eval {len(hx)}")
    decode = word_decoder()
    cal = nbest_cached(o / "nbest-val_select.json", ck, cx, decode, "val_select")
    nbest_cached(o / "nbest-val_eval.json", hk, hx, decode, "val_eval")
    rng = np.random.default_rng(SEED)
    pick = rng.choice(len(cx), size=min(N_NULL, len(cx)), replace=False)
    nk = [f"shuffled|{ck[i]}" for i in pick]
    nx = [cx[i][rng.permutation(cx[i].shape[0])] for i in pick]
    nulls = nbest_cached(o / "nbest-null-shuffled.json", nk, nx, decode, "null")
    t0 = time.time()
    try:
        guard = ft.calibrate(cal, ct, alpha=ALPHA, delta=DELTA, input_kind="nbest", null_inputs=nulls,
                             decoder_name=f"{decoder}-word-lm", modality="intracortical", name=f"p3-08-{decoder}",
                             seed=SEED)
    except ft.NullControlError as e:
        log(f"prep {decoder}: calibrate REFUSED: {e}")
        raise SystemExit(1) from None
    log(f"prep {decoder}: guard {guard.config_id} in {time.time() - t0:.0f} s\n{guard.sheet}")
    stats = calibration_stats(guard, cal, ct)
    prof = UserProfile.new(f"p3-08-{decoder}", guard, salt="fidetype-p3-08", calibration=stats,
                           consent_ref="public-dataset-cc0")
    prof.save(o / "profile.json")
    (o / "guard-sheet.json").write_text(json.dumps(guard.sheet.to_dict(), indent=1, default=str), encoding="utf-8")


def pick_trials(n_all: int, n: int) -> list[int]:
    if n <= 0 or n >= n_all:
        return list(range(n_all))
    return sorted({int(round(x)) for x in np.linspace(0, n_all - 1, n)})


def stream(decoder: str, trials: int) -> tuple[list[dict], list[str], dict]:
    """The NTS events (header first, ``end`` last) and the true texts of the replay trials."""
    from fidetype.writer import stream_meta

    src, o = source(decoder), own(decoder)
    hk, hx, ht = load_part(src["held"], "val_eval")
    nb = json.loads((o / "nbest-val_eval.json").read_text(encoding="utf-8"))
    sha = json.loads(src["held_meta"].read_text(encoding="utf-8")).get("checkpoint_sha256")
    idx = pick_trials(len(hk), trials)
    meta = stream_meta(modality="intracortical", decoder_name=f"{decoder} + B2T '25 word LM (P14-03)",
                       decoder_version="1", causal=True, lookahead_s=0.0, lm_name="eng_tatoeba_6gram_mkn",
                       weights_sha256=sha, stream_id="auto", adapter_name="p3-08 replay (fidetype.adapters.b2t25)",
                       adapter_version=FT_VERSION, extra={"fidetype.dataset": "brain-to-text-25/t15 val_eval"})
    header = {"type": "header", "spec_version": "1.0", "source": f"p3-08/{decoder}", "vocab": list(B.SYMBOL_VOCAB),
              "vocab_type": "phoneme", "blank_id": 0, "frame_period": FRAME_PERIOD, "latency": 0.0,
              "clock_domain": "other", "meta": meta}
    evs: list[dict] = [header]
    t = 0.0
    for n, i in enumerate(idx):
        x = hx[i]
        for row in x:
            evs.append({"type": "frame", "t": round(t, 6), "log_probs": [round(float(v), 5) for v in row]})
            t += FRAME_PERIOD
        evs.append({"type": "hypothesis", "id": f"h{n}", "is_final": True, "score_semantics": "none",
                    "nbest": nb[hk[i]] or [{"text": "", "score": 0.0}]})
        evs.append({"type": "segment_end", "t": round(t - FRAME_PERIOD, 6), "unit": "utterance"})
        t += PAUSE_S
    evs.append({"type": "end"})
    info = {"trials": len(idx), "of": len(hk), "frames": sum(hx[i].shape[0] for i in idx),
            "stream_seconds": round(t, 1), "checkpoint_sha256": sha}
    return evs, [ht[i] for i in idx], info


def replay(decoder: str, trials: int, receiver: str) -> None:
    from fidetype.collector import bench as BN

    o = own(decoder)
    if not (o / "profile.json").exists():
        raise SystemExit(f"p3-08: run 'prep --decoder {decoder}' first")
    evs, texts, info = stream(decoder, trials)
    log(f"replay {decoder}: {info['trials']} val_eval trials, {info['frames']} frames, "
        f"{info['stream_seconds']} s of stream at real time over {receiver}")
    r = BN.run("implant-speech", receiver, o / "run", profile_file=o / "profile.json", events=evs, texts=texts,
               seg_toml="max_frames = 4000\n", timeout_s=info["stream_seconds"] + 300.0).report
    print(BN.format_report({**r, "profile": f"b2t25-t15/{decoder}"}))
    keep = ("decisions", "segments", "actions", "typed", "committed", "typed_only_commits", "wrong_commits",
            "stop_reason", "wall_s", "frames", "producer_errors", "online_threshold")
    summary = {
        "task": "P3-08", "decoder": decoder, "receiver": receiver, "fidetype_version": FT_VERSION,
        "date": time.strftime("%Y-%m-%d %H:%M"), "dataset": "Brain-to-Text '25 T15 (CC0), val_eval only",
        "replay": {k: v for k, v in info.items() if k != "checkpoint_sha256"},
        "decoder_checkpoint_sha256": info["checkpoint_sha256"],
        "guard": {"alpha": ALPHA, "delta": DELTA, "seed": SEED, "input_kind": "nbest", "calibration": "val_select",
                  "null_control": f"{N_NULL} time-shuffled val_select trials"},
        "budget_ms": r["latency_ms"]["budget_ms"], "within_budget": r["latency_ms"]["within_budget"],
        "latency_ms": r["latency_ms"]["stages"], "decision_steps": r["latency_ms"]["decision_steps"],
        "conformance": r["conformance"],
        **{k: r[k] for k in keep if k in r},
    }
    OUT.mkdir(exist_ok=True)
    name = f"{decoder}-summary.json" if trials == DEFAULT_TRIALS else f"{decoder}-summary-{info['trials']}.json"
    (OUT / name).write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    log(f"replay {decoder}: p95 added {r['latency_ms']['stages'].get('added', {}).get('p95')} ms "
        f"(budget {r['latency_ms']['budget_ms']} ms); producer level {r['conformance']['producer_level']}; "
        f"actions {r['actions']}; wrote results/{name}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=("prep", "replay", "all"))
    ap.add_argument("--decoder", choices=tuple(SOURCES), default="m4-12")
    ap.add_argument("--trials", type=int, default=DEFAULT_TRIALS, help=f"replay trials (default {DEFAULT_TRIALS}; 0 = all)")
    ap.add_argument("--receiver", choices=("websocket", "lsl"), default="websocket")
    a = ap.parse_args()
    if a.stage in ("prep", "all"):
        prep(a.decoder)
    if a.stage in ("replay", "all"):
        replay(a.decoder, a.trials, a.receiver)
    return 0


if __name__ == "__main__":
    sys.exit(main())
