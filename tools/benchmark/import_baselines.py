r"""Build the baseline entries of leaderboard v0.1 from committed results.

Our own decoders have not been rerun as stream submissions (that needs the
GPU, the MEG cache and about 45 min of CPU per B2T rerun). So this script
scores them from the **committed** derived results of earlier experiments
and says so in each entry (``scored_from``):

- ``committed-per-trial``: per-trial arrays are committed (time, words,
  wrong commit, commit score per trial). The benchmark scorer recomputes
  eWPM, wrong-commit, error among commits, commit rate and the cluster
  bootstrap CIs; CRC / LTT thresholds are calibrated here on the
  committed calibration items with ``fidetype.trust.risk_control``.
- ``committed-aggregate``: only aggregate numbers and their bootstrap CIs
  are committed. They are copied as they are.

The local truth files (from ``python -m fidetype.benchmark prepare``) give
the truth lengths for the gaze reference and for pooled CERs. No truth
text is written to the results.

    .venv\Scripts\python.exe -I tools/benchmark/import_baselines.py \
        --truth-dir C:/Users/zhang/bci-data/benchmark \
        --stream-result C:/Users/zhang/bci-data/benchmark/b2t25-published-result.json
    .venv\Scripts\python.exe -m fidetype.benchmark leaderboard
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fidetype.benchmark.prepare import read_truth  # noqa: E402
from fidetype.benchmark.registry import get_track  # noqa: E402
from fidetype.benchmark.scoring import (  # noqa: E402
    RESULT_SCHEMA,
    bootstrap_ci,
    guarantee_block,
    metric_block,
    to_jsonable,
    weighted_metrics,
)
from fidetype.benchmark.splits import load_split  # noqa: E402
from fidetype.trust.risk_control import crc_threshold, ltt_threshold  # noqa: E402

OUT = ROOT / "benchmark" / "results" / "v0.1"
EXP = ROOT / "experiments"
B = 2000
ALPHA, DELTA = 0.05, 0.1

MEG_DECODER = {
    "name": "ConvCTC-M async + es char 6-gram beam (Fidetype)",
    "version": "m1-09-r4b-full-medium",
    "url": "https://github.com/zhangzibo/fidetype/tree/main/experiments/2026-11-11-m1-09-async-full",
    "weights_licence": "not released (trained on CC BY-NC 4.0 data: research only)",
    "training_data": ["SpanishBCBL train split (CC BY-NC 4.0)", "Tatoeba es (CC BY 2.0 FR) for the char LM"],
}
B2T_OURS = {
    "name": "Phoneme beam -> CMUdict word decoder (Fidetype)",
    "version": "m6-06",
    "url": "https://github.com/zhangzibo/fidetype/tree/main/experiments/2026-11-10-b2t25-trust",
    "weights_licence": "no trained weights (input: published RNN logits, CC0; CMUdict BSD-style; Tatoeba CC BY 2.0 FR)",
    "training_data": ["none (decoding only)"],
}
B2T_PUB = {
    "name": "Card et al. 2024 online decoder (published sentence)",
    "version": "t15-copytask-online",
    "url": "https://doi.org/10.5061/dryad.dncjsxm85",
    "weights_licence": "not released (outputs in the CC0 dataset)",
    "training_data": ["T15 sessions (Card et al. 2024)"],
    "training_regime": "online, per-user",
}
EMG_DECODER = {
    "name": "Key-press CNN + en char 6-gram beam (Fidetype)",
    "version": "m6-07",
    "url": "https://github.com/zhangzibo/fidetype/tree/main/experiments/2026-11-11-emg-toronto",
    "weights_licence": "not released (trained on CC BY 4.0 data)",
}
EMG_REGIME = {"xsession": "cross-session", "calib": "session-calibrated", "xsubject": "cross-subject"}

POLICY = {
    "commit": {"name": "always-commit", "description": "commit the top-1 text on every trial"},
    "trust": {"name": "trust gate (plug-in fit)", "description": "Fidetype trust core: COMMIT only above a "
              "calibrated p_top1 threshold fitted on the calibration split (empirical wrong-commit <= 0.05); else OFFER"},
    "crc": {"name": "trust gate + CRC", "description": "commit threshold by conformal risk control, alpha 0.05"},
    "ltt": {"name": "trust gate + LTT", "description": "commit threshold by Learn then Test, alpha 0.05, delta 0.1"},
}


def load(rel: str) -> dict:
    return json.loads((EXP / rel).read_text(encoding="utf-8"))


def fnum(x) -> float:
    return float("-inf") if x == "-inf" else (float("inf") if x == "inf" else float(x))


def result(track: str, entry: str, decoder: dict, policy: dict, metrics: dict, controls: dict, guarantee: dict,
           conformance: dict, scored_from: str, sources: list[str], n: int, notes: list[str]) -> dict:
    t = get_track(track)
    return {
        "schema": RESULT_SCHEMA, "benchmark_version": "0.1", "entry_id": f"{track}/{entry}", "track": track,
        "decoder": decoder, "policy": policy, "scored_from": scored_from, "sources": sources, "n_trials": n,
        "ci": {"unit": t.ci_unit, "method": "percentile cluster bootstrap", "B": B, "seed": 0, "level": 0.95},
        "metrics": metrics, "controls": controls, "guarantee": guarantee, "conformance": conformance,
        "user_model": {"name": t.user_model.name, "config": t.user_model.config,
                       "gaze_chars_per_min": t.user_model.gaze_chars_per_min},
        "notes": notes, "status": "baseline",
    }


def truth_lengths(truth_dir: Path, name: str, ids: list[str]) -> tuple[np.ndarray, np.ndarray]:
    tr = read_truth(truth_dir / name)
    nc = np.array([len(tr[i]["text"]) for i in ids], float)
    nw = np.array([len(tr[i]["text"].split()) for i in ids], float)
    return nc, nw


class Items:
    """Per-trial arrays of a committed items file (commit vs fallback outcome per trial)."""

    def __init__(self, d: dict):
        self.s = np.array([fnum(x) for x in d["score"]])
        for k in ("loss_c", "loss_f", "wc_c", "wc_f", "time_c", "time_f", "words_c", "words_f", "silent_c", "silent_f"):
            setattr(self, k, np.asarray(d[k], float))
        self.lam_old = float(d["lam_old"])

    def arrays(self, lam: float, nc: np.ndarray, nw: np.ndarray, gaze_cpm: float) -> dict[str, np.ndarray]:
        on = self.s >= lam
        return {"w": np.where(on, self.words_c, self.words_f), "t": np.where(on, self.time_c, self.time_f),
                "wc": np.where(on, self.wc_c, self.wc_f), "cm": on.astype(float),
                "se": np.where(on, self.silent_c, self.silent_f), "nw": nw, "gt": nc * 60.0 / gaze_cpm}


def per_trial_metrics(a: dict, clusters: list[dict], unit: str, cer: float | None, wer: float | None) -> dict:
    point = weighted_metrics(a)
    ci = bootstrap_ci(lambda w: weighted_metrics(a, w), unit, clusters, B=B, seed=0)
    m = metric_block(point, ci)
    m["cer"] = {"value": cer, "ci": None, "basis": "aggregate of the committed run (no per-trial CER)"}
    m["wer"] = {"value": wer, "ci": None, "basis": "aggregate of the committed run"}
    return m


def thresholds(it_fit: Items) -> dict[str, float]:
    return {"trust": it_fit.lam_old,
            "crc": crc_threshold(it_fit.s, it_fit.loss_c, ALPHA, it_fit.loss_f).threshold,
            "ltt": ltt_threshold(it_fit.s, it_fit.loss_c, ALPHA, DELTA, it_fit.loss_f).threshold}


def guarantee(kind: str, n_cal: int, cal_split: str, metrics: dict, lam: float) -> dict:
    if kind not in ("crc", "ltt"):
        return {"method": "none"}
    g = {"method": kind, "alpha": ALPHA, "n_cal": n_cal, "calibration_split": cal_split,
         "scope": "marginal wrong-commit rate over test trials; assumes calibration and test trials are exchangeable"}
    if kind == "ltt":
        g["delta"] = DELTA
    out = guarantee_block(g, metrics, n_cal)
    out["threshold"] = None if not math.isfinite(lam) else lam
    return out


def agg_control(status: str, basis: str, **kw) -> dict:
    return {"status": status, "basis": basis, **kw}


# ---------------------------------------------------------------------------
# MEG
# ---------------------------------------------------------------------------


def meg(truth_dir: Path) -> list[dict]:
    track = "spanishbcbl-meg-async"
    t = get_track(track)
    split = load_split(track)
    ids = split.ids("test")
    clusters = [r["clusters"] for r in split.trials("test")]
    nc, nw = truth_lengths(truth_dir, "meg-truth.jsonl", ids)
    g1 = "2026-11-11-g1-async-meg-trust/results/"
    items = load(g1 + "items-meg-async.json")
    harness = load(g1 + "harness-async.json")
    null = load(g1 + "null-audit-async.json")["policies"]
    ps = load("2026-11-11-m1-09-async-full/results/beam-m1-09-r4b-full-medium/per_sentence_cer.json")["test"]
    # Decoder-level controls: paired CER gaps from the M1-09 control run (beam + LM, val-tuned).
    real = np.array(ps["real"]["beam_lm_valtuned"]) * nc
    ctl = {}
    for kind, key in (("shuffled", "shuffled"), ("zeros", "zeros")):
        cc = np.array(ps[key]["beam_lm_valtuned"]) * nc

        def gap(w, cc=cc):
            den = float((nc * w).sum())
            return {"cer_control": float((cc * w).sum()) / den, "cer_gap": float(((cc - real) * w).sum()) / den}

        pt = gap(np.ones_like(nc))
        ci = bootstrap_ci(gap, t.ci_unit, clusters, B=B, seed=11)
        ctl[kind] = {"status": "pass" if ci["cer_gap"][0] > 0 else "fail", "cer_control": pt["cer_control"],
                     "cer_gap": pt["cer_gap"], "cer_gap_ci": ci["cer_gap"],
                     "basis": "per-trial CER of the M1-09 control run (beam + LM, val-tuned; same network)"}
    conf = {"level": "core", "gate": "trust-ready", "passed": False,
            "checked": "the M1-09 stream files (local); they predate the M5-10 adapter and lack device.modality, "
                       "decoder.causal, data.derived and language. The current adapter reaches provenance on "
                       "synthetic input; rerun infer.py to get trust-ready streams."}
    cer_beam = float(harness["policies"]["commit"]["cer"])
    wer_beam = float(harness["policies"]["commit"]["wer"])
    notes = [f"Decoder CER: greedy {np.sum(np.array(ps['real']['greedy']) * nc) / nc.sum():.3f}, beam + LM val-tuned "
             f"{real.sum() / nc.sum():.3f} (pooled over trials). The trust pipeline decodes with its own beam "
             f"(RETUNED, lm_weight 0.5, frame temperature): CER {cer_beam:.3f}."]
    src = [f"experiments/{g1}items-meg-async.json", f"experiments/{g1}harness-async.json",
           f"experiments/{g1}null-audit-async.json",
           "experiments/2026-11-11-m1-09-async-full/results/beam-m1-09-r4b-full-medium/per_sentence_cer.json"]
    out = []
    # Always commit: aggregate of the harness run (two-way bootstrap committed).
    pc = harness["policies"]["commit"]
    bt = harness["bootstrap"]["two_way"]["policies"]["commit"]
    gz = harness["policies"]["gaze_only"]["ewpm"]
    m = {"cer": {"value": cer_beam, "ci": None}, "wer": {"value": wer_beam, "ci": None},
         "ewpm": {"value": pc["ewpm"], "ci": bt["ewpm"]}, "gaze_ewpm": {"value": gz, "ci": None},
         "ewpm_minus_gaze": {"value": pc["ewpm"] - gz, "ci": None},
         "wrong_commit_rate": {"value": pc["wrong_commit_rate"], "ci": bt["wrong_commit_rate"]},
         "commit_rate": {"value": pc["rate_commit"], "ci": None},
         "error_among_commits": {"value": pc["wrong_commit_rate"] / pc["rate_commit"], "ci": bt["wrong_commit_rate"]},
         "silent_error_rate": {"value": pc["silent_error_rate"], "ci": bt["silent_error_rate"]}}
    zc = null["commit"]["zeros_meg"]["commit_rate"]
    c = {**ctl, "null_commit": {"status": "pass" if zc <= 0.05 else "fail", "commit_rate_zeros": zc,
                                "basis": "null audit (zeros MEG input), n=637"}}
    c["passed"] = all(c[k]["status"] == "pass" for k in ("shuffled", "zeros", "null_commit"))
    out.append(result(track, "convctc-m-async/always-commit", MEG_DECODER, POLICY["commit"], m, c, {"method": "none"},
                      conf, "committed-aggregate", src, len(ids), notes))
    # Per-trial policies.
    fit, test = Items(items["fit"]), Items(items["test"])
    th = thresholds(fit)
    for kind in ("trust", "crc", "ltt"):
        a = test.arrays(th[kind], nc, nw, t.user_model.gaze_chars_per_min)
        m = per_trial_metrics(a, clusters, t.ci_unit, cer_beam, wer_beam)
        if kind == "trust":
            zc = null["trust"]["zeros_meg"]["commit_rate"]
            nul = {"status": "pass" if zc <= 0.05 else "fail", "commit_rate_zeros": zc,
                   "basis": "null audit (zeros MEG input), n=637"}
        else:
            nul = {"status": "missing", "basis": "no null audit at this threshold"}
        c = {**ctl, "null_commit": nul}
        c["passed"] = all(c[k]["status"] == "pass" for k in ("shuffled", "zeros", "null_commit"))
        out.append(result(track, f"convctc-m-async/{kind}", MEG_DECODER, POLICY[kind], m, c,
                          guarantee(kind, len(fit.s), "val", m, th[kind]), conf, "committed-per-trial", src,
                          len(ids), notes + ([f"{POLICY[kind]['name']}: commit threshold on calibrated p_top1 {th[kind]:.4f} "
                                              f"(fitted on the {len(fit.s)} val trials)."] if math.isfinite(th[kind]) else
                                             [f"{POLICY[kind]['name']}: threshold +inf (never commit)."])))
    return out


# ---------------------------------------------------------------------------
# B2T
# ---------------------------------------------------------------------------


def b2t(truth_dir: Path, stream_result: Path | None) -> list[dict]:
    track = "b2t25-t15-copytask"
    t = get_track(track)
    split = load_split(track)
    ids = split.ids("test")
    clusters = [r["clusters"] for r in split.trials("test")]
    nc, nw = truth_lengths(truth_dir, "b2t25-truth.jsonl", ids)
    tj = load("2026-11-10-b2t25-trust/results/trust.json")["levels"]["word"]
    P, BD, NA = tj["policies"], tj["bootstrap_days"]["policies"], tj["null_audit"]
    conf = {"level": "trust-ready", "gate": "trust-ready", "passed": True,
            "checked": "adapter streams (fidetype.adapters.b2t25), all 816 test files of the stream submission"}
    src_t = "experiments/2026-11-10-b2t25-trust/results/trust.json"
    out = []

    def dec_controls(policy_key: str, null_policy: str | None) -> dict:
        na = NA.get("w_b_top1_commit", {})
        real_wc = na["real"]["wrong_commit_rate"]
        c = {"shuffled": agg_control("pass" if na["frame_shuffled"]["wrong_commit_rate"] > real_wc else "fail",
                                     "aggregate null audit of the top-1 decoder (n=300): wrong-commit real "
                                     f"{real_wc:.3f} vs frame-shuffled {na['frame_shuffled']['wrong_commit_rate']:.3f}"),
             "zeros": agg_control("pass" if na["uniform"]["wrong_commit_rate"] > real_wc else "fail",
                                  "aggregate null audit (uniform logits stand in for zeros input, n=300): wrong-commit "
                                  f"real {real_wc:.3f} vs uniform {na['uniform']['wrong_commit_rate']:.3f}")}
        if null_policy and null_policy in NA:
            zc = NA[null_policy]["uniform"]["commit_rate"]
            c["null_commit"] = {"status": "pass" if zc <= 0.05 else "fail", "commit_rate_zeros": zc,
                                "basis": "null audit, uniform logits, n=300"}
        else:
            c["null_commit"] = {"status": "missing", "basis": "no null audit for this policy"}
        c["passed"] = all(c[k]["status"] == "pass" for k in ("shuffled", "zeros", "null_commit"))
        return c

    # Our decoder, always commit (aggregate).
    pc, bt = P["w_b_top1_commit"], BD["w_b_top1_commit"]
    gz = tj["gaze_only_ewpm"]
    m = {"cer": {"value": pc["cer"], "ci": None}, "wer": {"value": pc["wer"], "ci": None},
         "ewpm": {"value": pc["ewpm"], "ci": bt["ewpm"]}, "gaze_ewpm": {"value": gz, "ci": None},
         "ewpm_minus_gaze": {"value": pc["ewpm"] - gz, "ci": None},
         "wrong_commit_rate": {"value": pc["wrong_commit_rate"], "ci": bt["wrong_commit_rate"]},
         "commit_rate": {"value": pc["rate_commit"], "ci": bt["rate_commit"]},
         "error_among_commits": {"value": pc["wrong_commit_rate"] / pc["rate_commit"], "ci": bt["wrong_commit_rate"]},
         "silent_error_rate": {"value": pc.get("silent_error_rate"), "ci": bt.get("silent_error_rate")}}
    out.append(result(track, "ours/always-commit", B2T_OURS, POLICY["commit"], m, dec_controls("b", "w_b_top1_commit"),
                      {"method": "none"}, conf, "committed-aggregate", [src_t], len(ids), []))
    # Per-trial policies for our decoder and for the published sentence.
    for dec, items_name, cer_key, null_pol, tag in (
            (B2T_OURS, "items-b2t-ours.json", "w_c_trust", "w_c_trust", "ours"),
            (B2T_PUB, "items-b2t-published.json", "w_q_published_trust", "w_q_published_trust", "published")):
        d = load(f"2026-11-11-m2-13-conformal/results/{items_name}")
        fit, test = Items(d["fit"]), Items(d["test"])
        assert all(int(c["day"][3:]) == x for c, x in zip(clusters, d["days_test"])), "day order"
        th = thresholds(fit)
        for kind in ("trust", "crc", "ltt"):
            a = test.arrays(th[kind], nc, nw, t.user_model.gaze_chars_per_min)
            m = per_trial_metrics(a, clusters, t.ci_unit, P[cer_key]["cer"], P[cer_key]["wer"])
            if tag == "ours":
                c = dec_controls(kind, null_pol if kind == "trust" else None)
            else:
                nul = ({"status": "pass" if NA[null_pol]["uniform"]["commit_rate"] <= 0.05 else "fail",
                        "commit_rate_zeros": NA[null_pol]["uniform"]["commit_rate"], "basis": "null audit, uniform "
                        "logits, n=300 (tests the gate; the text is fixed)"} if kind == "trust" else
                       {"status": "missing", "basis": "no null audit at this threshold"})
                c = {"shuffled": {"status": "missing", "basis": "text-only decoder: cannot rerun on shuffled input"},
                     "zeros": {"status": "missing", "basis": "text-only decoder: cannot rerun on zero input"},
                     "null_commit": nul, "passed": False}
            out.append(result(track, f"{tag}/{kind}", dec, POLICY[kind], m, c,
                              guarantee(kind, len(fit.s), "cal", m, th[kind]), conf, "committed-per-trial",
                              [src_t, f"experiments/2026-11-11-m2-13-conformal/results/{items_name}"], len(ids),
                              ["cal = first half of each day, test = second half: the test trials are later in the "
                               "day, so cal and test are not exchangeable (drift; see M2-13/M2-16)."]))
    if stream_result and stream_result.exists():
        r = json.loads(stream_result.read_text(encoding="utf-8"))
        r["entry_id"] = f"{track}/published/always-commit"
        r["sources"] = ["tools/benchmark/make_b2t25_published.py (local stream submission, 816 NTS files)"]
        r["status"] = "baseline"
        r["notes"] = ["Scored end to end from NTS files by `python -m fidetype.benchmark score`. Matches the committed "
                      "M6-06 numbers: CER 0.0309, WER 0.0431, wrong-commit 0.194 (eWPM differs only by the user-model "
                      "random draws: 19.61 committed)."] + list(r.get("notes", []))
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# EMG
# ---------------------------------------------------------------------------


def emg() -> list[dict]:
    track = "toronto-semg-composed"
    e = load("2026-11-11-emg-toronto/results/trust.json")
    conf = {"level": "trust-ready", "gate": "trust-ready", "passed": True,
            "checked": "local composed streams (cache streams/calib/test00_ctc.npz); provenance fails only on "
                       "decoder.weights_sha256 and stream.id"}
    src = ["experiments/2026-11-11-emg-toronto/results/trust.json"]
    out = []
    for cond, regime in EMG_REGIME.items():
        C = e["conditions"][cond]
        P, BP, NA = C["policies"], C["bootstrap_participants"]["policies"], C["null_audit"]
        gz = C["gaze_only_ewpm"]
        dec = {**EMG_DECODER, "training_regime": regime,
               "training_data": [f"Toronto sEMG ({regime}; CC BY 4.0)", "Tatoeba en (CC BY 2.0 FR) for the char LM"]}
        na_b = NA["b_top1_commit"]
        real_wc = na_b["real"]["wrong_commit_rate"]
        base_ctl = {
            "shuffled": agg_control("pass" if na_b["frame_shuffled"]["wrong_commit_rate"] > real_wc else "fail",
                                    f"aggregate null audit (n={e.get('null_audit_n', C.get('null_audit_n', 200))}): "
                                    f"wrong-commit real {real_wc:.3f} vs frame-shuffled "
                                    f"{na_b['frame_shuffled']['wrong_commit_rate']:.3f}"),
            "zeros": agg_control("pass" if na_b["zeros_input"]["wrong_commit_rate"] > real_wc else "fail",
                                 f"aggregate null audit: wrong-commit real {real_wc:.3f} vs zeros input "
                                 f"{na_b['zeros_input']['wrong_commit_rate']:.3f}")}
        for key, kind in (("b_top1_commit", "commit"), ("c_trust", "trust"), ("c_crc", "crc")):
            pc, bt = P[key], BP[key]
            cr = pc["rate_commit"]
            m = {"cer": {"value": pc["cer"], "ci": None}, "wer": {"value": pc["wer"], "ci": None},
                 "ewpm": {"value": pc["ewpm"], "ci": bt["ewpm"]}, "gaze_ewpm": {"value": gz, "ci": None},
                 "ewpm_minus_gaze": {"value": pc["ewpm"] - gz, "ci": None},
                 "wrong_commit_rate": {"value": pc["wrong_commit_rate"], "ci": bt["wrong_commit_rate"]},
                 "commit_rate": {"value": cr, "ci": bt["rate_commit"]},
                 "error_among_commits": {"value": (pc["wrong_commit_rate"] / cr) if cr > 0 else None, "ci": None},
                 "silent_error_rate": {"value": pc["silent_error_rate"], "ci": bt["silent_error_rate"]}}
            if key in NA:
                zc = NA[key]["zeros_input"]["commit_rate"]
                nul = {"status": "pass" if zc <= 0.05 else "fail", "commit_rate_zeros": zc,
                       "basis": "null audit, zeros input"}
            else:
                nul = {"status": "missing", "basis": "no null audit for this policy"}
            c = {**base_ctl, "null_commit": nul}
            c["passed"] = all(c[k]["status"] == "pass" for k in ("shuffled", "zeros", "null_commit"))
            g = {"method": "none"}
            if kind == "crc":
                g = guarantee_block({"method": "crc", "alpha": ALPHA, "n_cal": int(pc["fit_risk_control_n"]),
                                     "calibration_split": "cal (held-out half of the fit items)",
                                     "scope": "marginal wrong-commit rate over test sentences; exchangeable"}, m, None)
                g["threshold"] = pc.get("fit_risk_control_threshold")
                g["bound_on_cal"] = pc.get("fit_risk_control_bound")
            out.append(result(track, f"cnn-{cond}/{kind}", dec, POLICY[kind], m, c, g, conf, "committed-aggregate",
                              src, int(pc["n_test"]),
                              ["Composed sentences from isolated key presses: not natural typing."]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth-dir", required=True, type=Path)
    ap.add_argument("--stream-result", type=Path, default=None)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = meg(a.truth_dir) + b2t(a.truth_dir, a.stream_result) + emg()
    for r in rows:
        name = r["entry_id"].replace("/", "__") + ".json"
        (OUT / name).write_text(json.dumps(to_jsonable(r), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} results to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
