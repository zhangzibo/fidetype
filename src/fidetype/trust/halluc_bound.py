"""Risk-controlled bound on fluent-wrong (hallucinated) commits (P15-06, F2).

Problem
-------
A large language model (LLM) in the decoder makes the n-best list more
confident. The trust gate then commits more, and its wrong commits read
well ("fluent-wrong"). The P14-03 wrong-commit bound still holds, but it
says nothing special about this kind of error, and the P15-05 grounding
check (``tau`` at 95 % coverage of true texts) was too loose to stop it
(``experiments/2026-11-16-f2-e3-llm-grounding/results.md``).

What this module adds
---------------------
1. :class:`CommitGrounding`: two evidence statistics of a text that is
   about to be committed, from the decoder's own CTC log-probabilities:

   - **sentence deficit** ``(log p_ctc(anchor | x) - log p_ctc(text | x)) / T``
     in nats per frame. ``anchor`` is ``anchor_fn(log_probs)`` (for
     example the decoder top-1 without the LLM). With no ``anchor_fn``,
     the anchor score is the best path ``sum_t max_v log p(v | t)``
     (no text needed).
   - **word deficit** (per word, from a Viterbi forced alignment of the
     text): the mean over the frames that the alignment gives to the
     word's labels of ``max_v log p(v | t) - log p(label | t)``. The
     largest word deficit of the text is the statistic. A one-word swap
     in a long sentence is diluted in the sentence deficit, but not here.

   A text with no label sequence (a word without a pronunciation) has
   both statistics ``inf``.

2. :class:`HallucGate`: a commit passes if ``sentence deficit <= tau_commit``
   and ``max word deficit <= tau_word`` (``inf`` = check off). A failing
   COMMIT becomes the no-commit decision of the same policy (as the
   M2-18 commit gate does). The gate only removes commits.

3. :func:`joint_ltt`: Learn then Test over a joint grid
   ``lambda = (commit_p, tau_commit, tau_word)`` with **two** risks at once:

   - wrong-commit risk ``R_wc(lambda) <= alpha`` (the P14-03 loss,
     monotonised with the OFFER_WORDS fallback loss as in
     :mod:`fidetype.trust.risk_control`);
   - hallucination risk ``R_h(lambda) <= alpha_h``, loss = 1 if the item
     COMMITs a text that is wrong **and** fluent (LLM log-probability per
     word >= a fixed threshold). Without an LLM every wrong commit counts
     as fluent (a stricter, second wrong-commit bound).

   Each ``lambda`` has the null hypothesis ``H_lambda: R_wc > alpha or
   R_h > alpha_h`` with p-value ``max(p_wc, p_h)`` (exact binomial
   p-values; intersection-union test). The test order (a chain over the
   grid) comes from a separate **ordering** split: configurations with
   the smallest p-value there come first; ties: fewer commits, then
   stricter thresholds (Pareto-testing style). Fixed-sequence testing on
   the **test** split certifies the chain prefix whose p-values are all
   ``<= delta``. With exchangeable data, ``P(every certified lambda has
   R_wc <= alpha and R_h <= alpha_h) >= 1 - delta``. Any selection rule
   among the certified set keeps the guarantee.

Selection (fixed in advance, P15-06 plan): among certified configurations
with ``commit_p >= min_commit_p``, the fewest fluent-wrong commits on
ordering + test items, then the most right commits, then the fewest
commits, then the strictest thresholds. If none is certified, the guard
never commits (``commit_p = inf``).

The module needs no LLM and no decoder: the LLM enters only through the
per-item ``fluent`` flags (see :mod:`fidetype.lm.llm` for a scorer).
:func:`fidetype.trust.calibrate` (``grounding=``, ``llm=``) uses it.
Licence: our own code, Apache-2.0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

from fidetype.trust.grounding import LabelFn, ctc_log_likelihood_many, log_softmax_rows
from fidetype.trust.risk_control import binomial_pvalue

#: Default grids (P15-06 plan). Values in nats per frame; inf = check off.
DEFAULT_COMMIT_P_GRID: tuple[float, ...] = tuple([math.inf] + [round(1.0 - 0.01 * k, 2) for k in range(101)])
DEFAULT_TAU_COMMIT_GRID: tuple[float, ...] = (0.0, 0.002, 0.005, 0.01, 0.02, 0.05, math.inf)
DEFAULT_TAU_WORD_GRID: tuple[float, ...] = (0.25, 0.5, 1.0, 2.0, 4.0, math.inf)


# ---------------------------------------------------------------------------
# evidence statistics of one text
# ---------------------------------------------------------------------------


def ctc_viterbi_states(log_probs: np.ndarray, labels: Sequence[int], blank: int = 0) -> tuple[float, np.ndarray]:
    """Best CTC alignment of ``labels``: (log score, extended-state index per frame).

    The extended states are ``blank, l1, blank, l2, ..., blank`` (index
    ``2k + 1`` is label ``k``). Returns ``(-inf, empty)`` if the labels
    need more frames than there are.
    """
    lp = np.asarray(log_probs, dtype=np.float64)
    T = lp.shape[0]
    L = len(labels)
    S = 2 * L + 1
    ext = np.full(S, blank, dtype=np.int64)
    if L:
        ext[1::2] = np.asarray(labels, dtype=np.int64)
    if T == 0:
        return -math.inf, np.zeros(0, dtype=np.int64)
    skip = np.zeros(S, dtype=bool)
    if S > 3:
        skip[3::2] = ext[3::2] != ext[1:-2:2]
    emit = lp[:, ext]
    delta = np.full(S, -np.inf)
    delta[0] = emit[0, 0]
    if S > 1:
        delta[1] = emit[0, 1]
    back = np.zeros((T, S), dtype=np.int8)  # 0 stay, 1 from s-1, 2 from s-2
    for t in range(1, T):
        a0 = delta
        a1 = np.concatenate(([-np.inf], delta[:-1]))
        a2 = np.where(skip, np.concatenate(([-np.inf, -np.inf], delta[:-2])), -np.inf)
        stack = np.stack((a0, a1, a2))
        arg = np.argmax(stack, axis=0)
        back[t] = arg
        delta = stack[arg, np.arange(S)] + emit[t]
    ends = [S - 1] + ([S - 2] if S > 1 else [])
    s = max(ends, key=lambda k: delta[k])
    best = float(delta[s])
    if not math.isfinite(best):
        return -math.inf, np.zeros(0, dtype=np.int64)
    path = np.zeros(T, dtype=np.int64)
    for t in range(T - 1, -1, -1):
        path[t] = s
        s -= int(back[t, s])
    return best, path


@dataclass(frozen=True)
class GroundingStats:
    """Evidence statistics of one text (see :class:`CommitGrounding`)."""

    sentence_deficit: float
    word_deficits: tuple[float, ...]

    @property
    def max_word_deficit(self) -> float:
        return max(self.word_deficits) if self.word_deficits else (math.inf if not math.isfinite(
            self.sentence_deficit) else 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {"sentence_deficit": self.sentence_deficit, "max_word_deficit": self.max_word_deficit,
                "word_deficits": list(self.word_deficits)}


UNGROUNDED = GroundingStats(math.inf, (math.inf,))


class CommitGrounding:
    """Sentence and word evidence statistics of a text (module docstring, item 1).

    ``label_fn``: text -> alternative label-id sequences (for example
    :func:`fidetype.trust.grounding.lexicon_label_fn`). ``word_sep_id``:
    the label that separates words in those sequences (None: the words
    are aligned from ``label_fn(word)`` one by one, first variant, with no
    separator). ``anchor_fn``: ``log_probs -> text`` (None: the best path
    is the anchor). ``name`` goes into the guarantee sheet (a function
    cannot be stored).
    """

    def __init__(self, label_fn: LabelFn, *, blank: int = 0, word_sep_id: int | None = None,
                 anchor_fn: Callable[[np.ndarray], str] | None = None, name: str = "") -> None:
        self.label_fn = label_fn
        self.blank = int(blank)
        self.word_sep_id = None if word_sep_id is None else int(word_sep_id)
        self.anchor_fn = anchor_fn
        self.name = name or getattr(label_fn, "__qualname__", "label_fn")

    @classmethod
    def from_grounding_check(cls, check: Any, **kw: Any) -> "CommitGrounding":
        """Build from a :class:`fidetype.trust.grounding.GroundingCheck` (its ``label_fn`` and ``blank``)."""
        return cls(check.label_fn, blank=check.blank, **kw)

    def _word_sequences(self, text: str) -> list[tuple[list[int], list[int]]] | None:
        """Alternative (labels, word index per label) pairs, or None if the text has no labels."""
        words = text.split()
        if not words:
            return [([], [])]
        if self.word_sep_id is None:
            labels: list[int] = []
            widx: list[int] = []
            for k, w in enumerate(words):
                alts = self.label_fn(w)
                if not alts or not alts[0]:
                    return None
                labels += list(alts[0])
                widx += [k] * len(alts[0])
            return [(labels, widx)]
        seqs = self.label_fn(text)
        if not seqs:
            return None
        out = []
        for s in seqs:
            k = 0
            widx = []
            for lab in s:
                if lab == self.word_sep_id:
                    widx.append(-1)
                    k += 1
                else:
                    widx.append(k)
            out.append((list(s), widx))
        return out

    def stats(self, log_probs: np.ndarray, text: str) -> GroundingStats:
        """:class:`GroundingStats` of ``text`` on ``log_probs`` (``(T, V)``; rows are log-softmaxed)."""
        lp = log_softmax_rows(log_probs)
        T = max(1, lp.shape[0])
        alts = self._word_sequences(" ".join(str(text).split()))
        if alts is None:
            return UNGROUNDED
        ll = ctc_log_likelihood_many(lp, [a for a, _ in alts], self.blank)
        j = int(np.argmax(ll))
        if not math.isfinite(ll[j]):
            return UNGROUNDED
        if self.anchor_fn is None:
            anchor = float(lp.max(axis=1).sum())
        else:
            at = " ".join(str(self.anchor_fn(np.asarray(log_probs))).split())  # the input as given (cache keys)
            aa = self._word_sequences(at)
            a_ll = ctc_log_likelihood_many(lp, [a for a, _ in aa], self.blank) if aa else np.array([-np.inf])
            anchor = float(np.max(a_ll))
            if not math.isfinite(anchor):  # no anchor text: fall back to the best path
                anchor = float(lp.max(axis=1).sum())
        sent = (anchor - float(ll[j])) / T
        labels, widx = alts[j]
        n_words = len(str(text).split())
        if not labels:
            return GroundingStats(sent, ())
        _, path = ctc_viterbi_states(lp, labels, self.blank)
        if path.size == 0:
            return UNGROUNDED
        best = lp.max(axis=1)
        sums = np.zeros(n_words)
        cnts = np.zeros(n_words)
        for t, s in enumerate(path):
            if s % 2 == 1:
                k = widx[(s - 1) // 2]
                if k >= 0:
                    lab = labels[(s - 1) // 2]
                    sums[k] += best[t] - lp[t, lab]
                    cnts[k] += 1
        wd = tuple(float(sums[k] / cnts[k]) if cnts[k] else math.inf for k in range(n_words))
        return GroundingStats(float(sent), wd)


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HallucGate:
    """Commit condition on :class:`GroundingStats` (``inf`` = check off)."""

    tau_commit: float = math.inf
    tau_word: float = math.inf

    @property
    def is_off(self) -> bool:
        return math.isinf(self.tau_commit) and math.isinf(self.tau_word)

    def violation(self, st: GroundingStats) -> str | None:
        """Why a commit with these statistics is not allowed, or None."""
        if not (st.sentence_deficit <= self.tau_commit):
            return f"sentence deficit {st.sentence_deficit:.4f} > tau_commit {self.tau_commit:g}"
        if not (st.max_word_deficit <= self.tau_word):
            return f"word deficit {st.max_word_deficit:.3f} > tau_word {self.tau_word:g}"
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"tau_commit": _jf(self.tau_commit), "tau_word": _jf(self.tau_word)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "HallucGate":
        return cls(_fj(d.get("tau_commit", math.inf)), _fj(d.get("tau_word", math.inf)))


def _jf(x: float) -> float | str:
    return x if math.isfinite(x) else ("inf" if x > 0 else "-inf")


def _fj(x: Any) -> float:
    return {"inf": math.inf, "-inf": -math.inf, "nan": math.nan}[x] if isinstance(x, str) else float(x)


# ---------------------------------------------------------------------------
# joint Learn then Test
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemStats:
    """What :func:`joint_ltt` needs from one labelled item.

    ``can_commit``: the guard would COMMIT the top-1 at ``commit_p = 0``
    (all other commit conditions and the M2-18 gate pass). ``wrong``:
    the top-1 text is not the truth. ``fluent``: the top-1 text is fluent
    by the LLM test (unknown -> True). ``fallback_wrong``: the no-commit
    decision is a wrong OFFER_WORDS (loss 1 in the P14-03 wrong-commit
    loss). ``stats``: grounding statistics of the top-1 text.
    """

    can_commit: bool
    p_top1: float
    wrong: bool
    fluent: bool = True
    fallback_wrong: bool = False
    stats: GroundingStats = field(default_factory=lambda: GroundingStats(0.0, ()))


@dataclass(frozen=True)
class Config:
    commit_p: float
    gate: HallucGate

    def to_dict(self) -> dict[str, Any]:
        return {"commit_p": _jf(self.commit_p), **self.gate.to_dict()}


def _arrays(items: Sequence[ItemStats]) -> dict[str, np.ndarray]:
    return {
        "can": np.array([it.can_commit for it in items], dtype=bool),
        "p": np.array([it.p_top1 for it in items], dtype=np.float64),
        "wrong": np.array([it.wrong for it in items], dtype=bool),
        "fluent": np.array([it.fluent for it in items], dtype=bool),
        "fb": np.array([it.fallback_wrong for it in items], dtype=bool),
        "sd": np.array([it.stats.sentence_deficit for it in items], dtype=np.float64),
        "wd": np.array([it.stats.max_word_deficit for it in items], dtype=np.float64),
    }


def _counts(a: Mapping[str, np.ndarray], c: Config) -> dict[str, int]:
    com = a["can"] & (a["p"] >= c.commit_p) & (a["sd"] <= c.gate.tau_commit) & (a["wd"] <= c.gate.tau_word)
    wc = np.where(com, a["wrong"] | a["fb"], a["fb"])
    h = com & a["wrong"] & a["fluent"]
    return {"n": int(a["can"].shape[0]), "commits": int(com.sum()), "right": int((com & ~a["wrong"]).sum()),
            "wc_loss": int(wc.sum()), "h_loss": int(h.sum())}


def _pvals(k: Mapping[str, int], alpha: float, alpha_h: float, beta: float | None = None) -> tuple[float, ...]:
    n = max(1, k["n"])
    pv = (binomial_pvalue(k["wc_loss"] / n, n, alpha), binomial_pvalue(k["h_loss"] / n, n, alpha_h))
    if beta is None:
        return pv
    from fidetype.trust.precision_bound import precision_pvalue

    # P5-02: third risk = error rate among commits (exact binomial p-value given the number of commits)
    return (*pv, precision_pvalue(k["commits"] - k["right"], k["commits"], beta))


@dataclass
class JointLTTResult:
    """Output of :func:`joint_ltt`."""

    selected: Config | None
    certified: list[Config]
    chain_length: int
    n_tested: int
    alpha: float
    alpha_h: float
    delta: float
    n_order: int
    n_test: int
    #: Counts of the selected configuration on the ordering and test items.
    order_counts: dict[str, int] = field(default_factory=dict)
    test_counts: dict[str, int] = field(default_factory=dict)
    #: (p_wc, p_h) of the selected configuration on the test items; (p_wc, p_h, p_precision) with a precision target.
    test_pvalues: tuple[float, ...] = (math.nan, math.nan)
    #: P5-02 joint precision target (None: off, the P15-06 two-risk test).
    target_precision: float | None = None

    @property
    def feasible(self) -> bool:
        return self.selected is not None

    def to_dict(self) -> dict[str, Any]:
        d = {"selected": self.selected.to_dict() if self.selected else None, "n_certified": len(self.certified),
             "chain_length": self.chain_length, "n_tested": self.n_tested, "alpha": self.alpha,
             "alpha_h": self.alpha_h, "delta": self.delta, "n_order": self.n_order, "n_test": self.n_test,
             "order_counts": dict(self.order_counts), "test_counts": dict(self.test_counts),
             "test_pvalues": [None if math.isnan(x) else float(x) for x in self.test_pvalues],  # JSON: no NaN
             "feasible": self.feasible}
        if self.target_precision is not None:
            d["target_precision"] = self.target_precision
        return d


def grid(commit_p: Iterable[float] = DEFAULT_COMMIT_P_GRID, tau_commit: Iterable[float] = DEFAULT_TAU_COMMIT_GRID,
         tau_word: Iterable[float] = DEFAULT_TAU_WORD_GRID) -> list[Config]:
    """All configurations of the joint grid."""
    return [Config(float(c), HallucGate(float(a), float(b))) for c in commit_p for a in tau_commit for b in tau_word]


def _strictness(c: Config) -> tuple[float, float, float]:
    """Sort key: stricter first (higher commit_p, smaller taus)."""
    return (-c.commit_p, c.gate.tau_commit, c.gate.tau_word)


SELECT_RULES = ("fewest_halluc", "most_right")


def joint_ltt(order_items: Sequence[ItemStats], test_items: Sequence[ItemStats], configs: Sequence[Config], *,
              alpha: float, alpha_h: float, delta: float, min_commit_p: float = -math.inf,
              select: str = "fewest_halluc", target_precision: float | None = None) -> JointLTTResult:
    """Learn then Test over ``configs`` with the wrong-commit and the hallucination risk (module docstring).

    ``select`` (any rule keeps the guarantee): ``"fewest_halluc"`` (default) = fewest fluent-wrong commits on
    ordering + test items, then most right commits; ``"most_right"`` = most right commits, then fewest
    fluent-wrong. Further ties: fewest commits, then the strictest thresholds.

    ``target_precision`` (P5-02, default None = off): add a third risk, the error rate among commits
    ``P(wrong | commit) <= 1 - target_precision``. Its p-value is the exact binomial tail on the commits of
    the configuration (valid given the number of commits, see :mod:`fidetype.trust.precision_bound`). The
    p-value of a configuration is then ``max(p_wc, p_h, p_precision)`` (intersection-union test), with the
    same ordering split and the same fixed-sequence test. With exchangeable data, ``P(every certified
    configuration meets all three risks) >= 1 - delta``: one test, one delta, no union bound.
    """
    if not (0 < alpha < 1 and 0 < alpha_h < 1 and 0 < delta < 1):
        raise ValueError("alpha, alpha_h and delta must be in (0, 1)")
    if target_precision is not None and not 0 < target_precision < 1:
        raise ValueError("target_precision must be in (0, 1)")
    beta = None if target_precision is None else 1.0 - float(target_precision)
    if select not in SELECT_RULES:
        raise ValueError(f"select must be one of {SELECT_RULES}")
    if not configs:
        raise ValueError("the grid is empty")
    ao, at = _arrays(order_items), _arrays(test_items)
    keyed = []
    for c in configs:
        ko = _counts(ao, c)
        keyed.append((max(_pvals(ko, alpha, alpha_h, beta)), ko["commits"], _strictness(c), c, ko))
    keyed.sort(key=lambda r: (r[0], r[1], r[2]))
    certified: list[tuple[Config, dict[str, int], dict[str, int], tuple[float, ...]]] = []
    n_tested = 0
    for _, _, _, c, ko in keyed:
        kt = _counts(at, c)
        pv = _pvals(kt, alpha, alpha_h, beta)
        n_tested += 1
        if max(pv) > delta:
            break
        certified.append((c, ko, kt, pv))
    pool = [r for r in certified if r[0].commit_p >= min_commit_p]
    res = JointLTTResult(None, [r[0] for r in certified], len(keyed), n_tested, alpha, alpha_h, delta,
                         len(order_items), len(test_items),
                         test_pvalues=(math.nan,) * (2 if beta is None else 3),
                         target_precision=None if target_precision is None else float(target_precision))
    if pool:
        def key(r):
            c, ko, kt, _ = r
            h, right = ko["h_loss"] + kt["h_loss"], -(ko["right"] + kt["right"])
            first = (h, right) if select == "fewest_halluc" else (right, h)
            return (*first, ko["commits"] + kt["commits"], _strictness(c))

        c, ko, kt, pv = min(pool, key=key)
        res.selected, res.order_counts, res.test_counts, res.test_pvalues = c, ko, kt, pv
    return res


def fluent_threshold_from_texts(texts: Sequence[str], scorer: Any) -> float:
    """Median LLM log-probability per word of ``texts`` (the P15-05 "fluent" threshold)."""
    lps = scorer.score(list(texts))
    per = [lp / max(1, len(t.split())) for lp, t in zip(lps, texts) if math.isfinite(lp)]
    if not per:
        raise ValueError("no finite LLM score: cannot set the fluent threshold")
    return float(np.median(per))


def is_fluent(text: str, scorer: Any, threshold: float) -> bool:
    """LLM fluency test of the fluent-wrong loss. No scorer, or no finite score: True (conservative)."""
    if scorer is None:
        return True
    n = len(text.split())
    if n == 0:
        return False
    try:
        lp = float(scorer.score([text])[0])
    except Exception:  # noqa: BLE001 - unknown fluency counts as fluent (upper bound of the loss)
        return True
    if not math.isfinite(lp):
        return True
    return lp / n >= threshold
