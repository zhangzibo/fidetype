"""P11-09: trust config + real-time collector replay for the P11-01 emg2qwerty EMG decoder. CPU only.

Pre-registration: plan.md (this folder). RESEARCH ONLY: emg2qwerty data is CC BY-NC-SA 4.0. Per-prompt files
(windows, truths, decisions, collector outputs) stay in C:/Users/zhang/bci-data/derived/p11-09/. The repo gets
aggregates only (no per-user value, no text, no id).

Stages (repo root; launch.py runs them detached through the isolation runner):

  infer     (torch venv C:/venvs/fidetype-rocm, device cpu) P11-01 personal models -> causal log-probs of the
            8 track-val and 8 track-test sessions of the 8 P11-01 test users; input-level controls: the
            same sessions time-shuffled, and zero-EMG input. Check: equal to the cached P11-01 NTS streams.
  prompts   scored prompts (track rule: >= 3 in-vocabulary keys) with their key codes and frame windows;
            the test prompts must equal the track truth rows.
  guards    fidetype.trust.calibrate per arm (P primary, L learned score, H salted-hash split).
  decide    decisions on the evaluation prompts (real, shuffled, zeros).
  score     track submission + score card (declared subset), safe WPM v0.1 / proposed v0.2, verdicts.
  replay    the evaluation prompts at real time through one collector (WebSocket), latency.
  all       every stage after ``infer`` (``infer`` needs the torch venv: launch.py runs it first).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
os.environ.setdefault("HIP_VISIBLE_DEVICES", "")  # CPU only: the GPU runs P15-08
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.adapters import emg2qwerty as A  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p11-09"  # the only place this task writes per-prompt files
P1101 = DER / "p11-01-emg-decoder"  # READ ONLY: feature cache, splits, personal weights, NTS streams
E2Q_DATA = Path("C:/Users/zhang/bci-data/raw/emg2qwerty/extracted/emg2qwerty-data-2021-08")  # READ ONLY
TRUTH = DER / "p6-02-scorer" / "truth" / "emg2qwerty.jsonl"  # READ ONLY: the track truth file (P6-02)
EXP1101 = REPO / "experiments" / "2026-11-16-p11-01-emg-decoder"
OUT = HERE / "results"
TRACK = "emg2qwerty"

# --- pre-registered constants (plan.md) ------------------------------------------------------------
ALPHA, DELTA, SEED = 0.05, 0.1, 0
TAIL_FRAMES = 20  # decision window = prompt frames + 0.20 s (P11-01 emission delay p90 110 ms + 32 ms window)
FRAME_S = 0.01
N_NULL = 300  # input-level time-shuffled calibration windows passed as null_inputs
HASH_SALT = "fidetype-p11-09-2026-11-19"
REPLAY_PROMPTS = 240
PAUSE_S = 0.5
READ_S_PER_COMMIT, READ_S_PER_WORD = 0.5, 0.3  # P14-28 aac-gaze-v1 reading cost (proposed v0.2, secondary)
DECODER_NAME = "fidetype-p11-01-crt"
GUARD_DECODER = "fidetype-p11-01-crt+e2q-key-writer"
ARMS = ("P", "L", "H")
RESEARCH = {"data.licence": A.LICENCE, "data.research_only": True}  # FEP-0010 flags on every output


def log(*a: object) -> None:
    OUT.mkdir(exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def own(*parts: str) -> Path:
    p = OWN.joinpath(*parts)
    assert OWN in p.parents or p == OWN
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def save_json(obj: object, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def keep_awake(on: bool) -> None:
    if os.name != "nt":
        return
    import ctypes

    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def sessions() -> list[dict]:
    """The 16 sessions: per P11-01 test user i, j=0 = track val (calibration), j=1 = track test (evaluation)."""
    sp = load_json(P1101 / "splits.json")
    out = []
    for i, u in enumerate(sp["test_users"]):
        t = sp["personal"][u]["test"]
        assert len(t) == 2 and t[0] < t[1]
        for j, s in enumerate(t):
            out.append({"i": i, "j": j, "session": s, "user": u, "split": ("val", "test")[j]})
    return out


def check_track_splits(ss: list[dict]) -> None:
    """Our j=0 / j=1 sessions must be the track val / test sessions of the same users (leakage check)."""
    from fidetype.benchmark import tracks as TR

    units = {u.id: u for u in TR.local_units(TRACK, E2Q_DATA)}
    for s in ss:
        got = units[s["session"]].split
        if got != s["split"]:
            raise SystemExit(f"p11-09: session u{s['i']}-s{s['j']} is track '{got}', expected '{s['split']}'")


def hash_bucket(session: str, prompt_index: int) -> int:
    """Arm H split: 0 = calibration, 1 = evaluation (salted SHA-256 of session and prompt index)."""
    h = hashlib.sha256(f"{HASH_SALT}|{session}|{prompt_index}".encode()).hexdigest()
    return int(h[:8], 16) % 2


# --- stage infer (torch venv) ------------------------------------------------------------------------


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def stage_infer() -> dict:
    import torch

    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
    sys.path.insert(0, str(EXP1101))
    E = load_module("emgdec", EXP1101 / "emgdec.py")
    cfg = load_json(EXP1101 / "config.json")["personal"]["model"]
    mc = E.ModelCfg(**{**cfg, "dilations": tuple(cfg["dilations"])})
    store = E.SessionStore(P1101)
    info = load_json(own("infer.json")) if own("infer.json").exists() else {"sessions": {}}
    t_all = time.time()
    for s in sessions():
        tag = f"u{s['i']}-s{s['j']}"
        f_real, f_shuf = own("lp", f"{tag}-real.npy"), own("lp", f"{tag}-shuf33.npy")
        f_zero = own("lp", f"zeros-u{s['i']}.npy")
        if f_real.exists() and f_shuf.exists() and f_zero.exists():
            continue
        t0 = time.time()
        w = P1101 / "train" / f"personal-u{s['i']}" / "best.pt"
        sha = sha256_file(w)
        hdr = json.loads((P1101 / "train" / "nts" / tag / "p000.jsonl").open(encoding="utf-8").readline())
        if hdr["meta"]["decoder.weights_sha256"] != sha:
            raise SystemExit(f"p11-09: weights of {tag} differ from the P11-01 NTS streams")
        m = E.CRT(mc, store.mean, store.std)
        m.load_state_dict(torch.load(w, map_location="cpu", weights_only=True)["model"])
        m.eval()
        feat = np.asarray(store.feat(s["session"]))
        with torch.no_grad():
            lp = E.session_log_probs(m, feat, "cpu")
            # check against the cached P11-01 streams (GPU, 6 decimals): first 5 prompt streams
            lab = store.lab(s["session"])
            diffs = []
            for k in range(min(5, len(lab["prompt_lo"]))):
                p = P1101 / "train" / "nts" / tag / f"p{k:03d}.jsonl"
                if not p.exists():
                    continue
                fr = np.array([r["log_probs"] for r in map(json.loads, p.open(encoding="utf-8"))
                               if r.get("type") == "frame"], np.float32)
                lo = int(lab["prompt_lo"][k])
                diffs.append(float(np.abs(fr - lp[lo:lo + len(fr)]).max()))
            if not diffs or max(diffs) > 1e-3:
                raise SystemExit(f"p11-09: CPU log-probs of {tag} differ from the P11-01 streams: {diffs}")
            tmp = f_real.with_name(f_real.stem + ".tmp.npy")
            np.save(tmp, lp.astype(np.float32))
            os.replace(tmp, f_real)
            seed = int(hashlib.sha256(f"{HASH_SALT}|shuffle|{s['session']}".encode()).hexdigest()[:8], 16)
            perm = np.random.default_rng(seed).permutation(len(feat))
            lp_sh = E.session_log_probs(m, feat[perm], "cpu")
            del feat, perm
            tmp = f_shuf.with_name(f_shuf.stem + ".tmp.npy")
            np.save(tmp, A.merge_to_key_ctc(lp_sh, store.vocab))
            os.replace(tmp, f_shuf)
            del lp_sh
            if not f_zero.exists():  # zero EMG: every band at log(0 + log_eps); steady-state output row
                x = np.full((2000, E.N_CH, E.N_BANDS), np.log(store.index["log_eps"]), np.float32)
                z = E.session_log_probs(m, x, "cpu")
                np.save(f_zero, z[-1].astype(np.float32))
        info["sessions"][tag] = {"frames": int(len(lp)), "max_abs_diff_vs_p1101": max(diffs), "n_checked": len(diffs),
                                 "seconds": round(time.time() - t0, 1)}
        save_json(info, own("infer.json"))
        log(f"infer {tag}: {len(lp)} frames, max diff {max(diffs):.2e}, {time.time() - t0:.0f} s")
        del lp
    info["vocab"] = list(store.vocab)
    save_json(info, own("infer.json"))
    log(f"infer: done ({time.time() - t_all:.0f} s)")
    return info


# --- stage prompts -----------------------------------------------------------------------------------


def stage_prompts() -> list[dict]:
    from fidetype.benchmark import scorecard as SC
    from fidetype.benchmark import tracks as TR

    if own("prompts.json").exists():
        return load_json(own("prompts.json"))  # type: ignore[return-value]
    ss = sessions()
    check_track_splits(ss)
    truth = SC.read_truth(TRUTH, TRACK)
    index = load_json(P1101 / "index.json")
    nfr = {r["session"]: int(r["n_frames"]) for r in index["sessions"]}
    rows: list[dict] = []
    skipped = {"short_window": 0}
    for s in ss:
        with np.load(P1101 / "sessions" / f"{s['session']}.lab.npz", allow_pickle=False) as z:
            plo, phi = z["prompt_lo"].astype(np.int64), z["prompt_hi"].astype(np.int64)
        with A.Session(E2Q_DATA / f"{s['session']}.hdf5") as sess:
            t0, dur = sess.t0, sess.duration_s
            kept = [p for p in sess.prompts if not (p.end - t0 < 0 or p.start - t0 > dur)]  # P11-01 prep rule
            if len(kept) != len(plo):
                raise SystemExit(f"p11-09: prompt count of u{s['i']}-s{s['j']} differs from the P11-01 cache")
            ev = A.key_events(sess)
            h = TR.id_hash(TRACK, s["session"])
            for k, pr in enumerate(kept):
                pe = [e for e in A.prompt_events(sess, pr, ev) if A.key_class(e.key) is not None]
                if len(pe) < SC.E2Q_MIN_KEYS:
                    continue
                lo, hi = int(plo[k]), int(phi[k])
                if hi - lo < 2:
                    skipped["short_window"] += 1
                    continue
                rows.append({"i": s["i"], "j": s["j"], "split": s["split"], "session": s["session"],
                             "unit": f"{h}#{pr.index}", "prompt_index": int(pr.index), "k": k, "lo": lo, "hi": hi,
                             "end": min(hi + TAIL_FRAMES, nfr[s["session"]]),
                             "codes": " ".join(A.key_code(e.key) for e in pe),
                             "neural_s": float(pe[-1].t - pe[0].t), "bucket": hash_bucket(s["session"], int(pr.index))})
    test_sessions = {TR.id_hash(TRACK, s["session"]) for s in ss if s["split"] == "test"}
    test_truth = {k: v for k, v in truth.items() if k.split("#")[0] in test_sessions}
    have = {r["unit"]: r for r in rows if r["split"] == "test"}
    mism = [k for k, r in have.items() if k not in test_truth or test_truth[k]["text"] != r["codes"]]
    missing = [k for k in test_truth if k not in have]
    for r in rows:
        if r["split"] == "test" and r["unit"] in test_truth:
            r["group"] = test_truth[r["unit"]]["group"]
            r["neural_s"] = float(test_truth[r["unit"]]["neural_s"])
    chk = {"n_rows": len(rows), "n_cal": sum(r["split"] == "val" for r in rows),
           "n_eval": sum(r["split"] == "test" for r in rows), "truth_units_8_sessions": len(test_truth),
           "mismatch_vs_truth": len(mism), "missing_vs_truth": len(missing), **skipped}
    log(f"prompts: {chk}")
    if mism:
        raise SystemExit(f"p11-09: {len(mism)} test prompts differ from the track truth")
    save_json(chk, own("prompts-check.json"))
    save_json(rows, own("prompts.json"))
    return rows


# --- windows ---------------------------------------------------------------------------------------------


class Windows:
    """Decision windows of the prompts: key-CTC (T, 33) log-probs (real, shuffled, zeros)."""

    def __init__(self) -> None:
        self.vocab = load_json(P1101 / "index.json")["vocab"]  # type: ignore[index]  # the P11-01 98-token vocabulary
        self._mm: dict[str, np.ndarray] = {}

    def _arr(self, name: str) -> np.ndarray:
        if name not in self._mm:
            self._mm[name] = np.load(own("lp", name), mmap_mode="r", allow_pickle=False)
        return self._mm[name]

    def get(self, r: dict, kind: str = "real") -> np.ndarray:
        tag = f"u{r['i']}-s{r['j']}"
        if kind == "real":
            return A.merge_to_key_ctc(np.asarray(self._arr(f"{tag}-real.npy")[r["lo"]:r["end"]]), self.vocab)
        if kind == "shuffled":
            return np.array(self._arr(f"{tag}-shuf33.npy")[r["lo"]:r["end"]], np.float32)
        if kind == "zeros":
            row = np.asarray(self._arr(f"zeros-u{r['i']}.npy"))
            return A.merge_to_key_ctc(np.tile(row, (r["end"] - r["lo"], 1)), self.vocab)
        raise ValueError(kind)


def arm_split(rows: list[dict], arm: str) -> tuple[list[dict], list[dict]]:
    if arm in ("P", "L"):
        return [r for r in rows if r["split"] == "val"], [r for r in rows if r["split"] == "test"]
    return [r for r in rows if r["bucket"] == 0], [r for r in rows if r["bucket"] == 1]


def split_digest(rows: list[dict]) -> str:
    return hashlib.sha256("\n".join(sorted(r["unit"] for r in rows)).encode()).hexdigest()[:16]


# --- stage guards ---------------------------------------------------------------------------------------


def calibrate_arm(arm: str, rows: list[dict], W: Windows):
    import fidetype.trust as ft

    cal, _ = arm_split(rows, arm)
    xs = [W.get(r) for r in cal]
    texts = [A.codes_to_key_text(r["codes"]) for r in cal]
    pick = sorted(np.random.default_rng(SEED).choice(len(cal), size=min(N_NULL, len(cal)), replace=False).tolist())
    nulls = [W.get(cal[i], "shuffled") for i in pick]
    kw = {"confidence": "learned"} if arm == "L" else {}
    return ft.calibrate(xs, texts, alpha=ALPHA, delta=DELTA, input_kind="logits", vocab=A.key_ctc_vocab(), blank=0,
                        input_scale="log_probs", frame_period=FRAME_S, null_inputs=nulls,
                        decoder_name=GUARD_DECODER, decoder_version="1", modality="emg", name=f"p11-09-{arm}",
                        seed=SEED, audit_text=False, **kw)


def stage_guards(rows: list[dict], arms: tuple[str, ...] = ARMS) -> dict:
    import fidetype.trust as ft

    W = Windows()
    out = {}
    for arm in arms:
        f = own(f"guard-{arm}.json")
        rec_f = own(f"guard-{arm}.status.json")
        if rec_f.exists():
            out[arm] = load_json(rec_f)
            continue
        cal, ev = arm_split(rows, arm)
        t0 = time.time()
        rec: dict = {"arm": arm, "n_cal": len(cal), "n_eval": len(ev), "cal_digest": split_digest(cal),
                     "eval_digest": split_digest(ev)}
        try:
            g = calibrate_arm(arm, rows, W)
        except ft.NullControlError as e:
            rec.update(status="refused", reason=str(e)[:2000])
            log(f"guards {arm}: REFUSED ({time.time() - t0:.0f} s): {e}")
        else:
            g.save(f)
            sh = g.sheet.to_dict()
            rec.update(status="guard", config_id=g.config_id, sheet=sh)
            OUT.mkdir(exist_ok=True)
            save_json({"config_id": g.config_id, "sheet": sh, **RESEARCH}, OUT / f"guard-{arm}.json")
            log(f"guards {arm}: {g.config_id} ({time.time() - t0:.0f} s)\n{g.sheet}")
        rec["seconds"] = round(time.time() - t0, 1)
        save_json(rec, rec_f)
        out[arm] = rec
    return out


# --- stage decide ---------------------------------------------------------------------------------------


def decide_one(guard, x: np.ndarray) -> dict:
    """One decision plus the decoder n-best of the same events (as P6-02 ``decide``)."""
    t0 = time.perf_counter()
    events, _ = guard._codec.events(x)
    r = guard._result(*guard._final_gated(events))
    dt = time.perf_counter() - t0
    hyps = [e for e in events if e.get("type") == "hypothesis"]
    nb = [str(c.get("text", "")) for c in (hyps[-1].get("nbest", []) if hyps else [])]
    return {"action": r.action, "text": r.text, "choices": list(r.choices), "p_top1": float(r.p_top1),
            "nbest": nb[:3], "s": round(dt, 5)}


def stage_decide(rows: list[dict], arms: tuple[str, ...] = ARMS) -> dict:
    from fidetype.trust.dropin import load as load_guard

    W = Windows()
    out = {}
    for arm in arms:
        f = own(f"decisions-{arm}.json")
        if f.exists():
            out[arm] = load_json(f)
            continue
        st = load_json(own(f"guard-{arm}.status.json"))
        if st["status"] != "guard":  # type: ignore[index]
            out[arm] = {"status": "refused"}
            save_json(out[arm], f)
            continue
        g = load_guard(own(f"guard-{arm}.json"))
        _, ev = arm_split(rows, arm)
        kinds = ("real", "shuffled", "zeros") if arm == "P" else ("real",)
        rec: dict = {"status": "guard", "units": [r["unit"] for r in ev]}
        t0 = time.time()
        for kind in kinds:
            rec[kind] = [decide_one(g, W.get(r, kind)) for r in ev]
            log(f"decide {arm} {kind}: {len(ev)} prompts ({time.time() - t0:.0f} s)")
        save_json(rec, f)
        out[arm] = rec
    return out


# --- stage score ----------------------------------------------------------------------------------------


def guard_row(unit: str, d: dict) -> dict:
    """One units.jsonl row in the track text space (key codes); nbest[0] is the decoder top-1 for CER."""
    from fidetype.benchmark import scorecard as SC

    if d["action"] == "commit":
        texts, act = [d["text"] or ""], "commit"
    elif d["action"] == "offer":
        texts, act = d["choices"] or d["nbest"][:1] or [""], "offer"
    else:
        texts, act = d["nbest"][:3] or [""], "abstain"
    texts = [A.key_text_to_codes(t) for t in texts]
    return SC.unit_row(unit, texts, [d["p_top1"]] + [None] * (len(texts) - 1), action=act,
                       score_semantics="calibrated_prob", offer_k=3)


def always_row(unit: str, d: dict) -> dict:
    from fidetype.benchmark import scorecard as SC

    return SC.unit_row(unit, [A.key_text_to_codes(d["nbest"][0] if d["nbest"] else "")], action="commit")


def manifest(guard_status: dict, n_cal: int, always: bool) -> dict:
    from fidetype.benchmark import scorecard as SC

    sh = guard_status.get("sheet") or {}
    dec = {"name": "fidetype P11-01 causal ring-TCN CTC (personalised, no LM) + key-code writer",
           "version": "1", "url": "experiments/2026-11-16-p11-01-emg-decoder/",
           "weights_licence": "not released (CC BY-NC-SA data: research only)",
           "training_data": ["emg2qwerty: generic model on 100 other users; personal fine-tuning on the train "
                             "sessions of each of the 8 users (never the track val or test session)"],
           "training_regime": "personalised (fine-tuned on earlier sessions of the same user)"}
    if always:
        pol, gua = {"name": "always commit top-1"}, {"method": "none"}
    else:
        pol = {"name": "drop-in guard (built-in CTC beam, no LM, key-code space)",
               "description": f"fidetype.trust.calibrate on {n_cal} track-val prompts of the same 8 users, alpha "
                              f"{ALPHA}, delta {DELTA}, decision window = prompt + {TAIL_FRAMES * FRAME_S:.2f} s"}
        gua = {"method": "ltt", "alpha": sh.get("alpha"), "delta": sh.get("delta"), "n_cal": int(sh.get("n_ltt") or 0),
               "scope": "marginal over test prompts pooled over the 8 users; exchangeable val / test sessions",
               "calibration_split": "val", "config_id": guard_status.get("config_id"),
               "feasible": sh.get("feasible", True)}
    return SC.manifest_dict(
        TRACK, dec, policy=pol, guarantee=gua, regime="personalised",
        controls={"shuffled": "input level: the test session EMG features time-shuffled (seeded per session), "
                              "then the same decoder, writer and policy",
                  "zeros": "input level: zero EMG (every band at log(1e-6)), then the same decoder, writer and "
                           "policy"},
        coverage={"subset": "declared subset: the track test sessions of the 8 P11-01 test users only. The P11-01 "
                            "generic model trained on 96 of the other 104 track test sessions, so only these 8 "
                            "sessions are clean (P11-01 results, benchmark section)."},
        notes="RESEARCH ONLY (CC BY-NC-SA 4.0 data). Track-conformant: the decoder sees only the EMG (no key "
              "times). Causal, no lookahead; the decision waits 0.20 s after the prompt end. P11-09.")


def safe_v02(dec: dict, rows: list[dict], sheet: dict) -> dict:
    """Proposed safe-wpm/0.2 (not adopted) with the P14-28 reading cost, sentence commits only (secondary)."""
    from fidetype.benchmark import safe_wpm as SW
    from fidetype.benchmark.registry import keycodes_to_chars

    truths = [A.codes_to_key_text(r["codes"]) for r in rows]
    com = [d["action"] == "commit" for d in dec["real"]]
    cor = [c and d["text"] is not None and d["text"].split() == t.split() for c, d, t in zip(com, dec["real"], truths)]
    nw = [len(keycodes_to_chars(r["codes"]).split()) for r in rows]  # as the scorer: words of the key text
    nch = [len(keycodes_to_chars(r["codes"])) for r in rows]
    neural = [r["neural_s"] for r in rows]
    cl = [{"group": f"u{r['i']}"} for r in rows]
    g = SW.guarantee_from_sheet(sheet)
    res = {}
    for name, kw in (("v0.1", {}), ("v0.2", {"metric_version": "0.2"}),
                     ("v0.2+read", {"metric_version": "0.2", "read_s_per_commit": READ_S_PER_COMMIT,
                                    "read_s_per_word": READ_S_PER_WORD})):
        r = SW.safe_wpm(com, cor, nw, nch, neural, guarantee=g, timing="measured per prompt (first to last key)",
                        clusters=cl, ci_unit="group", B=2000, seed=0, **kw)
        res[name] = {k: r.get(k) for k in ("value", "ci", "status", "n_commits", "n_wrong_commits",
                                           "measured_wrong_commit", "measured_wrong_commit_cp95", "no_bci_wpm")}
    return res


def stage_score(rows: list[dict]) -> dict:
    from fidetype.benchmark import scorecard as SC
    from fidetype.utils.binomial import clopper_pearson

    dec = {a: load_json(own(f"decisions-{a}.json")) for a in ARMS}
    st = {a: load_json(own(f"guard-{a}.status.json")) for a in ARMS}
    res: dict = {"task": "P11-09", "date": time.strftime("%Y-%m-%d %H:%M"), **RESEARCH,
                 "note": "aggregates only (no per-user value, no text, no id)", "arms": {}}
    truth = SC.read_truth(TRUTH, TRACK)
    for arm in ARMS:
        cal, ev = arm_split(rows, arm)
        a: dict = {"status": st[arm]["status"], "n_cal": len(cal), "n_eval": len(ev),
                   "cal_digest": st[arm]["cal_digest"], "eval_digest": st[arm]["eval_digest"]}
        if st[arm]["status"] != "guard":
            a["reason"] = st[arm].get("reason")
            res["arms"][arm] = a
            continue
        sh = st[arm]["sheet"]
        a["config_id"] = st[arm]["config_id"]
        a["sheet"] = {k: sh.get(k) for k in ("alpha", "delta", "n_items", "n_fit", "n_policy", "n_ltt", "feasible",
                                             "commit_threshold", "controls", "warnings", "frame_temperature")}
        d = dec[arm]
        truths = [A.codes_to_key_text(r["codes"]) for r in ev]
        com = [x["action"] == "commit" for x in d["real"]]
        wrong = sum(c and (x["text"] or "").split() != t.split() for c, x, t in zip(com, d["real"], truths))
        top1 = sum((x["nbest"][0] if x["nbest"] else "").split() == t.split() for x, t in zip(d["real"], truths))
        lo, hi = clopper_pearson(wrong, len(ev), 0.05)
        a.update(n_commits=int(sum(com)), n_wrong_commits=int(wrong), wrong_commit_rate=wrong / len(ev),
                 wrong_commit_cp95=[lo, hi], commit_rate=sum(com) / len(ev),
                 error_among_commits=(wrong / sum(com)) if sum(com) else None, top1_exact=top1 / len(ev),
                 actions={k: sum(x["action"] == k for x in d["real"]) for k in ("commit", "offer", "withhold")},
                 decide_s={"p50": float(np.median([x["s"] for x in d["real"]])),
                           "p95": float(np.percentile([x["s"] for x in d["real"]], 95))})
        a["safe_wpm_direct"] = safe_v02(d, ev, sh)
        if arm == "P":
            for kind in ("shuffled", "zeros"):
                a[f"control_{kind}_commits"] = sum(x["action"] == "commit" for x in d[kind])
            for always in (False, True):
                name = f"{TRACK}__p11-01-crt-subset8__{'always-commit' if always else 'guard'}"
                fn = always_row if always else guard_row
                rws = [fn(u, x) for u, x in zip(d["units"], d["real"])]
                ctl = {k: [fn(u, x) for u, x in zip(d["units"], d[k])] for k in ("shuffled", "zeros")}
                sub = SC.write_submission(own("submissions", name, "x").parent, manifest(st[arm], len(cal), always),
                                          rws, ctl)
                card = SC.score(TRACK, sub, truth, B=2000, seed=0)
                card.setdefault("notes", []).append("FEP-0010: data.research_only = true (CC BY-NC-SA 4.0).")
                save_json(card, own("cards", f"{name}.json"))
                m = card["metrics"]
                a["card_always" if always else "card"] = {
                    "file": f"{name}.json", "status": card.get("status"), "certification": card.get("certification"),
                    "cer": m["cer"], "ewpm": m.get("ewpm"), "gaze_ewpm": m.get("gaze_ewpm"),
                    "controls": {k: v for k, v in card["controls"].items() if k != "basis"},
                    "safe_wpm": {k: card["safe_wpm"].get(k) for k in (
                        "value", "ci", "status", "n_trials", "n_commits", "n_wrong_commits", "measured_wrong_commit",
                        "measured_wrong_commit_cp95", "no_bci_wpm", "no_bci_note", "committed_correct_words",
                        "total_words", "minutes_neural", "minutes_correction")},
                    "coverage": card.get("coverage")}
        res["arms"][arm] = a
        log(f"score {arm}: commits {a['n_commits']} wrong {a['n_wrong_commits']} of {len(ev)}")
    save_json(res, OUT / "results.json")
    return res


# --- stage replay ---------------------------------------------------------------------------------------


def pick_even(n_all: int, n: int) -> list[int]:
    if n <= 0 or n >= n_all:
        return list(range(n_all))
    return sorted({int(round(x)) for x in np.linspace(0, n_all - 1, n)})


def user_weights_sha(i: int) -> str:
    """The SHA-256 of the user's P11-01 personal weights, as the cached P11-01 NTS streams declare it."""
    p = P1101 / "train" / "nts" / f"u{i}-s1" / "p000.jsonl"
    return json.loads(p.open(encoding="utf-8").readline())["meta"]["decoder.weights_sha256"]


