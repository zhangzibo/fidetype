"""M2-19: re-tune the trust config for the M4-12 decoder (pre-declared plan: plan.md). CPU, .venv.

Stages
------
fit       For each decoder (dedicated_0 primary, shared secondary): the Paper 1 v4 recipe on val_select
          (fit-A = positions 0::2 per session, clean cal = 1::2): pipe.fit(fitA, fitA) with risk_control none,
          then LTT alpha 0.05 delta 0.1 (combine max) on clean cal. Freeze -> configs/*.json (committed).
          Also the CRC sensitivity (dedicated_0). Reads val_select only.
eval      val_eval (701): StreamingTrustLayer (frames route) with each frozen config, batch equality,
          eWPM, action mix, always-commit, gaze. Only after `fit` wrote the configs.
controls  300-trial draw of val_eval (rng seed 0): frame-shuffled and uniform streams, dedicated_0 LTT config.
tables    results/tables.md

Run (repo root): .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
                 .venv\\Scripts\\python.exe -I experiments/2026-11-15-m2-19-trust-retune/run.py fit eval controls tables
Per-trial outputs go to C:/Users/zhang/bci-data/derived/m2-19-trust-retune only. The repo gets aggregates + configs.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from dataclasses import replace  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "2026-11-14-m4-12-decoder-retrain"))
import t15 as T  # noqa: E402  (read-only: paths, texts, sessions)

T.below_normal_priority()
sys.path.insert(0, str(T.REPO / "experiments/2026-11-12-paper1-r1-analyses"))
import common as C  # noqa: E402

from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.eval.ewpm import summarize  # noqa: E402
from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline  # noqa: E402
from fidetype.interact.simulated_user import UserConfig  # noqa: E402
from fidetype.streams.spec import NeuralTextStream  # noqa: E402
from fidetype.trust.frozen import PAPER1_V4_RECIPE, FrozenTrustConfig, paper1_v4_harness_config  # noqa: E402
from fidetype.trust.guard import shuffle_stream, uniform_stream  # noqa: E402
from fidetype.trust.policy import Action  # noqa: E402
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer  # noqa: E402

B = T.B
DER_IN = T.DERIVED  # M4-01/02 derived inputs: READ ONLY
OWN = Path("C:/Users/zhang/bci-data/derived/m2-19-trust-retune")  # the only place this task writes per-trial files
assert OWN.name == "m2-19-trust-retune"
OWN.mkdir(parents=True, exist_ok=True)
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
CFG_DIR = HERE / "configs"
CFG_DIR.mkdir(exist_ok=True)
LOGF = OUT / "run.log"
OLD_CFG = T.REPO / "experiments/2026-11-13-m4-06-real-replay/configs/trust-config-b2t25-ours-splitA.json"
DECODERS = {"dedicated_0": "m4-12-fixed0", "shared": "m4-12-shared"}
ALPHA, DELTA, SEED = 0.05, 0.1, 0
GAZE_CPM = 20.0


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def cp(k: int, n: int, level: float = 0.95) -> list:
    from scipy.stats import beta
    if n == 0:
        return [None, None]
    a = 1 - level
    lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return [lo, hi]


class Ctx:
    def __init__(self) -> None:
        self.bt = C.load_module("b2t25run", T.REPO / "experiments/2026-11-10-b2t25-trust/run.py")
        prep = self.bt.load_json("prep.json")
        tune = self.bt.load_json("tune.json")
        self.dec = self.bt.Decoders([], {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
        self.cpm = prep["speech_rate_125k"]["chars_per_min"]
        self.user = UserConfig.aac_gaze(chars_per_min=self.cpm)
        self.texts = T.texts()
        self.sessions = T.sessions()
        self.cache_path = OWN / "m2-19-word-decode-cache.pkl"
        self.cache: dict = pickle.loads(self.cache_path.read_bytes()) if self.cache_path.exists() else {}
        self.new = 0
        self._npz: dict = {}

    def words_fn(self, stream):
        k = hashlib.sha1(np.ascontiguousarray(stream.log_probs, dtype=np.float32).tobytes()).hexdigest()
        hit = self.cache.get(k)
        if hit is None:
            self.dec._wcache = {}
            hit = self.dec.words_fn(stream)
            self.cache[k] = hit
            self.new += 1
            if self.new % 200 == 0:
                self.save()
        return hit

    def save(self) -> None:
        if self.new:
            tmp = self.cache_path.with_suffix(".tmp")
            tmp.write_bytes(pickle.dumps(self.cache, protocol=pickle.HIGHEST_PROTOCOL))
            os.replace(tmp, self.cache_path)
            self.new = 0

    def ph(self, s: str, part: str, i: int) -> np.ndarray:
        if s not in self._npz:
            self._npz[s] = np.load(DER_IN / f"{s}.npz")
        return self._npz[s][f"{part}_ph{i}"]

    def items(self, which: str, part: str):
        """Items of a part in session order (sessions.json), index order; plus their keys."""
        run = DECODERS[which]
        z = np.load(OWN / f"logprobs-m2-19-{run}.npz")
        order = {s: j for j, s in enumerate(self.sessions)}
        keys = sorted({k.rsplit("|", 1)[0] for k in z.files if f"|{part}|" in k},
                      key=lambda k: (order[k.split("|")[0]], int(k.split("|")[2])))
        meta = json.loads((OWN / f"decode-m2-19-{run}.json").read_text(encoding="utf-8"))
        items = []
        base = 0 if part == "val_select" else 100000
        for gi, key in enumerate(keys):
            s, p, i = key.split("|")
            st = make_stream(z[f"{key}|L0"], key, run, base + gi, meta["model_config"])
            ph = self.ph(s, p, int(i))
            items.append(Item(st, self.texts[s][p][int(i)], stream_text=B.phonemes_to_symbols([B.VOCAB[j] for j in ph])))
        return items, keys

    def pipe_from(self, fz: FrozenTrustConfig) -> TrustPipeline:
        comp = fz.build()
        p = TrustPipeline(self.words_fn, HarnessConfig(seed=SEED, user_config=self.user, max_attempts=1), {})
        p.frame_scaler, p.calibrator, p.conformal, p.guard, p.policy = (
            comp.frame_scaler, comp.calibrator, comp.conformal, comp.guard, comp.policy)
        return p


def make_stream(lp: np.ndarray, key: str, run: str, gidx: int, cfgm) -> NeuralTextStream:
    s = key.split("|")[0]
    n = lp.shape[0]
    meta = {
        "device.modality": "intracortical", "device.channel_count": 256, "device.invasive": True,
        "device.regulatory_status": "investigational",
        "decoder.name": "fidetype-t15-lookahead-gru-ctc", "decoder.version": run,
        "decoder.causal": True, "decoder.lookahead_s": 0.0, "decoder.calibration_method": "none",
        "adapter.name": "experiments/2026-11-15-m2-19-trust-retune", "adapter.version": FT_VERSION, "lm.name": "none",
        "user.personalized": True, "calibration.applied": False, "subject.id": "T15", "session.id": s,
        "language": "en-US", "data.derived": True,
        "stream.id": hashlib.sha256(f"{run}/{key}/L0".encode()).hexdigest()[:32],
        "fidetype.vocab_id": B.VOCAB_ID, "fidetype.trial_index": gidx,
        "fidetype.timing": f"exact: 80 ms frames, frame time = end of the {cfgm['patch']} x 20 ms patch; L 0",
        "source.dataset": "Card et al. 2024 / B2T '25 t15_copyTask_neuralData (CC0)",
    }
    st = NeuralTextStream(log_probs=lp.astype(np.float32), frame_times=(np.arange(n) * cfgm["stride"] + cfgm["patch"]) * 0.02,
                          vocab=list(B.VOCAB), blank_id=0, source="t15-lookahead-gru-L0", meta=meta, vocab_type="phoneme",
                          frame_period=0.08, latency=0.0)
    return B.to_symbol_stream(st)


def split_val_select(items, keys):
    """fit-A = positions 0::2 inside each session, clean cal = 1::2 (session order kept)."""
    by_s: dict = {}
    for j, k in enumerate(keys):
        by_s.setdefault(k.split("|")[0], []).append(j)
    A, Cc = [], []
    for s in by_s:  # insertion order = session order
        A += by_s[s][0::2]
        Cc += by_s[s][1::2]
    return [items[j] for j in A], [items[j] for j in Cc]


def cfg_path(which: str, method: str) -> Path:
    return CFG_DIR / f"trust-config-t15-m4-12-{which}-{method}.json"


def recipe(which: str, method: str, nA: int, nC: int) -> dict:
    r = dict(PAPER1_V4_RECIPE)
    r["risk_control"] = dict(r["risk_control"], method=method)
    r.update({"name": f"m2-19-{method}", "experiment": "experiments/2026-11-15-m2-19-trust-retune",
              "decoder": f"{DECODERS[which]} best.pt (M4-12) at L 0 -> experiments/2026-11-10-b2t25-trust Decoders.words_fn",
              "fitted_on": f"B2T '25 T15 neural data val_select (even-index val trials): fit-A = positions 0::2 per session ({nA}), "
                           f"clean calibration = 1::2 ({nC}); val_eval (odd-index val) held out"})
    return r


# ---------------------------------------------------------------------------
# fit
# ---------------------------------------------------------------------------


def calib_side(pipe: TrustPipeline, items) -> dict:
    recs = pipe.run_items(items)
    n = len(recs)
    ncom = sum(r.actions[-1:] == ["COMMIT"] for r in recs)
    nwr = sum(bool(r.wrong_commit) for r in recs)
    return {"n": n, "n_commit": ncom, "commit_rate": ncom / n, "n_wrong_commit": nwr, "wrong_commit": nwr / n}


def stage_fit() -> dict:
    ctx = Ctx()
    res: dict = {"alpha": ALPHA, "delta": DELTA, "conditions": {}}
    for which in DECODERS:
        items, keys = ctx.items(which, "val_select")
        fitA, cal = split_val_select(items, keys)
        res["n_val_select"], res["n_fitA"], res["n_cal"] = len(items), len(fitA), len(cal)
        v4 = paper1_v4_harness_config(seed=SEED, user_config=ctx.user)
        assert v4.max_wrong_commit == ALPHA and v4.risk_control_delta == DELTA and v4.risk_control == "ltt"
        t0 = time.time()
        pipe = TrustPipeline(ctx.words_fn, replace(v4, risk_control="none"), {})
        pipe.fit(fitA, fitA)
        grid_policy = pipe.policy
        grid_report = C.clean(dict(pipe.fit_report))
        ctx.save()
        methods = ["ltt", "crc"] if which == "dedicated_0" else ["ltt"]
        for method in methods:
            pipe.policy = grid_policy
            pipe.config = v4
            r = pipe.calibrate_commit(cal, method=method)
            fz = FrozenTrustConfig.from_pipeline(pipe, name=f"t15-m4-12-{which}-m2-19-{method}",
                                                 recipe=recipe(which, method, len(fitA), len(cal)))
            fz.save(cfg_path(which, method))
            assert FrozenTrustConfig.load(cfg_path(which, method)).config_id == fz.config_id
            row = {"config_id": fz.config_id, "method": r.method, "lambda_hat": r.threshold, "feasible": r.feasible,
                   "bound": r.bound, "n_cal": r.n, "grid_commit_p": grid_policy.config.commit_p,
                   "final_commit_p": fz.policy["commit_p"], "policy": fz.policy, "frame_T": fz.frame_temperature,
                   "sentence_T": fz.sentence_temperature, "conformal_q": fz.conformal_q, "risk_control": fz.risk_control,
                   "fit_report": C.clean(dict(pipe.fit_report)), "grid_fit_report": grid_report}
            pc = ctx.pipe_from(fz)
            row["fitA_side"] = calib_side(pc, fitA)
            row["cal_side"] = calib_side(pc, cal)
            row["seconds"] = round(time.time() - t0, 1)
            res["conditions"][f"{which}/{method}"] = row
            log(f"fit {which}/{method}: {fz.config_id} grid commit_p {row['grid_commit_p']} lambda_hat {r.threshold} "
                f"(feasible {r.feasible}, bound {r.bound}) -> commit_p {row['final_commit_p']}; frame T {fz.frame_temperature:.4f}; "
                f"cal commit {row['cal_side']['n_commit']}/{row['cal_side']['n']} wrong {row['cal_side']['n_wrong_commit']}")
            ctx.save()
        T.dump(res, OUT / "fit.json")
    return res


# ---------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------


class ReplayPolicy:
    def __init__(self, decs) -> None:
        self.it = iter(decs)

    def decide(self, inputs, final_attempt=False):
        d = next(self.it)
        assert tuple(d.inputs.texts) == tuple(inputs.texts), "replayed decision belongs to another n-best"
        return d.decision


def events_of(st: NeuralTextStream) -> list[dict]:
    h = {"type": "header", "spec_version": st.version, "vocab": list(st.vocab), "vocab_type": st.vocab_type,
         "blank_id": st.blank_id, "source": st.source, "frame_period": st.frame_period, "latency": st.latency, "meta": dict(st.meta)}
    ev = [h] + [{"type": "frame", "t": float(t), "log_probs": [None if v == -math.inf else float(v) for v in row]}
                for t, row in zip(st.frame_times, st.log_probs)]
    return ev + [{"type": "end"}]


def evaluate(ctx: Ctx, fz: FrozenTrustConfig, items) -> tuple[dict, list]:
    layer = StreamingTrustLayer(fz, decode_fn=ctx.words_fn, streaming=StreamingConfig(route="frames", max_attempts=1))
    decs = []
    for it in items:
        sid = it.stream(0).meta["session.id"]
        got = []
        for ev in events_of(it.stream(0)):
            got += layer.push(ev, sid)
        fin = [d for d in got if d.final]
        assert len(fin) == 1
        decs.append(fin[0])
    pipe = ctx.pipe_from(fz)
    recs = pipe.run_items(items, ReplayPolicy(decs))
    brecs = ctx.pipe_from(fz).run_items(items)
    eq = sum(a.actions == b.actions and a.committed_text == b.committed_text for a, b in zip(recs, brecs))
    m = summarize(recs)
    n = len(recs)
    ncom = sum(d.action == Action.COMMIT for d in decs)
    nwr = sum(bool(x.wrong_commit) for x in recs)
    nempty = sum(x.committed_text is not None and x.committed_text.strip() == "" for x in recs)
    out = {"config_id": fz.config_id, "n": n, "n_commit": ncom, "commit_rate": ncom / n, "commit_rate_cp95": cp(ncom, n),
           "n_wrong_commit": nwr, "wrong_commit": nwr / n, "wrong_commit_cp95": cp(nwr, n),
           "error_among_commits": (nwr / ncom) if ncom else None, "error_among_commits_cp95": cp(nwr, ncom),
           "guarantee_point_holds": nwr / n <= ALPHA, "guarantee_cp_upper_holds": cp(nwr, n)[1] <= ALPHA,
           "n_commit_empty": nempty, "ewpm": m["ewpm"], "silent_error": m["silent_error_rate"],
           "rate_offer": m["rate_offer"], "abstain_rate": m["abstain_rate"], "stream_equals_batch": eq,
           "actions": {a: sum(d.action.value == a for d in decs) for a in ("COMMIT", "OFFER", "ASK", "ABSTAIN", "OFFER_WORDS")}}
    return out, decs


def stage_eval() -> dict:
    ctx = Ctx()
    fit = json.loads((OUT / "fit.json").read_text(encoding="utf-8"))
    res: dict = {"alpha": ALPHA, "delta": DELTA, "conditions": {}, "baselines": {}}
    old = FrozenTrustConfig.load(OLD_CFG)
    for which in DECODERS:
        items, keys = ctx.items(which, "val_eval")
        n = len(items)
        for name in [k for k in fit["conditions"] if k.startswith(which + "/")]:
            method = name.split("/")[1]
            fz = FrozenTrustConfig.load(cfg_path(which, method))
            assert fz.config_id == fit["conditions"][name]["config_id"]
            t0 = time.time()
            r, decs = evaluate(ctx, fz, items)
            r["seconds"] = round(time.time() - t0, 1)
            res["conditions"][name] = r
            T.dump({"keys": keys, "decisions": [d.to_event(include_text=True) for d in decs]}, OWN / f"m2-19-decisions-{which}-{method}.json")
            log(f"eval {name}: commit {r['n_commit']}/{n} wrong {r['n_wrong_commit']} ({r['wrong_commit']:.4f}, CP95 "
                f"[{r['wrong_commit_cp95'][0]:.4f}, {r['wrong_commit_cp95'][1]:.4f}]) eWPM {r['ewpm']:.2f}; actions {r['actions']}; "
                f"stream==batch {r['stream_equals_batch']}/{n}")
            ctx.save()
            T.dump(res, OUT / "eval.json")
        # baselines with the primary (LTT) config's frame temperature
        fz = FrozenTrustConfig.load(cfg_path(which, "ltt"))
        allc = TrustPipeline(ctx.words_fn, HarnessConfig(seed=SEED, user_config=ctx.user, max_attempts=1, policy="always_commit"), {})
        allc.frame_scaler = ctx.pipe_from(fz).frame_scaler
        ar = allc.run_items(items)
        nwr = sum(bool(x.wrong_commit) for x in ar)
        b = {"always_commit": {"ewpm": summarize(ar)["ewpm"], "n_wrong_commit": nwr, "wrong_commit": nwr / n, "wrong_commit_cp95": cp(nwr, n),
                               "n_correct": n - nwr},
             "gaze_ewpm": 60.0 * sum(len(it.text.split()) for it in items) / (sum(len(it.text) for it in items) * 60.0 / GAZE_CPM)}
        ro, _ = evaluate(ctx, old, items)
        b["old_frozen"] = ro
        res["baselines"][which] = b
        log(f"baselines {which}: always-commit eWPM {b['always_commit']['ewpm']:.2f} wrong {nwr}/{n}; gaze {b['gaze_ewpm']:.2f}; "
            f"old frozen commit {ro['n_commit']} eWPM {ro['ewpm']:.2f}")
        ctx.save()
        T.dump(res, OUT / "eval.json")
    return res


# ---------------------------------------------------------------------------
# controls
# ---------------------------------------------------------------------------


def stage_controls() -> dict:
    ctx = Ctx()
    items, _ = ctx.items("dedicated_0", "val_eval")
    rng = np.random.default_rng(SEED)
    idx = sorted(rng.choice(len(items), 300, replace=False).tolist())
    sub = [items[i] for i in idx]
    res: dict = {"n": len(sub), "conditions": {}}
    fz = FrozenTrustConfig.load(cfg_path("dedicated_0", "ltt"))
    variants = {"real": [it.stream(0) for it in sub],
                "frame_shuffled": [shuffle_stream(it.stream(0), rng) for it in sub],
                "uniform": [uniform_stream(it.stream(0), rng, 0.05) for it in sub]}
    for name, streams in variants.items():
        its = [Item(s, it.text, stream_text=it.stream_text) for s, it in zip(streams, sub)]
        recs = ctx.pipe_from(fz).run_items(its)
        ncom = sum(r.actions[-1:] == ["COMMIT"] for r in recs)
        res["conditions"][name] = {"n_commit": ncom, "commit_cp95_upper": cp(ncom, len(its))[1],
                                   "n_wrong_commit": sum(bool(r.wrong_commit) for r in recs)}
        log(f"controls {name}: commits {ncom}/{len(its)}")
        ctx.save()
    res["config_id"] = fz.config_id
    T.dump(res, OUT / "controls.json")
    return res


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------


def f(x, d=3):
    return "—" if x is None else f"{x:.{d}f}"


def stage_tables() -> None:
    fit = json.loads((OUT / "fit.json").read_text(encoding="utf-8"))
    ev = json.loads((OUT / "eval.json").read_text(encoding="utf-8"))
    ctl = json.loads((OUT / "controls.json").read_text(encoding="utf-8")) if (OUT / "controls.json").exists() else None
    L = ["# M2-19 tables (generated by run.py tables)", "",
         f"val_select {fit['n_val_select']} = fit-A {fit['n_fitA']} + clean cal {fit['n_cal']}; alpha {ALPHA}, delta {DELTA}.", "",
         "## Fitted configs", "",
         "| decoder / method | config_id | frame T | sentence T | grid commit_p | lambda_hat (feasible) | final commit_p | commit_max_risk | offer_max_k | abstain_risk | fallback | cal commit (wrong) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, r in fit["conditions"].items():
        p = r["policy"]
        L.append(f"| {k} | `{r['config_id']}` | {f(r['frame_T'], 4)} | {f(r['sentence_T'], 4)} | {r['grid_commit_p']} | "
                 f"{r['lambda_hat']} ({r['feasible']}) | {r['final_commit_p']} | {p['commit_max_risk']} | {p['offer_max_k']} | "
                 f"{p['abstain_risk']} | {p['final_fallback']} | {r['cal_side']['n_commit']}/{r['cal_side']['n']} "
                 f"({r['cal_side']['n_wrong_commit']}) |")
    L += ["", "## val_eval (held out)", "",
          "| decoder / config | n | commit (rate) | wrong-commit (rate) [CP95] | error among commits | wrong <= alpha | CP95 upper <= alpha | eWPM | COMMIT / OFFER / ASK / ABSTAIN | stream = batch |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for k, r in ev["conditions"].items():
        a = r["actions"]
        L.append(f"| {k} | {r['n']} | {r['n_commit']} ({f(r['commit_rate'])}) | {r['n_wrong_commit']} ({f(r['wrong_commit'], 4)}) "
                 f"[{f(r['wrong_commit_cp95'][0], 4)}, {f(r['wrong_commit_cp95'][1], 4)}] | {f(r['error_among_commits'])} | "
                 f"{r['guarantee_point_holds']} | {r['guarantee_cp_upper_holds']} | {f(r['ewpm'], 2)} | "
                 f"{a['COMMIT']} / {a['OFFER']} / {a['ASK']} / {a['ABSTAIN']} | {r['stream_equals_batch']}/{r['n']} |")
    for k, b in ev["baselines"].items():
        o = b["old_frozen"]
        L.append(f"| {k} / old frozen `{o['config_id']}` | {o['n']} | {o['n_commit']} ({f(o['commit_rate'])}) | {o['n_wrong_commit']} "
                 f"({f(o['wrong_commit'], 4)}) | {f(o['error_among_commits'])} | {o['guarantee_point_holds']} | {o['guarantee_cp_upper_holds']} | "
                 f"{f(o['ewpm'], 2)} | {o['actions']['COMMIT']} / {o['actions']['OFFER']} / {o['actions']['ASK']} / {o['actions']['ABSTAIN']} | "
                 f"{o['stream_equals_batch']}/{o['n']} |")
    L += ["", "## Baselines (val_eval)", "", "| decoder | always-commit eWPM | always-commit wrong-commit | gaze eWPM |", "|---|---|---|---|"]
    for k, b in ev["baselines"].items():
        L.append(f"| {k} | {f(b['always_commit']['ewpm'], 2)} | {f(b['always_commit']['wrong_commit'], 4)} | {f(b['gaze_ewpm'], 2)} |")
    if ctl:
        L += ["", f"## Controls (dedicated_0 LTT `{ctl['config_id']}`, {ctl['n']}-trial draw of val_eval, seed 0)", "",
              "| input | commits | one-sided-ish CP95 upper |", "|---|---|---|"]
        for k, r in ctl["conditions"].items():
            L.append(f"| {k} | {r['n_commit']}/{ctl['n']} | {f(r['commit_cp95_upper'], 4)} |")
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    stages = sys.argv[1:] or ["fit", "eval", "controls", "tables"]
    for st in stages:
        log(f"stage {st} start (fidetype {FT_VERSION})")
        {"fit": stage_fit, "eval": stage_eval, "controls": stage_controls, "tables": stage_tables}[st]()
        log(f"stage {st} done")
