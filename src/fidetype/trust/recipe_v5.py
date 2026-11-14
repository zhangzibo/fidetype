"""Trust v5 candidate recipe (P5-07): v4 plus four switchable safety changes.

The Paper 1 v4 recipe (:data:`fidetype.trust.frozen.PAPER1_V4_RECIPE`)
has known weak points (M2-18, M3-02, P12):

1. The policy grid contains ``commit_max_risk = 1.0``. That value turns
   the guard limit off. A fit that picks it can COMMIT empty texts on
   no-signal input (M2-18: 335/400 uniform T12 streams).
2. The grid fit sees only real, labelled streams. It cannot see what a
   grid point does on input without signal.
3. A decoder can give a confident output on zero input. Risk control
   cannot see that, because the calibration data has no such input
   (P12: 37 % of zero-input key presses acted on).
4. The declaration check has only "warn" (no change) and "abstain"
   (also no OFFER, so eWPM falls below gaze typing; M3-02).

This module does **not** change v4. ``PAPER1_V4_RECIPE`` and every
existing configuration id stay as they are. The v5 candidate is a new
recipe record (:data:`TRUST_V5_CANDIDATE`), so a frozen v5
configuration has its own ``config_id``.

Changes (each one is a switch of :class:`V5Options`, so it can be ablated)
--------------------------------------------------------------------------
(a) ``commit_gate``: commit gate B on (``CommitGate(1, 0, 1.0)``): no
    empty COMMIT and no COMMIT at guard risk 1.0.
(b) ``control_aware_fit``: a grid point is allowed only if it commits at
    most ``control_limit`` (1 %) of each kind of control copy of the
    grid-fit streams: uniform, frame-shuffled and the zero-input
    stand-in (every frame = the first frame). The copies need no labels.
(c) ``max_risk_grid``: ``"keep"`` (v4 grid) or ``"no-1.0"`` (1.0 in the
    ``commit_max_risk`` grid is replaced by 0.8).
(d) ``no_signal_reference``: after LTT, ``commit_p`` is raised to the
    smallest value on the 0.01 grid at which at most ``control_limit``
    of each no-signal reference kind (uniform and zero-input copies)
    is committed (as the P12 no-signal reference).
(e) ``declaration_check``: the streaming setting. ``"offer-only"`` (new):
    a declaration mismatch blocks COMMIT but keeps OFFER / ASK.

Why the risk bound stays valid
------------------------------
(b) and (c) only change the grid fit on the fit-A streams; the LTT
calibration half is not touched. (d) only raises ``commit_p`` above the
LTT value, and LTT (fixed-sequence testing from 1.00 down) certifies
every grid value above its ``lambda_hat`` too. (a) only removes commits
(M2-18). So the v4 guarantee (wrong-commit rate <= alpha with
probability >= 1 - delta, exchangeable data) holds for v5.

The controls are not a guarantee: they only stop grid points that
commit on the known no-signal patterns.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable, Literal, Sequence

import numpy as np

from fidetype.eval.ewpm import summarize
from fidetype.eval.harness import HarnessConfig, TrustPipeline, as_items
from fidetype.streams.spec import NeuralTextStream
from fidetype.trust.content import CommitGate, GatedPolicy
from fidetype.trust.guard import shuffle_stream, uniform_stream
from fidetype.trust.policy import DEFAULT_GRID, DecisionPolicy, PolicyConfig, PolicyInputs, fit_thresholds

#: Gate B of M2-18.
GATE_B: dict[str, Any] = {"min_chars": 1, "min_words": 0, "max_guard_risk": 1.0}
#: Control kinds of the control-aware grid fit (b).
CONTROL_KINDS: tuple[str, ...] = ("uniform", "frame_shuffled", "zero_standin")
#: No-signal reference kinds of (d).
REFERENCE_KINDS: tuple[str, ...] = ("uniform", "zero_standin")
#: The ``commit_p`` grid of the reference floor (d): 0.00 to 1.00, step 0.01.
FLOOR_GRID: tuple[float, ...] = tuple(round(i / 100, 2) for i in range(101))
#: commit_max_risk value that replaces 1.0 with ``max_risk_grid="no-1.0"`` (c).
NO_ONE_MAX_RISK = 0.8


@dataclass(frozen=True)
class V5Options:
    """The switches of the v5 candidate (module docstring). Defaults = the v5 candidate."""

    #: (a) commit gate B on.
    commit_gate: bool = True
    #: (b) control-aware grid fit.
    control_aware_fit: bool = True
    #: (c) "keep" (v4 commit_max_risk grid) or "no-1.0" (1.0 replaced by 0.8).
    max_risk_grid: Literal["keep", "no-1.0"] = "keep"
    #: (d) no-signal reference floor on commit_p.
    no_signal_reference: bool = True
    #: (e) streaming declaration check ("off", "warn", "abstain", "offer-only").
    declaration_check: Literal["off", "warn", "abstain", "offer-only"] = "offer-only"
    #: Largest allowed commit rate on each control / reference kind (b, d).
    control_limit: float = 0.01
    #: Control copies per kind (a random subset of the grid-fit streams if there are more).
    n_control: int = 200
    #: Seed of the control copies.
    control_seed: int = 0
    #: Jitter of the uniform copies (as the Paper 1 controls).
    uniform_jitter: float = 0.05

    def __post_init__(self) -> None:
        if self.max_risk_grid not in ("keep", "no-1.0"):
            raise ValueError(f"unknown max_risk_grid {self.max_risk_grid!r}")
        if self.declaration_check not in ("off", "warn", "abstain", "offer-only"):
            raise ValueError(f"unknown declaration_check {self.declaration_check!r}")
        if not 0.0 <= self.control_limit < 1.0:
            raise ValueError("control_limit must be in [0, 1)")
        if self.n_control < 1:
            raise ValueError("n_control must be >= 1")

    @property
    def gate(self) -> CommitGate | None:
        return CommitGate(**GATE_B) if self.commit_gate else None

    def grid(self, base: dict[str, Sequence[Any]] | None = None) -> dict[str, Sequence[Any]]:
        """The policy grid of these options (``base`` default: DEFAULT_GRID)."""
        g = dict(DEFAULT_GRID if base is None else base)
        if self.max_risk_grid == "no-1.0":
            g["commit_max_risk"] = tuple(NO_ONE_MAX_RISK if float(v) >= 1.0 else v for v in g["commit_max_risk"])
        return g

    def streaming_config(self, **kw: Any) -> Any:
        """A :class:`~fidetype.trust.streaming.StreamingConfig` with this declaration check."""
        from fidetype.trust.streaming import StreamingConfig

        return StreamingConfig(declaration_check=self.declaration_check, **kw)


def _switches(o: V5Options) -> tuple:
    """The safety switches (a)-(e) and the control limit; n_control and the seed are fit details."""
    return (o.commit_gate, o.control_aware_fit, o.max_risk_grid, o.no_signal_reference, o.declaration_check,
            o.control_limit)


def v5_recipe(options: V5Options | None = None) -> dict[str, Any]:
    """The recipe record of a v5 configuration (goes into ``FrozenTrustConfig.recipe``)."""
    o = options or V5Options()
    lim = o.control_limit
    return {
        "name": "trust-v5-candidate" if _switches(o) == _switches(V5Options()) else "trust-v5-candidate-variant",
        "status": "candidate (P5-07); not the default for new configurations",
        "base": "paper1-v4-frozen-config",
        "guard": "on (GuardConfig defaults, combine=max)",
        "policy_fit": "grid search, max eWPM s.t. plug-in wrong-commit <= 0.05"
        + (f"; each control kind {list(CONTROL_KINDS)} of the grid-fit streams committed <= {lim}" if o.control_aware_fit else ""),
        "commit_max_risk_grid": [float(v) for v in o.grid()["commit_max_risk"]],
        "commit_threshold": "max(grid commit_p, LTT lambda_hat"
        + (", no-signal reference floor)" if o.no_signal_reference else ")"),
        "risk_control": {"method": "ltt", "alpha": 0.05, "delta": 0.1, "pvalue": "auto (binomial for 0/1 losses)",
                         "grid": "1.00 to 0.00, step 0.01", "combine": "max"},
        "no_signal_reference": ({"kinds": list(REFERENCE_KINDS), "limit": lim, "grid": "0.00 to 1.00, step 0.01"}
                                if o.no_signal_reference else None),
        "commit_gate": dict(GATE_B) if o.commit_gate else None,
        "declaration_check": o.declaration_check,
        "controls": {"n_per_kind": o.n_control, "seed": o.control_seed, "uniform_jitter": o.uniform_jitter},
        "calibration": "clean calibration half, same user and session (exchangeable)",
        "options": asdict(o),
    }


#: The v5 candidate recipe record (all switches at their defaults).
TRUST_V5_CANDIDATE: dict[str, Any] = v5_recipe(V5Options())


# ---------------------------------------------------------------------------
# Control copies (no labels)
# ---------------------------------------------------------------------------

def zero_standin(stream: NeuralTextStream) -> NeuralTextStream:
    """Zero-input stand-in: every frame = the stream's first frame (pre-signal rest)."""
    lp = np.repeat(np.asarray(stream.log_probs)[:1], stream.log_probs.shape[0], axis=0)
    return replace(stream, log_probs=lp, source=stream.source + "+zero_standin",
                   meta={**stream.meta, "audit": "zero_standin"})


