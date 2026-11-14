"""M6-13 soak: evaluate the pass criteria of plan.md from the metrics files.

Writes ``results/summary.json`` and ``results/tables.md``. Reads ``metrics-trust.jsonl``,
``metrics-consumer.jsonl``, ``supervisor.jsonl`` (committed) and the local ``events.jsonl``
(full conformance check of the decision log as the consumer received it).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

WARMUP_S = 1800.0


def _jsonl(p: Path) -> list[dict[str, Any]]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _slope_per_h(t_s: list[float], y: list[float]) -> float | None:
    if len(t_s) < 3:
        return None
    return float(np.polyfit(np.asarray(t_s) / 3600.0, np.asarray(y), 1)[0])


def _f(x: Any, nd: int = 2) -> str:
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def analyze(results: Path, run_dir: Path) -> int:
    tr = _jsonl(results / "metrics-trust.jsonl")
    co = _jsonl(results / "metrics-consumer.jsonl")
    sv = _jsonl(results / "supervisor.jsonl")
    if not tr:
        print("no trust metrics")
        return 1
    # global time axis: the trust windows of all epochs, in order (t_s restarts per epoch)
    t_off, last_ep, last_t = 0.0, None, 0.0
    for r in tr:
        if last_ep is not None and r["epoch"] != last_ep:
            t_off += last_t
        r["T"] = t_off + r["t_s"]
        last_ep, last_t = r["epoch"], r["t_s"]
    t_off, last_ep, last_t = 0.0, None, 0.0
    for r in co:
        if last_ep is not None and r["epoch"] != last_ep:
            t_off += last_t
        r["T"] = t_off + r["t_s"]
        last_ep, last_t = r["epoch"], r["t_s"]
    trw = [r for r in tr if r["window_s"] > 1.0]
    post = [r for r in trw if r["T"] >= WARMUP_S]
    cpost = [r for r in co if r["T"] >= WARMUP_S and r["window_s"] > 1.0]
    finals_t = [r for r in tr if r["kind"] == "final"]
    finals_c = [r for r in co if r["kind"] == "final"]
    last_t_by_epoch: dict[int, dict] = {}
    for r in tr:
        last_t_by_epoch[r["epoch"]] = r
    last_c = co[-1] if co else {}

    emitted = sum(r["counts"]["emitted"] for r in last_t_by_epoch.values())
    exceptions = sum(r["counts"]["exceptions"] for r in last_t_by_epoch.values())
    actions: dict[str, dict[str, int]] = {}
    for r in last_t_by_epoch.values():
        for m, d in r["counts"]["actions"].items():
            for k, v in d.items():
                actions.setdefault(m, {}).setdefault(k, 0)
                actions[m][k] += v
    src_tot: dict[str, int] = {}
    for r in last_t_by_epoch.values():
        for k, v in r["source"].items():
            if isinstance(v, (int, float)):
                src_tot[k] = src_tot.get(k, 0) + v
    cc = last_c.get("counts", {})
    died = [e for e in sv if e["event"].endswith("died")]
    end = next((e for e in sv if e["event"] == "end"), None)
    bridge_starts = [e for e in sv if e["event"] == "bridge start"]
    pauses = sum(1 for e in bridge_starts if e.get("pause"))
    # a pause only happens if the bridge lived past pause-at: check the bridge exit/kill times
    ends = [e for e in sv if e["event"] in ("bridge killed", "bridge exit")]
    pause_at = (next((e for e in sv if e["event"] == "start"), {}) or {}).get("pause_at")

    # full conformance check of the received decision log
    conf: dict[str, Any] = {"checked": False}
    evp = run_dir / "events.jsonl"
    if evp.exists():
        from fidetype.conformance.profiles.fep0001 import check_events, read_events

        events, perr = read_events(evp)
        res = check_events(events, perr)
        conf = {"checked": True, "events": len(events),
                "results": {r.check_id: r.status for r in res},
                "fail_messages": {r.check_id: r.message for r in res if r.status == "fail"}}
        e2e_ev = [e["lsl"]["e2e_latency_s"] * 1e3 for e in events
                  if e.get("is_final") and isinstance((e.get("lsl") or {}).get("e2e_latency_s"), (int, float))]
        seqs = [e.get("seq") for e in events]
        # seq contiguity per epoch (a trust restart starts again at 0)
        holes, ep_max = 0, []
        prev = None
        for q in seqs:
            if prev is not None and q == 0 and prev > 0:
                ep_max.append(prev)
            elif prev is not None and q != prev + 1:
                holes += 1
            prev = q
        if prev is not None:
            ep_max.append(prev)
        conf["seq_holes"] = holes
        conf["seq_max_per_epoch"] = ep_max
        if e2e_ev:
            a = np.asarray(e2e_ev)
            conf["e2e_ms_from_events"] = {"n": int(a.size), "p50": float(np.percentile(a, 50)),
                                          "p95": float(np.percentile(a, 95)), "p99": float(np.percentile(a, 99)),
                                          "max": float(a.max())}

    push_p95 = [r["push_ms"]["p95"] for r in trw if r["push_ms"]["n"]]
    eou_p95 = [r["eou_ms"]["p95"] for r in trw if r["eou_ms"]["n"]]
    rss_slope = _slope_per_h([r["T"] for r in post], [r["rss_mb"] for r in post])
    priv_slope = _slope_per_h([r["T"] for r in post], [r["private_mb"] for r in post])
    h_slope = _slope_per_h([r["T"] for r in post], [r["handles"] for r in post])
    crss_slope = _slope_per_h([r["T"] for r in cpost], [r["rss_mb"] for r in cpost])
    tp50 = [(r["T"], r["transport_ms"]["p50"]) for r in post if r["transport_ms"]["n"]]
    tp_slope = _slope_per_h([a for a, _ in tp50], [b for _, b in tp50])
    spread = max((r["clock"]["spread_s"] or 0.0) for r in trw) if trw else None
    tcs = [r["clock"]["time_correction_s"] for r in trw if r["clock"]["time_correction_s"] is not None]
    lru_ok = all(r["caches"]["shadow_lm_entries"] <= r["caches"]["shadow_lm_bound"] for r in trw)
    exact_checked = sum(r["shadow"]["exact_checked"] for r in last_t_by_epoch.values())
    exact_mm = sum(r["shadow"]["exact_mismatch"] for r in last_t_by_epoch.values())
    whole = finals_t[-1].get("whole_run_ms", {}) if finals_t else {}
    e2e_src = conf.get("e2e_ms_from_events") or whole.get("e2e") or {}
    e2e_p95_whole = e2e_src.get("p95")
    external_stop = end is None and not died
    commits = sum(d.get("COMMIT", 0) for d in actions.values())
    n_restarts = max(0, len(bridge_starts) - 1)

    crit = {
        "C1 no crash": {"pass": not died and end is not None and end.get("trust_rc") == 0 and end.get("consumer_rc") == 0
                        and exceptions == 0,
                        "value": {"died": len(died), "external_stop": external_stop,
                                  "trust_rc": end and end.get("trust_rc"),
                                  "consumer_rc": end and end.get("consumer_rc"), "exceptions": exceptions}},
        "C2 RSS slope after warm-up <= 2 MB/h (trust, consumer)": {
            # plan.md: "slope <= 2 MB/h" (growth); a falling RSS passes
            "pass": rss_slope is not None and rss_slope <= 2.0 and crss_slope is not None and crss_slope <= 2.0,
            "value": {"trust_rss_mb_per_h": rss_slope, "trust_private_mb_per_h": priv_slope,
                      "consumer_rss_mb_per_h": crss_slope, "trust_handles_per_h": h_slope}},
        "C3 push p95 < 5 ms in every window": {"pass": bool(push_p95) and max(push_p95) < 5.0,
                                               "value": {"windows": len(push_p95), "worst_p95": max(push_p95, default=None),
                                                         "whole_run": whole.get("push")}},
        "C4 end-of-utterance p95 < 50 ms in every window; e2e p95 < 100 ms (whole run)": {
            "pass": bool(eou_p95) and max(eou_p95) < 50.0 and e2e_p95_whole is not None and e2e_p95_whole < 100.0,
            "value": {"worst_eou_p95": max(eou_p95, default=None), "eou_whole": whole.get("eou"),
                      "e2e_whole": e2e_src}},
        "C5 0 invalid events": {"pass": cc.get("invalid", 1) == 0 and conf.get("checked") and not conf.get("fail_messages"),
                                "value": {"invalid_online": cc.get("invalid"), "conformance": conf.get("results"),
                                          "fail_messages": conf.get("fail_messages")}},
        "C6 0 lost events": {"pass": cc.get("lost", 1) == 0 and cc.get("dup_or_reorder", 1) == 0
                             and (cc.get("received") == emitted if end is not None else
                                  conf.get("seq_holes") == 0 and conf.get("events", 0) >= emitted),
                             "value": {"emitted": emitted, "received": cc.get("received"),
                                       "events_in_log": conf.get("events"), "seq_holes": conf.get("seq_holes"),
                                       "lost": cc.get("lost"),
                                       "dup_or_reorder": cc.get("dup_or_reorder"), "epochs": cc.get("epochs")}},
        "C7 0 COMMIT (= 0 wrong commits) on the toy decoders": {"pass": commits == 0,
                                                               "value": {"actions": actions}},
        "C8 LSL: gaps = dropouts, 0 out-of-order drops, reconnect after every restart": {
            "pass": src_tot.get("gaps") == pauses and src_tot.get("dropped_out_of_order", 1) == 0
                    and src_tot.get("reconnects") == 2 * n_restarts,
            "value": {"gaps": src_tot.get("gaps"), "dropouts": pauses, "dropped_out_of_order": src_tot.get("dropped_out_of_order"),
                      "clamped": src_tot.get("clamped"), "late_releases": src_tot.get("late_releases"),
                      "lost": src_tot.get("lost"), "reconnects": src_tot.get("reconnects"), "bridge_restarts": n_restarts}},
        "C9 clock: offset spread < 1 ms; transport p50 slope < 1 ms/h": {
            "pass": spread is not None and spread < 1e-3 and tp_slope is not None and abs(tp_slope) < 1.0,
            "value": {"spread_ms": None if spread is None else spread * 1e3, "transport_p50_ms_per_h": tp_slope,
                      "time_correction_ms_min_max": [min(tcs) * 1e3, max(tcs) * 1e3] if tcs else None}},
        "C10 bounded caches: LRU <= bound; shadow incremental == batch": {
            "pass": lru_ok and exact_checked > 0 and exact_mm == 0,
            "value": {"lru_within_bound": lru_ok, "exact_checked": exact_checked, "exact_mismatch": exact_mm}},
    }
    summary = {
        "windows_trust": len(trw), "windows_consumer": len(co), "active_h": (trw[-1]["T"] / 3600) if trw else None,
        "bridge_cycles": len(bridge_starts), "bridge_ends": len(ends), "pause_at": pause_at,
        "final_decisions": sum(r["counts"]["final"] for r in last_t_by_epoch.values()),
        "criteria": crit, "all_pass": all(c["pass"] for c in crit.values()),
        "whole_run_ms": whole, "source_totals": src_tot, "consumer_final": finals_c[-1] if finals_c else None,
        "refcharlm_entries": {"first": trw[0]["caches"]["refcharlm_entries"], "last": trw[-1]["caches"]["refcharlm_entries"]},
        "rss_mb": {"first": trw[0]["rss_mb"], "after_warmup": post[0]["rss_mb"] if post else None, "last": trw[-1]["rss_mb"],
                   "max": max(r["rss_mb"] for r in trw)},
        "idle_gc_ms": whole.get("gc"), "supervisor_end": end,
    }
    (results / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")

    # tables.md: criteria + one row per 30 min (the window closest to each half hour) + all windows in short form
    L = ["# M6-13 soak: tables (generated by analyze.py)", "",
         "| criterion | pass | value |", "|---|---|---|"]
    for k, c in crit.items():
        L.append(f"| {k} | {'PASS' if c['pass'] else 'FAIL'} | `{json.dumps(c['value'], default=str)}` |")
    L += ["", "## Over time (one window every 30 min; window = 2 min)", "",
          "| t (h) | RSS MB | private MB | handles | push p50 / p95 / max ms | EOU p95 ms | e2e p95 ms | idle GC p50 ms "
          "| transport p50 ms | clock offset us | RefCharLM entries | shadow LRU entries | finals | mode |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    marks = sorted({int(r["T"] // 1800) for r in trw})
    for m in marks:
        r = min((x for x in trw if int(x["T"] // 1800) == m), key=lambda x: abs(x["T"] - m * 1800))
        p, tc = r["push_ms"], r["clock"]["time_correction_s"]
        L.append(f"| {r['T'] / 3600:.2f} | {_f(r['rss_mb'], 1)} | {_f(r['private_mb'], 1)} | {r['handles']} | "
                 f"{_f(p['p50'])} / {_f(p['p95'])} / {_f(p['max'])} | {_f(r['eou_ms']['p95'])} | {_f(r['e2e_ms']['p95'])} | "
                 f"{_f(r['idle_gc_ms']['p50'])} | {_f(r['transport_ms']['p50'])} | {_f(None if tc is None else tc * 1e6, 1)} | "
                 f"{r['caches']['refcharlm_entries']} | {r['caches']['shadow_lm_entries']} | {r['counts']['final']} | {r['mode']} |")
    (results / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(json.dumps({k: c["pass"] for k, c in crit.items()}, indent=1))
    print("ALL PASS" if summary["all_pass"] else "NOT ALL PASS")
    return 0
