r"""B1 pipeline: parse -> features + A0 -> fit (writes gate.json) -> test (nulls, metrics, outcome).

CPU only (NumPy / SciPy; no torch, no GPU). Stages:

    b1run.py parse   # hash order, session parsing, replacements, ranks          -> <out>/subjects.json
    b1run.py feat    # per session: A0 statistics + features (+ test-session nulls) -> <out>/feat/*.npz
    b1run.py fit     # A0 decision, decoders, Platt, gates on cal only            -> <out>/gate.json (+ results/)
    b1run.py test    # needs results/gate.json committed; test + nulls + rules    -> <out>/summary.json (+ results/)
    b1run.py all     # all stages; exits with code 4 after `fit` if gate.json is not yet committed

Every stage skips finished work (checkpoints per session / per stage). Stop: create <out>/stop.
Subject codes appear only in files under <out> (local). The repo gets only rank-keyed aggregates.
"""

from __future__ import annotations

import os

for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_k] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["HIP_VISIBLE_DEVICES"] = ""

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))

import b1data as D  # noqa: E402
import b1feat as FT  # noqa: E402
import b1gate as G  # noqa: E402
from scipy import stats  # noqa: E402

RAW = Path(r"C:\Users\zhang\bci-data\raw\penn-ram-fr1")
OUT = Path(r"C:\Users\zhang\bci-data\derived\b1-penn-ram-fr1")
RESULTS = HERE / "results"
N_SUBJECTS = 30
N_RANDOM_A0 = 300
N1_SEEDS = 20

# ------------------------------------------------------------------------------------------- utils


class Ctx:
    def __init__(self, raw: Path, out: Path, results: Path | None, n_subjects: int, workers: int, n_boot: int):
        self.raw, self.out, self.results = raw, out, results
        self.n_subjects, self.workers, self.n_boot = n_subjects, workers, n_boot
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "feat").mkdir(exist_ok=True)
        (self.out / "tmp").mkdir(exist_ok=True)

    def log(self, msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        with (self.out / "b1.log").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(line, flush=True)

    def stopped(self) -> bool:
        return (self.out / "stop").exists()


def jdump(obj, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True, default=_jdefault), encoding="utf-8")
    os.replace(tmp, path)


