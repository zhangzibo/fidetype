"""M4-13 final evaluation on val_eval (CPU, .venv). Run ONCE, after training and decode.py.

Same logic as the M4-12 accuracy stage (experiments/2026-11-14-m4-12-decoder-retrain/run.py) and the M2-19
eval / controls stages (experiments/2026-11-15-m2-19-trust-retune/run.py, posthoc_gate.py); code copied
here so that every per-trial file goes to C:/Users/zhang/bci-data/derived/m4-13 only.

- greedy PER (phonemes), word route WER / sentence exact / truth in n-best at T = 1 and at the frame T
  of the trust config
- trust: the M2-19 dedicated L 0 LTT config tcfg-e7e8c472f6d9ab33 WITH the M2-18 commit gate
  (min_chars 1, min_words 0, max_guard_risk 1.0) = tcfg-4e6143e37d1642f3; not refitted. StreamingTrustLayer
  (frames route), stream = batch check, eWPM, wrong-commit with CP95, empty commits. Also the ungated
  config for reference, always-commit and gaze baselines.
- null controls: 300-trial draw of val_eval (rng seed 0): real, frame-shuffled, uniform (jitter 0.05),
  gated and ungated config.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-15-m4-13-long-train/eval.py [--logprobs PATH] [--out DIR]
--logprobs / --out: dry run on another decoder's val_eval log-probs (results go to --out, not results/).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t15 as T  # noqa: E402

T.below_normal_priority()
sys.path.insert(0, str(T.REPO / "experiments/2026-11-12-paper1-r1-analyses"))
import common as C  # noqa: E402

from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.eval.ewpm import summarize  # noqa: E402
from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline  # noqa: E402
from fidetype.eval.metrics import ctc_greedy_decode, edit_distance  # noqa: E402
from fidetype.interact.simulated_user import UserConfig  # noqa: E402
from fidetype.streams.spec import NeuralTextStream  # noqa: E402
from fidetype.trust.frozen import FrozenTrustConfig  # noqa: E402
from fidetype.trust.guard import shuffle_stream, uniform_stream  # noqa: E402
from fidetype.trust.policy import Action  # noqa: E402
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer  # noqa: E402

B = T.B
CFG = T.CONFIG
OWN = T.OWN
assert OWN.name == "m4-13"
OWN.mkdir(parents=True, exist_ok=True)
RUN = CFG["runs"]["dedicated_0"]["run"]
ALPHA = 0.05
SEED = int(CFG["trust"]["seed"])
LOGF = None


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
    def __init__(self, cache_name: str) -> None:
        self.bt = C.load_module("b2t25run", T.REPO / "experiments/2026-11-10-b2t25-trust/run.py")
        prep = self.bt.load_json("prep.json")
        tune = self.bt.load_json("tune.json")
        self.dec = self.bt.Decoders([], {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
        self.cpm = prep["speech_rate_125k"]["chars_per_min"]
        self.user = UserConfig.aac_gaze(chars_per_min=self.cpm)
        self.texts = T.texts()
        self.sessions = T.sessions()
        self.cache_path = OWN / cache_name
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
            self._npz[s] = np.load(T.DERIVED / f"{s}.npz")
        return self._npz[s][f"{part}_ph{i}"]

    def items(self, lp_path: Path, model_config: dict):
        z = np.load(lp_path)
        order = {s: j for j, s in enumerate(self.sessions)}
        keys = sorted({k.rsplit("|", 1)[0] for k in z.files if "|val_eval|" in k},
                      key=lambda k: (order[k.split("|")[0]], int(k.split("|")[2])))
        items = []
        for gi, key in enumerate(keys):
            s, p, i = key.split("|")
            st = make_stream(z[f"{key}|L0"], key, 100000 + gi, model_config)
            ph = self.ph(s, p, int(i))
            items.append(Item(st, self.texts[s][p][int(i)], stream_text=B.phonemes_to_symbols([B.VOCAB[j] for j in ph])))
        return items, keys

    def pipe_from(self, fz: FrozenTrustConfig) -> TrustPipeline:
        comp = fz.build()
        p = TrustPipeline(self.words_fn, HarnessConfig(seed=SEED, user_config=self.user, max_attempts=1), {})
        p.frame_scaler, p.calibrator, p.conformal, p.guard, p.policy = (
            comp.frame_scaler, comp.calibrator, comp.conformal, comp.guard, comp.policy)
        return p


def make_stream(lp: np.ndarray, key: str, gidx: int, cfgm) -> NeuralTextStream:
    s = key.split("|")[0]
    n = lp.shape[0]
    meta = {
        "device.modality": "intracortical", "device.channel_count": 256, "device.invasive": True,
        "device.regulatory_status": "investigational",
        "decoder.name": "fidetype-t15-lookahead-gru-ctc", "decoder.version": RUN,
        "decoder.causal": True, "decoder.lookahead_s": 0.0, "decoder.calibration_method": "none",
        "adapter.name": "experiments/2026-11-15-m4-13-long-train", "adapter.version": FT_VERSION, "lm.name": "none",
        "user.personalized": True, "calibration.applied": False, "subject.id": "T15", "session.id": s,
        "language": "en-US", "data.derived": True,
        "stream.id": hashlib.sha256(f"{RUN}/{key}/L0".encode()).hexdigest()[:32],
        "fidetype.vocab_id": B.VOCAB_ID, "fidetype.trial_index": gidx,
        "fidetype.timing": f"exact: 80 ms frames, frame time = end of the {cfgm['patch']} x 20 ms patch; L 0",
        "source.dataset": "Card et al. 2024 / B2T '25 t15_copyTask_neuralData (CC0)",
    }
    st = NeuralTextStream(log_probs=lp.astype(np.float32), frame_times=(np.arange(n) * cfgm["stride"] + cfgm["patch"]) * 0.02,
                          vocab=list(B.VOCAB), blank_id=0, source="t15-lookahead-gru-L0", meta=meta, vocab_type="phoneme",
                          frame_period=0.08, latency=0.0)
    return B.to_symbol_stream(st)


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


def word_quality(fn, items, scale_T: float) -> dict:
    from fidetype.trust.calibration import TemperatureScaler
    sc = TemperatureScaler()
    sc.temperature = scale_T
    n_c = n_w = e_c = e_w = ex = inb = 0
    for it in items:
        st = it.stream(0)
        nb = fn(sc.transform_stream(st) if scale_T != 1.0 else st)
        top = nb.texts[0] if len(nb) else ""
        e_c += edit_distance(it.text, top)
        n_c += len(it.text)
        e_w += edit_distance(it.text.split(), top.split())
        n_w += len(it.text.split())
        ex += top == it.text
        inb += it.text in nb.texts
    n = len(items)
    return {"cer": e_c / max(1, n_c), "wer": e_w / max(1, n_w), "sentence_exact": ex / max(1, n), "n_exact": ex,
            "truth_in_nbest": inb / max(1, n)}


def greedy_per(items) -> dict:
    pe = pn = 0
    for it in items:
        g = ctc_greedy_decode(it.stream(0))
        pe += edit_distance(it.stream_text, g)
        pn += len(it.stream_text)
    return {"per": pe / max(1, pn), "n_symbols": pn, "n_edits": pe}


def trust_eval(ctx: Ctx, fz: FrozenTrustConfig, items) -> tuple[dict, list]:
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
    recs = ctx.pipe_from(fz).run_items(items, ReplayPolicy(decs))
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


def main() -> None:
    global LOGF
    ap = argparse.ArgumentParser()
    ap.add_argument("--logprobs", default=None, help="dry run: another val_eval log-prob file (read only)")
    ap.add_argument("--decode-meta", default=None, help="dry run: its decode json (model_config)")
    ap.add_argument("--out", default=None, help="dry run: output folder (default results/)")
    a = ap.parse_args()
    dry = a.logprobs is not None
    out_dir = Path(a.out) if a.out else HERE / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    LOGF = out_dir / "eval.log"
    lp_path = Path(a.logprobs) if dry else OWN / f"logprobs-{RUN}-val_eval.npz"
    meta_path = Path(a.decode_meta) if dry else OWN / f"decode-{RUN}-val_eval.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    ctx = Ctx("dryrun-word-decode-cache.pkl" if dry else "word-decode-cache.pkl")
    items, keys = ctx.items(lp_path, meta["model_config"])
    n = len(items)
    log(f"eval start (fidetype {FT_VERSION}) dry={dry} n={n} logprobs={lp_path}")
    base = FrozenTrustConfig.load(T.REPO / CFG["trust"]["m2_19_config"])
    assert base.config_id == CFG["trust"]["m2_19_config_id"], base.config_id
    g = CFG["trust"]["commit_gate"]
    gated = base.with_commit_gate(g["min_chars"], g["min_words"], g["max_guard_risk"])
    assert gated.config_id == CFG["trust"]["gated_config_id_expected"], gated.config_id
    res: dict = {"dry_run": dry, "n": n, "logprobs": str(lp_path), "checkpoint_sha256": meta.get("checkpoint_sha256"),
                 "step": meta.get("step"), "val_select_per": meta.get("val_select_per"), "fidetype": FT_VERSION,
                 "base_config_id": base.config_id, "gated_config_id": gated.config_id, "commit_gate": gated.commit_gate,
                 "reference": {"m4_12_dedicated_0_per": 0.2574, "published_val_per": 0.101, "published_online_per": 0.0954,
                               "close_rule": "val_eval greedy PER <= 0.101 + 0.05 = 0.151"}}
    t0 = time.time()
    res["greedy"] = greedy_per(items)
    res["close"] = res["greedy"]["per"] <= 0.151
    log(f"greedy PER {res['greedy']['per']:.4f} (close={res['close']})")
    res["words_T1"] = word_quality(ctx.words_fn, items, 1.0)
    res["words_cfgT"] = word_quality(ctx.words_fn, items, base.frame_temperature)
    ctx.save()
    log(f"WER T1 {res['words_T1']['wer']:.4f} exact {res['words_T1']['sentence_exact']:.3f}; WER cfgT "
        f"{res['words_cfgT']['wer']:.4f} exact {res['words_cfgT']['sentence_exact']:.3f}")
    res["trust"] = {}
    for tag, fz in (("gated", gated), ("ungated", base)):
        r, decs = trust_eval(ctx, fz, items)
        res["trust"][tag] = r
        T.dump({"keys": keys, "decisions": [d.to_event(include_text=True) for d in decs]},
               OWN / f"{'dryrun-' if dry else ''}m4-13-decisions-{tag}.json")
        ctx.save()
        log(f"trust {tag} {fz.config_id}: commit {r['n_commit']}/{n} wrong {r['n_wrong_commit']} ({r['wrong_commit']:.4f} CP95 "
            f"[{r['wrong_commit_cp95'][0]:.4f}, {r['wrong_commit_cp95'][1]:.4f}]) empty {r['n_commit_empty']} eWPM {r['ewpm']:.2f} "
            f"stream==batch {r['stream_equals_batch']}/{n}")
    allc = TrustPipeline(ctx.words_fn, HarnessConfig(seed=SEED, user_config=ctx.user, max_attempts=1, policy="always_commit"), {})
    allc.frame_scaler = ctx.pipe_from(base).frame_scaler
    ar = allc.run_items(items)
    nwr = sum(bool(x.wrong_commit) for x in ar)
    res["baselines"] = {"always_commit": {"ewpm": summarize(ar)["ewpm"], "n_wrong_commit": nwr, "wrong_commit": nwr / n},
                        "gaze_ewpm": 60.0 * sum(len(it.text.split()) for it in items)
                        / (sum(len(it.text) for it in items) * 60.0 / CFG["gaze_chars_per_min"])}
    # null controls
    rng = np.random.default_rng(SEED)
    idx = sorted(rng.choice(n, CFG["trust"]["controls_n"], replace=False).tolist())
    sub = [items[i] for i in idx]
    variants = {"real": [it.stream(0) for it in sub],
                "frame_shuffled": [shuffle_stream(it.stream(0), rng) for it in sub],
                "uniform": [uniform_stream(it.stream(0), rng, 0.05) for it in sub]}
    res["controls"] = {"n": len(sub), "conditions": {}}
    for name, streams in variants.items():
        for tag, fz in (("gated", gated), ("ungated", base)):
            recs = ctx.pipe_from(fz).run_items([Item(s, it.text, stream_text=it.stream_text) for s, it in zip(streams, sub)])
            com = [x for x in recs if x.actions[-1:] == ["COMMIT"]]
            res["controls"]["conditions"][f"{name}/{tag}"] = {
                "n_commit": len(com), "n_commit_empty": sum((x.committed_text or "").strip() == "" for x in com),
                "n_wrong_commit": sum(bool(x.wrong_commit) for x in recs), "commit_cp95_upper": cp(len(com), len(recs))[1]}
            log(f"controls {name}/{tag}: commits {len(com)}/{len(sub)}")
        ctx.save()
    c = res["controls"]["conditions"]
    res["controls_pass_gated"] = c["uniform/gated"]["n_commit"] == 0 and c["frame_shuffled/gated"]["n_commit"] == 0
    res["seconds"] = round(time.time() - t0, 1)
    T.dump(res, out_dir / "eval.json")
    log(f"eval done in {res['seconds']:.0f} s; controls pass (gated) = {res['controls_pass_gated']}")


if __name__ == "__main__":
    main()
