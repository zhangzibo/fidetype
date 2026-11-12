"""R1 item 6: CRC / LTT with small calibration sets (domain M9; methods Major 4, Minor 6).

Analysis only (CPU, < 2 min): it reuses committed per-item tables.

Protocols, n_cal in {20, 50, 100} (+ the paper's size as a reference):

- ``random``: random calibration / test splits inside one test pool
  (exchangeable by construction; the M2-13 protocol). B2T ours / published
  (M2-13 items), sEMG calib / xsession / xsubject (M2-16 items), MEG async (G1
  items). 500 splits. For LTT the realised test rate on the complement is the
  estimate of the calibration-conditional risk R(lambda_hat); we report its
  90th percentile (delta = 0.1) and the share of splits above alpha.
- ``deploy``: n_cal items drawn from the clean calibration pool, applied to the
  whole test half (B2T: fit-B of the ``alternate`` split; sEMG: fit-B2).
  Items from ``clean-drift``. 500 draws.
- ``per_session``: B2T: per post-implant day, calibrate on the first n_cal
  trials of the day's sequence fit-B (file order) + test, test on the rest of
  that day's test trials; pooled over days. sEMG: per participant, calibrate on
  the first n_cal test sentences, test on the rest. Only n_cal 20 and 30 fit
  in a day / participant.

Metrics: mean, p90, p95 of the test wrong-commit, share > alpha, commit rate,
error among commits (pooled over splits), share of splits that never commit,
mean eWPM.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r1-analyses/smallcal/run.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common as C  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
R = C.REPO / "experiments"
CLEAN = HERE.parent / "clean-drift" / "results"


class Tab:
    def __init__(self, d: dict):
        self.s = np.array([C.fnum(x) for x in d["score"]])
        for k in ("loss_c", "loss_f", "wc_c", "wc_f", "time_c", "time_f", "words_c", "words_f"):
            setattr(self, k, np.asarray(d[k], float))
        self.n = self.s.size

    def lam(self, idx, method: str) -> float:
        if method == "crc":
            return C.crc_threshold(self.s[idx], self.loss_c[idx], C.ALPHA, self.loss_f[idx]).threshold
        return C.ltt_threshold(self.s[idx], self.loss_c[idx], C.ALPHA, C.DELTA, self.loss_f[idx]).threshold

    def out(self, idx, lam: float) -> tuple:
        on = self.s[idx] >= lam
        wc = np.where(on, self.wc_c[idx], self.wc_f[idx])
        return (float(wc.mean()), float(on.mean()), float((wc * on).sum()), float(on.sum()),
                float(np.where(on, self.words_c[idx], self.words_f[idx]).sum()), float(np.where(on, self.time_c[idx], self.time_f[idx]).sum()))


def summ(rows: list[tuple]) -> dict:
    r = np.array(rows)
    return {"wrong_commit_mean": float(r[:, 0].mean()), "wrong_commit_p90": float(np.quantile(r[:, 0], 0.9)),
            "wrong_commit_p95": float(np.quantile(r[:, 0], 0.95)), "share_gt_alpha": float(np.mean(r[:, 0] > C.ALPHA + 1e-12)),
            "commit_rate_mean": float(r[:, 1].mean()),
            "error_among_commits_pooled": float(r[:, 2].sum() / r[:, 3].sum()) if r[:, 3].sum() > 0 else None,
            "share_never_commit": float(np.mean(r[:, 3] == 0)), "ewpm_mean": float(np.mean(60 * r[:, 4] / r[:, 5])),
            "n_splits": int(len(r))}


def random_splits(tab: Tab, n_cals, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    out = {}
    for n_cal in n_cals:
        if n_cal >= tab.n:
            continue
        rows = {"crc": [], "ltt": []}
        for _ in range(reps):
            perm = rng.permutation(tab.n)
            cal, tst = perm[:n_cal], perm[n_cal:]
            for m in rows:
                rows[m].append(tab.out(tst, tab.lam(cal, m)))
        out[str(n_cal)] = {m: summ(v) for m, v in rows.items()}
    return out


def deploy(cal: Tab, test: Tab, n_cals, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    allt = np.arange(test.n)
    out = {}
    for n_cal in n_cals:
        if n_cal > cal.n:
            continue
        rows = {"crc": [], "ltt": []}
        for _ in range(reps):
            idx = rng.choice(cal.n, n_cal, replace=False)
            for m in rows:
                rows[m].append(test.out(allt, cal.lam(idx, m)))
        out[str(n_cal)] = {m: summ(v) for m, v in rows.items()}
    full = {m: test.out(allt, cal.lam(np.arange(cal.n), m)) for m in ("crc", "ltt")}
    out[f"all {cal.n}"] = {m: summ([v]) for m, v in full.items()}
    return out


def per_session_b2t(cal: Tab, test: Tab, days_cal, days_test, n_cals) -> dict:
    """Per day: sequence = that day's fit-B items then its test items (file order)."""
    out = {}
    days_cal, days_test = np.asarray(days_cal), np.asarray(days_test)
    for n_cal in n_cals:
        agg = {"crc": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "ltt": [0.0] * 6}
        n_days = 0
        never = {"crc": 0, "ltt": 0}
        for d in sorted(set(days_test.tolist())):
            ic, it = np.where(days_cal == d)[0], np.where(days_test == d)[0]
            seq = [("c", i) for i in ic] + [("t", i) for i in it]
            if len(seq) <= n_cal or len(it) == 0:
                continue
            head, tail = seq[:n_cal], seq[n_cal:]
            tail_t = np.array([i for w, i in tail if w == "t"])
            if tail_t.size == 0:
                continue
            n_days += 1
            # Calibration scores: pool the two item tables (same fitted pipeline).
            s = np.r_[cal.s[[i for w, i in head if w == "c"]], test.s[[i for w, i in head if w == "t"]]]
            c = np.r_[cal.loss_c[[i for w, i in head if w == "c"]], test.loss_c[[i for w, i in head if w == "t"]]]
            f = np.r_[cal.loss_f[[i for w, i in head if w == "c"]], test.loss_f[[i for w, i in head if w == "t"]]]
            lams = {"crc": C.crc_threshold(s, c, C.ALPHA, f).threshold, "ltt": C.ltt_threshold(s, c, C.ALPHA, C.DELTA, f).threshold}
            for m, l in lams.items():
                o = test.out(tail_t, l)
                n = tail_t.size
                agg[m] = [agg[m][0] + o[0] * n, agg[m][1] + o[1] * n, agg[m][2] + o[2], agg[m][3] + o[3], agg[m][4] + o[4], agg[m][5] + o[5]]
                never[m] += int(o[3] == 0)
            agg.setdefault("n", 0)
            agg["n"] = agg.get("n", 0) + tail_t.size
        n = agg.pop("n", 0)
        out[str(n_cal)] = {m: {"wrong_commit_pooled": v[0] / n if n else None, "commit_rate_pooled": v[1] / n if n else None,
                               "error_among_commits_pooled": v[2] / v[3] if v[3] else None, "ewpm_pooled": 60 * v[4] / v[5] if v[5] else None,
                               "n_days": n_days, "n_test_items": n, "days_never_commit": never[m]} for m, v in agg.items()}
    return out


