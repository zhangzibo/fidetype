"""P5-01 part R: T12 multi-day replay of drift-triggered, gated re-calibration (plan.md, part R).

    python -I replay.py           -> results/replay.json, results/permutation.json
                                     per-item decisions: C:/Users/zhang/bci-data/derived/p5-01-personal/

Reads decoded outputs of the F1 / E2 pilot (read only; no new decoding, no text field is read).
"""

from __future__ import annotations

import json
import math
import pickle
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.trust.adaptive import GuardedUpdateLoop  # noqa: E402
from fidetype.trust.drift import ConformalDriftTest, RiskDriftTest  # noqa: E402
from fidetype.utils.binomial import clopper_pearson  # noqa: E402

PILOT = Path("C:/Users/zhang/bci-data/derived/f1-e2-pilot/replay/frozen")
GATED = Path("C:/Users/zhang/bci-data/derived/f1-e2-pilot-gated/replay/frozen")
NULLS = REPO / "experiments/2026-11-16-f1-e2-selfimprove-pilot/results/rerun-gated/arms/frozen.json"
OWN = Path("C:/Users/zhang/bci-data/derived/p5-01-personal")
OUT = HERE / "results"
DAYS = list(range(8, 24))
ALPHA, DELTA, N_CHECK = 0.05, 0.1, 48
N_NULL = 20


def load_items() -> list[dict]:
    items = []
    for d in DAYS:
        with open(PILOT / f"records-S{d:02d}.pkl", "rb") as f:
            a = pickle.load(f)
        with open(GATED / f"records-S{d:02d}.pkl", "rb") as f:
            b = pickle.load(f)
        if len(a) != len(b):
            raise SystemExit(f"S{d}: item counts differ ({len(a)} vs {len(b)})")
        for i, (x, y) in enumerate(zip(a, b)):
            if x["id"] != y["id"] or not (x["score"] == y["score"]):
                raise SystemExit(f"S{d} item {i}: ids or scores differ between pilot and gated records")
            items.append({"day": d, "k": i, "id": x["id"], "score": float(x["score"]), "text_ok": bool(x["text_ok"]),
                          "right": bool(x["right"]), "known": bool(x["truth_known"]),
                          "gr": float(y["guard_risk"])})
    return items


def load_nulls() -> dict[int, dict]:
    d = json.loads(NULLS.read_text(encoding="utf-8"))
    out = {}
    for day in d["days"]:
        lam = day["lambda_session"]
        out[int(day["session"])] = {"lam": float(lam) if not isinstance(lam, str) else math.inf,
                                    "k_shuffled": int(day["null_raw"]["shuffled"]),
                                    "uniform_gr_min": float(day["uniform_guard_risk_min"])}
    return out


NULL_INFO: dict[int, dict] = {}


def proxy_nulls(lam: float, days: set[int]) -> tuple[list, list]:
    """Proxy null inputs (plan.md): uniform at the measured uniform guard risk; shuffled by monotonicity."""
    info = [NULL_INFO[d] for d in sorted(days)]
    ugr = min(i["uniform_gr_min"] for i in info)
    uniform = [(1.0, "x", ugr)] * N_NULL
    if all(lam >= i["lam"] for i in info):
        k = max(i["k_shuffled"] for i in info)
    else:
        k = N_NULL  # unknown below the measured threshold: count as all commit (fails)
    shuffled = [(1.0, "x", 0.0)] * k + [(-math.inf, "x", 0.0)] * (N_NULL - k)
    return uniform, shuffled


def txt(it: dict) -> str:
    return "x" if it["text_ok"] else ""


