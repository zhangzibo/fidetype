"""P15-38: rebuild the Tatoeba 6-gram with every Willett text blocked, re-score the 41 E1a runs (CPU only).

Stages (``all`` runs them in order; finished units are skipped):
  blocks    the blocked texts: Willett (all 1,000 trials of the 10 sentences.mat + E1a meta.json) and the
            P11-11 emg2qwerty intended texts (local file only)
  lm0       recipe check: the P11-11 build with the Willett block empty; arrays compared with the P11-11 LM
  lm        the new LM (P11-11 recipe + Willett block); checks LMa / LMb
  overlap   descriptive overlap counts (Willett / emg2qwerty / Tatoeba export)
  check     C0' (greedy edits = P15-25 G) and R0 (F with the old LM = P15-25 F on two runs)
  lmonly    what F (new LM) emits on all-blank and on uniform log-probs
  test      F, FL, Fv (new LM) on the test log-probs of all 41 runs; F on the 12 time-shuffled C1 sets
  summary   M1-M4, verdicts (P15-25 code, unchanged), L1, L2 -> results/summary.json

It reads the P15-25 log-probs and decodes (``derived/p15-25``, read only) and writes only to
``derived/p15-38`` and ``results/``. Our own code (Apache-2.0); it imports P15-25 ``common.py``, P11-07
``lmbeam.py`` and P11-11 ``run.py`` (``contains_block``, ``intended_truth``) unchanged.

    .venv/Scripts/python.exe -I experiments/2026-11-20-p15-38-e1-lm-willett-blocked/run.py all
"""

from __future__ import annotations

import os
import sys

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ.setdefault("HIP_VISIBLE_DEVICES", "")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import hashlib  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

LMBEAM = REPO / "experiments" / "2026-11-20-p11-07-emg-beam-lm" / "lmbeam.py"
NEW_DECODERS = ("F", "FL", "Fv")
OLD_DECODERS = ("G", "B0", "F", "FL", "Fv")
LP = C.P1525 / "lp"  # READ ONLY
OLD_DEC = C.P1525 / "dec"  # READ ONLY
DEC = C.OWN / "dec"

_LMS: dict[str, object] = {}
_LEX = None
_META = None


def P():
    return C.p1525()


def p1111():
    """The P11-11 runner as a module. Read-only use: never call its stage functions, own(), log or caches."""
    return C.load_module("p1111run", REPO / C.config()["p1111_dir"] / "run.py")


def lb():
    return C.load_module("lmbeam_p1107", LMBEAM)


def lm_path(which: str) -> Path:
    return Path(C.config()["old_lm"]) if which == "old" else C.OWN / C.config()["new_lm"]


def get_lm(which: str):
    if which not in _LMS:
        from fidetype.lm.ngram import CharNgramLM

        _LMS[which] = CharNgramLM.load(lm_path(which))
    return _LMS[which]


def lexicon() -> frozenset[str]:
    """P11-11 lexicon, normalised as the LM text and split (the P11-07 / P15-25 rule)."""
    global _LEX
    if _LEX is None:
        from fidetype.streams.vocab import normalize_text

        ws = C.load_json(Path(C.config()["lexicon"]))["words"]  # type: ignore[index]
        _LEX = frozenset(p for w in ws for p in normalize_text(w).split())
    return _LEX


def meta() -> list[dict]:
    global _META
    if _META is None:
        _META = C.load_json(Path(C.config()["willett_meta"]))  # type: ignore[assignment]
    return _META  # type: ignore[return-value]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# --- blocked texts ------------------------------------------------------------------------------------------


