"""M4-08: incremental decoders and the incremental frame route of the streaming layer.

Main property: decoding chunk by chunk gives exactly the batch result
(greedy, segment beam, CTC prefix beam with and without LM), and the
streaming layer's final decision with ``incremental=...`` equals the
default frame route. Synthetic streams only.
"""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest

from fidetype.conformance.io import write_jsonl
from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
from fidetype.lm import RETUNED, CharNgramLM, IncrementalPrefixBeam, ctc_forced_align, ctc_prefix_beam_search
from fidetype.lm.beam import ctc_forced_align_many
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.streams.vocab import VOCAB
from fidetype.trust._ctc import find_segments
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.incremental import (
    BufferedDecoder,
    CTCBeamSpec,
    IncrementalDecoder,
    IncrementalGreedy,
    IncrementalReferenceDecoder,
    SegmentTracker,
    stability_metrics,
)
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, main, replay
from fidetype.trust.testing import RefCharLM, ReferenceDecoder, greedy_nbest

GRID = {"commit_p": (0.3, 0.8), "commit_max_risk": (0.4, 1.0), "offer_max_k": (0, 3), "abstain_risk": (0.45, 1.01),
        "final_fallback": ("offer",)}


@pytest.fixture(scope="module")
def setup():
    sents = sentences(400, seed=5)
    ref = ReferenceDecoder(RefCharLM(5).fit(sents[60:]), beam=8)
    lm = CharNgramLM(order=4).train(sents[60:])
    sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=0.5), seed=3)
    items = [Item(sim.simulate(s, seed=17 * i).stream, s) for i, s in enumerate(sents[:60])]
    pipe = TrustPipeline(ref, HarnessConfig(grid=GRID, max_wrong_commit=0.2), {})
    pipe.fit(items[:20], items[20:45])
    cfg = FrozenTrustConfig.from_pipeline(pipe, "m4-08-test")
    cfg = replace(cfg, frame_temperature=2.5)  # exercise the per-chunk temperature
    return ref, lm, cfg, [it.stream(0) for it in items[45:]]


def _chunks(T, rng, max_k=9):
    pos = 0
    while pos < T:
        k = int(rng.integers(1, max_k + 1))
        yield pos, min(T, pos + k)
        pos += k


def _push_all(dec, lp, rng):
    for a, b in _chunks(lp.shape[0], rng):
        dec.push_frames(lp[a:b])


def _nb_equal(a, b):
    assert a.texts == b.texts
    for x, y in zip(a.candidates, b.candidates):
        assert x.score == y.score and x.logp_acoustic == y.logp_acoustic
        assert tuple(x.char_confidences) == tuple(y.char_confidences)


# --- building blocks ----------------------------------------------------------


def test_segment_tracker_equals_find_segments(setup):
    rng = np.random.default_rng(0)
    for st in setup[3]:
        tr = SegmentTracker(st.blank_id)
        got = []
        for a, b in _chunks(st.n_frames, rng):
            got += tr.push(st.log_probs[a:b])
        got += tr.close()
        assert [(s, e, c) for s, e, c, _ in got] == find_segments(st)
        assert all(np.array_equal(row, st.log_probs[c]) for _, _, c, row in got)


def test_greedy_incremental_equals_batch_and_partial_is_prefix_decode(setup):
    rng = np.random.default_rng(1)
    for st in setup[3]:
        dec = IncrementalGreedy.factory({"vocab": st.vocab, "blank_id": st.blank_id})
        assert isinstance(dec, IncrementalDecoder)
        cut = st.n_frames // 2
        _push_all(dec, st.log_probs[:cut], rng)
        _nb_equal(dec.partial(), greedy_nbest(replace(st, log_probs=st.log_probs[:cut], frame_times=st.frame_times[:cut])))
        _push_all(dec, st.log_probs[cut:], rng)
        _nb_equal(dec.finalize(st), greedy_nbest(st))


