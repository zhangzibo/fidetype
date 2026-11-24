"""P11-11: a non-vacuous certified safe WPM for the P11-01 emg2qwerty EMG decoder. CPU only.

Pre-registration: plan.md (this folder). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0. Per-prompt files stay
in C:/Users/zhang/bci-data/derived/p11-11/. The P11-09 files (prompts, log-probs) are read only. The repo gets
aggregates only (no per-user value, no text, no id).

Stages (repo root; launch.py runs them detached through the isolation runner):

  lm        rebuild the Tatoeba 6-gram character LM without the intended texts of the 16 sessions (leak-free).
  lexicon   word list of the track-train sessions (typed at least twice).
  nbest     key CTC beam (64, 64-best) of every window used (cached by window).
  tune      (w, c) on the first 765 calibration prompts of the calibrate order (fit + policy grid).
  guards    fidetype.trust.calibrate per arm (S primary, SL, X, K).
  decide    decisions on the evaluation prompts (real, time-shuffled, zero EMG).
  score     safe WPM v0.1 / proposed v0.2, verdicts, aggregates; arm K card if certified and non-vacuous.
  all       every stage in this order.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
os.environ.setdefault("HIP_VISIBLE_DEVICES", "")  # CPU only
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import argparse  # noqa: E402
import collections  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.adapters import emg2qwerty as A  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p11-11"  # the only place this task writes per-prompt files
P1109 = DER / "p11-09"  # READ ONLY: prompts.json, lp/
P1101 = DER / "p11-01-emg-decoder"  # READ ONLY: key labels of the track-train sessions
E2Q_DATA = Path("C:/Users/zhang/bci-data/raw/emg2qwerty/extracted/emg2qwerty-data-2021-08")  # READ ONLY
TRUTH = DER / "p6-02-scorer" / "truth" / "emg2qwerty.jsonl"  # READ ONLY
EXP1109 = REPO / "experiments" / "2026-11-19-p11-09-emg-trust"
EXPLM = REPO / "experiments" / "2026-11-08-lm-beam"
OUT = HERE / "results"
TRACK = "emg2qwerty"

# --- pre-registered constants (plan.md) ------------------------------------------------------------
ALPHA, DELTA, SEED = 0.05, 0.1, 0
FRAME_S = 0.01
N_NULL = 300
BEAM, NBEST_BEAM, NBEST_OUT = 64, 64, 20
W_GRID = (0.25, 0.5, 0.75, 1.0, 1.5)
C_GRID = (0, 1, 2, 4, 8)
N_TUNE = 765  # fit (306) + policy grid (459) of calibrate's split of 1,224 items
LEX_MIN_COUNT = 2
OOV_GATE = 0.5  # amendment 1: no output (the guard withholds) if more than this share of the top-1 words is OOV
LM_BLOCK_MIN_LEN = 15
READ_S_PER_COMMIT, READ_S_PER_WORD = 0.5, 0.3
ARMS = ("S", "SL", "X", "K")
P1109_DIGESTS = {"cal": None, "eval": None}  # filled from the P11-09 guard status files at run time
RESEARCH = {"data.licence": A.LICENCE, "data.research_only": True}
DECODER_NAME = "fidetype-p11-01-crt+e2q-keys+beam64+tatoeba-noE2Q-6gram+train-lexicon"

BS_CHAR = A.key_chars()[A.KEY_VOCAB.index("Backspace")]
EN_CHAR = A.key_chars()[A.KEY_VOCAB.index("Enter")]


def log(*a: object) -> None:
    OUT.mkdir(exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def own(*parts: str) -> Path:
    p = OWN.joinpath(*parts)
    assert OWN in p.parents or p == OWN
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def save_json(obj: object, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def keep_awake(on: bool) -> None:
    if os.name != "nt":
        return
    import ctypes

    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# --- targets ---------------------------------------------------------------------------------------


def resolve(key_text: str) -> str:
    """Key text (``key_chars``: letters, ``_`` = Space, ``.``, ``,``, ``'``, Backspace, Enter) -> intended text.

    A character key appends its character; Space appends a space; Backspace removes the last character (if
    any); Enter is ignored. Then runs of spaces are joined and the ends stripped.
    """
    out: list[str] = []
    for ch in key_text:
        if ch == BS_CHAR:
            if out:
                out.pop()
        elif ch == EN_CHAR:
            continue
        elif ch == A.KEY_SPACE_CHAR:
            out.append(" ")
        else:
            out.append(ch)
    return " ".join("".join(out).split())


def intended_truth(r: dict) -> str:
    return resolve(A.codes_to_key_text(r["codes"]))


def key_truth(r: dict) -> str:
    return A.codes_to_key_text(r["codes"])


# --- prompts and windows (P11-09, read only) --------------------------------------------------------------


def p1109():
    """The P11-09 runner as a module (Windows, sessions, check_track_splits, split_digest). Read-only use."""
    if "p1109run" not in sys.modules:
        load_module("p1109run", EXP1109 / "run.py")
    return sys.modules["p1109run"]


def prompts() -> list[dict]:
    return load_json(P1109 / "prompts.json")  # type: ignore[return-value]


def split_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    return [r for r in rows if r["split"] == "val"], [r for r in rows if r["split"] == "test"]


def null_pick(n_cal: int) -> list[int]:
    return sorted(np.random.default_rng(SEED).choice(n_cal, size=min(N_NULL, n_cal), replace=False).tolist())


# --- window cache key ------------------------------------------------------------------------------------


def window_key(x: np.ndarray) -> str:
    """Cache key of one (T, 33) log-prob window: renormalised per row, rounded to 3 decimals."""
    a = np.asarray(x, np.float64)
    a = a - np.logaddexp.reduce(a, axis=1, keepdims=True)
    a = np.round(np.maximum(a, -60.0), 3)
    return hashlib.sha1(a.tobytes() + str(a.shape).encode()).hexdigest()


# --- decoder ---------------------------------------------------------------------------------------------


def beam_nbest(x: np.ndarray) -> list[tuple[str, float]]:
    """Built-in key CTC prefix beam (64, 64-best, no LM): [(key text, acoustic log-prob)], best first."""
    from fidetype.lm.beam import IncrementalPrefixBeam

    dec = IncrementalPrefixBeam(A.key_ctc_vocab(), 0, lm=None, beam=BEAM, n_best=NBEST_BEAM, prune_topk=None,
                                align=False, search="vector")
    dec.push(np.asarray(x, np.float64))
    return [(h.text, float(h.logp_acoustic)) for h in dec.finalize()]


class Decoder:
    """Beam (cached) -> intended texts (merged) -> LM / lexicon rescoring. One global instance per process."""

    def __init__(self) -> None:
        self.cache: dict[str, list[tuple[str, float]]] = {}
        self.lm = None
        self.lex: frozenset[str] = frozenset()
        self.w, self.c = 0.0, 0.0
        self.hits = self.misses = 0
        self._lm_memo: dict[str, float] = {}

    def load_cache(self) -> None:
        f = own("nbest.pkl")
        if f.exists():
            with open(f, "rb") as fh:
                self.cache.update(pickle.load(fh))

    def save_cache(self) -> None:
        f = own("nbest.pkl")
        tmp = f.with_suffix(".tmp")
        with open(tmp, "wb") as fh:
            pickle.dump(self.cache, fh, protocol=4)
        os.replace(tmp, f)

    def load_lm_lex(self) -> None:
        from fidetype.lm.ngram import CharNgramLM

        self.lm = CharNgramLM.load(own("eng_tatoeba_6gram_mkn_noE2Q.npz"))
        self.lex = frozenset(load_json(own("lexicon.json"))["words"])  # type: ignore[index]

    def beam(self, x: np.ndarray) -> list[tuple[str, float]]:
        k = window_key(x)
        hit = self.cache.get(k)
        if hit is not None:
            self.hits += 1
            return hit
        self.misses += 1
        out = beam_nbest(x)
        self.cache[k] = out
        return out

    def lm_score(self, text: str) -> float:
        v = self._lm_memo.get(text)
        if v is None:
            v = self.lm.score_sentence(text) if text else self.lm.score_sentence("")
            if len(self._lm_memo) > 500_000:
                self._lm_memo.clear()
            self._lm_memo[text] = v
        return v

    def n_oov(self, text: str) -> int:
        return sum(w not in self.lex for w in text.split())

    def rescore(self, text: str, ac: float, w: float, c: float) -> float:
        return ac + w * self.lm_score(text) - c * self.n_oov(text)

    def intended(self, hyps: list[tuple[str, float]], w: float, c: float) -> list[tuple[str, float]]:
        merged: dict[str, float] = {}
        for t, ac in hyps:
            r = resolve(t)
            merged[r] = float(np.logaddexp(merged.get(r, -np.inf), ac))
        sc = sorted(((t, self.rescore(t, a, w, c)) for t, a in merged.items()), key=lambda kv: (-kv[1], kv[0]))
        return sc[:NBEST_OUT]

    def keys(self, hyps: list[tuple[str, float]], w: float, c: float) -> list[tuple[str, float]]:
        sc = sorted(((t, self.rescore(resolve(t), a, w, c)) for t, a in hyps), key=lambda kv: (-kv[1], kv[0]))
        return sc[:NBEST_OUT]


DEC = Decoder()


def oov_gate(text: str) -> bool:
    """Amendment 1: True (no output) if the text is empty or more than OOV_GATE of its words are out of lexicon."""
    words = text.split()
    return not words or DEC.n_oov(text) > OOV_GATE * len(words)


def decode_intended(log_probs: np.ndarray) -> list[tuple[str, float]]:
    """``decode_fn`` of arms S, SL, X: n-best intended texts (P11-11 decoder, tuned (w, c)); empty if gated."""
    out = DEC.intended(DEC.beam(log_probs), DEC.w, DEC.c)
    if not out or oov_gate(out[0][0]):
        return []
    return [(t, s) for t, s in out if t]


def decode_keys(log_probs: np.ndarray) -> list[tuple[str, float]]:
    """``decode_fn`` of arm K: n-best raw key texts, rescored on their intended text; empty if gated."""
    out = DEC.keys(DEC.beam(log_probs), DEC.w, DEC.c)
    if not out or oov_gate(resolve(out[0][0])):
        return []
    return out


def contains_block(s: str, longt: list[str], _idx: dict = {}) -> bool:
    """True if a blocked text (>= LM_BLOCK_MIN_LEN chars) is inside ``s``, or ``s`` (>= that length) is inside one.

    Fast form of ``any(t in s ...) or any(s in t ...)``: an index of the first LM_BLOCK_MIN_LEN characters of each
    blocked text, and the set of all substrings (>= that length) of the blocked texts.
    """
    L = LM_BLOCK_MIN_LEN
    key = id(longt)
    if _idx.get("key") != key:
        heads: dict[str, list[str]] = {}
        for t in longt:
            heads.setdefault(t[:L], []).append(t)
        subs = {t[i:j] for t in longt for i in range(len(t)) for j in range(i + L, len(t) + 1)}
        _idx.clear()
        _idx.update(key=key, heads=heads, subs=subs)
    heads, subs = _idx["heads"], _idx["subs"]
    if len(s) >= L and s in subs:
        return True
    for i in range(len(s) - L + 1):
        for t in heads.get(s[i:i + L], ()):
            if s.startswith(t, i):
                return True
    return False


# --- stage lm --------------------------------------------------------------------------------------------


def stage_lm(rows: list[dict]) -> dict:
    """Rebuild the English Tatoeba LM (build_lms.py recipe) with the 16 sessions' intended texts blocked."""
    f = own("eng_tatoeba_6gram_mkn_noE2Q.npz")
    rep_f = own("lm-report.json")
    if f.exists() and rep_f.exists():
        return load_json(rep_f)  # type: ignore[return-value]
    from fidetype.lm.ngram import CharNgramLM, exclude_sentences
    from fidetype.streams import corpus
    from fidetype.streams.vocab import normalize_text

    B = load_module("build_lms_p1111", EXPLM / "build_lms.py")
    t0 = time.time()
    targets = sorted({normalize_text(intended_truth(r)) for r in rows} - {""})
    sents = B.read_tatoeba("eng")
    perm = np.random.default_rng(B.SEED).permutation(len(sents))
    sents = [sents[i] for i in perm]
    old_block = {normalize_text(s) for s in corpus.sentences(2000)}
    kept0 = exclude_sentences(sents, old_block)
    block = set(targets)
    longt = [t for t in block if len(t) >= LM_BLOCK_MIN_LEN]
    kept = [s for s in exclude_sentences(kept0, block) if not contains_block(s, longt)]
    n_removed = len(kept0) - len(kept)
    heldout, train = kept[:B.N_HELDOUT], kept[B.N_HELDOUT:][:B.MAX_TRAIN["eng"]]
    lm = CharNgramLM(order=B.ORDER, smoothing="mkn")
    lm.meta.update(language="eng", source="Tatoeba per-language sentence export (downloads.tatoeba.org)",
                   licence="CC BY 2.0 FR (Tatoeba default; some sentences CC0). Attribution: Tatoeba contributors",
                   downloaded="2026-11-08", seed=B.SEED, n_heldout=len(heldout),
                   blocklist="fidetype corpus.py sentences + P11-11: intended texts of the 16 emg2qwerty sessions "
                             f"(exact; containment both ways for texts of >= {LM_BLOCK_MIN_LEN} chars)",
                   task="P11-11")
    lm.train(train, normalize=False)
    lm.save(f)
    rep = {"n_targets": len(targets), "n_long_targets": len(longt), "n_removed_extra": n_removed,
           "n_train": len(train), "n_heldout": len(heldout),
           "ppl_heldout_2000": lm.perplexity(heldout[:2000], normalize=False),
           "sha256": sha256_file(f), "seconds": round(time.time() - t0, 1)}
    save_json(rep, rep_f)
    log(f"lm: {rep}")
    return rep


# --- stage lexicon ---------------------------------------------------------------------------------------


def stage_lexicon() -> dict:
    f = own("lexicon.json")
    if f.exists():
        d = load_json(f)
        return {k: v for k, v in d.items() if k != "words"}  # type: ignore[union-attr]
    from fidetype.benchmark import tracks as TR

    vocab = load_json(P1101 / "index.json")["vocab"]  # type: ignore[index]
    units = {u.id: u.split for u in TR.local_units(TRACK, E2Q_DATA)}
    own_sessions = {s["session"] for s in p1109().sessions()}
    cnt: collections.Counter = collections.Counter()
    n = 0
    for p in sorted((P1101 / "sessions").glob("*.lab.npz")):
        s = p.name[:-len(".lab.npz")]
        if units.get(s) != "train":
            continue
        assert s not in own_sessions
        with np.load(p, allow_pickle=False) as z:
            kf, kt, lo, hi = z["key_frame"], z["key_tok"], z["prompt_lo"], z["prompt_hi"]
        for a, b in zip(lo, hi):
            m = (kf >= a) & (kf < b)
            codes = [A.token_key_code(vocab[int(t)]) for t in kt[m]]
            cnt.update(resolve(A.codes_to_key_text(" ".join(c for c in codes if c))).split())
        n += 1
    words = sorted(w for w, c in cnt.items() if c >= LEX_MIN_COUNT)
    d = {"n_train_sessions": n, "n_distinct": len(cnt), "n_tokens": int(sum(cnt.values())), "min_count": LEX_MIN_COUNT,
         "n_words": len(words), **RESEARCH, "words": words}
    save_json(d, f)
    log(f"lexicon: {n} track-train sessions, {len(words)} words (count >= {LEX_MIN_COUNT})")
    return {k: v for k, v in d.items() if k != "words"}


# --- stage nbest -----------------------------------------------------------------------------------------


def all_windows(rows: list[dict]):
    W = p1109().Windows()
    cal, ev = split_rows(rows)
    for r in cal:
        yield W.get(r)
    for i in null_pick(len(cal)):
        yield W.get(cal[i], "shuffled")
    for kind in ("real", "shuffled", "zeros"):
        for r in ev:
            yield W.get(r, kind)


def stage_nbest(rows: list[dict]) -> dict:
    DEC.load_cache()
    t0 = time.time()
    n = new = 0
    for x in all_windows(rows):
        k = window_key(x)
        n += 1
        if k in DEC.cache:
            continue
        DEC.cache[k] = beam_nbest(x)
        new += 1
        if new % 250 == 0:
            DEC.save_cache()
            log(f"nbest: {n} windows ({new} new), {time.time() - t0:.0f} s")
    DEC.save_cache()
    rec = {"windows": n, "new": new, "cached": len(DEC.cache), "seconds": round(time.time() - t0, 1)}
    log(f"nbest: {rec}")
    return rec


# --- stage tune ------------------------------------------------------------------------------------------


def tune_items(n_cal: int) -> list[int]:
    """Positions (in calibration order) of calibrate's fit + policy-grid parts (seed 0)."""
    order = np.random.default_rng(SEED).permutation(n_cal)
    return sorted(int(i) for i in order[:N_TUNE])


def stage_tune(rows: list[dict]) -> dict:
    f = own("tune.json")
    if f.exists():
        return load_json(f)  # type: ignore[return-value]
    DEC.load_cache()
    DEC.load_lm_lex()
    W = p1109().Windows()
    cal, _ = split_rows(rows)
    assert len(cal) == 1224, len(cal)
    pos = tune_items(len(cal))
    hyps = [DEC.beam(W.get(cal[i])) for i in pos]
    truths = [intended_truth(cal[i]) for i in pos]
    grid = []
    for w in W_GRID:
        for c in C_GRID:
            ex = sum(DEC.intended(h, w, c)[0][0] == t for h, t in zip(hyps, truths))
            grid.append({"w": w, "c": c, "exact": ex, "rate": ex / len(pos)})
    best = sorted(grid, key=lambda g: (-g["exact"], g["w"], g["c"]))[0]
    rec = {"n_tune": len(pos), "tune_digest": hashlib.sha256(",".join(map(str, pos)).encode()).hexdigest()[:16],
           "grid": grid, "w": best["w"], "c": best["c"], "rate": best["rate"],
           "rate_no_lm": sum(DEC.intended(h, 0.0, 0.0)[0][0] == t for h, t in zip(hyps, truths)) / len(pos)}
    save_json(rec, f)
    log(f"tune: w {best['w']}, c {best['c']}, tuning-part exact {best['rate']:.3f} (no LM {rec['rate_no_lm']:.3f})")
    return rec


def set_decoder(tune: dict) -> None:
    DEC.load_cache()
    DEC.load_lm_lex()
    DEC.w, DEC.c = float(tune["w"]), float(tune["c"])


# --- stage guards ----------------------------------------------------------------------------------------


def arm_kw(arm: str) -> dict:
    return {"S": {}, "SL": {"confidence": "learned"}, "X": {"confidence": "learned", "commit_unit": "prefix"},
            "K": {}}[arm]


def arm_fn(arm: str):
    return decode_keys if arm == "K" else decode_intended


def arm_truth(arm: str, r: dict) -> str:
    return key_truth(r) if arm == "K" else intended_truth(r)


def calibrate_arm(arm: str, rows: list[dict], tune: dict):
    import fidetype.trust as ft

    W = p1109().Windows()
    cal, _ = split_rows(rows)
    xs = [W.get(r) for r in cal]
    texts = [arm_truth(arm, r) for r in cal]
    nulls = [W.get(cal[i], "shuffled") for i in null_pick(len(cal))]
    return ft.calibrate(xs, texts, alpha=ALPHA, delta=DELTA, input_kind="logits", vocab=A.key_ctc_vocab(), blank=0,
                        input_scale="log_probs", frame_period=FRAME_S, decode_fn=arm_fn(arm), null_inputs=nulls,
                        decoder_name=DECODER_NAME + ("+raw-keys" if arm == "K" else "+intended-text"),
                        decoder_version=f"1-w{tune['w']}-c{tune['c']}", modality="emg", name=f"p11-11-{arm}",
                        seed=SEED, audit_text=False, **arm_kw(arm))


def stage_guards(rows: list[dict], tune: dict, arms: tuple[str, ...] = ARMS) -> dict:
    import fidetype.trust as ft

    set_decoder(tune)
    cal, ev = split_rows(rows)
    out = {}
    for arm in arms:
        rec_f = own(f"guard-{arm}.status.json")
        if rec_f.exists():
            out[arm] = load_json(rec_f)
            continue
        t0 = time.time()
        h0, m0 = DEC.hits, DEC.misses
        rec: dict = {"arm": arm, "n_cal": len(cal), "n_eval": len(ev), "cal_digest": p1109().split_digest(cal),
                     "eval_digest": p1109().split_digest(ev)}
        try:
            g = calibrate_arm(arm, rows, tune)
        except ft.NullControlError as e:
            rec.update(status="refused", reason=str(e)[:2000])
            log(f"guards {arm}: REFUSED ({time.time() - t0:.0f} s): {e}")
        else:
            g.save(own(f"guard-{arm}.json"))
            sh = g.sheet.to_dict()
            rec.update(status="guard", config_id=g.config_id, sheet=sh)
            save_json({"config_id": g.config_id, "sheet": sh, **RESEARCH}, OUT / f"guard-{arm}.json")
            log(f"guards {arm}: {g.config_id} ({time.time() - t0:.0f} s)\n{g.sheet}")
        rec["cache"] = {"hits": DEC.hits - h0, "misses": DEC.misses - m0}
        rec["seconds"] = round(time.time() - t0, 1)
        save_json(rec, rec_f)
        out[arm] = rec
    return out


# --- stage decide ----------------------------------------------------------------------------------------


def decide_one(guard, x: np.ndarray, fn) -> dict:
    t0 = time.perf_counter()
    r = guard.decide(x)
    dt = time.perf_counter() - t0
    nb = fn(x)
    return {"action": r.action, "text": r.text, "choices": list(r.choices)[:3], "p_top1": float(r.p_top1),
            "n_words_committed": r.n_words_committed, "complete": r.complete,
            "top1": nb[0][0].strip() if nb else "", "s": round(dt, 5)}


def stage_decide(rows: list[dict], tune: dict, arms: tuple[str, ...] = ARMS) -> dict:
    from fidetype.trust.dropin import load as load_guard

    set_decoder(tune)
    W = p1109().Windows()
    _, ev = split_rows(rows)
    out = {}
    for arm in arms:
        f = own(f"decisions-{arm}.json")
        if f.exists():
            out[arm] = load_json(f)
            continue
        st = load_json(own(f"guard-{arm}.status.json"))
        if st["status"] != "guard":  # type: ignore[index]
            out[arm] = {"status": "refused"}
            save_json(out[arm], f)
            continue
        g = load_guard(own(f"guard-{arm}.json"), decode_fn=arm_fn(arm))
        rec: dict = {"status": "guard", "units": [r["unit"] for r in ev]}
        t0 = time.time()
        for kind in ("real", "shuffled", "zeros"):
            rec[kind] = [decide_one(g, W.get(r, kind), arm_fn(arm)) for r in ev]
            log(f"decide {arm} {kind}: {len(ev)} prompts ({time.time() - t0:.0f} s)")
        save_json(rec, f)
        out[arm] = rec
    return out


# --- stage score -----------------------------------------------------------------------------------------


def same(a: str | None, b: str) -> bool:
    return a is not None and a.split() == b.split()


def safe_block(r: dict) -> dict:
    return {k: r.get(k) for k in ("value", "ci", "status", "n_commits", "n_wrong_commits", "measured_wrong_commit",
                                  "measured_wrong_commit_cp95", "no_bci_wpm", "committed_correct_words",
                                  "total_words", "minutes_neural", "minutes_correction", "unguarded_wpm",
                                  "wpm_no_penalty", "reading_cost", "status_note")}


def score_arm(arm: str, d: dict, ev: list[dict], sheet: dict) -> dict:
    from fidetype.benchmark import safe_wpm as SW
    from fidetype.utils.binomial import clopper_pearson

    truths = [arm_truth(arm, r) for r in ev]
    real = d["real"]
    com = [x["action"] == "commit" for x in real]
    if arm == "K":  # as the track scorer: words and characters of the key text
        from fidetype.benchmark.registry import keycodes_to_chars

        nw = [len(keycodes_to_chars(r["codes"]).split()) for r in ev]
        nch = [len(keycodes_to_chars(r["codes"])) for r in ev]
    else:
        nw = [len(t.split()) for t in truths]
        nch = [len(t) for t in truths]
    neural = [r["neural_s"] for r in ev]
    cl = [{"group": f"u{r['i']}"} for r in ev]
    g = SW.guarantee_from_sheet(sheet)
    ctl = SW.controls_from_sheet(sheet)
    timing = "measured per prompt (first to last key-down, track truth neural_s)"
    a: dict = {}
    if arm == "X":
        outs = [SW.prefix_outcome(x["text"] or "", t, bool(x["complete"])) if c else None
                for c, x, t in zip(com, real, truths)]
        cor = [bool(o and o["correct"]) for o in outs]
        cw = [(o["committed_words"] if o else 0) for o in outs]
        full = [bool(x["complete"]) if c else True for c, x in zip(com, real)]
        pen = [(o["penalty_chars"] if o else 0) for o in outs]
        wrong = sum(c and not k for c, k in zip(com, cor))
        v02 = dict(metric_version="0.2", committed_words=cw, complete=full, penalty_chars=pen)
        r02 = SW.safe_wpm(com, cor, nw, nch, neural, guarantee=g, controls=ctl, timing=timing, clusters=cl,
                          ci_unit="group", B=2000, seed=0, read_s_per_commit=0.0, read_s_per_word=0.0, **v02)
        r02r = SW.safe_wpm(com, cor, nw, nch, neural, guarantee=g, controls=ctl, timing=timing, clusters=cl,
                           ci_unit="group", B=2000, seed=0, read_s_per_commit=READ_S_PER_COMMIT,
                           read_s_per_word=READ_S_PER_WORD, **v02)
        # v0.1 complete-only: prefix commits become no commit (P5-24 rule)
        com_c = [c and bool(x["complete"]) for c, x in zip(com, real)]
        cor_c = [c and same(x["text"], t) for c, x, t in zip(com_c, real, truths)]
        r01c = SW.safe_wpm(com_c, cor_c, nw, nch, neural, guarantee=g, controls=ctl, timing=timing, clusters=cl,
                           ci_unit="group", B=2000, seed=0, metric_version="0.1")
        a.update(safe_v02=safe_block(r02), safe_v02_read=safe_block(r02r), safe_v01_complete_only=safe_block(r01c),
                 n_prefix_commits=sum(c and not bool(x["complete"]) for c, x in zip(com, real)),
                 n_complete_commits=sum(com_c), committed_right_words=int(sum(o["credit_words"] for o in outs if o)))
    else:
        cor = [c and same(x["text"], t) for c, x, t in zip(com, real, truths)]
        wrong = sum(c and not k for c, k in zip(com, cor))
        r01 = SW.safe_wpm(com, cor, nw, nch, neural, guarantee=g, controls=ctl, timing=timing, clusters=cl,
                          ci_unit="group", B=2000, seed=0, metric_version="0.1")
        r02 = SW.safe_wpm(com, cor, nw, nch, neural, guarantee=g, controls=ctl, timing=timing, clusters=cl,
                          ci_unit="group", B=2000, seed=0, metric_version="0.2", read_s_per_commit=0.0, read_s_per_word=0.0)
        r02r = SW.safe_wpm(com, cor, nw, nch, neural, guarantee=g, controls=ctl, timing=timing, clusters=cl,
                           ci_unit="group", B=2000, seed=0, metric_version="0.2", read_s_per_commit=READ_S_PER_COMMIT,
                           read_s_per_word=READ_S_PER_WORD)
        always_c = [True] * len(ev)
        always_k = [same(x["top1"], t) for x, t in zip(real, truths)]
        ra = SW.safe_wpm(always_c, always_k, nw, nch, neural, guarantee=None, timing=timing, clusters=cl,
                         ci_unit="group", B=2000, seed=0, metric_version="0.1")
        a.update(safe_v01=safe_block(r01), safe_v02=safe_block(r02), safe_v02_read=safe_block(r02r),
                 always_commit={"unguarded_wpm": ra.get("unguarded_wpm"), "n_right": int(sum(always_k))})
    lo, hi = clopper_pearson(wrong, len(ev), 0.95)
    nc = int(sum(com))
    a.update(n_eval=len(ev), n_commits=nc, n_wrong_commits=int(wrong), wrong_commit_rate=wrong / len(ev),
             wrong_commit_cp95=[lo, hi], commit_rate=nc / len(ev), error_among_commits=(wrong / nc) if nc else None,
             top1_exact=sum(same(x["top1"], t) for x, t in zip(real, truths)) / len(ev),
             actions={k: sum(x["action"] == k for x in real) for k in ("commit", "offer", "withhold")},
             decide_s={"p50": float(np.median([x["s"] for x in real])),
                       "p95": float(np.percentile([x["s"] for x in real], 95))})
    for kind in ("shuffled", "zeros"):
        k = sum(x["action"] == "commit" for x in d[kind])
        a[f"control_{kind}_commits"] = int(k)
        a[f"control_{kind}_rate"] = k / len(ev)
    return a


def verdicts(a: dict, sheet: dict, arm: str) -> dict:
    sw = a["safe_v02"] if arm == "X" else a["safe_v01"]
    lo = a["wrong_commit_cp95"][0]
    v = {"V1_guard": "certified" if sheet.get("feasible", True) else "refused (infeasible)",
         "V2_safety": ("clear violation" if lo > ALPHA else "holds" if a["wrong_commit_rate"] <= ALPHA else "fails"),
         "V3_value": ("non-vacuous" if sw["status"] == "certified" and a["n_commits"] > 0 and (sw["value"] or 0) > 0
                      else "vacuous" if a["n_commits"] == 0 else f"no certified value (status {sw['status']})")}
    ref = sw.get("no_bci_wpm")
    val = sw.get("value") or 0.0
    ci = sw.get("ci") or [None, None]
    if ref is not None:
        v["V4_vs_no_bci"] = ("clearly above" if ci[0] is not None and ci[0] > ref else
                             "above" if val > ref else "below")
        v["V4_vs_p1109_2.93"] = "above" if val > 2.93 else "below"
    ctl_ok = all(c.get("passed") for c in sheet.get("controls", []))
    v["V6_controls"] = ("pass" if ctl_ok and a["control_shuffled_rate"] <= ALPHA and a["control_zeros_rate"] <= ALPHA
                        else "fail")
    return v


def stage_score(rows: list[dict], tune: dict) -> dict:
    cal, ev = split_rows(rows)
    lexd = load_json(own("lexicon.json"))
    lex = set(lexd["words"])  # type: ignore[index]
    ev_words = [w for r in ev for w in intended_truth(r).split()]
    res: dict = {"task": "P11-11", "date": time.strftime("%Y-%m-%d %H:%M"), **RESEARCH,
                 "note": "aggregates only (no per-user value, no text, no id)",
                 "tune": {k: tune[k] for k in ("w", "c", "rate", "rate_no_lm", "n_tune", "tune_digest")},
                 "lm": load_json(own("lm-report.json")),
                 "lexicon": {**{k: v for k, v in lexd.items() if k != "words"},  # type: ignore[union-attr]
                             "eval_truth_word_coverage": sum(w in lex for w in ev_words) / len(ev_words)},
                 "eval": {"n_prompts": len(ev), "n_words_intended": len(ev_words),
                          "minutes_neural": sum(r["neural_s"] for r in ev) / 60.0,
                          "share_with_backspace": sum("Backspace" in r["codes"] for r in ev) / len(ev)},
                 "arms": {}}
    for arm in ARMS:
        st = load_json(own(f"guard-{arm}.status.json"))
        a: dict = {"status": st["status"], "cal_digest": st["cal_digest"], "eval_digest": st["eval_digest"],
                   "cache": st.get("cache")}
        if st["status"] != "guard":
            a["reason"] = st.get("reason")
            res["arms"][arm] = a
            continue
        sh = st["sheet"]
        a["config_id"] = st["config_id"]
        a["sheet"] = {k: sh.get(k) for k in ("alpha", "delta", "n_items", "n_fit", "n_policy", "n_ltt", "feasible",
                                             "commit_threshold", "controls", "warnings", "confidence")}
        d = load_json(own(f"decisions-{arm}.json"))
        a.update(score_arm(arm, d, ev, sh))
        a["verdicts"] = verdicts(a, sh, arm)
        res["arms"][arm] = a
        log(f"score {arm}: commits {a['n_commits']} wrong {a['n_wrong_commits']} of {len(ev)}; {a['verdicts']}")
    # P11-09 digests must match
    p9 = load_json(P1109 / "guard-P.status.json")
    res["digests_match_p1109"] = all(res["arms"][a]["cal_digest"] == p9["cal_digest"] and
                                     res["arms"][a]["eval_digest"] == p9["eval_digest"] for a in ARMS)
    save_json(res, OUT / "results.json")
    return res


# --- main ------------------------------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stages", nargs="+", choices=("lm", "lexicon", "nbest", "tune", "guards", "decide", "score", "all"))
    ap.add_argument("--arms", default=",".join(ARMS))
    a = ap.parse_args()
    arms = tuple(x for x in a.arms.split(",") if x)
    st = set(a.stages)
    if "all" in st:
        st |= {"lm", "lexicon", "nbest", "tune", "guards", "decide", "score"}
    keep_awake(True)
    try:
        rows = prompts()
        p1109().check_track_splits(p1109().sessions())
        if "lm" in st:
            stage_lm(rows)
        if "lexicon" in st:
            stage_lexicon()
        if "nbest" in st:
            stage_nbest(rows)
        tune = stage_tune(rows) if st & {"tune", "guards", "decide", "score"} else None
        if "guards" in st:
            stage_guards(rows, tune, arms)
        if "decide" in st:
            stage_decide(rows, tune, arms)
            DEC.save_cache()
        if "score" in st:
            stage_score(rows, tune)
        if "all" in a.stages:
            (OWN / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
            log("all: DONE")
    finally:
        keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
