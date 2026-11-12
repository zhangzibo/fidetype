# M1-09 near-variant, per-participant and like-for-like analysis (2026-11-11). CPU only (repo .venv).
# Reuses the "close" test-sentence set from the M1-15 analysis (nearest train sentence CER <= 0.25).
# Run: .venv\Scripts\python.exe -I experiments/2026-11-11-m1-09-async-full/analysis/analyse.py
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
from fidetype.streams.vocab import normalize_text  # noqa: E402

OUT = Path(__file__).resolve().parent
S = Path("C:/Users/zhang/bci-data/streams")
EXP = REPO / "experiments"
CACHE = Path("C:/Users/zhang/bci-data/cache/spanishbcbl/v1")
# Same rule as M1-15 analysis/analyse.py: a test sentence is "close" if a train sentence (non-practice) is within CER 0.25.
from fidetype.eval.metrics import cer  # noqa: E402

_train, _test = set(), set()
for _f in CACHE.glob("S*/*.json"):
    for _s in json.load(open(_f, encoding="utf-8"))["segments"]:
        if _s.get("is_training"):
            continue
        _t = normalize_text(_s["target_text"])
        if _s["split"] == "train":
            _train.add(_t)
        elif _s["split"] == "test":
            _test.add(_t)
NEAREST = {t: min((cer(t, x), x) for x in _train) for t in _test}
CLOSE = {t for t, (c, _) in NEAREST.items() if c <= 0.25}
assert len(_test) == 17 and len(CLOSE) == 6, (len(_test), len(CLOSE))


def jl(p):
    return [json.loads(x) for x in open(p, encoding="utf-8") if x.strip()]


