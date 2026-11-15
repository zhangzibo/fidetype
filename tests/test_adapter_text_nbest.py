"""Tests of the text n-best adapter (fidetype.adapters.text_nbest, P4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fidetype.adapters import text_nbest as X

DEC = X.TextDecoderInfo(modality="intracortical", name="test-decoder", version="1", lm_name="test-5gram",
                        weights_sha256="cd" * 32)


def _lines(p: Path) -> list[dict]:
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()]


def test_normalise_item_forms():
    assert X.normalise_item("hi") == {"text": "hi", "score": 0.0}
    assert X.normalise_item(("hi", -1.5)) == {"text": "hi", "score": -1.5}
    d = X.normalise_item({"text": "ab", "score": -2, "char_confidences": [0.9, 0.5], "logp_acoustic": -3.0})
    assert d == {"text": "ab", "score": -2.0, "char_confidences": [0.9, 0.5], "logp_acoustic": -3.0}
    with pytest.raises(ValueError, match="EVD-1"):
        X.normalise_item({"text": "ab", "char_confidences": [0.9]})
    with pytest.raises(ValueError, match="EVD-4"):
        X.normalise_item({"text": "ab", "logp_lm": 0.5})
    with pytest.raises(ValueError, match="finite"):
        X.normalise_item(("ab", float("nan")))
    with pytest.raises(ValueError, match="text"):
        X.normalise_item({"score": 1.0})


def test_events_shape_and_conformance(tmp_path: Path):
    utts = [X.Utterance([("the cat", -1.0), ("the hat", -2.0)], t_start=0.0, t_end=1.2),
            X.Utterance(["hello"], id="trial-7")]
    p = X.write_stream(utts, DEC, tmp_path / "s.jsonl",
                       decode_declaration={"decoder": "test-beam", "params": {"beam": 8}})
    ev = _lines(p)
    assert [e["type"] for e in ev] == ["header", "hypothesis", "segment_end", "hypothesis", "segment_end", "end"]
    head = ev[0]
    assert head["vocab"] == [] and head["blank_id"] is None
    assert head["decode_declaration"]["decoder"] == "test-beam"
    assert head["meta"]["adapter.name"] == X.ADAPTER_NAME and len(head["meta"]["stream.id"]) == 32
    assert ev[1]["id"] == "h1" and ev[1]["nbest"][0] == {"text": "the cat", "score": -1.0}
    assert ev[2] == {"type": "segment_end", "unit": "utterance", "t": 1.2}
    assert ev[3]["id"] == "trial-7"
    assert X.check_stream_file(p, "provenance") == []


def test_no_text_in_header_or_meta(tmp_path: Path):
    p = X.write_stream([X.Utterance(["secret sentence"])], DEC, tmp_path / "s.jsonl")
    assert "secret" not in json.dumps(_lines(p)[0])


def test_stream_id_depends_on_content():
    a = X.stream_events([X.Utterance(["a"])], DEC)[0]["meta"]["stream.id"]
    b = X.stream_events([X.Utterance(["a"])], DEC)[0]["meta"]["stream.id"]
    c = X.stream_events([X.Utterance(["b"])], DEC)[0]["meta"]["stream.id"]
    assert a == b != c


def test_errors():
    with pytest.raises(ValueError, match="HYP-1"):
        X.stream_events([X.Utterance(["a"], id="x"), X.Utterance(["b"], id="x")], DEC)
    with pytest.raises(ValueError, match="DEC-2"):
        X.stream_events([X.Utterance([("a", 3.0)])], DEC, score_semantics="uncalibrated_prob")
    with pytest.raises(ValueError, match="score_range"):
        X.stream_events([X.Utterance(["a"])], DEC, score_semantics="power")
    with pytest.raises(ValueError, match="DCL-1"):
        X.stream_events([X.Utterance(["a"])], DEC, decode_declaration={"params": {}})
    with pytest.raises(ValueError, match="at least one"):
        X.Utterance([])
    with pytest.raises(ValueError, match="before"):
        X.Utterance(["a"], t_start=2.0, t_end=1.0)
    off = X.TextDecoderInfo(modality="meg", name="x", version="1", causal=False)
    with pytest.raises(ValueError, match="MET-5"):
        X.stream_events([X.Utterance(["a"])], off, latency=1.0)


def test_probability_scores_pass(tmp_path: Path):
    p = X.write_stream([X.Utterance([("yes", 0.8), ("no", 0.2)])], DEC, tmp_path / "s.jsonl",
                       score_semantics="uncalibrated_prob")
    assert X.check_stream_file(p, "trust-ready") == []


def test_read_csv_groups_nbest(tmp_path: Path):
    f = tmp_path / "sub.csv"
    f.write_text("id,text,score\n0,the cat,-1\n0,the hat,-2\n1,,\n2,hello,-0.5\n", encoding="utf-8")
    utts = X.read_csv(f, score_col="score")
    assert [u.id for u in utts] == ["0", "1", "2"]
    assert [it["text"] for it in utts[0].nbest] == ["the cat", "the hat"]
    assert utts[1].nbest == [{"text": "", "score": 0.0}]
    with pytest.raises(ValueError, match="no column"):
        X.read_csv(f, text_col="sentence")


def test_read_jsonl_both_forms(tmp_path: Path):
    f = tmp_path / "nb.jsonl"
    f.write_text('{"id": "a", "nbest": [{"text": "x", "score": -1}]}\n\n'
                 '{"id": "b", "text": "y", "score": -2, "t_start": 0, "t_end": 1}\n', encoding="utf-8")
    utts = X.read_jsonl(f)
    assert [(u.id, u.nbest[0]["text"], u.t_end) for u in utts] == [("a", "x", None), ("b", "y", 1.0)]
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"id": "a", "text": "x", "score": NaN}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="GEN-2"):
        X.read_jsonl(bad)


def test_utterances_from_texts():
    utts = X.utterances_from_texts(["a", "b"], ids=["1", "2"])
    assert [(u.id, u.nbest[0]["text"]) for u in utts] == [("1", "a"), ("2", "b")]
    with pytest.raises(ValueError, match="same length"):
        X.utterances_from_texts(["a"], ids=["1", "2"])


def test_cli(tmp_path: Path, capsys):
    f = tmp_path / "sub.csv"
    f.write_text("id,text\n0,i need water\n1,thank you\n", encoding="utf-8")
    out = tmp_path / "s.jsonl"
    rc = X.main([str(f), "--modality", "emg", "--decoder-name", "kaggle-entry", "--decoder-version", "1",
                 "--out", str(out), "--level", "trust-ready"])
    assert rc == 0
    assert "2 utterance(s)" in capsys.readouterr().out
    ev = _lines(out)
    assert [e["id"] for e in ev if e["type"] == "hypothesis"] == ["0", "1"]


def test_broken_stream_is_caught(tmp_path: Path):
    ev = X.stream_events([X.Utterance(["a"])], DEC)
    ev[1]["nbest"][0]["score"] = None  # EVD-3 / HYP-1 type error
    p = X.write_events(ev, tmp_path / "bad.jsonl")
    assert X.check_stream_file(p) != []
