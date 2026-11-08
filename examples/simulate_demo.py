"""Simulate three sentences at each preset and print the results.

Run: uv run python examples/simulate_demo.py
"""

import numpy as np

from fidetype.eval.metrics import cer, ctc_greedy_decode
from fidetype.streams.simulator import PRESET_CER, NoisyDecoderSimulator, SimConfig

SENTENCES = [
    "the quick brown fox jumps over the lazy dog",
    "please close the window before you leave",
    "the jazz band played until midnight",
]


def main() -> None:
    for preset in ("perfect", "best", "median", "worst"):
        for temperature in (1.0, 0.5):
            cfg = SimConfig.preset(preset, confidence_temperature=temperature)
            sim = NoisyDecoderSimulator(cfg, seed=42)
            print(f"\n=== preset {preset} (target CER {PRESET_CER[preset]:.2f}), "
                  f"confidence_temperature {temperature} ===")
            for text in SENTENCES:
                res = sim.simulate(text)
                hyp = ctc_greedy_decode(res.stream)
                print(f"  target : {res.text}")
                print(f"  greedy : {hyp}")
                print(f"  CER {cer(res.text, hyp):.3f} | "
                      f"mean reported confidence {np.mean(res.peak_confidence):.3f} | "
                      f"true peak accuracy {np.mean(res.peak_correct):.3f} | "
                      f"{res.stream.n_frames} frames")


if __name__ == "__main__":
    main()
