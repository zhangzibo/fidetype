"""P11-14: declared-subset emg2qwerty score card (target ``intended_text``) for the P11-14 primary arm L-FL. CPU only.

Adapted from the P11-13 card script (same scorer, same card convention). Plan rule: a card for the primary arm only.

RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0. Inputs are READ ONLY: the cached P11-14 decisions and guard
status files (``C:/Users/zhang/bci-data/derived/p11-14/``) and the local track truth
(``derived/p6-02-scorer/truth/emg2qwerty.jsonl``). Submission folders and scratch cards go to
``derived/p11-14/cardwork/`` (local only, never in git). The repo gets the score card (aggregates only).

Stages (repo root):

  score   build the submission folder (units + controls, key codes), score it with the track scorer
          (target intended_text), and compare with the P11-14 results.json.
  cards   copy the card into benchmark/results/v0.2/ with a full rerun recipe (P13-06 / P13-11).

    .venv\\Scripts\\python.exe -I experiments/2026-11-20-p11-14-emg-lm-confidence/cards.py score cards --code-ref <sha>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.adapters import emg2qwerty as A  # noqa: E402
from fidetype.benchmark import scorecard as SC  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
P1114 = DER / "p11-14"  # READ ONLY here (decisions, guard status)
P1111 = DER / "p11-11"  # READ ONLY (hashes of the LM and lexicon only)
OWN = DER / "p11-14" / "cardwork"
TRUTH = DER / "p6-02-scorer" / "truth" / "emg2qwerty.jsonl"  # READ ONLY
EXP = "experiments/2026-11-20-p11-14-emg-lm-confidence"
OUT = HERE / "results"
TRACK = "emg2qwerty"
TARGET = "intended_text"
ARMS = ("L-FL",)
B, SEED = 2000, 0
P1109_CARD = REPO / "benchmark" / "results" / "v0.2" / "emg2qwerty__p11-01-crt-subset8__guard.json"


def card_name(arm: str) -> str:
    return f"{TRACK}__p11-14-intended-{arm.lower().replace('-', '')}-subset8__guard"


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(obj: object, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    from fidetype.benchmark.scoring import to_jsonable

    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(to_jsonable(obj), indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, p)


def log(*a: object) -> None:
    OUT.mkdir(exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def to_codes(text: str) -> str:
    """Intended text (decoder output: key characters, real spaces) -> key codes of the track text space."""
    return A.key_text_to_codes(" ".join(text.split()).replace(" ", A.KEY_SPACE_CHAR))


def unit_row(unit: str, d: dict) -> dict:
    """One units.jsonl row. nbest[0] is the decoder top-1 (CER); an OFFER shows the top-1 (the only choice)."""
    if d["action"] == "commit":
        texts, act = [d["text"] or ""], "commit"
    elif d["action"] == "offer":
        texts, act = ([d["top1"]] if d["top1"] else []), "offer"
    else:
        texts, act = ([d["top1"]] if d["top1"] else []), "abstain"
    if act == "offer" and not texts:
        act = "abstain"
    codes = [to_codes(t) for t in texts]
    return SC.unit_row(unit, codes, [d["p_top1"]] + [None] * (len(codes) - 1), action=act,
                       score_semantics="calibrated_prob", offer_k=3)


def manifest(arm: str, st: dict) -> dict:
    sh = st["sheet"]
    g = st["gate"]
    c = st["decoder"]
    dec = {"name": "fidetype P11-01 causal ring-TCN CTC (personalised) + P11-07 in-beam LM key beam (Tatoeba 6-gram, "
                   "lexicon term) + intended-text merge + P11-11 OOV gate + P11-12 no-signal gate",
           "version": f"{st['decoder_version']}-k{g['k_min']}-r{g['r_min']:.4f}-{g['r_max']:.4f}",
           "url": f"{EXP}/",
           "weights_licence": "not released (CC BY-NC-SA data: research only)",
           "training_data": ["emg2qwerty: generic model on 100 other users; personal fine-tuning on the train "
                             "sessions of each of the 8 users (never the track val or test session)",
                             "LM: Tatoeba English (no emg2qwerty text); lexicon: words of the track-train sessions; "
                             f"LM weight {c['w']}, bonus {c['beta']}, lexicon term {c['lam']}, beam {c['B']} tuned on "
                             "the calibration tuning part (P11-07); confidence model fitted on the same tuning part "
                             "(P11-14)"],
           "training_regime": "personalised (fine-tuned on earlier sessions of the same user)"}
    pol = {"name": "intended-text guard, sentence commits, learned confidence L (P11-14 arm L-FL)",
           "description": f"fidetype.trust.calibrate on {st['n_cal']} track-val prompts of the same 8 users, alpha "
                          f"{sh['alpha']}, delta {sh['delta']}, commit threshold {sh['commit_threshold']} on p_top1 of "
                          "a two-item n-best (top-1 text, reject item) that carries the P11-14 learned confidence "
                          "(logistic score on beam, LM and acoustic features, fitted on the calibration tuning part); "
                          f"acoustic no-signal gate (greedy keys >= {g['k_min']}, {g['r_min']:.2f} <= keys/s <= "
                          f"{g['r_max']:.2f})"}
    gua = {"method": "ltt", "alpha": sh["alpha"], "delta": sh["delta"], "n_cal": int(sh["n_ltt"]),
           "scope": "marginal over test prompts pooled over the 8 users; exchangeable val / test sessions; wrong = "
                    "committed intended text differs from the truth intended text",
           "calibration_split": "val", "config_id": st["config_id"], "feasible": sh.get("feasible", True)}
    return SC.manifest_dict(
        TRACK, dec, policy=pol, guarantee=gua, regime="personalised", target=TARGET,
        controls={"shuffled": "input level: the test session EMG features time-shuffled (seeded per session, "
                              "P11-09 windows), then the same decoder, gate and guard",
                  "zeros": "input level: zero EMG (every band at log(1e-6)), then the same decoder, gate and guard"},
        coverage={"subset": "declared subset: the track test sessions of the 8 P11-01 test users only. The P11-01 "
                            "generic model trained on 96 of the other 104 track test sessions, so only these 8 "
                            "sessions are clean (P11-01 results, benchmark section)."},
        notes="RESEARCH ONLY (CC BY-NC-SA 4.0 data). Target intended_text (intended-text/1): the guard commits the "
              "intended text, so truth and outputs are compared after Backspace is applied. Offline decisions on "
              "full prompt windows (no latency claim). P11-14 decisions (primary arm, selected on calibration "
              "tuning items only).")


def stage_score() -> dict:
    truth = SC.read_truth(TRUTH, TRACK)
    p14 = load_json(REPO / EXP / "results" / "results.json")
    res: dict = {"task": "P11-14 card", "date": time.strftime("%Y-%m-%d %H:%M"), "data.licence": A.LICENCE,
                 "data.research_only": True, "note": "aggregates only (no per-user value, no text, no id)",
                 "target": SC.target_block(TARGET), "arms": {}}
    for arm in ARMS:
        st = load_json(P1114 / f"guard-{arm}.status.json")
        d = load_json(P1114 / f"decisions-{arm}.json")
        assert st["status"] == "guard" and d["status"] == "guard"
        missing = [u for u in d["units"] if u not in truth]
        assert not missing, f"{len(missing)} decision units are not in the truth"
        name = card_name(arm)
        rows = [unit_row(u, x) for u, x in zip(d["units"], d["real"])]
        ctl = {k: [unit_row(u, x) for u, x in zip(d["units"], d[k])] for k in ("shuffled", "zeros")}
        sub = SC.write_submission(OWN / "submissions" / name, manifest(arm, st), rows, ctl)
        card = SC.score(TRACK, sub, truth, B=B, seed=SEED)
        card.setdefault("notes", []).append("FEP-0010: data.research_only = true (CC BY-NC-SA 4.0).")
        save_json(card, OWN / "cards" / f"{name}.json")
        sw, m, a = card["safe_wpm"], card["metrics"], p14["arms"][arm]
        ref = a["safe_v01"]
        cmp = {
            "safe_wpm_value": [sw["value"], ref["value"]],
            "safe_wpm_ci": [sw["ci"], ref["ci"]],
            "n_commits": [sw["n_commits"], a["n_commits"]],
            "n_wrong_commits": [sw["n_wrong_commits"], a["n_wrong_commits"]],
            "committed_correct_words": [sw["committed_correct_words"], ref["committed_correct_words"]],
            "total_words": [sw["total_words"], ref["total_words"]],
            "no_bci_wpm": [sw["no_bci_wpm"], ref["no_bci_wpm"]],
            "minutes_correction": [sw["minutes_correction"], ref["minutes_correction"]],
            "minutes_neural": [sw["minutes_neural"], ref["minutes_neural"]],
            "status": [sw["status"], ref["status"]],
        }
        exact = {k: (v[0] == v[1] if not isinstance(v[0], float) else abs(v[0] - v[1]) < 1e-9)
                 for k, v in cmp.items() if k != "safe_wpm_ci"}
        res["arms"][arm] = {
            "card": f"{name}.json", "status": card["status"], "certification": card["certification"],
            "cer_intended": m["cer"], "ewpm": m["ewpm"], "gaze_ewpm": m["gaze_ewpm"],
            "wrong_commit_rate": m["wrong_commit_rate"], "error_among_commits": m["error_among_commits"],
            "commit_rate": m["commit_rate"], "controls": {k: v for k, v in card["controls"].items() if k != "basis"},
            "guarantee": card["guarantee"], "safe_wpm": {k: sw.get(k) for k in (
                "value", "ci", "status", "n_trials", "n_commits", "n_wrong_commits", "measured_wrong_commit",
                "measured_wrong_commit_cp95", "no_bci_wpm", "committed_correct_words", "total_words",
                "minutes_neural", "minutes_correction")},
            "coverage": card["coverage"], "vs_p11_14": cmp, "same_as_p11_14": exact}
        log(f"card score {arm}: {card['status']}; safe WPM {sw['value']:.4f} {sw['ci']} vs P11-14 {ref['value']:.4f} "
            f"{ref['ci']}; commits {sw['n_commits']} wrong {sw['n_wrong_commits']}; same {exact}")
    save_json(res, OUT / "card-results.json")
    return res


def stage_cards(code_ref: str) -> list[str]:
    from fidetype.benchmark.hub.recipe import card_json, check_recipe

    p9 = load_json(P1109_CARD)["rerun"]["decoder"]
    lm_files = sorted([{"name": f"<derived>/p11-11/{n}", "sha256": sha256_file(P1111 / n)}
                       for n in ("eng_tatoeba_6gram_mkn_noE2Q.npz", "lexicon.json")]
                      + [{"name": f"{EXP}/results/model-L-FL.json",
                          "sha256": sha256_file(REPO / EXP / "results" / "model-L-FL.json")}],
                      key=lambda f: f["name"])
    out = []
    for arm in ARMS:
        st = load_json(P1114 / f"guard-{arm}.status.json")
        name = card_name(arm)
        card = load_json(OWN / "cards" / f"{name}.json")
        r = card["rerun"]
        # The neural weights are the P11-09 / P11-01 personal models: same files, same manifest hash (P13-11).
        r["decoder"].pop("weights_sha256_reason", None)
        r["decoder"]["weights_files"] = p9["weights_files"]
        r["decoder"]["weights_sha256"] = p9["weights_sha256"]
        r["decoder"]["lm_files"] = lm_files
        r["policy"].pop("config_id_reason", None)
        r["policy"]["config_id"] = st["config_id"]
        r["policy"]["config_id_source"] = f"{EXP}/results/guard-{arm}.json"
        r["code_ref"] = f"git {code_ref} (P11-14 run.py and this card script)"
        r["level"] = "rescore"
        sub = f"<derived>/p11-14/cardwork/submissions/{name}"
        r["steps"] = [
            {"step": "truth", "command": "python -m fidetype.benchmark truth emg2qwerty --data <data> --out "
                                         "<derived>/p6-02-scorer/truth/emg2qwerty.jsonl"},
            {"step": "build", "command": f"python {EXP}/launch.py all (P11-14 decisions; needs the P11-09, P11-11 "
                                         f"and P11-12 local files), then python {EXP}/cards.py score"},
            {"step": "score", "command": f"python -m fidetype.benchmark score emg2qwerty {sub} --truth "
                                         f"<derived>/p6-02-scorer/truth/emg2qwerty.jsonl --B {B} --seed {SEED} "
                                         f"--out benchmark/results/v0.2/{name}.json"}]
        r["inputs"] = {"outputs": f"submission folder {sub} (decoded key codes, target intended_text; local only, "
                                  "never in git)",
                       "build": "the build step needs the P11-01 feature cache and personal weights, the P11-11 LM, "
                                f"lexicon and beam cache, the P11-12 gate (local, research only); see {EXP}/results.md",
                       "derived": "<derived> = the local folder for per-unit files (never in git)"}
        r["recorded"] = f"{time.strftime('%Y-%m-%d')}, P11-14 (cards.py cards)"
        errs = check_recipe(r)
        if errs:
            raise SystemExit(f"p11-14: recipe of {name}: {errs}")
        f = REPO / "benchmark" / "results" / "v0.2" / f"{name}.json"
        f.write_text(card_json(card), encoding="utf-8", newline="\n")
        out.append(str(f))
        log(f"cards: wrote {f.name}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stages", nargs="+", choices=("score", "cards"))
    ap.add_argument("--code-ref", default=None, help="git commit of run.py and this script (cards)")
    a = ap.parse_args()
    if "score" in a.stages:
        stage_score()
    if "cards" in a.stages:
        if not a.code_ref:
            raise SystemExit("cards needs --code-ref <git sha>")
        stage_cards(a.code_ref)
    return 0


if __name__ == "__main__":
    sys.exit(main())