def replay_events(ev: list[dict], idx: list[int], W: Windows, weights_sha: str) -> tuple[list[dict], list[str], dict]:
    """One NTS stream (one user, so one weights SHA-256) of the prompts ``ev[idx]`` at 100 Hz, 0.5 s pauses."""
    from fidetype import __version__ as FT_VERSION
    from fidetype.writer import stream_meta

    meta = stream_meta(modality="emg", decoder_name=f"{DECODER_NAME} + emg2qwerty key-code writer (P11-09)",
                       decoder_version="1", causal=True, lookahead_s=0.0, lm_name="none", weights_sha256=weights_sha,
                       stream_id="auto", adapter_name="p11-09 replay (fidetype.adapters.emg2qwerty)",
                       adapter_version=FT_VERSION,
                       extra={**RESEARCH, "fidetype.dataset": "emg2qwerty track test, 8 users (declared subset)"})
    header = {"type": "header", "spec_version": "1.0", "source": "p11-09/p11-01-crt", "vocab": A.key_ctc_vocab(),
              "vocab_type": "char", "blank_id": 0, "frame_period": FRAME_S, "latency": 0.0, "clock_domain": "other",
              "meta": meta}
    evs: list[dict] = [header]
    t = 0.0
    nfr = 0
    for i in idx:
        x = W.get(ev[i])
        for row in x:
            evs.append({"type": "frame", "t": round(t, 6), "log_probs": [round(float(v), 4) for v in row]})
            t += FRAME_S
        nfr += len(x)
        evs.append({"type": "segment_end", "t": round(t - FRAME_S, 6), "unit": "utterance"})
        t += PAUSE_S
    evs.append({"type": "end"})
    texts = [A.codes_to_key_text(ev[i]["codes"]) for i in idx]
    return evs, texts, {"prompts": len(idx), "frames": nfr, "stream_seconds": round(t, 1)}


