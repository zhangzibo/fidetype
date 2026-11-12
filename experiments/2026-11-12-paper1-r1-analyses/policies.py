"""Policy and pipeline variants shared by the R1 analyses (baselines, ablation, user model).

Every variant is fitted on the condition's own fit data (``cond.calib`` for
temperatures and conformal sets, ``cond.val`` for the policy grid), exactly as
the main trust run, and scored on ``cond.test``.

Variants
--------
trust            the main trust layer (plug-in grid fit, max wrong-commit 0.05)
always_commit    commit the (calibrated) LM top-1 every time
never_commit     the trust grid with commit disabled (commit_p 1.01 only): always offer / abstain, refit
no_guard         plain threshold on calibrated p_top1: guard off (commit_max_risk 1, abstain_risk 1.01), refit
raw_no_guard     plain threshold on raw (uncalibrated) p_top1: no temperatures, no guard, refit
no_calib         trust without any temperature
conf_only        frame temperature NOT applied to the stream before the beam (decode raw); sentence temperature on
beam_only        frame temperature applied before the beam; sentence temperature off (identity)
no_conformal     conformal sets off: OFFER shows the top offer_max_k (fitted) candidates instead of the set
ow_off_base      trust on the small BASE_GRID (the OFFER_WORDS reference grid)
ow_on            trust + OFFER_WORDS (BASE_GRID x OFFER_WORDS_GRID)
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

import common as C
from fidetype.eval import harness as H
from fidetype.eval.harness import Item, TrustPipeline, as_items
from fidetype.eval.metrics import edit_distance
from fidetype.interact.simulated_user import Outcome, SimulatedUser, _nwords
from fidetype.trust.calibration import expected_calibration_error
from fidetype.trust.policy import DEFAULT_GRID, OFFER_WORDS_GRID

BASE_GRID = {
    "commit_p": (0.5, 0.7, 0.8, 0.9, 0.95, 0.98, 1.01),
    "commit_max_risk": (0.3, 1.0),
    "offer_max_k": (0, 1, 3, 5),
    "abstain_risk": (0.8, 1.01),
    "final_fallback": ("offer", "abstain"),
}


class NoConformalPipe(TrustPipeline):
    """Conformal sets off: the policy sees a 'set' of all candidates, so OFFER shows the top offer_max_k."""

    def analyze(self, raw):
        an = super().analyze(raw)
        an.inputs = replace(an.inputs, set_indices=tuple(range(len(an.inputs.texts))), includes_other=False)
        return an


class SymmetricUser(SimulatedUser):
    """OFFER without the target: the user always fixes the closest candidate word by word (no oracle
    choice between fix / repeat / retype), and misses each wrong word with p_miss_unflagged, as under
    COMMIT. Use with ``allow_full_retype=False`` so that COMMIT has no oracle retype either."""

    def _offer_words_model(self, shown, truth, can_repeat, rng, t_read, t_sel, base) -> Outcome:
        t0 = t_read + t_sel
        if not shown:
            o = self._retype(truth, t0, base)
            o.keystrokes += 1
            return o
        best = min(shown, key=lambda s: C_ed(tuple(s.split()), tuple(truth.split())))
        p = self._word_pass(best, truth, {}, rng, miss_unflagged=True)
        ok = p["final"] == truth
        bd = {**base, "select": t_sel + p["select"], "nav": p["nav"], "type": p["type"]}
        return Outcome(t0 + p["fix_time"], p["final"], ok, silent_error=not ok, corrected=p["wrong"] > p["missed"],
                       breakdown=bd, words_selected=p["sys"] if ok else 0, words_typed=p["typed"] if ok else 0,
                       keystrokes=1 + p["keys"], n_wrong_slots=p["wrong"], n_missed=p["missed"])


def C_ed(a, b) -> int:
    from fidetype.trust._align import cached_edit_distance

    return cached_edit_distance(a, b)


def fit_custom(pipe: TrustPipeline, calib, val, frame_decode: bool, sentence_cal: bool) -> TrustPipeline:
    """TrustPipeline.fit with the two temperature effects separated (no risk control)."""
    cfg = pipe.config
    items = as_items(calib)
    n_conf = int(round(len(items) * cfg.conformal_fraction))
    temp, conf = items[: len(items) - n_conf], items[len(items) - n_conf:]
    fs = H.fit_frame_temperature([it.stream(0) for it in temp], [it.stream_text for it in temp])
    if frame_decode:
        pipe.frame_scaler = fs
    nbs = [pipe.decode(it, 0) for it in temp]
    if sentence_cal:
        pipe.calibrator = H.NBestCalibrator.fit(nbs, [it.text for it in temp], fit_char=False)
    conf = conf or temp
    posts, idx, texts = [], [], []
    for it in conf:
        nb = pipe.decode(it, 0)
        posts.append(pipe.calibrator.posteriors(nb))
        idx.append(nb.index_of(it.text))
        texts.append(nb.texts)
    pipe.conformal.fit(posts, idx)
    pipe.word_conformal.fit(texts, posts, [it.text for it in conf])
    pipe.fit_report = {"temperature_frame_fitted": fs.temperature, "temperature_frame_used": pipe.frame_scaler.temperature,
                       "temperature_sentence": pipe.calibrator.sentence.temperature, "conformal_q": pipe.conformal.q}
    pipe._fit_policy(as_items(val))
    return pipe


def grid_of(cond) -> dict:
    return dict(cond.base.get("grid") or DEFAULT_GRID)


def build(cond, variant: str, cache: dict, user=None, user_cls=None) -> TrustPipeline:
    """Fit one variant on the condition's fit data."""
    g = grid_of(cond)
    over: dict = {}
    cls = TrustPipeline
    custom = None
    if variant == "trust":
        pass
    elif variant == "always_commit":
        over = dict(policy="always_commit")
    elif variant == "never_commit":
        over = dict(grid={**g, "commit_p": (1.01,)})
    elif variant == "no_guard":
        over = dict(use_guard=False)
    elif variant == "raw_no_guard":
        over = dict(use_guard=False, use_calibration=False)
    elif variant == "no_calib":
        over = dict(use_calibration=False)
    elif variant == "conf_only":
        custom = (False, True)
    elif variant == "beam_only":
        custom = (True, False)
    elif variant == "no_conformal":
        cls = NoConformalPipe
    elif variant == "ow_off_base":
        over = dict(grid=BASE_GRID)
    elif variant == "ow_on":
        over = dict(grid=BASE_GRID, offer_words=True, word_grid=OFFER_WORDS_GRID)
    else:
        raise ValueError(variant)
    cfg = H.HarnessConfig(seed=C.SEED, user_config=user or cond.user, **{**cond.base, **over})
    pipe = cls(cond.decode, cfg, cache)
    if user_cls is not None:
        pipe.user = user_cls(cfg.user_config, seed=cfg.seed)
    if custom is not None:
        fit_custom(pipe, cond.calib, cond.val, *custom)
    else:
        pipe.fit(cond.calib, cond.val)
    return pipe


