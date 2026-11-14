"""CPU isolation for latency measurements while other agents run.

Two job classes share the machine:

- ``timing``: pinned to a reserved set of physical cores (one logical CPU per
  core; the SMT siblings of those cores stay idle), at above-normal priority.
  Only one timing job runs at a time: an OS file lock under
  ``~/bci-data/runs/cpu-isolation/`` guards the reserved cores.
- ``background``: pinned to all logical CPUs of the other physical cores, at
  below-normal priority. Any number of background jobs can run.

Use it from the command line (children inherit the affinity)::

    python -m fidetype.utils.isolation run --class timing -- python bench.py
    python -m fidetype.utils.isolation run --class background -- python train.py
    python -m fidetype.utils.isolation show

or in-process for a latency experiment::

    from fidetype.utils.isolation import isolated
    with isolated("timing") as iso:
        ...measure...
    results["measurement_env"] = iso.record   # affinity, priority, load, CPU model

The record tells later readers if the measurement was clean (``clean`` and
``clean_reasons``). Windows uses ctypes only (no psutil). Linux uses
``os.sched_setaffinity`` and ``os.nice``; other systems run without pinning.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Sequence

CLASSES = ("timing", "background")
DEFAULT_TIMING_CORES = 4
THREAD_ENV_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                   "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
TORCH_THREADS_ENV = "FIDETYPE_TORCH_THREADS"
CLASS_ENV = "FIDETYPE_ISOLATION_CLASS"
CPUS_ENV = "FIDETYPE_ISOLATION_CPUS"
#: A run counts as clean if other processes used less than this share of the timing CPUs.
CLEAN_FOREIGN_LOAD_PCT = 5.0

# Windows priority classes.
ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
NORMAL_PRIORITY_CLASS = 0x00000020
_PRIORITY_NAMES = {0x40: "idle", 0x4000: "below_normal", 0x20: "normal",
                   0x8000: "above_normal", 0x80: "high", 0x100: "realtime"}
_CLASS_PRIORITY = {"timing": ABOVE_NORMAL_PRIORITY_CLASS, "background": BELOW_NORMAL_PRIORITY_CLASS}
_CLASS_NICE = {"timing": -5, "background": 10}

IS_WIN = sys.platform == "win32"


def isolation_dir() -> Path:
    """Directory for the lock and the job registry (env ``FIDETYPE_ISOLATION_DIR`` overrides)."""
    env = os.environ.get("FIDETYPE_ISOLATION_DIR")
    return Path(env) if env else Path.home() / "bci-data" / "runs" / "cpu-isolation"


# --------------------------------------------------------------------------- topology

def physical_cores() -> list[list[int]]:
    """Logical CPU ids grouped by physical core, e.g. ``[[0, 1], [2, 3], ...]``."""
    if IS_WIN:
        try:
            cores = _win_physical_cores()
            if cores:
                return cores
        except OSError:
            pass
    else:
        cores = _sysfs_physical_cores()
        if cores:
            return cores
    return [[i] for i in range(os.cpu_count() or 1)]


def _win_physical_cores() -> list[list[int]]:
    class SLPI(ctypes.Structure):
        _fields_ = [("ProcessorMask", ctypes.c_size_t), ("Relationship", ctypes.c_int),
                    ("_union", ctypes.c_ulonglong * 2)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetLogicalProcessorInformation.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    n = ctypes.c_uint32(0)
    k32.GetLogicalProcessorInformation(None, ctypes.byref(n))
    count = n.value // ctypes.sizeof(SLPI)
    buf = (SLPI * count)()
    if not k32.GetLogicalProcessorInformation(buf, ctypes.byref(n)):
        raise OSError(ctypes.get_last_error(), "GetLogicalProcessorInformation failed")
    cores = []
    for e in buf:
        if e.Relationship == 0:  # RelationProcessorCore
            cores.append([i for i in range(64) if e.ProcessorMask >> i & 1])
    return sorted(cores)


def _sysfs_physical_cores() -> list[list[int]]:
    base = Path("/sys/devices/system/cpu")
    groups: set[tuple[int, ...]] = set()
    for p in base.glob("cpu[0-9]*/topology/thread_siblings_list"):
        try:
            groups.add(tuple(_parse_cpu_list(p.read_text().strip())))
        except (OSError, ValueError):
            return []
    return sorted(list(g) for g in groups)


def _parse_cpu_list(s: str) -> list[int]:
    out: list[int] = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


@dataclass(frozen=True)
class Plan:
    """The CPU split: timing CPUs, background CPUs and idle SMT siblings."""

    timing: tuple[int, ...]
    background: tuple[int, ...]
    idle: tuple[int, ...]
    smt: bool

    def cpus(self, cls: str) -> tuple[int, ...]:
        return self.timing if cls == "timing" else self.background


def plan_classes(cores: Sequence[Sequence[int]], n_timing: int | None = None) -> Plan:
    """Reserve the highest-numbered ``n_timing`` physical cores for timing.

    Timing takes the first logical CPU of each reserved core. Its other SMT
    siblings stay idle (in no class). Background takes every logical CPU of the
    other cores. ``n_timing`` defaults to env ``FIDETYPE_TIMING_CORES`` or 4,
    and is capped so that background keeps at least one physical core.
    """
    if n_timing is None:
        n_timing = int(os.environ.get("FIDETYPE_TIMING_CORES", DEFAULT_TIMING_CORES))
    cores = sorted(sorted(c) for c in cores)
    if len(cores) < 2:
        raise ValueError("CPU isolation needs at least 2 physical cores")
    n_timing = max(1, min(n_timing, len(cores) - 1))
    reserved, rest = cores[-n_timing:], cores[:-n_timing]
    timing = tuple(c[0] for c in reserved)
    idle = tuple(i for c in reserved for i in c[1:])
    background = tuple(i for c in rest for i in c)
    return Plan(timing=timing, background=background, idle=idle,
                smt=any(len(c) > 1 for c in cores))


def mask_of(cpus: Sequence[int]) -> int:
    m = 0
    for c in cpus:
        m |= 1 << c
    return m


def cpus_of(mask: int) -> list[int]:
    return [i for i in range(64) if mask >> i & 1]


# --------------------------------------------------------------------------- process settings

def _k32() -> Any:
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                                         ctypes.POINTER(ctypes.c_size_t)]
    k.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    k.GetPriorityClass.argtypes = [ctypes.c_void_p]
    k.GetPriorityClass.restype = ctypes.c_uint32
    k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    return k


def get_affinity() -> list[int]:
    """Logical CPUs the current process may run on."""
    if IS_WIN:
        k = _k32()
        pm, sm = ctypes.c_size_t(0), ctypes.c_size_t(0)
        if k.GetProcessAffinityMask(k.GetCurrentProcess(), ctypes.byref(pm), ctypes.byref(sm)):
            return cpus_of(pm.value)
    elif hasattr(os, "sched_getaffinity"):
        return sorted(os.sched_getaffinity(0))
    return list(range(os.cpu_count() or 1))


def set_affinity(cpus: Sequence[int]) -> bool:
    """Pin the current process (and the children it starts later) to ``cpus``."""
    if IS_WIN:
        k = _k32()
        return bool(k.SetProcessAffinityMask(k.GetCurrentProcess(), mask_of(cpus)))
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, set(cpus))
        return True
    return False


def get_priority() -> str:
    if IS_WIN:
        k = _k32()
        return _PRIORITY_NAMES.get(k.GetPriorityClass(k.GetCurrentProcess()), "unknown")
    try:
        return f"nice={os.nice(0)}"
    except (AttributeError, OSError):
        return "unknown"


def _get_priority_raw() -> int:
    if IS_WIN:
        k = _k32()
        return int(k.GetPriorityClass(k.GetCurrentProcess()))
    return os.nice(0) if hasattr(os, "nice") else 0


def _set_priority_raw(value: int) -> bool:
    if IS_WIN:
        k = _k32()
        return bool(k.SetPriorityClass(k.GetCurrentProcess(), value))
    if hasattr(os, "nice"):
        try:
            os.nice(value - os.nice(0))
            return True
        except OSError:  # raising priority needs root on Linux
            return False
    return False


def set_class_priority(cls: str) -> bool:
    return _set_priority_raw(_CLASS_PRIORITY[cls] if IS_WIN else _CLASS_NICE[cls])


def thread_env(n_threads: int) -> dict[str, str]:
    """Thread-count variables for numeric libraries (read when the library loads)."""
    env = {v: str(n_threads) for v in THREAD_ENV_VARS}
    env[TORCH_THREADS_ENV] = str(n_threads)
    return env


def apply_torch_threads() -> int | None:
    """Call ``torch.set_num_threads`` from ``FIDETYPE_TORCH_THREADS`` if torch is loaded."""
    n = os.environ.get(TORCH_THREADS_ENV)
    torch = sys.modules.get("torch")
    if n and torch is not None:
        torch.set_num_threads(int(n))
        return int(n)
    return None


# --------------------------------------------------------------------------- machine facts

def cpu_model() -> str:
    if IS_WIN:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def cpu_times() -> list[tuple[float, float]] | None:
    """Per logical CPU: (busy seconds, total seconds) since boot. None if not available."""
    if IS_WIN:
        class SPPI(ctypes.Structure):
            _fields_ = [("IdleTime", ctypes.c_longlong), ("KernelTime", ctypes.c_longlong),
                        ("UserTime", ctypes.c_longlong), ("DpcTime", ctypes.c_longlong),
                        ("InterruptTime", ctypes.c_longlong), ("InterruptCount", ctypes.c_ulong)]

        n = os.cpu_count() or 1
        buf = (SPPI * n)()
        ret = ctypes.c_ulong(0)
        ntdll = ctypes.WinDLL("ntdll")
        status = ntdll.NtQuerySystemInformation(8, ctypes.byref(buf), ctypes.sizeof(buf), ctypes.byref(ret))
        if status != 0:
            return None
        out = []
        for e in buf:  # KernelTime includes IdleTime; units of 100 ns
            total = (e.KernelTime + e.UserTime) / 1e7
            out.append((total - e.IdleTime / 1e7, total))
        return out
    try:
        out = []
        for line in Path("/proc/stat").read_text().splitlines():
            if line.startswith("cpu") and line[3:4].isdigit():
                v = [float(x) for x in line.split()[1:]]
                idle = v[3] + (v[4] if len(v) > 4 else 0.0)
                total = sum(v[:8])
                out.append(((total - idle) / 100.0, total / 100.0))
        return out or None
    except OSError:
        return None


def load_pct(before: list[tuple[float, float]] | None, after: list[tuple[float, float]] | None,
             cpus: Sequence[int]) -> float | None:
    """Mean busy % of ``cpus`` between two :func:`cpu_times` samples."""
    if not before or not after or not cpus:
        return None
    busy = sum(after[c][0] - before[c][0] for c in cpus if c < len(after))
    total = sum(after[c][1] - before[c][1] for c in cpus if c < len(after))
    return round(100.0 * busy / total, 2) if total > 0 else None


# --------------------------------------------------------------------------- lock + registry

class TimingBusy(RuntimeError):
    """The reserved timing cores are held by another job."""


class TimingLock:
    """OS file lock on the timing cores. The OS frees it if the holder dies."""

    def __init__(self, directory: Path | None = None) -> None:
        self.dir = Path(directory) if directory else isolation_dir()
        self.path = self.dir / "timing.lock"
        self.owner_path = self.dir / "timing.owner.json"
        self._fh: Any = None

    def _try(self) -> bool:
        self.dir.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+b")
        try:
            if IS_WIN:
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh
        return True

    def owner(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.owner_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def acquire(self, wait_s: float = 0.0, label: str = "", poll_s: float = 1.0) -> None:
        """Take the lock. Wait up to ``wait_s`` seconds (negative = forever), else raise TimingBusy."""
        t0 = time.monotonic()
        warned = False
        while not self._try():
            if 0 <= wait_s <= time.monotonic() - t0:
                raise TimingBusy(f"timing cores are busy: held by {self.owner() or 'an unknown process'} "
                                 f"(lock {self.path}). Wait or use --wait.")
            if not warned:
                print(f"[isolation] timing cores busy, waiting (holder: {self.owner()})", file=sys.stderr)
                warned = True
            time.sleep(poll_s)
        info = {"pid": os.getpid(), "label": label, "since": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        self.owner_path.write_text(json.dumps(info), encoding="utf-8")

    def release(self) -> None:
        if self._fh is None:
            return
        with contextlib.suppress(OSError):
            self.owner_path.unlink()
        try:
            if IS_WIN:
                import msvcrt

                self._fh.seek(0)
                with contextlib.suppress(OSError):
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self._fh.close()
            self._fh = None

    @property
    def held(self) -> bool:
        return self._fh is not None


def _pid_alive(pid: int) -> bool:
    if IS_WIN:
        k = ctypes.WinDLL("kernel32")
        k.OpenProcess.restype = ctypes.c_void_p
        h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong(0)
        k.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
        k.CloseHandle(ctypes.c_void_p(h))
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def register_job(cls: str, label: str, pid: int | None = None) -> Path:
    d = isolation_dir() / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    pid = pid or os.getpid()
    p = d / f"{pid}.json"
    p.write_text(json.dumps({"pid": pid, "class": cls, "label": label,
                             "since": time.strftime("%Y-%m-%dT%H:%M:%S%z")}), encoding="utf-8")
    return p


def list_jobs(prune: bool = True) -> list[dict[str, Any]]:
    """Registered jobs; entries of dead processes are removed."""
    out = []
    for p in sorted((isolation_dir() / "jobs").glob("*.json")):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if _pid_alive(int(j.get("pid", 0))):
            out.append(j)
        elif prune:
            with contextlib.suppress(OSError):
                p.unlink()
    return out


# --------------------------------------------------------------------------- in-process helper

@dataclass
class Isolation:
    cls: str
    plan: Plan
    record: dict[str, Any] = field(default_factory=dict)


def describe_current() -> dict[str, Any]:
    """Affinity, priority and class of the current process, without changing them."""
    return {"class": os.environ.get(CLASS_ENV), "affinity": get_affinity(), "priority": get_priority(),
            "cpu_model": cpu_model(), "logical_cpus": os.cpu_count()}


@contextlib.contextmanager
def isolated(cls: str = "timing", n_timing: int | None = None, wait_s: float = 600.0,
             set_thread_env: bool = True, label: str = "") -> Iterator[Isolation]:
    """Run the block in a CPU class; fill ``.record`` with the measurement conditions.

    The process affinity and priority are restored on exit. Thread variables are
    set in ``os.environ`` (they only affect libraries loaded after this point;
    torch threads are set at once if torch is loaded).
    """
    if cls not in CLASSES:
        raise ValueError(f"cls must be one of {CLASSES}")
    plan = plan_classes(physical_cores(), n_timing)
    cpus = plan.cpus(cls)
    lock = TimingLock() if cls == "timing" else None
    if lock is not None:
        lock.acquire(wait_s=wait_s, label=label or f"in-process pid {os.getpid()}")
    old_aff, old_prio = get_affinity(), _get_priority_raw()
    old_env = {k: os.environ.get(k) for k in (*THREAD_ENV_VARS, TORCH_THREADS_ENV, CLASS_ENV, CPUS_ENV)}
    iso = Isolation(cls=cls, plan=plan)
    try:
        pinned = set_affinity(cpus)
        prio_ok = set_class_priority(cls)
        if set_thread_env:
            os.environ.update(thread_env(len(cpus)))
            apply_torch_threads()
        os.environ[CLASS_ENV] = cls
        os.environ[CPUS_ENV] = ",".join(map(str, cpus))
        t0_wall, t0_cpu, s0 = time.perf_counter(), time.process_time(), cpu_times()
        try:
            yield iso
        finally:
            wall = time.perf_counter() - t0_wall
            own_cpu = time.process_time() - t0_cpu
            s1 = cpu_times()
            iso.record = build_record(cls, plan, pinned, prio_ok, wall, own_cpu, s0, s1,
                                      lock_held=bool(lock and lock.held))
    finally:
        set_affinity(old_aff)
        _set_priority_raw(old_prio)
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if lock is not None:
            lock.release()


def build_record(cls: str, plan: Plan, pinned: bool, prio_ok: bool, wall_s: float, own_cpu_s: float,
                 s0: list[tuple[float, float]] | None, s1: list[tuple[float, float]] | None,
                 lock_held: bool, priority: str | None = None) -> dict[str, Any]:
    """The JSON block that states how clean a measurement was."""
    cpus = plan.cpus(cls)
    class_load = load_pct(s0, s1, cpus)
    foreign = None
    if class_load is not None and wall_s > 0:
        # Busy CPU-seconds on the class CPUs minus our own CPU time (upper bound for us).
        foreign = round(max(0.0, class_load - 100.0 * own_cpu_s / (wall_s * len(cpus))), 2)
    reasons = []
    if cls != "timing":
        reasons.append("not the timing class")
    if not pinned:
        reasons.append("affinity not set")
    if not prio_ok:
        reasons.append("priority not set")
    if cls == "timing" and not lock_held:
        reasons.append("timing lock not held")
    if foreign is None:
        reasons.append("load not measured")
    elif foreign >= CLEAN_FOREIGN_LOAD_PCT:
        reasons.append(f"other load on the class CPUs {foreign}% >= {CLEAN_FOREIGN_LOAD_PCT}%")
    if plan.idle and s0 and s1:
        idle_load = load_pct(s0, s1, plan.idle)
        if cls == "timing" and idle_load is not None and idle_load >= 20.0:
            reasons.append(f"SMT siblings of timing cores busy {idle_load}%")
    else:
        idle_load = None
    return {
        "schema": "fidetype.isolation/0.1",
        "class": cls,
        "cpus": list(cpus),
        "affinity_set": pinned,
        "priority": priority or get_priority(),
        "priority_set": prio_ok,
        "timing_lock_held": lock_held,
        "plan": {"timing": list(plan.timing), "background": list(plan.background),
                 "idle_smt_siblings": list(plan.idle), "smt": plan.smt},
        "cpu_model": cpu_model(),
        "logical_cpus": os.cpu_count(),
        "platform": platform.platform(),
        "wall_s": round(wall_s, 3),
        "own_cpu_s": round(own_cpu_s, 3),
        "class_cpu_load_pct": class_load,
        "foreign_load_pct": foreign,
        "idle_sibling_load_pct": idle_load,
        "machine_load_pct": load_pct(s0, s1, range(len(s1))) if s1 else None,
        "background_cpu_load_pct": load_pct(s0, s1, plan.background),
        "clean": not reasons,
        "clean_reasons": reasons,
    }


# --------------------------------------------------------------------------- command line

def run_command(cls: str, cmd: Sequence[str], wait_s: float = 0.0, n_threads: int | None = None,
                n_timing: int | None = None, env_json: str | None = None, label: str = "") -> int:
    """Run ``cmd`` in class ``cls``; return its exit code."""
    plan = plan_classes(physical_cores(), n_timing)
    cpus = plan.cpus(cls)
    lock = TimingLock() if cls == "timing" else None
    label = label or " ".join(cmd)[:200]
    if lock is not None:
        try:
            lock.acquire(wait_s=wait_s, label=label)
        except TimingBusy as e:
            print(f"[isolation] {e}", file=sys.stderr)
            return 75  # EX_TEMPFAIL
    reg = None
    try:
        # Windows: a job object holds this launcher and every process it starts, so
        # grandchildren (for example the real python behind a venv python.exe) also
        # get the affinity and the priority class. Elsewhere: affinity is inherited.
        job = _win_job(cpus, _CLASS_PRIORITY[cls]) if IS_WIN else None
        pinned = set_affinity(cpus)
        env = dict(os.environ)
        env.update(thread_env(n_threads or len(cpus)))
        env[CLASS_ENV] = cls
        env[CPUS_ENV] = ",".join(map(str, cpus))
        flags = _CLASS_PRIORITY[cls] if IS_WIN else 0  # also for the child if no job object
        preexec = None
        if not IS_WIN and hasattr(os, "nice"):
            nice = _CLASS_NICE[cls]

            def preexec() -> None:  # pragma: no cover - POSIX only
                with contextlib.suppress(OSError):
                    os.nice(nice)
        print(f"[isolation] class={cls} cpus={list(cpus)} threads={n_threads or len(cpus)}", file=sys.stderr)
        s0, t0 = cpu_times(), time.perf_counter()
        exe = shutil.which(cmd[0]) or cmd[0]
        proc = subprocess.Popen([exe, *cmd[1:]], env=env, creationflags=flags, preexec_fn=preexec)
        reg = register_job(cls, label, proc.pid)
        try:
            code = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            code = proc.wait()
        s1 = cpu_times()
        child_cpu = _job_cpu_s(job) if job else 0.0
        if env_json:
            rec = build_record(cls, plan, pinned, True, time.perf_counter() - t0, child_cpu, s0, s1,
                               lock_held=bool(lock and lock.held),
                               priority=_PRIORITY_NAMES[_CLASS_PRIORITY[cls]] if IS_WIN else f"nice={_CLASS_NICE[cls]}")
            rec["job_object"] = bool(job)
            rec["note"] = "own_cpu_s = CPU time of all processes of the job (Windows job object)."
            rec["command"] = list(cmd)
            rec["exit_code"] = code
            Path(env_json).write_text(json.dumps(rec, indent=2), encoding="utf-8")
        return code
    finally:
        if reg is not None:
            with contextlib.suppress(OSError):
                reg.unlink()
        if lock is not None:
            lock.release()


class _JOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32)]


class _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [("TotalUserTime", ctypes.c_longlong), ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong), ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", ctypes.c_uint32), ("TotalProcesses", ctypes.c_uint32),
                ("ActiveProcesses", ctypes.c_uint32), ("TotalTerminatedProcesses", ctypes.c_uint32)]


def _win_job(cpus: Sequence[int], priority_class: int) -> int | None:
    """Put the current process in a new job object with affinity + priority limits.

    Returns the job handle, or None if Windows refused (then plain inheritance applies).
    """
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.restype = ctypes.c_void_p
    k.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    k.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k.GetCurrentProcess.restype = ctypes.c_void_p
    job = k.CreateJobObjectW(None, None)
    if not job:
        return None
    info = _JOBJECT_BASIC_LIMIT_INFORMATION()
    info.LimitFlags = 0x10 | 0x20  # JOB_OBJECT_LIMIT_AFFINITY | JOB_OBJECT_LIMIT_PRIORITY_CLASS
    info.Affinity = mask_of(cpus)
    info.PriorityClass = priority_class
    if not k.SetInformationJobObject(job, 2, ctypes.byref(info), ctypes.sizeof(info)):
        return None
    if not k.AssignProcessToJobObject(job, k.GetCurrentProcess()):
        return None
    return int(job)


def _job_cpu_s(job: int) -> float:
    """Kernel + user CPU seconds of all processes that ran in the job."""
    k = ctypes.WinDLL("kernel32")
    k.QueryInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                            ctypes.c_uint32, ctypes.c_void_p]
    acc = _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
    if not k.QueryInformationJobObject(ctypes.c_void_p(job), 1, ctypes.byref(acc), ctypes.sizeof(acc), None):
        return 0.0
    return (acc.TotalUserTime + acc.TotalKernelTime) / 1e7


def show() -> dict[str, Any]:
    cores = physical_cores()
    plan = plan_classes(cores)
    lock = TimingLock()
    return {"cpu_model": cpu_model(), "physical_cores": cores,
            "timing": list(plan.timing), "background": list(plan.background),
            "idle_smt_siblings": list(plan.idle), "timing_lock_owner": lock.owner(),
            "lock_dir": str(lock.dir), "jobs": list_jobs()}


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidetype.utils.isolation", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a command in a CPU class")
    r.add_argument("--class", dest="cls", choices=CLASSES, required=True)
    r.add_argument("--wait", type=float, default=0.0,
                   help="timing only: seconds to wait for the cores (-1 = forever; default 0 = fail at once)")
    r.add_argument("--threads", type=int, default=None, help="thread count for OMP/MKL/torch (default: class CPUs)")
    r.add_argument("--timing-cores", type=int, default=None, help="physical cores to reserve (default 4)")
    r.add_argument("--env-json", default=None, help="write the measurement-conditions record here")
    r.add_argument("--label", default="")
    r.add_argument("command", nargs=argparse.REMAINDER)
    sub.add_parser("show", help="print the CPU split, the lock holder and the registered jobs")
    a = ap.parse_args(argv)
    if a.cmd == "show":
        print(json.dumps(show(), indent=2))
        return 0
    cmd = a.command[1:] if a.command[:1] == ["--"] else a.command
    if not cmd:
        ap.error("give a command after --")
    return run_command(a.cls, cmd, a.wait, a.threads, a.timing_cores, a.env_json, a.label)


if __name__ == "__main__":
    raise SystemExit(main())
