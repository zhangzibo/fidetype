"""P5-03 (lineage + licence flags) and P5-04 (consent refs, privacy policy, deletion / redaction).

Synthetic data only: no participant data, fake consent references.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from fidetype.collector import Collector, ConfigError, parse
from fidetype.trust import licence as L
from fidetype.trust.policy import Action, Decision, PolicyInputs
from fidetype.trust.privacy import (
    ConsentRecord,
    PrivacyPolicy,
    check_consent_ref,
    delete_profile,
    erase,
)
from fidetype.trust.privacy import main as privacy_main
from fidetype.trust.provenance import (
    LedgerView,
    ProvenanceLedger,
    entry_hash,
    is_tombstone,
    lineage_report,
    main,
    read_entries,
    record_lineage_spec,
    verify,
)

CTX = {"decoder": {"name": "dec", "version": "1"}, "calibration": {"id": "cal-1"}, "policy": {"version": "p1"}}


def inputs(texts=("hello world",), p=0.95):
    return PolicyInputs(texts=texts, p_top1=p, set_indices=(0,), guard_risk=0.01)


class _S:
    """A stand-in stream with a pseudonymous subject (only what record_decision reads)."""

    def __init__(self, subject):
        import numpy as np

        self.log_probs = np.zeros((4, 3), dtype=np.float32)
        self.frame_times = np.arange(4) * 0.04
        self.vocab, self.blank_id, self.source = ["<b>", "a", "b"], 0, "t"
        self.meta = {"subject.id": subject, "session.id": "s1"}


# --- licence flags -----------------------------------------------------------------------------


@pytest.mark.parametrize("given,spdx", [("CC0 1.0", "CC0-1.0"), ("CC BY 4.0", "CC-BY-4.0"),
                                        ("CC BY-NC 4.0", "CC-BY-NC-4.0"), ("CC-BY-NC-SA-4.0", "CC-BY-NC-SA-4.0"),
                                        ("CC BY 2.0 FR", "CC-BY-2.0-FR"), ("MIT", "MIT"),
                                        ("BSD-2-Clause style", L.UNKNOWN), (None, L.UNKNOWN)])
def test_normalise(given, spdx):
    assert L.normalise(given) == spdx


def test_flags_and_combine():
    cc0, ccby, nc = (L.source_summary(x) for x in ("CC0-1.0", "CC-BY-4.0", "CC-BY-NC-4.0"))
    assert cc0["product_ok"] == {"project": True, "commercial": True}
    assert ccby["product_ok"] == {"project": False, "commercial": True} and ccby["attribution"] == ["CC-BY-4.0"]
    assert nc["research_only"] and not nc["product_ok"]["commercial"]
    c = L.combine([cc0, ccby, nc])
    assert c["research_only"] and c["licences"] == ["CC-BY-4.0", "CC-BY-NC-4.0", "CC0-1.0"]
    assert L.combine([cc0, ccby])["commercial_ok"]
    assert L.source_summary("CC-BY-ND-4.0")["product_ok"]["commercial"] is False
    assert L.source_summary(L.UNKNOWN)["unknown"] == [L.UNKNOWN]
    # Consented own data: product use only with the train-product scope.
    assert not L.source_summary(L.CONSENTED, ["decode"])["commercial_ok"]
    assert L.source_summary(L.CONSENTED, ["decode", "train-product"])["product_ok"]["project"]


def test_track_licences_match_tracks():
    from fidetype.benchmark.tracks import TRACKS

    for slug in TRACKS:
        spdx, ro, _ = L.track_licence(slug)
        assert L.source_summary(spdx)["research_only"] == ro, slug


# --- lineage in the ledger ---------------------------------------------------------------------


def lineage_ledger(path=None, nc=False):
    led = ProvenanceLedger(path, text_mode="store")
    data = led.record_track_source("spanishbcbl-meg" if nc else "willett-hw")
    corpus = led.record_source("Tatoeba English", "CC BY 2.0 FR", url="https://tatoeba.org")
    w = led.record_artifact("weights", "dec", derived_from=[data], sha256="ab" * 32, version="1")
    lm = led.record_artifact("lm", "char-lm", derived_from=[corpus])
    cal = led.record_artifact("calibration", "cal-1", derived_from=[w, data])
    cid = led.record_context({**CTX, "lineage": [w, lm, cal]})
    d = led.record_decision(context_id=cid, decision=Decision(Action.COMMIT, ("hello world",), "p"),
                            inputs=inputs(), item_ref="t1")
    led.record_correction(d["body"]["decision_id"], "hello world")
    return led, d["body"]["decision_id"], {"data": data, "corpus": corpus, "w": w, "lm": lm, "cal": cal}


def test_lineage_of_one_committed_word(tmp_path):
    p = tmp_path / "l.jsonl"
    led, did, ids = lineage_ledger(p)
    assert verify(p).ok
    lin = LedgerView(p).lineage(did)
    assert [a["body"]["artifact_id"] for a in lin["artifacts"]][-1] == ids["cal"]
    assert {s["body"]["source_id"] for s in lin["sources"]} == {ids["data"], ids["corpus"]}
    assert lin["licence"] == {"research_only": False, "commercial_ok": True,
                              "product_ok": {"project": False, "commercial": True}}
    assert len(lin["corrections"]) == 1 and len(lin["entries"]) == 8
    rep = lineage_report(p, did, word=1)
    assert "PASS" in rep and "'world'" in rep and "CC-BY-2.0-FR" in rep and "CC0-1.0" in rep
    assert main(["lineage", str(p), did, "--word", "0"]) == 0
    assert main(["lineage", str(p), did, "--json"]) == 0


def test_nc_source_flags_every_output_and_blocks_product_weights():
    led, did, ids = lineage_ledger(nc=True)
    assert led.entries[-2]["body"]["licence"]["research_only"] is True  # the decision
    with pytest.raises(L.LicenceError, match="CC-BY-NC-4.0"):
        led.record_artifact("weights", "product-dec", derived_from=[ids["data"]], purpose="product")
    with pytest.raises(L.LicenceError):  # CC BY is not CC0: the project rule says no
        led.record_artifact("lm", "product-lm", derived_from=[ids["corpus"]], purpose="product")
    led.record_artifact("lm", "product-lm", derived_from=[ids["corpus"]], purpose="product",
                        product_policy="commercial")
    assert verify(led.entries).ok


def test_verify_catches_forged_licence_flags():
    led, did, ids = lineage_ledger(nc=True)
    es = json.loads(json.dumps(led.entries))
    i = next(k for k, e in enumerate(es) if e["kind"] == "decision")
    es[i]["body"]["licence"]["research_only"] = False  # claim the output is clean
    es[i]["body_sha256"] = __import__("fidetype.trust.provenance", fromlist=["x"]).body_digest(es[i]["salt"], es[i]["body"])
    es[i]["hash"] = entry_hash(es[i])
    r = verify(es)
    assert not r.ok and any("licence flags differ" in e for e in r.errors)
    # a forged product artifact (rewritten chain) fails the licence rule in verify
    es = json.loads(json.dumps(led.entries))
    j = next(k for k, e in enumerate(es) if e["kind"] == "artifact")
    es[j]["body"]["artifact"]["purpose"] = "product"
    assert any("licence rule" in e or "artifact_id" in e for e in verify(es).errors)


def test_unknown_lineage_and_consented_source():
    led = ProvenanceLedger()
    with pytest.raises(ValueError, match="unknown artifact"):
        led.record_context({**CTX, "lineage": ["art-nope"]})
    with pytest.raises(ValueError, match="consent"):
        led.record_source("pilot", "LicenseRef-fidetype-consented")
    with pytest.raises(ValueError, match="opaque"):
        led.record_source("pilot", "LicenseRef-fidetype-consented", consent={"ref": "jane@example.org",
                                                                             "scope": ["decode"]})
    s = led.record_source("pilot", "LicenseRef-fidetype-consented",
                          consent={"ref": "cr-2026-0001", "scope": ["decode", "train-product"]})
    a = led.record_artifact("weights", "w", derived_from=[s], purpose="product")
    led.set_lineage([a])
    cid = led.record_context(CTX)
    assert led.licence_of(cid)["product_ok"]["project"] is True
    assert verify(led.entries).ok
    # no input at all: unknown lineage, research only
    b = led.record_artifact("weights", "orphan")
    assert led._artifacts[b]["research_only"] and led._artifacts[b]["unknown"] == [L.UNKNOWN]


def test_lineage_spec_file(tmp_path):
    (tmp_path / "w.bin").write_bytes(b"weights")
    spec = {"schema": "fidetype.lineage-spec/0.1", "use": ["dec"],
            "sources": {"d": {"track": "kt-semg"}},
            "artifacts": {"dec": {"kind": "weights", "name": "emg-dec", "file": "w.bin", "derived_from": ["d"]}}}
    (tmp_path / "lineage.json").write_text(json.dumps(spec), encoding="utf-8")
    led = ProvenanceLedger()
    ids = record_lineage_spec(led, tmp_path / "lineage.json")
    art = LedgerView(led).artifacts[ids["dec"]]["body"]["artifact"]
    assert art["sha256"] == hashlib.sha256(b"weights").hexdigest()
    assert led.default_lineage == [ids["dec"]]
    with pytest.raises(ValueError, match="unknown input"):
        record_lineage_spec(ProvenanceLedger(), {"artifacts": {"x": {"kind": "lm", "derived_from": ["nope"]}}})


def test_anchor_cli(tmp_path):
    p = tmp_path / "l.jsonl"
    led, _, _ = lineage_ledger(p)
    a = tmp_path / "anchor.json"
    assert main(["anchor", str(p), "--out", str(a)]) == 0
    assert main(["verify", str(p), "--anchor", str(a)]) == 0
    led.note({"event": "more"})
    assert main(["verify", str(p), "--anchor", str(a)]) == 1  # the anchor no longer is the head


# --- redaction (P5-04) -------------------------------------------------------------------------


def subject_ledger(path, key=b"k" * 32):
    led = ProvenanceLedger(path, text_mode="store", hash_key=key)
    cid = led.record_context(CTX)
    ids = {}
    for subj, text in (("P01", "my secret words"), ("P02", "other person"), ("P01", "second line")):
        d = led.record_decision(context_id=cid, decision=Decision(Action.COMMIT, (text,), "p"),
                                inputs=inputs((text,)), stream=_S(subj))
        led.record_correction(d["body"]["decision_id"], text + " fixed")
        ids.setdefault(subj, []).append(d["body"]["decision_id"])
    return led, ids


def test_redact_subject_keeps_chain_verifiable(tmp_path):
    p = tmp_path / "l.jsonl"
    led, ids = subject_ledger(p)
    head_before = led.anchor()["hash"]
    e = led.redact_subject("P01", request_ref="er-2026-0007")
    assert e["body"]["n"] == 4  # 2 decisions + 2 corrections
    body = p.read_text(encoding="utf-8")
    assert "my secret words" not in body and "second line" not in body and "other person" in body
    r = verify(p)
    assert r.ok, r.errors
    es = read_entries(p)
    assert sum(is_tombstone(x) for x in es) == 4
    # the head before the erasure is still an entry of the chain (only bodies went away)
    assert any(x["hash"] == head_before for x in es)
    v = LedgerView(p)
    assert set(v.decisions) == set(ids["P02"]) and len(v.redacted) == 4
    # reopen: the ledger continues, the redacted decision is gone
    led2 = ProvenanceLedger(p, hash_key=b"k" * 32)
    with pytest.raises(ValueError):
        led2.record_correction(ids["P01"][0], "x")
    assert verify(p).ok


def test_tombstone_without_redaction_entry_fails(tmp_path):
    p = tmp_path / "l.jsonl"
    led, ids = subject_ledger(p)
    es = json.loads(json.dumps(led.entries))
    i = next(k for k, x in enumerate(es) if x["kind"] == "decision")
    del es[i]["body"], es[i]["salt"]
    r = verify(es)
    assert not r.ok and any("no redaction entry" in x for x in r.errors)
    # a decision body cannot be removed without its correction (the correction would point to nothing)
    es = json.loads(json.dumps(led.entries))
    led2 = ProvenanceLedger(None, hash_key=b"k" * 32)
    assert led2.hash_rule == "salted-body"


def test_body_edit_detected_and_v0_ledger_cannot_redact(tmp_path):
    led, _ = subject_ledger(None)
    es = json.loads(json.dumps(led.entries))
    i = next(k for k, x in enumerate(es) if x["kind"] == "decision")
    es[i]["body"]["action"] = "OFFER"
    assert any("hash mismatch" in x for x in verify(es).errors)
    old = ProvenanceLedger(hash_rule="v0")
    cid = old.record_context(CTX)
    d = old.record_decision(context_id=cid, decision=Decision(Action.COMMIT, ("a",), "p"), inputs=inputs(("a",)))
    assert "salt" not in d and verify(old.entries).ok
    with pytest.raises(ValueError, match="v0"):
        old.redact_decisions([d["body"]["decision_id"]], request_ref="er-0001")


def test_redact_rules():
    led, ids = subject_ledger(None)
    with pytest.raises(ValueError, match="only"):
        led.redact([1], request_ref="er-0001")  # the context entry
    with pytest.raises(ValueError, match="opaque"):
        led.redact_decisions(ids["P02"], request_ref="call jane on 555 0100")
    with pytest.raises(ValueError, match="reason"):
        led.redact_decisions(ids["P02"], request_ref="er-0001", reason="because")
    with pytest.raises(ValueError, match="no decision"):
        led.redact_subject("P99", request_ref="er-0001")


def test_redact_cli(tmp_path, monkeypatch):
    p = tmp_path / "l.jsonl"
    subject_ledger(p)
    monkeypatch.setenv("FT_LEDGER_KEY", "k" * 32)
    monkeypatch.setenv("FT_SUBJECT", "P02")
    assert main(["redact", str(p), "--subject-env", "FT_SUBJECT", "--request-ref", "er-0002",
                 "--key-env", "FT_LEDGER_KEY"]) == 0
    assert "other person" not in p.read_text(encoding="utf-8") and verify(p).ok


# --- consent and deletion ----------------------------------------------------------------------


@pytest.mark.parametrize("ref", ["cr-2026-0001", "consent:pending", "urn:uuid:3f1c0f4e-1b2a-4c3d-9e8f-001122334455",
                                 "synthetic-data"])
def test_consent_ref_ok(ref):
    assert check_consent_ref(ref) == ref


@pytest.mark.parametrize("ref", ["", "abc", "Jane Doe", "jane@example.org", "+1 555 010 0199", "a" * 200, None])
def test_consent_ref_bad(ref):
    with pytest.raises(ValueError):
        check_consent_ref(ref)


def test_consent_record():
    r = ConsentRecord("cr-2026-0001", ["decode", "train-research"], "form-v2", "2026-11-01T00:00:00Z",
                      expires_utc="2027-11-01T00:00:00Z", jurisdiction="US-CO")
    assert r.allows("decode", "2026-11-17T00:00:00Z") and not r.allows("train-product", "2026-11-17T00:00:00Z")
    assert not r.allows("decode", "2026-10-01T00:00:00Z") and not r.allows("decode", "2027-12-01T00:00:00Z")
    r.withdraw("2026-11-20T00:00:00Z")
    assert not r.allows("decode", "2026-11-21T00:00:00Z")
    assert r.scope_ref() == {"ref": "cr-2026-0001", "scope": ["decode", "train-research"]}
    assert ConsentRecord.from_dict(r.to_dict()) == r
    with pytest.raises(ValueError):
        ConsentRecord("cr-1x", ["decode", "sell"], "v", "2026-01-01T00:00:00Z")
    with pytest.raises(ValueError):
        ConsentRecord("cr-2026-0002", ["decode"], "v", "2026-01-01T00:00:00Z", extra={"email": "x"})


def test_profile_consent_ref_checked_and_erase(tmp_path):
    from fidetype.trust.personal import UserProfile

    with pytest.raises(ValueError):
        UserProfile.new("participant-07", None, salt="s", consent_ref="Jane Doe signed on paper")
    prof = UserProfile.new("participant-07", None, salt="s", consent_ref="cr-2026-0001")
    pp = prof.save(tmp_path / "profiles" / "p07.json")
    lp = tmp_path / "l.jsonl"
    subject_ledger(lp)
    rec = erase(request_ref="er-2026-0009", profile=pp, ledgers=[lp], subject_id="P01", ledger_key=b"k" * 32)
    assert not pp.exists() and rec["profile"]["user_hash"] == prof.user_hash and rec["profile"]["deleted"]
    assert rec["ledgers"][0]["n_redacted"] == 4 and rec["ledgers"][0]["verify_ok"]
    txt = json.dumps(rec)
    assert "P01" not in txt and "participant-07" not in txt and "p07" not in txt
    # a second request finds nothing more of the subject
    rec2 = erase(request_ref="er-2026-0010", ledgers=[lp], subject_id="P01", ledger_key=b"k" * 32)
    assert rec2["ledgers"][0]["n_redacted"] == 0


def test_delete_profile_receipt(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"user_hash": "u:abc"}', encoding="utf-8")
    r = delete_profile(p)
    assert r["user_hash"] == "u:abc" and r["deleted"] and not p.exists()


# --- privacy policy and the collector processor -------------------------------------------------

META = {"data.derived": True, "decoder.name": "d", "decoder.version": "1", "subject.id": "P01",
        "session.id": "s1", "user.personalized": True, "acme.operator": "ops@example.org", "acme.gain": 3,
        "device.serial": "+1 555 010 0199", "consent.ref": "cr-2026-0001", "language": "en"}


def test_default_policy():
    out, n = PrivacyPolicy().apply_meta(META)
    assert set(out) == {"data.derived", "decoder.name", "decoder.version", "consent.ref", "language"}
    assert n == {"kept": 5, "dropped": 5, "hashed": 0, "pii_dropped": 1}  # device.serial looks like a phone


def test_policy_rules_and_hash():
    pol = PrivacyPolicy({"default": "keep", "text": "hash", "meta": {"subject.*": "hash", "subject.keep": "keep",
                                                                     "acme.*": "drop"}})
    assert pol.action("subject.id") == "hash" and pol.action("subject.keep") == "keep"
    assert pol.action("acme.gain") == "drop" and pol.action("other") == "keep" and pol.needs_key
    out, _ = pol.apply_meta({"subject.id": "P01"}, key=b"k")
    assert out["subject.id"] == "h:" + hmac.new(b"k", b"P01", hashlib.sha256).hexdigest()[:32]
    with pytest.raises(ValueError):
        pol.apply_meta({"subject.id": "P01"})
    for bad in ({"default": "maybe"}, {"meta": {"a*b": "keep"}}, {"bogus": 1}, {"schema": "x"}):
        with pytest.raises(ValueError):
            PrivacyPolicy(bad)


def _write(path, events):
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def test_collector_privacy_filters_meta(tmp_path):
    hdr = {"type": "header", "spec_version": "0.1", "vocab": ["<blank>", "a"], "vocab_type": "char", "blank_id": 0,
           "source": "t", "frame_period": 0.04, "meta": dict(META)}
    _write(tmp_path / "s.jsonl", [hdr, {"type": "frame", "t": 0.0, "log_probs": [-0.1, -2.4]}, {"type": "end"}])
    (tmp_path / "policy.toml").write_text('schema = "fidetype.privacy-policy/1.0"\ndefault = "drop"\n'
                                          '[meta]\n"data.*" = "keep"\n"decoder.*" = "keep"\n"subject.id" = "hash"\n',
                                          encoding="utf-8")
    import os

    os.environ["FT_TEST_PRIV_KEY"] = "unit-test-key"
    try:
        d = {"service": {"log": "quiet"}, "receivers": {"in": {"type": "file", "paths": [str(tmp_path / "s.jsonl")]}},
             "processors": {"priv": {"type": "privacy", "policy": "policy.toml", "key_env": "FT_TEST_PRIV_KEY"}},
             "exporters": {"log": {"type": "jsonl", "path": "out/s.jsonl", "types": ["header", "frame", "end"]}},
             "pipelines": {"main": {"receivers": ["in"], "processors": ["priv"], "exporters": ["log"]}}}
        col = Collector(parse(d, base_dir=tmp_path))
        col.run()
    finally:
        del os.environ["FT_TEST_PRIV_KEY"]
    body = (tmp_path / "out" / "s.jsonl").read_text(encoding="utf-8")
    h = json.loads(body.splitlines()[0])
    assert set(h["meta"]) == {"data.derived", "decoder.name", "decoder.version", "subject.id"}
    assert h["meta"]["subject.id"].startswith("h:") and "P01" not in body and "example.org" not in body
    assert "unit-test-key" not in body
    m = col.metrics()["pipelines"]["main"]["processors"]["priv"]
    assert m["meta_hashed"] == 1 and m["headers"] == 1


def test_collector_privacy_config_errors(tmp_path):
    base = {"service": {"log": "quiet"}, "receivers": {"in": {"type": "file", "paths": ["s.jsonl"]}},
            "exporters": {"log": {"type": "jsonl", "path": "o.jsonl"}}}
    from fidetype.trust.frozen import FrozenTrustConfig

    FrozenTrustConfig(name="t").save(tmp_path / "trust.json")
    (tmp_path / "drop.json").write_text(json.dumps({"text": "drop"}), encoding="utf-8")
    (tmp_path / "hash.json").write_text(json.dumps({"meta": {"subject.id": "hash"}}), encoding="utf-8")
    procs = {"trust": {"type": "trust", "config": "trust.json"}, "p": {"type": "privacy", "policy": "drop.json"}}
    d = {**base, "processors": procs, "pipelines": {"m": {"receivers": ["in"], "processors": ["p", "trust"],
                                                          "exporters": ["log"]}}}
    with pytest.raises(ConfigError, match="before the trust step"):
        parse(d, base_dir=tmp_path)
    d["pipelines"]["m"]["processors"] = ["trust", "p"]
    parse(d, base_dir=tmp_path)  # after trust: fine
    d["processors"]["p"] = {"type": "privacy", "policy": "hash.json"}
    with pytest.raises(ConfigError, match="key_env"):
        parse(d, base_dir=tmp_path)
    d["processors"]["p"] = {"type": "privacy", "policy": "missing.toml"}
    with pytest.raises(ConfigError, match="not found"):
        parse(d, base_dir=tmp_path)
    d["processors"]["p"] = {"type": "privacy"}  # built-in default keeps text: may run before trust
    d["pipelines"]["m"]["processors"] = ["p", "trust"]
    parse(d, base_dir=tmp_path)


def test_privacy_cli(tmp_path, capsys):
    (tmp_path / "p.json").write_text(json.dumps({"id": "site-a", "text": "drop"}), encoding="utf-8")
    assert privacy_main(["check-policy", str(tmp_path / "p.json")]) == 0
    assert privacy_main(["check-consent-ref", "cr-2026-0001"]) == 0
    assert privacy_main(["check-consent-ref", "Jane Doe"]) == 2
