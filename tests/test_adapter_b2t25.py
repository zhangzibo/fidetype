"""Tests for the Brain-to-Text '25 adapter and the phoneme -> word decoder."""

from __future__ import annotations

import io
import json
import os
import pickle
from pathlib import Path

import numpy as np
import pytest

from fidetype.adapters import b2t25 as b
from fidetype.eval.harness import Item
from fidetype.eval.metrics import ctc_greedy_decode
from fidetype.lm import ctc_prefix_beam_search
from fidetype.lm.phoneme_words import PhonemeWordDecoder, PronLexicon, edit_distance_str, unigram_logprobs
from fidetype.streams.spec import NeuralTextStream

REAL_PKL = Path(os.environ.get("B2T25_PKL", "C:/Users/zhang/bci-data/brain-to-text-25/t15_copyTask.pkl"))


def synthetic_logits(phonemes: list[str], frames_per_token: int = 3, gap: int = 2, peak: float = 8.0, seed: int = 0):
    """Unnormalised logits with one peak run per phoneme and blank gaps."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in phonemes:
        k = b.VOCAB.index(p)
        for _ in range(gap):
            r = rng.normal(0, 0.3, len(b.VOCAB))
            r[b.BLANK_ID] += peak
            rows.append(r)
        for _ in range(frames_per_token):
            r = rng.normal(0, 0.3, len(b.VOCAB))
            r[k] += peak
            rows.append(r)
    for _ in range(gap):
        r = rng.normal(0, 0.3, len(b.VOCAB))
        r[b.BLANK_ID] += peak
        rows.append(r)
    return np.array(rows, dtype=np.float32)


PH = ["K", "L", "IY", "N", "SIL", "DH", "AE", "T", "SIL", "AH", "P", "SIL"]


def synthetic_dict(n: int = 3) -> dict:
    seqs = [PH, ["Y", "UW", "SIL", "F", "IY", "L", "SIL"], ["AH", "P", "SIL"]][:n]
    sents = ["clean that up", "you feel", "up"][:n]
    return {
        "post_implant_day": [25] * n,
        "vocab_size": [50] * n,
        "cue_sentence": sents,
        "cue_sentence_phonemes": seqs,
        "decoded_logits": [synthetic_logits(s, seed=i) for i, s in enumerate(seqs)],
        "decoded_phonemes_raw": seqs,
        "decoded_sentence": sents,
        "decoded_sentence_phonemes": seqs,
        "speech_duration_s": [np.float64(1.5)] * n,
    }


# --- vocabulary ------------------------------------------------------------------


def test_vocab_shape_and_order():
    assert len(b.VOCAB) == 41 and len(b.SYMBOL_VOCAB) == 41
    assert b.VOCAB[:3] == ("<blank>", "SIL", "AA") and b.VOCAB[-1] == "ZH"
    assert len(set(b.SYMBOL_VOCAB)) == 41
    assert all(len(t) == 1 for t in b.SYMBOL_VOCAB[1:])


def test_symbols_round_trip():
    s = b.phonemes_to_symbols(PH)
    assert s.count(" ") == 2 and not s.endswith(" ")
    assert b.symbols_to_phonemes(s) == PH[:-1]  # the final SIL is stripped
    with pytest.raises(ValueError):
        b.phonemes_to_symbols(["XX"])


def test_normalize_words_keeps_apostrophe():
    assert b.normalize_words("That's  getting, back!") == "that's getting back"


# --- streams --------------------------------------------------------------------


def test_trial_stream_validates_and_fields():
    trials = b.trials_from_dict(synthetic_dict())
    s = b.trial_stream(trials[0])
    assert isinstance(s, NeuralTextStream)
    assert s.vocab_type == "phoneme" and s.blank_id == 0
    assert s.frame_period == pytest.approx(0.08) and s.latency == 0.0
    assert s.frame_times[0] == pytest.approx(14 * 0.02)
    assert np.allclose(np.diff(s.frame_times), 0.08)
    lse = np.log(np.exp(s.log_probs.astype(np.float64)).sum(1))
    assert np.abs(lse).max() < 1e-3
    assert s.meta["device.modality"] == "intracortical"
    assert s.meta["decoder.causal"] is True


def test_stream_has_no_ground_truth():
    t = b.trials_from_dict(synthetic_dict())[0]
    s = b.trial_stream(t)
    blob = json.dumps(s.meta)
    assert t.cue_sentence not in blob and t.decoded_sentence not in blob
    assert "K L IY" not in blob


def test_npz_round_trip(tmp_path):
    s = b.trial_stream(b.trials_from_dict(synthetic_dict())[0])
    p = tmp_path / "s.npz"
    s.to_npz(p)
    r = NeuralTextStream.from_npz(p)
    assert r.vocab == list(b.VOCAB) and r.vocab_type == "phoneme"
    assert r.frame_period == pytest.approx(0.08) and r.latency == 0.0
    assert np.array_equal(r.log_probs, s.log_probs) and np.array_equal(r.frame_times, s.frame_times)
    assert r.meta == s.meta


def test_symbol_stream_round_trip_and_greedy():
    t = b.trials_from_dict(synthetic_dict())[0]
    s = b.trial_stream(t)
    sym = b.to_symbol_stream(s)
    assert sym.vocab == list(b.SYMBOL_VOCAB) and np.array_equal(sym.log_probs, s.log_probs)
    back = b.from_symbol_stream(sym)
    assert back.vocab == s.vocab and back.meta["fidetype.vocab_id"] == b.VOCAB_ID
    assert " ".join(ctc_greedy_decode(sym).split()) == t.truth_symbols
    h = ctc_prefix_beam_search(sym, None, beam=8, n_best=3)
    assert " ".join(h[0].text.split()) == t.truth_symbols


def test_bad_logit_shape_rejected():
    d = synthetic_dict(1)
    d["decoded_logits"] = [np.zeros((5, 40), np.float32)]
    with pytest.raises(ValueError):
        b.trials_from_dict(d)


# --- safe pickle loading ------------------------------------------------------------


class _Evil:
    def __reduce__(self):
        return (os.system, ("echo pwned",))


def test_scan_accepts_numpy_dict_and_loads(tmp_path):
    p = tmp_path / "ok.pkl"
    p.write_bytes(pickle.dumps(synthetic_dict(), protocol=4))
    rep = b.scan_pickle(p.read_bytes())
    assert set(rep["imports"]) <= {f"{m}.{n}" for m, n in b.ALLOWED_GLOBALS}
    trials = b.trials_from_dict(b.safe_load(p))
    assert len(trials) == 3 and trials[0].cue_sentence == "clean that up"


def test_scan_rejects_os_system():
    data = pickle.dumps({"x": _Evil()}, protocol=4)  # dumps only, never loaded
    with pytest.raises(b.UnsafePickleError):
        b.scan_pickle(data)
    with pytest.raises(b.UnsafePickleError):
        b.RestrictedUnpickler(io.BytesIO(data)).load()


def test_safe_load_checks_sha(tmp_path):
    p = tmp_path / "ok.pkl"
    p.write_bytes(pickle.dumps({"a": 1}))
    with pytest.raises(ValueError, match="SHA-256"):
        b.safe_load(p, expected_sha256="0" * 64)


# --- phoneme -> words ------------------------------------------------------------


def tiny_lexicon() -> PronLexicon:
    words = {
        "clean": ["K", "L", "IY", "N"], "keen": ["K", "IY", "N"], "that": ["DH", "AE", "T"],
        "up": ["AH", "P"], "you": ["Y", "UW"], "feel": ["F", "IY", "L"], "fill": ["F", "IH", "L"],
    }
    return PronLexicon({w: [b.phonemes_to_symbols(p)] for w, p in words.items()})


def test_edit_distance_str():
    assert edit_distance_str("abc", "abc") == 0
    assert edit_distance_str("abc", "abd") == 1
    assert edit_distance_str("abcd", "a", max_d=1) == 2


def test_lexicon_fuzzy_candidates():
    lex = tiny_lexicon()
    seg = b.phonemes_to_symbols(["K", "L", "IY", "N"])
    assert lex.candidates(seg)[0] == ("clean", 0)
    seg2 = b.phonemes_to_symbols(["K", "L", "IH", "N"])  # one substitution
    assert ("clean", 1) in lex.candidates(seg2)


class _H:
    def __init__(self, text, lp):
        self.text, self.logp_acoustic = text, lp
        self.confidence_variants = {"frame": np.full(len(text), 0.9)}


def test_word_decoder_on_synthetic_hyps():
    lex = tiny_lexicon()
    uni = unigram_logprobs({"clean": 5, "that": 9, "up": 7}, lex.words)
    dec = PhonemeWordDecoder(lex, uni, sentence_lm=None, n_best=5)
    good = b.phonemes_to_symbols(PH)
    noisy = b.phonemes_to_symbols(["K", "L", "IH", "N", "SIL", "DH", "AE", "T", "SIL", "AH", "P"])
    out = dec.decode([_H(good, -1.0), _H(noisy, -3.0)])
    assert out[0].text == "clean that up" and out[0].edits == 0
    assert len(out[0].char_confidences) == len(out[0].text)
    assert len({h.text for h in out}) == len(out)


def test_word_decoder_lower_conf_for_edits():
    lex = tiny_lexicon()
    dec = PhonemeWordDecoder(lex, unigram_logprobs({}, lex.words), n_best=3)
    noisy = b.phonemes_to_symbols(["K", "L", "IH", "N"])
    out = dec.decode([_H(noisy, -1.0)])
    assert out[0].text == "clean" and out[0].edits == 1
    assert max(out[0].char_confidences) == pytest.approx(0.45)


# --- harness Item ------------------------------------------------------------------


def test_item_stream_text_default():
    s = b.to_symbol_stream(b.trial_stream(b.trials_from_dict(synthetic_dict())[0]))
    assert Item(s, "abc").stream_text == "abc"
    assert Item(s, "clean that up", stream_text="x y").stream_text == "x y"


# --- real data (skipped when the file is absent) ----------------------------------------


@pytest.mark.skipif(not REAL_PKL.exists(), reason="t15_copyTask.pkl not downloaded")
def test_real_copytask_loads_and_vocab_order():
    trials = b.load_copytask(REAL_PKL)
    assert len(trials) == 1718
    same = 0
    for t in trials:
        s = b.to_symbol_stream(b.trial_stream(t))
        same += " ".join(ctc_greedy_decode(s).split()) == b.phonemes_to_symbols(t.decoded_phonemes_raw)
    assert same >= 1700  # 1,709 on 2026-11-10
