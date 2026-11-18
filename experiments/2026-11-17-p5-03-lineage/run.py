"""P5-03 / P5-04 demo: full lineage of one committed word on the Brain-to-Text '25 replay (CPU only).

Exit criterion of roadmap P5: "The ledger reproduces the full lineage of one committed word."

Rebuilds the M6-06 / M2-09 trust pipeline on B2T '25 (T15, CC0; our phoneme -> word decoder over the
published online RNN logits) on a SUBSET (every 4th trial of the fit half for the fit, every 12th trial of
the test half for the replay), because this demo is about the ledger, not about the metrics. Before the
replay it writes the lineage into the ledger:

- sources: the B2T '25 track (``record_track_source("b2t25-t15")``: CC0 1.0), Tatoeba English (CC BY 2.0 FR),
  CMUdict (BSD-2-Clause);
- artifacts: the RNN logits ("weights" of the published decoder, derived from the T15 data; its digest is
  the dataset file's SHA-256), the LM (char 6-gram + lexicon, derived from Tatoeba + CMUdict, file
  SHA-256s), the calibration (derived from the T15 data and the decoder; the fit-subset id);
- the context names these three artifacts (``lineage``).

Then: pick the first COMMIT that the oracle confirmed, write its lineage report (``lineage_report``, word 0),
check the licence flags, try a product artifact (refused: CC BY in the LM under the project rule), and
erase that decision (P5-04 redaction) in a copy of the ledger: verify must still pass.

Run (repo root; heavy part through the isolation runner)::

    .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
        .venv\\Scripts\\python.exe -I experiments/2026-11-17-p5-03-lineage/run.py
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import gzip  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.trust.licence import LicenceError  # noqa: E402
from fidetype.trust.provenance import (  # noqa: E402
    LedgerView,
    ProvenanceLedger,
    file_sha256,
    lineage_report,
    read_entries,
    verify,
)

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
LOG = OUT / "run.log"


def log(*a) -> None:
    msg = time.strftime("%H:%M:%S") + " " + " ".join(str(x) for x in a)
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> None:
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig

    t0 = time.time()
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    prep, tune = bt.load_json("prep.json"), bt.load_json("tune.json")
    trials = bt.load_trials()
    fit_all, test_all = bt.split(trials)
    fit, test = fit_all[::4], test_all[::12]
    best = tune["best"]
    wkw = {k: best[k] for k in ("lm_weight", "edit_penalty", "word_bonus")}
    dec = bt.Decoders(trials, wkw)
    user = UserConfig.aac_gaze(chars_per_min=prep["speech_rate_125k"]["chars_per_min"])
    streams = {t.index: bt.B.to_symbol_stream(bt.B.trial_stream(t)) for t in fit + test}

    def mk(ts, split):
        out = []
        for t in ts:
            it = Item(streams[t.index], t.truth_words, stream_text=t.truth_symbols)
            it.ref = f"b2t25-{split}-trial-{t.index}"
            out.append(it)
        return out

    fi, ti = mk(fit, "fit"), mk(test, "test")
    log(f"loaded {len(fi)} fit / {len(ti)} test trials (subset) ({time.time() - t0:.0f}s)")

    cfgs = bt.CONFIG
    pkl_sha = file_sha256(cfgs["pkl"])
    path = OUT / "ledger.jsonl"
    if path.exists():
        path.unlink()
    led = ProvenanceLedger(path, text_mode="store", id_mode="hash")
    led.note({"event": "replay start", "experiment": "2026-11-17-p5-03-lineage", "code": git_head()})
    # --- lineage: sources and artifacts ---
    t15 = led.record_track_source("b2t25-t15", digest=pkl_sha)
    tato = led.record_source("Tatoeba English sentences", "CC BY 2.0 FR", url="https://tatoeba.org",
                             digest=file_sha256(cfgs["tatoeba_eng"]))
    cmu = led.record_source("CMUdict", "BSD-2-Clause", url="https://github.com/cmusphinx/cmudict",
                            digest=file_sha256(cfgs["cmudict"]))
    rnn = led.record_artifact("weights", "card2024-online-rnn (published logits)", derived_from=[t15],
                              version="t15-copytask-online", sha256=pkl_sha,
                              details={"note": "logits come with the dataset file; no weights file here"})
    lm = led.record_artifact("lm", "tatoeba-eng-char-6gram-mkn + cmudict lexicon", derived_from=[tato, cmu],
                             sha256=file_sha256(cfgs["char_lm"]))
    cal_set = f"b2t25-fit-subset-{len(fi)}-trials (every 4th of the per-day first half)"
    cal = led.record_artifact("calibration", "M6-06 plug-in gate fit", derived_from=[t15, rnn, lm],
                              details={"calibration_set_id": cal_set})
    product_refusal = None
    try:
        led.record_artifact("lm", "product LM", derived_from=[tato, cmu], purpose="product")
    except LicenceError as e:
        product_refusal = str(e)
    log("product LM under the project rule:", "refused" if product_refusal else "ALLOWED (unexpected)")

    ts = time.time()
    pipe = TrustPipeline(dec.words_fn, HarnessConfig(seed=bt.SEED, user_config=user,
                                                     max_wrong_commit=cfgs["max_wrong_commit"]), {})
    pipe.fit(fi, fi)
    prov = {
        "adapter": {"name": "fidetype.adapters.b2t25", "version": git_head(), "source_file_sha256": pkl_sha},
        "decoder": {"name": "card2024-online-rnn + fidetype PhonemeWordDecoder",
                    "version": f"t15-copytask-online; words {json.dumps(wkw, sort_keys=True)}"},
        "lm": {"name": "tatoeba-eng-char-6gram-mkn + cmudict"},
        "calibration_set_id": cal_set,
        "lineage": [rnn, lm, cal],
    }
    pipe.attach_ledger(led, prov, corrections="oracle")
    m = pipe.evaluate(ti)
    recs = m.pop("records")
    log(f"fit + replay: eWPM {m['ewpm']:.3f} wrong-commit {m['wrong_commit_rate']:.4f} commit "
        f"{m['rate_commit']:.3f} on {len(recs)} trials ({time.time() - ts:.0f}s)")
    anchor = led.anchor()

    entries = read_entries(path)
    res = verify(path, expected_head=anchor)
    view = LedgerView(entries)
    # The first COMMIT whose shown text equals the truth (oracle wrote no correction, or a confirmation).
    pick = None
    for did, e in view.decisions.items():
        b = e["body"]
        if b["action"] == "COMMIT" and b.get("shown") and not view.is_wrong_commit(did):
            pick = did
            break
    report = lineage_report(entries, pick, word=0, expected_head=anchor) if pick else "no confirmed commit"
    (OUT / "lineage-report.md").write_text(report + "\n", encoding="utf-8")
    lin = view.lineage(pick) if pick else None
    flags = {"decisions": len(view.decisions),
             "with_licence_flags": sum("licence" in e["body"] for e in view.decisions.values()),
             "research_only": sum(e["body"].get("licence", {}).get("research_only", False)
                                  for e in view.decisions.values())}

    # P5-04: erase the picked decision in a copy; the chain must still verify.
    copy = OUT / "ledger-erased-copy.jsonl"
    shutil.copyfile(path, copy)
    led2 = ProvenanceLedger(copy)
    red = led2.redact_decisions([pick], request_ref="demo-erasure-0001") if pick else None
    res2 = verify(copy)
    gone = pick is not None and pick not in LedgerView(copy).decisions

    raw = path.stat().st_size
    with open(path, "rb") as f_in, gzip.open(str(path) + ".gz", "wb", compresslevel=9) as f_out:
        shutil.copyfileobj(f_in, f_out)
    path.unlink()
    copy.unlink()
    summary = {
        "anchor": anchor,
        "verify": {"ok": res.ok, "n_entries": res.n_entries, "errors": res.errors[:5],
                   "ok_gz": verify(str(path) + ".gz", expected_head=anchor).ok},
        "entry_kinds": {k: sum(e["kind"] == k for e in entries)
                        for k in ("genesis", "note", "source", "artifact", "context", "decision", "correction")},
        "subset": {"fit": len(fi), "test": len(ti)},
        "metrics_subset": {"ewpm": m["ewpm"], "wrong_commit_rate": m["wrong_commit_rate"],
                           "rate_commit": m["rate_commit"]},
        "picked_decision": pick,
        "lineage": None if lin is None else {
            "n_entries": len(lin["entries"]), "kinds": [x["kind"] for x in lin["entries"]],
            "artifacts": [a["body"]["artifact"]["kind"] for a in lin["artifacts"]],
            "sources": [s["body"]["source"]["licence"] for s in lin["sources"]], "licence": lin["licence"]},
        "licence_flags": flags,
        "product_lm_refused": product_refusal is not None,
        "erasure": {"redaction_seq": None if red is None else red["seq"],
                    "n_redacted": None if red is None else red["body"]["n"],
                    "verify_after": res2.ok, "decision_gone": gone},
        "bytes": {"ledger_jsonl": raw, "ledger_jsonl_gz": Path(str(path) + ".gz").stat().st_size},
        "elapsed_s": time.time() - t0,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    log(f"verify {res.ok}; lineage of {pick}: {summary['lineage'] and summary['lineage']['n_entries']} entries; "
        f"erasure verify {res2.ok}; done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
