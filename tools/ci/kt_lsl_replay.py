"""CI check P14-11: replay a public EMG recording over LSL through ``fidetype live`` and validate the NTS output.

Data: KT-sEMG run3 (77 s, 32 channels, 2000 Hz) from the KT-sEMG dataset,
copyright 2021 Nokia, licensed CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/), Harvard Dataverse
doi:10.7910/DVN/AV6XIR, version 1.1. The files are downloaded at run time,
checked against the SHA-256 values in ``tools/ci/kt-semg-run3.sha256``
and never committed. We do not change the data.

Steps (one command)::

    python tools/ci/kt_lsl_replay.py --cache ~/.cache/fidetype-ci/kt-semg --work /tmp/kt

1. Download ``run3.csv``, ``run3_keys.txt``, ``run3_ts.txt`` into ``--cache``
   (skipped when the cached files have the pinned SHA-256).
2. ``fidetype live train-kt`` on run3 only (an IN-SAMPLE plumbing model;
   the guard cannot certify a threshold on 77 s, so it never commits).
3. For each timing (``markers`` = key-log onsets; ``detect`` = the envelope
   onset detector of P4-10): ``fidetype live replay-kt`` publishes run3 on
   a loopback LSL stream, and ``fidetype live --source lsl`` decodes it.
4. ``fidetype validate`` must pass at level ``trust-ready``, the stream must
   have trust decisions, and the header must carry the replay attribution.

Exit code 0 when every check passes. Our own code (Apache-2.0).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = HERE / "kt-semg-run3.sha256"
BASE = "https://dataverse.harvard.edu/api/access/datafile/"
ATTRIBUTION = ("KT-sEMG dataset (run3), copyright 2021 Nokia, CC BY 4.0, doi:10.7910/DVN/AV6XIR v1.1; "
               "downloaded unchanged for this check")


def say(msg: str) -> None:
    print(f"[kt-lsl-replay] {msg}", flush=True)


def pins() -> list[tuple[str, str, str, str]]:
    out = []
    for line in PINS.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            sha, name, fid, q = line.split()
            out.append((sha, name, fid, q))
    return out


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def fetch(cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    for sha, name, fid, q in pins():
        dst = cache / name
        if dst.exists() and sha256(dst) == sha:
            say(f"cached: {name} (SHA-256 OK)")
            continue
        url = BASE + fid + ("" if q == "-" else "?" + q)
        tmp = dst.with_suffix(dst.suffix + ".part")
        for attempt in range(1, 4):
            try:
                say(f"download {name} from {url} (try {attempt})")
                req = urllib.request.Request(url, headers={"User-Agent": "fidetype-ci"})
                with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as f:
                    for blk in iter(lambda: r.read(1 << 20), b""):
                        f.write(blk)
                break
            except OSError as e:
                say(f"download failed: {e}")
                if attempt == 3:
                    raise
                time.sleep(10 * attempt)
        got = sha256(tmp)
        if got != sha:
            tmp.unlink()
            raise SystemExit(f"SHA-256 mismatch for {name}: got {got}, pinned {sha}")
        tmp.replace(dst)
        say(f"got {name}: {dst.stat().st_size} bytes, SHA-256 OK")


def run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:
    say("$ " + " ".join(cmd))
    return subprocess.run(cmd, check=True, **kw)  # type: ignore[call-overload]


def replay_and_decode(py: str, cache: Path, model_dir: Path, work: Path, timing: str, speed: float) -> dict:
    name = f"fidetype.ci.kt-semg.{timing}.{uuid.uuid4().hex[:8]}"
    out, summ = work / f"live-{timing}.nts.jsonl", work / f"live-{timing}.summary.json"
    pub = subprocess.Popen([py, "-m", "fidetype", "live", "replay-kt", "--data", str(cache), "--run", "run3",
                            "--speed", str(speed), "--name", name, "--wait-consumers", "60"])
    try:
        cmd = [py, "-m", "fidetype", "live", "--source", "lsl", "--stream-name", name,
               "--model", str(model_dir / "kt-semg-lda.model.json"),
               "--guard", str(model_dir / "kt-semg-lda.guard.json"),
               "--out", str(out), "--summary", str(summ), "--json", "--duration", "180",
               "--max-reconnects", "0", "--timing", timing]
        if timing == "detect":
            cmd += ["--onset", "envelope"]
        run(cmd)
    finally:
        try:
            pub.wait(timeout=60)
        except subprocess.TimeoutExpired:
            pub.kill()
    run([py, "-m", "fidetype", "validate", str(out)])
    from fidetype.conformance import check_file

    rep = check_file(out)
    bad = rep.failures("trust-ready")
    if bad:
        raise SystemExit(f"{timing}: NTS not trust-ready: {bad}")
    evs = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    s = json.loads(summ.read_text(encoding="utf-8"))
    n_dec = sum(1 for e in evs if e["type"] == "trust_decision")
    head = evs[0]
    rep_attr = head.get("meta", {}).get("fidetype.replay", "")
    say(f"{timing}: {s['decisions']} decisions ({s['commits']} commit, {s['offers']} offer, {s['withholds']} "
        f"withhold), {s['frames']} windows, onsets {s.get('onsets', 0)}; header replay = {rep_attr!r}")
    if n_dec < 1 or n_dec != s["decisions"]:
        raise SystemExit(f"{timing}: expected >= 1 trust_decision events (summary {s['decisions']}, file {n_dec})")
    if "kt-semg run3" not in rep_attr or "CC BY 4.0" not in rep_attr:
        raise SystemExit(f"{timing}: the header does not carry the replay attribution")
    if head.get("meta", {}).get("fidetype.live", {}).get("timing") != timing:
        raise SystemExit(f"{timing}: the header does not record the timing")
    return {"decisions": s["decisions"], "commits": s["commits"], "frames": s["frames"], "onsets": s.get("onsets", 0)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", default=os.path.expanduser("~/.cache/fidetype-ci/kt-semg"))
    ap.add_argument("--work", default="kt-lsl-replay.work")
    ap.add_argument("--speed", type=float, default=4.0, help="replay speed (default 4: about 20 s per pass)")
    ap.add_argument("--fetch-only", action="store_true")
    a = ap.parse_args()
    say(ATTRIBUTION)
    cache, work = Path(a.cache), Path(a.work)
    fetch(cache)
    if a.fetch_only:
        return 0
    work.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    model_dir = work / "model"
    run([py, "-m", "fidetype", "live", "train-kt", "--data", str(cache), "--out", str(model_dir),
         "--fit-run", "run3", "--guard-run", "run3", "--guard-chunk-keys", "5"], stdout=subprocess.DEVNULL)
    res = {t: replay_and_decode(py, cache, model_dir, work, t, a.speed) for t in ("markers", "detect")}
    say("PASS " + json.dumps(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
