r"""P14-63 (gap 203): effect of the several-commits-per-trial rule (proposal section 7) on every entry it touches.

Decision support only. It changes no adopted scorer, card or published number. CPU only, read only on local data.

What it does:

1. Scans every committed score card (benchmark/results/**.json) and the leaderboard for trials with several
   commits (a ``multi_commit`` block, or a ``safe_wpm_v02.n_commits`` above its trial count). The benchmark
   submission format holds one action per unit, so none is expected.
2. Re-scores the three T15 arms that have per-trial commit-event logs (local, read only):
   single (P5-24 prefix guard, one commit per trial), stream (P5-27), hybrid (P5-28), under five rules:

   R7     the proposed rule (7): every commit event pays 0.5 s, every committed word 0.3 s once
   ONE    the union scored as one commit (what the adopted scorer does when a caller omits n_commits)
   REREAD every commit event pays 0.5 s + 0.3 s per word committed so far (the user re-reads the text)
   FIRST  only the first commit event of a trial counts (later commits ignored)
   REFUSE the adopted v0.2 rule 3 (one commit per trial): no value for an arm with several commits

   and gives paired trial-bootstrap differences (B = 2,000, seed 0) against R7 and hybrid - single per rule.

    C:\venvs\fidetype-rocm\Scripts\python.exe -I experiments/2026-11-24-p14-63-multi-commit-decision/analyse.py
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fidetype.benchmark.safe_wpm import (READ_S_PER_COMMIT, READ_S_PER_WORD, CorrectionRule,  # noqa: E402
                                         prefix_outcome, safe_wpm)

DER = Path("C:/Users/zhang/bci-data/derived")
OUT = Path(__file__).resolve().parent / "results.json"
B, SEED = 2000, 0
C, W = READ_S_PER_COMMIT, READ_S_PER_WORD
NO_BCI = 4.02
RULES = ("R7", "ONE", "REREAD", "FIRST")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def scan_cards() -> dict:
    rows = []
    for f in sorted((REPO / "benchmark" / "results").rglob("*.json")):
        c = json.loads(f.read_text(encoding="utf-8"))
        s2 = c.get("safe_wpm_v02") or {}
        s1 = c.get("safe_wpm") or {}
        nt = s2.get("n_trials") or s1.get("n_trials")
        mc = s2.get("multi_commit") or s1.get("multi_commit")
        several = bool(mc and mc.get("n_trials_with_several_commits")) or (
            isinstance(s2.get("n_commits"), int) and isinstance(nt, int) and s2["n_commits"] > nt)
        rows.append({"card": f.relative_to(REPO).as_posix(), "has_v02": bool(s2), "several_commits": several,
                     "n_prefix_commits": s2.get("n_prefix_commits")})
    lb = json.loads((REPO / "benchmark" / "site" / "leaderboard.json").read_text(encoding="utf-8"))
    lb_txt = json.dumps(lb)
    by_folder: dict = {}
    for r in rows:
        k = r["card"].split("/")[2]
        b = by_folder.setdefault(k, {"cards": 0, "several_commits": 0, "prefix_commits": 0})
        b["cards"] += 1
        b["several_commits"] += int(r["several_commits"])
        b["prefix_commits"] += int(bool(r["n_prefix_commits"]))
    return {"by_folder": by_folder, "n_cards": len(rows), "n_with_v02": sum(r["has_v02"] for r in rows),
            "n_with_several_commits": sum(r["several_commits"] for r in rows),
            "n_with_prefix_commits": sum(bool(r["n_prefix_commits"]) for r in rows),
            "cards_with_several_commits": [r["card"] for r in rows if r["several_commits"]],
            "leaderboard_mentions_multi_commit": ("multi_commit" in lb_txt or "wrong-stream-commit" in lb_txt)}


def durations() -> list[float]:
    p1405 = load_module("p1405run", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
    sessions = json.loads((DER / "m4-01-02-lookahead" / "sessions.json").read_text(encoding="utf-8"))
    keys = p1405.t15_keys(DER / "m4-13" / "logprobs-m4-13-long0-val_eval.npz", sessions, "val_eval")
    return p1405.t15_durations(keys)


def events(r: dict) -> list[dict]:
    """Commit events of one row (the single arm has no event list: one event if it commits)."""
    if r.get("commits") is not None:
        return list(r["commits"])
    if r["action"] == "commit":
        return [{"k_from": 0, "k_to": len(str(r["text"]).split()), "complete": bool(r["complete"])}]
    return []


def per_trial(rows: list[dict], rule: str) -> dict:
    """Per-trial credit, penalty and reading time under ``rule`` (aac-gaze-v1 constants)."""
    pen_rule = CorrectionRule()
    cr, pen, rd, cm, wrong, nev = [], [], [], [], [], []
    for r in rows:
        ev = events(r)
        y = r["truth"]
        if r["action"] != "commit" or not ev:
            cr.append(0.0), pen.append(0.0), rd.append(0.0), cm.append(False), wrong.append(False), nev.append(0)
            continue
        words = str(r["text"]).split()
        if rule == "FIRST":
            ev = ev[:1]
            text, comp = " ".join(words[:ev[0]["k_to"]]), bool(ev[0]["complete"])
        else:
            text, comp = r["text"], bool(r["complete"])
        po = prefix_outcome(text, y, comp)
        k = po["committed_words"]
        if rule in ("R7", "FIRST"):
            read = C * len(ev) + W * k
        elif rule == "ONE":
            read = C + W * k
        elif rule == "REREAD":
            read = sum(C + W * e["k_to"] for e in ev)
        else:
            raise ValueError(rule)
        ok = po["correct"]
        cr.append(float(po["credit_words"]) if ok else 0.0)
        pen.append(0.0 if ok else float(pen_rule.penalty(po["penalty_chars"])))
        rd.append(read), cm.append(True), wrong.append(not ok), nev.append(len(ev))
    return {k: np.asarray(v, float) for k, v in
            (("credit", cr), ("pen", pen), ("read", rd), ("cm", cm), ("wrong", wrong), ("nev", nev))}


def wpm(t: dict, ns: np.ndarray, w: np.ndarray | None = None) -> float:
    w = np.ones(len(ns)) if w is None else w
    return float(60.0 * (t["credit"] * w).sum() / ((ns * w).sum() + ((t["pen"] + t["read"]) * w).sum()))


def paired(ta: dict, tb: dict, ns: np.ndarray) -> dict:
    """b - a, paired multinomial trial bootstrap."""
    rng = np.random.default_rng(SEED)
    n = len(ns)
    d = []
    for _ in range(B):
        w = rng.multinomial(n, np.full(n, 1.0 / n)).astype(float)
        d.append(wpm(tb, ns, w) - wpm(ta, ns, w))
    return {"diff": wpm(tb, ns) - wpm(ta, ns), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}


def main() -> int:
    out: dict = {"task": "P14-63 (gap 203)", "constants": {"read_s_per_commit": C, "read_s_per_word": W,
                                                            "B": B, "seed": SEED, "no_bci": NO_BCI}}
    out["cards"] = scan_cards()
    ns = np.asarray(durations(), float)
    arms = {
        "single": json.loads((DER / "p5-27" / "decisions-single.json").read_text(encoding="utf-8")),
        "stream": json.loads((DER / "p5-27" / "decisions-stream.json").read_text(encoding="utf-8")),
        "hybrid": json.loads((DER / "p5-28" / "decisions-hybrid.json").read_text(encoding="utf-8")),
    }
    assert all(len(v) == len(ns) == 701 for v in arms.values())
    recorded = {"single": 4.667061076225306, "stream": 2.343539936697323, "hybrid": 4.890195222754168}
    guar = {"single": "wrong-prefix-commit", "stream": "wrong-stream-commit", "hybrid": "wrong-stream-commit"}
    tr = {a: {r: per_trial(rows, r) for r in RULES} for a, rows in arms.items()}
    res: dict = {}
    for a, rows in arms.items():
        # cross-check: the library scorer with n_commits (R7) and without it (ONE) gives the manual values
        t7 = tr[a]["R7"]
        po = [prefix_outcome(r["text"], r["truth"], bool(r["complete"])) if r["action"] == "commit" else None
              for r in rows]
        g = {"method": "ltt", "alpha": 0.05, "delta": 0.1, "n_cal": 271, "risk": guar[a]}
        kw = dict(guarantee=g, metric_version="0.2", B=0,
                  committed_words=[p["committed_words"] if p else math.nan for p in po],
                  complete=[p["complete"] if p else True for p in po],
                  penalty_chars=[p["penalty_chars"] if p else math.nan for p in po])
        cm = [p is not None for p in po]
        ok = [bool(p and p["correct"]) for p in po]
        nw = [len(r["truth"].split()) for r in rows]
        nc = [len(r["truth"]) for r in rows]
        lib7 = safe_wpm(cm, ok, nw, nc, list(ns), n_commits=[int(x) for x in t7["nev"]], **kw)
        lib1 = safe_wpm(cm, ok, nw, nc, list(ns), **kw)
        nev = t7["nev"]
        res[a] = {
            "recorded_value": recorded[a],
            "library_R7": {"value": lib7["value"], "status": lib7["status"],
                           "adopted_headline": lib7["adopted_headline"]},
            "library_without_n_commits": {"value": lib1["value"], "status": lib1["status"],
                                          "adopted_headline": lib1["adopted_headline"],
                                          "not_headline_because": lib1.get("not_headline_because")},
            "committing_trials": int(t7["cm"].sum()), "commit_events": int(nev.sum()),
            "trials_with_several_commits": int((nev > 1).sum()), "max_commits": int(nev.max()),
            "wrong_trials": int(t7["wrong"].sum()),
            "rules": {},
        }
        for r in RULES:
            t = tr[a][r]
            res[a]["rules"][r] = {"value": wpm(t, ns), "reading_min": float(t["read"].sum() / 60.0),
                                  "wrong_trials": int(t["wrong"].sum()), "right_words": int(t["credit"].sum()),
                                  "commit_events": int(t["nev"].sum())}
            if r != "R7":
                res[a]["rules"][r]["vs_R7"] = paired(t7, t, ns)
        res[a]["rules"]["REFUSE"] = {"value": None if (nev > 1).any() else wpm(t7, ns),
                                     "note": "adopted v0.2 rule 3: at most one commit per trial"}
        # fee per commit event at which the arm falls to the single-arm value / to the no-BCI reference
        base = 60.0 * t7["credit"].sum()
        fixed = ns.sum() + t7["pen"].sum() + (t7["read"] - C * nev).sum()
        for name, target in (("single_value", recorded["single"]), ("no_bci", NO_BCI)):
            c_star = (base / target - fixed) / nev.sum() if nev.sum() else None
            res[a].setdefault("break_even_s_per_event", {})[name] = c_star
    # fee per commit event (paid by both arms) at which hybrid = single
    h, s1 = tr["hybrid"]["R7"], tr["single"]["R7"]
    fh = ns.sum() + h["pen"].sum() + (h["read"] - C * h["nev"]).sum()
    fs = ns.sum() + s1["pen"].sum() + (s1["read"] - C * s1["nev"]).sum()
    ch, cs, eh, es = h["credit"].sum(), s1["credit"].sum(), h["nev"].sum(), s1["nev"].sum()
    res["break_even_fee_both_arms_s"] = float((ch * fs - cs * fh) / (cs * eh - ch * es))
    res["hybrid_minus_single"] = {r: paired(tr["single"][r], tr["hybrid"][r], ns) for r in RULES}
    res["stream_minus_single"] = {r: paired(tr["single"][r], tr["stream"][r], ns) for r in RULES}
    out["t15"] = res
    out["neural_min"] = float(ns.sum() / 60.0)
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
