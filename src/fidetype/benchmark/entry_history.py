"""Entry history of the leaderboard from git (P13-09).

Every score card is a JSON file under ``benchmark/results/``. Its history is the list of commits
that changed the file (``git log --no-renames``, newest first). For each commit the card is read
as it was at that commit (``git show <commit>:<path>``), so the history shows the date, the
split, the scorer and metric versions and the rerun level of each version. Nothing is typed by
hand.

Rules:

- No rename or copy detection: a card's history starts at the commit that added that file.
  (``git log --follow`` reports some new v0.2 cards as copies of v0.1 cards; that is wrong.)
- A card that differs from ``HEAD`` (or is not in git) gets a first row "working tree, not
  committed". The history of a committed card is fixed for a given ``HEAD``.
- Cards deleted from a results folder are listed as removed entries, with the card as it was
  before the deleting commit.
- Without git (no ``git`` program, not a repository, a shallow clone) the history is empty and
  ``available`` is False. The leaderboard then says so; it never guesses dates.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from fidetype.benchmark.hub.recipe import rerun_level

HISTORY_SCHEMA = "fidetype.benchmark.history/0.1"

# runner(args, cwd) -> stdout (str), or None when the git command fails.
Runner = Callable[[Sequence[str], Path], "str | None"]


def git_runner(args: Sequence[str], cwd: Path) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def repo_root(folder: str | Path, run: Runner = git_runner) -> Path | None:
    """The top folder of the git repository that holds ``folder``; None if there is none (or it is shallow)."""
    f = Path(folder).resolve()
    if not f.is_dir():
        return None
    top = run(["rev-parse", "--show-toplevel"], f)
    if not top:
        return None
    if (run(["rev-parse", "--is-shallow-repository"], f) or "").strip() == "true":
        return None
    return Path(top.strip()).resolve()


def _short(h: str) -> str:
    return h[:7]


def _load(text: str | None) -> dict[str, Any] | None:
    if text is None:
        return None
    try:
        d = json.loads(text)
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def version_facts(card: Mapping[str, Any]) -> dict[str, Any]:
    """Split, scorer, metric versions, rerun level and two headline values of one card version."""
    rr = card.get("rerun") if isinstance(card.get("rerun"), Mapping) else {}
    tr = rr.get("track") or {}
    sc = rr.get("scorer") or {}
    split = tr.get("split_version") or ("tracks-v0.2" if str(card.get("schema", "")).endswith("/0.2") else "tracks-v0.1")
    digest = tr.get("digest") or (card.get("track_info") or {}).get("split_digest")
    scorer = card.get("scorer_version") or sc.get("scorer_version") or f"benchmark-{card.get('benchmark_version', '?')}"
    metrics = dict(sc.get("metrics") or {})
    sw = card.get("safe_wpm") if isinstance(card.get("safe_wpm"), Mapping) else None
    if sw and sw.get("definition"):
        metrics.setdefault("safe_wpm", sw["definition"])
    ew = ((card.get("metrics") or {}).get("ewpm") or {}).get("value")
    return {"schema": card.get("schema"), "split_version": split, "split_digest": digest, "scorer_version": scorer,
            "metric_versions": metrics, "rerun_level": rerun_level(card),
            "ewpm": ew, "safe_wpm": sw.get("value") if sw else None, "safe_wpm_status": sw.get("status") if sw else None}


def changed_fields(old: Mapping[str, Any] | None, new: Mapping[str, Any]) -> list[str]:
    """Top-level card fields that are new, removed or different (sorted). ``_file`` is ignored."""
    if old is None:
        return []
    keys = (set(old) | set(new)) - {"_file"}
    return sorted(k for k in keys if old.get(k) != new.get(k))


def _log(rel: str, root: Path, run: Runner) -> list[tuple[str, str, str]]:
    out = run(["log", "--no-renames", "--format=%H%x09%cs%x09%s", "--", rel], root) or ""
    rows = []
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def card_history(path: str | Path, root: Path, run: Runner = git_runner) -> list[dict[str, Any]]:
    """Versions of one card, newest first. Each item: commit, date, subject, action, changed fields, facts."""
    p = Path(path).resolve()
    rel = p.relative_to(root).as_posix()
    commits = _log(rel, root, run)
    cards = [_load(run(["show", f"{h}:{rel}"], root)) for h, _, _ in commits]
    out: list[dict[str, Any]] = []
    for i, ((h, date, subj), card) in enumerate(zip(commits, cards)):
        if card is None:
            continue
        older = next((c for c in cards[i + 1:] if c is not None), None)
        out.append({"commit": _short(h), "date": date, "subject": subj,
                    "action": "added" if older is None else "changed",
                    "changed": changed_fields(older, card), **version_facts(card)})
    now = _load(p.read_text(encoding="utf-8")) if p.is_file() else None
    head = cards[0] if cards else None
    if now is not None and now != head:
        out.insert(0, {"commit": None, "date": None, "subject": "working tree, not committed",
                       "action": "added" if head is None else "changed",
                       "changed": changed_fields(head, now), **version_facts(now)})
    return out


def removed_cards(folder: str | Path, root: Path, run: Runner = git_runner) -> list[dict[str, Any]]:
    """Cards that a commit deleted from ``folder`` and that are not back in the working tree."""
    f = Path(folder).resolve()
    rel_dir = f.relative_to(root).as_posix()
    out_txt = run(["log", "--no-renames", "--diff-filter=D", "--format=@%H%x09%cs%x09%s", "--name-only", "--",
                   rel_dir], root) or ""
    out: list[dict[str, Any]] = []
    cur: tuple[str, str, str] | None = None
    for line in out_txt.splitlines():
        if line.startswith("@"):
            parts = line[1:].split("\t", 2)
            cur = (parts[0], parts[1], parts[2] if len(parts) > 2 else "") if len(parts) >= 2 else None
            continue
        name = line.strip()
        if not name or cur is None or not name.endswith(".json") or (root / name).is_file():
            continue
        if any(r["file"] == Path(name).name for r in out):
            continue  # newest deletion only
        card = _load(run(["show", f"{cur[0]}^:{name}"], root))
        if card is None or not str(card.get("schema", "")).startswith("fidetype.benchmark.result/"):
            continue
        out.append({"file": Path(name).name, "track": card.get("track"), "entry_id": card.get("entry_id"),
                    "commit": _short(cur[0]), "date": cur[1], "subject": cur[2], "action": "removed",
                    **version_facts(card)})
    return out


def build_history(folders: Sequence[str | Path], run: Runner = git_runner) -> dict[str, Any]:
    """History of every card in ``folders``: {"available", "note", "cards": {file: [...]}, "removed": [...]}."""
    folders = [Path(f) for f in folders]
    root = next((r for r in (repo_root(f, run) for f in folders) if r is not None), None)
    if root is None:
        return {"schema": HISTORY_SCHEMA, "available": False,
                "note": "no git history (not a git repository, no git program, or a shallow clone)",
                "cards": {}, "removed": []}
    cards: dict[str, list[dict[str, Any]]] = {}
    removed: list[dict[str, Any]] = []
    rels = []
    for f in folders:
        try:
            rels.append(f.resolve().relative_to(root).as_posix())
        except ValueError:
            pass
    # Commit order over all result folders (0 = newest): orders the events of one day.
    order = (run(["log", "--no-renames", "--format=%h", "--abbrev=7", "--", *rels], root) or "").split() if rels else []
    seq = {h[:7]: i for i, h in enumerate(order)}
    for f in folders:
        fr = f.resolve()
        try:
            fr.relative_to(root)
        except ValueError:
            continue
        for p in sorted(fr.glob("*.json")):
            cards[p.name] = card_history(p, root, run)
        removed += removed_cards(fr, root, run)
    for v in [x for vs in cards.values() for x in vs] + removed:
        v["seq"] = -1 if v.get("commit") is None else seq.get(v["commit"], len(seq))
    return {"schema": HISTORY_SCHEMA, "available": True,
            "note": "from git log (no rename detection); dates are commit dates (YYYY-MM-DD)",
            "cards": cards, "removed": removed}


def track_events(history: Mapping[str, Any], files: Mapping[str, str], track: str) -> list[dict[str, Any]]:
    """All events of one track, newest first: card versions of its entries plus removed entries.

    ``files`` maps a card file name to its entry anchor."""
    ev: list[dict[str, Any]] = []
    for fname, anchor in files.items():
        for v in (history.get("cards") or {}).get(fname, []):
            ev.append({**v, "file": fname, "anchor": anchor})
    for r in history.get("removed") or []:
        if r.get("track") == track:
            ev.append({**r, "anchor": None})
    # Working-tree rows first, then newest commit first (commit order, then date), then by file name.
    ev.sort(key=lambda e: (e.get("seq", 0), e["file"]))
    return sorted(ev, key=lambda e: "9999-99-99" if e["date"] is None else e["date"], reverse=True)