def stage_blocks() -> dict:
    """Willett texts (normalised) and the P11-11 emg2qwerty intended texts. Local file (texts) + counts."""
    f = C.own("blocks.json")
    if f.exists():
        d = C.load_json(f)
        return {k: v for k, v in d.items() if not k.endswith("_texts")}  # type: ignore[union-attr]
    from scipy.io import loadmat

    from fidetype.adapters import willett_handwriting as W
    from fidetype.streams.vocab import normalize_text

    cfg = C.config()
    files = W.list_session_files(cfg["willett_root"])
    raw: list[str] = []
    per_file = {}
    for p in files:
        d = loadmat(p, variable_names=["intendedText"])
        t = [W.ascii_to_text(s) for s in W._cellstr(d["intendedText"])]
        per_file[p.parent.name] = len(t)
        raw += t
    raw_n = {normalize_text(t) for t in raw} - {""}
    meta_n = {normalize_text(x["text"]) for x in meta()} - {""}
    willett = sorted(raw_n | meta_n)
    rows = C.load_json(Path(cfg["e2q_prompts"]))
    e2q = sorted({normalize_text(p1111().intended_truth(r)) for r in rows} - {""})  # type: ignore[union-attr]
    L = p1111().LM_BLOCK_MIN_LEN
    rec = {"willett_files": per_file, "willett_trials": len(raw), "willett_unique_raw": len(raw_n),
           "willett_unique_meta": len(meta_n), "willett_meta_not_in_raw": len(meta_n - raw_n),
           "willett_unique": len(willett), "willett_long": sum(len(t) >= L for t in willett),
           "e2q_unique": len(e2q), "e2q_long": sum(len(t) >= L for t in e2q),
           "willett_in_e2q_exact": len(set(willett) & set(e2q)), "block_min_len": L,
           "willett_texts": willett, "e2q_texts": e2q}  # texts stay local (derived/p15-38)
    C.save_json(rec, f)
    out = {k: v for k, v in rec.items() if not k.endswith("_texts")}
    C.log(f"blocks: {out}")
    return out


def blocks() -> tuple[list[str], list[str]]:
    d = C.load_json(C.own("blocks.json"))
    return d["willett_texts"], d["e2q_texts"]  # type: ignore[index]


# --- LM build (P11-11 stage_lm recipe) ----------------------------------------------------------------------


