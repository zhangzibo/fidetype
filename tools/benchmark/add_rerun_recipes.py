r"""Add the rerun recipe (P13-06, docs/hub-design.md section 5) to every committed leaderboard score card.

New cards get the recipe from the scorer itself (``fidetype.benchmark.scorecard.score``). The cards that
existed before P13-06 were made by experiment scripts. This tool writes, for each of them, the exact pipeline
that made it: the truth step, the build step (experiment stage) and the score step, with ``<placeholders>``
for local paths, plus ``code_ref`` = the last commit that changed the card. It changes no other field: the
card is re-serialised in the scorer format (``indent=1``) and every other key keeps its value and order.

    .venv\Scripts\python.exe -I tools/benchmark/add_rerun_recipes.py            # dry run: print a summary
    .venv\Scripts\python.exe -I tools/benchmark/add_rerun_recipes.py --write    # update the cards

A card that already has a ``rerun`` block is left as it is (use ``--force`` to rebuild it).

P13-11 (gap 83) adds two modes. Both change only the ``rerun`` block, and the tool checks that key by key:

    .venv\Scripts\python.exe -I tools/benchmark/add_rerun_recipes.py --fill [--runs <runs>] --write
    .venv\Scripts\python.exe -I tools/benchmark/add_rerun_recipes.py --halluc [--runs <runs>] --write

``--fill`` writes the decoder weights SHA-256 and the frozen policy ``config_id`` into the existing recipes of
the leaderboard cards, or an explicit reason when no value exists (never a bare null). The weights stay outside
the repository: :data:`WEIGHTS` records their SHA-256 (cross-checked with the decode records and the
pre-registration); ``--runs <runs>`` hashes the local files again, read only, and stops on a difference. The
config ids come from the committed guard files and results of the build experiments (a guard file is loaded and
its id recomputed). ``--halluc`` adds a recipe to every hallucination score card
(``benchmark/results/halluc-v0.*/*.card.json``): level ``rescore`` from the committed outcomes file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fidetype.benchmark.hub.recipe import (card_json, check_recipe, make_halluc_recipe, make_recipe,  # noqa: E402
                                           score_command)

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


def code_ref(path: Path, before: str = "P13-06") -> str | None:
    r = subprocess.run(["git", "log", "-1", "--format=%h", "--", str(path.relative_to(REPO))], cwd=REPO,
                       capture_output=True, text=True)
    h = r.stdout.strip()
    return f"git {h} (last commit that changed this card before {before})" if h else None


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


# --- P13-11: weights SHA-256 and policy config_id (value or reason) ------------------------------------------

AMENDED = "2026-11-19, P13-11: decoder weights SHA-256 and policy config_id (tools/benchmark/add_rerun_recipes.py --fill)"

#: SHA-256 of the local decoder weights (``<runs>`` = the local runs folder; never in git). Cross-checks:
#: t12-v2 = the pre-registration (experiments/2026-11-13-confirmatory-t12-v2/preregistration.md) and the
#: logprobs meta; m4-12 / m4-13 = ``checkpoint_sha256`` of the decode records. Hashed read only on 2026-11-19.
WEIGHTS = {
    "m1-09-r4b-full-medium/best.pt": "61eb7950215482a97bf2c3a8a8487948069a80d278ad8a22145a50dc4263bce7",
    "emg-toronto/calib_a/best.pt": "43bbef9c3d6a8649ce55e5706a209afcaa2c8fede1812ec385338a02d4e5b3f3",
    "emg-toronto/calib_b/best.pt": "146c23e3f873c16253a152bac62cef121600adbca57d65f2a0f4879c5370d857",
    "emg-toronto/xsession/best.pt": "4ee4bd245a3e974d6b12fefd6f2a375eceffacacca7f67fabd19dfb8e63d97f4",
    "emg-toronto/xsubject_f0/best.pt": "391f7ed4556e80512f8b563178e7a549b270cd28814f5defa91deedbded817ed",
    "emg-toronto/xsubject_f1/best.pt": "c6fa0b5b8529297bf2f881799c23ff3a8521a04be8c9509cdb58626c0e59facb",
    "emg-toronto/xsubject_f2/best.pt": "3b0c6de53e3fa56d97649297655ddf73161b6ac2a9a6301cbbcb1a62eb21ac5e",
    "emg-toronto/xsubject_f3/best.pt": "f9983ce4e44fd43be9ac75bfb8810b23b2674891eaa77ea1a1e7d0588e562d91",
    "t12-v2-final/best.pt": "5317b0600a5cbfc6679116d2c47f4da1007a1544a63962d8dbdf9308f1063787",
    "m4-12-fixed0/best.pt": "2b92ab33d12d4b887eed150b09749fec303e3286aa84e05442721444a9351fd5",
    "m4-13-long0/best.pt": "8fafe9160616815296a27cab00b16a795dbcbc56dcc52fa75c1c68e82482ac72",
}

#: card-name prefix -> weights files (one file: its SHA-256; several: the SHA-256 of the manifest).
WEIGHT_FILES = {
    "spanishbcbl-meg": ["m1-09-r4b-full-medium/best.pt"],
    "toronto-semg-composed__cnn-calib__": ["emg-toronto/calib_a/best.pt", "emg-toronto/calib_b/best.pt"],
    "toronto-semg__cnn-calib__": ["emg-toronto/calib_a/best.pt", "emg-toronto/calib_b/best.pt"],
    "toronto-semg-composed__cnn-xsession__": ["emg-toronto/xsession/best.pt"],
    "toronto-semg__cnn-xsession__": ["emg-toronto/xsession/best.pt"],
    "toronto-semg-composed__cnn-xsubject__": [f"emg-toronto/xsubject_f{k}/best.pt" for k in range(4)],
    "toronto-semg__cnn-xsubject__": [f"emg-toronto/xsubject_f{k}/best.pt" for k in range(4)],
    "b2t24-t12__t12v2__": ["t12-v2-final/best.pt"],
    "b2t25-t15__m4-12__": ["m4-12-fixed0/best.pt"],
    "b2t25-t15__m4-13__": ["m4-13-long0/best.pt"],
}

_NO_TRAINED = ("no weights: the decoder has no trained part (phoneme beam search with CMUdict and a Tatoeba word "
               "LM over the published RNN logits, CC0)")
_LDA = ("no weights file: the build step ({exp}/run.py, stage {stage}) fits the shrinkage LDA in memory from the "
        "train split and saves no file; a full rerun refits it")
#: card-name prefix -> reason why no weights SHA-256 exists.
WEIGHT_REASONS = {
    "b2t25-t15-copytask__ours__": _NO_TRAINED,
    "b2t25-t15__ours__": _NO_TRAINED,
    "b2t25-t15-copytask__published__": "weights not released by the authors (Card et al. 2024); the card scores "
                                       "the published decoder output in the CC0 dataset",
    "b2t25-t15__published__": "weights not released by the authors (Card et al. 2024); the card scores the "
                              "published decoder output in the CC0 dataset",
    "willett-hw__": "weights not released by the authors (Willett et al. 2021); the card scores the real-time RNN "
                    "output in the CC0 dataset",
    "kt-semg__": _LDA.format(exp=P602, stage="kt"),
    "emg2qwerty__": _LDA.format(exp=P602, stage="e2q"),
}

#: card-name prefix -> committed file that holds the frozen guard config (``config`` + ``sheet.config_id``) or
#: the ``config_id`` the build step logged.
CONFIG_FILES = {
    "b2t24-t12__t12v2__guard": f"{P602}/results/guard-t12.json",
    "kt-semg__lda-oracle__guard": f"{P602}/results/guard-kt.json",
    "emg2qwerty__lda-oracle__guard": f"{P602}/results/guard-e2q.json",
    "willett-hw__rnn-published__guard": f"{P602}/results/willett.json",
    "b2t25-t15__m4-12__guard": f"{P602B}/results/guard-t15-m4-12.json",
    "b2t25-t15__m4-13__guard": f"{P602B}/results/guard-t15-m4-13.json",
}

_ALWAYS = "always-commit: no trust configuration exists; every top-1 text is committed"


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:  # read only
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _weight_items(files: list[str], runs: Path | None) -> list[dict]:
    items = []
    for f in files:
        sha = WEIGHTS[f]
        if runs is not None:
            got = _sha_file(runs / f)
            if got != sha:
                raise SystemExit(f"{f}: SHA-256 {got} differs from the recorded {sha}")
        items.append({"name": f"<runs>/{f}", "sha256": sha})
    return items


def weights_value(name: str, runs: Path | None) -> dict:
    """``weights_sha256`` (+ ``weights_files``), or ``weights_sha256_reason``."""
    files = next((v for k, v in WEIGHT_FILES.items() if name.startswith(k)), None)
    if files is None:
        why = next((v for k, v in WEIGHT_REASONS.items() if name.startswith(k)), None)
        if why is None:
            raise SystemExit(f"{name}: no weights rule")
        return {"weights_sha256": None, "weights_sha256_reason": why}
    items = _weight_items(files, runs)
    if len(items) == 1:
        return {"weights_sha256": items[0]["sha256"], "weights_files": items}
    manifest = "".join(f"{i['sha256']}  {i['name']}\n" for i in sorted(items, key=lambda i: i["name"]))
    return {"weights_sha256": hashlib.sha256(manifest.encode("utf-8")).hexdigest(), "weights_files": items,
            "weights_sha256_kind": "manifest: SHA-256 of the sha256sum lines of weights_files, sorted by name"}


def config_value(card: dict, name: str) -> dict:
    """``config_id`` from the committed guard file / results, or ``config_id_reason``."""
    rel = next((v for k, v in CONFIG_FILES.items() if name.startswith(k)), None)
    if rel is not None:
        d = json.loads((REPO / rel).read_text(encoding="utf-8"))
        cid = (d.get("sheet") or {}).get("config_id") or d.get("config_id")
        if "config" in d:  # a saved guard: recompute the id from its content
            from fidetype.trust.frozen import FrozenTrustConfig

            got = FrozenTrustConfig.from_dict(d["config"]).config_id
            if got != cid:
                raise SystemExit(f"{rel}: config_id {cid} but the content gives {got}")
        return {"config_id": cid, "config_id_source": rel}
    if (card.get("guarantee") or {}).get("method") in (None, "none") and "always" in str(
            (card.get("policy") or {}).get("name", "")):
        return {"config_id": None, "config_id_reason": _ALWAYS}
    exp, stage = next(((v[0], v[1]) for k, v in V02_STAGES.items() if name.startswith(k)), (None, None))
    if exp and str(card.get("schema", "")).endswith("/0.2"):
        where = f"{exp}/run.py, stage {stage},"
    else:
        where = "the source experiment of the card (see sources)"
    return {"config_id": None,
            "config_id_reason": f"no frozen config saved: {where} fitted the trust policy (TrustPipeline) in memory "
                                "and kept only the decisions, before the cards recorded config ids; "
                                "FrozenTrustConfig.from_pipeline on a refit gives the id (gap 85, P13-13)"}


def fill_ids(card: dict, path: Path, runs: Path | None) -> dict:
    """The card's recipe with the weights SHA-256 and the policy config_id filled (value or reason)."""
    r = json.loads(json.dumps(card["rerun"]))
    dec, pol = r["decoder"], r["policy"]
    for k in ("weights_sha256", "weights_sha256_reason", "weights_files", "weights_sha256_kind"):
        dec.pop(k, None)
    head = ("name", "version", "url")
    r["decoder"] = {**{k: v for k, v in dec.items() if k in head}, **weights_value(path.stem, runs),
                    **{k: v for k, v in dec.items() if k not in head}}
    for k in ("config_id", "config_id_reason", "config_id_source"):
        pol.pop(k, None)
    r["policy"] = {**{k: v for k, v in pol.items() if k == "name"}, **config_value(card, path.stem),
                   **{k: v for k, v in pol.items() if k != "name"}}
    r["amended"] = AMENDED
    return r


