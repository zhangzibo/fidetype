"""Pipeline integration run and latency budget of the collector (roadmap P3-04).

One configuration file, one real collector, synthetic input at a realistic
rate. The run checks the outputs with ``nts-conform`` and reports the added
latency per stage against the budget (:data:`fidetype.collector.latency.BUDGET_MS`)::

    python -m fidetype.collector.bench --out bench-out                 # both profiles, WebSocket + file
    python -m fidetype.collector.bench --profile emg-key --receiver lsl --json report.json

Pipeline (TOML, written to ``<out>/<profile>-<receiver>/collector.toml``)::

    receiver (websocket /nts | file | lsl)
      -> validate (stream level provenance)
      -> segment (blank run, pause, length)
      -> guard (drop-in guard from a per-user profile, online ACI, passthrough)
      -> exporters: jsonl NTS stream + jsonl decision log + os_text (stub) [+ websocket /decisions]

Profiles (synthetic, our own; no participant data):

``implant-speech``  a CTC character stream at 50 Hz (20 ms frames; the frame rate of speech
                    implant decoders), 28 tokens with a blank, plus the decoder's final n-best
                    ``hypothesis`` after each utterance (the decoder and its language model run
                    before the collector, as in a B2T '25 replay). No boundaries in the source:
                    the segmenter cuts at 6 blank frames. Guard: input kind ``nbest``, calibrated
                    here on 300 synthetic n-best lists. **Budget-gated.**
``emg-key``         one key-posterior frame per key press over the 32-key KT-sEMG vocabulary,
                    sent at 50 Hz (faster than a typist: a stress case), with a ``segment_end``
                    per phrase. Guard: ``builtin:synthetic-keys`` of ``fidetype live`` (n-best),
                    fed by the same key beam search (:func:`fidetype.live.runner.nbest_of_frames`).
                    **Budget-gated.**
``implant-logits``  the implant-speech frames without the hypothesis: the guard (input kind
                    ``logits``) runs its built-in CTC prefix beam search (beam 64, lexicon,
                    n-best marginal confidences) **inside the collector** at each boundary.
                    Reported, not gated: this search is decoding work, and it is slower than
                    the budget (an open gap; see ``docs/collector.md``).

Each guard is wrapped in a per-user profile (:class:`fidetype.trust.personal.UserProfile`),
so the guard processor runs :class:`~fidetype.trust.personal.PersonalTrust` drift tests and the
online controller (``guard.online("aci")``) on every decision. After the run the bench gives the
user's final text to :meth:`GuardProcessor.feedback` (the online / profile feedback path).

Our own code (Apache-2.0).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import string
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from fidetype.collector.latency import BUDGET_MS

PROFILES = ("implant-speech", "emg-key", "implant-logits")
#: Profiles whose p95 added latency must stay below the budget (the CI gate).
GATED_PROFILES = ("implant-speech", "emg-key")
RECEIVERS = ("websocket", "file", "lsl")
CHAR_VOCAB = ["_"] + list(string.ascii_lowercase) + [" "]
PHRASES = ["yes please", "thank you", "i am thirsty", "call my wife", "turn on the light", "i need help",
           "open the window", "good morning", "how are you", "more water please"]
LEXICON = sorted({w for p in PHRASES for w in p.split()})
FRAME_HZ = 50.0
#: Blank frames between two implant utterances (silence); the segmenter cuts after BLANK_CUT of them.
SILENCE_FRAMES, BLANK_CUT = 12, 6


def _log_softmax(x: np.ndarray) -> np.ndarray:
    m = x.max(axis=-1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(axis=-1, keepdims=True))


def implant_logits(text: str, rng: np.random.Generator, noise: float | None = None) -> np.ndarray:
    """Synthetic CTC logits of one utterance: per character one peak frame and two blank frames."""
    noise = rng.uniform(0.0, 1.0) if noise is None else noise
    rows = []
    for ch in text:
        target = CHAR_VOCAB.index(ch)
        if rng.random() < 0.25 * noise:
            target = int(rng.integers(1, len(CHAR_VOCAB)))
        for k in range(3):
            row = rng.normal(0.0, 1.0, len(CHAR_VOCAB))
            row[target if k == 0 else 0] += (9.0 - 6.0 * noise) if k == 0 else 7.0
            rows.append(row)
    return np.array(rows)


def _key_codes() -> dict[str, str]:
    codes = {c: f"Key{c.upper()}" for c in string.ascii_lowercase}
    codes[" "] = "Space"
    return codes


def implant_nbest(text: str, rng: np.random.Generator) -> list[dict[str, Any]]:
    """A synthetic decoder n-best list (best first; log-domain scores) for one implant utterance."""
    noise = rng.uniform(0.0, 1.0)
    others = [p for p in PHRASES if p != text]
    cands = [text] + [str(p) for p in rng.choice(others, size=3, replace=False)]
    gap = 6.0 * (1.0 - noise)
    scores = [0.0] + [float(-gap * rng.uniform(0.5, 1.5)) for _ in range(3)]
    if rng.random() < 0.3 * noise:
        scores[1] = 0.5
    order = np.argsort(scores)[::-1]
    return [{"text": cands[i], "score": round(scores[i], 4)} for i in order]


def key_logits(text: str, rng: np.random.Generator) -> np.ndarray:
    """Synthetic key posteriors (one frame per key press) over the 32-key KT-sEMG vocabulary."""
    from fidetype.adapters.kt_semg import KEY_VOCAB

    codes = _key_codes()
    noise = rng.uniform(0.0, 1.0)
    rows = []
    for ch in text:
        row = rng.normal(0.0, 1.0, len(KEY_VOCAB))
        row[KEY_VOCAB.index(codes[ch])] += 9.0 - 4.0 * noise
        rows.append(row)
    return np.array(rows)


# --- guards and per-user profiles ---------------------------------------------------------------


def implant_nbest_guard(seed: int = 5, n: int = 300) -> Any:
    """An n-best guard for the implant-speech profile (calibrated on synthetic n-best lists, a few seconds)."""
    import fidetype.trust as ft

    rng = np.random.default_rng(seed)
    texts = [str(rng.choice(PHRASES)) for _ in range(n)]
    nulls = [[{"text": str(p), "score": float(-rng.uniform(0.0, 0.5))} for p in rng.choice(PHRASES, 4, replace=False)]
             for _ in range(60)]
    return ft.calibrate([implant_nbest(t, rng) for t in texts], texts, null_inputs=nulls, null_trials=60,
                        decoder_name="bench-implant-lm", modality="intracortical")


def implant_guard(seed: int = 3, n: int = 200) -> Any:
    """A logits guard for the implant-logits profile (calibrated on synthetic utterances, a few seconds)."""
    import fidetype.trust as ft

    rng = np.random.default_rng(seed)
    texts = [str(rng.choice(PHRASES)) for _ in range(n)]
    return ft.calibrate([implant_logits(t, rng) for t in texts], texts, vocab=CHAR_VOCAB, blank="_",
                        lexicon=LEXICON, null_trials=40, decoder_name="bench-implant-ctc",
                        modality="intracortical")


def emg_key_guard() -> Any:
    """The packaged ``builtin:synthetic-keys`` guard of ``fidetype live`` (input kind n-best)."""
    import fidetype.trust as ft
    from fidetype.live.model import resolve_asset

    return ft.load(resolve_asset("builtin:synthetic-keys", ".guard.json"))


def write_profile(profile: str, path: Path, seed: int = 11) -> Path:
    """Make the guard of ``profile``, wrap it in a per-user profile (no text, no signal), save it."""
    from fidetype.live.runner import nbest_of_frames
    from fidetype.trust.personal import UserProfile, calibration_stats

    rng = np.random.default_rng(seed)
    texts = [str(rng.choice(PHRASES)) for _ in range(60)]
    if profile == "implant-speech":
        guard = implant_nbest_guard()
        inputs = [implant_nbest(t, rng) for t in texts]
    elif profile == "implant-logits":
        guard = implant_guard()
        inputs = [implant_logits(t, rng) for t in texts]
    else:
        guard = emg_key_guard()
        inputs = []
        for t in texts:
            lp = _log_softmax(key_logits(t, rng))
            inputs.append(nbest_of_frames(lp, np.arange(len(lp)) / FRAME_HZ))
    stats = calibration_stats(guard, inputs, texts)
    prof = UserProfile.new(f"bench-{profile}", guard, salt="fidetype-bench", calibration=stats,
                           consent_ref="synthetic-data")
    path.parent.mkdir(parents=True, exist_ok=True)
    prof.save(path)
    return path


# --- input streams ------------------------------------------------------------------------------


def stream_events(profile: str, n_utterances: int, seed: int = 0) -> tuple[list[dict[str, Any]], list[str]]:
    """The NTS events of one synthetic stream (header first, ``end`` last) and the true texts."""
    from fidetype import __version__
    from fidetype.adapters.kt_semg import KEY_VOCAB
    from fidetype.writer import stream_meta

    rng = np.random.default_rng(seed)
    texts = [str(rng.choice(PHRASES)) for _ in range(n_utterances)]
    implant = profile in ("implant-speech", "implant-logits")
    modality = "intracortical" if implant else "emg"
    name = "bench-implant-ctc" if implant else "bench-emg-keys"
    meta = stream_meta(modality=modality, decoder_name=name, decoder_version="0", causal=True, lookahead_s=0.0,
                       weights_sha256=hashlib.sha256(name.encode()).hexdigest(), stream_id="auto",
                       adapter_name="fidetype.collector.bench", adapter_version=__version__,
                       extra={"fidetype.synthetic": True})
    header: dict[str, Any] = {"type": "header", "spec_version": "1.0", "source": f"fidetype.collector.bench/{profile}",
                              "meta": meta, "latency": 0.0}
    if implant:
        header.update(vocab=CHAR_VOCAB, vocab_type="char", blank_id=0, frame_period=1.0 / FRAME_HZ)
    else:
        header.update(vocab=list(KEY_VOCAB), vocab_type="key", blank_id=None)
    evs: list[dict[str, Any]] = [header]
    k = 0

    def frame(row: np.ndarray) -> None:
        nonlocal k
        evs.append({"type": "frame", "t": round(k / FRAME_HZ, 6), "log_probs": [round(float(v), 6) for v in row]})
        k += 1

    for t in texts:
        if implant:
            for row in _log_softmax(implant_logits(t, rng)):
                frame(row)
            if profile == "implant-speech":  # the decoder's final n-best, right after the utterance
                evs.append({"type": "hypothesis", "id": f"h{len(evs)}", "is_final": True, "score_semantics": "none",
                            "nbest": implant_nbest(t, rng)})
            for _ in range(SILENCE_FRAMES):
                sil = rng.normal(0.0, 1.0, len(CHAR_VOCAB))
                sil[0] += 8.0
                frame(_log_softmax(sil))
        else:
            for row in _log_softmax(key_logits(t, rng)):
                frame(row)
            evs.append({"type": "segment_end", "t": round((k - 1) / FRAME_HZ, 6), "unit": "utterance"})
    evs.append({"type": "end"})
    return evs, texts


# --- configuration ------------------------------------------------------------------------------


def config_toml(profile: str, receiver: str, input_path: str, lsl_name: str = "") -> str:
    """The collector configuration of one bench run (TOML)."""
    rec = {"websocket": 'type = "websocket"\nlisten = "127.0.0.1:0"\n',
           "file": f'type = "file"\npaths = ["{input_path}"]\nstream_id = "bench"\nbatch = 1\n',
           "lsl": f'type = "lsl"\nstream_name = "{lsl_name}"\nstream_id = "bench"\nresolve_timeout_s = 10.0\n'
                  'on_gap = "mark"\n'}[receiver]
    seg = f"blank_frames = {BLANK_CUT}\nmax_frames = 400\n" if profile != "emg-key" else "max_frames = 200\n"
    ws_out = ""
    exporters = '"nts", "log", "typing"'
    if receiver == "websocket":
        ws_out = '\n[exporters.aac]\ntype = "websocket"\nreceiver = "in"\n'
        exporters += ', "aac"'
    return f"""# Collector pipeline of the P3-04 integration run ({profile}, {receiver} input). Generated.
