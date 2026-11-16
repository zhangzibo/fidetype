"""Tests of the drop-in trust wrapper (fidetype.trust.dropin, P14-03)."""

from __future__ import annotations

import json
import string
from pathlib import Path

import numpy as np
import pytest

import fidetype
import fidetype.trust as ft
from fidetype.trust import dropin as D

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


def fake_nbest(text: str, rng: np.random.Generator) -> list[tuple[str, float]]:
    noise = rng.uniform(0.0, 1.0)
    others = [p for p in PHRASES if p != text]
    cands = [text] + [str(p) for p in rng.choice(others, size=3, replace=False)]
    gap = 6.0 * (1.0 - noise)
    scores = [0.0] + [float(-gap * rng.uniform(0.5, 1.5)) for _ in range(3)]
    if rng.random() < 0.3 * noise:
        scores[1] = 0.5
    order = np.argsort(scores)[::-1]
    return [(cands[i], scores[i]) for i in order]


def noise_nbest(rng: np.random.Generator) -> list[tuple[str, float]]:
    return [(str(p), float(-rng.uniform(0.0, 0.5))) for p in rng.choice(PHRASES, size=4, replace=False)]


def nbest_data(n: int, seed: int) -> tuple[list, list[str]]:
    rng = np.random.default_rng(seed)
    texts = [str(rng.choice(PHRASES)) for _ in range(n)]
    return [fake_nbest(t, rng) for t in texts], texts


@pytest.fixture(scope="module")
def nbest_guard() -> ft.TrustGuard:
    xs, ts = nbest_data(300, 0)
    rng = np.random.default_rng(1)
    return ft.calibrate(xs, ts, null_inputs=[noise_nbest(rng) for _ in range(60)], null_trials=60,
                        decoder_name="test-nbest", modality="emg")


@pytest.fixture(scope="module")
def logits_guard() -> ft.TrustGuard:
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(200)]
    return ft.calibrate([fake_logits(t, rng) for t in ts], ts, vocab=VOCAB, blank="_", lexicon=LEXICON,
                        null_trials=40, decoder_name="test-ctc")


# --- public API shape ----------------------------------------------------------------------


def test_public_names_are_lazy_exports():
    for name in ("calibrate", "wrap", "load", "TrustGuard", "TrustResult", "GuaranteeSheet", "ControlResult",
                 "NullControlError"):
        assert getattr(ft, name) is getattr(D, name)
        assert name in ft.__all__


# --- n-best route --------------------------------------------------------------------------


def test_nbest_guard_sheet_and_decisions(nbest_guard: ft.TrustGuard):
    g = nbest_guard
    assert g.input_kind == "nbest"
    s = g.sheet
    assert s is not None and s.config_id == g.config_id == g.config.config_id
    assert (s.alpha, s.delta) == (0.05, 0.1)
    assert s.n_items == 300 and s.n_fit + s.n_policy + s.n_ltt == 300
    assert s.commit_gate == D.COMMIT_GATE == g.config.commit_gate
    assert {c.name for c in s.controls} == {"uniform", "shuffled"}
    assert all(c.passed for c in s.controls)
    text = str(s)
    assert "P( wrong-commit rate <= 0.05 ) >= 0.9" in text and "Exchangeable" in text
    json.dumps(s.to_dict(), allow_nan=False)
    xs, ts = nbest_data(200, 7)
    rs = g.decide_many(xs)
    assert {r.action for r in rs} <= {"commit", "offer", "withhold"}
    assert any(r.action == "commit" for r in rs)
    for r in rs:
        assert (r.text is not None) == (r.action == "commit")
        assert r.event["type"] == "trust_decision" and r.event["config_id"] == g.config_id
    wrong = sum(r.action == "commit" and r.text != t for r, t in zip(rs, ts))
    assert wrong / len(rs) <= 0.05 + 0.03  # one held-out draw; the bound is alpha with prob >= 1 - delta


