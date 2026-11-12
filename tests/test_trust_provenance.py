"""Tests of the provenance ledger (M2-09)."""

import json

import numpy as np
import pytest

from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust.policy import Action, Decision, DecisionPolicy, PolicyConfig, PolicyInputs
from fidetype.trust.provenance import (
    GENESIS_PREV,
    LedgeredPolicy,
    LedgerView,
    ProvenanceLedger,
    audit_report,
    canonical_json,
    check_no_raw,
    entry_hash,
    main,
    read_entries,
    stream_fingerprint,
    verify,
)
from fidetype.trust.testing import RefCharLM, ReferenceDecoder

CTX = {
    "adapter": {"name": "test-adapter", "version": "1"},
    "decoder": {"name": "dec-a", "version": "1.0", "weights_sha256": "ab" * 32},
    "lm": {"name": "none"},
    "calibration": {"id": "cal-1", "temperature_frame": 1.5},
    "policy": {"version": "pol-1"},
}


def clock():
    clock.t += 1
    return f"2026-11-11T00:00:{clock.t:02d}.000000Z"


clock.t = 0


def inputs(texts=("hello world", "hello word"), p=0.9, risk=0.1):
    return PolicyInputs(texts=texts, p_top1=p, set_indices=(0,), guard_risk=risk)


def stream(seed=0):
    sim = NoisyDecoderSimulator(SimConfig.preset("median"), seed=seed)
    return sim.simulate("hello world", seed=seed).stream


def small_ledger(path=None, **kw):
    led = ProvenanceLedger(path, clock=clock, **kw)
    cid = led.record_context(CTX)
    d1 = led.record_decision(context_id=cid, decision=Decision(Action.COMMIT, ("hello word",), "p"),
                             inputs=inputs(("hello word", "hello world")), stream=stream(1), item_ref="s1")
    d2 = led.record_decision(context_id=cid, decision=Decision(Action.OFFER, ("a b", "a c"), "set"),
                             inputs=inputs(("a b", "a c"), p=0.4), stream=stream(2), item_ref="s2")
    led.record_correction(d1["body"]["decision_id"], "hello world", source="user")
    return led, d1, d2


# --- format and round trip --------------------------------------------------------


def test_canonical_json_is_stable_and_handles_nonfinite():
    a = canonical_json({"b": 1, "a": [1.0, float("inf"), np.float32(0.5)], "c": float("nan")})
    assert a == '{"a":[1.0,"inf",0.5],"b":1,"c":"nan"}'
    assert canonical_json({"x": "é"}) == '{"x":"é"}'


def test_round_trip_file(tmp_path):
    p = tmp_path / "ledger.jsonl"
    led, d1, _ = small_ledger(p)
    entries = read_entries(p)
    assert entries == led.entries
    assert [e["kind"] for e in entries] == ["genesis", "context", "decision", "decision", "correction"]
    assert entries[0]["prev_hash"] == GENESIS_PREV
    assert all(e["hash"] == entry_hash(e) for e in entries)
    r = verify(p)
    assert r.ok and r.n_entries == 5 and r.head_hash == entries[-1]["hash"]
    # Reopen and continue: the chain goes on.
    led2 = ProvenanceLedger(p, clock=clock)
    assert led2.ledger_id == led.ledger_id
    led2.note({"event": "session end"})
    assert verify(p).ok and len(read_entries(p)) == 6


def test_context_written_once():
    led = ProvenanceLedger(clock=clock)
    a = led.record_context(CTX)
    b = led.record_context(json.loads(json.dumps(CTX)))
    assert a == b
    assert sum(e["kind"] == "context" for e in led.entries) == 1
    c = led.record_context({**CTX, "decoder": {"name": "dec-a", "version": "1.1"}})
    assert c != a


def test_decision_without_context_is_refused():
    led = ProvenanceLedger(clock=clock)
    with pytest.raises(ValueError):
        led.record_decision(context_id="ctx-x", decision=Decision(Action.ASK))


# --- tamper detection ---------------------------------------------------------------


def write(p, entries):
    p.write_text("".join(canonical_json(e) + "\n" for e in entries), encoding="utf-8")


def test_detects_edit(tmp_path):
    p = tmp_path / "l.jsonl"
    led, _, _ = small_ledger(p)
    es = read_entries(p)
    es[2]["body"]["scores"]["p_top1"] = 0.99  # raise the score after the fact
    write(p, es)
    r = verify(p)
    assert not r.ok and any("entry 2: hash mismatch" in e for e in r.errors)


