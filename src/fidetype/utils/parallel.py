"""Deterministic parallel map for CPU experiments (process pool, background CPU class).

``pmap(fn, items)`` runs ``fn`` on each item in worker processes and returns the
results in input order. It gives the same results as a plain loop, if ``fn`` is
a pure function of the item, its seed and read-only shared data:

- **Order:** results come back in input order, whatever order the workers finish in.
- **Seeds:** with ``seed=s``, item ``i`` gets ``item_seed(s, i)`` as its second
  argument (``fn(item, seed_i)``). The seed depends only on ``s`` and ``i``, not on
  the worker, the worker count or the chunk size.
- **Workers:** spawned processes (also on Linux, so all systems behave the same),
  pinned to the ``background`` CPU class at below-normal priority, with 1 BLAS /
  OpenMP / torch thread each. The count is sized automatically:
  background CPUs minus the slots of other registered jobs
  (``python -m fidetype.utils.isolation show``), optionally limited by free RAM,
  and capped by ``workers=`` and the env variable ``FIDETYPE_WORKERS``.
- **Shared data:** large read-only data loads once per worker in ``initializer``
  (not once per task), or lives in memory-mapped ``.npy`` files
  (:func:`save_shared` / :func:`load_shared`), which the OS shares between processes.
- **Checkpoints:** with ``checkpoint=DIR``, each finished chunk is written to
  ``DIR/chunk-NNNNNN.pkl`` at once. A rerun with the same items loads the
  finished chunks and runs only the rest.
- **Serial fallback:** ``workers=1`` (or one item, or one free slot) runs in the
  calling process, with the same initializer, seeds, order and checkpoints.

Example::

    from fidetype.utils.parallel import pmap, add_workers_arg

    _CTX = None
    def init(path):                 # runs once per worker
        global _CTX
        _CTX = load_big_context(path)
    def one_split(r, seed):         # module-level function, so spawn can import it
        return evaluate(_CTX, r, np.random.default_rng(seed))

    if __name__ == "__main__":      # required for spawn
        rows = pmap(one_split, range(200), seed=3, initializer=init, initargs=(path,),
                    workers=args.workers, checkpoint=out_dir / "ckpt")

``fn`` and ``initializer`` must be importable module-level functions (spawn
pickles them by name). A script that uses ``pmap`` needs an
``if __name__ == "__main__":`` guard, because each worker imports the script again.
"""

from __future__ import annotations

import concurrent.futures as cf
import contextlib
import ctypes
import hashlib
import json
import multiprocessing as mp
import os
import pickle
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from fidetype.utils import isolation as iso

WORKERS_ENV = "FIDETYPE_WORKERS"
WORKER_ENV = "FIDETYPE_PMAP_WORKER"  # set to "1" inside pmap workers
CHECKPOINT_SCHEMA = "fidetype.pmap-checkpoint/0.1"

__all__ = ["pmap", "item_seed", "resolve_workers", "available_memory_gb", "in_worker", "add_workers_arg",
           "save_shared", "load_shared", "WORKERS_ENV"]


# --------------------------------------------------------------------------- seeds

def item_seed(seed: int, index: int) -> int:
    """Seed of item ``index`` under base ``seed`` (NumPy ``SeedSequence([seed, index])``, 32 bit)."""
    import numpy as np

    return int(np.random.SeedSequence([int(seed), int(index)]).generate_state(1, np.uint32)[0])


def in_worker() -> bool:
    """True inside a pmap worker process (for example to skip writing shared cache files)."""
    return os.environ.get(WORKER_ENV) == "1"


# --------------------------------------------------------------------------- sizing

def available_memory_gb() -> float | None:
    """Free physical memory in GB (Windows: GlobalMemoryStatusEx; Linux: MemAvailable)."""
    if sys.platform == "win32":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_uint32), ("dwMemoryLoad", ctypes.c_uint32),
                        ("ullTotalPhys", ctypes.c_uint64), ("ullAvailPhys", ctypes.c_uint64),
                        ("ullTotalPageFile", ctypes.c_uint64), ("ullAvailPageFile", ctypes.c_uint64),
                        ("ullTotalVirtual", ctypes.c_uint64), ("ullAvailVirtual", ctypes.c_uint64),
                        ("ullAvailExtendedVirtual", ctypes.c_uint64)]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(st)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return st.ullAvailPhys / 2**30
        return None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 2**20
    except OSError:
        pass
    return None


