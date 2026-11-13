"""Bridge a stream over Lab Streaming Layer (LSL) into the trust layer, on one computer.

Run: pip install "fidetype[lsl]"; python examples/lsl_bridge.py

A sender thread publishes a demo stream as LSL outlets (as a decoder on
another machine would). The receiver resolves it, feeds the events to the
streaming trust layer and prints each trust_decision event. The same
works with two shells:

    fidetype demo --write-streams demo-streams
    fidetype lsl replay-to-lsl demo-streams/demo-04-no-signal.jsonl --name demo
    fidetype lsl run --config demo-streams/trust-config-demo.json --stream-name demo --decoder demo
"""

import tempfile
import threading
from pathlib import Path

import fidetype
from fidetype.adapters import lsl
from fidetype.demo import build_decoder
from fidetype.demo.__main__ import _write_streams


def main() -> None:
    if not lsl.pylsl_available():
        raise SystemExit('pylsl is not installed: pip install "fidetype[lsl]"')
    paths = _write_streams(Path(tempfile.mkdtemp(prefix="fidetype-lsl-")))
    stream_file, config_path = paths[4], paths[-1]     # demo-04-no-signal.jsonl

    ready = threading.Event()
    sender = threading.Thread(target=lsl.replay_to_lsl, args=(stream_file,),
                              kwargs={"name": "fidetype.example", "speed": 4.0, "ready": ready}, daemon=True)
    sender.start()
    ready.wait(10)

    layer = fidetype.StreamingTrustLayer(fidetype.FrozenTrustConfig.load(config_path), decode_fn=build_decoder(),
                                         streaming=fidetype.StreamingConfig(max_attempts=1))
    source = lsl.open_source("fidetype.example", timeout=10)
    runner = lsl.LSLTrustRunner(layer, source, sink=lambda ev: print(ev["action"], ev.get("shown"), ev.get("reason")))
    runner.run(duration_s=30, max_decisions=1)
    sender.join(5)


if __name__ == "__main__":
    main()
