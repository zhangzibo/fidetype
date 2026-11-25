"""P5-42: the new calibrate(users=...) check and per-user bound on the emg2qwerty arms of the pooled-guard check.

Pre-registration: plan.md (this folder, commit ad51861), rules E0-E2. CPU only. Reads (read only) the files that
the pooled-guard check reads (its E2Q loader: derived/p11-11, p11-12, p11-14 and the P11 experiment modules).
Never derived/p15-50. Writes only C:/Users/zhang/bci-data/derived/p5-42/ and, for the repo, results/e2q.json with
aggregates only (no per-user value: emg2qwerty is research-only data; no text, no id).

The library is a clean copy of src/ at the code commit (``--snap``), because other agents edit the working tree.

Usage (repo root): python experiments/2026-11-25-p5-42-per-user-null/run_e2q.py --snap <dir> [--arm S]
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "1"
os.environ["HIP_VISIBLE_DEVICES"] = "-1"  # CPU only
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import argparse  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p5-42"  # the only place this task writes outside the repo
OUT = HERE / "results"
PGC = REPO / "experiments" / "2026-11-25-pooled-guard-check" / "run.py"
ARMS = ("S", "SL", "L-FL")
ALPHA = 0.05
# E0: the pooled-guard check's reproduction (results.md of that check)
E0 = {"S": ("tcfg-3875f995e4c256fb", 71, 16), "SL": ("tcfg-0cd6e9578e965f42", 80, 16),
      "L-FL": ("tcfg-4b2192820e68660b", 108, 16)}
# the pooled-guard check's full-recipe nulls (results/summary.json there), for the side-by-side report
PGC_SUMMARY = REPO / "experiments" / "2026-11-25-pooled-guard-check" / "results" / "summary.json"


def out_path(p: Path) -> Path:
    assert OWN in Path(p).parents, p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def save_json(obj: object, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def log(*a: object) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(out_path(OWN / "run.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def below_normal() -> None:
    if os.name == "nt":
        import ctypes

        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def load_pgc(snap: Path):
    spec = importlib.util.spec_from_file_location("pgc_run", PGC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["pgc_run"] = m
    spec.loader.exec_module(m)
    m.SNAP = snap  # our library copy (the pooled-guard check used 8dde818)
    m.OWN = OWN  # its loader writes nothing on this path; any write would land here
    return m


def test_eval(m, E, g, arm: str) -> dict:
    """Decisions of guard g on the 1,221 track-test prompts; per-user R3 of the pooled-guard check (local)."""
    users = [r["i"] for r in E.ev]
    truth = [E.R.intended_truth(r) for r in E.ev]
    commit, wrong = [], []
    for r, t in zip(E.ev, truth):
        d = g._decide_quiet(E.W.get(r))
        c = d.action == "commit"
        commit.append(c)
        wrong.append(c and not m.same(d.text, t))
    commit, wrong = np.array(commit), np.array(wrong)
    rec = m.r3(users, commit, wrong)
    tab = rec.pop("_table")
    n_alpha = sum(t["rate"] > ALPHA for t in tab)
    return {"local_table": tab, "n": int(commit.size), "commits": int(commit.sum()), "wrong": int(wrong.sum()),
            "users_rate_above_alpha": int(n_alpha), "users_cp_upper_above_2alpha": int(rec.get("n_above", -1)),
            "r3_passed": bool(rec["passed"]), "n_users": int(rec["n_groups"])}


def run_arm(m, E, arm: str) -> dict:
    import fidetype.trust as ft

    f = out_path(OWN / f"e2q-{arm}.json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    orig = ft.calibrate
    rec: dict = {"arm": arm}
    users = [int(u) if isinstance(u, (int, np.integer)) else u for u in E.users.tolist()]
    for bound in ("pooled", "each", "all"):
        t0 = time.time()
        ft.calibrate = lambda *a, _b=bound, **k: orig(*a, users=users, user_bound=_b, **k)  # noqa: E731
        try:
            g = E.calibrate(arm, list(E.truths), None)
        except ValueError as e:
            rec[bound] = {"status": "refused", "reason": str(e)[:400], "seconds": round(time.time() - t0, 1)}
            log(f"{arm} {bound}: refused: {str(e)[:200]}")
            continue
        finally:
            ft.calibrate = orig
        sh = g.sheet
        r = {"status": "guard", "config_id": g.config_id, "commit_threshold": float(sh.commit_threshold),
             "ltt_commits": int(sh.ltt_commits), "ltt_wrong": int(sh.ltt_wrong_commits), "n_ltt": int(sh.n_ltt),
             "controls": {c.name: [int(c.n_commit), int(c.n)] for c in sh.controls}, "users": sh.users,
             "warnings": [w for w in sh.warnings if w.startswith("user")]}
        if bound != "pooled":
            r["test"] = test_eval(m, E, g, arm)
        r["seconds"] = round(time.time() - t0, 1)
        rec[bound] = r
        log(f"{arm} {bound}: {g.config_id} thr {sh.commit_threshold} LTT {sh.ltt_commits}/{sh.ltt_wrong_commits} "
            f"check {sh.users.get('check', {}).get('verdict')} ({r['seconds']} s)")
    # pooled guard's real test decisions (cached by P11-12 / P11-14), per-user R3 of the same function
    d = E.test_decisions(arm)
    truth = [E.R.intended_truth(r) for r in E.ev]
    commit = np.array([x["action"] == "commit" for x in d])
    wrong = np.array([c and not m.same(x["text"], t) for c, x, t in zip(commit, d, truth)])
    p = m.r3([r["i"] for r in E.ev], commit, wrong)
    tab = p.pop("_table")
    rec["pooled_test"] = {"local_table": tab, "commits": int(commit.sum()), "wrong": int(wrong.sum()),
                          "users_rate_above_alpha": int(sum(t["rate"] > ALPHA for t in tab)),
                          "users_cp_upper_above_2alpha": int(p.get("n_above", -1))}
    save_json(rec, f)
    return rec


def strip_local(x):
    if isinstance(x, dict):
        return {k: strip_local(v) for k, v in x.items() if k != "local_table"}
    if isinstance(x, list):
        return [strip_local(v) for v in x]
    return x


def summary() -> dict:
    pgc = json.loads(PGC_SUMMARY.read_text(encoding="utf-8"))["guards"]
    res: dict = {"task": "P5-42 emg2qwerty re-run", "plan": "plan.md (ad51861)", "alpha": ALPHA,
                 "note": "aggregates only: no per-user value for emg2qwerty, no text, no id",
                 "emg2qwerty_licence": {"data.licence": "CC-BY-NC-SA-4.0", "data.research_only": True}, "arms": {}}
    e0_all = True
    for arm in ARMS:
        rec = strip_local(json.loads((OWN / f"e2q-{arm}.json").read_text(encoding="utf-8")))
        po = rec["pooled"]
        cid, k, w = E0[arm]
        e0 = po.get("config_id") == cid and po.get("ltt_commits") == k and po.get("ltt_wrong") == w
        e0_all &= e0
        c = po["users"]["check"]
        gid = {"S": "E-S", "SL": "E-SL", "L-FL": "E-LFL"}[arm]
        res["arms"][gid] = {
            "E0": {"passed": bool(e0), "config_id": po.get("config_id"), "expected": cid,
                   "ltt_commits": po.get("ltt_commits"), "ltt_wrong": po.get("ltt_wrong")},
            "E1": {k2: c[k2] for k2 in ("verdict", "p_user", "p_leak", "real_commits", "real_threshold",
                                        "nw_commits_median", "np_commits_median", "nw_commits_max", "np_commits_max",
                                        "n_items", "n_users", "n_runs")},
            "E1_full_recipe_nulls": {k2: pgc[gid]["nulls"][k2] for k2 in ("commits_median", "mwu_p_NW_gt_NP")},
            "E2": {b: ({"status": "refused", "reason": rec[b]["reason"]} if rec[b]["status"] == "refused" else
                       {"status": "guard", "config_id": rec[b]["config_id"],
                        "commit_threshold": rec[b]["commit_threshold"], "ltt_commits": rec[b]["ltt_commits"],
                        "ltt_wrong": rec[b]["ltt_wrong"], "test": rec[b]["test"],
                        "level_per_user": rec[b]["users"]["per_user"]["level_per_user"],
                        "n_min_per_user": rec[b]["users"]["per_user"]["n_min_per_user"],
                        "users_never": rec[b]["users"]["per_user"]["users_never"]})
                   for b in ("each", "all")},
            "pooled_test": rec["pooled_test"], "pooled_threshold": po["commit_threshold"],
            "warnings": po["warnings"]}
        # no single-user value in the repo: the per-user item range of the check is a per-user value
        res["arms"][gid]["E1"].pop("items_per_user", None)
        for b in ("each", "all"):
            res["arms"][gid]["E2"][b].pop("ltt_items_per_user", None)
    res["E0_all_passed"] = bool(e0_all)
    OUT.mkdir(exist_ok=True)
    save_json(res, OUT / "e2q.json")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snap", type=Path)
    ap.add_argument("--arm", choices=ARMS + ("all",), default="all")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    if a.summary:
        print(json.dumps(summary(), indent=1))
        return 0
    below_normal()
    assert a.snap and OWN in a.snap.parents, "the library copy must be under derived/p5-42"
    m = load_pgc(a.snap)
    E = m.E2Q()
    import fidetype

    log(f"library {fidetype.__file__}")
    for arm in (ARMS if a.arm == "all" else (a.arm,)):
        run_arm(m, E, arm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