def control_copies(streams: Sequence[NeuralTextStream], options: V5Options | None = None,
                   kinds: Iterable[str] = CONTROL_KINDS) -> dict[str, list[NeuralTextStream]]:
    """Signal-destroying copies of ``streams`` (at most ``n_control`` per kind)."""
    o = options or V5Options()
    rng = np.random.default_rng(o.control_seed)
    idx = np.arange(len(streams))
    if len(idx) > o.n_control:
        idx = np.sort(rng.choice(len(idx), o.n_control, replace=False))
    base = [streams[int(i)] for i in idx]
    out: dict[str, list[NeuralTextStream]] = {}
    for k in kinds:
        if k == "uniform":
            out[k] = [uniform_stream(s, rng, o.uniform_jitter) for s in base]
        elif k == "frame_shuffled":
            out[k] = [shuffle_stream(s, rng) for s in base]
        elif k == "zero_standin":
            out[k] = [zero_standin(s) for s in base]
        else:
            raise ValueError(f"unknown control kind {k!r}")
    return out


# ---------------------------------------------------------------------------
# Commit rule on precomputed inputs (fast, for the grid sweep)
# ---------------------------------------------------------------------------

class InputArrays:
    """Policy inputs as arrays, for fast commit counts over many policy configs."""

    def __init__(self, inputs: Sequence[PolicyInputs], use_guard: bool = True, gate: CommitGate | None = None) -> None:
        self.n = len(inputs)
        self.has_text = np.array([bool(x.texts) for x in inputs], bool)
        self.p = np.array([float(x.p_top1) for x in inputs], float)
        self.risk = np.array([float(x.guard_risk) if use_guard else 0.0 for x in inputs], float)
        self.set_size = np.array([x.set_size for x in inputs], int)
        if gate is None:
            self.gate_ok = np.ones(self.n, bool)
        else:
            self.gate_ok = np.array([gate.violation(x.texts[0] if x.texts else "", float(x.guard_risk) if use_guard else None)
                                     is None for x in inputs], bool)

    def eligible(self, cfg: PolicyConfig | dict[str, Any]) -> np.ndarray:
        """Items that ``cfg`` would COMMIT at commit_p = -inf (DecisionPolicy rule order), after the gate."""
        c = cfg if isinstance(cfg, dict) else asdict(cfg)
        ok = self.has_text & (self.risk < float(c["abstain_risk"])) & (self.risk <= float(c["commit_max_risk"]))
        if c.get("commit_max_set") is not None:
            ok &= self.set_size <= int(c["commit_max_set"])
        return ok & self.gate_ok

    def commits(self, cfg: PolicyConfig | dict[str, Any]) -> np.ndarray:
        c = cfg if isinstance(cfg, dict) else asdict(cfg)
        return self.eligible(c) & (self.p >= float(c["commit_p"]))