def test_reference_decoder_incremental_equals_batch(setup):
    ref, _, _, streams = setup
    rng = np.random.default_rng(2)
    fac = IncrementalReferenceDecoder.factory_for(ref)
    for st in streams[:8]:
        dec = fac({"vocab": st.vocab, "blank_id": st.blank_id})
        _push_all(dec, st.log_probs, rng)
        dec.partial()
        _nb_equal(dec.finalize(st), ref(st))


@pytest.mark.parametrize("kw", [dict(beam=8, n_best=5), dict(RETUNED, beam=32), dict(beam_logp=6.0, max_per_stem=2)])
@pytest.mark.parametrize("use_lm", [False, True])
def test_prefix_beam_chunked_equals_batch(setup, kw, use_lm):
    _, lm, _, streams = setup
    rng = np.random.default_rng(3)
    L = lm if use_lm else None
    for st in streams[:4]:
        ref = ctc_prefix_beam_search(st, L, **kw)
        dec = IncrementalPrefixBeam(list(st.vocab), st.blank_id, L, **kw)
        for a, b in _chunks(st.n_frames, rng):
            dec.push(st.log_probs[a:b])
            part = dec.partial(3)
            assert all(h.char_confidences.size == 0 for h in part)  # provisional: no confidences
            dec.prewarm()
        got = dec.finalize()
        assert [h.text for h in got] == [h.text for h in ref]
        for x, y in zip(got, ref):
            assert (x.score, x.logp_acoustic, x.logp_lm, x.frame_spans) == (y.score, y.logp_acoustic, y.logp_lm, y.frame_spans)
            for k in x.confidence_variants:
                assert np.array_equal(x.confidence_variants[k], y.confidence_variants[k], equal_nan=True)
        assert dec.finalize() is got  # idempotent
        with pytest.raises(RuntimeError):
            dec.push(st.log_probs[:1])


def test_prewarm_cache_is_bounded(setup):
    _, _, _, streams = setup
    st = streams[0]
    dec = IncrementalPrefixBeam(list(st.vocab), st.blank_id, None, beam=16, n_best=4)
    for t in range(st.n_frames):
        dec.push(st.log_probs[t:t + 1])
        dec.prewarm()
        assert len(dec._pairs) <= 4 * 64
    top, _ = dec.end_candidates()
    assert top == [h.text for h in dec.finalize()]


def test_forced_align_many_equals_single():
    rng = np.random.default_rng(4)
    V = 6
    for _ in range(40):
        T = int(rng.integers(1, 30))
        x = rng.normal(0, 2, (T, V))
        lp = x - np.log(np.exp(x).sum(1, keepdims=True))
        lp[rng.random((T, V)) < 0.1] = -np.inf  # some impossible paths
        seqs = [tuple(int(c) for c in rng.integers(1, V, int(rng.integers(0, 12)))) for _ in range(5)]
        seqs.append((1, 1, 1))  # repeats need blanks
        got = ctc_forced_align_many(lp, seqs, 0)
        assert got == [ctc_forced_align(lp, s, 0) if s else [] for s in seqs]


# --- the streaming layer -------------------------------------------------------


def _decisions(layer, streams, tmp_path, tag):
    out = []
    for i, st in enumerate(streams):
        p = tmp_path / f"{tag}-{i}.jsonl"
        write_jsonl(st, p)
        out.append(replay(p, layer, session_id=f"s{i}"))
    return out


def _layer(cfg, **kw):
    sc = {k: kw.pop(k) for k in ("partial_every_frames", "incremental_chunk_frames") if k in kw}
    return StreamingTrustLayer(cfg, streaming=StreamingConfig(max_attempts=1, **sc), **kw)


def _same_final(a, b):
    fa = [d for d in a if d.final]
    fb = [d for d in b if d.final]
    assert len(fa) == len(fb) == 1
    assert fa[0].decision == fb[0].decision
    assert fa[0].inputs == fb[0].inputs
    assert fa[0].guard == fb[0].guard
    assert fa[0].provenance["input"]["stream_sha256"] == fb[0].provenance["input"]["stream_sha256"]


