"""M2-10: the trust core on real MEG decoder output (synchronous keystroke decoder).

Stages (each stage writes its results; a later run reuses them):

1. ``decoder``: cut the -0.2..+0.3 s key windows from the SpanishBCBL
   cache, fit per-subject logistic regression (and a shared MLP), pick
   the better model on val, build CTC-form NeuralTextStreams for every
   val/test trial, write them to ``STREAM_ROOT``, and score the decoder
   with two controls (shuffled MEG, permuted training labels).
2. ``lm``: CTC prefix beam + Spanish 6-gram LM, lm_weight sweep, pick on val.
3. ``trust``: the M2 harness (calibrate and fit the policy on val, report
   on test), policies a-e, bootstrap CIs, null-input audit.

Run (repo root, GPU env, detached; see config.json):

    C:\\venvs\\fidetype-rocm\\Scripts\\python.exe experiments/2026-11-08-m2-real-keystroke/run.py
    ... run.py --stages lm,trust      # reuse the decoder stage
    ... run.py --redo                 # ignore saved stage results

**Setting.** Oracle key timing (Brain2Qwerty v1 synchronous setting),
not a real-time device setting.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import argparse
import bz2
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from fidetype.data.preprocess import load_cached_block
from fidetype.decoders.keystroke import (
    N_CLASSES,
    KeyTrial,
    LogRegDecoder,
    fit_logreg_cv,
    greedy_keys,
    keystroke_stream,
    stream_meta,
    trials_from_segments,
)
from fidetype.eval.ewpm import summarize
from fidetype.eval.metrics import edit_distance
from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import normalize_text

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
CACHE = Path(CONFIG["cache"])
STREAM_ROOT = Path(CONFIG["stream_root"])
SEED = CONFIG["seed"]


def log(*a) -> None:
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def dump(obj, path: Path) -> None:
    def default(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)

    def clean(o):
        if isinstance(o, float) and not math.isfinite(o):
            return None if math.isnan(o) else str(o)
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        return o

    path.write_text(json.dumps(clean(obj), indent=1, default=default), encoding="utf-8")


def norm_spaces(t: str) -> str:
    return " ".join(t.split())


def pooled_rate(refs, hyps, words=False) -> float:
    if words:
        refs, hyps = [r.split() for r in refs], [h.split() for h in hyps]
    n = sum(len(r) for r in refs)
    return sum(edit_distance(r, h) for r, h in zip(refs, hyps)) / n if n else math.nan


# ---------------------------------------------------------------------------
# Stage 1: decoder
# ---------------------------------------------------------------------------


def discover_blocks() -> dict[str, list[dict]]:
    idx = json.loads((CACHE / "_index.json").read_text(encoding="utf-8"))
    subs: dict[str, list[dict]] = defaultdict(list)
    for b in idx["blocks"]:
        p = CACHE / b["npz"]
        if p.exists() and p.with_suffix(".json").exists():
            subs[b["subject"]].append(b)
    return dict(sorted(subs.items(), key=lambda kv: int(kv[0][1:])))


def load_trials(blocks: dict[str, list[dict]]) -> dict[str, list[KeyTrial]]:
    out = {}
    for s, bl in blocks.items():
        trials = []
        for b in bl:
            blk = load_cached_block(CACHE / b["npz"])
            trials += trials_from_segments(blk.data, blk.sfreq, blk.sidecar, tuple(CONFIG["window_s"]), CONFIG["n_bins"])
            del blk
        out[s] = trials
        log(f"loaded {s}: {len(trials)} trials, {sum(t.n_keys for t in trials)} keys")
    return out


def stack(trials: list[KeyTrial]):
    X = np.concatenate([t.features for t in trials])
    y = np.concatenate([t.labels for t in trials])
    g = np.concatenate([np.full(t.n_keys, i) for i, t in enumerate(trials)])
    return X, y, g


def derangement_partner(trials: list[KeyTrial], rng: np.random.Generator) -> list[int]:
    """For each trial, another trial of the same group with a different target text."""
    n = len(trials)
    for _ in range(200):
        p = rng.permutation(n)
        if n < 2 or all(p[i] != i and trials[p[i]].target_text != trials[i].target_text for i in range(n)):
            return p.tolist()
    return [(i + 1) % n for i in range(n)]


def stage_decoder() -> dict:
    t0 = time.time()
    blocks = discover_blocks()
    trials = load_trials(blocks)
    rng = np.random.default_rng(SEED)
    train = {s: [t for t in ts if t.split == "train" and not t.is_training and t.n_keys] for s, ts in trials.items()}
    evals = {s: [t for t in ts if t.split in ("val", "test") and not t.is_training and t.n_keys] for s, ts in trials.items()}
    info: dict = {"blocks": {s: [b["npz"] for b in bl] for s, bl in blocks.items()}, "subjects": {}}

    preds: dict[str, dict[str, np.ndarray]] = defaultdict(dict)  # kind -> trial_id -> (n, 27)
    lr_models: dict[str, LogRegDecoder] = {}
    for s in trials:
        X, y, g = stack(train[s])
        ts = time.time()
        dec, cv = fit_logreg_cv(X, y, g, lams=CONFIG["lr_lams"], n_folds=3, seed=SEED)
        lr_models[s] = dec
        # Control (b): the same model, trained on permuted labels.
        dperm = LogRegDecoder(lam=cv["lam"]).fit(X, rng.permutation(y))
        for t in evals[s]:
            preds["lr"][t.trial_id] = dec.predict_log_proba(t.features)
            preds["lr_perm"][t.trial_id] = dperm.predict_log_proba(t.features)
        counts = np.bincount(y, minlength=N_CLASSES)
        info["subjects"][s] = {
            "n_train_trials": len(train[s]),
            "n_train_keys": int(len(y)),
            "n_val_trials": sum(t.split == "val" for t in evals[s]),
            "n_test_trials": sum(t.split == "test" for t in evals[s]),
            "n_is_training_trials_dropped": sum(t.is_training for t in trials[s]),
            "lr_lam": cv["lam"],
            "lr_cv": cv["cv"],
            "lr_components": dec.info["n_components"],
            "train_majority_share": float(counts.max() / counts.sum()),
            "fit_s": round(time.time() - ts, 1),
        }
        log(f"LR {s}: lam={cv['lam']} cv_acc={cv['cv'][str(cv['lam'])]['acc']:.3f} ({time.time() - ts:.0f}s)")
        del X, y, g

    # Optional shared MLP with a subject embedding.
    if CONFIG["mlp"]["enabled"]:
        try:
            import torch

            torch.set_num_threads(4)
            from fidetype.decoders.keystroke import SharedMLPDecoder

            dev = "cuda" if torch.cuda.is_available() else "cpu"
            hp = {k: v for k, v in CONFIG["mlp"].items() if k != "enabled"}
            data = {s: stack(train[s]) for s in trials}
            nf = next(iter(data.values()))[0].shape[1]
            for kind, perm in (("mlp", False), ("mlp_perm", True)):
                d2 = {s: (X, rng.permutation(y) if perm else y, g) for s, (X, y, g) in data.items()}
                ts = time.time()
                m = SharedMLPDecoder(nf, list(trials), device=dev, seed=SEED, **hp).fit(d2)
                for s in trials:
                    for t in evals[s]:
                        preds[kind][t.trial_id] = m.predict_log_proba(s, t.features)
                info[kind] = {"best_epoch": m.best_epoch, "history": m.history, "device": dev, "fit_s": round(time.time() - ts, 1)}
                log(f"{kind}: best epoch {m.best_epoch}, holdout acc {m.history[m.best_epoch]['holdout_acc']:.3f} ({time.time() - ts:.0f}s)")
                if not perm:
                    mlp_model = m
            del data
        except Exception as e:  # pragma: no cover - logged and reported
            info["mlp_error"] = repr(e)
            log("MLP failed:", repr(e))

    # Pick the model on val (pooled key accuracy).
    allev = [t for s in trials for t in evals[s]]
    val = [t for t in allev if t.split == "val"]

    def acc(kind, ts):
        n = sum(t.n_keys for t in ts)
        return sum(int((preds[kind][t.trial_id].argmax(1) == t.labels).sum()) for t in ts) / n

    def nll(kind, ts):
        n = sum(t.n_keys for t in ts)
        return -sum(float(preds[kind][t.trial_id][np.arange(t.n_keys), t.labels].sum()) for t in ts) / n

    cands = [k for k in ("lr", "mlp") if k in preds]
    sel = {k: {"val_acc": acc(k, val), "val_nll": nll(k, val)} for k in cands}
    chosen = max(cands, key=lambda k: (sel[k]["val_acc"], -sel[k]["val_nll"]))
    info["model_selection"] = sel
    info["chosen_model"] = chosen
    log("model selection", sel, "->", chosen)

    # Control (a): shuffled MEG = the key windows of another trial (same subject, same split).
    for s in trials:
        for split in ("val", "test"):
            grp = [t for t in evals[s] if t.split == split]
            part = derangement_partner(grp, rng)
            for t, j in zip(grp, part):
                o = grp[j]
                feats = o.features[np.arange(t.n_keys) % o.n_keys]
                if chosen == "lr":
                    lp = lr_models[s].predict_log_proba(feats)
                else:
                    lp = mlp_model.predict_log_proba(s, feats)
                preds["shuffled_meg"][t.trial_id] = lp
    preds["real"] = preds[chosen]
    preds["perm_label"] = preds[chosen + "_perm"]

    # Save predictions and trial info (labels stay out of the streams).
    OUT.mkdir(exist_ok=True)
    arrays = {f"{k}__{tid}": v.astype(np.float32) for k, d in preds.items() for tid, v in d.items()}
    np.savez_compressed(OUT / "predictions.npz", **arrays)
    tinfo = [
        {
            "trial_id": t.trial_id, "subject": t.subject, "session": t.session, "block": t.block,
            "trial_idx": t.trial_idx, "split": t.split, "target_text": t.target_text, "typed_text": t.typed_text,
            "typed_keys": t.typed_keys, "labels": t.labels.tolist(), "key_times": t.key_times.tolist(),
        }
        for t in allev
    ]
    dump(tinfo, OUT / "trials.json")
    write_streams(tinfo, preds["real"], info)
    info["decoder_metrics"] = decoder_metrics(tinfo, preds)
    info["seconds"] = round(time.time() - t0, 1)
    dump(info, OUT / "decoder.json")
    return info


def make_stream(t: dict, lp: np.ndarray, extra: dict | None = None) -> NeuralTextStream:
    meta = stream_meta(t["subject"], t["session"], {"fidetype.trial_id": t["trial_id"], **(extra or {})})
    return keystroke_stream(lp, np.asarray(t["key_times"]), meta, CONFIG["key_blank"], CONFIG["gap_nonblank"])


def write_streams(tinfo: list[dict], lp: dict[str, np.ndarray], info: dict) -> None:
    STREAM_ROOT.mkdir(parents=True, exist_ok=True)
    for split in ("val", "test"):
        lab = []
        for t in tinfo:
            if t["split"] != split:
                continue
            rel = Path(split) / t["subject"] / f"{t['session']}_{t['block']}_t{t['trial_idx']:03d}.npz"
            (STREAM_ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
            make_stream(t, lp[t["trial_id"]], {"decoder.version": info["chosen_model"]}).to_npz(STREAM_ROOT / rel)
            lab.append({"stream": rel.as_posix(), "trial_id": t["trial_id"], "target_text": t["target_text"],
                        "typed_text": t["typed_text"], "typed_keys": t["typed_keys"]})
        (STREAM_ROOT / split / "labels.jsonl").write_text("\n".join(json.dumps(r) for r in lab) + "\n", encoding="utf-8")
    manifest = {
        "description": "Synchronous keystroke decoder streams (oracle key timing). Not a real-time setting.",
        "decoder": "fidetype.decoders.keystroke", "chosen_model": info["chosen_model"],
        "experiment": "experiments/2026-11-08-m2-real-keystroke", "spec": "NeuralTextStream v0.1",
        "frames": "key, blank, key, ... (one key frame per key press; blank frames at midpoints)",
        "labels": "<split>/labels.jsonl (kept apart from the streams)", "config": CONFIG,
    }
    dump(manifest, STREAM_ROOT / "manifest.json")


def decoder_metrics(tinfo: list[dict], preds: dict) -> dict:
    out: dict = {}
    for kind in [k for k in ("real", "shuffled_meg", "perm_label", "lr", "mlp", "lr_perm", "mlp_perm") if k in preds]:
        out[kind] = {}
        for split in ("val", "test"):
            ts = [t for t in tinfo if t["split"] == split]
            groups = {"all": ts}
            for t in ts:
                groups.setdefault(t["subject"], []).append(t)
            res = {}
            for gname, g in groups.items():
                n = sum(len(t["labels"]) for t in g)
                corr = sum(int((preds[kind][t["trial_id"]].argmax(1) == np.array(t["labels"])).sum()) for t in g)
                greedy = [norm_spaces(greedy_keys(make_stream(t, preds[kind][t["trial_id"]]))) for t in g]
                res[gname] = {
                    "n_trials": len(g),
                    "n_keys": n,
                    "key_acc": corr / n,
                    "greedy_cer_typed": pooled_rate([t["typed_text"] for t in g], greedy),
                    "greedy_cer_target": pooled_rate([t["target_text"] for t in g], greedy),
                    "greedy_wer_target": pooled_rate([t["target_text"] for t in g], greedy, words=True),
                    "greedy_cer_typed_keys": pooled_rate([norm_spaces(t["typed_keys"]) for t in g], greedy),
                }
            out[kind][split] = res
    # Chance levels: majority class and per-key prior of the eval keys.
    for split in ("val", "test"):
        lab = np.concatenate([t["labels"] for t in tinfo if t["split"] == split])
        out.setdefault("chance", {})[split] = float(np.bincount(lab, minlength=N_CLASSES).max() / len(lab))
    return out


# ---------------------------------------------------------------------------
# Stage 2: LM beam
# ---------------------------------------------------------------------------


def load_streams(kind: str = "real") -> tuple[list[dict], dict[str, NeuralTextStream]]:
    tinfo = json.loads((OUT / "trials.json").read_text(encoding="utf-8"))
    with np.load(OUT / "predictions.npz") as z:
        streams = {t["trial_id"]: make_stream(t, z[f"{kind}__{t['trial_id']}"].astype(np.float64)) for t in tinfo}
    return tinfo, streams


def beam_settings() -> dict[str, dict]:
    from fidetype.lm import beam as beam_mod

    out = {"default": {}}
    ret = getattr(beam_mod, "RETUNED", None)
    if ret is not None and CONFIG["try_retuned_beam"]:
        out["retuned"] = dict(ret)
    return out


def stage_lm() -> dict:
    """lm_weight sweep. Rows: the old beam defaults and RETUNED on raw streams
    (baselines), and RETUNED (n_best = trust n_best) on frame-calibrated
    streams (frame T fitted on val, as the harness does). The trust stage
    uses the best calibrated RETUNED row on val."""
    from fidetype.lm import CharNgramLM, ctc_prefix_beam_search
    from fidetype.trust.calibration import fit_frame_temperature

    t0 = time.time()
    lm = CharNgramLM.load(CONFIG["lm"])
    tinfo, streams = load_streams("real")
    val_t = [t for t in tinfo if t["split"] == "val"]
    scaler = fit_frame_temperature([streams[t["trial_id"]] for t in val_t], [t["target_text"] for t in val_t])
    cal_streams = {k: scaler.transform_stream(v) for k, v in streams.items()}
    settings = beam_settings()
    if "retuned" in settings:
        settings["retuned_calT"] = {**settings["retuned"], "n_best": CONFIG["trust_n_best"]}
    res: dict = {"settings": settings, "frame_temperature_val": scaler.temperature, "results": {}}
    for sname, kw in settings.items():
        src = cal_streams if sname.endswith("_calT") else streams
        for w in CONFIG["lm_weights"]:
            key = f"{sname}/w={w}"
            r = {}
            for split in ("val", "test"):
                ts = [t for t in tinfo if t["split"] == split]
                tops, inn, in3 = [], [], []
                for t in ts:
                    h = ctc_prefix_beam_search(src[t["trial_id"]], lm, **{**kw, "lm_weight": w})
                    texts = [norm_spaces(x.text) for x in h]
                    tops.append(texts[0] if texts else "")
                    inn.append(t["target_text"] in texts)
                    in3.append(t["target_text"] in texts[:3])
                tg = [t["target_text"] for t in ts]
                r[split] = {
                    "cer_target": pooled_rate(tg, tops), "wer_target": pooled_rate(tg, tops, words=True),
                    "cer_typed": pooled_rate([t["typed_text"] for t in ts], tops),
                    "sentence_acc": float(np.mean([a == b for a, b in zip(tg, tops)])),
                    "target_in_nbest": float(np.mean(inn)), "target_in_top3": float(np.mean(in3)),
                }
                if split == "test":
                    r["test_examples"] = [{"target": a, "top1": b} for a, b in list(zip(tg, tops))[:12]]
            res["results"][key] = r
            log(f"LM {key}: val CER {r['val']['cer_target']:.3f} WER {r['val']['wer_target']:.3f} | "
                f"test CER {r['test']['cer_target']:.3f} WER {r['test']['wer_target']:.3f} in-nbest {r['test']['target_in_nbest']:.2f}")
    keys = list(res["results"])
    pick = lambda ks: min(ks, key=lambda k: (res["results"][k]["val"]["cer_target"], res["results"][k]["val"]["wer_target"]))  # noqa: E731
    pool = [k for k in keys if k.startswith("retuned_calT/")] or keys
    best = pick(pool)
    res["best_on_val"] = best
    res["best_default_on_val"] = pick([k for k in keys if k.startswith("default/")])
    if any(k.startswith("retuned/") for k in keys):
        res["best_retuned_raw_on_val"] = pick([k for k in keys if k.startswith("retuned/")])
    sname, w = best.split("/w=")
    res["chosen_kwargs"] = {**res["settings"][sname], "lm_weight": float(w)}
    res["seconds"] = round(time.time() - t0, 1)
    dump(res, OUT / "lm.json")
    log("LM best on val:", best, res["chosen_kwargs"])
    return res


# ---------------------------------------------------------------------------
# Stage 3: trust pipeline
# ---------------------------------------------------------------------------


def spanish_lexicon() -> set[str]:
    words: set[str] = set()
    with bz2.open(CONFIG["lexicon_corpus"], "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if parts:
                words.update(normalize_text(parts[-1]).split())
    return words


def bootstrap(per_policy: dict[str, dict], n_items: int, clusters: np.ndarray | None, B: int, seed: int) -> dict:
    """Percentile 95% CIs. Resample trials (or clusters of trials) with replacement."""
    rng = np.random.default_rng(seed)
    keys = ("ewpm", "wrong_commit_rate", "silent_error_rate", "communicated_rate", "committed_cer", "rate_commit",
            "abstain_rate")
    samples: dict[str, dict[str, list]] = {p: defaultdict(list) for p in per_policy}
    diffs: dict[str, list] = defaultdict(list)
    uc = np.unique(clusters) if clusters is not None else None
    members = {c: np.where(clusters == c)[0] for c in uc} if uc is not None else None
    for _ in range(B):
        if uc is None:
            idx = rng.integers(0, n_items, n_items)
        else:
            idx = np.concatenate([members[c] for c in rng.choice(uc, len(uc))])
        vals = {}
        for p, d in per_policy.items():
            recs = [d["records"][i] for i in idx]
            m = summarize(recs)
            m["top1_cer"] = sum(d["top1_ed"][i] for i in idx) / sum(d["n_chars"][i] for i in idx)
            m["top1_wer"] = sum(d["top1_wed"][i] for i in idx) / sum(d["n_words"][i] for i in idx)
            for k in keys + ("top1_cer", "top1_wer"):
                samples[p][k].append(m[k])
            vals[p] = m
        for a, b in (("c_trust", "b_top1_commit"), ("c_trust", "a_greedy_commit"), ("b_top1_commit", "a_greedy_commit")):
            if a in vals and b in vals:
                for k in ("ewpm", "wrong_commit_rate", "silent_error_rate"):
                    diffs[f"{a}-{b}:{k}"].append(vals[a][k] - vals[b][k])

    def ci(v):
        v = np.array([x for x in v if x is not None and not (isinstance(x, float) and math.isnan(x))], dtype=float)
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size else None

    return {
        "policies": {p: {k: ci(v) for k, v in d.items()} for p, d in samples.items()},
        "diffs": {k: {"ci": ci(v), "p_le_0": float(np.mean(np.array(v) <= 0))} for k, v in diffs.items()},
    }


def word_align(ref: list[str], hyp: list[str]) -> list[tuple[int, int]]:
    """Levenshtein alignment of two word lists: (ref index, hyp index) of aligned pairs."""
    n, m = len(ref), len(hyp)
    D = np.zeros((n + 1, m + 1), dtype=np.int64)
    D[:, 0] = np.arange(n + 1)
    D[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = min(D[i - 1, j] + 1, D[i, j - 1] + 1, D[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]))
    i, j, out = n, m, []
    while i > 0 and j > 0:
        if D[i, j] == D[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]):
            out.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif D[i, j] == D[i - 1, j] + 1:
            i -= 1
        else:
            j -= 1
    return out[::-1]


def signal_aurocs(ans, truths, tops, auroc) -> dict:
    """AUROC of each guard signal for 'top-1 CER above the test median'.

    The usual target (top-1 sentence wrong) has one class only when no
    top-1 is exactly right, so the harness AUROCs are then undefined.
    """
    cer = np.array([edit_distance(t, h) / max(1, len(t)) for t, h in zip(truths, tops)])
    bad = cer > np.median(cer)
    sigs = {
        "risk": [a.guard.risk for a in ans],
        "inconsistency": [1 - a.guard.consistency for a in ans],
        "neg_p_top1": [-a.inputs.p_top1 for a in ans],
        "low_evidence": [a.guard.low_evidence_frac for a in ans],
    }
    out = {f"auroc_highcer_{k}": auroc(v, bad) for k, v in sigs.items()}
    for k, v in sigs.items():  # Spearman rank correlation with the top-1 CER
        r1, r2 = np.argsort(np.argsort(v)), np.argsort(np.argsort(cer))
        out[f"spearman_cer_{k}"] = float(np.corrcoef(r1, r2)[0, 1])
    out["median_top1_cer"] = float(np.median(cer))
    return out


def word_alt_metrics(ans, truths, word_alternatives) -> dict:
    """Share of true words found: top-1 word, top-3 per-word slot, best of the top-3 sentences."""
    n = hit1 = hit_slot = hit_sent = 0
    for an, truth in zip(ans, truths):
        nb = an.nbest
        tw = truth.split()
        n += len(tw)
        if not len(nb):
            continue
        top = nb.texts[0].split()
        pairs = dict(word_align(tw, top))
        slots = word_alternatives(nb.candidates, posteriors=an.posteriors, max_alternatives=3)
        for i, w in enumerate(tw):
            j = pairs.get(i)
            if j is not None and top[j] == w:
                hit1 += 1
            if j is not None and j < len(slots) and w in [a for a, _ in slots[j].alternatives[:3]]:
                hit_slot += 1
        best = 0
        for t in nb.texts[:3]:
            hw = t.split()
            best = max(best, sum(hw[j] == tw[i] for i, j in word_align(tw, hw)))
        hit_sent += best
    return {"word_top1_recall": hit1 / n, "word_slot_top3_recall": hit_slot / n,
            "word_best_of_top3_sentences_recall": hit_sent / n}


def stage_trust(lm_res: dict) -> dict:
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.lm import CharNgramLM, ctc_prefix_beam_search
    from fidetype.lm import word_alternatives
    from fidetype.trust.guard import GuardConfig, auroc, lexicon_fluency, shuffle_stream, uniform_stream
    from fidetype.trust.policy import Action
    from fidetype.trust.testing import greedy_nbest
    from fidetype.trust.types import from_lm_hypotheses

    t0 = time.time()
    lm = CharNgramLM.load(CONFIG["lm"])
    kw = {**lm_res["chosen_kwargs"], "n_best": CONFIG["trust_n_best"]}

    def decode_fn(s: NeuralTextStream):
        return from_lm_hypotheses(ctc_prefix_beam_search(s, lm, **kw), s.meta, confidence_variant="frame")

    tinfo, streams = load_streams("real")
    _, shuf_streams = load_streams("shuffled_meg")
    val_t = [t for t in tinfo if t["split"] == "val"]
    test_t = [t for t in tinfo if t["split"] == "test"]
    val_items = [Item(streams[t["trial_id"]], t["target_text"]) for t in val_t]
    test_items = [Item(streams[t["trial_id"]], t["target_text"]) for t in test_t]
    mwc = CONFIG["max_wrong_commit"]
    specs = {
        "a_greedy_commit": (greedy_nbest, dict(policy="always_commit", use_calibration=False)),
        # Frame calibration before the beam for every LM policy except the ablations.
        "b_top1_commit": (decode_fn, dict(policy="always_commit")),
        "b0_top1_commit_uncal": (decode_fn, dict(policy="always_commit", use_calibration=False)),
        "c_trust": (decode_fn, dict(max_wrong_commit=mwc)),
        "d_trust_no_calib": (decode_fn, dict(max_wrong_commit=mwc, use_calibration=False)),
        "e_trust_no_guard": (decode_fn, dict(max_wrong_commit=mwc, use_guard=False)),
        # (f): guard risk = 1 - n-best consistency only (no evidence term); the policy also gates on p_top1.
        "f_trust_consistency_ptop1": (decode_fn, dict(max_wrong_commit=mwc, guard_config=GuardConfig(w_evidence=0.0))),
    }
    for lim in CONFIG["pareto_limits"]:
        specs[f"pareto_trust_{lim}"] = (decode_fn, dict(max_wrong_commit=lim))
    cache_lm: dict = {}
    pipes, metrics, per = {}, {}, {}
    for name, (fn, cfg) in specs.items():
        ts = time.time()
        pipe = TrustPipeline(fn, HarnessConfig(seed=SEED, **cfg), {} if fn is greedy_nbest else cache_lm)
        pipe.fit(val_items, val_items)  # calibrate and fit the policy on val
        m = pipe.evaluate(test_items)
        recs = m.pop("records")
        tops, ans = [], []
        for it in test_items:
            an = pipe.analyze(pipe.decode(it, 0))
            ans.append(an)
            tops.append(an.nbest.texts[0] if len(an.nbest) else "")
        truths = [it.text for it in test_items]
        if fn is not greedy_nbest:
            m.update(signal_aurocs(ans, truths, tops, auroc))
            if name in ("c_trust", "b_top1_commit"):
                m.update(word_alt_metrics(ans, truths, word_alternatives))
        per[name] = {
            "records": recs,
            "top1_ed": [edit_distance(a, b) for a, b in zip(truths, tops)],
            "top1_wed": [edit_distance(a.split(), b.split()) for a, b in zip(truths, tops)],
            "n_chars": [len(a) for a in truths],
            "n_words": [len(a.split()) for a in truths],
        }
        com = [r for r in recs if r.committed_text is not None]
        nw = sum(len(r.truth.split()) for r in com)
        m["committed_wer"] = sum(edit_distance(r.truth.split(), r.committed_text.split()) for r in com) / nw if nw else math.nan
        m["top1_cer_check"] = sum(per[name]["top1_ed"]) / sum(per[name]["n_chars"])
        m["seconds"] = round(time.time() - ts, 1)
        metrics[name] = m
        pipes[name] = pipe
        log(f"{name}: eWPM {m['ewpm']:.2f} wrong-commit {m['wrong_commit_rate']:.3f} CER {m['cer']:.3f} "
            f"commit {m['rate_commit']:.2f} offer {m['rate_offer']:.2f} abstain {m['rate_abstain']:.2f} ({m['seconds']}s)")

    core = ["a_greedy_commit", "b_top1_commit", "b0_top1_commit_uncal", "c_trust", "d_trust_no_calib",
            "e_trust_no_guard", "f_trust_consistency_ptop1"]
    sid = {t: i for i, t in enumerate(sorted({it.text for it in test_items}))}
    sent = np.array([sid[it.text] for it in test_items])
    boot_trial = bootstrap({p: per[p] for p in core}, len(test_items), None, CONFIG["bootstrap_B"], SEED)
    boot_sent = bootstrap({p: per[p] for p in core}, len(test_items), sent, CONFIG["bootstrap_B"], SEED + 1)
    log("bootstrap done")

    # Null-input audit: the same null streams for every policy.
    lex = spanish_lexicon()
    fluent = lexicon_fluency(lex)
    rng = np.random.default_rng(SEED)
    base = [streams[t["trial_id"]] for t in test_t]
    null_inputs = {
        "real": base,
        "shuffled_meg": [shuf_streams[t["trial_id"]] for t in test_t],
        "frame_shuffled": [shuffle_stream(s, rng) for s in base],
        "uniform": [uniform_stream(s, rng, 0.05) for s in base],
    }
    dcache: dict = {}
    audit: dict = {}
    for name in core:
        pipe = pipes[name]
        T = pipe.frame_scaler.temperature
        audit[name] = {}
        sig: dict[str, list] = {}
        for cond, ss in null_inputs.items():
            fl, acc, fa, nonempty, chars = [], [], [], [], []
            for i, s in enumerate(ss):
                key = (pipe.decode_fn is greedy_nbest, cond, i, round(T, 9))
                nb = dcache.get(key)
                if nb is None:
                    s2 = pipe.frame_scaler.transform_stream(s) if T != 1.0 else s
                    nb = pipe.decode_fn(s2)
                    dcache[key] = nb
                top = nb.top.text if nb.top is not None else ""
                an = pipe.analyze(nb)
                d = pipe.policy.decide(an.inputs, final_attempt=True)
                sig.setdefault(cond, []).append((an.guard.risk, 1 - an.guard.consistency, -an.inputs.p_top1,
                                                 an.guard.low_evidence_frac))
                f = fluent(top)
                a = d.action == Action.COMMIT
                fl.append(f)
                acc.append(a)
                fa.append(a and f)
                nonempty.append(bool(top))
                chars.append(len(top))
            audit[name][cond] = {
                "fluent_rate": float(np.mean(fl)), "commit_rate": float(np.mean(acc)),
                "fluent_commit_rate": float(np.mean(fa)), "nonempty_rate": float(np.mean(nonempty)),
                "mean_chars": float(np.mean(chars)),
            }
        if name != "a_greedy_commit":
            real = np.array(sig["real"])
            audit[name]["null_vs_real_auroc"] = {
                cond: {lab: auroc(np.r_[np.array(v)[:, j], real[:, j]], np.r_[np.ones(len(v)), np.zeros(len(real))])
                       for j, lab in enumerate(("risk", "inconsistency", "neg_p_top1", "low_evidence"))}
                for cond, v in sig.items() if cond != "real"
            }
        log(f"audit {name}: " + " ".join(f"{c}={v['fluent_commit_rate']:.2f}" for c, v in audit[name].items() if c in null_inputs))

    # Per-subject breakdown of the main policies (test).
    by_subj: dict = {}
    for name in ("b_top1_commit", "c_trust"):
        recs = per[name]["records"]
        for s in sorted({t["subject"] for t in test_t}, key=lambda x: int(x[1:])):
            idx = [i for i, t in enumerate(test_t) if t["subject"] == s]
            m = summarize([recs[i] for i in idx])
            by_subj.setdefault(s, {"n": len(idx)})[name] = {k: m[k] for k in ("ewpm", "wrong_commit_rate", "rate_commit")}

    res = {
        "n_val": len(val_items), "n_test": len(test_items),
        "n_test_sentences": len({it.text for it in test_items}), "n_val_sentences": len({it.text for it in val_items}),
        "decode_kwargs": kw,
        "policies": metrics,
        "bootstrap_trials": boot_trial,
        "bootstrap_sentences": boot_sent,
        "null_audit": audit,
        "lexicon_size": len(lex),
        "per_subject": by_subj,
        "seconds": round(time.time() - t0, 1),
    }
    dump(res, OUT / "trust.json")
    return res


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def f3(v, nd=3):
    if v is None:
        return "-"
    if isinstance(v, str):
        return v
    if isinstance(v, float) and math.isnan(v):
        return "-"
    return f"{v:.{nd}f}"


def write_tables() -> None:
    L = ["# M2-10 real keystroke decoder: generated tables (run.py)", ""]
    dec = json.loads((OUT / "decoder.json").read_text(encoding="utf-8")) if (OUT / "decoder.json").exists() else None
    if dec:
        dm = dec["decoder_metrics"]
        L += [f"Chosen model: **{dec['chosen_model']}**. Model selection (val): `{json.dumps(dec['model_selection'])}`", ""]
        L += ["## Decoder (pooled over subjects)", "",
              "| input | split | trials | keys | key acc | greedy CER vs typed | greedy CER vs target | greedy WER vs target |",
              "|---|---|---|---|---|---|---|---|"]
        for kind in [k for k in ("real", "shuffled_meg", "perm_label", "lr", "mlp", "lr_perm", "mlp_perm") if k in dm]:
            for split in ("val", "test"):
                a = dm[kind][split]["all"]
                L.append(f"| {kind} | {split} | {a['n_trials']} | {a['n_keys']} | {f3(a['key_acc'])} | {f3(a['greedy_cer_typed'])} "
                         f"| {f3(a['greedy_cer_target'])} | {f3(a['greedy_wer_target'])} |")
        L += ["", f"Majority-class chance: val {f3(dm['chance']['val'])}, test {f3(dm['chance']['test'])}.", ""]
        L += ["## Decoder per subject (real input; val+test shown separately)", "",
              "| subject | train keys | lam | test trials | test key acc | test greedy CER typed | val key acc | shuffled-MEG test acc | perm-label test acc |",
              "|---|---|---|---|---|---|---|---|---|"]
        for s, si in dec["subjects"].items():
            te, va = dm["real"]["test"].get(s), dm["real"]["val"].get(s)
            sh, pe = dm["shuffled_meg"]["test"].get(s), dm["perm_label"]["test"].get(s)
            L.append(f"| {s} | {si['n_train_keys']} | {si['lr_lam']} | {te['n_trials'] if te else 0} | {f3(te['key_acc']) if te else '-'} "
                     f"| {f3(te['greedy_cer_typed']) if te else '-'} | {f3(va['key_acc']) if va else '-'} "
                     f"| {f3(sh['key_acc']) if sh else '-'} | {f3(pe['key_acc']) if pe else '-'} |")
        L.append("")
    if (OUT / "lm.json").exists():
        lmr = json.loads((OUT / "lm.json").read_text(encoding="utf-8"))
        L += ["## Beam + Spanish 6-gram LM (CER/WER vs target)", "",
              f"Frame T fitted on val (for the _calT rows): {f3(lmr.get('frame_temperature_val'))}.", "",
              "| setting | val CER | val WER | test CER | test WER | test sentence acc | test target in n-best |", "|---|---|---|---|---|---|---|"]
        for k, r in lmr["results"].items():
            mark = " (best on val)" if k == lmr["best_on_val"] else ""
            L.append(f"| {k}{mark} | {f3(r['val']['cer_target'])} | {f3(r['val']['wer_target'])} | {f3(r['test']['cer_target'])} "
                     f"| {f3(r['test']['wer_target'])} | {f3(r['test']['sentence_acc'])} | {f3(r['test']['target_in_nbest'])} |")
        L.append("")
    if (OUT / "trust.json").exists():
        tr = json.loads((OUT / "trust.json").read_text(encoding="utf-8"))
        bt, bs = tr["bootstrap_trials"]["policies"], tr["bootstrap_sentences"]["policies"]

        def wci(p, k, nd=3):
            v = tr["policies"][p].get(k)
            c1, c2 = bt.get(p, {}).get(k), bs.get(p, {}).get(k)
            s = f3(v, nd)
            if c1:
                s += f" [{f3(c1[0], nd)}, {f3(c1[1], nd)}]"
            if c2:
                s += f" {{{f3(c2[0], nd)}, {f3(c2[1], nd)}}}"
            return s

        L += [f"## Trust pipeline on test ({tr['n_test']} trials, {tr['n_test_sentences']} sentences; fit on val: "
              f"{tr['n_val']} trials, {tr['n_val_sentences']} sentences)", "",
              "Values: point [trial-bootstrap 95% CI] {sentence-cluster bootstrap 95% CI}.", "",
              "| policy | eWPM | wrong-commit | silent error | top-1 CER | committed CER |", "|---|---|---|---|---|---|"]
        core = [p for p in ("a_greedy_commit", "b_top1_commit", "b0_top1_commit_uncal", "c_trust", "d_trust_no_calib",
                            "e_trust_no_guard", "f_trust_consistency_ptop1") if p in tr["policies"]]
        for p in core:
            m = tr["policies"][p]
            tc = bt[p]["top1_cer"]
            L.append(f"| {p} | {wci(p, 'ewpm', 2)} | {wci(p, 'wrong_commit_rate')} | {wci(p, 'silent_error_rate')} "
                     f"| {f3(m['cer'])} [{f3(tc[0])}, {f3(tc[1])}] | {wci(p, 'committed_cer')} |")
        L += ["", "| policy | COMMIT | OFFER | ASK | ABSTAIN | communicated | committed WER | WER top-1 |", "|---|---|---|---|---|---|---|---|"]
        for p in list(tr["policies"]):
            m = tr["policies"][p]
            L.append(f"| {p} | {f3(m['rate_commit'], 2)} | {f3(m['rate_offer'], 2)} | {f3(m['rate_ask'], 2)} | {f3(m['rate_abstain'], 2)} "
                     f"| {f3(m['communicated_rate'])} | {f3(m.get('committed_wer'))} | {f3(m['wer'])} |")
        L += ["", "## Calibration, conformal and guard (test)", "",
              "| policy | T frame | T sentence | ECE char before | after | ECE sentence before | after | coverage | coverage in n-best | mean set size | n-best miss | guard AUROC | inconsistency AUROC | p_top1 AUROC |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for p in [q for q in core if q.startswith(("c_", "d_", "e_", "f_"))]:
            m = tr["policies"][p]
            L.append(f"| {p} | {f3(m.get('fit_temperature_frame'))} | {f3(m.get('fit_temperature_sentence'))} | {f3(m.get('ece_char_before'))} "
                     f"| {f3(m.get('ece_char_after'))} | {f3(m.get('ece_sentence_before'))} | {f3(m.get('ece_sentence_after'))} | {f3(m.get('coverage'))} "
                     f"| {f3(m.get('coverage_in_nbest'))} | {f3(m.get('mean_set_size'))} | {f3(m.get('miss_rate'))} | {f3(m.get('guard_auroc'))} "
                     f"| {f3(m.get('guard_auroc_inconsistency'))} | {f3(m.get('p_top1_auroc'))} |")
        L += ["", "## Paired bootstrap differences (test)", "", "| difference | trial CI | P(diff <= 0) | sentence CI |", "|---|---|---|---|"]
        for k, v in tr["bootstrap_trials"]["diffs"].items():
            vs = tr["bootstrap_sentences"]["diffs"].get(k, {})
            L.append(f"| {k} | [{f3(v['ci'][0])}, {f3(v['ci'][1])}] | {f3(v['p_le_0'])} | "
                     f"[{f3(vs.get('ci', [None, None])[0])}, {f3(vs.get('ci', [None, None])[1])}] |")
        L += ["", "## Null-input audit (test streams)", "", "| policy | input | fluent top-1 | COMMIT rate | fluent and committed | mean chars |", "|---|---|---|---|---|---|"]
        for p, d in tr["null_audit"].items():
            for c, v in d.items():
                if c == "null_vs_real_auroc":
                    continue
                L.append(f"| {p} | {c} | {f3(v['fluent_rate'])} | {f3(v['commit_rate'])} | {f3(v['fluent_commit_rate'])} | {f3(v['mean_chars'], 1)} |")
        L += ["", "## Guard signals (test): AUROC for top-1 CER above the median, Spearman with top-1 CER", "",
              "| policy | risk | inconsistency | -p_top1 | low evidence | rho risk | rho inconsistency | rho -p_top1 |",
              "|---|---|---|---|---|---|---|---|"]
        for p in core:
            m = tr["policies"][p]
            if "auroc_highcer_risk" in m:
                L.append(f"| {p} | {f3(m['auroc_highcer_risk'])} | {f3(m['auroc_highcer_inconsistency'])} | {f3(m['auroc_highcer_neg_p_top1'])} "
                         f"| {f3(m['auroc_highcer_low_evidence'])} | {f3(m['spearman_cer_risk'])} | {f3(m['spearman_cer_inconsistency'])} "
                         f"| {f3(m['spearman_cer_neg_p_top1'])} |")
        L += ["", "## Guard signals: AUROC null input vs real input (test streams)", "",
              "| policy | null input | risk | inconsistency | -p_top1 | low evidence |", "|---|---|---|---|---|---|"]
        for p, d in tr["null_audit"].items():
            for c, v in d.get("null_vs_real_auroc", {}).items():
                L.append(f"| {p} | {c} | {f3(v['risk'])} | {f3(v['inconsistency'])} | {f3(v['neg_p_top1'])} | {f3(v['low_evidence'])} |")
        L += ["", "## Word-level alternatives (test): share of true words found", "",
              "| policy | top-1 sentence word | top-3 per-word slot | best of top-3 sentences |", "|---|---|---|---|"]
        for p in core:
            m = tr["policies"][p]
            if "word_slot_top3_recall" in m:
                L.append(f"| {p} | {f3(m['word_top1_recall'])} | {f3(m['word_slot_top3_recall'])} | {f3(m['word_best_of_top3_sentences_recall'])} |")
        L += ["", "## Per subject (test)", "", "| subject | n | eWPM b | wrong-commit b | eWPM c | wrong-commit c | COMMIT c |", "|---|---|---|---|---|---|---|"]
        for s, d in tr["per_subject"].items():
            b, c = d["b_top1_commit"], d["c_trust"]
            L.append(f"| {s} | {d['n']} | {f3(b['ewpm'], 2)} | {f3(b['wrong_commit_rate'])} | {f3(c['ewpm'], 2)} | {f3(c['wrong_commit_rate'])} | {f3(c['rate_commit'], 2)} |")
        L += ["", f"Fitted policy (c): `{json.dumps(tr['policies']['c_trust'].get('fit_policy_config'))}` "
              f"feasible on val: {tr['policies']['c_trust'].get('fit_policy_fit_feasible')}"]
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="decoder,lm,trust")
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args()
    stages = args.stages.split(",")
    OUT.mkdir(exist_ok=True)
    log("start", stages)
    if "decoder" in stages and (args.redo or not (OUT / "decoder.json").exists()):
        stage_decoder()
        write_tables()
    if "lm" in stages and (args.redo or not (OUT / "lm.json").exists()):
        lm_res = stage_lm()
    else:
        lm_res = json.loads((OUT / "lm.json").read_text(encoding="utf-8"))
    write_tables()
    if "trust" in stages:
        stage_trust(lm_res)
    write_tables()
    log("done")


if __name__ == "__main__":
    main()
