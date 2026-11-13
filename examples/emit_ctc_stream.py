"""Emit a NeuralTextStream from the log-probabilities of a CTC decoder.

Run: python examples/emit_ctc_stream.py [OUT_DIR]

Your decoder gives a (T, V) matrix of per-frame log-probabilities over
the vocabulary (blank first). Here a synthetic decoder stands in for it.
The script writes the stream two ways (whole matrix, and one frame at a
time as a live decoder would), then checks both with the conformance suite.
"""

import sys
import tempfile
from pathlib import Path

import fidetype
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig


def my_decoder_log_probs(text: str):
    """Stand-in for your CTC decoder: return (frame_times, log_probs (T, V))."""
    sim = NoisyDecoderSimulator(SimConfig(target_cer=0.1, frame_rate_hz=25.0), seed=0)
    st = sim.simulate(text).stream
    return st.frame_times, st.log_probs


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="fidetype-"))
    out.mkdir(parents=True, exist_ok=True)
    times, log_probs = my_decoder_log_probs("hello world")

    # The meta keys that the 'trust-ready' level asks for.
    meta = fidetype.stream_meta(modality="eeg", decoder_name="my-ctc", decoder_version="1.0")

    # 1. Whole matrix -> NeuralTextStream -> file (.jsonl or .npz).
    stream = fidetype.make_stream(log_probs, frame_times=times, frame_period=0.04, source="my-ctc", meta=meta)
    a = fidetype.write_stream(stream, out / "batch.jsonl")

    # 2. One frame at a time (a live decoder). Each event is checked before it is written.
    with fidetype.open_stream(out / "live.jsonl", "w", source="my-ctc", meta=meta, frame_period=0.04) as w:
        for t, row in zip(times, log_probs):
            w.frame(t, row)          # or w.frame(t, logits=raw_scores)
        w.segment_end(float(times[-1]))

    for path in (a, out / "live.jsonl"):
        report = fidetype.validate(path)
        print(f"{path}: level {report.level}")
        for f in report.failures():   # here: the provenance checks (add weights_sha256= and stream_id="auto")
            print(f"  not met: {f.check_id} (spec {f.clause}): {f.message}")


if __name__ == "__main__":
    main()