def test_nbest_needs_null_inputs():
    xs, ts = nbest_data(60, 0)
    with pytest.raises(ValueError, match="null_inputs"):
        ft.calibrate(xs, ts)


def test_null_control_refusal_nbest():
    xs, ts = nbest_data(300, 0)
    # "Null" lists that are as confident as real ones: the guard commits on them -> refuse.
    with pytest.raises(ft.NullControlError, match="calibration refused") as ei:
        ft.calibrate(xs, ts, null_inputs=xs[:60], null_trials=40)
    rep = {c.name: c for c in ei.value.report}
    assert not rep["shuffled"].passed and rep["shuffled"].n_commit > rep["shuffled"].allowed
    assert rep["uniform"].passed


def test_null_control_rate_zero_is_strict():
    xs, ts = nbest_data(300, 0)
    rng = np.random.default_rng(5)
    nulls = [noise_nbest(rng) for _ in range(40)] + [xs[0]] * 3  # 3 confident lists among the nulls
    g = ft.calibrate(xs, ts, null_inputs=nulls, null_trials=20, null_max_commit_rate=0.1)
    assert g.sheet.null_max_commit_rate == 0.1
    with pytest.raises(ft.NullControlError):
        ft.calibrate(xs, ts, null_inputs=nulls, null_trials=20, null_max_commit_rate=0.0)


def test_audit_log_and_save_load(nbest_guard: ft.TrustGuard, tmp_path: Path):
    g = D.load(nbest_guard.save(tmp_path / "guard.json"))
    assert g.config_id == nbest_guard.config_id and g.sheet == nbest_guard.sheet
    saved = json.loads((tmp_path / "guard.json").read_text(encoding="utf-8"))
    assert saved["schema"] == D.GUARD_SCHEMA
    xs, _ = nbest_data(20, 9)
    a = [g.decide(x, utterance_id=f"u{i}") for i, x in enumerate(xs)]
    b = [nbest_guard._decide_quiet(x) for x in xs]
    assert [(r.action, r.choices) for r in a] == [(r.action, r.choices) for r in b]
    p = g.write_audit(tmp_path / "audit.jsonl")
    lines = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["type"] == "audit_header" and lines[0]["config_id"] == g.config_id
    assert lines[0]["guarantee"]["alpha"] == 0.05
    recs = lines[1:]
    assert len(recs) == 20 and [r["seq"] for r in recs] == list(range(20))
    for r, res in zip(recs, a):
        assert r["type"] == "trust_decision" and r["user_action"] == res.action
        assert r["action"] == res.raw_action and len(r["input_sha256"]) == 64
        assert r["shown"] == list(res.choices)
    assert recs[3]["utterance_id"] == "u3"
    quiet = D.load(tmp_path / "guard.json", audit_text=False)
    quiet.decide(xs[0])
    assert "shown" not in quiet.audit_log[0]


def test_wrap_equals_calibrate(nbest_guard: ft.TrustGuard):
    xs, ts = nbest_data(300, 0)
    rng = np.random.default_rng(1)
    nulls = [noise_nbest(rng) for _ in range(60)]
    g = ft.wrap(zip(xs, ts), null_inputs=nulls, null_trials=60, decoder_name="test-nbest", modality="emg")
    assert g.config_id == nbest_guard.config_id


def test_nts_events_are_valid_nts(nbest_guard: ft.TrustGuard, logits_guard: ft.TrustGuard, tmp_path: Path):
    xs, _ = nbest_data(1, 4)
    rng = np.random.default_rng(4)
    for name, g, x in (("nbest", nbest_guard, xs[0]), ("logits", logits_guard, fake_logits("thank you", rng))):
        ev = g.nts_events(x)
        assert ev[0]["type"] == "header" and ev[-1]["type"] == "end"
        p = tmp_path / f"{name}.jsonl"
        p.write_text("".join(json.dumps(e) + "\n" for e in ev), encoding="utf-8")
        rep = fidetype.validate(p)
        assert rep.passes("core"), rep.failures()


