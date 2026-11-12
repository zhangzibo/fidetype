"""Evaluation harness for the trust core.

:func:`run_harness` runs every stage on lists of (stream, true text)::

    decode -> calibrate -> conformal -> guard -> policy -> simulated user

and returns one flat metrics dict. The decoder is pluggable: any
``decode_fn(stream) -> NBest`` works (see :mod:`fidetype.trust.types`).

Splits
------
- ``calib``: the first part (``1 - conformal_fraction``) fits the
  temperatures: first a frame-level T on the greedy CTC peaks (the
  harness applies it to every stream *before* ``decode_fn``, so the LM
  fuses with calibrated evidence), then a sentence-level T on the n-best
  scores. The second part fits the conformal thresholds. Two
  disjoint parts keep the conformal scores exchangeable with the test
  scores (the temperature is fixed before the conformal step).
- ``val``: fits the policy thresholds (max eWPM subject to a maximum
  wrong-commit rate).
- ``test``: all reported metrics.

Repeats
-------
An item can carry a ``regen(attempt) -> stream`` function. After ASK, or
after the user rejects an OFFER, the harness charges a repeat (overhead
plus typing time) and decodes ``regen(attempt)``: a new, independent
input of the same sentence. Without ``regen`` the item has one attempt.
The last attempt cannot repeat: there, the policy runs with
``final_attempt=True``.

Per-word choices
----------------
With ``HarnessConfig.offer_words`` (or a ``policy_config`` with
``offer_words=True``), :meth:`TrustPipeline.analyze` also computes the
word slots of the top-1 sentence with ``fidetype.lm.word_alternatives``
(calibrated sentence posteriors), and the policy fit adds ``word_grid``
(default :data:`~fidetype.trust.policy.OFFER_WORDS_GRID`). The word
model of the simulated user is set in ``user_config`` (see
``UserConfig.aac_gaze``). With the defaults nothing changes.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Literal, Sequence

import numpy as np

from fidetype.eval.ewpm import SentenceRecord, summarize
from fidetype.eval.metrics import ctc_greedy_decode, edit_distance, expected_calibration_error
from fidetype.interact.simulated_user import SimulatedUser, UserConfig
from fidetype.streams.spec import NeuralTextStream
from fidetype.trust.calibration import NBestCalibrator, TemperatureScaler, fit_frame_temperature, greedy_peaks
from fidetype.trust.conformal import PredictionSet, SplitConformal, WordConformal
from fidetype.trust.guard import GuardConfig, GuardScore, HallucinationGuard, auroc
from fidetype.trust.policy import (
    DEFAULT_GRID,
    OFFER_WORDS_GRID,
    Action,
    AlwaysCommitPolicy,
    DecisionPolicy,
    PolicyConfig,
    PolicyInputs,
    WordSlotInfo,
    fit_thresholds,
)
from fidetype.trust.types import NBest

DecodeFn = Callable[[NeuralTextStream], NBest]


class Item:
    """One intended sentence: its first stream and an optional ``regen``.

    ``stream_text`` is the truth in the token space of the stream, if it
    differs from ``text``. Example: a phoneme stream (``text`` is words,
    ``stream_text`` is the phoneme string). Only the frame-level steps use
    it: the frame temperature fit, the character ECE and ``greedy_cer``.
    The default (None) means ``text``.
    """

    def __init__(
        self,
        stream: NeuralTextStream,
        text: str,
        regen: Callable[[int], NeuralTextStream] | None = None,
        stream_text: str | None = None,
    ) -> None:
        self.text = text
        self.stream_text = text if stream_text is None else stream_text
        self._streams: dict[int, NeuralTextStream] = {0: stream}
        self.regen = regen

    @property
    def max_attempts(self) -> int:
        return 1 if self.regen is None else 10**9

    def stream(self, attempt: int) -> NeuralTextStream:
        if attempt not in self._streams:
            if self.regen is None:
                raise ValueError("this item has no regen function")
            self._streams[attempt] = self.regen(attempt)
        return self._streams[attempt]


def as_items(items: Sequence[Any]) -> list[Item]:
    out = []
    for it in items:
        out.append(it if isinstance(it, Item) else Item(*it))
    return out


@dataclass
class HarnessConfig:
    alpha: float = 0.1
    conformal_score: Literal["lac", "aps"] = "lac"
    conformal_mode: Literal["conditional", "marginal"] = "conditional"
    conformal_fraction: float = 0.5
    use_calibration: bool = True
    use_guard: bool = True
    policy: Literal["trust", "always_commit"] = "trust"
    policy_config: PolicyConfig | None = None
    fit_policy: bool = True
    grid: dict[str, Sequence[Any]] | None = None
    max_wrong_commit: float = 0.05
    max_attempts: int = 2
    guard_config: GuardConfig = field(default_factory=GuardConfig)
    user_config: UserConfig = field(default_factory=UserConfig)
    seed: int = 0
    #: Fit the OFFER_WORDS thresholds too (and compute the word slots).
    offer_words: bool = False
    #: OFFER_WORDS grid for the fit (None = OFFER_WORDS_GRID).
    word_grid: dict[str, Sequence[Any]] | None = None
    #: Optional second fit limit, on the silent-error rate.
    max_silent_error: float | None = None
    #: Alternatives kept per word slot.
    word_max_alternatives: int = 5
    #: Finite-sample control of the wrong-commit rate (M2-13; see
    #: :mod:`fidetype.trust.risk_control`). "crc" or "ltt": the last
    #: ``risk_control_fraction`` of ``val`` is held out; the policy grid is
    #: fitted on the rest; then ``commit_p`` is calibrated on the held-out
    #: part with target ``max_wrong_commit``. "none" keeps the old fit.
    risk_control: Literal["none", "crc", "ltt"] = "none"
    risk_control_fraction: float = 0.5
    risk_control_delta: float = 0.1
    #: "max": keep the grid commit_p if it is stricter (still valid).
    risk_control_combine: Literal["replace", "max"] = "max"


@dataclass
class Analysis:
    """All trust-core outputs for one decoded attempt."""

    nbest: NBest  # character confidences calibrated
    raw_nbest: NBest
    raw_posteriors: np.ndarray
    posteriors: np.ndarray
    pset: PredictionSet
    guard: GuardScore
    inputs: PolicyInputs


class TrustPipeline:
    """The trust core plus the simulated user, fitted on calib/val items."""

    def __init__(
        self,
        decode_fn: DecodeFn,
        config: HarnessConfig | None = None,
        decode_cache: dict | None = None,
    ) -> None:
        self.decode_fn = decode_fn
        self.config = config or HarnessConfig()
        self.decode_cache = {} if decode_cache is None else decode_cache
        self.frame_scaler = TemperatureScaler()
        self.calibrator = NBestCalibrator.identity()
        self.conformal = SplitConformal(self.config.alpha, self.config.conformal_score, self.config.conformal_mode)
        self.word_conformal = WordConformal(self.config.alpha)
        self.guard = HallucinationGuard(self.config.guard_config)
        self.user = SimulatedUser(self.config.user_config, seed=self.config.seed)
        self.policy: DecisionPolicy | AlwaysCommitPolicy = (
            AlwaysCommitPolicy()
            if self.config.policy == "always_commit"
            else DecisionPolicy(self.config.policy_config, use_guard=self.config.use_guard)
        )
        self.fit_report: dict[str, Any] = {}

    # --- decoding and analysis ------------------------------------------

    def decode(self, item: Item, attempt: int) -> NBest:
        """Calibrate the stream at frame level (if fitted), then decode it."""
        t = self.frame_scaler.temperature
        key = (id(item), attempt, round(t, 9))
        hit = self.decode_cache.get(key)
        if hit is not None:
            return hit[0]
        stream = item.stream(attempt)
        if t != 1.0:
            stream = self.frame_scaler.transform_stream(stream)
        nb = self.decode_fn(stream)
        self.decode_cache[key] = (nb, item)  # keep the item alive so its id stays unique
        return nb

    def analyze(self, raw: NBest) -> Analysis:
        nb = self.calibrator.calibrate_chars(raw)
        raw_post = NBestCalibrator.identity().posteriors(raw)
        post = self.calibrator.posteriors(raw)
        if math.isnan(self.conformal.q):  # not fitted: no set information
            pset = PredictionSet(list(range(len(raw))))
        else:
            pset = self.conformal.predict(post)
        g = self.guard.score(nb, post)
        slots: tuple = ()
        if self._needs_word_slots() and len(nb):
            from fidetype.lm import word_alternatives  # lazy: only for OFFER_WORDS

            ws = word_alternatives(nb.candidates, posteriors=post, max_alternatives=self.config.word_max_alternatives)
            slots = tuple(WordSlotInfo(w.word, tuple(w.alternatives)) for w in ws)
        inputs = PolicyInputs(
            texts=tuple(nb.texts),
            p_top1=float(post[0]) if len(post) else 0.0,
            set_indices=tuple(pset.indices),
            includes_other=pset.includes_other,
            guard_risk=g.risk,
            word_slots=slots,
        )
        return Analysis(nb, raw, raw_post, post, pset, g, inputs)

    def _needs_word_slots(self) -> bool:
        pc = self.config.policy_config
        return self.config.offer_words or (pc is not None and pc.offer_words)

    # --- fitting ----------------------------------------------------------

    def fit(self, calib: Sequence[Any], val: Sequence[Any] | None = None) -> "TrustPipeline":
        cfg = self.config
        calib_items = as_items(calib)
        n_conf = int(round(len(calib_items) * cfg.conformal_fraction))
        temp_items, conf_items = calib_items[: len(calib_items) - n_conf], calib_items[len(calib_items) - n_conf :]
        if cfg.use_calibration and temp_items:
            # 1. Frame level, before LM fusion. 2. Sentence level, on the n-best scores.
            self.frame_scaler = fit_frame_temperature(
                [it.stream(0) for it in temp_items], [it.stream_text for it in temp_items]
            )
            nbs = [self.decode(it, 0) for it in temp_items]
            self.calibrator = NBestCalibrator.fit(nbs, [it.text for it in temp_items], fit_char=False)
        conf_items = conf_items or temp_items
        posts, idx, texts = [], [], []
        for it in conf_items:
            nb = self.decode(it, 0)
            p = self.calibrator.posteriors(nb)
            posts.append(p)
            idx.append(nb.index_of(it.text))
            texts.append(nb.texts)
        self.conformal.fit(posts, idx)
        self.word_conformal.fit(texts, posts, [it.text for it in conf_items])
        self.fit_report = {
            "temperature_frame": self.frame_scaler.temperature,
            "temperature_sentence": self.calibrator.sentence.temperature,
            "temperature_char": self.calibrator.char.temperature,
            "conformal_q": self.conformal.q,
            "word_conformal_q": self.word_conformal.q,
            "calib_miss_rate": self.conformal.calibration_miss_rate,
        }
        if val is not None and cfg.policy == "trust" and cfg.fit_policy:
            val_items = as_items(val)
            if cfg.risk_control != "none":
                n_rc = int(round(len(val_items) * cfg.risk_control_fraction))
                if n_rc <= 0 or n_rc >= len(val_items):
                    raise ValueError("risk_control_fraction must leave items for both the grid fit and the calibration")
                self._fit_policy(val_items[: len(val_items) - n_rc])
                self.calibrate_commit(val_items[len(val_items) - n_rc :])
            else:
                self._fit_policy(val_items)
        return self

    def calibrate_commit(
        self,
        items: Sequence[Any],
        method: Literal["crc", "ltt"] | None = None,
        alpha: float | None = None,
        delta: float | None = None,
        combine: Literal["replace", "max"] | None = None,
    ) -> Any:
        """Set ``commit_p`` with conformal risk control (or LTT) on ``items``.

        ``items`` must have known truth, must not have been used for any
        other fit, and must be exchangeable with the items of use (same
        user, same session). Defaults come from the config; ``alpha``
        defaults to ``max_wrong_commit``. Returns the
        :class:`~fidetype.trust.risk_control.RiskControlResult`.
        """
        from fidetype.trust.risk_control import CommitRiskControl

        cfg = self.config
        if not isinstance(self.policy, DecisionPolicy):
            raise TypeError("calibrate_commit needs a DecisionPolicy")
        method = method or (cfg.risk_control if cfg.risk_control != "none" else "crc")
        rc = CommitRiskControl(
            alpha=cfg.max_wrong_commit if alpha is None else alpha,
            method=method,
            delta=cfg.risk_control_delta if delta is None else delta,
        )
        its = as_items(items)
        inputs = [self.analyze(self.decode(it, 0)).inputs for it in its]
        rc.fit_policy(self.policy, inputs, [it.text for it in its])
        self.policy = rc.apply(self.policy, combine or cfg.risk_control_combine)
        r = rc.result
        self.fit_report.update(
            {
                "risk_control_method": r.method,
                "risk_control_threshold": r.threshold,
                "risk_control_feasible": r.feasible,
                "risk_control_n": r.n,
                "risk_control_bound": r.bound,
                "risk_control_commit_p": self.policy.config.commit_p,
            }
        )
        return r

    def _fit_policy(self, val_items: list[Item]) -> None:
        cfg = self.config
        cache: dict[tuple[int, int], Analysis] = {}
        grid = dict(cfg.grid if cfg.grid is not None else DEFAULT_GRID)
        if not cfg.use_guard:
            grid["commit_max_risk"] = (1.0,)
            grid["abstain_risk"] = (1.01,)

        def evaluate(pc: PolicyConfig) -> dict[str, float]:
            pol = DecisionPolicy(pc, use_guard=cfg.use_guard)
            return summarize(self.run_items(val_items, pol, cache))

        word_grid = None
        if cfg.offer_words:
            word_grid = dict(cfg.word_grid if cfg.word_grid is not None else OFFER_WORDS_GRID)
        res = fit_thresholds(
            evaluate, grid, cfg.max_wrong_commit, base=cfg.policy_config or PolicyConfig(),
            word_grid=word_grid, max_silent_error=cfg.max_silent_error,
        )
        self.policy = DecisionPolicy(res.config, use_guard=cfg.use_guard)
        self.fit_report.update(
            {
                "policy_config": asdict(res.config),
                "policy_fit_feasible": res.feasible,
                "val_ewpm": res.metrics["ewpm"],
                "val_wrong_commit_rate": res.metrics["wrong_commit_rate"],
            }
        )

    # --- interaction -------------------------------------------------------

    def run_items(
        self,
        items: Sequence[Item],
        policy: Any = None,
        cache: dict[tuple[int, int], Analysis] | None = None,
    ) -> list[SentenceRecord]:
        policy = policy or self.policy
        cache = {} if cache is None else cache
        cfg = self.config
        user = self.user
        records = []
        for i, it in enumerate(items):
            max_a = max(1, min(cfg.max_attempts, it.max_attempts))
            t = user.typing_time(it.text)
            actions: list[str] = []
            committed, wrong, silent, final, comm = None, False, False, None, False
            breakdown: dict[str, float] = {"typing": t}
            keys = 0
            o = None
            system_text = None
            for a in range(max_a):
                if a > 0:
                    rc = user.repeat_cost(it.text)
                    t += rc
                    breakdown["repeat"] = breakdown.get("repeat", 0.0) + rc
                    actions.append("REPEAT")
                key = (id(it), a)
                an = cache.get(key)
                if an is None:
                    an = self.analyze(self.decode(it, a))
                    cache[key] = an
                final_attempt = a == max_a - 1
                d = policy.decide(an.inputs, final_attempt=final_attempt)
                actions.append(d.action.value)
                o = user.respond(
                    d, it.text, can_repeat=not final_attempt, rng=np.random.default_rng([cfg.seed, i, a])
                )
                t += o.time_s
                keys += o.keystrokes
                system_text = an.inputs.texts[0] if an.inputs.texts else None
                for k, v in o.breakdown.items():
                    breakdown[k] = breakdown.get(k, 0.0) + v
                if d.action == Action.COMMIT:
                    committed = d.shown_candidates[0] if d.shown_candidates else ""
                    wrong = o.wrong_commit
                elif d.action == Action.OFFER_WORDS:
                    wrong = o.wrong_commit
                final, comm, silent = o.final_text, o.communicated, o.silent_error
                if not o.needs_repeat:
                    break
            rec = SentenceRecord(it.text, final, comm, t, actions, committed, wrong, silent, breakdown)
            if o is not None:
                rec.words_system, rec.words_selected, rec.words_typed = o.words_system, o.words_selected, o.words_typed
                rec.n_missed = o.n_missed
            rec.keystrokes = keys
            rec.system_text = system_text
            records.append(rec)
        return records

    # --- evaluation ----------------------------------------------------------

    def evaluate(self, test: Sequence[Any]) -> dict[str, Any]:
        items = as_items(test)
        cache: dict[tuple[int, int], Analysis] = {}
        analyses = []
        for it in items:
            an = self.analyze(self.decode(it, 0))
            cache[(id(it), 0)] = an
            analyses.append(an)
        truths = [it.text for it in items]
        tops = [an.nbest.texts[0] if len(an.nbest) else "" for an in analyses]
        n_chars = sum(len(t) for t in truths)
        n_words = sum(len(t.split()) for t in truths)
        m: dict[str, Any] = {
            "n_test": len(items),
            "cer": sum(edit_distance(t, h) for t, h in zip(truths, tops)) / n_chars,
            "wer": sum(edit_distance(t.split(), h.split()) for t, h in zip(truths, tops)) / n_words,
            "greedy_cer": sum(edit_distance(it.stream_text, ctc_greedy_decode(it.stream(0))) for it in items)
            / max(1, sum(len(it.stream_text) for it in items)),
            "top1_sentence_acc": float(np.mean([t == h for t, h in zip(truths, tops)])),
        }
        top1_ok = np.array([t == h for t, h in zip(truths, tops)])
        p_raw = np.array([an.raw_posteriors[0] if len(an.raw_posteriors) else 0.0 for an in analyses])
        p_cal = np.array([an.posteriors[0] if len(an.posteriors) else 0.0 for an in analyses])
        m["ece_sentence_before"] = expected_calibration_error(p_raw, top1_ok)
        m["ece_sentence_after"] = expected_calibration_error(p_cal, top1_ok)
        # Character ECE on the greedy CTC peaks (acoustic evidence only).
        c_raw, c_cal, c_ok = [], [], []
        for it in items:
            s = it.stream(0)
            pk = greedy_peaks(s, it.stream_text)
            c_raw.append(pk["confidence"])
            c_ok.append(pk["correct"])
            lp = self.frame_scaler.transform_logits(s.log_probs[pk["centres"]]) if pk["centres"].size else np.zeros((0, 1))
            c_cal.append(np.exp(lp[np.arange(len(pk["labels"])), pk["labels"]]) if pk["centres"].size else np.zeros(0))
        c_raw_a, c_cal_a, c_ok_a = np.concatenate(c_raw), np.concatenate(c_cal), np.concatenate(c_ok)
        if c_ok_a.size:
            m["ece_char_before"] = expected_calibration_error(c_raw_a, c_ok_a)
            m["ece_char_after"] = expected_calibration_error(np.clip(c_cal_a, 0, 1), c_ok_a)
        true_idx = [an.nbest.index_of(t) for an, t in zip(analyses, truths)]
        m.update(self.conformal.evaluate([an.posteriors for an in analyses], true_idx))
        m.update(self.word_conformal.evaluate([an.nbest.texts for an in analyses], [an.posteriors for an in analyses], truths))
        wrong = ~top1_ok
        m["guard_auroc"] = auroc([an.guard.risk for an in analyses], wrong)
        m["guard_auroc_low_evidence"] = auroc([an.guard.low_evidence_frac for an in analyses], wrong)
        m["guard_auroc_inconsistency"] = auroc([1 - an.guard.consistency for an in analyses], wrong)
        m["p_top1_auroc"] = auroc(-p_cal, wrong)
        records = self.run_items(items, self.policy, cache)
        m.update(summarize(records))
        m.update({f"fit_{k}": v for k, v in self.fit_report.items()})
        m["records"] = records
        return m


def run_harness(
    test: Sequence[Any],
    decode_fn: DecodeFn,
    calib: Sequence[Any],
    val: Sequence[Any] | None = None,
    config: HarnessConfig | None = None,
    decode_cache: dict | None = None,
) -> dict[str, Any]:
    """Fit the trust core on ``calib`` (and the policy on ``val``), then
    evaluate on ``test``.

    Items are ``(stream, text)``, ``(stream, text, regen)`` or
    :class:`Item`. Pass the same :class:`Item` objects and one
    ``decode_cache`` dict to several calls to decode each stream once.

    The returned dict holds: ``cer``, ``wer``, ``greedy_cer``,
    ``ece_sentence_before/after``, ``ece_char_before/after``, conformal
    ``coverage``/``coverage_in_nbest``/``mean_set_size``/``miss_rate``,
    ``word_coverage``/``word_mean_set_size``, ``guard_auroc`` (risk vs.
    wrong top-1), action rates ``rate_commit/offer/ask/abstain/offer_words``,
    ``system_word_accuracy``, ``keystrokes_saved``,
    ``share_words_system/selected/typed``,
    ``ewpm``, ``wrong_commit_rate``, ``silent_error_rate``,
    ``abstain_rate``, ``committed_cer``, the fit results (``fit_*``) and
    the per-sentence ``records``.
    """
    pipe = TrustPipeline(decode_fn, config, decode_cache)
    pipe.fit(calib, val)
    return pipe.evaluate(test)