def stage_replay(rows: list[dict], n: int = REPLAY_PROMPTS) -> dict:
    """One collector run per user (one stream per user: the provenance check needs one weights SHA-256 per
    stream); n / 8 prompts per user, spread evenly over that user's evaluation prompts. Pooled report only."""
    from fidetype.collector import bench as BN
    from fidetype.collector.exporters import committed_text
    from fidetype.trust.dropin import load as load_guard
    from fidetype.trust.personal import UserProfile

    if own("replay", "summary.json").exists():
        return load_json(own("replay", "summary.json"))  # type: ignore[return-value]
    st = load_json(own("guard-P.status.json"))
    if st["status"] != "guard":  # type: ignore[index]
        rec = {"status": "not run: the primary guard was refused"}
        save_json(rec, OUT / "replay-summary.json")
        return rec
    W = Windows()
    _, ev_all = arm_split(rows, "P")
    offline = load_json(own("decisions-P.json"))["real"]  # type: ignore[index]
    pos = {r["unit"]: k for k, r in enumerate(ev_all)}
    users = sorted({r["i"] for r in ev_all})
    per = max(1, n // len(users)) if n > 0 else 0
    runs = []
    tot: dict = {"prompts": 0, "frames": 0, "stream_seconds": 0.0, "decisions": 0, "committed": 0, "typed": 0,
                 "wrong_commits": 0, "same": 0, "paired": 0, "actions": {}, "typed_only_commits": True,
                 "producer_levels": [], "producer_errors": 0}
    for u in users:
        f = own("replay", f"run-u{u}.json")
        if f.exists():
            runs.append(load_json(f))
            continue
        ev = [r for r in ev_all if r["i"] == u]
        idx = pick_even(len(ev), per)
        g = load_guard(own("guard-P.json"))
        prof = UserProfile.new(f"p11-09-u{u}", g, salt="fidetype-p11-09", consent_ref="public-dataset-research-only")
        prof.save(own("replay", f"profile-u{u}.json"))
        evs, texts, info = replay_events(ev, idx, W, user_weights_sha(u))
        log(f"replay user {users.index(u) + 1}/{len(users)}: {info['prompts']} prompts, {info['frames']} frames, "
            f"{info['stream_seconds']} s at real time (WebSocket)")
        r = BN.run("implant-logits", "websocket", own("replay", f"run-u{u}"),
                   profile_file=own("replay", f"profile-u{u}.json"), events=evs, texts=texts,
                   seg_toml="max_frames = 100000\n", timeout_s=info["stream_seconds"] + 600.0).report
        dec_file = own("replay", f"run-u{u}") / "implant-logits-websocket" / "out" / "decisions.jsonl"
        out_dec = [json.loads(x) for x in dec_file.read_text(encoding="utf-8").splitlines() if x]
        paired = [d for d in out_dec if isinstance(d.get("utterance"), int) and 0 <= d["utterance"] < len(idx)]
        same = sum((committed_text(d) is not None)
                   == (offline[pos[ev[idx[d["utterance"]]]["unit"]]]["action"] == "commit") for d in paired)
        run = {"info": info, "latency_ms": r["latency_ms"]["stages"], "within_budget": r["latency_ms"]["within_budget"],
               "producer_level": r["conformance"]["producer_level"], "conformance": r["conformance"],
               "decisions": r["decisions"], "actions": r["actions"], "committed": r["committed"], "typed": r["typed"],
               "typed_only_commits": r["typed_only_commits"], "wrong_commits": r["wrong_commits"],
               "producer_errors": len(r.get("producer_errors") or []), "same": int(same), "paired": len(paired),
               "stop_reason": r.get("stop_reason"), "wall_s": r.get("wall_s")}
        save_json(run, f)  # local only: one user's run
        runs.append(run)
        log(f"replay user {users.index(u) + 1}: added p50/p95 {run['latency_ms'].get('added', {}).get('p50')} / "
            f"{run['latency_ms'].get('added', {}).get('p95')} ms")
    for run in runs:
        for k in ("prompts", "frames", "stream_seconds"):
            tot[k] += run["info"][k]
        for k in ("decisions", "committed", "typed", "wrong_commits", "same", "paired", "producer_errors"):
            tot[k] += run[k]
        for a, c in run["actions"].items():
            tot["actions"][a] = tot["actions"].get(a, 0) + c
        tot["typed_only_commits"] = tot["typed_only_commits"] and run["typed_only_commits"]
        tot["producer_levels"].append(run["producer_level"])
    stages = sorted({k for run in runs for k in run["latency_ms"]})
    lat = {}
    for k in stages:
        qs = [run["latency_ms"][k] for run in runs if run["latency_ms"].get(k, {}).get("n")]
        if qs:
            lat[k] = {"n": sum(q["n"] for q in qs), "p50_median_over_runs": float(np.median([q["p50"] for q in qs])),
                      "p95_max_over_runs": max(q["p95"] for q in qs),
                      "p95_median_over_runs": float(np.median([q["p95"] for q in qs])),
                      "max": max(q["max"] for q in qs)}
    added = lat.get("added", {})
    summary = {"task": "P11-09", **RESEARCH, "date": time.strftime("%Y-%m-%d %H:%M"),
               "note": "pooled over the per-user runs; no per-user value",
               "guard": {"config_id": st["config_id"], "input_kind": "logits (built-in CTC beam inside the collector)",
                         "online": "aci", "profile": "one per-user profile per run (the pooled arm-P guard)"},
               "runs": len(runs), "budget_ms": BN.BUDGET_MS,
               "within_budget_all_runs": all(run["within_budget"] for run in runs),
               "v5_rule": "p95 of added < 50 ms in every run (the bench keeps no pooled samples)",
               "added_ms": added, "latency_ms": lat, "tail_wait_s": TAIL_FRAMES * FRAME_S,
               "producer_levels": sorted(set(tot.pop("producer_levels"))),
               "commit_agreement_with_offline": {"same": tot.pop("same"), "of": tot.pop("paired")}, **tot}
    save_json(summary, own("replay", "summary.json"))
    save_json(summary, OUT / "replay-summary.json")
    log(f"replay: added p50 (median over runs) {added.get('p50_median_over_runs')} ms, p95 (max over runs) "
        f"{added.get('p95_max_over_runs')} ms; actions {tot['actions']}")
    return summary



# --- main -----------------------------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stages", nargs="+", choices=("infer", "prompts", "guards", "decide", "score", "replay", "all"))
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--replay-prompts", type=int, default=REPLAY_PROMPTS)
    a = ap.parse_args()
    arms = tuple(x for x in a.arms.split(",") if x)
    keep_awake(True)
    try:
        st = set(a.stages)
        if "infer" in st:
            stage_infer()
        if st & {"prompts", "all", "guards", "decide", "score", "replay"}:
            rows = stage_prompts()
            if st & {"guards", "all"}:
                stage_guards(rows, arms)
            if st & {"decide", "all"}:
                stage_decide(rows, arms)
            if st & {"score", "all"}:
                stage_score(rows)
            if st & {"replay", "all"}:
                stage_replay(rows, a.replay_prompts)
            if "all" in st:
                (OWN / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
                log("all: DONE")
    finally:
        keep_awake(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
