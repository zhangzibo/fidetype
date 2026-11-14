"""M4-02: accuracy, trust outcomes and latency against the lookahead L (CPU, .venv).

Stages
------
accuracy  For every decoded condition (run, L): greedy PER; word route (frozen frame
          temperature, as the trust layer decodes) WER / sentence exact / truth in n-best,
          and the same at T = 1; trust outcomes of the frozen v4 config 'ours' (M4-06,
          tcfg-f5ca0020b3b8fce2) through StreamingTrustLayer (frames route), with eWPM
          from the harness user simulation fed the streaming decisions (as M4-06).
emission  Phoneme emission times of the greedy CTC path. A phoneme is *available* at its
          first frame's stamp + L. We compare matched phonemes across L (relative to L = 0).
latency   (only after the M6-13 soak test) raw 20 ms bins -> StreamingLookaheadGRU (NumPy)
          -> NTS frames -> StreamingTrustLayer with the incremental CTC beam + word decoder.
          Compute per bin push, per frame push, and at the end of the utterance. Inside
          fidetype.utils.isolation.isolated("timing").
tables    results/tables.md

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-13-m4-01-02-lookahead/run.py <stage> [...]
Per-trial outputs go to DERIVED (outside the repo). The repo gets aggregate numbers only.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "4"

import gc  # noqa: E402
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
from fidetype.trust.policy import Action  # noqa: E402
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer  # noqa: E402

B = T.B
CFG = T.CONFIG
OUT = Path(os.environ.get("M4_OUT", str(T.RESULTS)))  # M4_OUT: smoke tests write elsewhere
OUT.mkdir(exist_ok=True)
DER = T.DERIVED
LOGF = OUT / "run.log"
RUN_NAMES = {k: v["run"] for k, v in CFG["runs"].items()}


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


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


class Ctx:
    def __init__(self) -> None:
        self.bt = C.load_module("b2t25run", T.REPO / "experiments/2026-11-10-b2t25-trust/run.py")
        prep = self.bt.load_json("prep.json")
        tune = self.bt.load_json("tune.json")
        self.dec = self.bt.Decoders([], {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
        self.cpm = prep["speech_rate_125k"]["chars_per_min"]
        self.user = UserConfig.aac_gaze(chars_per_min=self.cpm)
        self.fz = FrozenTrustConfig.load(T.REPO / CFG["trust"]["frozen_config"])
        assert self.fz.config_id == CFG["trust"]["frozen_config_id"], self.fz.config_id
        self.texts = T.texts()
        self.sessions = T.sessions()
        self.cache_path = DER / "word-decode-cache.pkl"
        self.cache: dict = pickle.loads(self.cache_path.read_bytes()) if self.cache_path.exists() else {}
        self.new = 0
        self.raw = self.dec.words_fn

    def words_fn(self, stream):
        """Word route with a cache keyed by the (scaled) log-probs (decodes are deterministic)."""
        k = hashlib.sha1(np.ascontiguousarray(stream.log_probs, dtype=np.float32).tobytes()).hexdigest()
        hit = self.cache.get(k)
        if hit is None:
            self.dec._wcache = {}
            hit = self.raw(stream)
            self.cache[k] = hit
            self.new += 1
            if self.new % 300 == 0:
                self.save()
        return hit

    def save(self) -> None:
        if self.new:
            tmp = self.cache_path.with_suffix(".tmp")
            tmp.write_bytes(pickle.dumps(self.cache, protocol=pickle.HIGHEST_PROTOCOL))
            os.replace(tmp, self.cache_path)
            self.new = 0

    def pipe(self) -> TrustPipeline:
        comp = self.fz.build()
        p = TrustPipeline(self.words_fn, HarnessConfig(seed=CFG["trust"]["seed"], user_config=self.user, max_attempts=1), {})
        p.frame_scaler, p.calibrator, p.conformal, p.guard, p.policy = (
            comp.frame_scaler, comp.calibrator, comp.conformal, comp.guard, comp.policy)
        return p


def make_stream(lp: np.ndarray, key: str, la: int, run: str, gidx: int, cfgm) -> NeuralTextStream:
    s = key.split("|")[0]
    n = lp.shape[0]
    meta = {
        "device.modality": "intracortical", "device.channel_count": 256, "device.invasive": True,
        "device.regulatory_status": "investigational",
        "decoder.name": "fidetype-t15-lookahead-gru-ctc", "decoder.version": run,
        "decoder.causal": True, "decoder.lookahead_s": la * 0.02, "decoder.calibration_method": "none",
        "adapter.name": "experiments/2026-11-13-m4-01-02-lookahead", "adapter.version": FT_VERSION, "lm.name": "none",
        "user.personalized": True, "calibration.applied": False, "subject.id": "T15", "session.id": s,
        "language": "en-US", "data.derived": True,
        "stream.id": hashlib.sha256(f"{run}/{key}/L{la}".encode()).hexdigest()[:32],
        "fidetype.vocab_id": B.VOCAB_ID, "fidetype.trial_index": gidx,
        "fidetype.timing": f"exact: 80 ms frames, frame time = end of the {cfgm['patch']} x 20 ms patch; output ready {la * 20} ms later (lookahead)",
        "source.dataset": "Card et al. 2024 / B2T '25 t15_copyTask_neuralData (CC0)",
    }
    st = NeuralTextStream(log_probs=lp.astype(np.float32), frame_times=(np.arange(n) * cfgm["stride"] + cfgm["patch"]) * 0.02,
                          vocab=list(B.VOCAB), blank_id=0, source=f"t15-lookahead-gru-L{la}", meta=meta, vocab_type="phoneme",
                          frame_period=0.08, latency=la * 0.02)
    return B.to_symbol_stream(st)


def conditions() -> list[tuple[str, str, int]]:
    """(which, run, L bins) for every decoded run."""
    out = []
    for which, run in RUN_NAMES.items():
        p = DER / f"decode-{run}.json"
        if p.exists():
            m = json.loads(p.read_text(encoding="utf-8"))
            out += [(which, run, la) for la in m["lookahead_bins"]]
    return out


def load_items(ctx: Ctx, run: str, la: int):
    meta = json.loads((DER / f"decode-{run}.json").read_text(encoding="utf-8"))
    z = np.load(DER / f"logprobs-{run}.npz")
    keys = sorted({k.rsplit("|", 1)[0] for k in z.files}, key=lambda k: (k.split("|")[0], int(k.split("|")[2])))
    items, refs = [], []
    for gi, key in enumerate(keys):
        s, part, i = key.split("|")
        words = ctx.texts[s][part][int(i)]
        lp = z[f"{key}|L{la}"]
        st = make_stream(lp, key, la, run, gi, meta["model_config"])
        ph = load_ph(s, part, int(i))
        it = Item(st, words, stream_text=B.phonemes_to_symbols([B.VOCAB[j] for j in ph]))
        items.append(it)
        refs.append(key)
    return items, refs, meta


_NPZ: dict = {}


def load_ph(s: str, part: str, i: int) -> np.ndarray:
    if s not in _NPZ:
        _NPZ[s] = np.load(DER / f"{s}.npz")
    return _NPZ[s][f"{part}_ph{i}"]


# ---------------------------------------------------------------------------
# Accuracy + trust
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
    return {"per": pe / max(1, pn), "n_symbols": pn}


def stage_accuracy(only: set | None = None) -> dict:
    ctx = Ctx()
    path = OUT / "accuracy.json"
    res = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"conditions": {}}
    res.update({"frozen_config_id": ctx.fz.config_id, "frame_temperature": ctx.fz.frame_temperature, "user_cpm": ctx.cpm,
                "gaze_cpm": CFG["gaze_chars_per_min"]})
    for which, run, la in conditions():
        name = f"{which}/L{la}"
        if only and name not in only:
            continue
        if name in res["conditions"]:
            log(f"accuracy {name}: done before, skip")
            continue
        t0 = time.time()
        items, refs, meta = load_items(ctx, run, la)
        r = {"which": which, "run": run, "lookahead_bins": la, "lookahead_ms": la * 20, "n": len(items),
             "checkpoint_sha256": meta["checkpoint_sha256"], "epoch": meta["epoch"]}
        r["greedy"] = greedy_per(items)
        r["words_frozenT"] = word_quality(ctx.words_fn, items, ctx.fz.frame_temperature)
        r["words_T1"] = word_quality(ctx.words_fn, items, 1.0)
        # streaming trust layer, frames route, frozen config
        layer = StreamingTrustLayer(ctx.fz, decode_fn=ctx.words_fn, streaming=StreamingConfig(route="frames", max_attempts=1))
        decs = []
        for gi, it in enumerate(items):
            sid = it.stream(0).meta["session.id"]
            got = []
            for ev in events_of(it.stream(0)):
                got += layer.push(ev, sid)
            fin = [d for d in got if d.final]
            assert len(fin) == 1
            decs.append(fin[0])
        pipe = ctx.pipe()
        recs = pipe.run_items(items, ReplayPolicy(decs))
        # batch harness (same frozen components) for the equality check
        bpipe = ctx.pipe()
        brecs = bpipe.run_items(items)
        eq = sum(a.actions == b.actions and a.committed_text == b.committed_text for a, b in zip(recs, brecs))
        m = summarize(recs)
        ncom = sum(d.action == Action.COMMIT for d in decs)
        nwr = sum(bool(x.wrong_commit) for x in recs)
        n = len(recs)
        nempty = sum(x.committed_text is not None and x.committed_text.strip() == "" for x in recs)
        r["trust"] = {"n_commit": ncom, "commit_rate": ncom / n, "n_wrong_commit": nwr, "wrong_commit": nwr / n,
                      "wrong_commit_cp95": cp(nwr, n), "error_among_commits": (nwr / ncom) if ncom else None,
                      "n_commit_empty": nempty, "ewpm": m["ewpm"], "silent_error": m["silent_error_rate"],
                      "rate_offer": m["rate_offer"], "abstain_rate": m["abstain_rate"],
                      "stream_equals_batch": eq,
                      "actions": {a: sum(d.action.value == a for d in decs) for a in ("COMMIT", "OFFER", "ASK", "ABSTAIN", "OFFER_WORDS")}}
        allc = TrustPipeline(ctx.words_fn, HarnessConfig(seed=0, user_config=ctx.user, max_attempts=1, policy="always_commit"), {})
        allc.frame_scaler = pipe.frame_scaler
        ar = allc.run_items(items)
        am = summarize(ar)
        r["always_commit"] = {"wrong_commit": sum(bool(x.wrong_commit) for x in ar) / n, "ewpm": am["ewpm"]}
        r["gaze_ewpm"] = 60.0 * sum(len(it.text.split()) for it in items) / (sum(len(it.text) for it in items) * 60.0 / CFG["gaze_chars_per_min"])
        r["seconds"] = round(time.time() - t0, 1)
        res["conditions"][name] = r
        ctx.save()
        T.dump(res, path)
        # per-trial (outside the repo)
        T.dump({"refs": refs, "decisions": [d.to_event(include_text=True) for d in decs]}, DER / f"trust-{which}-L{la}.json")
        tr = r["trust"]
        log(f"accuracy {name}: PER {r['greedy']['per']:.4f}; WER(frozen T) {r['words_frozenT']['wer']:.4f} exact "
            f"{r['words_frozenT']['sentence_exact']:.3f}; WER(T1) {r['words_T1']['wer']:.4f}; commit {tr['commit_rate']:.3f} "
            f"({tr['n_commit']}) wrong {tr['wrong_commit']:.4f} ({tr['n_wrong_commit']}) eWPM {tr['ewpm']:.2f}; stream==batch {eq}/{n} "
            f"({r['seconds']:.0f}s)")
    return res


# ---------------------------------------------------------------------------
# Emission timing
# ---------------------------------------------------------------------------


def greedy_runs(lp: np.ndarray) -> list[tuple[int, int]]:
    """(label, first frame) of each greedy CTC emission."""
    a = lp.argmax(-1)
    out, prev = [], -1
    for t, x in enumerate(a):
        if x != prev and x != 0:
            out.append((int(x), t))
        prev = x
    return out


def align_matches(ref: list[int], hyp: list[int]) -> dict[int, int]:
    """Levenshtein alignment; returns ref index -> hyp index for exact matches."""
    n, m = len(ref), len(hyp)
    D = np.zeros((n + 1, m + 1), np.int32)
    D[:, 0] = np.arange(n + 1)
    D[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = min(D[i - 1, j] + 1, D[i, j - 1] + 1, D[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]))
    i, j, out = n, m, {}
    while i > 0 and j > 0:
        if D[i, j] == D[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]):
            if ref[i - 1] == hyp[j - 1]:
                out[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif D[i, j] == D[i - 1, j] + 1:
            i -= 1
        else:
            j -= 1
    return out


def stage_emission() -> dict:
    conds = conditions()
    per: dict = {}
    for which, run, la in conds:
        meta = json.loads((DER / f"decode-{run}.json").read_text(encoding="utf-8"))
        mc = meta["model_config"]
        z = np.load(DER / f"logprobs-{run}.npz")
        d = {}
        for k in z.files:
            if not k.endswith(f"|L{la}"):
                continue
            key = k.rsplit("|", 1)[0]
            s, part, i = key.split("|")
            ref = [int(x) for x in load_ph(s, part, int(i))]
            lp = z[k]
            runs = greedy_runs(lp)
            hyp = [x for x, _ in runs]
            mt = align_matches(ref, hyp)
            stamp = lambda f: (f * mc["stride"] + mc["patch"]) * 0.02  # noqa: E731
            n_frames = lp.shape[0]
            d[key] = {ri: (stamp(runs[hj][1]), stamp(runs[hj][1]) + la * 0.02) for ri, hj in mt.items()}
            d[key]["_end"] = stamp(n_frames - 1)
        per[(which, la)] = d
    res: dict = {"note": "available = stamp of the first greedy frame of the phoneme + L. Matched = the phoneme is aligned "
                         "exactly (Levenshtein) to the reference in both conditions. Delta = this condition - reference "
                         "(seconds), median and IQR over phonemes.", "comparisons": {}}
    refs = [("shared", 0)] + ([("dedicated_0", 0)] if ("dedicated_0", 0) in per else [])
    for rk in refs:
        for ck in per:
            if ck == rk:
                continue
            ds, dav = [], []
            last_gap = []
            R, Cc = per[rk], per[ck]
            for key in R:
                if key not in Cc:
                    continue
                common = [i for i in R[key] if i != "_end" and i in Cc[key]]
                for i in common:
                    ds.append(Cc[key][i][0] - R[key][i][0])
                    dav.append(Cc[key][i][1] - R[key][i][1])
                if common:
                    li = max(common)
                    last_gap.append(Cc[key][li][1] - R[key][li][1])
            if not ds:
                continue
            q = lambda v: {"median": float(np.median(v)), "p25": float(np.percentile(v, 25)), "p75": float(np.percentile(v, 75)),  # noqa: E731
                           "mean": float(np.mean(v)), "n": len(v)}
            res["comparisons"][f"{ck[0]}/L{ck[1]} vs {rk[0]}/L{rk[1]}"] = {
                "emission_stamp_delta_s": q(ds), "available_delta_s": q(dav), "last_matched_phoneme_available_delta_s": q(last_gap)}
    # absolute: time from the stamp of the last emitted phoneme to the end of the utterance (how late CTC emits at the end)
    res["last_emission_to_end_s"] = {}
    for (which, la), d in per.items():
        gaps = [v["_end"] - max(t[0] for i, t in v.items() if i != "_end") for v in d.values() if len(v) > 1]
        res["last_emission_to_end_s"][f"{which}/L{la}"] = {"median": float(np.median(gaps)), "p25": float(np.percentile(gaps, 25)),
                                                           "p75": float(np.percentile(gaps, 75))}
    T.dump(res, OUT / "emission.json")
    for k, v in res["comparisons"].items():
        log(f"emission {k}: stamp delta median {v['emission_stamp_delta_s']['median'] * 1e3:.0f} ms, available delta median "
            f"{v['available_delta_s']['median'] * 1e3:.0f} ms (n {v['available_delta_s']['n']})")
    return res


# ---------------------------------------------------------------------------
# Latency (after the soak test)
# ---------------------------------------------------------------------------


def soak_finished() -> bool:
    return Path("C:/Users/zhang/bci-data/soak/m6-13/DONE").exists()


def stage_latency(n_trials: int = 200, force: bool = False) -> dict:
    if not soak_finished() and not force:
        raise SystemExit("M6-13 soak test still running (no DONE file): latency stage refused")
    from fidetype.decoders.lookahead_gru import LookaheadGRUConfig, NumpyLookaheadGRU, StreamingLookaheadGRU, log_softmax
    from fidetype.trust.incremental import CTCBeamSpec
    from fidetype.trust.types import from_lm_hypotheses
    from fidetype.utils.isolation import isolated

    ctx = Ctx()
    run = RUN_NAMES["shared"]
    meta = json.loads((DER / f"decode-{run}.json").read_text(encoding="utf-8"))
    mc = LookaheadGRUConfig(**meta["model_config"])
    pz = np.load(DER / f"params-{run}.npz")
    model = NumpyLookaheadGRU(mc, {k: pz[k] for k in pz.files})
    keys_all = sorted({k.rsplit("|", 1)[0] for k in np.load(DER / f"logprobs-{run}.npz").files},
                      key=lambda k: (k.split("|")[0], int(k.split("|")[2])))
    rng = np.random.default_rng(20261113)
    keys = sorted(rng.choice(len(keys_all), min(n_trials, len(keys_all)), replace=False).tolist())
    keys = [keys_all[i] for i in keys]
    sess_idx = {s: i for i, s in enumerate(ctx.sessions)}
    X = {}
    for key in keys:
        s, part, i = key.split("|")
        if s not in _NPZ:
            _NPZ[s] = np.load(DER / f"{s}.npz")
        X[key] = _NPZ[s][f"{part}_X{i}"].astype(np.float32)
    wdec = ctx.dec.wdec

    def post(hyps, stream):
        return from_lm_hypotheses(wdec.decode(hyps), stream.meta, confidence_variant=None)

    spec = CTCBeamSpec(dict(ctx.dec.beam_kw), post=post)
    ref = json.loads((OUT / "accuracy.json").read_text(encoding="utf-8"))["conditions"]
    res: dict = {"n_trials": len(keys), "run": run, "conditions": {}, "bin_s": 0.02, "frame_period_s": 0.08}
    gc.collect()
    gc.freeze()
    with isolated("timing") as iso:
        for la in T.LA_BINS:
            wdec.clear_caches() if hasattr(wdec, "clear_caches") else None
            layer = StreamingTrustLayer(ctx.fz, incremental=spec.factory,
                                        streaming=StreamingConfig(route="frames", max_attempts=1, incremental_chunk_frames=1))
            t_bin, t_frame, t_end_dec, t_end_trust, t_end_total, n_out_at_end = [], [], [], [], [], []
            decs = []
            stream_lat_check = 0
            for gi, key in enumerate(keys):
                s = key.split("|")[0]
                lp_ref = np.load(DER / f"logprobs-{run}.npz")[f"{key}|L{la}"] if gi < 20 else None
                st_meta = make_stream(np.zeros((1, 41), np.float32), key, la, run, gi, meta["model_config"])
                head = events_of(st_meta)[0]
                gc.collect()
                gc.disable()
                layer.push(head, s)
                dec = StreamingLookaheadGRU(model, sess_idx[s], la)
                x = X[key]
                k = 0
                rows_all = []
                for b in range(x.shape[0]):
                    t0 = time.perf_counter()
                    rows = dec.push(x[b:b + 1])
                    t1 = time.perf_counter()
                    t_bin.append(t1 - t0)
                    for row in rows:
                        lpr = log_softmax(row[None])[0]
                        rows_all.append(lpr)
                        ev = {"type": "frame", "t": float((k * mc.stride + mc.patch) * 0.02),
                              "log_probs": [float(v) for v in lpr]}
                        t2 = time.perf_counter()
                        layer.push(ev, s)
                        t_frame.append(time.perf_counter() - t2)
                        k += 1
                # end of the utterance: flush the decoder, push the remaining frames, then the end event
                t0 = time.perf_counter()
                rows = dec.flush()
                t1 = time.perf_counter()
                out = []
                for row in rows:
                    lpr = log_softmax(row[None])[0]
                    rows_all.append(lpr)
                    out += layer.push({"type": "frame", "t": float((k * mc.stride + mc.patch) * 0.02),
                                       "log_probs": [float(v) for v in lpr]}, s)
                    k += 1
                out += layer.push({"type": "end"}, s)
                t2 = time.perf_counter()
                gc.enable()
                t_end_dec.append(t1 - t0)
                t_end_trust.append(t2 - t1)
                t_end_total.append(t2 - t0)
                n_out_at_end.append(len(rows))
                fin = [d for d in out if d.final]
                assert len(fin) == 1
                decs.append(fin[0])
                if lp_ref is not None:
                    stream_lat_check = max(stream_lat_check, float(np.abs(np.stack(rows_all) - lp_ref).max()))
            # decisions vs the accuracy stage (torch logits, batch decode)
            acc = json.loads((DER / f"trust-shared-L{la}.json").read_text(encoding="utf-8"))
            amap = dict(zip(acc["refs"], acc["decisions"]))
            same = sum(d.action.value == amap[key]["action"] for d, key in zip(decs, keys))
            ms = lambda v: {"p50": float(np.percentile(v, 50) * 1e3), "p95": float(np.percentile(v, 95) * 1e3),  # noqa: E731
                            "max": float(np.max(v) * 1e3), "mean": float(np.mean(v) * 1e3), "n": len(v)}
            r = {"lookahead_bins": la, "algorithmic_lookahead_ms": la * 20,
                 "stride_wait_ms_max": (mc.stride - 1) * 20,
                 "decoder_push_per_bin_ms": ms(t_bin), "trust_push_per_frame_ms": ms(t_frame),
                 "end_decoder_flush_ms": ms(t_end_dec), "end_trust_ms": ms(t_end_trust), "end_total_ms": ms(t_end_total),
                 "frames_flushed_at_end": {"median": float(np.median(n_out_at_end)), "max": int(max(n_out_at_end))},
                 "numpy_vs_torch_max_abs_logprob": stream_lat_check,
                 "same_action_as_accuracy_stage": same, "n": len(decs),
                 "accuracy_stage_commit_rate_all": ref.get(f"shared/L{la}", {}).get("trust", {}).get("commit_rate")}
            res["conditions"][f"L{la}"] = r
            log(f"latency L{la}: bin push p50/p95 {r['decoder_push_per_bin_ms']['p50']:.2f}/{r['decoder_push_per_bin_ms']['p95']:.2f} ms; "
                f"frame push p95 {r['trust_push_per_frame_ms']['p95']:.2f}; end total p50/p95/max {r['end_total_ms']['p50']:.1f}/"
                f"{r['end_total_ms']['p95']:.1f}/{r['end_total_ms']['max']:.1f} ms; same action {same}/{len(decs)}; "
                f"numpy-torch {stream_lat_check:.2e}")
        res["measurement_env"] = iso.record
    gc.unfreeze()
    T.dump(res, OUT / "latency.json")
    return res


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def f(x, nd=3):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:.{nd}f}"


def stage_tables() -> None:
    acc = json.loads((OUT / "accuracy.json").read_text(encoding="utf-8"))
    emi = json.loads((OUT / "emission.json").read_text(encoding="utf-8")) if (OUT / "emission.json").exists() else None
    lat = json.loads((OUT / "latency.json").read_text(encoding="utf-8")) if (OUT / "latency.json").exists() else None
    L = ["# M4-01 / M4-02 tables: lookahead L against accuracy, trust outcomes and latency", "",
         f"T15 val_eval ({next(iter(acc['conditions'].values()))['n']} trials, 41 sessions). Frozen trust config `{acc['frozen_config_id']}` "
         f"(Paper 1 v4 recipe, fitted on the published decoder in M4-06; frame T {acc['frame_temperature']:.3f}); not refitted.", "",
         "## Accuracy and trust outcomes against L", "",
         "| model | L (ms) | greedy PER | WER (frozen T) | sentence exact (frozen T) | WER (T=1) | exact (T=1) | truth in n-best | commit rate (n) | wrong-commit (n) [CP95] | EAC | eWPM | always-commit eWPM | gaze eWPM | stream = batch |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    order = sorted(acc["conditions"].values(), key=lambda r: ({"shared": 0, "dedicated_0": 1, "dedicated_25": 2}[r["which"]], r["lookahead_bins"]))
    for r in order:
        t = r["trust"]
        ci = t["wrong_commit_cp95"]
        L.append(f"| {r['which']} | {r['lookahead_ms']} | {f(r['greedy']['per'], 4)} | {f(r['words_frozenT']['wer'], 4)} | "
                 f"{f(r['words_frozenT']['sentence_exact'])} ({r['words_frozenT']['n_exact']}) | {f(r['words_T1']['wer'], 4)} | "
                 f"{f(r['words_T1']['sentence_exact'])} | {f(r['words_frozenT']['truth_in_nbest'])} | {f(t['commit_rate'])} ({t['n_commit']}) | "
                 f"{f(t['wrong_commit'], 4)} ({t['n_wrong_commit']}) [{f(ci[0], 3)}, {f(ci[1], 3)}] | {f(t['error_among_commits'])} | "
                 f"{f(t['ewpm'], 2)} | {f(r['always_commit']['ewpm'], 2)} | {f(r['gaze_ewpm'], 2)} | {t['stream_equals_batch']}/{r['n']} |")
    if emi:
        L += ["", "## Emission timing (greedy CTC path)", "", emi["note"], "",
              "| comparison | emission stamp Δ median ms [IQR] | available Δ median ms [IQR] | last matched phoneme available Δ median ms | n phonemes |",
              "|---|---|---|---|---|"]
        for k, v in emi["comparisons"].items():
            a, b, c = v["emission_stamp_delta_s"], v["available_delta_s"], v["last_matched_phoneme_available_delta_s"]
            L.append(f"| {k} | {a['median'] * 1e3:.0f} [{a['p25'] * 1e3:.0f}, {a['p75'] * 1e3:.0f}] | {b['median'] * 1e3:.0f} "
                     f"[{b['p25'] * 1e3:.0f}, {b['p75'] * 1e3:.0f}] | {c['median'] * 1e3:.0f} | {b['n']} |")
        L += ["", "| condition | last emission stamp -> utterance end, median s [IQR] |", "|---|---|"]
        for k, v in emi["last_emission_to_end_s"].items():
            L.append(f"| {k} | {v['median']:.2f} [{v['p25']:.2f}, {v['p75']:.2f}] |")
    if lat:
        env = lat.get("measurement_env", {})
        L += ["", f"## Latency against L (shared model, {lat['n_trials']} trials, NumPy streaming decoder + StreamingTrustLayer incremental)", "",
              f"Measurement environment clean: {env.get('clean')} ({', '.join(env.get('clean_reasons', []) or [])}).", "",
              "| L (ms) | algorithmic lookahead ms | + stride wait ms (max) | decoder push per 20 ms bin p50 / p95 ms | trust push per frame p50 / p95 ms | end of utterance: decoder flush p50 ms | trust end p50 / p95 / max ms | total end p50 / p95 / max ms | same action as accuracy stage |",
              "|---|---|---|---|---|---|---|---|---|"]
        for k, r in lat["conditions"].items():
            L.append(f"| {r['algorithmic_lookahead_ms']} | {r['algorithmic_lookahead_ms']} | {r['stride_wait_ms_max']} | "
                     f"{r['decoder_push_per_bin_ms']['p50']:.2f} / {r['decoder_push_per_bin_ms']['p95']:.2f} | "
                     f"{r['trust_push_per_frame_ms']['p50']:.2f} / {r['trust_push_per_frame_ms']['p95']:.2f} | "
                     f"{r['end_decoder_flush_ms']['p50']:.1f} | {r['end_trust_ms']['p50']:.1f} / {r['end_trust_ms']['p95']:.1f} / {r['end_trust_ms']['max']:.1f} | "
                     f"{r['end_total_ms']['p50']:.1f} / {r['end_total_ms']['p95']:.1f} / {r['end_total_ms']['max']:.1f} | {r['same_action_as_accuracy_stage']}/{r['n']} |")
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv: list[str]) -> None:
    stages = argv or ["accuracy", "emission", "tables"]
    for st in stages:
        t0 = time.time()
        log(f"stage {st} start")
        if st == "accuracy":
            stage_accuracy()
        elif st.startswith("accuracy="):
            stage_accuracy(set(st.split("=", 1)[1].split(",")))
        elif st == "emission":
            stage_emission()
        elif st == "latency":
            stage_latency()
        elif st == "latency-force":
            stage_latency(force=True)
        elif st == "tables":
            stage_tables()
        else:
            raise SystemExit(f"unknown stage {st}")
        log(f"stage {st} done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main(sys.argv[1:])
