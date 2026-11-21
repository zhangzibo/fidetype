"""P15-38 shared helpers. Our own code (Apache-2.0).

The metric and verdict code is the P15-25 ``common.py``, imported unchanged from its folder (module name
``p1525_common``). This module adds only the P15-38 paths, log, stop file and the read-only loaders.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "results"
DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p15-38"  # the only place this task writes derived files
P1525 = DER / "p15-25"  # READ ONLY (log-probs, P15-25 decodes)


def load_module(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def config() -> dict:
    return json.loads((HERE / "config.json").read_text(encoding="utf-8"))


def p1525():
    """The P15-25 ``common.py`` (VOCAB, encode, levenshtein, greedy_tokens, bootstrap, verdict, run lists)."""
    return load_module("p1525_common", REPO / config()["p1525_dir"] / "common.py")


def own(*parts: str) -> Path:
    p = OWN.joinpath(*parts).resolve()
    assert OWN.resolve() in p.parents or p == OWN.resolve(), p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def log(*a: object) -> None:
    OUT.mkdir(exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def save_json(obj: object, path: Path) -> None:
    rp = Path(path).resolve()
    assert OWN.resolve() in rp.parents or OUT.resolve() in rp.parents, path  # never write to P15-25 or elsewhere
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_json(path: Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def stop_requested() -> bool:
    return (OWN / "STOP").exists()