def per_session_emg(test: Tab, who, n_cals) -> dict:
    who = np.asarray(who)
    out = {}
    for n_cal in n_cals:
        tot = {"crc": np.zeros(6), "ltt": np.zeros(6)}
        never = {"crc": 0, "ltt": 0}
        n_all = 0
        n_p = 0
        for p in sorted(set(who.tolist())):
            idx = np.where(who == p)[0]
            if idx.size <= n_cal:
                continue
            n_p += 1
            cal, tst = idx[:n_cal], idx[n_cal:]
            for m in tot:
                o = test.out(tst, test.lam(cal, m))
                tot[m] += np.array([o[0] * tst.size, o[1] * tst.size, o[2], o[3], o[4], o[5]])
                never[m] += int(o[3] == 0)
            n_all += tst.size
        out[str(n_cal)] = {m: {"wrong_commit_pooled": v[0] / n_all, "commit_rate_pooled": v[1] / n_all,
                               "error_among_commits_pooled": v[2] / v[3] if v[3] else None, "ewpm_pooled": 60 * v[4] / v[5],
                               "n_participants": n_p, "n_test_items": n_all, "participants_never_commit": never[m]} for m, v in tot.items()}
    return out


def main() -> None:
    n_cals = CONFIG["n_cal"]
    reps = CONFIG["reps"]
    res: dict = {"config": CONFIG, "random": {}, "deploy": {}, "per_session": {}}
    pools = {
        "b2t-ours": R / "2026-11-11-m2-13-conformal/results/items-b2t-ours.json",
        "b2t-published": R / "2026-11-11-m2-13-conformal/results/items-b2t-published.json",
        "emg-calib": R / "2026-11-11-m2-16-online-recal/results/items-emg-calib.json",
        "emg-xsession": R / "2026-11-11-m2-16-online-recal/results/items-emg-xsession.json",
        "emg-xsubject": R / "2026-11-11-m2-16-online-recal/results/items-emg-xsubject.json",
        "meg-async": R / "2026-11-11-g1-async-meg-trust/results/items-meg-async.json",
    }
    ref = {"b2t-ours": 408, "b2t-published": 408, "emg-calib": 275, "emg-xsession": 275, "emg-xsubject": 275, "meg-async": 408}
    for name, p in pools.items():
        d = json.loads(p.read_text(encoding="utf-8"))
        res["random"][name] = random_splits(Tab(d["test"]), list(n_cals) + [ref[name]], reps, CONFIG["seed"])
    for name, fn in (("b2t-ours", "items-ours-alternate.json"), ("b2t-published", "items-published-alternate.json"),
                     ("emg-calib", "items-emg-calib.json"), ("emg-xsession", "items-emg-xsession.json"),
                     ("emg-xsubject", "items-emg-xsubject.json")):
        d = json.loads((CLEAN / fn).read_text(encoding="utf-8"))
        cal, test = Tab(d["items_cal"]), Tab(d["items_test"])
        res["deploy"][name] = deploy(cal, test, n_cals, reps, CONFIG["seed"] + 1)
        if name.startswith("b2t"):
            res["per_session"][name] = per_session_b2t(cal, test, d["days_cal"], d["days_test"], CONFIG["per_session_n_cal"])
        else:
            res["per_session"][name] = per_session_emg(test, d["participants_test"], CONFIG["per_session_n_cal"])
    C.dump(res, OUT / "smallcal.json")
    tables(res)