def _jdefault(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def jload(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------- parse


def parse_session(raw_files: Path, subject: str, ses: int) -> tuple[bool, str, dict]:
    p = D.session_paths(raw_files, subject, ses)
    if not p["edf"].exists() or not p["ok"].exists() or not p["events"].exists():
        return False, "not downloaded", {}
    try:
        h = D.read_edf_header(p["edf"])
        fs = h.fs
        words, cnt = D.words_from_events(D.read_events(p["events"]))
    except Exception as e:  # header or events error -> session dropped (plan)
        return False, f"parse error: {type(e).__name__}: {e}", {}
    if len(words) == 0:
        return False, "no WORD events", {}
    return True, "ok", {"fs": fs, "n_samples": h.n_samples, "n_channels": len(h.data_idx), **cnt,
                        "n_words": len(words)}


def stage_parse(ctx: Ctx) -> dict:
    path = ctx.out / "subjects.json"
    if path.exists():
        return jload(path)
    sel = D.load_selection(ctx.raw)
    files = ctx.raw / "files"
    chosen, log = [], []
    for ent in sel["order"]:
        if len(chosen) == ctx.n_subjects:
            break
        s, sessions = ent["subject"], ent["sessions"]
        if not (files / s).exists():
            ctx.log(f"STOP: {s} (next in hash order) is not downloaded; run download.py --extra {len(log) + 1}")
            raise SystemExit(5)
        ok = []
        for n in sessions:
            good, why, info = parse_session(files, s, n)
            if good:
                ok.append({"session": n, **info})
            else:
                log.append({"subject": s, "session": n, "reason": why})
                ctx.log(f"drop {s} ses-{n}: {why}")
        if len(ok) >= 3:
            chosen.append({"subject": s, "sessions": ok})
        else:
            log.append({"subject": s, "reason": f"only {len(ok)} usable sessions: subject replaced"})
            ctx.log(f"replace {s}: only {len(ok)} usable sessions")
    if len(chosen) < ctx.n_subjects:
        ctx.log(f"STOP: only {len(chosen)} usable subjects")
        raise SystemExit(5)
    for r, c in enumerate(chosen, start=1):
        c["rank"] = r
    res = {"subjects": chosen, "drops": log}
    jdump(res, path)
    ctx.log(f"parse: {len(chosen)} subjects, {sum(len(c['sessions']) for c in chosen)} sessions, "
            f"{len(log)} drop / replacement records")
    return res


# -------------------------------------------------------------------------------------- features


class CMReader:
    """Channel-major int16 memmap with the EdfReader.segment interface (physical units)."""

    def __init__(self, mm: np.ndarray, gain: np.ndarray, offset: np.ndarray):
        self.mm, self.gain, self.offset = mm, gain, offset
        self.n_samples = mm.shape[1]

    def segment(self, a: int, b: int) -> np.ndarray:
        return self.mm[:, a:b].astype(np.float64) * self.gain[:, None] + self.offset[:, None]

    def channel(self, k: int) -> np.ndarray:
        return self.mm[k].astype(np.float64) * self.gain[k] + self.offset[k]


def feat_name(rank: int, ses: int) -> str:
    return f"r{rank:02d}_ses{ses}.npz"


def session_features(raw_files: str, out: str, subject: str, rank: int, ses: int, is_test: bool,
                     index_mode: str) -> str:
    """Worker: A0 statistics + features of one session; writes feat/<name>.npz. Returns a log line."""
    t0 = time.time()
    outp = Path(out) / "feat" / feat_name(rank, ses)
    if index_mode != "sample":
        outp = outp.with_name(outp.stem + f"_{index_mode}.npz")
    if outp.exists():
        return f"skip {outp.name}"
    p = D.session_paths(Path(raw_files), subject, ses)
    rd = D.EdfReader(p["edf"])
    fs = rd.fs
    words, _ = D.words_from_events(D.read_events(p["events"]))
    idx_all = D.event_index(words, fs, index_mode)
    valid = FT.valid_word_mask(idx_all, fs, rd.n_samples) & (words.sample >= 0)   # amendment-1 F6
    w = words.subset(valid)
    idx = idx_all[valid]
    tmp = Path(out) / "tmp" / f"r{rank:02d}_ses{ses}_{os.getpid()}.i16"
    mm = rd.to_channel_major(tmp)
    cm = None
    try:
        cm = CMReader(mm, rd.gain, rd.offset)
        # A0 (labels not used): WORD statistic vs 300 random times, seed [rank, session, 0]
        a0w = D.a0_statistic(cm, idx, fs)
        rnd = D.a0_random_times(idx, fs, N_RANDOM_A0, [rank, ses, 0])
        a0r = D.a0_statistic(cm, rnd, fs)
        nulls = None
        if is_test:
            L = FT.epoch_len(fs)
            nulls = {"phases": FT.common_phases(len(idx), L, [rank, 7, 3]),
                     "Z": FT.common_gaussian(len(idx), L, [rank, 7, 4])}
        bank = FT.morlet_bank(fs)
        keys = ["main", "p0"] + (["n2", "n3a", "n3b"] if is_test else [])
        nc = mm.shape[0]
        arr = {k: np.empty((len(idx), nc, len(FT.FREQS)), dtype=np.float32) for k in keys}
        for c in range(nc):
            f = FT.channel_features(cm.channel(c), fs, idx, nulls, bank)
            for k in keys:
                arr[k][:, c, :] = f[k]
        z = {k: FT.zscore_session(arr[k].reshape(len(idx), -1).astype(np.float64)).reshape(arr[k].shape)
             .astype(np.float32) for k in keys}
    finally:
        cm = None
        mm._mmap.close()          # Windows: a mapped file cannot be deleted
        del mm
        try:
            tmp.unlink()
        except OSError:
            pass
    rd.close()
    part = outp.with_suffix(".part.npz")
    np.savez(part, labels=np.array(rd.labels), y=w.recalled, lst=w.lst, sp=w.serialpos, fs=fs,
             a0=np.array([a0w, a0r]), n_dropped_range=int((~valid).sum()), **z)
    os.replace(part, outp)
    return f"feat {outp.name}: {len(idx)} words, {nc} ch, {int((~valid).sum())} words out of range, {time.time() - t0:.0f} s"


def stage_feat(ctx: Ctx, subj: dict, index_mode: str = "sample") -> bool:
    jobs = []
    for c in subj["subjects"]:
        ses = [s["session"] for s in c["sessions"]]
        for n in ses:
            jobs.append((c["subject"], c["rank"], n, n == ses[-1]))
    todo = [j for j in jobs if not (ctx.out / "feat" / (feat_name(j[1], j[2]) if index_mode == "sample" else
                                    feat_name(j[1], j[2]).replace(".npz", f"_{index_mode}.npz"))).exists()]
    ctx.log(f"feat ({index_mode}): {len(jobs) - len(todo)} of {len(jobs)} sessions done, {len(todo)} to do, "
            f"{ctx.workers} workers")
    if not todo:
        return True
    with ProcessPoolExecutor(max_workers=ctx.workers) as ex:
        futs = {}
        it = iter(todo)

        def submit_next() -> bool:
            if ctx.stopped():
                return False
            try:
                s, r, n, t = next(it)
            except StopIteration:
                return False
            futs[ex.submit(session_features, str(ctx.raw / "files"), str(ctx.out), s, r, n, t, index_mode)] = (s, n)
            return True

        for _ in range(ctx.workers):
            submit_next()
        while futs:
            done = next(as_completed(list(futs)))
            s, n = futs.pop(done)
            try:
                ctx.log(done.result())
            except Exception:
                ctx.log(f"ERROR feat {s} ses-{n}:\n{traceback.format_exc()}")
                raise
            submit_next()
    if ctx.stopped():
        ctx.log("stop file found: exit after the running sessions")
        return False
    return True


# ------------------------------------------------------------------------------------------ A0


def a0_decision(ctx: Ctx, subj: dict, index_mode: str) -> dict:
    wv, rv = [], []
    for c in subj["subjects"]:
        for s in c["sessions"]:
            name = feat_name(c["rank"], s["session"])
            if index_mode != "sample":
                name = name.replace(".npz", f"_{index_mode}.npz")
            with np.load(ctx.out / "feat" / name) as z:
                a = z["a0"]
            wv.append(float(a[0]))
            rv.append(float(a[1]))
    wv, rv = np.array(wv), np.array(rv)
    ok = np.isfinite(wv) & np.isfinite(rv)
    t = stats.wilcoxon(wv[ok], rv[ok], alternative="greater")
    res = {"index_mode": index_mode, "n_sessions": int(ok.sum()), "wilcoxon_stat": float(t.statistic),
           "p_one_sided": float(t.pvalue), "pass": bool(t.pvalue < 0.01),
           "median_ratio_word_over_random": float(np.median(wv[ok] / rv[ok])),
           "share_sessions_word_gt_random": float(np.mean(wv[ok] > rv[ok]))}
    ctx.log(f"A0 ({index_mode}): p = {res['p_one_sided']:.3g}, median ratio {res['median_ratio_word_over_random']:.3f}, "
            f"pass = {res['pass']}")
    return res


# ---------------------------------------------------------------------------------- subject data


def b0_features(lst: np.ndarray, sp: np.ndarray) -> np.ndarray:
    oh = np.zeros((len(sp), 12))
    for k in range(12):
        oh[:, k] = (sp == k + 1)
    return np.column_stack([oh, lst.astype(np.float64)])


def load_subject(ctx: Ctx, c: dict, index_mode: str) -> dict:
    """Per session: z-scored features per kind, labels, lists, serial positions; common channels."""
    sess = []
    for s in c["sessions"]:
        name = feat_name(c["rank"], s["session"])
        if index_mode != "sample":
            name = name.replace(".npz", f"_{index_mode}.npz")
        with np.load(ctx.out / "feat" / name) as z:
            d = {k: z[k] for k in z.files}
        d["session"] = s["session"]
        d["labels"] = [str(x) for x in d["labels"]]
        sess.append(d)
    common = set(sess[0]["labels"])
    for d in sess[1:]:
        common &= set(d["labels"])
    common = sorted(common)
    # drop channels with any nan in any session (any kind) -> SD = 0 or a non-finite value
    keep = []
    for ch in common:
        good = True
        for d in sess:
            k = d["labels"].index(ch)
            for kind in ("main", "p0", "n2", "n3a", "n3b"):
                if kind in d and not np.all(np.isfinite(d[kind][:, k, :])):
                    good = False
        if good:
            keep.append(ch)
    for d in sess:
        ix = [d["labels"].index(ch) for ch in keep]
        for kind in ("main", "p0", "n2", "n3a", "n3b"):
            if kind in d:
                d[kind] = d[kind][:, ix, :].reshape(d[kind].shape[0], -1).astype(np.float64)
        b0 = b0_features(d["lst"], d["sp"])
        mu, sd = b0.mean(axis=0), b0.std(axis=0)
        d["b0"] = np.where(sd > 0, (b0 - mu) / np.where(sd > 0, sd, 1.0), 0.0)
        d["b0n"] = np.column_stack([d["main"], d["b0"]])
    return {"rank": c["rank"], "subject": c["subject"], "sessions": sess, "n_common": len(common),
            "n_channels": len(keep)}


KINDS = {"neural": "main", "b0": "b0", "b0n": "b0n", "p0": "p0"}


def split_cal(sd: dict) -> tuple[np.ndarray, np.ndarray]:
    cal = sd["sessions"][-2]
    order_l, cert_l = D.cal_list_split(sd["subject"], int(cal["session"]), list(np.unique(cal["lst"])))
    if not order_l:          # amendment-1 F10: fewer than 3 cal lists -> all cal words are order words
        order_l, cert_l = cert_l, []
    return np.isin(cal["lst"], order_l), np.isin(cal["lst"], cert_l)


def fit_models(subjects: list[dict], labels: dict | None = None, kinds: tuple[str, ...] = tuple(KINDS)) -> dict:
    """Decoders on train, scores on cal, Platt on order words; returns per subject / kind.

    ``labels``: optional {(rank, session): y} that replaces the labels (N1).
    """
    out = {}
    for sd in subjects:
        ss = sd["sessions"]
        ys = [labels[(sd["rank"], int(d["session"]))] if labels else d["y"].astype(int) for d in ss]
        order, cert = split_cal(sd)
        per = {}
        for name in kinds:
            kind = KINDS[name]
            Xtr = np.vstack([d[kind] for d in ss[:-2]])
            ytr = np.concatenate(ys[:-2])
            m = G.fit_logreg(Xtr, ytr)
            s_cal = m.logit(ss[-2][kind])
            pl = G.fit_platt(s_cal[order], ys[-2][order])
            per[name] = {"model": m, "platt": pl, "s_cal": s_cal, "p_cal": pl(s_cal)}
        out[sd["rank"]] = {"per": per, "y_cal": ys[-2], "y_test": ys[-1], "order": order, "cert": cert}
    return out


def fit_gates(models: dict, kind: str) -> dict:
    ranks = sorted(models)
    yo = np.concatenate([models[r]["y_cal"][models[r]["order"]] for r in ranks])
    yc = np.concatenate([models[r]["y_cal"][models[r]["cert"]] for r in ranks])
    po = np.concatenate([models[r]["per"][kind]["p_cal"][models[r]["order"]] for r in ranks])
    pc = np.concatenate([models[r]["per"][kind]["p_cal"][models[r]["cert"]] for r in ranks])
    b = float(yo.mean())
    tau_p = b + 0.10
    tau_m = (1.0 - b) + 0.05
    gp = G.fit_gate(po, yo == 0, pc, yc == 0, tau_p)
    gm = G.fit_gate(1 - po, yo == 1, 1 - pc, yc == 1, tau_m)
    q = G.fit_offer(pc, yc)
    return {"b_order": b, "n_order_words": int(yo.size), "n_cert_words": int(yc.size), "cert_recall_rate": float(yc.mean()),
            "tau_plus": tau_p, "tau_minus": tau_m, "g_plus": gp, "g_minus": gm, "offer_q": q}


# ------------------------------------------------------------------------------------------- fit


def stage_fit(ctx: Ctx, subj: dict) -> dict | None:
    gpath = ctx.out / "gate.json"
    if gpath.exists():
        return jload(gpath)
    a0 = a0_decision(ctx, subj, "sample")
    mode = "sample"
    if not a0["pass"]:
        ctx.log("A0 failed with `sample`: repeat once with round(onset * fs)")
        if not stage_feat(ctx, subj, "onset"):
            return None
        a0b = a0_decision(ctx, subj, "onset")
        a0 = {"sample": a0, "onset": a0b, "pass": a0b["pass"], "index_mode": "onset"}
        mode = "onset"
        if not a0b["pass"]:
            res = {"outcome": "N", "reason": "event timing not usable (A0 failed)", "a0": a0}
            jdump(res, ctx.out / "summary.json")
            if ctx.results:
                ctx.results.mkdir(exist_ok=True)
                jdump(res, ctx.results / "summary.json")
            ctx.log("outcome N: A0 failed")
            return None
    subjects = [load_subject(ctx, c, mode) for c in subj["subjects"]]
    for sd in subjects:
        ctx.log(f"subject rank {sd['rank']} ({sd['subject']}): {sd['n_channels']} of {sd['n_common']} common channels, "
                f"{len(sd['sessions'])} sessions")
    models = fit_models(subjects)
    gates = {k: fit_gates(models, k) for k in KINDS}
    mpath = ctx.out / "models.npz"
    arrs = {}
    for r, m in models.items():
        for k, v in m["per"].items():
            arrs[f"r{r:02d}_{k}_w"] = v["model"].w
            arrs[f"r{r:02d}_{k}_b"] = np.array([v["model"].b])
    np.savez(mpath, **arrs)
    platt = {str(r): {k: [m["per"][k]["platt"].a, m["per"][k]["platt"].b] for k in KINDS} for r, m in models.items()}
    gate = {"plan": "experiments/2026-11-24-b1-memory-state-gate/plan.md", "amendment": "amendment-1.md",
            "alpha": G.ALPHA, "delta": G.DELTA, "C": G.C_EZZYAT, "index_mode": mode, "a0": a0,
            "n_subjects": len(subjects), "n_sessions": sum(len(sd["sessions"]) for sd in subjects),
            "n_cal_order_lists_total": int(sum(len(np.unique(sd["sessions"][-2]["lst"][models[sd["rank"]]["order"]]))
                                               for sd in subjects)),
            "n_cal_lists_total": int(sum(len(np.unique(sd["sessions"][-2]["lst"])) for sd in subjects)),
            "n_subjects_no_order_list_F10": int(sum(len(np.unique(sd["sessions"][-2]["lst"])) < 3 for sd in subjects)),
            "n_words_dropped_edge_F6": int(sum(int(d["n_dropped_range"]) for sd in subjects for d in sd["sessions"])),
            "channels_per_subject": {"min": int(min(sd["n_channels"] for sd in subjects)),
                                     "median": float(np.median([sd["n_channels"] for sd in subjects])),
                                     "max": int(max(sd["n_channels"] for sd in subjects))},
            "gates": gates, "platt_by_rank": platt, "models_sha256": sha_file(mpath),
            "features_sha256": {p.name: sha_file(p) for p in sorted((ctx.out / "feat").glob("r*.npz"))}}
    jdump(gate, gpath)
    if ctx.results:
        ctx.results.mkdir(exist_ok=True)
        g2 = dict(gate)
        g2.pop("features_sha256")     # file names only carry ranks; kept local to keep the commit small
        jdump(g2, ctx.results / "gate.json")
    gp = gates["neural"]["g_plus"]
    ctx.log(f"fit: b_order {gates['neural']['b_order']:.4f}, G+ lambda {gp['lambda']}, G- lambda "
            f"{gates['neural']['g_minus']['lambda']}; gate.json written")
    return gate


def gate_committed(ctx: Ctx) -> bool:
    if ctx.results is None:
        return True
    p = ctx.results / "gate.json"
    try:
        rel = p.resolve().relative_to(ROOT).as_posix()
    except ValueError:        # a results folder outside the repo (tests): nothing to commit
        return p.exists()
    r1 = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", rel], capture_output=True)
    r2 = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--", rel], capture_output=True)
    return r1.returncode == 0 and r2.returncode == 0


# ------------------------------------------------------------------------------------------ test


def score_test(models: dict, subjects: list[dict], gate: dict, kind: str, feat_key: str | None = None) -> dict:
    out = {}
    for sd in subjects:
        r = sd["rank"]
        m = models[r]["per"][kind]
        X = sd["sessions"][-1][feat_key or KINDS[kind]]
        s = m["model"].logit(X)
        out[r] = {"s": s, "p": m["platt"](s)}
    return out


def platt_from_gate(gate: dict, r: int, kind: str) -> G.Platt:
    a, b = gate["platt_by_rank"][str(r)][kind]
    return G.Platt(a, b)


def evaluate_scores(gate_k: dict, p_by_rank: dict, y_by_rank: dict, n_boot: int) -> dict:
    ranks = sorted(p_by_rank)
    fp = [G.flags(p_by_rank[r], gate_k["g_plus"]["lambda"]) for r in ranks]
    fm = [G.flags(1 - p_by_rank[r], gate_k["g_minus"]["lambda"]) for r in ranks]
    ys = [y_by_rank[r] for r in ranks]
    res = {"g_plus": G.gate_metrics(fp, ys, 0, n_boot), "g_minus": G.gate_metrics(fm, ys, 1, n_boot)}
    q = gate_k["offer_q"]
    sing = cover = n = 0
    for r in ranks:
        inr, inf = G.offer_sets(p_by_rank[r], q)
        y = y_by_rank[r]
        sing += int(np.sum(inr ^ inf))
        cover += int(np.sum(np.where(y == 1, inr, inf)))
        n += len(y)
    res["offer"] = {"q": q, "singleton_share": sing / n, "coverage": cover / n}
    return res


def stage_test(ctx: Ctx, subj: dict, gate: dict) -> dict:
    spath = ctx.out / "summary.json"
    if spath.exists():
        return jload(spath)
    if not gate_committed(ctx):
        ctx.log("gate.json is not committed: commit + push results/gate.json, then run again (exit 4)")
        raise SystemExit(4)
    mode = gate["index_mode"]
    subjects = [load_subject(ctx, c, mode) for c in subj["subjects"]]
    if sha_file(ctx.out / "models.npz") != gate["models_sha256"]:
        raise RuntimeError("models.npz changed after gate.json")
    models = fit_models(subjects)          # deterministic refit; checked against the saved weights below
    with np.load(ctx.out / "models.npz") as z:
        for r, m in models.items():
            for k in KINDS:
                if not np.allclose(z[f"r{r:02d}_{k}_w"], m["per"][k]["model"].w, rtol=0, atol=1e-12):
                    raise RuntimeError("refit differs from the saved decoder")
                m["per"][k]["platt"] = platt_from_gate(gate, r, k)
    y_test = {sd["rank"]: sd["sessions"][-1]["y"].astype(int) for sd in subjects}
    per_subject = {}
    summary: dict = {"n_subjects": len(subjects), "n_test_words": int(sum(len(v) for v in y_test.values())),
                     "test_recall_rate": float(np.mean(np.concatenate(list(y_test.values())))),
                     "index_mode": mode, "a0": gate["a0"]}
    # real input, all kinds
    real = {}
    for kind in KINDS:
        sc = score_test(models, subjects, gate, kind)
        aucs = {r: G.auc(sc[r]["s"], y_test[r]) for r in sc}
        real[kind] = sc
        summary[kind] = {"auc": G.ttest_vs_half(list(aucs.values())),
                         **evaluate_scores(gate["gates"][kind], {r: sc[r]["p"] for r in sc}, y_test, ctx.n_boot),
                         "gate": {"lambda_plus": gate["gates"][kind]["g_plus"]["lambda"],
                                  "lambda_minus": gate["gates"][kind]["g_minus"]["lambda"],
                                  "tau_plus": gate["gates"][kind]["tau_plus"],
                                  "tau_minus": gate["gates"][kind]["tau_minus"],
                                  "b_order": gate["gates"][kind]["b_order"]}}
        for r in sc:
            per_subject.setdefault(sd_code(subjects, r), {})[f"auc_{kind}"] = aucs[r]
    gN = gate["gates"]["neural"]
    # invariance checks N2, N3a; safety null N3b (frozen decoder + gate)
    for null in ("n2", "n3a", "n3b"):
        sc = score_test(models, subjects, gate, "neural", null)
        summary[null] = {"auc": G.ttest_vs_half([G.auc(sc[r]["s"], y_test[r]) for r in sc]),
                         **evaluate_scores(gN, {r: sc[r]["p"] for r in sc}, y_test, ctx.n_boot)}
        if null in ("n2", "n3a"):
            agree = [np.mean(G.flags(sc[r]["p"], gN["g_plus"]["lambda"]) ==
                             G.flags(real["neural"][r]["p"], gN["g_plus"]["lambda"])) for r in sc]
            summary[null]["g_plus_flag_agreement_with_real"] = float(np.mean(agree))
            summary[null]["score_corr_with_real"] = float(np.mean(
                [np.corrcoef(sc[r]["s"], real["neural"][r]["s"])[0, 1] for r in sc]))
    # N4 shuffled signal: features of a random other word of the same session, seed [rank, 7, 5]
    p4 = {}
    for sd in subjects:
        r = sd["rank"]
        n = len(y_test[r])
        rng = np.random.default_rng([r, 7, 5])
        j = rng.integers(0, n - 1, size=n)
        j = j + (j >= np.arange(n))           # uniform over the other n - 1 words
        p4[r] = real["neural"][r]["p"][j]
    summary["n4"] = evaluate_scores(gN, p4, y_test, ctx.n_boot)
    # N5 uniform score
    p5 = {r: np.full(len(y_test[r]), gN["b_order"]) for r in y_test}
    summary["n5"] = evaluate_scores(gN, p5, y_test, ctx.n_boot)
    # N1 label-permuted, end to end (20 seeds [k, 2026])
    n1 = []
    for k in range(N1_SEEDS):
        rng = np.random.default_rng([k, 2026])
        lab = {}
        for sd in subjects:
            for d in sd["sessions"]:
                lab[(sd["rank"], int(d["session"]))] = rng.permutation(d["y"].astype(int))
        mk = fit_models(subjects, lab, ("neural",))
        gk = fit_gates(mk, "neural")
        yt = {r: mk[r]["y_test"] for r in mk}
        pt = {r: mk[r]["per"]["neural"]["platt"](mk[r]["per"]["neural"]["model"].logit(
            next(sd for sd in subjects if sd["rank"] == r)["sessions"][-1]["main"])) for r in mk}
        ev = evaluate_scores(gk, pt, yt, 1000)
        n1.append({"seed": k, "g_plus_certified_any": gk["g_plus"]["certified_any"], "lambda_plus": gk["g_plus"]["lambda"],
                   "g_minus_certified_any": gk["g_minus"]["certified_any"],
                   "test_g_plus_flag_rate": ev["g_plus"]["flag_rate"], "test_g_plus_wrong_rate": ev["g_plus"]["wrong_rate"],
                   "test_g_plus_precision_minus_base": ev["g_plus"]["precision_minus_base"]})
        ctx.log(f"N1 seed {k}: G+ certified {gk['g_plus']['certified_any']} (lambda {gk['g_plus']['lambda']})")
    summary["n1"] = {"runs": n1, "n_g_plus_certified": int(sum(x["g_plus_certified_any"] for x in n1)),
                     "n_g_minus_certified": int(sum(x["g_minus_certified_any"] for x in n1))}
    summary["rules"], summary["outcome"] = evaluate_rules(summary, gate)
    jdump({k: v for k, v in per_subject.items()}, ctx.out / "per_subject_local.json")
    jdump(summary, spath)
    if ctx.results:
        jdump(summary, ctx.results / "summary.json")
    ctx.log(f"test done: outcome {summary['outcome']}")
    return summary


def sd_code(subjects: list[dict], r: int) -> str:
    return next(sd["subject"] for sd in subjects if sd["rank"] == r)


# ------------------------------------------------------------------------------------------ rules


def evaluate_rules(s: dict, gate: dict) -> tuple[dict, str]:
    alpha = gate["alpha"]
    tau = gate["gates"]["neural"]["tau_plus"]
    gp = s["neural"]["g_plus"]
    rules = {}
    rules["A0"] = {"pass": bool(gate["a0"]["pass"])}
    a = s["neural"]["auc"]
    rules["V1"] = {"mean_auc": a["mean"], "p_two_sided": a["p_two_sided"],
                   "pass": bool(a["mean"] is not None and a["mean"] >= 0.55 and a["p_two_sided"] < 0.01)}
    rules["i"] = {"n_certified_of_20": s["n1"]["n_g_plus_certified"], "pass": s["n1"]["n_g_plus_certified"] <= 4}
    if gp["flags"] == 0:
        rules["ii"] = {"flags": 0, "pass": True, "note": "no flag"}
    else:
        up = gp["boot"]["wrong_rate"][1]
        rules["ii"] = {"wrong_rate": gp["wrong_rate"], "limit": 1 - tau, "boot_upper": up, "boot_limit": 1 - tau + 0.10,
                       "pass": bool(gp["wrong_rate"] <= 1 - tau and up is not None and up <= 1 - tau + 0.10)}
    lo = gp["boot"]["precision_minus_base"][0]
    rules["iii"] = {"flag_rate": gp["flag_rate"], "boot_lower_precision_minus_base": lo,
                    "pass": bool(gp["flag_rate"] >= 0.05 and lo is not None and lo > 0)}
    n3 = s["n3b"]["g_plus"]
    n4 = s["n4"]["g_plus"]
    n3_ok = bool(n3["flag_rate"] <= alpha and (n3["flag_rate_cp_upper95"] or 0.0) <= 2 * alpha
                 and (n3["boot"]["flag_rate"][1] or 0.0) <= 2 * alpha)
    n4_ok = bool(n4["flags"] == 0 or n4["precision"] <= n4["base_rate"] + 0.05)
    rules["iv"] = {"n3b_flag_rate": n3["flag_rate"], "n3b_cp_upper": n3["flag_rate_cp_upper95"],
                   "n3b_boot_upper": n3["boot"]["flag_rate"][1], "n4_precision": n4["precision"],
                   "n4_base_rate": n4["base_rate"], "n3b_pass": n3_ok, "n4_pass": n4_ok, "pass": n3_ok and n4_ok}
    if gp["flag_rate"] is not None and gp["flag_rate"] <= alpha:
        rules["iv"]["n3b_over_real_flag_ratio"] = (n3["flag_rate"] / gp["flag_rate"]) if gp["flag_rate"] > 0 else None
    if not rules["A0"]["pass"] or not rules["V1"]["pass"]:
        out = "N"
    elif not (rules["i"]["pass"] and rules["ii"]["pass"] and rules["iv"]["pass"]):
        out = "C"
    elif not rules["iii"]["pass"]:
        out = "B"
    else:
        out = "A"
    b0 = s["b0"]["g_plus"]
    rules["qualifier_behaviour_explains_it"] = bool(
        s["b0"]["gate"]["lambda_plus"] is not None and b0["flags"] >= gp["flags"] and out in ("A", "B"))
    return rules, out


# ------------------------------------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["parse", "feat", "fit", "test", "all"])
    ap.add_argument("--raw", default=str(RAW))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--results", default=str(RESULTS), help="repo results folder; 'none' to skip")
    ap.add_argument("--n-subjects", type=int, default=N_SUBJECTS)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--n-boot", type=int, default=10_000)
    args = ap.parse_args()
    ctx = Ctx(Path(args.raw), Path(args.out), None if args.results == "none" else Path(args.results),
              args.n_subjects, args.workers, args.n_boot)
    ctx.log(f"start stage {args.stage} (pid {os.getpid()})")
    subj = stage_parse(ctx)
    if args.stage == "parse":
        return 0
    if args.stage in ("feat", "all"):
        if not stage_feat(ctx, subj):
            return 3
        if args.stage == "feat":
            return 0
    gate = stage_fit(ctx, subj)
    if gate is None:
        return 0 if (ctx.out / "summary.json").exists() else 3
    if args.stage == "fit":
        return 0
    if args.stage == "all" and not gate_committed(ctx):
        ctx.log("gate.json written; waiting for the commit (exit 4)")
        return 4
    stage_test(ctx, subj, gate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