# --- logits route --------------------------------------------------------------------------


def test_logits_guard_with_lexicon(logits_guard: ft.TrustGuard, tmp_path: Path):
    g = logits_guard
    assert g.input_kind == "logits" and "lexicon" in g.sheet.decoder
    assert all(c.passed for c in g.sheet.controls)
    rng = np.random.default_rng(11)
    ts = [str(rng.choice(PHRASES)) for _ in range(60)]
    rs = [g(fake_logits(t, rng)) for t in ts]
    assert any(r.action == "commit" for r in rs)
    assert all(r.text in PHRASES for r in rs if r.action == "commit")
    g2 = ft.load(g.save(tmp_path / "g.json"))
    x = fake_logits("good morning", rng)
    assert g2._decide_quiet(x).choices == g._decide_quiet(x).choices


def test_null_control_refusal_logits_without_lexicon():
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(200)]
    xs = [fake_logits(t, rng) for t in ts]
    # The built-in decoder has no LM and no lexicon: shuffled frames keep their confidence.
    with pytest.raises(ft.NullControlError, match="lexicon=") as ei:
        ft.calibrate(xs, ts, vocab=VOCAB, blank="_", null_trials=40, null_max_commit_rate=0.0)
    assert any(c.name == "shuffled" and not c.passed for c in ei.value.report)


def test_custom_decode_fn_and_load_requires_it(tmp_path: Path):
    rng = np.random.default_rng(6)
    ts = [str(rng.choice(PHRASES)) for _ in range(160)]
    xs = [fake_logits(t, rng) for t in ts]

    def phrase_decoder(log_probs: np.ndarray) -> list[tuple[str, float]]:
        # "Your" decoder: a CTC beam search, then a word-list filter; returns (text, log score) pairs.
        from fidetype.lm.beam import ctc_prefix_beam_search

        hyps = ctc_prefix_beam_search(log_probs, beam=32, n_best=32, prune_topk=None, blank_id=0)
        return [(h.text, h.score) for h in hyps if h.text and all(w in LEXICON for w in h.text.split())][:8]

    g = ft.calibrate(xs, ts, vocab=VOCAB, blank="_", decode_fn=phrase_decoder, null_trials=30)
    assert g.sheet.decoder.startswith("custom:")
    path = g.save(tmp_path / "g.json")
    with pytest.raises(ValueError, match="decode_fn"):
        ft.load(path)
    assert ft.load(path, decode_fn=phrase_decoder).config_id == g.config_id


def _shift(text: str, k: int) -> str:
    """A letter cipher: the "token space" of a decoder whose tokens are not the letters of the texts."""
    a = string.ascii_lowercase
    return "".join(a[(a.index(c) + k) % 26] if c in a else c for c in text)


