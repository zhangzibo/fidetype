"""Erasure in Collector output files (P5-15).

P5-04 erases a person's profile and ledger entries. The Collector also writes plain output files: JSON Lines
decision logs, NTS streams (``jsonl`` exporter with input event types, for example after a ``guard`` with
``passthrough``), and the ``os_text`` stub log. This module removes one subject's items from those files.

How the Collector links a subject to its outputs
-----------------------------------------------
1. **Subject index.** The ``privacy`` processor option ``subject_index = "out/subject-index.jsonl"`` writes one
   line per stream header that names a ``subject.id``: ``{"schema": "fidetype.subject-index/1.0",
   "session": <stream id>, "subject": "h:" + HMAC-SHA256(key, subject.id)[:32]}``. The key is the privacy key
   (``key_env``). The raw ``subject.id`` is never written. The policy can still drop ``subject.id`` from the
   headers; the index keeps the link.
2. **Per-session files.** A ``jsonl`` exporter path may hold ``{session}``, for example
   ``out/streams/{session}.nts.jsonl``: one file per stream (or per decision session). An erasure deletes
   the whole file. :func:`session_token` gives the file-name form of a session id.

What an erasure does with each file kind
----------------------------------------
============================  ======================================================================
File                          Action
============================  ======================================================================
per-session file (template)   deleted (all items in it belong to the session)
NTS stream file (header)      deleted when the header ``meta["subject.id"]`` is the subject (raw id
                              or its ``h:`` code); else unchanged
decision log                  the subject's ``trust_decision`` lines (by ``session``) are removed;
                              the other lines stay byte for byte
``os_text`` stub log          the lines whose ``decision.session`` is the subject's are removed
subject index                 the subject's lines are removed
other files                   unchanged (reported as ``unknown``)
============================  ======================================================================

A file is rewritten atomically (temporary file + rename). A file with no line left is deleted (an empty
file is not an NTS decision log). Decision-log rules are per session (TD-5 ... TD-7), so removing whole
sessions keeps the other sessions conformant: the receipt holds the ``nts-conform`` result before and after
for each rewritten file.

The receipt part (:func:`erase_outputs`) holds, per file, its position in the request, the form, the
action, the counts, the SHA-256 before and after, and the conformance result. It holds no path, no session
id and no subject id.

Not reached: copies outside these files (backups, synced folders), live channels (WebSocket ``/decisions``,
LSL outlets, standard output) and the metrics file (counts only; it holds no id and no text).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable, Sequence

INDEX_SCHEMA = "fidetype.subject-index/1.0"
SESSION_PLACEHOLDER = "{session}"
_SAFE = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9._-]{0,63}$")


def subject_code(subject_id: str, key: bytes) -> str:
    """``"h:" + HMAC-SHA256(key, subject_id)[:32]``: the same code as a privacy policy ``hash`` rule."""
    return "h:" + hmac.new(key, subject_id.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def session_token(session: str) -> str:
    """The file-name form of a session id: unchanged when it is safe (letters, digits, ``. _ -``, at most 64
    characters, no leading dot), else the unsafe characters become ``_`` and a short hash is added (so
    ``a/b`` and ``a_b`` give different names)."""
    s = str(session)
    if _SAFE.match(s):
        return s
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)[:48].lstrip(".") + "-" + hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def session_path(template: str, session: str) -> str:
    """The path of a per-session output file: ``template`` with ``{session}`` replaced by :func:`session_token`."""
    return template.replace(SESSION_PLACEHOLDER, session_token(session))


def index_line(session: str, code: str) -> dict[str, Any]:
    return {"schema": INDEX_SCHEMA, "session": str(session), "subject": code}


def sessions_in_index(paths: Iterable[str | os.PathLike[str]], code: str) -> set[str]:
    """The sessions that the subject index files link to the subject code ``code``."""
    out: set[str] = set()
    for p in paths:
        p = Path(p)
        if not p.is_file():
            continue
        for raw in p.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(raw)
            except ValueError:
                continue
            if isinstance(o, dict) and o.get("schema") == INDEX_SCHEMA and o.get("subject") == code:
                out.add(str(o.get("session")))
    return out


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _conform(path: Path) -> dict[str, Any] | None:
    from fidetype.conformance.nts_conform import InputError, conform_file

    try:
        tr = conform_file(path)
    except InputError:
        return None
    return {"form": tr.form, "ok": not tr.fails, "verdict": tr.verdict, "stream_level": tr.stream_level}


def _rewrite(path: Path, lines: list[str]) -> None:
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.writelines(lines)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _classify(objs: list[Any]) -> str:
    dicts = [o for o in objs if isinstance(o, dict)]
    if not dicts:
        return "unknown"
    if dicts[0].get("type") == "header":
        return "nts-stream"
    if all(o.get("schema") == INDEX_SCHEMA for o in dicts):
        return "subject-index"
    if all("typed" in o and isinstance(o.get("decision"), dict) for o in dicts):
        return "os-text-log"
    if all(o.get("type") == "trust_decision" for o in dicts):
        return "decision-log"
    return "unknown"


def _erase_file(path: Path, sessions: set[str], ids: set[str], codes: set[str], check: bool) -> dict[str, Any]:
    data = path.read_bytes()
    row: dict[str, Any] = {"sha256_before": _sha(data)}
    lines = data.decode("utf-8").splitlines(keepends=True)
    objs: list[Any] = []
    for raw in lines:
        try:
            objs.append(json.loads(raw) if raw.strip() else None)
        except ValueError:
            objs.append(None)
    form = _classify(objs)
    row["form"] = form
    drop = [False] * len(lines)
    if form == "nts-stream":
        meta = objs[0].get("meta") if isinstance(objs[0], dict) else None
        sub = meta.get("subject.id") if isinstance(meta, dict) else None
        if isinstance(sub, str) and (sub in ids or sub in codes):
            drop = [True] * len(lines)
    for i, o in enumerate(objs):
        if not isinstance(o, dict):
            continue
        if form == "decision-log":
            drop[i] = str(o.get("session")) in sessions
        elif form == "os-text-log":
            drop[i] = str(o["decision"].get("session")) in sessions
        elif form == "subject-index":
            drop[i] = str(o.get("session")) in sessions or o.get("subject") in codes
    n_rm = sum(1 for i, d in enumerate(drop) if d and objs[i] is not None)
    keep = [raw for raw, d in zip(lines, drop) if not d]
    n_keep = sum(1 for raw in keep if raw.strip())
    row.update(n_removed=n_rm, n_kept=n_keep)
    if not n_rm:
        row.update(action="unchanged", sha256_after=row["sha256_before"])
        return row
    conf_before = _conform(path) if check and form in ("nts-stream", "decision-log") else None
    if n_keep == 0:
        path.unlink()
        row.update(action="deleted", sha256_after=None)
    else:
        _rewrite(path, keep)
        row.update(action="rewritten", sha256_after=_sha(path.read_bytes()))
    if conf_before is not None:
        row["conform"] = {"before": conf_before, "after": _conform(path) if path.exists() else None}
    return row


def erase_outputs(
    *,
    subject_id: str | None = None,
    key: bytes | None = None,
    indexes: Sequence[str | os.PathLike[str]] = (),
    sessions: Iterable[str] = (),
    files: Sequence[str | os.PathLike[str]] = (),
    templates: Sequence[str] = (),
    check_conformance: bool = True,
) -> dict[str, Any]:
    """Remove one subject's items from Collector output files. Return the receipt part (no path, no id).

    The subject's sessions are ``sessions`` plus the sessions that the ``indexes`` link to
    ``subject_code(subject_id, key)``. ``files``: decision logs, NTS stream files, ``os_text`` logs (any
    order; the form is detected). ``templates``: per-session paths with ``{session}``; the file of each
    session is deleted. The index files themselves lose the subject's lines at the end.
    """
    sess = {str(s) for s in sessions}
    codes: set[str] = set()
    ids: set[str] = set()
    if subject_id is not None:
        ids.add(subject_id)
        if key:
            codes.add(subject_code(subject_id, key))
    if indexes:
        if subject_id is not None and not key:
            raise ValueError("a subject index needs the privacy key (the index holds HMAC codes, not ids)")
        for c in codes:
            sess |= sessions_in_index(indexes, c)
    out: dict[str, Any] = {"n_sessions": len(sess), "files": [], "templates": [], "indexes": []}
    for i, f in enumerate(files, 1):
        p = Path(f)
        row = {"output": i, **(_erase_file(p, sess, ids, codes, check_conformance) if p.is_file()
                                 else {"form": None, "action": "missing"})}
        out["files"].append(row)
    for j, t in enumerate(templates, 1):
        if SESSION_PLACEHOLDER not in str(t):
            raise ValueError(f"template {j} has no {SESSION_PLACEHOLDER} placeholder")
        digests = []
        for s in sorted(sess):
            p = Path(session_path(str(t), s))
            if p.is_file():
                digests.append(_sha(p.read_bytes()))
                p.unlink()
        out["templates"].append({"template": j, "action": "deleted" if digests else "unchanged",
                                 "n_files_deleted": len(digests), "sha256_deleted": sorted(digests)})
    for k, ip in enumerate(indexes, 1):
        p = Path(ip)
        row = {"index": k, **(_erase_file(p, sess, ids, codes, False) if p.is_file()
                              else {"form": None, "action": "missing"})}
        out["indexes"].append(row)
    return out