def control_rates(ctl: dict[str, InputArrays], cfg: PolicyConfig | dict[str, Any]) -> dict[str, float]:
    """Commit rate of ``cfg`` on each control kind."""
    return {k: (float(a.commits(cfg).mean()) if a.n else 0.0) for k, a in ctl.items()}


def select_policy(table: Sequence[tuple[dict[str, Any], dict[str, float]]], max_wrong_commit: float,
                  ctl: dict[str, InputArrays] | None = None, limit: float = 0.01,
                  max_risk_values: Iterable[float] | None = None,
                  max_silent_error: float | None = None) -> tuple[dict[str, Any], dict[str, float], bool]:
    """Select a grid point from a ``fit_thresholds(keep_table=True)`` table.

    Same rule as :func:`~fidetype.trust.policy.fit_thresholds` (highest
    eWPM among feasible points, the first one wins a tie; else the lowest
    wrong-commit rate), on the rows with ``commit_max_risk`` in
    ``max_risk_values`` (None: all rows). With ``ctl``, a row is feasible
    only if its commit rate on every control kind is <= ``limit``. With
    ``ctl=None`` and the v4 grid values this gives exactly the v4 choice.
    Returns (config dict, metrics, feasible).
    """
    allowed = None if max_risk_values is None else {round(float(v), 9) for v in max_risk_values}
    best = fallback = None
    for cfg, m in table:
        if allowed is not None and round(float(cfg["commit_max_risk"]), 9) not in allowed:
            continue
        ok_silent = max_silent_error is None or m.get("silent_error_rate", 0.0) <= max_silent_error + 1e-12
        ok_ctl = ctl is None or all(r <= limit + 1e-12 for r in control_rates(ctl, cfg).values())
        if m["wrong_commit_rate"] <= max_wrong_commit + 1e-12 and ok_silent and ok_ctl:
            if best is None or m["ewpm"] > best[1]["ewpm"] + 1e-12:
                best = (cfg, m)
        if ok_ctl:
            key = (m["wrong_commit_rate"], -m["ewpm"])
            if fallback is None or key < (fallback[1]["wrong_commit_rate"], -fallback[1]["ewpm"]):
                fallback = (cfg, m)
    if best is not None:
        return dict(best[0]), dict(best[1]), True
    if fallback is None:
        raise ValueError("no grid row passes the control limit (add commit_p > 1 to the grid)")
    return dict(fallback[0]), dict(fallback[1]), False


