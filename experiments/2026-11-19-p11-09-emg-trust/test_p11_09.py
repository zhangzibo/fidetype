"""P11-09 run.py helpers (CPU, no data): split buckets, replay selection, unit rows, guard on synthetic keys.

    .venv\\Scripts\\python.exe -m pytest -q experiments/2026-11-19-p11-09-emg-trust/test_p11_09.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def run():
    spec = importlib.util.spec_from_file_location("p11_09_run", HERE / "run.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["p11_09_run"] = m
    spec.loader.exec_module(m)
    return m


def test_hash_bucket_is_stable_and_balanced(run):
    b = [run.hash_bucket(f"s{i % 16}", i) for i in range(4000)]
    assert b == [run.hash_bucket(f"s{i % 16}", i) for i in range(4000)]
    assert set(b) == {0, 1} and 0.45 < np.mean(b) < 0.55


def test_pick_even(run):
    assert run.pick_even(10, 0) == list(range(10))
    assert run.pick_even(10, 20) == list(range(10))
    p = run.pick_even(1000, 240)
    assert len(p) == 240 and p[0] == 0 and p[-1] == 999


def test_arm_split(run):
    rows = [{"unit": f"u{k}", "split": ("val", "test")[k % 2], "bucket": (k // 2) % 2} for k in range(8)]
    cal, ev = run.arm_split(rows, "P")
    assert all(r["split"] == "val" for r in cal) and all(r["split"] == "test" for r in ev)
    cal, ev = run.arm_split(rows, "H")
    assert all(r["bucket"] == 0 for r in cal) and all(r["bucket"] == 1 for r in ev)
    assert run.split_digest(cal) != run.split_digest(ev)


def test_unit_rows_write_key_codes(run):
    from fidetype.adapters import emg2qwerty as A

    d = {"action": "commit", "text": A.codes_to_key_text("KeyH KeyI Space Enter"), "choices": [], "p_top1": 0.97,
         "nbest": ["hi_⏎"]}
    r = run.guard_row("abc#1", d)
    assert r["action"] == "commit" and r["nbest"][0]["text"] == "KeyH KeyI Space Enter"
    d2 = dict(d, action="withhold", text=None, nbest=["ha", "hi"])
    r2 = run.guard_row("abc#2", d2)
    assert r2["action"] == "abstain" and [x["text"] for x in r2["nbest"]] == ["KeyH KeyA", "KeyH KeyI"]
    r3 = run.always_row("abc#3", d2)
    assert r3["action"] == "commit" and r3["nbest"] == [{"text": "KeyH KeyA"}]


def test_peaky_no_lm_key_ctc_is_refused_by_the_shuffled_control():
    """The P11-09 guard recipe on a synthetic, perfectly peaky key decoder: the frame-shuffled control refuses it.

    Shuffled frames of a peaky CTC output keep their confidence (no LM, no lexicon), so the guard would commit
    confident nonsense. The real P11-01 output is not peaky in this way; the run reports the real controls.
    """
    import fidetype.trust as ft
    from fidetype.adapters import emg2qwerty as A

    v = A.key_ctc_vocab()
    rng = np.random.default_rng(0)
    words = ["the", "fox", "a", "dog", "is", "red"]
    texts, xs = [], []
    for _ in range(120):
        t = "_".join(rng.choice(words, size=2)) + "⏎"
        rows = []
        for ch in t:
            for tok in (v.index(ch), 0):
                p = np.full(len(v), 0.02 / (len(v) - 1))
                p[tok] = 0.98
                rows.append(np.log(p))
        texts.append(t)
        xs.append(np.array(rows, np.float32))
    with pytest.raises(ft.NullControlError, match="shuffled"):
        ft.calibrate(xs, texts, alpha=0.1, delta=0.2, input_kind="logits", vocab=v, blank=0,
                     input_scale="log_probs", frame_period=0.01, null_trials=40, decoder_name="test-keys",
                     modality="emg", seed=0)
