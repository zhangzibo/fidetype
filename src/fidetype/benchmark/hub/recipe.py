"""Rerun recipes for score cards (roadmap P13-06, design ``docs/hub-design.md`` section 5).

A rerun recipe is a small JSON block (key ``rerun``) in a score card. It names every versioned input of the
number: the registry dataset entry, the track and its split digest, the adapter (module, package version,
SHA-256 of the source; rule RA-9), the decoder, the trust policy, the scorer and metric versions, and the exact
command lines with ``<placeholders>`` for local paths. It holds no text from the data and no local path.

::

    from fidetype.benchmark.hub.recipe import make_recipe, check_recipe, recipe_text

Standard library only, except :func:`rescore`, which imports the scorer.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

RECIPE_SCHEMA = "fidetype.hub.recipe/0.1"
LEVELS = ("rescore", "replay", "full")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CONFIG_ID = re.compile(r"^tcfg-[0-9a-f]{16}$")
_SPLIT_VERSION = re.compile(r"^(tracks|halluc)-v\d+\.\d+$")
#: Default reasons when a new card does not give the value (P13-11: a recipe holds a value or a reason, never a
#: bare null).
NO_WEIGHTS_GIVEN = ("not given: the scorer reads only the decoded outputs; the submitter adds the weights SHA-256 "
                    "(or the reason) to the card's decoder block")
NO_CONFIG_GIVEN = ("not given: the submission names no frozen trust config; the submitter adds the config_id "
                   "(or the reason) to the card's policy block")
_MODULE = re.compile(r"(fidetype(?:\.[A-Za-z_][A-Za-z0-9_]*)+)")
#: The local inputs of a ``rescore`` recipe. Neither goes into git (hub decision Q3; NTS leakage rule).
RESCORE_INPUTS = {"outputs": "the submission folder (decoded text; never in git, hub decision Q3)",
                  "truth": "local truth file from `python -m fidetype.benchmark truth <track> --data <data> "
                           "--out <truth.jsonl>` (never in git)"}
_REQUIRED = ("schema", "level", "dataset", "track", "adapter", "decoder", "policy", "scorer", "versions", "command")


def package_version() -> str:
    from fidetype import __version__

    return __version__


def source_sha256(path: str | Path) -> str:
    """SHA-256 of a source file with line ends made LF (so a Windows and a Linux checkout give one hash)."""
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def adapter_id(module: str) -> dict[str, Any]:
    """Rule RA-9: module name, package version and SHA-256 of the module source. The module is not imported."""
    spec = importlib.util.find_spec(module)
    if spec is None or not spec.origin or not spec.origin.endswith(".py"):
        raise LookupError(f"no Python source for adapter module {module!r}")
    return {"module": module, "package_version": package_version(), "sha256": source_sha256(spec.origin)}


def adapter_module_for(track: str) -> str | None:
    """The adapter module of a track: the hub registry entry first, else the ``adapter`` field of ``tracks.py``."""
    d = dataset_for_track(track)
    if d and d.get("adapters"):
        return str(d["adapters"][0]["module"])
    try:
        from fidetype.benchmark.tracks import TRACKS
    except ImportError:  # pragma: no cover - numpy missing
        return None
    t = TRACKS.get(track)
    m = _MODULE.search(t.adapter) if t is not None else None
    parts = m.group(1).split(".") if m else []
    while len(parts) > 1:  # "fidetype.benchmark.tracks.t12_trial_features" -> the module "fidetype.benchmark.tracks"
        try:
            if importlib.util.find_spec(".".join(parts)) is not None:
                return ".".join(parts)
        except (ImportError, ValueError):
            pass
        parts.pop()
    return None


def dataset_for_track(track: str) -> dict[str, Any] | None:
    """The newest hub registry entry that lists ``track``, or None (dataset not yet in the hub)."""
    from fidetype.benchmark import hub

    ds = hub.load_registry()["datasets"]
    hits = [d for d in ds if any(t.get("track") == track for t in d.get("tracks", []))]
    if not hits:  # a v0.1 track: same dataset files, older split (fidetype.benchmark.registry)
        from fidetype.benchmark.registry import TRACKS as V01

        if track in V01:
            hits = [d for d in ds if d["id"] == V01[track].dataset]
    return hits[-1] if hits else None


def _dataset_block(track: str) -> tuple[dict[str, Any] | None, str | None]:
    d = dataset_for_track(track)
    if d is not None:
        return {"id": d["id"], "version": d["version"], "revision": d["revision"]}, None
    try:
        from fidetype.benchmark.tracks import TRACKS

        t = TRACKS.get(track)
    except ImportError:  # pragma: no cover
        t = None
    if t is not None:
        return None, f"dataset {t.dataset!r} is not yet in the hub registry (gap 79, P13-07); source: {t.url}"
    return None, "dataset not known to the hub registry or to tracks v0.2"


def _split_digest(card: Mapping[str, Any]) -> tuple[str | None, str]:
    """The split digest: the v0.2 entries digest from the card, else the SHA-256 of the v0.1 split file (LF)."""
    d = (card.get("track_info") or {}).get("split_digest")
    if d:
        return d, "entries"
    from importlib import resources

    f = resources.files("fidetype.benchmark").joinpath("splits", "v0.1", f"{card.get('track')}.json")
    if f.is_file():
        return hashlib.sha256(f.read_bytes().replace(b"\r\n", b"\n")).hexdigest(), "file-sha256"
    return None, "none"


def _split_version(card: Mapping[str, Any]) -> str:
    return "tracks-v0.2" if str(card.get("schema", "")).endswith("/0.2") else "tracks-v0.1"


def make_recipe(card: Mapping[str, Any], *, command: str, level: str = "rescore",
                steps: Sequence[Mapping[str, str]] | None = None, inputs: Mapping[str, str] | None = None,
                code_ref: str | None = None, recorded: str | None = None,
                adapter_module: str | None = None, weights_sha256: str | None = None,
                weights_reason: str | None = None, weights_files: Sequence[Mapping[str, Any]] | None = None,
                policy_config_id: str | None = None, config_id_reason: str | None = None) -> dict[str, Any]:
    """Build the rerun recipe (design section 5.1) of one score card.

    ``command`` is the exact command line that gives the card from local inputs (``<placeholders>`` for local
    paths). ``steps`` lists the full pipeline (truth, build, score) when more than one command is needed.

    The decoder weights SHA-256 and the policy ``config_id`` are a value or a reason (P13-11): with no value,
    the recipe gets ``weights_sha256_reason`` / ``config_id_reason`` (a default reason when none is given).
    """
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}")
    track = str(card.get("track"))
    ds, ds_note = _dataset_block(track)
    module = adapter_module or adapter_module_for(track)
    try:
        adapter = adapter_id(module) if module else None
    except LookupError:
        adapter = None
    dec = card.get("decoder") or {}
    pol = card.get("policy") or {}
    sw = card.get("safe_wpm") or {}
    ci = card.get("ci") or {}
    digest, digest_kind = _split_digest(card)
    metrics: dict[str, Any] = {}
    if sw.get("definition"):
        metrics["safe_wpm"] = sw["definition"]
    sha = weights_sha256 or dec.get("weights_sha256")
    cid = policy_config_id or pol.get("config_id")
    decoder: dict[str, Any] = {"name": dec.get("name"), "version": dec.get("version"), "url": dec.get("url"),
                               "weights_sha256": sha, "training_data": dec.get("training_data")}
    if not sha:
        decoder["weights_sha256_reason"] = weights_reason or NO_WEIGHTS_GIVEN
    if weights_files:
        decoder["weights_files"] = [dict(f) for f in weights_files]
    policy: dict[str, Any] = {"name": pol.get("name"), "config_id": cid,
                              "guarantee": (card.get("guarantee") or {}).get("method")}
    if not cid:
        policy["config_id_reason"] = config_id_reason or NO_CONFIG_GIVEN
    r: dict[str, Any] = {
        "schema": RECIPE_SCHEMA,
        "level": level,
        "dataset": ds,
        **({"dataset_note": ds_note} if ds_note else {}),
        "track": {"track": track, "split_version": _split_version(card), "digest": digest,
                  "digest_kind": digest_kind},
        "adapter": adapter,
        "decoder": decoder,
        "policy": policy,
        # v0.1 cards have no scorer_version field: the benchmark version names their scorer.
        "scorer": {"scorer_version": card.get("scorer_version") or f"benchmark-{card.get('benchmark_version')}",
                   "metrics": metrics,
                   "B": ci.get("B"), "seed": ci.get("seed")},
        "versions": {"fidetype": package_version(), "benchmark": card.get("benchmark_version"),
                     "python": f"{sys.version_info.major}.{sys.version_info.minor}"},
        "command": command,
    }
    if steps:
        r["steps"] = [dict(s) for s in steps]
    if inputs:
        r["inputs"] = dict(inputs)
    if code_ref:
        r["code_ref"] = code_ref
    if recorded:
        r["recorded"] = recorded
    return r


def halluc_split_file(dataset: str, split_version: str = "halluc-v0.1") -> Path | None:
    """The committed hallucination split file of ``dataset`` (``splits/halluc-v0.1/<dataset>.json``)."""
    from importlib import resources

    f = resources.files("fidetype.benchmark").joinpath("splits", split_version, f"{dataset}.json")
    return Path(str(f)) if f.is_file() else None


def make_halluc_recipe(card: Mapping[str, Any], *, card_rel: str, outcomes_rel: str, track: str,
                       decoder: Mapping[str, Any], code_ref: str | None = None, recorded: str | None = None,
                       split_version: str = "halluc-v0.1") -> dict[str, Any]:
    """The rerun recipe of one hallucination score card (P13-11).

    Level ``rescore``: ``python -m fidetype.benchmark.hallucination rescore`` recomputes the card from the
    committed outcomes file (flags only, no text) and ``--check`` compares it with the card (the ``rerun``
    block is left out of the comparison). ``card_rel`` and ``outcomes_rel`` are repository-relative paths.
    ``track`` is the leaderboard track of the held-out data (it names the hub dataset entry). ``decoder``
    holds ``name``, ``version``, ``url``, ``training_data`` and the weights SHA-256 (or the reason).
    """
    dataset = str(card.get("dataset"))
    protocol = str(card.get("protocol"))
    rules = card.get("rules") or {}
    meta = card.get("meta") or {}
    split = halluc_split_file(dataset, split_version)
    digest = hashlib.sha256(split.read_bytes().replace(b"\r\n", b"\n")).hexdigest() if split else None
    ds, ds_note = _dataset_block(track)
    cmd = (f"python -m fidetype.benchmark.hallucination rescore {outcomes_rel} --protocol {protocol}"
           f" --alpha-wrong {rules.get('alpha_wrong')} --alpha-fluent {rules.get('alpha_fluent')} --check {card_rel}")
    dec = dict(decoder)
    sha = dec.get("weights_sha256")
    d_block: dict[str, Any] = {"name": dec.get("name"), "version": dec.get("version"), "url": dec.get("url"),
                               "weights_sha256": sha, "training_data": dec.get("training_data")}
    if not sha:
        d_block["weights_sha256_reason"] = dec.get("weights_sha256_reason") or NO_WEIGHTS_GIVEN
    if dec.get("weights_files"):
        d_block["weights_files"] = [dict(f) for f in dec["weights_files"]]
    cid = meta.get("guard_config_id")
    p_block: dict[str, Any] = {"name": card.get("system"), "config_id": cid, "guarantee": "ltt",
                               "description": meta.get("description")}
    if not cid:
        p_block["config_id_reason"] = NO_CONFIG_GIVEN
    r: dict[str, Any] = {
        "schema": RECIPE_SCHEMA,
        "level": "rescore",
        "dataset": ds,
        **({"dataset_note": ds_note} if ds_note else {}),
        "track": {"track": f"halluc/{dataset}", "split_version": split_version, "digest": digest,
                  "digest_kind": "file-sha256" if digest else "none", "data_track": track},
        "adapter": None,
        "decoder": d_block,
        "policy": p_block,
        "scorer": {"scorer_version": protocol, "metrics": {"halluc": protocol},
                   "fluency": (card.get("fluency") or {}).get("mode"), "B": None, "seed": meta.get("seed")},
        "versions": {"fidetype": package_version(), "benchmark": None,
                     "python": f"{sys.version_info.major}.{sys.version_info.minor}"},
        "command": cmd,
        "inputs": {"outcomes": f"{outcomes_rel} (committed; per-trial flags only, no text)",
                   "split": f"src/fidetype/benchmark/splits/{split_version}/{dataset}.json (committed; hashes only)",
                   "adapter": "none: the rescore reads the committed outcomes file, no adapter runs"},
    }
    if code_ref:
        r["code_ref"] = code_ref
    if recorded:
        r["recorded"] = recorded
    return r


def score_command(track: str, *, B: int, seed: int, out: str | None = None) -> str:
    """The v0.2 scorer command (``python -m fidetype.benchmark score``) with placeholders for local paths."""
    cmd = f"python -m fidetype.benchmark score {track} <submission> --truth <truth.jsonl> --B {B} --seed {seed}"
    return cmd + (f" --out {out}" if out else "")


def check_recipe(r: Any) -> list[str]:
    """Return the problems of one rerun recipe (an empty list = valid)."""
    if not isinstance(r, Mapping):
        return ["rerun: must be an object"]
    errs = [f"rerun.{k}: required" for k in _REQUIRED if k not in r]
    if r.get("schema") != RECIPE_SCHEMA:
        errs.append(f"rerun.schema: must be {RECIPE_SCHEMA!r}")
    if r.get("level") not in LEVELS:
        errs.append(f"rerun.level: one of {', '.join(LEVELS)}")
    if r.get("dataset") is None and not r.get("dataset_note"):
        errs.append("rerun.dataset: a registry entry, or a dataset_note that says why there is none")
    tr = r.get("track") or {}
    if not tr.get("track") or not _SPLIT_VERSION.match(str(tr.get("split_version", ""))):
        errs.append("rerun.track: needs track and split_version (tracks-vX.Y or halluc-vX.Y)")
    errs += _value_or_reason(r)
    ad = r.get("adapter")
    if ad is not None and not (str(ad.get("module", "")).startswith("fidetype.") and _SHA256.match(str(ad.get("sha256")))):
        errs.append("rerun.adapter: module (fidetype.*) and sha256 (RA-9)")
    cmd = r.get("command")
    if not (isinstance(cmd, str) and cmd.strip()):
        errs.append("rerun.command: the exact command line is required")
    # Local paths never go into a public card: commands use <placeholders>.
    for s in [cmd, *[x.get("command") for x in r.get("steps") or []]]:
        if isinstance(s, str) and re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/home/|/Users/", s):
            errs.append(f"rerun: a command holds a local path ({s[:60]}...); use <placeholders>")
    return errs


def _value_or_reason(r: Mapping[str, Any]) -> list[str]:
    """P13-11: the weights SHA-256 and the policy config_id are each a value or a reason, never both, never
    neither."""
    errs = []
    dec, pol = r.get("decoder"), r.get("policy")
    if isinstance(dec, Mapping):
        sha, why = dec.get("weights_sha256"), dec.get("weights_sha256_reason")
        if sha is not None and not _SHA256.match(str(sha)):
            errs.append("rerun.decoder.weights_sha256: 64 lower-case hex characters")
        if (sha is None) == (not (isinstance(why, str) and why.strip())):
            errs.append("rerun.decoder: weights_sha256 or weights_sha256_reason (exactly one)")
        for f in dec.get("weights_files") or []:
            if not (isinstance(f, Mapping) and f.get("name") and _SHA256.match(str(f.get("sha256")))):
                errs.append("rerun.decoder.weights_files: each item needs name and sha256")
    elif dec is not None:
        errs.append("rerun.decoder: must be an object")
    if isinstance(pol, Mapping):
        cid, why = pol.get("config_id"), pol.get("config_id_reason")
        if cid is not None and not _CONFIG_ID.match(str(cid)):
            errs.append("rerun.policy.config_id: tcfg- + 16 hex characters")
        if (cid is None) == (not (isinstance(why, str) and why.strip())):
            errs.append("rerun.policy: config_id or config_id_reason (exactly one)")
    elif pol is not None:
        errs.append("rerun.policy: must be an object")
    return errs


#: P13-13: the reasons a trust card (any policy other than always-commit) may give in place of a ``config_id``.
#: A new submission that names no config gets :data:`NO_CONFIG_GIVEN`; a card whose refit gave other decisions
#: says so. Any other reason (for example "no frozen config saved ... (gap 85)") is flagged.
TRUST_CARD_REASONS = (NO_CONFIG_GIVEN, "refit does not reproduce the card")


def is_always_commit(card: Mapping[str, Any]) -> bool:
    """True when the card's policy commits every top-1 text (no trust configuration exists)."""
    g = card.get("guarantee") or {}
    name = str((card.get("policy") or {}).get("name", "")).lower()
    return g.get("method") in (None, "none") and "always" in name


