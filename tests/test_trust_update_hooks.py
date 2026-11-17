"""Tests of the P15-02 update hooks and ledger records.

- fidetype.trust.adaptive.GuardedUpdateLoop: ledger entries and listeners
- fidetype.trust.provenance: the ``update`` entry kind and its verify rules
- fidetype.trust.update_hooks: TrustGuardUpdater, OnlinePolicyUpdater, swap_guard
"""

from __future__ import annotations

import functools
import json
import math

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.trust.adaptive import GuardedUpdateLoop
from fidetype.trust.online_risk import OnlineCommitRiskControl, OnlineTrustPolicy
from fidetype.trust.policy import Action, DecisionPolicy, PolicyConfig, PolicyInputs
from fidetype.trust.provenance import ProvenanceLedger, read_entries, verify
from fidetype.trust.update_hooks import OnlinePolicyUpdater, TrustGuardUpdater, swap_guard

from test_trust_dropin import LEXICON, PHRASES, VOCAB, fake_logits, nbest_data, noise_nbest

GOOD_RISK = 0.2
NO_EVIDENCE = 1.0


def quiet_nulls(n: int = 20):
    return [(0.99, "the cat", NO_EVIDENCE)] * (n // 2) + [(-math.inf, "a", GOOD_RISK)] * (n - n // 2)


def run_update(loop, version, ids, *, bad=0, champion=True, trained_on=(), nulls=None):
    loop.new_version(version, trained_on=trained_on)
    for k, i in enumerate(ids):
        wrong = k < bad
        loop.add_check_item(i, 0.1 if wrong else 0.9, 1.0 if wrong else 0.0, text="a b", guard_risk=GOOD_RISK,
                            champion=(0.9, 0.0, GOOD_RISK, "a b") if champion else None)
    loop.recalibrate()
    loop.check_null_controls(uniform=quiet_nulls() if nulls is None else nulls, shuffled=quiet_nulls())
    return loop.finish_update()


def updates(ledger):
    return [(e["body"]["stage"], e["body"]["update_id"]) for e in ledger.entries if e["kind"] == "update"]


# --- ledger records of the loop ----------------------------------------------------


def test_every_proposal_and_decision_is_a_hash_chained_update_entry(tmp_path):
    path = tmp_path / "updates.jsonl"
    led = ProvenanceLedger(path)
    loop = GuardedUpdateLoop(lam_init=0.0, ledger=led)
    loop.start_session("d1")
    r1 = run_update(loop, "v1", range(48), champion=False)
    assert r1.accepted
    loop.start_session("d2")
    r2 = run_update(loop, "v2", range(100, 160), bad=20, trained_on=range(48))  # worse than the champion
    assert not r2.accepted and loop.version == "v1"
    loop.check_null_controls(uniform=quiet_nulls(), shuffled=quiet_nulls())  # champion re-check (rollback)
    r3 = loop.finish_update()
    assert r3.accepted and r3.version == "v1"
    st = updates(led)
    assert [s for s, _ in st] == ["proposed", "accepted", "proposed", "rejected", "proposed", "accepted"]
    ents = [e for e in led.entries if e["kind"] == "update"]
    assert ents[4]["body"]["details"]["origin"] == "rollback"
    # decisions link to their proposal; the config chain follows the loop
    assert ents[1]["body"]["proposal_hash"] == ents[0]["hash"]
    assert ents[1]["body"]["config_id"] == r1.config_id and ents[1]["body"]["parent_config_id"] is None
    assert ents[3]["body"]["config_id"] == ents[3]["body"]["parent_config_id"] == r1.config_id
    assert ents[5]["body"]["parent_config_id"] == r1.config_id and ents[5]["body"]["config_id"] == loop.config_id
    assert "worse than champion" in ents[3]["body"]["details"]["reasons"][0]
    # privacy: session and version are hashed (default id_mode), trained-on ids only as count + hash
    assert ents[2]["body"]["details"]["session"].startswith("h:")
    assert ents[2]["body"]["details"]["n_trained_on"] == 48 and "trained_on" not in ents[2]["body"]["details"]
    # append-only file, verified chain
    res = verify(path)
    assert res.ok, res.errors
    assert len(read_entries(path)) == len(led.entries)


def test_verify_detects_edits_of_update_entries(tmp_path):
    led = ProvenanceLedger()
    loop = GuardedUpdateLoop(lam_init=0.0, ledger=led)
    loop.start_session(1)
    run_update(loop, "v1", range(48), champion=False)
    ents = json.loads(json.dumps(led.entries))
    assert verify(ents).ok
    ents[-1]["body"]["stage"] = "rejected"  # edited decision
    assert not verify(ents).ok
    # a decision without its proposal, rebuilt with valid hashes, still fails the update rules
    from fidetype.trust.provenance import entry_hash

    ents = json.loads(json.dumps(led.entries))
    del ents[-2]
    prev = ents[-2]["hash"]
    for i in range(len(ents)):
        ents[i]["seq"] = i
    ents[-1]["prev_hash"] = prev
    ents[-1]["hash"] = entry_hash({k: v for k, v in ents[-1].items() if k != "hash"})
    res = verify(ents)
    assert not res.ok and any("unknown or later proposal" in e for e in res.errors)


def test_record_update_enforces_the_config_chain():
    led = ProvenanceLedger()
    led.record_update("proposed", "u0", chain="c")
    with pytest.raises(ValueError, match="new config_id"):
        led.record_update("accepted", "u0", chain="c", parent_config_id=None, config_id=None)
    with pytest.raises(ValueError, match="chain head"):
        led.record_update("accepted", "u0", chain="c", parent_config_id="x", config_id="y")
    led.record_update("accepted", "u0", chain="c", parent_config_id=None, config_id="cfg-1")
    assert led.chain_head("c") == "cfg-1"
    with pytest.raises(ValueError, match="already decided"):
        led.record_update("rejected", "u0", chain="c", parent_config_id="cfg-1", config_id="cfg-1")
    led.record_update("proposed", "u1", chain="c")
    with pytest.raises(ValueError, match="keep the config_id"):
        led.record_update("rejected", "u1", chain="c", parent_config_id="cfg-1", config_id="cfg-2")
    with pytest.raises(ValueError, match="no proposal"):
        led.record_update("accepted", "u9", chain="c", parent_config_id="cfg-1", config_id="cfg-2")
    with pytest.raises(ValueError, match="already proposed"):
        led.record_update("proposed", "u1", chain="c")
    with pytest.raises(ValueError, match="stage"):
        led.record_update("maybe", "u2", chain="c")
    assert verify(led.entries).ok


def test_loop_continues_the_chain_of_an_existing_ledger_file(tmp_path):
    path = tmp_path / "u.jsonl"
    loop = GuardedUpdateLoop(lam_init=0.0, ledger=ProvenanceLedger(path))
    loop.start_session(1)
    run_update(loop, "v1", range(48), champion=False)
    cid = loop.config_id
    loop2 = GuardedUpdateLoop(lam_init=0.0, ledger=ProvenanceLedger(path))
    assert loop2.config_id == cid
    loop2.start_session(2)
    loop2.set_champion("v1", trained_on=range(48))
    assert run_update(loop2, "v2", range(100, 148), trained_on=range(48)).accepted
    assert verify(path).ok


def test_superseded_proposal_and_reject_proposal_are_recorded():
    led = ProvenanceLedger()
    loop = GuardedUpdateLoop(lam_init=0.0, ledger=led)
    loop.start_session(1)
    loop.new_version("v1")
    loop.new_version("v1b")  # v1 never decided
    rec = loop.reject_proposal("calibration failed")
    assert not rec.accepted and rec.reasons == ("calibration failed",) and not loop.can_commit
    assert [s for s, _ in updates(led)] == ["proposed", "rejected", "proposed", "rejected"]
    assert verify(led.entries).ok
    with pytest.raises(ValueError):
        loop.reject_proposal("")


def test_listener_runs_once_per_decision_and_its_output_goes_to_the_ledger():
    led = ProvenanceLedger()
    loop = GuardedUpdateLoop(lam_init=0.0, ledger=led)
    seen = []

    def hook(rec, lp):
        seen.append((rec.version, rec.accepted))
        return {"saw": str(rec.version)}

    loop.add_listener(hook)
    loop.start_session(1)
    run_update(loop, "v1", range(48), champion=False)
    assert seen == [("v1", True)]
    last = [e for e in led.entries if e["kind"] == "update"][-1]
    assert last["body"]["details"]["hooks"] == {"hook0": {"saw": "v1"}}


def test_listener_error_is_recorded_then_raised():
    led = ProvenanceLedger()
    loop = GuardedUpdateLoop(lam_init=0.0, ledger=led)

    def boom(rec, lp):
        raise RuntimeError("swap failed")

    loop.add_listener(boom)
    loop.start_session(1)
    with pytest.raises(RuntimeError, match="swap failed"):
        run_update(loop, "v1", range(48), champion=False)
    last = [e for e in led.entries if e["kind"] == "update"][-1]
    assert "swap failed" in last["body"]["details"]["hook_error"] and verify(led.entries).ok


def test_loop_without_ledger_is_unchanged():
    loop = GuardedUpdateLoop(lam_init=0.0)
    loop.start_session(1)
    assert run_update(loop, "v1", range(48), champion=False).accepted and loop.ledger is None


# --- OnlineTrustPolicy hook ------------------------------------------------------------


def _inputs(p: float, risk: float = 0.1) -> PolicyInputs:
    return PolicyInputs(texts=("a b", "a c"), p_top1=p, set_indices=(0, 1), guard_risk=risk)


def test_online_policy_swaps_only_on_accepted_updates():
    pol1 = DecisionPolicy(PolicyConfig(commit_p=0.5, commit_max_risk=0.3, offer_max_k=3))
    pol2 = DecisionPolicy(PolicyConfig(commit_p=0.5, commit_max_risk=0.05, offer_max_k=3))
    op = OnlineTrustPolicy(pol1, OnlineCommitRiskControl(alpha=0.05, method="aci", lam_init=0.0))
    assert op.commit_floor == -math.inf  # backward compatible default
    loop = GuardedUpdateLoop(lam_init=0.0, ledger=ProvenanceLedger())
    OnlinePolicyUpdater(op, loop, {"v1": pol1, "v2": pol2})
    loop.start_session(1)
    assert run_update(loop, "v1", range(48), champion=False).accepted
    assert op.commit_floor == pytest.approx(loop.lambda_session) and op.policy is pol1
    thr_before = op.controller.threshold
    # rejected update (worse challenger): policy, floor and controller unchanged
    floor = op.commit_floor
    loop.start_session(2)
    assert not run_update(loop, "v2", range(100, 160), bad=20, trained_on=range(48)).accepted
    assert op.policy is pol1 and op.commit_floor == floor and op.controller.threshold == thr_before
    # accepted update: the new policy is live; the ACI controller keeps its state
    loop.start_session(3)
    loop.set_champion("v1", trained_on=range(48))
    assert run_update(loop, "v2", range(200, 248), trained_on=range(48)).accepted
    assert op.policy is pol2 and op.controller is not None and len(op.policy_history) == 2
    d, tk = op.decide(_inputs(0.95, risk=0.1))  # pol2 needs guard risk <= 0.05
    assert d.action != Action.COMMIT
    hooks = [e["body"]["details"]["hooks"] for e in loop.ledger.entries
             if e["kind"] == "update" and e["body"]["stage"] != "proposed"]
    assert [h["online_policy"]["policy_swapped"] for h in hooks] == [True, False, True]


def test_commit_floor_only_removes_commits():
    pol = DecisionPolicy(PolicyConfig(commit_p=0.5, commit_max_risk=0.3, offer_max_k=3))
    op = OnlineTrustPolicy(pol, OnlineCommitRiskControl(alpha=0.05, method="aci", lam_init=0.0))
    assert op.decide(_inputs(0.8))[0].action == Action.COMMIT
    op.swap_policy(pol, commit_floor=0.9)
    d, tk = op.decide(_inputs(0.8))
    assert d.action != Action.COMMIT and tk.score == -math.inf
    assert op.decide(_inputs(0.95))[0].action == Action.COMMIT
    with pytest.raises(ValueError):
        op.swap_policy(pol, commit_floor=math.nan)


# --- TrustGuard hook ------------------------------------------------------------------


@pytest.fixture(scope="module")
def guard_v1() -> ft.TrustGuard:
    xs, ts = nbest_data(300, 0)
    rng = np.random.default_rng(1)
    return ft.calibrate(xs, ts, null_inputs=[noise_nbest(rng) for _ in range(60)], null_trials=60,
                        decoder_name="test-nbest", decoder_version="1")


@functools.lru_cache(maxsize=None)
def _fresh_guard(seed: int, version: str) -> ft.TrustGuard:
    xs, ts = nbest_data(300, seed)
    rng = np.random.default_rng(seed + 1)
    return ft.calibrate(xs, ts, null_inputs=[noise_nbest(rng) for _ in range(60)], null_trials=60,
                        decoder_name="test-nbest", decoder_version=version)


def _copy_guard(g: ft.TrustGuard) -> ft.TrustGuard:
    from fidetype.trust.dropin import TrustGuard

    return TrustGuard(g.config, g._codec, g.sheet, None, g.audit_text)


def test_accepted_update_swaps_the_guard_config_in_place():
    live = _copy_guard(_fresh_guard(0, "1"))
    led = ProvenanceLedger()
    up = TrustGuardUpdater(live, GuardedUpdateLoop(alpha=live.alpha, delta=live.delta, ledger=led), null_trials=60)
    cx, ct = nbest_data(120, 50)
    before = live.config_id
    live.decide(cx[0])
    nrng = np.random.default_rng(2)
    out = up.propose(_fresh_guard(7, "2"), cx, ct, version="v2", check_ids=[("c", i) for i in range(120)],
                     trained_on=[("cal", i) for i in range(300)], null_inputs=[noise_nbest(nrng) for _ in range(60)])
    assert out.accepted, out.reasons
    assert live.config_id != before and out.config_id_after == live.config_id
    # the live object keeps its audit log; a config_update record marks the change
    assert live.audit_log[-1]["type"] == "config_update" and live.audit_log[-1]["from_config_id"] == before
    r = live.decide(cx[1])
    assert r.config_id == live.config_id and r.seq == 1
    # commit_p >= the loop's session threshold (only removes commits)
    assert float(live.config.policy["commit_p"]) >= up.loop.lambda_session - 1e-12
    if live.sheet is not None:
        assert live.sheet.config_id == live.config_id
    st = [e["body"] for e in led.entries if e["kind"] == "update"]
    assert [b["stage"] for b in st] == ["proposed", "accepted"]
    h = st[1]["details"]["hooks"]["trust_guard"]
    assert h["guard_swapped"] and h["guard_config_before"] == before and h["guard_config_after"] == live.config_id
    assert verify(led.entries).ok


def test_worse_candidate_is_rejected_and_the_guard_is_unchanged(guard_v1):
    live = _copy_guard(guard_v1)
    up = TrustGuardUpdater(live, GuardedUpdateLoop(alpha=live.alpha, delta=live.delta, ledger=ProvenanceLedger()),
                           null_trials=40)
    cx, ct = nbest_data(120, 60)
    rng = np.random.default_rng(5)
    # the challenger decoder: confident but wrong top-1 on 40 items where the champion is right
    bad_x = []
    for i, (x, t) in enumerate(zip(cx, ct)):
        if i < 40:
            others = [p for p in PHRASES if p != t]
            bad_x.append([(str(rng.choice(others)), 0.0), (t, -8.0)])
        else:
            bad_x.append(x)
    cfg, sheet_before, log_len = live.config, live.sheet, len(live.audit_log)
    out = up.propose(_fresh_guard(11, "2"), bad_x, ct, champion_inputs=cx, version="v2-bad",
                     null_inputs=[noise_nbest(rng) for _ in range(40)])
    assert not out.accepted and any("worse than champion" in r for r in out.reasons)
    assert live.config is cfg and live.sheet is sheet_before and len(live.audit_log) == log_len
    assert out.config_id_after == out.config_id_before == live.config_id


def test_candidate_that_fails_the_null_controls_is_rejected(guard_v1):
    live = _copy_guard(guard_v1)
    up = TrustGuardUpdater(live, GuardedUpdateLoop(alpha=live.alpha, delta=live.delta, ledger=ProvenanceLedger()),
                           null_trials=40)
    cx, ct = nbest_data(120, 70)
    rng = np.random.default_rng(9)
    # the decoder's output on null input: confident sentences (an LM that writes without evidence)
    nulls = [[(str(p), 0.0), ("x", -30.0)] for p in rng.choice(PHRASES, size=40)]
    cfg = live.config
    out = up.propose(_fresh_guard(13, "2"), cx, ct, version="v2-null", null_inputs=nulls)
    if up.loop.lambda_session == math.inf:
        pytest.skip("check block infeasible: no commits to test")
    assert not out.accepted and any("null controls failed" in r for r in out.reasons)
    assert live.config is cfg


def test_failed_calibration_is_a_recorded_rejection(guard_v1):
    live = _copy_guard(guard_v1)
    led = ProvenanceLedger()
    up = TrustGuardUpdater(live, GuardedUpdateLoop(alpha=live.alpha, delta=live.delta, ledger=led), null_trials=40)
    cx, ct = nbest_data(60, 80)
    cfg = live.config
    rng = np.random.default_rng(3)
    # calibration refuses: the new decoder commits on null input (NullControlError)
    bad_nulls = [[(str(p), 0.0), ("x", -30.0)] for p in rng.choice(PHRASES, size=60)]
    xs, ts = nbest_data(300, 90)
    out = up.propose_calibration(xs, ts, cx, ct, version="v2", null_inputs=bad_nulls, null_trials=60)
    assert not out.accepted and "calibration refused" in out.reasons[0]
    assert live.config is cfg
    assert [e["body"]["stage"] for e in led.entries if e["kind"] == "update"] == ["proposed", "rejected"]
    assert verify(led.entries).ok


def test_nbest_update_needs_null_inputs(guard_v1):
    up = TrustGuardUpdater(_copy_guard(guard_v1), null_trials=10)
    cx, ct = nbest_data(60, 2)
    with pytest.raises(ValueError, match="null_inputs"):
        up.propose(_fresh_guard(11, "2"), cx, ct, version="v2")


def test_propose_input_checks(guard_v1):
    live = _copy_guard(guard_v1)
    up = TrustGuardUpdater(live, null_trials=10)
    cx, ct = nbest_data(10, 1)
    with pytest.raises(ValueError, match="needs >="):
        up.propose(_copy_guard(guard_v1), cx, ct, version="x")
    with pytest.raises(TypeError):
        up.propose("not a guard", cx, ct)
    with pytest.raises(ValueError, match="live champion"):
        cx, ct = nbest_data(60, 1)
        up.propose(_copy_guard(guard_v1), cx, ct)  # same config_id as the live guard


def test_swap_guard_with_logits_input():
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(120)]
    xs = [fake_logits(t, rng) for t in ts]
    g1 = ft.calibrate(xs, ts, vocab=VOCAB, blank="_", lexicon=LEXICON, null_trials=20, decoder_name="t", seed=0)
    g2 = ft.calibrate(xs, ts, vocab=VOCAB, blank="_", lexicon=LEXICON, null_trials=20, decoder_name="t", seed=1)
    live = _copy_guard(g1)
    live._user_decode = None
    swap_guard(live, g2, note={"why": "test"})
    assert live.config_id == g2.config_id and live.audit_log[-1]["why"] == "test"
    a, b = live.decide(xs[0]), g2.decide(xs[0])
    assert (a.action, a.text, a.p_top1) == (b.action, b.text, b.p_top1)
    with pytest.raises(ValueError, match="input kind"):
        swap_guard(live, _fresh_guard(0, "1"))