def reference_floor(ref: dict[str, InputArrays], cfg: PolicyConfig | dict[str, Any], limit: float = 0.01,
                    grid: Sequence[float] = FLOOR_GRID) -> float:
    """Smallest ``commit_p`` on ``grid`` with commit rate <= ``limit`` on every reference kind (+inf if none)."""
    c = cfg if isinstance(cfg, dict) else asdict(cfg)
    floor = -math.inf
    for a in ref.values():
        if not a.n:
            continue
        p = np.sort(a.p[a.eligible(c)])[::-1]
        k = int(math.floor(limit * a.n + 1e-9))  # allowed commits
        if p.size <= k:
            continue
        # commits(lam) = #{p >= lam} <= k  <=>  lam > p[k] (the (k+1)-th largest)
        lam = next((g for g in grid if g > p[k] + 1e-12), math.inf)
        floor = max(floor, lam)
    return floor


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def trust_v5_harness_config(options: V5Options | None = None, **overrides: Any) -> HarnessConfig:
    """Harness settings of the v5 candidate (guard on; grid of option (c); risk control set by :func:`fit_trust_v5`)."""
    o = options or V5Options()
    kw: dict[str, Any] = dict(use_guard=True, max_wrong_commit=0.05, risk_control="none",
                              risk_control_delta=0.1, risk_control_combine="max", grid=o.grid())
    kw.update(overrides)
    return HarnessConfig(**kw)


