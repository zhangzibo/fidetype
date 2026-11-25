r"""P15-49 runner: E2 self-teaching on T15 with the wrong-commit bound through every update (gap 209; wrapper = P15-52).

Our own code, Apache-2.0. Plan: plan.md (pre-registered, 29c1dc9; frozen). Configuration: config.json.

Reuses READ-ONLY and UNCHANGED:
  - the M4-13 trainer ``experiments/2026-11-15-m4-13-long-train/train.py`` (``main``, ``collate``, ``micro_chunks``,
    ``patch_model``, ``param_groups`` logic, ``evaluate``, ``edit``, ``greedy``) and ``t15.py``. For the base decoder
    this wrapper only sets the run folder (``T.RUNS``), a run entry, ``--steps 30000`` and a ``load_part`` that keeps
    the sessions S0-S7 (plan.md: "a wrapper filters load_part('train') to S0-S7").
  - ``fidetype.trust``: ``calibrate``, ``GuardedUpdateLoop``, ``TrustGuardUpdater``, ``FeedbackUser``,
    ``ProvenanceLedger`` (no re-implementation of the gate).
  - the P14-03 / P15-05 T15 word route (``common.word_decoder`` + ``make_decode_fn``).
The replay schedule (phases A / B / C, update 1, nightly update, arms, users) is plan.md, written here.

Stages (``all`` runs them in order; finished parts are skipped; every part resumes from its checkpoint):
  base     30,000 steps M4-13 recipe on S0-S7 train (latest.pt every 4 min); base stop if S0-S7 val PER > 0.30
  guard    start guard: calibrate() on S8 with the base decoder
  grid     S8 fit-setting grid (FB, U1, seed 0) -> grid.json (also results/grid.json)
  gate     the replay starts only if results/grid.json is committed and on origin/main (plan.md: "committed
           before the replay starts"); exit code 4 = waiting
  replay   20 runs in plan order (checkpoint after every session); GPU cap 90 h (checked before each part)
  summary  P1-P5 and the outcome -> summary.json (aggregates only; also results/results.json)
  dry      CPU-only plumbing run into a scratch folder (never the result folder; no replay-session data)

A file ``pause`` or ``stop`` in --out stops the job at the next safe point (exit code 3). Re-run to resume.
"""

from __future__ import annotations

import os
import sys

if (len(sys.argv) > 1 and sys.argv[1] == "dry") or ("--device" in sys.argv
                                                    and sys.argv[sys.argv.index("--device") + 1:][:1] == ["cpu"]):
    # CPU only: hide every GPU from this process before torch is imported (dry runs never touch the GPU).
    os.environ["HIP_VISIBLE_DEVICES"] = "-1"
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import argparse  # noqa: E402
import dataclasses  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
M413_DIR = HERE.parent / "2026-11-15-m4-13-long-train"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(M413_DIR))
import t15 as T  # noqa: E402
import train as M  # noqa: E402  (sets threads, below-normal priority, cudnn off: the M4-13 settings)

import fidetype.trust as ft  # noqa: E402
from fidetype.adapters import b2t25 as B  # noqa: E402
from fidetype.decoders.lookahead_gru import LookaheadGRUConfig, build_torch_model  # noqa: E402
from fidetype.trust.adaptive import FeedbackUser, GuardedUpdateLoop  # noqa: E402
from fidetype.trust.bandit_risk import ipw_slack  # noqa: E402  (the G3 audit bound, reused by the exposure test)
from fidetype.trust.dropin import TrustGuard  # noqa: E402
from fidetype.trust.online_risk import OnlineCommitRiskControl  # noqa: E402
from fidetype.trust.provenance import ProvenanceLedger, verify  # noqa: E402
from fidetype.trust.update_hooks import TrustGuardUpdater  # noqa: E402
from fidetype.utils.binomial import clopper_pearson  # noqa: E402

CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
OUT = Path(CONFIG["out"])
DERIVED = Path(r"C:\Users\zhang\bci-data\derived")
GRID_REPO = HERE / "results" / "grid.json"
PAUSED, WAITING = 3, 4
LICENCE = {"data": ["T15 B2T'25 copy-task neural data (Card et al. 2024, Dryad doi:10.5061/dryad.dncjsxm85), CC0-1.0",
                    "CMUdict lexicon (BSD-2-Clause)", "Tatoeba-derived word / char LMs (CC BY 2.0 FR, attribution)"],
           "research_only": False, "copy_to_rented_machine": "allowed (plan.md)"}
# The five plan arms, then the two secondary arms of amendment 2 (appended, so the plan arms keep their seed index).
# Arm CR trains on every labelled new item, as FB (amendment 2, correction 1: Card et al. 2026 fine-tuning text).
ARM_LABELS = {"F": None, "FB": "feedback", "OR": "oracle", "ST": "self", "SH": "shuffled", "CR": "feedback",
              "FBX": "feedback"}
USER_ID = {"U1": 1, "U2": 2}


class Paused(Exception):
    pass


class CapReached(Exception):
    pass


# --- small helpers ---------------------------------------------------------------------------------------------------


def norm(t) -> str:
    return " ".join(str(t).split())


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.floating, float)):
        o = float(o)
        return o if math.isfinite(o) else str(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    return o


def save_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(jsonable(obj), indent=1), encoding="utf-8")
    os.replace(tmp, path)


def read_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def check_out(out: Path, derived: Path = DERIVED, own: str = "p15-49") -> bool:
    """True if ``out`` may be written: inside the derived root only its own folder ``own``."""
    out, d = Path(out).resolve(), Path(derived).resolve()
    if out == d:
        return False
    if d in out.parents:
        return out.relative_to(d).parts[0] == own
    return True


def stop_requested(out: Path) -> bool:
    return (out / "pause").exists() or (out / "stop").exists()


