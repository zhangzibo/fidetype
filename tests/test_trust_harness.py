"""End-to-end test of the evaluation harness (simulator + reference decoder)."""

import math

import pytest

from fidetype.eval.harness import HarnessConfig, Item, run_harness
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust.testing import RefCharLM, ReferenceDecoder, greedy_nbest

SMALL_GRID = {
    "commit_p": (0.5, 0.8, 0.95),
    "commit_max_risk": (0.3, 1.0),
    "offer_max_k": (0, 3),
    "abstain_risk": (1.01,),
    "final_fallback": ("offer",),
}


@pytest.fixture(scope="module")
def setup():
    sents = sentences(900, seed=11)
    lm = RefCharLM(5).fit(sents[150:])
    dec = ReferenceDecoder(lm, beam=8)
    sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=0.5), seed=5)

    def item(i, s):
        return Item(sim.simulate(s, seed=100 * i).stream, s, regen=lambda a: sim.simulate(s, seed=100 * i + a).stream)

    items = [item(i, s) for i, s in enumerate(sents[40:130])]
    return dec, items[:30], items[30:60], items[60:]


def test_harness_end_to_end(setup):
    dec, cal, val, test = setup
    cache: dict = {}
    m = run_harness(test, dec, cal, val, HarnessConfig(grid=SMALL_GRID, max_wrong_commit=0.1), cache)
    for k in (
        "cer", "wer", "ece_sentence_before", "ece_sentence_after", "ece_char_before", "ece_char_after",
        "coverage", "mean_set_size", "guard_auroc", "rate_commit", "rate_offer", "rate_ask",
        "rate_abstain", "ewpm", "wrong_commit_rate",
    ):
        assert k in m and not (isinstance(m[k], float) and math.isnan(m[k])), k
    assert m["cer"] < m["greedy_cer"]  # the LM helps
    assert 1.5 < m["fit_temperature_frame"] < 2.5  # inverse of the simulator's 0.5
    assert m["ece_char_after"] < m["ece_char_before"]
    assert abs(m["rate_commit"] + m["rate_offer"] + m["rate_ask"] + m["rate_abstain"] - 1) < 1e-9
    assert 0 < m["ewpm"] < 40
    assert len(m["records"]) == len(test)
    # Baselines through the same harness.
    base = run_harness(test, dec, cal, val, HarnessConfig(policy="always_commit"), cache)
    assert base["rate_commit"] == 1.0
    g = run_harness(test, greedy_nbest, cal, None, HarnessConfig(policy="always_commit"))
    assert g["wrong_commit_rate"] > base["wrong_commit_rate"]
    assert g["ewpm"] < base["ewpm"]


def test_harness_ablations_run(setup):
    dec, cal, val, test = setup
    cache: dict = {}
    for cfg in (
        HarnessConfig(grid=SMALL_GRID, use_calibration=False),
        HarnessConfig(grid=SMALL_GRID, use_guard=False),
    ):
        m = run_harness(test, dec, cal, val, cfg, cache)
        assert m["n_sentences"] == len(test)
    assert m["fit_policy_config"]["commit_max_risk"] == 1.0
