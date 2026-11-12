"""R1 item 4: user-model sensitivity (gap G6; methods Major 5; domain M4).

Conditions: B2T '25 ours and published gate, sEMG calib / xsession / xsubject,
and MEG async (MEG had a refit-only grid in G1; here it also gets the
symmetric-offer and misspecified-user runs). For each user variant:

- refit: always commit, trust, never commit (always offer, refit) are refitted
  under the variant (best case for each model);
- misspecified: trust and never commit are fitted under the main user
  (``UserConfig.aac_gaze``) and scored under the variant without refit;
- gaze typing only, and gaze typing with word completion (LM-assisted gaze,
  see ``gaze_lm``) under the variant's fallback rate and selection cost.

Variants: main; fallback 10 / 40 chars/min (main 20); selection cost x0.5 /
x2 (all selection and navigation times: select_a_s, select_b_s_per_bit,
word_scan_a_s, word_scan_b_s_per_bit, word_select_s, nav_s); p_miss_unflagged
0 / 0.2 (main 0.05); symmetric offer: OFFER without the target makes the user
fix the closest candidate word by word with the same miss probability as
COMMIT, and no oracle full retype for any action (``allow_full_retype``
False).

LM-assisted gaze (a simple, documented model): the user types each word letter
by letter at the fallback rate. Before each letter, the keyboard shows the
k = 3 most frequent vocabulary words that start with the typed prefix
(unigram from the condition's LM corpus, no sentence context, test sentences
excluded where the BCI LM excluded them). If the intended word is shown and
selecting it is faster than typing the rest of the word plus its space, the
user selects it (word_scan_time(3) + word_select_s = 4.5 s, as for one
OFFER_WORDS slot; the completion adds the space). The user pays no time to
look at the list when the word is not in it (optimistic for gaze typing:
this favours the baseline). Variant ``glance``: 1.0 s per look at the list
before each letter.

Ranking: by eWPM point value among trust / always commit / never commit /
gaze / gaze+LM; CIs of trust - gaze, trust - gaze+LM, trust - never commit at
the condition's unit.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r1-analyses/user-model/run.py --conds ...
"""

from __future__ import annotations

import argparse
import bz2
import json
import math
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common as C  # noqa: E402
import policies as P  # noqa: E402
from fidetype.interact.simulated_user import SimulatedUser  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
SEL_KEYS = ("select_a_s", "select_b_s_per_bit", "word_scan_a_s", "word_scan_b_s_per_bit", "word_select_s", "nav_s")


def variants(user):
    sel = lambda f: {k: getattr(user, k) * f for k in SEL_KEYS}  # noqa: E731
    return {
        "main": (user, None),
        "fallback 10 cpm": (replace(user, fallback_chars_per_min=10.0), None),
        "fallback 40 cpm": (replace(user, fallback_chars_per_min=40.0), None),
        "selection x0.5": (replace(user, **sel(0.5)), None),
        "selection x2": (replace(user, **sel(2.0)), None),
        "p_miss 0": (replace(user, p_miss_unflagged=0.0), None),
        "p_miss 0.2": (replace(user, p_miss_unflagged=0.2), None),
        "symmetric offer (p_miss 0.05, no oracle retype)": (replace(user, allow_full_retype=False), P.SymmetricUser),
        "symmetric offer, p_miss 0.2": (replace(user, allow_full_retype=False, p_miss_unflagged=0.2), P.SymmetricUser),
    }


# ---------------------------------------------------------------------------
# LM-assisted gaze typing
# ---------------------------------------------------------------------------


class Completer:
    def __init__(self, counts: Counter, k: int = 3, min_count: int = 2):
        self.k = k
        self.top: dict[str, list[str]] = {}
        for w, c in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            if c < min_count or not w:
                continue
            for j in range(len(w)):
                lst = self.top.setdefault(w[:j], [])
                if len(lst) < k:
                    lst.append(w)
        self.vocab = len(counts)

    def shown(self, prefix: str) -> list[str]:
        return self.top.get(prefix, [])


def gaze_lm_time(sentence: str, comp: Completer, user, glance_s: float = 0.0) -> tuple[float, int]:
    """Time (s) to type ``sentence`` with word completion; and the number of completions used."""
    t_char = 60.0 / user.fallback_chars_per_min
    t_sel = SimulatedUser(user).word_scan_time(comp.k) + user.word_select_s
    words = sentence.split()
    total, used = 0.0, 0
    for i, w in enumerate(words):
        sp = 1 if i < len(words) - 1 else 0  # the space after the word
        done = False
        for j in range(len(w)):
            total += glance_s
            rest = (len(w) - j + sp) * t_char
            if w in comp.shown(w[:j]) and t_sel < rest:
                total += t_sel
                used += 1
                done = True
                break
            total += t_char
        if not done:
            total += sp * t_char
    return total, used