class Log:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
        print(line, flush=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


class Clock:
    """Wall-clock hours of the job, summed over launches (gpu_clock.json). The job blocks the GPU while it runs."""

    def __init__(self, path: Path):
        self.path = path
        old = read_json(path) if path.exists() else {}
        self.base = float(old.get("seconds", 0.0))
        self.launches = old.get("launches", []) + [{"start": time.strftime("%Y-%m-%dT%H:%M:%S")}]
        self.t0 = time.time()

    def hours(self) -> float:
        return (self.base + time.time() - self.t0) / 3600.0

    def save(self) -> None:
        self.launches[-1]["end"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.launches[-1]["seconds"] = round(time.time() - self.t0, 1)
        save_json({"seconds": round(self.base + time.time() - self.t0, 1), "launches": self.launches}, self.path)


def word_errors(hyp: str, ref: str) -> tuple[int, int]:
    r = ref.split()
    return M.edit(hyp.split(), r), len(r)


# --- data ------------------------------------------------------------------------------------------------------------


def load_part_sessions(part: str, keep, max_items: int | None = None):
    """``T.load_part`` restricted to the sessions in ``keep`` (same item format and order; only those files read)."""
    ss = T.sessions()
    keep = set(int(k) for k in keep)
    items = []
    for si, s in enumerate(ss):
        if si not in keep:
            continue
        z = np.load(T.DERIVED / f"{s}.npz")
        n = int(z[f"{part}_n"]) if f"{part}_n" in z else 0
        for i in range(n):
            if not bool(z[f"{part}_known"][i]):
                continue
            items.append((si, z[f"{part}_X{i}"], z[f"{part}_ph{i}"].astype(np.int64), f"{s}|{part}|{i}"))
            if max_items and len(items) >= max_items:
                return items
    return items


def stream_order(n_train: int, n_vs: int, n_ve: int) -> list[tuple[str, int]]:
    """plan.md: the session's train trials in file order, then its val trials in file order. prep.py split the val
    file as val_select = val[0::2], val_eval = val[1::2], so val trial j is (val_select, j // 2) for even j."""
    out = [("train", i) for i in range(n_train)]
    for j in range(n_vs + n_ve):
        out.append(("val_select", j // 2) if j % 2 == 0 else ("val_eval", j // 2))
    return out


class Store:
    """T15 items of the M4-01/02 derived folder (read only). X is read from the npz on demand."""

    def __init__(self, derived: Path):
        self.derived = Path(derived)
        self.sessions = read_json(self.derived / "sessions.json")
        self.texts = read_json(self.derived / "texts.json")
        self._z: dict = {}

    def z(self, si: int):
        if si not in self._z:
            self._z[si] = np.load(self.derived / f"{self.sessions[si]}.npz")
        return self._z[si]

    def items(self, si: int) -> list[dict]:
        """The labelled stream of session ``si`` (items with a known phonemisation), plan order."""
        z, s = self.z(si), self.sessions[si]
        n = {p: (int(z[f"{p}_n"]) if f"{p}_n" in z else 0) for p in ("train", "val_select", "val_eval")}
        out = []
        for part, i in stream_order(n["train"], n["val_select"], n["val_eval"]):
            if not bool(z[f"{part}_known"][i]):
                continue
            x = z[f"{part}_X{i}"]
            out.append({"id": f"{s}|{part}|{i}", "si": si, "part": part, "i": i, "n_bins": int(x.shape[0]),
                        "text": norm(self.texts[s][part][i]), "ph": z[f"{part}_ph{i}"].astype(np.int64)})
        return out

    def X(self, it: dict) -> np.ndarray:
        return self.z(it["si"])[f"{it['part']}_X{it['i']}"]


def ctc_ok(n_bins: int, n_lab: int) -> bool:
    """The train.py length filter (random cut 3 bins, patch 14, stride 4)."""
    return (n_bins - M.TC["random_cut_bins"] - 14) // 4 + 1 >= n_lab


def phoneme_label(text: str | None, cmu: dict) -> np.ndarray | None:
    """CMUdict phonemes of a label text (T.phonemize, SIL between words) -> ids; None if any word is unknown."""
    if text is None or not norm(text):
        return None
    ph, ok = T.phonemize(norm(text), cmu)
    if not ok or not ph:
        return None
    return np.asarray([T.PH_ID[p] for p in ph], np.int64)


# --- model -----------------------------------------------------------------------------------------------------------


def build_model(model_config: dict, sd: dict | None, dev: str):
    """The M4-13 model (input dropout via patch_model, as in training); weights from ``sd``."""
    model = build_torch_model(LookaheadGRUConfig(**model_config))
    M.patch_model(model)
    if sd is not None:
        model.load_state_dict(sd)
    return model.to(dev)


def delta_keys(sd: dict, layers: int) -> list[str]:
    """The parameters any fit may change: all day layers, the last GRU layer, the output layer."""
    last = f"grus.{layers - 1}."
    return [k for k in sd if k in ("day_W", "day_b") or k.startswith(last) or k.startswith("out.")]


@dataclasses.dataclass
class Version:
    name: str
    delta: dict
    trained_on: frozenset
    last_sess: int
    broken: bool = False


def with_day(v: Version, src: int, dst: int) -> Version:
    """plan.md step 1: the day layer of ``dst`` is a copy of the day layer of ``src``."""
    d = {k: t.clone() for k, t in v.delta.items()}
    if src != dst:
        d["day_W"][dst] = d["day_W"][src]
        d["day_b"][dst] = d["day_b"][src]
    return Version(v.name, d, v.trained_on, dst, v.broken)


def load_version(model, v: Version) -> None:
    params = dict(model.named_parameters())
    with torch.no_grad():
        for k, t in v.delta.items():
            params[k].copy_(t.to(params[k].device))


@torch.no_grad()
def log_probs(model, items: list[dict], X_of, dev: str, chunk: int = 16) -> list[np.ndarray]:
    """(frames, 41) float32 log-probs (80 ms frames) of each item, L 0, in item order."""
    model.eval()
    out: list = [None] * len(items)
    order = sorted(range(len(items)), key=lambda j: items[j]["n_bins"])
    for a in range(0, len(order), chunk):
        idx = order[a:a + chunk]
        b = [(items[j]["si"], X_of(items[j]), items[j]["ph"]) for j in idx]
        X, sess, lens, _, _ = M.collate(b, dev, False)
        lp = model(X, sess, 0, lens).log_softmax(-1)
        fl = model.n_frames(lens)
        for k, j in enumerate(idx):
            out[j] = lp[k, :int(fl[k])].float().cpu().numpy()
    return out


def trainable(model, mode: str, layers: int) -> list:
    ps = [model.day_W, model.day_b]
    if mode == "nightly":
        ps += list(model.grus[layers - 1].parameters()) + list(model.out.parameters())
    elif mode != "day":
        raise ValueError(mode)
    return ps


def fit(model, v: Version, data: list[tuple], d: int, mode: str, steps: int, lr: float, batch: int,
        seed: tuple, dev: str, layers: int, stop_fn=None) -> tuple[dict, bool, float]:
    """Fine-tune version ``v`` on ``data`` = [(session, X, phoneme ids)] with the M4-13 CTC step (collate with
    augmentation, micro_chunks, size-weighted chunk losses, clip 10) and AdamW. ``mode`` "day": only the day layer of
    session ``d``; "nightly": that day layer + the last GRU layer + the output layer. Other day layers stay exact.
    Returns (new delta, broken = non-finite loss or weights, mean loss)."""
    load_version(model, v)
    tp = trainable(model, mode, layers)
    ids = {id(p) for p in tp}
    for p in model.parameters():
        p.requires_grad_(id(p) in ids)
    day = [model.day_W, model.day_b]
    day_ids = {id(p) for p in day}
    rest_w = [p for p in tp if id(p) not in day_ids and p.dim() > 1]
    rest_b = [p for p in tp if id(p) not in day_ids and p.dim() <= 1]
    groups = [{"params": day, "weight_decay": M.TC["weight_decay_day"]}]
    if rest_w:
        groups += [{"params": rest_w, "weight_decay": M.TC["weight_decay"]}, {"params": rest_b, "weight_decay": 0.0}]
    opt = torch.optim.AdamW(groups, lr=float(lr))
    rng = np.random.default_rng(list(seed))
    torch.manual_seed(int(rng.integers(2 ** 31)))
    keep_W, keep_b = model.day_W.detach().clone(), model.day_b.detach().clone()
    mask = torch.zeros(model.day_W.shape[0], dtype=torch.bool, device=model.day_W.device)
    mask[d] = True
    model.train()
    broken, losses = False, []
    try:
        for step in range(int(steps)):
            if stop_fn is not None and step % 25 == 0 and stop_fn():
                raise Paused()
            b = data if len(data) <= batch else [data[j] for j in rng.choice(len(data), batch, replace=False)]
            b_rng = np.random.default_rng(list(seed) + [step])
            opt.zero_grad(set_to_none=True)
            lv = 0.0
            for ch in M.micro_chunks(b):
                X, sess, lens, tg, tl = M.collate(ch, dev, True, b_rng)
                lp = model(X, sess, 0, lens).log_softmax(-1)
                loss = F.ctc_loss(lp.transpose(0, 1), tg, model.n_frames(lens).cpu(), tl.cpu(), blank=0,
                                  reduction="mean", zero_infinity=True)
                w = len(ch) / len(b)
                (loss * w).backward()
                lv += float(loss.detach()) * w
            if not math.isfinite(lv):
                broken = True
                break
            model.day_W.grad[~mask] = 0.0
            model.day_b.grad[~mask] = 0.0
            torch.nn.utils.clip_grad_norm_(tp, M.TC["grad_clip"])
            opt.step()
            losses.append(lv)
        with torch.no_grad():
            model.day_W[~mask] = keep_W[~mask]
            model.day_b[~mask] = keep_b[~mask]
        new = {k: t.detach().cpu().clone() for k, t in model.named_parameters() if k in v.delta}
        if not all(bool(torch.isfinite(t).all()) for t in new.values()):
            broken = True
    finally:
        for p in model.parameters():
            p.requires_grad_(True)
        model.eval()
    return new, broken, (float(np.mean(losses)) if losses else float("nan"))


# --- trust layer -----------------------------------------------------------------------------------------------------


class NBestTap:
    """The ``decode_fn`` of every guard of a run: the P14-03 word route, unchanged. It keeps the last n-best list,
    which is the list the user is offered (plan.md: offer = top 5)."""

    def __init__(self, inner=None):
        self.inner = inner
        self.last = None
        self.n_calls = 0

    def __call__(self, log_probs):
        out = self.inner(log_probs)
        self.last = out
        self.n_calls += 1
        return out


def word_route():
    sys.path.insert(0, str(ROOT / "experiments" / "2026-11-17-trust-reruns-m4-13"))
    import common as K

    wdec, _ = K.word_decoder()
    m14 = K.load_module("p14_03_run", ROOT / "experiments/2026-11-16-p14-03-replay-validation/run.py")
    return m14.make_decode_fn(wdec)


def copy_guard(g: TrustGuard) -> TrustGuard:
    return TrustGuard(g.config, g._codec, g.sheet, g._user_decode, g.audit_text)


def guard_out(g: TrustGuard, tap: NBestTap, lp: np.ndarray, k: int) -> dict:
    """One decision of guard ``g`` (not logged). score / top1 / risk exactly as ``TrustGuardUpdater._item``; offered =
    the top-1 text, then the n-best texts in order, distinct, at most ``k``."""
    tap.last = None
    r = g._decide_quiet(lp)
    top1 = norm(r.choices[0]) if r.choices else ""
    score = float(r.p_top1) if r.action == "commit" else -math.inf
    offered: list[str] = []
    for t in ([top1] if top1 else []) + [norm(c["text"]) for c in (tap.last or [])]:
        if t and t not in offered:
            offered.append(t)
        if len(offered) >= k:
            break
    return {"top1": top1, "score": score, "risk": float(r.guard_risk), "action": r.action, "offered": offered}


def make_loop(cfg: dict, ledger, chain: str, lam_init) -> GuardedUpdateLoop:
    L = cfg["loop"]
    return GuardedUpdateLoop(alpha=L["alpha"], delta=L["delta"], gamma=L["gamma"], eta=L["eta"], n_check=L["n_check"],
                             lam_init=lam_init, challenger_test=L["challenger_test"],
                             challenger_level=L["challenger_level"], challenger_margin=L["challenger_margin"],
                             challenger_margin_abs=L["challenger_margin_abs"],
                             recalibration_rule=L["recalibration_rule"], ledger=ledger, ledger_chain=chain)


def bound_now(loop: GuardedUpdateLoop) -> dict:
    """The aci bound G1 (plan.md P2a): observed long-run rate <= alpha + (lambda_{T+1} - lambda_1) / (eta T)."""
    r = loop.aci.report()
    n, mean, cert = int(r["n_observed"]), r["mean_loss"], r["certificate"]
    holds = True if n == 0 else bool(math.isfinite(cert) and mean <= cert + 1e-12)
    return {"n_observed": n, "observed_rate": mean, "certificate": cert, "lam_1": r["lam_1"],
            "lam_t": float(getattr(loop.aci, "lam_t", float("nan"))), "upper_clip_hits": r["upper_clip_hits"],
            "holds": holds}


def lam_init_of(g: TrustGuard):
    cp = float(g.config.policy.get("commit_p", math.inf))
    return cp if math.isfinite(cp) else None


# --- labels ----------------------------------------------------------------------------------------------------------


def label_text(arm: str, rec: dict) -> str | None:
    """The training text an arm takes from one item record (before SH permutation)."""
    kind = ARM_LABELS[arm]
    if kind is None:
        return None
    if kind == "oracle":
        return rec["truth"]
    if kind == "self":
        return rec["top1"] or None
    return rec["label"]  # feedback and shuffled: what the simulated user gave (silent errors included)


def label_set(arm: str, recs: list[dict], cmu: dict, rng: np.random.Generator | None) -> list[dict]:
    """Labelled entries {id, si, part, i, n_bins, ph, correct} of ``recs`` for ``arm``. SH: the FB labels permuted at
    random inside this training set. The CTC length filter is applied after the permutation."""
    rows = []
    for r in recs:
        t = label_text(arm, r)
        ph = r["truth_ph"] if ARM_LABELS[arm] == "oracle" else phoneme_label(t, cmu)
        if ph is None:
            continue
        row = {"id": r["id"], "si": r["si"], "part": r["part"], "i": r["i"], "n_bins": r["n_bins"], "ph": ph,
               "correct": bool(norm(t) == r["truth"])}
        if "holdout" in r:  # arm CR: the item went to the held-out validation buffer
            row["holdout"] = bool(r["holdout"])
        rows.append(row)
    if ARM_LABELS[arm] == "shuffled" and len(rows) > 1:
        perm = rng.permutation(len(rows))
        rows = [{**rows[k], "ph": rows[int(perm[k])]["ph"], "correct": bool(int(perm[k]) == k and rows[k]["correct"])}
                for k in range(len(rows))]
    return [r for r in rows if ctc_ok(r["n_bins"], len(r["ph"]))]


def shuffle_pool(pool: list[dict], rng: np.random.Generator) -> list[dict]:
    """SH nightly: permute the labels of the whole training set (fresh permutation every night)."""
    if len(pool) < 2:
        return list(pool)
    perm = rng.permutation(len(pool))
    rows = [{**pool[k], "ph": pool[int(perm[k])]["ph"], "correct": False} for k in range(len(pool))]
    return [r for r in rows if ctc_ok(r["n_bins"], len(r["ph"]))]


# --- amendment 2: secondary controller, exposure test, Card rule, check-block report ---------------------------------


def make_shadow(cfg: dict, lam_init, q_lower: float) -> OnlineCommitRiskControl:
    """Amendment 2, item 1: the noticing-adjusted ACI controller (target alpha * q_lower). It sees the same phase-C
    items, the same session threshold and gate as the live loop, and the observed loss of its own commits. It never
    changes a live decision (a shadow on the same decoder versions)."""
    L = cfg["loop"]
    if not 0.0 < q_lower <= 1.0:
        raise ValueError("q_lower must be in (0, 1]")
    return OnlineCommitRiskControl(alpha=float(L["alpha"]) * float(q_lower), method="aci", eta=float(L["eta"]),
                                   lam_init=lam_init, score_max=1.0)


def ipw_challenger_test(items: list[dict], pi: float, level: float = 0.05, margin: float = 0.1,
                        margin_abs: float = 0.1) -> dict:
    """Amendment 2, item 2: the champion / challenger test under randomised exposure (design-based, IPW).

    ``items``: one dict per check item with ``shown`` ("ch" or "cp": whose offer the user saw; chosen by a coin with
    P(ch) = ``pi``, drawn before the feedback), ``ch`` / ``cp`` (top-1 texts), ``truth`` (the text the system knows,
    or None). Only observed data are used. Per item, W = 1[challenger wrong, champion right] and B = 1[challenger
    right, champion wrong] (top-1 right / wrong; no CER tie-break). With ``p_sloppy`` 0 a right shown top-1 is
    always accepted, so W is observed on every champion-shown item and B on every challenger-shown item. Horvitz-
    Thompson sums: W_hat = sum_cp W / (1 - pi), B_hat = sum_ch B / pi. The bounds are the G3 audit bound
    (``bandit_risk.ipw_slack``: Bennett + Ville) with one test each, at level / 2 (Bonferroni, as the plan test):

    - absolute branch: pass if W_hat + slack(n_diff pi / (1 - pi)) < margin_abs * N (H0: worse share >= margin_abs);
    - non-inferiority branch: pass if (0.5 + m) B_hat - (0.5 - m) W_hat - slack(n_diff v) > 0
      (H0: W / (W + B) >= 0.5 + m), v = max((0.5 + m)^2 (1 - pi) / pi, (0.5 - m)^2 pi / (1 - pi)).

    n_diff = items whose two top-1 texts differ (identical texts give W = B = 0, known). All identical: pass."""
    if not 0.0 < pi < 1.0:
        raise ValueError("pi must be in (0, 1)")
    m = float(margin)
    if max((0.5 + m) * (1.0 / pi - 1.0), 0.5 - m) > 1.0:
        raise ValueError("pi too far from 0.5 for this margin: the Bennett bound needs increments <= 1")
    n_items = len(items)
    n_diff = w_obs = b_obs = n_ch = 0
    for it in items:
        if it["shown"] not in ("ch", "cp"):
            raise ValueError("shown must be 'ch' or 'cp'")
        n_ch += it["shown"] == "ch"
        ch, cp = norm(it.get("ch") or ""), norm(it.get("cp") or "")
        t = None if it.get("truth") is None else norm(it["truth"])
        if ch == cp:
            continue
        n_diff += 1
        if it["shown"] == "cp":
            w_obs += int(t is not None and cp == t and ch != t)
        else:
            b_obs += int(t is not None and ch == t and cp != t)
    W_hat, B_hat = w_obs / (1.0 - pi), b_obs / pi
    slack_abs = float(ipw_slack(n_diff * pi / (1.0 - pi), 1, level / 2.0)[0])
    v = max((0.5 + m) ** 2 * (1.0 - pi) / pi, (0.5 - m) ** 2 * pi / (1.0 - pi))
    slack_ni = float(ipw_slack(n_diff * v, 1, level / 2.0)[0])
    upper_w = W_hat + slack_abs
    lower_s = (0.5 + m) * B_hat - (0.5 - m) * W_hat - slack_ni
    pass_abs, pass_ni = bool(upper_w < margin_abs * n_items), bool(lower_s > 0.0)
    passed_by = ("identical top-1" if n_diff == 0 else "noninferior" if pass_ni else "few worse items" if pass_abs
                 else None)
    return {"test": "ipw", "pi": pi, "level": level, "margin": m, "margin_abs": margin_abs, "n_items": n_items,
            "n_challenger_shown": n_ch, "n_diff": n_diff, "worse_seen": w_obs, "better_seen": b_obs,
            "W_hat": W_hat, "B_hat": B_hat, "upper_worse": upper_w, "abs_limit": margin_abs * n_items,
            "lower_S": lower_s, "pass_abs": pass_abs, "pass_ni": pass_ni, "passed": passed_by is not None,
            "passed_by": passed_by}


def card_rule(ch_ed: int, ch_n: int, cp_ed: int, cp_n: int) -> dict:
    """Amendment 2, item 3 (Card et al. 2026): accept the challenger iff its error rate on the held-out validation
    buffer is strictly lower than the champion's. An empty buffer gives no evidence: refuse."""
    if ch_n <= 0 or cp_n <= 0:
        return {"test": "card", "passed": False, "why": "empty validation buffer", "n_ph": int(ch_n)}
    a, b = ch_ed / ch_n, cp_ed / cp_n
    return {"test": "card", "passed": bool(a < b), "challenger_per": a, "champion_per": b, "n_ph": int(ch_n),
            "why": "held-out PER improves" if a < b else "held-out PER does not improve"}


def unknown_split(rows: list[dict]) -> dict:
    """Amendment 2, item 2 (report only): check items whose truth stays unknown to the system, split by the true
    status of the champion and of the challenger (the simulator knows the truth). ``rows``: {known, cp_right,
    ch_right (None without a challenger), shown}. 'lost_better' = champion wrong, challenger right, unknown: the
    plan test scores such a pair as a tie, so the challenger cannot win it. 'hidden_worse' = champion right,
    challenger wrong, unknown (possible only when the challenger's offer was shown)."""
    out = {"n_items": len(rows), "n_unknown": 0, "champion_right": 0, "champion_wrong": 0, "lost_better": 0,
           "hidden_worse": 0, "unknown_challenger_shown": 0}
    for r in rows:
        if r["known"]:
            continue
        out["n_unknown"] += 1
        out["champion_right" if r["cp_right"] else "champion_wrong"] += 1
        if r.get("ch_right") is not None:
            out["lost_better"] += int(r["ch_right"] and not r["cp_right"])
            out["hidden_worse"] += int(r["cp_right"] and not r["ch_right"])
        out["unknown_challenger_shown"] += int(r.get("shown") == "ch")
    return out


def add_counts(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + b.get(k, 0) for k in sorted(set(a) | set(b))}


def plan_test_shadow(cfg: dict, ch_out: list[dict], cp_out: list[dict], truths: list, rejected: list) -> dict:
    """The plan's paired champion / challenger test (non-inferiority, unchanged library code) on one check block, in
    a throw-away loop: report only (arms CR and FBX, where another rule decides). No LTT and no null controls."""
    loop = make_loop(cfg, None, "shadow", None)
    loop.set_champion("champion")
    loop.start_session("shadow")
    loop.new_version("challenger")
    for j, (a, c, t, rej) in enumerate(zip(ch_out, cp_out, truths, rejected)):
        tt = None if t is None else norm(t)
        loop.add_check_item(j, a["score"], None if tt is None else float(a["top1"] != tt), text=a["top1"] or None,
                            text_ok=bool(a["top1"]), guard_risk=a["risk"],
                            champion=(c["score"], None if tt is None else float(c["top1"] != tt), c["risk"],
                                      c["top1"]), truth=tt, not_truth=[norm(x) for x in (rej or [])])
    t = loop._challenger_test()
    return {"refused": bool(t.refused), "p_value": float(t.p_value), "worse": int(t.worse_only),
            "better": int(t.better_only), "n_unknown": int(t.n_unknown), "passed_by": t.passed_by}


# --- one run ---------------------------------------------------------------------------------------------------------


@dataclasses.dataclass
class SessionSpec:
    si: int
    lo: int = 0
    hi: int | None = None
    tag: str = ""

    def name(self) -> str:
        return self.tag or f"S{self.si:02d}"


class Run:
    """One replay run (arm, user, seed) over a list of sessions, with a checkpoint after every session."""

    def __init__(self, ctx: "Ctx", name: str, arm: str, user: str, seed: int, settings: dict,
                 sessions: list[SessionSpec], out: Path, nightly: bool = True):
        self.ctx, self.name, self.arm, self.user_name, self.seed = ctx, name, arm, user, int(seed)
        u = ctx.cfg["users"][user]
        self.user = FeedbackUser(p_notice=u["p_notice"], p_retype=u["p_retype"], p_sloppy=u["p_sloppy"])
        self.settings, self.sessions, self.out, self.do_nightly = settings, sessions, out, nightly
        self.ledger_path = out / "ledger.jsonl"
        self.chain = f"p15-49-{name}"
        # amendment 2: per-arm options (plan arms: exposure 0, the plan gate) and the secondary controller
        acfg, a2 = ctx.cfg["arms"][arm], ctx.cfg["amendment_2"]
        self.exposure_p = float(acfg.get("exposure_p", 0.0))
        self.gate = acfg.get("gate", "plan")
        self.holdout_share = float(acfg.get("holdout_share", 0.0))
        self.q_lower = float(a2["secondary_aci"]["q_lower"][user])

    # state -------------------------------------------------------------------
    def fresh(self) -> None:
        c = self.ctx
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        self.start_guard = c.load_start_guard()
        live_guard = c.load_start_guard()
        self.loop = make_loop(c.cfg, ProvenanceLedger(self.ledger_path), self.chain, lam_init_of(self.start_guard))
        self.up = TrustGuardUpdater(live_guard, self.loop, null_trials=c.null_trials,
                                    seed=1000 * self.seed + 10 * USER_ID[self.user_name] + list(ARM_LABELS).index(self.arm),
                                    champion_version="base")
        self.live = c.base_version()
        self.nightly = None
        self.pool: list[dict] = []
        self.rows: list[dict] = []
        self.done: list[str] = []
        self.shadow = make_shadow(c.cfg, lam_init_of(self.start_guard), self.q_lower)
        self.val_buf: list[dict] = []  # arm CR: the held-out validation buffer (label rows)
        self.per_cache: dict = {}  # arm CR: (version name, item id) -> greedy phoneme edits of the champion

    def checkpoint(self) -> None:
        n = len(self.done)
        d = self.out / f"ckpt-{n:03d}"
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        self.up.guard.save(d / "live_guard.json")
        self.start_guard.save(d / "start_guard.json")
        shutil.copyfile(self.ledger_path, d / "ledger.jsonl")
        loop = self.loop
        lis, led = loop.listeners, loop.ledger
        loop.listeners, loop.ledger = [], None
        try:
            torch.save({"loop": loop, "rng": self.up.rng, "outcomes": self.up.outcomes, "live": self.live,
                        "nightly": self.nightly, "pool": self.pool, "rows": self.rows, "done": self.done,
                        "shadow": self.shadow, "val_buf": self.val_buf, "per_cache": self.per_cache,
                        "anchor": led.anchor()}, d / "state.pt")
        finally:
            loop.listeners, loop.ledger = lis, led
        tmp = self.out / "LATEST.tmp"
        tmp.write_text(d.name, encoding="utf-8")
        os.replace(tmp, self.out / "LATEST")
        for old in self.out.glob("ckpt-*"):
            if old.name != d.name:
                shutil.rmtree(old, ignore_errors=True)

    def resume(self) -> bool:
        p = self.out / "LATEST"
        if not p.exists():
            return False
        c = self.ctx
        d = self.out / p.read_text(encoding="utf-8").strip()
        shutil.copyfile(d / "ledger.jsonl", self.ledger_path)  # drop entries of a session that did not finish
        st = torch.load(d / "state.pt", map_location="cpu", weights_only=False)
        self.start_guard = ft.load(d / "start_guard.json", decode_fn=c.tap)
        guard = ft.load(d / "live_guard.json", decode_fn=c.tap)
        loop = st["loop"]
        loop.ledger = ProvenanceLedger(self.ledger_path)
        if loop.ledger.anchor() != st["anchor"]:
            raise RuntimeError(f"{self.name}: ledger does not match the checkpoint")
        self.loop = loop
        self.up = TrustGuardUpdater(guard, loop, null_trials=c.null_trials)
        self.up.rng, self.up.outcomes = st["rng"], st["outcomes"]
        self.live, self.nightly, self.pool = st["live"], st["nightly"], st["pool"]
        self.rows, self.done = st["rows"], st["done"]
        self.shadow, self.val_buf, self.per_cache = st["shadow"], st["val_buf"], st["per_cache"]
        return True

    # one session ---------------------------------------------------------------
    def propose(self, version: Version, lp_check, lp_champ, truths, rejected, check_ids, sess: str,
                kind: str | None = None):
        """One proposal through TrustGuardUpdater (unchanged): a decoder change if ``lp_champ`` is given, else the
        same-decoder re-calibration (kind 'recalibration'). Amendment 2: ``kind="decoder"`` without ``lp_champ`` is
        a decoder change that another rule (Card rule, IPW test) has already accepted; the paired test then compares
        the version with itself, and the loop still runs the block LTT, the null controls and the ledger."""
        decoder = lp_champ is not None or kind == "decoder"
        out = self.up.propose(copy_guard(self.start_guard), lp_check, truths, champion_inputs=lp_champ,
                              check_ids=check_ids, trained_on=version.trained_on,
                              version=version.name if decoder else f"{self.name}-{sess}-r", session=sess,
                              check_rejected=rejected, kind=kind)
        rec = out.record
        row = {"kind": "decoder" if decoder else "recalibration", "version": rec.version if rec else None,
               "accepted": bool(out.accepted), "reasons": list(out.reasons), "outcome": out.to_dict(),
               "loop_config_before": rec.parent_config_id if rec else None,
               "loop_config_after": rec.config_id if rec else None,
               "controls_passed": bool(rec is not None and all(c.passed for c in rec.controls) and rec.controls),
               "lambda_session": None if rec is None else rec.lambda_session}
        if out.accepted:
            row["bound_at_accept"] = bound_now(self.loop)
            b = row["bound_at_accept"]
            self.ctx.log(f"[{self.name} {sess}] accepted {row['kind']} {row['version']}: config "
                         f"{row['loop_config_after']}, lambda {row['lambda_session']}, aci bound: observed "
                         f"{b['observed_rate']} <= {b['certificate']} (T {b['n_observed']}) holds {b['holds']}")
        return out, row

    def refuse(self, version: Version, reason: str, sess: str, **extra) -> dict:
        """Record a refused decoder proposal without the loop checks (broken fit, or the amendment-2 rule)."""
        if self.loop.session != sess:
            self.loop.start_session(sess)
        self.loop.new_version(version.name, version.trained_on)
        r0 = self.loop.reject_proposal(reason)
        return {"kind": "decoder", "version": version.name, "accepted": False, "reasons": list(r0.reasons),
                "loop_config_before": r0.parent_config_id, "loop_config_after": r0.config_id,
                "controls_passed": False, "lambda_session": None, **extra}

    def add_val(self, rows: list[dict]) -> None:
        """Arm CR: add held-out label rows to the validation buffer (each item once)."""
        have = {r["id"] for r in self.val_buf}
        self.val_buf.extend(dict(r) for r in rows if r["id"] not in have)

    def val_edits(self, v: Version, cache: bool) -> tuple[int, int]:
        """Arm CR: greedy phoneme edits and length of version ``v`` on the validation buffer (champion cached)."""
        c = self.ctx
        buf = self.val_buf
        todo = [r for r in buf if not cache or (v.name, r["id"]) not in self.per_cache]
        got = {}
        if todo:
            load_version(c.model, v)
            for r, lp in zip(todo, log_probs(c.model, todo, c.store.X, c.dev)):
                got[r["id"]] = int(M.edit(list(r["ph"]), M.greedy(lp)))
            if cache:
                self.per_cache.update({(v.name, k): e for k, e in got.items()})
        ed = sum(self.per_cache[(v.name, r["id"])] if cache else got[r["id"]] for r in buf)
        return int(ed), int(sum(len(r["ph"]) for r in buf))

    def session(self, spec: SessionSpec) -> dict:
        c, cfg = self.ctx, self.ctx.cfg
        L = cfg["loop"]
        t0 = time.time()
        sess, d = spec.name(), spec.si
        items = c.store.items(d)[spec.lo:spec.hi]
        nA, nB, k = L["n_phase_a"], L["n_check"], L["offer_k"]
        if len(items) < nA + nB + 1:
            raise RuntimeError(f"{sess}: {len(items)} items, need > {nA + nB}")
        A, Bk, Cc = items[:nA], items[nA:nA + nB], items[nA + nB:]
        model, dev, tap, user = c.model, c.dev, c.tap, self.user
        rng_user = lambda j: np.random.default_rng([self.seed, USER_ID[self.user_name], d, spec.lo + j])  # noqa: E731
        recs: list[dict] = []

        def rec(it, phase, j, o, fb, shown, action, dec=None, lp=None, thr=None):
            we, wn = word_errors(o["top1"], it["text"])
            r = {"id": it["id"], "si": it["si"], "part": it["part"], "i": it["i"], "n_bins": it["n_bins"],
                 "phase": phase, "idx": j, "shown": shown, "action": action, "top1": o["top1"], "offered": o["offered"],
                 "score": o["score"], "risk": o["risk"], "guard_action": o["action"], "truth": it["text"],
                 "truth_ph": it["ph"], "source": fb.source, "label": fb.label, "label_correct": fb.label_correct,
                 "truth_known": fb.truth_known, "true_loss": fb.true_loss, "observed_loss": fb.observed_commit_loss,
                 "silent": fb.silent_error, "w_ed": we, "w_n": wn}
            if lp is not None:
                r["ph_ed"], r["ph_n"] = M.edit(list(it["ph"]), M.greedy(lp)), int(len(it["ph"]))
            if dec is not None:
                r["reason"], r["threshold"] = dec.reason, dec.threshold
            if thr is not None:
                r["thr"] = thr
            if self.holdout_share > 0.0:  # arm CR: the 1/3 hold-out coin of the item (Card et al. 2026)
                r["holdout"] = bool(np.random.default_rng([self.seed, d, spec.lo + j, 33]).random()
                                    < self.holdout_share)
            recs.append(r)
            return r

        champ = with_day(self.live, self.live.last_sess, d)
        # --- phase A: the live champion, offer only --------------------------------------------------------------
        load_version(model, champ)
        lpA = log_probs(model, A, c.store.X, dev)
        for j, (it, lp) in enumerate(zip(A, lpA)):
            o = guard_out(self.up.guard, tap, lp, k)
            rec(it, "A", j, o, user.respond_offer(o["offered"], it["text"], rng_user(j)), champ.name, "offer", lp=lp)
        if stop_requested(c.out):
            raise Paused()
        # --- update 1: the challenger ------------------------------------------------------------------------------
        ch, fits = None, {}
        if ARM_LABELS[self.arm] is not None:
            base_ch = with_day(self.nightly, self.nightly.last_sess, d) if self.nightly is not None else champ
            lab = label_set(self.arm, recs, c.cmu, np.random.default_rng([self.seed, d, spec.lo, 31]))
            if self.holdout_share > 0.0:  # arm CR: held-out items validate, they never train
                self.add_val([r for r in lab if r["holdout"]])
                lab = [r for r in lab if not r["holdout"]]
            data = [(r["si"], c.store.X(r), r["ph"]) for r in lab]
            fits["u1"] = {"n_labels": len(lab), "n_correct": int(sum(r["correct"] for r in lab)),
                          "from": "nightly" if self.nightly is not None else "champion"}
            if data:
                delta, broken, loss = fit(model, base_ch, data, d, "day", self.settings["update1_steps"],
                                          self.settings["lr"], c.batch, (self.seed, d, spec.lo, 1), dev, c.layers,
                                          lambda: stop_requested(c.out))
            else:
                delta, broken, loss = {kk: t.clone() for kk, t in base_ch.delta.items()}, False, float("nan")
            fits["u1"].update(loss=loss, broken=broken)
            ch = Version(f"{self.name}-{sess}-c", delta, frozenset(base_ch.trained_on | {r["id"] for r in lab}), d,
                         bool(broken or base_ch.broken))
        # --- phase B: held-back check block; the champion's offer is shown (arm FBX: a coin may show the
        # challenger's offer instead; amendment 2) ---------------------------------------------------------------------
        cand = copy_guard(self.start_guard)  # the candidate guard of a decoder proposal (as in propose)
        load_version(model, champ)
        lpB = log_probs(model, Bk, c.store.X, dev)
        lpB_ch, o_ch = None, None
        expose = self.exposure_p > 0.0 and ch is not None and not ch.broken
        if expose:
            load_version(model, ch)
            lpB_ch = log_probs(model, Bk, c.store.X, dev)
            o_ch = [guard_out(cand, tap, lp, k) for lp in lpB_ch]
        truths, rejected, ids, shown_arm, o_cp = [], [], [], [], []
        for j, (it, lp) in enumerate(zip(Bk, lpB)):
            o = guard_out(self.up.guard, tap, lp, k)
            z = bool(expose and np.random.default_rng([self.seed, USER_ID[self.user_name], d, spec.lo + nA + j, 41])
                     .random() < self.exposure_p)
            so = o_ch[j] if z else o
            fb = user.respond_offer(so["offered"], it["text"], rng_user(nA + j))
            rec(it, "B", nA + j, so, fb, ch.name if z else champ.name, "offer", lp=lpB_ch[j] if z else lp)
            truths.append(it["text"] if fb.truth_known else None)
            rejected.append(None if fb.truth_known else so["offered"])
            ids.append(it["id"])
            shown_arm.append("ch" if z else "cp")
            o_cp.append(o)
        props, accepted_ch = [], False
        if ch is not None and not ch.broken and o_ch is None:
            load_version(model, ch)
            lpB_ch = log_probs(model, Bk, c.store.X, dev)
            o_ch = [guard_out(cand, tap, lp, k) for lp in lpB_ch]
        check_unknown = unknown_split([{"known": t is not None, "cp_right": o_cp[j]["top1"] == Bk[j]["text"],
                                        "ch_right": None if o_ch is None else o_ch[j]["top1"] == Bk[j]["text"],
                                        "shown": shown_arm[j]} for j, t in enumerate(truths)])
        if ch is not None:
            if ch.broken:
                props.append(self.refuse(ch, "non-finite loss or weights in a fit (broken-fit stop: refused, "
                                             "counted, not retried)", sess, broken=True))
            else:
                ext = shadow = None
                if self.gate == "card":
                    ce, cn = self.val_edits(champ, cache=True)
                    he, hn = self.val_edits(ch, cache=False)
                    ext = {**card_rule(he, hn, ce, cn), "val_items": len(self.val_buf)}
                elif self.gate == "ipw":
                    ext = ipw_challenger_test([{"shown": s_, "ch": a["top1"], "cp": b["top1"], "truth": t}
                                               for s_, a, b, t in zip(shown_arm, o_ch, o_cp, truths)],
                                              self.exposure_p, L["challenger_level"], L["challenger_margin"],
                                              L["challenger_margin_abs"])
                elif self.gate != "plan":
                    raise ValueError(f"unknown gate {self.gate!r}")
                if ext is not None:
                    shadow = plan_test_shadow(cfg, o_ch, o_cp, truths, rejected)
                if ext is None:
                    out, row = self.propose(ch, lpB_ch, lpB, truths, rejected, ids, sess)
                elif ext["passed"]:
                    out, row = self.propose(ch, lpB_ch, None, truths, rejected, ids, sess, kind="decoder")
                else:
                    out, row = None, self.refuse(ch, f"refused by the {ext['test']} rule (amendment 2): "
                                                     f"{ext.get('why') or ext.get('passed_by')}", sess)
                row["per_check"] = {"challenger": _per(lpB_ch, Bk), "champion": _per(lpB, Bk)}
                if ext is not None:
                    row["external_rule"], row["plan_test_shadow"] = ext, shadow
                props.append(row)
                accepted_ch = bool(out is not None and out.accepted)
        if not accepted_ch:
            out, row = self.propose(champ, lpB, None, truths, rejected, ids, sess)
            props.append(row)
        live = ch if accepted_ch else champ
        if stop_requested(c.out):
            raise Paused()
        # --- phase C: the live version decides (commit iff the loop allows it) -----------------------------------
        # amendment 2: the noticing-adjusted secondary controller decides on the same items as a shadow.
        load_version(model, live)
        lpC = log_probs(model, Cc, c.store.X, dev)
        alarms0 = self.loop.n_alarms
        for j, (it, lp) in enumerate(zip(Cc, lpC)):
            o = guard_out(self.up.guard, tap, lp, k)
            dec = self.loop.decide(o["score"], text_ok=bool(o["top1"]), text=o["top1"] or None, guard_risk=o["risk"])
            idx = nA + nB + j
            if dec.commit:
                fb = user.respond_commit(o["top1"], it["text"], rng_user(idx))
            else:
                fb = user.respond_offer(o["offered"], it["text"], rng_user(idx))
            self.loop.observe(dec, fb.observed_commit_loss if dec.commit else None)
            thr = None
            if dec.ticket is not None:  # commit mode: the same effective score as the loop gives its ACI
                lam_s = float(self.loop.lambda_session)
                gate_ok = self.loop.gate_violation(o["top1"] or None, o["risk"], bool(o["top1"]),
                                                   need_risk=True) is None
                eff = o["score"] if (gate_ok and o["score"] >= lam_s) else -math.inf
                if (eff >= dec.ticket.threshold) != dec.commit:
                    raise RuntimeError("internal: the shadow input differs from the live ACI input")
                tk2 = self.shadow.decide(eff)
                fb2 = None
                if tk2.commit:  # the same notice coin as the live user would draw on a commit of this item
                    fb2 = fb if dec.commit else user.respond_commit(o["top1"], it["text"], rng_user(idx))
                self.shadow.observe(tk2, fb2.observed_commit_loss if fb2 is not None else None)
                thr = {"lam_session": lam_s, "lam_aci": float(dec.ticket.threshold), "lam_q": float(tk2.threshold),
                       "commit_q": bool(tk2.commit), "true_q": float(fb2.true_loss) if fb2 is not None else 0.0,
                       "obs_q": float(fb2.observed_commit_loss) if fb2 is not None else 0.0}
            rec(it, "C", idx, o, fb, live.name, "commit" if dec.commit else "offer", dec=dec, lp=lp, thr=thr)
        rc = [r for r in recs if r["phase"] == "C"]
        com = [r for r in rc if r["action"] == "commit"]
        cm = [r for r in rc if r.get("thr") is not None]
        phase_c = {"items": len(rc), "commits": len(com), "wrong": int(sum(r["true_loss"] for r in com)),
                   "silent": int(sum(r["silent"] for r in com)),
                   "corrections": int(sum(r["source"] == "correction" for r in com)),
                   "w_ed": int(sum(r["w_ed"] for r in rc)), "w_n": int(sum(r["w_n"] for r in rc)),
                   "ph_ed": int(sum(r["ph_ed"] for r in rc)), "ph_n": int(sum(r["ph_n"] for r in rc)),
                   # amendment 2: which threshold binds, and the secondary controller
                   "commit_mode": len(cm),
                   "aci_binds": int(sum(r["thr"]["lam_aci"] > r["thr"]["lam_session"] for r in cm)),
                   "aci_binds_commits": int(sum(r["thr"]["lam_aci"] > r["thr"]["lam_session"] for r in com
                                                if r.get("thr") is not None)),
                   "q_commits": int(sum(r["thr"]["commit_q"] for r in cm)),
                   "q_wrong": int(sum(r["thr"]["true_q"] for r in cm)),
                   "q_observed_wrong": int(sum(r["thr"]["obs_q"] for r in cm))}
        # learning view: the latest trained version, regardless of the gate (descriptive)
        learn = None
        if ch is not None and not ch.broken:
            if accepted_ch:
                learn = {"same_as_live": True, "w_ed": phase_c["w_ed"], "w_n": phase_c["w_n"],
                         "ph_ed": phase_c["ph_ed"], "ph_n": phase_c["ph_n"]}
            else:
                load_version(model, ch)
                lpL = log_probs(model, Cc, c.store.X, dev)
                we = wn = pe = pn = 0
                for it, lp in zip(Cc, lpL):
                    o = guard_out(self.up.guard, tap, lp, k)
                    a, b = word_errors(o["top1"], it["text"])
                    we, wn = we + a, wn + b
                    pe, pn = pe + M.edit(list(it["ph"]), M.greedy(lp)), pn + len(it["ph"])
                learn = {"same_as_live": False, "w_ed": we, "w_n": wn, "ph_ed": pe, "ph_n": pn}
        # --- nightly update (from the live version, on all labels the arm has so far) ----------------------------
        if ARM_LABELS[self.arm] is not None and self.do_nightly:
            new = label_set(self.arm if self.arm != "SH" else "FB", recs, c.cmu, None)
            if self.holdout_share > 0.0:  # arm CR: held-out items go to the validation buffer only
                self.add_val([r for r in new if r["holdout"]])
                new = [r for r in new if not r["holdout"]]
            self.pool.extend({kk: v for kk, v in r.items()} for r in new)
            train_set = shuffle_pool(self.pool, np.random.default_rng([self.seed, d, spec.lo, 32])) \
                if self.arm == "SH" else list(self.pool)
            data = [(r["si"], c.store.X(r), r["ph"]) for r in train_set]
            delta, broken, loss = fit(model, live, data, d, "nightly", self.settings["nightly_steps"],
                                      self.settings["lr"], c.batch, (self.seed, d, spec.lo, 2), dev, c.layers,
                                      lambda: stop_requested(c.out))
            fits["nightly"] = {"n_labels": len(train_set), "n_correct": int(sum(r["correct"] for r in train_set)),
                               "loss": loss, "broken": broken}
            self.nightly = Version(f"{self.name}-{sess}-n", delta,
                                   frozenset(live.trained_on | {r["id"] for r in self.pool}), d, bool(broken))
        self.live = live
        row = {"session": sess, "si": d, "n": len(items), "champion": champ.name,
               "challenger": None if ch is None else ch.name, "live": live.name, "proposals": props,
               "phase_c": phase_c, "learning_view": learn, "fits": fits,
               "alarm": self.loop.n_alarms > alarms0, "bound_end": bound_now(self.loop),
               "labels": {"source_counts": _counts([r["source"] for r in recs])},
               "check_unknown": check_unknown, "n_challenger_shown": int(sum(s_ == "ch" for s_ in shown_arm)),
               "val_buffer": len(self.val_buf), "seconds": round(time.time() - t0, 1)}
        save_items(recs, self.out / "items" / f"{sess}.jsonl")
        return row

    def run(self, stop_after: int | None = None) -> dict:
        c = self.ctx
        if (self.out / "result.json").exists():
            return read_json(self.out / "result.json")
        if not self.resume():
            self.fresh()
        else:
            c.log(f"[{self.name}] resume after {len(self.done)} sessions")
        for spec in self.sessions:
            if spec.name() in self.done:
                continue
            if stop_requested(c.out):
                raise Paused()
            row = self.session(spec)
            self.rows.append(row)
            self.done.append(spec.name())
            self.checkpoint()
            pc = row["phase_c"]
            c.log(f"[{self.name} {spec.name()}] live {row['live']} accepted "
                  f"{[p['kind'] for p in row['proposals'] if p['accepted']]} commits {pc['commits']}/{pc['items']} "
                  f"wrong {pc['wrong']} WER {pc['w_ed'] / max(1, pc['w_n']):.4f} bound {row['bound_end']['observed_rate']}"
                  f" <= {row['bound_end']['certificate']} ({row['seconds']:.0f} s)")
            if stop_after is not None and len(self.done) >= stop_after:
                raise Paused()
        res = self.result()
        save_json(res, self.out / "result.json")
        return res

    def result(self) -> dict:
        ver = verify(self.ledger_path, expected_head=self.loop.ledger.anchor())
        ups = [e["body"] for e in self.loop.ledger.entries if e["kind"] == "update"]
        stages = [u["stage"] for u in ups]
        props = [p for r in self.rows for p in r["proposals"]]
        acc = [p for p in props if p["accepted"]]
        nc = sum(r["phase_c"]["items"] for r in self.rows)
        w = sum(r["phase_c"]["wrong"] for r in self.rows)
        k = sum(r["phase_c"]["commits"] for r in self.rows)
        aci = bound_now(self.loop)
        cfg_ok = all((p["loop_config_after"] != p["loop_config_before"]) == p["accepted"] for p in props)
        # amendment 2: which threshold binds, the secondary controller, the check-block report, the other rules
        pcs = [r["phase_c"] for r in self.rows]
        cm, ab = sum(p.get("commit_mode", 0) for p in pcs), sum(p.get("aci_binds", 0) for p in pcs)
        qk, qw = sum(p.get("q_commits", 0) for p in pcs), sum(p.get("q_wrong", 0) for p in pcs)
        sh = self.shadow.report()
        ext = [p for p in props if "external_rule" in p]
        unk: dict = {}
        for r in self.rows:
            unk = add_counts(unk, r.get("check_unknown", {}))
        a2 = {
            "binding": {"commit_mode_items": cm, "aci_binds_items": ab, "share_aci_binds": ab / cm if cm else None,
                        "commits": k, "aci_binds_commits": sum(p.get("aci_binds_commits", 0) for p in pcs),
                        "note": "aci binds = lambda_aci > lambda_session on a commit-mode phase-C item"},
            "p2b_q": {"wrong": qw, "items": nc, "rate": qw / nc if nc else None, "cp95": clopper_pearson(qw, nc, 0.95),
                      "commits": qk, "observed_wrong": sum(p.get("q_observed_wrong", 0) for p in pcs),
                      "q_lower": self.q_lower, "alpha_obs": float(self.shadow.alpha),
                      "aci_observed_rate": sh["mean_loss"], "aci_certificate": sh["certificate"],
                      "aci_n_observed": sh["n_observed"]},
            "noticing_adjusted_bound": {"p_notice": self.user.p_notice,
                                        "g1_over_p_notice": (aci["certificate"] / self.user.p_notice
                                                             if self.user.p_notice > 0 else None)},
            "check_unknown": unk,
            "external_rule": {"rule": self.gate, "n_tested": len(ext),
                              "n_passed": sum(bool(p["external_rule"]["passed"]) for p in ext),
                              "n_plan_test_would_pass": sum(not p["plan_test_shadow"]["refused"] for p in ext),
                              "n_both_pass": sum(bool(p["external_rule"]["passed"]) and not p["plan_test_shadow"]
                                                 ["refused"] for p in ext)} if ext else {"rule": self.gate},
        }
        return {
            "run": self.name, "arm": self.arm, "user": self.user_name, "seed": self.seed, "settings": self.settings,
            "sessions": [r["session"] for r in self.rows],
            "per_session": [{"session": r["session"], "si": r["si"], **{kk: r["phase_c"][kk] for kk in
                             ("items", "commits", "wrong", "silent", "w_ed", "w_n", "ph_ed", "ph_n")},
                             **{kk: r["phase_c"].get(kk) for kk in
                                ("commit_mode", "aci_binds", "q_commits", "q_wrong")},
                             "check_unknown": r.get("check_unknown"),
                             "accepted": [p["kind"] for p in r["proposals"] if p["accepted"]],
                             "learning_view": r["learning_view"]} for r in self.rows],
            "n_proposals": len(props), "n_accepted": len(acc),
            "n_accepted_decoder": sum(p["kind"] == "decoder" for p in acc),
            "n_broken_fits": sum(bool(p.get("broken")) for p in props)
            + sum(bool(r["fits"].get("nightly", {}).get("broken")) for r in self.rows),
            "refusal_reasons": _counts([x.split(" (")[0] for p in props if not p["accepted"] for x in p["reasons"]]),
            "bounds_at_accept": [p.get("bound_at_accept") for p in acc],
            "p2a": {"aci": aci, "holds": aci["holds"] and all(p.get("bound_at_accept", {}).get("holds", True) for p in acc)},
            "p2b": {"wrong": w, "items": nc, "rate": w / nc if nc else None, "cp95": clopper_pearson(w, nc, 0.95)},
            "p3": {"accepted": len(acc), "controls_passed": sum(p["controls_passed"] for p in acc),
                   "pass": all(p["controls_passed"] for p in acc)},
            "p5": {"ledger_verify_ok": ver.ok, "ledger_errors": ver.errors[:5],
                   "every_proposal_decided": stages.count("proposed") == stages.count("accepted") + stages.count("rejected"),
                   "config_changes_on_accept_only": cfg_ok},
            "commits": k, "precision": (k - w) / k if k else None,
            "silent_errors": sum(r["phase_c"]["silent"] for r in self.rows),
            "observed_wrong": sum(r["phase_c"]["corrections"] for r in self.rows),
            "sessions_true_rate_above_alpha": sum(r["phase_c"]["wrong"] / max(1, r["phase_c"]["items"]) > self.ctx.cfg["loop"]["alpha"]
                                                  for r in self.rows),
            "final_loop_config_id": self.loop.config_id, "final_live": self.live.name,
            **a2,
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }


def _per(lps, items) -> float:
    e = sum(M.edit(list(it["ph"]), M.greedy(lp)) for it, lp in zip(items, lps))
    return e / max(1, sum(len(it["ph"]) for it in items))


def _counts(xs) -> dict:
    out: dict = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


def save_items(recs: list[dict], path: Path) -> None:
    """Per-item records (derived folder only: they hold texts)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(jsonable({kk: v for kk, v in r.items() if kk != "truth_ph"})) + "\n")
    os.replace(tmp, path)


# --- the job ---------------------------------------------------------------------------------------------------------


class Ctx:
    """Shared objects of one job: config, device, data, base model, word route, log."""

    def __init__(self, cfg: dict, out: Path, dev: str, log: Log, dry: dict | None = None):
        self.cfg, self.out, self.dev, self.log, self.dry = cfg, out, dev, log, dry or {}
        self.store = Store(Path(cfg["t15_derived"]))
        self.cmu = T.load_cmudict(T.CONFIG["cmudict"])
        self.tap = NBestTap()
        self.null_trials = int(self.dry.get("null_trials", cfg["loop"]["null_trials"]))
        self.batch = int(self.dry.get("batch", cfg["fit"]["batch_choice"]))
        self.model = None

    def ensure_route(self) -> None:
        if self.tap.inner is None:
            self.tap.inner = word_route()

    def ensure_model(self, ckpt: Path) -> None:
        if self.model is not None:
            return
        ck = torch.load(ckpt, map_location="cpu", weights_only=False)
        self.model_config = ck["model_config"]
        self.layers = int(self.model_config["layers"])
        self.base_sd = ck["model"]
        self.model = build_model(self.model_config, self.base_sd, self.dev)
        self.keys = delta_keys(self.base_sd, self.layers)
        self.base_last = max(int(s) for s in self.cfg["sessions"]["base"])

    def base_version(self) -> Version:
        return Version("base", {k: self.base_sd[k].detach().cpu().clone() for k in self.keys}, frozenset(),
                       self.base_last)

    def load_start_guard(self) -> TrustGuard:
        self.ensure_route()
        return ft.load(self.out / "guard" / "start_guard.json", decode_fn=self.tap)


def stage_base(ctx: Ctx, clock: Clock, steps: int | None = None, batch: int | None = None,
               limit_val: int | None = None, n_val: int | None = None) -> dict:
    cfg, out, log = ctx.cfg, ctx.out, ctx.log
    bdir = out / "base"
    if (bdir / "DONE.json").exists():
        return read_json(bdir / "DONE.json")
    if clock.hours() >= float(cfg["gpu_cap_hours"]):
        raise CapReached()
    total = int(steps or cfg["base"]["steps"])
    run = bdir / cfg["base"]["run_name"]
    run.mkdir(parents=True, exist_ok=True)
    keep = cfg["sessions"]["base"]
    for f in ("pause", "stop"):
        (run / f).unlink(missing_ok=True)
    orig = (T.load_part, T.RUNS)
    T.load_part = lambda part, max_items=None: load_part_sessions(part, keep, max_items)
    T.RUNS = bdir
    T.CONFIG["runs"]["p15_49_base"] = {"run": cfg["base"]["run_name"], "lookahead_bins": 0}
    argv = ["train.py", "--which", "p15_49_base", "--steps", str(total)]
    if (run / "latest.pt").exists():
        argv.append("--resume")
    if batch:
        argv += ["--batch", str(batch)]
    if limit_val:
        argv += ["--limit-val", str(limit_val)]
    done = threading.Event()

    def watch():  # our pause / stop file -> the trainer's own pause file (it saves latest.pt and returns)
        while not done.wait(5.0):
            if stop_requested(out):
                (run / "pause").write_text("p15-49 stop request", encoding="utf-8")
                return

    th = threading.Thread(target=watch, daemon=True)
    th.start()
    log(f"[base] train.py {' '.join(argv[1:])} (M4-13 recipe, sessions {keep})")
    old = sys.argv
    sys.argv = argv
    try:
        M.main()
    finally:
        sys.argv = old
        T.load_part, T.RUNS = orig
        done.set()
        clock.save()
    st = read_json(run / "status.json")
    if st["status"] != "done":
        log(f"[base] trainer status {st['status']} at step {st['step']}: exit (resume with the same command)")
        raise Paused()
    ck = torch.load(run / "latest.pt", map_location="cpu", weights_only=False)
    if int(ck["state"]["step"]) != total:
        raise RuntimeError(f"base: latest.pt is at step {ck['state']['step']}, not {total}")
    fin = bdir / "final.pt"
    torch.save({"model": ck["model"], "model_config": ck["model_config"], "step": total,
                "sessions": ck["sessions"], "train_config": ck["train_config"]}, fin)
    val = load_part_sessions("val_select", keep) + load_part_sessions("val_eval", keep)
    val = val[:n_val] if n_val else val
    model = build_model(ck["model_config"], ck["model"], ctx.dev)
    ev = M.evaluate(model, val, ctx.dev, 0)
    thr = float(cfg["base"]["stop_if_val_per_above"])
    rec = {"steps": total, "val_per": ev["per"], "val_loss": ev["loss"], "n_val": len(val),
           "base_stop": bool(ev["per"] > thr), "stop_threshold": thr, "final_sha256": T.sha256_file(fin),
           "train_hours": st.get("train_sec", 0) / 3600, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    save_json(rec, bdir / "DONE.json")
    del model
    log(f"[base] DONE: S0-S7 val PER {ev['per']:.4f} on {len(val)} trials (stop if > {thr}): base_stop "
        f"{rec['base_stop']}")
    return rec


def stage_guard(ctx: Ctx, clock: Clock, ckpt: Path, limit: int | None = None) -> dict:
    cfg, out = ctx.cfg, ctx.out
    gdir = out / "guard"
    if (gdir / "guard.json").exists():
        return read_json(gdir / "guard.json")
    if clock.hours() >= float(cfg["gpu_cap_hours"]):
        raise CapReached()
    ctx.ensure_model(ckpt)
    ctx.ensure_route()
    sg = cfg["start_guard_choice"]
    s8 = int(cfg["sessions"]["tuning"])
    items = ctx.store.items(s8)[:limit]
    v = with_day(ctx.base_version(), ctx.base_last, s8)
    load_version(ctx.model, v)
    lps = log_probs(ctx.model, items, ctx.store.X, ctx.dev)
    ph = [B.phonemes_to_symbols([B.VOCAB[j] for j in it["ph"]]) for it in items]
    ctx.log(f"[guard] calibrate the start guard on {len(items)} S8 items (null trials "
            f"{int(ctx.dry.get('guard_null_trials', sg['null_trials']))})")
    g = ft.calibrate(lps, [it["text"] for it in items], alpha=cfg["loop"]["alpha"], delta=cfg["loop"]["delta"],
                     stream_texts=ph, decoder_name=sg["decoder_name"], name="p15-49-start-guard", seed=sg["seed"],
                     null_trials=int(ctx.dry.get("guard_null_trials", sg["null_trials"])),
                     vocab=list(B.SYMBOL_VOCAB), blank=0, input_scale=sg["input_scale"],
                     frame_period=sg["frame_period"], decode_fn=ctx.tap, modality=sg["modality"])
    gdir.mkdir(parents=True, exist_ok=True)
    g.save(gdir / "start_guard.json")
    rec = {"config_id": g.config_id, "commit_p": g.config.policy.get("commit_p"), "n_items": len(items),
           "aci_lam_init": lam_init_of(g), "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    save_json(rec, gdir / "guard.json")
    clock.save()
    ctx.log(f"[guard] start guard {rec}")
    return rec


def grid_cells(cfg: dict) -> list[dict]:
    g = cfg["grid"]
    return [{"lr": lr, "nightly_steps": st} for lr in g["update1_lr"] for st in g["nightly_steps"]]


def select_grid(cells: list[dict]) -> dict:
    """plan.md: lowest S8 phase-C WER; ties to the smaller LR, then fewer nightly steps."""
    best = sorted(cells, key=lambda c: (c["wer"], c["lr"], c["nightly_steps"]))[0]
    return {"lr": best["lr"], "nightly_steps": best["nightly_steps"], "wer": best["wer"]}


def stage_grid(ctx: Ctx, clock: Clock, u1_steps: int | None = None, limit: int | None = None) -> dict:
    cfg, out = ctx.cfg, ctx.out
    p = out / "grid.json"
    if p.exists():
        return read_json(p)
    if clock.hours() >= float(cfg["gpu_cap_hours"]):
        raise CapReached()
    g = cfg["grid"]
    by_lr = {}
    for lr in g["update1_lr"]:
        st = {"lr": lr, "update1_steps": int(u1_steps or cfg["fit"]["update1_steps"]), "nightly_steps": 0}
        r = Run(ctx, f"grid-lr{lr:g}", g["arm"], g["user"], g["seed"], st,
                [SessionSpec(int(g["session"]), 0, limit)], out / "grid" / f"lr{lr:g}", nightly=False)
        res = r.run()
        ps = res["per_session"][0]
        by_lr[lr] = {"wer": ps["w_ed"] / max(1, ps["w_n"]), "w_ed": ps["w_ed"], "w_n": ps["w_n"],
                     "accepted": ps["accepted"], "commits": ps["commits"], "wrong": ps["wrong"]}
        clock.save()
        ctx.log(f"[grid] lr {lr:g}: S8 phase-C WER {by_lr[lr]['wer']:.4f} accepted {ps['accepted']}")
    cells = [{**c, **by_lr[c["lr"]]} for c in grid_cells(cfg)]
    sel = {"note": "P15-49 fit-setting grid on S8 only (plan.md 29c1dc9): FB arm, U1, seed 0; lowest S8 phase-C WER "
                   "of the live output; ties to the smaller LR, then fewer nightly steps. The nightly fit comes after "
                   "phase C and cannot change the S8 phase-C WER, so each LR ran once and its result is the result of "
                   "both step cells (exact tie). S8 only: no replay session is read.",
           "cells": cells, "chosen": select_grid(cells), "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    save_json(sel, p)
    return sel


def grid_committed(out: Path, root: Path = ROOT, repo_file: Path = GRID_REPO) -> tuple[bool, str]:
    """results/grid.json equals the derived one, is committed in HEAD, and the commit is on origin/main."""
    rel = repo_file.relative_to(root).as_posix()
    try:
        here, mine = read_json(repo_file), read_json(out / "grid.json")
        if here != mine:
            return False, "results/grid.json differs from the derived grid.json"
        git = ["git", "-C", str(root)]
        head = subprocess.run(git + ["show", f"HEAD:{rel}"], capture_output=True, text=True, encoding="utf-8")
        if head.returncode != 0 or json.loads(head.stdout) != mine:
            return False, "not committed in HEAD"
        c = subprocess.run(git + ["log", "-1", "--format=%H", "--", rel], capture_output=True, text=True).stdout.strip()
        anc = subprocess.run(git + ["merge-base", "--is-ancestor", c, "refs/remotes/origin/main"], capture_output=True)
        if not c or anc.returncode != 0:
            return False, "commit not on origin/main yet"
        return True, c
    except Exception as ex:  # noqa: BLE001
        return False, repr(ex)


def _specs(names: list[str]) -> list[dict]:
    out = []
    for name in names:
        arm, user, s = name.split("-")
        out.append({"name": name, "arm": arm, "user": user, "seed": int(s[1:])})
    return out


def run_specs(cfg: dict) -> list[dict]:
    """The 20 plan replay runs in plan order: {name, arm, user, seed}."""
    return _specs(cfg["run_order"])


def exec_specs(cfg: dict) -> list[dict]:
    """All replay runs in execution order (amendment 2): the plan's U1 runs, the Card-rule runs, the plan's U2 runs,
    then the exposure runs."""
    names = cfg["execution_order"]
    if sorted(names) != sorted(cfg["run_order"] + cfg["secondary_runs"]):
        raise ValueError("execution_order must hold every plan run and every secondary run once")
    return _specs(names)


def stage_replay(ctx: Ctx, clock: Clock, grid: dict, sessions: list[SessionSpec] | None = None,
                 specs: list[dict] | None = None, u1_steps=None, nightly_steps=None, stop_after=None) -> bool:
    cfg = ctx.cfg
    sessions = sessions or [SessionSpec(si) for si in cfg["sessions"]["replay"]]
    st = {"lr": float(grid["chosen"]["lr"]), "update1_steps": int(u1_steps or cfg["fit"]["update1_steps"]),
          "nightly_steps": int(nightly_steps or grid["chosen"]["nightly_steps"])}
    for sp in specs or exec_specs(cfg):
        d = ctx.out / "runs" / sp["name"]
        if (d / "result.json").exists():
            continue
        if clock.hours() >= float(cfg["gpu_cap_hours"]):
            raise CapReached()
        ctx.log(f"[{sp['name']}] start: settings {st}, GPU clock {clock.hours():.2f} h")
        Run(ctx, sp["name"], sp["arm"], sp["user"], sp["seed"], st, sessions, d).run(stop_after=stop_after)
        clock.save()
    return True


# --- rules and summary -----------------------------------------------------------------------------------------------


def wer_delta(a: dict, b: dict, window: list[int], n_boot: int, seed: int) -> dict:
    """Phase-C WER of run a minus run b over the sessions in ``window`` (pooled), paired by item; CI95 by a
    session-cluster bootstrap (resample the sessions with replacement)."""
    ra = {r["si"]: r for r in a["per_session"] if r["si"] in window}
    rb = {r["si"]: r for r in b["per_session"] if r["si"] in window}
    ss = sorted(set(ra) & set(rb))
    if len(ss) != len(window):
        return {"status": "incomplete", "n_sessions": len(ss)}
    for s in ss:
        if ra[s]["w_n"] != rb[s]["w_n"] or ra[s]["items"] != rb[s]["items"]:
            raise RuntimeError(f"session {s}: the two runs have different phase-C items")
    ea = np.array([ra[s]["w_ed"] for s in ss], float)
    eb = np.array([rb[s]["w_ed"] for s in ss], float)
    n = np.array([ra[s]["w_n"] for s in ss], float)
    point = float(ea.sum() / n.sum() - eb.sum() / n.sum())
    rng = np.random.default_rng(seed)
    bs = np.empty(n_boot)
    for k in range(n_boot):
        p = rng.integers(0, len(ss), len(ss))
        bs[k] = ea[p].sum() / n[p].sum() - eb[p].sum() / n[p].sum()
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return {"status": "done", "delta": point, "ci95": [float(lo), float(hi)], "n_sessions": len(ss),
            "wer_a": float(ea.sum() / n.sum()), "wer_b": float(eb.sum() / n.sum())}


def outcome(r: dict) -> dict:
    """plan.md outcome table. r: P1, P2a, P2b, P3, P4, P5 (True / False / None), base_stop, primary_done."""
    if r.get("base_stop"):
        return {"label": "N", "why": "base stop"}
    if r["P2a"] is False or r["P5"] is False:
        return {"label": "X", "why": "P2a or P5 failed (code fault)"}
    if not r.get("primary_done"):
        return {"label": "N", "why": "the U1 F / FB runs of both seeds did not finish"}
    if r["P4"] is False:
        return {"label": "D", "why": "P4 failed: shuffled labels also 'learn'"}
    if r["P1"] is True and (r["P2b"] is False or r["P3"] is False):
        return {"label": "C", "why": "P1 passes, P2b or P3 fails"}
    vals = [r[k] for k in ("P1", "P2a", "P2b", "P3", "P4", "P5")]
    if any(v is None for v in vals):
        return {"label": "not_determined", "why": "a rule could not be evaluated (runs missing)"}
    if all(vals):
        return {"label": "A", "why": "P1-P5 pass"}
    if r["P1"] is False and all(r[k] for k in ("P2a", "P2b", "P3", "P4", "P5")):
        return {"label": "B", "why": "P2-P5 pass, P1 fails"}
    return {"label": "no pre-registered label", "why": "a combination the outcome table does not name"}


def all_or_none(vals: list) -> bool | None:
    if any(v is False for v in vals):
        return False
    if not vals or any(v is None for v in vals):
        return None
    return True


def verdict(cfg: dict, res_all: dict, base: dict | None) -> dict:
    """Plan rules P1-P5 on the 20 plan runs (unchanged), plus amendment 2: P2b_q, the amended outcome, and the
    secondary runs (CR, FBX; descriptive)."""
    R = cfg["rules"]
    win = cfg["sessions"]["last_third"]
    res = {n: r for n, r in res_all.items() if n in cfg["run_order"]}

    def get(a, u, s):
        return res.get(f"{a}-{u}-s{s}")

    def delta(a, b, s, u="U1"):
        ra, rb = get(a, u, s), get(b, u, s)
        if ra is None or rb is None:
            return {"status": "not_run"}
        return wer_delta(ra, rb, win, int(R["bootstrap_n"]), int(R["bootstrap_seed"]))

    p1 = {s: delta("FB", "F", s) for s in (0, 1)}
    for v in p1.values():
        if v["status"] == "done":
            v["pass"] = bool(v["delta"] <= R["p1_max_delta"] and v["ci95"][1] < 0)
    P1 = all_or_none([v.get("pass") for v in p1.values()])
    p2a = {n: r["p2a"]["holds"] for n, r in res.items()}
    P2a = all_or_none(list(p2a.values())) if len(p2a) == len(cfg["run_order"]) else (
        False if any(v is False for v in p2a.values()) else None)
    p2b = {n: {**r["p2b"], "pass": bool(r["p2b"]["rate"] is not None and r["p2b"]["rate"] <= R["p2b_max_rate"])}
           for n, r in res.items()}
    u1 = [n for n in cfg["run_order"] if "-U1-" in n]
    P2b = all_or_none([p2b[n]["pass"] if n in p2b else None for n in u1])
    p3 = {n: r["p3"]["pass"] for n, r in res.items()}
    P3 = all_or_none([p3.get(n) for n in cfg["run_order"]])
    p4 = {s: delta("SH", "F", s) for s in (0, 1)}
    for v in p4.values():
        if v["status"] == "done":
            v["pass"] = bool(v["delta"] > R["p4_min_delta"])
    p4_ctrl = [p2b[n]["pass"] if n in p2b else None for n in u1 if n.startswith(("SH-", "ST-"))]
    P4 = all_or_none([v.get("pass") for v in p4.values()] + p4_ctrl)
    p5 = {n: bool(r["p5"]["ledger_verify_ok"] and r["p5"]["every_proposal_decided"]
                  and r["p5"]["config_changes_on_accept_only"]) for n, r in res.items()}
    P5 = all_or_none([p5.get(n) for n in cfg["run_order"]]) if p5 else None
    if any(v is False for v in p5.values()):
        P5 = False
    primary = all(f"{a}-U1-s{s}" in res for a in ("F", "FB") for s in (0, 1))
    rules = {"P1": P1, "P2a": P2a, "P2b": P2b, "P3": P3, "P4": P4, "P5": P5,
             "base_stop": bool(base and base.get("base_stop")), "primary_done": primary}
    desc = {"OR_minus_FB": {s: delta("OR", "FB", s) for s in (0, 1)},
            "ST_minus_F": {s: delta("ST", "F", s) for s in (0, 1)},
            "OR_minus_F": {s: delta("OR", "F", s) for s in (0, 1)},
            "U2_FB_minus_F": {s: delta("FB", "F", s, "U2") for s in (0, 1)}}
    # --- amendment 2 -------------------------------------------------------------------------------------------
    def q_pass(r):
        q = r.get("p2b_q")
        return None if q is None or q.get("rate") is None else bool(q["rate"] <= R["p2b_max_rate"])

    p2b_q = {n: {**r["p2b_q"], "pass": q_pass(r)} for n, r in res.items() if r.get("p2b_q") is not None}
    P2b_q = all_or_none([p2b_q[n]["pass"] if n in p2b_q else None for n in u1])
    p4_ctrl_q = [p2b_q[n]["pass"] if n in p2b_q else None for n in u1 if n.startswith(("SH-", "ST-"))]
    P4_q = all_or_none([v.get("pass") for v in p4.values()] + p4_ctrl_q)
    rules_a2 = {**rules, "P2b": P2b_q, "P4": P4_q}
    binding = {n: r.get("binding") for n, r in res_all.items()}

    def delta_all(a, b, s, u):
        ra, rb = res_all.get(f"{a}-{u}-s{s}"), res_all.get(f"{b}-{u}-s{s}")
        if ra is None or rb is None:
            return {"status": "not_run"}
        return wer_delta(ra, rb, win, int(R["bootstrap_n"]), int(R["bootstrap_seed"]))

    sec = {}
    for n in cfg["secondary_runs"]:
        r = res_all.get(n)
        if r is None:
            sec[n] = {"status": "not_run"}
            continue
        a, u, s = n.split("-")
        sec[n] = {"status": "done", "p2a": r["p2a"]["holds"], "p2b": r["p2b"], "p2b_q": r.get("p2b_q"),
                  "p3": r["p3"]["pass"], "p5": bool(r["p5"]["ledger_verify_ok"] and r["p5"]["every_proposal_decided"]
                                                    and r["p5"]["config_changes_on_accept_only"]),
                  "n_accepted_decoder": r.get("n_accepted_decoder"), "external_rule": r.get("external_rule"),
                  "minus_F": delta_all(a, "F", int(s[1:]), u), "minus_FB": delta_all(a, "FB", int(s[1:]), u)}
    sec_fault = any(v.get("p2a") is False or v.get("p5") is False for v in sec.values())
    a2 = {"P2b_q": p2b_q, "rules_amendment_2": rules_a2, "outcome_amendment_2": outcome(rules_a2),
          "P4_P2b_q_SH_ST": p4_ctrl_q, "binding": binding, "secondary": sec, "secondary_code_fault": sec_fault,
          "note": "outcome = the plan reading (plan.md rules, unchanged); outcome_amendment_2 = the same table with "
                  "P2b read on the noticing-adjusted secondary controller (amendment-2.md). Both are reported."}
    return {"rules": rules, "P1": p1, "P2a": p2a, "P2b": p2b, "P3": p3, "P4": {"SH_minus_F": p4, "P2b_SH_ST": p4_ctrl},
            "P5": p5, "descriptive": desc, "outcome": outcome(rules), "amendment_2": a2}


def stage_summary(ctx: Ctx, status: str, gpu_h: float, repo: Path | None) -> dict:
    cfg, out = ctx.cfg, ctx.out
    base = read_json(out / "base" / "DONE.json") if (out / "base" / "DONE.json").exists() else None
    res = {}
    for sp in exec_specs(cfg):
        p = out / "runs" / sp["name"] / "result.json"
        if p.exists():
            res[sp["name"]] = read_json(p)
    v = verdict(cfg, res, base)
    runs = {n: {kk: r[kk] for kk in ("arm", "user", "seed", "n_proposals", "n_accepted", "n_accepted_decoder",
                                      "n_broken_fits", "refusal_reasons", "p2a", "p2b", "p3", "p5", "commits",
                                      "precision", "silent_errors", "observed_wrong", "sessions_true_rate_above_alpha")
                 if kk in r} | {kk: r.get(kk) for kk in ("binding", "p2b_q", "noticing_adjusted_bound",
                                                         "check_unknown", "external_rule")}
            for n, r in res.items()}
    agg = {"note": "P15-49 E2 on T15 (plan.md 29c1dc9, amendments 1 and 2): aggregates only, no text. Phase-C WER "
                   "of the live output; simulated users; one participant.",
           "status": status, "gpu_hours_wall": round(gpu_h, 3), "base": base,
           "guard": read_json(out / "guard" / "guard.json") if (out / "guard" / "guard.json").exists() else None,
           "grid": read_json(out / "grid.json")["chosen"] if (out / "grid.json").exists() else None,
           "runs_done": sorted(res), "runs_not_run": [n for n in cfg["execution_order"] if n not in res],
           **v, "runs": runs, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    save_json(agg, out / "summary.json")
    if repo is not None:
        save_json(agg, repo / "results.json")
    return agg


# --- main ------------------------------------------------------------------------------------------------------------


def dry_run(ctx: Ctx, clock: Clock, a) -> int:
    """CPU plumbing run (plan.md order step 2: "a dry run on S8 only with a small step count"). The base trainer runs a
    few steps on S0-S7 train; the start guard, the grid and two pseudo-sessions (the first and the second 100 S8
    items) run every arm with tiny fit steps; one FB run is stopped after its first session and resumed, and its
    second session must equal an uninterrupted run. Nothing is read from the replay sessions S9-S44."""
    log = ctx.log
    base = stage_base(ctx, clock, steps=a.dry_base_steps, batch=4, limit_val=8, n_val=16)
    ck = Path(a.dry_ckpt) if a.dry_ckpt else ctx.out / "base" / "final.pt"
    log(f"[dry] base {base}; replay part uses {ck}")
    ctx.ensure_model(ck)
    stage_guard(ctx, clock, ck, limit=200)
    grid = stage_grid(ctx, clock, u1_steps=2, limit=100)
    log(f"[dry] grid chosen {grid['chosen']} (dry numbers are not results)")
    ok, why = grid_committed(ctx.out)
    log(f"[dry] replay gate would wait: {not ok} ({why}); the dry run skips the gate")
    s8 = int(ctx.cfg["sessions"]["tuning"])
    sess = [SessionSpec(s8, 0, 100, "S08a"), SessionSpec(s8, 100, 200, "S08b")]
    arms = [x for x in ARM_LABELS if not a.dry_arms or x in a.dry_arms.split(",")]
    specs = [{"name": f"{arm}-U1-s0", "arm": arm, "user": "U1", "seed": 0} for arm in arms]
    stage_replay(ctx, clock, grid, sess, specs, u1_steps=2, nightly_steps=2)
    if "FB" not in arms:
        log(f"[dry] arms {arms}: no FB run, so no resume test")
        agg = stage_summary(ctx, "dry", clock.hours(), None)
        log(f"[dry] summary rules {agg['rules']} outcome {agg['outcome']} (dry: S8 stand-in, not results)")
        return 0
    # resume test: FB run again, stopped after one session, then resumed
    spec_r = [{"name": "FB-U1-s0-resume", "arm": "FB", "user": "U1", "seed": 0}]
    try:
        stage_replay(ctx, clock, grid, sess, spec_r, u1_steps=2, nightly_steps=2, stop_after=1)
    except Paused:
        log("[dry] FB-U1-s0-resume stopped after session 1 (test); resume")
    stage_replay(ctx, clock, grid, sess, spec_r, u1_steps=2, nightly_steps=2)
    a1 = read_json(ctx.out / "runs" / "FB-U1-s0" / "result.json")
    a2 = read_json(ctx.out / "runs" / "FB-U1-s0-resume" / "result.json")
    same = a1["per_session"] == a2["per_session"] and a1["n_accepted"] == a2["n_accepted"]
    log(f"[dry] resume equals the uninterrupted run: {same}")
    agg = stage_summary(ctx, "dry", clock.hours(), None)
    log(f"[dry] summary rules {agg['rules']} outcome {agg['outcome']} (dry: S8 stand-in, not results)")
    log(f"[dry] cuda initialised: {torch.cuda.is_initialized()}")
    return 0 if same else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P15-49 E2 self-teaching runner")
    ap.add_argument("stage", choices=("all", "summary", "gate", "dry"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--device", default=None)
    ap.add_argument("--dry-base-steps", type=int, default=3)
    ap.add_argument("--dry-ckpt", default=None, help="dry run only: a read-only checkpoint for the replay part")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--dry-arms", default=None, help="dry run only: comma list of arms (default: all arms)")
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    if not check_out(out):
        print(f"never write into {out}", file=sys.stderr)
        return 2
    if a.stage == "dry" and (out == OUT.resolve() or DERIVED.resolve() in out.parents):
        print("a dry run needs a scratch --out outside the derived folder", file=sys.stderr)
        return 2
    dev = a.device or ("cuda" if torch.cuda.is_available() else "cpu")
    if a.stage == "dry" and dev != "cpu":
        print("a dry run is CPU only", file=sys.stderr)
        return 2
    if dev == "cpu":
        torch.cuda.is_available = lambda: False  # train.main picks its device with this call
    torch.set_num_threads(a.threads)
    out.mkdir(parents=True, exist_ok=True)
    log = Log(out / "run.log")
    save_json(LICENCE, out / "licence.json")
    dry = {"null_trials": 20, "guard_null_trials": 100, "batch": 4} if a.stage == "dry" else None
    ctx = Ctx(CONFIG, out, dev, log, dry)
    log(f"start stage={a.stage} device={dev} torch={torch.__version__} pid={os.getpid()} out={out}")
    if a.stage == "gate":
        ok, why = grid_committed(out)
        print(ok, why)
        return 0 if ok else WAITING
    if a.stage == "summary":
        c = read_json(out / "gpu_clock.json")["seconds"] / 3600 if (out / "gpu_clock.json").exists() else 0.0
        agg = stage_summary(ctx, "summary", c, HERE / "results" if out == OUT.resolve() else None)
        log(f"[summary] outcome {agg['outcome']}")
        return 0
    clock = Clock(out / "gpu_clock.json")
    try:
        from fidetype.utils.power import set_keep_awake
        set_keep_awake(True)
    except Exception:  # noqa: BLE001
        pass
    try:
        if a.stage == "dry":
            return dry_run(ctx, clock, a)
        base = stage_base(ctx, clock)
        repo = HERE / "results" if out == OUT.resolve() else None
        if base["base_stop"]:
            agg = stage_summary(ctx, "base stop", clock.hours(), repo)
            (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " base stop", encoding="utf-8")
            log(f"[base] base stop (outcome {agg['outcome']}): no replay")
            return 0
        ck = out / "base" / "final.pt"
        ctx.ensure_model(ck)
        stage_guard(ctx, clock, ck)
        grid = stage_grid(ctx, clock)
        log(f"[grid] chosen {grid['chosen']}")
        if repo is not None and not GRID_REPO.exists():
            save_json(grid, GRID_REPO)
        ok, why = grid_committed(out)
        if not ok:
            log(f"[gate] the replay waits: {why} (commit + push results/grid.json, then launch again)")
            return WAITING
        log(f"[gate] grid.json committed in {why}: the replay starts")
        stage_replay(ctx, clock, grid)
        clock.save()
        agg = stage_summary(ctx, "done", clock.hours(), repo)
        log(f"[summary] outcome {agg['outcome']} rules {agg['rules']} wall h {agg['gpu_hours_wall']:.2f}")
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
        log("ALL DONE")
    except Paused:
        log("pause / stop: exit (resume with the same command)")
        return PAUSED
    except CapReached:
        clock.save()
        log(f"GPU cap {CONFIG['gpu_cap_hours']} h reached: stop (plan.md); remaining runs 'not run (cap)'")
        stage_summary(ctx, "cap", clock.hours(), HERE / "results" if out == OUT.resolve() else None)
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " cap", encoding="utf-8")
        return 0
    except Exception as ex:  # noqa: BLE001
        log(f"FAILED: {ex!r}")
        (out / "FAILED").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + f" {ex!r}", encoding="utf-8")
        raise
    finally:
        clock.save()
        try:
            from fidetype.utils.power import set_keep_awake
            set_keep_awake(False)
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