def test_detects_edit_with_recomputed_hash(tmp_path):
    # An editor recomputes the edited entry's hash: the next link breaks.
    p = tmp_path / "l.jsonl"
    small_ledger(p)
    es = read_entries(p)
    es[2]["body"]["action"] = "OFFER"
    es[2]["hash"] = entry_hash(es[2])
    write(p, es)
    r = verify(p)
    assert not r.ok and any("entry 3: prev_hash" in e for e in r.errors)


def test_detects_delete(tmp_path):
    p = tmp_path / "l.jsonl"
    small_ledger(p)
    es = read_entries(p)
    del es[3]
    write(p, es)
    r = verify(p)
    assert not r.ok and any("seq" in e for e in r.errors) and any("prev_hash" in e for e in r.errors)


def test_detects_reorder(tmp_path):
    p = tmp_path / "l.jsonl"
    small_ledger(p)
    es = read_entries(p)
    es[2], es[3] = es[3], es[2]
    write(p, es)
    assert not verify(p).ok


def test_detects_truncation_only_with_anchor(tmp_path):
    p = tmp_path / "l.jsonl"
    led, _, _ = small_ledger(p)
    anchor = led.anchor()
    es = read_entries(p)[:-1]
    write(p, es)
    assert verify(p).ok  # a cut at the end keeps a valid chain ...
    r = verify(p, expected_head=anchor)  # ... the external anchor catches it
    assert not r.ok and "head hash" in r.errors[0]


def test_detects_bad_reference_and_bad_json(tmp_path):
    led, d1, _ = small_ledger()
    es = [json.loads(json.dumps(e)) for e in led.entries]
    es[4]["body"]["decision_hash"] = "0" * 64
    es[4]["hash"] = entry_hash(es[4])
    assert any("decision_hash" in e for e in verify(es).errors)
    p = tmp_path / "bad.jsonl"
    p.write_text("{not json\n", encoding="utf-8")
    assert not verify(p).ok


def test_refuses_to_continue_a_tampered_file(tmp_path):
    p = tmp_path / "l.jsonl"
    small_ledger(p)
    es = read_entries(p)
    es[1]["body"]["context"]["decoder"]["version"] = "9"
    write(p, es)
    with pytest.raises(ValueError):
        ProvenanceLedger(p)


# --- corrections -------------------------------------------------------------------


def test_correction_links_to_decision():
    led, d1, d2 = small_ledger(text_mode="store")
    view = LedgerView(led)
    c = view.latest_correction(d1["body"]["decision_id"])["body"]
    assert c["decision_hash"] == d1["hash"]
    assert c["changed"] is True and c["char_edits"] == 1 and c["word_edits"] == 1
    assert c["relation"] == "correction"
    assert view.is_wrong_commit(d1["body"]["decision_id"])
    assert not view.is_wrong_commit(d2["body"]["decision_id"])
    wc = view.wrong_commits()
    assert len(wc) == 1 and wc[0]["context"]["decoder"]["name"] == "dec-a"
    with pytest.raises(ValueError):
        led.record_correction("dec-unknown", "x")


def test_confirmation_and_rejection():
    led = ProvenanceLedger(clock=clock, text_mode="omit")
    cid = led.record_context(CTX)
    d = led.record_decision(context_id=cid, decision=Decision(Action.COMMIT, ("ok",)), inputs=inputs(("ok",)))
    c = led.record_correction(d["body"]["decision_id"], "ok")
    assert c["body"]["changed"] is False and c["body"]["relation"] == "confirmation"
    r = led.record_correction(d["body"]["decision_id"], None)
    assert r["body"]["relation"] == "rejection" and r["body"]["changed"] is True
    assert LedgerView(led).is_wrong_commit(d["body"]["decision_id"])  # latest correction wins


def test_original_text_must_match_record():
    led = ProvenanceLedger(clock=clock, text_mode="hash")
    cid = led.record_context(CTX)
    d = led.record_decision(context_id=cid, decision=Decision(Action.COMMIT, ("abc",)), inputs=inputs(("abc",)))
    with pytest.raises(ValueError):
        led.record_correction(d["body"]["decision_id"], "abd", original_text="xyz")