def completer_for(name: str) -> Completer:
    if name.startswith("b2t"):
        counts = Counter(json.loads(Path("C:/Users/zhang/bci-data/lm/eng_tatoeba_word_counts.json").read_text(encoding="utf-8")))
        return Completer(counts)
    if name.startswith("emg"):  # the char-LM corpus without the 5,000 held-out sentences (the sEMG test pool)
        from fidetype.streams.vocab import normalize_text

        held = set(Path("C:/Users/zhang/bci-data/lm/eng_tatoeba_heldout.txt").read_text(encoding="utf-8").splitlines())
        c: Counter = Counter()
        with bz2.open("C:/Users/zhang/bci-data/corpora/tatoeba/eng_sentences.tsv.bz2", "rt", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 3:
                    continue
                s = normalize_text(parts[2])
                if s and s not in held:
                    c.update(s.split())
        return Completer(c)
    from fidetype.streams.vocab import normalize_text  # MEG: Spanish corpus without the SpanishBCBL targets

    block = set(Path("C:/Users/zhang/bci-data/lm/spanishbcbl_blocklist.txt").read_text(encoding="utf-8").splitlines())
    c = Counter()
    with bz2.open("C:/Users/zhang/bci-data/corpora/tatoeba/spa_sentences.tsv.bz2", "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            s = normalize_text(parts[2])
            if s and s not in block:
                c.update(s.split())
    return Completer(c)


def gaze_lm_arrays(truths, comp, user, glance_s=0.0) -> tuple[dict, float]:
    ts, used = [], 0
    for s in truths:
        t, u = gaze_lm_time(s, comp, user, glance_s)
        ts.append(t)
        used += u
    z = np.zeros(len(truths))
    a = {"w": np.array([len(s.split()) for s in truths], float), "t": np.array(ts), "wc": z, "com": z, "wcc": z, "se": z, "offer": z}
    return a, used / max(1, sum(len(s.split()) for s in truths))


# ---------------------------------------------------------------------------


def run_condition(cond, comp: Completer) -> dict:
    cache: dict = {}
    main_user = cond.user
    truths = [it.text for it in cond.test]
    main_pipes = {v: P.build(cond, v, cache) for v in ("trust", "never_commit")}
    out = {}
    for vname, (u, ucls) in variants(main_user).items():
        ts = time.time()
        arrs = {}
        for v in ("always_commit", "trust", "never_commit"):
            pipe = P.build(cond, v, cache, user=u, user_cls=ucls) if vname != "main" else (main_pipes.get(v) or P.build(cond, v, cache))
            arrs[v] = C.rec_arrays(P.score(pipe, cond.test))
        if vname != "main":
            for v in ("trust", "never_commit"):
                arrs[f"{v} (misspecified: fit under main)"] = C.rec_arrays(P.score(main_pipes[v], cond.test, user=u, user_cls=ucls or SimulatedUser))
        arrs["gaze_only"] = C.gaze_arrays(truths, u.fallback_chars_per_min)
        arrs["gaze_lm"], share = gaze_lm_arrays(truths, comp, u)
        arrs["gaze_lm_glance1s"], share_g = gaze_lm_arrays(truths, comp, u, glance_s=1.0)
        pt = C.point(arrs)
        rank_keys = ["trust", "always_commit", "never_commit", "gaze_only", "gaze_lm"]
        ranking = sorted(rank_keys, key=lambda k: -pt[k]["ewpm"])
        diffs = [("trust", "gaze_only"), ("trust", "gaze_lm"), ("trust", "never_commit"), ("trust", "always_commit"),
                 ("never_commit", "gaze_lm")]
        if vname != "main":
            diffs.append(("trust (misspecified: fit under main)", "trust"))
            diffs.append(("trust (misspecified: fit under main)", "gaze_only"))
        bs = C.bootstrap(arrs, cond, B=CONFIG["bootstrap_B"], seed=CONFIG["seed"] + 13, diffs=diffs)
        out[vname] = {"point": pt, "ranking_by_ewpm": ranking, "gaze_lm_completion_share": share,
                      "gaze_lm_glance_completion_share": share_g,
                      "ci": {"policies": {k: v["ewpm"] for k, v in bs["policies"].items()},
                             "diffs_ewpm": {k: v["ewpm"] for k, v in bs["diffs"].items()},
                             "diffs_silent": {k: v["silent_error"] for k, v in bs["diffs"].items()}},
                      "ci_unit": bs["scheme"], "seconds": round(time.time() - ts, 1)}
        C.log(f"{cond.name} [{vname}]: " + ", ".join(f"{k} {pt[k]['ewpm']:.2f}" for k in pt) + f" | rank {ranking}")
    C.save_caches(cond)
    return {"n_test": len(cond.test), "vocab_completer": comp.vocab, "variants": out}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conds", default="emg-calib,emg-xsession,emg-xsubject,b2t-ours,b2t-published,meg-async")
    a = ap.parse_args()
    out_p = OUT / f"user-model-{a.conds.replace(',', '+')}.json"
    res: dict = {"conditions": {}}
    b2t = None
    comps: dict = {}
    for name in a.conds.split(","):
        key = name.split("-")[0]
        comps[key] = comps.get(key) or completer_for(name)
        if name.startswith("emg"):
            cond = C.emg_condition(name.split("-")[1])
        elif name == "meg-async":
            cond = C.meg_ctx()
        else:
            b2t = b2t or C.b2t_ctx()
            cond = C.b2t_condition(b2t, name.split("-")[1])
            cond.cached = b2t.cached
        res["conditions"][name] = run_condition(cond, comps[key])
        C.dump(res, out_p)
    C.log("done")


if __name__ == "__main__":
    main()
