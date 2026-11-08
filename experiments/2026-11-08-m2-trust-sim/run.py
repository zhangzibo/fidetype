"""M2 experiment: the trust core on simulator data.

Compare five policies on effective WPM and safety metrics:

(a) always COMMIT the greedy CTC output (baseline),
(b) always COMMIT the top-1 of the n-best (LM beam, no trust core),
(c) the full trust policy, thresholds fitted on validation,
(d) (c) without calibration (ablation),
(e) (c) without the guard (ablation).

Conditions: simulator presets best/median/worst x confidence_temperature
0.5/1.0/2.0. Each condition has 360 template sentences: 120 calibration,
120 validation, 120 test. The LM is trained on other template sentences.

Run (about 20 min on a laptop CPU):

    uv run python experiments/2026-11-08-m2-trust-sim/run.py
    uv run python experiments/2026-11-08-m2-trust-sim/run.py --quick   # smoke run

Outputs go to ``results/metrics.json`` and ``results/tables.md`` next to
this file.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np

from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
from fidetype.streams.corpus import sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
from fidetype.trust.guard import lexicon_fluency, null_input_audit
from fidetype.trust.policy import Action
from fidetype.trust.testing import RefCharLM, ReferenceDecoder, greedy_nbest
from fidetype.trust.types import from_lm_hypotheses

OUT = Path(__file__).parent / "results"
PRESETS = ("best", "median", "worst")
TEMPS = (0.5, 1.0, 2.0)
MAX_WRONG_COMMIT = 0.05
PARETO_LIMITS = (0.02, 0.10, 0.20, 1.0)

METRIC_KEYS = (
    "ewpm", "ewpm_partial", "wrong_commit_rate", "silent_error_rate", "committed_cer", "communicated_rate",
    "abstain_rate", "rate_commit", "rate_offer", "rate_ask", "rate_abstain", "mean_attempts", "mean_time_s",
)
DIAG_KEYS = (
    "greedy_cer", "cer", "wer", "top1_sentence_acc", "fit_temperature_frame", "fit_temperature_sentence",
    "ece_char_before", "ece_char_after", "ece_sentence_before", "ece_sentence_after", "coverage",
    "coverage_in_nbest", "mean_set_size", "empty_rate", "miss_rate", "word_coverage", "word_mean_set_size",
    "guard_auroc", "guard_auroc_low_evidence", "guard_auroc_inconsistency", "p_top1_auroc",
)


def make_items(sim: NoisyDecoderSimulator, sents: list[str], base_seed: int) -> list[Item]:
    def item(i: int, s: str) -> Item:
        seed = base_seed + 1000 * i
        return Item(sim.simulate(s, seed=seed).stream, s, regen=lambda a: sim.simulate(s, seed=seed + a).stream)

    return [item(i, s) for i, s in enumerate(sents)]


def clean(m: dict) -> dict:
    out = {}
    for k, v in m.items():
        if k == "records":
            continue
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            v = None if math.isnan(v) else str(v)
        out[k] = v
    return out


def run_policy(name, decode_fn, cal, val, test, cache, **cfg):
    t0 = time.time()
    pipe = TrustPipeline(decode_fn, HarnessConfig(**cfg), cache)
    pipe.fit(cal, val)
    m = pipe.evaluate(test)
    m["seconds"] = time.time() - t0
    return pipe, m


def null_audit(pipe: TrustPipeline, dec, streams, fluent) -> dict:
    """Hallucination audit through the fitted pipeline."""

    def decode(s):
        if pipe.frame_scaler.temperature != 1.0:
            s = pipe.frame_scaler.transform_stream(s)
        return dec(s)

    def committed(nb):
        return pipe.policy.decide(pipe.analyze(nb).inputs).action == Action.COMMIT

    return null_input_audit(decode, streams, fluent, accept_fn=committed, seed=0)


def fmt(v, nd=3):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="small smoke run")
    ap.add_argument("--no-lm-beam", action="store_true", help="skip the fidetype.lm cross-check")
    args = ap.parse_args()
    n_split = 30 if args.quick else 120
    presets = ("median",) if args.quick else PRESETS
    temps = (0.5,) if args.quick else TEMPS

    all_s = sentences(3400, seed=0)
    eval_s = all_s[40 : 40 + 3 * n_split]  # template sentences only
    lm_s = all_s[400:]  # disjoint from every evaluation sentence
    lm = RefCharLM(order=5).fit(lm_s)
    dec = ReferenceDecoder(lm)
    lexicon = {w for s in all_s for w in s.split()}
    fluent = lexicon_fluency(lexicon)

    results: dict = {"config": {"n_split": n_split, "max_wrong_commit": MAX_WRONG_COMMIT}, "conditions": {}}
    for pi, preset in enumerate(presets):
        for ti, temp in enumerate(temps):
            cond = f"{preset}/T={temp}"
            t0 = time.time()
            sim = NoisyDecoderSimulator(SimConfig.preset(preset, confidence_temperature=temp), seed=pi * 10 + ti)
            items = make_items(sim, eval_s, base_seed=100_000 * (pi * 10 + ti))
            cal, val, test = items[:n_split], items[n_split : 2 * n_split], items[2 * n_split :]
            cache: dict = {}
            res: dict = {}
            _, res["a_greedy_commit"] = run_policy(
                "a", greedy_nbest, cal, val, test, {}, policy="always_commit", use_calibration=False
            )
            _, res["b_top1_commit"] = run_policy(
                "b", dec, cal, val, test, cache, policy="always_commit", use_calibration=False
            )
            pipe_c, res["c_trust"] = run_policy("c", dec, cal, val, test, cache, max_wrong_commit=MAX_WRONG_COMMIT)
            _, res["d_trust_no_calib"] = run_policy(
                "d", dec, cal, val, test, cache, max_wrong_commit=MAX_WRONG_COMMIT, use_calibration=False
            )
            _, res["e_trust_no_guard"] = run_policy(
                "e", dec, cal, val, test, cache, max_wrong_commit=MAX_WRONG_COMMIT, use_guard=False
            )
            pareto = {}
            for lim in PARETO_LIMITS:
                _, m = run_policy("p", dec, cal, val, test, cache, max_wrong_commit=lim)
                pareto[str(lim)] = {k: m.get(k) for k in METRIC_KEYS} | {"fit_policy_config": m.get("fit_policy_config")}
            audit = None
            if preset == "median" and temp == 1.0 or args.quick:
                streams = [it.stream(0) for it in test[:60]]
                audit = {
                    "trust_policy": null_audit(pipe_c, dec, streams, fluent),
                    "always_commit_top1": null_input_audit(dec, streams, fluent, accept_fn=lambda nb: True, seed=0),
                    "always_commit_greedy": null_input_audit(
                        greedy_nbest, streams, fluent, accept_fn=lambda nb: True, seed=0
                    ),
                }
            results["conditions"][cond] = {
                "policies": {k: clean(v) for k, v in res.items()},
                "pareto_trust": pareto,
                "null_audit": audit,
            }
            c = res["c_trust"]
            print(
                f"{cond}: a={res['a_greedy_commit']['ewpm']:.2f} b={res['b_top1_commit']['ewpm']:.2f} "
                f"c={c['ewpm']:.2f} d={res['d_trust_no_calib']['ewpm']:.2f} e={res['e_trust_no_guard']['ewpm']:.2f} "
                f"| wrong b={res['b_top1_commit']['wrong_commit_rate']:.2f} c={c['wrong_commit_rate']:.2f} "
                f"| {time.time() - t0:.0f}s",
                flush=True,
            )

    # Cross-check with the LM agent's CTC prefix beam search (one condition).
    if not args.no_lm_beam:
        try:
            from fidetype.lm import CharNgramLM, ctc_prefix_beam_search

            lm2 = CharNgramLM(order=6).train(lm_s)

            def dec2(stream):
                return from_lm_hypotheses(ctc_prefix_beam_search(stream, lm2), stream.meta)

            sim = NoisyDecoderSimulator(SimConfig.preset("median", confidence_temperature=1.0), seed=11)
            items = make_items(sim, eval_s, base_seed=100_000 * 11)
            cal, val, test = items[:n_split], items[n_split : 2 * n_split], items[2 * n_split :]
            cache = {}
            lmres = {}
            _, lmres["b_top1_commit"] = run_policy(
                "b", dec2, cal, val, test, cache, policy="always_commit", use_calibration=False
            )
            _, lmres["c_trust"] = run_policy("c", dec2, cal, val, test, cache, max_wrong_commit=MAX_WRONG_COMMIT)
            results["lm_beam_crosscheck"] = {k: clean(v) for k, v in lmres.items()}
            print(f"lm beam median/T=1.0: b={lmres['b_top1_commit']['ewpm']:.2f} c={lmres['c_trust']['ewpm']:.2f}")
        except ImportError as e:  # pragma: no cover
            results["lm_beam_crosscheck"] = f"skipped: {e}"

    OUT.mkdir(exist_ok=True)
    (OUT / "metrics.json").write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    write_tables(results, OUT / "tables.md")
    print("wrote", OUT)


def write_tables(results: dict, path: Path) -> None:
    lines = ["# M2 trust-core simulator results (generated by run.py)", ""]
    lines += [
        "## Policies",
        "",
        "| condition | policy | eWPM | wrong-commit | silent err | committed CER | communicated | COMMIT | OFFER | ASK | ABSTAIN |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for cond, r in results["conditions"].items():
        for pol, m in r["policies"].items():
            lines.append(
                f"| {cond} | {pol} | {fmt(m['ewpm'], 2)} | {fmt(m['wrong_commit_rate'])} | {fmt(m['silent_error_rate'])} "
                f"| {fmt(m['committed_cer'])} | {fmt(m['communicated_rate'])} | {fmt(m['rate_commit'], 2)} "
                f"| {fmt(m['rate_offer'], 2)} | {fmt(m['rate_ask'], 2)} | {fmt(m['rate_abstain'], 2)} |"
            )
    lines += ["", "## Calibration, conformal and guard (trust policy c)", ""]
    lines.append("| condition | " + " | ".join(DIAG_KEYS) + " |")
    lines.append("|---" * (len(DIAG_KEYS) + 1) + "|")
    for cond, r in results["conditions"].items():
        m = r["policies"]["c_trust"]
        lines.append(f"| {cond} | " + " | ".join(fmt(m.get(k)) for k in DIAG_KEYS) + " |")
    lines += ["", "## Pareto: trust policy at other wrong-commit limits", ""]
    lines.append("| condition | limit | eWPM | wrong-commit | COMMIT | OFFER | ASK | ABSTAIN |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for cond, r in results["conditions"].items():
        for lim, m in r["pareto_trust"].items():
            lines.append(
                f"| {cond} | {lim} | {fmt(m['ewpm'], 2)} | {fmt(m['wrong_commit_rate'])} | {fmt(m['rate_commit'], 2)} "
                f"| {fmt(m['rate_offer'], 2)} | {fmt(m['rate_ask'], 2)} | {fmt(m['rate_abstain'], 2)} |"
            )
    lines += ["", "## Null-input audit", ""]
    for cond, r in results["conditions"].items():
        if r["null_audit"]:
            lines.append(f"### {cond}")
            lines.append("")
            lines.append("| pipeline | input | fluent rate | committed rate | fluent and committed |")
            lines.append("|---|---|---|---|---|")
            for pipe, a in r["null_audit"].items():
                for inp, v in a.items():
                    lines.append(
                        f"| {pipe} | {inp} | {fmt(v['fluent_rate'])} | {fmt(v.get('accepted_rate'))} "
                        f"| {fmt(v.get('fluent_accepted_rate'))} |"
                    )
            lines.append("")
    lb = results.get("lm_beam_crosscheck")
    if isinstance(lb, dict):
        lines += ["## Cross-check with fidetype.lm CTC prefix beam (median/T=1.0)", ""]
        lines.append("| policy | eWPM | wrong-commit | CER | coverage in n-best | miss rate | guard AUROC |")
        lines.append("|---|---|---|---|---|---|---|")
        for pol, m in lb.items():
            lines.append(
                f"| {pol} | {fmt(m['ewpm'], 2)} | {fmt(m['wrong_commit_rate'])} | {fmt(m['cer'])} "
                f"| {fmt(m['coverage_in_nbest'])} | {fmt(m['miss_rate'])} | {fmt(m['guard_auroc'])} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