def config_id_problems(card: Mapping[str, Any], root: Any = None, card_key: str | None = None) -> list[str]:
    """Return the problems of the policy ``config_id`` of one leaderboard card (P13-13; empty list = valid).

    - ``config_id`` or ``config_id_reason``, exactly one (as :func:`check_recipe`).
    - A trust card (not always-commit) without a ``config_id`` gives one of :data:`TRUST_CARD_REASONS`.
    - With ``root`` (the repository folder): ``config_id_source`` names a committed file. If the file holds the
      frozen ``config``, its recomputed id equals ``config_id``; otherwise the file records that id. If the file
      lists the ``cards`` it backs, ``card_key`` (``"v0.x/<stem>"``) is in the list.
    """
    pol = ((card.get("rerun") or {}).get("policy")) or {}
    cid, why = pol.get("config_id"), pol.get("config_id_reason")
    has_why = isinstance(why, str) and bool(why.strip())
    if bool(cid) == has_why:
        return ["rerun.policy: config_id or config_id_reason (exactly one)"]
    errs: list[str] = []
    if cid and not _CONFIG_ID.match(str(cid)):
        errs.append("rerun.policy.config_id: tcfg- + 16 hex characters")
    if not cid and not is_always_commit(card) and not str(why).startswith(TRUST_CARD_REASONS):
        errs.append(f"rerun.policy: a trust card needs a config_id (or a reason that starts with one of "
                    f"{[r[:40] for r in TRUST_CARD_REASONS]}), not {str(why)[:60]!r}")
    if cid and root is not None:
        src = pol.get("config_id_source")
        p = Path(root) / str(src or "")
        if not src or not p.is_file():
            return errs + [f"rerun.policy.config_id_source: committed file not found ({src!r})"]
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d.get("config"), Mapping):
            from fidetype.trust.frozen import FrozenTrustConfig

            got = FrozenTrustConfig.from_dict(dict(d["config"])).config_id
            if got != cid:
                errs.append(f"rerun.policy.config_id: {cid} but the frozen config in {src} gives {got}")
        elif cid not in ((d.get("sheet") or {}).get("config_id"), d.get("config_id")):
            errs.append(f"rerun.policy.config_id: {src} does not record {cid}")
        if card_key is not None and "cards" in d and card_key not in d["cards"]:
            errs.append(f"rerun.policy.config_id_source: {src} does not list {card_key}")
    return errs