def build_lm(extra: set[str], fname: str, report: str, task: str) -> dict:
    """P11-11 ``stage_lm`` with ``extra`` added to the blocked texts. Returns the report (+ local train lists)."""
    f = C.own(fname)
    rep_f = C.own(report)
    if f.exists() and rep_f.exists():
        return C.load_json(rep_f)  # type: ignore[return-value]
    from fidetype.lm.ngram import CharNgramLM, exclude_sentences
    from fidetype.streams import corpus
    from fidetype.streams.vocab import normalize_text

    M = p1111()
    B = C.load_module("build_lms_p1538", M.EXPLM / "build_lms.py")
    t0 = time.time()
    _, e2q = blocks()
    sents = B.read_tatoeba("eng")
    perm = np.random.default_rng(B.SEED).permutation(len(sents))
    sents = [sents[i] for i in perm]
    old_block = {normalize_text(s) for s in corpus.sentences(2000)}
    kept0 = exclude_sentences(sents, old_block)
    del sents
    block = set(e2q) | set(extra)
    longt = [t for t in block if len(t) >= M.LM_BLOCK_MIN_LEN]
    kept = [s for s in exclude_sentences(kept0, block) if not M.contains_block(s, longt)]
    n_removed = len(kept0) - len(kept)
    heldout, train = kept[:B.N_HELDOUT], kept[B.N_HELDOUT:][:B.MAX_TRAIN["eng"]]
    lm = CharNgramLM(order=B.ORDER, smoothing="mkn")
    lm.meta.update(language="eng", source="Tatoeba per-language sentence export (downloads.tatoeba.org)",
                   licence="CC BY 2.0 FR (Tatoeba default; some sentences CC0). Attribution: Tatoeba contributors",
                   downloaded="2026-11-08", seed=B.SEED, n_heldout=len(heldout),
                   blocklist="fidetype corpus.py sentences + P11-11: intended texts of the 16 emg2qwerty sessions"
                             + (" + P15-38: every Willett handwriting sentence (all 1,000 trials)" if extra else "")
                             + f" (exact; containment both ways for texts of >= {M.LM_BLOCK_MIN_LEN} chars)",
                   task=task)
    lm.train(train, normalize=False)
    lm.save(f)
    rep = {"n_kept0": len(kept0), "n_block": len(block), "n_long_block": len(longt), "n_removed_extra": n_removed,
           "n_train": len(train), "n_heldout": len(heldout),
           "ppl_heldout_2000": lm.perplexity(heldout[:2000], normalize=False),
           "sha256": sha256_file(f), "seconds": round(time.time() - t0, 1), "peak_mb": round(P().peak_mb(), 1)}
    if extra:
        W = sorted(extra)
        wset = set(W)
        wlong = [t for t in W if len(t) >= M.LM_BLOCK_MIN_LEN]
        rep["LMa_exact_in_lm_text"] = sum(s in wset for s in heldout) + sum(s in wset for s in train)
        rep["LMb_containment_in_lm_text"] = sum(M.contains_block(s, wlong) for s in heldout) + \
            sum(M.contains_block(s, wlong) for s in train)
        # the P11-11 LM text under the same recipe (for the M3 / overlap story): Willett texts it held
        e2q_long = [t for t in set(e2q) if len(t) >= M.LM_BLOCK_MIN_LEN]  # one list: contains_block caches by id
        k0 = [s for s in exclude_sentences(kept0, set(e2q)) if not M.contains_block(s, e2q_long)]
        old_txt = k0[:B.N_HELDOUT + B.MAX_TRAIN["eng"]]
        old_train = set(k0[B.N_HELDOUT:][:B.MAX_TRAIN["eng"]])
        rep["old_lm_train_willett_exact"] = len(old_train & wset)
        rep["old_lm_heldout_willett_exact"] = len(set(old_txt[:B.N_HELDOUT]) & wset)
        rep["old_lm_train_willett_containment"] = sum(M.contains_block(s, wlong) for s in old_train)
        rep["peak_mb"] = round(P().peak_mb(), 1)
    C.save_json(rep, rep_f)
    C.log(f"{task} lm {fname}: {rep}")
    return rep


def stage_lm0() -> dict:
    rep = build_lm(set(), C.config()["lm0"], "lm0-report.json", "P15-38 LM0 (P11-11 recipe check)")
    if "LM0_pass" in rep:
        return rep
    a = np.load(C.own(C.config()["lm0"]), allow_pickle=False)
    b = np.load(C.config()["old_lm"], allow_pickle=False)
    import json

    ha, hb = json.loads(str(a["header_json"])), json.loads(str(b["header_json"]))
    keys = sorted((set(a.files) | set(b.files)) - {"header_json"})
    diff = [k for k in keys if k not in a.files or k not in b.files or a[k].shape != b[k].shape
            or not np.array_equal(a[k], b[k])]
    same_hdr = all(ha[k] == hb[k] for k in ("format", "format_version", "order", "smoothing", "discounts"))
    rep["LM0_arrays"] = len(keys)
    rep["LM0_arrays_different"] = diff
    rep["LM0_header_equal"] = bool(same_hdr)
    rep["LM0_pass"] = bool(not diff and same_hdr)
    rep["old_lm_sha256_ok"] = sha256_file(Path(C.config()["old_lm"])) == C.config()["old_lm_sha256"]
    C.save_json(rep, C.own("lm0-report.json"))
    C.log(f"lm0: pass {rep['LM0_pass']} ({len(keys)} arrays, different {diff}, header equal {same_hdr}); "
          f"old sha ok {rep['old_lm_sha256_ok']}")
    a.close()
    b.close()
    return rep


def stage_lm() -> dict:
    W, _ = blocks()
    return build_lm(set(W), C.config()["new_lm"], "lm-report.json", "P15-38")


# --- overlap (descriptive) ----------------------------------------------------------------------------------


