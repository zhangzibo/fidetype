"""Print the QC summary of the SpanishBCBL cache as markdown.

Usage: python summarize_cache.py [<cache root>]

It reads only the sidecars (.json) and _index.json. It reads no MEG data, and
it prints no participant data beyond counts and QC numbers.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

CACHE = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\zhang\bci-data\cache\spanishbcbl\v1")


def main() -> None:
    sides = []
    for js in sorted(CACHE.glob("S*/*.json")):
        sides.append(json.loads(js.read_text(encoding="utf-8")))
    by_subj = defaultdict(list)
    for d in sides:
        by_subj[d["subject"]].append(d)

    print(f"Blocks cached: {len(sides)}. Subjects: {len(by_subj)}.\n")
    print("| Subject | Participant | Blocks | Trials (test) | Keys | Key match | Resid median (ms) | Resid p95 max (ms) | Bad channels (per block) | 23 Hz before -> after (dB) | Time per block (s) | Peak RAM (GB) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for subj in sorted(by_subj, key=lambda s: int(s[1:])):
        ds = sorted(by_subj[subj], key=lambda d: (d["session"], d["block"]))
        segs = [s for d in ds for s in d["segments"]]
        al = [d["qc"]["alignment"] for d in ds]
        nk = sum(a["n_keys"] for a in al)
        km = sum(a["key_matched_fraction"] * a["n_keys"] for a in al) / max(nk, 1)
        bads = ", ".join(str(len(d["qc"]["bad_channels"])) for d in ds)
        b23 = [d["qc"].get("peak_23hz_before", {}).get("prominence_db", np.nan) for d in ds]
        a23 = [d["qc"].get("peak_23hz_after", {}).get("prominence_db", np.nan) for d in ds]
        tt = [sum(d["qc"].get("timings_s", {}).values()) for d in ds]
        mem = [d["qc"].get("peak_memory_gb") or np.nan for d in ds]
        print(
            f"| {subj} | {ds[0]['participant']} | {len(ds)} | {len(segs)} ({sum(not s['is_training'] for s in segs)}) | {nk} "
            f"| {km:.4f} | {np.median([a['resid_ms_median'] for a in al]):.2f} | {max(a['resid_ms_p95'] for a in al):.2f} "
            f"| {bads} | {np.nanmedian(b23):.1f} -> {np.nanmedian(a23):.1f} | {np.median(tt):.0f} | {np.nanmax(mem):.1f} |"
        )

    print("\nPer block:\n")
    print("| Block | Duration (s) | Segments | Key match | Resid p95 (ms) | Bads | 23 Hz before/after (dB) | tSSS (s) | Total (s) | Log |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for d in sorted(sides, key=lambda d: (int(d["subject"][1:]), d["session"], d["block"])):
        a = d["qc"]["alignment"]
        t = d["qc"].get("timings_s", {})
        print(
            f"| {d['subject']}/{d['session']}_{d['block']} | {d['source']['duration_s']:.0f} | {len(d['segments'])} "
            f"| {a['key_matched_fraction']:.4f} | {a['resid_ms_p95']:.2f} | {', '.join(d['qc']['bad_channels']) or '-'} "
            f"| {d['qc'].get('peak_23hz_before', {}).get('prominence_db', float('nan')):.1f} / "
            f"{d['qc'].get('peak_23hz_after', {}).get('prominence_db', float('nan')):.1f} "
            f"| {t.get('tsss', 0):.0f} | {sum(t.values()):.0f} | {Path(d['source']['log']).name}{' (reassigned)' if d['qc'].get('log_reassigned') else ''} |"
        )

    # Splits
    trials = defaultdict(int)
    sents = defaultdict(set)
    test_trials = defaultdict(int)
    typed_eq = 0
    for d in sides:
        for s in d["segments"]:
            trials[s["split"]] += 1
            sents[s["split"]].add(s["target_text"])
            test_trials[s["split"]] += not s["is_training"]
            typed_eq += s["typed_text"] == s["target_text"]
    allsent = set().union(*sents.values()) if sents else set()
    print(f"\nUnique sentences: {len(allsent)}. Trials: {sum(trials.values())}. Typed text equals target: {typed_eq}.\n")
    print("| Split | Unique sentences | Trials | Test trials (no training) |")
    print("|---|---|---|---|")
    for k in ("train", "val", "test"):
        print(f"| {k} | {len(sents[k])} | {trials[k]} | {test_trials[k]} |")


if __name__ == "__main__":
    main()