def rerun_level(card: Mapping[str, Any]) -> str:
    """``rescore`` / ``replay`` / ``full``, or ``no`` when the card has no recipe (design section 5.2)."""
    r = card.get("rerun")
    return str(r.get("level")) if isinstance(r, Mapping) and r.get("level") in LEVELS else "no"


def _value_text(block: Any, key: str, reason_key: str) -> str:
    if not isinstance(block, Mapping):
        return "none"
    v = block.get(key)
    if v:
        return f"{str(v)[:16]}..." if len(str(v)) > 24 else str(v)
    return f"none ({block.get(reason_key) or 'no reason given'})"


def recipe_text(r: Mapping[str, Any] | None) -> str:
    """A short human-readable view of a recipe."""
    if not r:
        return "rerun: no (this card has no rerun recipe)"
    ds = r.get("dataset")
    tr = r.get("track") or {}
    ad = r.get("adapter")
    sc = r.get("scorer") or {}
    lines = [f"rerun level: {r.get('level')}",
             "dataset: " + (f"{ds['id']} {ds['version']} r{ds['revision']}" if ds else str(r.get("dataset_note"))),
             f"track: {tr.get('track')} ({tr.get('split_version')}, split digest {str(tr.get('digest'))[:16]}...)",
             "adapter: " + (f"{ad['module']} {ad['package_version']} sha256 {ad['sha256'][:16]}..." if ad else "none"),
             "decoder weights: " + _value_text(r.get("decoder"), "weights_sha256", "weights_sha256_reason"),
             "policy config: " + _value_text(r.get("policy"), "config_id", "config_id_reason"),
             f"scorer: {sc.get('scorer_version')} {json.dumps(sc.get('metrics') or {})} B={sc.get('B')} seed={sc.get('seed')}"]
    if r.get("code_ref"):
        lines.append(f"code: {r['code_ref']}")
    for k, v in (r.get("inputs") or {}).items():
        lines.append(f"input {k}: {v}")
    if r.get("steps"):
        lines.append("steps:")
        lines += [f"  [{s.get('step')}] {s.get('command')}" for s in r["steps"]]
    lines.append(f"command: {r.get('command')}")
    return "\n".join(lines)