def stage_overlap() -> dict:
    f = C.own("overlap.json")
    if f.exists():
        return C.load_json(f)  # type: ignore[return-value]
    from fidetype.streams.vocab import normalize_text

    M = p1111()
    B = C.load_module("build_lms_p1538", M.EXPLM / "build_lms.py")
    tat = set(B.read_tatoeba("eng"))
    W, E = blocks()
    L = M.LM_BLOCK_MIN_LEN
    wlong = [t for t in W if len(t) >= L]
    # Willett texts hit by the containment rule (either way) somewhere in the export
    hit_c: set[str] = set()
    n_tat_c = 0
    for s in tat:
        if M.contains_block(s, wlong):
            n_tat_c += 1
            for t in W:
                if (len(t) >= L and t in s) or (len(s) >= L and s in t):
                    hit_c.add(t)
    sp = C.load_json(Path(C.config()["willett_splits"]))
    m = meta()
    rec: dict = {"tatoeba_unique": len(tat), "tatoeba_sentences_hit_by_willett_containment": n_tat_c}
    test_mask = None
    for split in ("test", "val", "pool"):
        txt = [normalize_text(m[i]["text"]) for i in sp[split]]  # type: ignore[index]
        uniq = sorted(set(txt))
        rec[split] = {"sentences": len(txt), "in_tatoeba": sum(t in tat for t in txt),
                      "in_tatoeba_or_containment": sum((t in tat) or (t in hit_c) for t in txt),
                      "unique": len(uniq), "unique_in_tatoeba": sum(t in tat for t in uniq),
                      "unique_in_tatoeba_or_containment": sum((t in tat) or (t in hit_c) for t in uniq)}
        if split == "test":
            test_mask = {int(i): bool(t in tat) for i, t in zip(sp[split], txt)}  # type: ignore[index]
    rec["all_willett_unique"] = {"unique": len(W), "in_tatoeba": sum(t in tat for t in W),
                                 "in_tatoeba_or_containment": sum((t in tat) or (t in hit_c) for t in W)}
    rec["e2q"] = {"unique": len(E), "in_tatoeba": sum(t in tat for t in E),
                  "willett_in_e2q_exact": len(set(W) & set(E))}
    C.save_json(rec, f)
    C.save_json({"test_in_tatoeba_by_meta_index": test_mask}, C.own("test_mask.json"))  # local (indices only)
    C.log(f"overlap: {rec}")
    return rec


# --- decoding -----------------------------------------------------------------------------------------------


def decode(x: np.ndarray, cfg: dict, which: str) -> list[int]:
    if cfg.get("greedy"):
        return P().greedy_tokens(x)
    use_lm = cfg.get("w", 0) > 0
    d = lb().LMBeam(P().VOCAB, 0, lm=get_lm(which) if use_lm else None, lm_weight=cfg.get("w", 0.0),
                    bonus=cfg.get("beta", 0.0), beam=int(cfg["B"]), prune_logp=float(C.config()["prune_logp"]),
                    lexicon=lexicon() if cfg.get("lam", 0) > 0 else None, lam=cfg.get("lam", 0.0))
    d.push(x)
    hs = d.nbest(1)
    return hs[0].tokens if hs else []


def unit_path(dec: str, split: str, run: str) -> Path:
    return DEC / dec / split / f"{run}.json"


def old_unit(dec: str, split: str, run: str) -> dict:
    return C.load_json(OLD_DEC / dec / split / f"{run}.json")  # type: ignore[return-value]


