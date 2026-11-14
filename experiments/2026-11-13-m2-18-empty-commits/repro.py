"""M2-18 minimal reproducer (synthetic data only): the v4 policy commits empty texts on no-signal input.

A toy word decoder: CTC greedy decode, then drop every word that is not in the lexicon.
On a near-uniform stream the greedy text is random characters, so every word is dropped
and the decoder returns one candidate, the empty text. Then:

- the guard gives the empty text risk 1.0 (its low-evidence term is set to 1.0);
- the calibrated p_top1 of a one-candidate list is 1.0;
- with commit_max_risk = 1.0 (a value of the default grid) the guard test
  ``risk <= commit_max_risk`` is 1.0 <= 1.0, always true, so the policy COMMITs "";
- with commit_max_risk < 1.0 (or abstain_risk <= 1.0) the empty text is blocked.

Run (repo root):  .venv\\Scripts\\python.exe -I experiments/2026-11-13-m2-18-empty-commits/repro.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline  # noqa: E402
from fidetype.streams.corpus import sentences  # noqa: E402
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig  # noqa: E402
from fidetype.trust.content import CommitGate, GatedPolicy  # noqa: E402
from fidetype.trust.guard import uniform_stream  # noqa: E402
from fidetype.trust.policy import DecisionPolicy, PolicyConfig  # noqa: E402
from fidetype.trust.testing import greedy_nbest  # noqa: E402
from fidetype.trust.types import Candidate, NBest  # noqa: E402


def lexicon_decoder(lexicon: set[str]):
    def decode(stream):
        top = greedy_nbest(stream).top
        text, conf = (top.text, list(top.char_confidences)) if top else ("", [])
        words, confs, i = [], [], 0
        for w in text.split(" "):  # keep the acoustic confidence of each kept character
            if w and w in lexicon:
                words.append(w)
                confs.append(conf[i:i + len(w)] if conf else [])
            i += len(w) + 1
        out = " ".join(words)
        cc: list[float] = []
        for k, c in enumerate(confs):
            cc += ([1.0] if k else []) + list(c)  # joining space: neutral
        return NBest([Candidate(out, 0.0, char_confidences=tuple(cc) if len(cc) == len(out) else ())])
    return decode


def run(n: int = 60, seed: int = 0) -> dict:
    sents = sentences(n, seed=seed)
    lex = {w for s in sents for w in s.split()}
    sim = NoisyDecoderSimulator(SimConfig.preset("median"), seed=seed)
    rng = np.random.default_rng(seed)
    real = [Item(sim.simulate(s, seed=i).stream, s) for i, s in enumerate(sents)]
    uni = [Item(uniform_stream(it.stream(0), rng, 0.05), it.text) for it in real]
    out = {}
    for cmr, ar in ((1.0, 1.01), (0.5, 1.01), (0.1, 1.01), (1.0, 0.8)):
        pc = PolicyConfig(commit_p=0.3, commit_max_risk=cmr, offer_max_k=1, abstain_risk=ar)
        pipe = TrustPipeline(lexicon_decoder(lex), HarnessConfig(policy_config=pc, fit_policy=False, use_calibration=False), {})
        pols = (("v4 policy", DecisionPolicy(pc)), ("+ gate A (no empty)", GatedPolicy.wrap(DecisionPolicy(pc), CommitGate())),
                ("+ gate B (A, risk<1)", GatedPolicy.wrap(DecisionPolicy(pc), CommitGate(1, 0, 1.0))))
        for name, pol in pols:
            for cond, its in (("real", real), ("uniform", uni)):
                recs = pipe.run_items(its, pol, {})
                com = [r for r in recs if r.committed_text is not None]
                out[(cmr, ar, name, cond)] = (len(com), sum(not (r.committed_text or "").strip() for r in com), len(recs))
    an = TrustPipeline(lexicon_decoder(lex)).analyze(lexicon_decoder(lex)(uni[0].stream(0)))
    out["uniform[0]"] = {"top1": an.inputs.texts[0], "p_top1": an.inputs.p_top1, "guard_risk": an.inputs.guard_risk}
    return out


if __name__ == "__main__":
    res = run()
    print("uniform[0]:", res.pop("uniform[0]"))
    print("commit_max_risk abstain_risk policy              input    commits empty n")
    for (cmr, ar, name, cond), (k, e, n) in res.items():
        print(f"{cmr:>15} {ar:>12} {name:<20} {cond:<8} {k:>7} {e:>5} {n}")
