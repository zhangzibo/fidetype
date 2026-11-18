"""P14-18 / P14-19: word-setting follow-ups of P14-15 (plan.md, pre-registered, commit 3d07cb4).

Stages (CPU only; run each in its own process):
  rebuild    P14-19 step 1: checks with the paper setting, then for the 35 changed re-splits the
             published-g1, ours-g0, published-g0 tables (+ published-m0/0.5/1/4 and trust v5 rows for r < 50)
             with the split's own fit-A setting; forward-chain prefix 0 with lm 1.0 / edit 8 / bonus 3.
  m4 --exp m412|m402   P14-18 A / B: M4 accuracy rows, reference (edit 12, committed cache read-only) and edit 8.
  p1403      P14-18 C: P14-03 T15 guard rows, reference (edit 12) and edit 8.
  analyze    P14-19 step 2 (R3 split_policies on published-g1 / ours-g0 / published-g0, forward chain) and
             P14-18 decision. Writes results/p14-19-step2.json, results/p14-18.json.
  downstream P14-19 step 3: reruns of the downstream analyses with redirected tables; results/p14-19-step3.json.
  queue      all of the above in order, one child process per stage.

Local outputs only: C:/Users/zhang/bci-data/derived/p14-18-19/. Repo: counts, rates and metrics only.
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- \\
      .venv\\Scripts\\python.exe -I experiments/2026-11-17-p14-18-19-followups/run.py --stage queue
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pickle  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP = REPO / "experiments"
R3 = EXP / "2026-11-12-paper1-r3-analyses"
R4 = EXP / "2026-11-12-paper1-r4-analyses"
P1415 = EXP / "2026-11-17-p14-15-retune"
SMOKE = int(os.environ.get("P1419_SMOKE", "0"))  # > 0: code check on a few trials, separate folder
DER = Path("C:/Users/zhang/bci-data/derived/p14-18-19")
assert DER.name == "p14-18-19"
if SMOKE:
    DER = DER / "smoke"
DER.mkdir(parents=True, exist_ok=True)
DER1415 = Path("C:/Users/zhang/bci-data/derived/p14-15-retune")  # read only
TABD = DER / "tables"
FWD = DER / "forward"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
PAPER = (1.0, 12.0, 3.0)
E8 = (1.0, 8.0, 3.0)
ALPHA = 0.05
MARGINS = (0.0, 0.5, 1.0, 4.0)
LOGF = DER / "run.log"


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        o = float(o)
    if isinstance(o, float) and not math.isfinite(o):
        return str(o)
    return o


def dump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(clean(obj), indent=1), encoding="utf-8")
    os.replace(tmp, path)


def changed_splits() -> list[dict]:
    tune = json.loads((P1415 / "results/tune.json").read_text(encoding="utf-8"))
    return [c for c in tune["T1"]["splits"] if not c["same_as_paper"]]


def r4():
    sys.path.insert(0, str(R4))
    import common4 as Q  # noqa: E402
    return Q


# ---------------------------------------------------------------------------
# P14-19 step 1: rebuild
# ---------------------------------------------------------------------------

def jobs(r: int) -> list[tuple[str, str, bool, float | None]]:
    j = [("published-g1", "published", True, None), ("ours-g0", "ours", False, None), ("published-g0", "published", False, None)]
    if r < 50:
        j += [(f"published-m{m:g}", "published", True, m) for m in MARGINS]
    return j


def same_table(a: dict, b: dict, n: int | None = None) -> dict:
    keys = [k for k in a if isinstance(a[k], list)]
    out = {k: (a[k][:n] if n else a[k]) == (b[k][:n] if n else b[k]) for k in keys}
    out["lam_old"] = a.get("lam_old") == b.get("lam_old")
    return out


def stage_rebuild() -> None:
    Q = r4()
    K, C = Q.K, Q.C
    C.Log.path = DER / "run-rebuild.log"
    K.install_snap(0.02)
    sp = Q.splits200()
    ctx = C.b2t_ctx()
    bt = ctx.bt
    trials = ctx.fit + ctx.test
    items = ctx.items(trials)
    TABD.mkdir(exist_ok=True)
    FWD.mkdir(exist_ok=True)
    state = {"key": None, "dec": None, "T": None}

    def use(key, T):
        key = tuple(float(x) for x in key)
        if state["key"] != key:
            state["dec"] = None
            import gc
            gc.collect()
            state["dec"] = bt.Decoders(ctx.trials, {"lm_weight": key[0], "edit_penalty": key[1], "word_bonus": key[2]})
            state["key"], state["T"] = key, None
        if state["T"] != T:  # one temperature in memory (bounded RAM)
            state["dec"]._wcache = {}
            state["T"] = T
        ctx.dec = state["dec"]

    def tables(which, fit_items, sets, guard, margin):
        return Q.b2t_tables(ctx, which, fit_items, sets, use_guard=guard, margin=margin)

    # --- checks with the paper setting (plan: before any rebuilt table is used) ---
    chk_p = DER / "check-rebuild.json"
    if not chk_p.exists():
        t0 = time.time()
        s = sp[0]
        use(PAPER, s["T_used"])
        A = [items[i] for i in s["A"]]
        te = tables("published", A, {"test": [items[i] for i in s["test"][:100]]}, True, None)
        ref = json.loads(Q.split_path("b2t-published", 0).read_text(encoding="utf-8"))
        eq = same_table(te["test"], ref["test"], 100)
        chk = {"published_g1_split0": {"same": eq, "T_used": te["T_used"], "T_used_ref": ref["T_used"],
                                       "all_same": all(eq.values()) and abs(te["T_used"] - ref["T_used"]) < 1e-12}}
        # forward chain prefix 0, ours guard on, paper setting
        fc = json.loads((Q.CACHE4 / "forward/b2t-ours-g1-p00.json").read_text(encoding="utf-8"))
        days = sorted({int(t.post_implant_day) for t in trials})
        by = {d: sorted([i for i, t in enumerate(trials) if int(t.post_implant_day) == d], key=lambda i: trials[i].index) for d in days}
        F = [items[i] for i in by[days[0]]]
        if fc.get("ok"):
            # the T of prefix 0 is fitted inside b2t_tables; select the decoder cache after the fit
            use(PAPER, None)
            res = tables("ours", F, {str(d): [items[i] for i in by[d]] for d in days[1:]}, True, None)
            eqf = {d: all(same_table(res[str(d)], fc[str(d)]).values()) for d in days[1:]}
            chk["forward_p00_ours_g1"] = {"same_per_day": eqf, "T_used": res["T_used"], "T_used_ref": fc["T_used"],
                                          "all_same": all(eqf.values()) and res["T_used"] == fc["T_used"]}
        else:
            chk["forward_p00_ours_g1"] = {"original_ok": False, "all_same": None}
        chk["all_pass"] = bool(chk["published_g1_split0"]["all_same"] and chk["forward_p00_ours_g1"]["all_same"] in (True, None))
        chk["seconds"] = round(time.time() - t0, 1)
        dump(chk, chk_p)
        log("rebuild checks", chk)
    chk = json.loads(chk_p.read_text(encoding="utf-8"))
    if not chk["all_pass"]:
        raise SystemExit("rebuild check failed: stop (plan.md)")

    # --- trust v5 module (rows of the 8 changed r < 50 splits) ---
    sys.path.insert(0, str(EXP / "2026-11-14-trust-v5-candidate"))
    import v5x as X  # noqa: E402
    C.Log.path = DER / "run-rebuild.log"

    # --- forward chain prefix 0 with edit 8 (grouped with the other (1.0, 8, 3) splits) ---
    def forward_p00() -> None:
        days = sorted({int(t.post_implant_day) for t in trials})
        by = {d: sorted([i for i, t in enumerate(trials) if int(t.post_implant_day) == d], key=lambda i: trials[i].index) for d in days}
        F = [i for i in by[days[0]]]
        for which in ("ours", "published"):
            for g in (1, 0):
                p = FWD / f"b2t-{which}-g{g}-p00.json"
                if p.exists():
                    continue
                t0 = time.time()
                use(E8, "fwd")
                sets = {str(d): [items[i] for i in by[d]] for d in days[1:]}
                try:
                    res = tables(which, [items[i] for i in F], sets, bool(g), None)
                    res["ok"] = True
                except Exception as e:  # noqa: BLE001  (a 30-trial fit can fail, as in R4)
                    res = {"ok": False, "error": repr(e)}
                res.update({"prefix": 0, "fit_days": days[:1], "n_fit": len(F), "which": which, "guard": g,
                            "day_idx": {str(d): by[d] for d in days[1:]}, "decoder": list(E8)})
                dump(res, p)
                log(f"forward p00 {which} g{g}: ok {res['ok']} T {res.get('T_used')} ({time.time() - t0:.0f}s)")

    ch = changed_splits()
    todo = sorted(ch, key=lambda c: (tuple(c["choice"]), sp[c["r"]]["T_used"]))
    done_fwd = False
    for c in todo:
        key = tuple(float(x) for x in c["choice"])
        if key == E8 and not done_fwd:
            forward_p00()
            done_fwd = True
        s = sp[c["r"]]
        A = [items[i] for i in s["A"]]
        sets = {"reuse": A, "cal": [items[i] for i in s["cal"]], "test": [items[i] for i in s["test"]]}
        for job, which, guard, margin in jobs(s["r"]):
            p = TABD / f"b2t-{job}-{s['r']:03d}.json"
            if p.exists():
                continue
            t0 = time.time()
            use(key, s["T_used"])
            res = tables(which, A, sets, guard, margin)
            res.update({"r": s["r"], "job": job, "which": which, "decoder": list(key), "test_idx": s["test"], "cal_idx": s["cal"],
                        "T_used_original": s["T_used"]})
            dump(res, p)
            log(f"{job} split {s['r']} decoder {key}: T {res['T_used']:.2f} (orig {s['T_used']:.2f}) ({time.time() - t0:.0f}s)")
        if s["r"] < 50:
            for which in ("ours", "published"):
                p = TABD / f"v5-b2t-{which}-{s['r']:03d}.json"
                if p.exists():
                    continue
                t0 = time.time()
                use(key, s["T_used"])
                fn = Q.decoder_fn(ctx, which)
                pipe = X.fit_sweep(fn, ctx.user, (A, A))
                ev = X.evaluate_split(pipe, sets["cal"], sets["test"])
                ev.pop("_lam_of")
                row = {"r": s["r"], "cond": f"b2t-{which}", "T_fitted": K.TState.fitted, "decoder": list(key), **X.split_row(ev)}
                dump(row, p)
                C.Log.path = DER / "run-rebuild.log"
                log(f"trust v5 b2t-{which} split {s['r']} decoder {key}: v4 {ev['arms']['v4']['wrong_commit']:.4f} "
                    f"v5 {ev['arms']['v5']['wrong_commit']:.4f} ({time.time() - t0:.0f}s)")
    if not done_fwd:
        forward_p00()
    (DER / "rebuild.DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    log("rebuild done")


# ---------------------------------------------------------------------------
# P14-18: M4 accuracy rows (A, B) and P14-03 guard rows (C)
# ---------------------------------------------------------------------------

M4EXP = {"m412": EXP / "2026-11-14-m4-12-decoder-retrain", "m402": EXP / "2026-11-13-m4-01-02-lookahead"}
M4CACHE = {"m412": Path("C:/Users/zhang/bci-data/derived/m4-12-decoder-retrain/word-decode-cache.pkl"),
           "m402": Path("C:/Users/zhang/bci-data/derived/m4-01-02-lookahead/word-decode-cache.pkl")}


def derive_dec(dec, ep: float):
    """A second b2t25-trust Decoders with another edit penalty that shares the lexicon, LM and word caches
    (the original tune and the P14-15 grid share these caches across settings too; reproduced exactly)."""
    d = object.__new__(type(dec))
    d.__dict__.update(dec.__dict__)
    d.wkw = {**dec.wkw, "edit_penalty": float(ep)}
    d.wdec = dec.make_wdec(d.wkw)
    d._wcache = {}
    return d


def boot_half(vals_fn, n: int, B: int = 2000, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    xs = [vals_fn(rng.integers(0, n, n)) for _ in range(B)]
    lo, hi = np.percentile(xs, [2.5, 97.5])
    return float((hi - lo) / 2)


def wilson_half(p: float, n: int) -> float:
    z = 1.96
    den = 1 + z * z / n
    return z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den


def stage_m4(exp: str) -> None:
    os.environ["M4_OUT"] = str(DER / f"m4-{exp}")  # the module's OUT / run.log go here
    for k in ("t15",):
        sys.modules.pop(k, None)
    M = None
    sys.path.insert(0, str(REPO / "experiments/2026-11-12-paper1-r1-analyses"))
    import common as RC  # noqa: E402
    M = RC.load_module(f"m4run_{exp}", M4EXP[exp] / "run.py")
    from fidetype.eval.ewpm import summarize
    from fidetype.eval.metrics import edit_distance
    from fidetype.trust.calibration import TemperatureScaler

    committed = json.loads((M4EXP[exp] / "results/accuracy.json").read_text(encoding="utf-8"))["conditions"]
    outp = DER / f"m4-{exp}.json"
    res = json.loads(outp.read_text(encoding="utf-8")) if outp.exists() else {"conditions": {}}
    bt = RC.load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    tune = bt.load_json("tune.json")
    prep = bt.load_json("prep.json")
    base_kw = {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")}
    assert (base_kw["lm_weight"], base_kw["edit_penalty"], base_kw["word_bonus"]) == PAPER

    dec12 = bt.Decoders([], dict(base_kw))

    def make_ctx(ep: float, cache: dict, save_path: Path | None):
        ctx = object.__new__(M.Ctx)
        ctx.bt = bt
        ctx.dec = dec12 if ep == 12.0 else derive_dec(dec12, ep)
        ctx.cpm = prep["speech_rate_125k"]["chars_per_min"]
        ctx.user = M.UserConfig.aac_gaze(chars_per_min=ctx.cpm)
        ctx.fz = M.FrozenTrustConfig.load(REPO / M.CFG["trust"]["frozen_config"])
        assert ctx.fz.config_id == M.CFG["trust"]["frozen_config_id"]
        ctx.texts, ctx.sessions = M.T.texts(), M.T.sessions()
        ctx.cache, ctx.new, ctx.raw = cache, 0, ctx.dec.words_fn
        ctx.misses = 0
        ctx.cache_path = save_path if save_path else DER / "never-written.pkl"
        if save_path is None:
            ctx.save = lambda: None
        return ctx

    def word_pt(ctx, items, T):
        sc = TemperatureScaler()
        sc.temperature = T
        rows = []
        for it in items:
            st = it.stream(0)
            nb = ctx.words_fn(sc.transform_stream(st) if T != 1.0 else st)
            top = nb.texts[0] if len(nb) else ""
            rows.append((edit_distance(it.text, top), len(it.text), edit_distance(it.text.split(), top.split()),
                         len(it.text.split()), int(top == it.text), int(it.text in nb.texts)))
        a = np.array(rows, float)
        n = len(items)
        agg = {"cer": a[:, 0].sum() / max(1, a[:, 1].sum()), "wer": a[:, 2].sum() / max(1, a[:, 3].sum()),
               "sentence_exact": a[:, 4].sum() / max(1, n), "n_exact": int(a[:, 4].sum()), "truth_in_nbest": a[:, 5].sum() / max(1, n)}
        return agg, a

    def run_cond(ctx, which, run, la):
        items, refs, meta = M.load_items(ctx, run, la)
        if SMOKE:
            items = items[:SMOKE]
        out = {"n": len(items)}
        out["words_frozenT"], a_f = word_pt(ctx, items, ctx.fz.frame_temperature)
        out["words_T1"], a_1 = word_pt(ctx, items, 1.0)
        layer = M.StreamingTrustLayer(ctx.fz, decode_fn=ctx.words_fn, streaming=M.StreamingConfig(route="frames", max_attempts=1))
        decs = []
        for it in items:
            sid = it.stream(0).meta["session.id"]
            got = []
            for ev in M.events_of(it.stream(0)):
                got += layer.push(ev, sid)
            fin = [d for d in got if d.final]
            assert len(fin) == 1
            decs.append(fin[0])
        recs = ctx.pipe().run_items(items, M.ReplayPolicy(decs))
        m = summarize(recs)
        n = len(recs)
        ncom = sum(d.action == M.Action.COMMIT for d in decs)
        nwr = sum(bool(x.wrong_commit) for x in recs)
        out["trust"] = {"n_commit": ncom, "commit_rate": ncom / n, "n_wrong_commit": nwr, "wrong_commit": nwr / n,
                        "error_among_commits": (nwr / ncom) if ncom else None, "ewpm": m["ewpm"]}
        allc = M.TrustPipeline(ctx.words_fn, M.HarnessConfig(seed=0, user_config=ctx.user, max_attempts=1, policy="always_commit"), {})
        allc.frame_scaler = ctx.pipe().frame_scaler
        ar = allc.run_items(items)
        out["always_commit"] = {"wrong_commit": sum(bool(x.wrong_commit) for x in ar) / n, "ewpm": summarize(ar)["ewpm"]}
        pt = {"a_frozen": a_f, "a_T1": a_1, "recs": recs, "ar": ar}
        return out, pt

    def halfwidths(out, pt) -> dict:
        n = out["n"]
        aF, a1, recs, ar = pt["a_frozen"], pt["a_T1"], pt["recs"], pt["ar"]
        hw = {
            "words_T1.wer": boot_half(lambda i: a1[i, 2].sum() / a1[i, 3].sum(), n),
            "words_frozenT.wer": boot_half(lambda i: aF[i, 2].sum() / aF[i, 3].sum(), n),
            "words_frozenT.sentence_exact": wilson_half(out["words_frozenT"]["sentence_exact"], n),
            "words_frozenT.truth_in_nbest": wilson_half(out["words_frozenT"]["truth_in_nbest"], n),
            "trust.commit_rate": wilson_half(out["trust"]["commit_rate"], n),
            "trust.wrong_commit": wilson_half(out["trust"]["wrong_commit"], n),
            "trust.ewpm": boot_half(lambda i: summarize([recs[j] for j in i])["ewpm"], n, B=500),
            "always_commit.wrong_commit": wilson_half(out["always_commit"]["wrong_commit"], n),
            "always_commit.ewpm": boot_half(lambda i: summarize([ar[j] for j in i])["ewpm"], n, B=500),
        }
        return hw

    log(f"m4 {exp}: loading the committed word-decode cache (read only)")
    ref_cache = pickle.loads(M4CACHE[exp].read_bytes())
    e8_path = DER / f"word-decode-cache-e8-{exp}.pkl"
    e8_cache = pickle.loads(e8_path.read_bytes()) if e8_path.exists() else {}
    ref = make_ctx(12.0, ref_cache, None)
    new = make_ctx(8.0, e8_cache, e8_path)
    # count misses of the reference cache (decoded with edit 12, never saved)
    raw_ref = ref.raw

    def ref_raw(st, _r=raw_ref):
        ref.misses += 1
        return _r(st)
    ref.raw = ref_raw
    conds = M.conditions()
    conds.sort(key=lambda c: (c[0] != "dedicated_0", c[0], c[2]))
    for which, run, la in conds:
        name = f"{which}/L{la}"
        if name in res["conditions"] or name not in committed:
            continue
        t0 = time.time()
        ref.misses = 0
        o_ref, pt_ref = run_cond(ref, which, run, la)
        cm = committed[name]
        repro = {
            "words_T1.wer": abs(o_ref["words_T1"]["wer"] - cm["words_T1"]["wer"]) < 1e-9,
            "words_frozenT.wer": abs(o_ref["words_frozenT"]["wer"] - cm["words_frozenT"]["wer"]) < 1e-9,
            "words_frozenT.n_exact": o_ref["words_frozenT"]["n_exact"] == cm["words_frozenT"]["n_exact"],
            "words_frozenT.truth_in_nbest": abs(o_ref["words_frozenT"]["truth_in_nbest"] - cm["words_frozenT"]["truth_in_nbest"]) < 1e-9,
            "trust.n_commit": o_ref["trust"]["n_commit"] == cm["trust"]["n_commit"],
            "trust.n_wrong_commit": o_ref["trust"]["n_wrong_commit"] == cm["trust"]["n_wrong_commit"],
            "trust.ewpm": abs(o_ref["trust"]["ewpm"] - cm["trust"]["ewpm"]) < 1e-6,
            "always_commit.wrong_commit": abs(o_ref["always_commit"]["wrong_commit"] - cm["always_commit"]["wrong_commit"]) < 1e-9,
            "always_commit.ewpm": abs(o_ref["always_commit"]["ewpm"] - cm["always_commit"]["ewpm"]) < 1e-6,
        }
        hw = halfwidths(o_ref, pt_ref)
        t1 = time.time()
        o_new, _ = run_cond(new, which, run, la)
        new.save()
        res["conditions"][name] = {"reference": o_ref, "reference_cache_misses": ref.misses, "reproduces_committed": repro,
                                   "reproduces_all": all(repro.values()), "edit8": o_new, "ci_half": hw,
                                   "seconds_reference": round(t1 - t0, 1), "seconds_edit8": round(time.time() - t1, 1)}
        dump(res, outp)
        log(f"m4 {exp} {name}: repro {all(repro.values())} (misses {ref.misses}); WER T1 {o_ref['words_T1']['wer']:.4f} -> "
            f"{o_new['words_T1']['wer']:.4f} (hw {hw['words_T1.wer']:.4f}); commits {o_ref['trust']['n_commit']} -> {o_new['trust']['n_commit']}; "
            f"eWPM {o_ref['trust']['ewpm']:.3f} -> {o_new['trust']['ewpm']:.3f} ({t1 - t0:.0f}s + {time.time() - t1:.0f}s)")
        if SMOKE:
            break
    new.save()
    log(f"m4 {exp} done")


def stage_p1403() -> None:
    P = None
    sys.path.insert(0, str(REPO / "experiments/2026-11-12-paper1-r1-analyses"))
    import common as RC  # noqa: E402
    P = RC.load_module("p1403run", EXP / "2026-11-16-p14-03-replay-validation/run.py")
    P.LOGF = DER / "run-p1403-module.log"
    committed = json.loads((EXP / "2026-11-16-p14-03-replay-validation/results/results.json").read_text(encoding="utf-8"))["t15"]
    outp = DER / "p1403.json"
    res = json.loads(outp.read_text(encoding="utf-8")) if outp.exists() else {}
    (cx, ct, cph), (hx, ht, hph), dec12, cpm, split = P.data_t15()
    ht = [" ".join(t.split()) for t in ht]
    from fidetype.eval.ewpm import summarize

    def ewpm_recs(results, truths):
        user = P.SimulatedUser(P.UserConfig.aac_gaze(chars_per_min=cpm), seed=P.SEED)
        recs = []
        for i, (r, t) in enumerate(zip(results, truths)):
            d = P.Decision(P.Action(r.raw_action), tuple(r.choices), r.reason)
            o = user.respond(d, t, can_repeat=False, rng=np.random.default_rng([P.SEED, i, 0]))
            tt = user.typing_time(t) + o.time_s
            recs.append(P.SentenceRecord(t, o.final_text, o.communicated, tt, [r.raw_action],
                                         r.text if r.action == "commit" else None, o.wrong_commit, o.silent_error))
        return recs

    assert (dec12.wkw["lm_weight"], dec12.wkw["edit_penalty"], dec12.wkw["word_bonus"]) == PAPER
    if SMOKE:
        hx, ht = hx[:SMOKE], ht[:SMOKE]
    for tag, ep in (("reference", 12.0), ("edit8", 8.0)):
        if tag in res:
            continue
        dec = dec12 if ep == 12.0 else derive_dec(dec12, ep)
        fn = P.make_decode_fn(dec)
        out = {}
        for alpha in (P.ALPHAS[:1] if SMOKE else P.ALPHAS):
            t0 = time.time()
            guard = P.ft.calibrate(cx, ct, alpha=alpha, delta=0.1, vocab=list(P.B.SYMBOL_VOCAB), blank=0, input_scale="log_probs",
                                   frame_period=0.08, decode_fn=fn, stream_texts=cph, decoder_name="p14-03-t15",
                                   modality="intracortical", name="p14-03-t15", seed=P.SEED)
            rr = [guard.decide(x, utterance_id=f"t15-{i}") for i, x in enumerate(hx)]
            n = len(rr)
            com = [(r, t) for r, t in zip(rr, ht) if r.action == "commit"]
            nw = sum(r.text != t for r, t in com)
            recs = ewpm_recs(rr, ht)
            s = summarize(recs)
            row = {"config_id": guard.config_id, "frame_temperature": guard.config.frame_temperature,
                   "sentence_temperature": guard.config.sentence_temperature, "n": n, "n_commit": len(com), "n_wrong_commit": nw,
                   "wrong_commit_rate": nw / n, "commit_rate": len(com) / n, "error_among_commits": (nw / len(com)) if com else None,
                   "ewpm": s["ewpm"], "actions": {a: sum(r.action == a for r in rr) for a in ("commit", "offer", "withhold")},
                   "lambda_hat": guard.sheet.to_dict().get("lambda_hat") if hasattr(guard.sheet, "to_dict") else None,
                   "seconds": round(time.time() - t0, 1)}
            if tag == "reference":
                row["ci_half"] = {"wrong_commit_rate": wilson_half(row["wrong_commit_rate"], n), "commit_rate": wilson_half(row["commit_rate"], n),
                                  "error_among_commits": wilson_half(row["error_among_commits"], len(com)) if com else None,
                                  "ewpm": boot_half(lambda i: summarize([recs[j] for j in i])["ewpm"], n, B=500)}
                c = committed["alpha"][str(alpha)]
                row["reproduces_committed"] = {"n_commit": len(com) == c["n_commit"], "n_wrong_commit": nw == c["n_wrong_commit"],
                                               "ewpm": abs(s["ewpm"] - c["ewpm"]["ewpm"]) < 1e-6}
                row["config_id_equal_committed"] = guard.config_id == c["config_id"]  # info only (the id hashes more than the decisions)
            guard.save(DER / f"guard-p1403-{tag}-a{alpha:.2f}.json")
            out[str(alpha)] = row
            log(f"p1403 {tag} alpha {alpha}: commits {len(com)} wrong {nw} eWPM {s['ewpm']:.3f} ({row['seconds']:.0f}s)")
        res[tag] = out
        dump(res, outp)
    log("p1403 done")


# ---------------------------------------------------------------------------
# analyses
# ---------------------------------------------------------------------------

def stage_analyze() -> None:
    Q = r4()
    C = Q.C
    C.Log.path = DER / "run-analyze.log"
    m4_decision()
    if not (DER / "rebuild.DONE").exists():
        log("analyze: rebuild not finished, P14-19 step 2 skipped")
        return
    sys.path.insert(0, str(R3 / "repeated-splits"))
    RS = C.load_module("r3rs", R3 / "repeated-splits/run.py")
    C.Log.path = DER / "run-analyze.log"
    ch = {c["r"] for c in changed_splits()}
    out: dict = {"changed_splits": sorted(ch), "tables": {}}
    for which, guard in (("published", 1), ("ours", 0), ("published", 0)):
        job = f"{which}-g{guard}"
        for R in (50, 200):
            orig, new = [], []
            for r in range(R):
                tab = json.loads(Q.split_path(f"b2t-{which}", r, guard).read_text(encoding="utf-8"))
                orig.append(RS.split_policies(tab))
                if r in ch:
                    tab = json.loads((TABD / f"b2t-{job}-{r:03d}.json").read_text(encoding="utf-8"))
                new.append(RS.split_policies(tab))
            rows = policy_rows(RS, orig, new, R)
            out["tables"][f"b2t-{job}/R{R}"] = {"n_changed": sum(r in ch for r in range(R)), "rows": rows,
                                               "n_effect": sum(x["effect"] for x in rows), "n_metrics": len(rows),
                                               "max_ratio": max(abs(x["delta"]) / x["ci_half"] if x["ci_half"] > 0 else 0.0 for x in rows)}
            log(f"b2t-{job} R{R}: effect {out['tables'][f'b2t-{job}/R{R}']['n_effect']}/{len(rows)}, "
                f"max ratio {out['tables'][f'b2t-{job}/R{R}']['max_ratio']:.3f}")
    out["forward_chain"] = forward_analysis(Q)
    eff = sum(v["n_effect"] for v in out["tables"].values()) + out["forward_chain"]["n_effect"]
    out["decision_step2"] = "effect" if eff else "no effect"
    dump(out, OUT / "p14-19-step2.json")
    log("P14-19 step 2:", out["decision_step2"])


def policy_rows(RS, orig, new, R) -> list[dict]:
    rows = []
    for p in RS.POL:
        for m in ("wrong_commit", "commit_rate", "ewpm"):
            a = np.array([x["test"][p][m] for x in orig], float)
            b = np.array([x["test"][p][m] for x in new], float)
            hw = 1.96 * a.std(ddof=1) / math.sqrt(R)
            d = float(b.mean() - a.mean())
            rows.append({"policy": p, "metric": f"mean {m}", "orig": float(a.mean()), "new": float(b.mean()), "delta": d,
                         "ci_half": hw, "effect": bool(abs(d) > 0 and abs(d) >= hw)})
        nco = sum(x["test"][p]["n_commit"] for x in orig)
        nwo = sum(x["test"][p]["n_commit_wrong"] for x in orig)
        ncn = sum(x["test"][p]["n_commit"] for x in new)
        nwn = sum(x["test"][p]["n_commit_wrong"] for x in new)
        po, pn = (nwo / nco if nco else 0.0), (nwn / ncn if ncn else 0.0)
        hw = wilson_half(po, max(nco, 1))
        rows.append({"policy": p, "metric": "pooled error among commits", "orig": po, "new": pn, "delta": pn - po, "ci_half": hw,
                     "effect": bool(abs(pn - po) > 0 and abs(pn - po) >= hw)})
        so = float(np.mean([x["test"][p]["wrong_commit"] > ALPHA + 1e-12 for x in orig]))
        sn = float(np.mean([x["test"][p]["wrong_commit"] > ALPHA + 1e-12 for x in new]))
        hw = wilson_half(so, R)
        rows.append({"policy": p, "metric": "share wrong-commit > alpha", "orig": so, "new": sn, "delta": sn - so, "ci_half": hw,
                     "effect": bool(abs(sn - so) > 0 and abs(sn - so) >= hw)})
    return rows


def forward_dir(Q) -> Path:
    """Copy of the R4 forward-chain tables with prefix 0 replaced by the rebuilt tables."""
    d = DER / "forward-merged"
    d.mkdir(exist_ok=True)
    for p in (Q.CACHE4 / "forward").glob("*.json"):
        q = d / p.name
        src = FWD / p.name if (FWD / p.name).exists() else p
        if not q.exists() or q.stat().st_size != src.stat().st_size:
            shutil.copyfile(src, q)
    return d


def forward_analysis(Q) -> dict:
    C = Q.C
    FCM = C.load_module("r4fwd", R4 / "forward-chain/run.py")
    FCM.FC = forward_dir(Q)
    FCM.OUT = DER / "forward-chain"
    FCM.OUT.mkdir(exist_ok=True)
    C.Log.path = DER / "run-analyze.log"
    FCM.stage_analyze()
    new = json.loads((FCM.OUT / "forward_chain.json").read_text(encoding="utf-8"))
    orig = json.loads((R4 / "forward-chain/results/forward_chain.json").read_text(encoding="utf-8"))
    rows = []
    for cname, c in orig["conditions"].items():
        for vname, v in c["variants"].items():
            folds = v["folds"]
            for r in ("plug-in", "CRC max", "LTT max", "joint LTT b0.10", "joint LTT b0.20"):
                so, sn = v["summary"][r], new["conditions"][cname]["variants"][vname]["summary"][r]
                ntest = sum(f["n_test"] for f in folds)
                ew = [f["rules"][r]["ewpm"] for f in folds]
                spec = [("pooled_wrong_commit", _cp_half(so.get("pooled_wrong_commit_cp95"))),
                        ("share_days_above_alpha", _cp_half(so.get("share_days_above_alpha_cp95"))),
                        ("pooled_commit_rate", wilson_half(so["pooled_commit_rate"] or 0.0, max(ntest, 1))),
                        ("mean_day_ewpm", 1.96 * float(np.std(ew, ddof=1)) / math.sqrt(len(ew)) if len(ew) > 1 else 0.0)]
                for m, hw in spec:
                    a, b = so.get(m), sn.get(m)
                    if a is None or b is None:
                        continue
                    d = float(b) - float(a)
                    rows.append({"condition": cname, "variant": vname, "rule": r, "metric": m, "orig": a, "new": b, "delta": d,
                                 "ci_half": hw, "effect": bool(abs(d) > 1e-12 and abs(d) >= hw)})
    changed = [x for x in rows if abs(x["delta"]) > 1e-12]
    p0 = {}
    for which in ("ours", "published"):
        for g in (1, 0):
            q = FWD / f"b2t-{which}-g{g}-p00.json"
            o = json.loads((Q.CACHE4 / "forward" / q.name).read_text(encoding="utf-8"))
            nn = json.loads(q.read_text(encoding="utf-8"))
            p0[f"{which}-g{g}"] = {"ok_orig": o.get("ok"), "ok_new": nn.get("ok"), "T_orig": o.get("T_used"), "T_new": nn.get("T_used"),
                                   "commit_p_orig": (o.get("fit_report") or {}).get("policy_config", {}).get("commit_p"),
                                   "commit_p_new": (nn.get("fit_report") or {}).get("policy_config", {}).get("commit_p")}
    return {"prefix0": p0, "n_metrics": len(rows), "n_changed": len(changed), "n_effect": sum(x["effect"] for x in rows),
            "max_ratio": max([abs(x["delta"]) / x["ci_half"] for x in rows if x["ci_half"] > 0] or [0.0]),
            "changed_rows": changed}


def _cp_half(ci) -> float:
    if not ci or ci[0] is None:
        return 0.0
    return (ci[1] - ci[0]) / 2


def m4_decision() -> None:
    out: dict = {"m4": {}, "p1403": {}}
    n_eff = n_met = 0
    ok_all = True
    for exp in ("m412", "m402"):
        p = DER / f"m4-{exp}.json"
        if not p.exists():
            out["m4"][exp] = "not run"
            continue
        d = json.loads(p.read_text(encoding="utf-8"))["conditions"]
        rows = []
        for name, c in d.items():
            ok_all &= c["reproduces_all"]
            for key, hw in c["ci_half"].items():
                sec, met = key.split(".")
                a, b = c["reference"][sec][met], c["edit8"][sec][met]
                dd = float(b) - float(a)
                rows.append({"condition": name, "metric": key, "orig": a, "new": b, "delta": dd, "ci_half": hw,
                             "effect": bool(abs(dd) > 1e-12 and abs(dd) >= hw)})
            for k in ("n_commit", "n_wrong_commit"):
                rows.append({"condition": name, "metric": f"trust.{k}", "orig": c["reference"]["trust"][k], "new": c["edit8"]["trust"][k],
                             "delta": c["edit8"]["trust"][k] - c["reference"]["trust"][k], "ci_half": None, "effect": False})
        out["m4"][exp] = {"conditions": len(d), "reproduces_all": all(c["reproduces_all"] for c in d.values()),
                          "cache_misses": {k: c["reference_cache_misses"] for k, c in d.items()}, "rows": rows,
                          "n_effect": sum(x["effect"] for x in rows), "n_metrics": sum(x["ci_half"] is not None for x in rows),
                          "max_ratio": max([abs(x["delta"]) / x["ci_half"] for x in rows if x["ci_half"]] or [0.0])}
        n_eff += out["m4"][exp]["n_effect"]
        n_met += out["m4"][exp]["n_metrics"]
    p = DER / "p1403.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        rows = []
        for a in d.get("reference", {}):
            ref, new = d["reference"][a], d.get("edit8", {}).get(a)
            ok_all &= all(ref["reproduces_committed"].values())
            if new is None:
                continue
            for m in ("wrong_commit_rate", "commit_rate", "error_among_commits", "ewpm"):
                hw = ref["ci_half"][m]
                x, y = ref[m], new[m]
                if hw is None:  # 0 commits in the reference: the commit rate decides (plan)
                    rows.append({"alpha": a, "metric": m, "orig": x, "new": y, "delta": None, "ci_half": None, "effect": False})
                    continue
                if x is None or y is None:
                    rows.append({"alpha": a, "metric": m, "orig": x, "new": y, "delta": None, "ci_half": hw,
                                 "effect": bool(x != y)})
                    continue
                dd = float(y) - float(x)
                rows.append({"alpha": a, "metric": m, "orig": x, "new": y, "delta": dd, "ci_half": hw,
                             "effect": bool(abs(dd) > 1e-12 and abs(dd) >= hw)})
            for k in ("n_commit", "n_wrong_commit", "frame_temperature", "sentence_temperature", "config_id"):
                rows.append({"alpha": a, "metric": k, "orig": ref[k], "new": new[k], "info_only": True})
        out["p1403"] = {"rows": rows, "reproduces_all": all(all(r["reproduces_committed"].values()) for r in d.get("reference", {}).values()),
                        "n_effect": sum(bool(x.get("effect")) for x in rows)}
        n_eff += out["p1403"]["n_effect"]
    out["all_reference_runs_reproduce"] = bool(ok_all)
    out["n_effect"] = n_eff
    out["decision"] = ("effect" if n_eff else "no effect") if ok_all else "reference run did not reproduce: no decision"
    dump(out, OUT / "p14-18.json")
    log("P14-18 decision:", out["decision"], f"({n_eff} effects)")


# ---------------------------------------------------------------------------
# P14-19 step 3: downstream analyses with redirected tables
# ---------------------------------------------------------------------------

def patch_loader(Q) -> set:
    ch = {c["r"] for c in changed_splits()}
    orig = Q.split_path

    def split_path(cond, r, guard=1, margin=None, _o=orig):
        if cond.startswith("b2t-") and r in ch:
            which = cond[4:]
            if margin is not None and abs(margin - 2.0) > 1e-9:
                return TABD / f"b2t-published-m{margin:g}-{r:03d}.json"
            if which == "ours" and guard:
                return DER1415 / "tables" / f"b2t-ours-{r:03d}.json"
            return TABD / f"b2t-{which}-g{guard}-{r:03d}.json"
        return _o(cond, r, guard, margin)
    Q.split_path = split_path
    Q._orig_split_path = orig
    return ch


def leaves(o, path=()):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, path + (str(k),))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from leaves(v, path + (i,))
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        yield path, float(o)


def get(o, path):
    for k in path:
        if isinstance(o, dict):
            if k not in o:
                return None
            o = o[k]
        elif isinstance(o, list):
            if not isinstance(k, int) or k >= len(o):
                return None
            o = o[k]
        else:
            return None
    return o


CI_SUFFIX = ("_cp95", "_ci", "_ci95", "_cp")


def ci_of(orig, path):
    """Committed CI of a leaf: sibling key <name><suffix> (list [lo, hi]), or 'share_cp95' for 'share*' keys."""
    if not path or not isinstance(path[-1], str):
        return None
    parent = get(orig, path[:-1])
    if not isinstance(parent, dict):
        return None
    k = path[-1]
    if k == "wrong" and "rate" in parent:
        return None  # a count; its rate is compared below ("rate" <-> "wrong_cp95", A2)
    cands = [k + s for s in CI_SUFFIX]
    # exact pairs only (fix 2026-11-17, before the write-up: the first pass paired any 'share*' key with
    # 'share_gt_alpha_cp95' and A2's count 'wrong' with its rate CI 'wrong_cp95')
    extra = {"share_gt_alpha": ["share_cp95"], "share_eac_gt_beta_of_committing": ["share_eac_gt_beta_cp95"],
             "rate": ["wrong_cp95"] if "wrong" in parent else []}
    cands += extra.get(k, [])
    for c in cands:
        v = parent.get(c)
        if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
            return v
    return None


def compare(orig, new, skip_keys=("seconds", "wall_s", "config", "env")) -> dict:
    rows, nochg = [], 0
    for path, a in leaves(orig):
        if any(isinstance(k, str) and (k in skip_keys or k.endswith("_p") or k.startswith("p_") or "pvalue" in k or k.endswith("holm"))
               for k in path):
            continue
        if any(isinstance(k, str) and any(k.endswith(s) for s in CI_SUFFIX) for k in path):
            continue  # CI bounds themselves
        b = get(new, path)
        if not isinstance(b, (int, float)) or isinstance(b, bool):
            continue
        d = float(b) - a
        if abs(d) <= 1e-12:
            nochg += 1
            continue
        ci = ci_of(orig, path)
        hw = (ci[1] - ci[0]) / 2 if ci else None
        rows.append({"path": "/".join(str(x) for x in path), "orig": a, "new": float(b), "delta": d, "ci_half": hw,
                     "ratio": (abs(d) / hw) if hw else None, "effect": bool(hw is not None and abs(d) >= hw)})
    withci = [x for x in rows if x["ci_half"] is not None]
    noci = [x for x in rows if x["ci_half"] is None]
    return {"n_unchanged": nochg, "n_changed": len(rows), "n_changed_with_ci": len(withci), "n_effect": sum(x["effect"] for x in rows),
            "max_ratio": max([x["ratio"] for x in withci] or [0.0]),
            "top_with_ci": sorted(withci, key=lambda x: -x["ratio"])[:10],
            "max_abs_change_no_ci": sorted(noci, key=lambda x: -abs(x["delta"]))[:10]}


def per_split_ci(orig_res: dict, per_split: dict) -> list:
    """Joint-LTT: MC half-widths of the means over splits from the committed per-split values (plan, step 3)."""
    out = []
    for key, per in per_split.items():
        for rule in ("LTT max", "joint LTT b0.10", "joint LTT b0.20"):
            for m_mean, m in (("wrong_commit_mean", "wrong_commit"), ("commit_rate_mean", "commit_rate"), ("ewpm_mean", "ewpm")):
                vals = [x[rule].get(m) for x in per if isinstance(x.get(rule), dict)]
                vals = [v for v in vals if isinstance(v, (int, float))]
                if len(vals) > 1:
                    out.append((("repeated", key, rule, m_mean), 1.96 * float(np.std(vals, ddof=1)) / math.sqrt(len(vals))))
    return out


def stage_downstream() -> None:
    Q = r4()
    C = Q.C
    LOGD = DER / "run-downstream.log"
    C.Log.path = LOGD
    patch_loader(Q)
    D = DER / "downstream"
    D.mkdir(exist_ok=True)
    res = json.loads((OUT / "p14-19-step3.json").read_text(encoding="utf-8")) if (OUT / "p14-19-step3.json").exists() else {"analyses": {}}

    def run_mod(name, path, call, outfiles, prep=None):
        if name in res["analyses"]:
            return
        t0 = time.time()
        od = D / name
        od.mkdir(exist_ok=True)
        try:
            mod = C.load_module(f"ds_{name.replace('-', '_')}", path)
            mod.OUT = od
            C.Log.path = LOGD
            if prep:
                prep(mod, od)
            call(mod)
            C.Log.path = LOGD
            comp = {}
            for of, cf in outfiles:
                orig = json.loads(Path(cf).read_text(encoding="utf-8"))
                new = json.loads((od / of).read_text(encoding="utf-8"))
                comp[of] = compare(orig, new)
            res["analyses"][name] = {"status": "ok", "files": comp, "seconds": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001
            import traceback
            res["analyses"][name] = {"status": "error", "error": repr(e), "trace": traceback.format_exc()[-2000:]}
        dump(res, OUT / "p14-19-step3.json")
        a = res["analyses"][name]
        log(f"downstream {name}: {a['status']} " + (", ".join(f"{k}: changed {v['n_changed']}, with CI {v['n_changed_with_ci']}, effect {v['n_effect']}, max ratio {v['max_ratio']:.3f}"
                                                            for k, v in a.get("files", {}).items())) + f" ({time.time() - t0:.0f}s)")

    def copy_in(*names):
        def prep(mod, od, _n=names, _src=None):
            for n in _n:
                shutil.copyfile(Path(mod.HERE) / "results" / n, od / n)
        return prep

    rp = R4
    run_mod("r4-population-risk", rp / "population-risk/run.py", lambda m: m.main(),
            [("population_risk.json", rp / "population-risk/results/population_risk.json")])
    run_mod("r4-per-day", rp / "per-day/run.py", lambda m: m.main(), [("per_day.json", rp / "per-day/results/per_day.json")])
    run_mod("r4-joint-ltt", rp / "joint-ltt/run.py", lambda m: m.main(), [("joint_ltt.json", rp / "joint-ltt/results/joint_ltt.json")])
    # joint LTT: MC half-widths from the committed per-split values (plan)
    if res["analyses"].get("r4-joint-ltt", {}).get("status") == "ok" and "mc" not in res["analyses"]["r4-joint-ltt"]:
        orig = json.loads((rp / "joint-ltt/results/joint_ltt.json").read_text(encoding="utf-8"))
        new = json.loads((D / "r4-joint-ltt/joint_ltt.json").read_text(encoding="utf-8"))
        per = json.loads((rp / "joint-ltt/results/per_split.json").read_text(encoding="utf-8"))
        mc = []
        for path, hw in per_split_ci(orig, per):
            a, b = get(orig, path), get(new, path)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                d = float(b) - float(a)
                mc.append({"path": "/".join(path), "orig": a, "new": b, "delta": d, "ci_half": hw,
                           "effect": bool(abs(d) > 1e-12 and abs(d) >= hw)})
        res["analyses"]["r4-joint-ltt"]["mc"] = {"n": len(mc), "n_effect": sum(x["effect"] for x in mc),
                                                 "max_ratio": max([abs(x["delta"]) / x["ci_half"] for x in mc if x["ci_half"] > 0] or [0.0]),
                                                 "top": sorted(mc, key=lambda x: -(abs(x["delta"]) / x["ci_half"] if x["ci_half"] > 0 else 0))[:10]}
        dump(res, OUT / "p14-19-step3.json")
    run_mod("r4-no-guard-tab2", rp / "no-guard/run.py", lambda m: m.stage_tables(), [("no_guard.json", rp / "no-guard/results/no_guard.json")],
            prep=copy_in("no_guard_b2t.json", "no_guard_emg.json", "no_guard_meg.json"))
    run_mod("r4-bonus-repeated", rp / "bonus-sensitivity/run.py", lambda m: m.stage_tables(),
            [("bonus.json", rp / "bonus-sensitivity/results/bonus.json")], prep=copy_in("bonus_fixed.json"))
    run_mod("r4-reuse", rp / "reuse/run.py", lambda m: m.main(), [("reuse.json", rp / "reuse/results/reuse.json")])
    run_mod("r4-cleanup", rp / "cleanup/run.py", lambda m: m.main(), [("cleanup.json", rp / "cleanup/results/cleanup.json")])

    # M3-01/02 repeated-split arms
    m3 = EXP / "2026-11-14-m3-01-02-ablations"

    if "m3-01-02-splits" not in res["analyses"]:
        sys.path.insert(0, str(m3))
        import abl as A  # noqa: E402
        t0 = time.time()
        od = D / "m3-01-02-splits"
        od.mkdir(exist_ok=True)
        try:
            out = {cond: A.split_arm_outcomes(cond, R) for cond, R in (("b2t-ours", 200), ("b2t-published", 200))}
            dump(out, od / "splits.json")
            orig = json.loads((m3 / "results/splits.json").read_text(encoding="utf-8"))
            res["analyses"]["m3-01-02-splits"] = {"status": "ok", "files": {"splits.json": compare({k: orig[k] for k in out}, out)},
                                                  "seconds": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001
            import traceback
            res["analyses"]["m3-01-02-splits"] = {"status": "error", "error": repr(e), "trace": traceback.format_exc()[-2000:]}
        C.Log.path = LOGD
        dump(res, OUT / "p14-19-step3.json")
        log("downstream m3-01-02-splits:", res["analyses"]["m3-01-02-splits"]["status"])

    # trust v5 split summary (8 rebuilt rows replace the committed ones)
    if "trust-v5-splits" not in res["analyses"]:
        t0 = time.time()
        try:
            sys.path.insert(0, str(EXP / "2026-11-14-trust-v5-candidate"))
            import v5x as X  # noqa: E402
            C.Log.path = LOGD
            ch = {c["r"] for c in changed_splits()}
            out = {}
            for cond in ("b2t-ours", "b2t-published"):
                rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((X.CACHE6 / "splits").glob(f"{cond}-*.json"))]
                rows = [r for r in rows if r["r"] < 50]
                new = []
                for r in rows:
                    if r["r"] in ch:
                        r = json.loads((TABD / f"v5-{cond}-{r['r']:03d}.json").read_text(encoding="utf-8"))
                    new.append(r)
                out[cond] = X.summarise_splits(new)
            dump(out, D / "trust-v5-splits.json")
            orig = json.loads((EXP / "2026-11-14-trust-v5-candidate/results/splits.json").read_text(encoding="utf-8"))
            res["analyses"]["trust-v5-splits"] = {"status": "ok", "files": {"splits.json": compare({k: orig[k] for k in out}, out)},
                                                  "seconds": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001
            import traceback
            res["analyses"]["trust-v5-splits"] = {"status": "error", "error": repr(e), "trace": traceback.format_exc()[-2000:]}
        dump(res, OUT / "p14-19-step3.json")
        log("downstream trust-v5-splits:", res["analyses"]["trust-v5-splits"]["status"])

    # A2 per-session risk: re-split and forward-chain parts (B2T)
    a2 = EXP / "2026-11-13-a2-per-session-risk"

    def a2_prep(mod, od):
        mod.FC = forward_dir(Q)

    def a2_call(mod):
        fc = {w: mod.fc_b2t(w) for w in ("published", "ours")}
        Q.C.dump(fc, mod.OUT / "forward_chain.json")
        for cond in ("b2t-published", "b2t-ours"):
            Q.C.dump(mod.rs_b2t(cond), mod.OUT / f"rs-{cond}.json")
    run_mod("a2-per-session-risk", a2 / "run.py", a2_call,
            [("forward_chain.json", a2 / "results/forward_chain.json"), ("rs-b2t-published.json", a2 / "results/rs-b2t-published.json"),
             ("rs-b2t-ours.json", a2 / "results/rs-b2t-ours.json")], prep=a2_prep)

    ok = [a for a in res["analyses"].values() if a["status"] == "ok"]
    n_eff = sum(v["n_effect"] for a in ok for v in a["files"].values()) + sum(a.get("mc", {}).get("n_effect", 0) for a in ok)
    res["n_effect"] = n_eff
    res["errors"] = [k for k, a in res["analyses"].items() if a["status"] != "ok"]
    res["decision_step3"] = "effect" if n_eff else ("no effect" if not res["errors"] else "no effect in the analyses that ran")
    dump(res, OUT / "p14-19-step3.json")
    log("P14-19 step 3:", res["decision_step3"], "errors:", res["errors"])


# ---------------------------------------------------------------------------

def stage_recompare() -> None:
    """Re-run only the comparison of step 3 on the saved downstream outputs (after the CI-pairing fix)."""
    p = OUT / "p14-19-step3.json"
    res = json.loads(p.read_text(encoding="utf-8"))
    D = DER / "downstream"
    rp, a2, m3, v5 = R4, EXP / "2026-11-13-a2-per-session-risk", EXP / "2026-11-14-m3-01-02-ablations", EXP / "2026-11-14-trust-v5-candidate"
    spec = {"r4-population-risk": [("population_risk.json", rp / "population-risk/results/population_risk.json")],
            "r4-per-day": [("per_day.json", rp / "per-day/results/per_day.json")],
            "r4-joint-ltt": [("joint_ltt.json", rp / "joint-ltt/results/joint_ltt.json")],
            "r4-no-guard-tab2": [("no_guard.json", rp / "no-guard/results/no_guard.json")],
            "r4-bonus-repeated": [("bonus.json", rp / "bonus-sensitivity/results/bonus.json")],
            "r4-reuse": [("reuse.json", rp / "reuse/results/reuse.json")],
            "r4-cleanup": [("cleanup.json", rp / "cleanup/results/cleanup.json")],
            "a2-per-session-risk": [("forward_chain.json", a2 / "results/forward_chain.json"),
                                    ("rs-b2t-published.json", a2 / "results/rs-b2t-published.json"),
                                    ("rs-b2t-ours.json", a2 / "results/rs-b2t-ours.json")]}
    for name, files in spec.items():
        res["analyses"][name]["files"] = {of: compare(json.loads(Path(cf).read_text(encoding="utf-8")),
                                                      json.loads((D / name / of).read_text(encoding="utf-8"))) for of, cf in files}
    for name, new_p, orig_p in (("m3-01-02-splits", D / "m3-01-02-splits/splits.json", m3 / "results/splits.json"),
                                ("trust-v5-splits", D / "trust-v5-splits.json", v5 / "results/splits.json")):
        new = json.loads(new_p.read_text(encoding="utf-8"))
        orig = json.loads(orig_p.read_text(encoding="utf-8"))
        res["analyses"][name]["files"] = {"splits.json": compare({k: orig[k] for k in new}, new)}
    ok = [a for a in res["analyses"].values() if a["status"] == "ok"]
    res["n_effect"] = sum(v["n_effect"] for a in ok for v in a["files"].values()) + sum(a.get("mc", {}).get("n_effect", 0) for a in ok)
    res["decision_step3"] = "effect" if res["n_effect"] else "no effect"
    res["recompared"] = "2026-11-17: CI pairing fixed (exact sibling pairs only; A2 count vs rate); outputs not rerun"
    dump(res, p)
    for name, a in res["analyses"].items():
        log(f"recompare {name}: " + ", ".join(f"{k}: with CI {v['n_changed_with_ci']}, effect {v['n_effect']}, max ratio {v['max_ratio']:.3f}"
                                              for k, v in a["files"].items()))
    log("P14-19 step 3 (recompared):", res["decision_step3"], res["n_effect"])


def stage_queue() -> None:
    py = sys.executable
    me = str(Path(__file__).resolve())
    rcs = {}
    for args in (["--stage", "m4", "--exp", "m412"], ["--stage", "p1403"], ["--stage", "rebuild"], ["--stage", "m4", "--exp", "m402"],
                 ["--stage", "analyze"], ["--stage", "downstream"]):
        if args[1] == "downstream" and rcs.get("rebuild") != 0:
            log("queue: rebuild failed, skip downstream")
            continue
        t0 = time.time()
        log("queue start", args)
        with open(DER / f"stdout-{'-'.join(args[1:])}.log", "a", encoding="utf-8") as fo:
            rc = subprocess.call([py, "-I", me] + args, stdout=fo, stderr=subprocess.STDOUT, cwd=str(REPO))
        rcs[args[1]] = rc
        log("queue end", args, "rc", rc, f"({time.time() - t0:.0f}s)")
    (DER / "queue.DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=("rebuild", "m4", "p1403", "analyze", "downstream", "recompare", "queue"))
    ap.add_argument("--exp", default="m412")
    a = ap.parse_args()
    sys.path.insert(0, str(REPO / "src"))
    if a.stage == "m4":
        stage_m4(a.exp)
    else:
        {"rebuild": stage_rebuild, "p1403": stage_p1403, "analyze": stage_analyze, "downstream": stage_downstream,
         "queue": stage_queue, "recompare": stage_recompare}[a.stage]()
    log("done", a.stage)


if __name__ == "__main__":
    main()