def test_stream_texts_fit_the_frame_temperature_in_the_token_space():
    # The decoder emits tokens in another space than the texts (like phonemes vs words). The frame
    # temperature must not be fitted against the word texts (P14-03 replay validation, 2026-11-16).
    from fidetype.adapters.ctc_logits import vocab_from_list
    from fidetype.streams.spec import NeuralTextStream
    from fidetype.trust.calibration import fit_frame_temperature

    rng = np.random.default_rng(8)
    ts = [str(rng.choice(PHRASES)) for _ in range(160)]
    tok = [_shift(t, 1) for t in ts]
    xs = [fake_logits(t, rng) for t in tok]

    def decoder(log_probs: np.ndarray) -> list[tuple[str, float]]:
        from fidetype.lm.beam import ctc_prefix_beam_search

        hyps = ctc_prefix_beam_search(log_probs, beam=32, n_best=32, prune_topk=None, blank_id=0)
        out = [(_shift(h.text, -1), h.score) for h in hyps]
        return [(t, s) for t, s in out if t and all(w in LEXICON for w in t.split())][:8]

    plain = ft.calibrate(xs, ts, vocab=VOCAB, blank="_", decode_fn=decoder, null_trials=30)
    assert plain.config.frame_temperature == 1.0
    assert any("frame temperature not fitted" in w for w in plain.sheet.warnings)
    assert plain.config.recipe["frame_temperature"] == "not fitted (1.0)"

    g = ft.calibrate(xs, ts, vocab=VOCAB, blank="_", decode_fn=decoder, stream_texts=tok, null_trials=30)
    assert not any("frame temperature not fitted" in w for w in g.sheet.warnings)
    assert g.config.recipe["frame_temperature"] == "fitted on stream_texts"
    # Same value as a direct fit on the token-space truth; the old behaviour (word texts) is far off.
    cv = vocab_from_list(VOCAB, "_")
    from fidetype.adapters.ctc_logits import to_log_probs

    sts = [NeuralTextStream(log_probs=to_log_probs(x, "auto").astype(np.float32), frame_times=np.arange(len(x)) * 0.02,
                            vocab=list(cv.tokens), blank_id=0) for x in xs]
    order = np.random.default_rng(0).permutation(len(xs))
    n_fit = D._split(len(xs))[0]
    fit_idx = order[:n_fit][: n_fit - int(round(n_fit * 0.5))]  # temperature items of the fit part
    right = fit_frame_temperature([sts[i] for i in fit_idx], [tok[i] for i in fit_idx]).temperature
    wrong = fit_frame_temperature([sts[i] for i in fit_idx], [ts[i] for i in fit_idx]).temperature
    assert g.config.frame_temperature == pytest.approx(right, rel=1e-6)
    assert abs(wrong - right) > 0.5
    # A list of tokens works the same as a string of one-character tokens.
    g2 = ft.calibrate(xs, ts, vocab=VOCAB, blank="_", decode_fn=decoder, stream_texts=[list(t) for t in tok],
                      null_trials=30)
    assert g2.config.frame_temperature == pytest.approx(g.config.frame_temperature)
    with pytest.raises(ValueError, match="same length"):
        ft.calibrate(xs, ts, vocab=VOCAB, blank="_", decode_fn=decoder, stream_texts=tok[:-1])


def test_sheet_flags_a_guard_that_the_commit_gate_blocks():
    # Quickstart timing run (2026-11-16): noisy data gave guard risk 1.00 everywhere, so the commit gate
    # blocked every commit while all sheet checks looked fine. The sheet must say so.
    rng = np.random.default_rng(3)
    ts = [str(rng.choice(PHRASES)) for _ in range(200)]
    xs = [fake_logits(t, rng) for t in ts]
    g = ft.calibrate(xs, ts, vocab=VOCAB, blank="_", lexicon=LEXICON, null_trials=40,
                     guard_settings={"low_conf_threshold": 1.0})  # every character counts as "no evidence"
    assert g.config.guard["low_conf_threshold"] == 1.0
    assert g.sheet.ltt_median_guard_risk == pytest.approx(1.0)
    assert g.sheet.ltt_gate_blocked > 0 and g.sheet.ltt_commits == 0
    assert any("commit gate blocked" in w for w in g.sheet.warnings)
    assert "blocked by the commit gate" in str(g.sheet)
    r = g.decide(xs[0])
    assert r.action != "commit"
    if r.p_top1 >= g.sheet.commit_threshold:
        assert r.reason.startswith("commit blocked: low acoustic evidence (guard risk 1.00")
    # the sheet round-trips with the new field; an old sheet without it still loads
    d = g.sheet.to_dict()
    assert D.GuaranteeSheet.from_dict(d).ltt_median_guard_risk == pytest.approx(1.0)
    d.pop("ltt_median_guard_risk")
    assert np.isnan(D.GuaranteeSheet.from_dict(d).ltt_median_guard_risk)
    with pytest.raises(ValueError, match="unknown guard_settings"):
        ft.calibrate(xs, ts, vocab=VOCAB, blank="_", lexicon=LEXICON, guard_settings={"no_such_field": 1})


