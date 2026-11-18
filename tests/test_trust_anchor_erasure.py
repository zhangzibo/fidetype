"""P5-14 (signed ledger anchors) and P5-15 (erasure in Collector output files).

Synthetic data only. Keys are throwaway keys made in the test; no key file is in the repository.
"""

from __future__ import annotations

import json
import math

import pytest

from fidetype.collector import Collector, ConfigError, parse
from fidetype.conformance.nts_conform import conform_file
from fidetype.trust import anchor as A
from fidetype.trust.erasure import INDEX_SCHEMA, erase_outputs, session_path, session_token, subject_code
from fidetype.trust.frozen import FrozenTrustConfig
from fidetype.trust.policy import Action, Decision, PolicyInputs
from fidetype.trust.privacy import erase
from fidetype.trust.privacy import main as privacy_main
from fidetype.trust.provenance import ProvenanceLedger, body_digest, entry_hash, main, read_entries, verify

needs_sign = pytest.mark.skipif(not A.signing_available(), reason='needs cryptography (pip install "fidetype[sign]")')
CTX = {"decoder": {"name": "dec", "version": "1"}, "calibration": {"id": "cal-1"}, "policy": {"version": "p1"}}


class _S:
    def __init__(self, subject):
        import numpy as np

        self.log_probs = np.zeros((4, 3), dtype=np.float32)
        self.frame_times = np.arange(4) * 0.04
        self.vocab, self.blank_id, self.source = ["<b>", "a", "b"], 0, "t"
        self.meta = {"subject.id": subject, "session.id": "s1"}


def _ledger(path, key=b"k" * 32):
    led = ProvenanceLedger(path, text_mode="store", hash_key=key)
    cid = led.record_context(CTX)
    for subj, text in (("P01", "my secret words"), ("P02", "other person"), ("P01", "second line")):
        led.record_decision(context_id=cid, decision=Decision(Action.COMMIT, (text,), "p"),
                            inputs=PolicyInputs(texts=(text,), p_top1=0.95, set_indices=(0,), guard_risk=0.01),
                            stream=_S(subj))
    return led


def _replace(obj, old, new):
    if isinstance(obj, dict):
        return {k: _replace(v, old, new) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace(v, old, new) for v in obj]
    return obj.replace(old, new) if isinstance(obj, str) else obj


def _rewrite_and_rechain(entries, old, new):
    """The attack: edit a body, then recompute every digest and hash so that the chain verifies again."""
    out, prev, remap = [], None, {}
    for e in entries:
        e = json.loads(json.dumps(e))
        e["body"] = _replace(e["body"], old, new)
        for k, v in list(e["body"].items()):
            if isinstance(v, str) and v in remap:
                e["body"][k] = remap[v]
        if prev is not None:
            e["prev_hash"] = prev
        if "salt" in e:
            e["body_sha256"] = body_digest(e["salt"], e["body"])
        h = entry_hash(e)
        remap[e["hash"]] = h
        e["hash"] = prev = h
        out.append(e)
    return out


# --- P5-14 signed anchors ----------------------------------------------------------------------


@needs_sign
def test_signed_anchor_detects_a_rewritten_ledger_with_a_recomputed_chain(tmp_path):
    led = _ledger(tmp_path / "l.jsonl")
    priv, pub = A.generate_key()
    anc = A.sign_anchor(A.make_anchor(led.entries), priv)
    assert anc["signature"]["key_id"] == A.key_id(pub) and anc["schema"] == A.ANCHOR_SCHEMA
    assert A.verify_anchored(led.entries, anc, pub).ok
    forged = _rewrite_and_rechain(led.entries, "my secret words", "forged words")
    assert verify(forged).ok  # the chain alone cannot see the rewrite (tamper-evident, not tamper-proof)
    res = A.verify_anchored(forged, anc, pub)
    assert not res.ok and any("another hash" in e for e in res.errors)
    # The attacker also rewrites the anchor: the signature no longer verifies.
    fake = dict(anc, hash=forged[-1]["hash"])
    assert any("does not verify" in e for e in A.verify_anchored(forged, fake, pub).errors)
    # ... or signs a new anchor with an own key: the key id and the signature fail against the real key.
    other, _ = A.generate_key()
    res = A.verify_anchored(forged, A.sign_anchor(A.make_anchor(forged), other), pub)
    assert any("key_id" in e for e in res.errors) and any("does not verify" in e for e in res.errors)