[service]
log = "quiet"
metrics_file = "metrics.json"
latency = true
latency_budget_ms = {BUDGET_MS:g}

[receivers.in]
{rec}
[processors.check]
type = "validate"
level = "provenance"

[processors.seg]
type = "segment"
{seg}
[processors.guard]
type = "guard"
profile = "profile.json"
online = "aci"
passthrough = true

[exporters.nts]
type = "jsonl"
path = "out/stream.nts.jsonl"
types = ["header", "frame", "segment_end", "hypothesis", "end"]

[exporters.log]
type = "jsonl"
path = "out/decisions.jsonl"

[exporters.typing]
type = "os_text"
backend = "stub"
path = "out/typed.jsonl"
{ws_out}
[pipelines.main]
receivers = ["in"]
processors = ["check", "seg", "guard"]
exporters = [{exporters}]
"""


# --- run ----------------------------------------------------------------------------------------


@dataclass
class BenchResult:
    profile: str
    receiver: str
    workdir: Path
    report: dict[str, Any]


def _pace(evs: Sequence[dict[str, Any]], send: Any, rate_scale: float = 1.0) -> None:
    """Send events in real time: a frame at its ``t`` (50 Hz); other events right after the frame before them."""
    t0 = time.perf_counter()
    for ev in evs:
        if ev.get("type") == "frame":
            due = t0 + float(ev["t"]) * rate_scale
            while True:
                left = due - time.perf_counter()
                if left <= 0:
                    break
                time.sleep(min(left, 0.005))
        send(ev)


def _ws_producer(port: int, evs: list[dict[str, Any]], errors: list[str]) -> None:
    from fidetype.adapters.ws import WSProducer

    try:
        prod = WSProducer(f"ws://127.0.0.1:{port}/nts", evs[0], stream_id="bench", batch=1).connect()
        _pace(evs[1:], prod.send)
        prod.close()
    except Exception as e:  # noqa: BLE001 - reported by the caller
        errors.append(f"{type(e).__name__}: {e}")


def run(profile: str, receiver: str, out_dir: str | Path, *, n_utterances: int = 12, seed: int = 0,
        profile_file: Path | None = None, timeout_s: float = 120.0) -> BenchResult:
    """One integration run: write the inputs and the TOML file, run the collector, check the outputs."""
    from fidetype.collector.config import load
    from fidetype.collector.service import Collector

    if profile not in PROFILES or receiver not in RECEIVERS:
        raise ValueError(f"profile must be one of {PROFILES}, receiver one of {RECEIVERS}")
    work = Path(out_dir) / f"{profile}-{receiver}"
    (work / "out").mkdir(parents=True, exist_ok=True)
    prof = work / "profile.json"
    if profile_file is not None:
        prof.write_bytes(Path(profile_file).read_bytes())
    elif not prof.is_file():
        write_profile(profile, prof)
    evs, texts = stream_events(profile, n_utterances, seed)
    inp = work / "input.nts.jsonl"
    inp.write_text("".join(json.dumps(e) + "\n" for e in evs), encoding="utf-8", newline="\n")
    lsl_name = f"fidetype-bench-{profile}-{time.monotonic_ns() % 10**9}"
    (work / "collector.toml").write_text(config_toml(profile, receiver, inp.name, lsl_name), encoding="utf-8",
                                         newline="\n")
    col = Collector(load(work / "collector.toml"))
    errors: list[str] = []
    threads: list[threading.Thread] = []
    wall0 = time.perf_counter()
    if receiver == "lsl":
        from fidetype.adapters import lsl as L

        ready = threading.Event()
        th = threading.Thread(target=L.replay_to_lsl, args=(evs, lsl_name), daemon=True,
                              kwargs={"speed": 1.0, "channel_format": "double64", "wait_consumers_s": 20.0,
                                      "linger_s": 1.0, "ready": ready})
        th.start()
        threads.append(th)
        if not ready.wait(10):
            raise RuntimeError("LSL replay did not start")
    col.start()
    if receiver == "websocket":
        port = col.receiver("in").port
        th = threading.Thread(target=_ws_producer, args=(port, evs, errors), daemon=True)
        th.start()
        threads.append(th)
    reason = col.run(duration_s=timeout_s, max_streams=1)
    wall = time.perf_counter() - wall0
    for th in threads:
        th.join(timeout=5.0)
    guard = next(p for p in col.pipelines[0].processors if p.type == "guard")
    for utt, truth in enumerate(texts):  # the user's final text: online controller + profile drift tests
        guard.feedback("bench", utt, truth)
    report = check_outputs(work, col, texts)
    report.update(profile=profile, receiver=receiver, stop_reason=reason, wall_s=round(wall, 3),
                  frame_hz=FRAME_HZ, n_utterances=n_utterances, producer_errors=errors,
                  frames=sum(e.get("type") == "frame" for e in evs),
                  online_threshold=guard.stats().get("online_threshold"))
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    return BenchResult(profile, receiver, work, report)


def check_outputs(work: Path, col: Any, texts: list[str]) -> dict[str, Any]:
    """``nts-conform`` on the stream export and the decision log; OS-text rule; latency summary."""
    from fidetype.collector.exporters import committed_text
    from fidetype.conformance.levels import producer_level
    from fidetype.conformance.nts_conform import conform_file

    out = work / "out"
    targets = [conform_file(out / "stream.nts.jsonl", "trust-ready"), conform_file(out / "decisions.jsonl", "trust-ready")]
    prod = producer_level([t.level_input() for t in targets], ["text"])
    decisions = [json.loads(x) for x in (out / "decisions.jsonl").read_text(encoding="utf-8").splitlines() if x]
    typed = [json.loads(x) for x in (out / "typed.jsonl").read_text(encoding="utf-8").splitlines() if x]
    commits = [d for d in decisions if committed_text(d) is not None]
    lat = col.latency()["main"]
    return {
        "conformance": {"producer_level": prod["level"], "levels": prod["levels"], "why_not_higher": prod["why_not_higher"],
                        "targets": [{"target": Path(t.target).name, "form": t.form, "verdict": t.verdict,
                                     "stream_level": t.stream_level, "fails": [r.check for r in t.fails]}
                                    for t in targets]},
        "decisions": len(decisions), "segments": len(texts),
        "actions": {a: sum(d["action"] == a for d in decisions) for a in sorted({d["action"] for d in decisions})},
        "typed": len(typed), "committed": len(commits),
        "typed_only_commits": len(typed) == len(commits) and all(t["decision"]["action"] == "COMMIT" for t in typed),
        "wrong_commits": sum(committed_text(d).strip() != texts[d["utterance"]] for d in commits
                             if d["utterance"] < len(texts)),
        "latency_ms": lat,
        "metrics": col.metrics()["pipelines"]["main"]["processors"],
    }


def format_report(r: dict[str, Any]) -> str:
    lat = r["latency_ms"]
    lines = [f"{r['profile']} / {r['receiver']}: {r['decisions']} decisions for {r['segments']} segments "
             f"({', '.join(f'{k} {v}' for k, v in r['actions'].items())}); typed {r['typed']} (commits only: "
             f"{r['typed_only_commits']}); producer level {r['conformance']['producer_level']}"]
    for k, q in lat["stages"].items():
        if q["n"]:
            lines.append(f"  {k:<22} n={q['n']:<4} p50 {q['p50']:8.3f}  p95 {q['p95']:8.3f}  p99 {q['p99']:8.3f}"
                         f"  max {q['max']:8.3f} ms")
    lines.append(f"  budget: p95 added < {lat['budget_ms']:g} ms -> {'PASS' if lat['within_budget'] else 'FAIL'}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidetype.collector.bench",
                                 description="P3-04: run the collector pipeline on synthetic input at 50 Hz, check "
                                             "the outputs with nts-conform, report latency against the budget.")
    ap.add_argument("--out", default="bench-out", help="work folder (inputs, configuration, outputs, reports)")
    ap.add_argument("--profile", action="append", choices=PROFILES, help="profile (repeatable; default all three)")
    ap.add_argument("--receiver", action="append", choices=RECEIVERS,
                    help="receiver (repeatable; default websocket and file)")
    ap.add_argument("--utterances", type=int, default=12, help="segments per run (default 12)")
    ap.add_argument("--json", help="write all reports to this JSON file")
    a = ap.parse_args(argv)
    reports = []
    ok = True
    for prof in a.profile or list(PROFILES):
        for rec in a.receiver or ["websocket", "file"]:
            if rec == "lsl":
                from fidetype.adapters.lsl import pylsl_available

                if not pylsl_available():
                    print(f"{prof} / lsl: skipped (pylsl is not installed)")
                    continue
            r = run(prof, rec, a.out, n_utterances=a.utterances).report
            reports.append(r)
            print(format_report(r))
            ok = ok and r["conformance"]["producer_level"] == "trust-ready"
            if prof in GATED_PROFILES:
                ok = ok and bool(r["latency_ms"]["within_budget"])
    if a.json:
        Path(a.json).write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
