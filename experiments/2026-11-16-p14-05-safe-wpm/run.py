"""P14-05: safe WPM baselines (CPU only). Definition: docs/safe-wpm.md, code: fidetype.benchmark.safe_wpm.

Stages (default: tracks t15-m4-12 t12; add t15-m4-13 when M4-13 has finished):
  tracks          leaderboard v0.1 entries: add the `safe_wpm` block to benchmark/results/v0.1/*.json
                  (only that key changes), from the committed per-trial items; then rebuild benchmark/site
  t15-m4-12       T15 M4-12 + P14-03 drop-in guard (alpha 0.05): P14-03 decisions, read only
  t12             T12 v2 + P14-03 drop-in guard (alpha 0.05): P14-03 decisions, read only
  t15-m4-13       T15 M4-13 + the same drop-in recipe: calibrate on val_select, decide val_eval (about 6 min CPU)
  t15-m4-12-recompute   the t15-m4-13 code path on M4-12 (check: must give the P14-03 decisions)

Run (repo root), one command per new decoder:
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-16-p14-05-safe-wpm/run.py t15-m4-13
Per-trial files (with truth text): C:/Users/zhang/bci-data/derived/p14-05-safe-wpm/ only.
Repo: results/safe-wpm.json (aggregates only), results/guard-*.json (no signal, no text).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype import __version__ as FT_VERSION  # noqa: E402
from fidetype.benchmark.safe_wpm import (  # noqa: E402
    CorrectionRule,
    controls_from_sheet,
    format_line,
    guarantee_from_sheet,
    model_neural_s,
    safe_wpm,
    summarize_controls,
)

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p14-05-safe-wpm"  # the only place this task writes per-trial files
assert OWN.name == "p14-05-safe-wpm"
OUT = HERE / "results"
RESULTS = REPO / "benchmark" / "results" / "v0.1"
TRUTH_DIR = Path("C:/Users/zhang/bci-data/benchmark")
B2T_PKL = Path("C:/Users/zhang/bci-data/brain-to-text-25/t15_copyTask.pkl")
BIN_S = 0.02  # B2T '24 / '25 neural feature bins (fidetype.adapters.b2t25.BIN_S)
ALPHA, DELTA, SEED = 0.05, 0.1, 0
B = 2000
LOGF = OUT / "run.log"


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def norm(t: str | None) -> str:
    return " ".join((t or "").split())


def not_certified_block(controls: dict | None, note: str) -> dict:
    out = {"definition": "safe-wpm/0.1", "value": None, "ci": None, "status": "not-certified", "method": "none",
           "note": note}
    if controls:
        out["controls"] = summarize_controls(controls)
    return out


# ---------------------------------------------------------------------------
# Leaderboard tracks
# ---------------------------------------------------------------------------


def b2t_durations() -> dict[str, float]:
    """Measured speech duration per benchmark trial id (t15_copyTask.pkl, CC0)."""
    from fidetype.adapters.b2t25 import load_copytask

    return {f"t15-copytask-{t.index:04d}": float(t.speech_duration_s) for t in load_copytask(B2T_PKL, verify=True)}


def stage_tracks() -> dict:
    from fidetype.benchmark.leaderboard import build
    from fidetype.benchmark.prepare import read_truth
    from fidetype.benchmark.registry import get_track
    from fidetype.benchmark.scoring import to_jsonable
    from fidetype.benchmark.splits import load_split

    ib = load_module("import_baselines", REPO / "tools/benchmark/import_baselines.py")
    summary: dict = {}
    files = {p.stem: p for p in RESULTS.glob("*.json")}

    def write(stem: str, block: dict) -> None:
        p = files[stem]
        d = json.loads(p.read_text(encoding="utf-8"))
        d["safe_wpm"] = to_jsonable(block)
        p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        summary[stem] = {k: block.get(k) for k in ("value", "ci", "status", "method", "alpha", "delta", "n_cal",
                                                   "measured_wrong_commit", "measured_wrong_commit_cp95", "n_trials",
                                                   "n_commits", "n_wrong_commits", "unguarded_wpm", "wpm_no_penalty",
                                                   "no_bci_wpm", "timing", "controls", "note")}
        log(f"{stem}: " + (format_line(block) if block.get("n_trials") else f"{block['status']} ({block.get('note')})"))

    def per_trial(stem: str, track: str, items_rel: str, truth_name: str, neural: dict[str, float] | None,
                  kinds=("trust", "crc", "ltt")) -> None:
        t = get_track(track)
        split = load_split(track)
        ids = split.ids("test")
        clusters = [r["clusters"] for r in split.trials("test")]
        tr = read_truth(TRUTH_DIR / truth_name)
        nc = np.array([len(tr[i]["text"]) for i in ids], float)
        nw = np.array([len(tr[i]["text"].split()) for i in ids], float)
        if neural is not None:
            ns = np.array([neural[i] for i in ids], float)
            timing = "measured per-trial speech duration (t15_copyTask.pkl speech_duration_s)"
        else:
            cpm = t.user_model.config["chars_per_min"]
            ns = model_neural_s(nc, cpm)
            timing = f"track rate model: len(truth) * 60 / {cpm:g} chars/min (no per-trial timing in the committed data)"
        d = ib.load(items_rel)
        fit, test = ib.Items(d["fit"]), ib.Items(d["test"])
        th = ib.thresholds(fit)
        for kind in kinds:
            name = f"{stem}__{kind}"
            res = json.loads(files[name].read_text(encoding="utf-8"))
            on = test.s >= th[kind]
            # Consistency with the committed entry (same threshold, same items).
            cr = res["metrics"]["commit_rate"]["value"]
            assert abs(float(on.mean()) - cr) < 1e-9, (name, float(on.mean()), cr)
            correct = on & (test.wc_c == 0)
            g = res.get("guarantee") or {"method": "none"}
            if g.get("method", "none") == "none":
                g = {"method": "none"}
            blk = safe_wpm(on, correct, nw, nc, ns, guarantee=g, timing=timing, clusters=clusters, ci_unit=t.ci_unit,
                           controls=res.get("controls"), gaze_chars_per_min=t.user_model.gaze_chars_per_min, B=B,
                           seed=SEED)
            if blk["status"] == "not-certified":
                blk["note"] = "plug-in threshold fit, no certified bound; unguarded_wpm is for reference only"
            write(name, blk)

    log("tracks: loading B2T speech durations")
    dur = b2t_durations()
    per_trial("b2t25-t15-copytask__ours", "b2t25-t15-copytask", "2026-11-11-m2-13-conformal/results/items-b2t-ours.json",
              "b2t25-truth.jsonl", dur)
    per_trial("b2t25-t15-copytask__published", "b2t25-t15-copytask",
              "2026-11-11-m2-13-conformal/results/items-b2t-published.json", "b2t25-truth.jsonl", dur)
    per_trial("spanishbcbl-meg-async__convctc-m-async", "spanishbcbl-meg-async",
              "2026-11-11-g1-async-meg-trust/results/items-meg-async.json", "meg-truth.jsonl", None)

    # Toronto sEMG: only aggregates are committed. Approximate from them (no CI).
    track = "toronto-semg-composed"
    t = get_track(track)
    split = load_split(track)
    ids = split.ids("test")
    tr = read_truth(TRUTH_DIR / "emg-truth.jsonl")
    nc_all = np.array([len(tr[i]["text"]) for i in ids], float)
    nw_all = np.array([len(tr[i]["text"].split()) for i in ids], float)
    cpm = t.user_model.config["chars_per_min"]
    e = json.loads((REPO / "experiments/2026-11-11-emg-toronto/results/trust.json").read_text(encoding="utf-8"))
    for cond in ("calib", "xsession", "xsubject"):
        pc = e["conditions"][cond]["policies"]["c_crc"]
        name = f"{track}__cnn-{cond}__crc"
        res = json.loads(files[name].read_text(encoding="utf-8"))
        n = int(pc["n_test"])
        assert n == len(ids), (n, len(ids))
        k_commit = int(round(pc["rate_commit"] * n))
        k_wrong = int(round(pc["wrong_commit_rate"] * n))
        credit = float(pc["share_words_system"]) * nw_all.sum()  # words right because the system showed them
        t_neural = float(model_neural_s(nc_all, cpm).sum())
        t_pen = k_wrong * float(CorrectionRule().penalty(np.array([nc_all.mean()]))[0])
        # Build per-trial arrays with the same sums: the approximation is in the sums, not in the trials.
        committed = np.zeros(n, bool)
        committed[:k_commit] = True
        correct = committed.copy()
        correct[:k_wrong] = False
        nw_fake = np.zeros(n)
        nw_fake[k_wrong:k_commit] = credit / max(k_commit - k_wrong, 1)
        nc_fake = np.full(n, nc_all.mean())
        ns_fake = np.full(n, t_neural / n)
        blk = safe_wpm(committed, correct, nw_fake, nc_fake, ns_fake, guarantee=res.get("guarantee"),
                       timing=f"track rate model: len(truth) * 60 / {cpm:g} chars/min (composed sentences, no "
                             "natural typing time)", controls=res.get("controls"),
                       gaze_chars_per_min=t.user_model.gaze_chars_per_min)
        blk["committed_correct_words"] = round(credit, 1)
        blk["total_words"] = int(nw_all.sum())
        blk["no_bci_wpm"] = 60.0 * nw_all.sum() / (nc_all.sum() * 60.0 / t.user_model.gaze_chars_per_min)
        blk["minutes_correction"] = t_pen / 60.0
        blk["basis"] = ("aggregate approximation: committed-correct words = share_words_system x test words; "
                        "wrong-commit penalty at the mean test sentence length; no per-trial data, so no CI")
        write(name, blk)

    # Entries without a certified bound and without per-trial data.
    for stem in files:
        d = json.loads(files[stem].read_text(encoding="utf-8"))
        if "safe_wpm" in d and stem in summary:
            continue
        if "safe_wpm" in d and d["safe_wpm"].get("status") != "not-certified":
            continue
        write(stem, not_certified_block(d.get("controls"),
                                        f"policy '{(d.get('policy') or {}).get('name')}' has no certified bound"))
    info = build(RESULTS, REPO / "benchmark" / "site")
    log(f"leaderboard rebuilt: {info}")
    return summary


# ---------------------------------------------------------------------------
# Replay sets with the P14-03 drop-in guard
# ---------------------------------------------------------------------------


def t15_keys(npz_path: Path, sessions: list[str], part: str) -> list[str]:
    order = {s: j for j, s in enumerate(sessions)}
    z = np.load(npz_path)
    return sorted((k for k in z.files if f"|{part}|" in k), key=lambda k: (order[k.split("|")[0]], int(k.split("|")[2])))


def t15_durations(keys: list[str]) -> list[float]:
    """Trial duration = number of 20 ms neural bins of the trial (per-session npz, read only)."""
    d_in = DER / "m4-01-02-lookahead"
    cache: dict = {}
    out = []
    for k in keys:
        s, p, i, _ = k.split("|")
        if s not in cache:
            cache[s] = np.load(d_in / f"{s}.npz")
        out.append(cache[s][f"{p}_X{int(i)}"].shape[0] * BIN_S)
    return out


def replay_block(decisions: list[dict], durations: list[float], sheet: dict, label: str, timing: str) -> dict:
    truths = [norm(d["truth"]) for d in decisions]
    committed = [d["action"] == "commit" for d in decisions]
    correct = [c and norm(d["text"]) == t for c, d, t in zip(committed, decisions, truths)]
    blk = safe_wpm(committed, correct, [len(t.split()) for t in truths], [len(t) for t in truths], durations,
                   guarantee=guarantee_from_sheet(sheet), timing=timing, controls=controls_from_sheet(sheet), B=B,
                   seed=SEED)
    blk["set"] = label
    blk["config_id"] = sheet.get("config_id")
    blk["ci_note"] = "no CI: one participant; a trial bootstrap would be too narrow (see docs/safe-wpm.md)"
    log(f"{label}: {format_line(blk)}")
    return blk


def stage_t15_from_p1403() -> dict:
    d_in = DER / "m4-01-02-lookahead"
    sessions = json.loads((d_in / "sessions.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    keys = t15_keys(d_in / "logprobs-m4-12-fixed0.npz", sessions, "val_eval")
    dec = json.loads((DER / "p14-03-replay-validation/decisions-t15-a0.05.json").read_text(encoding="utf-8"))
    assert len(dec) == len(keys) == 701
    for k, d in zip(keys, dec):
        s, p, i, _ = k.split("|")
        assert norm(texts[s][p][int(i)]) == norm(d["truth"]), k
    sheet = json.loads((REPO / "experiments/2026-11-16-p14-03-replay-validation/results/guard-t15-a0.05.json")
                       .read_text(encoding="utf-8"))["sheet"]
    return replay_block(dec, t15_durations(keys), sheet, "T15 M4-12 (val_eval 701) + P14-03 drop-in guard",
                        "measured trial duration: 20 ms neural bins per val_eval trial (B2T '25)")


def stage_t12_from_p1403() -> dict:
    exp = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
    cfg = json.loads((exp / "config.json").read_text(encoding="utf-8"))
    d_in = Path(cfg["derived_dir"])
    prep = json.loads((exp / "results/prep.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    durs, truths = [], []
    for r in prep["sessions"]:
        if r["role"] != "test":
            continue
        z = np.load(d_in / f"{r['session']}.npz")
        for i, w in enumerate(texts[r["session"]]["pool"]):
            durs.append(z[f"pool_X{i}"].shape[0] * BIN_S)
            truths.append(w)
    dec = json.loads((DER / "p14-03-replay-validation/decisions-t12-a0.05.json").read_text(encoding="utf-8"))
    assert len(dec) == len(durs) == 400
    assert all(norm(a) == norm(d["truth"]) for a, d in zip(truths, dec))
    sheet = json.loads((REPO / "experiments/2026-11-16-p14-03-replay-validation/results/guard-t12-a0.05.json")
                       .read_text(encoding="utf-8"))["sheet"]
    return replay_block(dec, durs, sheet, "T12 v2 (10 test sessions, 400) + P14-03 drop-in guard",
                        "measured trial duration: 20 ms neural bins per trial (B2T '24)")


def stage_t15_compute(model: str) -> dict:
    """Calibrate the drop-in guard (P14-03 recipe) on val_select and decide val_eval for one T15 decoder."""
    import fidetype.trust as ft

    p1403 = load_module("p1403run", REPO / "experiments/2026-11-16-p14-03-replay-validation/run.py")
    Bm = p1403.B
    d_in = DER / "m4-01-02-lookahead"
    sessions = json.loads((d_in / "sessions.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    if model == "m4-13":
        cal_p = DER / "trust-reruns-m4-13" / "logprobs-m4-13-long0-val_select.npz"
        held_p = DER / "m4-13" / "logprobs-m4-13-long0-val_eval.npz"
        if not held_p.exists():
            held_p = DER / "trust-reruns-m4-13" / "logprobs-m4-13-long0-val_eval.npz"
    else:
        cal_p = DER / "m2-19-trust-retune" / "logprobs-m2-19-m4-12-fixed0.npz"
        held_p = d_in / "logprobs-m4-12-fixed0.npz"
    for p in (cal_p, held_p):
        if not p.exists():
            raise SystemExit(f"missing {p}: has the decoder (and the trust-reruns CPU decode) finished?")
    npz: dict = {}

    def part(path: Path, name: str):
        z = np.load(path)
        keys = t15_keys(path, sessions, name)
        xs, ts, ph = [], [], []
        for k in keys:
            s, p, i, _ = k.split("|")
            xs.append(z[k].astype(np.float32))
            ts.append(texts[s][p][int(i)])
            ph.append(p1403.ph_symbols(npz, d_in, s, p, int(i)))
        return keys, xs, ts, ph

    _, cx, ct, cph = part(cal_p, "val_select")
    hkeys, hx, ht, _ = part(held_p, "val_eval")
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    tune = bt.load_json("tune.json")
    dec = bt.Decoders([], {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    fn = p1403.make_decode_fn(dec)
    t0 = time.time()
    guard = ft.calibrate(cx, ct, alpha=ALPHA, delta=DELTA, vocab=list(Bm.SYMBOL_VOCAB), blank=0,
                         input_scale="log_probs", frame_period=0.08, decode_fn=fn, stream_texts=cph,
                         decoder_name=f"p14-05-t15-{model}", modality="intracortical", name=f"p14-05-t15-{model}",
                         seed=SEED)
    log(f"t15-{model}: calibrated {guard.config_id} in {time.time() - t0:.0f} s")
    res = [guard.decide(x, utterance_id=f"t15-{model}-{i}") for i, x in enumerate(hx)]
    decisions = [{"i": i, "key": k, "action": r.action, "raw": r.raw_action, "p_top1": r.p_top1, "text": r.text,
                  "truth": norm(t)} for i, (k, r, t) in enumerate(zip(hkeys, res, ht))]
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / f"decisions-t15-{model}.json").write_text(json.dumps(decisions, indent=0), encoding="utf-8")
    guard.save(OUT / f"guard-t15-{model}.json")
    sheet = guard.sheet.to_dict()
    return replay_block(decisions, t15_durations(hkeys), sheet,
                        f"T15 {model.upper()} (val_eval {len(hx)}) + drop-in guard (P14-03 recipe, recomputed)",
                        "measured trial duration: 20 ms neural bins per val_eval trial (B2T '25)")


STAGES = {
    "tracks": stage_tracks,
    "t15-m4-12": stage_t15_from_p1403,
    "t12": stage_t12_from_p1403,
    "t15-m4-13": lambda: stage_t15_compute("m4-13"),
    "t15-m4-12-recompute": lambda: stage_t15_compute("m4-12"),
}


def main() -> None:
    stages = sys.argv[1:] or ["tracks", "t15-m4-12", "t12"]
    bad = [s for s in stages if s not in STAGES]
    if bad:
        raise SystemExit(f"unknown stage(s) {bad}; known: {list(STAGES)}")
    OUT.mkdir(exist_ok=True)
    path = OUT / "safe-wpm.json"
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr["fidetype_version"] = FT_VERSION
    allr["definition"] = "safe-wpm/0.1 (docs/safe-wpm.md)"
    allr.setdefault("stages", {})
    for st in stages:
        t0 = time.time()
        log(f"stage {st} start")
        out = STAGES[st]()
        allr["stages"][st] = {"seconds": round(time.time() - t0, 1), "result": out}
        from fidetype.benchmark.scoring import to_jsonable

        path.write_text(json.dumps(to_jsonable(allr), indent=1, default=str) + "\n", encoding="utf-8")
        log(f"stage {st} done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