@needs_sign
def test_signed_anchor_rules(tmp_path):
    led = _ledger(tmp_path / "l.jsonl")
    priv, pub = A.generate_key()
    anc = A.sign_anchor(A.make_anchor(led.entries), priv)
    # A signed anchor without a public key proves nothing: fail.
    assert any("public key" in e for e in A.verify_anchored(led.entries, anc).errors)
    # An unsigned anchor with a public key: fail.
    assert not A.verify_anchored(led.entries, A.make_anchor(led.entries), pub).ok
    # Growth after the anchor: fail by default, pass with allow_growth (the anchored entry is still there).
    led.record_context({**CTX, "policy": {"version": "p2"}})
    assert any("after the anchored head" in e for e in A.verify_anchored(led.entries, anc, pub).errors)
    assert A.verify_anchored(led.entries, anc, pub, allow_growth=True).ok
    # A cut below the anchor: fail.
    assert any("not in the ledger" in e for e in A.verify_anchored(led.entries[:3], anc, pub).errors)
    # Another ledger id: fail.
    assert any("ledger_id" in e for e in A.verify_anchored(led.entries, A.sign_anchor({**anc, "ledger_id": "x"}, priv),
                                                            pub, allow_growth=True).errors)
    # Redaction keeps the entry hashes: the anchor stays valid after an erasure (P5-04 tombstones).
    led.redact_subject("P01", request_ref="er-0001")
    assert A.verify_anchored(read_entries(tmp_path / "l.jsonl"), anc, pub, allow_growth=True).ok


@needs_sign
def test_anchor_cli_keygen_sign_verify(tmp_path, monkeypatch, capsys):
    p = tmp_path / "l.jsonl"
    _ledger(p)
    k, pub = tmp_path / "keys" / "anchor.pem", tmp_path / "keys" / "anchor.pub.pem"
    k.parent.mkdir()
    assert main(["keygen", "--private", str(k), "--public", str(pub)]) == 0
    assert main(["keygen", "--private", str(k), "--public", str(pub)]) == 2  # never overwrites a key
    assert main(["anchor", str(p), "--out", str(tmp_path / "a.json"), "--sign-key-file", str(k)]) == 0
    assert json.loads((tmp_path / "a.json").read_text())["signature"]["alg"] == "ed25519"
    monkeypatch.setenv("FT_ANCHOR_KEY", k.read_text())
    assert main(["anchor", str(p), "--out", str(tmp_path / "b.json"), "--sign-key-env", "FT_ANCHOR_KEY"]) == 0
    capsys.readouterr()
    assert main(["verify", str(p), "--anchor", str(tmp_path / "a.json"), "--public-key", str(pub)]) == 0
    assert "signature checked" in capsys.readouterr().out
    assert main(["verify", str(p), "--anchor", str(tmp_path / "a.json")]) == 1  # signed, no key given
    forged = _rewrite_and_rechain(read_entries(p), "second line", "forged line")
    p.write_text("".join(json.dumps(e) + "\n" for e in forged), encoding="utf-8")
    assert main(["verify", str(p)]) == 0  # the chain alone passes
    assert main(["verify", str(p), "--anchor", str(tmp_path / "a.json"), "--public-key", str(pub)]) == 1
    assert main(["verify", str(p), "--public-key", str(pub)]) == 2  # --public-key needs --anchor


def test_unsigned_anchor_still_works(tmp_path):
    led = _ledger(tmp_path / "l.jsonl")
    anc = A.make_anchor(led.entries)
    assert A.verify_anchored(led.entries, anc).ok
    assert main(["verify", str(tmp_path / "l.jsonl"), "--head", anc["hash"]]) == 0


# --- P5-15 erasure in Collector output files ---------------------------------------------------

LP = [math.log(0.9), math.log(0.07), math.log(0.03)]  # blank
LP_A = [math.log(0.05), math.log(0.9), math.log(0.05)]  # "a": blank / "a" frames decode to a non-blank text
KEY_ENV = "FT_TEST_ERASE_KEY"
KEY = "erase-test-key-0123456789"


def _stream(subject, n):
    hdr = {"type": "header", "spec_version": "0.1", "vocab": ["<blank>", "a", "b"], "vocab_type": "char",
           "blank_id": 0, "source": "t", "frame_period": 0.04,
           "meta": {"data.derived": True, "subject.id": subject, "decoder.name": "sim"}}
    evs = [hdr]
    for u in range(3):
        evs += [{"type": "frame", "t": round((u * (n + 5) + i) * 0.04, 6), "log_probs": LP_A if i % 2 == 0 else LP} for i in range(n)]
        evs.append({"type": "segment_end"})
    evs[-1] = {"type": "end"}
    return evs


