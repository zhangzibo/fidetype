"""Pooled-guard check: can the B1 base-rate failure happen in our pooled text guards? CPU only.

Pre-registration: plan.md (this folder, commit 8dde818). Diagnostic only: no shipped guard, card or published
number changes. Reads C:/Users/zhang/bci-data/derived/ (read only; never p15-50) and the Spanish BCBL val/test
labels.jsonl (subject ids only). Writes only C:/Users/zhang/bci-data/derived/pooled-guard-check/. The repo gets
aggregates only (no per-user value for emg2qwerty, no text, no id).

The library code is a clean copy of src/ at commit 8dde818 (``SNAP``), because other agents edit the working tree.

Stages (repo root):
  e2q-base   per-item labels of the 3 emg2qwerty arms (cal) + real test decisions -> per-user breakdown
  e2q-null   recalibrations under the label nulls NX / NW / NP (``--jobs``: one worker's share)
  launch     start 3 detached below-normal workers for e2q-null
  meg        SpanishBCBL CRC / LTT: score-level nulls + per-participant breakdown
  groups     per-group breakdown of the other committing pooled cards (Toronto, T15, T12, B2T '25)
  summary    rules R1-R3 -> results/summary.json (aggregates only)
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "1"
os.environ["HIP_VISIBLE_DEVICES"] = ""  # CPU only
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import argparse  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pickle  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "pooled-guard-check"  # the only place this task writes
SNAP = OWN / "src-8dde818"
OUT = HERE / "results"
EXP1112 = REPO / "experiments" / "2026-11-20-p11-12-emg-nosignal-gate"
EXP1114 = REPO / "experiments" / "2026-11-20-p11-14-emg-lm-confidence"
MEG_ITEMS = REPO / "experiments" / "2026-11-11-g1-async-meg-trust" / "results" / "items-meg-async.json"
MEG_STREAMS = Path("C:/Users/zhang/bci-data/streams/m1-09-r4b-full-medium")  # labels.jsonl only (subject ids)
SUB_B = DER / "p6-02b-v02-entries"
SUB_A = DER / "p6-02-scorer"

# --- pre-registered constants (plan.md) ------------------------------------------------------------
ALPHA, DELTA = 0.05, 0.1
NULLS = ("NX", "NW", "NP")
SEEDS = tuple(range(1, 21))
ARMS = ("S", "SL", "L-FL")
R1_MAX = 4  # certified runs of 20
R2_P = 0.01
R3_MIN_N = 36
R3_MAX = 2 * ALPHA
R3B_PERM = 10_000
R3B_P = 0.01
N_WORKERS = 3
NULL_CODE = {"NX": 1, "NW": 2, "NP": 3}
ARM_CODE = {"S": 1, "SL": 2, "L-FL": 3}
SHIPPED_ID = {"S": "tcfg-3875f995e4c256fb", "SL": "tcfg-0cd6e9578e965f42"}


def guard_path(p: Path) -> Path:
    p = Path(p)
    assert OWN in p.parents, p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def save_json(obj: object, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_json(path: Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def log(*a: object) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(guard_path(OWN / "run.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def below_normal() -> None:
    if os.name == "nt":
        import ctypes

        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


# --- pure helpers (tested in test_pooled.py) ------------------------------------------------------------


def same(a: str | None, b: str) -> bool:
    return a is not None and a.split() == b.split()


def derangement(rng: np.random.Generator, n: int) -> np.ndarray:
    """A uniform random permutation with no fixed point (n >= 2), by rejection."""
    if n < 2:
        raise ValueError("a derangement needs n >= 2")
    while True:
        p = rng.permutation(n)
        if not np.any(p == np.arange(n)):
            return p


def null_labels(kind: str, right: np.ndarray, comm: np.ndarray, users: np.ndarray,
                rng: np.random.Generator) -> np.ndarray:
    """Permuted 'top-1 is right' labels. Items with comm False keep their label (they take no part).

    NP: permuted over all committable items. NW: permuted inside each user. NX: a derangement pi of the users;
    user u's items get labels drawn without replacement from user pi(u)'s labels (with replacement for the rest
    if pi(u) has fewer items), in random order.
    """
    right = np.asarray(right, bool)
    comm = np.asarray(comm, bool)
    users = np.asarray(users)
    y = right.copy()
    idx = np.nonzero(comm)[0]
    if kind == "NP":
        y[idx] = rng.permutation(right[idx])
        return y
    us = sorted(set(users[idx].tolist()))
    if kind == "NW":
        for u in us:
            iu = idx[users[idx] == u]
            y[iu] = rng.permutation(right[iu])
        return y
    if kind == "NX":
        pi = derangement(rng, len(us))
        for k, u in enumerate(us):
            iu = idx[users[idx] == u]
            pool = right[idx[users[idx] == us[pi[k]]]]
            if len(pool) >= len(iu):
                lab = rng.choice(pool, size=len(iu), replace=False)
            else:
                lab = rng.permutation(np.concatenate([pool, rng.choice(pool, size=len(iu) - len(pool), replace=True)]))
            y[iu] = lab
        return y
    raise ValueError(kind)


def build_texts(truths: list[str], top1: list[str], comm: np.ndarray, right: np.ndarray, new: np.ndarray,
                users: np.ndarray, rng: np.random.Generator) -> list[str]:
    """Truth texts that give the new labels: right -> the top-1; wrong -> the old truth if it was wrong, else the
    truth of another item of the same user that differs from this top-1."""
    out = list(truths)
    users = np.asarray(users)
    for i in range(len(truths)):
        if not comm[i]:
            continue
        if new[i]:
            out[i] = top1[i]
        elif right[i]:
            cands = [j for j in np.nonzero(users == users[i])[0] if not same(truths[j], top1[i])]
            if not cands:
                cands = [j for j in range(len(truths)) if not same(truths[j], top1[i])]
            out[i] = truths[int(rng.choice(cands))]
    return out


def cp_upper(k: int, n: int, level: float = 0.95) -> float:
    """Upper end of the two-sided Clopper-Pearson interval."""
    from scipy.stats import beta

    if n == 0:
        return 1.0
    if k >= n:
        return 1.0
    return float(beta.ppf(1 - (1 - level) / 2, k + 1, n - k))


def group_table(groups: list, commit: np.ndarray, wrong: np.ndarray) -> list[dict]:
    out = []
    g = np.asarray(groups)
    for u in sorted(set(g.tolist()), key=str):
        m = g == u
        n, c, w = int(m.sum()), int(commit[m].sum()), int(wrong[m].sum())
        out.append({"group": u, "n": n, "commits": c, "wrong": w, "rate": w / n if n else math.nan,
                    "cp_upper": cp_upper(w, n)})
    return out


def max_rate_perm_p(groups: list, wrong: np.ndarray, n_perm: int = R3B_PERM, seed: int = 0) -> float:
    """Permutation p-value of the largest group wrong-commit rate (group labels permuted over the items)."""
    g = np.unique(np.asarray(groups), return_inverse=True)[1]
    w = np.asarray(wrong, float)
    cnt = np.bincount(g)

    def stat(gg: np.ndarray) -> float:
        return float((np.bincount(gg, weights=w, minlength=len(cnt)) / cnt).max())

    s0 = stat(g)
    rng = np.random.default_rng(seed)
    hits = sum(stat(rng.permutation(g)) >= s0 - 1e-12 for _ in range(n_perm))
    return (hits + 1) / (n_perm + 1)


def r3(groups: list, commit: np.ndarray, wrong: np.ndarray) -> dict:
    tab = group_table(groups, commit, wrong)
    big = [t for t in tab if t["n"] >= R3_MIN_N]
    n = len(commit)
    rec = {"n": n, "commits": int(np.sum(commit)), "wrong": int(np.sum(wrong)),
           "pooled_rate": float(np.sum(wrong)) / n, "pooled_cp_upper": cp_upper(int(np.sum(wrong)), n),
           "n_groups": len(tab), "n_groups_ge_min": len(big),
           "group_n_range": [min(t["n"] for t in tab), max(t["n"] for t in tab)],
           "groups_with_commits": sum(t["commits"] > 0 for t in tab)}
    if big:
        ups = [t["cp_upper"] for t in big]
        rec.update(rule="R3", n_above=sum(u > R3_MAX + 1e-12 for u in ups), max_cp_upper=max(ups),
                   median_cp_upper=float(np.median(ups)), max_rate=max(t["rate"] for t in big),
                   passed=all(u <= R3_MAX + 1e-12 for u in ups))
        small = [t for t in tab if t["n"] < R3_MIN_N]
        rec["small_groups"] = {"n": len(small), "wrong": sum(t["wrong"] for t in small),
                               "items": sum(t["n"] for t in small)}
    else:
        p = max_rate_perm_p(groups, wrong)
        rec.update(rule="R3b", perm_p=p, max_rate=max(t["rate"] for t in tab), passed=p >= R3B_P)
    # post hoc (not pre-registered): is any group clearly above alpha (CP lower end > alpha)? heterogeneity p
    rec["posthoc_groups_cp_lower_above_alpha"] = sum(cp_lower(t["wrong"], t["n"]) > ALPHA for t in tab)
    rec["posthoc_groups_rate_above_alpha"] = sum(t["rate"] > ALPHA for t in tab)
    rec["posthoc_heterogeneity_p"] = rec.get("perm_p", max_rate_perm_p(groups, wrong))
    rec["_table"] = tab  # local only (stripped before the repo summary)
    return rec


def cp_lower(k: int, n: int, level: float = 0.95) -> float:
    """Lower end of the two-sided Clopper-Pearson interval."""
    from scipy.stats import beta

    if k <= 0 or n == 0:
        return 0.0
    return float(beta.ppf((1 - level) / 2, k, n - k + 1))


def mwu_greater(a: list[float], b: list[float]) -> float:
    from scipy.stats import mannwhitneyu

    if np.allclose(a, a[0]) and np.allclose(b, a[0]):
        return 1.0
    return float(mannwhitneyu(a, b, alternative="greater").pvalue)


# --- emg2qwerty arms ---------------------------------------------------------------------------------


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def use_snapshot() -> None:
    sys.path.insert(0, str(SNAP))
    import fidetype

    assert Path(fidetype.__file__).resolve().is_relative_to(SNAP.resolve()), fidetype.__file__


class E2Q:
    """The P11-12 (S, SL) and P11-14 (L-FL) recipes, loaded read only."""

    def __init__(self) -> None:
        use_snapshot()
        self.m14 = load_module("p1114run", EXP1114 / "run.py")
        self.m12 = self.m14.p1112()
        self.R = self.m14.p1111()
        rows = self.R.prompts()
        self.cal, self.ev = self.R.split_rows(rows)
        self.tune = load_json(DER / "p11-11" / "tune.json")
        self.R.set_decoder(self.tune)  # reads the P11-11 beam cache, LM and lexicon (never saved)
        g = load_json(DER / "p11-12" / "gate.json")
        self.m12.GATE.update({k: g[k] for k in ("k_min", "r_min", "r_max")})
        self.an = self.m14.Analyser()
        self.an.load()
        self.an.save = lambda: None  # never write the P11-14 feature cache
        self.W = self.R.p1109().Windows()
        self.users = np.array([r["i"] for r in self.cal])
        self.truths = [self.R.intended_truth(r) for r in self.cal]

    def base(self, arm: str) -> dict:
        f = guard_path(OWN / "e2q" / f"base-{arm}.pkl")
        if f.exists():
            with open(f, "rb") as fh:
                return pickle.load(fh)
        top1, comm = [], []
        for r in self.cal:
            x = self.W.get(r)
            if arm == "L-FL":
                a = self.an.get(x, "FL")
                ok = a is not None and a["status"] == "ok"
                top1.append(a["top"] if ok else "")
            else:
                nb = self.m12.decode_gated(x)
                ok = bool(nb)
                top1.append(nb[0][0].strip() if ok else "")
            comm.append(ok)
        comm = np.array(comm)
        right = np.array([c and same(t, tr) for c, t, tr in zip(comm, top1, self.truths)])
        b = {"top1": top1, "comm": comm, "right": right}
        with open(f, "wb") as fh:
            pickle.dump(b, fh, protocol=4)
        return b

    def calibrate(self, arm: str, texts: list[str], labels: np.ndarray | None):
        import fidetype.trust as ft

        R, m12, m14 = self.R, self.m12, self.m14
        xs = [self.W.get(r) for r in self.cal]
        nulls = [self.W.get(self.cal[i], "shuffled") for i in R.null_pick(len(self.cal))]
        if arm in ("S", "SL"):
            G = m12.GATE
            return ft.calibrate(xs, texts, alpha=R.ALPHA, delta=R.DELTA, input_kind="logits", vocab=R.A.key_ctc_vocab(),
                                blank=0, input_scale="log_probs", frame_period=R.FRAME_S, decode_fn=m12.decode_gated,
                                null_inputs=nulls, decoder_name=R.DECODER_NAME + "+intended-text+nosignal-gate",
                                decoder_version=(f"1-w{self.tune['w']}-c{self.tune['c']}-k{G['k_min']}-r{G['r_min']:.4f}-"
                                                 f"{G['r_max']:.4f}"),
                                modality="emg", name=f"p11-12-{arm}", seed=R.SEED, audit_text=False, **R.arm_kw(arm))
        # L-FL: refit the P11-14 confidence on the tuning items with these labels (shipped: the real labels)
        tab = m14.tuning_table(self.an, self.cal, "FL")
        pos = m14.tune_pos(self.cal)
        y = tab["right"] if labels is None else np.asarray(labels, bool)[pos]
        okm = tab["ok"]
        model = m14.Learned.fit(tab["X"][okm], y[okm])
        fn = m14.GuardFn(self.an, "L-FL", model)
        name, _ = "", ""
        c = m14.DECODERS["FL"]
        name = ("fidetype-p11-01-crt+e2q-keys+inbeam-tatoeba-noE2Q-6gram+lexicon+intended-text+nosignal-gate+conf-L")
        ver = f"p11-14-w{c['w']}-b{c['beta']}-l{c['lam']}-B{c['B']}-L{model.digest()}"
        return ft.calibrate(xs, texts, alpha=R.ALPHA, delta=R.DELTA, input_kind="logits", vocab=self.an.KV, blank=0,
                            input_scale="log_probs", frame_period=R.FRAME_S, decode_fn=fn, null_inputs=nulls,
                            decoder_name=name, decoder_version=ver, modality="emg", name="p11-14-L-FL", seed=R.SEED,
                            audit_text=False)

    def run_job(self, arm: str, kind: str, seed: int) -> dict:
        import fidetype.trust as ft

        f = guard_path(OWN / "e2q" / "runs" / f"{arm}-{kind}-{seed:02d}.json")
        if f.exists():
            return load_json(f)  # type: ignore[return-value]
        b = self.base(arm)
        t0 = time.time()
        if kind == "real":
            labels, texts = None, list(self.truths)
        else:
            rng = np.random.default_rng([20261125, seed, NULL_CODE[kind], ARM_CODE[arm]])
            labels = null_labels(kind, b["right"], b["comm"], self.users, rng)
            texts = build_texts(self.truths, b["top1"], b["comm"], b["right"], labels, self.users, rng)
            chk = np.array([c and same(t, tr) for c, t, tr in zip(b["comm"], b["top1"], texts)])
            assert np.array_equal(chk, labels & b["comm"]), "texts do not give the null labels"
        rec: dict = {"arm": arm, "null": kind, "seed": seed}
        try:
            g = self.calibrate(arm, texts, labels)
        except ft.NullControlError as e:
            rec.update(status="refused", reason=str(e)[:500], certified=False)
        else:
            sh = g.sheet
            thr = float(sh.commit_threshold)
            rec.update(status="guard", config_id=g.config_id, commit_threshold=thr if math.isfinite(thr) else None,
                       lambda_hat=float(sh.lambda_hat) if math.isfinite(sh.lambda_hat) else None,
                       feasible=bool(sh.feasible), ltt_commits=int(sh.ltt_commits),
                       ltt_wrong=int(sh.ltt_wrong_commits), n_ltt=int(sh.n_ltt),
                       controls={c.name: [int(c.n_commit), int(c.n)] for c in sh.controls},
                       certified=bool(math.isfinite(thr) and sh.ltt_commits >= 1))
        rec["seconds"] = round(time.time() - t0, 1)
        save_json(rec, f)
        return rec

    def test_decisions(self, arm: str) -> list[dict]:
        p = DER / ("p11-14" if arm == "L-FL" else "p11-12") / f"decisions-{arm}.json"
        d = load_json(p)
        assert d["units"] == [r["unit"] for r in self.ev]  # type: ignore[index]
        return d["real"]  # type: ignore[index]


def stage_e2q_base() -> dict:
    E = E2Q()
    out: dict = {}
    ev_users = [r["i"] for r in E.ev]
    ev_truth = [E.R.intended_truth(r) for r in E.ev]
    for arm in ARMS:
        b = E.base(arm)
        d = E.test_decisions(arm)
        commit = np.array([x["action"] == "commit" for x in d])
        wrong = np.array([c and not same(x["text"], t) for c, x, t in zip(commit, d, ev_truth)])
        top_ok = np.array([bool(x.get("top1")) for x in d])
        right_t = np.array([o and same(x["top1"], t) for o, x, t in zip(top_ok, d, ev_truth)])
        res = r3(ev_users, commit, wrong)
        # descriptive: per-user base rates (share of right top-1 among committable items), cal and test
        cal_rate, test_rate = [], []
        for u in sorted(set(ev_users)):
            mc = (E.users == u) & b["comm"]
            mt = (np.array(ev_users) == u) & top_ok
            cal_rate.append(float(b["right"][mc].mean()))
            test_rate.append(float(right_t[mt].mean()))
        # eta^2 of the test score (p_top1) on the user, committable items
        s = np.array([x["p_top1"] for x in d], float)
        uu = np.array(ev_users)
        sm = s[top_ok]
        um = uu[top_ok]
        gm = np.array([sm[um == u].mean() for u in um])
        eta2 = float(((gm - sm.mean()) ** 2).sum() / ((sm - sm.mean()) ** 2).sum())
        # B1 own-user check: commit precision vs the commit-weighted own-user test base rate
        rate_of = dict(zip(sorted(set(ev_users)), test_rate))
        cu = uu[commit]
        prec = float(1 - wrong[commit].mean()) if commit.any() else math.nan
        own_base = float(np.mean([rate_of[u] for u in cu])) if commit.any() else math.nan
        out[arm] = {"r3": res, "cal_base_rate_range": [min(cal_rate), max(cal_rate)],
                    "test_base_rate_range": [min(test_rate), max(test_rate)],
                    "cal_test_r": float(np.corrcoef(cal_rate, test_rate)[0, 1]),
                    "pooled_test_base_rate": float(right_t[top_ok].mean()),
                    "eta2_score_on_user": eta2, "commit_precision": prec,
                    "commit_weighted_own_user_base_rate": own_base, "own_user_excess": prec - own_base,
                    "pooled_excess": prec - float(right_t[top_ok].mean()),
                    "users_with_commits": int(len(set(cu.tolist()))),
                    "cal_committable": int(b["comm"].sum()), "cal_right": int(b["right"].sum())}
        log(f"e2q-base {arm}: commits {res['commits']} wrong {res['wrong']} R3 {res['rule']} passed {res['passed']}")
    save_json(out, guard_path(OWN / "e2q" / "base.json"))
    return out


def jobs_all() -> list[tuple[str, str, int]]:
    js = [(a, "real", 0) for a in ARMS]
    for s in SEEDS:
        for k in NULLS:
            for a in ARMS:
                js.append((a, k, s))
    return js


def stage_e2q_null(worker: int, n_workers: int) -> None:
    below_normal()
    E = E2Q()
    js = jobs_all()[worker::n_workers]
    for n, (a, k, s) in enumerate(js, 1):
        r = E.run_job(a, k, s)
        log(f"w{worker} {n}/{len(js)} {a} {k} {s}: {r['status']} cert {r.get('certified')} "
            f"commits {r.get('ltt_commits')} wrong {r.get('ltt_wrong')} thr {r.get('commit_threshold')} ({r['seconds']} s)")
    (OWN / "e2q" / f"DONE-w{worker}").write_text("done\n", encoding="utf-8")


def stage_launch() -> None:
    py = sys.executable
    for w in range(N_WORKERS):
        lf = guard_path(OWN / "e2q" / f"worker-{w}.out")
        flags = 0
        if os.name == "nt":
            flags = 0x00000008 | 0x00000200 | 0x00004000  # DETACHED_PROCESS | NEW_PROCESS_GROUP | BELOW_NORMAL
        with open(lf, "ab") as fh:
            subprocess.Popen([py, str(Path(__file__).resolve()), "--stage", "e2q-null", "--worker", str(w),
                              "--workers", str(N_WORKERS)], stdout=fh, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, creationflags=flags, cwd=str(REPO))
    log(f"launched {N_WORKERS} workers")


# --- SpanishBCBL (score level) ----------------------------------------------------------------------------


def stage_meg() -> dict:
    use_snapshot()
    from fidetype.trust.risk_control import crc_threshold, ltt_threshold

    d = load_json(MEG_ITEMS)
    fit, test = d["fit"], d["test"]  # type: ignore[index]
    num = lambda v: np.array([float(x) for x in v])  # noqa: E731
    s, c, f = num(fit["score"]), num(fit["loss_c"]), num(fit["loss_f"])
    st, ct = num(test["score"]), num(test["loss_c"])
    val_lab = [json.loads(x) for x in (MEG_STREAMS / "val" / "labels.jsonl").read_text(encoding="utf-8").splitlines() if x]
    users = np.array([r["subject"] for r in val_lab])
    assert len(users) == s.size == 437
    parts_test = d["participants_test"]  # type: ignore[index]
    comm = np.isfinite(s)
    out: dict = {"n_val": int(s.size), "n_val_committable": int(comm.sum()), "n_val_groups": len(set(users.tolist())),
                 "methods": {}}
    for meth in ("crc", "ltt"):
        fn = (lambda s_, c_, f_: crc_threshold(s_, c_, ALPHA, f_)) if meth == "crc" else \
             (lambda s_, c_, f_: ltt_threshold(s_, c_, ALPHA, DELTA, f_))
        lam = fn(s, c, f).threshold
        commit = st >= lam
        wrong = commit & (ct > 0)
        card = load_json(REPO / "benchmark" / "results" / "v0.2" / f"spanishbcbl-meg__convctc-m-async__{meth}.json")
        sw = card["safe_wpm"]  # type: ignore[index]
        rec: dict = {"lambda": lam, "test_commits": int(commit.sum()), "test_wrong": int(wrong.sum()),
                     "card_commits": sw["n_commits"], "card_wrong": sw["n_wrong_commits"],
                     "reproduces_card": bool(int(commit.sum()) == sw["n_commits"] and int(wrong.sum()) == sw["n_wrong_commits"]),
                     "real_val_commits": int((s >= lam).sum()), "r3": r3(parts_test, commit, wrong), "nulls": {}}
        right = comm & (c == 0)
        for kind in NULLS:
            runs = []
            for seed in SEEDS:
                rng = np.random.default_rng([20261125, seed, NULL_CODE[kind], 10 + (meth == "ltt")])
                lab = null_labels(kind, right, comm, users, rng)
                c2 = np.where(comm, (~lab).astype(float), c)
                lam2 = fn(s, c2, f).threshold
                k = int((s >= lam2).sum()) if math.isfinite(lam2) else 0
                runs.append({"seed": seed, "lambda": lam2 if math.isfinite(lam2) else None, "commits": k,
                             "wrong": int(((s >= lam2) & (c2 > 0)).sum()) if math.isfinite(lam2) else 0,
                             "certified": bool(math.isfinite(lam2) and k >= 1)})
            rec["nulls"][kind] = runs
        out["methods"][meth] = rec
        log(f"meg {meth}: lam {lam} commits {rec['test_commits']}/{rec['test_wrong']} card {rec['reproduces_card']} "
            + " ".join(f"{k} cert {sum(r['certified'] for r in v)}/20" for k, v in rec["nulls"].items()))
    # descriptive: per-participant val base rate, eta^2 of the score on the participant
    rates = [float(right[comm & (users == u)].mean()) for u in sorted(set(users.tolist())) if (comm & (users == u)).any()]
    out["val_base_rate_range"] = [min(rates), max(rates)]
    sm, um = s[comm], users[comm]
    gm = np.array([sm[um == u].mean() for u in um])
    out["eta2_score_on_participant"] = float(((gm - sm.mean()) ** 2).sum() / ((sm - sm.mean()) ** 2).sum())
    save_json(out, guard_path(OWN / "meg.json"))
    return out


# --- other pooled cards: per-group breakdown ------------------------------------------------------------


GROUP_CARDS = {
    "T-CAL": ("toronto-semg__cnn-calib__crc", SUB_B, "toronto-semg"),
    "T-XS": ("toronto-semg__cnn-xsession__crc", SUB_B, "toronto-semg"),
    "S-T15": ("b2t25-t15__m4-13__guard", SUB_B, "b2t25-t15"),
    "S-T12": ("b2t24-t12__t12v2__guard", SUB_A, "b2t24-t12"),
    "S-B2T-ours-crc": ("b2t25-t15__ours__crc", SUB_B, "b2t25-t15"),
    "S-B2T-ours-ltt": ("b2t25-t15__ours__ltt", SUB_B, "b2t25-t15"),
    "S-B2T-pub-crc": ("b2t25-t15__published__crc", SUB_B, "b2t25-t15"),
    "S-B2T-pub-ltt": ("b2t25-t15__published__ltt", SUB_B, "b2t25-t15"),
}


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def stage_groups() -> dict:
    out: dict = {}
    for gid, (stem, root, track) in GROUP_CARDS.items():
        truth = {r["unit"]: r for r in read_jsonl(root / "truth" / f"{track}.jsonl")[1:]}
        units = read_jsonl(root / "submissions" / stem / "units.jsonl")[1:]
        card = load_json(REPO / "benchmark" / "results" / "v0.2" / f"{stem}.json")
        sw = card["safe_wpm"]  # type: ignore[index]
        used = [u for u in units if u["unit"] in truth]
        commit = np.array([u["action"] == "commit" for u in used])
        wrong = np.array([c and not same(u["nbest"][0]["text"], truth[u["unit"]]["text"]) for c, u in zip(commit, used)])
        groups = [truth[u["unit"]]["group"] for u in used]
        rec = r3(groups, commit, wrong)
        rec.update(card_commits=sw["n_commits"], card_wrong=sw["n_wrong_commits"], card_n=card["n_trials"],  # type: ignore[index]
                   reproduces_card=bool(rec["commits"] == sw["n_commits"] and rec["wrong"] == sw["n_wrong_commits"]
                                        and rec["n"] == card["n_trials"]))  # type: ignore[index]
        out[gid] = rec
        log(f"groups {gid}: n {rec['n']} commits {rec['commits']} wrong {rec['wrong']} card {rec['reproduces_card']} "
            f"{rec['rule']} passed {rec['passed']}")
    save_json(out, guard_path(OWN / "groups.json"))
    return out


# --- summary --------------------------------------------------------------------------------------------


def null_rules(runs: dict[str, list[dict]], count_key: str) -> dict:
    cert = {k: sum(bool(r["certified"]) for r in v) for k, v in runs.items()}
    cnt = {k: [float(r.get(count_key) or 0) for r in v] for k, v in runs.items()}
    p_nw = mwu_greater(cnt["NW"], cnt["NP"])
    p_nx = mwu_greater(cnt["NX"], cnt["NP"])
    r1 = cert["NX"] <= R1_MAX
    r1ref = cert["NP"] > R1_MAX
    r2 = p_nw >= R2_P and p_nx >= R2_P
    return {"certified_of_20": cert,
            "commits_median": {k: float(np.median(v)) for k, v in cnt.items()},
            "commits_range": {k: [min(v), max(v)] for k, v in cnt.items()},
            "mwu_p_NW_gt_NP": p_nw, "mwu_p_NX_gt_NP": p_nx,
            "R1": r1, "R1_ref_applies": r1ref, "R2": r2, "null_pass": bool((r1 or r1ref) and r2)}


def strip(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if not k.startswith("_")}


def stage_summary() -> dict:
    base = load_json(OWN / "e2q" / "base.json")
    res: dict = {"task": "pooled-guard check (diagnostic after B1)", "plan": "plan.md (8dde818)",
                 "date": time.strftime("%Y-%m-%d %H:%M"), "alpha": ALPHA, "delta": DELTA,
                 "note": "aggregates only: no per-user value for emg2qwerty, no text, no id",
                 "emg2qwerty_licence": {"data.licence": "CC-BY-NC-SA-4.0", "data.research_only": True}, "guards": {}}
    for arm in ARMS:
        runs: dict[str, list[dict]] = {}
        for k in NULLS:
            runs[k] = [load_json(OWN / "e2q" / "runs" / f"{arm}-{k}-{s:02d}.json") for s in SEEDS]  # type: ignore[misc]
        real = load_json(OWN / "e2q" / "runs" / f"{arm}-real-00.json")
        b = dict(base[arm])  # type: ignore[index]
        r3r = strip(b.pop("r3"))
        nr = null_rules(runs, "ltt_commits")
        refused = {k: sum(r["status"] == "refused" for r in v) for k, v in runs.items()}
        wrong_med = {k: float(np.median([r.get("ltt_wrong") or 0 for r in v])) for k, v in runs.items()}
        g = {"id": {"S": "E-S", "SL": "E-SL", "L-FL": "E-LFL"}[arm], "recalibration": "full shipped recipe",
             "reproduction": {"config_id": real.get("config_id"), "shipped_config_id": SHIPPED_ID.get(arm),  # type: ignore[union-attr]
                              "ltt_commits": real.get("ltt_commits"), "ltt_wrong": real.get("ltt_wrong"),  # type: ignore[union-attr]
                              "commit_threshold": real.get("commit_threshold")},  # type: ignore[union-attr]
             "nulls": {**nr, "refused": refused, "ltt_wrong_median": wrong_med}, "per_user": r3r,
             "descriptive": b}
        if arm == "L-FL":
            g["reproduction"]["shipped_config_id"] = load_json(DER / "p11-14" / "guard-L-FL.status.json").get("config_id")  # type: ignore[union-attr]
        g["outcome"] = "pass" if (nr["null_pass"] and r3r["passed"]) else "FAIL"
        # emg2qwerty: no single-user value in the repo (research-only data): drop maxima and ranges
        for k in ("max_rate", "max_cp_upper", "group_n_range"):
            g["per_user"].pop(k, None)
        for k in ("cal_base_rate_range", "test_base_rate_range"):
            g["descriptive"].pop(k, None)
        res["guards"][g["id"]] = g
    meg = load_json(OWN / "meg.json")
    for meth in ("crc", "ltt"):
        m = meg["methods"][meth]  # type: ignore[index]
        nr = null_rules(m["nulls"], "commits")
        r3r = strip(m["r3"])
        res["guards"][f"M-{meth.upper()}"] = {
            "recalibration": "score level (calibrated score kept, loss permuted, shipped threshold step)",
            "reproduction": {k: m[k] for k in ("lambda", "test_commits", "test_wrong", "card_commits", "card_wrong",
                                               "reproduces_card", "real_val_commits")},
            "nulls": nr, "per_user": r3r,
            "descriptive": {k: meg[k] for k in ("n_val", "n_val_committable", "n_val_groups", "val_base_rate_range",  # type: ignore[index]
                                                "eta2_score_on_participant")},
            "outcome": "pass" if (nr["null_pass"] and r3r["passed"]) else "FAIL"}
    grp = load_json(OWN / "groups.json")
    for gid, rec in grp.items():  # type: ignore[union-attr]
        r = strip(rec)
        res["guards"][gid] = {"recalibration": "none (per-group breakdown only)", "per_group": r,
                              "outcome": "pass" if r["passed"] else "FAIL"}
    OUT.mkdir(exist_ok=True)
    save_json(res, OUT / "summary.json")
    for k, v in res["guards"].items():
        log(f"summary {k}: {v['outcome']}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["e2q-base", "e2q-null", "launch", "meg", "groups", "summary", "job"])
    ap.add_argument("--worker", type=int, default=0)
    ap.add_argument("--workers", type=int, default=N_WORKERS)
    ap.add_argument("--arm", default="S")
    ap.add_argument("--null", default="real")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    if a.stage == "e2q-base":
        stage_e2q_base()
    elif a.stage == "e2q-null":
        stage_e2q_null(a.worker, a.workers)
    elif a.stage == "launch":
        stage_launch()
    elif a.stage == "job":
        below_normal()
        print(json.dumps(E2Q().run_job(a.arm, a.null, a.seed), indent=1))
    elif a.stage == "meg":
        stage_meg()
    elif a.stage == "groups":
        stage_groups()
    elif a.stage == "summary":
        stage_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
