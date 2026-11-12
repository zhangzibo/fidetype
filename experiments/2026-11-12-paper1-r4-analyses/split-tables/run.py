"""R4: item tables for the extended repeated splits (shared input of items 2-7).

Builds per-split item tables (fit-A pipeline; reused = fit-A, clean
calibration, test), with the round-3 split generator and seed:

- B2T '25 splits r = 50..199 (guard on, ours + published): the R3 generator
  (seed 3, day-stratified 1/4 fit-A, 1/4 clean calibration, 1/2 test) with
  R = 200; its first 50 splits are the R3 splits (checked against
  ``splits-b2t.json``).
- B2T '25 splits r = 0..199 with the guard off (plain threshold), ours +
  published (item 5).
- B2T '25 published gate, splits r = 0..49, published-sentence bonus
  ``published_margin`` in {0, 0.5, 1, 4} (item 6; 2.0 = the R3 tables).
- sEMG calib / xsession / xsubject splits r = 0..49 with the guard off
  (item 5; the R3 generator, seed 3 + 100).

Tables go to ``C:/Users/zhang/bci-data/cache/paper1-r4/splits`` (outside the
repo). Frame temperature snapped to 0.02 (B2T) / 0.01 (sEMG), decode caches
shared with R3.

Run (repo root):
  .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r4-analyses/split-tables/run.py --stage temps
  ... --stage b2t --worker 0 --nworkers 6     (one process per worker)
  ... --stage emg --cond calib
  ... --stage manifest
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common4 as Q  # noqa: E402

K, C = Q.K, Q.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
TAB = Q.CACHE4 / "splits"
TAB.mkdir(exist_ok=True)


def b2t_splits(trials, R: int, seed: int) -> list[dict]:
    """Exact copy of the R3 generator (repeated-splits/run.py: b2t_splits) with R splits."""
    by_day: dict = {}
    for i, t in enumerate(trials):
        by_day.setdefault(int(t.post_implant_day), []).append(i)
    rng = np.random.default_rng(seed)
    out = []
    for r in range(R):
        A, Cc, T = [], [], []
        for d in sorted(by_day):
            idx = np.array(by_day[d])
            p = rng.permutation(idx.size)
            na = int(round(idx.size / 4))
            nc = int(round(idx.size / 4))
            A += idx[p[:na]].tolist()
            Cc += idx[p[na:na + nc]].tolist()
            T += idx[p[na + nc:]].tolist()
        out.append({"r": r, "A": sorted(A), "cal": sorted(Cc), "test": sorted(T)})
    return out


def stage_temps() -> None:
    K.install_snap(CONFIG["frame_T_snap_b2t"])
    ctx = C.b2t_ctx()
    trials = ctx.fit + ctx.test
    items = ctx.items(trials)
    sp = b2t_splits(trials, CONFIG["R_b2t"], CONFIG["seed"])
    r3 = Q.SPLITS_B2T["splits"]
    for a, b in zip(sp[: len(r3)], r3):
        assert a["A"] == b["A"] and a["cal"] == b["cal"] and a["test"] == b["test"], f"split {a['r']} differs from R3"
    for s in sp:
        A = [items[i] for i in s["A"]]
        n_conf = int(round(len(A) * 0.5))
        temp = A[: len(A) - n_conf]
        s["T_fitted"], _ = K.fit_T([it.stream(0) for it in temp], [it.stream_text for it in temp])
        s["T_used"] = K.snap(s["T_fitted"], CONFIG["frame_T_snap_b2t"])
    C.dump({"n_trials": len(trials), "days": [int(t.post_implant_day) for t in trials], "splits": sp,
            "first_50_equal_r3": True, "distinct_T_used": sorted({s["T_used"] for s in sp})}, Q.CACHE4 / "splits-b2t-200.json")
    C.dump({"R": len(sp), "first_50_equal_r3": True, "T_used": [s["T_used"] for s in sp],
            "distinct_T_used": sorted({s["T_used"] for s in sp})}, OUT / "splits-b2t-200-summary.json")
    C.log("distinct T:", sorted({s["T_used"] for s in sp}))


def jobs_for(r: int) -> list[tuple[str, str, bool, float | None]]:
    """(job name, decoder, use_guard, margin)."""
    j = []
    if r >= 50:
        j += [("ours-g1", "ours", True, None), ("published-g1", "published", True, None)]
    j += [("ours-g0", "ours", False, None), ("published-g0", "published", False, None)]
    if r < 50:
        j += [(f"published-m{m:g}", "published", True, m) for m in CONFIG["margins"]]
    return j


def stage_b2t(worker: int, nworkers: int) -> None:
    ctx, router, trials, items = Q.b2t_env(CONFIG["frame_T_snap_b2t"])
    sp = json.loads((Q.CACHE4 / "splits-b2t-200.json").read_text(encoding="utf-8"))["splits"]
    groups: dict = {}
    for s in sp:
        groups.setdefault(f"{s['T_used']:.2f}", []).append(s)
    # balance: chunks of <= 6 splits of one temperature (one decode cache in memory), greedy by job count
    chunks = []
    for g, ss in groups.items():
        for i in range(0, len(ss), 6):
            chunks.append((g, ss[i:i + 6]))
    chunks.sort(key=lambda c: -sum(len(jobs_for(s["r"])) for s in c[1]))
    load = [0] * nworkers
    assign = [[] for _ in range(nworkers)]
    for ch in chunks:
        w = int(np.argmin(load))
        assign[w].append(ch)
        load[w] += sum(len(jobs_for(s["r"])) for s in ch[1])
    mine = assign[worker]
    C.log(f"worker {worker}/{nworkers}: {len(mine)} chunks, {load[worker]} jobs")
    for g, ss in mine:
        router.d = {k: v for k, v in router.d.items() if k == g}
        for s in ss:
            for job, which, guard, margin in jobs_for(s["r"]):
                p = TAB / f"b2t-{job}-{s['r']:03d}.json"
                if p.exists():
                    continue
                t0 = time.time()
                A = [items[i] for i in s["A"]]
                n0 = router.new_count()
                res = Q.b2t_tables(ctx, which, A, {"reuse": A, "cal": [items[i] for i in s["cal"]],
                                                   "test": [items[i] for i in s["test"]]}, use_guard=guard, margin=margin)
                res.update({"r": s["r"], "job": job, "which": which, "test_idx": s["test"], "cal_idx": s["cal"],
                            "new_decodes": router.new_count() - n0})
                C.dump(res, p)
                C.log(f"{job} split {s['r']}: T {res['T_used']:.2f} commit_p {res['cal']['lam_old']} "
                      f"new decodes {res['new_decodes']} ({time.time() - t0:.0f}s)")
            router.save()
    router.save()


def stage_emg(cname: str) -> None:
    """R3 emg_tables with the guard off (same generator, seed + 100, same draws)."""
    K.install_snap(CONFIG["frame_T_snap_emg"])
    cond = C.emg_condition(cname)
    router = K.TRouter(cond.decode.fn, f"emg-{cname}-w{cond.lm_weight}")
    pool = list(cond.A) + list(cond.Bv)
    who = np.asarray(cond.fit_who)
    rng = np.random.default_rng(CONFIG["seed"] + 100)
    for r in range(CONFIG["R_emg"]):
        t0 = time.time()
        A, B1, B2 = [], [], []
        for pid in sorted(set(who.tolist())):
            idx = np.where(who == pid)[0]
            q = rng.permutation(idx)
            na, nb = int(round(idx.size / 2)), int(round(idx.size / 4))
            A += q[:na].tolist()
            B1 += q[na:na + nb].tolist()
            B2 += q[na + nb:].tolist()
        A, B1, B2 = (rng.permutation(np.array(x)).tolist() for x in (A, B1, B2))
        r3 = json.loads((Q.TAB3 / f"emg-{cname}-{r:03d}.json").read_text(encoding="utf-8"))["assign"]
        assert r3 == {"A": A, "B1": B1, "B2": B2}, f"emg split {r} differs from R3"
        p = TAB / f"emg-{cname}-g0-{r:03d}.json"
        if p.exists():
            continue
        pipe = C.TrustPipeline(router, C.HarnessConfig(seed=C.SEED, user_config=cond.user, use_guard=False, **cond.base), {})
        pipe.fit([pool[i] for i in A], [pool[i] for i in B1])
        res = {"r": r, "cond": cname, "use_guard": False, "T_fitted": K.TState.fitted, "T_used": K.TState.used,
               "fit_report": C.clean(pipe.fit_report), "assign": {"A": A, "B1": B1, "B2": B2},
               "reuse": Q.M13.item_table(pipe, [pool[i] for i in B1]), "cal": Q.M13.item_table(pipe, [pool[i] for i in B2]),
               "test": Q.M13.item_table(pipe, cond.test)}
        router.save()
        C.dump(res, p)
        C.log(f"emg-{cname}-g0 split {r}: T {K.TState.used:.2f} commit_p {pipe.policy.config.commit_p} ({time.time() - t0:.0f}s)")


def stage_manifest() -> None:
    files = sorted(TAB.glob("*.json"))
    cnt: dict = {}
    for f in files:
        key = f.name.rsplit("-", 1)[0]
        cnt[key] = cnt.get(key, 0) + 1
    C.dump({"cache_dir": str(TAB), "counts": cnt, "n_files": len(files)}, OUT / "manifest.json")
    C.log(cnt)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--worker", type=int, default=0)
    ap.add_argument("--nworkers", type=int, default=1)
    ap.add_argument("--cond")
    a = ap.parse_args()
    C.Log.path = OUT / f"run-{a.stage}{'-' + a.cond if a.cond else ''}{f'-w{a.worker}' if a.stage == 'b2t' else ''}.log"
    {"temps": stage_temps, "manifest": stage_manifest}.get(a.stage, lambda: None)()
    if a.stage == "b2t":
        stage_b2t(a.worker, a.nworkers)
    elif a.stage == "emg":
        stage_emg(a.cond)
    C.log("done", a.stage)


if __name__ == "__main__":
    main()