def boot(d, n=10000, seed=0):
    d = np.asarray(d, float)
    idx = np.random.default_rng(seed).integers(0, len(d), (n, len(d)))
    m = d[idx].mean(1)
    return [float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


# subject -> participant map (from the M1-09 per-sentence rows)
P = {}
for sp in ("val", "test"):
    for r in jl(S / "m1-09-r4b-full-medium" / f"per_sentence_{sp}.jsonl"):
        P[r["subject"]] = r["participant"]


def load_async(run, beam_dir):
    """Rows in labels.jsonl order with per-instance CER (vs target) for each decoder and input."""
    lab = jl(S / run / "test" / "labels.jsonl")
    pb = json.load(open(beam_dir / "per_sentence_cer.json", encoding="utf-8"))["test"]
    rows = []
    for i, l in enumerate(lab):
        r = dict(file=l["file"], subject=l["subject"], participant=P[l["subject"]], text=normalize_text(l["target_text"]))
        for kind in ("real", "shuffled", "zeros"):
            for dec, key in (("greedy", "greedy"), ("beam_lm", "beam_lm_valtuned")):
                r[f"{kind}/{dec}"] = pb[kind][key][i]
        rows.append(r)
    ps = {r["file"]: r["cer_target"] for r in jl(S / run / "per_sentence_test.jsonl")}
    diff = max(abs(ps[r["file"]] - r["real/greedy"]) for r in rows)
    return rows, diff


def summ(rows, k):
    v = [r[k] for r in rows]
    byp, bys = defaultdict(list), defaultdict(list)
    for r in rows:
        byp[r["participant"]].append(r[k])
        bys[r["subject"]].append(r[k])
    return dict(n=len(v), sent=float(np.mean(v)), subj=float(np.mean([np.mean(x) for x in bys.values()])),
                part=float(np.mean([np.mean(x) for x in byp.values()])))


def rd(d):
    return {a: (round(b, 3) if isinstance(b, float) else b) for a, b in d.items()}


out = {"close_sentences": sorted(CLOSE)}
runs = {"small": ("m1-09-r4b-full", EXP / "2026-11-11-m1-09-async-full/results/beam-m1-09-r4b-full"),
        "medium": ("m1-09-r4b-full-medium", EXP / "2026-11-11-m1-09-async-full/results/beam-m1-09-r4b-full-medium")}
data = {}
for name, (run, bd) in runs.items():
    rows, diff = load_async(run, bd)
    data[name] = rows
    print(f"== {name} ({run}) n={len(rows)}; max |CPU beam-file greedy - GPU infer greedy| = {diff:.2e}")
    res = {"cpu_vs_gpu_greedy_max_abs_diff": diff}
    far = [r for r in rows if r["text"] not in CLOSE]
    close = [r for r in rows if r["text"] in CLOSE]
    for k in ("real/greedy", "real/beam_lm", "shuffled/greedy", "shuffled/beam_lm", "zeros/greedy", "zeros/beam_lm"):
        res[k] = dict(all=summ(rows, k), far=summ(far, k), close=summ(close, k), far_ci=boot([r[k] for r in far]))
        print(k, "all", rd(res[k]["all"]), "| far", rd(res[k]["far"]), "| close", rd(res[k]["close"]))
    for dec in ("greedy", "beam_lm"):
        res[f"far_gap_shuffled_minus_real/{dec}"] = boot([r[f"shuffled/{dec}"] - r[f"real/{dec}"] for r in far])
        print("far shuffled gap", dec, [round(x, 3) for x in res[f"far_gap_shuffled_minus_real/{dec}"]])
    pp = {}
    for dec in ("greedy", "beam_lm"):
        byp = defaultdict(list)
        for r in rows:
            byp[r["participant"]].append(r[f"real/{dec}"])
        m = np.array([np.mean(v) for v in byp.values()])
        pp[dec] = dict(n_participants=len(m), mean=float(m.mean()), sem=float(m.std(ddof=1) / np.sqrt(len(m))),
                       median=float(np.median(m)), min=float(m.min()), max=float(m.max()),
                       n_le_0_59=int((m <= 0.59).sum()), n_le_0_50=int((m <= 0.50).sum()),
                       n_instances_min=int(min(len(v) for v in byp.values())),
                       n_instances_max=int(max(len(v) for v in byp.values())))
        print("per participant", dec, rd(pp[dec]))
    res["per_participant"] = pp
    out[name] = res

assert all(m["file"] == s["file"] for m, s in zip(data["medium"], data["small"]))
for dec in ("greedy", "beam_lm"):
    out[f"medium_minus_small/{dec}"] = boot([m[f"real/{dec}"] - s[f"real/{dec}"] for m, s in zip(data["medium"], data["small"])])
    print("medium - small", dec, [round(x, 3) for x in out[f"medium_minus_small/{dec}"]])

# like for like vs M1-C (20 blocks; streams m1c-r4-small-aux0.5-pretrained, beam M1-C2 val-tuned)
lab_c = jl(S / "m1c-r4-small-aux0.5-pretrained" / "test" / "labels.jsonl")
pb_c = json.load(open(EXP / "2026-11-08-m1c2-beam-lm/results/per_sentence_cer.json", encoding="utf-8"))["test"]
mc = {l["file"]: dict(greedy=pb_c["real"]["greedy"][i], beam_lm=pb_c["real"]["beam_lm_valtuned"][i],
                      text=normalize_text(l["target_text"]), subject=l["subject"]) for i, l in enumerate(lab_c)}
med = {r["file"]: r for r in data["medium"]}
sml = {r["file"]: r for r in data["small"]}
common = [f for f in mc if f in med]
assert all(mc[f]["text"] == med[f]["text"] for f in common)
print(f"== like for like vs M1-C: {len(common)} of {len(mc)} M1-C test instances are in the M1-09 test set")
ll = {"n_common": len(common), "n_m1c": len(mc)}
far_c = [f for f in common if mc[f]["text"] not in CLOSE]
ll["n_far_common"] = len(far_c)
for dec in ("greedy", "beam_lm"):
    rows_c = [dict(participant=P[mc[f]["subject"]], subject=mc[f]["subject"], v=mc[f][dec]) for f in common]
    ll[f"m1c/{dec}"] = summ(rows_c, "v")
    for nm, src in (("small", sml), ("medium", med)):
        ll[f"{nm}/{dec}"] = summ([dict(participant=src[f]["participant"], subject=src[f]["subject"], v=src[f][f"real/{dec}"])
                                  for f in common], "v")
        ll[f"{nm}_minus_m1c/{dec}"] = boot([src[f][f"real/{dec}"] - mc[f][dec] for f in common])
    ll[f"far/m1c/{dec}"] = float(np.mean([mc[f][dec] for f in far_c]))
    ll[f"far/medium/{dec}"] = float(np.mean([med[f][f"real/{dec}"] for f in far_c]))
    ll[f"far/medium_minus_m1c/{dec}"] = boot([med[f][f"real/{dec}"] - mc[f][dec] for f in far_c])
    for k, v in ll.items():
        if k.endswith(dec):
            print(k, rd(v) if isinstance(v, dict) else ([round(x, 3) for x in v] if isinstance(v, list) else round(v, 3)))
out["like_for_like_m1c"] = ll

# async (medium) vs sync M1-15 full-r1 on the same instances
sync = {r["file"]: r for r in jl(S / "m1-15-sentence-context-full-r1" / "per_sentence_greedy_test.jsonl")}
syncb = {r["file"]: r for r in jl(S / "m1-15-sentence-context-full-r1" / "per_sentence_beam_lm_test.jsonl")}
cm = [f for f in med if f in sync]
out["async_medium_minus_sync_full_r1"] = dict(
    n=len(cm), greedy=boot([med[f]["real/greedy"] - sync[f]["cer_target"] for f in cm]),
    beam_lm=boot([med[f]["real/beam_lm"] - syncb[f]["cer_target"] for f in cm]))
print("async medium - sync full-r1 (same instances)", out["async_medium_minus_sync_full_r1"])
json.dump(out, open(OUT / "analysis.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", OUT / "analysis.json")
