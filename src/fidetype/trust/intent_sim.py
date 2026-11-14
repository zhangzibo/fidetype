"""Synthetic intent trials for tests and the FEP-0003 evaluation (SYNTHETIC DATA, no people).

A simple, clearly artificial generator of N-way intent decisions. It is
not a model of any device. It exists so that the intent trust layer
(:mod:`fidetype.trust.intent`) can be tested with known truth, with a
"rest" (null) class and with no-signal trials.

Model of one trial with true intent y::

    z_j = snr * 1[j = y] + N(0, 1)          (signal trial)
    z_j = N(0, 1)                           (no-signal trial: no intent, truth -1)
    p   = softmax(overconfidence * z)       (a miscalibrated decoder output)

A "rest" trial is a signal trial whose truth is the vocabulary's null
intent (if it has one). Each trial also has a signal-quality index in
[0, 1] (spec 3.9): uniform in [0.6, 1.0] for signal and rest trials,
uniform in [0.0, 0.4] for no-signal trials (an idealised quality channel).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from fidetype.trust.intent import DECLARATION_KEY, IntentSpec, IntentVocabulary


@dataclass(frozen=True)
class IntentTrials:
    """Synthetic trials. ``labels`` -1 = no intent (no-signal trial)."""

    probs: np.ndarray
    labels: np.ndarray
    kind: np.ndarray  # "signal", "rest" or "nosignal"
    quality: np.ndarray | None = None

    def __len__(self) -> int:
        return len(self.labels)

    def subset(self, idx: np.ndarray) -> "IntentTrials":
        return IntentTrials(self.probs[idx], self.labels[idx], self.kind[idx],
                            None if self.quality is None else self.quality[idx])


def demo_vocabulary() -> IntentVocabulary:
    """A small assistive-control vocabulary (12 intents) used by tests and the simulator."""
    specs = [
        IntentSpec("intent.rest", "safe", "null", "no intent"),
        IntentSpec("intent.select", "undoable"),
        IntentSpec("intent.next", "safe"),
        IntentSpec("intent.previous", "safe"),
        IntentSpec("intent.stop", "safe", label="stop the device"),
        IntentSpec("intent.mode.switch", "undoable"),
        IntentSpec("intent.menu.1", "undoable"),
        IntentSpec("intent.menu.2", "undoable"),
        IntentSpec("intent.undo", "undoable", "undo"),
        IntentSpec("intent.cancel", "safe", "cancel"),
        IntentSpec("intent.confirm", "irreversible", "confirm"),
        IntentSpec("intent.call-caregiver", "irreversible", label="call the caregiver"),
    ]
    return IntentVocabulary(tuple(specs), vocab_id="intent.demo-assistive", vocab_version="1")


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def simulate_trials(vocab: IntentVocabulary, n: int, snr: float = 3.0, overconfidence: float = 1.5,
                    rest_rate: float = 0.1, no_signal_rate: float = 0.1, seed: int = 0) -> IntentTrials:
    """``n`` synthetic trials (module docstring). Truths are uniform over the non-null intents."""
    rng = np.random.default_rng(seed)
    N = len(vocab)
    null = np.where(vocab.null_mask())[0]
    act = np.where(~vocab.null_mask())[0]
    u = rng.random(n)
    kind = np.where(u < no_signal_rate, "nosignal", np.where(u < no_signal_rate + (rest_rate if len(null) else 0), "rest", "signal"))
    y = rng.choice(act, size=n)
    if len(null):
        y = np.where(kind == "rest", null[0], y)
    y = np.where(kind == "nosignal", -1, y)
    z = rng.standard_normal((n, N))
    sig = y >= 0
    z[np.arange(n)[sig], y[sig]] += snr
    q = np.where(kind == "nosignal", rng.uniform(0.0, 0.4, n), rng.uniform(0.6, 1.0, n))
    return IntentTrials(_softmax(overconfidence * z), y.astype(np.int64), kind, q)


def uniform_control(t: IntentTrials) -> IntentTrials:
    """No-signal control: every trial has the uniform distribution (truths unchanged)."""
    return IntentTrials(np.full_like(t.probs, 1.0 / t.probs.shape[1]), t.labels, t.kind, t.quality)


def shuffled_control(t: IntentTrials, seed: int = 0) -> IntentTrials:
    """Pairing control: decoder outputs permuted across trials (outputs no longer match truths)."""
    perm = np.random.default_rng(seed).permutation(len(t))
    return IntentTrials(t.probs[perm], t.labels, t.kind, t.quality)


def trials_to_events(vocab: IntentVocabulary, t: IntentTrials, top_k: int | None = 5, dt: float = 1.0,
                     source: str = "intent-simulator") -> list[dict[str, Any]]:
    """A FEP-0003 JSON Lines stream (header + one final ``intent`` event per trial + ``end``)."""
    header = {"type": "header", "spec_version": "0.1", "vocab": list(vocab.ids), "vocab_type": "command",
              "blank_id": None, "source": source, "clock_domain": "trial",
              "meta": {"data.derived": True, "data.synthetic": True}, DECLARATION_KEY: vocab.to_declaration()}
    evs: list[dict[str, Any]] = [header]
    for i in range(len(t)):
        if t.quality is not None:
            evs.append({"type": "signal_quality", "t": round(i * dt, 6), "value": round(float(t.quality[i]), 4),
                        "unit": "index"})
        order = np.argsort(-t.probs[i], kind="stable")[: top_k or None]
        cands = [{"intent": vocab.ids[j], "score": round(float(t.probs[i, j]), 6)} for j in order]
        tot = sum(c["score"] for c in cands)
        if tot > 1.0:  # rounding
            cands[0]["score"] = round(cands[0]["score"] - (tot - 1.0) - 1e-6, 6)
            cands.sort(key=lambda c: -c["score"])
        evs.append({"type": "intent", "id": f"i{i}", "t": round(i * dt, 6), "is_final": True,
                    "score_semantics": "uncalibrated_prob", "candidates": cands})
    evs.append({"type": "end"})
    return evs


__all__ = ["IntentTrials", "demo_vocabulary", "shuffled_control", "simulate_trials", "trials_to_events",
           "uniform_control"]
