"""Confirmatory T12 test (M3-27): streams, word decoding, frozen recipe fit, single test run,
controls, CIs, tables. Follows PROTOCOL.md (pre-registration commit a7cf624).

Stages (repo root, CPU):
  .venv\\Scripts\\python.exe -I experiments/2026-11-13-confirmatory-t12/run.py --stage decoder   # decoder quality on decoder-validation only
  .venv\\Scripts\\python.exe -I experiments/2026-11-13-confirmatory-t12/run.py --stage trust     # fit-A, LTT, freeze, ONE test run, controls
  .venv\\Scripts\\python.exe -I experiments/2026-11-13-confirmatory-t12/run.py --stage tables
Inputs: prep.py and decode.py outputs (outside the repo). Writes results/*.json, results/tables.md.
Per-trial records, the provenance ledger and stream files go to the derived dir (outside the repo).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "2"

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t12 as T  # noqa: E402

B = T.B
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.eval.ewpm import summarize  # noqa: E402
from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline  # noqa: E402
from fidetype.eval.metrics import ctc_greedy_decode, edit_distance  # noqa: E402
from fidetype.interact.simulated_user import UserConfig  # noqa: E402
from fidetype.streams.spec import NeuralTextStream  # noqa: E402
from fidetype.trust.frozen import PAPER1_V4_RECIPE, FrozenTrustConfig  # noqa: E402
from fidetype.trust.guard import shuffle_stream, uniform_stream  # noqa: E402
from fidetype.trust.policy import AlwaysCommitPolicy, DecisionPolicy  # noqa: E402
from fidetype.trust.risk_control import _log_binom_cdf, commit_calibration_data  # noqa: E402

CFG = T.CONFIG
OUT = T.RESULTS
OUT.mkdir(exist_ok=True)
DER = T.DERIVED
ALPHA, DELTA = CFG["trust"]["alpha"], CFG["trust"]["delta"]
LOGF = OUT / "run.log"


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_b2t25():
    p = T.REPO / "experiments/2026-11-10-b2t25-trust/run.py"
    spec = importlib.util.spec_from_file_location("b2t25run", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def cp(k: int, n: int, level: float = 0.95) -> list:
    from scipy.stats import beta
    if n == 0:
        return [None, None]
    a = 1 - level
    lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return [lo, hi]


def cp_upper_one_sided(k: int, n: int) -> float:
    from scipy.stats import beta
    return 1.0 if k == n else float(beta.ppf(0.95, k + 1, n - k))


# ---------------------------------------------------------------------------
# Streams and items
# ---------------------------------------------------------------------------

class Data:
    def __init__(self) -> None:
        self.prep = json.loads((OUT / "prep.json").read_text(encoding="utf-8"))
        self.texts = json.loads((DER / "texts.json").read_text(encoding="utf-8"))
        self.lp = np.load(DER / "logprobs.npz")
        self.lpmeta = json.loads((DER / "logprobs-meta.json").read_text(encoding="utf-8"))
        self.role = {r["session"]: r["role"] for r in self.prep["sessions"]}
        self.sessions = [r["session"] for r in self.prep["sessions"]]
        self.npz = {}
        self.gidx = 0

    def ph(self, s: str, part: str, i: int) -> list[str]:
        if s not in self.npz:
            self.npz[s] = np.load(DER / f"{s}.npz")
        return [B.VOCAB[j] for j in self.npz[s][f"{part}_ph{i}"]]

    def stream(self, s: str, part: str, i: int, gidx: int) -> NeuralTextStream:
        lp = self.lp[f"{s}|{part}|{i}"].astype(np.float32)
        h = hashlib.sha256(f"b2t24-competitionData/{CFG['archive_md5']}/{s}/{part}/{i}/".encode())
        h.update(self.lpmeta["checkpoint_sha256"].encode())
        h.update(np.ascontiguousarray(lp).tobytes())
        meta = {
            "device.modality": "intracortical", "device.channel_count": 256, "device.invasive": True,
            "device.regulatory_status": "investigational",
            "decoder.name": "fidetype-t12-gru-ctc", "decoder.version": "m3-27-" + self.lpmeta["checkpoint_sha256"][:12],
            "decoder.causal": True, "decoder.lookahead_s": 0.0, "decoder.calibration_method": "none",
            "adapter.name": "experiments/2026-11-13-confirmatory-t12", "adapter.version": FT_VERSION, "lm.name": "none",
            "user.personalized": True, "calibration.applied": False, "subject.id": "T12", "session.id": s,
            "language": "en-US", "data.derived": True, "stream.id": h.hexdigest()[:32],
            "fidetype.vocab_id": B.VOCAB_ID, "fidetype.trial_index": gidx,
            "fidetype.timing": "exact: 80 ms frames, frame time = end of a 14 x 20 ms patch (causal smoothing, unidirectional GRU)",
            "source.dataset": "Willett et al. 2023 / B2T '24 competitionData (CC0)",
        }
        n = lp.shape[0]
        st = NeuralTextStream(log_probs=lp, frame_times=(np.arange(n) * 4 + 14) * 0.02, vocab=list(B.VOCAB), blank_id=0,
                              source="b2t24-t12-gru", meta=meta, vocab_type="phoneme", frame_period=0.08, latency=0.0)
        return B.to_symbol_stream(st)

    def items(self, part: str, sessions: list[str]) -> tuple[list[Item], list[str]]:
        its, sess = [], []
        for s in sessions:
            for i, w in enumerate(self.texts[s][part]):
                st = self.stream(s, part, i, self.gidx)
                self.gidx += 1
                it = Item(st, w, stream_text=B.phonemes_to_symbols(self.ph(s, part, i)))
                it.ref = f"{s}/{part}/{i}"
                its.append(it)
                sess.append(s)
        return its, sess


def decoders(bt):
    bt.CONFIG.update({k: v for k, v in bt.CONFIG.items()})
    return bt.Decoders([], CFG["word_decoder_tuned"])


def quality(fn, items) -> dict:
    """Decoder quality of the word route on items (no policy)."""
    n_c = n_w = e_c = e_w = 0
    ex = inb = 0
    pe = pn = 0
    for it in items:
        nb = fn(it.stream(0))
        top = nb.texts[0] if len(nb) else ""
        e_c += edit_distance(it.text, top)
        n_c += len(it.text)
        e_w += edit_distance(it.text.split(), top.split())
        n_w += len(it.text.split())
        ex += top == it.text
        inb += it.text in nb.texts
        g = ctc_greedy_decode(it.stream(0))
        pe += edit_distance(it.stream_text, g)
        pn += len(it.stream_text)
    n = len(items)
    return {"n": n, "cer": e_c / max(1, n_c), "wer": e_w / max(1, n_w), "sentence_exact": ex / max(1, n),
            "truth_in_nbest": inb / max(1, n), "greedy_per_symbols": pe / max(1, pn)}


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def joint_ltt(s, c, f, beta: float, alpha=ALPHA, delta=DELTA) -> float:
    grid = [round(0.05 * k, 2) for k in range(1, 21)]
    rej = []
    for lam in grid:
        on = s >= lam
        loss = np.where(on, c, f)
        pm = math.exp(_log_binom_cdf(int(round(loss.sum())), loss.size, alpha))
        n1 = int(on.sum())
        pv = 1.0 if n1 == 0 else math.exp(_log_binom_cdf(int(round(c[on].sum())), n1, beta))
        if max(pm, pv) <= delta / len(grid):
            rej.append(lam)
    return min(rej) if rej else math.inf


def rec_summary(records) -> dict:
    m = summarize(records)
    n = len(records)
    ncom = sum(r.committed_text is not None for r in records)
    nwr = sum(bool(r.wrong_commit) for r in records)
    return {"n": n, "n_commit": ncom, "n_wrong_commit": nwr, "wrong_commit": nwr / n if n else math.nan,
            "wrong_commit_cp95": cp(nwr, n), "commit_rate": ncom / n if n else math.nan,
            "error_among_commits": nwr / ncom if ncom else math.nan, "eac_cp95": cp(nwr, ncom) if ncom else [None, None],
            "silent_error_rate": m["silent_error_rate"], "ewpm": m["ewpm"], "abstain_rate": m["abstain_rate"],
            "rate_offer": m["rate_offer"]}


def gaze_ewpm(truths, cpm) -> float:
    t = sum(len(s) for s in truths) * 60.0 / cpm
    return 60.0 * sum(len(s.split()) for s in truths) / t


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

def trust_core_identical() -> dict:
    files = ["src/fidetype/trust/policy.py", "src/fidetype/trust/guard.py", "src/fidetype/trust/risk_control.py",
             "src/fidetype/trust/calibration.py", "src/fidetype/trust/conformal.py", "src/fidetype/eval/harness.py",
             "src/fidetype/interact/simulated_user.py", "src/fidetype/eval/ewpm.py"]
    out = {}
    for f in files:
        tag = subprocess.run(["git", "show", f"{CFG['frozen_tag']}:{f}"], cwd=T.REPO, capture_output=True).stdout
        cur = (T.REPO / f).read_bytes()
        norm = lambda b: b.replace(b"\r\n", b"\n")  # noqa: E731
        out[f] = norm(tag) == norm(cur)
    return out


def stage_decoder() -> None:
    D = Data()
    bt = load_b2t25()
    dec = decoders(bt)
    val, _ = D.items("val", D.sessions)
    t0 = time.time()
    q = quality(dec.words_fn, val)
    q["seconds"] = round(time.time() - t0, 1)
    res = {"decoder_validation": q, "checkpoint": D.lpmeta, "word_route": CFG["word_decoder_tuned"]}
    T.dump(res, OUT / "decoder.json")
    log("decoder validation", json.dumps(q))


def stage_trust(part: str = "pool", out_name: str = "trust.json", limit: int | None = None) -> None:
    """part="val" + out_name="dryrun-trust.json": code check on decoder-validation data (not the trust pool)."""
    marker = OUT / out_name
    if marker.exists() and part == "pool":
        raise SystemExit("trust.json exists: the confirmatory test was already run once (PROTOCOL.md sec. 7)")
    t0 = time.time()
    D = Data()
    bt = load_b2t25()
    dec = decoders(bt)
    S = D.sessions
    fit_s = [s for s in S if D.role[s] == "fit_a"]
    cal_s = [s for s in S if D.role[s] == "calibration"]
    test_s = [s for s in S if D.role[s] == "test"]
    fitA, _ = D.items(part, fit_s)
    cal, _ = D.items(part, cal_s)
    test, test_sess = D.items(part, test_s)
    if limit:
        fitA, cal, test, test_sess = fitA[:limit], cal[:limit], test[:limit], test_sess[:limit]
    test_sess = np.array(test_sess)
    cpm = D.prep["speech_rate_decoder_train"]["chars_per_min"]
    user = UserConfig.aac_gaze(chars_per_min=cpm)
    ident = trust_core_identical()
    log("trust core identical to tag:", ident)
    log(f"fit-A {len(fitA)} ({len(fit_s)} sessions), calibration {len(cal)} ({len(cal_s)}), test {len(test)} ({len(test_s)}); cpm {cpm:.1f}")

    # 1-2. fit-A pipeline (frozen recipe; guard on)
    cfg = HarnessConfig(seed=CFG["trust"]["seed"], user_config=user, max_wrong_commit=ALPHA, use_guard=True)
    pipe = TrustPipeline(dec.words_fn, cfg, {})
    pipe.fit(fitA, fitA)
    plug_cfg = pipe.policy.config
    log("fit-A done", json.dumps({k: v for k, v in pipe.fit_report.items() if k != "policy_config"}, default=str))
    # calibration item table (for the secondary joint LTT); computed with the plug-in policy, as in Paper 1
    cal_inputs = [pipe.analyze(pipe.decode(it, 0)).inputs for it in cal]
    s_c, c_c, f_c = commit_calibration_data(pipe.policy, cal_inputs, [it.text for it in cal])
    # 3. LTT max on the calibration sessions
    r = pipe.calibrate_commit(cal, method="ltt", alpha=ALPHA, delta=DELTA, combine="max")
    log("LTT", r)
    # 4. freeze
    frozen = FrozenTrustConfig.from_pipeline(pipe, name="t12-confirmatory-m3-27", recipe=PAPER1_V4_RECIPE)
    frozen.save(OUT / ("trust-config-t12.json" if part == "pool" else "dryrun-trust-config.json"))
    log("frozen config", frozen.config_id, "commit_p", pipe.policy.config.commit_p)

    # 5. the single test run (with provenance ledger, outside the repo)
    from fidetype.trust.provenance import ProvenanceLedger
    ledger_path = DER / ("ledger-test.jsonl" if part == "pool" else "ledger-dryrun.jsonl")
    if ledger_path.exists():
        ledger_path.unlink()
    led = ProvenanceLedger(ledger_path)
    pipe.attach_ledger(led, context={"calibration_set_id": "t12-sessions-" + ",".join(cal_s),
                                     "extra": {"trust_config_id": frozen.config_id, "preregistration": CFG["preregistration_commit"]}})
    ev = pipe.evaluate(test)
    recs = ev.pop("records")
    main = rec_summary(recs)
    log("TEST (LTT max)", json.dumps(main))

    # secondary rules on the same test items (same fitted pipeline, decode cache shared)
    cache: dict = {}
    for it in test:
        cache[(id(it), 0)] = pipe.analyze(pipe.decode(it, 0))
    lam_ltt = pipe.policy.config.commit_p
    pols = {"LTT max (primary)": pipe.policy,
            "plug-in": DecisionPolicy(plug_cfg, use_guard=True),
            "no commits": DecisionPolicy(replace(pipe.policy.config, commit_p=math.inf), use_guard=True),
            "always commit top-1": AlwaysCommitPolicy()}
    lams = {"LTT max (primary)": lam_ltt, "plug-in": plug_cfg.commit_p, "no commits": math.inf}
    for b_ in CFG["joint_ltt_betas"]:
        lj = joint_ltt(s_c, c_c, f_c, b_)
        lams[f"joint LTT b{b_:.2f}"] = lj
        pols[f"joint LTT b{b_:.2f}"] = DecisionPolicy(replace(plug_cfg, commit_p=lj), use_guard=True)
    recs_by = {k: pipe.run_items(test, p, cache) for k, p in pols.items()}
    assert [r.actions for r in recs_by["LTT max (primary)"]] == [r.actions for r in recs]
    rules = {k: rec_summary(v) for k, v in recs_by.items()}
    truths = [it.text for it in test]
    gz = gaze_ewpm(truths, CFG["gaze_chars_per_min"])

    # per session (P2)
    per_session = {}
    for s in test_s:
        idx = np.where(test_sess == s)[0]
        per_session[s] = {k: rec_summary([recs_by[k][i] for i in idx]) for k in ("LTT max (primary)", "plug-in")}
    above = sum(v["LTT max (primary)"]["wrong_commit"] > ALPHA for v in per_session.values())
    above_cp = sum((v["LTT max (primary)"]["wrong_commit_cp95"][0] or 0) > ALPHA for v in per_session.values())

    # bootstrap over test sessions
    rng = np.random.default_rng(CFG["bootstrap"]["seed"])
    members = {s: np.where(test_sess == s)[0] for s in test_s}
    bs = {k: {"wrong_commit": [], "commit_rate": [], "ewpm": [], "eac": []} for k in recs_by}
    gain, gain_gaze = [], []
    for _ in range(CFG["bootstrap"]["B"]):
        idx = np.concatenate([members[s] for s in rng.choice(test_s, len(test_s))])
        vals = {}
        for k, rr in recs_by.items():
            sub = [rr[i] for i in idx]
            m = rec_summary(sub)
            vals[k] = m
            bs[k]["wrong_commit"].append(m["wrong_commit"])
            bs[k]["commit_rate"].append(m["commit_rate"])
            bs[k]["ewpm"].append(m["ewpm"])
            bs[k]["eac"].append(m["error_among_commits"])
        gain.append(vals["LTT max (primary)"]["ewpm"] - vals["no commits"]["ewpm"])
        gain_gaze.append(vals["LTT max (primary)"]["ewpm"] - gaze_ewpm([truths[i] for i in idx], CFG["gaze_chars_per_min"]))

    def pci(v):
        v = np.array([x for x in v if x is not None and np.isfinite(x)], float)
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size else None

    boot = {k: {m: pci(v) for m, v in d.items()} for k, d in bs.items()}
    # paired gain vs no commits + sign test over sessions
    from scipy.stats import binomtest
    d_s = [per_session[s]["LTT max (primary)"]["ewpm"] - rec_summary([recs_by["no commits"][i] for i in members[s]])["ewpm"]
           for s in test_s]
    pos, neg = sum(x > 1e-12 for x in d_s), sum(x < -1e-12 for x in d_s)
    sign_p = float(binomtest(pos, pos + neg, 0.5).pvalue) if pos + neg else 1.0

    # P3 controls + intent mismatch
    crng = np.random.default_rng(CFG["controls_seed"])
    ctl_items = {"frame_shuffled": [], "uniform": [], "intent_mismatch": []}
    perm = crng.permutation(len(test))
    for i in range(len(perm)):
        if test[perm[i]].text == test[i].text:
            perm[i], perm[(i + 1) % len(perm)] = perm[(i + 1) % len(perm)], perm[i]
    for i, it in enumerate(test):
        st = it.stream(0)
        ctl_items["frame_shuffled"].append(Item(shuffle_stream(st, crng), it.text))
        ctl_items["uniform"].append(Item(uniform_stream(st, crng, CFG["uniform_jitter"]), it.text))
        ctl_items["intent_mismatch"].append(Item(test[perm[i]].stream(0), it.text))
    controls = {}
    for name, its in ctl_items.items():
        controls[name] = {}
        for k in ("LTT max (primary)", "plug-in"):
            rr = pipe.run_items(its, pols[k], {})
            m = rec_summary(rr)
            m["commit_cp95_one_sided_upper"] = cp_upper_one_sided(m["n_commit"], m["n"])
            controls[name][k] = m
        log("control", name, json.dumps(controls[name]["LTT max (primary)"]))

    crit = {
        "C1_pooled_wrong_commit_le_alpha": main["wrong_commit"] <= ALPHA,
        "C2_no_session_cp_lower_above_alpha": above_cp == 0,
        "C3_controls_commit_le_0.01": all(controls[c]["LTT max (primary)"]["commit_rate"] <= 0.01 for c in ("frame_shuffled", "uniform")),
        "commits_any": main["n_commit"] > 0,
    }
    ok = crit["C1_pooled_wrong_commit_le_alpha"] and crit["C2_no_session_cp_lower_above_alpha"] and crit["C3_controls_commit_le_0.01"]
    label = ("confirmed" if crit["commits_any"] else "uninformative") if ok else "not confirmed"
    res = {
        "preregistration_commit": CFG["preregistration_commit"], "trust_core_identical_to_tag": ident,
        "n": {"fit_a": len(fitA), "calibration": len(cal), "test": len(test)},
        "sessions": {"fit_a": fit_s, "calibration": cal_s, "test": test_s},
        "chars_per_min": cpm, "fit_report": pipe.fit_report, "plug_in_policy": plug_cfg.__dict__,
        "ltt": {"threshold": r.threshold, "feasible": r.feasible, "n": r.n, "bound": r.bound, "commit_p_final": lam_ltt},
        "trust_config_id": frozen.config_id, "lambdas": lams,
        "test_harness_metrics": ev, "primary": main, "rules": rules, "bootstrap_sessions": boot,
        "gain_vs_no_commits": {"point": rules["LTT max (primary)"]["ewpm"] - rules["no commits"]["ewpm"], "ci": pci(gain),
                               "sign_test": {"pos": pos, "neg": neg, "p": sign_p}},
        "gaze_ewpm": gz, "gain_vs_gaze": {"point": rules["LTT max (primary)"]["ewpm"] - gz, "ci": pci(gain_gaze)},
        "per_session": per_session, "sessions_above_alpha": above, "sessions_cp_lower_above_alpha": above_cp,
        "controls": controls, "criteria": crit, "outcome": label,
        "decoder_test_quality": {k: ev.get(k) for k in ("cer", "wer", "greedy_cer", "top1_sentence_acc", "guard_auroc")},
        "ledger_entries": len(led.entries) if hasattr(led, "entries") else None,
        "seconds": round(time.time() - t0, 1),
    }
    T.dump(res, marker)
    # per-trial records (no text in repo): outside
    T.dump([{"ref": it.ref, "actions": r_.actions, "wrong_commit": bool(r_.wrong_commit), "time_s": r_.time_s}
            for it, r_ in zip(test, recs)], DER / ("test-records.json" if part == "pool" else "dryrun-records.json"))
    log("OUTCOME", label, json.dumps(crit))


def f(x, nd=3):
    if x is None or (isinstance(x, str)) or (isinstance(x, float) and not math.isfinite(x)):
        return "—" if not isinstance(x, str) else x
    return f"{x:.{nd}f}"


def ci(c, nd=3):
    return "" if not c or c[0] is None else f" [{c[0]:.{nd}f}, {c[1]:.{nd}f}]"


def stage_tables() -> None:
    R = json.loads((OUT / "trust.json").read_text(encoding="utf-8"))
    P = json.loads((OUT / "prep.json").read_text(encoding="utf-8"))
    Dq = json.loads((OUT / "decoder.json").read_text(encoding="utf-8"))
    L = ["# Tables: confirmatory T12 test (M3-27)", "",
         f"Pre-registration: commit `{R['preregistration_commit'][:7]}`. Frozen trust config id `{R['trust_config_id']}`. Outcome: **{R['outcome']}**.", "",
         "## Data and splits", "", "| part | sessions | trials |", "|---|---|---|",
         f"| decoder train | {P['N']} | {P['n_decoder_train']} |", f"| decoder validation | {P['N']} | {P['n_decoder_val']} |",
         f"| fit-A (trust pool) | {P['n_fit_a_sessions']} | {R['n']['fit_a']} |",
         f"| calibration (trust pool) | {P['n_cal_sessions']} | {R['n']['calibration']} |",
         f"| test (trust pool) | {P['n_test_sessions']} | {R['n']['test']} |", "",
         f"Speech rate (decoder-train trials): {R['chars_per_min']:.1f} characters/min.", "",
         "## Decoder", "", "| set | n | greedy PER | CER | WER | sentence exact | truth in n-best |", "|---|---|---|---|---|---|---|"]
    q = Dq["decoder_validation"]
    L.append(f"| decoder validation | {q['n']} | {f(q['greedy_per_symbols'])} | {f(q['cer'])} | {f(q['wer'])} | {f(q['sentence_exact'])} | {f(q['truth_in_nbest'])} |")
    t = R["decoder_test_quality"]
    L.append(f"| test sessions | {R['n']['test']} | {f(t['greedy_cer'])} | {f(t['cer'])} | {f(t['wer'])} | {f(t['top1_sentence_acc'])} | — |")
    L += ["", "## Primary and secondary rules (test sessions)", "",
          "CP95: exact Clopper-Pearson; {..}: session-cluster bootstrap 95 % (B 2000, seed 20261112).", "",
          "| rule | λ | wrong-commit [CP95] {boot} | commit rate {boot} | EAC (wrong/commits) | silent | eWPM {boot} |", "|---|---|---|---|---|---|---|"]
    for k, m in R["rules"].items():
        b = R["bootstrap_sessions"][k]
        lam = R["lambdas"].get(k, "—")
        L.append(f"| {k} | {f(lam, 2) if not isinstance(lam, str) else lam} | {f(m['wrong_commit'], 4)}{ci(m['wrong_commit_cp95'])} {{{ci(b['wrong_commit']).strip(' []')}}} | "
                 f"{f(m['commit_rate'])} {{{ci(b['commit_rate']).strip(' []')}}} | {f(m['error_among_commits'])} ({m['n_wrong_commit']}/{m['n_commit']}) | "
                 f"{f(m['silent_error_rate'], 4)} | {f(m['ewpm'], 2)} {{{ci(b['ewpm'], 2).strip(' []')}}} |")
    g = R["gain_vs_no_commits"]
    L += ["", f"Gaze typing alone: {R['gaze_ewpm']:.2f} eWPM. Gain of LTT max over the same policy without commits: {g['point']:+.3f}{ci(g['ci'])} eWPM (sign test over sessions: {g['sign_test']['pos']}+ / {g['sign_test']['neg']}-, p = {g['sign_test']['p']:.3f}). Gain over gaze: {R['gain_vs_gaze']['point']:+.2f}{ci(R['gain_vs_gaze']['ci'], 2)}.", "",
          "## Per test session (P2, LTT max)", "", "| session | n | wrong commits | wrong-commit [CP95] | commit rate | > α |", "|---|---|---|---|---|---|"]
    for s, d in R["per_session"].items():
        m = d["LTT max (primary)"]
        L.append(f"| {s} | {m['n']} | {m['n_wrong_commit']} | {f(m['wrong_commit'], 3)}{ci(m['wrong_commit_cp95'])} | {f(m['commit_rate'])} | {'yes' if m['wrong_commit'] > ALPHA else 'no'} |")
    L += ["", f"Sessions above α: {R['sessions_above_alpha']} of {len(R['per_session'])}; with CP lower bound above α: {R['sessions_cp_lower_above_alpha']}.", "",
          "## Controls (P3)", "", "| control | rule | commits / n | one-sided CP95 upper | wrong commits |", "|---|---|---|---|---|"]
    for c, d in R["controls"].items():
        for k, m in d.items():
            L.append(f"| {c} | {k} | {m['n_commit']}/{m['n']} | {m['commit_cp95_one_sided_upper']:.4f} | {m['n_wrong_commit']} |")
    L += ["", "## Criteria", "", "| criterion | pass |", "|---|---|"] + [f"| {k} | {v} |" for k, v in R["criteria"].items()]
    L += ["", "## Fit", "", f"LTT: λ̂ = {R['ltt']['threshold']}, feasible {R['ltt']['feasible']}, n {R['ltt']['n']}; final commit_p = {R['ltt']['commit_p_final']}.",
          f"Fit report: frame T {f(R['fit_report'].get('temperature_frame'))}, sentence T {f(R['fit_report'].get('temperature_sentence'))}, conformal q {f(R['fit_report'].get('conformal_q'))}, policy fit feasible {R['fit_report'].get('policy_fit_feasible')}.",
          f"Trust core identical to tag `{CFG['frozen_tag']}`: {all(R['trust_core_identical_to_tag'].values())}."]
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["decoder", "trust", "dryrun", "tables"])
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.stage == "dryrun":
        stage_trust("val", "dryrun-trust.json", a.limit)
        return
    {"decoder": stage_decoder, "trust": stage_trust, "tables": stage_tables}[a.stage]()


if __name__ == "__main__":
    main()
