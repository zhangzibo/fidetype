"""M6-13: offline memory check of the trust process without LSL (finds what grows; one process, CPU).

The same layer as ``trust_proc.py`` (toy ``features`` frames from random 16-channel signal, demo decoder
incremental, GC rule), 4-s utterances pushed as fast as possible. Prints private bytes, RSS, the guard
edit-distance memo and the RefCharLM memo every 400 utterances.

    .venv\\Scripts\\python.exe experiments\\2026-11-13-m6-13-soak\\offline_memory.py [n_utterances] [--shadow]

Before the fix (guard on the shared 200,000-entry ``cached_edit_distance``) the memo grew by about 30
entries per utterance and private bytes by about 21 KB per utterance. After the fix
(``guard_edit_distance``, 4,096 entries) private bytes are flat after about 1,200 utterances.
"""

from __future__ import annotations

import gc
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import proc_stats  # noqa: E402
from trust_proc import CONFIG, Shadow, SwitchingToy  # noqa: E402


def main() -> None:
    from fidetype.demo import build_decoder
    from fidetype.trust import _align
    from fidetype.trust.frozen import FrozenTrustConfig
    from fidetype.trust.incremental import IncrementalReferenceDecoder
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer

    n_utt = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 4400
    use_shadow = "--shadow" in sys.argv
    memo = getattr(_align, "guard_edit_distance", _align.cached_edit_distance)
    cfg = FrozenTrustConfig.load(CONFIG)
    dec = build_decoder()
    layer = StreamingTrustLayer(cfg, decode_fn=dec, incremental=IncrementalReferenceDecoder.factory_for(dec),
                                streaming=StreamingConfig(max_attempts=1))
    sw, sh = SwitchingToy(250.0, 16), Shadow(20000, 20)
    rng, t = np.random.default_rng(0), 0.0
    h = {"type": "header", "spec_version": "0.1", **sw.header}
    layer.push(h, "s")
    sh.on_header(h)
    gc.collect()
    gc.freeze()
    gc.disable()
    for u in range(n_utt + 1):
        x = rng.standard_normal((1000, 16))
        ts = t + np.arange(1000) / 250
        t = ts[-1] + 1 / 250
        for ft, row in sw.process(x, ts):
            ev = {"type": "frame", "t": ft, "log_probs": row.tolist()}
            layer.push(ev, "s")
            if use_shadow:
                sh.push(ev)
        layer.push({"type": "segment_end", "lsl_t": t}, "s")
        if use_shadow:
            sh.finalize()
        gc.collect()
        if u % 400 == 0:
            m = proc_stats()
            print(u, f"private {m['private_mb']:.1f} MB", f"RSS {m['rss_mb']:.1f} MB", memo.cache_info(),
                  f"RefCharLM {len(dec.lm._cache)}", flush=True)


if __name__ == "__main__":
    main()
