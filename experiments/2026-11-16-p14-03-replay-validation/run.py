"""P14-03 replay validation: the drop-in trust API on two public replay sets (plan: plan.md). CPU only.

Uses only the public API: fidetype.trust.calibrate(...) -> TrustGuard.decide(x). The word decoders of the
earlier experiments are passed as the user's own ``decode_fn``.

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-16-p14-03-replay-validation/run.py t15 t12
Per-trial outputs: C:/Users/zhang/bci-data/derived/p14-03-replay-validation/ only. Repo: aggregates + guard files.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

import fidetype.trust as ft  # noqa: E402
from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.adapters import b2t25 as B  # noqa: E402
from fidetype.eval.ewpm import SentenceRecord, summarize  # noqa: E402
from fidetype.interact.simulated_user import SimulatedUser, UserConfig  # noqa: E402
from fidetype.streams.spec import NeuralTextStream  # noqa: E402
from fidetype.trust.policy import Action, Decision  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p14-03-replay-validation"  # the only place this task writes per-trial files
assert OWN.name == "p14-03-replay-validation"
OWN.mkdir(parents=True, exist_ok=True)
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
LOGF = OUT / "run.log"
ALPHAS = (0.05, 0.10)
SEED = 0


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def cp(k: int, n: int, level: float = 0.95) -> list:
    from scipy.stats import beta

    a = 1 - level
    lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return [lo, hi]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_decode_fn(dec):
    """The user's own text decoder: (T, 41) phoneme log-probs -> word n-best list (dicts)."""
    cache: dict = {}

    def phoneme_words_decoder(log_probs: np.ndarray) -> list[dict]:
        lp = np.ascontiguousarray(log_probs, dtype=np.float32)
        k = hashlib.sha1(lp.tobytes()).hexdigest()
        hit = cache.get(k)
        if hit is not None:
            return hit
        st = NeuralTextStream(log_probs=lp, frame_times=np.arange(lp.shape[0]) * 0.08, vocab=list(B.SYMBOL_VOCAB),
                              blank_id=0, vocab_type="phoneme")
        dec._wcache = {}
        nb = dec.words_fn(st)
        out = []
        for c in nb.candidates:
            d = {"text": c.text, "score": float(c.score)}
            for f in ("logp_acoustic", "logp_lm"):
                v = float(getattr(c, f))
                if math.isfinite(v) and v <= 0:
                    d[f] = v
            if c.char_confidences:
                d["char_confidences"] = [min(1.0, max(0.0, float(x))) for x in c.char_confidences]
            out.append(d)
        cache[k] = out
        return out

    return phoneme_words_decoder


def ph_symbols(npz: dict, folder: Path, s: str, part: str, i: int) -> str:
    if s not in npz:
        npz[s] = np.load(folder / f"{s}.npz")
    return B.phonemes_to_symbols([B.VOCAB[j] for j in npz[s][f"{part}_ph{i}"]])


# ---------------------------------------------------------------------------
# data of the two sets
# ---------------------------------------------------------------------------


