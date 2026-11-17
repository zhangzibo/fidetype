"""P5-10: the T12 replay of P5-01 again, plus arms that run the alarm path through PersonalTrust (plan-p5-10.md).

    .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
        .venv\\Scripts\\python.exe -I experiments/2026-11-16-p5-01-personal/replay_p5_10.py
    -> results/replay-p5-10.json (aggregates only). Nothing is written to the P5-01 derived folder.

Part 1 re-runs the four P5-01 arms with the unchanged code of replay.py and compares them with results/replay.json.
Part 2 feeds the same items through ``PersonalTrust`` (``guard_risk_test=True`` and the default), segment by segment:
a new controller starts wherever the P5-01 arm started new drift tests (after an accepted update), with the same
reference block, the same seed and the same levels. The guard is a stub that replays the recorded decision of the
arm; the replay has no decoder inputs, so PersonalTrust re-calibration itself is not run here (unit tests cover it).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import importlib.util  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.trust.personal import PersonalTrust, UserProfile  # noqa: E402

spec = importlib.util.spec_from_file_location("p5_01_replay", HERE / "replay.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
R.OWN = Path("C:/Users/zhang/bci-data/derived/p5-10-personal-guard-risk")  # never the P5-01 folder
OUT = HERE / "results"


class TArm(R.Arm):
    """The P5-01 arm, unchanged, plus a trace: where drift tests start, and which items update them."""

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        self.cur = -1
        self.starts: list[dict] = []
        self.fed: list[int] = []

    def start_tests(self, block):
        if self.drift:
            self.starts.append({"after_item": self.cur, "seed": self.n_props, "block": list(block)})
        super().start_tests(block)

    def step(self, it, i):
        self.cur = i
        if self.drift and self.tests and not (self.collect is not None and self.offer_only_collect):
            self.fed.append(i)
        super().step(it, i)


class StubResult:
    def __init__(self, seq: int, it: dict, commit: bool) -> None:
        self.seq, self.p_top1, self.guard_risk = seq, it["score"], it["gr"]
        self.action, self.text = ("commit", "x") if commit else ("offer", None)


class StubGuard:
    """Replays the recorded decision of the P5-01 arm for each item (no decoder inputs in this replay)."""

    alpha, delta = R.ALPHA, R.DELTA

    def __init__(self, cid: str) -> None:
        self.config_id, self.seq = cid, 0

    def decide(self, x, utterance_id=None):
        self.seq += 1
        it, commit = x
        return StubResult(self.seq, it, commit)


class StubUpdater:
    def __init__(self, guard) -> None:
        self.guard = guard
        self.loop = type("L", (), {"n_check": R.N_CHECK})()


def personal_arm(name: str, items: list[dict], arm: TArm, *, guard_risk: bool, spread: bool) -> dict:
    """Run PersonalTrust over the items the P5-01 arm fed to its drift tests, one controller per segment."""
    commits = {i: bool(d[2]) for i, d in enumerate(arm.decisions)}
    fed = set(arm.fed)
    ls, lr = (0.0025, 0.005) if guard_risk else (0.005, 0.005)
    alarms, history = [], []
    for k, st in enumerate(arm.starts):
        end = arm.starts[k + 1]["after_item"] if k + 1 < len(arm.starts) else len(items) - 1
        block = st["block"]
        prof = UserProfile.new(f"t12-{name}-{k}", None, calibration={
            "reference_scores": [b["score"] for b in block], "reference_guard_risk": [b["gr"] for b in block]})
        g = StubGuard(f"segment-{k}")
        pt = PersonalTrust(prof, g, updater=StubUpdater(g), level_scores=ls, level_risk=lr, seed=st["seed"],
                           guard_risk_test=guard_risk, level_guard_risk=0.0025, spread=spread)
        seen = {"scores": False, "risk": False, "guard_risk": False}
        for i in range(st["after_item"] + 1, end + 1):
            if i not in fed:
                continue
            it = items[i]
            r = pt.decide((it, commits[i]))
            truth = ("x" if it["right"] else "y") if commits[i] else None
            pt.feedback(r, truth)
            tests = {"scores": pt.monitor.scores, "risk": pt.monitor.risk, "guard_risk": pt.guard_risk_test}
            for tname, t in tests.items():
                if t is not None and t.alarmed and not seen[tname]:
                    seen[tname] = True
                    alarms.append({"test": tname, "item": i, "day": it["day"], "segment": k, "n_in_test": t.n})
        history += [{"segment": k, **{kk: h[kk] for kk in ("event", "test", "action") if kk in h}}
                    for h in pt.profile.history if h["event"] != "calibrate"]
    return {"arm": name, "guard_risk_test": guard_risk, "spread": spread, "segments": len(arm.starts),
            "items_fed": len(fed), "alarms": alarms, "history": history}


KEYS = ("commits", "wrong_commits", "labels_spent_check_blocks", "proposals", "accepted", "offer_only_items",
        "days_rate_above_alpha", "tightenings", "lambda_changes_outside_finish_update")


def main() -> None:
    t0 = time.time()
    OUT.mkdir(exist_ok=True)
    items = R.load_items()
    R.NULL_INFO.update(R.load_nulls())
    arms = [TArm("A0-static"), TArm("A1-daily", daily=True), TArm("A2-drift", drift=True),
            TArm("A2g-drift-guard", drift=True, guard_test=True)]
    for a in arms:
        a.collect = [] if not a.daily else None
        for i, it in enumerate(items):
            a.step(it, i)
    res = {a.name: a.result(len(items)) for a in arms}
    old = json.loads((OUT / "replay.json").read_text(encoding="utf-8"))["arms"]
    repro = {}
    for k, r in res.items():
        diff = {f: (old[k][f], r[f]) for f in KEYS if old[k][f] != r[f]}
        oa = [(x["test"], x["item"]) for x in old[k]["alarms"]]
        na = [(x["test"], x["item"]) for x in r["alarms"]]
        if oa != na:
            diff["alarms"] = (oa, na)
        repro[k] = {"identical": not diff, "diff": diff, **{f: r[f] for f in KEYS},
                    "alarms": na}
    a2, a2g = arms[2], arms[3]
    pers = {
        "A2p-personal-guard-risk": personal_arm("A2p", items, a2g, guard_risk=True, spread=False),
        "A2d-personal-default": personal_arm("A2d", items, a2, guard_risk=False, spread=False),
        "A2ps-personal-default-spread": personal_arm("A2ps", items, a2, guard_risk=False, spread=True),
        "A2gs-personal-guard-risk-spread": personal_arm("A2gs", items, a2g, guard_risk=True, spread=True),
    }
    a2g_alarms = [(x["test"], x["item"]) for x in res["A2g-drift-guard"]["alarms"]]
    a2_alarms = [(x["test"], x["item"]) for x in res["A2-drift"]["alarms"]]
    crit = {
        "P10-1_reproduces_p5_01": all(v["identical"] for v in repro.values()),
        "P10-2_guard_risk_alarms_through_personaltrust": [(x["test"], x["item"]) for x in
                                                          pers["A2p-personal-guard-risk"]["alarms"]] == a2g_alarms,
        "P10-2_history_records_each_alarm": sum(h["event"] == "drift_alarm" for h in
                                                pers["A2p-personal-guard-risk"]["history"]) == len(a2g_alarms),
        "P10-3_default_matches_a2": [(x["test"], x["item"]) for x in
                                     pers["A2d-personal-default"]["alarms"]] == a2_alarms,
    }
    out = {"plan": "experiments/2026-11-16-p5-01-personal/plan-p5-10.md", "n_items": len(items),
           "reproduction": repro, "personal_arms": pers, "criteria": crit, "seconds": round(time.time() - t0, 1)}
    (OUT / "replay-p5-10.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
    for k, v in repro.items():
        print(k, "identical" if v["identical"] else v["diff"], flush=True)
    for k, v in pers.items():
        print(k, [(x["test"], x["item"], x["day"]) for x in v["alarms"]], flush=True)
    print("criteria", crit, "seconds", out["seconds"])


if __name__ == "__main__":
    main()
