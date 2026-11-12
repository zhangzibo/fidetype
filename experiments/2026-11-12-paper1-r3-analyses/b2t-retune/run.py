"""R3 item 4: re-tune the B2T word decoder on fit-A only.

Stats review M4(c). The word-decoder grid (LM weight, edit penalty, word
bonus; 12 points) was tuned on a random 400 of the 812 fit trials
(``b2t25-trust/run.py`` ``stage_tune``). About half of each clean
calibration set (fit-B) overlaps that tuning set. Here the same tuning
procedure (same grid, same criterion: lowest pooled WER, then highest
truth-in-n-best; raw streams, no temperature) runs on the fit-A trials of
split A (``alternate``) and split B (``chrono``) only. If the selected grid
point equals the paper's (lm_weight 1.0, edit_penalty 12, word_bonus 3),
the decoder is the same and every clean CRC / LTT row is unchanged. If not,
the clean rows are re-run with the fit-A-tuned decoder.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r3-analyses/b2t-retune/run.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common3 as K  # noqa: E402

C = K.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
M13 = C.load_module("m213run", C.REPO / "experiments/2026-11-11-m2-13-conformal/run.py")


def fit_a(ctx, split: str):
    by_day: dict = {}
    for i, t in enumerate(ctx.fit):
        by_day.setdefault(t.post_implant_day, []).append(i)
    A, Bi = [], []
    for d, idx in sorted(by_day.items()):
        if split == "alternate":
            A += idx[0::2]
            Bi += idx[1::2]
        else:
            h = (len(idx) + 1) // 2
            A += idx[:h]
            Bi += idx[h:]
    return [ctx.fit[i] for i in sorted(A)], [ctx.fit[i] for i in sorted(Bi)]


def tune(bt, dec, trials) -> dict:
    t0 = time.time()
    ph = {t.index: dec.phonemes(bt.B.to_symbol_stream(bt.B.trial_stream(t))) for t in trials}
    g = bt.CONFIG["word_decoder_grid"]
    rows = []
    refs = [t.truth_words for t in trials]
    for lw in g["lm_weight"]:
        for ep in g["edit_penalty"]:
            for wb in g["word_bonus"]:
                kw = {**bt.CONFIG["word_decoder_fixed"], "lm_weight": lw, "edit_penalty": ep, "word_bonus": wb}
                wd = dec.make_wdec(kw)
                tops, inn = [], []
                for t in trials:
                    hs = wd.decode(ph[t.index])
                    tops.append(hs[0].text if hs else "")
                    inn.append(t.truth_words in [h.text for h in hs])
                rows.append({"lm_weight": lw, "edit_penalty": ep, "word_bonus": wb, "wer": bt.pooled(refs, tops, True),
                             "sentence_exact": float(np.mean([a == b for a, b in zip(refs, tops)])), "truth_in_nbest": float(np.mean(inn))})
    best = min(rows, key=lambda r: (r["wer"], -r["truth_in_nbest"]))
    return {"n": len(trials), "rows": rows, "best": best, "seconds": round(time.time() - t0, 1)}


def main() -> None:
    ctx = C.b2t_ctx()
    bt = ctx.bt
    paper = {k: ctx.bt.load_json("tune.json")["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")}
    # Overlap of the paper's tuning set with each clean calibration set
    rng = np.random.default_rng(bt.SEED)
    tune_idx = set(t.index for t in [ctx.fit[i] for i in sorted(rng.choice(len(ctx.fit), min(bt.CONFIG["tune_trials"], len(ctx.fit)), replace=False))])
    res = {"paper_choice": paper, "splits": {}}
    for split, lab in (("alternate", "split A"), ("chrono", "split B")):
        A, Bc = fit_a(ctx, split)
        r = tune(bt, ctx.dec, A)
        sel = {k: r["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")}
        r["same_as_paper"] = sel == paper
        r["overlap_tuning_set_with_clean_cal"] = {"n_cal": len(Bc), "n_overlap": sum(t.index in tune_idx for t in Bc),
                                                  "n_fitA_overlap": sum(t.index in tune_idx for t in A)}
        rank = sorted(r["rows"], key=lambda x: (x["wer"], -x["truth_in_nbest"]))
        r["paper_point_rank"] = next(i for i, x in enumerate(rank) if all(x[k] == paper[k] for k in paper)) + 1
        C.log(f"{lab}: fit-A tune best {sel} (paper {paper}) same={r['same_as_paper']}; paper point rank {r['paper_point_rank']}; "
              f"overlap {r['overlap_tuning_set_with_clean_cal']} ({r['seconds']}s)")
        if not r["same_as_paper"]:
            r["rerun"] = rerun(ctx, A, Bc, sel, split)
        res["splits"][lab] = r
        C.dump(res, OUT / "retune.json")
    L = ["# B2T word decoder re-tuned on fit-A only", "",
         f"Paper choice (tuned on a random 400 of the 812 fit trials): {paper}.", "",
         "| split | n fit-A | fit-A choice | same as paper | rank of the paper point on fit-A (of 12) | WER best / paper point | clean cal trials also in the paper tuning set |",
         "|---|---|---|---|---|---|---|"]
    for lab, r in res["splits"].items():
        pp = next(x for x in r["rows"] if all(x[k] == paper[k] for k in paper))
        o = r["overlap_tuning_set_with_clean_cal"]
        L.append(f"| {lab} | {r['n']} | lm {r['best']['lm_weight']}, edit {r['best']['edit_penalty']}, bonus {r['best']['word_bonus']} | "
                 f"{r['same_as_paper']} | {r['paper_point_rank']} | {r['best']['wer']:.4f} / {pp['wer']:.4f} | {o['n_overlap']} of {o['n_cal']} |")
    for lab, r in res["splits"].items():
        if "rerun" in r:
            L += ["", f"## {lab}: clean rows with the fit-A-tuned decoder", "", "| rule | wrong-commit | commit rate | error among commits | eWPM |", "|---|---|---|---|---|"]
            for k, v in r["rerun"]["test"].items():
                L.append(f"| {k} | {v['wrong_commit']:.4f} | {v['commit_rate']:.3f} | {C.fmt(v['error_among_commits'], 3)} | {v['ewpm']:.2f} |")
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")
    C.log("done")


def rerun(ctx, A, Bc, sel: dict, split: str) -> dict:
    bt = ctx.bt
    dec = bt.Decoders(ctx.trials, sel)
    cached = C.DiskCachedDecoder(dec.words_fn, f"b2t-words-retune-{split}")
    dec.words_fn = cached
    out = {"decoder": sel, "test": {}}
    T = ctx.items(ctx.test)
    for which in ("ours", "published"):
        fn = dec.words_fn if which == "ours" else dec.published_plus_fn
        pipe = C.TrustPipeline(fn, C.HarnessConfig(seed=C.SEED, user_config=ctx.user, max_wrong_commit=C.ALPHA), {})
        pipe.fit(ctx.items(A), ctx.items(A))
        tb, tt = M13.item_table(pipe, ctx.items(Bc)), M13.item_table(pipe, T)
        cached.save()
        ca, te = K.arr(tb), K.arr(tt)
        lp = te["lam_old"]
        rc, rl = K.crc(ca), K.ltt(ca)
        for k, lam in (("plug-in (fit-A)", lp), ("CRC pure", rc.threshold), ("CRC max-rule", max(lp, rc.threshold)), ("LTT pure", rl.threshold)):
            out["test"][f"{which}: {k}"] = K.outcome(te, lam)
    return out


if __name__ == "__main__":
    main()