def _env_cap() -> int | None:
    v = os.environ.get(WORKERS_ENV, "").strip()
    if not v:
        return None
    n = int(v)
    if n < 1:
        raise ValueError(f"{WORKERS_ENV} must be >= 1, got {v!r}")
    return n


def background_cpus() -> tuple[int, ...]:
    try:
        return iso.plan_classes(iso.physical_cores()).background
    except ValueError:  # fewer than 2 physical cores
        return tuple(range(os.cpu_count() or 1))


def resolve_workers(workers: int | None = None, *, exact: bool = False, mem_per_worker_gb: float | None = None,
                    n_tasks: int | None = None) -> tuple[int, dict[str, Any]]:
    """Worker count and the reasons for it.

    ``auto`` = background CPUs minus the slots of other registered jobs (at least 1),
    then at most ``free RAM / mem_per_worker_gb``. ``workers`` and env
    ``FIDETYPE_WORKERS`` are caps. ``exact=True`` uses ``workers`` as given (still
    capped by the env variable and by ``n_tasks``).
    """
    cpus = background_cpus()
    me = {os.getpid(), os.getppid()}
    try:
        jobs = [j for j in iso.list_jobs() if j.get("class") == "background" and int(j.get("pid", 0)) not in me]
    except OSError:
        jobs = []
    held = sum(int(j.get("slots") or 1) for j in jobs)
    auto = max(1, len(cpus) - held)
    info: dict[str, Any] = {"background_cpus": len(cpus), "slots_held_by_other_jobs": held, "auto": auto}
    if mem_per_worker_gb:
        free = available_memory_gb()
        info["free_ram_gb"] = None if free is None else round(free, 1)
        if free is not None:
            auto = max(1, min(auto, int(free // mem_per_worker_gb)))
            info["auto_after_ram"] = auto
    if workers is not None and workers < 1:
        raise ValueError(f"workers must be >= 1, got {workers}")
    n = workers if (exact and workers) else min(auto, workers or auto)
    env = _env_cap()
    if env is not None:
        n = min(n, env)
        info["env_cap"] = env
    if n_tasks is not None:
        n = max(1, min(n, n_tasks))
    info["workers"] = n
    return n, info


def add_workers_arg(parser: Any, default: int | None = None) -> None:
    """Add ``--workers N`` (a cap; default: auto) and ``--exact-workers`` to an argparse parser."""
    parser.add_argument("--workers", type=int, default=default,
                        help=f"max worker processes (default: auto = free background CPUs; env {WORKERS_ENV} also caps; "
                             "1 = serial)")
    parser.add_argument("--exact-workers", action="store_true",
                        help="use --workers as given, without the auto limit from other jobs")


# --------------------------------------------------------------------------- shared arrays

def save_shared(arrays: dict[str, Any], directory: str | Path) -> Path:
    """Write NumPy arrays as ``<name>.npy`` files, for :func:`load_shared` with memory mapping."""
    import numpy as np

    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    for k, v in arrays.items():
        if not k.isidentifier():
            raise ValueError(f"array name must be an identifier: {k!r}")
        tmp = d / f"{k}.tmp.npy"
        np.save(tmp, np.asarray(v), allow_pickle=False)
        os.replace(tmp, d / f"{k}.npy")
    return d


def load_shared(directory: str | Path) -> dict[str, Any]:
    """Memory-map the ``.npy`` files of :func:`save_shared` (read-only; the OS shares the pages)."""
    import numpy as np

    return {p.stem: np.load(p, mmap_mode="r", allow_pickle=False)
            for p in sorted(Path(directory).glob("*.npy")) if not p.stem.endswith(".tmp")}


# --------------------------------------------------------------------------- checkpoints

class _Checkpoint:
    def __init__(self, directory: str | Path, n_items: int, chunksize: int, key: str, label: str) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        man = {"schema": CHECKPOINT_SCHEMA, "n_items": n_items, "chunksize": chunksize, "key": key, "label": label}
        mp_ = self.dir / "manifest.json"
        if mp_.exists():
            old = json.loads(mp_.read_text(encoding="utf-8"))
            if {k: old.get(k) for k in ("n_items", "chunksize", "key")} != {k: man[k] for k in ("n_items", "chunksize", "key")}:
                raise ValueError(f"checkpoint {self.dir} belongs to another run (manifest {old}); "
                                 "use a new directory or delete it")
        else:
            mp_.write_text(json.dumps(man, indent=1), encoding="utf-8")

    def path(self, k: int) -> Path:
        return self.dir / f"chunk-{k:06d}.pkl"

    def load(self, n_chunks: int) -> dict[int, list]:
        out = {}
        for k in range(n_chunks):
            p = self.path(k)
            if p.exists():
                try:
                    out[k] = pickle.loads(p.read_bytes())
                except Exception:  # noqa: BLE001  (a torn file from a crash: rerun the chunk)
                    continue
        return out

    def save(self, k: int, results: list) -> None:
        p = self.path(k)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(pickle.dumps(results, protocol=pickle.HIGHEST_PROTOCOL))
        os.replace(tmp, p)


def _default_key(items: Sequence[Any], seed: int | None, fn: Callable) -> str:
    h = hashlib.sha256()
    h.update(f"{getattr(fn, '__module__', '')}.{getattr(fn, '__qualname__', repr(fn))}|{seed}|".encode())
    h.update(pickle.dumps(list(items), protocol=4))
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- workers

def _thread_env(threads: int) -> dict[str, str]:
    """Variables that spawned workers must have at start (numeric libraries read them at import)."""
    env = iso.thread_env(threads)
    env[iso.CLASS_ENV] = "background"
    return env


def _worker_init(threads: int, cpus: Sequence[int] | None, user_init: Callable | None, user_args: tuple) -> None:
    os.environ.update(_thread_env(threads))
    os.environ[WORKER_ENV] = "1"
    if cpus:
        with contextlib.suppress(Exception):
            iso.set_affinity(cpus)
            os.environ[iso.CPUS_ENV] = ",".join(map(str, cpus))
        with contextlib.suppress(Exception):
            iso.set_class_priority("background")
    iso.apply_torch_threads()
    if user_init is not None:
        user_init(*user_args)


def _run_chunk(fn: Callable, k: int, idx: list[int], items: list[Any], seed: int | None) -> tuple[int, list, float]:
    t0 = time.perf_counter()
    if seed is None:
        out = [fn(it) for it in items]
    else:
        out = [fn(it, item_seed(seed, i)) for i, it in zip(idx, items)]
    return k, out, time.perf_counter() - t0


class _Progress:
    def __init__(self, label: str, total: int, done: int, log: Callable[[str], None], every_s: float) -> None:
        self.label, self.total, self.done, self.log, self.every = label, total, done, log, every_s
        self.t0 = self.last = time.monotonic()
        self.start_done = done

    def step(self, n: int, force: bool = False) -> None:
        self.done += n
        now = time.monotonic()
        if force or now - self.last >= self.every or self.done == self.total:
            self.last = now
            el = now - self.t0
            new = self.done - self.start_done
            eta = el / new * (self.total - self.done) if new else float("nan")
            self.log(f"[pmap {self.label}] {self.done}/{self.total} items, {el:.0f}s elapsed, eta {eta:.0f}s")


def _stderr_log(msg: str) -> None:
    print(time.strftime("%H:%M:%S ") + msg, file=sys.stderr, flush=True)


def pmap(fn: Callable, items: Iterable[Any], *, workers: int | None = None, exact: bool = False, chunksize: int = 1,
         seed: int | None = None, initializer: Callable | None = None, initargs: tuple = (),
         checkpoint: str | Path | None = None, checkpoint_key: str | None = None, label: str = "",
         log: Callable[[str], None] | None = _stderr_log, log_every_s: float = 30.0,
         mem_per_worker_gb: float | None = None, threads_per_worker: int = 1, pin: bool = True,
         info: dict | None = None) -> list:
    """Map ``fn`` over ``items`` in worker processes; return the results in input order.

    Args:
        fn: module-level function; called as ``fn(item)``, or ``fn(item, seed_i)`` if ``seed`` is set.
        workers: cap on the worker count (None = auto). 1 = serial in this process.
        exact: use ``workers`` as given, without the auto limit (the env cap still applies).
        chunksize: items per task. A chunk is also the checkpoint unit.
        seed: base seed; item ``i`` gets ``item_seed(seed, i)``.
        initializer, initargs: run once per worker (and once in this process in serial
            mode) before any task; use it to load large read-only data into module globals.
        checkpoint: directory for per-chunk results; a rerun skips finished chunks.
        checkpoint_key: identifies the inputs (default: hash of fn name, seed and pickled items).
        label: name in the log lines and in the job registry.
        log: function for progress lines (None = silent).
        mem_per_worker_gb: also limit the auto worker count by free RAM.
        threads_per_worker: BLAS / OpenMP / torch threads per worker (default 1).
        pin: pin workers to the background CPU class at below-normal priority.
        info: if given, filled with the worker count, its reasons and timings.
    """
    items = list(items)
    if chunksize < 1:
        raise ValueError("chunksize must be >= 1")
    label = label or getattr(fn, "__name__", "pmap")
    n = len(items)
    chunks = [list(range(s, min(n, s + chunksize))) for s in range(0, n, chunksize)]
    store = None
    done: dict[int, list] = {}
    if checkpoint is not None:
        store = _Checkpoint(checkpoint, n, chunksize, checkpoint_key or _default_key(items, seed, fn), label)
        done = store.load(len(chunks))
    todo = [k for k in range(len(chunks)) if k not in done]
    nw, why = resolve_workers(workers, exact=exact, mem_per_worker_gb=mem_per_worker_gb, n_tasks=max(1, len(todo)))
    t_start = time.perf_counter()
    prog = _Progress(label, n, sum(len(chunks[k]) for k in done), log or (lambda m: None), log_every_s)
    if log:
        log(f"[pmap {label}] {n} items in {len(chunks)} chunks; {len(done)} chunks from checkpoint; "
            f"workers {nw} ({json.dumps(why)})")
    results: dict[int, list] = dict(done)
    cpus = background_cpus() if pin else None

    if nw <= 1 or not todo:
        if todo:
            # serial mode: same initializer, seeds, order and checkpoints, in this process
            if initializer is not None:
                initializer(*initargs)
            for k in todo:
                _, out, _ = _run_chunk(fn, k, chunks[k], [items[i] for i in chunks[k]], seed)
                results[k] = out
                if store:
                    store.save(k, out)
                prog.step(len(chunks[k]))
    else:
        ctx = mp.get_context("spawn")
        env_new = _thread_env(threads_per_worker)
        env_old = {k: os.environ.get(k) for k in env_new}
        os.environ.update(env_new)  # spawned workers inherit these before they import numpy
        reg, reg_old = None, None
        with contextlib.suppress(OSError):
            own = iso.isolation_dir() / "jobs" / f"{os.getpid()}.json"
            reg_old = own.read_text(encoding="utf-8") if own.exists() else None  # registered by `isolation run`
            reg = iso.register_job("background", f"pmap {label} ({nw} workers)", slots=nw)
        ex = cf.ProcessPoolExecutor(max_workers=nw, mp_context=ctx, initializer=_worker_init,
                                    initargs=(threads_per_worker, cpus, initializer, tuple(initargs)))
        try:
            futs = {ex.submit(_run_chunk, fn, k, chunks[k], [items[i] for i in chunks[k]], seed): k for k in todo}
            err: BaseException | None = None
            for fut in cf.as_completed(futs):
                if fut.cancelled():
                    continue
                try:
                    k, out, _ = fut.result()
                except Exception as e:  # noqa: BLE001
                    # first failure: cancel the queued chunks, let the running ones finish and keep them
                    if err is None:
                        err = e
                        for f in futs:
                            f.cancel()
                    continue
                results[k] = out
                if store:
                    store.save(k, out)
                prog.step(len(chunks[k]))
            if err is not None:
                raise err
        except BaseException:
            ex.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            ex.shutdown(wait=True)
        finally:
            for k, v in env_old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            if reg is not None:
                with contextlib.suppress(OSError):
                    if reg_old is None:
                        reg.unlink()
                    else:
                        reg.write_text(reg_old, encoding="utf-8")
    wall = time.perf_counter() - t_start
    if log:
        log(f"[pmap {label}] done: {n} items, {wall:.1f}s, workers {nw}")
    if info is not None:
        info.update({"workers": nw, "sizing": why, "chunks": len(chunks), "chunks_from_checkpoint": len(done),
                     "wall_s": round(wall, 3)})
    return [r for k in range(len(chunks)) for r in results[k]]
