"""Tests of fidetype.trust.policy."""

from fidetype.trust.policy import (
    Action,
    AlwaysCommitPolicy,
    DecisionPolicy,
    PolicyConfig,
    PolicyInputs,
    fit_thresholds,
)

TEXTS = tuple(f"candidate {i}" for i in range(10))


def _x(p, set_size, risk=0.0, other=False):
    return PolicyInputs(TEXTS, p, tuple(range(set_size)), other, risk)


def test_high_confidence_commits():
    pol = DecisionPolicy(PolicyConfig(commit_p=0.8))
    d = pol.decide(_x(0.95, 1))
    assert d.action == Action.COMMIT
    assert d.shown_candidates == (TEXTS[0],)
    assert d.reason


def test_low_confidence_asks_or_abstains():
    pol = DecisionPolicy(PolicyConfig(commit_p=0.8, offer_max_k=3, abstain_risk=0.9))
    assert pol.decide(_x(0.2, 8)).action == Action.ASK  # set too large to offer
    assert pol.decide(_x(0.2, 8, risk=0.95)).action == Action.ABSTAIN  # guard veto
    assert pol.decide(_x(0.99, 1, risk=0.95)).action == Action.ABSTAIN  # even when p is high
    pol2 = DecisionPolicy(PolicyConfig(commit_p=0.8, offer_max_k=3, final_fallback="abstain"))
    assert pol2.decide(_x(0.2, 8), final_attempt=True).action == Action.ABSTAIN


def test_medium_confidence_offers_conformal_set():
    pol = DecisionPolicy(PolicyConfig(commit_p=0.8, offer_max_k=3))
    d = pol.decide(_x(0.5, 3))
    assert d.action == Action.OFFER
    assert d.shown_candidates == TEXTS[:3]
    assert pol.decide(_x(0.5, 3, other=True)).action == Action.ASK
    d = pol.decide(_x(0.5, 8), final_attempt=True)
    assert d.action == Action.OFFER and len(d.shown_candidates) == 3


def test_guard_blocks_commit_and_can_be_disabled():
    cfg = PolicyConfig(commit_p=0.8, commit_max_risk=0.3, offer_max_k=3)
    assert DecisionPolicy(cfg).decide(_x(0.95, 2, risk=0.5)).action == Action.OFFER
    assert DecisionPolicy(cfg, use_guard=False).decide(_x(0.95, 2, risk=0.5)).action == Action.COMMIT


def test_empty_list_and_always_commit():
    empty = PolicyInputs((), 0.0, ())
    assert DecisionPolicy().decide(empty).action == Action.ASK
    assert DecisionPolicy().decide(empty, final_attempt=True).action == Action.ABSTAIN
    assert AlwaysCommitPolicy().decide(_x(0.01, 10)).action == Action.COMMIT


def test_fit_thresholds_respects_wrong_commit_limit():
    def evaluate(cfg):
        # A lower commit threshold is faster but makes more wrong commits.
        return {"ewpm": 10 - 5 * cfg.commit_p, "wrong_commit_rate": 0.5 * (1 - cfg.commit_p)}

    grid = {"commit_p": (0.2, 0.5, 0.8, 0.9, 0.95)}
    res = fit_thresholds(evaluate, grid, max_wrong_commit=0.05)
    assert res.feasible and res.config.commit_p == 0.9
    res = fit_thresholds(evaluate, grid, max_wrong_commit=0.001)
    assert not res.feasible and res.config.commit_p == 0.95
    assert res.n_evaluated == 5