def tables(res: dict) -> None:
    f = C.fmt
    L = ["# Small calibration sets: generated tables", "",
         "Random = splits inside one test pool (exchangeable). Deploy = n_cal clean calibration items -> whole test half. "
         "EAC = error among commits (pooled over splits). Never = share of splits (days / participants) with no commit.", ""]
    for proto in ("random", "deploy"):
        L += [f"## {proto}", "", "| condition | n_cal | method | wrong-commit mean | p90 | p95 | share > α | commit rate | EAC | never | eWPM |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for name, d in res[proto].items():
            for n_cal, mm in d.items():
                for m, v in mm.items():
                    L.append(f"| {name} | {n_cal} | {m.upper()} | {f(v['wrong_commit_mean'], 4)} | {f(v['wrong_commit_p90'], 4)} | "
                             f"{f(v['wrong_commit_p95'], 4)} | {f(v['share_gt_alpha'], 2)} | {f(v['commit_rate_mean'])} | "
                             f"{f(v['error_among_commits_pooled'])} | {f(v['share_never_commit'], 2)} | {f(v['ewpm_mean'], 2)} |")
        L.append("")
    L += ["## per session (B2T: per day; sEMG: per participant)", "",
          "| condition | n_cal | method | wrong-commit (pooled) | commit rate | EAC | eWPM | sessions | sessions with no commit |", "|---|---|---|---|---|---|---|---|---|"]
    for name, d in res["per_session"].items():
        for n_cal, mm in d.items():
            for m, v in mm.items():
                ns = v.get("n_days", v.get("n_participants"))
                nn = v.get("days_never_commit", v.get("participants_never_commit"))
                L.append(f"| {name} | {n_cal} | {m.upper()} | {f(v['wrong_commit_pooled'], 4)} | {f(v['commit_rate_pooled'])} | "
                         f"{f(v['error_among_commits_pooled'])} | {f(v['ewpm_pooled'], 2)} | {ns} | {nn} |")
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