# --- privacy ---------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["store", "hash", "omit"])
def test_text_modes(mode, tmp_path):
    p = tmp_path / "l.jsonl"
    led, d1, _ = small_ledger(p, text_mode=mode, id_mode=mode)
    raw = p.read_text(encoding="utf-8")
    top1 = d1["body"]["top1"]
    if mode == "store":
        assert "hello word" in raw and top1["text"] == "hello word"
    else:
        assert "hello" not in raw  # neither the decoded nor the corrected text
    if mode == "hash":
        assert len(top1["hash"]) == 64 and top1["n_chars"] == 10
    if mode == "omit":
        assert top1 == {"omitted": True}
    # The correction still knows that the text changed and by how much (session memory).
    c = LedgerView(led).latest_correction(d1["body"]["decision_id"])["body"]
    assert c["changed"] is True and c["char_edits"] == 1
    assert verify(p).ok


def test_keyed_hash_differs_and_is_required_to_reopen(tmp_path):
    a = ProvenanceLedger(clock=clock, text_mode="hash").text_record("yes")["hash"]
    led = ProvenanceLedger(tmp_path / "k.jsonl", clock=clock, text_mode="hash", hash_key=b"secret", key_id="k1")
    b = led.text_record("yes")["hash"]
    assert a != b and led.entries[0]["body"]["text_hash_alg"] == "hmac-sha256"
    with pytest.raises(ValueError):
        ProvenanceLedger(tmp_path / "k.jsonl")
    ProvenanceLedger(tmp_path / "k.jsonl", hash_key=b"secret")


def test_no_raw_signal_in_ledger():
    with pytest.raises(ValueError):
        check_no_raw({"x": np.zeros((100, 3))})
    with pytest.raises(ValueError):
        check_no_raw({"x": [0.1] * 200})
    check_no_raw({"frame_range": [0, 100], "names": ["a"] * 200})
    led = ProvenanceLedger(clock=clock)
    with pytest.raises(ValueError):
        led.note({"signal": list(range(1000))})


def test_stream_stored_as_hash_and_ids_pseudonymised():
    s = stream(3)
    s.meta.update({"subject.id": "sub-07", "session.id": "ses-1", "decoder.name": "dec-a", "notes": "free text"})
    led = ProvenanceLedger(clock=clock)
    cid = led.record_context({**CTX, "stream_meta": s.meta})
    ctx = led.entries[1]["body"]["context"]
    assert ctx["stream_meta"] == {"decoder.name": "dec-a"}  # ids and free text dropped
    d = led.record_decision(context_id=cid, decision=Decision(Action.ASK), inputs=inputs(), stream=s)
    inp = d["body"]["input"]
    assert inp["stream_id"] == stream_fingerprint(s) and inp["n_frames"] == s.n_frames
    assert inp["frame_range"] == [0, s.n_frames]
    assert inp["subject"].startswith("h:") and "sub-07" not in canonical_json(led.entries)
    assert "log_probs" not in canonical_json(led.entries)
    s2 = stream(3)
    s2.meta.update(s.meta)
    assert stream_fingerprint(s2) == stream_fingerprint(s)
    s2.log_probs[0, 0] += 0  # unchanged
    s3 = stream(4)
    assert stream_fingerprint(s3) != stream_fingerprint(s)


# --- policy hook, reports, CLI ------------------------------------------------------


def test_ledgered_policy_records_each_decision():
    led = ProvenanceLedger(clock=clock)
    pol = LedgeredPolicy(DecisionPolicy(PolicyConfig(commit_p=0.8)), led, led.record_context(CTX))
    d = pol.decide(inputs(p=0.95), stream=stream(5))
    assert d.action == Action.COMMIT and pol.last_entry["body"]["action"] == "COMMIT"
    pol.decide(inputs(p=0.2), final_attempt=True)
    assert sum(e["kind"] == "decision" for e in led.entries) == 2
    assert pol.config.commit_p == 0.8


def test_summary_and_report(tmp_path, capsys):
    p = tmp_path / "l.jsonl"
    led, _, _ = small_ledger(p, text_mode="store")
    cid2 = led.record_context({**CTX, "decoder": {"name": "dec-b", "version": "2"}})
    led.record_decision(context_id=cid2, decision=Decision(Action.COMMIT, ("x",)), inputs=inputs(("x",)))
    rows = {r["decoder.name"]: r for r in LedgerView(p).summary()}
    assert rows["dec-a"]["n_decisions"] == 2 and rows["dec-a"]["n_wrong_commits"] == 1
    assert rows["dec-a"]["wrong_commit_rate"] == 0.5 and rows["dec-a"]["commit_precision"] == 0.0
    assert rows["dec-b"]["n_wrong_commits"] == 0
    rep = audit_report(p)
    assert "PASS" in rep and "Wrong commits (1)" in rep and '"hello word"' in rep and '"hello world"' in rep
    assert main(["verify", str(p)]) == 0
    assert main(["report", str(p)]) == 0
    assert "Provenance audit report" in capsys.readouterr().out
    es = read_entries(p)
    es[2]["body"]["action"] = "ASK"
    write(p, es)
    assert main(["verify", str(p)]) == 1