class V5Pipeline(TrustPipeline):
    """A :class:`TrustPipeline` with the v5 grid fit, floor and gate (module docstring).

    ``control_streams`` (kind -> streams) replaces the default control
    copies of the grid-fit streams. After :meth:`fit` (and after
    :meth:`calibrate_commit`) the policy is a :class:`GatedPolicy` if
    option (a) is on, and ``commit_p`` includes the floor of option (d).
    The full grid table and the control inputs stay on the object
    (``fit_table``, ``control_inputs``) for analysis.
    """

    def __init__(self, decode_fn: Any, config: HarnessConfig | None = None, decode_cache: dict | None = None,
                 options: V5Options | None = None,
                 control_streams: dict[str, list[NeuralTextStream]] | None = None) -> None:
        self.options = options or V5Options()
        super().__init__(decode_fn, config or trust_v5_harness_config(self.options), decode_cache)
        self.control_streams = control_streams
        self.fit_table: list[tuple[dict[str, Any], dict[str, float]]] = []
        self.control_inputs: dict[str, list[PolicyInputs]] = {}
        #: Keep per-item outcomes of every grid point (``fit_outcomes``; for bootstrap stability analyses).
        self.keep_item_outcomes = False
        #: One dict of arrays (wrong_commit, words, time_s) per ``fit_table`` row.
        self.fit_outcomes: list[dict[str, np.ndarray]] = []

    # control inputs at the fitted frame temperature
    def analyze_streams(self, streams: Sequence[NeuralTextStream]) -> list[PolicyInputs]:
        t = self.frame_scaler.temperature
        out = []
        for s in streams:
            s2 = self.frame_scaler.transform_stream(s) if t != 1.0 else s
            out.append(self.analyze(self.decode_fn(s2)).inputs)
        return out

    def _arrays(self, kinds: Iterable[str]) -> dict[str, InputArrays]:
        return {k: InputArrays(self.control_inputs[k], self.config.use_guard, self.options.gate)
                for k in kinds if k in self.control_inputs}

    def _fit_policy(self, val_items: list) -> None:
        cfg = self.config
        o = self.options
        if self.control_streams is None:
            self.control_streams = control_copies([it.stream(0) for it in val_items], o)
        need = set(CONTROL_KINDS if o.control_aware_fit else ()) | set(REFERENCE_KINDS if o.no_signal_reference else ())
        self.control_inputs = {k: self.analyze_streams(v) for k, v in self.control_streams.items() if k in need}
        grid = dict(cfg.grid if cfg.grid is not None else o.grid())
        if not cfg.use_guard:
            grid["commit_max_risk"] = (1.0,)
            grid["abstain_risk"] = (1.01,)
        cache: dict = {}
        self.fit_outcomes = []

        def evaluate(pc: PolicyConfig) -> dict[str, float]:
            recs = self.run_items(val_items, DecisionPolicy(pc, use_guard=cfg.use_guard), cache)
            if self.keep_item_outcomes:
                from fidetype.eval.ewpm import correct_words_strict

                self.fit_outcomes.append({"wrong_commit": np.array([float(r.wrong_commit) for r in recs]),
                                          "words": np.array([float(correct_words_strict(r)) for r in recs]),
                                          "time_s": np.array([float(r.time_s) for r in recs])})
            return summarize(recs)

        res = fit_thresholds(evaluate, grid, cfg.max_wrong_commit, base=cfg.policy_config or PolicyConfig(),
                             keep_table=True, max_silent_error=cfg.max_silent_error)
        self.fit_table = res.table
        ctl = self._arrays(CONTROL_KINDS) if o.control_aware_fit else None
        chosen, m, feasible = select_policy(res.table, cfg.max_wrong_commit, ctl, o.control_limit,
                                            max_silent_error=cfg.max_silent_error)
        pc = PolicyConfig(**chosen)
        self.policy = DecisionPolicy(pc, use_guard=cfg.use_guard)
        self.fit_report.update({
            "policy_config": asdict(pc), "policy_fit_feasible": feasible, "val_ewpm": m["ewpm"],
            "val_wrong_commit_rate": m["wrong_commit_rate"],
            "v5_control_rates_at_grid": control_rates(self._arrays(CONTROL_KINDS), pc) if self.control_inputs else {},
            "v5_n_control": {k: len(v) for k, v in self.control_inputs.items()},
        })
        self._finish_v5()

    def calibrate_commit(self, items: Sequence[Any], method: Any = None, alpha: float | None = None,
                         delta: float | None = None, combine: Any = None) -> Any:
        if isinstance(self.policy, GatedPolicy):  # LTT is fitted on the ungated policy (the gate only removes commits)
            self.policy = DecisionPolicy(self.policy.config, use_guard=self.policy.use_guard)
        r = super().calibrate_commit(items, method, alpha, delta, combine)
        self._finish_v5()
        return r

    def _finish_v5(self) -> None:
        """Apply the reference floor (d) and the gate (a). Idempotent."""
        o = self.options
        pol = self.policy
        if not isinstance(pol, DecisionPolicy):
            return
        base = DecisionPolicy(pol.config, use_guard=pol.use_guard)
        if o.no_signal_reference and self.control_inputs:
            fl = reference_floor(self._arrays(REFERENCE_KINDS), base.config, o.control_limit)
            self.fit_report["v5_reference_floor"] = fl
            if fl > base.config.commit_p:
                base = DecisionPolicy(replace(base.config, commit_p=fl), use_guard=base.use_guard)
        self.fit_report["v5_commit_p"] = base.config.commit_p
        self.policy = GatedPolicy.wrap(base, o.gate) if o.gate is not None else base


def fit_trust_v5(decode_fn: Any, fit_items: Sequence[Any], cal_items: Sequence[Any], options: V5Options | None = None,
                 control_streams: dict[str, list[NeuralTextStream]] | None = None, decode_cache: dict | None = None,
                 **harness_overrides: Any) -> V5Pipeline:
    """Fit the v5 candidate: calibration + grid on ``fit_items``, LTT on ``cal_items``, then floor and gate."""
    o = options or V5Options()
    pipe = V5Pipeline(decode_fn, trust_v5_harness_config(o, **harness_overrides), decode_cache, o, control_streams)
    fit = as_items(fit_items)
    pipe.fit(fit, fit)
    pipe.calibrate_commit(cal_items, method="ltt", alpha=pipe.config.max_wrong_commit,
                          delta=pipe.config.risk_control_delta, combine="max")
    return pipe


def freeze_v5(pipe: V5Pipeline, name: str = "") -> Any:
    """:class:`~fidetype.trust.frozen.FrozenTrustConfig` of a fitted v5 pipeline (recipe = its options)."""
    from fidetype.trust.frozen import FrozenTrustConfig

    return FrozenTrustConfig.from_pipeline(pipe, name=name, recipe=v5_recipe(pipe.options))
