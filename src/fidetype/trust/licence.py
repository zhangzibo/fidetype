"""Licence flags for data sources and derived artifacts (P5-03).

The project licence rule (``wiki/questions/project-plan.md#licence-rule``):

- Non-commercial (NC) data is for research only.
- Product weights come only from CC0 data or our own consented data.
- A provenance ledger records which data trained which weights.

This module turns a licence string into flags and combines the flags of
all inputs of an artifact. :class:`~fidetype.trust.provenance.ProvenanceLedger`
uses it: a ``source`` entry carries the flags of one data source, an
``artifact`` entry (weights, LM, calibration) carries the combined flags
of everything it was derived from, and each decision carries the flags of
its context. So an output that depends on NC data is flagged
``research_only``, and an artifact marked for product use with an NC input
is refused.

Licence ids are SPDX ids (``CC0-1.0``, ``CC-BY-4.0``, ``CC-BY-NC-4.0``,
``Apache-2.0``, ...). :func:`normalise` also reads the forms of the
benchmark tracks (``"CC BY-NC 4.0"``) and the adapters
(``"CC-BY-NC-SA-4.0"``). Two project ids exist:

``LicenseRef-fidetype-consented``
    Our own data, recorded with consent. Commercial use (product weights)
    needs a consent reference whose scope holds ``"train-product"``
    (:mod:`fidetype.trust.privacy`).
``LicenseRef-fidetype-own``
    Data that we made ourselves and that holds no personal data (for
    example simulator output).

An unknown string maps to ``LicenseRef-unknown``: research only, and it is
listed in ``unknown``. This is a design aid, not legal advice.

Combined flags (:func:`summary`, :func:`combine`)::

    {"licences": ["CC-BY-4.0", "CC0-1.0"], "commercial_ok": true, "research_only": false,
     "product_ok": {"project": false, "commercial": true},
     "attribution": ["CC-BY-4.0"], "share_alike": [], "no_derivatives": [], "unknown": []}

Product policies (``product_ok``):

``project`` (the project rule, default)
    every input is CC0, ``LicenseRef-fidetype-own``, or consented data
    with the ``train-product`` scope.
``commercial``
    every input allows commercial use, has a known licence and allows
    derivative works (attribution and share-alike duties are listed, not
    checked).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

CONSENTED = "LicenseRef-fidetype-consented"
OWN = "LicenseRef-fidetype-own"
UNKNOWN = "LicenseRef-unknown"
#: Purpose scope that allows product use of consented data.
PRODUCT_SCOPE = "train-product"
PRODUCT_POLICIES = ("project", "commercial")
#: Licences that the ``project`` policy allows in product weights (consented data needs the product scope).
PROJECT_PRODUCT = frozenset({"CC0-1.0", OWN})


@dataclass(frozen=True)
class LicenceTerms:
    """The flags of one licence id."""

    spdx: str
    commercial: bool
    attribution: bool = False
    share_alike: bool = False
    no_derivatives: bool = False
    known: bool = True


_FIXED: dict[str, LicenceTerms] = {t.spdx: t for t in (
    LicenceTerms("CC0-1.0", True),
    LicenceTerms("Apache-2.0", True, attribution=True),
    LicenceTerms("MIT", True, attribution=True),
    LicenceTerms("BSD-2-Clause", True, attribution=True),
    LicenceTerms("BSD-3-Clause", True, attribution=True),
    LicenceTerms("ODbL-1.0", True, attribution=True, share_alike=True),
    LicenceTerms("PDDL-1.0", True),
    LicenceTerms(OWN, True),
    # Consented data: research by default; product use only with the product scope (see source_terms).
    LicenceTerms(CONSENTED, False),
    LicenceTerms(UNKNOWN, False, known=False),
)}

_CC = re.compile(r"^CC-BY((?:-(?:NC|ND|SA))*)-(\d\.\d)(-[A-Z]{2,3})?$")
_ALIASES = {"CC0": "CC0-1.0", "CC0-1": "CC0-1.0", "PUBLIC-DOMAIN": "CC0-1.0", "APACHE-2": "Apache-2.0",
            "APACHE-2.0": "Apache-2.0", "MIT": "MIT", "BSD-2-CLAUSE": "BSD-2-Clause",
            "BSD-3-CLAUSE": "BSD-3-Clause", "ODBL-1.0": "ODbL-1.0", "PDDL-1.0": "PDDL-1.0"}


def normalise(licence: str | None) -> str:
    """The SPDX id of ``licence`` (``"CC BY-NC 4.0"`` -> ``"CC-BY-NC-4.0"``). Unknown -> ``LicenseRef-unknown``."""
    if not licence or not isinstance(licence, str):
        return UNKNOWN
    s = licence.strip()
    if s in _FIXED:
        return s
    if s.lower() in (CONSENTED.lower(), OWN.lower()):
        return CONSENTED if s.lower() == CONSENTED.lower() else OWN
    u = re.sub(r"[\s_]+", "-", s.upper()).replace("--", "-")
    if u in _ALIASES:
        return _ALIASES[u]
    for k in _FIXED:
        if k.upper() == u:
            return k
    m = _CC.match(u)
    if m:
        return u
    return UNKNOWN


def terms(licence: str | None) -> LicenceTerms:
    """The flags of one licence (consented data: research only; see :func:`source_terms`)."""
    spdx = normalise(licence)
    if spdx in _FIXED:
        return _FIXED[spdx]
    m = _CC.match(spdx)
    if m is None:  # pragma: no cover - normalise returns only fixed ids or CC ids
        return _FIXED[UNKNOWN]
    parts = set(filter(None, m.group(1).split("-")))
    return LicenceTerms(spdx, commercial="NC" not in parts, attribution=True, share_alike="SA" in parts,
                        no_derivatives="ND" in parts)


def _unit(t: LicenceTerms, *, consent_product: bool = False) -> dict[str, Any]:
    commercial = t.commercial or (t.spdx == CONSENTED and consent_product)
    project = (t.spdx in PROJECT_PRODUCT) or (t.spdx == CONSENTED and consent_product)
    return {
        "licences": [t.spdx],
        "commercial_ok": bool(commercial and t.known),
        "research_only": not (commercial and t.known),
        "product_ok": {"project": bool(project), "commercial": bool(commercial and t.known and not t.no_derivatives)},
        "attribution": [t.spdx] if t.attribution else [],
        "share_alike": [t.spdx] if t.share_alike else [],
        "no_derivatives": [t.spdx] if t.no_derivatives else [],
        "unknown": [t.spdx] if not t.known else [],
    }


def source_summary(licence: str | None, consent_scope: Sequence[str] | None = None) -> dict[str, Any]:
    """The flags of one data source. ``consent_scope``: the purposes of its consent (consented data only)."""
    t = terms(licence)
    return _unit(t, consent_product=t.spdx == CONSENTED and PRODUCT_SCOPE in set(consent_scope or ()))


def empty_summary() -> dict[str, Any]:
    """The flags of no input at all (neutral for :func:`combine`)."""
    return {"licences": [], "commercial_ok": True, "research_only": False,
            "product_ok": {p: True for p in PRODUCT_POLICIES},
            "attribution": [], "share_alike": [], "no_derivatives": [], "unknown": []}


def combine(summaries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """The flags of an artifact derived from inputs with these flags (the most restrictive of each)."""
    out = empty_summary()
    sets: dict[str, set[str]] = {k: set() for k in ("licences", "attribution", "share_alike", "no_derivatives",
                                                    "unknown")}
    for s in summaries:
        for k in sets:
            sets[k].update(s.get(k, ()))
        out["commercial_ok"] = out["commercial_ok"] and bool(s.get("commercial_ok"))
        for p in PRODUCT_POLICIES:
            out["product_ok"][p] = out["product_ok"][p] and bool((s.get("product_ok") or {}).get(p))
    for k, v in sets.items():
        out[k] = sorted(v)
    out["research_only"] = not out["commercial_ok"]
    return out


def flag(summary_: Mapping[str, Any]) -> dict[str, Any]:
    """The short flag set that a decision carries: research_only, commercial_ok, product_ok."""
    return {"research_only": bool(summary_["research_only"]), "commercial_ok": bool(summary_["commercial_ok"]),
            "product_ok": dict(summary_["product_ok"])}


class LicenceError(ValueError):
    """An artifact for product use depends on an input that the product policy does not allow."""


def check_product(summary_: Mapping[str, Any], policy: str = "project", what: str = "artifact") -> None:
    """Raise :class:`LicenceError` if ``summary_`` does not allow product use under ``policy``."""
    if policy not in PRODUCT_POLICIES:
        raise ValueError(f"product policy must be one of {PRODUCT_POLICIES}")
    if not summary_["product_ok"][policy]:
        bad = [s for s in summary_["licences"] if not source_summary(s, (PRODUCT_SCOPE,))["product_ok"][policy]]
        why = ", ".join(bad) if bad else f"{CONSENTED} without the {PRODUCT_SCOPE!r} consent scope"
        raise LicenceError(
            f"{what} is marked for product use, but its inputs do not allow it under the {policy!r} policy "
            f"(licences {summary_['licences']}; not allowed: {why}). "
            "Non-commercial data is for research only (licence rule).")


#: NTS ``meta`` keys of the data licence (FEP-0010, NTS 1.0 RC4 amendment 6, MET-12).
META_LICENCE = "data.licence"
META_RESEARCH_ONLY = "data.research_only"


def licence_meta(licence: str, *also: str, research_only: bool | None = None) -> dict[str, Any]:
    """The ``meta`` keys a producer writes for its data licence (FEP-0010).

    ``licence``: the licence of the recorded data (SPDX id or a common form; it is normalised).
    ``also``: licences of other inputs that made the stream (for example the training data of the decoder).
    ``data.research_only`` is true when any of them does not allow commercial use or is unknown (MET-12);
    ``research_only=True`` forces it (a producer may be stricter, never looser).
    """
    spdx = normalise(licence)
    ro = bool(combine(source_summary(x) for x in (licence, *also))["research_only"])
    return {META_LICENCE: spdx, META_RESEARCH_ONLY: ro or bool(research_only)}


def track_meta(track: str) -> dict[str, Any]:
    """The ``meta`` licence keys of a benchmark track's dataset (FEP-0010)."""
    spdx, research_only, _ = track_licence(track)
    return {META_LICENCE: spdx, META_RESEARCH_ONLY: bool(research_only)}