def _job(args: tuple) -> dict:
    """Worker: decode one (decoder id, split, run) with cfg and LM ``which``; per-sentence edits (local hyps)."""
    dec, split, run, cfg, which = args
    f = unit_path(dec, split, run)
    if f.exists():
        return C.load_json(f)  # type: ignore[return-value]
    if C.stop_requested():
        return {"stopped": True}
    t0 = time.time()
    ix = C.load_json(LP / run / f"{split}.json")
    arr = np.load(LP / run / f"{split}.npy", mmap_mode="r")
    off = ix["offsets"]  # type: ignore[index]
    m = meta()
    edits, refs, hyps = [], [], []
    for j, i in enumerate(ix["idx"]):  # type: ignore[index]
        x = np.asarray(arr[off[j]:off[j + 1]], np.float64)
        h = decode(x, cfg, which)
        r = P().encode(m[i]["text"])
        edits.append(P().levenshtein(r, h))
        refs.append(len(r))
        hyps.append("".join(P().VOCAB[t] for t in h))
    rec = {"decoder": dec, "split": split, "run": run, "cfg": cfg, "lm": which, "idx": list(ix["idx"]),  # type: ignore[index]
           "cer": sum(edits) / max(1, sum(refs)), "edits": edits, "ref": refs, "hyp_len": sum(len(h) for h in hyps),
           "seconds": round(time.time() - t0, 2), "peak_mb": round(P().peak_mb(), 1),
           "hyp_local": hyps}  # text stays in derived/p15-38 (never committed)
    C.save_json(rec, f)
    return rec


def run_pool(jobs: list[tuple], label: str) -> list[dict]:
    todo = [j for j in jobs if not unit_path(j[0], j[1], j[2]).exists()]
    C.log(f"{label}: {len(jobs)} units, {len(todo)} to do")
    peak = 0.0
    if todo:
        import multiprocessing as mp

        n = min(int(C.config()["workers"]), len(todo))
        t0 = time.time()
        with mp.get_context("spawn").Pool(n) as pool:
            for k, rec in enumerate(pool.imap_unordered(_job, todo), 1):
                if rec.get("stopped"):
                    continue
                peak = max(peak, rec.get("peak_mb", 0.0))
                if k % 10 == 0 or k == len(todo):
                    C.log(f"{label}: {k}/{len(todo)} (last {rec['decoder']} {rec['split']} {rec['run']} "
                          f"cer {rec['cer']:.4f}, {rec['seconds']} s; worker peak {peak:.0f} MB; "
                          f"{time.time() - t0:.0f} s)")
    if C.stop_requested():
        C.log(f"{label}: STOP file seen; exit")
        raise SystemExit(3)
    return [C.load_json(unit_path(*j[:3])) for j in jobs]  # type: ignore[misc]


def stage_check() -> dict:
    f = C.own("check.json")
    if f.exists():
        return C.load_json(f)  # type: ignore[return-value]
    cfg = C.config()
    runs = P().all_runs()
    jobs = [("G", "test", r, {"greedy": True}, "none") for r in runs]
    jobs += [("R0-F-oldLM", "test", r, cfg["decoders"]["F"], "old") for r in cfg["r0_runs"]]
    recs = run_pool(jobs, "check")
    c0 = [{"run": x["run"], "same": x["edits"] == old_unit("G", "test", x["run"])["edits"]} for x in recs
          if x["decoder"] == "G"]
    r0 = [{"run": x["run"], "cer": x["cer"], "p1525_cer": old_unit("F", "test", x["run"])["cer"],
           "same": x["edits"] == old_unit("F", "test", x["run"])["edits"]} for x in recs if x["decoder"] != "G"]
    rec = {"C0p": {"pass": all(x["same"] for x in c0), "n_same": sum(x["same"] for x in c0), "n": len(c0)},
           "R0": {"pass": all(x["same"] for x in r0), "runs": r0}}
    C.save_json(rec, f)
    C.log(f"check: C0' {rec['C0p']}; R0 {rec['R0']}")
    return rec


def stage_lmonly() -> dict:
    f = C.own("lmonly.json")
    if f.exists():
        return C.load_json(f)  # type: ignore[return-value]
    cfg = C.config()["decoders"]["F"]
    T = 4100
    blank = np.full((T, 98), -1e9)
    blank[:, 0] = 0.0
    uni = np.full((T, 98), -np.log(98.0))
    rec = {}
    for name, x in (("all_blank", blank), ("uniform", uni)):
        h = decode(x, cfg, "new")
        rec[name] = {"frames": T, "n_tokens": len(h), "text_local": "".join(P().VOCAB[t] for t in h)[:200]}
    C.save_json(rec, f)
    C.log(f"lmonly: all_blank {rec['all_blank']['n_tokens']} tokens, uniform {rec['uniform']['n_tokens']} tokens")
    return rec


