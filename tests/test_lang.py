"""P14-34: per-language config (fidetype.lang). English must stay bit-identical."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype import lang
from fidetype.adapters.b2t25 import normalize_words
from fidetype.benchmark import safe_wpm as W
from fidetype.lm.llm import normalize_text as llm_normalize
from fidetype.streams import vocab as V

FIX = Path(__file__).parent / "fixtures" / "lang"


# --- English: pinned current behaviour ---------------------------------------------------------------------


def test_en_is_the_default_and_reuses_the_existing_objects():
    en = lang.get()
    assert en is lang.get("en") and en.tag == lang.DEFAULT_TAG == "en"
    assert en.vocab is V.VOCAB
    assert en.vocab == ("<blank>", *"abcdefghijklmnopqrstuvwxyz", " ") and len(en.vocab) == 28
    assert en.letters == V.LETTERS and en.vocab_id == "char.b2q-28"
    assert en.charset == frozenset("abcdefghijklmnopqrstuvwxyz ")
    assert (en.correction_chars_per_min, en.gaze_chars_per_min) == (152.0, 20.0)
    assert 2.0 * 60.0 / en.correction_chars_per_min == W.DEFAULT_S_PER_CHAR
    assert en.gaze_chars_per_min == W.GAZE_CHARS_PER_MIN


def test_en_normalisation_is_pinned():
    doc = json.loads((FIX / "normalize_en.json").read_text(encoding="utf-8"))
    en = lang.get("en")
    assert len(doc["cases"]) >= 20
    for c in doc["cases"]:
        t = c["text"]
        assert V.normalize_text(t) == c["char28_space"], t
        assert V.normalize_text(t, "drop") == c["char28_drop"], t
        assert en.normalize(t) == c["char28_space"], t
        assert en.normalize(t, "drop") == c["char28_drop"], t
        assert normalize_words(t) == c["words_b2t25"], t
        assert llm_normalize(t) == c["words_llm"], t
        assert en.encode(t) == V.encode(t)
        assert en.decode(en.encode(t)) == V.decode(V.encode(t))


def _fixture_trials():
    return [json.loads(x) for x in (FIX / "safe_wpm_en.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def test_en_safe_wpm_is_bit_identical_on_the_committed_fixture():
    exp = json.loads((FIX / "safe_wpm_en.expected.json").read_text(encoding="utf-8"))
    cols = W.load_trials_jsonl(str(FIX / "safe_wpm_en.jsonl"))
    assert cols["n_words"] == exp["n_words"] and cols["n_chars"] == exp["n_chars"]
    # the language hook gives the same counts as the safe-WPM reader
    wc = lang.wpm_counts([d["truth"] for d in _fixture_trials()], "en")
    assert wc["defined"] and [float(x) for x in wc["n_words"]] == exp["n_words"]
    assert [float(x) for x in wc["n_chars"]] == exp["n_chars"]
    for n_words, n_chars in ((cols["n_words"], cols["n_chars"]), (wc["n_words"], wc["n_chars"])):
        r = W.safe_wpm(cols["committed"], cols["correct"], n_words, n_chars, cols["neural_s"],
                       guarantee=exp["guarantee"], clusters=[{"session": x} for x in cols["cluster"]],
                       ci_unit=exp["ci_unit"], B=exp["B"], seed=exp["seed"], timing="measured")
        for k, v in exp["result"].items():
            assert r[k] == v, k  # exact equality, not approximate


# --- registry -------------------------------------------------------------------------------------------------


def test_registry_resolves_bcp47_tags():
    assert set(lang.available()) >= {"en", "es", "zh"}
    assert lang.get("en-US") is lang.get("EN") is lang.get(None) is lang.resolve(None)
    assert lang.get("es-419") is lang.get("es-ES") is lang.get("es")
    assert lang.get("zh-Hans-CN") is lang.get("zh")
    assert lang.resolve(lang.get("es")) is lang.get("es")
    with pytest.raises(KeyError, match="registered"):
        lang.get("fr")
    with pytest.raises(ValueError, match="BCP 47"):
        lang.get("not a tag")
    with pytest.raises(ValueError):
        lang.check_tag("fr")
    assert lang.check_tag("en-GB") == "en-GB"
    with pytest.raises(ValueError, match="already registered"):
        lang.register(lang.get("es"))


# --- Spanish --------------------------------------------------------------------------------------------------


def test_es_charset_and_normalisation():
    es = lang.get("es")
    for ch in "ñáéíóúü¿¡":
        assert ch in es.charset
    assert len(es.vocab) == 37 and es.vocab[0] == "<blank>" and es.vocab[-1] == " "
    assert es.normalize("¿Qué AÑO es? ¡Sí, señor!") == "¿qué año es ¡sí señor"
    assert es.normalize("Pingüino ÑANDÚ") == "pingüino ñandú"
    assert es.normalize("é") == "é"  # NFD input is composed
    assert es.normalize("à la carte, ça va") == "a la carte ca va"  # other accents fold to a-z
    assert es.normalize("İstanbul b̃") == "istanbul b"
    assert es.normalize("x 1 y", "drop") == "x y" and es.normalize("x1y", "drop") == "xy"
    t = "¿dónde está el baño?"
    assert es.decode(es.encode(t)) == es.normalize(t)
    assert es.words("¿dónde  está\tel baño") == ["¿dónde", "está", "el", "baño"]
    assert es.status == "provisional" and "provisional" in es.rates_source


# --- no word segmentation: never a silent WPM ------------------------------------------------------------------


def test_zh_words_per_minute_is_not_defined():
    zh = lang.get("zh-Hans")
    assert not zh.wpm_defined
    with pytest.raises(lang.WordsNotDefinedError, match="P14-39"):
        zh.words("我想喝水")
    with pytest.raises(lang.WordsNotDefinedError):
        zh.count_words("我想喝水")
    with pytest.raises(lang.WordsNotDefinedError):
        lang.wpm_counts(["我想喝水"], "zh")
    r = lang.wpm_counts(["我想喝水"], "zh", on_undefined="report")
    assert r["defined"] is False and r["status"] == "not-defined" and r["n_words"] is None and r["reason"]
    with pytest.raises(NotImplementedError):
        zh.vocab
    assert zh.normalize(" 我想　喝水 ") == "我想 喝水"
    assert zh.to_dict()["vocab_size"] is None


def test_language_needs_a_reason_without_segmentation():
    with pytest.raises(ValueError, match="words_not_defined_reason"):
        lang.Language(tag="ja", name="Japanese", script="Jpan", letters=None, normalizer=lambda t, u: t,
                      word_segmentation="none")


# --- threading: manifest and trust guard ---------------------------------------------------------------------


def test_packaged_manifests_are_english():
    from fidetype.pretrained.manifest import all_manifests

    ms = all_manifests()
    assert ms and all(m.language == "en" for m in ms)
    # The P14-34 manifests have no key (default en); willett-hw (P14-33) states "en" explicitly.
    assert all(m.raw.get("language", "en") == "en" for m in ms)
    assert {m.name for m in ms if "language" in m.raw} == {"willett-hw"}


def test_manifest_language_key_is_checked():
    from fidetype.pretrained.manifest import ManifestError, load_manifest, parse_manifest

    raw = dict(load_manifest("t15-m4-13").raw)
    assert parse_manifest({**raw, "language": "es-ES"}).language == "es-ES"
    with pytest.raises(ManifestError, match="language"):
        parse_manifest({**raw, "language": "xx"})
    with pytest.raises(ManifestError, match="BCP 47"):
        parse_manifest({**raw, "language": "not a tag"})


SPANISH = ["sí por favor", "muchas gracias", "tengo sed", "llama a mi esposa", "enciende la luz", "necesito ayuda",
           "abre la ventana", "buenos días", "cómo estás", "más agua por favor", "el niño pequeño", "mañana"]


def _es_logits(text: str, vocab: tuple[str, ...], rng: np.random.Generator) -> np.ndarray:
    noise = rng.uniform(0.0, 1.0)
    rows = []
    for ch in text:
        target = vocab.index(ch)
        if rng.random() < 0.25 * noise:
            target = int(rng.integers(1, len(vocab)))
        for k in range(3):
            row = rng.normal(0.0, 1.0, len(vocab))
            if k == 0:
                row[target] += 9.0 - 6.0 * noise
            else:
                row[0] += 7.0
            rows.append(row)
    return np.array(rows)


def test_spanish_config_end_to_end_on_synthetic_input(tmp_path: Path):
    es = lang.get("es")
    phrases = [es.normalize(p) for p in SPANISH]
    lexicon = sorted({w for p in phrases for w in es.words(p)})
    rng = np.random.default_rng(5)
    ts = [str(rng.choice(phrases)) for _ in range(200)]
    g = ft.calibrate([_es_logits(t, es.vocab, rng) for t in ts], ts, vocab=list(es.vocab), blank=0,
                     lexicon=lexicon, null_trials=40, decoder_name="test-es", language="es")
    assert g.language == "es"
    # held-out synthetic trials: decide, then score safe WPM through the language hook
    test = [str(rng.choice(phrases)) for _ in range(40)]
    res = [g.decide(_es_logits(t, es.vocab, rng)) for t in test]
    committed = [r.action == "commit" for r in res]
    correct = [r.action == "commit" and r.text == t for r, t in zip(res, test)]
    assert any(committed) and any("ñ" in r.text or "í" in r.text for r in res if r.action == "commit")
    wc = lang.wpm_counts(test, es)
    out = W.safe_wpm(committed, correct, wc["n_words"], wc["n_chars"], [5.0] * len(test),
                     guarantee={"method": "ltt", "alpha": g.alpha, "delta": g.delta, "n_cal": 200},
                     gaze_chars_per_min=wc["gaze_chars_per_min"])
    assert out["total_words"] == sum(len(t.split()) for t in test)
    # the guard file keeps the language; load reads it back
    p = g.save(tmp_path / "es.json")
    assert json.loads(p.read_text(encoding="utf-8"))["language"] == "es"
    g2 = ft.load(p)
    assert g2.language == "es"
    assert g2.decide(_es_logits(test[0], es.vocab, np.random.default_rng(9))).action == \
        g.decide(_es_logits(test[0], es.vocab, np.random.default_rng(9))).action


def test_english_guard_file_has_no_language_key(tmp_path: Path):
    # the n-best data of tests/test_trust_dropin.py (nbest_data, noise_nbest)
    phrases = ["yes please", "thank you", "i am thirsty", "call my wife", "turn on the light", "i need help",
               "open the window", "good morning", "how are you", "more water please"]

    def nb(t, rng):
        noise = rng.uniform(0.0, 1.0)
        others = [p for p in phrases if p != t]
        cands = [t] + [str(p) for p in rng.choice(others, size=3, replace=False)]
        gap = 6.0 * (1.0 - noise)
        scores = [0.0] + [float(-gap * rng.uniform(0.5, 1.5)) for _ in range(3)]
        if rng.random() < 0.3 * noise:
            scores[1] = 0.5
        order = np.argsort(scores)[::-1]
        return [(cands[i], scores[i]) for i in order]

    rng = np.random.default_rng(0)
    ts = [str(rng.choice(phrases)) for _ in range(300)]
    xs = [nb(t, rng) for t in ts]
    rng = np.random.default_rng(1)
    nulls = [[(str(p), float(-rng.uniform(0.0, 0.5))) for p in rng.choice(phrases, size=4, replace=False)]
             for _ in range(60)]
    g = ft.calibrate(xs, ts, null_inputs=nulls, null_trials=60)
    assert g.language == "en" and "language" not in g.to_dict()
    assert "language" not in json.loads(g.save(tmp_path / "en.json").read_text(encoding="utf-8"))
    assert ft.load(tmp_path / "en.json").language == "en"
    with pytest.raises(ValueError, match="language"):
        ft.calibrate(xs, ts, null_inputs=nulls, null_trials=60, language="xx")
    with pytest.raises(ValueError, match="word boundaries"):
        ft.calibrate(xs, ts, null_inputs=nulls, null_trials=60, language="zh",
                     commit_unit="prefix", confidence="learned")


def test_committed_t15_guard_file_loads_as_english():
    from fidetype.pretrained.manifest import manifest_dir

    p = manifest_dir().parent / "guards" / "t15-m4-13.guard.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    assert "language" not in d


def test_safe_wpm_reader_language_hook(tmp_path: Path):
    en = W.load_trials_jsonl(str(FIX / "safe_wpm_en.jsonl"))
    assert W.load_trials_jsonl(str(FIX / "safe_wpm_en.jsonl"), language="en") == en
    assert W.load_trials_jsonl(str(FIX / "safe_wpm_en.jsonl"), language="es-ES")["n_words"] == en["n_words"]
    p = tmp_path / "zh.jsonl"
    p.write_text(json.dumps({"truth": "我想喝水", "committed": True, "correct": True, "neural_s": 3.0},
                            ensure_ascii=False) + "\n", encoding="utf-8")
    assert W.load_trials_jsonl(str(p))["n_words"] == [1.0]  # the v0.1 rule: silent and wrong for zh
    with pytest.raises(lang.WordsNotDefinedError):
        W.load_trials_jsonl(str(p), language="zh")