# --- integration through the pipeline -----------------------------------------------

GRID = {"commit_p": (0.3, 0.6, 0.9), "commit_max_risk": (1.0,), "offer_max_k": (0, 3),
        "abstain_risk": (1.01,), "final_fallback": ("offer",)}


@pytest.fixture(scope="module")
def pipe_setup():
    sents = sentences(400, seed=3)
    lm = RefCharLM(4).fit(sents[100:])
    dec = ReferenceDecoder(lm, beam=6)
    sim = NoisyDecoderSimulator(SimConfig.preset("median"), seed=9)

    def item(i, s):
        it = Item(sim.simulate(s, seed=10 * i).stream, s, regen=lambda a: sim.simulate(s, seed=10 * i + a).stream)
        return it

    items = [item(i, s) for i, s in enumerate(sents[:60])]
    return dec, items[:20], items[20:40], items[40:]


@pytest.mark.parametrize("corrections", ["oracle", "user"])
def test_pipeline_writes_one_entry_per_decision(pipe_setup, tmp_path, corrections):
    dec, cal, val, test = pipe_setup
    cfg = HarnessConfig(grid=GRID, max_wrong_commit=0.3, risk_control="crc", risk_control_fraction=0.5)
    pipe = TrustPipeline(dec, cfg, {}).fit(cal, val)
    p = tmp_path / "ledger.jsonl"
    led = ProvenanceLedger(p, text_mode="store")
    pipe.attach_ledger(led, {"decoder": {"name": "ref-decoder", "version": "test"},
                             "calibration_set_id": "calib-items-0-20"}, corrections=corrections)
    m = pipe.evaluate(test)
    entries = read_entries(p)
    decisions = [e for e in entries if e["kind"] == "decision"]
    assert len(decisions) == sum(len(r.actions) - r.actions.count("REPEAT") for r in m["records"])
    assert [e["kind"] for e in entries[:2]] == ["genesis", "context"]  # fit wrote nothing
    assert verify(p).ok
    ctx = entries[1]["body"]["context"]
    assert ctx["calibration"]["risk_control"]["method"] == "crc"
    assert ctx["calibration"]["risk_control"]["alpha"] == 0.3
    assert ctx["calibration"]["calibration_set_id"] == "calib-items-0-20"
    assert ctx["calibration"]["temperature_frame"] == pytest.approx(m["fit_temperature_frame"])
    assert ctx["policy"]["config"]["commit_p"] == pytest.approx(pipe.policy.config.commit_p)
    view = LedgerView(p)
    n_wrong = sum(r.wrong_commit for r in m["records"] if r.committed_text is not None)
    n_silent = sum(r.wrong_commit and r.silent_error for r in m["records"] if r.committed_text is not None)
    if corrections == "oracle":
        assert len(view.wrong_commits()) == n_wrong
    else:
        assert len(view.wrong_commits()) == n_wrong - n_silent
    for w in view.wrong_commits():
        b = w["decision"]["body"]
        assert b["action"] == "COMMIT" and b["shown"][0]["text"] != w["corrections"][-1]["body"]["corrected"]["text"]
        assert w["context"]["decoder"]["name"] == "ref-decoder"
    rows = view.summary()
    assert len(rows) == 1 and rows[0]["n_decisions"] == len(decisions)


def test_evaluate_without_ledger_is_unchanged(pipe_setup):
    dec, cal, val, test = pipe_setup
    cfg = HarnessConfig(grid=GRID, max_wrong_commit=0.3)
    a = TrustPipeline(dec, cfg, {}).fit(cal, val).evaluate(test)
    pipe = TrustPipeline(dec, cfg, {}).fit(cal, val)
    b = pipe.evaluate(test, ledger=ProvenanceLedger())
    assert a["ewpm"] == b["ewpm"] and a["wrong_commit_rate"] == b["wrong_commit_rate"]
