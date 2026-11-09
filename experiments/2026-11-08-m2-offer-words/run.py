"""M2 OFFER_WORDS: per-word choices and partial correction in the trust layer.

Part ``sim`` (template sentences, as in experiments/2026-11-08-beam-retune, part trust):
  RETUNED beam (n_best 10) + 6-gram char LM, frame calibration before the
  beam, median/worst x T = 0.5/1.0, 120 calib / 120 val / 120 test, the M2
  seeds, one repeat allowed (regen). Policies, all with the word-model user
  (``UserConfig.aac_gaze()``):
    commit     always commit the LM top-1
    trust      trust policy without OFFER_WORDS
    trust_ow   trust policy with OFFER_WORDS
  plus two reference rows with the old sentence-model user (``UserConfig()``)
  that reproduce the beam-retune numbers.

Part ``real`` (real MEG keystroke streams, as in experiments/2026-11-08-m2-real-keystroke):
  RETUNED beam, lm_weight 0.5 (chosen on val there), n_best 10, Spanish 6-gram
  LM. Fit on val (frame T, sentence T, conformal, policy), report on test.
  Sentence-cluster and trial bootstrap CIs. User-model sensitivity runs.

Run (repo root, one process, numpy only):

    uv run python experiments/2026-11-08-m2-offer-words/run.py --part sim
    uv run python experiments/2026-11-08-m2-offer-words/run.py --part real
    uv run python experiments/2026-11-08-m2-offer-words/run.py --part tables

Outputs: results/sim.json, results/real.json, results/tables.md.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

from fidetype.eval.ewpm import summarize
from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
from fidetype.interact.simulated_user import UserConfig, slot_targets
from fidetype.lm import RETUNED, CharNgramLM, ctc_prefix_beam_search
from fidetype.streams.spec import NeuralTextStream
from fidetype.trust.policy import DEFAULT_GRID, OFFER_WORDS_GRID, Action, PolicyConfig
from fidetype.trust.types import from_lm_hypotheses

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
STREAM_ROOT = Path("C:/Users/zhang/bci-data/streams/keystroke-sync-2026-11-08")
SPA_LM = Path("C:/Users/zhang/bci-data/lm/spa_tatoeba_6gram_mkn.npz")
SEED = 0
MAX_WRONG_COMMIT = 0.05
B = 1000

#: Base grid for both trust policies (smaller than DEFAULT_GRID, so that the
#: product with OFFER_WORDS_GRID stays fast: 224 x 35 = 7840 configs).
BASE_GRID = {
    "commit_p": (0.5, 0.7, 0.8, 0.9, 0.95, 0.98, 1.01),
    "commit_max_risk": (0.3, 1.0),
    "offer_max_k": (0, 1, 3, 5),
    "abstain_risk": (0.8, 1.01),
    "final_fallback": ("offer", "abstain"),
}
KEYS = ("ewpm", "wrong_commit_rate", "silent_error_rate", "keystrokes_saved", "system_word_accuracy",
        "communicated_rate", "share_words_system", "share_words_selected", "share_words_typed", "rate_commit",
        "rate_offer", "rate_ask", "rate_abstain", "rate_offer_words", "mean_time_s", "cer", "wer",
        "top1_sentence_acc", "miss_rate", "fit_temperature_frame", "fit_temperature_sentence")


def log(*a) -> None:
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def clean(o):
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return o


def dump(obj, path: Path) -> None:
    path.write_text(json.dumps(clean(obj), indent=1, default=str), encoding="utf-8")


MAX_SILENT = 0.05
#: Fixed (not fitted) diagnostic: OFFER_WORDS for every sentence, every slot highlighted.
OW_ALL = PolicyConfig(commit_p=1.01, offer_max_k=0, final_fallback="abstain", offer_words=True,
                      word_conf_threshold=1.01, offer_words_min_conf=0.0)


def policy_specs(user: UserConfig, mwc: float = MAX_WRONG_COMMIT, diagnostics: bool = True) -> dict[str, HarnessConfig]:
    """The three main policies, plus (if ``diagnostics``) the silent-error-limited fits and OW_ALL."""
    specs = {
        "commit": HarnessConfig(policy="always_commit", user_config=user, seed=SEED),
        "trust": HarnessConfig(grid=BASE_GRID, max_wrong_commit=mwc, user_config=user, seed=SEED),
        "trust_ow": HarnessConfig(grid=BASE_GRID, max_wrong_commit=mwc, user_config=user, seed=SEED,
                                  offer_words=True, word_grid=OFFER_WORDS_GRID),
    }
    if diagnostics:
        # Limit on what reaches the reader (silent errors) instead of on wrong commits.
        specs["trust_silent"] = HarnessConfig(grid=BASE_GRID, max_wrong_commit=1.0, max_silent_error=MAX_SILENT,
                                              user_config=user, seed=SEED)
        specs["trust_ow_silent"] = HarnessConfig(grid=BASE_GRID, max_wrong_commit=1.0, max_silent_error=MAX_SILENT,
                                                 user_config=user, seed=SEED, offer_words=True,
                                                 word_grid=OFFER_WORDS_GRID)
        specs["ow_all"] = HarnessConfig(policy_config=OW_ALL, fit_policy=False, user_config=user, seed=SEED)
    return specs


def word_diagnostics(pipe: TrustPipeline, items) -> dict:
    """OFFER_WORDS details on the first attempt of each test item."""
    n_ow = n_flag = n_flag_wrong = n_flag_hit = n_wrong = n_unflag_wrong = 0
    for it in items:
        an = pipe.analyze(pipe.decode(it, 0))
        d = pipe.policy.decide(an.inputs, final_attempt=it.max_attempts == 1)
        top = an.inputs.texts[0] if an.inputs.texts else ""
        tg = slot_targets(top, it.text)
        wrong = {i for i, (w, t) in enumerate(zip(top.split(), tg)) if w != t}
        n_wrong += len(wrong)
        if d.action != Action.OFFER_WORDS:
            continue
        n_ow += 1
        fl = {c.index: c for c in d.word_choices}
        n_flag += len(fl)
        for i in wrong:
            if i in fl:
                n_flag_wrong += 1
                n_flag_hit += tg[i] in fl[i].alternatives
            else:
                n_unflag_wrong += 1
    return {
        "n_offer_words": n_ow,
        "mean_highlighted": n_flag / n_ow if n_ow else None,
        "highlight_precision": n_flag_wrong / n_flag if n_flag else None,  # highlighted slots that are wrong
        "alt_hit_rate": n_flag_hit / n_flag_wrong if n_flag_wrong else None,  # wrong highlighted slots: truth shown
        "wrong_slots_per_sentence": n_wrong / max(1, len(items)),
        "unflagged_wrong_per_ow": n_unflag_wrong / n_ow if n_ow else None,
    }


def run_policies(decode_fn, cal, val, test, user, cache, extra_specs=None, mwc=MAX_WRONG_COMMIT, diagnostics=True):
    specs = policy_specs(user, mwc, diagnostics)
    specs.update(extra_specs or {})
    out, recs = {}, {}
    for name, cfg in specs.items():
        t0 = time.time()
        pipe = TrustPipeline(decode_fn, cfg, cache)
        pipe.fit(cal, val)
        m = pipe.evaluate(test)
        recs[name] = m.pop("records")
        row = {k: m.get(k) for k in KEYS}
        row["fit_policy_config"] = m.get("fit_policy_config")
        row["fit_feasible"] = m.get("fit_policy_fit_feasible")
        row["val_ewpm"] = m.get("fit_val_ewpm")
        if cfg.offer_words or (cfg.policy_config is not None and cfg.policy_config.offer_words):
            row["word_diag"] = word_diagnostics(pipe, test)
        row["seconds"] = round(time.time() - t0, 1)
        out[name] = row
        log(f"  {name}: eWPM {row['ewpm']:.2f} wrong-commit {row['wrong_commit_rate']:.3f} "
            f"silent {row['silent_error_rate']:.3f} KSR {row['keystrokes_saved']:.3f} "
            f"OW {row['rate_offer_words']:.2f} commit {row['rate_commit']:.2f} ({row['seconds']}s)")
    return out, recs


BOOT_KEYS = ("ewpm", "wrong_commit_rate", "silent_error_rate", "keystrokes_saved", "communicated_rate")
DIFFS = (("trust_ow", "commit"), ("trust_ow", "trust"), ("trust", "commit"),
         ("trust_ow_silent", "commit"), ("trust_ow_silent", "trust_silent"), ("ow_all", "commit"))


def bootstrap(recs: dict[str, list], clusters: np.ndarray | None, seed: int, b: int = B) -> dict:
    """Percentile 95 % CIs; resample items or clusters of items; paired differences."""
    rng = np.random.default_rng(seed)
    n = len(next(iter(recs.values())))
    uc = np.unique(clusters) if clusters is not None else None
    members = {c: np.where(clusters == c)[0] for c in uc} if uc is not None else None
    samples = {p: defaultdict(list) for p in recs}
    diffs = defaultdict(list)
    for _ in range(b):
        idx = rng.integers(0, n, n) if uc is None else np.concatenate([members[c] for c in rng.choice(uc, len(uc))])
        vals = {}
        for p, rs in recs.items():
            m = summarize([rs[i] for i in idx])
            vals[p] = m
            for k in BOOT_KEYS:
                samples[p][k].append(m[k])
        for a, c in DIFFS:
            if a in vals and c in vals:
                for k in BOOT_KEYS:
                    diffs[f"{a}-{c}:{k}"].append(vals[a][k] - vals[c][k])

    def ci(v):
        v = np.asarray([x for x in v if x is not None and math.isfinite(x)], dtype=float)
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size else None

    return {
        "policies": {p: {k: ci(v) for k, v in d.items()} for p, d in samples.items()},
        "diffs": {k: {"ci": ci(v), "p_le_0": float(np.mean(np.asarray(v) <= 0))} for k, v in diffs.items()},
    }


def gaze_only(truths: list[str], user: UserConfig) -> dict:
    """Reference: no BCI, the user types every sentence with the fallback method."""
    t = sum(len(s) for s in truths) * 60.0 / user.fallback_chars_per_min
    return {"ewpm": 60.0 * sum(len(s.split()) for s in truths) / t, "keystrokes_saved": 0.0,
            "silent_error_rate": 0.0, "wrong_commit_rate": 0.0}


# --- part a: simulator ------------------------------------------------------------


def part_sim(quick: bool) -> dict:
    from fidetype.streams.corpus import sentences
    from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig

    n_split = 30 if quick else 120
    all_s = sentences(3400, seed=0)
    eval_s = all_s[40 : 40 + 3 * n_split]
    lm6 = CharNgramLM(order=6).train(all_s[400:])
    kw = dict(RETUNED, n_best=10)

    def dec(stream):
        return from_lm_hypotheses(ctc_prefix_beam_search(stream, lm6, **kw), stream.meta)

    user = UserConfig.aac_gaze()
    old_user = UserConfig()
    res: dict = {"n_split": n_split, "decode_kwargs": kw, "user": asdict(user), "base_grid": BASE_GRID,
                 "offer_words_grid": OFFER_WORDS_GRID, "conditions": {}}
    temps = (1.0,) if quick else (0.5, 1.0)
    presets = ("median",) if quick else ("median", "worst")
    for preset in presets:
        pi = ("best", "median", "worst").index(preset)
        for temp in temps:
            ti = (0.5, 1.0, 2.0).index(temp)
            sd = pi * 10 + ti  # the M2 seeds
            cond = f"{preset}/T={temp}"
            log(cond)
            sim = NoisyDecoderSimulator(SimConfig.preset(preset, confidence_temperature=temp), seed=sd)

            def item(i, s, sim=sim, sd=sd):
                seed = 100_000 * sd + 1000 * i
                return Item(sim.simulate(s, seed=seed).stream, s, regen=lambda a: sim.simulate(s, seed=seed + a).stream)

            items = [item(i, s) for i, s in enumerate(eval_s)]
            cal, val, test = items[:n_split], items[n_split : 2 * n_split], items[2 * n_split :]
            cache: dict = {}
            extra = {
                "ref_commit_old_user": HarnessConfig(policy="always_commit", use_calibration=False, user_config=old_user),
                "ref_trust_old_user": HarnessConfig(max_wrong_commit=MAX_WRONG_COMMIT, user_config=old_user,
                                                    grid=DEFAULT_GRID),
            }
            rows, recs = run_policies(dec, cal, val, test, user, cache, extra)
            boot = bootstrap({p: recs[p] for p in recs if not p.startswith("ref_")}, None, SEED)
            rows["gaze_only"] = gaze_only([it.text for it in test], user)
            res["conditions"][cond] = {"policies": rows, "bootstrap_items": boot}
            dump(res, OUT / ("sim_quick.json" if quick else "sim.json"))
    return res


# --- part b: real MEG -----------------------------------------------------------------


def load_split(split: str) -> list[tuple[NeuralTextStream, dict]]:
    rows = [json.loads(x) for x in (STREAM_ROOT / split / "labels.jsonl").read_text(encoding="utf-8").splitlines() if x]
    return [(NeuralTextStream.from_npz(STREAM_ROOT / r["stream"]), r) for r in rows]


def part_real(quick: bool) -> dict:
    t0 = time.time()
    lm = CharNgramLM.load(SPA_LM)
    kw = {**dict(RETUNED), "n_best": 10, "lm_weight": 0.5}

    def dec(stream):
        return from_lm_hypotheses(ctc_prefix_beam_search(stream, lm, **kw), stream.meta, confidence_variant="frame")

    val_raw, test_raw = load_split("val"), load_split("test")
    if quick:
        val_raw, test_raw = val_raw[:30], test_raw[:40]
    val = [Item(s, r["target_text"]) for s, r in val_raw]
    test = [Item(s, r["target_text"]) for s, r in test_raw]
    log(f"real: {len(val)} val trials ({len({i.text for i in val})} sentences), "
        f"{len(test)} test trials ({len({i.text for i in test})} sentences)")
    sid = {t: i for i, t in enumerate(sorted({it.text for it in test}))}
    clusters = np.array([sid[it.text] for it in test])
    user = UserConfig.aac_gaze()
    cache: dict = {}
    res: dict = {"n_val": len(val), "n_test": len(test), "n_test_sentences": len(sid),
                 "n_val_sentences": len({i.text for i in val}), "decode_kwargs": kw, "user": asdict(user),
                 "base_grid": BASE_GRID, "offer_words_grid": OFFER_WORDS_GRID}
    log("main run (aac_gaze user)")
    rows, recs = run_policies(dec, val, val, test, user, cache)  # fit(val, val): as in the M2-10 run
    rows["gaze_only"] = gaze_only([it.text for it in test], user)
    res["policies"] = rows
    res["bootstrap_sentences"] = bootstrap(recs, clusters, SEED + 1)
    res["bootstrap_trials"] = bootstrap(recs, None, SEED)
    res["examples"] = examples(recs, test)
    dump(res, OUT / ("real_quick.json" if quick else "real.json"))
    # User-model sensitivity: refit every policy for each variant.
    variants = {
        "fallback_40cpm (FP1, 8.1 WPM)": dict(fallback_chars_per_min=40.0),
        "p_miss_unflagged 0": dict(p_miss_unflagged=0.0),
        "p_miss_unflagged 0.2": dict(p_miss_unflagged=0.2),
        "slow selection (scan, select, nav x2)": dict(word_scan_a_s=2.0, word_scan_b_s_per_bit=2.0, word_select_s=3.0,
                                                      nav_s=6.0),
        "no full retype": dict(allow_full_retype=False),
        "no typing after ABSTAIN": dict(fallback_after_abstain=False),
    }
    if quick:
        variants = dict(list(variants.items())[:1])
    res["sensitivity"] = {}
    for vname, ov in variants.items():
        log(f"sensitivity: {vname}")
        u = replace(user, **ov)
        r2, rc2 = run_policies(dec, val, val, test, u, cache, diagnostics=False)
        bs = bootstrap(rc2, clusters, SEED + 1, b=300)
        res["sensitivity"][vname] = {
            "policies": {p: {k: v[k] for k in ("ewpm", "wrong_commit_rate", "silent_error_rate", "keystrokes_saved",
                                               "rate_offer_words", "rate_commit")} for p, v in r2.items()},
            "gaze_only_ewpm": gaze_only([it.text for it in test], u)["ewpm"],
            "diffs": {k: v for k, v in bs["diffs"].items() if k.endswith(":ewpm") or k.endswith(":silent_error_rate")},
        }
        dump(res, OUT / ("real_quick.json" if quick else "real.json"))
    res["seconds"] = round(time.time() - t0, 1)
    dump(res, OUT / ("real_quick.json" if quick else "real.json"))
    return res


def examples(recs, test, n: int = 4) -> list[dict]:
    out, seen = [], set()
    for i, it in enumerate(test):
        if it.text in seen:
            continue
        seen.add(it.text)
        out.append({"truth": it.text, **{p: {"system": rs[i].system_text, "final": rs[i].final_text,
                                              "actions": rs[i].actions, "time_s": round(rs[i].time_s, 1),
                                              "keystrokes": rs[i].keystrokes} for p, rs in recs.items()}})
        if len(out) >= n:
            break
    return out


# --- tables ------------------------------------------------------------------------------


def f(v, nd=2):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def fci(point, ci, nd=2):
    if ci is None:
        return f(point, nd)
    if point is None:
        return f"[{f(ci[0], nd)}, {f(ci[1], nd)}]"
    return f"{f(point, nd)} [{f(ci[0], nd)}, {f(ci[1], nd)}]"


MAIN = ("commit", "trust", "trust_ow", "trust_silent", "trust_ow_silent", "ow_all", "gaze_only")
NAMES = {"commit": "always commit LM top-1", "trust": "trust, no OFFER_WORDS", "trust_ow": "trust + OFFER_WORDS",
         "trust_silent": "diag: trust, silent-error limit", "trust_ow_silent": "diag: trust + OFFER_WORDS, silent-error limit",
         "ow_all": "diag: OFFER_WORDS always, all slots highlighted",
         "gaze_only": "reference: gaze typing only (no BCI)", "ref_commit_old_user": "ref: commit, old user, no calib",
         "ref_trust_old_user": "ref: trust, old user, full grid"}


def write_tables() -> None:
    L = ["# Tables (generated by run.py --part tables)", ""]
    sp = OUT / "sim.json"
    if sp.exists():
        sim = json.loads(sp.read_text(encoding="utf-8"))
        L += ["## (a) Simulator, test set (120 sentences per condition)", "",
              "eWPM [item-bootstrap 95 % CI]. User: `UserConfig.aac_gaze()` (rows `ref:` use `UserConfig()`).", "",
              "| condition | policy | eWPM | wrong-commit | silent error | KSR | sys word acc | COMMIT | OFFER | ASK | ABSTAIN | OFFER_WORDS |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for cond, d in sim["conditions"].items():
            bp = d["bootstrap_items"]["policies"]
            for p in MAIN + ("ref_commit_old_user", "ref_trust_old_user"):
                r = d["policies"].get(p)
                if r is None:
                    continue
                ci = bp.get(p, {}).get("ewpm")
                L.append(f"| {cond} | {NAMES[p]} | {fci(r['ewpm'], ci)} | {f(r.get('wrong_commit_rate'), 3)} | "
                         f"{f(r.get('silent_error_rate'), 3)} | {f(r.get('keystrokes_saved'))} | "
                         f"{f(r.get('system_word_accuracy'))} | {f(r.get('rate_commit'))} | {f(r.get('rate_offer'))} | "
                         f"{f(r.get('rate_ask'))} | {f(r.get('rate_abstain'))} | {f(r.get('rate_offer_words'))} |")
        L += ["", "### Paired differences (item bootstrap)", "", "| condition | difference | eWPM CI | silent-error CI | KSR CI |",
              "|---|---|---|---|---|"]
        for cond, d in sim["conditions"].items():
            df = d["bootstrap_items"]["diffs"]
            for a, c in DIFFS:
                g = lambda k: df.get(f"{a}-{c}:{k}", {}).get("ci")
                L.append(f"| {cond} | {a} − {c} | {fci(None, g('ewpm'))} | {fci(None, g('silent_error_rate'), 3)} | "
                         f"{fci(None, g('keystrokes_saved'))} |")
        L += ["", "### OFFER_WORDS details (trust + OFFER_WORDS, first attempt)", "",
              "| condition | fitted word_conf_threshold / min_conf | OFFER_WORDS sentences | mean highlighted | highlighted that are wrong | truth among alternatives (wrong highlighted) | unflagged wrong per OFFER_WORDS | words: system / selected / typed |",
              "|---|---|---|---|---|---|---|---|"]
        for cond, d in sim["conditions"].items():
            for pn in ("trust_ow", "trust_ow_silent", "ow_all"):
                r = d["policies"][pn]
                w, pc = r.get("word_diag", {}), r.get("fit_policy_config") or asdict(OW_ALL)
                L.append(
                    f"| {cond} {pn} | {pc.get('word_conf_threshold')} / {pc.get('offer_words_min_conf')} | "
                    f"{w.get('n_offer_words')} | {f(w.get('mean_highlighted'))} | {f(w.get('highlight_precision'))} | "
                    f"{f(w.get('alt_hit_rate'))} | {f(w.get('unflagged_wrong_per_ow'))} | "
                    f"{f(r['share_words_system'])} / {f(r['share_words_selected'])} / {f(r['share_words_typed'])} |"
                )
    rp = OUT / "real.json"
    if rp.exists():
        real = json.loads(rp.read_text(encoding="utf-8"))
        bs, bt = real["bootstrap_sentences"], real["bootstrap_trials"]
        L += ["", f"## (b) Real MEG, test ({real['n_test']} trials, {real['n_test_sentences']} sentences; fitted on val)", "",
              "Value [trial-bootstrap 95 % CI] {sentence-cluster bootstrap 95 % CI}.", "",
              "| policy | eWPM | wrong-commit | silent error | KSR | sys word acc | COMMIT | OFFER | ASK | ABSTAIN | OFFER_WORDS | mean time (s) |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for p in MAIN:
            r = real["policies"][p]

            def c3(k, nd=2):
                t = bt["policies"].get(p, {}).get(k)
                s = bs["policies"].get(p, {}).get(k)
                out = fci(r.get(k), t, nd)
                if s:
                    out += " {" + f"{f(s[0], nd)}, {f(s[1], nd)}" + "}"
                return out

            L.append(f"| {NAMES[p]} | {c3('ewpm')} | {f(r.get('wrong_commit_rate'), 3)} | {c3('silent_error_rate', 3)} | "
                     f"{c3('keystrokes_saved')} | {f(r.get('system_word_accuracy'))} | {f(r.get('rate_commit'))} | "
                     f"{f(r.get('rate_offer'))} | {f(r.get('rate_ask'))} | {f(r.get('rate_abstain'))} | "
                     f"{f(r.get('rate_offer_words'))} | {f(r.get('mean_time_s'), 1)} |")
        L += ["", "### Paired differences (real, test)", "", "| difference | metric | trial CI | sentence CI | P(diff <= 0), sentence |",
              "|---|---|---|---|---|"]
        for a, c in DIFFS:
            for k in ("ewpm", "silent_error_rate", "keystrokes_saved"):
                key = f"{a}-{c}:{k}"
                if key not in bt["diffs"]:
                    continue
                L.append(f"| {a} − {c} | {k} | {fci(None, bt['diffs'][key]['ci'], 3)} | {fci(None, bs['diffs'][key]['ci'], 3)} | "
                         f"{f(bs['diffs'][key]['p_le_0'], 3)} |")
        L += ["", "### OFFER_WORDS details (real, test)", ""]
        for pn in ("trust_ow", "trust_ow_silent", "ow_all"):
            r = real["policies"][pn]
            w, pc = r.get("word_diag", {}), r.get("fit_policy_config") or asdict(OW_ALL)
            L += [
                f"- **{pn}**. Config: `{json.dumps(pc)}` (fit feasible: {r.get('fit_feasible')}).",
                f"  OFFER_WORDS sentences: {w.get('n_offer_words')}; mean highlighted slots {f(w.get('mean_highlighted'))}; "
                f"highlighted slots that are wrong {f(w.get('highlight_precision'))}; truth among the alternatives of a "
                f"wrong highlighted slot {f(w.get('alt_hit_rate'))}; wrong slots per sentence "
                f"{f(w.get('wrong_slots_per_sentence'))}; unflagged wrong slots per OFFER_WORDS "
                f"{f(w.get('unflagged_wrong_per_ow'))}.",
                f"  Words right at the end: system {f(r['share_words_system'])}, selected "
                f"{f(r['share_words_selected'])}, typed {f(r['share_words_typed'])}.",
            ]
        for pn in ("trust", "trust_silent"):
            L.append(f"- {pn} fitted config: `{json.dumps(real['policies'][pn].get('fit_policy_config'))}`.")
        if real.get("sensitivity"):
            L += ["", "### User-model sensitivity (real, test; every policy refitted on val)", "",
                  "| variant | commit eWPM / silent | trust eWPM / silent | trust+OW eWPM / silent | OW rate | gaze-only eWPM | OW − commit eWPM, sentence CI | OW − trust eWPM, sentence CI |",
                  "|---|---|---|---|---|---|---|---|"]
            for vn, v in real["sensitivity"].items():
                P = v["policies"]
                cell = lambda p: f"{f(P[p]['ewpm'])} / {f(P[p]['silent_error_rate'], 3)}"
                L.append(f"| {vn} | {cell('commit')} | {cell('trust')} | {cell('trust_ow')} | {f(P['trust_ow']['rate_offer_words'])} | "
                         f"{f(v['gaze_only_ewpm'])} | {fci(None, v['diffs']['trust_ow-commit:ewpm']['ci'])} | "
                         f"{fci(None, v['diffs']['trust_ow-trust:ewpm']['ci'])} |")
        if real.get("examples"):
            L += ["", "### Examples (real, test, first trial of the first sentences)", ""]
            for e in real["examples"]:
                L.append(f"- truth `{e['truth']}`; top-1 `{e['trust_ow']['system']}`; trust+OW: {e['trust_ow']['actions']}, "
                         f"{e['trust_ow']['time_s']} s, {e['trust_ow']['keystrokes']} keystrokes; commit: "
                         f"{e['commit']['time_s']} s, {e['commit']['keystrokes']} keystrokes.")
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=("sim", "real", "tables"), required=True)
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.part == "sim":
        part_sim(a.quick)
    elif a.part == "real":
        part_real(a.quick)
    if not a.quick:
        write_tables()


if __name__ == "__main__":
    main()
