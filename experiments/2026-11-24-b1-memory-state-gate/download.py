"""Download the B1 inputs: Penn RAM FR1 (OpenNeuro ds004789, snapshot 3.1.0, CC0), 30 subjects.

The script reads the file tree of the snapshot from the OpenNeuro GraphQL API, applies the
subject rule of the plan, and downloads only the plan's file set:

* eligible: subjects with at least 3 sessions that have an ``acq-bipolar_ieeg.edf``;
* chosen: the first 30 eligible subjects ranked by
  ``sha256("fidetype-b1-2026-11-24/" + subject_id)``, with ``subject_id = "sub-<code>"``
  (this reproduces the plan's 56,790,482,460 bytes and 99 sessions);
* per chosen session (a session with a bipolar EDF): the bipolar EDF, the bipolar
  ``channels.tsv`` and ``ieeg.json``, ``events.tsv`` / ``events.json`` and the electrodes
  files (``*_electrodes.tsv``, ``*_electrodes.json``, ``*_coordsystem.json``).

The full hash order of the 74 eligible subjects is written to ``<out>/selection.json``
(local only, never committed; replacements use the next subject in this order). Files go to
``<out>/files/<path in the dataset>``. The script resumes partial files (curl -C -), retries,
checks every size against the API, checks the EDF header (header bytes + records x record
bytes = file size), writes a log and a DONE file. It stops if the free space on the target
disk would fall below ``--min-free-gb``.

    python -I download.py --out C:/Users/zhang/bci-data/raw/penn-ram-fr1

Downloaded files are untrusted data. This script never imports or runs them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

API = "https://openneuro.org/crn/graphql"
DATASET, TAG = "ds004789", "3.1.0"
SALT = "fidetype-b1-2026-11-24/"
N_CHOSEN = 30
CAP_BYTES = 60 * 10**9
PLAN_EDF_BYTES = 56_790_482_460

_EDF = re.compile(r"^(sub-[^/]+)/ses-(\d+)/ieeg/[^/]*_acq-bipolar_ieeg\.edf$")
_KEEP = re.compile(r"(_acq-bipolar_ieeg\.edf|_acq-bipolar_channels\.tsv|_acq-bipolar_ieeg\.json|"
                   r"_events\.tsv|_events\.json|_electrodes\.tsv|_electrodes\.json|_coordsystem\.json)$")


def log(msg: str, logf: Path) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    with logf.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def fetch_tree() -> list[dict]:
    q = {"query": 'query { snapshot(datasetId:"%s", tag:"%s") { files(recursive:true) '
                  "{ filename size directory urls } } }" % (DATASET, TAG)}
    req = urllib.request.Request(API, data=json.dumps(q).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode("utf-8"))
    return [f for f in d["data"]["snapshot"]["files"] if not f["directory"]]


def rank_key(subject_id: str) -> str:
    return hashlib.sha256((SALT + subject_id).encode("utf-8")).hexdigest()


def select(files: list[dict]) -> tuple[list[str], dict[str, list[int]]]:
    """Hash order of the eligible subjects and their bipolar sessions."""
    ses: dict[str, set[int]] = defaultdict(set)
    for f in files:
        m = _EDF.match(f["filename"])
        if m:
            ses[m[1]].add(int(m[2]))
    elig = [s for s in ses if len(ses[s]) >= 3]
    order = sorted(elig, key=rank_key)
    return order, {s: sorted(ses[s]) for s in order}


def file_set(files: list[dict], subjects: list[str], sessions: dict[str, list[int]]) -> list[dict]:
    want = {(s, n) for s in subjects for n in sessions[s]}
    out = []
    for f in files:
        m = re.match(r"^(sub-[^/]+)/ses-(\d+)/ieeg/", f["filename"])
        if m and (m[1], int(m[2])) in want and _KEEP.search(f["filename"]):
            out.append(f)
    return sorted(out, key=lambda f: f["filename"])


def edf_size_ok(path: Path) -> bool:
    """EDF header check: 256 + 256 * ns header bytes + n_records * record bytes == file size."""
    with path.open("rb") as fh:
        h = fh.read(256)
        hdr_bytes = int(h[184:192].decode("ascii").strip())
        n_rec = int(h[236:244].decode("ascii").strip())
        ns = int(h[252:256].decode("ascii").strip())
        fh.seek(256 + ns * 216)
        spr = [int(fh.read(8).decode("ascii").strip()) for _ in range(ns)]
    return hdr_bytes == 256 * (ns + 1) and hdr_bytes + n_rec * 2 * sum(spr) == path.stat().st_size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--retries", type=int, default=20)
    ap.add_argument("--min-free-gb", type=float, default=150.0)
    ap.add_argument("--extra", type=int, default=0, help="also fetch the next N subjects in hash order (replacements)")
    ap.add_argument("--list-only", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    logf = out / "download.log"
    files = fetch_tree()
    order, sessions = select(files)
    chosen = order[: N_CHOSEN + args.extra]
    sel = {"dataset": DATASET, "snapshot": TAG, "salt": SALT, "n_eligible": len(order),
           "order": [{"subject": s, "sessions": sessions[s]} for s in order], "chosen": chosen}
    (out / "selection.json").write_text(json.dumps(sel, indent=1), encoding="utf-8")
    todo = file_set(files, chosen, sessions)
    edf_bytes = sum(f["size"] for f in todo if f["filename"].endswith(".edf"))
    total = sum(f["size"] for f in todo)
    log(f"start: {len(order)} eligible, {len(chosen)} chosen, {sum(len(sessions[s]) for s in chosen)} sessions, "
        f"{len(todo)} files, {total / 1e9:.3f} GB (bipolar EDF {edf_bytes} bytes)", logf)
    if args.extra == 0 and edf_bytes != PLAN_EDF_BYTES:
        log(f"STOP: EDF bytes {edf_bytes} != plan {PLAN_EDF_BYTES}", logf)
        return 2
    if total > CAP_BYTES:
        log(f"STOP: {total} bytes over the 60 GB cap", logf)
        return 2
    if args.list_only:
        return 0
    root = out / "files"
    ok = True
    for f in todo:
        name, size = f["filename"], int(f["size"])
        dst = root / name
        mark = dst.with_name(dst.name + ".ok")
        if mark.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        have0 = dst.stat().st_size if dst.exists() else 0
        free = shutil.disk_usage(out).free
        if free - (size - have0) < args.min_free_gb * 1e9:
            log(f"STOP: free space {free / 1e9:.1f} GB would fall below {args.min_free_gb} GB", logf)
            return 3
        url = f["urls"][0]
        for attempt in range(1, args.retries + 1):
            have = dst.stat().st_size if dst.exists() else 0
            if have > size:
                dst.unlink()
                have = 0
            if have < size:
                log(f"get {name} ({size} bytes) attempt {attempt} from byte {have}", logf)
                subprocess.run(["curl.exe", "-sS", "-L", "--fail", "-C", "-", "--retry", "3",
                                "--speed-limit", "10000", "--speed-time", "120", "-o", str(dst), url], check=False)
            have = dst.stat().st_size if dst.exists() else 0
            if have == size:
                if name.endswith(".edf") and not edf_size_ok(dst):
                    log(f"EDF header size check failed for {name}; delete and retry", logf)
                    dst.unlink()
                else:
                    mark.write_text(str(size), encoding="utf-8")
                    log(f"ok {name} {size} bytes", logf)
                    break
            time.sleep(min(60, 5 * attempt))
        else:
            log(f"FAILED {name}", logf)
            ok = False
    if ok:
        (out / "DONE").write_text("ok\n", encoding="utf-8")
        log("all files size-checked", logf)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
