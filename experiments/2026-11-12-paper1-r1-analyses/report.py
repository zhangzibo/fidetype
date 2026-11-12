"""Write results/tables.md for baselines, ablation, user-model, leakage and fixchecks from their JSON files.

Run (repo root): .venv\\Scripts\\python.exe -I -X utf8 experiments/2026-11-12-paper1-r1-analyses/report.py
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

f, fci = C.fmt, C.fci
ORDER = ["b2t-ours", "b2t-published", "emg-calib", "emg-xsession", "emg-xsubject", "meg-async"]


def load(path):
    p = HERE / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def merged(pattern) -> dict:
    out = {}
    for p in sorted(glob.glob(str(HERE / pattern))):
        out.update(json.loads(Path(p).read_text(encoding="utf-8")).get("conditions", {}))
    return out


def row(name, pt, ci):
    return (f"| {name} | {f(pt['ewpm'], 2)} {fci(ci.get('ewpm'), 2)} | {f(pt['wrong_commit'], 4)} {fci(ci.get('wrong_commit'), 4)} | "
            f"{f(pt['commit_rate'])} | {f(pt['error_among_commits'])} {fci(ci.get('error_among_commits'))} | {f(pt['silent_error'], 4)} |")


HEAD = ["| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits [CI] | silent error |", "|---|---|---|---|---|---|"]


def baselines() -> None:
    d = load("baselines/results/baselines.json")
    if not d:
        return
    names = {"always_commit": "always commit", "never_commit": "never commit / always offer (refit)",
             "raw_no_guard": "plain threshold, raw p_top1, no guard", "no_guard": "plain threshold, calibrated p_top1, no guard",
             "trust": "trust (plug-in)", "clean_plugin": "trust, fit-A pipeline (plug-in)", "crc": "trust, fit-A + CRC (clean cal)",
             "ltt": "trust, fit-A + LTT (clean cal)", "gaze_only": "gaze typing only"}
    L = ["# Baselines and selective risk: generated tables", "",
         "CI: 95 % percentile bootstrap, B = 2000, at the condition's unit (B2T: day clusters; sEMG: participant clusters; MEG: two-way "
         "sentences x participants). Wrong-commit = P(commit and wrong) over all items; error among commits = P(wrong | commit).", ""]
    for c in ORDER:
        r = d["conditions"].get(c)
        if not r:
            continue
        bs = r["bootstrap"]
        L += [f"## {c} (n test {r['n_test']}; CI unit {r['ci_unit']})", ""] + HEAD
        for k in names:
            if k in r["point"]:
                L.append(row(names[k], r["point"][k], bs["policies"][k]))
        th = r.get("clean_thresholds", {})
        if th:
            L += ["", f"Clean thresholds: CRC λ {f(C.fnum(th.get('crc')), 4)}, LTT λ {f(C.fnum(th.get('ltt')), 4)}, fit-A plug-in λ "
                       f"{f(C.fnum(th.get('clean_plugin')), 4)} (calibration n {th.get('crc_info', {}).get('n')})."]
        L += ["", "Paired differences (eWPM; wrong-commit):", ""]
        for k, v in bs["diffs"].items():
            L.append(f"- {k}: {fci(v['ewpm'], 2)}; {fci(v['wrong_commit'], 4)}")
        for extra in ("bootstrap_sentences", "bootstrap_participants"):
            if extra in r:
                L.append(f"- ({extra.split('_')[1]}) trust - gaze_only eWPM {fci(r[extra]['diffs'].get('trust-gaze_only', {}).get('ewpm'), 2)}; "
                         f"trust - never_commit {fci(r[extra]['diffs'].get('trust-never_commit', {}).get('ewpm'), 3)}")
        L.append("")
    rs = d.get("random_split_selective_risk", {})
    if rs:
        L += ["## CRC / LTT selective risk in random calibration / test splits (committed item files, 200 splits)", "",
              "| pool | n_cal | method | wrong-commit mean | commit rate mean | error among commits (pooled) | share of splits with no commit |",
              "|---|---|---|---|---|---|---|"]
        for pool, dd in rs.items():
            for n_cal, mm in dd.items():
                for m, v in mm.items():
                    L.append(f"| {pool} | {n_cal} | {m.upper()} | {f(v['wrong_commit_mean'], 4)} | {f(v['commit_rate_mean'])} | "
                             f"{f(v['error_among_commits_pooled'])} | {f(v['share_splits_no_commit'], 2)} |")
    (HERE / "baselines/results/tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def ablation() -> None:
    d = merged("ablation/results/ablation-*.json")
    if not d:
        return
    L = ["# Unified ablation: generated tables", "",
         "Each variant refitted on the condition's fit data; test metrics. CI at the condition's unit (B = 2000). "
         "Δ = paired difference to the full layer (trust). conf_only = frame temperature not applied before the beam (sentence T on); "
         "beam_only = frame temperature before the beam, no sentence T.", ""]
    for c in ORDER:
        r = d.get(c)
        if not r:
            continue
        bs, dec = r["bootstrap"], r["decoder"]
        L += [f"## {c}", "", "| variant | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits | Δ eWPM vs trust | Δ wrong-commit vs trust | "
                             "top-1 CER | frame T used | sentence ECE (cal) |", "|---|---|---|---|---|---|---|---|---|---|"]
        for k, pt in r["point"].items():
            ci = bs["policies"][k]
            dd = bs["diffs"].get(f"{k}-trust", {})
            ds = dec.get(k, {})
            L.append(f"| {k} | {f(pt['ewpm'], 2)} {fci(ci['ewpm'], 2)} | {f(pt['wrong_commit'], 4)} {fci(ci['wrong_commit'], 4)} | "
                     f"{f(pt['commit_rate'])} | {f(pt['error_among_commits'])} | {fci(dd.get('ewpm'), 2)} | {fci(dd.get('wrong_commit'), 4)} | "
                     f"{f(ds.get('cer'))} | {f(ds.get('frame_T'), 2)} | {f(ds.get('ece_sentence_cal'))} |")
        other = [k for k in bs["diffs"] if not k.endswith("-trust")]
        if other:
            L += ["", "Other paired differences (eWPM; wrong-commit): " + "; ".join(
                f"{k}: {fci(bs['diffs'][k]['ewpm'], 2)}, {fci(bs['diffs'][k]['wrong_commit'], 4)}" for k in other)]
        if r.get("extra"):
            L += ["", "Extra: " + json.dumps(C.clean(r["extra"]))]
        L.append("")
    (HERE / "ablation/results/tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def user_model() -> None:
    d = merged("user-model/results/user-model-*.json")
    if not d:
        return
    L = ["# User-model sensitivity: generated tables", "",
         "eWPM point values; refit = policy refitted under the variant; misspecified = fitted under the main user, scored under the variant. "
         "gaze+LM = gaze typing with k = 3 word completion (no glance cost); glance = 1 s per look. CIs of differences at the condition's unit (B = 1000).", ""]
    for c in ORDER:
        r = d.get(c)
        if not r:
            continue
        L += [f"## {c}", "", "| variant | always commit | trust | never commit | trust (misspec.) | gaze | gaze+LM | gaze+LM glance | ranking | "
                             "trust − gaze [CI] | trust − gaze+LM [CI] | trust − never commit [CI] | trust − always commit [CI] |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for v, x in r["variants"].items():
            p = x["point"]
            dd = x["ci"]["diffs_ewpm"]
            ms = p.get("trust (misspecified: fit under main)", {}).get("ewpm")
            L.append(f"| {v} | {f(p['always_commit']['ewpm'], 2)} | {f(p['trust']['ewpm'], 2)} | {f(p['never_commit']['ewpm'], 2)} | {f(ms, 2)} | "
                     f"{f(p['gaze_only']['ewpm'], 2)} | {f(p['gaze_lm']['ewpm'], 2)} | {f(p['gaze_lm_glance1s']['ewpm'], 2)} | "
                     f"{' > '.join(x['ranking_by_ewpm'])} | {fci(dd.get('trust-gaze_only'), 2)} | {fci(dd.get('trust-gaze_lm'), 2)} | "
                     f"{fci(dd.get('trust-never_commit'), 3)} | {fci(dd.get('trust-always_commit'), 2)} |")
        sil = {v: x["point"]["trust"]["silent_error"] for v, x in r["variants"].items()}
        L += ["", "Trust silent-error rate per variant: " + "; ".join(f"{k} {f(s, 4)}" for k, s in sil.items()), ""]
    (HERE / "user-model/results/tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def leakage() -> None:
    d, rep = load("leakage/results/leakage.json"), load("leakage/results/build_report.json")
    if not rep:
        return
    L = ["# Leakage (G9): generated tables", "", "## LM rebuild", "",
         f"Rule: {rep['rule']}. Original training slice {rep['n_train_original']} sentences (matches the original build: "
         f"{rep['check_n_train_matches_original']}).", ""]
    b, e = rep["b2t"], rep["emg"]
    L += [f"- B2T: {b['n_cue_sentences']} unique cue sentences; {b['cues_with_exact_match_in_lm_train']} have an exact copy and "
          f"{b['cues_with_near_variant_in_lm_train']} an exact or near variant in the char-LM training slice; removed "
          f"{b['lm_train_sentences_removed']} training sentences; word unigram rebuilt without {b['word_count_sentences_removed']} sentences.",
          f"- sEMG: {e['n_test_sentences']} test sentences; {e['test_with_exact_match_in_lm_train']} exact, "
          f"{e['test_with_near_variant_in_lm_train']} with a near variant in the training slice ({e['fit_with_near_variant_in_lm_train']} "
          f"of {e['n_fit_sentences']} fit sentences); removed {e['lm_train_sentences_removed']} training sentences.", ""]
    if d:
        for c in ORDER:
            r = d.get(c)
            if not r:
                continue
            bs = r["bootstrap"]
            L += [f"## {c}", "", "| policy | eWPM [CI] | wrong-commit [CI] | commit rate | error among commits | silent |", "|---|---|---|---|---|---|"]
            for k, pt in r["point"].items():
                L.append(row(k, pt, bs["policies"][k])[:-1] + "|")
            L += ["", "Paired: " + "; ".join(f"{k}: eWPM {fci(v['ewpm'], 2)}, wrong-commit {fci(v['wrong_commit'], 4)}" for k, v in bs["diffs"].items())]
            dec = r.get("decoder", {})
            L += ["", "Top-1 decoder (clean LM): " + "; ".join(f"{k}: CER {f(v.get('cer'))}, WER {f(v.get('wer'))}, sentence acc "
                                                               f"{f(v.get('sentence_acc'))}, truth in n-best {f(v.get('truth_in_nbest'))}" for k, v in dec.items())]
            if "lm_weight_clean" in r:
                L.append(f"LM weight: original {r['lm_weight_original']}, re-tuned with the clean LM {r['lm_weight_clean']} (fit-A CER {r['lm_weight_tune_clean']}).")
            ex = r["exclusion"]
            L += [f"Exclusion (original LM, {ex['n_kept']} kept / {ex['n_removed']} removed test items): " + "; ".join(
                f"{k} eWPM {f(v['ewpm'], 2)}, wc {f(v['wrong_commit'], 4)}" for k, v in ex["point"].items() if k.startswith("original") or k == "gaze_only")
                  + "; trust − gaze " + fci(ex["bootstrap"]["diffs"]["original:trust-gaze_only"]["ewpm"], 2), ""]
    (HERE / "leakage/results/tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def fixchecks() -> None:
    d = load("fixchecks/results/fixchecks.json")
    if not d:
        return
    b = d.get("b2t_counts", {})
    L = ["# Fix checks: generated tables", "", "## B2T '25 counts", "", b.get("correct_description", ""), "",
         "| day | 50-word trials | 125k trials | fit | test |", "|---|---|---|---|---|"]
    for day, v in b.get("trials_per_day_by_vocab", {}).items():
        L.append(f"| {day} | {v.get('50', 0)} | {v.get('125000', 0)} | {b['fit_per_day'].get(day, 0)} | {b['test_per_day'].get(day, 0)} |")
    m = d.get("meg_cer")
    if m:
        L += ["", "## MEG: harness top-1 CER vs the M1-09 beam", "",
              f"Harness frame T {f(m['T_harness'], 3)} (fit on the first half of val); M1-09 frame T {f(m['T_m109'], 3)} (all val).", "",
              "| setting | frame T | LM weight | insertion bonus | CER pooled | CER mean over instances | sentence acc |", "|---|---|---|---|---|---|---|"]
        for r in m["rows"]:
            L.append(f"| {r['setting']} | {f(r['frame_T'], 3)} | {r['lm_weight']} | {r['insertion_bonus']} | {f(r['cer_pooled'])} | "
                     f"{f(r['cer_mean_over_instances'])} | {f(r['sentence_acc'], 4)} |")
    e = d.get("emg_decoder")
    if e:
        ch = e["chance"]
        L += ["", "## sEMG key decoder (day-2 presses, 27 classes)", "",
              f"Chance: uniform 1/27 = {f(ch['uniform'])}; uniform over letters 1/26 = {f(ch['letters_uniform'])}; majority class (space) {f(ch['majority_space'])}.", "",
              "| run | n | accuracy | balanced accuracy | letter accuracy | space accuracy | top-5 |", "|---|---|---|---|---|---|---|"]
        for k, v in e["runs"].items():
            L.append(f"| {k} | {v['n']} | {f(v['acc'])} | {f(v['balanced_acc'])} | {f(v['acc_letters'])} | {f(v['acc_space'])} | {f(v['top5'])} |")
    (HERE / "fixchecks/results/tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    baselines()
    ablation()
    user_model()
    leakage()
    fixchecks()
    print("ok")