# --- P13-11: hallucination score cards --------------------------------------------------------------------

HALLUC_RECORDED = "2026-11-19, backfill by P13-11 (tools/benchmark/add_rerun_recipes.py --halluc)"
_T12 = {"name": "t12-v2 GRU + word LM (ours)", "version": "5317b0600a5c",
        "url": "experiments/2026-11-13-confirmatory-t12-v2",
        "training_data": ["b2t24-t12 train split (train blocks of the train partition)"], "files": ["t12-v2-final/best.pt"]}
_M412 = {"name": "M4-12 causal T15 GRU-CTC + phoneme-to-word decoder (ours)", "version": "m4-12",
         "url": "experiments/2026-11-14-m4-12-decoder-retrain",
         "training_data": ["B2T '25 HDF5 train partition (CC0)"], "files": ["m4-12-fixed0/best.pt"]}
_M413 = {"name": "M4-13 causal T15 GRU-CTC + phoneme-to-word decoder (ours)", "version": "m4-13",
         "url": "experiments/2026-11-15-m4-13-long-train",
         "training_data": ["B2T '25 HDF5 train partition (CC0)"], "files": ["m4-13-long0/best.pt"]}


def halluc_decoder(card: dict, runs: Path | None) -> tuple[str, dict]:
    """(data track, decoder block) of a hallucination card. T12 = the T12 v2 decoder (its logprobs meta pins the
    checkpoint SHA-256); T15 = M4-12 fixed0 (P15-05 / P15-06 / P15-07 read its logprobs; the decode record pins the
    SHA-256), or M4-13 long0 for the ``m4-13-*`` systems (F2 reruns)."""
    ds, system = card["dataset"], card["system"]
    if ds == "b2t24-t12-test":
        track, d = "b2t24-t12", _T12
    elif ds == "b2t25-t15-val-eval":
        track, d = "b2t25-t15", _M413 if system.startswith("m4-13-") else _M412
    else:
        raise SystemExit(f"unknown hallucination dataset {ds!r}")
    items = _weight_items(d["files"], runs)
    return track, {"name": d["name"], "version": d["version"], "url": d["url"], "weights_sha256": items[0]["sha256"],
                   "weights_files": items, "training_data": d["training_data"]}


