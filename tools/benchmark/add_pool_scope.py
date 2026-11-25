r"""Make the pool scope explicit on the score cards, and record two safety findings (2026-11-25).

Basis: the pooled-guard check (commit ``74a21f8``, ``experiments/2026-11-25-pooled-guard-check/results.md``).
This tool changes no number on any card. It adds text only:

1. **Scope line.** Every card with a CRC / LTT bound pools its test set over users, participants, sessions, days
   or runs. The bound covers that pool, not each group (docs/trust-guarantee.md section 4). The tool appends this
   to ``guarantee.scope`` and adds a dated note to ``notes``.
2. **SpanishBCBL MEG CRC / LTT** (tracks v0.1 and v0.2): a ``safety_findings`` entry "label-blind commit step,
   no evidence of signal" and a dated note. Root cause: only 14 of the 437 calibration trials can commit at all
   (the other rules of the trust policy block the rest), 13 of them are wrong, and 14 / 437 is below alpha. So
   every threshold is feasible, CRC and LTT take the lowest one, and the commit step is the same under any labels.
   The numbers come from the committed items file ``experiments/2026-11-11-g1-async-meg-trust/results/
   items-meg-async.json``; the tool computes them again and checks them against the card.
3. **B2T '25 "published" CRC / LTT** (tracks v0.1 and v0.2): a ``safety_findings`` entry "one day above alpha",
   with the per-day table of the pooled-guard check (local file ``groups.json``, aggregates only) and a dated note.
   The tool checks that the per-day totals equal the card totals (trials, commits, wrong commits).

The tool is idempotent: a second run changes nothing. Cards are written in the scorer's JSON form.

    python -I tools/benchmark/add_pool_scope.py            # dry run: print what would change
    python -I tools/benchmark/add_pool_scope.py --write    # update the cards
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fidetype.benchmark.hub.recipe import card_json  # noqa: E402

DATE = "2026-11-25"
BASIS = ("the pooled-guard check (commit 74a21f8; "
         "https://github.com/zhangzibo/fidetype/blob/main/experiments/2026-11-25-pooled-guard-check/results.md)")
SECTION4 = "https://github.com/zhangzibo/fidetype/blob/main/docs/trust-guarantee.md#4-what-is-not-guaranteed"
SCOPE_MARK = "the bound covers the pool"
ALPHA = 0.05

#: Track -> (plural, singular, "of one participant" or "") of the groups that the test set pools.
POOL = {
    "b2t25-t15-copytask": ("days", "day", " of one participant"),
    "b2t25-t15": ("days", "day", " of one participant"),
    "b2t24-t12": ("sessions", "session", " of one participant"),
    "willett-hw": ("sessions", "session", " of one participant"),
    "emg2qwerty": ("users", "user", ""),
    "toronto-semg-composed": ("participants", "participant", ""),
    "toronto-semg": ("participants", "participant", ""),
    "spanishbcbl-meg-async": ("participants", "participant", ""),
    "spanishbcbl-meg": ("participants", "participant", ""),
    "kt-semg": ("runs", "run", ""),
}

MEG_CARDS = ("spanishbcbl-meg-async__convctc-m-async__{m}.json", "spanishbcbl-meg__convctc-m-async__{m}.json")
B2T_CARDS = ("b2t25-t15-copytask__published__{m}.json", "b2t25-t15__published__{m}.json")
MEG_ITEMS = REPO / "experiments/2026-11-11-g1-async-meg-trust/results/items-meg-async.json"
GROUPS = Path("C:/Users/zhang/bci-data/derived/pooled-guard-check/groups.json")


def scope_suffix(track: str) -> str:
    plural, single, of = POOL[track]
    return (f"; {SCOPE_MARK} (all {plural}{of} together), not each {single}: one {single} can be worse "
            f"(trust guarantee section 4: {SECTION4})")


def scope_note(track: str) -> str:
    plural, single, of = POOL[track]
    return (f"{DATE}: the scope line now says that the bound covers the pool of all {plural}{of}, not each "
            f"{single} (trust guarantee section 4). Basis: {BASIS}. No number changed.")


def has_bound(card: dict) -> bool:
    return (card.get("guarantee") or {}).get("method", "none") not in ("none", None)


def cp_interval(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """Two-sided Clopper-Pearson interval (the convention of the pooled-guard check)."""
    from scipy.stats import beta

    lo = 0.0 if k <= 0 else float(beta.ppf((1 - level) / 2, k, n - k + 1))
    hi = 1.0 if k >= n else float(beta.ppf(1 - (1 - level) / 2, k + 1, n - k))
    return lo, hi


def meg_facts() -> dict:
    """The eligibility facts of the SpanishBCBL CRC / LTT entries, from the committed items file."""
    d = json.loads(MEG_ITEMS.read_text(encoding="utf-8"))

    def facts(part: dict) -> dict:
        s = [float(x) for x in part["score"]]
        c = part["loss_c"]
        elig = [i for i, x in enumerate(s) if math.isfinite(x)]
        return {"n": len(s), "eligible": len(elig), "eligible_wrong": int(sum(c[i] > 0 for i in elig)),
                "top1_right": int(sum(x == 0 for x in c))}

    return {"val": facts(d["fit"]), "test": facts(d["test"])}


def meg_finding(card: dict, f: dict) -> dict:
    sw = card["safe_wpm"]
    v, k = f["val"], card["guarantee"]["method"].upper()
    if not (v["eligible"] / v["n"] < ALPHA and sw["n_trials"] == f["test"]["n"]):
        raise SystemExit(f"{card['entry_id']}: the MEG facts do not match the card")
    return {
        "date": DATE, "kind": "label-blind-commit-step",
        "mark": "LABEL-BLIND COMMIT STEP: no evidence of signal",
        "summary": (f"Only {v['eligible']} of the {v['n']} calibration (val) trials can commit at all: the other rules "
                    f"of the trust policy block the rest. {v['eligible_wrong']} of these {v['eligible']} are wrong (the "
                    f"top-1 sentence is right for {v['top1_right']} of {v['n']} val trials). Because "
                    f"{v['eligible']} / {v['n']} is below alpha {ALPHA}, every threshold meets the {k} bound, so {k} "
                    f"takes the lowest one and commits all {v['eligible']}, whatever the labels are. With permuted "
                    f"labels it commits the same {v['eligible']} items. On test, {sw['n_wrong_commits']} of "
                    f"{sw['n_commits']} commits are wrong. The bound holds (test wrong-commit rate "
                    f"{card['guarantee']['measured_wrong_commit']:.3f}), but only because the policy almost never "
                    "commits: the commit step shows no evidence that the score separates right from wrong text. Read "
                    f"this entry as a vacuous guard result, not as evidence that the guard works on this decoder. "
                    f"Basis: {BASIS}. No number changed."),
        "facts": {"val_trials": v["n"], "val_can_commit": v["eligible"], "val_can_commit_wrong": v["eligible_wrong"],
                  "val_top1_right": v["top1_right"], "test_trials": f["test"]["n"],
                  "test_can_commit": f["test"]["eligible"], "test_commits": sw["n_commits"],
                  "test_wrong_commits": sw["n_wrong_commits"]},
        "numbers_changed": False,
    }


def b2t_finding(card: dict, g: dict) -> dict:
    sw = card["safe_wpm"]
    if not (g["n"] == card["n_trials"] == sum(r["n"] for r in g["_table"]) and g["commits"] == sw["n_commits"]
            == sum(r["commits"] for r in g["_table"]) and g["wrong"] == sw["n_wrong_commits"]
            == sum(r["wrong"] for r in g["_table"])):
        raise SystemExit(f"{card['entry_id']}: the per-day table does not add up to the card totals")
    rows = []
    for r in g["_table"]:
        lo, hi = cp_interval(r["wrong"], r["n"])
        rows.append({"group": r["group"], "n": r["n"], "commits": r["commits"], "wrong": r["wrong"],
                     "rate": r["wrong"] / r["n"], "cp_lower": lo, "cp_upper": hi})
    above = [r for r in rows if r["cp_lower"] > ALPHA]
    if len(above) != 1:
        raise SystemExit(f"{card['entry_id']}: expected exactly one day with a CP lower bound above alpha")
    a, k = above[0], card["guarantee"]["method"].upper()
    pooled = g["wrong"] / g["n"]
    return {
        "date": DATE, "kind": "per-day-exceedance",
        "mark": "SAFETY FINDING: one day above alpha",
        "summary": (f"The {k} bound covers the pool of all {len(rows)} days ({g['wrong']} wrong commits in {g['n']} "
                    f"test trials, rate {pooled:.3f}, alpha {ALPHA}). It does not hold for each day: on "
                    f"{a['group']}, {a['wrong']} of {a['n']} test trials are wrong commits (rate {a['rate']:.2f}; "
                    f"Clopper-Pearson 95 % interval [{a['cp_lower']:.3f}, {a['cp_upper']:.3f}], so even the lower end "
                    f"is above alpha). A bound per day is not promised (trust guarantee section 4: {SECTION4}). The "
                    f"table gives every day. Basis: {BASIS}. No number changed."),
        "per_group": {"unit": "day", "alpha": ALPHA, "interval": "Clopper-Pearson 95 % (two-sided)",
                      "note": ("Each day is named by its post-implant day, as in the split file of the track. Only "
                               f"{a['group']} has an interval whose lower end is above alpha. Days with few trials "
                               "have wide intervals: an upper end above alpha alone is not proof of a rate above "
                               "alpha."),
                      "rows": rows},
        "numbers_changed": False,
    }


def with_finding(card: dict, finding: dict) -> dict:
    """The card with ``finding`` in ``safety_findings`` (right after ``guarantee``); unchanged if already there."""
    have = card.get("safety_findings") or []
    if any(f.get("kind") == finding["kind"] and f.get("date") == finding["date"] for f in have):
        return card
    out = {}
    for k, v in card.items():
        if k == "safety_findings":
            continue
        out[k] = v
        if k == "guarantee":
            out["safety_findings"] = have + [finding]
    return out


def with_note(card: dict, note: str) -> dict:
    notes = list(card.get("notes") or [])
    if note in notes:
        return card
    return {**card, "notes": notes + [note]}


def with_scope(card: dict) -> dict:
    g = dict(card["guarantee"])
    if SCOPE_MARK in str(g.get("scope", "")):
        return card
    g["scope"] = str(g.get("scope", "")) + scope_suffix(card["track"])
    return {**card, "guarantee": g}


def finding_note(f: dict, card: dict) -> str:
    return (f"{f['date']}: safety finding on the entry {card['entry_id']}: {f['mark']}. The key safety_findings of "
            "the card (and the entry on the track page) gives the details. No number changed.")


def update(name: str, card: dict, meg: dict | None, groups: dict | None) -> dict:
    if not has_bound(card):
        return card
    out = with_note(with_scope(card), scope_note(card["track"]))
    m = card["guarantee"]["method"]
    if name in {c.format(m=x) for c in MEG_CARDS for x in ("crc", "ltt")}:
        f = meg_finding(card, meg)
        out = with_note(with_finding(out, f), finding_note(f, card))
    if name in {c.format(m=x) for c in B2T_CARDS for x in ("crc", "ltt")}:
        if groups is None:
            raise SystemExit(f"{name}: needs the local pooled-guard groups.json ({GROUPS})")
        f = b2t_finding(card, groups[f"S-B2T-pub-{m}"])
        out = with_note(with_finding(out, f), finding_note(f, card))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", nargs="+", default=[str(REPO / "benchmark/results/v0.1"),
                                                     str(REPO / "benchmark/results/v0.2")])
    ap.add_argument("--groups", default=str(GROUPS))
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    meg = meg_facts()
    gp = Path(a.groups)
    groups = json.loads(gp.read_text(encoding="utf-8")) if gp.is_file() else None
    n_changed = 0
    for folder in a.results:
        for f in sorted(Path(folder).glob("*.json")):
            text = f.read_text(encoding="utf-8")
            card = json.loads(text)
            if card_json(card) != text:
                raise SystemExit(f"{f.name}: the card is not in the scorer's JSON form")
            new = card_json(update(f.name, card, meg, groups))
            if new == text:
                continue
            n_changed += 1
            before, after = json.loads(text), json.loads(new)
            for k in ("metrics", "safe_wpm", "safe_wpm_v02", "controls", "n_trials"):
                if before.get(k) != after.get(k):
                    raise SystemExit(f"{f.name}: {k} would change (this tool must not change a number)")
            g0 = {k: v for k, v in (before.get("guarantee") or {}).items() if k != "scope"}
            g1 = {k: v for k, v in (after.get("guarantee") or {}).items() if k != "scope"}
            if g0 != g1:
                raise SystemExit(f"{f.name}: the guarantee block would change outside its scope line")
            keys = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
            print(f"{'WRITE' if a.write else 'would'} {Path(folder).name}/{f.name}: {', '.join(keys)}")
            if a.write:
                f.write_text(new, encoding="utf-8", newline="\n")
    print(f"{n_changed} cards {'changed' if a.write else 'would change'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
