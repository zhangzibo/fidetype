"""The decode declaration of FEP-0001 (section 4): who made a hypothesis, and how.

On the hypothesis route the producer decodes, not the trust layer. A
frozen trust configuration is valid only with the decoding it was fitted
on: the same decoder, the same decode parameters and the same frozen
frame temperature (M4-06 finding). The layer cannot see the decoding. So
the producer **declares** it, and the layer compares the declaration
with its own configuration.

A declaration is a JSON object, in the header (for the whole stream) or
on a ``hypothesis`` event (for that event; it replaces the header value)::

    {"decoder": "acme-beam", "decoder_version": "2.1",
     "frame_temperature": 1.37, "params": {"beam": 16, "lm_weight": 0.8},
     "config_id": "tcfg-f5ca0020b3b8fce2"}

Only ``decoder`` is required. ``frame_temperature`` defaults to 1.0 (no
scaling), so a declaration without it says "I applied no temperature".
"""

from __future__ import annotations

import math
from typing import Any, Mapping

#: The key in the header and on ``hypothesis`` events.
DECLARATION_KEY = "decode_declaration"
#: Relative tolerance of the frame temperature comparison.
TEMPERATURE_RTOL = 1e-9
_STR_FIELDS = ("decoder", "decoder_version", "config_id")
KNOWN_FIELDS = ("decoder", "decoder_version", "frame_temperature", "params", "config_id")


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def validate_declaration(decl: Any) -> list[str]:
    """Return the format errors of a declaration (empty list: valid)."""
    if not isinstance(decl, dict):
        return [f"{DECLARATION_KEY} must be a JSON object"]
    errs = []
    if not isinstance(decl.get("decoder"), str) or not decl["decoder"]:
        errs.append(f"{DECLARATION_KEY}.decoder must be a non-empty string")
    for k in ("decoder_version", "config_id"):
        if k in decl and (not isinstance(decl[k], str) or not decl[k]):
            errs.append(f"{DECLARATION_KEY}.{k} must be a non-empty string")
    if "frame_temperature" in decl:
        t = decl["frame_temperature"]
        if not _num(t) or t <= 0:
            errs.append(f"{DECLARATION_KEY}.frame_temperature must be a finite number > 0")
    if "params" in decl and not isinstance(decl["params"], dict):
        errs.append(f"{DECLARATION_KEY}.params must be a JSON object")
    return errs


def declared_temperature(decl: Mapping[str, Any]) -> float:
    return float(decl.get("frame_temperature", 1.0))


def compare_declaration(
    decl: Mapping[str, Any],
    config_id: str | None = None,
    frame_temperature: float | None = None,
    expected: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return the mismatches between a (valid) declaration and the layer's configuration.

    - ``config_id``: if the declaration names a config id, it must be this one.
    - ``frame_temperature``: the declared temperature (default 1.0) must equal
      the frozen one (relative tolerance :data:`TEMPERATURE_RTOL`).
    - ``expected``: optional ``decoder``, ``decoder_version`` and ``params``
      that the layer requires. Each given key must match; ``params`` is a
      subset match (every expected parameter must be declared with the same value).
    """
    out: list[str] = []
    cid = decl.get("config_id")
    if cid is not None and config_id is not None and cid != config_id:
        out.append(f"config_id {cid!r} != {config_id!r}")
    if frame_temperature is not None:
        t = declared_temperature(decl)
        ft = float(frame_temperature)
        if not math.isclose(t, ft, rel_tol=TEMPERATURE_RTOL, abs_tol=0.0):
            out.append(f"frame_temperature {t!r} != frozen {ft!r}")
    if expected:
        for k in ("decoder", "decoder_version"):
            want = expected.get(k)
            if want is not None and decl.get(k) != want:
                out.append(f"{k} {decl.get(k)!r} != expected {want!r}")
        params = decl.get("params") or {}
        for k, want in (expected.get("params") or {}).items():
            if k not in params:
                out.append(f"params.{k} not declared (expected {want!r})")
            elif params[k] != want:
                out.append(f"params.{k} {params[k]!r} != expected {want!r}")
    return out