def score(pipe: TrustPipeline, items, user=None, user_cls=None) -> list:
    """Run the fitted pipe on ``items``; optionally with another simulated user (no refit)."""
    if user is not None or user_cls is not None:
        cfg = user if user is not None else pipe.config.user_config
        old = pipe.user
        pipe.user = (user_cls or SimulatedUser)(cfg, seed=pipe.config.seed)
        try:
            return pipe.run_items(items)
        finally:
            pipe.user = old
    return pipe.run_items(items)


def decoder_stats(pipe: TrustPipeline, items) -> dict:
    """Top-1 CER / WER / sentence accuracy, truth in n-best, sentence ECE before / after, of the fitted pipe."""
    tops, ok, p_raw, p_cal, inn = [], [], [], [], []
    for it in items:
        an = pipe.analyze(pipe.decode(it, 0))
        t = an.nbest.texts[0] if len(an.nbest) else ""
        tops.append(t)
        ok.append(t == it.text)
        inn.append(an.nbest.index_of(it.text) >= 0)
        p_raw.append(an.raw_posteriors[0] if len(an.raw_posteriors) else 0.0)
        p_cal.append(an.posteriors[0] if len(an.posteriors) else 0.0)
    truths = [it.text for it in items]
    ok = np.array(ok)
    return {"cer": sum(edit_distance(a, b) for a, b in zip(truths, tops)) / sum(len(t) for t in truths),
            "wer": sum(edit_distance(a.split(), b.split()) for a, b in zip(truths, tops)) / sum(len(t.split()) for t in truths),
            "sentence_acc": float(ok.mean()), "truth_in_nbest": float(np.mean(inn)),
            "ece_sentence_raw": float(expected_calibration_error(np.array(p_raw), ok)),
            "ece_sentence_cal": float(expected_calibration_error(np.array(p_cal), ok)),
            "frame_T": pipe.frame_scaler.temperature,
            "policy": ({k: (v if not isinstance(v, float) or math.isfinite(v) else str(v)) for k, v in pipe.policy.config.__dict__.items()}
                       if hasattr(pipe.policy, "config") else "always commit")}
