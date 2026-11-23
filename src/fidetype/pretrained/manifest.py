"""Model manifests of the pretrained decoders (P14-01).

A manifest is one JSON file per model in ``fidetype/pretrained/manifests/``. It ships in the
package. The weights do not: they load from a local path or from the cache folder, and each file
is checked against the SHA-256 and the size in the manifest.

Manifest keys (schema ``fidetype.pretrained-manifest/0.1``)::

    name, version, title, status ("available" | "planned"), task, modality, runtime,
    input        {kind, channels, sample_rate_hz | bin_s, file_formats, ...}
    output       {vocab_type, vocab_id, frame_period_s, latency_s}
    architecture {runtime-specific settings}
    files        [{role, name, sha256, size, url}]      role: weights | card | guard | text
    licence      {"data.licence": SPDX, "data.research_only": bool,     (FEP-0010 keys)
                  weights, weights_status, attribution, share_alike, notes}
    training     {data, doi, split, run, checkpoint_sha256}
    metrics      [{name, split, value, source}]
    limits       [str]
    trust        {config (packaged file or file role), decode, alpha, ..., offer_control} | null
                 offer_control (optional, P14-56): the P5-31 offer null control of the saved guard,
                 {verdict "pass" | "fail", mode, checked, rule, real {n, n_offer},
                  controls [{name, label, n, n_offer, p_value, passed}], ltt_commits,
                  commits_match_sheet, effect, source}; a readout guard has its own copy in
                 readouts.<name>.trust.offer_control
                 Offer-control policy (user decision 2026-11-22, gap 152): the default of
                 fidetype.trust.calibrate stays offer_control="warn"; a trust block that ships an
                 offer_gate is held to "refuse": it must carry an offer_control block with verdict
                 "pass", or the manifest is refused (ManifestError)
    hosting      {host, release, notes}   (the download URL slot; null until P14-02)

``licence["data.licence"]`` and ``licence["data.research_only"]`` use the stream keys of FEP-0010
(NTS 1.0 RC4 amendment 6). A model with ``data.research_only = true`` loads only after an explicit
opt-in (:func:`fidetype.pretrained.load` with ``accept_research_only=True``), like the collector's
``refuse_research_only`` gate.

Our own code (Apache-2.0).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

from fidetype.trust.licence import META_LICENCE, META_RESEARCH_ONLY, combine, normalise, source_summary

__all__ = ["MANIFEST_SCHEMA", "FILE_ROLES", "STATUSES", "OFFER_VERDICTS",
           "ManifestError", "FileEntry", "Manifest", "manifest_dir",
           "load_manifest", "all_manifests", "parse_manifest"]

MANIFEST_SCHEMA = "fidetype.pretrained-manifest/0.1"
FILE_ROLES = ("weights", "card", "guard", "text")
STATUSES = ("available", "planned")
OFFER_VERDICTS = ("pass", "fail")
_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]{1,63}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ManifestError(ValueError):
    """A manifest is not valid."""


@dataclass(frozen=True)
class FileEntry:
    """One release file of a model."""

    role: str
    name: str
    sha256: str
    size: int
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "name": self.name, "sha256": self.sha256, "size": self.size, "url": self.url}


@dataclass(frozen=True)
class Manifest:
    """A parsed, checked manifest. ``raw`` keeps the full JSON document."""

    name: str
    version: str
    title: str
    status: str
    task: str
    modality: str
    runtime: str
    files: tuple[FileEntry, ...]
    licence: dict[str, Any]
    raw: dict[str, Any] = field(repr=False)

    @property
    def data_licence(self) -> str:
        return str(self.licence[META_LICENCE])

    @property
    def research_only(self) -> bool:
        return bool(self.licence[META_RESEARCH_ONLY])

    @property
    def language(self) -> str:
        """BCP 47 tag of the decoded text (manifest key ``language``; absent = ``en``, P14-34)."""
        return str(self.raw.get("language") or "en")

    @property
    def input(self) -> dict[str, Any]:
        return dict(self.raw.get("input") or {})

    @property
    def output(self) -> dict[str, Any]:
        return dict(self.raw.get("output") or {})

    @property
    def architecture(self) -> dict[str, Any]:
        return dict(self.raw.get("architecture") or {})

    @property
    def trust(self) -> dict[str, Any] | None:
        t = self.raw.get("trust")
        return dict(t) if t else None

    @property
    def offer_controls(self) -> dict[str, dict[str, Any]]:
        """The P5-31 offer null control of each packaged guard (P14-56).

        Key ``"default"`` is the guard of ``trust``; key ``"<readout>"`` is the guard of
        ``readouts.<readout>.trust``. A guard without a recorded check is not in the dict.
        """
        return {k: dict(v) for k, v in _offer_blocks(self.raw)}

    @property
    def metrics(self) -> list[dict[str, Any]]:
        return list(self.raw.get("metrics") or [])

    @property
    def limits(self) -> list[str]:
        return list(self.raw.get("limits") or [])

    def files_of(self, role: str) -> list[FileEntry]:
        return [f for f in self.files if f.role == role]

    def file(self, role: str) -> FileEntry:
        fs = self.files_of(role)
        if len(fs) != 1:
            raise ManifestError(f"{self.name}: expected one file with role {role!r}, found {len(fs)}")
        return fs[0]

    @property
    def weights_sha256(self) -> str | None:
        fs = self.files_of("weights")
        return fs[0].sha256 if fs else None

    def licence_meta(self) -> dict[str, Any]:
        """The FEP-0010 ``meta`` keys of every stream this model writes."""
        return {META_LICENCE: self.data_licence, META_RESEARCH_ONLY: self.research_only}

    def card(self) -> str:
        """A short, human-readable model card."""
        r = self.raw
        lic = self.licence
        lines = [f"{self.name} v{self.version}: {self.title}", f"  status:   {self.status}",
                 f"  task:     {self.task}", f"  modality: {self.modality}",
                 f"  data:     {(r.get('training') or {}).get('data', '-')}",
                 f"  licence:  data {self.data_licence}; research_only {str(self.research_only).lower()}; "
                 f"weights {lic.get('weights') or '-'} ({lic.get('weights_status') or '-'})"]
        if lic.get("attribution"):
            lines.append(f"  attribution: {lic['attribution']}")
        for f in self.files:
            lines.append(f"  file:     {f.role:<7} {f.name}  {f.size} bytes  sha256 {f.sha256[:16]}...")
        for m in self.metrics:
            lines.append(f"  metric:   {m.get('name')} = {m.get('value')} ({m.get('split')})")
        for lim in self.limits:
            lines.append(f"  limit:    {lim}")
        if self.trust:
            lines.append(f"  trust:    {self.trust.get('config')} (decode: {self.trust.get('decode')})")
        else:
            lines.append("  trust:    no committed trust config")
        for key, t in _trust_blocks(r):
            g = t.get("offer_gate")
            if isinstance(g, Mapping):
                where = "" if key == "default" else f" (readout {key})"
                lines.append(f"  offer gate{where}: withhold an offer if {g.get('feature')} < "
                             f"{g.get('threshold'):.6g} (P5-33; on by default, guard(offer_gate=False) switches it "
                             "off; commits unchanged)")
        for key, oc in self.offer_controls.items():
            where = "" if key == "default" else f" (readout {key})"
            parts = [f"{c.get('label') or c['name']} {c['n_offer']}/{c['n']} {'pass' if c['passed'] else 'FAIL'}"
                     for c in oc.get("controls", [])]
            real = oc.get("real") or {}
            lines.append(f"  offer control{where}: {str(oc.get('verdict')).upper()} ({oc.get('mode')} mode, "
                         f"P5-31, checked {oc.get('checked')}): real {real.get('n_offer')}/{real.get('n')}; "
                         + ", ".join(parts))
        if r.get("status_note"):
            lines.append(f"  note:     {r['status_note']}")
        return "\n".join(lines)


def _trust_blocks(doc: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    """``("default", trust)`` and ``("<readout>", readouts.<readout>.trust)`` of a manifest document."""
    out: list[tuple[str, Mapping[str, Any]]] = []
    t = doc.get("trust")
    if isinstance(t, Mapping):
        out.append(("default", t))
    ro = doc.get("readouts")
    if isinstance(ro, Mapping):
        for k, v in ro.items():
            if isinstance(v, Mapping) and isinstance(v.get("trust"), Mapping):
                out.append((str(k), v["trust"]))
    return out


def _offer_blocks(doc: Mapping[str, Any]) -> list[tuple[str, Any]]:
    out = []
    t = doc.get("trust")
    if isinstance(t, Mapping) and "offer_control" in t:
        out.append(("default", t["offer_control"]))
    ro = doc.get("readouts")
    if isinstance(ro, Mapping):
        for name, r in ro.items():
            rt = r.get("trust") if isinstance(r, Mapping) else None
            if isinstance(rt, Mapping) and "offer_control" in rt:
                out.append((str(name), rt["offer_control"]))
    return out


def _check_offer_control(oc: Any, where: str) -> None:
    """Check one ``offer_control`` block: types, counts and verdict = all controls passed."""
    if not isinstance(oc, Mapping):
        raise ManifestError(f"{where}: an object is needed")
    verdict = _req(oc, "verdict", str, where)
    if verdict not in OFFER_VERDICTS:
        raise ManifestError(f"{where}: verdict must be one of {OFFER_VERDICTS}")
    _req(oc, "mode", str, where)
    _req(oc, "source", str, where)
    for i, (tag, c) in enumerate([("real", _req(oc, "real", Mapping, where))]
                                 + [(f"controls[{j}]", c) for j, c in enumerate(_req(oc, "controls", list, where))]):
        w = f"{where}: {tag}"
        if not isinstance(c, Mapping):
            raise ManifestError(f"{w}: an object is needed")
        n, k = _req(c, "n", int, w), _req(c, "n_offer", int, w)
        if not 0 <= k <= n:
            raise ManifestError(f"{w}: n_offer must be in [0, n]")
        if i:
            _req(c, "name", str, w)
            _req(c, "passed", bool, w)
    ctr = oc["controls"]
    if not ctr:
        raise ManifestError(f"{where}: controls must not be empty")
    if (verdict == "pass") != all(c["passed"] for c in ctr):
        raise ManifestError(f"{where}: verdict {verdict!r} does not match the passed flags of the controls")


def _req(d: Mapping[str, Any], key: str, typ: type | tuple[type, ...], where: str) -> Any:
    if key not in d:
        raise ManifestError(f"{where}: missing key {key!r}")
    v = d[key]
    if not isinstance(v, typ) or (isinstance(v, bool) and typ is int):
        raise ManifestError(f"{where}: {key!r} has the wrong type ({type(v).__name__})")
    return v


def parse_manifest(doc: Mapping[str, Any], where: str = "<manifest>") -> Manifest:
    """Check a manifest document and return a :class:`Manifest`. Raise :class:`ManifestError`."""
    if not isinstance(doc, Mapping):
        raise ManifestError(f"{where}: a manifest is a JSON object")
    if doc.get("schema") != MANIFEST_SCHEMA:
        raise ManifestError(f"{where}: schema must be {MANIFEST_SCHEMA!r}, got {doc.get('schema')!r}")
    name = _req(doc, "name", str, where)
    if not _NAME.match(name):
        raise ManifestError(f"{where}: bad model name {name!r} (lower case, digits, '.', '-')")
    status = _req(doc, "status", str, where)
    if status not in STATUSES:
        raise ManifestError(f"{where}: status must be one of {STATUSES}")
    files = []
    seen = set()
    for i, f in enumerate(_req(doc, "files", list, where)):
        w = f"{where}: files[{i}]"
        if not isinstance(f, Mapping):
            raise ManifestError(f"{w}: an object is needed")
        role, fname = _req(f, "role", str, w), _req(f, "name", str, w)
        sha, size = _req(f, "sha256", str, w), _req(f, "size", int, w)
        url = f.get("url")
        if role not in FILE_ROLES:
            raise ManifestError(f"{w}: role must be one of {FILE_ROLES}")
        if not _FILE.match(fname) or fname in seen:
            raise ManifestError(f"{w}: bad or repeated file name {fname!r} (no folders allowed)")
        if not _SHA.match(sha):
            raise ManifestError(f"{w}: sha256 must be 64 lower-case hex characters")
        if size <= 0:
            raise ManifestError(f"{w}: size must be > 0")
        if url is not None and (not isinstance(url, str) or not url.startswith("https://")):
            raise ManifestError(f"{w}: url must be null or an https:// URL")
        seen.add(fname)
        files.append(FileEntry(role, fname, sha, int(size), url))
    if status == "available" and not any(f.role == "weights" for f in files):
        raise ManifestError(f"{where}: an available model needs a weights file")
    if "language" in doc:
        from fidetype.lang import check_tag

        try:
            check_tag(doc["language"], f"{where}: language")
        except ValueError as e:
            raise ManifestError(str(e)) from None
    lic = _req(doc, "licence", Mapping, where)
    spdx = _req(lic, META_LICENCE, str, f"{where}: licence")
    if normalise(spdx) != spdx:
        raise ManifestError(f"{where}: licence {META_LICENCE!r} must be an SPDX id (got {spdx!r}, "
                            f"normalised {normalise(spdx)!r})")
    ro = _req(lic, META_RESEARCH_ONLY, bool, f"{where}: licence")
    # A manifest may be stricter than its data licence, never looser (FEP-0010 MET-12).
    needed = bool(combine([source_summary(spdx)])["research_only"])
    if needed and not ro:
        raise ManifestError(f"{where}: data licence {spdx} needs data.research_only = true")
    for key, tr in _trust_blocks(doc):
        if "offer_gate" in tr:
            from fidetype.trust.offer_gate import OfferGate

            try:
                OfferGate.from_dict(tr["offer_gate"])
            except (KeyError, TypeError, ValueError) as e:
                block = "trust" if key == "default" else f"readouts.{key}.trust"
                raise ManifestError(f"{where}: {block}.offer_gate: {e}") from None
    for key, oc in _offer_blocks(doc):
        _check_offer_control(oc, f"{where}: {'trust' if key == 'default' else 'readouts.' + key + '.trust'}"
                                 f".offer_control")
    # Offer-control policy (user decision 2026-11-22, gap 152): "warn" stays the calibrate() default, but a
    # guard that ships an offer gate is held to "refuse": it must show a passing offer null control.
    for key, tr in _trust_blocks(doc):
        if "offer_gate" in tr:
            block = "trust" if key == "default" else f"readouts.{key}.trust"
            oc = tr.get("offer_control")
            if not isinstance(oc, Mapping) or oc.get("verdict") != "pass":
                raise ManifestError(f"{where}: {block} ships an offer_gate, so its offer_control must have "
                                    "verdict 'pass' (refuse policy for gated guards, gap 152)")
    return Manifest(
        name=name, version=str(_req(doc, "version", str, where)), title=str(_req(doc, "title", str, where)),
        status=status, task=str(_req(doc, "task", str, where)), modality=str(_req(doc, "modality", str, where)),
        runtime=str(_req(doc, "runtime", str, where)), files=tuple(files), licence=dict(lic), raw=dict(doc),
    )


def manifest_dir() -> Path:
    """The folder of the packaged manifests."""
    return Path(str(resources.files("fidetype.pretrained").joinpath("manifests")))


def load_manifest(name_or_path: str | Path) -> Manifest:
    """A packaged manifest by model name, or a manifest file by path (``*.json``)."""
    s = str(name_or_path)
    p = Path(s) if s.endswith(".json") else manifest_dir() / f"{s}.json"
    if not p.is_file():
        known = ", ".join(sorted(m.name for m in all_manifests()))
        raise KeyError(f"no pretrained model {s!r}; known: {known}")
    return parse_manifest(json.loads(p.read_text(encoding="utf-8")), p.name)


def all_manifests() -> list[Manifest]:
    """Every packaged manifest, sorted by name."""
    out = []
    for p in sorted(manifest_dir().glob("*.json")):
        out.append(parse_manifest(json.loads(p.read_text(encoding="utf-8")), p.name))
    return out
