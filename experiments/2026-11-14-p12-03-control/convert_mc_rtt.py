"""Convert the NLB MC_RTT train NWB file (DANDI 000129, CC-BY-4.0) to binned arrays.

Run in a throw-away environment with h5py (not a project dependency)::

    uv run --no-project --with h5py --with numpy python -I convert_mc_rtt.py IN.nwb OUT.npz [--bin-ms 20]

Output (outside the repository, for example C:/Users/zhang/bci-data/derived/nlb-mc-rtt/):
``counts`` (T x U uint16 spike counts per bin), ``t`` (bin end times, s),
``vel`` (T x 2 finger velocity, mm/s, bin mean), ``pos`` (T x 2 cursor position, mm, at bin end),
``target`` (T x 2 target position, mm, at bin end), ``valid`` (T bool: behaviour not NaN),
``heldout`` (U bool: NLB held-out units), ``bin_s``.

The file holds monkey data only. Nothing from this script goes into the repository.
"""

from __future__ import annotations

import argparse

import h5py
import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("nwb")
    ap.add_argument("out")
    ap.add_argument("--bin-ms", type=int, default=20)
    a = ap.parse_args()
    f = h5py.File(a.nwb, "r")
    beh = f["processing/behavior"]
    rate = float(beh["cursor_pos/starting_time"].attrs["rate"])
    t0 = float(beh["cursor_pos/starting_time"][()])
    pos = beh["cursor_pos/data"][()]
    vel = beh["finger_vel/data"][()]
    tgt = beh["target_pos/data"][()]
    n = pos.shape[0]
    step = int(round(a.bin_ms * rate / 1000.0))
    nb = n // step
    cut = nb * step
    vel_b = np.nanmean(vel[:cut].reshape(nb, step, 2), axis=1)
    pos_b = pos[step - 1:cut:step]
    tgt_b = tgt[step - 1:cut:step]
    t_end = t0 + (np.arange(nb) + 1) * step / rate
    edges = t0 + np.arange(nb + 1) * step / rate
    st = f["units/spike_times"][()]
    idx = f["units/spike_times_index"][()]
    heldout = f["units/heldout"][()].astype(bool)
    u = len(idx)
    counts = np.zeros((nb, u), dtype=np.uint16)
    start = 0
    for j in range(u):
        s = st[start:idx[j]]
        start = idx[j]
        h, _ = np.histogram(s, bins=edges)
        counts[:, j] = h
    valid = np.isfinite(vel_b).all(1) & np.isfinite(pos_b).all(1) & np.isfinite(tgt_b).all(1)
    np.savez_compressed(a.out, counts=counts, t=t_end, vel=vel_b, pos=pos_b, target=tgt_b, valid=valid,
                        heldout=heldout, bin_s=np.float64(step / rate))
    print(f"bins {nb} x units {u}; bin {step / rate * 1000:.0f} ms; valid {valid.mean():.3f}; "
          f"spikes {int(counts.sum())}; duration {nb * step / rate:.1f} s")


if __name__ == "__main__":
    main()