def halluc_json(card: dict) -> str:
    """Serialise a hallucination card as its scorer writes it (``indent=1``, LF, final newline)."""
    return json.dumps(card, indent=1, ensure_ascii=False) + "\n"


def halluc_main(write: bool, force: bool, runs: Path | None) -> int:
    n = 0
    for p in sorted((REPO / "benchmark" / "results").glob("halluc-v0.*/*.card.json")):
        text = p.read_text(encoding="utf-8").replace("\r\n", "\n")
        card = json.loads(text)
        if "rerun" in card and not force:
            continue
        base = {k: v for k, v in card.items() if k != "rerun"}
        old_ref = (card.get("rerun") or {}).get("code_ref")  # --force: keep the commit that made the card
        if "rerun" not in card and halluc_json(base) != text:
            raise SystemExit(f"{p.name}: the card does not re-serialise to its own bytes")
        oc = (card.get("meta") or {}).get("outcomes_file") or p.relative_to(REPO).as_posix().replace(
            ".card.json", ".outcomes.json")
        if not (REPO / oc).is_file():
            raise SystemExit(f"{p.name}: outcomes file {oc} not found")
        track, dec = halluc_decoder(card, runs)
        card["rerun"] = make_halluc_recipe(card, card_rel=p.relative_to(REPO).as_posix(), outcomes_rel=oc,
                                           track=track, decoder=dec, code_ref=old_ref or code_ref(p, "P13-11"),
                                           recorded=HALLUC_RECORDED)
        errs = check_recipe(card["rerun"])
        if errs:
            raise SystemExit(f"{p.name}: {errs}")
        if {k: v for k, v in card.items() if k != "rerun"} != base:
            raise SystemExit(f"{p.name}: a field other than rerun changed")
        n += 1
        print(f"{p.parent.name}/{p.name}: {card['rerun']['policy']['config_id']}, {dec['version']}")
        if write:
            p.write_bytes(halluc_json(card).encode("utf-8"))
    print(f"{n} hallucination card(s) {'updated' if write else 'to update (dry run; add --write)'}")
    return 0


