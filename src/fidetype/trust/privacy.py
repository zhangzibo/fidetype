"""Privacy and consent: consent references, the privacy policy, deletion (P5-04).

Not legal advice. Neural-data laws differ by jurisdiction and change often
(``wiki/questions/neural-data-law.md``). These tools help an operator to
document consent, keep less data and delete data on request. They do not
make a deployment compliant.

Consent references
------------------
The repository and the streams never hold a consent record. They hold only
an **opaque reference** to a record that the operator keeps elsewhere (NTS
``meta["consent.ref"]``, rule SEC-6; :attr:`UserProfile.consent_ref
<fidetype.trust.personal.UserProfile.consent_ref>`; a ``source`` entry of the
provenance ledger). :func:`check_consent_ref` checks the form:

- 4 to 128 characters: letters, digits and ``. _ : / # -``; it starts with a
  letter or a digit;
- no white space, no ``@`` (no e-mail address), not a phone-number-like
  run of digits.

Good: ``cr-2026-0001``, ``urn:uuid:3f1c...``, ``consent:pending``. Bad: a
name, an e-mail address, the consent text.

:class:`ConsentRecord` is the record **on the operator's side** (never in
this repository): reference, purposes (:data:`PURPOSES`), form version, the
grant, expiry and withdrawal times, the jurisdiction code. It holds no name
and no contact data; the operator links it to a person in its own system.
:meth:`ConsentRecord.allows` answers "may I do X now?".
:meth:`ConsentRecord.scope_ref` gives the part that the ledger may hold
(``ref`` and ``scope``).

Privacy policy (collector processor ``privacy``)
-----------------------------------------------
:class:`PrivacyPolicy` says what happens to each header ``meta`` key and to
decoded text. A policy file (TOML or JSON)::

    schema = "fidetype.privacy-policy/1.0"
    id = "site-a-v1"            # optional; else a content hash
    default = "drop"            # meta keys that no rule names: keep | drop | hash
    text = "keep"               # decoded text (trust_decision.shown, hypothesis n-best): keep | drop | hash
    scan_pii = true             # drop a kept meta string that holds an e-mail address, a phone number or an IP

    [meta]
    "subject.id" = "hash"       # exact key
    "session.id" = "hash"
    "decoder.*" = "keep"        # namespace pattern

The exact key wins over a pattern; a longer pattern wins over a shorter one.
``hash`` gives ``"h:" + HMAC-SHA256(key, value)[:32]`` (a pseudonymous code
that still passes the PV-PSEUDONYM check); it needs a key (the collector
reads it from an environment variable). :data:`DEFAULT_POLICY` keeps the
provenance namespaces, ``data.*``, ``consent.ref``, ``language`` and the
modality keys; it drops ``subject.*``, ``session.*``, ``user.*`` and every
other key, and keeps text (so the processor may run before the trust step).

Deletion
--------
- :func:`delete_profile` deletes a user's profile file and returns a
  receipt (user hash and file digest; no raw id, no path).
- :meth:`ProvenanceLedger.redact_subject
  <fidetype.trust.provenance.ProvenanceLedger.redact_subject>` removes the
  bodies of a subject's decisions and corrections; the chain still verifies
  (tombstones).
- :func:`erase` does both for one request and returns one receipt
  (``fidetype.deletion-receipt/1.1``). P5-15: it can also remove the subject's
  items from Collector output files (decision logs, NTS stream files, the
  ``os_text`` log, per-session files) through :mod:`fidetype.trust.erasure`.

Command line::

    python -m fidetype.trust.privacy check-policy policy.toml
    python -m fidetype.trust.privacy check-consent-ref <ref>
    python -m fidetype.trust.privacy erase --request-ref <ref> [--profile p.json] [--ledger l.jsonl ...]
        [--subject-env VAR] [--ledger-key-env VAR] [--receipt out.json]
        [--output FILE ...] [--output-template 'out/{session}.jsonl' ...] [--subject-index FILE ...]
        [--index-key-env VAR] [--sessions-env VAR]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

#: Purposes that a consent can cover. ``train-product`` is the one that allows product weights (licence rule).
PURPOSES = ("decode", "store-text", "store-ledger", "calibrate", "personalise", "train-research", "train-product",
            "share-research")
POLICY_SCHEMA = "fidetype.privacy-policy/1.0"
#: 1.1 (P5-15) adds ``outputs`` (Collector output files); a 1.0 receipt is a 1.1 receipt without it.
RECEIPT_SCHEMA = "fidetype.deletion-receipt/1.1"
META_ACTIONS = ("keep", "drop", "hash")

_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{3,127}$")
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"^\+?[\d\s().-]+$")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _looks_like_phone(s: str) -> bool:
    return bool(_PHONE_RE.match(s)) and 9 <= sum(c.isdigit() for c in s) <= 15


def check_opaque_ref(ref: Any, what: str = "reference") -> str:
    """Return ``ref`` if it is an opaque reference (module docstring), else raise ``ValueError``."""
    if not isinstance(ref, str) or not _REF_RE.match(ref):
        raise ValueError(f"{what} must be an opaque id: 4-128 characters of letters, digits and . _ : / # - "
                         f"(no spaces, no e-mail address); got {ref!r}"[:300])
    if _looks_like_phone(ref.replace(":", "").replace("/", "")) and not any(c.isalpha() for c in ref):
        raise ValueError(f"{what} looks like a phone number; use an opaque id")
    return ref


def check_consent_ref(ref: Any) -> str:
    """Return ``ref`` if it is a valid consent reference (SEC-6: opaque, no personal data)."""
    return check_opaque_ref(ref, "consent reference")


def check_scope(scope: Sequence[str]) -> list[str]:
    """The sorted, unique purposes of a consent scope; raise on an unknown purpose."""
    s = sorted(set(str(x) for x in scope))
    bad = [x for x in s if x not in PURPOSES]
    if bad:
        raise ValueError(f"unknown consent purpose(s) {bad}; known: {PURPOSES}")
    return s


@dataclass
class ConsentRecord:
    """A consent record on the operator's side (never in this repository). No name, no contact data."""

    ref: str
    purposes: list[str]
    form_version: str
    granted_utc: str
    expires_utc: str | None = None
    withdrawn_utc: str | None = None
    #: A jurisdiction code (for example ``"US-CO"``, ``"EU"``, ``"CL"``); informative.
    jurisdiction: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        check_consent_ref(self.ref)
        self.purposes = check_scope(self.purposes)
        for k in ("name", "email", "e-mail", "phone", "address", "birth_date", "dob"):
            if k in self.extra:
                raise ValueError(f"a consent record here must not hold personal data (key {k!r})")

    def allows(self, purpose: str, at: str | None = None) -> bool:
        """True if the consent covers ``purpose`` at time ``at`` (ISO 8601 UTC; default now)."""
        if purpose not in PURPOSES:
            raise ValueError(f"unknown purpose {purpose!r}")
        t = at or _now()
        if purpose not in self.purposes or t < self.granted_utc:
            return False
        if self.withdrawn_utc is not None and t >= self.withdrawn_utc:
            return False
        return not (self.expires_utc is not None and t >= self.expires_utc)

    def withdraw(self, at: str | None = None) -> None:
        self.withdrawn_utc = at or _now()

    def scope_ref(self) -> dict[str, Any]:
        """``{"ref", "scope"}``: the part that a ledger ``source`` entry may hold."""
        return {"ref": self.ref, "scope": list(self.purposes)}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ConsentRecord":
        return cls(**{k: d[k] for k in d if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Privacy policy
# ---------------------------------------------------------------------------

DEFAULT_POLICY: dict[str, Any] = {
    "schema": POLICY_SCHEMA,
    "id": "fidetype-default-1",
    "default": "drop",
    "text": "keep",
    "scan_pii": True,
    "meta": {
        "device.*": "keep", "decoder.*": "keep", "adapter.*": "keep", "lm.*": "keep", "calibration.*": "keep",
        "stream.*": "keep", "data.*": "keep", "emg.*": "keep", "meg.*": "keep", "implant.*": "keep",
        "consent.ref": "keep", "language": "keep",
        "subject.*": "drop", "session.*": "drop", "user.*": "drop",
    },
}


def _hmac(key: bytes, value: str) -> str:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


class PrivacyPolicy:
    """What happens to each ``meta`` key and to decoded text (module docstring)."""

    def __init__(self, d: Mapping[str, Any] | None = None) -> None:
        d = dict(DEFAULT_POLICY if d is None else d)
        if d.get("schema", POLICY_SCHEMA) != POLICY_SCHEMA:
            raise ValueError(f"unknown privacy policy schema {d.get('schema')!r} (expected {POLICY_SCHEMA!r})")
        unknown = set(d) - {"schema", "id", "default", "text", "scan_pii", "meta"}
        if unknown:
            raise ValueError(f"unknown privacy policy key(s) {sorted(unknown)}")
        self.default = d.get("default", "drop")
        self.text = d.get("text", "keep")
        self.scan_pii = bool(d.get("scan_pii", True))
        for name, v in (("default", self.default), ("text", self.text)):
            if v not in META_ACTIONS:
                raise ValueError(f"{name} must be one of {META_ACTIONS}, got {v!r}")
        self.exact: dict[str, str] = {}
        self.prefixes: list[tuple[str, str]] = []
        for k, v in dict(d.get("meta") or {}).items():
            if v not in META_ACTIONS:
                raise ValueError(f"meta.{k}: action must be one of {META_ACTIONS}, got {v!r}")
            if k.endswith(".*"):
                self.prefixes.append((k[:-1], v))
            elif "*" in k:
                raise ValueError(f"meta.{k}: a pattern is 'namespace.*'; other wildcards are not allowed")
            else:
                self.exact[k] = v
        self.prefixes.sort(key=lambda kv: -len(kv[0]))
        body = {"default": self.default, "text": self.text, "scan_pii": self.scan_pii, "meta": dict(d.get("meta") or {})}
        self.id = str(d.get("id") or "pp-" + hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16])

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "PrivacyPolicy":
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        if p.suffix.lower() == ".toml":
            import tomllib

            return cls(tomllib.loads(text))
        return cls(json.loads(text))

    @property
    def needs_key(self) -> bool:
        """True if any rule hashes (then a key is required)."""
        return "hash" in (self.default, self.text, *self.exact.values(), *(v for _, v in self.prefixes))

    def action(self, key: str) -> str:
        if key in self.exact:
            return self.exact[key]
        for pre, v in self.prefixes:
            if key.startswith(pre):
                return v
        return self.default

    @staticmethod
    def pii_hit(value: Any) -> str | None:
        """A reason if ``value`` looks like personal data (e-mail, phone number, IPv4 address), else None."""
        if not isinstance(value, str):
            return None
        if _EMAIL_RE.search(value):
            return "e-mail address"
        if _looks_like_phone(value):
            return "phone number"
        if _IPV4_RE.search(value):
            return "IP address"
        return None

    def apply_meta(self, meta: Mapping[str, Any], key: bytes | None = None) -> tuple[dict[str, Any], dict[str, int]]:
        """Return the filtered ``meta`` and counts (kept, dropped, hashed, pii_dropped)."""
        out: dict[str, Any] = {}
        n = {"kept": 0, "dropped": 0, "hashed": 0, "pii_dropped": 0}
        for k, v in meta.items():
            a = self.action(k)
            if a == "drop":
                n["dropped"] += 1
                continue
            if a == "hash":
                if not key:
                    raise ValueError("the privacy policy hashes values but no key was given")
                out[k] = "h:" + _hmac(key, v if isinstance(v, str) else json.dumps(v, sort_keys=True))[:32]
                n["hashed"] += 1
                continue
            if self.scan_pii and self._pii_any(v):
                n["pii_dropped"] += 1
                continue
            out[k] = v
            n["kept"] += 1
        return out, n

    def _pii_any(self, v: Any) -> bool:
        if isinstance(v, str):
            return self.pii_hit(v) is not None
        if isinstance(v, (list, tuple)):
            return any(self._pii_any(x) for x in v)
        if isinstance(v, Mapping):
            return any(self._pii_any(x) for x in v.values())
        return False

    def text_value(self, text: str, key: bytes | None = None) -> str | None:
        """The text under ``text``: itself (keep), None (drop) or its HMAC hex (hash)."""
        if self.text == "keep":
            return text
        if self.text == "drop":
            return None
        if not key:
            raise ValueError("the privacy policy hashes text but no key was given")
        return _hmac(key, text)


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------


def delete_profile(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Delete a user's profile file. Return ``{"user_hash", "profile_sha256", "deleted"}`` (no path, no id).

    The file is removed from the file system. Copies elsewhere (backups, a synced folder, an SSD's spare
    blocks) are not reached: the operator's retention process must cover them.
    """
    p = Path(path)
    data = p.read_bytes()
    try:
        user_hash = json.loads(data.decode("utf-8")).get("user_hash")
    except (ValueError, UnicodeDecodeError):
        user_hash = None
    sha = hashlib.sha256(data).hexdigest()
    p.unlink()
    return {"user_hash": user_hash, "profile_sha256": sha, "deleted": not p.exists()}


def erase(
    *,
    request_ref: str,
    profile: str | os.PathLike[str] | None = None,
    ledgers: Sequence[str | os.PathLike[str]] = (),
    subject_id: str | None = None,
    ledger_key: bytes | None = None,
    reason: str = "erasure-request",
    outputs: Sequence[str | os.PathLike[str]] = (),
    output_templates: Sequence[str] = (),
    subject_indexes: Sequence[str | os.PathLike[str]] = (),
    index_key: bytes | None = None,
    sessions: Sequence[str] = (),
) -> dict[str, Any]:
    """Carry out one erasure request: delete the profile, redact the subject in each ledger. Return a receipt.

    P5-15: ``outputs`` (Collector decision logs, NTS stream files, ``os_text`` logs), ``output_templates``
    (per-session paths with ``{session}``) and ``subject_indexes`` (with the privacy key ``index_key``) also
    lose the subject's items (:func:`fidetype.trust.erasure.erase_outputs`); ``sessions`` adds session ids
    directly. The receipt then has ``outputs`` (no path, no session id, no subject id).

    ``subject_id``: the stream ``subject.id`` of the person (pseudonymous; it is not written to the receipt).
    A ledger without a decision of the subject is listed with ``n_redacted = 0``. The receipt
    (``fidetype.deletion-receipt/1.0``) holds the request reference, the time, the profile's user hash and
    digest, and per ledger its id, the redaction entry (seq, hash), the count and the new head.
    """
    from fidetype.trust.provenance import ProvenanceLedger, verify

    check_opaque_ref(request_ref, "request_ref")
    rec: dict[str, Any] = {"schema": RECEIPT_SCHEMA, "request_ref": request_ref, "time_utc": _now(),
                           "reason": reason, "profile": None, "ledgers": []}
    if profile is not None:
        rec["profile"] = delete_profile(profile)
    for lp in ledgers:
        led = ProvenanceLedger(lp, hash_key=ledger_key)
        row: dict[str, Any] = {"ledger_id": led.ledger_id, "n_redacted": 0}
        if subject_id is not None:
            try:
                e = led.redact_subject(subject_id, request_ref=request_ref, reason=reason)
                row.update(n_redacted=e["body"]["n"], redaction_seq=e["seq"], redaction_hash=e["hash"])
            except ValueError as ex:
                if "no decision of this subject" not in str(ex):
                    raise
        res = verify(lp)
        row.update(verify_ok=res.ok, head=led.anchor())
        rec["ledgers"].append(row)
    if outputs or output_templates or subject_indexes or sessions:
        from fidetype.trust.erasure import erase_outputs

        rec["outputs"] = erase_outputs(subject_id=subject_id, key=index_key, indexes=subject_indexes,
                                       sessions=sessions, files=outputs, templates=output_templates)
    return rec


def outputs_ok(rec: Mapping[str, Any]) -> bool:
    """True when no rewritten output file of the receipt lost conformance (``nts-conform`` ok before -> after)."""
    for r in (rec.get("outputs") or {}).get("files", ()):
        c = r.get("conform")
        if c and c.get("before") and c["before"].get("ok") and c.get("after") and not c["after"].get("ok"):
            return False
    return True


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidetype.trust.privacy")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cp = sub.add_parser("check-policy", help="load a privacy policy file and print its rules")
    cp.add_argument("path")
    cr = sub.add_parser("check-consent-ref", help="check that a consent reference is opaque")
    cr.add_argument("ref")
    er = sub.add_parser("erase", help="delete a profile and redact a subject in ledgers; print a receipt")
    er.add_argument("--request-ref", required=True)
    er.add_argument("--profile", default=None)
    er.add_argument("--ledger", action="append", default=[])
    er.add_argument("--subject-env", default=None, help="environment variable that holds the subject.id")
    er.add_argument("--ledger-key-env", default=None, help="environment variable with the ledgers' hash key")
    er.add_argument("--reason", default="erasure-request")
    er.add_argument("--receipt", default=None, help="write the receipt JSON here")
    er.add_argument("--output", action="append", default=[],
                    help="Collector output file: decision log, NTS stream file or os_text log (repeat)")
    er.add_argument("--output-template", action="append", default=[],
                    help="per-session output path with {session}; each session's file is deleted (repeat)")
    er.add_argument("--subject-index", action="append", default=[],
                    help="subject index file of a privacy processor (repeat); needs --index-key-env")
    er.add_argument("--index-key-env", default=None,
                    help="environment variable with the privacy key of the subject index (HMAC codes)")
    er.add_argument("--sessions-env", default=None,
                    help="environment variable with comma-separated session ids to erase (not on the command line)")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    try:
        if a.cmd == "check-policy":
            pol = PrivacyPolicy.load(a.path)
            print(json.dumps({"id": pol.id, "default": pol.default, "text": pol.text, "scan_pii": pol.scan_pii,
                              "needs_key": pol.needs_key, "exact": pol.exact, "patterns": dict(pol.prefixes)},
                             indent=1))
            return 0
        if a.cmd == "check-consent-ref":
            check_consent_ref(a.ref)
            print("OK: opaque consent reference")
            return 0
        subj = os.environ.get(a.subject_env) if a.subject_env else None
        if a.subject_env and not subj:
            print(f"environment variable {a.subject_env} is empty", file=sys.stderr)
            return 2
        key = os.environ.get(a.ledger_key_env, "").encode("utf-8") if a.ledger_key_env else None
        ikey = os.environ.get(a.index_key_env, "").encode("utf-8") if a.index_key_env else None
        if a.subject_index and not ikey:
            print("--subject-index needs --index-key-env (a non-empty key)", file=sys.stderr)
            return 2
        sess = [s.strip() for s in os.environ.get(a.sessions_env, "").split(",") if s.strip()] if a.sessions_env else []
        rec = erase(request_ref=a.request_ref, profile=a.profile, ledgers=a.ledger, subject_id=subj,
                    ledger_key=key or None, reason=a.reason, outputs=a.output, output_templates=a.output_template,
                    subject_indexes=a.subject_index, index_key=ikey or None, sessions=sess)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    txt = json.dumps(rec, indent=1)
    if a.receipt:
        Path(a.receipt).write_text(txt + "\n", encoding="utf-8")
    print(txt)
    return 0 if all(r.get("verify_ok") for r in rec["ledgers"]) and outputs_ok(rec) else 1


if __name__ == "__main__":
    raise SystemExit(main())
