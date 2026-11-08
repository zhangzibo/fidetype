"""Integration: simulator -> fidetype.lm beam search -> trust core -> harness."""

import importlib.util

import pytest

HAS_LM = importlib.util.find_spec("fidetype.lm") is not None and importlib.util.find_spec("fidetype.lm.beam") is not None

pytestmark = pytest.mark.skipif(not HAS_LM, reason="fidetype.lm (LM agent's beam search) is not available yet")


def test_simulator_lm_beam_trust_core_end_to_end():
    from fidetype.eval.harness import HarnessConfig, Item, run_harness
    from fidetype.lm import CharNgramLM, ctc_prefix_beam_search
    from fidetype.streams.corpus import sentences
    from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
    from fidetype.trust.types import from_lm_hypotheses

    sents = sentences(600, seed=21)
    lm = CharNgramLM(order=5).train(sents[60:])
    sim = NoisyDecoderSimulator(SimConfig.preset("best"), seed=2)

    def decode(stream):
        return from_lm_hypotheses(ctc_prefix_beam_search(stream, lm, beam=8, n_best=5), stream.meta)

    items = [Item(sim.simulate(s, seed=i).stream, s) for i, s in enumerate(sents[:24])]
    nb = decode(items[0].stream(0))
    assert len(nb) >= 1 and len(nb.top.char_confidences) == len(nb.top.text)
    grid = {"commit_p": (0.5, 0.9), "commit_max_risk": (1.0,), "offer_max_k": (3,),
            "abstain_risk": (1.01,), "final_fallback": ("offer",)}
    m = run_harness(items[16:], decode, items[:8], items[8:16], HarnessConfig(grid=grid, max_wrong_commit=1.0))
    assert m["n_sentences"] == 8
    assert m["cer"] <= m["greedy_cer"] + 0.05
    assert m["ewpm"] > 0
