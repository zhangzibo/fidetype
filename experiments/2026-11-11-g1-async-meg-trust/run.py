"""G1 (Paper 1): the full trust evaluation on the async M1-09 MEG streams.

CPU only. Same settings as the M1-15 full-r1 run (``ewpm_check.py`` ->
M2-14 ``part_real``), M2-13 (CRC / LTT) and M2-16 (online re-calibration),
but on the async decoder ``m1-09-r4b-full-medium`` (the Paper 1 MEG decoder).

Stages (``--stages``, comma list):

- ``harness``: eWPM harness on test (fit on val): commit, trust, trust_ow,
  trust_silent, trust_ow_silent, ow_all, gaze only. 95 % percentile CIs from
  four bootstraps: trials, clusters of unique sentences (17), clusters of
  participants (19), and a two-way (crossed) bootstrap over sentences x
  participants. Paired differences, including policy - gaze only.
  Then the user-model sensitivity runs (refit per variant).
- ``null``: null-input audit with the fitted commit / trust / trust_ow pipes:
  real, shuffled MEG and zeros MEG (the M1-09 ``infer --control`` outputs),
  other sentence (the stream of another test instance with another target),
  frame-shuffled and near-uniform streams.
- ``items`` + ``splits``: M2-13 per-trial item table of the trust gate and
  200 random cal / test splits (n_cal 100 and 408): old, plug-in, CRC,
  CRC + tune, LTT. Plus grouped splits (calibrate on 11 sentences / 12
  participants, test on the others) and the one-shot val -> test row.
- ``online``: M2-16 drift protocol (warm start on val, test in file order =
  participant by participant).

``--streams sync`` runs the harness (no sensitivity) on the synchronous
M1-15 full-r1 streams, to give the old MEG row the same CIs.

Run (repo root):
    .venv\\Scripts\\python.exe -I experiments/2026-11-11-g1-async-meg-trust/run.py
    .venv\\Scripts\\python.exe -I experiments/2026-11-11-g1-async-meg-trust/run.py --streams sync --stages harness --no-sensitivity
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "2"
os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import argparse
import bz2
import importlib.util
import json
import math
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.streams.vocab import normalize_text  # noqa: E402
from fidetype.eval.ewpm import correct_words_strict, summarize  # noqa: E402
from fidetype.eval.harness import Item, TrustPipeline  # noqa: E402
from fidetype.interact.simulated_user import UserConfig  # noqa: E402
from fidetype.lm import RETUNED, CharNgramLM, ctc_prefix_beam_search  # noqa: E402
from fidetype.streams.spec import NeuralTextStream  # noqa: E402
from fidetype.trust.guard import auroc, lexicon_fluency, shuffle_stream, uniform_stream  # noqa: E402
from fidetype.trust.policy import Action  # noqa: E402
from fidetype.trust.types import from_lm_hypotheses  # noqa: E402

CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
SEED = CONFIG["seed"]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M2 = load_module("m2ow", REPO / "experiments/2026-11-08-m2-offer-words/run.py")


class Logger:
    path: Path | None = None


def log(*a) -> None:
    msg = time.strftime("%H:%M:%S") + " " + " ".join(str(x) for x in a)
    print(msg, flush=True)
    if Logger.path is not None:
        with open(Logger.path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def dump(obj, path: Path) -> None:
    path.write_text(json.dumps(M2.clean(obj), indent=1, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def load_split(root: Path, split: str):
    rows = [json.loads(x) for x in (root / split / "labels.jsonl").read_text(encoding="utf-8").splitlines() if x]
    out = []
    for r in rows:
        s = NeuralTextStream.from_npz(root / split / r["file"])
        r = dict(r)
        r.setdefault("participant", s.meta.get("participant"))
        out.append((s, r))
    return out


def make_decoder():
    lm = CharNgramLM.load(M2.SPA_LM)
    kw = {**dict(RETUNED), "n_best": 10, "lm_weight": 0.5}

    def dec(stream):
        return from_lm_hypotheses(ctc_prefix_beam_search(stream, lm, **kw), stream.meta, confidence_variant="frame")

    return dec, kw


# ---------------------------------------------------------------------------
# Bootstrap with weights (trials, sentence clusters, participant clusters, two-way)
# ---------------------------------------------------------------------------


def rec_arrays(recs) -> dict[str, np.ndarray]:
    return {
        "w": np.array([correct_words_strict(r) for r in recs], float),
        "t": np.array([r.time_s for r in recs], float),
        "wc": np.array([float(r.wrong_commit) for r in recs]),
        "se": np.array([float(r.silent_error) for r in recs]),
        "ks": np.array([r.keystrokes for r in recs], float),
        "nc": np.array([len(r.truth) for r in recs], float),
    }


def gaze_arrays(truths: list[str], user: UserConfig) -> dict[str, np.ndarray]:
    nc = np.array([len(s) for s in truths], float)
    z = np.zeros(len(truths))
    return {"w": np.array([len(s.split()) for s in truths], float), "t": nc * 60.0 / user.fallback_chars_per_min,
            "wc": z, "se": z, "ks": nc.copy(), "nc": nc}


def wmetrics(a: dict, wt: np.ndarray) -> dict[str, float]:
    sw = wt.sum()
    return {"ewpm": 60.0 * float((a["w"] * wt).sum() / (a["t"] * wt).sum()),
            "wrong_commit_rate": float((a["wc"] * wt).sum() / sw),
            "silent_error_rate": float((a["se"] * wt).sum() / sw),
            "keystrokes_saved": 1.0 - float((a["ks"] * wt).sum() / (a["nc"] * wt).sum())}


def weights(rng, scheme: str, sent: np.ndarray, part: np.ndarray) -> np.ndarray:
    n = len(sent)
    if scheme == "trials":
        return np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
    if scheme == "sentences":
        k = sent.max() + 1
        return np.bincount(rng.integers(0, k, k), minlength=k)[sent].astype(float)
    if scheme == "participants":
        k = part.max() + 1
        return np.bincount(rng.integers(0, k, k), minlength=k)[part].astype(float)
    if scheme == "two_way":
        ks, kp = sent.max() + 1, part.max() + 1
        cs = np.bincount(rng.integers(0, ks, ks), minlength=ks)
        cp = np.bincount(rng.integers(0, kp, kp), minlength=kp)
        w = (cs[sent] * cp[part]).astype(float)
        return w
    raise ValueError(scheme)


SCHEMES = ("trials", "sentences", "participants", "two_way")
MKEYS = ("ewpm", "wrong_commit_rate", "silent_error_rate", "keystrokes_saved")


def boot_all(arrs: dict[str, dict], diffs: list[tuple[str, str]], sent, part, B: int, seed: int,
             schemes=SCHEMES) -> dict:
    out = {}
    for si, sc in enumerate(schemes):
        rng = np.random.default_rng(seed + si)
        samp = {p: {k: [] for k in MKEYS} for p in arrs}
        dsamp = {f"{a}-{b}": {k: [] for k in MKEYS} for a, b in diffs}
        for _ in range(B):
            wt = weights(rng, sc, sent, part)
            if wt.sum() == 0:
                continue
            vals = {p: wmetrics(a, wt) for p, a in arrs.items()}
            for p, v in vals.items():
                for k in MKEYS:
                    samp[p][k].append(v[k])
            for a, b in diffs:
                for k in MKEYS:
                    dsamp[f"{a}-{b}"][k].append(vals[a][k] - vals[b][k])

        def ci(v):
            v = np.asarray(v, float)
            v = v[np.isfinite(v)]
            return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size else None

        out[sc] = {
            "policies": {p: {k: ci(v) for k, v in d.items()} for p, d in samp.items()},
            "diffs": {name: {k: {"ci": ci(v), "p_le_0": float(np.mean(np.asarray(v) <= 0))} for k, v in d.items()}
                      for name, d in dsamp.items()},
        }
    return out


DIFFS = [("trust", "commit"), ("trust_ow", "commit"), ("trust_ow", "trust"), ("trust", "gaze_only"),
         ("trust_ow", "gaze_only"), ("commit", "gaze_only"), ("ow_all", "gaze_only"), ("ow_all", "commit")]


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def run_policies(dec, val, test, user, cache, diagnostics=True):
    specs = M2.policy_specs(user, M2.MAX_WRONG_COMMIT, diagnostics)
    rows, recs, pipes = {}, {}, {}
    for name, cfg in specs.items():
        t0 = time.time()
        pipe = TrustPipeline(dec, cfg, cache)
        pipe.fit(val, val)  # as in M2-10 / M2-14 / M1-15 full-r1
        m = pipe.evaluate(test)
        recs[name] = m.pop("records")
        row = {k: m.get(k) for k in M2.KEYS}
        row["fit_policy_config"] = m.get("fit_policy_config")
        row["fit_feasible"] = m.get("fit_policy_fit_feasible")
        row["val_ewpm"] = m.get("fit_val_ewpm")
        if cfg.offer_words or (cfg.policy_config is not None and cfg.policy_config.offer_words):
            row["word_diag"] = M2.word_diagnostics(pipe, test)
        row["seconds"] = round(time.time() - t0, 1)
        rows[name], pipes[name] = row, pipe
        log(f"  {name}: eWPM {row['ewpm']:.3f} wrong-commit {row['wrong_commit_rate']:.3f} "
            f"silent {row['silent_error_rate']:.3f} KSR {row['keystrokes_saved']:.3f} "
            f"OW {row['rate_offer_words']:.2f} commit {row['rate_commit']:.2f} offer {row['rate_offer']:.2f} "
            f"({row['seconds']}s)")
    return rows, recs, pipes


def nbest_hits(pipe, items) -> dict:
    """Share of test trials with the true sentence at rank 1 / in the 10-best (first attempt)."""
    top1 = inn = 0
    for it in items:
        nb = pipe.decode(it, 0)
        texts = [c.text for c in nb.candidates] if hasattr(nb, "candidates") else list(nb.texts)
        top1 += bool(texts) and texts[0] == it.text
        inn += it.text in texts
    return {"top1_sentence_acc": top1 / len(items), "in_nbest": inn / len(items)}


def per_group(recs_by_policy: dict, groups: list[str]) -> dict:
    out = {}
    for g in sorted(set(groups)):
        idx = [i for i, x in enumerate(groups) if x == g]
        out[g] = {"n": len(idx), **{p: {k: summarize([rs[i] for i in idx])[k] for k in ("ewpm", "wrong_commit_rate")}
                                    for p, rs in recs_by_policy.items()}}
    return out


def stage_harness(ctx: dict, sensitivity: bool) -> None:
    t0 = time.time()
    dec, kw = ctx["dec"], ctx["kw"]
    val, test, test_raw = ctx["val"], ctx["test"], ctx["test_raw"]
    user = UserConfig.aac_gaze()
    log(f"harness [{ctx['name']}]: {len(val)} val ({len({i.text for i in val})} sentences), {len(test)} test "
        f"({len({i.text for i in test})} sentences, {len(set(ctx['part_names']))} participants)")
    rows, recs, pipes = run_policies(dec, val, test, user, ctx["cache"])
    truths = [it.text for it in test]
    rows["gaze_only"] = M2.gaze_only(truths, user)
    arrs = {p: rec_arrays(r) for p, r in recs.items()}
    arrs["gaze_only"] = gaze_arrays(truths, user)
    for p, r in recs.items():  # check: weighted metrics == harness metrics
        chk = wmetrics(arrs[p], np.ones(len(r)))
        assert abs(chk["ewpm"] - rows[p]["ewpm"]) < 1e-9 and abs(chk["wrong_commit_rate"] - rows[p]["wrong_commit_rate"]) < 1e-12, p
    assert abs(wmetrics(arrs["gaze_only"], np.ones(len(truths)))["ewpm"] - rows["gaze_only"]["ewpm"]) < 1e-9
    res = {"streams": ctx["name"], "stream_root": str(ctx["root"]), "n_val": len(val), "n_test": len(test),
           "n_test_sentences": int(ctx["sent"].max() + 1), "n_test_participants": int(ctx["part"].max() + 1),
           "n_val_sentences": len({i.text for i in val}), "decode_kwargs": kw, "user": asdict(user),
           "base_grid": M2.BASE_GRID, "policies": rows}
    log("bootstrap ...")
    res["bootstrap"] = boot_all(arrs, DIFFS, ctx["sent"], ctx["part"], CONFIG["bootstrap_B"], SEED + 10)
    res["nbest"] = nbest_hits(pipes["trust"], test)
    res["per_participant"] = per_group({p: recs[p] for p in ("commit", "trust", "trust_ow")}, ctx["part_names"])
    res["per_participant"]["_gaze_only"] = {g: M2.gaze_only([truths[i] for i, x in enumerate(ctx["part_names"]) if x == g], user)["ewpm"]
                                            for g in sorted(set(ctx["part_names"]))}
    res["examples"] = M2.examples(recs, test)
    ctx["pipes"] = pipes
    out = ctx["out"] / f"harness-{ctx['name']}.json"
    dump(res, out)
    if sensitivity:
        variants = {
            "fallback_40cpm (FP1, 8.1 WPM)": dict(fallback_chars_per_min=40.0),
            "p_miss_unflagged 0": dict(p_miss_unflagged=0.0),
            "p_miss_unflagged 0.2": dict(p_miss_unflagged=0.2),
            "slow selection (scan, select, nav x2)": dict(word_scan_a_s=2.0, word_scan_b_s_per_bit=2.0,
                                                          word_select_s=3.0, nav_s=6.0),
            "no full retype": dict(allow_full_retype=False),
            "no typing after ABSTAIN": dict(fallback_after_abstain=False),
        }
        res["sensitivity"] = {}
        for vname, ov in variants.items():
            log(f"sensitivity: {vname}")
            u = replace(user, **ov)
            r2, rc2, _ = run_policies(dec, val, test, u, ctx["cache"], diagnostics=False)
            a2 = {p: rec_arrays(r) for p, r in rc2.items()}
            a2["gaze_only"] = gaze_arrays(truths, u)
            bs = boot_all(a2, [("trust", "commit"), ("trust_ow", "commit"), ("trust", "gaze_only"), ("trust_ow", "gaze_only")],
                          ctx["sent"], ctx["part"], CONFIG["bootstrap_B_sensitivity"], SEED + 20,
                          schemes=("sentences", "participants"))
            res["sensitivity"][vname] = {
                "policies": {p: {k: v[k] for k in ("ewpm", "wrong_commit_rate", "silent_error_rate", "keystrokes_saved",
                                                   "rate_offer_words", "rate_commit")} for p, v in r2.items()},
                "gaze_only_ewpm": M2.gaze_only(truths, u)["ewpm"],
                "diffs_ewpm": {sc: {k: v["ewpm"] for k, v in d["diffs"].items()} for sc, d in bs.items()},
            }
            dump(res, out)
    res["seconds"] = round(time.time() - t0, 1)
    dump(res, out)
    log(f"harness done ({res['seconds']} s)")


# ---------------------------------------------------------------------------
# Null audit
# ---------------------------------------------------------------------------


def spanish_lexicon() -> set[str]:
    words: set[str] = set()
    with bz2.open(CONFIG["lexicon_corpus"], "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if parts:
                words.update(normalize_text(parts[-1]).split())
    return words


def with_logprobs(s: NeuralTextStream, lp: np.ndarray, tag: str) -> NeuralTextStream:
    assert lp.shape == s.log_probs.shape, (lp.shape, s.log_probs.shape)
    return NeuralTextStream(log_probs=lp.astype(np.float32), frame_times=s.frame_times, vocab=s.vocab,
                            blank_id=s.blank_id, source=s.source + "+" + tag, meta={**s.meta, "audit": tag},
                            vocab_type=s.vocab_type)


def stage_null(ctx: dict) -> None:
    t0 = time.time()
    pipes = ctx["pipes"]
    test_raw = ctx["test_raw"]
    truths = [it.text for it in ctx["test"]]
    rng = np.random.default_rng(SEED)
    base = [s for s, _ in test_raw]
    ctl = np.load(CONFIG["controls_npz"])
    # Other sentence: a derangement inside the same participant where possible (else any other sentence).
    n = len(base)
    other = []
    for i in range(n):
        same_p = [j for j in range(n) if ctx["part"][j] == ctx["part"][i] and truths[j] != truths[i]]
        pool = same_p or [j for j in range(n) if truths[j] != truths[i]]
        other.append(int(rng.choice(pool)))
    nulls = {
        "real": base,
        "shuffled_meg": [with_logprobs(s, ctl["shuffled__" + r["file"]], "shuffled_meg") for s, r in test_raw],
        "zeros_meg": [with_logprobs(s, ctl["zeros__" + r["file"]], "zeros_meg") for s, r in test_raw],
        "other_sentence": [base[j] for j in other],
        "frame_shuffled": [shuffle_stream(s, rng) for s in base],
        "uniform": [uniform_stream(s, rng, 0.05) for s in base],
    }
    lex = spanish_lexicon()
    fluent = lexicon_fluency(lex)
    dcache: dict = {}
    audit: dict = {"lexicon_size": len(lex), "n": n, "policies": {}}
    for name in ("commit", "trust", "trust_ow"):
        pipe = pipes[name]
        T = pipe.frame_scaler.temperature
        a = audit["policies"][name] = {}
        sig: dict = {}
        for cond, ss in nulls.items():
            fl, com, fc, wc, ow, nonempty = [], [], [], [], [], []
            for i, s in enumerate(ss):
                key = (cond, i, round(T, 9))
                nb = dcache.get(key)
                if nb is None:
                    s2 = pipe.frame_scaler.transform_stream(s) if T != 1.0 else s
                    nb = ctx["dec"](s2)
                    dcache[key] = nb
                an = pipe.analyze(nb)
                d = pipe.policy.decide(an.inputs, final_attempt=True)
                top = nb.top.text if nb.top is not None else ""
                c = d.action == Action.COMMIT
                f = fluent(top)
                fl.append(f)
                com.append(c)
                fc.append(f and c)
                wc.append(c and top != truths[i])
                ow.append(d.action == Action.OFFER_WORDS)
                nonempty.append(bool(top))
                sig.setdefault(cond, []).append(an.guard.risk)
            a[cond] = {"fluent_rate": float(np.mean(fl)), "commit_rate": float(np.mean(com)),
                       "fluent_commit_rate": float(np.mean(fc)), "wrong_commit_rate": float(np.mean(wc)),
                       "offer_words_rate": float(np.mean(ow)), "nonempty_rate": float(np.mean(nonempty))}
        a["risk_auroc_null_vs_real"] = {
            c: auroc(np.r_[sig[c], sig["real"]], np.r_[np.ones(len(sig[c])), np.zeros(len(sig["real"]))])
            for c in nulls if c != "real"}
        log(f"audit {name}: " + " ".join(f"{c}: commit {v['commit_rate']:.3f} fluent+commit {v['fluent_commit_rate']:.3f}"
                                          for c, v in a.items() if c in nulls))
    audit["seconds"] = round(time.time() - t0, 1)
    dump(audit, ctx["out"] / f"null-audit-{ctx['name']}.json")


# ---------------------------------------------------------------------------
# CRC / LTT (M2-13) and online (M2-16)
# ---------------------------------------------------------------------------


def stage_items(ctx: dict) -> None:
    t0 = time.time()
    m13 = load_module("m213", REPO / "experiments/2026-11-11-m2-13-conformal/run.py")
    pipe = ctx["pipes"]["trust"]
    res = {"fit": m13.item_table(pipe, ctx["val"]), "test": m13.item_table(pipe, ctx["test"]),
           "fit_report": {k: m13.fnum(v) if isinstance(v, float) else v for k, v in pipe.fit_report.items()},
           "participants_test": ctx["part_names"], "sentence_ids_test": ctx["sent"].tolist()}
    s = np.array([float(x) for x in res["test"]["score"]])
    log(f"items: eligible {np.isfinite(s).mean():.3f}, top-1 right overall {1 - np.mean(res['test']['loss_c']):.4f} "
        f"({time.time() - t0:.0f}s)")
    dump(res, ctx["out"] / f"items-meg-{ctx['name']}.json")


def stage_splits(ctx: dict) -> None:
    m13 = load_module("m213", REPO / "experiments/2026-11-11-m2-13-conformal/run.py")
    m13.ALPHA, m13.DELTA = CONFIG["alpha"], CONFIG["delta"]
    d = json.loads((ctx["out"] / f"items-meg-{ctx['name']}.json").read_text(encoding="utf-8"))
    a_fit, a_test = m13.Arr(d["fit"]), m13.Arr(d["test"])
    n = len(a_test.s)
    sent, part = np.asarray(d["sentence_ids_test"]), np.unique(d["participants_test"], return_inverse=True)[1]
    allidx = np.arange(n)
    ds = {"alpha": CONFIG["alpha"], "delta": CONFIG["delta"], "reps": CONFIG["reps"], "n_test": n,
          "n_fit": len(a_fit.s), "lam_old": a_test.lam_old, "eligible_rate": float(np.isfinite(a_test.s).mean()),
          "top1_right_rate": float(1 - a_test.loss_c.mean()),
          "whole_test": {"old": a_test.metrics(allidx, a_test.lam_old),
                         "always_commit_eligible": a_test.metrics(allidx, -math.inf),
                         "never_commit": a_test.metrics(allidx, math.inf)},
          "splits": {}}
    th = m13.thresholds(a_fit, np.arange(len(a_fit.s)))
    th["old"] = a_test.lam_old
    ds["earlier_data"] = {k: {"threshold": m13.fnum(v), **a_test.metrics(allidx, v)} for k, v in th.items()}
    rng = np.random.default_rng(SEED)

    def run(label, make_split):
        per = {k: [] for k in ("old", "plugin", "crc", "crc_tune", "ltt")}
        lam = {k: [] for k in per}
        ncal = []
        for _ in range(CONFIG["reps"]):
            cal, tst = make_split()
            ncal.append(len(cal))
            for k, v in m13.thresholds(a_test, cal).items():
                per[k].append(a_test.metrics(tst, v))
                lam[k].append(v)
        ds["splits"][label] = {k: {**m13.summarise(per[k]), "threshold_median": m13.fnum(float(np.median(lam[k]))),
                                   "never_commit_share": float(np.mean(np.isinf(lam[k])))} for k in per}
        ds["splits"][label]["_n_cal_mean"] = float(np.mean(ncal))
        r = ds["splits"][label]
        log(f"splits {label}: " + "; ".join(f"{k} wc {v['wrong_commit']['mean']:.4f}/p95 {v['wrong_commit']['p95']:.4f} "
                                            f"eWPM {v['ewpm']['mean']:.3f}" for k, v in r.items() if not k.startswith("_")))

    for n_cal in CONFIG["n_cal"]:
        def mk(n_cal=n_cal):
            perm = rng.permutation(n)
            return perm[:n_cal], perm[n_cal:]
        run(f"random_{n_cal}", mk)
    for gname, g in (("sentence", sent), ("participant", part)):
        k = CONFIG["grouped_cal"][gname]
        ug = np.unique(g)

        def mkg(g=g, ug=ug, k=k):
            cg = rng.choice(ug, k, replace=False)
            m = np.isin(g, cg)
            return np.where(m)[0], np.where(~m)[0]
        run(f"grouped_{gname}_{k}of{len(ug)}", mkg)
    dump(ds, ctx["out"] / f"crc-splits-{ctx['name']}.json")


def stage_online(ctx: dict) -> None:
    m16 = load_module("m216", REPO / "experiments/2026-11-11-m2-16-online-recal/run.py")
    d = json.loads((ctx["out"] / f"items-meg-{ctx['name']}.json").read_text(encoding="utf-8"))
    fit, test = m16.Arr(d["fit"]), m16.Arr(d["test"])
    res = {"order": "test file order (participant by participant)", "n_fit": int(fit.s.size), "n_test": int(test.s.size),
           "drift": m16.protocol_drift(fit, test), "iid_reference": m16.iid_reference(test.s.size),
           "config": m16.CONFIG}
    dump(res, ctx["out"] / f"online-{ctx['name']}.json")
    for k, m in res["drift"]["online"].items():
        log(f"online {k}: wc {m['wrong_commit']:.4f} commit {m['commit_rate']:.3f} eWPM {m['ewpm']:.3f}")
    for k, m in res["drift"]["offline"].items():
        log(f"offline {k}: wc {m['wrong_commit']:.4f} commit {m['commit_rate']:.3f} eWPM {m['ewpm']:.3f}")


# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--streams", default="async", choices=list(CONFIG["streams"]))
    ap.add_argument("--stages", default="harness,null,items,splits,online")
    ap.add_argument("--no-sensitivity", action="store_true")
    a = ap.parse_args()
    st = a.stages.split(",")
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    Logger.path = out / f"run-{a.streams}.log"
    root = Path(CONFIG["streams"][a.streams])
    dec, kw = make_decoder()
    val_raw, test_raw = load_split(root, "val"), load_split(root, "test")
    val = [Item(s, r["target_text"]) for s, r in val_raw]
    test = [Item(s, r["target_text"]) for s, r in test_raw]
    sid = {t: i for i, t in enumerate(sorted({it.text for it in test}))}
    part_names = [r["participant"] for _, r in test_raw]
    ctx = {"name": a.streams, "root": root, "out": out, "dec": dec, "kw": kw, "val": val, "test": test,
           "test_raw": test_raw, "cache": {}, "sent": np.array([sid[it.text] for it in test]),
           "part": np.unique(part_names, return_inverse=True)[1], "part_names": part_names}
    need_pipes = any(s in st for s in ("null", "items"))
    if "harness" in st or need_pipes:
        stage_harness(ctx, sensitivity=("harness" in st and not a.no_sensitivity))
    if "null" in st:
        stage_null(ctx)
    if "items" in st:
        stage_items(ctx)
    if "splits" in st:
        stage_splits(ctx)
    if "online" in st:
        stage_online(ctx)
    log("done")


if __name__ == "__main__":
    main()
