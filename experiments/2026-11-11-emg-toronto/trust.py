"""Toronto sEMG: decoder tables + trust layer on composed sentences (CPU).

Stages (each writes JSON to results/):

1. ``decoder``: key accuracy of every trained run on its predict set; chance;
   zero-input and label-permuted controls.
2. ``trust``: per condition (``xsession``, ``calib``, ``xsubject``), compose
   sentences from held-out key presses, build NeuralTextStreams with the
   adapter, decode (CTC prefix beam + English char 6-gram), run the trust
   harness: always commit vs trust (plug-in fit) vs CRC vs LTT; gaze-only
   baseline; null audit (other sentence, frame shuffle, zeros input,
   label-permuted decoder); bootstrap CIs over sentences and participants.
3. ``tables``: results/tables.md.

Composed sentences (read this first). The dataset has isolated key presses
(5 x space, then 10 x one letter, metronome paced), not text. For each
participant and each sentence we take, per character, one real day-2 EMG
key press of that character and put the decoder's output for it in a
stream, one frame per character, 0.792 s apart (the median inter-key
interval of the data). Fit sentences use only presses of the first day-2
recording of each letter; test sentences only presses of the later ones.
Sentences: the 5,000 Tatoeba English sentences that were held out of the
char LM's training set (no LM leakage); fit and test texts are disjoint.

Run (repo root, CPU):
    .venv\\Scripts\\python.exe -I experiments/2026-11-11-emg-toronto/trust.py
    ... trust.py --stages tables
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "2"

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from fidetype.adapters import toronto_semg as T  # noqa: E402
from fidetype.eval.ewpm import summarize  # noqa: E402
from fidetype.eval.metrics import edit_distance  # noqa: E402

OUT = HERE / "results"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
CACHE = Path(CONFIG["cache"])
RUNS = Path(CONFIG["runs"])
SEED = CONFIG["seed"]
LOG = OUT / "run.log"
CONDITIONS = {
    # name: (fit-pool run, test-pool run, description)
    "xsession": ("xsession", "xsession", "decoder trained on day 1 of all 19 participants; day-2 presses"),
    "calib": ("calib_b", "calib_a", "day 1 + half of day 2 (cross-fitted: the other half is predicted)"),
    "xsubject": ("xsubject", "xsubject", "4-fold leave-participants-out; no data of the user"),
}


def log(*a) -> None:
    msg = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def dump(obj, path: Path) -> None:
    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (np.floating, float)):
            v = float(o)
            return None if math.isnan(v) or math.isinf(v) else v
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        return o

    path.write_text(json.dumps(clean(obj), indent=1), encoding="utf-8")


def load_meta():
    d = np.load(CACHE / "windows.npz", allow_pickle=False)
    files = json.loads((CACHE / "files.json").read_text(encoding="utf-8"))
    info = json.loads((CACHE / "info.json").read_text(encoding="utf-8"))
    return d["label"].astype(np.int64), d["file_idx"], files, info


def load_logits(run: str, n: int) -> tuple[np.ndarray, np.ndarray, dict]:
    """Logits for all windows that ``run`` predicted (NaN elsewhere). ``xsubject``
    merges the 4 folds. Returns (logits [n, 27], have [n], zero_logits by run)."""
    names = [f"xsubject_f{k}" for k in range(CONFIG["xsubject_folds"])] if run == "xsubject" else [run]
    lg = np.full((n, 27), np.nan, np.float32)
    zeros = {}
    for nm in names:
        p = np.load(RUNS / nm / "preds.npz", allow_pickle=False)
        lg[p["idx"]] = p["logits"]
        zeros[nm] = p["zero_logits"]
    return lg, ~np.isnan(lg[:, 0]), zeros


# ---------------------------------------------------------------------------
# Stage 1: decoder tables
# ---------------------------------------------------------------------------


def stage_decoder() -> dict:
    y, file_idx, files, info = load_meta()
    sess = np.array([files[i]["session"] for i in file_idx])
    part = np.array([files[i]["participant"] for i in file_idx])
    res: dict = {"n_windows": int(len(y)), "label_counts": info["label_counts"], "runs": {}}
    counts = np.bincount(y, minlength=27)
    res["chance"] = {"majority_space": float(counts[26] / counts.sum()), "uniform": 1 / 27, "letters_uniform": 1 / 26}
    runs = ["xsession", "xsession_linear", "xsession_permuted", "calib", "xsubject"]
    for r in runs:
        if r == "calib":
            la, ha, _ = load_logits("calib_a", len(y))
            lb, hb, _ = load_logits("calib_b", len(y))
            lg = np.where(ha[:, None], la, lb)
            have = ha | hb
        else:
            lg, have, _ = load_logits(r, len(y))
        m = have & (sess == "T2")
        pred = np.argmax(lg[m], axis=1)
        ok = pred == y[m]
        letters = y[m] < 26
        lp = lg[m] - np.logaddexp.reduce(lg[m].astype(np.float64), axis=1, keepdims=True)
        nll = float(-np.mean(lp[np.arange(m.sum()), y[m]]))
        bal = float(np.mean([ok[y[m] == c].mean() for c in range(27) if np.any(y[m] == c)]))
        pp = part[m]
        per = {p: float(ok[pp == p].mean()) for p in sorted(set(pp), key=lambda s: int(s[1:]))}
        top5 = float(np.mean([y[m][i] in np.argsort(-lg[m][i])[:5] for i in range(m.sum())]))
        res["runs"][r] = {"n": int(m.sum()), "acc": float(ok.mean()), "acc_letters": float(ok[letters].mean()),
                          "acc_space": float(ok[~letters].mean()), "balanced_acc": bal, "top5": top5, "nll": nll,
                          "acc_by_participant": per, "acc_participant_mean": float(np.mean(list(per.values()))),
                          "acc_participant_min": float(min(per.values())), "acc_participant_max": float(max(per.values()))}
        log(f"decoder {r}: T2 acc {ok.mean():.3f} letters {ok[letters].mean():.3f} space {ok[~letters].mean():.3f} "
            f"balanced {bal:.3f} top5 {top5:.3f} nll {nll:.3f} participants {min(per.values()):.3f}-{max(per.values()):.3f}")
    for r in ("xsession", "calib_a", "xsubject_f0"):
        z = np.load(RUNS / r / "preds.npz", allow_pickle=False)["zero_logits"]
        res.setdefault("zero_input", {})[r] = {"argmax": T.KEY_CHARS[int(np.argmax(z))],
                                               "p_max": float(np.exp(z.max() - np.logaddexp.reduce(z.astype(np.float64))))}
    summ = json.loads((RUNS / "summary.json").read_text()) if (RUNS / "summary.json").exists() else {}
    res["train_summary"] = summ
    dump(res, OUT / "decoder.json")
    return res


# ---------------------------------------------------------------------------
# Stage 2: trust
# ---------------------------------------------------------------------------


def sentences() -> list[str]:
    lo, hi = CONFIG["sentence_chars"]
    out, seen = [], set()
    for line in Path(CONFIG["heldout_sentences"]).read_text(encoding="utf-8").splitlines():
        s = " ".join(line.split())
        if lo <= len(s) <= hi and T.is_typeable(s) and len(s.split()) >= 2 and s not in seen:
            seen.add(s)
            out.append(s)
    rng = np.random.default_rng(SEED)
    return [out[i] for i in rng.permutation(len(out))]


def pools(y, file_idx, files):
    """{participant: {"fit": {char: [win idx]}, "test": {...}}} over day-2 windows."""
    out: dict = defaultdict(lambda: {"fit": defaultdict(list), "test": defaultdict(list)})
    for i, (lab, fi) in enumerate(zip(y, file_idx)):
        f = files[fi]
        if f["session"] != "T2":
            continue
        which = "fit" if f["order"] == 1 else "test"
        out[f["participant"]][which][T.KEY_CHARS[lab]].append(i)
    return out


def compose(texts, pool, rng, n_want):
    """Pick up to ``n_want`` texts whose characters all have presses in ``pool``;
    return [(text, [window idx per char])]."""
    out = []
    for t in texts:
        if len(out) >= n_want:
            break
        if any(len(pool.get(c, ())) == 0 for c in set(t)):
            continue
        used = defaultdict(set)
        idx = []
        for c in t:
            cand = [i for i in pool[c] if i not in used[c]] or pool[c]
            j = int(cand[rng.integers(len(cand))])
            used[c].add(j)
            idx.append(j)
        out.append((t, idx))
    return out


def gaze_ewpm(truths, cpm) -> float:
    t = sum(len(s) for s in truths) * 60.0 / cpm
    return 60.0 * sum(len(s.split()) for s in truths) / t


def bootstrap(per: dict[str, list], truths: list[str], clusters: np.ndarray | None, B_: int, seed: int, pairs) -> dict:
    rng = np.random.default_rng(seed)
    keys = ("ewpm", "wrong_commit_rate", "silent_error_rate", "rate_commit")
    samples = {p: defaultdict(list) for p in per}
    diffs = defaultdict(list)
    n = len(truths)
    uc = np.unique(clusters) if clusters is not None else None
    members = {c: np.where(clusters == c)[0] for c in uc} if uc is not None else None
    gz = CONFIG["gaze_chars_per_min"]
    for _ in range(B_):
        idx = rng.integers(0, n, n) if uc is None else np.concatenate([members[c] for c in rng.choice(uc, len(uc))])
        vals = {}
        for p, recs in per.items():
            m = summarize([recs[i] for i in idx])
            vals[p] = m
            for k in keys:
                samples[p][k].append(m[k])
        vals["gaze_only"] = {"ewpm": gaze_ewpm([truths[i] for i in idx], gz), "wrong_commit_rate": 0.0, "silent_error_rate": 0.0}
        for a, b in pairs:
            if a in vals and b in vals:
                for k in ("ewpm", "wrong_commit_rate", "silent_error_rate"):
                    diffs[f"{a}-{b}:{k}"].append(vals[a][k] - vals[b][k])

    def ci(v):
        v = np.array([x for x in v if x is not None and not (isinstance(x, float) and math.isnan(x))], float)
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size else None

    return {"policies": {p: {k: ci(v) for k, v in d.items()} for p, d in samples.items()},
            "diffs": {k: {"ci": ci(v), "p_le_0": float(np.mean(np.array(v) <= 0))} for k, v in diffs.items()}}


def make_stream(logits_rows: np.ndarray, period: float, subject: str, condition: str) -> "object":
    meta = T.stream_meta(subject=subject, session="T2", decoder_name=f"fidetype-emg-convnet-{condition}",
                         decoder_version="m6-07", personalized=condition != "xsubject", composed=True,
                         extra={"fidetype.timing": "composed: one real key-press window per character, fixed period"})
    ks = T.keypress_stream(logits_rows, T.compose_times(len(logits_rows), period), meta)
    return T.to_ctc_char_stream(ks)


def stage_trust(conditions: list[str], quick: bool) -> dict:
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig
    from fidetype.lm import CharNgramLM, ctc_prefix_beam_search
    from fidetype.trust.guard import auroc, shuffle_stream
    from fidetype.trust.policy import Action
    from fidetype.trust.testing import greedy_nbest
    from fidetype.trust.types import from_lm_hypotheses

    t0 = time.time()
    y, file_idx, files, info = load_meta()
    period = float(info["inter_key_interval_s"]["median"])
    cpm = 60.0 / period
    user = UserConfig.aac_gaze(chars_per_min=cpm)
    lm = CharNgramLM.load(CONFIG["char_lm"])
    texts = sentences()
    nfit, ntest = CONFIG["sentences_per_participant"]["fit"], CONFIG["sentences_per_participant"]["test"]
    if quick:
        nfit, ntest = 8, 8
    P = pools(y, file_idx, files)
    pids = sorted(P, key=lambda s: int(s[1:]))
    # Disjoint texts: participant k takes fit texts and test texts from separate slices.
    half = len(texts) // 2
    fit_texts, test_texts = texts[:half], texts[half:]
    per_p = len(fit_texts) // len(pids)
    rng = np.random.default_rng(SEED)
    plan = {}
    for k, p in enumerate(pids):
        plan[p] = {"fit": compose(fit_texts[k * per_p : (k + 1) * per_p], P[p]["fit"], rng, nfit),
                   "test": compose(test_texts[k * per_p : (k + 1) * per_p], P[p]["test"], rng, ntest)}
    n_fit = sum(len(v["fit"]) for v in plan.values())
    n_test = sum(len(v["test"]) for v in plan.values())
    assert not ({t for v in plan.values() for t, _ in v["fit"]} & {t for v in plan.values() for t, _ in v["test"]})
    log(f"trust: {len(texts)} held-out sentences usable; fit {n_fit}, test {n_test}; period {period:.3f} s, user {cpm:.1f} chars/min")
    mwc = CONFIG["max_wrong_commit"]
    res: dict = {"n_fit": n_fit, "n_test": n_test, "period_s": period, "user_chars_per_min": cpm,
                 "n_sentences_pool": len(texts), "conditions": {}}
    prev = OUT / ("trust_quick.json" if quick else "trust.json")
    if prev.exists():  # keep the conditions of an earlier call (same plan: same seed and config)
        old = json.loads(prev.read_text(encoding="utf-8"))
        if old.get("n_fit") == n_fit and old.get("n_test") == n_test:
            res["conditions"] = {k: v for k, v in old.get("conditions", {}).items() if k not in conditions}
    perm_lg, perm_have, _ = load_logits("xsession_permuted", len(y))
    for cond in conditions:
        fit_run, test_run, desc = CONDITIONS[cond]
        lg_fit, have_fit, zeros = load_logits(fit_run, len(y))
        lg_test, have_test, zeros_t = load_logits(test_run, len(y))
        zero_vec = next(iter(zeros_t.values()))

        def items_of(which, lg, have):
            its, meta = [], []
            for p in pids:
                for t, idx in plan[p][which]:
                    assert have[idx].all(), (cond, p, which)
                    its.append(Item(make_stream(lg[idx], period, p, cond), t))
                    meta.append((p, t, idx))
            return its, meta

        fit_items, _ = items_of("fit", lg_fit, have_fit)
        test_items, test_meta = items_of("test", lg_test, have_test)
        order = np.random.default_rng(SEED + 7).permutation(len(fit_items))
        fit_items = [fit_items[i] for i in order]  # mix participants before the A/B split
        A, Bv = fit_items[: len(fit_items) // 2], fit_items[len(fit_items) // 2 :]

        # LM weight: tune on fit half A only (CER of the top-1).
        tune = {}
        for w in CONFIG["lm_weights"]:
            kw = {**CONFIG["beam"], "lm_weight": w}
            tops = [ctc_prefix_beam_search(it.stream(0), lm, **kw) for it in A]
            tops = [" ".join(h[0].text.split()) if h else "" for h in tops]
            tune[w] = sum(edit_distance(it.text, h) for it, h in zip(A, tops)) / sum(len(it.text) for it in A)
        w_best = min(tune, key=tune.get)
        kw = {**CONFIG["beam"], "lm_weight": w_best}
        log(f"{cond}: LM weight CER on fit-A {tune} -> {w_best}")

        def decode_fn(s):
            return from_lm_hypotheses(ctc_prefix_beam_search(s, lm, **kw), s.meta, confidence_variant="frame")

        specs = {
            "a_greedy_commit": (greedy_nbest, dict(policy="always_commit", use_calibration=False)),
            "b_top1_commit": (decode_fn, dict(policy="always_commit")),
            "c_trust": (decode_fn, dict(max_wrong_commit=mwc)),
            "c_crc": (decode_fn, dict(max_wrong_commit=mwc, risk_control="crc")),
            "c_ltt": (decode_fn, dict(max_wrong_commit=mwc, risk_control="ltt", risk_control_delta=CONFIG["risk_control_delta"])),
            "d_trust_no_calib": (decode_fn, dict(max_wrong_commit=mwc, use_calibration=False)),
        }
        metrics, per, pipes = {}, {}, {}
        caches: dict = {}
        for name, (fn, cfg) in specs.items():
            ts = time.time()
            pipe = TrustPipeline(fn, HarnessConfig(seed=SEED, user_config=user, **cfg), caches.setdefault(getattr(fn, "__name__", "f"), {}))
            pipe.fit(A, Bv)
            m = pipe.evaluate(test_items)
            per[name] = m.pop("records")
            ans = [pipe.analyze(pipe.decode(it, 0)) for it in test_items]
            m["truth_in_nbest"] = float(np.mean([an.nbest.index_of(it.text) >= 0 for an, it in zip(ans, test_items)]))
            m["seconds"] = round(time.time() - ts, 1)
            metrics[name] = m
            pipes[name] = pipe
            log(f"{cond} {name}: eWPM {m['ewpm']:.2f} wrong-commit {m['wrong_commit_rate']:.3f} silent {m['silent_error_rate']:.3f} "
                f"CER {m['cer']:.3f} WER {m['wer']:.3f} exact {m['top1_sentence_acc']:.3f} in-nbest {m['truth_in_nbest']:.2f} "
                f"commit {m['rate_commit']:.2f} offer {m['rate_offer']:.2f} abstain {m['rate_abstain']:.2f} "
                f"rc {m.get('fit_risk_control_threshold')} ({m['seconds']}s)")
        truths = [it.text for it in test_items]
        clusters = np.array([p for p, _, _ in test_meta])
        pairs = [("c_trust", "b_top1_commit"), ("c_crc", "b_top1_commit"), ("c_ltt", "b_top1_commit"),
                 ("c_trust", "gaze_only"), ("c_crc", "gaze_only"), ("c_ltt", "gaze_only"), ("b_top1_commit", "gaze_only"),
                 ("c_crc", "c_trust"), ("c_ltt", "c_trust")]
        cr = {"description": desc, "fit_run": fit_run, "test_run": test_run, "lm_weight_tune": tune, "lm_weight": w_best,
              "policies": metrics, "gaze_only_ewpm": gaze_ewpm(truths, CONFIG["gaze_chars_per_min"]),
              "bootstrap_sentences": bootstrap(per, truths, None, CONFIG["bootstrap_B"], SEED, pairs),
              "bootstrap_participants": bootstrap(per, truths, clusters, CONFIG["bootstrap_B"], SEED + 1, pairs),
              "examples": [{"truth": t, "top1": (pipes["b_top1_commit"].decode(it, 0).texts or [""])[0]}
                           for it, t in list(zip(test_items, truths))[:12]]}
        # Null audit on a random subset of test sentences.
        arng = np.random.default_rng(SEED)
        na = min(len(test_items), CONFIG["audit_n"])
        aud = sorted(arng.choice(len(test_items), na, replace=False).tolist())
        base = [test_items[i].stream(0) for i in aud]
        aperm = arng.permutation(na)
        for i in range(na):  # the swapped stream must carry another sentence
            if truths[aud[aperm[i]]] == truths[aud[i]]:
                aperm[i], aperm[(i + 1) % na] = aperm[(i + 1) % na], aperm[i]
        zeros_rows = lambda n: np.repeat(zero_vec[None, :], n, axis=0)  # noqa: E731
        nulls = {
            "real": base,
            "other_sentence": [base[j] for j in aperm],
            "frame_shuffled": [shuffle_stream(s, arng) for s in base],
            "zeros_input": [make_stream(zeros_rows(len(test_meta[i][2])), period, test_meta[i][0], cond) for i in aud],
        }
        if perm_have[np.concatenate([test_meta[i][2] for i in aud])].all():
            nulls["permuted_label_decoder"] = [make_stream(perm_lg[test_meta[i][2]], period, test_meta[i][0], cond) for i in aud]
        audit: dict = {}
        for name in ("b_top1_commit", "c_trust", "c_crc", "c_ltt"):
            pipe = pipes[name]
            Tm = pipe.frame_scaler.temperature
            audit[name] = {}
            risk = {}
            for nc, ss in nulls.items():
                com, wrong = [], []
                for i, s in enumerate(ss):
                    s2 = pipe.frame_scaler.transform_stream(s) if Tm != 1.0 else s
                    nb = decode_fn(s2)
                    an = pipe.analyze(nb)
                    d = pipe.policy.decide(an.inputs, final_attempt=True)
                    c = d.action == Action.COMMIT
                    com.append(c)
                    wrong.append(c and (nb.top.text if nb.top is not None else "") != truths[aud[i]])
                    risk.setdefault(nc, []).append(an.inputs.p_top1)
                audit[name][nc] = {"commit_rate": float(np.mean(com)), "wrong_commit_rate": float(np.mean(wrong))}
            audit[name]["p_top1_auroc_real_vs_null"] = {
                nc: auroc(np.r_[risk["real"], risk[nc]], np.r_[np.ones(na), np.zeros(na)]) for nc in nulls if nc != "real"}
            log(f"{cond} audit {name}: " + " ".join(f"{nc} commit {v['commit_rate']:.2f}/wrong {v['wrong_commit_rate']:.2f}"
                                                     for nc, v in audit[name].items() if nc in nulls))
        cr["null_audit"] = audit
        cr["null_audit_n"] = na
        res["conditions"][cond] = cr
        dump(res, OUT / ("trust_quick.json" if quick else "trust.json"))
        # Save a few example streams outside the repo (derived data, no text in meta).
        ex = CACHE / "streams" / cond
        ex.mkdir(parents=True, exist_ok=True)
        for i in range(3):
            T.from_ctc_char_stream(test_items[i].stream(0)).to_npz(ex / f"test{i:02d}_key.npz")
            test_items[i].stream(0).to_npz(ex / f"test{i:02d}_ctc.npz")
    res["seconds"] = round(time.time() - t0, 1)
    dump(res, OUT / ("trust_quick.json" if quick else "trust.json"))
    return res


# ---------------------------------------------------------------------------
# Stage 3: tables
# ---------------------------------------------------------------------------


def f3(v, nd=3):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "-"
    return f"{v:.{nd}f}"


def ci_s(c, nd=2):
    return f"[{c[0]:.{nd}f}, {c[1]:.{nd}f}]" if c else ""


def stage_tables(quick: bool) -> None:
    L = ["# Toronto sEMG: generated tables", ""]
    dec = json.loads((OUT / "decoder.json").read_text(encoding="utf-8"))
    L += ["## Decoder (day-2 key presses, 27 classes)", "",
          f"Chance: majority (space) {dec['chance']['majority_space']:.3f}; uniform {dec['chance']['uniform']:.3f}.", "",
          "| run | n | acc | letters | space | balanced | top-5 | NLL | participant mean (min-max) |", "|---|---|---|---|---|---|---|---|---|"]
    for r, m in dec["runs"].items():
        L.append(f"| {r} | {m['n']} | {f3(m['acc'])} | {f3(m['acc_letters'])} | {f3(m['acc_space'])} | {f3(m['balanced_acc'])} | "
                 f"{f3(m['top5'])} | {f3(m['nll'])} | {f3(m['acc_participant_mean'])} ({f3(m['acc_participant_min'])}-{f3(m['acc_participant_max'])}) |")
    L += ["", "Zero input: " + "; ".join(f"{k}: argmax {v['argmax']!r} p {v['p_max']:.2f}" for k, v in dec.get("zero_input", {}).items()), ""]
    p = OUT / ("trust_quick.json" if quick else "trust.json")
    if p.exists():
        tr = json.loads(p.read_text(encoding="utf-8"))
        L += [f"## Trust harness (composed sentences; fit {tr['n_fit']}, test {tr['n_test']}; user {tr['user_chars_per_min']:.1f} chars/min)", ""]
        for cond, c in tr["conditions"].items():
            bs, bp = c["bootstrap_sentences"], c["bootstrap_participants"]
            L += [f"### {cond}: {c['description']}", "", f"LM weight {c['lm_weight']} (fit-A CER {c['lm_weight_tune']})", "",
                  "| policy | eWPM [sent] {participant} | wrong-commit [sent] | silent error | CER | WER | exact | truth in n-best | COMMIT / OFFER / ABSTAIN | CRC/LTT threshold (n) |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
            for name, m in c["policies"].items():
                thr = m.get("fit_risk_control_threshold")
                rc = f"{f3(thr)} ({m.get('fit_risk_control_n')}, feasible {m.get('fit_risk_control_feasible')})" if "fit_risk_control_method" in m else ""
                L.append(f"| {name} | {f3(m['ewpm'], 2)} {ci_s(bs['policies'][name]['ewpm'])} {{{ci_s(bp['policies'][name]['ewpm'])[1:-1]}}} | "
                         f"{f3(m['wrong_commit_rate'])} {ci_s(bs['policies'][name]['wrong_commit_rate'], 3)} | {f3(m['silent_error_rate'])} | "
                         f"{f3(m['cer'])} | {f3(m['wer'])} | {f3(m['top1_sentence_acc'])} | {f3(m['truth_in_nbest'], 2)} | "
                         f"{m['rate_commit']:.2f} / {m['rate_offer']:.2f} / {m['rate_abstain']:.2f} | {rc} |")
            L.append(f"| gaze typing only | {f3(c['gaze_only_ewpm'], 2)} | 0 | 0 | | | | | | |")
            L += ["", "Paired differences (sentence CI; participant CI):", ""]
            for k, v in bs["diffs"].items():
                L.append(f"- {k}: {ci_s(v['ci'], 3)}; {ci_s(bp['diffs'][k]['ci'], 3)}")
            L += ["", "Calibration (trust policy c_trust): " + ", ".join(
                f"{k} {f3(c['policies']['c_trust'].get(k))}" for k in ("fit_temperature_frame", "fit_temperature_sentence", "ece_sentence_before",
                                                                     "ece_sentence_after", "ece_char_before", "ece_char_after", "p_top1_auroc", "guard_auroc")), ""]
            L += ["Null audit (commit rate / wrong-commit rate):", "", "| policy | " + " | ".join(c["null_audit"]["c_trust"].keys() - {"p_top1_auroc_real_vs_null"}) + " |"]
            conds = [k for k in c["null_audit"]["c_trust"] if k != "p_top1_auroc_real_vs_null"]
            L[-1] = "| policy | " + " | ".join(conds) + " |"
            L.append("|---|" + "---|" * len(conds))
            for name, a in c["null_audit"].items():
                L.append(f"| {name} | " + " | ".join(f"{a[k]['commit_rate']:.2f} / {a[k]['wrong_commit_rate']:.2f}" for k in conds) + " |")
            L += ["", "Examples (truth -> always-commit top-1):", ""]
            L += [f"- `{e['truth']}` -> `{e['top1']}`" for e in c["examples"][:6]]
            L.append("")
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    log("tables written")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="decoder,trust,tables")
    ap.add_argument("--conditions", default="xsession,calib,xsubject")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    st = a.stages.split(",")
    if "decoder" in st:
        stage_decoder()
    if "trust" in st:
        stage_trust(a.conditions.split(","), a.quick)
    if "tables" in st:
        stage_tables(a.quick)


if __name__ == "__main__":
    main()
