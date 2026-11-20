"""P3-12: streaming CRT model, batch frame push and the incremental guard session give the offline results."""

from __future__ import annotations

import string

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.pretrained import _crt
from fidetype.trust.streaming import StreamEventError

VOCAB = ["_"] + list(string.ascii_lowercase) + [" "]
PHRASES = ["yes please", "thank you", "i am thirsty", "call my wife", "turn on the light", "i need help",
           "open the window", "good morning", "how are you", "more water please"]
LEXICON = sorted({w for p in PHRASES for w in p.split()})


def fake_logits(text: str, rng: np.random.Generator) -> np.ndarray:
    noise = rng.uniform(0.0, 1.0)
    rows = []
    for ch in text:
        target = VOCAB.index(ch)
        if rng.random() < 0.25 * noise:
            target = int(rng.integers(1, len(VOCAB)))
        for k in range(3):
            row = rng.normal(0.0, 1.0, len(VOCAB))
            if k == 0:
                row[target] += 9.0 - 6.0 * noise
            else:
                row[0] += 7.0
            rows.append(row)
    return np.array(rows)


def crt_params(d: int = 16, dil: tuple[int, ...] = (1, 2, 4), seed: int = 0) -> dict[str, np.ndarray]:
    r = np.random.default_rng(seed)
    p = {"mean": r.standard_normal((1, 1, 32, 12)).astype(np.float32),
         "std": (1.0 + r.random((1, 1, 32, 12))).astype(np.float32),
         "out_norm.weight": np.ones(d, np.float32), "out_norm.bias": np.zeros(d, np.float32),
         "head.weight": (0.3 * r.standard_normal((11, d))).astype(np.float32),
         "head.bias": np.zeros(11, np.float32)}
    for s in ("left", "right"):
        p[f"{s}.conv.weight"] = (0.3 * r.standard_normal((4, 12, 5))).astype(np.float32)
        p[f"{s}.conv.bias"] = (0.1 * r.standard_normal(4)).astype(np.float32)
        p[f"{s}.proj.weight"] = (0.3 * r.standard_normal((d // 2, 4 * 16))).astype(np.float32)
        p[f"{s}.proj.bias"] = (0.1 * r.standard_normal(d // 2)).astype(np.float32)
    for i in range(len(dil)):
        q = f"blocks.{i}."
        p[q + "norm.weight"] = (1.0 + 0.1 * r.standard_normal(d)).astype(np.float32)
        p[q + "norm.bias"] = (0.1 * r.standard_normal(d)).astype(np.float32)
        p[q + "dw.weight"] = (0.3 * r.standard_normal((d, 1, 5))).astype(np.float32)
        p[q + "dw.bias"] = (0.1 * r.standard_normal(d)).astype(np.float32)
        p[q + "ff.0.weight"] = (0.3 * r.standard_normal((2 * d, d))).astype(np.float32)
        p[q + "ff.0.bias"] = (0.1 * r.standard_normal(2 * d)).astype(np.float32)
        p[q + "ff.3.weight"] = (0.3 * r.standard_normal((d, 2 * d))).astype(np.float32)
        p[q + "ff.3.bias"] = (0.1 * r.standard_normal(d)).astype(np.float32)
    return p


# --- streaming CRT -------------------------------------------------------------------------


@pytest.mark.parametrize("chunk", [1, 4, 13])
def test_crt_stream_equals_one_pass(chunk: int):
    p = crt_params()
    kw = dict(ring_k=5, kernel=5, dilations=(1, 2, 4))
    feat = np.random.default_rng(5).standard_normal((120, 32, 12)).astype(np.float32)
    full = _crt._forward(p, feat, **kw)
    s = _crt.CRTStream(p, **kw)
    out = np.concatenate([s.push(feat[a:a + chunk]) for a in range(0, len(feat), chunk)])
    np.testing.assert_allclose(out, full, atol=2e-5)
    assert (out.argmax(1) == full.argmax(1)).all()
    s.reset()  # a new stream starts from the zero state again
    np.testing.assert_allclose(s.push(feat[:9]), full[:9], atol=2e-5)
    assert s.push(feat[:0]).shape == (0, 11)


# --- batch frame push ----------------------------------------------------------------------


def _layer(guard: ft.TrustGuard):
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer
    from fidetype.trust.types import NBest

    sc = StreamingConfig(route="frames", max_attempts=1, provisional=False)
    return StreamingTrustLayer(guard.config, decode_fn=lambda st: NBest([]), streaming=sc)


def _rows(n: int, seed: int = 0) -> np.ndarray:
    a = np.random.default_rng(seed).normal(size=(n, len(VOCAB)))
    a = a - np.log(np.exp(a).sum(1, keepdims=True))
    return a.astype(np.float32).astype(np.float64)


def test_push_frames_equals_frame_events(guards):
    head = {"type": "header", "spec_version": "1.0", "vocab": VOCAB, "vocab_type": "char", "blank_id": 0,
            "source": "test", "frame_period": 0.01, "meta": {}}
    rows = _rows(25)
    ts = 0.01 + 0.01 * np.arange(25)
    a, b = _layer(guards["custom-logits"]), _layer(guards["custom-logits"])
    a.push(dict(head))
    for t, r in zip(ts, rows):
        a.push({"type": "frame", "t": float(t), "log_probs": [float(v) for v in r]})
    b.push(dict(head))
    b.push_frames(ts, rows)
    sa, sb = a._sessions["default"], b._sessions["default"]
    assert sa.n_events == sb.n_events and sa.last_t == sb.last_t and sa.times == sb.times
    assert all(np.array_equal(x, y) for x, y in zip(sa.rows, sb.rows)) and len(sa.rows) == len(sb.rows)
    rows[0, 0] = -1e9  # the caller's array may change: the session keeps a copy
    assert sb.rows[0][0] != -1e9


def test_push_frames_checks(guards):
    head = {"type": "header", "spec_version": "1.0", "vocab": VOCAB, "vocab_type": "char", "blank_id": 0,
            "source": "test", "frame_period": 0.01, "meta": {}}
    with pytest.raises(StreamEventError, match="before the header"):
        _layer(guards["custom-logits"]).push_frames([0.01], _rows(1))
    lay = _layer(guards["custom-logits"])
    lay.push(dict(head))
    with pytest.raises(StreamEventError, match="log-sum-exp"):
        lay.push_frames([0.01], _rows(1) + 1.0)
    with pytest.raises(StreamEventError, match="does not increase"):
        lay.push_frames([0.02, 0.02], _rows(2))
    with pytest.raises(StreamEventError, match="vocab has"):
        lay.push_frames([0.05], np.zeros((1, 3)))


# --- incremental guard session -------------------------------------------------------------


def _phrase_decoder(log_probs: np.ndarray) -> list[tuple[str, float]]:
    from fidetype.lm.beam import ctc_prefix_beam_search

    hyps = ctc_prefix_beam_search(log_probs, beam=32, n_best=32, prune_topk=None, blank_id=0)
    return [(h.text, h.score) for h in hyps if h.text and all(w in LEXICON for w in h.text.split())][:8]


@pytest.fixture(scope="module")
def guards() -> dict[str, ft.TrustGuard]:
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(160)]
    xs = [fake_logits(t, rng) for t in ts]
    return {
        "custom-logits": ft.calibrate(xs, ts, vocab=VOCAB, blank="_", decode_fn=_phrase_decoder, null_trials=30,
                                      input_scale="logits", decoder_name="t-custom"),
        "lexicon-auto": ft.calibrate(xs, ts, vocab=VOCAB, blank="_", lexicon=LEXICON, null_trials=30,
                                     decoder_name="t-lex"),
    }


def _strip(rec: dict) -> dict:
    rec = dict(rec)
    for k in ("time_utc", "latency_s"):
        rec.pop(k, None)
    return rec


def _result(r) -> dict:
    d = dict(r.__dict__)
    d["event"] = _strip(d["event"])
    return d


@pytest.mark.parametrize("name", ["custom-logits", "lexicon-auto"])
@pytest.mark.parametrize("chunk", [1, 4, 7])
def test_session_equals_decide(guards, name: str, chunk: int):
    g0 = guards[name]
    path = g0.save(_tmp() / "g.json")
    kw = {"decode_fn": _phrase_decoder} if name == "custom-logits" else {}
    g, h = ft.load(path, **kw), ft.load(path, **kw)  # two guards in the same state
    rng = np.random.default_rng(11)
    for i, t in enumerate(PHRASES[:6]):
        x = fake_logits(t, rng)
        a = g.decide(x, utterance_id=f"u{i}")
        s = h.session(utterance_id=f"u{i}")
        seen = [s.push(x[k:k + chunk]) for k in range(0, len(x), chunk)]
        assert s.n_frames == len(x)
        b = s.end()
        assert _result(a) == _result(b)
        assert _strip(g.audit_log[-1]) == _strip(h.audit_log[-1])
        # push returns the rows that the guard's stream carries (what a streaming decoder should read)
        st = g._codec.stream(x)
        np.testing.assert_array_equal(np.concatenate(seen), np.asarray(st.log_probs, np.float64))


def test_session_streaming_decoder_gives_offline_decision(guards):
    """A decoder fed with the session rows chunk by chunk gives the offline n-best, so the same decision."""
    g = guards["custom-logits"]
    rng = np.random.default_rng(12)
    x = fake_logits("turn on the light", rng)
    holder: dict = {}
    g2 = ft.load(g.save(_tmp() / "g.json"), decode_fn=lambda lp: holder["nb"])
    s = g2.session()
    rows = np.concatenate([s.push(x[k:k + 4]) for k in range(0, len(x), 4)])
    holder["nb"] = _phrase_decoder(rows)
    assert _result(s.end())["action"] == _result(g.decide(x))["action"]


def _tmp():
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp())


def test_session_errors(guards):
    g = guards["custom-logits"]
    s = g.session()
    with pytest.raises(ValueError, match="chunk must be"):
        s.push(np.zeros((2, 3)))
    s.push(fake_logits("yes please", np.random.default_rng(0)))
    s.end()
    with pytest.raises(RuntimeError, match="ended"):
        s.end()
    with pytest.raises(RuntimeError, match="ended"):
        s.push(np.zeros((1, len(VOCAB))))
