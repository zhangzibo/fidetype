"""M2-09: provenance ledger demo on the Brain-to-Text '25 replay (CPU only).

Rebuilds the M6-06 trust pipeline on B2T '25 (our phoneme -> word decoder
over the published online RNN logits), fitted on the fit half exactly as
in M6-06 / M2-13, and a second pipeline with conformal risk control (CRC)
on the same fit half. Each pipeline evaluates the test half with a
provenance ledger attached. The oracle (ground truth) writes a correction
for every wrong commit, so the audit report can list them all.

Outputs (results/):
- ``ledger-store.jsonl.gz``: the ledger with text stored (B2T '25 is CC0;
  M6-06 already uses its sentences). Verify it with
  ``python -m fidetype.trust.provenance verify results/ledger-store.jsonl.gz``.
- ``ledger-hash-head.json``: the head of the same run in ``hash`` mode
  (text as HMAC-SHA256 with a throw-away key; the ledger itself is not kept).
- ``audit-report.md``: the audit report of the stored ledger.
- ``summary.json``: counts, the cross-check against the harness metrics,
  tamper checks, sizes and the time cost per entry.

Run (repo root):

    .venv\\Scripts\\python.exe -I experiments/2026-11-11-m2-09-provenance/run.py
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "2"
os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import gzip
import importlib.util
import json
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.trust.provenance import (  # noqa: E402
    LedgerView,
    ProvenanceLedger,
    audit_report,
    canonical_json,
    entry_hash,
    file_sha256,
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


def tamper_checks(entries: list[dict]) -> dict:
    """Edit, delete and reorder one entry each; verify must fail every time."""
    out = {}
    e = [json.loads(json.dumps(x)) for x in entries]
    i = next(k for k, x in enumerate(e) if x["kind"] == "decision" and x["body"]["action"] == "COMMIT")
    e[i]["body"]["scores"]["p_top1"] = 0.999
    out["edit_score"] = verify(e).errors[:2]
    e = [json.loads(json.dumps(x)) for x in entries]
    e[i]["body"]["action"] = "OFFER"
    e[i]["hash"] = entry_hash(e[i])
    out["edit_with_rehash"] = verify(e).errors[:2]
    e = [json.loads(json.dumps(x)) for x in entries]
    j = next(k for k, x in enumerate(e) if x["kind"] == "correction")
    del e[j]
    out["delete_correction"] = verify(e).errors[:2]
    e = [json.loads(json.dumps(x)) for x in entries]
    e[i], e[i + 1] = e[i + 1], e[i]
    out["reorder"] = verify(e).errors[:2]
    out["truncate_without_anchor_ok"] = verify(entries[:-3]).ok
    out["truncate_with_anchor"] = verify(entries[:-3], expected_head=entries[-1]["hash"]).errors[:1]
    out["all_detected"] = all(bool(out[k]) for k in ("edit_score", "edit_with_rehash", "delete_correction", "reorder",
                                                     "truncate_with_anchor"))
    return out


def main() -> None:
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig

    t0 = time.time()
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    prep, tune = bt.load_json("prep.json"), bt.load_json("tune.json")
    trials = bt.load_trials()
    fit, test = bt.split(trials)
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
    log(f"loaded {len(fi)} fit / {len(ti)} test trials ({time.time() - t0:.0f}s)")

    cfgs = bt.CONFIG
    prov = {
        "adapter": {"name": "fidetype.adapters.b2t25", "version": git_head(),
                    "source_dataset": "brain-to-text-25-copytask (CC0 1.0)",
                    "source_file_sha256": file_sha256(cfgs["pkl"])},
        "decoder": {"name": "card2024-online-rnn + fidetype PhonemeWordDecoder",
                    "version": f"t15-copytask-online; words {json.dumps(wkw, sort_keys=True)}",
                    "weights_sha256": None,
                    "weights_note": "the RNN logits come from the dataset file (source_file_sha256); no weights here",
                    "training_data": [{"dataset": "T15 intracortical speech data (Card et al. 2024); RNN trained by the authors",
                                       "licence": "logits released as CC0 1.0 in the B2T '25 copy-task file"}],
                    "phoneme_beam": cfgs["phoneme_beam"], "word_decoder": {**cfgs["word_decoder_fixed"], **wkw}},
        "lm": {"name": "tatoeba-eng-char-6gram-mkn + tatoeba word unigram + cmudict",
               "char_lm_sha256": file_sha256(cfgs["char_lm"]), "lexicon_sha256": file_sha256(cfgs["cmudict"]),
               "training_data": [{"dataset": "Tatoeba English sentences", "licence": "CC BY 2.0 FR"},
                                 {"dataset": "CMUdict", "licence": "BSD-2-Clause style"}]},
        "calibration_set_id": f"b2t25-fit-half-{len(fi)}-trials (per-day first half, file order)",
    }

    store_path = OUT / "ledger-store.jsonl"
    if store_path.exists():
        store_path.unlink()
    led = ProvenanceLedger(store_path, text_mode="store", id_mode="hash")
    led.note({"event": "replay start", "experiment": "2026-11-11-m2-09-provenance", "data": "B2T '25 test half"})
    cache: dict = {}
    metrics = {}
    pipes = {}
    for name, extra in (("plug-in (M6-06)", {}), ("crc", {"risk_control": "crc", "risk_control_fraction": 0.5})):
        ts = time.time()
        pipe = TrustPipeline(dec.words_fn, HarnessConfig(seed=bt.SEED, user_config=user,
                                                         max_wrong_commit=cfgs["max_wrong_commit"], **extra), cache)
        pipe.fit(fi, fi)
        pipe.attach_ledger(led, {**prov, "extra": {"gate": name}}, corrections="oracle")
        n_before = len(led.entries)
        te = time.time()
        m = pipe.evaluate(ti)
        dt_eval = time.time() - te
        recs = m.pop("records")
        n_dec = sum(len(r.actions) - r.actions.count("REPEAT") for r in recs)
        metrics[name] = {
            "policy_config": pipe.policy.config.__dict__,
            "ewpm": m["ewpm"], "wrong_commit_rate": m["wrong_commit_rate"], "rate_commit": m["rate_commit"],
            "n_test": len(recs), "n_decisions_expected": n_dec,
            "n_wrong_commits_harness": int(sum(r.wrong_commit for r in recs if r.committed_text is not None)),
            "n_silent_wrong_commits_harness": int(sum(r.wrong_commit and r.silent_error for r in recs
                                                      if r.committed_text is not None)),
            "ledger_entries_written": len(led.entries) - n_before,
            "eval_s": dt_eval,
        }
        pipes[name] = pipe
        log(f"{name}: eWPM {m['ewpm']:.3f} wrong-commit {m['wrong_commit_rate']:.4f} commit {m['rate_commit']:.3f} "
            f"entries {len(led.entries) - n_before} ({time.time() - ts:.0f}s)")
    anchor = led.anchor()

    # Time cost of the ledger alone: re-run the plug-in evaluation (decodes are cached) with and without it.
    pipe = pipes["plug-in (M6-06)"]
    an_cache: dict = {}
    pipe.run_items(ti, pipe.policy, an_cache)  # warm the analysis cache
    t1 = time.time()
    pipe.run_items(ti, pipe.policy, an_cache)
    t_plain = time.time() - t1
    hash_led = ProvenanceLedger(None, text_mode="hash", hash_key=secrets.token_bytes(32), key_id="demo-throwaway")
    pipe.attach_ledger(hash_led, {**prov, "extra": {"gate": "plug-in (M6-06)"}}, corrections="oracle")
    t1 = time.time()
    pipe.run_items(ti, pipe.policy, an_cache, ledger=hash_led)
    t_ledger = time.time() - t1
    n_hash = sum(e["kind"] == "decision" for e in hash_led.entries)
    hash_bytes = sum(len(canonical_json(e)) + 1 for e in hash_led.entries)
    (OUT / "ledger-hash-head.json").write_text(json.dumps({**hash_led.anchor(), "n_entries": len(hash_led.entries),
                                                           "bytes": hash_bytes}, indent=1), encoding="utf-8")
    log(f"time: run_items {t_plain:.2f}s without, {t_ledger:.2f}s with an in-memory hash-mode ledger "
        f"({n_hash} decisions; {1000 * (t_ledger - t_plain) / max(1, n_hash):.2f} ms per decision)")

    # Verify, report, tamper checks.
    entries = read_entries(store_path)
    res = verify(store_path, expected_head=anchor)
    view = LedgerView(entries)
    rep = audit_report(entries, max_items=15, expected_head=anchor)
    (OUT / "audit-report.md").write_text(rep + "\n", encoding="utf-8")
    raw_bytes = store_path.stat().st_size
    with open(store_path, "rb") as f_in, gzip.open(str(store_path) + ".gz", "wb", compresslevel=9) as f_out:
        shutil.copyfileobj(f_in, f_out)
    store_path.unlink()
    gz = Path(str(store_path) + ".gz")
    res_gz = verify(gz, expected_head=anchor)
    tam = tamper_checks(entries)
    summary = {
        "anchor": anchor,
        "verify": {"ok": res.ok, "ok_gz": res_gz.ok, "n_entries": res.n_entries, "errors": res.errors},
        "entry_kinds": {k: sum(e["kind"] == k for e in entries) for k in ("genesis", "note", "context", "decision", "correction")},
        "per_gate": metrics,
        "ledger_summary": view.summary(("extra.gate", "calibration.id", "policy.version")),
        "wrong_commits_in_ledger": len(view.wrong_commits()),
        "tamper": tam,
        "bytes": {"store_jsonl": raw_bytes, "store_jsonl_gz": gz.stat().st_size,
                  "hash_mode_plugin_only": hash_bytes, "per_decision_store": raw_bytes / max(1, len(view.decisions))},
        "time": {"run_items_without_s": t_plain, "run_items_with_hash_ledger_s": t_ledger,
                 "ms_per_decision": 1000 * (t_ledger - t_plain) / max(1, n_hash)},
        "elapsed_s": time.time() - t0,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    log(f"verify {res.ok} (gz {res_gz.ok}); entries {res.n_entries}; wrong commits in ledger "
        f"{summary['wrong_commits_in_ledger']}; tamper all detected {tam['all_detected']}; done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