def fill_main(write: bool, runs: Path | None) -> int:
    n, filled = 0, {"weights": 0, "weights_reason": 0, "config": 0, "config_reason": 0}
    w_keys = {"weights_sha256", "weights_sha256_reason", "weights_files", "weights_sha256_kind"}
    c_keys = {"config_id", "config_id_reason", "config_id_source"}
    for folder in ("v0.1", "v0.2"):
        for p in sorted((REPO / "benchmark" / "results" / folder).glob("*.json")):
            card = json.loads(p.read_text(encoding="utf-8"))
            old = card["rerun"]
            new = fill_ids(card, p, runs)
            errs = check_recipe(new)
            if errs:
                raise SystemExit(f"{p.name}: {errs}")
            # key by key: only the weights fields, the policy config fields and "amended" may change
            bad = sorted(k for k in set(old) | set(new)
                         if k not in ("decoder", "policy", "amended") and old.get(k) != new.get(k))
            for blk, keys in (("decoder", w_keys), ("policy", c_keys)):
                o, nw = old.get(blk) or {}, new.get(blk) or {}
                bad += [f"{blk}.{k}" for k in sorted(set(o) | set(nw)) if k not in keys and o.get(k) != nw.get(k)]
            if bad:
                raise SystemExit(f"{p.name}: recipe keys changed that must not change: {bad}")
            out = dict(card, rerun=new)
            if card_json({k: v for k, v in out.items() if k != "rerun"}) != card_json(
                    {k: v for k, v in card.items() if k != "rerun"}):
                raise SystemExit(f"{p.name}: a field other than rerun changed")
            filled["weights" if new["decoder"]["weights_sha256"] else "weights_reason"] += 1
            filled["config" if new["policy"]["config_id"] else "config_reason"] += 1
            n += 1
            print(f"{folder}/{p.name}: weights {str(new['decoder']['weights_sha256'])[:12]}, "
                  f"config {new['policy']['config_id']}")
            if write and new != old:
                p.write_bytes(card_json(out).encode("utf-8"))
    print(f"{n} card(s) {'filled' if write else 'to fill (dry run; add --write)'}: {filled}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--fill", action="store_true", help="P13-11: weights SHA-256 and policy config_id (or reason)")
    ap.add_argument("--halluc", action="store_true", help="P13-11: recipes for the hallucination score cards")
    ap.add_argument("--runs", default=None, help="local runs folder: hash the weights again (read only)")
    a = ap.parse_args(argv)
    runs = Path(a.runs) if a.runs else None
    if a.fill:
        return fill_main(a.write, runs)
    if a.halluc:
        return halluc_main(a.write, a.force, runs)
    n = 0
    for folder, fn in (("v0.1", v01_recipe), ("v0.2", v02_recipe)):
        for p in sorted((REPO / "benchmark" / "results" / folder).glob("*.json")):
            text = p.read_text(encoding="utf-8").replace("\r\n", "\n")
            card = json.loads(text)
            if "rerun" in card and not a.force:
                continue
            before = card_json({k: v for k, v in card.items() if k != "rerun"})
            old_ref = (card.get("rerun") or {}).get("code_ref")
            card["rerun"] = fn(card, p)
            if old_ref:  # --force: keep the commit that made the card, not the backfill commit
                card["rerun"]["code_ref"] = old_ref
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
