"""Causality of the lookahead GRU decoder (M4-01).

The key property: output step k depends on input bins <= t_k + L only
(t_k = newest bin of patch k, L = lookahead in bins). So changing the input
after bin t + L must not change any output stamped at or before t.
The NumPy tests always run; the torch tests skip without torch.
"""

from __future__ import annotations

import numpy as np
import pytest

from fidetype.decoders.lookahead_gru import (
    LookaheadGRUConfig,
    NumpyLookaheadGRU,
    StreamingLookaheadGRU,
    forward_numpy,
    lookahead_bins,
)

CFG = LookaheadGRUConfig(n_in=6, n_out=5, n_sessions=2, hidden=8, layers=2, patch=4, stride=2, smooth_sd=1.0,
                         la_max=6, la_proj=3, dropout=0.0)


@pytest.fixture(scope="module")
def model() -> NumpyLookaheadGRU:
    return NumpyLookaheadGRU.random(CFG, seed=1)


def _x(T: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal((T, CFG.n_in)).astype(np.float32)


@pytest.mark.parametrize("L", [0, 1, 3, 6])
def test_outputs_before_t_ignore_input_after_t_plus_L(model, L):
    T = 60
    x = _x(T, 0)
    base = forward_numpy(model, x, 1, L)
    rng = np.random.default_rng(10 + L)
    for t in [10, 25, 40, 52]:
        x2 = x.copy()
        x2[t + L + 1:] = rng.standard_normal((T - t - L - 1, CFG.n_in)) * 5.0
        out = forward_numpy(model, x2, 1, L)
        # steps whose stamp (newest patch bin t_k) is <= t
        ks = [k for k in range(base.shape[0]) if CFG.step_end_bin(k) <= t]
        assert ks, "test needs steps before t"
        np.testing.assert_array_equal(out[ks], base[ks])
        # and the change is visible later (the test is not vacuous)
        later = [k for k in range(base.shape[0]) if CFG.step_end_bin(k) > t + L]
        if later:
            assert not np.allclose(out[later], base[later])


@pytest.mark.parametrize("L", [1, 4])
def test_lookahead_is_used(model, L):
    """Input inside (t_k, t_k + L] changes step k: the lookahead is real, not only a delay."""
    T = 40
    x = _x(T, 3)
    base = forward_numpy(model, x, 0, L)
    k = 5
    tk = CFG.step_end_bin(k)
    x2 = x.copy()
    x2[tk + L] += 3.0
    out = forward_numpy(model, x2, 0, L)
    np.testing.assert_array_equal(out[:k], base[:k])
    assert not np.allclose(out[k], base[k])


def test_zero_lookahead_is_strictly_causal(model):
    T = 40
    x = _x(T, 4)
    base = forward_numpy(model, x, 0, 0)
    for k in range(base.shape[0] - 1):
        tk = CFG.step_end_bin(k)
        x2 = x.copy()
        x2[tk + 1:] = 0.0
        np.testing.assert_array_equal(forward_numpy(model, x2, 0, 0)[: k + 1], base[: k + 1])


@pytest.mark.parametrize("L", [0, 2, 6])
@pytest.mark.parametrize("chunk", [1, 3, 7])
def test_streaming_equals_batch(model, L, chunk):
    T = 47
    x = _x(T, 5)
    base = forward_numpy(model, x, 1, L)
    st = StreamingLookaheadGRU(model, 1, L)
    rows = []
    for i in range(0, T, chunk):
        rows.append(st.push(x[i:i + chunk]))
    rows.append(st.flush())
    out = np.concatenate(rows, 0)
    assert out.shape == base.shape
    np.testing.assert_allclose(out, base, rtol=1e-5, atol=1e-5)


@pytest.mark.parametrize("L", [0, 3, 6])
def test_streaming_emits_row_only_after_lookahead_bins(model, L):
    """A row comes out of push() exactly when bin t_k + L has arrived, never earlier."""
    T = 40
    x = _x(T, 6)
    st = StreamingLookaheadGRU(model, 0, L)
    emitted = 0
    for t in range(T):
        emitted += st.push(x[t:t + 1]).shape[0]
        # number of steps with t_k + L <= t
        expect = sum(1 for k in range(CFG.n_steps(T)) if CFG.step_end_bin(k) + L <= t)
        assert emitted == expect
    assert emitted + st.flush().shape[0] == CFG.n_steps(T)


def test_streaming_memory_is_bounded(model):
    st = StreamingLookaheadGRU(model, 0, 6)
    x = _x(400, 7)
    for t in range(400):
        st.push(x[t:t + 1])
        assert len(st.z) <= CFG.patch + CFG.la_max + CFG.stride + 1


def test_lookahead_bins_rounds_down():
    assert [lookahead_bins(ms) for ms in (0, 50, 100, 200, 300, 500)] == [0, 2, 5, 10, 15, 25]
    assert lookahead_bins(59.9) == 2


def test_frame_times_are_patch_ends():
    c = LookaheadGRUConfig()
    np.testing.assert_allclose(c.frame_times(3), [0.28, 0.36, 0.44])


# ---------------------------------------------------------------------------
# torch module (GPU env only)
# ---------------------------------------------------------------------------


def _torch_model():
    torch = pytest.importorskip("torch")
    from fidetype.decoders.lookahead_gru import build_torch_model, export_numpy_params

    torch.manual_seed(0)
    m = build_torch_model(CFG)
    with torch.no_grad():
        m.la_emb.weight.normal_(0, 0.3)
        m.day_W.add_(0.1 * torch.randn_like(m.day_W))
    m.eval()
    return torch, m, export_numpy_params


@pytest.mark.parametrize("L", [0, 2, 6])
def test_torch_equals_numpy(L):
    torch, m, export = _torch_model()
    nm = NumpyLookaheadGRU(CFG, export(m))
    x = _x(37, 8)
    with torch.no_grad():
        out_t = m(torch.from_numpy(x)[None], torch.tensor([1]), L)[0].numpy()
    np.testing.assert_allclose(out_t, forward_numpy(nm, x, 1, L), rtol=1e-4, atol=1e-4)


def test_torch_causal_and_padding_invariant():
    torch, m, _ = _torch_model()
    L = 3
    x = torch.from_numpy(_x(50, 9))[None]
    with torch.no_grad():
        base = m(x, torch.tensor([0]), L)[0]
        x2 = x.clone()
        t = 20
        x2[0, t + L + 1:] = 7.0
        out = m(x2, torch.tensor([0]), L)[0]
        ks = [k for k in range(base.shape[0]) if CFG.step_end_bin(k) <= t]
        assert torch.equal(out[ks], base[ks])
        # a padded batch item gives the same rows as the item alone (padding is masked)
        xp = torch.cat([x, torch.zeros(1, 13, CFG.n_in)], 1)
        outp = m(torch.cat([xp, xp]), torch.tensor([0, 0]), torch.tensor([L, L]), torch.tensor([50, 50]))[0]
        assert torch.allclose(outp[: base.shape[0]], base, atol=1e-5)