def test_healthy_guard_has_no_gate_warning(logits_guard):
    sh = logits_guard.sheet
    assert sh.ltt_commits > sh.ltt_gate_blocked
    assert not any("commit gate blocked" in w for w in sh.warnings)
    assert "utterances, not commits" in str(logits_guard.sheet)


def test_user_reason_texts():
    f = D._user_reason
    gated = f("commit gate: guard risk 1.00 >= 1.00; final attempt: low confidence", 1.0, 1.0, 0.3)
    assert gated == ("commit blocked: low acoustic evidence (guard risk 1.00; the commit gate needs < 1.00) "
                     "although p_top1 1.00; withhold")
    assert f("final attempt: low confidence", 0.12, 0.4, 0.3) == (
        "withhold: p_top1 0.12 < commit threshold 0.30 and no small choice set")
    assert f("commit gate: empty text; final attempt: offer top-k", 0.9, 0.2, 0.3).startswith(
        "commit blocked by the commit gate (empty text); offer")
    assert f("p_top1 0.95 >= 0.30", 0.95, 0.1, 0.3) == "p_top1 0.95 >= 0.30"
    assert f("no candidate", 0.0, 1.0, 0.3) == "withhold: the decoder gave no text"


# --- input checks --------------------------------------------------------------------------


def test_input_checks():
    xs, ts = nbest_data(30, 0)
    with pytest.raises(ValueError, match="same length"):
        ft.calibrate(xs, ts[:-1], null_inputs=xs)
    with pytest.raises(ValueError, match="at least 20"):
        ft.calibrate(xs[:10], ts[:10], null_inputs=xs)
    with pytest.raises(TypeError, match="input kind"):
        ft.calibrate([object()] * 30, ts, null_inputs=xs)
    with pytest.raises(ValueError, match="vocab"):
        ft.calibrate([np.zeros((5, 4))] * 30, ts)
    with pytest.raises(ValueError, match="logits input only"):
        ft.calibrate(xs, ts, null_inputs=xs, lexicon=["a"])
    with pytest.raises(ValueError, match="modality"):
        ft.calibrate(xs, ts, null_inputs=xs, modality="telepathy")
    assert D._detect_kind(np.zeros((3, 4))) == "logits"
    assert D._detect_kind([[0.0, 1.0], [1.0, 0.0]]) == "logits"
    assert D._detect_kind([np.zeros(4), np.ones(4)]) == "logits"  # a list of frame rows
    assert D._detect_kind(["a", "b"]) == "nbest"
    assert D._detect_kind([("a", -1.0)]) == "nbest"
    assert D._detect_kind([{"text": "a", "score": 0.0}]) == "nbest"


def test_load_rejects_other_files(tmp_path: Path):
    p = tmp_path / "x.json"
    p.write_text('{"schema": "something-else"}', encoding="utf-8")
    with pytest.raises(ValueError, match="not a trust guard file"):
        ft.load(p)


def test_guard_needs_commit_gate(nbest_guard: ft.TrustGuard):
    from dataclasses import replace

    with pytest.raises(ValueError, match="commit gate"):
        D.TrustGuard(replace(nbest_guard.config, commit_gate={}), nbest_guard._codec)


def test_quickstart_example_runs():
    """The quickstart script runs (n-best route end to end; the logits route is the logits_guard fixture)."""
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "examples" / "trust_dropin_quickstart.py"
    spec = importlib.util.spec_from_file_location("trust_dropin_quickstart", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    rng = np.random.default_rng(0)
    x = mod.my_decoder_logits("thank you", rng)
    assert x.ndim == 2 and x.shape[1] == len(mod.VOCAB)
    nb = mod.my_decoder_nbest("thank you", rng)
    assert len(nb) == 4 and all(isinstance(t, str) for t, _ in nb)
    mod.run_nbest(None)  # the n-best route of the quickstart, end to end (a few seconds)
