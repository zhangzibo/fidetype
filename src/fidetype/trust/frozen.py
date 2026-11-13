"""A fitted trust configuration as one JSON file (M4-03).

A :class:`~fidetype.eval.harness.TrustPipeline` holds its fitted state in
several objects: the frame temperature, the sentence and character
temperatures, the conformal threshold, the guard settings and the policy
thresholds (with the risk-controlled ``commit_p``). A streaming consumer
must load exactly that state, without the data that fitted it.

:class:`FrozenTrustConfig` is that state. It is plain data:

- :meth:`FrozenTrustConfig.from_pipeline` reads a fitted pipeline.
- :meth:`FrozenTrustConfig.save` / :meth:`FrozenTrustConfig.load` write
  and read canonical JSON. ``inf`` and ``nan`` are written as the strings
  ``"inf"``, ``"-inf"`` and ``"nan"`` (JSON has no such numbers).
- :meth:`FrozenTrustConfig.build` returns the live trust-core objects.
- :attr:`FrozenTrustConfig.config_id` is the SHA-256 content id of the
  file. Provenance records cite it.

The file holds no signal, no text and no participant data: only numbers
and settings.

Paper 1 frozen configuration
----------------------------
Paper 1 (git tag ``paper1-v4-frozen-config``) freezes a *recipe*, not a
set of numbers: guard on, policy grid fit, then ``commit_p`` from Learn
then Test (alpha 0.05, delta 0.1, default grid, binomial p-values) on a
clean calibration half, combined with the grid value by ``max``. The
numbers depend on the user and the session. :func:`paper1_v4_harness_config`
returns the harness settings of that recipe. Fit a pipeline with them on
the user's calibration data, then freeze it with
:meth:`FrozenTrustConfig.from_pipeline`. :data:`PAPER1_V4_RECIPE` is the
recipe record that goes into the file.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, fields, replace
from os import PathLike
from pathlib import Path
from typing import Any

SCHEMA = "fidetype.trust-config/0.1"

#: The Paper 1 v4 frozen recipe (git tag ``paper1-v4-frozen-config``).
PAPER1_V4_RECIPE: dict[str, Any] = {
    "name": "paper1-v4-frozen-config",
    "git_tag": "paper1-v4-frozen-config",
    "guard": "on (GuardConfig defaults, combine=max)",
    "policy_fit": "grid search, max eWPM s.t. plug-in wrong-commit <= 0.05",
    "commit_threshold": "max(grid commit_p, LTT lambda_hat)",
    "risk_control": {"method": "ltt", "alpha": 0.05, "delta": 0.1, "pvalue": "auto (binomial for 0/1 losses)",
                     "grid": "1.00 to 0.00, step 0.01", "combine": "max"},
    "calibration": "clean calibration half, same user and session (exchangeable)",
}


def _enc(x: Any) -> Any:
    """JSON-safe value: non-finite floats become strings."""
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, float):
        if math.isnan(x):
            return "nan"
        if math.isinf(x):
            return "inf" if x > 0 else "-inf"
        return x
    if isinstance(x, dict):
        return {str(k): _enc(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_enc(v) for v in x]
    if hasattr(x, "item") and callable(x.item):  # numpy scalar
        return _enc(x.item())
    return x


_NONFINITE = {"nan": math.nan, "inf": math.inf, "-inf": -math.inf}


def _dec_float(x: Any) -> float:
    if isinstance(x, str):
        return _NONFINITE[x]
    return float(x)


def _canonical(obj: Any) -> str:
    return json.dumps(_enc(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class FrozenTrustConfig:
    """The fitted state of the trust core (module docstring)."""

    name: str = ""
    frame_temperature: float = 1.0
    sentence_temperature: float = 1.0
    char_temperature: float = 1.0
    conformal_alpha: float = 0.1
    conformal_score: str = "lac"
    conformal_mode: str = "conditional"
    #: Split-conformal threshold. nan = not fitted (every candidate is in the set).
    conformal_q: float = math.nan
    #: :class:`~fidetype.trust.guard.GuardConfig` fields.
    guard: dict[str, Any] = field(default_factory=dict)
    #: :class:`~fidetype.trust.policy.PolicyConfig` fields (``commit_p`` is final).
    policy: dict[str, Any] = field(default_factory=dict)
    use_guard: bool = True
    #: Alternatives kept per word slot (OFFER_WORDS only).
    word_max_alternatives: int = 5
    #: "trust" (DecisionPolicy) or "always_commit".
    policy_class: str = "trust"
    #: Risk-control record (method, alpha, delta, threshold, feasible, n, bound, combine).
    risk_control: dict[str, Any] = field(default_factory=dict)
    #: Free description of how the numbers were made (for example PAPER1_V4_RECIPE).
    recipe: dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA

    # --- construction -------------------------------------------------------

    @classmethod
    def from_pipeline(cls, pipe: Any, name: str = "", recipe: dict[str, Any] | None = None) -> "FrozenTrustConfig":
        """Freeze a fitted :class:`~fidetype.eval.harness.TrustPipeline`."""
        from fidetype.trust.policy import DecisionPolicy

        cfg = pipe.config
        fr = dict(getattr(pipe, "fit_report", {}) or {})
        pol = pipe.policy
        is_trust = isinstance(pol, DecisionPolicy)
        rc = {}
        if "risk_control_method" in fr:
            rc = {
                "method": fr.get("risk_control_method"),
                "alpha": fr.get("risk_control_alpha"),
                "delta": fr.get("risk_control_delta"),
                "threshold": fr.get("risk_control_threshold"),
                "feasible": fr.get("risk_control_feasible"),
                "n": fr.get("risk_control_n"),
                "bound": fr.get("risk_control_bound"),
                "combine": cfg.risk_control_combine,
            }
        return cls(
            name=name,
            frame_temperature=float(pipe.frame_scaler.temperature),
            sentence_temperature=float(pipe.calibrator.sentence.temperature),
            char_temperature=float(pipe.calibrator.char.temperature),
            conformal_alpha=float(pipe.conformal.alpha),
            conformal_score=str(pipe.conformal.score),
            conformal_mode=str(pipe.conformal.mode),
            conformal_q=float(pipe.conformal.q),
            guard=asdict(pipe.guard.config),
            policy=asdict(pol.config) if is_trust else {},
            use_guard=bool(pol.use_guard) if is_trust else bool(cfg.use_guard),
            word_max_alternatives=int(cfg.word_max_alternatives),
            policy_class="trust" if is_trust else "always_commit",
            risk_control=rc,
            recipe=dict(recipe or {}),
        )

    # --- serialisation ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return _enc(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"

    @property
    def config_id(self) -> str:
        """SHA-256 of the canonical JSON: ``"tcfg-" + 16 hex``."""
        return "tcfg-" + hashlib.sha256(_canonical(asdict(self)).encode("utf-8")).hexdigest()[:16]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FrozenTrustConfig":
        if d.get("schema", SCHEMA) != SCHEMA:
            raise ValueError(f"unknown trust-config schema {d.get('schema')!r} (expected {SCHEMA!r})")
        known = {f.name for f in fields(cls)}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"unknown trust-config keys {sorted(unknown)}")
        kw = dict(d)
        for k in ("frame_temperature", "sentence_temperature", "char_temperature", "conformal_alpha", "conformal_q"):
            if k in kw:
                kw[k] = _dec_float(kw[k])
        kw["policy"] = _decode_policy(kw.get("policy", {}))
        kw["guard"] = dict(kw.get("guard", {}))
        rc = dict(kw.get("risk_control", {}))
        for k in ("threshold", "bound", "alpha", "delta"):
            if isinstance(rc.get(k), str):
                rc[k] = _dec_float(rc[k])
        kw["risk_control"] = rc
        return cls(**kw)

    def save(self, path: str | PathLike[str]) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: str | PathLike[str]) -> "FrozenTrustConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # --- live objects -------------------------------------------------------

    def build(self) -> "TrustComponents":
        """Return the live trust-core objects of this configuration."""
        from fidetype.trust.calibration import NBestCalibrator, TemperatureScaler
        from fidetype.trust.conformal import SplitConformal
        from fidetype.trust.guard import GuardConfig, HallucinationGuard
        from fidetype.trust.policy import AlwaysCommitPolicy, DecisionPolicy, PolicyConfig

        frame = TemperatureScaler()
        frame.temperature = float(self.frame_temperature)
        sent = TemperatureScaler()
        sent.temperature = float(self.sentence_temperature)
        char = TemperatureScaler()
        char.temperature = float(self.char_temperature)
        conf = SplitConformal(self.conformal_alpha, self.conformal_score, self.conformal_mode)  # type: ignore[arg-type]
        conf.q = float(self.conformal_q)
        guard = HallucinationGuard(GuardConfig(**self.guard))
        if self.policy_class == "always_commit":
            policy: Any = AlwaysCommitPolicy()
        elif self.policy_class == "trust":
            policy = DecisionPolicy(PolicyConfig(**self.policy), use_guard=self.use_guard)
        else:
            raise ValueError(f"unknown policy_class {self.policy_class!r}")
        return TrustComponents(frame, NBestCalibrator(sent, char), conf, guard, policy)

    def with_policy(self, **changes: Any) -> "FrozenTrustConfig":
        """A copy with some policy fields changed (for experiments)."""
        return replace(self, policy={**self.policy, **changes})


def _decode_policy(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    for k in ("commit_p", "commit_max_risk", "abstain_risk", "word_conf_threshold", "offer_words_min_conf"):
        if k in out and out[k] is not None:
            out[k] = _dec_float(out[k])
    return out


@dataclass
class TrustComponents:
    """The live objects of a :class:`FrozenTrustConfig`."""

    frame_scaler: Any
    calibrator: Any
    conformal: Any
    guard: Any
    policy: Any


def paper1_v4_harness_config(**overrides: Any) -> Any:
    """Harness settings of the Paper 1 v4 frozen recipe (guard + LTT max).

    Returns a :class:`~fidetype.eval.harness.HarnessConfig`. Fit a
    :class:`~fidetype.eval.harness.TrustPipeline` with it on the user's
    calibration data (``val`` is split: the first half fits the policy
    grid, the second half is the LTT calibration half), then freeze the
    result with :meth:`FrozenTrustConfig.from_pipeline` and
    ``recipe=PAPER1_V4_RECIPE``.
    """
    from fidetype.eval.harness import HarnessConfig

    kw: dict[str, Any] = dict(
        use_guard=True,
        max_wrong_commit=0.05,
        risk_control="ltt",
        risk_control_delta=0.1,
        risk_control_fraction=0.5,
        risk_control_combine="max",
    )
    kw.update(overrides)
    return HarnessConfig(**kw)