def data_t15():
    """Calibration: val_select (722); held out: val_eval (701). M4-12 fixed0 log-probs, read only."""
    d_in = DER / "m4-01-02-lookahead"
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    sessions = json.loads((d_in / "sessions.json").read_text(encoding="utf-8"))
    order = {s: j for j, s in enumerate(sessions)}
    npz: dict = {}

    def part(path: Path, name: str):
        z = np.load(path)
        keys = sorted((k for k in z.files if f"|{name}|" in k),
                      key=lambda k: (order[k.split("|")[0]], int(k.split("|")[2])))
        xs, ts, ph = [], [], []
        for k in keys:
            s, p, i, _ = k.split("|")
            xs.append(z[k].astype(np.float32))
            ts.append(texts[s][p][int(i)])
            ph.append(ph_symbols(npz, d_in, s, p, int(i)))
        return xs, ts, ph

    cal = part(DER / "m2-19-trust-retune/logprobs-m2-19-m4-12-fixed0.npz", "val_select")
    held = part(d_in / "logprobs-m4-12-fixed0.npz", "val_eval")
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    tune = bt.load_json("tune.json")
    dec = bt.Decoders([], {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    cpm = bt.load_json("prep.json")["speech_rate_125k"]["chars_per_min"]
    return cal, held, dec, cpm, {"calibration": "val_select (even-index val trials)", "held_out": "val_eval (odd-index val trials)"}


def data_t12():
    """Calibration: trust pool of the fit_a + calibration sessions (480); held out: test sessions (400)."""
    exp = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
    cfg = json.loads((exp / "config.json").read_text(encoding="utf-8"))
    d_in = Path(cfg["derived_dir"])
    prep = json.loads((exp / "results/prep.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    meta = json.loads((d_in / "logprobs-meta.json").read_text(encoding="utf-8"))
    assert meta["checkpoint_sha256"] == cfg["decoder_checkpoint_sha256"]
    z = np.load(d_in / "logprobs.npz")
    npz: dict = {}

    def part(roles: tuple[str, ...]):
        xs, ts, ph = [], [], []
        for r in prep["sessions"]:
            if r["role"] not in roles:
                continue
            s = r["session"]
            for i, w in enumerate(texts[s]["pool"]):
                xs.append(z[f"{s}|pool|{i}"].astype(np.float32))
                ts.append(w)
                ph.append(ph_symbols(npz, d_in, s, "pool", i))
        return xs, ts, ph

    cal, held = part(("fit_a", "calibration")), part(("test",))
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    dec = bt.Decoders([], cfg["word_decoder_tuned"])
    sys.path.insert(0, str(exp))
    import wordlm  # noqa: E402

    beta = cfg["word_lm"]["beta"]
    cache = Path(cfg["word_lm"]["cache"])
    assert cache.exists(), "word LM cache missing (would be rebuilt)"
    wm = wordlm.load_or_build(bt.CONFIG["tatoeba_eng"], cache, B.normalize_words)
    char = dec.lm.score_sentence
    dec.wdec.sentence_lm = lambda t: char(t) + beta * wm.score_sentence(t)
    dec.wdec.clear_caches()
    dec._wcache.clear()
    cpm = prep["speech_rate_decoder_train"]["chars_per_min"]
    return cal, held, dec, cpm, {"calibration": "trust pool, 14 fit_a + calibration sessions",
                                 "held_out": "trust pool, 10 test sessions"}


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


def ewpm(results, truths, cpm: float) -> dict:
    """Public simulated user on the guard decisions; one attempt per trial (as the earlier experiments)."""
    user = SimulatedUser(UserConfig.aac_gaze(chars_per_min=cpm), seed=SEED)
    recs = []
    for i, (r, t) in enumerate(zip(results, truths)):
        d = Decision(Action(r.raw_action), tuple(r.choices), r.reason)
        o = user.respond(d, t, can_repeat=False, rng=np.random.default_rng([SEED, i, 0]))
        tt = user.typing_time(t) + o.time_s
        rec = SentenceRecord(t, o.final_text, o.communicated, tt, [r.raw_action],
                             r.text if r.action == "commit" else None, o.wrong_commit, o.silent_error)
        recs.append(rec)
    s = summarize(recs)
    return {k: s[k] for k in ("ewpm", "ewpm_partial") if k in s}


def run_set(name: str, loader) -> dict:
    t0 = time.time()
    (cx, ct, cph), (hx, ht, hph), dec, cpm, split = loader()
    fn = make_decode_fn(dec)
    ht = [" ".join(t.split()) for t in ht]
    log(f"{name}: calibration {len(cx)}, held out {len(hx)}, cpm {cpm:.1f}")
    out: dict = {"split": split, "n_calibration": len(cx), "n_held_out": len(hx), "chars_per_min": cpm, "alpha": {}}
    for alpha in ALPHAS:
        ta = time.time()
        row: dict = {}
        try:
            guard = ft.calibrate(cx, ct, alpha=alpha, delta=0.1, vocab=list(B.SYMBOL_VOCAB), blank=0,
                                 input_scale="log_probs", frame_period=0.08, decode_fn=fn, stream_texts=cph,
                                 decoder_name=f"p14-03-{name}", modality="intracortical", name=f"p14-03-{name}",
                                 seed=SEED)
        except ft.NullControlError as e:
            row = {"status": "refused", "controls": [c.to_dict() for c in e.report], "message": str(e)}
            log(f"{name} alpha {alpha}: REFUSED {row['controls']}")
            out["alpha"][str(alpha)] = row
            continue
        sh = guard.sheet
        log(f"{name} alpha {alpha}: calibrated {guard.config_id} in {time.time() - ta:.0f}s\n{sh}")
        res = [guard.decide(x, utterance_id=f"{name}-{i}") for i, x in enumerate(hx)]
        n = len(res)
        acts = {a: sum(r.action == a for r in res) for a in ("commit", "offer", "withhold")}
        raw = {}
        for r in res:
            raw[r.raw_action] = raw.get(r.raw_action, 0) + 1
        com = [(r, t) for r, t in zip(res, ht) if r.action == "commit"]
        nw = sum(r.text != t for r, t in com)
        rate = nw / n
        row = {
            "status": "ok", "config_id": guard.config_id, "sheet": sh.to_dict(),
            "frame_temperature": guard.config.frame_temperature,
            "sentence_temperature": guard.config.sentence_temperature,
            "n": n, "actions": acts, "raw_actions": raw, "n_commit": len(com), "n_wrong_commit": nw,
            "wrong_commit_rate": rate, "wrong_commit_cp95": cp(nw, n),
            "error_among_commits": (nw / len(com)) if com else None,
            "error_among_commits_cp95": cp(nw, len(com)) if com else None,
            "empty_commits": sum(not (r.text or "").strip() for r, _ in com),
            "top1_exact_held_out": None,
            "ewpm": ewpm(res, ht, cpm),
            "seconds": round(time.time() - ta, 1),
        }
        row["pass"] = rate <= alpha
        row["vacuous"] = len(com) == 0
        row["cp95_upper_le_alpha"] = row["wrong_commit_cp95"][1] <= alpha
        tag = f"{name}-a{alpha:.2f}"
        guard.save(OUT / f"guard-{tag}.json")
        guard.write_audit(OWN / f"audit-{tag}.jsonl")
        (OWN / f"decisions-{tag}.json").write_text(json.dumps(
            [{"i": i, "action": r.action, "raw": r.raw_action, "p_top1": r.p_top1, "guard_risk": r.guard_risk,
              "reason": r.reason, "text": r.text, "truth": t} for i, (r, t) in enumerate(zip(res, ht))], indent=0),
            encoding="utf-8")
        log(f"{name} alpha {alpha}: held out commits {len(com)}/{n}, wrong {nw} ({rate:.4f}, CP95 "
            f"[{row['wrong_commit_cp95'][0]:.4f}, {row['wrong_commit_cp95'][1]:.4f}]); actions {acts}; "
            f"eWPM {row['ewpm']}; pass {row['pass']} vacuous {row['vacuous']}")
        out["alpha"][str(alpha)] = row
    out["seconds"] = round(time.time() - t0, 1)
    return out


def main() -> None:
    stages = sys.argv[1:] or ["t15", "t12"]
    path = OUT / "results.json"
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr["fidetype_version"] = FT_VERSION
    for st in stages:
        log(f"stage {st} start")
        allr[st] = run_set(st, {"t15": data_t15, "t12": data_t12}[st])
        path.write_text(json.dumps(allr, indent=1, default=str), encoding="utf-8")
        log(f"stage {st} done")


if __name__ == "__main__":
    main()
