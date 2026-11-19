r"""Add the rerun recipe (P13-06, docs/hub-design.md section 5) to every committed leaderboard score card.

New cards get the recipe from the scorer itself (``fidetype.benchmark.scorecard.score``). The cards that
existed before P13-06 were made by experiment scripts. This tool writes, for each of them, the exact pipeline
that made it: the truth step, the build step (experiment stage) and the score step, with ``<placeholders>``
for local paths, plus ``code_ref`` = the last commit that changed the card. It changes no other field: the
card is re-serialised in the scorer format (``indent=1``) and every other key keeps its value and order.

    .venv\Scripts\python.exe -I tools/benchmark/add_rerun_recipes.py            # dry run: print a summary
    .venv\Scripts\python.exe -I tools/benchmark/add_rerun_recipes.py --write    # update the cards

A card that already has a ``rerun`` block is left as it is (use ``--force`` to rebuild it).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fidetype.benchmark.hub.recipe import card_json, check_recipe, make_recipe, score_command  # noqa: E402

RECORDED = "2026-11-18, backfill by P13-06 (tools/benchmark/add_rerun_recipes.py)"
P602 = "experiments/2026-11-16-p6-02-scorer"
P602B = "experiments/2026-11-17-p6-02b-v02-entries"

#: v0.2 card name prefix -> (experiment folder, build stage of its run.py)
V02_STAGES = {
    "b2t25-t15__ours__": (P602B, "b2t"),
    "b2t25-t15__published__": (P602B, "b2t"),
    "b2t25-t15__m4-12__": (P602B, "t15-m4-12"),
    "b2t25-t15__m4-13__": (P602B, "t15-m4-13"),
    "spanishbcbl-meg__": (P602B, "meg"),
    "toronto-semg__": (P602B, "toronto"),
    "b2t24-t12__": (P602, "t12"),
    "willett-hw__": (P602, "willett"),
    "kt-semg__": (P602, "kt"),
    "emg2qwerty__": (P602, "e2q"),
}

TRUTH_EXTRA = {"toronto-semg": " --cache <window cache> --sentences <eng_tatoeba_heldout.txt>"}


def code_ref(path: Path) -> str | None:
    r = subprocess.run(["git", "log", "-1", "--format=%h", "--", str(path.relative_to(REPO))], cwd=REPO,
                       capture_output=True, text=True)
    h = r.stdout.strip()
    return f"git {h} (last commit that changed this card before P13-06)" if h else None


def v02_recipe(card: dict, path: Path) -> dict:
    name, track = path.stem, card["track"]
    exp, stage = next(v for k, v in V02_STAGES.items() if name.startswith(k))
    der = f"<derived>/{Path(exp).name.split('-', 3)[-1]}"
    truth = f"{der}/truth/{track}.jsonl"
    ci = card.get("ci") or {}
    score = score_command(track, B=ci.get("B", 2000), seed=ci.get("seed", 0),
                          out=f"benchmark/results/v0.2/{path.name}")
    score = score.replace("<submission>", f"{der}/submissions/{name}").replace("<truth.jsonl>", truth)
    steps = [
        {"step": "truth", "command": f"python -m fidetype.benchmark truth {track} --data <data>"
                                     f"{TRUTH_EXTRA.get(track, '')} --out {truth}"},
        {"step": "build", "command": f"python -I {exp}/run.py {stage}"},
        {"step": "score", "command": score},
    ]
    inputs = {"outputs": f"submission folder {der}/submissions/{name} (decoded text; local only, never in git, "
                         "hub decision Q3)",
              "build": f"the build step reads local decoder outputs; see {exp}/results.md",
              "derived": "<derived> = the local folder for per-unit files (never in git)"}
    return make_recipe(card, command=score, level="rescore", steps=steps, inputs=inputs, code_ref=code_ref(path),
                       recorded=RECORDED)


def v01_recipe(card: dict, path: Path) -> dict:
    track = card["track"]
    steps = [
        {"step": "truth", "command": f"python -m fidetype.benchmark prepare {track} --data <data> "
                                     f"--out <truth-dir>/{track}.jsonl"},
        {"step": "build", "command": "python -I tools/benchmark/import_baselines.py --truth-dir <truth-dir> "
                                     "--stream-result <b2t25-published-result.json>"},
        {"step": "controls", "command": "python -I experiments/2026-11-16-p6-01-tracks/update_results.py"},
        {"step": "safe-wpm", "command": "python -I experiments/2026-11-16-p14-05-safe-wpm/run.py tracks"},
    ]
    cmd = " && ".join(s["command"] for s in steps[1:])
    how = {"committed-aggregate": "aggregate numbers are copied from committed results; the command rebuilds "
                                  "the card but does not recompute them",
           "committed-per-trial": "the scorer recomputes the metrics from committed per-trial arrays",
           "stream-submission": "the scorer reads a local NTS stream submission (816 files, never in git)"}
    inputs = {"sources": "; ".join(card.get("sources") or []),
              "how": how.get(card.get("scored_from"), str(card.get("scored_from")))}
    return make_recipe(card, command=cmd, level="rescore", steps=steps, inputs=inputs, code_ref=code_ref(path),
                       recorded=RECORDED)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    n = 0
    for folder, fn in (("v0.1", v01_recipe), ("v0.2", v02_recipe)):
        for p in sorted((REPO / "benchmark" / "results" / folder).glob("*.json")):
            text = p.read_text(encoding="utf-8").replace("\r\n", "\n")
            card = json.loads(text)
            if "rerun" in card and not a.force:
                continue
            before = card_json({k: v for k, v in card.items() if k != "rerun"})
            card["rerun"] = fn(card, p)
            errs = check_recipe(card["rerun"])
            if errs:
                raise SystemExit(f"{p.name}: {errs}")
            if card_json({k: v for k, v in card.items() if k != "rerun"}) != before:
                raise SystemExit(f"{p.name}: a field other than rerun changed")
            n += 1
            print(f"{folder}/{p.name}: level {card['rerun']['level']}, {card['rerun'].get('code_ref')}")
            if a.write:
                p.write_bytes(card_json(card).encode("utf-8"))
    print(f"{n} card(s) {'updated' if a.write else 'to update (dry run; add --write)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
