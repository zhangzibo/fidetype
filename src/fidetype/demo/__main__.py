"""``fidetype demo`` / ``python -m fidetype.demo``: the offline trust-layer demo.

::

    fidetype demo                      # live terminal demo (about 30 s at speed 4)
    fidetype demo --fast               # no waiting
    fidetype demo --html demo.html     # also write the static page (open it in a browser)
    fidetype demo --json log.json      # also write the decision log
    fidetype demo --write-streams DIR  # write the session streams as .jsonl (for replay or LSL)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Sequence, TextIO

from fidetype import demo

_COLORS = {"COMMIT": "32", "OFFER": "33", "OFFER_WORDS": "33", "ASK": "36", "ABSTAIN": "31", "dim": "2", "bold": "1"}
_OUTCOME_TEXT = {
    "commit-correct": "typed, correct",
    "commit-wrong": "typed, WRONG",
    "offer-hit": "offered; the intended text is in the offer",
    "offer-miss": "offered; the user rejects it",
    "abstain": "nothing typed",
}


class _Out:
    def __init__(self, stream: TextIO, color: bool) -> None:
        self.s = stream
        self.color = color

    def c(self, text: str, key: str) -> str:
        return f"\x1b[{_COLORS[key]}m{text}\x1b[0m" if self.color and key in _COLORS else text

    def line(self, text: str = "") -> None:
        self.s.write(text + "\n")
        self.s.flush()


def _clip(text: str, n: int = 52) -> str:
    return text if len(text) <= n else text[: n - 3] + "..."


def _use_color(flag: bool | None, stream: TextIO) -> bool:
    if flag is not None:
        return flag
    if os.environ.get("NO_COLOR") or not hasattr(stream, "isatty") or not stream.isatty():
        return False
    if os.name == "nt":
        os.system("")  # enables ANSI escape codes in the Windows console
    return True


def _write_streams(out_dir: Path) -> list[Path]:
    from fidetype.conformance.io import write_jsonl

    out_dir.mkdir(parents=True, exist_ok=True)
    texts = demo.demo_phrases()
    paths = []
    for k, cond in enumerate(demo.SESSION):
        p = out_dir / f"demo-{k:02d}-{cond}.jsonl"
        write_jsonl(demo.make_stream(texts[k], cond, seed=5000 + k), p)
        paths.append(p)
    cfg_path = out_dir / "trust-config-demo.json"
    demo.load_config().save(cfg_path)
    return paths + [cfg_path]


def run_terminal(args: argparse.Namespace, out: _Out) -> dict[str, Any]:
    cfg = demo.load_config()
    pol = cfg.policy
    out.line(out.c("Fidetype demo: the trust layer on synthetic decoder streams (offline, no participant data)", "bold"))
    out.line(f"config {cfg.config_id}: COMMIT if p >= {pol['commit_p']:.2f} and guard risk <= {pol['commit_max_risk']:.2f}; "
             f"ABSTAIN if guard risk >= {pol['abstain_risk']:.2f}; else OFFER (the user confirms).")
    out.line(out.c("Baseline 'always commit' types the top-1 text every time.", "dim"))
    utts = []
    start = time.monotonic()
    for u in demo.iter_session(cfg, partial_every_frames=args.partial_every):
        utts.append(u)
        out.line()
        target = f'"{u["truth"]}"' if u["truth"] else "(no intended text: the user is not typing)"
        out.line(out.c(f"[{u['k'] + 1:02d}] {u['label']}", "bold") + f"   intended: {target}")
        last = None
        for pv in u["previews"]:
            if not args.fast:
                due = start + (u["t0"] + pv["t"]) / args.speed
                time.sleep(max(0.0, due - time.monotonic()))
            text = _clip(pv["top1"])
            if text != last:
                out.line(out.c(f"   t={pv['t']:5.1f}s  preview  \"{text}\"  p={pv['p_top1']:.2f} risk={pv['guard_risk']:.2f}",
                               "dim"))
                last = text
        if not args.fast:
            due = start + (u["t0"] + u["duration"]) / args.speed
            time.sleep(max(0.0, due - time.monotonic()))
        f = u["final"]
        shown = f'"{_clip(f["shown"][0])}"' if f["shown"] else ""
        out.line(f"   t={u['duration']:5.1f}s  " + out.c(f"FINAL {f['action']:<7}", f["action"])
                 + f" {shown}  p={f['p_top1']:.2f} risk={f['guard_risk']:.2f}  ({f['reason']})")
        b = u["baseline"]
        mark = out.c("WRONG", "ABSTAIN") if b["outcome"] == "commit-wrong" else "correct"
        out.line(f"            -> {_OUTCOME_TEXT[f['outcome']]}.  always commit: \"{_clip(b['text'], 40)}\" ({mark})")
    return {"utterances": utts}


def print_totals(totals: dict[str, Any], out: _Out) -> None:
    out.line()
    n = next(iter(totals.values()))["n"] if totals else 0
    out.line(out.c(f"Totals over {n} other phrases per condition (wrong commits / phrases)", "bold"))
    out.line(f"  {'condition':<36}{'trust: commit':>14}{'trust: wrong':>14}{'always commit: wrong':>22}")
    for v in totals.values():
        out.line(f"  {v['label']:<36}{v['trust_commit_rate']:>14.3f}{v['trust_wrong_commit_rate']:>14.3f}"
                 f"{v['always_commit_wrong_commit_rate']:>22.3f}")
    ns = totals.get("no-signal")
    if ns:
        c = ns["trust"]["commit-correct"] + ns["trust"]["commit-wrong"]
        out.line()
        b = round(ns["always_commit_wrong_commit_rate"] * ns["n"])
        out.line(out.c(f"No signal: the trust layer typed {c}/{ns['n']} times; always commit typed "
                       f"{b}/{ns['n']} wrong texts.", "bold"))


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fidetype demo", description="Offline demo of the Fidetype trust layer "
                                 "(synthetic decoder streams; nothing leaves your computer).")
    ap.add_argument("--speed", type=float, default=4.0, help="replay speed (1 = real time; default 4)")
    ap.add_argument("--fast", action="store_true", help="do not wait: print all decisions at once")
    ap.add_argument("--totals", type=int, default=40, metavar="N",
                    help="phrases per condition for the totals table (0: skip; default 40)")
    ap.add_argument("--partial-every", type=int, default=25, metavar="FRAMES",
                    help="a provisional decision every N frames (default 25 = 1 s)")
    ap.add_argument("--html", type=Path, help="write the static demo page to this file")
    ap.add_argument("--json", type=Path, help="write the decision log (JSON) to this file")
    ap.add_argument("--write-streams", type=Path, metavar="DIR",
                    help="write the session streams (.jsonl) and the config to DIR, then exit")
    ap.add_argument("--color", dest="color", action="store_true", default=None, help="force colours")
    ap.add_argument("--no-color", dest="color", action="store_false", help="no colours")
    a = ap.parse_args(argv)
    if a.speed <= 0:
        ap.error("--speed must be positive")
    out = _Out(sys.stdout, _use_color(a.color, sys.stdout))
    if a.write_streams:
        for p in _write_streams(a.write_streams):
            out.line(str(p))
        out.line(f"Replay: fidetype trust --config {a.write_streams / 'trust-config-demo.json'} --decoder demo "
                 f"--max-attempts 1 {a.write_streams / 'demo-04-no-signal.jsonl'}")
        return 0
    log = demo.log_header(demo.load_config(), a.partial_every) | run_terminal(a, out)
    if a.totals:
        out.line()
        out.line(out.c(f"Computing totals ({a.totals} phrases x {len(demo.CONDITIONS)} conditions) ...", "dim"))
        log["totals"] = demo.run_totals(a.totals)
        print_totals(log["totals"], out)
    else:
        log["totals"] = {}
    from fidetype import __version__

    log["fidetype_version"] = __version__
    if a.json:
        a.json.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        out.line(f"decision log: {a.json}")
    if a.html:
        from fidetype.demo.page import render

        a.html.write_text(render(log), encoding="utf-8")
        out.line(f"demo page: {a.html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