class Arm:
    def __init__(self, name: str, *, daily: bool = False, drift: bool = False, guard_test: bool = False) -> None:
        self.name, self.daily, self.drift, self.guard_test = name, daily, drift, guard_test
        self.loop = GuardedUpdateLoop(alpha=ALPHA, delta=DELTA, n_check=N_CHECK)
        self.collect: list[dict] | None = []  # open check block (None: none open)
        self.collect_reason = "initial"
        self.offer_only_collect = True  # the initial / daily block: offer-only while collecting
        self.tightened = False
        self.tests: dict = {}
        self.events: list[dict] = []
        self.labels_spent = 0
        self.n_updates = 0
        self.lambda_changes_outside = 0
        self.decisions: list[tuple] = []
        self.per_day: dict[int, dict] = {d: {"n": 0, "commits": 0, "wrong": 0, "offer_only": 0} for d in DAYS}
        self.n_props = 0
        self.ever_accepted = False

    # --- drift tests ---
    def start_tests(self, block: list[dict]) -> None:
        if not self.drift:
            return
        ls, lr = (0.0025, 0.005) if self.guard_test else (0.005, 0.005)
        self.tests = {"scores": ConformalDriftTest([b["score"] for b in block], level=ls, seed=self.n_props),
                      "risk": RiskDriftTest(ALPHA, level=lr)}
        if self.guard_test:
            self.tests["guard_risk"] = ConformalDriftTest([b["gr"] for b in block], level=0.0025, seed=self.n_props)
        self.alarm_seen = {k: False for k in self.tests}

    # --- gated update ---
    def update(self, block: list[dict], session: str) -> dict:
        lp = self.loop
        self.n_props += 1
        lp.start_session(session)
        ver = f"{self.name}-v{self.n_props}"
        lp.new_version(ver)
        champ = lp.champion if lp.champion != ver else None
        for b in block:
            lp.add_check_item(b["id"], b["score"], 0.0 if b["right"] else 1.0, text=txt(b), text_ok=b["text_ok"],
                              guard_risk=b["gr"],
                              champion=(b["score"], 0.0 if b["right"] else 1.0, b["gr"], txt(b)) if champ else None)
        lp.recalibrate()
        days = {b["day"] for b in block}
        u, s = proxy_nulls(lp.lambda_session, days)
        lp.check_null_controls(uniform=u, shuffled=s)
        rec = lp.finish_update()
        out = {"proposal": self.n_props, "session": session, "reason": self.collect_reason, "accepted": rec.accepted,
               "reasons": list(rec.reasons), "lambda": rec.lambda_session, "days": sorted(days),
               "controls": [c.to_dict() for c in rec.controls]}
        if not rec.accepted and lp.version != ver and lp.calibrated:  # rollback: the champion's own check
            u, s = proxy_nulls(lp.lambda_session, days)
            lp.check_null_controls(uniform=u, shuffled=s)
            rec2 = lp.finish_update()
            out["rollback"] = {"accepted": rec2.accepted, "reasons": list(rec2.reasons),
                               "lambda": rec2.lambda_session}
        self.n_updates += 1
        self.labels_spent += len(block)
        if rec.accepted:
            self.tightened = False
        out = json.loads(json.dumps(out, default=str).replace("Infinity", '"inf"'))
        self.events.append({"type": "update", **out})
        return {"accepted": rec.accepted}

    def step(self, it: dict, i: int) -> None:
        d = it["day"]
        pd = self.per_day[d]
        pd["n"] += 1
        lam_before = self.loop.lambda_session
        # daily arm: a new day opens a new offer-only check block
        if self.daily and (i == 0 or it["k"] == 0) and self.collect is None:
            self.collect, self.collect_reason, self.offer_only_collect = [], f"day S{d}", True
        commit, loss = False, 0.0
        offer_only = (self.collect is not None and self.offer_only_collect) or self.tightened
        if offer_only:
            pd["offer_only"] += 1
        else:
            dec = self.loop.decide(it["score"], it["text_ok"], text=txt(it), guard_risk=it["gr"])
            commit = bool(dec.commit)
            loss = (0.0 if it["right"] else 1.0) if commit else 0.0
            self.loop.observe(dec, loss if commit else None)
        if self.loop.lambda_session != lam_before and not (
                math.isinf(self.loop.lambda_session) and math.isinf(lam_before)):
            self.lambda_changes_outside += 1
        pd["commits"] += commit
        pd["wrong"] += int(commit and loss > 0)
        self.decisions.append((d, it["k"], int(commit), int(loss > 0), int(offer_only)))
        # drift tests (only while a calibrated configuration is live)
        if self.drift and self.tests and not (self.collect is not None and self.offer_only_collect):
            fired = []
            for name, t in self.tests.items():
                if name == "scores":
                    t.update(it["score"])
                elif name == "guard_risk":
                    t.update(it["gr"])
                else:
                    t.update(loss)
                if t.alarmed and not self.alarm_seen[name]:
                    self.alarm_seen[name] = True
                    fired.append(name)
            for name in fired:
                self.events.append({"type": "alarm", "test": name, "item": i, "day": d,
                                    "n_in_test": self.tests[name].n})
                if name == "risk":
                    self.tightened = True
                    self.events.append({"type": "tighten", "item": i, "day": d})
                if self.collect is None:
                    self.collect, self.collect_reason, self.offer_only_collect = [], f"{name} alarm", False
        # check block collection
        if self.collect is not None and it["known"]:
            self.collect.append(it)
            if len(self.collect) >= N_CHECK:
                block, self.collect = self.collect, None
                lam0 = self.loop.lambda_session
                r = self.update(block, f"{self.name}-s{self.n_props + 1}")
                if r["accepted"] or self.loop.lambda_session != lam0:
                    self.start_tests(block)
                if r["accepted"]:
                    self.ever_accepted = True
                elif not self.daily and (self.drift or not self.ever_accepted):
                    # the proposal stays open: collect the next 48 labelled items (offer-only if nothing is live)
                    self.collect, self.offer_only_collect = [], not self.ever_accepted

    def result(self, n_items: int) -> dict:
        com = sum(p["commits"] for p in self.per_day.values())
        wr = sum(p["wrong"] for p in self.per_day.values())
        rates = {d: (p["wrong"] / p["n"] if p["n"] else 0.0) for d, p in self.per_day.items()}
        ups = [e for e in self.events if e["type"] == "update"]
        return {"arm": self.name, "n_items": n_items, "commits": com, "wrong_commits": wr,
                "wrong_commit_rate": wr / n_items, "cp95": clopper_pearson(wr, n_items),
                "days_rate_above_alpha": sum(r > ALPHA for r in rates.values()),
                "max_day_rate": max(rates.values()), "labels_spent_check_blocks": self.labels_spent,
                "proposals": len(ups), "accepted": sum(e["accepted"] for e in ups),
                "rejected": sum(not e["accepted"] for e in ups),
                "offer_only_items": sum(p["offer_only"] for p in self.per_day.values()),
                "loop_monitor_alarms": self.loop.n_alarms,
                "lambda_changes_outside_finish_update": self.lambda_changes_outside,
                "alarms": [e for e in self.events if e["type"] == "alarm"],
                "tightenings": sum(e["type"] == "tighten" for e in self.events),
                "updates": ups, "per_day": {f"S{d}": p for d, p in self.per_day.items()},
                "aci": self.loop.aci.report()}