def _pipeline_config(tmp_path, paths):
    FrozenTrustConfig(name="erase-test").with_policy(commit_p=0.3, commit_max_risk=1.0,
                                                     abstain_risk=1.01).save(tmp_path / "trust.json")
    files = [str(p) for p in paths]
    return {
        "service": {"log": "quiet", "metrics_file": "out/metrics.json"},
        "receivers": {"in": {"type": "file", "paths": files}, "raw": {"type": "file", "paths": files}},
        "processors": {
            "check": {"type": "validate"},
            "priv": {"type": "privacy", "key_env": KEY_ENV, "subject_index": "out/subject-index.jsonl"},
            "trust": {"type": "trust", "config": "trust.json", "decoder": "greedy", "max_attempts": 1},
            "priv2": {"type": "privacy", "key_env": KEY_ENV, "subject_index": "out/subject-index-raw.jsonl"},
        },
        "exporters": {
            "log": {"type": "jsonl", "path": "out/decisions.jsonl"},
            "per": {"type": "jsonl", "path": "out/decisions/{session}.jsonl"},
            "typed": {"type": "os_text", "path": "out/typed.jsonl"},
            "streams": {"type": "jsonl", "path": "out/streams/{session}.jsonl",
                        "types": ["header", "frame", "segment_end", "end"]},
        },
        "pipelines": {
            "dec": {"receivers": ["in"], "processors": ["check", "priv", "trust"], "exporters": ["log", "per", "typed"]},
            "nts": {"receivers": ["raw"], "processors": ["priv2"], "exporters": ["streams"]},
        },
    }


def _lines(p):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _run_pipeline(tmp_path, monkeypatch):
    for name, subj, n in (("a.jsonl", "P-AAA-01", 5), ("b.jsonl", "P-BBB-02", 4), ("c.jsonl", "P-AAA-01", 3)):
        (tmp_path / name).write_text("".join(json.dumps(e) + "\n" for e in _stream(subj, n)), encoding="utf-8")
    monkeypatch.setenv(KEY_ENV, KEY)
    col = Collector(parse(_pipeline_config(tmp_path, [tmp_path / x for x in ("a.jsonl", "b.jsonl", "c.jsonl")]),
                          base_dir=tmp_path))
    col.run()
    return tmp_path / "out"


def test_collector_writes_per_session_files_and_subject_index(tmp_path, monkeypatch):
    out = _run_pipeline(tmp_path, monkeypatch)
    idx = _lines(out / "subject-index.jsonl")
    code = subject_code("P-AAA-01", KEY.encode())
    assert [(r["schema"], r["session"], r["subject"]) for r in idx if r["subject"] == code] == [
        (INDEX_SCHEMA, "in-0", code), (INDEX_SCHEMA, "in-2", code)]
    body = "".join(p.read_text(encoding="utf-8") for p in out.rglob("*.jsonl"))
    assert "P-AAA-01" not in body and "P-BBB-02" not in body and KEY not in body
    assert sorted(p.name for p in (out / "streams").iterdir()) == ["raw-0.jsonl", "raw-1.jsonl", "raw-2.jsonl"]
    assert {d["session"] for d in _lines(out / "decisions" / "in-1.jsonl")} == {"in-1"}
    for p in [out / "decisions.jsonl", *(out / "streams").iterdir(), *(out / "decisions").iterdir()]:
        assert not conform_file(p).fails, p


