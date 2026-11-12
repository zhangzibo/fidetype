"""Make the data figures of Paper 1 (Fidetype) from committed result files only.

Run from the repo root:   .venv/Scripts/python papers/paper1/make_figures.py
Output: papers/paper1/figures/*.pdf (vector) and a few *.png previews (--png).

Inputs (all committed):
  experiments/2026-11-10-b2t25-trust/results/trust.json            (B2T '25 harness)
  experiments/2026-11-11-emg-toronto/results/trust.json            (Toronto sEMG harness)
  experiments/2026-11-11-m2-13-conformal/results/splits.json        (CRC / LTT over 200 splits)
  experiments/2026-11-11-m2-13-conformal/results/items-*.json       (per-trial scores and losses)
  experiments/2026-11-11-m2-16-online-recal/results/online.json     (drift protocol)
  experiments/2026-11-11-m2-16-online-recal/results/items-emg-*.json
  experiments/2026-11-11-m1-09-async-full/analysis/analysis.json    (MEG CER)
  experiments/2026-11-11-g1-async-meg-trust/results/harness-async.json  (MEG trust, async; used only if git tracks it)
  papers/paper1/data/markdown-only-numbers.json                     (numbers that exist only in markdown; sources inside)
  papers/paper1/data/r1-derived.json                                (analysis_r1.py: split percentiles from committed items)
  experiments/2026-11-11-g1-async-meg-trust/results/null-audit-async.json (MEG guard-risk AUROC)

The script recomputes two things from per-trial items: the risk-coverage curves (Fig. risk) and the
running wrong-commit trace under drift (Fig. drift a). The drift trace re-runs fidetype.trust.online_risk
with the M2-16 configuration and asserts that the final means equal online.json.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
EXP = REPO / "experiments"
OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)
PNG = "--png" in sys.argv

# Okabe-Ito colour-blind-safe palette
C = {"commit": "#D55E00", "trust": "#0072B2", "gaze": "#555555", "crc": "#009E73", "ltt": "#CC79A7",
     "old": "#E69F00", "aci": "#56B4E9", "aciw": "#0072B2", "window": "#F0E442", "decay": "#999999",
     "shuf": "#E69F00", "zeros": "#999999", "pub": "#CC79A7"}
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "axes.spines.top": False,
    "axes.spines.right": False, "axes.linewidth": 0.6, "lines.linewidth": 1.2, "pdf.fonttype": 42,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})
FULL, HALF = 6.3, 3.1  # inches: text width of the one-column draft, and half of it
ALPHA = 0.05


def load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def tracked(rel: str) -> bool:
    r = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=REPO, capture_output=True)
    return r.returncode == 0


def save(fig, name: str) -> None:
    fig.savefig(OUT / f"{name}.pdf")
    if PNG:
        fig.savefig(OUT / f"{name}.png", dpi=200)
    plt.close(fig)
    print("wrote", name)


def panel_label(ax, s: str) -> None:
    t = ax.get_title()
    ax.set_title("")
    ax.set_title(f"({s}) {t}", loc="left")


# ---------------------------------------------------------------- data
B2T = load("experiments/2026-11-10-b2t25-trust/results/trust.json")["levels"]["word"]
EMG = load("experiments/2026-11-11-emg-toronto/results/trust.json")["conditions"]
MD = load("papers/paper1/data/markdown-only-numbers.json")
R1 = load("papers/paper1/data/r1-derived.json")
SPLITS = load("experiments/2026-11-11-m2-13-conformal/results/splits.json")
G1_REL = "experiments/2026-11-11-g1-async-meg-trust/results/harness-async.json"
G1 = load(G1_REL) if tracked(G1_REL) else None


def b2t_row(key: str) -> dict:
    p, ci = B2T["policies"][key], B2T["bootstrap_trials"]["policies"][key]
    return {"ewpm": p["ewpm"], "ewpm_ci": ci["ewpm"], "wc": p["wrong_commit_rate"], "wc_ci": ci["wrong_commit_rate"]}


def emg_row(cond: str, key: str) -> dict:
    c = EMG[cond]
    p, ci = c["policies"][key], c["bootstrap_sentences"]["policies"][key]
    return {"ewpm": p["ewpm"], "ewpm_ci": ci["ewpm"], "wc": p["wrong_commit_rate"], "wc_ci": ci["wrong_commit_rate"]}


def meg_rows() -> tuple[dict, dict, float, str]:
    if G1 is not None:
        # sentence-cluster CIs (17 unique test sentences) are the primary MEG intervals
        p, ci = G1["policies"], G1["bootstrap"]["sentences"]["policies"]
        r = {k: {"ewpm": p[k]["ewpm"], "ewpm_ci": ci[k]["ewpm"], "wc": p[k]["wrong_commit_rate"],
                 "wc_ci": ci[k]["wrong_commit_rate"]} for k in ("commit", "trust")}
        gaze = p["gaze_only"]["ewpm"]
        return r["commit"], r["trust"], gaze, "MEG (async M1-09)"
    m = MD["meg_trust_sync_m1_15"]
    commit = {"ewpm": m["commit"]["ewpm"], "ewpm_ci": None, "wc": m["commit"]["wrong_commit"], "wc_ci": None}
    trust = {"ewpm": m["trust"]["ewpm"], "ewpm_ci": m["trust"]["ewpm_ci"], "wc": m["trust"]["wrong_commit"], "wc_ci": None}
    return commit, trust, m["gaze_only"]["ewpm"], "MEG (sync M1-15)"


def errbar(ax, r: dict, color: str, marker: str, filled: bool, label: str | None = None) -> None:
    xe = None if r["ewpm_ci"] is None else [[r["ewpm"] - r["ewpm_ci"][0]], [r["ewpm_ci"][1] - r["ewpm"]]]
    ye = None if r["wc_ci"] is None else [[max(r["wc"] - r["wc_ci"][0], 0)], [max(r["wc_ci"][1] - r["wc"], 0)]]
    ax.errorbar(r["ewpm"], r["wc"], xerr=xe, yerr=ye, fmt=marker, ms=5, color=color,
                mfc=color if filled else "white", mew=1.1, elinewidth=0.8, capsize=1.5, label=label, zorder=3)


# ---------------------------------------------------------------- Fig 1: teaser
def fig_teaser() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 2.5), sharey=True)
    # (a) B2T
    ax = axes[0]
    for ck, tk, name in (("w_b_top1_commit", "w_c_trust", "our decoder"), ("w_p_published_commit", "w_q_published_trust", "published decoder")):
        a, b = b2t_row(ck), b2t_row(tk)
        ax.annotate("", xy=(b["ewpm"], b["wc"]), xytext=(a["ewpm"], a["wc"]),
                    arrowprops=dict(arrowstyle="->", color="#888888", lw=0.8, shrinkA=4, shrinkB=4))
        errbar(ax, a, C["commit"], "o", False)
        errbar(ax, b, C["trust"], "o", True)
        ax.text(a["ewpm"], a["wc"] + 0.06, name, ha="center", fontsize=6.5)
    for dk in ("b2t-ours", "b2t-published"):
        nc = SPLITS["datasets"][dk]["whole_test"]["never_commit"]
        ax.plot(nc["ewpm"], nc["wrong_commit"], "^", ms=5, color=C["gaze"], mfc="white", mew=1.0, zorder=4)
    ax.axvline(B2T["gaze_only_ewpm"], color=C["gaze"], ls="--", lw=0.9)
    ax.set_title("Intracortical (B2T '25)")
    ax.set_xlim(2, 22)
    # (b) EMG
    ax = axes[1]
    names = {"calib": "session-cal.", "xsession": "cross-session", "xsubject": "cross-subject"}
    for cond in ("calib", "xsession", "xsubject"):
        a, b = emg_row(cond, "b_top1_commit"), emg_row(cond, "c_trust")
        ax.annotate("", xy=(b["ewpm"], b["wc"]), xytext=(a["ewpm"], a["wc"]),
                    arrowprops=dict(arrowstyle="->", color="#888888", lw=0.8, shrinkA=4, shrinkB=4))
        errbar(ax, a, C["commit"], "s", False)
        errbar(ax, b, C["trust"], "s", True)
        off = {"calib": (0.15, 0.03), "xsession": (0.25, -0.06), "xsubject": (0.0, 0.05)}[cond]
        ax.text(a["ewpm"] + off[0], a["wc"] + off[1], names[cond], fontsize=6.3,
                ha="center" if off[0] == 0 else "left")
    ax.axvline(EMG["calib"]["gaze_only_ewpm"], color=C["gaze"], ls="--", lw=0.9)
    ax.set_title("sEMG (Toronto)")
    ax.set_xlim(2.5, 9.5)
    # (c) MEG
    ax = axes[2]
    a, b, gaze, title = meg_rows()
    ax.annotate("", xy=(b["ewpm"], b["wc"]), xytext=(a["ewpm"], a["wc"]),
                arrowprops=dict(arrowstyle="->", color="#888888", lw=0.8, shrinkA=4, shrinkB=4))
    errbar(ax, a, C["commit"], "D", False, "always commit")
    errbar(ax, b, C["trust"], "D", True, "trust layer")
    ax.annotate("commits 0%", xy=(b["ewpm"], b["wc"]), xytext=(2.9, 0.35), fontsize=6.3,
                ha="center", arrowprops=dict(arrowstyle="-", color="#888888", lw=0.6))
    ax.plot([], [], "^", ms=5, color=C["gaze"], mfc="white", label="always offer")
    ax.axvline(gaze, color=C["gaze"], ls="--", lw=0.9, label="gaze typing only")
    ax.set_title("MEG (asynchronous)")
    ax.set_xlim(2.0, 4.0)
    for i, ax in enumerate(axes):
        ax.set_xlabel("eWPM (higher is better)")
        ax.axhline(ALPHA, color="#BBBBBB", lw=0.6, ls=":")
        panel_label(ax, "abc"[i])
    axes[0].set_ylabel("wrong commits / all sentences\n(lower is better)")
    axes[0].set_ylim(-0.04, 1.08)
    h, lab = axes[2].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=4, frameon=False, handlelength=1.2, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(w_pad=0.6, rect=(0, 0.08, 1, 1))
    save(fig, "fig1_teaser")


# ---------------------------------------------------------------- Fig: eWPM per policy
def fig_ewpm() -> None:
    rows = []  # (group, label, value, ci, color)
    rows += [("B2T '25", "commit (ours)", *_v(b2t_row("w_b_top1_commit")), C["commit"]),
             ("B2T '25", "trust (ours)", *_v(b2t_row("w_c_trust")), C["trust"]),
             ("B2T '25", "commit (published)", *_v(b2t_row("w_p_published_commit")), C["commit"]),
             ("B2T '25", "trust gate (published)", *_v(b2t_row("w_q_published_trust")), C["trust"])]
    for cond, nm in (("calib", "session-cal."), ("xsession", "cross-session"), ("xsubject", "cross-subject")):
        rows += [("sEMG", f"commit, {nm}", *_v(emg_row(cond, "b_top1_commit")), C["commit"]),
                 ("sEMG", f"trust, {nm}", *_v(emg_row(cond, "c_trust")), C["trust"])]
    a, b, gaze_meg, title = meg_rows()
    rows += [("MEG", "commit", *_v(a), C["commit"]), ("MEG", "trust", *_v(b), C["trust"])]
    gazes = {"B2T '25": B2T["gaze_only_ewpm"], "sEMG": EMG["calib"]["gaze_only_ewpm"], "MEG": gaze_meg}
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 2.4), gridspec_kw={"width_ratios": [4, 5, 2.4]})
    for ax, g in zip(axes, ("B2T '25", "sEMG", "MEG")):
        rr = [r for r in rows if r[0] == g]
        y = np.arange(len(rr))[::-1]
        for yi, r in zip(y, rr):
            ci = r[3]
            ax.barh(yi, r[2], color=r[4], alpha=0.85, height=0.65)
            if ci is not None:
                ax.errorbar(r[2], yi, xerr=[[r[2] - ci[0]], [ci[1] - r[2]]], color="black", lw=0.8, capsize=1.5)
        ax.axvline(gazes[g], color=C["gaze"], ls="--", lw=0.9)
        ax.set_yticks(y)
        ax.set_yticklabels([r[1] for r in rr])
        ax.set_xlabel("eWPM")
        ax.set_title(g if g != "MEG" else title, fontsize=8)
    axes[0].text(gazes["B2T '25"], 3.55, " gaze only", color=C["gaze"], fontsize=6.5, va="center")
    fig.tight_layout(w_pad=0.4)
    save(fig, "fig_ewpm_policies")


def _v(r: dict):
    return r["ewpm"], r["ewpm_ci"]


# ---------------------------------------------------------------- Fig: risk-coverage
def _items(rel: str) -> dict:
    d = load(rel)["test"]
    s = np.array([float(x) for x in d["score"]])
    return {"s": s, "wc_c": np.asarray(d["wc_c"], float), "wc_f": np.asarray(d["wc_f"], float)}


RISK_SETS = [("B2T '25, our decoder", "experiments/2026-11-11-m2-13-conformal/results/items-b2t-ours.json", C["trust"], "-"),
            ("B2T '25, published", "experiments/2026-11-11-m2-13-conformal/results/items-b2t-published.json", C["pub"], "-"),
            ("sEMG session-cal.", "experiments/2026-11-11-m2-16-online-recal/results/items-emg-calib.json", C["crc"], "--"),
            ("sEMG cross-session", "experiments/2026-11-11-m2-16-online-recal/results/items-emg-xsession.json", C["old"], "--"),
            ("MEG (asynchronous)", "experiments/2026-11-11-g1-async-meg-trust/results/items-meg-async.json", C["gaze"], ":")]
SMALL = (2.15, 2.0)


def _curve(it: dict, min_commits: int = 10):
    fin = np.sort(np.unique(it["s"][np.isfinite(it["s"])]))[::-1]
    cov, marg, sel = [], [], []
    for lam in fin:
        on = it["s"] >= lam
        if on.sum() < min_commits:
            continue
        cov.append(on.mean())
        marg.append(np.where(on, it["wc_c"], it["wc_f"]).mean())
        sel.append(it["wc_c"][on].mean())
    return np.array(cov), np.array(marg), np.array(sel)


def fig_risk() -> None:
    for kind in ("marginal", "selective"):
        fig, ax = plt.subplots(figsize=SMALL)
        for name, rel, col, ls in RISK_SETS:
            cov, marg, sel = _curve(_items(rel))
            ax.plot(cov, marg if kind == "marginal" else sel, ls=ls, color=col, label=name, lw=1.1)
        ax.axhline(ALPHA, color="black", lw=0.6, ls=":")
        ax.set_xlabel("commit rate")
        ax.set_xlim(0, 0.7)
        if kind == "marginal":
            ax.set_ylabel("wrong commits / all items")
            ax.set_ylim(0, 0.32)
            ax.legend(frameon=True, framealpha=0.9, edgecolor="none", fontsize=5.4, loc="upper left")
            save(fig, "fig_risk_coverage")
        else:
            ax.set_ylabel("wrong commits / commits")
            ax.set_ylim(0, 1.02)
            save(fig, "fig_selective_risk")


# ---------------------------------------------------------------- Fig: CRC / LTT over splits
def fig_crc() -> None:
    S = load("experiments/2026-11-11-m2-13-conformal/results/splits.json")
    MEGCRC = load("experiments/2026-11-11-g1-async-meg-trust/results/crc-splits-async.json")
    ds = [("b2t-ours", "B2T '25\nours"), ("b2t-published", "B2T '25\npublished"), ("meg-async", "MEG\n(asynchronous)")]
    meth = [("old", "fixed gate", C["old"]), ("crc", "CRC", C["crc"]), ("ltt", "LTT", C["ltt"])]
    fig, axes = plt.subplots(1, 2, figsize=(FULL, 2.2), sharey=True)
    for ax, ncal in zip(axes, ("100", "408")):
        for i, (dk, dn) in enumerate(ds):
            for j, (mk, mn, col) in enumerate(meth):
                if dk == "meg-async":
                    w = R1["splits_meg_async"][ncal][mk]
                    ref = MEGCRC["splits"][f"random_{ncal}"][mk]["wrong_commit"]["mean"]
                else:
                    w = R1["splits_m213"][dk][ncal][mk]
                    ref = S["datasets"][dk]["splits"][ncal][mk]["wrong_commit"]["mean"]
                assert abs(w["wrong_commit_mean"] - ref) < 1e-4
                x = i + (j - 1) * 0.22
                ax.plot([x, x], [w["wrong_commit_p05"], w["wrong_commit_p90"]], color=col, lw=2.2, alpha=0.55,
                        solid_capstyle="butt")
                ax.plot(x, w["wrong_commit_mean"], "o", color=col, ms=4.5, label=mn if i == 0 else None)
        ax.axhline(ALPHA, color="black", lw=0.6, ls=":")
        ax.set_xticks(range(len(ds)))
        ax.set_xticklabels([d[1] for d in ds])
        ax.set_title(f"$n_{{cal}}$ = {ncal}, 200 random splits")
    axes[0].set_ylabel("test wrong-commit rate")
    axes[0].legend(frameon=False, loc="upper right")
    panel_label(axes[0], "a")
    panel_label(axes[1], "b")
    fig.tight_layout()
    save(fig, "fig_crc_splits")


# ---------------------------------------------------------------- Fig: drift
def fig_drift() -> None:
    from fidetype.trust.online_risk import OnlineCommitRiskControl
    from fidetype.trust.risk_control import crc_threshold

    on_json = load("experiments/2026-11-11-m2-16-online-recal/results/online.json")
    cfg = on_json["config"]
    d = load("experiments/2026-11-11-m2-13-conformal/results/items-b2t-ours.json")
    keys = ("loss_c", "loss_f", "wc_c", "wc_f")

    def arr(x):
        o = {k: np.asarray(x[k], float) for k in keys}
        o["s"] = np.array([float(v) for v in x["score"]])
        return o

    fit, test = arr(d["fit"]), arr(d["test"])
    traces = {}
    lam = crc_threshold(fit["s"], fit["loss_c"], ALPHA, fit["loss_f"]).threshold
    on = test["s"] >= lam
    traces["offline CRC"] = np.where(on, test["wc_c"], test["wc_f"])
    for name in ("aci", "aci_window"):
        o = OnlineCommitRiskControl(alpha=ALPHA, **cfg["methods"][name])
        o.fit(fit["s"], fit["loss_c"], fit["loss_f"])
        onl = np.zeros(test["s"].size, bool)
        for i in range(test["s"].size):
            tk = o.decide(test["s"][i])
            onl[i] = tk.commit
            o.observe(tk, test["loss_c"][i], test["loss_f"][i])
        traces[name] = np.where(onl, test["wc_c"], test["wc_f"])
    ref = on_json["datasets"]["b2t-ours"]["drift"]
    chk = {"offline CRC": ref["offline"]["crc"]["wrong_commit"], "aci": ref["online"]["aci@d0"]["wrong_commit"],
           "aci_window": ref["online"]["aci_window@d0"]["wrong_commit"]}
    for k, v in chk.items():
        assert abs(traces[k].mean() - v) < 1e-9, (k, traces[k].mean(), v)

    fig, axes = plt.subplots(1, 2, figsize=(FULL, 2.3), gridspec_kw={"width_ratios": [1.1, 1]})
    ax = axes[0]
    cols = {"offline CRC": C["commit"], "aci": C["aci"], "aci_window": C["aciw"]}
    for k, tr in traces.items():
        n = np.arange(1, tr.size + 1)
        ax.plot(n, np.cumsum(tr) / n, color=cols[k], label=f"{k} (final {tr.mean():.4f})")
    ax.axhline(ALPHA, color="black", lw=0.6, ls=":")
    ax.set_xlim(50, test["s"].size)
    ax.set_ylim(0, 0.12)
    ax.set_xlabel("trials of the later half-days, in time order")
    ax.set_ylabel("running wrong-commit rate")
    ax.set_title("B2T '25, our decoder")
    ax.legend(frameon=False, loc="upper right", fontsize=6.3)
    panel_label(ax, "a")

    ax = axes[1]
    dsn = [("b2t-ours", "B2T '25\nours"), ("b2t-published", "B2T '25\npublished"), ("emg-xsession", "sEMG\ncross-session")]
    meth = [("offline CRC", None, C["commit"]), ("window", "window@d0", C["window"]), ("decay", "decay@d0", C["decay"]),
            ("aci", "aci@d0", C["aci"]), ("aci_window", "aci_window@d0", C["aciw"])]
    w = 0.16
    for i, (dk, _) in enumerate(dsn):
        dr = on_json["datasets"][dk]["drift"]
        for j, (mn, key, col) in enumerate(meth):
            v = dr["offline"]["crc"]["wrong_commit"] if key is None else dr["online"][key]["wrong_commit"]
            ax.bar(i + (j - 2) * w, v, width=w, color=col, edgecolor="black", lw=0.3, label=mn if i == 0 else None)
    ax.axhline(ALPHA, color="black", lw=0.6, ls=":")
    ax.set_xticks(range(len(dsn)))
    ax.set_xticklabels([x[1] for x in dsn])
    ax.set_ylabel("wrong-commit rate (later data)")
    ax.set_ylim(0, 0.095)
    ax.legend(frameon=False, ncol=3, fontsize=6.2, loc="upper center", columnspacing=0.8, handlelength=1.0)
    panel_label(ax, "b")
    fig.tight_layout()
    save(fig, "fig_drift")


# ---------------------------------------------------------------- Fig: null-input audit
def fig_null() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 2.2), gridspec_kw={"width_ratios": [4, 5, 5]})
    # B2T: commit_rate of always-commit vs trust (wrong commits on null input = commits)
    na = B2T["null_audit"]
    cats = [("real", "real"), ("other_trial", "other\nsentence"), ("frame_shuffled", "frame-\nshuffled"), ("uniform", "uniform")]
    _null_panel(axes[0], cats, [na["w_b_top1_commit"][c]["commit_rate"] for c, _ in cats],
                [na["w_c_trust"][c]["commit_rate"] for c, _ in cats], "B2T '25, our decoder\n(300 trials)")
    ne = EMG["xsession"]["null_audit"]
    cats = [("real", "real"), ("other_sentence", "other\nsentence"), ("frame_shuffled", "frame-\nshuffled"),
            ("zeros_input", "zeros"), ("permuted_label_decoder", "perm.\ndecoder")]
    _null_panel(axes[1], cats, [ne["b_top1_commit"][c]["commit_rate"] for c, _ in cats],
                [ne["c_trust"][c]["commit_rate"] for c, _ in cats], f"sEMG cross-session\n({EMG['xsession']['null_audit_n']} sentences)")
    nm = load("experiments/2026-11-11-g1-async-meg-trust/results/null-audit-async.json")
    cats = [("other_sentence", "other\nsentence"), ("frame_shuffled", "frame-\nshuffled"),
            ("uniform", "uniform"), ("shuffled_meg", "shuffled\nMEG"), ("zeros_meg", "zeros")]
    ax = axes[2]
    au = [_meg_auroc(nm, c) for c, _ in cats]
    x = np.arange(len(cats))
    ax.bar(x, au, 0.55, color=C["trust"], alpha=0.85)
    for xi, v in zip(x, au):
        ax.text(xi, v + 0.02, f"{v:.2f}", ha="center", fontsize=5.8)
    ax.axhline(0.5, color="black", lw=0.6, ls=":")
    ax.set_xticks(x)
    ax.set_xticklabels([c[1] for c in cats], fontsize=5.2)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("guard-risk AUROC vs real", fontsize=6.5)
    ax.yaxis.set_tick_params(labelleft=True)
    ax.set_title(f"MEG, asynchronous decoder\n({nm['n']} instances; no commits)", fontsize=7.5)
    axes[0].set_ylabel("commit rate")
    for i, ax in enumerate(axes):
        panel_label(ax, "abc"[i])
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    save(fig, "fig_null_audit")


def _meg_auroc(nm: dict, cat: str) -> float:
    """Guard-risk AUROC null vs real, as stored by the G1 null audit."""
    return float(nm["policies"]["trust"]["risk_auroc_null_vs_real"][cat])


def _null_panel(ax, cats, commit, trust, title):
    x = np.arange(len(cats))
    ax.bar(x - 0.19, commit, 0.36, color=C["commit"], label="always commit")
    ax.bar(x + 0.19, trust, 0.36, color=C["trust"], label="trust layer")
    for xi, t in zip(x, trust):
        ax.text(xi + 0.19, t + 0.02, (f"{t:.1%}" if 0 < t < 0.1 else f"{t:.0%}") if t < 0.995 else "100%", ha="center", fontsize=5.8)
    ax.set_xticks(x)
    ax.set_xticklabels([c[1] for c in cats], fontsize=5.2)
    ax.set_ylim(0, 1.12)
    ax.set_title(title, fontsize=7.5)


# ---------------------------------------------------------------- Fig: MEG CER
def fig_meg_cer() -> None:
    a = load("experiments/2026-11-11-m1-09-async-full/analysis/analysis.json")
    m, s = a["medium"], a["small"]
    rows = [("v2 async\n(published;\nother split)", MD["meg_v2_reference"]["cer"], MD["meg_v2_reference"]["sem"], C["pub"]),
            ("M1-C r4b\n(20 blocks)", MD["meg_m1c_r4b"]["greedy"], None, C["gaze"]),
            ("M1-09\nsmall", s["real/greedy"]["all"]["sent"], None, C["aci"]),
            ("M1-09\nmedium", m["real/greedy"]["all"]["sent"], None, C["trust"]),
            ("medium\n+ beam + LM", m["real/beam_lm"]["all"]["sent"], None, C["trust"]),
            ("shuffled MEG\n(control)", m["shuffled/greedy"]["all"]["sent"], None, C["shuf"]),
            ("zeros\n(control)", m["zeros/greedy"]["all"]["sent"], None, C["zeros"])]
    fig, ax = plt.subplots(figsize=(FULL, 2.1))
    x = np.arange(len(rows))
    for xi, (lab, v, e, col) in zip(x, rows):
        ax.bar(xi, v, 0.62, color=col, hatch="//" if "control" in lab else None, edgecolor="white" if "control" not in lab else "black", lw=0.3)
        if e is not None:
            ax.errorbar(xi, v, yerr=e, color="black", capsize=2, lw=0.8)
        ax.text(xi, v + 0.02 + (e or 0), f"{v:.3f}" if e is None else f"{v:.2f}", ha="center", fontsize=6.5)
    ax.set_xticks(x)
    ax.set_xticklabels([r[0] for r in rows], fontsize=6.5)
    ax.set_ylabel("test CER (greedy unless noted)")
    ax.set_ylim(0, 1.05)
    save(fig, "fig_meg_cer")


# ---------------------------------------------------------------- Fig: calibration (ECE)
def fig_ece() -> None:
    rows = [("B2T\n'25", B2T["policies"]["w_c_trust"])] + \
           [(f"sEMG\n{n}", EMG[c]["policies"]["c_trust"]) for c, n in (("calib", "s.-cal."), ("xsession", "x-sess."), ("xsubject", "x-subj."))]
    fig, ax = plt.subplots(figsize=SMALL)
    x = np.arange(len(rows))
    b = [r[1]["ece_sentence_before"] for r in rows]
    a = [r[1]["ece_sentence_after"] for r in rows]
    ax.bar(x - 0.19, b, 0.36, color=C["commit"], label="before")
    ax.bar(x + 0.19, a, 0.36, color=C["trust"], label="after scaling")
    for xi, v1, v2 in zip(x, b, a):
        ax.text(xi - 0.21, v1 + 0.01, f"{v1:.2f}", ha="center", fontsize=5.0)
        ax.text(xi + 0.21, v2 + 0.01, f"{v2:.2f}", ha="center", fontsize=5.0)
    ax.set_xticks(x)
    ax.set_xticklabels([r[0] for r in rows], fontsize=6.5)
    ax.set_ylabel("sentence-level ECE")
    ax.set_ylim(0, 0.62)
    ax.legend(frameon=False, fontsize=5.8, loc="upper left")
    save(fig, "fig_ece")


if __name__ == "__main__":
    print("MEG trust source:", "G1 async (committed)" if G1 is not None else "M1-15 sync (markdown JSON); G1 not committed")
    fig_teaser()
    fig_risk()
    fig_crc()
    fig_drift()
    fig_null()
    fig_ece()
    # fig_ewpm() and fig_meg_cer() are no longer in the paper (v1): Table 4 and Table 3 carry their numbers.