def run_arms(items: list[dict]) -> dict:
    arms = [Arm("A0-static"), Arm("A1-daily", daily=True), Arm("A2-drift", drift=True),
            Arm("A2g-drift-guard", drift=True, guard_test=True)]
    for a in arms:
        a.collect = [] if not a.daily else None
        for i, it in enumerate(items):
            a.step(it, i)
    OWN.mkdir(parents=True, exist_ok=True)
    for a in arms:  # per-item decisions: derived folder only
        np.save(OWN / f"decisions-{a.name}.npy", np.asarray(a.decisions, dtype=np.int32))
    return {a.name: a.result(len(items)) for a in arms}


def permutation_null(items: list[dict], a0_lambda: float, runs: int = 200) -> dict:
    sc = np.asarray([it["score"] for it in items])
    gate_ok = np.asarray([it["text_ok"] and it["gr"] < 1.0 for it in items])
    commit = gate_ok & (sc >= a0_lambda)
    loss = (commit & ~np.asarray([it["right"] for it in items])).astype(float)
    a_s = a_r = 0
    for r in range(runs):
        perm = np.random.default_rng(r).permutation(len(items))
        s = sc[perm]
        t = ConformalDriftTest(s[:N_CHECK], level=0.05, seed=r)
        t.update_many(s[N_CHECK:])
        a_s += t.alarmed
        a_r += RiskDriftTest(ALPHA, level=0.05).update_many(loss[perm]).alarmed
    lim = 0.05 + 3 * math.sqrt(0.05 * 0.95 / runs)
    return {"runs": runs, "score_alarm_rate": a_s / runs, "risk_alarm_rate": a_r / runs, "limit": lim,
            "pooled_loss_rate": float(loss.mean()), "a0_lambda": a0_lambda,
            "R2_pass": a_s / runs <= lim and a_r / runs <= lim}


def main() -> None:
    t0 = time.time()
    OUT.mkdir(exist_ok=True)
    items = load_items()
    NULL_INFO.update(load_nulls())
    res = run_arms(items)
    a0 = res["A0-static"]
    lam0 = next((u["lambda"] for u in a0["updates"] if u["accepted"]), math.inf)
    lam0 = float(lam0) if not isinstance(lam0, str) else math.inf
    perm = permutation_null(items, lam0)
    a1, a2, a2g = res["A1-daily"], res["A2-drift"], res["A2g-drift-guard"]
    crit = {
        "R1": a2["wrong_commit_rate"] <= ALPHA,
        "R2": perm["R2_pass"],
        "R3": a2["labels_spent_check_blocks"] < a1["labels_spent_check_blocks"],
        "R4": a2["days_rate_above_alpha"] <= a0["days_rate_above_alpha"],
        "R5": all(r["lambda_changes_outside_finish_update"] == 0 for r in (a2, a2g)),
    }
    summary = {"n_items": len(items), "days": [f"S{d}" for d in DAYS],
               "n_known": sum(it["known"] for it in items), "n_right": sum(it["right"] for it in items),
               "criteria": crit, "seconds": round(time.time() - t0, 1)}
    (OUT / "replay.json").write_text(json.dumps({"summary": summary, "arms": res}, indent=1, default=str) + "\n",
                                     encoding="utf-8")
    (OUT / "permutation.json").write_text(json.dumps(perm, indent=1) + "\n", encoding="utf-8")
    for k, r in res.items():
        print(k, r["commits"], r["wrong_commits"], round(r["wrong_commit_rate"], 5), r["cp95"],
              "days>a", r["days_rate_above_alpha"], "labels", r["labels_spent_check_blocks"],
              "props", r["proposals"], r["accepted"], "alarms", [(x["test"], x["day"]) for x in r["alarms"]],
              "offer-only", r["offer_only_items"], flush=True)
    print("perm", perm)
    print("criteria", crit, "seconds", summary["seconds"])


if __name__ == "__main__":
    main()