def stream_licence(meta: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The licence flags that a stream declares in its ``meta`` (None: it declares neither key).

    ``data.licence`` gives the flags of that licence. ``data.research_only = true`` makes them research only
    (the most restrictive of the two wins; a stream cannot declare itself looser than its licence). Only
    ``data.research_only = false`` without a licence: unknown licence, research only (the claim cannot be
    checked). A wrongly typed value counts as absent (the validators refuse such a stream, NTS-META-TYPES).
    """
    meta = meta or {}
    lic = meta.get(META_LICENCE)
    ro = meta.get(META_RESEARCH_ONLY)
    has_lic = isinstance(lic, str) and lic != ""
    has_ro = isinstance(ro, bool)
    if not has_lic and not has_ro:
        return None
    s = source_summary(lic if has_lic else None)
    return restrict(s) if ro is True else s


def restrict(summary_: Mapping[str, Any]) -> dict[str, Any]:
    """The flags made research only (no commercial use, no product use); the licence lists stay."""
    return dict(summary_, commercial_ok=False, research_only=True, product_ok={p: False for p in PRODUCT_POLICIES})


def track_licence(track: str) -> tuple[str, bool, str]:
    """``(spdx, research_only, attribution)`` of a benchmark track (``fidetype.benchmark.tracks``)."""
    from fidetype.benchmark.tracks import get_track

    t = get_track(track)
    spdx = normalise(t.licence)
    if terms(spdx).commercial == t.research_only:
        raise ValueError(f"track {track!r}: licence {t.licence!r} and research_only={t.research_only} disagree")
    return spdx, t.research_only, t.attribution