def test_erase_one_subject_from_pipeline_outputs(tmp_path, monkeypatch):
    out = _run_pipeline(tmp_path, monkeypatch)
    log = out / "decisions.jsonl"
    before = conform_file(log)
    n_b = sum(d["session"] == "in-1" for d in _lines(log))
    typed_b = [t for t in _lines(out / "typed.jsonl") if t["decision"]["session"] == "in-1"]
    monkeypatch.setenv("FT_SUBJ", "P-AAA-01")
    monkeypatch.setenv("FT_IDX", KEY)
    receipt = tmp_path / "receipt.json"
    rc = privacy_main(["erase", "--request-ref", "er-2026-0042", "--subject-env", "FT_SUBJ",
                       "--index-key-env", "FT_IDX",
                       "--subject-index", str(out / "subject-index.jsonl"),
                       "--subject-index", str(out / "subject-index-raw.jsonl"),
                       "--output", str(log), "--output", str(out / "typed.jsonl"),
                       "--output-template", str(out / "decisions" / "{session}.jsonl"),
                       "--output-template", str(out / "streams" / "{session}.jsonl"),
                       "--receipt", str(receipt)])
    assert rc == 0
    rec = json.loads(receipt.read_text())
    # The subject's sessions are gone from every output; the other subject's items stay unchanged.
    assert {d["session"] for d in _lines(log)} == {"in-1"} and len(_lines(log)) == n_b
    assert [t for t in _lines(out / "typed.jsonl")] == typed_b
    assert sorted(p.name for p in (out / "decisions").iterdir()) == ["in-1.jsonl"]
    assert sorted(p.name for p in (out / "streams").iterdir()) == ["raw-1.jsonl"]
    code = subject_code("P-AAA-01", KEY.encode())
    for ip in ("subject-index.jsonl", "subject-index-raw.jsonl"):
        assert all(r["subject"] != code for r in _lines(out / ip))
    # Every remaining file still passes nts-conform check, at the same level as before.
    after = conform_file(log)
    assert not after.fails and after.verdict == before.verdict
    for p in [*(out / "streams").iterdir(), *(out / "decisions").iterdir()]:
        r = conform_file(p)
        assert not r.fails, p
    assert conform_file(out / "streams" / "raw-1.jsonl").stream_level is not None
    # The receipt: one entry per file, counts and digests, conformance before / after; no path and no id.
    o = rec["outputs"]
    assert rec["schema"] == "fidetype.deletion-receipt/1.1" and o["n_sessions"] == 4
    f1 = o["files"][0]
    assert f1["form"] == "decision-log" and f1["action"] == "rewritten" and f1["n_kept"] == n_b
    assert f1["conform"]["before"]["ok"] and f1["conform"]["after"]["ok"]
    assert typed_b and o["files"][1]["form"] == "os-text-log" and o["files"][1]["action"] == "rewritten"
    assert [t["n_files_deleted"] for t in o["templates"]] == [2, 2]
    assert [x["action"] for x in o["indexes"]] == ["rewritten", "rewritten"]
    txt = receipt.read_text()
    for secret in ("P-AAA-01", "in-0", "in-2", "raw-0", str(tmp_path).replace("\\", "\\\\"), "decisions.jsonl", KEY,
                   code):
        assert secret not in txt, secret
    # A second request is a no-op: nothing of the subject is left.
    rec2 = erase(request_ref="er-2026-0043", subject_id="P-AAA-01", index_key=KEY.encode(),
                 subject_indexes=[out / "subject-index.jsonl"], outputs=[log])
    assert rec2["outputs"]["n_sessions"] == 0 and rec2["outputs"]["files"][0]["action"] == "unchanged"


def test_erase_nts_stream_file_by_header_and_explicit_sessions(tmp_path):
    key = b"k2"
    s1, s2 = tmp_path / "s1.jsonl", tmp_path / "s2.jsonl"
    ev = _stream(subject_code("P07", key), 3)
    s1.write_text("".join(json.dumps(e) + "\n" for e in ev), encoding="utf-8")
    s2.write_text("".join(json.dumps(e) + "\n" for e in _stream("h:" + "0" * 32, 3)), encoding="utf-8")
    log = tmp_path / "d.jsonl"
    log.write_text(json.dumps({"type": "trust_decision", "session": "x/1"}) + "\n", encoding="utf-8")
    r = erase_outputs(subject_id="P07", key=key, files=[s1, s2, log, tmp_path / "missing.jsonl"], sessions=["x/1"])
    assert [f["action"] for f in r["files"]] == ["deleted", "unchanged", "deleted", "missing"]
    assert not s1.exists() and s2.exists() and not log.exists()
    with pytest.raises(ValueError, match="placeholder"):
        erase_outputs(sessions=["a"], templates=[str(tmp_path / "x.jsonl")])
    with pytest.raises(ValueError, match="privacy key"):
        erase_outputs(subject_id="P07", indexes=[tmp_path / "i.jsonl"])


def test_session_token_and_config_rules(tmp_path, monkeypatch):
    assert session_token("in-0") == "in-0"
    assert session_token("ra/ra-0") != session_token("ra_ra-0") and "/" not in session_token("ra/ra-0")
    assert session_token("..") != ".." and session_path("o/{session}.jsonl", "a/b").startswith("o/a_b-")
    base = {"service": {"log": "quiet"}, "receivers": {"in": {"type": "file", "paths": ["s.jsonl"]}},
            "exporters": {"log": {"type": "jsonl", "path": "o/{subject}.jsonl"}},
            "pipelines": {"m": {"receivers": ["in"], "exporters": ["log"]}}}
    with pytest.raises(ConfigError, match="placeholder"):
        parse(base, base_dir=tmp_path)
    base["exporters"]["log"]["path"] = "o/{session}.jsonl"
    base["processors"] = {"p": {"type": "privacy", "subject_index": "i.jsonl"}}
    base["pipelines"]["m"]["processors"] = ["p"]
    with pytest.raises(ConfigError, match="key_env"):
        parse(base, base_dir=tmp_path)
    base["processors"]["p"]["key_env"] = KEY_ENV
    parse(base, base_dir=tmp_path)
