"""A hypothesis-only stream: your decoder sends text n-best lists, not frames.

Run: python examples/hypothesis_stream.py

Use this route when your decoder has its own beam search and language
model. The trust layer then decides on each final n-best list.

The demo configuration was fitted on another (synthetic) decoder, so its
calibration maps these scores conservatively. For your decoder, fit a
configuration on your own labelled data with fidetype.calibrate().
"""

import io
import json

import fidetype
from fidetype.demo import load_config


def main() -> None:
    buf = io.StringIO()
    meta = fidetype.stream_meta(modality="emg", decoder_name="my-beam-decoder", decoder_version="0.3")
    w = fidetype.StreamWriter(buf, source="my-beam-decoder", meta=meta)
    w.hypothesis([("the boy found a red", 0.55), ("the boy found a bed", 0.30)],
                 is_final=False, score_semantics="uncalibrated_prob")
    w.hypothesis([("the boy found a red box", 0.92), ("the boy found a red fox", 0.05)],
                 is_final=True, score_semantics="uncalibrated_prob")
    w.segment_end()
    w.hypothesis([("my sister likes", 0.40), ("my sister lines", 0.35), ("by sister likes", 0.20)],
                 is_final=True, score_semantics="uncalibrated_prob")
    w.end()

    # Any frozen configuration works here; the demo ships one (fitted on synthetic data).
    # No decode_fn: hypothesis route. max_attempts=1: no ASK (the user does not repeat the phrase).
    layer = fidetype.StreamingTrustLayer(load_config(), streaming=fidetype.StreamingConfig(max_attempts=1))
    for line in buf.getvalue().splitlines():
        for d in layer.push(json.loads(line)):
            kind = "final" if d.final else "preview"
            print(f"{kind:8} {d.action.value:8} {list(d.shown)}  ({d.decision.reason})")


if __name__ == "__main__":
    main()