def stage_test() -> None:
    cfg = C.config()
    runs = P().all_runs()
    jobs = [(dec, "test", r, cfg["decoders"][dec], "new") for r in runs for dec in NEW_DECODERS]
    jobs += [("F", "shuf", r, cfg["decoders"]["F"], "new") for r in P().c1_runs()]
    run_pool(jobs, "test")


# --- summary ------------------------------------------------------------------------------------------------


def status(v: dict, key: str) -> str:
    x = v.get(key)
    if x is None:
        return "-"
    if "status" in x:
        return x["status"]
    return "pass" if x.get("pass") else "fail"


def l1(res_g: dict, res_f: dict, rules: dict, k: int) -> dict:
    """P15-25 L1 (same code path as P15-25 ``stage_summary``)."""
    out = []
    for r in ("E-ball-s0", "E-ball-s1"):
        eg = np.asarray(res_g[r]["edits"], float)
        ef = np.asarray(res_f[r]["edits"], float)
        ref = np.asarray(res_f[r]["ref"], float)
        bs = P().bootstrap(eg, ef, ref, int(rules["bootstrap_n"]), int(rules["bootstrap_seed"]), k)
        out.append({"run": r, "cer_G": res_g[r]["cer"], "cer_F": res_f[r]["cer"], "delta": bs["delta"],
                    "ci95": [bs["lo"], bs["hi"]], "ci_bonf": [bs["lo_bonf"], bs["hi_bonf"]],
                    "win": bool(bs["delta"] > 0 and bs["lo"] > 0),
                    "robust": bool(bs["delta"] > 0 and bs["lo_bonf"] > 0)})
    return {"runs": out, "pass": all(x["win"] for x in out), "robust": all(x["robust"] for x in out)}