def test_chunk_temperature_equals_stream_temperature(setup):
    _, _, cfg, streams = setup
    fs = cfg.build().frame_scaler
    assert fs.temperature != 1.0
    st = streams[0]
    whole = fs.transform_stream(st).log_probs
    parts = [fs.transform_logits(st.log_probs[a:b].astype(np.float32)).astype(np.float32)
             for a, b in _chunks(st.n_frames, np.random.default_rng(5))]
    assert np.array_equal(np.concatenate(parts), whole)


@pytest.mark.parametrize("chunk", [1, 7])
def test_layer_incremental_equals_default(setup, tmp_path, chunk):
    ref, lm, cfg, streams = setup
    spec = CTCBeamSpec(dict(RETUNED, beam=32), lm=lm, prewarm_every=5)
    cases = [
        (greedy_nbest, IncrementalGreedy.factory),
        (ref, IncrementalReferenceDecoder.factory_for(ref)),
        (spec.decode_fn, spec.factory),
        (greedy_nbest, BufferedDecoder.factory_for(greedy_nbest)),
    ]
    sts = streams[:5]
    for k, (fn, fac) in enumerate(cases):
        base = _decisions(_layer(cfg, decode_fn=fn), sts, tmp_path, f"b{k}")
        inc_layer = _layer(cfg, incremental=fac, incremental_chunk_frames=chunk, partial_every_frames=6)
        inc = _decisions(inc_layer, sts, tmp_path, f"i{k}")
        for a, b in zip(base, inc):
            _same_final(a, b)
            prov = [d for d in b if not d.final]
            assert prov and all(d.provenance["input"]["decoder_mode"] == "incremental" for d in prov)
        assert inc_layer.session_state("s0")["incremental_frames_pushed"] == 0  # reset after the utterance


def test_layer_partials_do_not_change_final(setup, tmp_path):
    _, _, cfg, streams = setup
    a = _decisions(_layer(cfg, incremental=IncrementalGreedy.factory), streams[:3], tmp_path, "a")
    b = _decisions(_layer(cfg, incremental=IncrementalGreedy.factory, partial_every_frames=1), streams[:3], tmp_path, "b")
    for x, y, st in zip(a, b, streams):
        _same_final(x, y)
        assert sum(not d.final for d in y) == st.n_frames  # one preview per frame


def test_layer_config_validation(setup):
    _, _, cfg, _ = setup
    with pytest.raises(ValueError):
        StreamingConfig(incremental_chunk_frames=0)
    with pytest.raises(ValueError):
        StreamingTrustLayer(cfg, streaming=StreamingConfig(route="frames"))
    lay = StreamingTrustLayer(cfg, incremental=IncrementalGreedy.factory)
    assert lay.route == "frames"


def test_cli_incremental_matches(setup, tmp_path, capsys):
    _, _, cfg, streams = setup
    cfgp = tmp_path / "trust.json"
    cfg.save(cfgp)
    p = tmp_path / "a.jsonl"
    write_jsonl(streams[0], p)
    outs = []
    for extra in ([], ["--incremental"]):
        assert main(["replay", "--config", str(cfgp), "--decoder", "greedy", *extra, str(p)]) == 0
        ev = json.loads(capsys.readouterr().out.splitlines()[0])
        outs.append({k: ev[k] for k in ("action", "shown", "p_top1", "guard_risk")})
    assert outs[0] == outs[1]


def test_stability_metrics():
    pv = [(0.1, "h"), (0.2, "he"), (0.3, "hx"), (0.4, "hel"), (0.5, "hello"), (0.6, "hello")]
    m = stability_metrics(pv, "hello", 0.8)
    assert m["n_previews"] == 6 and m["n_changes"] == 4 and m["n_rewrites"] == 2
    assert m["stable_at"] == 0.5 and abs(m["time_to_stable_before_end"] - 0.3) < 1e-12
    assert m["last_preview_equals_final"] and abs(m["prefix_ok_fraction"] - 5 / 6) < 1e-12
    m2 = stability_metrics([(0.1, "a")], "b", 1.0)
    assert m2["stable_at"] is None and not m2["last_preview_equals_final"]
