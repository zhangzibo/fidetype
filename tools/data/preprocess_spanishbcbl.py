"""Preprocess all complete SpanishBCBL subjects into the block cache.

Usage (GPU env or ``uv run``):

    python tools/data/preprocess_spanishbcbl.py [--subjects S25,S3] [--workers 3]
        [--preset default|v1] [--root DIR] [--cache DIR] [--force] [--dry-run]

The job is idempotent and resumable. It skips a block when its sidecar exists
with the same config version. It writes each block atomically (the sidecar is
written last), so a killed run loses at most the blocks in progress. Rerun the
same command to continue, for example after the download finishes.

It processes only subjects whose .fif files are all complete (local size =
size in ``_filelist.tsv``). It never touches the ``_download*`` files.

Log: ``<cache>/_preprocess.log``. Index: ``<cache>/_index.json``. Excluded
files: ``<cache>/_excluded.json``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

from fidetype.data import preprocess as pp
from fidetype.data import spanishbcbl as sb

DEFAULT_ROOT = Path(r"C:\Users\zhang\bci-data\SpanishBCBL")
#: Estimated peak RAM of one block = MEM_FACTOR * size of its .fif files + MEM_BASE_GB.
MEM_FACTOR = 5.5  # measured: 7.6 GB peak for a 1.2 GB block
MEM_BASE_GB = 1.0

DEFAULT_CACHE = {
    "default": Path(r"C:\Users\zhang\bci-data\cache\spanishbcbl\v1"),
    "v1": Path(r"C:\Users\zhang\bci-data\cache\spanishbcbl\v1-b2q1band"),
}


def _worker(spec_dict: dict, root: str, cache: str, preset: str, dest_trans) -> dict:
    """Run one block in a child process. Never raises."""
    t0 = time.time()
    try:
        from mne.transforms import Transform

        spec = sb.BlockSpec(**spec_dict)
        dest = Transform("meg", "head", dest_trans) if dest_trans is not None else None
        res = pp.process_block(spec, root, cache, pp.get_config(preset), dest)
        res["ok"] = True
    except Exception as exc:  # noqa: BLE001
        res = {"key": spec_dict.get("subject", "?") + "/" + spec_dict.get("session", "?") + "_" + spec_dict.get("block", "?"),
               "ok": False, "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()}
    res["elapsed_s"] = round(time.time() - t0, 1)
    return res


def free_ram_gb() -> float | None:
    """Free physical memory in GB (Windows only, else None)."""
    if os.name != "nt":
        return None
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [
            (n, ctypes.c_ulonglong)
            for n in ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
                      "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")
        ]

    ms = MS()
    ms.dwLength = ctypes.sizeof(MS)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
        return None
    return ms.ullAvailPhys / 1e9


def _parse_subjects(arg: str | None) -> set[int] | None:
    if not arg:
        return None
    return {int(s.strip().upper().lstrip("S")) for s in arg.split(",") if s.strip()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--preset", choices=sorted(pp.PRESETS), default="default")
    ap.add_argument("--subjects", default=None, help="comma list, e.g. S25,S3 (default: all complete)")
    ap.add_argument("--workers", type=int, default=3, help="parallel blocks (peak RAM about 5.5 x the .fif size each)")
    ap.add_argument("--mem-budget-gb", type=float, default=22.0,
                    help="start a block only if the estimated RAM of running blocks stays below this")
    ap.add_argument("--threads", type=int, default=None,
                    help="BLAS threads per worker (default: CPU count // workers)")
    ap.add_argument("--priority", default="S25", help="comma list of subjects to run first")
    ap.add_argument("--force", action="store_true", help="redo blocks that are already cached")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    cfg = pp.get_config(args.preset)
    cache = args.cache or DEFAULT_CACHE[args.preset]
    cache.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("preprocess")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    for h in (logging.FileHandler(cache / "_preprocess.log", encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        h.setFormatter(fmt)
        log.addHandler(h)

    log.info("START pid=%d preset=%s version=%s workers=%d root=%s cache=%s", os.getpid(), args.preset,
             cfg.version, args.workers, args.root, cache)
    disc = sb.discover_from_root(args.root)
    (cache / "_excluded.json").write_text(json.dumps(disc.excluded, indent=1), encoding="utf-8")
    sizes = sb.read_filelist(args.root)
    complete = sb.complete_subjects(args.root, sizes)
    wanted = _parse_subjects(args.subjects)

    todo: list[sb.BlockSpec] = []
    first_block: dict[str, sb.BlockSpec] = {}
    for spec in disc.blocks:
        first_block.setdefault(spec.subject, spec)
        if wanted is not None and spec.subject_num not in wanted:
            continue
        if not complete.get(spec.subject_num, False):
            continue
        files = [spec.fif, *spec.split_parts, spec.log]
        if not all(sb.is_complete(args.root, f, sizes) or (f.startswith("MEG/logs/") and (args.root / f).is_file())
                   for f in files):
            log.warning("SKIP %s: files incomplete", spec.key)
            continue
        if not args.force and pp.is_cached(cache, spec, cfg):
            log.info("CACHED %s", spec.key)
            continue
        todo.append(spec)
    subjects = sorted({s.subject_num for s in todo})
    log.info("complete subjects: %s", ",".join(f"S{k}" for k, v in sorted(complete.items()) if v))
    log.info("blocks to do: %d (subjects %s)", len(todo), ",".join(f"S{s}" for s in subjects))
    if args.dry_run or not todo:
        pp.write_index(cache)
        log.info("END (nothing to run)" if not todo else "END (dry run)")
        return 0

    # One head position per subject: dev_head_t of the subject's first block.
    dests: dict[str, object] = {}
    for subj in {s.subject for s in todo}:
        fb = first_block[subj]
        try:
            dht = pp.subject_destination(args.root, fb)
            dests[subj] = dht["trans"] if dht is not None else None
            log.info("destination %s from %s", subj, fb.key)
        except Exception as exc:  # noqa: BLE001 - first block may be incomplete
            log.warning("destination %s: %s; using the block's own head position", subj, exc)
            dests[subj] = None

    n_ok = n_fail = 0
    t_start = time.time()
    def est_gb(spec: sb.BlockSpec) -> float:
        nbytes = sum(sizes.get(f, 0) for f in [spec.fif, *spec.split_parts])
        return MEM_FACTOR * nbytes / 1e9 + MEM_BASE_GB

    # Priority subjects first; then large blocks, so that small ones fill the gaps at the end.
    prio = _parse_subjects(args.priority) or set()
    queue = sorted(todo, key=lambda s: (s.subject_num not in prio, -est_gb(s)))
    for s in queue:
        log.info("QUEUED %s (%s, est %.1f GB)", s.key, s.fif, est_gb(s))
    workers = max(1, args.workers)
    # Child processes inherit these. Without a cap, each worker's BLAS uses all cores.
    threads = args.threads or max(1, (os.cpu_count() or 1) // workers)
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[var] = str(threads)
    log.info("workers=%d threads/worker=%d mem budget=%.0f GB", workers, threads, args.mem_budget_gb)
    # max_tasks_per_child=1: a fresh process per block, so memory goes back to the OS.
    with ProcessPoolExecutor(max_workers=workers, max_tasks_per_child=1) as ex:
        pending: dict = {}
        while queue or pending:
            used = sum(est_gb(s) for s in pending.values())
            while queue and len(pending) < workers:
                nxt = next((s for s in queue if not pending or used + est_gb(s) <= args.mem_budget_gb), None)
                if nxt is None:
                    break
                free = free_ram_gb()
                if pending and free is not None and free < est_gb(nxt) + 1.0:
                    log.info("WAIT RAM: %.1f GB free, %s needs about %.1f GB", free, nxt.key, est_gb(nxt))
                    break
                queue.remove(nxt)
                used += est_gb(nxt)
                fut = ex.submit(_worker, nxt.to_dict(), str(args.root), str(cache), args.preset, dests[nxt.subject])
                pending[fut] = nxt
                log.info("START %s (running %d, est %.1f GB in use)", nxt.key, len(pending), used)
            # Wake up every 60 s to recheck free RAM.
            done, _ = wait(pending, timeout=60, return_when=FIRST_COMPLETED)
            for fut in done:
                spec = pending.pop(fut)
                try:
                    res = fut.result()
                except Exception as exc:  # noqa: BLE001 - worker process died (for example out of memory)
                    res = {"key": spec.key, "ok": False, "error": f"worker died: {exc!r}"}
                if res.get("ok"):
                    n_ok += 1
                    a = res["qc"]["alignment"]
                    log.info(
                        "DONE %s in %.0fs: segments=%d keys matched=%.4f resid p95=%.2fms bads=%s 23Hz %s->%s dB peakmem=%s GB %s",
                        res["key"], res.get("elapsed_s", 0), res["n_segments"], a["key_matched_fraction"],
                        a["resid_ms_p95"], res["qc"]["bad_channels"],
                        res["qc"].get("peak_23hz_before", {}).get("prominence_db"),
                        res["qc"].get("peak_23hz_after", {}).get("prominence_db"),
                        res["qc"].get("peak_memory_gb"),
                        "(log reassigned)" if res["qc"].get("log_reassigned") else "",
                    )
                else:
                    n_fail += 1
                    log.error("FAIL %s: %s\n%s", res["key"], res.get("error"), res.get("trace", ""))
                pp.write_index(cache)
                log.info("progress: %d ok, %d failed, %d running, %d queued", n_ok, n_fail, len(pending), len(queue))
    pp.write_index(cache)
    log.info("END ok=%d failed=%d elapsed=%.0fs", n_ok, n_fail, time.time() - t_start)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
