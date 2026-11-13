"""Run the streaming trust layer with a frozen configuration on stream files.

Run: python examples/streaming_trust.py [CONFIG.json STREAM.jsonl ...]

Without arguments the script writes the demo streams and the demo
configuration to a temporary folder and uses them. With your own data:
fit a configuration once with fidetype.calibrate(streams, texts, decode_fn)
on labelled calibration data, save it with config.save("trust.json"),
then load it here. A configuration is valid only with the decode_fn it
was fitted with.
"""

import sys
import tempfile
from pathlib import Path

import fidetype
from fidetype.demo import build_decoder
from fidetype.demo.__main__ import _write_streams


def main() -> None:
    if len(sys.argv) > 2:
        config_path, files = Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]]
        decode_fn = fidetype.greedy_decoder()          # use the decode_fn your config was fitted with
    else:
        paths = _write_streams(Path(tempfile.mkdtemp(prefix="fidetype-demo-")))
        config_path, files = paths[-1], paths[:-1]
        decode_fn = build_decoder()                    # the demo beam search + 5-gram LM

    config = fidetype.FrozenTrustConfig.load(config_path)
    print(f"config {config.config_id}")
    layer = fidetype.StreamingTrustLayer(config, decode_fn=decode_fn,
                                         streaming=fidetype.StreamingConfig(max_attempts=1))
    for i, path in enumerate(files):
        for event in fidetype.open_stream(path):
            for d in layer.push(event, session_id=f"s{i}"):
                if d.final:
                    print(f"{path.name:32} {d.action.value:8} {list(d.shown)[:1]}  ({d.decision.reason})")


if __name__ == "__main__":
    main()