def card_json(card: Mapping[str, Any]) -> str:
    """Serialise a card as the scorer CLI writes it (``indent=1``, UTF-8, LF line ends, final newline)."""
    from fidetype.benchmark.scoring import to_jsonable

    return json.dumps(to_jsonable(card), indent=1, ensure_ascii=False) + "\n"


def rescore(card: Mapping[str, Any], submission: str | Path, truth: str | Path) -> dict[str, Any]:
    """Rerun a ``rescore``-level recipe: score ``submission`` against the local ``truth`` with the recorded
    scorer settings. Returns ``{"card": new card, "same": bool, "diff": [top-level keys that differ]}``.
    The ``rerun`` block itself is left out of the comparison."""
    from fidetype.benchmark import scorecard as SC

    r = card.get("rerun") or {}
    if r.get("level") != "rescore":
        raise ValueError(f"only rescore-level recipes rerun here (this card: {rerun_level(card)})")
    track = card["track"]
    if r.get("scorer", {}).get("scorer_version") != SC.SCORER_VERSION:
        raise ValueError(f"the card needs scorer {r['scorer'].get('scorer_version')}; installed {SC.SCORER_VERSION}")
    sc = r.get("scorer") or {}
    res = SC.score(track, Path(submission), SC.read_truth(truth, track), B=int(sc.get("B") or 2000),
                   seed=int(sc.get("seed") or 0))
    new = json.loads(card_json(res))
    old = {k: v for k, v in card.items() if k not in ("rerun", "_file")}
    new_cmp = {k: v for k, v in new.items() if k != "rerun"}
    diff = sorted(k for k in set(old) | set(new_cmp) if old.get(k) != new_cmp.get(k))
    return {"card": new, "same": not diff and card_json(old) == card_json(new_cmp), "diff": diff}


__all__ = ["RECIPE_SCHEMA", "LEVELS", "adapter_id", "adapter_module_for", "dataset_for_track", "make_recipe",
           "score_command", "check_recipe", "make_halluc_recipe", "halluc_split_file", "NO_WEIGHTS_GIVEN",
           "NO_CONFIG_GIVEN", "rerun_level", "recipe_text", "card_json", "rescore", "source_sha256"]
