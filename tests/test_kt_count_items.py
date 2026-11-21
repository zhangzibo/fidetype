"""P14-52 (gap 148): the KT-sEMG item count reads only the key log and the start-time file."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from fidetype.adapters import kt_semg as K
from fidetype.pretrained import readers as R

START = datetime(2020, 9, 13, 8, 26, 40)
OFFSET = -4  # US daylight time, as on the real runs
DUR_S = 14.0


def _run(root: Path, with_csv: bool = True) -> Path:
    """One small KT-sEMG run: 3 bursts of >= 5 keys, 1 short burst, 1 key inside the start margin,
    1 duplicate key time."""
    root.mkdir(parents=True, exist_ok=True)
    t0 = K.start_unix(START, OFFSET)
    rel: list[float] = [0.05]  # inside the 0.15 s margin: dropped by the reader
    rel += [1.0 + 0.3 * i for i in range(6)]  # burst 1 (6 keys)
    rel += [5.0 + 0.3 * i for i in range(3)]  # 3 keys: too short
    rel += [8.0, 8.3, 8.3, 8.6, 8.9, 9.2]  # burst 2: one duplicate time (kept once) -> 5 keys
    rel += [12.0 + 0.25 * i for i in range(7)]  # burst 3 (7 keys)
    chars = "abcdefghijklmnopqrstuvwxyz"
    lines = [f"{chars[i % 26]} {t0 + r:.6f}" for i, r in enumerate(rel)]
    (root / "run3_keys.txt").write_bytes(("\r\n".join(lines) + "\r\n").encode("latin-1"))
    (root / "run3_ts.txt").write_text(START.strftime("%Y-%m-%d %H:%M:%S.000"), encoding="ascii")
    if with_csv:
        n = int(DUR_S * K.SAMPLE_RATE_HZ)
        head = "Time\t" + "\t".join(f"c{i}" for i in range(K.N_CHANNELS))
        a = np.zeros((n, K.N_CHANNELS + 1), np.float32)
        a[:, 0] = np.arange(n) / K.SAMPLE_RATE_HZ
        a[:, 1:] = np.random.default_rng(0).integers(-9, 10, (n, K.N_CHANNELS))
        np.savetxt(root / "run3.csv", a, fmt="%g", delimiter="\t", header=head, comments="")
    return root / "run3.csv"


def test_key_log_count_equals_the_reader_count(tmp_path):
    csv = _run(tmp_path)
    full = len(R.read_kt_run(csv)[1])
    assert full == 3
    assert R.count_kt_run(csv) == full == R.count_items("kt-semg-run", csv)


def test_count_does_not_open_the_emg_file(tmp_path, monkeypatch):
    csv = _run(tmp_path)

    def no_csv(*_a, **_k):
        raise AssertionError("count_items must not read runN.csv")

    monkeypatch.setattr(K, "read_emg_csv", no_csv)
    assert R.count_items("kt-semg-run", csv) == 3
    csv.unlink()  # the CSV may be absent
    assert R.count_items("kt-semg-run", csv) == 3
    with pytest.raises(ValueError, match="runN.csv"):
        R.count_kt_run(tmp_path / "other.csv")


def test_offset_from_keys_equals_the_offset_with_the_duration(tmp_path):
    _run(tmp_path, with_csv=False)
    keys = [k.unix_s for k in K.read_keys(tmp_path / "run3_keys.txt")]
    assert K.infer_utc_offset_from_keys(START, keys) == K.infer_utc_offset_hours(START, keys, DUR_S) == OFFSET
    with pytest.raises(ValueError, match="no key presses"):
        K.infer_utc_offset_from_keys(START, [])
    with pytest.raises(ValueError, match="no UTC offset"):
        K.infer_utc_offset_from_keys(START, [K.start_unix(START, 14) - 10.0])


# Local data only (KT-sEMG, CC BY 4.0, about 20 GB; not in CI). The expected counts come from
# read_kt_run's rule with the EMG length of each runN.csv (row count / 2000 Hz), measured on
# 2026-11-21 (P14-52): no key press falls outside a recording, all runs last under one hour.
KT_RAW = Path(r"C:\Users\zhang\bci-data\raw\kt-semg")
KT_COUNTS = {1: 11, 2: 3, 3: 3, 4: 11, 5: 9, 6: 15, 7: 38, 8: 11, 9: 9, 10: 12, 11: 25, 12: 44, 13: 25, 14: 33,
             15: 40, 16: 48, 17: 44, 18: 39, 19: 19, 20: 42, 21: 56, 22: 20, 23: 13, 24: 44, 25: 42, 26: 3,
             27: 15, 28: 22, 29: 46}


@pytest.mark.skipif(not (KT_RAW / "run28_keys.txt").is_file(), reason="KT-sEMG data is local only")
def test_key_log_counts_on_the_real_runs(monkeypatch):
    monkeypatch.setattr(K, "read_emg_csv", lambda *_a, **_k: pytest.fail("runN.csv was read"))
    got = {r: R.count_items("kt-semg-run", KT_RAW / f"run{r}.csv") for r in KT_COUNTS}
    assert got == KT_COUNTS
