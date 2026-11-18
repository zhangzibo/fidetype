"""One guarantee sheet per policy, in one uniform format (P5-02).

The trust layer has several ways to choose the COMMIT threshold. Each
gives a different kind of statement:

======================  =======================================  =================================
policy type             statement                                kind of validity
======================  =======================================  =================================
``offline_crc``         E[wrong-commit loss] <= alpha            finite sample, in expectation
``offline_ltt``         P(wrong-commit rate <= alpha) >= 1-delta finite sample, high probability
``precision_ltt``       P(error among commits <= beta) >= 1-d_p  finite sample, high probability
``joint_fluent_wrong``  P(wrong-commit <= alpha and fluent-wrong finite sample, high probability
                        <= alpha_h [and precision]) >= 1-delta_h (one joint test)
``online_aci``          mean loss <= certificate (any sequence)  deterministic, long run
``online_aci_window``   mean loss <= certificate (any sequence)  deterministic, long run
``online_window``       approximate (weighted CRC)               approximate
``bandit``              (G1) / (G2) any sequence, (G3) audit     deterministic + anytime audit
======================  =======================================  =================================

:class:`PolicySheet` states each one with the same fields: method,
levels (alpha, delta, ...), the controlled risk, the kind of validity,
the calibration size and scope, the assumptions, what is NOT
guaranteed, the null-control results and the current status. It is
machine-readable (:meth:`PolicySheet.to_dict`, schema
:data:`SHEET_SCHEMA`) and printable (``str(sheet)``). A list of sheets
round-trips through :func:`save_sheets` and :func:`load_sheets`.

:func:`policy_sheets` builds the sheets of any supported object: a
:class:`~fidetype.trust.dropin.TrustGuard` (one sheet per bound on its
:class:`~fidetype.trust.dropin.GuaranteeSheet`), an
:class:`~fidetype.trust.online_guard.OnlineGuard`, a
:class:`~fidetype.trust.risk_control.CommitRiskControl` (CRC or LTT),
an :class:`~fidetype.trust.online_risk.OnlineCommitRiskControl` or a
:class:`~fidetype.trust.bandit_risk.BanditCommitRiskControl`.

Command line (no decoder needed; reads a saved guard or a sheet file)::

    python -m fidetype.trust.guarantee_sheet guard.json          # printable text
    python -m fidetype.trust.guarantee_sheet guard.json --json   # JSON

The sheet is a statement about the method and the calibration. It is
not a medical or legal claim. Licence: our own code, Apache-2.0.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
from dataclasses import dataclass, field, fields
from os import PathLike
from pathlib import Path
from typing import Any, Mapping, Sequence

__all__ = [
    "SHEET_SCHEMA",
    "SHEET_SET_SCHEMA",
    "POLICY_TYPES",
    "VALIDITY_KINDS",
    "PolicySheet",
    "policy_sheets",
    "sheets_from_guarantee_sheet",
    "sheet_from_risk_control",
    "sheet_from_online",
    "sheet_from_bandit",
    "save_sheets",
    "load_sheets",
    "format_sheets",
]

#: Schema of one sheet (major.minor). A reader accepts every 1.x sheet; unknown keys go to ``extra``.
SHEET_SCHEMA = "fidetype.guarantee-sheet/1.0"
#: Schema of a file with a list of sheets (:func:`save_sheets`).
SHEET_SET_SCHEMA = "fidetype.guarantee-sheets/1.0"

POLICY_TYPES: tuple[str, ...] = (
    "offline_crc", "offline_ltt", "precision_ltt", "joint_fluent_wrong",
    "online_aci", "online_aci_window", "online_window", "bandit",
)
#: ``finite_sample_expectation``: E[loss] <= alpha over calibration and test draws (CRC).
#: ``finite_sample_probability``: P(risk <= alpha) >= 1 - delta over the calibration draw (LTT).
#: ``deterministic_long_run``: an identity on the observed losses; holds for any sequence (ACI).
#: ``deterministic_long_run+anytime_audit``: as above, plus a bound with probability >= 1 - delta over the
#: exploration coins (bandit audit).
#: ``approximate``: no finite-sample statement (weighted CRC under drift).
VALIDITY_KINDS: tuple[str, ...] = (
    "finite_sample_expectation", "finite_sample_probability", "deterministic_long_run",
    "deterministic_long_run+anytime_audit", "approximate",
)

_MEDICAL = "Any medical or legal claim. Fidetype is research software, not a medical device."
_SILENT = ("Silent errors: a wrong commit that the user never corrects looks like a right one; online statements "
           "are about OBSERVED losses only.")


# ---------------------------------------------------------------------------
# JSON helpers (inf / nan safe; tuples -> lists), so that a sheet equals its loaded copy
# ---------------------------------------------------------------------------


def _enc(x: Any) -> Any:
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, (int,)) and not isinstance(x, bool):
        return int(x)
    if hasattr(x, "dtype") and str(getattr(x, "dtype", "")) == "bool":
        return bool(x)
    if isinstance(x, float) or hasattr(x, "dtype"):
        try:
            v = float(x)
        except (TypeError, ValueError):
            return str(x)
        if math.isnan(v):
            return None
        if math.isinf(v):
            return "inf" if v > 0 else "-inf"
        if hasattr(x, "dtype") and float(v).is_integer() and "int" in str(getattr(x, "dtype", "")):
            return int(v)
        return v
    if isinstance(x, Mapping):
        return {str(k): _enc(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_enc(v) for v in x]
    return str(x)


def _dec(x: Any) -> Any:
    if x == "inf":
        return math.inf
    if x == "-inf":
        return -math.inf
    if isinstance(x, Mapping):
        return {k: _dec(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_dec(v) for v in x]
    return x


def _norm(x: Any) -> Any:
    """The in-memory form that a JSON round trip gives back."""
    return _dec(json.loads(json.dumps(_enc(x), allow_nan=False)))


def _f(x: Any) -> float | None:
    """A float or None (nan / None / missing)."""
    if x is None:
        return None
    if isinstance(x, str):
        return _dec(x) if x in ("inf", "-inf") else float(x)
    v = float(x)
    return None if math.isnan(v) else v


def _fmt(x: Any) -> str:
    if x is None:
        return "-"
    if isinstance(x, float):
        if math.isinf(x):
            return "inf (never)" if x > 0 else "-inf"
        return f"{x:.4g}"
    return str(x)


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# the sheet
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicySheet:
    """The guarantee of one policy, in the uniform P5-02 format.

    All fields are plain data. ``str(sheet)`` prints it; :meth:`to_dict`
    / :meth:`from_dict` round-trip it through JSON (``inf`` is written as
    the string ``"inf"``, nan as ``null``).
    """

    #: One of :data:`POLICY_TYPES`.
    policy_type: str
    #: The guarantee in one sentence, in plain words.
    statement: str
    #: How the threshold is chosen (method and its parameters).
    method: str
    #: The controlled risk: ``{"name": ..., "definition": ...}`` (or a list of them for a joint test).
    risk: dict[str, Any]
    #: The levels: ``alpha`` always; ``delta`` (None = deterministic); others such as ``alpha_h``,
    #: ``target_precision``, ``eta``.
    levels: dict[str, Any]
    #: One of :data:`VALIDITY_KINDS`.
    validity: str
    #: Calibration size and scope: ``n_items``, ``split``, ``scope`` (what data), ``feedback`` (online).
    calibration: dict[str, Any]
    assumptions: tuple[str, ...]
    not_guaranteed: tuple[str, ...]
    #: Null-control results (``name``, ``n``, ``n_commit``, ``allowed``, ``passed``); empty if none ran.
    controls: tuple[dict[str, Any], ...] = ()
    #: Current state: ``feasible``, ``threshold`` and, online, ``n_observed``, ``realised``, ``certificate``.
    status: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    #: The frozen configuration id (``tcfg-...``), if any.
    config_id: str | None = None
    references: tuple[str, ...] = ()
    created_utc: str = ""
    schema: str = SHEET_SCHEMA
    #: Keys of a newer 1.x sheet that this version does not know (kept on load and save).
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.policy_type not in POLICY_TYPES:
            raise ValueError(f"unknown policy_type {self.policy_type!r}; known: {POLICY_TYPES}")
        if self.validity not in VALIDITY_KINDS:
            raise ValueError(f"unknown validity {self.validity!r}; known: {VALIDITY_KINDS}")
        if not str(self.schema).startswith("fidetype.guarantee-sheet/1."):
            raise ValueError(f"unsupported sheet schema {self.schema!r} (this reader: {SHEET_SCHEMA})")
        if "alpha" not in self.levels or "delta" not in self.levels:
            raise ValueError("levels must hold 'alpha' and 'delta' (delta None = deterministic)")
        for k in ("risk", "levels", "calibration", "status", "extra"):
            object.__setattr__(self, k, _norm(getattr(self, k)))
        object.__setattr__(self, "controls", tuple(_norm(list(self.controls))))
        for k in ("assumptions", "not_guaranteed", "warnings", "references"):
            object.__setattr__(self, k, tuple(str(a) for a in getattr(self, k)))

    # --- data -------------------------------------------------------------

    @property
    def alpha(self) -> float | None:
        return _f(self.levels.get("alpha"))

    @property
    def delta(self) -> float | None:
        return _f(self.levels.get("delta"))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for f in fields(self):
            if f.name == "extra":
                continue
            v = getattr(self, f.name)
            d[f.name] = _enc(list(v) if isinstance(v, tuple) else v)
        d.update(_enc(self.extra))
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "PolicySheet":
        known = {f.name for f in fields(cls)} - {"extra"}
        kw = {k: _dec(v) for k, v in d.items() if k in known}
        kw["extra"] = {k: _dec(v) for k, v in d.items() if k not in known}
        for k in ("assumptions", "not_guaranteed", "warnings", "references", "controls"):
            kw[k] = tuple(kw.get(k) or ())
        return cls(**kw)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)

    # --- text -------------------------------------------------------------

    def __str__(self) -> str:
        title = f"Fidetype guarantee sheet: {self.policy_type}"
        lv = ", ".join(f"{k} {_fmt(v)}" for k, v in self.levels.items())
        risks = self.risk.get("risks") if isinstance(self.risk.get("risks"), list) else [self.risk]
        lines = [title, "=" * len(title), f"schema           {self.schema}"]
        if self.config_id:
            lines.append(f"config_id        {self.config_id}")
        lines += [f"guarantee        {self.statement}", f"validity         {self.validity}", f"levels           {lv}"]
        for r in risks:
            lines.append(f"risk             {r.get('name')}: {r.get('definition')}")
        lines.append(f"method           {self.method}")
        lines.append("calibration")
        lines += [f"  {k:<22}{_fmt(v) if not isinstance(v, (dict, list)) else json.dumps(_enc(v), sort_keys=True)}"
                  for k, v in self.calibration.items()]
        if self.status:
            lines.append("status")
            lines += [f"  {k:<22}{_fmt(v) if not isinstance(v, (dict, list)) else json.dumps(_enc(v), sort_keys=True)}"
                      for k, v in self.status.items()]
        if self.controls:
            lines.append("null controls")
            for c in self.controls:
                lines.append(f"  {str(c.get('name')):<14} {c.get('n_commit')}/{c.get('n')} commits (allowed "
                             f"{c.get('allowed')}): {'PASS' if c.get('passed') else 'FAIL'}")
        else:
            lines.append("null controls    none run for this policy")
        lines.append("assumptions")
        lines += [f"  - {a}" for a in self.assumptions]
        lines.append("not guaranteed")
        lines += [f"  - {a}" for a in self.not_guaranteed]
        if self.warnings:
            lines.append("warnings")
            lines += [f"  ! {w}" for w in self.warnings]
        if self.references:
            lines.append("references")
            lines += [f"  {r}" for r in self.references]
        lines.append("Details: docs/trust-guarantee.md")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# files
# ---------------------------------------------------------------------------


def save_sheets(sheets: Sequence[PolicySheet] | PolicySheet, path: str | PathLike[str]) -> Path:
    """Write sheets as JSON (``{"schema": SHEET_SET_SCHEMA, "sheets": [...]}``)."""
    if isinstance(sheets, PolicySheet):
        sheets = [sheets]
    p = Path(path)
    data = {"schema": SHEET_SET_SCHEMA, "sheets": [s.to_dict() for s in sheets]}
    p.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
                 encoding="utf-8", newline="\n")
    return p


def load_sheets(path: str | PathLike[str]) -> list[PolicySheet]:
    """Read sheets from a sheet file, one sheet, or a saved guard (``fidetype.trust-guard/*``)."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return _sheets_of_json(d)


def _sheets_of_json(d: Mapping[str, Any]) -> list[PolicySheet]:
    schema = str(d.get("schema", ""))
    if schema.startswith("fidetype.guarantee-sheets/1."):
        return [PolicySheet.from_dict(s) for s in d["sheets"]]
    if schema.startswith("fidetype.guarantee-sheet/1."):
        return [PolicySheet.from_dict(d)]
    if schema.startswith("fidetype.trust-guard/"):
        from fidetype.trust.dropin import GuaranteeSheet

        if not d.get("sheet"):
            raise ValueError("this guard file has no guarantee sheet")
        return sheets_from_guarantee_sheet(GuaranteeSheet.from_dict(d["sheet"]))
    raise ValueError(f"not a guarantee sheet file (schema {schema!r})")


def format_sheets(sheets: Sequence[PolicySheet]) -> str:
    """Printable text of several sheets."""
    return "\n\n".join(str(s) for s in sheets)


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

_LTT_REF = "Angelopoulos, Bates, Candes, Jordan & Lei, Learn then Test, arXiv:2110.01052"
_CRC_REF = "Angelopoulos, Bates, Fisch, Lei & Schuster, Conformal Risk Control, ICLR 2024, arXiv:2208.02814"
_ACI_REF = "Gibbs & Candes 2021, Adaptive Conformal Inference Under Distribution Shift, arXiv:2106.00170"
_ACI2_REF = "Angelopoulos, Candes & Tibshirani 2023, Conformal PID Control, arXiv:2307.16895"
_NEX_REF = "Barber, Candes, Ramdas & Tibshirani 2023, arXiv:2202.13415; Farinhas et al., ICLR 2024, arXiv:2310.01262"
_BANDIT_REF = ("Ge, Bastani & Bastani 2024, arXiv:2405.13268; Waudby-Smith et al. 2022, arXiv:2210.10768 "
               "(IPW confidence sequences)")
_WRONG_COMMIT = {"name": "wrong-commit rate", "definition": "wrong COMMITs / all utterances"}
_PRECISION = {"name": "error rate among commits", "definition": "wrong COMMITs / all COMMITs (1 - precision)"}

_OFFLINE_ASSUMPTIONS = (
    "Exchangeable data: calibration and live utterances come from the same distribution (same user, device, "
    "decoder, task and session type).",
    "The decoder, the vocabulary and every other fitted part do not change after calibration.",
    "The calibration items were used for nothing else, and their true texts are right.",
)
_OFFLINE_NOT = (
    "Any single utterance; a bound per session or per user.",
    "Data that differ from the calibration data (a new day, a new user, drift). Use an online policy for drift.",
    _MEDICAL,
)


def sheets_from_guarantee_sheet(gs: Any) -> list[PolicySheet]:
    """The per-policy sheets of a drop-in :class:`~fidetype.trust.dropin.GuaranteeSheet`.

    Always the ``offline_ltt`` sheet (P14-03); plus ``precision_ltt`` (P5-02) or ``joint_fluent_wrong``
    (P15-06, with the precision risk if it was part of the joint test).
    """
    controls = tuple(c.to_dict() for c in gs.controls)
    split = {"fit": gs.n_fit, "policy_grid": gs.n_policy, "ltt": gs.n_ltt, "seed": gs.seed}
    cal = {"n_items": gs.n_items, "split": split, "ltt_items_needed": gs.n_ltt_min,
           "scope": f"{gs.input_kind} input, decoder {gs.decoder}; a random split of your labelled utterances"}
    base_status = {"feasible": bool(gs.feasible), "lambda_hat": _f(gs.lambda_hat),
                   "commit_threshold": _f(gs.commit_threshold), "ltt_commits": gs.ltt_commits,
                   "ltt_wrong_commits": gs.ltt_wrong_commits, "commit_gate": dict(gs.commit_gate)}
    cf = getattr(gs, "confidence", None)
    if cf:  # P5-23: the learned commit score (fit items disjoint from the LTT items); absent = p_top1
        base_status["commit_score"] = "learned"
        cal = dict(cal, score_fit_items=cf.get("fit_items"), score_certify_items=cf.get("certify_items"))
        base_status["commit_score_model"] = {k: cf.get(k) for k in ("schema", "model", "features", "l2", "coef",
                                                                    "intercept")}
    # the base statement (assumptions / not-guaranteed lines that belong to other bounds are left out)
    base_ass = tuple(a for a in gs.assumptions if not a.startswith(("Precision bound", "Hallucination bound")))
    base_not = tuple(a for a in gs.not_guaranteed if not a.startswith(("Precision bound", "Hallucination bound")))
    if gs.precision and not any(a.startswith("The error rate among commits") for a in base_not):
        base_not = base_not + ("The error rate among commits, unless a precision sheet is listed.",)
    out = [PolicySheet(
        policy_type="offline_ltt",
        statement=f"With probability >= {1 - gs.delta:g} over the calibration draw, the wrong-commit rate on new "
                  f"utterances from the same distribution is <= {gs.alpha:g}.",
        method=gs.method, risk=dict(_WRONG_COMMIT), levels={"alpha": gs.alpha, "delta": gs.delta},
        validity="finite_sample_probability", calibration=cal, assumptions=base_ass, not_guaranteed=base_not,
        controls=controls, status=base_status, warnings=tuple(gs.warnings), config_id=gs.config_id,
        references=(_LTT_REF,), created_utc=gs.created_utc,
    )]
    h, q = gs.halluc, gs.precision
    if h:
        joint = bool(q and q.get("joint_with") == "halluc")
        risks = [dict(_WRONG_COMMIT),
                 {"name": "fluent-wrong rate", "definition": f"COMMITs that are wrong and {h['fluent_rule']} / all "
                                                             "utterances"}]
        levels: dict[str, Any] = {"alpha": gs.alpha, "delta": h["delta_h"], "alpha_h": h["alpha_h"]}
        stmt = (f"With probability >= {1 - h['delta_h']:g}: fluent-wrong rate <= {h['alpha_h']:g} and wrong-commit "
                f"rate <= {gs.alpha:g}")
        if joint:
            risks.append(dict(_PRECISION))
            levels["target_precision"] = q["target_precision"]
            stmt += f" and error rate among commits <= {q['beta']:.4g}"
        status = {"feasible": bool(h["feasible"]), "selected": h.get("selected"), "n_certified": h["n_certified"],
                  "chain_length": h["chain_length"], "n_tested": h["n_tested"], "test_counts": h.get("test_counts"),
                  "commit_threshold": _f(gs.commit_threshold)}
        if joint:
            status["test_precision_lower"] = q.get("test_precision_lower")
            status["min_commits"] = q.get("min_commits")
        out.append(PolicySheet(
            policy_type="joint_fluent_wrong", statement=stmt + " (all together, one joint test).",
            method=h["method"], risk={"risks": risks}, levels=levels, validity="finite_sample_probability",
            calibration={"n_items": gs.n_items, "split": split, "ordering_items": h["n_order"],
                         "test_items": h["n_test"], "grounding": h.get("grounding"),
                         "fluent_threshold": h.get("fluent_threshold"), "scope": cal["scope"]},
            assumptions=gs.assumptions, not_guaranteed=gs.not_guaranteed,
            controls=tuple(h.get("controls_final") or controls), status=status, warnings=tuple(gs.warnings),
            config_id=gs.config_id, references=(_LTT_REF, "P15-06 joint Learn then Test (fidetype.trust.halluc_bound)"),
            created_utc=gs.created_utc,
        ))
    if q and q.get("joint_with") != "halluc":
        tc = q.get("test_counts") or {}
        out.append(PolicySheet(
            policy_type="precision_ltt",
            statement=f"With probability >= {1 - q['delta_p']:g}, the error rate among commits on new utterances is "
                      f"<= {q['beta']:.4g} (precision >= {q['target_precision']:g}). Together with the "
                      f"offline_ltt sheet: both hold with probability >= {max(0.0, 1 - gs.delta - q['delta_p']):g}.",
            method=q["method"], risk=dict(_PRECISION),
            levels={"alpha": q["beta"], "delta": q["delta_p"], "target_precision": q["target_precision"]},
            validity="finite_sample_probability",
            calibration={"n_items": gs.n_items, "split": split, "ordering_items": q["n_order"],
                         "test_items": q["n_test"], "commits_needed": q["min_commits"], "scope": cal["scope"]},
            assumptions=gs.assumptions, not_guaranteed=gs.not_guaranteed,
            controls=tuple(q.get("controls_final") or controls),
            status={"feasible": bool(q["feasible"]), "selected": q.get("selected"),
                    "base_commit_p": q.get("base_commit_p"), "n_certified": q["n_certified"],
                    "chain_length": q["chain_length"], "n_tested": q["n_tested"],
                    "test_commits": tc.get("commits", 0), "test_wrong": tc.get("wrong", 0),
                    "test_precision_lower": q.get("test_precision_lower")},
            warnings=tuple(gs.warnings), config_id=gs.config_id,
            references=(_LTT_REF, "P5-02 precision LTT (fidetype.trust.precision_bound)"), created_utc=gs.created_utc,
        ))
    return out


def sheet_from_risk_control(rc: Any, *, scope: str = "your calibration items", config_id: str | None = None,
                            controls: Sequence[Any] = ()) -> PolicySheet:
    """The sheet of an offline :class:`~fidetype.trust.risk_control.CommitRiskControl` (or its result)."""
    res = getattr(rc, "result", rc)
    if res is None:
        raise ValueError("call fit() first")
    crc = str(res.method) == "crc"
    status = {"feasible": bool(res.feasible), "threshold": _f(res.threshold),
              "empirical_risk": _f(res.empirical_risk), "commit_rate": _f(res.commit_rate)}
    if crc:
        status["crc_bound"] = _f(res.bound)
        stmt = (f"The expected wrong-commit loss of a new utterance is <= {res.alpha:g} (over the calibration and "
                "the test draw).")
        method = ("conformal risk control: smallest threshold with (n R_hat + B) / (n + 1) <= alpha; loss "
                  "max(c, f), B = 1")
    else:
        status["pvalue"] = _f(res.bound)
        stmt = (f"With probability >= {1 - res.delta:g} over the calibration draw, the wrong-commit rate is "
                f"<= {res.alpha:g}.")
        method = f"Learn then Test, fixed sequence from the strictest threshold ({res.method} p-values)"
    return PolicySheet(
        policy_type="offline_crc" if crc else "offline_ltt", statement=stmt, method=method,
        risk=dict(_WRONG_COMMIT), levels={"alpha": res.alpha, "delta": None if crc else res.delta},
        validity="finite_sample_expectation" if crc else "finite_sample_probability",
        calibration={"n_items": res.n, "scope": scope}, assumptions=_OFFLINE_ASSUMPTIONS,
        not_guaranteed=(("One calibration draw: CRC bounds the mean over draws; one session can be above alpha.",)
                        if crc else ()) + _OFFLINE_NOT,
        controls=tuple(c.to_dict() if hasattr(c, "to_dict") else dict(c) for c in controls), status=status,
        warnings=() if res.feasible else ("no threshold is feasible: the policy never commits",),
        config_id=config_id, references=(_CRC_REF if crc else _LTT_REF,), created_utc=_now(),
    )


def _online_common_not(long_run: bool) -> tuple[str, ...]:
    return ((("One short window or one session: the bound is a long-run average with slack O(1 / (eta T)).",)
             if long_run else ()) + (_SILENT, "Any single utterance.", _MEDICAL))


def sheet_from_online(ctrl: Any, *, scope: str = "the live stream of one guard", config_id: str | None = None,
                      floor: float | None = None, controls: Sequence[Any] = ()) -> PolicySheet:
    """The sheet of an :class:`~fidetype.trust.online_risk.OnlineCommitRiskControl` (its current state)."""
    rep = ctrl.report()
    m = ctrl.method
    status = {"n_observed": rep["n_observed"], "n_missing": rep["n_missing"], "pending": rep["pending"],
              "realised": _f(rep["mean_loss"]), "certificate": _f(rep["certificate"]),
              "threshold": _f(rep["threshold"]), "lam_1": _f(rep["lam_1"])}
    levels: dict[str, Any] = {"alpha": ctrl.alpha, "delta": None}
    feedback = "realised loss (commit labels; the non-commit loss is known)"
    if m == "aci":
        levels["eta"] = ctrl.eta
        stmt = (f"For ANY sequence of utterances, after T observed losses: mean wrong-commit loss <= {ctrl.alpha:g} "
                "+ (lambda_T+1 - lambda_1) / (eta T) (the certificate below).")
        method = f"online threshold update lambda <- max(lam_min, lambda + eta (L - alpha)), eta {ctrl.eta:g}"
        if rep["n_observed"] and ctrl.upper_clip_hits == 0:
            status["prior_bound"] = _f(ctrl.prior_bound(rep["n_observed"]))
        validity, refs = "deterministic_long_run", (_ACI_REF, _ACI2_REF)
    elif m == "aci_window":
        levels["gamma"] = ctrl.gamma
        stmt = (f"For ANY sequence, after T observed losses: mean wrong-commit loss <= {ctrl.alpha:g} + "
                "(alpha_1 - alpha_T+1) / (gamma T) (the certificate below).")
        method = (f"window CRC at an adaptive level alpha_t <- min(alpha_max, alpha_t + gamma (alpha - L)), "
                  f"gamma {ctrl.gamma:g}, window {ctrl.window}, decay {ctrl.decay}")
        status["alpha_t"] = _f(rep["alpha_t"])
        feedback = "full feedback for the window (truth of non-commits too); the level update needs the realised loss"
        validity, refs = "deterministic_long_run", (_ACI_REF, _NEX_REF)
    else:
        stmt = ("Approximate only: E[loss] <= alpha + B sum_i w_i d_TV(Z, Z^(i)); exact (alpha) only under "
                "exchangeability.")
        method = f"weighted CRC on the last {ctrl.window} items with known truth (decay {ctrl.decay})"
        feedback = "full feedback (truth of non-commits too); items with unknown truth are left out (selection bias)"
        validity, refs = "approximate", (_NEX_REF,)
    if floor is not None:
        status["floor"] = _f(floor)
    warnings = []
    if m == "aci" and ctrl.upper_clip_hits:
        warnings.append("the upper clip lam_max bound: the certificate does not hold (nan)")
    if ctrl.missing == "skip" and rep["n_missing"]:
        warnings.append(f"{rep['n_missing']} commit(s) without feedback were skipped: the bound covers observed items only")
    return PolicySheet(
        policy_type=f"online_{m}", statement=stmt, method=method, risk=dict(_WRONG_COMMIT), levels=levels,
        validity=validity,
        calibration={"n_items": rep["n_observed"], "scope": scope, "feedback": feedback, "missing": ctrl.missing,
                     **({"history_items": len(ctrl.hist_s), "window": ctrl.window} if m != "aci" else {})},
        assumptions=("Each utterance is decided once, in order; feedback can be late and out of order.",
                     "The loss of a commit is reported (a correction means wrong; a missing correction within the "
                     "timeout means right, or use missing='pessimistic')."),
        not_guaranteed=_online_common_not(m != "window") + (
            ("Any finite-sample statement under drift: the window method is approximate.",) if m == "window" else ()),
        controls=tuple(c.to_dict() if hasattr(c, "to_dict") else dict(c) for c in controls), status=status,
        warnings=tuple(warnings), config_id=config_id, references=refs, created_utc=_now(),
    )


def sheet_from_bandit(ctrl: Any, *, scope: str = "the live stream of one guard", config_id: str | None = None,
                      floor: float | None = None, controls: Sequence[Any] = ()) -> PolicySheet:
    """The sheet of a :class:`~fidetype.trust.bandit_risk.BanditCommitRiskControl` (its current state)."""
    rep = ctrl.report()
    prec = ctrl.target == "precision"
    who = "commits" if prec else "decided utterances"
    stmt = (f"For ANY sequence: (wrong commits) / ({who}) <= {ctrl.alpha:g} + (lambda_end - lambda_1) / (eta N) "
            f"(the certificate below; N = number of {who}), from shown-only feedback")
    if ctrl.explore > 0:
        stmt += (f"; audit: with probability >= {1 - ctrl.delta:g} over the exploration coins, the wrong commits that "
                 "any grid threshold would have made on the items so far are below the IPW bound")
    status = {"n_observed": rep["n_observed"], "n_commits": rep["n_commits"], "n_shown": rep["n_shown"],
              "n_explore": rep["n_explore"], "n_missing": rep["n_missing"], "pending": rep["pending"],
              "realised": _f(rep["realised"]), "certificate": _f(rep["certificate"]),
              "threshold": _f(rep["threshold"]), "lam_aci": _f(rep["lam_aci"]), "lam_1": _f(rep["lam_1"])}
    if floor is not None:
        status["floor"] = _f(floor)
    return PolicySheet(
        policy_type="bandit", statement=stmt + ".",
        method=f"rule {ctrl.rule!r}, target {ctrl.target!r}: ACI update on commit labels (eta {ctrl.eta:g})"
               + (f"; forced exploration {ctrl.explore:g} shown as OFFER + IPW audit over {len(ctrl.grid)} thresholds"
                  if ctrl.explore > 0 else ""),
        risk=dict(_PRECISION if prec else _WRONG_COMMIT),
        levels={"alpha": ctrl.alpha, "delta": ctrl.delta if ctrl.explore > 0 else None, "eta": ctrl.eta,
                "explore": ctrl.explore},
        validity="deterministic_long_run+anytime_audit" if ctrl.explore > 0 else "deterministic_long_run",
        calibration={"n_items": rep["n_observed"], "scope": scope,
                     "feedback": "shown-only (bandit): labels of COMMITs and OFFERs only; withheld items get none"},
        assumptions=("Each utterance is decided once; the exploration coin is drawn after the score and the truth "
                     "are fixed.",
                     "A shown item without a label counts as wrong in the audit (pessimistic).")
                    + (("Audit: the exploration coins are unpredictable to whatever produces the data (seed=None, "
                        "fresh OS entropy, in live use; a fixed seed is a public, fixed coin stream).",
                        "Audit: every decided item enters the audit at decision time, in decision order; a shown item "
                        "counts as wrong until its label arrives, so late or never-returned feedback only makes the "
                        "bound larger.")
                       + ((f"Audit rows for grid thresholds below the floor {floor:g} are floored (scores below the "
                           "floor never reach the controller): they are not bounds for those thresholds.",)
                          if floor is not None else ())
                       if ctrl.explore > 0 else ()),
        not_guaranteed=_online_common_not(True) + (
            "Future items for the audit bound unless they are like the past (the audit is about items seen so far).",
            "A user whose intended text changes because of what was shown."),
        controls=tuple(c.to_dict() if hasattr(c, "to_dict") else dict(c) for c in controls), status=status,
        config_id=config_id, references=(_ACI_REF, _ACI2_REF, _BANDIT_REF), created_utc=_now(),
    )


def policy_sheets(obj: Any) -> list[PolicySheet]:
    """The per-policy sheets of a guard, an online guard, a controller or a drop-in guarantee sheet."""
    from fidetype.trust.bandit_risk import BanditCommitRiskControl
    from fidetype.trust.online_risk import OnlineCommitRiskControl
    from fidetype.trust.risk_control import CommitRiskControl, RiskControlResult

    if hasattr(obj, "policy_sheets") and not isinstance(obj, type) and obj.__class__.__name__ == "OnlineGuard":
        return obj.policy_sheets()
    if obj.__class__.__name__ == "TrustGuard":
        if obj.sheet is None:
            raise ValueError("this guard has no guarantee sheet")
        return sheets_from_guarantee_sheet(obj.sheet)
    if obj.__class__.__name__ == "GuaranteeSheet":
        return sheets_from_guarantee_sheet(obj)
    if isinstance(obj, (CommitRiskControl, RiskControlResult)):
        return [sheet_from_risk_control(obj)]
    if isinstance(obj, OnlineCommitRiskControl):
        return [sheet_from_online(obj)]
    if isinstance(obj, BanditCommitRiskControl):
        return [sheet_from_bandit(obj)]
    ctrl = getattr(obj, "controller", None)  # OnlineTrustPolicy / BanditTrustPolicy
    if ctrl is not None:
        return policy_sheets(ctrl)
    if isinstance(obj, PolicySheet):
        return [obj]
    raise TypeError(f"no guarantee sheet for {type(obj).__name__}")


def _main(argv: Sequence[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m fidetype.trust.guarantee_sheet",
                                 description="Print the per-policy guarantee sheets of a saved guard or sheet file.")
    ap.add_argument("path", help="a saved guard (guard.save) or a sheet file (save_sheets)")
    ap.add_argument("--json", action="store_true", help="print JSON (schema %s)" % SHEET_SET_SCHEMA)
    a = ap.parse_args(argv)
    sheets = load_sheets(a.path)
    if a.json:
        print(json.dumps({"schema": SHEET_SET_SCHEMA, "sheets": [s.to_dict() for s in sheets]}, indent=2,
                         sort_keys=True, ensure_ascii=False, allow_nan=False))
    else:
        print(format_sheets(sheets))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