def stage_summary() -> dict:
    cfg = C.config()
    e1a = P().e1a_config()
    rules = e1a["rules"]
    k = int(cfg["secondary_k"])
    runs = P().all_runs()
    c1r = P().c1_runs()
    e1a_res = {r: C.load_json(P().E1A_OUT / "runs" / r / "result.json") for r in runs}
    minutes = {r: float(e1a_res[r]["minutes"]) for r in runs}  # type: ignore[index]
    new = {dec: {r: C.load_json(unit_path(dec, "test", r)) for r in runs} for dec in NEW_DECODERS}
    new["G"] = {r: C.load_json(unit_path("G", "test", r)) for r in runs}
    old = {dec: {r: old_unit(dec, "test", r) for r in runs} for dec in OLD_DECODERS}
    shuf_new = {r: C.load_json(unit_path("F", "shuf", r))["cer"] for r in c1r}  # type: ignore[index]
    shuf_old = {r: old_unit("F", "shuf", r)["cer"] for r in c1r}
    out: dict = {"task": "P15-38", "decoders": cfg["decoders"], "primary": cfg["primary_decoder"],
                 "secondary_k": k, "old_lm_sha256": cfg["old_lm_sha256"],
                 "data": {"licence": "Willett CC0-1.0; T/E/S runs and FL lexicon CC-BY-NC-SA-4.0 (research only); "
                                     "LM text Tatoeba CC BY 2.0 FR", "research_only_parts": ["T", "E", "S", "FL"]}}
    for extra in ("blocks.json", "lm0-report.json", "lm-report.json", "overlap.json", "check.json", "lmonly.json"):
        d = C.load_json(C.own(extra))
        if extra == "blocks.json":
            d = {kk: vv for kk, vv in d.items() if not kk.endswith("_texts")}  # type: ignore[union-attr]
        if extra == "lmonly.json":
            d = {kk: {"frames": vv["frames"], "n_tokens": vv["n_tokens"]} for kk, vv in d.items()}  # type: ignore[union-attr]
        out[extra.split(".")[0].replace("-", "_")] = d
    # verdicts: P15-25 code, unchanged
    v_new = {dec: P().verdict(new[dec], minutes, e1a, k, shuf=shuf_new if dec == "F" else None)
             for dec in NEW_DECODERS}
    v_old = {dec: P().verdict(old[dec], minutes, e1a, k, shuf=shuf_old if dec == "F" else None)
             for dec in ("F", "FL", "Fv")}
    g_shuf = {r: float(e1a_res[r]["c1_shuffled_cer"]) for r in c1r if "c1_shuffled_cer" in e1a_res[r]}  # type: ignore[index]
    v_g = P().verdict(new["G"], minutes, e1a, k, shuf=g_shuf)
    out["verdicts_new"] = v_new
    out["verdicts_old"] = v_old
    out["L1_new"] = l1(new["G"], new["F"], rules, k)
    out["L1_old"] = l1(old["G"], old["F"], rules, k)
    keys = ("V1", "H1", "H2", "H3", "H4", "H5", "H6", "roadmap_rule", "C1", "C2")
    # cross-check: our re-computed old F verdicts equal P15-25 summary.json
    s25 = C.load_json(REPO / cfg["p1525_dir"] / "results" / "summary.json")
    out["old_verdicts_match_p1525_summary"] = all(
        status(v_old["F"], kk) == status(s25["verdicts"]["F"], kk) for kk in keys)  # type: ignore[index]
    # M1
    rows = []
    for kk in keys + ("L1",):
        if kk == "L1":
            o, n = ("pass" if out["L1_old"]["pass"] else "fail"), ("pass" if out["L1_new"]["pass"] else "fail")
        else:
            o, n = status(v_old["F"], kk), status(v_new["F"], kk)
        rows.append({"id": kk, "G": status(v_g, kk) if kk != "L1" else "-", "F_old": o, "F_new": n,
                     "FL_old": status(v_old["FL"], kk) if kk != "L1" else "-",
                     "FL_new": status(v_new["FL"], kk) if kk != "L1" else "-",
                     "Fv_old": status(v_old["Fv"], kk) if kk != "L1" else "-",
                     "Fv_new": status(v_new["Fv"], kk) if kk != "L1" else "-"})
    hs = [r for r in rows if r["id"] in ("H1", "H2", "H3", "H4", "H5", "H6")]
    chk = out["check"]
    out["M1"] = {"rows": rows, "holds": all(r["F_old"] == r["F_new"] for r in hs),
                 "changed": [r["id"] for r in rows if r["F_old"] != r["F_new"]],
                 "comparable": bool(chk["C0p"]["pass"] and chk["R0"]["pass"])}
    # L2 on new F
    l2 = [{"id": kk, "G": status(v_g, kk), "F": status(v_new["F"], kk)} for kk in keys]
    out["L2_new"] = {"rows": l2, "holds": all(r["G"] == r["F"] for r in l2 if r["id"].startswith("H")),
                     "changed": [r["id"] for r in l2 if r["G"] != r["F"]]}
    # M2: CER change per arm / budget (and per run)
    out["runs"] = {r: {"G": new["G"][r]["cer"], "B0_p1525": old["B0"][r]["cer"],
                       **{f"{d}_old": old[d][r]["cer"] for d in NEW_DECODERS},
                       **{f"{d}_new": new[d][r]["cer"] for d in NEW_DECODERS},
                       "F_shuf_old": shuf_old.get(r), "F_shuf_new": shuf_new.get(r)} for r in runs}
    m2 = {}
    for dec in NEW_DECODERS:
        tn, to = v_new[dec]["table"], v_old[dec]["table"]
        m2[dec] = {a: {b: {"old": to[a][b]["mean"], "new": tn[a][b]["mean"], "delta": tn[a][b]["mean"] - to[a][b]["mean"],
                           "delta_seeds": [x - y for x, y in zip(tn[a][b]["seeds"], to[a][b]["seeds"])]}
                       for b in P().BUDGETS} for a in P().ARMS}
    out["M2"] = m2
    lab = "E-b30-s0-labelshuf"
    out["M2_labelshuf"] = {"old": old["F"][lab]["cer"], "new": new["F"][lab]["cer"]}
    # M3: CER on the 13 test sentences in Tatoeba vs the other 67
    mask_d = C.load_json(C.own("test_mask.json"))["test_in_tatoeba_by_meta_index"]  # type: ignore[index]
    m3 = []
    for r in cfg["m3_runs"]:
        idx = new["F"][r]["idx"]
        mk = np.asarray([mask_d[str(i)] for i in idx], bool)
        ref = np.asarray(new["F"][r]["ref"], float)
        row = {"run": r, "n_in": int(mk.sum()), "n_out": int((~mk).sum()),
               "chars_in": int(ref[mk].sum()), "chars_out": int(ref[~mk].sum())}
        for tag, src in (("old", old["F"][r]), ("new", new["F"][r]), ("G", new["G"][r])):
            e = np.asarray(src["edits"], float)
            row[f"{tag}_in"] = float(e[mk].sum() / ref[mk].sum())
            row[f"{tag}_out"] = float(e[~mk].sum() / ref[~mk].sum())
        m3.append(row)
    out["M3"] = m3
    # M4: per-run paired bootstrap of new - old
    m4 = []
    for r in cfg["m4_runs"]:
        en = np.asarray(new["F"][r]["edits"], float)
        eo = np.asarray(old["F"][r]["edits"], float)
        ref = np.asarray(new["F"][r]["ref"], float)
        bs = P().bootstrap(en, eo, ref, int(rules["bootstrap_n"]), int(rules["bootstrap_seed"]), k)
        m4.append({"run": r, "old": old["F"][r]["cer"], "new": new["F"][r]["cer"], "delta": bs["delta"],
                   "ci95": [bs["lo"], bs["hi"]], "ci_bonf": [bs["lo_bonf"], bs["hi_bonf"]],
                   "sentences_changed": int(np.sum(en != eo))})
    out["M4"] = m4
    out["hyp_ref_ratio_new"] = {dec: {r: new[dec][r]["hyp_len"] / max(1, sum(new[dec][r]["ref"])) for r in runs}
                                for dec in NEW_DECODERS}
    out["timing_s"] = {dec: round(sum(new[dec][r]["seconds"] for r in runs), 1) for dec in NEW_DECODERS}
    out["worker_peak_mb"] = max(new[dec][r]["peak_mb"] for dec in NEW_DECODERS for r in runs)
    C.save_json(out, C.OUT / "summary.json")
    C.log(f"summary: M1 holds {out['M1']['holds']} changed {out['M1']['changed']} comparable "
          f"{out['M1']['comparable']}; F new: V1 {v_new['F']['V1']}, H1 {v_new['F']['H1']['status']}; "
          f"old verdicts match P15-25 {out['old_verdicts_match_p1525_summary']}")
    return out


STAGES = ("blocks", "lm0", "lm", "overlap", "check", "lmonly", "test", "summary")


def main(argv: list[str]) -> int:
    stages = [a for a in argv if not a.startswith("--")] or ["all"]
    if stages == ["all"]:
        stages = list(STAGES)
    bad = [s for s in stages if s not in STAGES]
    if bad:
        C.log(f"run.py: unknown stages {bad}")
        return 2
    if not (LP / "DONE.json").exists():
        C.log("run.py: P15-25 lp/DONE.json missing")
        return 2
    P().keep_awake(True)
    t0 = time.time()
    try:
        for s in stages:
            C.log(f"start {s}")
            globals()[f"stage_{s}"]()
            C.log(f"end {s} (main peak {P().peak_mb():.0f} MB)")
    finally:
        P().keep_awake(False)
    if stages[-1] == "summary":
        C.own("DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
        C.log(f"ALL DONE ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
