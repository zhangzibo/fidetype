r"""P14-01: rerun the model-card metrics with the packaged pretrained decoders (CPU only). Our own code.

Each stage loads a model with ``fidetype.pretrained.load`` (weights from the local cache, SHA-256
checked), decodes the public data files with ``decode_file`` and recomputes the metric of the
model card. It also compares the log-probs with the stored outputs of the training runs (same
weights, PyTorch) where they exist. Aggregates go to ``results/results.json``; per-trial records
(decoded text, truth) go to ``C:\Users\zhang\bci-data\derived\p14-01-pretrained`` only (R-24).

Stages: ``t15`` (val_eval 701, greedy PER + guard decisions vs P14-05), ``t12`` (test blocks of the
10 test sessions, 400, greedy PER), ``kt`` (run28 key accuracy), ``e2q`` (generic model, prompt CER
on the 16 generic-test sessions). Run (repo root, low priority, CPU)::

    .venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- ^
        .venv\Scripts\python.exe -I experiments/2026-11-19-p14-01-pretrained/run.py t15 t12 kt e2q
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("FIDETYPE_PRETRAINED_DIR", r"C:\Users\zhang\bci-data\pretrained")

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

import fidetype.conformance as C  # noqa: E402
import fidetype.pretrained as ftp  # noqa: E402
from fidetype.adapters import b2t25 as B  # noqa: E402
from fidetype.eval.metrics import ctc_greedy_decode, edit_distance  # noqa: E402

DATA = Path(r"C:\Users\zhang\bci-data")
DER = DATA / "derived"
OWN = DER / "p14-01-pretrained"
OUT = HERE / "results"
B2T25 = DATA / "brain-to-text-25/neural/extracted/hdf5_data_final"
B2T24 = DATA / "raw/b2t24/extracted/competitionData"
KT = DATA / "raw/kt-semg"
E2Q = DATA / "raw/emg2qwerty/extracted/emg2qwerty-data-2021-08"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    OUT.mkdir(exist_ok=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def per_of(stream, truth_ids) -> tuple[int, int]:
    hyp = ctc_greedy_decode(B.to_symbol_stream(stream))
    ref = B.phonemes_to_symbols([B.VOCAB[j] for j in truth_ids])
    return edit_distance(ref, hyp), len(ref)


def norm(t: str) -> str:
    return B.normalize_words(t)


def provenance_ok(streams) -> int:
    return sum(C.check(s).passes("provenance") for s in streams)


def stage_t15() -> dict:
    d_in = DER / "m4-01-02-lookahead"
    sessions = json.loads((d_in / "sessions.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    ref_lp = np.load(DER / "m4-13/logprobs-m4-13-long0-val_eval.npz")
    p1405 = {d["key"]: d for d in json.loads((DER / "p14-05-safe-wpm/decisions-t15-m4-13.json").read_text(encoding="utf-8"))}
    t0 = time.time()
    m = ftp.load("t15-m4-13")
    guard = m.guard()
    log(f"t15: loaded {m} + guard {guard.config_id} in {time.time() - t0:.1f} s")
    by_sess: dict[str, list[int]] = {}
    for k in ref_lp.files:
        s, _, j, _ = k.split("|")
        by_sess.setdefault(s, []).append(int(j))
    e = n = 0
    maxdiff = 0.0
    recs = []
    prov = 0
    agree_action = agree_text = 0
    commits = wrong = 0
    t0 = time.time()
    for s in sessions:
        js = sorted(by_sess.get(s, []))
        if not js:
            continue
        z = np.load(d_in / f"{s}.npz")
        pairs = m.decode_file(B2T25 / s / "data_val.hdf5", indices=[2 * j + 1 for j in js], with_items=True)
        for j, (it, st) in zip(js, pairs):
            key = f"{s}|val_eval|{j}|L0"
            maxdiff = max(maxdiff, float(np.abs(ref_lp[key] - st.log_probs).max()))
            de, dn = per_of(st, z[f"val_eval_ph{j}"])
            e, n = e + de, n + dn
            prov += C.check(st).passes("provenance")
            r = guard.decide(st.log_probs, utterance_id=key)
            ref = p1405[key]
            agree_action += r.action == ref["action"]
            agree_text += (r.text or "") == (ref["text"] or "")
            truth = norm(texts[s]["val_eval"][j])
            if r.action == "commit":
                commits += 1
                wrong += norm(r.text or "") != truth
            recs.append({"key": key, "per_edits": de, "per_len": dn, "action": r.action, "text": r.text,
                         "p14_05_action": ref["action"], "truth": truth})
        log(f"t15: {s} done ({len(recs)} trials, {time.time() - t0:.0f} s)")
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / "t15-records.json").write_text(json.dumps(recs, indent=0), encoding="utf-8")
    return {"model": "t15-m4-13", "n": len(recs), "greedy_per": e / max(n, 1), "per_edits": e, "per_symbols": n,
            "card_value": 0.1210, "max_abs_logprob_diff_vs_torch_run": maxdiff, "provenance_pass": prov,
            "guard_config_id": guard.config_id, "guard_actions_equal_p14_05": agree_action,
            "guard_texts_equal_p14_05": agree_text, "commits": commits, "wrong_commits": wrong,
            "p14_05_commits": sum(d["action"] == "commit" for d in p1405.values()), "p14_05_wrong_commits": 17,
            "seconds": round(time.time() - t0, 1)}


def stage_t12() -> dict:
    exp = REPO / "experiments/2026-11-13-confirmatory-t12-v2"
    cfg = json.loads((exp / "config.json").read_text(encoding="utf-8"))
    d_in = Path(cfg["derived_dir"])
    prep = json.loads((exp / "results/prep.json").read_text(encoding="utf-8"))
    ref_lp = np.load(d_in / "logprobs.npz")
    m = ftp.load("t12-v2")
    e = n = 0
    maxdiff = 0.0
    cnt = prov = 0
    t0 = time.time()
    for r in prep["sessions"]:
        if r["role"] != "test":
            continue
        s = r["session"]
        z = np.load(d_in / f"{s}.npz")
        pairs = m.decode_file(B2T24 / "test" / f"{s}.mat", with_items=True)
        known = z["pool_known"]
        for i, (it, st) in enumerate(pairs):
            if not known[i]:
                continue
            key = f"{s}|pool|{i}"
            if key in ref_lp.files:
                maxdiff = max(maxdiff, float(np.abs(ref_lp[key] - st.log_probs).max()))
            de, dn = per_of(st, z[f"pool_ph{i}"])
            e, n = e + de, n + dn
            cnt += 1
            prov += C.check(st).passes("provenance")
        log(f"t12: {s} done ({cnt} trials, {time.time() - t0:.0f} s)")
    return {"model": "t12-v2", "n": cnt, "greedy_per": e / max(n, 1), "per_edits": e, "per_symbols": n,
            "card_value": 0.269, "max_abs_logprob_diff_vs_torch_run": maxdiff, "provenance_pass": prov,
            "seconds": round(time.time() - t0, 1)}


def stage_kt() -> dict:
    from fidetype.adapters.kt_semg import KEY_VOCAB

    m = ftp.load("kt-semg-lda")
    guard = m.guard()
    out = {"model": "kt-semg-lda", "runs": {}}
    for run in ("run28", "run26"):
        t0 = time.time()
        pairs = m.decode_file(KT / f"{run}.csv", with_items=True)
        right = tot = maj = 0
        acts: dict[str, int] = {}
        prov = 0
        from collections import Counter

        cnt: Counter = Counter()
        for it, st in pairs:
            pred = [KEY_VOCAB[i] for i in np.argmax(st.log_probs, axis=1)]
            for p, c in zip(pred, it.extra["codes"]):
                tot += 1
                right += p == c
                cnt[c] += 1
            a = guard.decide(m.nbest(st)).action
            acts[a] = acts.get(a, 0) + 1
            prov += C.check(st).passes("provenance")
        maj = max(cnt.values()) if cnt else 0
        out["runs"][run] = {"segments": len(pairs), "keys": tot, "key_accuracy": right / max(tot, 1),
                            "majority_class": maj / max(tot, 1), "guard_actions": acts, "provenance_pass": prov,
                            "seconds": round(time.time() - t0, 1)}
        log(f"kt: {run} {out['runs'][run]}")
    out["card_value_run28"] = 0.248
    return out


def stage_e2q() -> dict:
    from fidetype.adapters import emg2qwerty as e2q
    from fidetype.pretrained import _crt

    splits = json.loads((DER / "p11-01-emg-decoder/splits.json").read_text(encoding="utf-8"))
    tok = {ch: i for i, ch in enumerate(_crt.VOCAB)}
    named = {"Key.space": tok[" "], "Key.backspace": tok[_crt.BACKSPACE], "Key.enter": tok[_crt.ENTER]}

    def key_token(k: str):
        if k in named:
            return named[k]
        if len(k) == 1 and k in tok and k != "<blank>":
            return tok[k]
        return None

    m = ftp.load("emg2qwerty-p11-01", accept_research_only=True)
    e = n = cnt = prov = 0
    t0 = time.time()
    for name in splits["generic_test"]:
        path = E2Q / f"{name}.hdf5"
        pairs = m.decode_file(path, with_items=True)
        with e2q.Session(path) as sess:
            ev = e2q.key_events(sess)
            toks = [(key_token(x.key), x.sample) for x in ev]
            toks = [(t, s) for t, s in toks if t is not None]
            kf = np.array([max(0, -((_crt.WIN - s) // _crt.HOP)) for _, s in toks], np.int64)
            kt = np.array([t for t, _ in toks], np.int64)
        for it, st in pairs:
            klo = int(round(float(st.frame_times[0]) * _crt.FS - _crt.WIN)) // _crt.HOP
            khi = klo + st.n_frames
            a, b = np.searchsorted(kf, [klo, khi])
            ref = kt[a:b]
            if len(ref) == 0:
                continue
            lp = st.log_probs
            g = lp.argmax(1)
            keep = np.ones(len(g), bool)
            keep[1:] = g[1:] != g[:-1]
            hyp = [int(x) for x in g[keep] if x != 0]
            e += edit_distance(list(ref), hyp)
            n += len(ref)
            cnt += 1
            prov += C.check(st).passes("provenance")
        log(f"e2q: {name[:30]} done ({cnt} prompts, {time.time() - t0:.0f} s)")
    return {"model": "emg2qwerty-p11-01", "sessions": len(splits["generic_test"]), "prompts": cnt,
            "prompt_cer": e / max(n, 1), "edits": int(e), "ref_keys": int(n), "card_value_prompt_cer": 0.5832,
            "card_value_session_cer": 0.5375, "provenance_pass": prov, "seconds": round(time.time() - t0, 1)}


STAGES = {"t15": stage_t15, "t12": stage_t12, "kt": stage_kt, "e2q": stage_e2q}


def _js(o):
    return o.item() if hasattr(o, "item") else str(o)


def main() -> None:
    stages = sys.argv[1:] or list(STAGES)
    OUT.mkdir(exist_ok=True)
    path = OUT / "results.json"
    res = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    res["fidetype_version"] = ftp._FIDETYPE_VERSION
    for st in stages:
        t0 = time.time()
        log(f"stage {st} start")
        res[st] = STAGES[st]()
        res[st]["stage_seconds"] = round(time.time() - t0, 1)
        path.write_text(json.dumps(res, indent=1, default=_js), encoding="utf-8")
        log(f"stage {st} done: {json.dumps(res[st], default=_js)[:400]}")


if __name__ == "__main__":
    main()
