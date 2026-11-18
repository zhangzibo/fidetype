"""Signed anchors of the provenance ledger head (P5-14).

The hash chain of :mod:`fidetype.trust.provenance` is tamper-evident, not
tamper-proof: a person who can rewrite the whole ledger can recompute every
hash, and can also rewrite a plain anchor file. A **signed anchor** closes
that gap. The operator signs the head (ledger id, ``seq``, ``hash``) with an
Ed25519 private key that is kept outside the ledger and outside the
repository. A verifier needs only the public key. A rewritten ledger with a
recomputed chain then fails: its head differs from the signed head, and a
new anchor for the new head cannot be signed without the private key.

Anchor format (``fidetype.ledger-anchor/1.0``)::

    {"schema": "fidetype.ledger-anchor/1.0", "ledger_id": "...", "seq": 41, "hash": "<64 hex>",
     "ts": "<time of the head entry>", "n_entries": 42,
     "signature": {"alg": "ed25519", "key_id": "ed25519:<16 hex>", "value": "<base64>"}}

The signature covers the canonical JSON (:func:`fidetype.trust.provenance.canonical_json`) of the anchor
without ``signature`` (:func:`anchor_payload`). ``key_id`` is the first 16 hex characters of the SHA-256 of
the raw public key; it names the key, it is not a secret.

Redaction (P5-04) keeps the entry hashes (tombstones), so an anchor stays valid after an erasure.

The ledger may grow after the anchor. :func:`verify_anchored` with ``allow_growth=True`` checks that the
anchored entry is still in the chain at its ``seq`` with its ``hash``; the chain then authenticates every
entry up to the anchor. Entries after the anchor need a later anchor.

External stores (no code here, no network call): keep a copy of the anchor on a second host, or get an
RFC 3161 timestamp token for the anchor file from a timestamp authority (for example with
``openssl ts -query -data anchor.json -sha256 -cert``) and check it with ``openssl ts -verify``. See
``docs/provenance-and-privacy.md``.

Automatic anchors (P5-16): :class:`AutoAnchor` listens to a ledger and writes a signed anchor file
``anchor-<seq>.json`` into a separate directory every N entries, every T seconds (when there are new entries)
and at stop. The Collector ``trust`` processor option ``ledger.anchor`` uses it. ``verify --anchor <directory>
--allow-growth --public-key ...`` checks the newest anchor of the directory.

Needs the optional package ``cryptography`` (``pip install "fidetype[sign]"``) for keys and signatures.
An unsigned anchor works without it.
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

ANCHOR_SCHEMA = "fidetype.ledger-anchor/1.0"
SIG_ALG = "ed25519"


class SigningUnavailable(RuntimeError):
    """The optional package ``cryptography`` is not installed."""


def _crypto() -> Any:
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise SigningUnavailable('signed anchors need the package cryptography: pip install "fidetype[sign]"') from e
    return ed25519


def signing_available() -> bool:
    try:
        _crypto()
    except SigningUnavailable:
        return False
    return True


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------


def generate_key() -> tuple[bytes, bytes]:
    """A new Ed25519 key pair as ``(private PEM (PKCS#8, unencrypted), public PEM)``.

    Keep the private PEM in a secret store or a file with owner-only access, never in a repository.
    """
    from cryptography.hazmat.primitives import serialization as S

    priv = _crypto().Ed25519PrivateKey.generate()
    pem = priv.private_bytes(S.Encoding.PEM, S.PrivateFormat.PKCS8, S.NoEncryption())
    pub = priv.public_key().public_bytes(S.Encoding.PEM, S.PublicFormat.SubjectPublicKeyInfo)
    return pem, pub


def _private(key: Any) -> Any:
    ed = _crypto()
    if isinstance(key, ed.Ed25519PrivateKey):
        return key
    from cryptography.hazmat.primitives import serialization as S

    k = S.load_pem_private_key(key if isinstance(key, bytes) else str(key).encode("utf-8"), password=None)
    if not isinstance(k, ed.Ed25519PrivateKey):
        raise ValueError("the signing key is not an Ed25519 private key")
    return k


def _public(key: Any) -> Any:
    ed = _crypto()
    if isinstance(key, ed.Ed25519PublicKey):
        return key
    if isinstance(key, ed.Ed25519PrivateKey):
        return key.public_key()
    from cryptography.hazmat.primitives import serialization as S

    k = S.load_pem_public_key(key if isinstance(key, bytes) else str(key).encode("utf-8"))
    if not isinstance(k, ed.Ed25519PublicKey):
        raise ValueError("the public key is not an Ed25519 public key")
    return k


def key_id(public_key: Any) -> str:
    """``"ed25519:" + sha256(raw public key)[:16]``. Accepts a PEM or a key object (private or public)."""
    from cryptography.hazmat.primitives import serialization as S

    raw = _public(public_key).public_bytes(S.Encoding.Raw, S.PublicFormat.Raw)
    return f"{SIG_ALG}:{hashlib.sha256(raw).hexdigest()[:16]}"


def write_key_pair(private_path: str | os.PathLike[str], public_path: str | os.PathLike[str]) -> str:
    """Generate a key pair and write the two PEM files (the private one with owner-only access where the OS
    supports it). Refuse to overwrite a file. Return the key id."""
    pp, qp = Path(private_path), Path(public_path)
    for p in (pp, qp):
        if p.exists():
            raise FileExistsError(f"{p} exists; refusing to overwrite a key file")
    pem, pub = generate_key()
    fd = os.open(pp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    qp.write_bytes(pub)
    return key_id(pub)


# ---------------------------------------------------------------------------
# Anchors
# ---------------------------------------------------------------------------


def make_anchor(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The anchor of a ledger's head (unsigned). The caller checks the chain first."""
    g = entries[0].get("body") or {}
    last = entries[-1]
    return {"schema": ANCHOR_SCHEMA, "ledger_id": g.get("ledger_id"), "seq": last.get("seq"),
            "hash": last.get("hash"), "ts": last.get("ts"), "n_entries": len(entries)}


def anchor_payload(anchor: Mapping[str, Any]) -> bytes:
    """The bytes that the signature covers: canonical JSON of the anchor without ``signature``."""
    from fidetype.trust.provenance import canonical_json

    return canonical_json({k: v for k, v in anchor.items() if k != "signature"}).encode("utf-8")


def sign_anchor(anchor: Mapping[str, Any], private_key: Any) -> dict[str, Any]:
    """Return a copy of ``anchor`` with an Ed25519 ``signature`` (``private_key``: PEM bytes / str or key)."""
    k = _private(private_key)
    a = {kk: v for kk, v in anchor.items() if kk != "signature"}
    a.setdefault("schema", ANCHOR_SCHEMA)
    sig = k.sign(anchor_payload(a))
    a["signature"] = {"alg": SIG_ALG, "key_id": key_id(k), "value": base64.b64encode(sig).decode("ascii")}
    return a


def check_signature(anchor: Mapping[str, Any], public_key: Any) -> list[str]:
    """Errors of the anchor's signature against ``public_key`` (an empty list: the signature is good)."""
    from cryptography.exceptions import InvalidSignature

    s = anchor.get("signature")
    if not isinstance(s, dict):
        return ["anchor is not signed"]
    if s.get("alg") != SIG_ALG:
        return [f"unknown signature algorithm {s.get('alg')!r} (known: {SIG_ALG})"]
    pub = _public(public_key)
    errs: list[str] = []
    if s.get("key_id") != key_id(pub):
        errs.append(f"signature key_id {s.get('key_id')!r} is not the key id of the given public key "
                    f"({key_id(pub)})")
    try:
        sig = base64.b64decode(str(s.get("value", "")), validate=True)
        pub.verify(sig, anchor_payload(anchor))
    except (InvalidSignature, ValueError):
        errs.append("anchor signature does not verify (the anchor was changed or signed with another key)")
    return errs


def verify_anchored(
    source: Any,
    anchor: Mapping[str, Any],
    public_key: Any = None,
    *,
    allow_growth: bool = False,
    require_signature: bool | None = None,
) -> Any:
    """Verify a ledger against an anchor: signature, ledger id, the anchored entry, then the whole chain.

    ``public_key``: PEM (bytes / str) or key object. ``require_signature`` (default: True when
    ``public_key`` is given or the anchor is signed): fail on an unsigned anchor, and fail on a signed anchor
    when no public key is given (a signature that nobody checks proves nothing). ``allow_growth``: the
    ledger may hold entries after the anchor; else the head must be the anchored entry (detects a cut and an
    addition at the end). Returns a :class:`fidetype.trust.provenance.VerifyResult`.
    """
    from fidetype.trust.provenance import VerifyResult, read_entries, verify

    try:
        entries = list(source) if not isinstance(source, (str, os.PathLike)) else read_entries(source)
    except ValueError as e:
        return VerifyResult(False, 0, [str(e)])
    res = verify(entries)
    errors = list(res.errors)
    signed = isinstance(anchor.get("signature"), dict)
    need = (public_key is not None or signed) if require_signature is None else require_signature
    if need:
        if public_key is None:
            errors.append("signed anchor: give the public key to check the signature")
        elif not signed:
            errors.append("anchor is not signed")
        else:
            errors += check_signature(anchor, public_key)
    if entries:
        g = entries[0].get("body") if isinstance(entries[0].get("body"), dict) else {}
        if anchor.get("ledger_id") is not None and g.get("ledger_id") != anchor.get("ledger_id"):
            errors.append("ledger_id differs from the anchor's ledger_id (another ledger, or a new genesis)")
        s = anchor.get("seq")
        if not isinstance(s, int) or not 0 <= s < len(entries):
            errors.append(f"anchored entry seq {s!r} is not in the ledger (entries cut at the end)")
        elif entries[s].get("seq") != s or entries[s].get("hash") != anchor.get("hash"):
            errors.append(f"entry seq {s} has another hash than the anchor (ledger rewritten)")
        elif not allow_growth and len(entries) != s + 1:
            errors.append(f"{len(entries) - s - 1} entries after the anchored head (pass allow_growth to accept "
                          "entries added after the anchor)")
    return VerifyResult(not errors, len(entries), errors, res.head_hash, res.head_seq)


# ---------------------------------------------------------------------------
# Automatic signed anchors (P5-16)
# ---------------------------------------------------------------------------

#: File name of an automatic anchor: ``anchor-<seq, 10 digits>.json`` (the newest has the highest seq).
AUTO_ANCHOR_PREFIX = "anchor-"


def load_private_key(*, key_env: str | None = None, key_file: str | os.PathLike[str] | None = None) -> Any:
    """Load an Ed25519 private key from an environment variable (PEM text) or a PEM file. Exactly one source.

    The error messages name the variable or the file, never the key.
    """
    if (key_env is None) == (key_file is None):
        raise ValueError("give exactly one of key_env (an environment variable) and key_file (a PEM file)")
    if key_env is not None:
        pem = os.environ.get(key_env, "")
        if not pem:
            raise ValueError(f"environment variable {key_env!r} that should hold the anchor signing key is empty "
                             "or not set")
        data = pem.encode("utf-8")
    else:
        p = Path(key_file)  # type: ignore[arg-type]
        if not p.is_file():
            raise ValueError(f"anchor signing key file not found: {p}")
        data = p.read_bytes()
    try:
        return _private(data)
    except SigningUnavailable:
        raise
    except (ValueError, TypeError):
        src = f"environment variable {key_env!r}" if key_env is not None else f"file {key_file}"
        raise ValueError(f"{src}: not an Ed25519 private key in PEM form") from None


def anchor_files(directory: str | os.PathLike[str], ledger_id: str | None = None) -> list[Path]:
    """The automatic anchor files of ``directory``, oldest first (by anchored ``seq``).

    ``ledger_id``: keep only the anchors of that ledger. A file that is not an anchor is skipped.
    """
    import json

    d = Path(directory)
    if not d.is_dir():
        return []
    out: list[tuple[int, str, Path]] = []
    for p in d.glob(f"{AUTO_ANCHOR_PREFIX}*.json"):
        try:
            a = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(a, dict) or a.get("schema") != ANCHOR_SCHEMA or not isinstance(a.get("seq"), int):
            continue
        if ledger_id is not None and a.get("ledger_id") != ledger_id:
            continue
        out.append((a["seq"], p.name, p))
    return [p for _, _, p in sorted(out)]


def newest_anchor(path: str | os.PathLike[str], ledger_id: str | None = None) -> dict[str, Any]:
    """Read an anchor file, or the newest automatic anchor (highest ``seq``) of a directory."""
    import json

    p = Path(path)
    if p.is_dir():
        files = anchor_files(p, ledger_id)
        if not files:
            raise ValueError(f"no anchor file ({AUTO_ANCHOR_PREFIX}*.json) in {p}")
        p = files[-1]
    a = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(a, dict):
        raise ValueError(f"{p}: an anchor must be a JSON object")
    return a


class AutoAnchor:
    """Write signed anchors of a :class:`~fidetype.trust.provenance.ProvenanceLedger` by itself (P5-16).

    An anchor is written after every ``every_n`` new entries, when ``every_s`` seconds have passed since the
    last anchor and there are new entries (checked at each new entry and at each :meth:`tick`), and at
    :meth:`close` (``on_stop``). Each anchor is a separate file ``anchor-<seq>.json`` in ``directory`` (atomic
    write; an older anchor is never changed). ``verify --anchor <directory> --allow-growth`` checks the newest.

    ``private_key``: PEM bytes / str or a key object; load it with :func:`load_private_key` (environment
    variable or key file). The key is never written to an anchor, a log or an error message.
    ``keep``: keep only the newest ``keep`` anchor files of this ledger (None: keep all).
    """

    def __init__(self, ledger: Any, private_key: Any, directory: str | os.PathLike[str], *,
                 every_n: int | None = None, every_s: float | None = None, on_stop: bool = True,
                 keep: int | None = None, clock: Any = None) -> None:
        import time

        if every_n is not None and (isinstance(every_n, bool) or not isinstance(every_n, int) or every_n < 1):
            raise ValueError("every_n must be an integer >= 1")
        if every_s is not None and not every_s > 0:
            raise ValueError("every_s must be > 0")
        if keep is not None and (isinstance(keep, bool) or not isinstance(keep, int) or keep < 1):
            raise ValueError("keep must be an integer >= 1")
        self.ledger = ledger
        self._key = _private(private_key)
        self.key_id = key_id(self._key)
        self.directory = Path(directory)
        self.every_n, self.every_s, self.on_stop, self.keep = every_n, every_s, on_stop, keep
        self._clock = clock or time.monotonic
        self._last_t = self._clock()
        self._busy = False
        self.closed = False
        #: seq of the newest written anchor (None: none yet), and the number of anchors written.
        self.last_seq: int | None = None
        self.written = 0
        ledger.on_append.append(self._after_append)

    def __enter__(self) -> "AutoAnchor":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __repr__(self) -> str:  # never shows the key
        return f"AutoAnchor(key_id={self.key_id!r}, directory={str(self.directory)!r}, written={self.written})"

    @property
    def pending(self) -> int:
        """Entries after the newest anchor."""
        head = self.ledger.head["seq"]
        return head + 1 if self.last_seq is None else head - self.last_seq

    def _due(self) -> bool:
        n = self.pending
        if n <= 0:
            return False
        if self.every_n is not None and n >= self.every_n:
            return True
        return self.every_s is not None and self._clock() - self._last_t >= self.every_s

    def _after_append(self, entry: Mapping[str, Any]) -> None:
        if not self._busy and not self.closed and self._due():
            self.write()

    def tick(self) -> Path | None:
        """Check the timer (call it from a loop). Return the written file, or None."""
        if not self.closed and self._due():
            return self.write()
        return None

    def write(self) -> Path | None:
        """Sign and write the anchor of the current head now. Return the file (None: no new entry)."""
        import json

        if self.pending <= 0:
            return None
        self._busy = True
        try:
            anc = sign_anchor(make_anchor(self.ledger.entries), self._key)
            self.directory.mkdir(parents=True, exist_ok=True)
            p = self.directory / f"{AUTO_ANCHOR_PREFIX}{int(anc['seq']):010d}.json"
            tmp = p.with_name(p.name + ".tmp")
            tmp.write_text(json.dumps(anc, indent=1) + "\n", encoding="utf-8")
            os.replace(tmp, p)
            self.last_seq = int(anc["seq"])
            self._last_t = self._clock()
            self.written += 1
            if self.keep is not None:
                for old in anchor_files(self.directory, self.ledger.ledger_id)[:-self.keep]:
                    old.unlink(missing_ok=True)
            return p
        finally:
            self._busy = False

    def close(self) -> Path | None:
        """Write the last anchor (``on_stop``) and stop listening to the ledger."""
        if self.closed:
            return None
        p = self.write() if self.on_stop else None
        self.closed = True
        try:
            self.ledger.on_append.remove(self._after_append)
        except ValueError:
            pass
        return p

    def stats(self) -> dict[str, Any]:
        return {"anchors_written": self.written, "last_anchor_seq": self.last_seq, "key_id": self.key_id}
