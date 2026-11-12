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
  experiments/2026-11-12-paper1-r1-analyses/baselines/results/baselines.json  (v2: all baselines, primary-unit CIs)
  experiments/2026-11-12-paper1-r1-analyses/user-model/results/user-model-*.json (v2: user-model sensitivity)

The script recomputes the risk-coverage curves (Fig. risk) from per-trial items. Draft v2 removed the
drift figure: its offline baseline reused the fit data for calibration (see the clean-drift analysis).
The teaser (Fig. 1) reads the R1 baselines file and asserts that its trust rows equal the harness files.
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
    fig.savefig(OUT / f"{name}.pdf", metadata={"CreationDate": None})  # v4: byte-identical re-runs
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
    # v4: unified two-way bootstrap (R3 unified-ci), the same intervals as Table 1
    c = load("experiments/2026-11-12-paper1-r3-analyses/unified-ci/results/ci.json")["table2_baselines"]["meg-async"]
    r = {k: {"ewpm": c["point"][k]["ewpm"], "ewpm_ci": c["ci"]["policies"][k]["ewpm"], "wc": c["point"][k]["wrong_commit"],
             "wc_ci": c["ci"]["policies"][k]["wrong_commit"]} for k in ("always_commit", "trust")}
    return r["always_commit"], r["trust"], c["point"]["gaze_only"]["ewpm"], "MEG (async, unified CIs)"
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


# ---------------------------------------------------------------- Fig 1: teaser (v2)
R1X = "experiments/2026-11-12-paper1-r1-analyses"
R3X = "experiments/2026-11-12-paper1-r3-analyses"
# v3: one bootstrap for every CI (seed 20261112, B = 2000; R3 unified-ci). Point values equal the R1 files.
BASE = load(f"{R3X}/unified-ci/results/ci.json")["table2_baselines"]
UM: dict = load(f"{R3X}/unified-ci/results/rerun/user-model/results/"
                "user-model-emg-calib+emg-xsession+emg-xsubject+b2t-ours+b2t-published+meg-async.json")["conditions"]
DEPLOY = load(f"{R3X}/deployable-rule/results/deployable.json")["rows"]
UM_VARIANTS = [("main", "main user model"), ("fallback 10 cpm", "fallback 10 cpm"), ("fallback 40 cpm", "fallback 40 cpm"),
               ("selection x0.5", "selection ×0.5"), ("selection x2", "selection ×2"), ("p_miss 0", "miss prob. 0"),
               ("p_miss 0.2", "miss prob. 0.2"), ("symmetric offer (p_miss 0.05, no oracle retype)", "symmetric (miss 0.05)"),
               ("symmetric offer, p_miss 0.2", "symmetric, miss 0.2")]
CONDS = [("b2t-ours", "B2T '25, ours"), ("b2t-published", "B2T '25, published"), ("emg-calib", "sEMG session-cal."),
         ("emg-xsession", "sEMG cross-session"), ("emg-xsubject", "sEMG cross-subject"), ("meg-async", "MEG")]


def base_row(cond: str, key: str) -> dict:
    c = BASE[cond]
    p, ci = c["point"][key], c["ci"]["policies"][key]
    return {"ewpm": p["ewpm"], "ewpm_ci": ci["ewpm"], "wc": p["wrong_commit"], "wc_ci": ci["wrong_commit"]}


def _sqrt_axis(ax) -> None:
    """Signed square-root y-axis: expands the safety region (0-0.1) while showing 0-1."""
    f = lambda y: np.sign(y) * np.sqrt(np.abs(y))  # noqa: E731
    g = lambda y: np.sign(y) * y ** 2  # noqa: E731
    ax.set_yscale("function", functions=(f, g))
    ax.set_yticks([0, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0])
    ax.set_yticklabels(["0", "0.01", "0.05", "0.1", "0.25", "0.5", "1"])


def _check_teaser_sources() -> None:
    """The R1 baselines file must reproduce the paper's harness numbers for trust and always commit."""
    pairs = [(b2t_row("w_c_trust"), base_row("b2t-ours", "trust")),
             (b2t_row("w_b_top1_commit"), base_row("b2t-ours", "always_commit")),
             (b2t_row("w_q_published_trust"), base_row("b2t-published", "trust"))]
    for cond in ("calib", "xsession", "xsubject"):
        pairs.append((emg_row(cond, "c_trust"), base_row(f"emg-{cond}", "trust")))
    for old, new in pairs:
        assert abs(old["ewpm"] - new["ewpm"]) < 5e-3 and abs(old["wc"] - new["wc"]) < 1e-6, (old, new)


def fig_teaser() -> None:
    """v3: signed-sqrt y-axis (safety region readable), guaranteed rule (fit-A + clean LTT max-rule) added."""
    _check_teaser_sources()
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 2.6), sharey=True)
    groups = [(("b2t-ours", "our decoder"), ("b2t-published", "published")),
              (("emg-calib", "session-cal."), ("emg-xsession", "cross-session"), ("emg-xsubject", "cross-subject")),
              (("meg-async", None),)]
    marks = ["o", "s", "D"]
    # label position (dx in eWPM, y in data units, ha) next to the always-commit marker
    lab = {"b2t-ours": (0.6, 0.66, "left"), "b2t-published": (0.0, 0.27, "center"), "emg-calib": (0.25, 0.47, "left"),
           "emg-xsession": (0.25, 0.80, "left"), "emg-xsubject": (-0.2, 1.0, "right")}
    for gi, (ax, grp) in enumerate(zip(axes, groups)):
        _sqrt_axis(ax)
        for cond, name in grp:
            a, b, n = base_row(cond, "always_commit"), base_row(cond, "trust"), base_row(cond, "never_commit")
            ax.annotate("", xy=(b["ewpm"], max(b["wc"], 0.002)), xytext=(a["ewpm"], a["wc"]),
                        arrowprops=dict(arrowstyle="->", color="#888888", lw=0.8, shrinkA=4, shrinkB=4))
            errbar(ax, a, C["commit"], marks[gi], False, "always commit" if gi == 2 else None)
            # always offer has no wrong commits; drawn just below 0 so that it does not hide the trust marker
            ax.plot(n["ewpm"], -0.006, "^", ms=4.5, color=C["gaze"], mfc="white", mew=1.0, zorder=4,
                    label="always offer" if gi == 2 else None)
            errbar(ax, b, C["trust"], marks[gi], True, "trust, plug-in (no guarantee)" if gi == 2 else None)
            cr = BASE[cond]["point"]["trust"]["commit_rate"]
            if cond.startswith("b2t-") or cr > 0:
                ax.text(b["ewpm"] + (0.35 if gi == 0 else 0.12), max(b["wc"], 0.002) * 1.35 + 0.004, f"{cr:.0%}",
                        fontsize=5.6, color=C["trust"], ha="left", va="bottom")
            if name:
                dx, y, ha = lab[cond]
                ax.text(a["ewpm"] + dx, y, name, fontsize=6.2, ha=ha, va="center")
        c0 = grp[0][0]
        gaze = BASE[c0]["point"]["gaze_only"]["ewpm"]
        glm = UM[c0]["variants"]["main"]["point"]["gaze_lm"]["ewpm"]
        ax.axvline(gaze, color=C["gaze"], ls="--", lw=0.9, label="gaze typing" if gi == 2 else None)
        ax.axvline(glm, color=C["gaze"], ls="-.", lw=0.9, label="gaze + word completion" if gi == 2 else None)
    # guaranteed rule: fit-A pipeline + clean calibration, LTT max-rule, splits A and B (same 816 test trials)
    for k, row in DEPLOY.items():
        if not k.startswith("b2t-"):
            continue
        pt = row["point"]["LTT max-rule (clean)"]
        axes[0].plot(pt["ewpm"], pt["wrong_commit"], "D", ms=4.0, color=C["crc"], mfc=C["crc"], mec="white", mew=0.6, zorder=6, alpha=0.95)
        if k.startswith("b2t-published"):
            if k.endswith("split A"):  # A and B lie on top of each other: one label for both
                pb = DEPLOY["b2t-published/split B"]["point"]["LTT max-rule (clean)"]
                axes[0].text(pt["ewpm"] - 0.35, 0.022, f"{pt['commit_rate']:.0%}, {pb['commit_rate']:.0%}", fontsize=5.6,
                             color=C["crc"], ha="right", va="center")
            continue
        dy = 0.0 if k.endswith("split A") else 0.012
        axes[0].text(pt["ewpm"] - 0.35, pt["wrong_commit"] + dy, f"{pt['commit_rate']:.0%}", fontsize=5.6, color=C["crc"],
                     ha="right", va="center")
    pt = DEPLOY["meg-async"]["point"]["LTT max-rule (clean)"]
    axes[2].plot([], [], "D", ms=4.2, color=C["crc"], label="trust, LTT max-rule (guaranteed)")
    axes[0].set_title("Intracortical (1 participant)")
    axes[0].set_xlim(2, 22)
    axes[1].set_title("sEMG (composed)")
    axes[1].set_xlim(1.6, 9.5)
    axes[2].set_title("MEG (negative control)")
    axes[2].set_xlim(2.0, 4.6)
    b = base_row("meg-async", "trust")
    axes[2].annotate("commits 0%", xy=(b["ewpm"], 0.0), xytext=(2.75, 0.2), fontsize=6.3,
                     ha="center", arrowprops=dict(arrowstyle="-", color="#888888", lw=0.6))
    for i, ax in enumerate(axes):
        ax.set_xlabel("eWPM (higher is better)")
        ax.axhline(ALPHA, color="#999999", lw=0.7, ls=":")
        panel_label(ax, "abc"[i])
    axes[0].text(2.3, ALPHA * 1.12, "α = 0.05", fontsize=6, color="#666666", va="bottom")
    axes[0].set_ylabel("wrong commits / all sentences\n(lower is better; √ scale)")
    axes[0].set_ylim(-0.012, 1.05)
    h, lab_ = axes[2].get_legend_handles_labels()
    fig.legend(h, lab_, loc="lower center", ncol=3, frameon=False, handlelength=1.4, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(w_pad=0.6, rect=(0, 0.13, 1, 1))
    save(fig, "fig1_teaser")


# ---------------------------------------------------------------- Fig: deployment across days (v4)
R4X = "experiments/2026-11-12-paper1-r4-analyses"


def fig_deploy() -> None:
    """v4: (a) forward chain V1, LTT max per test day with CP95; (b) per-day rates pooled over 50 random re-splits."""
    fc = load(f"{R4X}/forward-chain/results/forward_chain.json")["conditions"]
    pdy = load(f"{R4X}/per-day/results/per_day.json")["repeated"]
    fig, axes = plt.subplots(1, 2, figsize=(FULL, 2.4), sharey=True)
    sets = [("b2t-ours", "our decoder", C["trust"], -0.17, "o"), ("b2t-published", "published gate", C["pub"], 0.17, "s")]
    for cond, name, col, dx, m in sets:
        folds = fc[f"{cond}/guard"]["variants"]["V1 previous day"]["folds"]
        days = [f["test_day"] for f in folds]
        x = np.arange(len(days)) + dx
        for xi, fo in zip(x, folds):
            r = fo["rules"]["LTT max"]
            lo, hi = r["wrong_commit_cp95"]
            axes[0].plot([xi, xi], [lo, hi], color=col, lw=0.8, alpha=0.8)
            axes[0].plot(xi + 0.08, fo["rules"]["plug-in"]["wrong_commit"], "_", ms=4, color="#888888", mew=1.0)
        axes[0].plot(x, [fo["rules"]["LTT max"]["wrong_commit"] for fo in folds], m, ms=3.4, color=col, mfc=col, ls="none", label=name)
        axes[0].set_xticks(np.arange(len(days)))
        axes[0].set_xticklabels([str(d) for d in days], rotation=90, fontsize=6)
        rr = pdy[f"{cond}/R50"]["rules"]["LTT max"]
        dk = list(rr.keys())
        x2 = np.arange(len(dk)) + dx
        axes[1].vlines(x2, [rr[k]["p05"] for k in dk], [rr[k]["p95"] for k in dk], color=col, lw=0.8, alpha=0.8)
        axes[1].plot(x2, [rr[k]["pooled"] for k in dk], m, ms=3.4, color=col, mfc=col, ls="none", label=name)
        axes[1].set_xticks(np.arange(len(dk)))
        axes[1].set_xticklabels(dk, rotation=90, fontsize=6)
    for i, ax in enumerate(axes):
        ax.axhline(ALPHA, color="#999999", lw=0.7, ls=":")
        ax.set_xlabel("post-implant day")
        panel_label(ax, "ab"[i])
    axes[0].set_title("time order: calibrate on the previous day", loc="right")
    axes[0].plot([], [], "_", ms=5, color="#888888", mew=1.0, label="plug-in (no guarantee)")
    axes[1].set_title("random re-splits: per day, pooled over 50", loc="right")
    axes[0].set_ylabel("wrong-commit rate (LTT max rule)")
    axes[0].set_ylim(-0.005, 0.30)
    axes[0].legend(frameon=False, loc="upper right", fontsize=6.5)
    fig.tight_layout(w_pad=0.6)
    save(fig, "fig_deploy")


# ---------------------------------------------------------------- Fig: user-model sensitivity (v2)
def fig_user_model() -> None:
    cols = {"b2t-ours": C["trust"], "b2t-published": C["pub"], "emg-calib": C["crc"], "emg-xsession": C["old"],
            "emg-xsubject": C["aci"], "meg-async": "#000000"}
    mk = {"b2t-ours": "o", "b2t-published": "o", "emg-calib": "s", "emg-xsession": "s", "emg-xsubject": "s", "meg-async": "D"}
    panels = [("trust-always_commit", "trust − always commit\n(> 0: trust faster)"),
              ("trust-never_commit", "trust − always offer\n(> 0: trust faster)"),
              ("trust-gaze_lm", "trust − gaze + completion\n(> 0: trust faster)")]
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 2.45), sharey=True)
    nv = len(UM_VARIANTS)
    for ax, (dk, title) in zip(axes, panels):
        for ci_, (cond, cname) in enumerate(CONDS):
            for vi, (vk, _) in enumerate(UM_VARIANTS):
                v = UM[cond]["variants"][vk]
                pt = v["point"]
                a, bb = dk.split("-", 1)
                d = pt[a]["ewpm"] - pt[bb]["ewpm"]
                lo, hi = v["ci"]["diffs_ewpm"][dk]
                y = (nv - 1 - vi) - (ci_ - 2.5) * 0.12
                ax.plot([lo, hi], [y, y], color=cols[cond], lw=0.8, alpha=0.8)
                ax.plot(d, y, mk[cond], ms=3.0, color=cols[cond], mfc=cols[cond] if cond != "meg-async" else "white",
                        mew=0.8, label=cname if vi == 0 else None)
        ax.axvline(0, color="black", lw=0.6)
        for yy in range(nv - 1):
            ax.axhline(yy + 0.5, color="#E6E6E6", lw=0.5, zorder=0)
        ax.set_title(title)
        ax.set_xlabel("eWPM difference")
    axes[2].set_xscale("symlog", linthresh=1.0)
    axes[2].set_xlim(-5, 16)
    axes[2].set_xticks([-4, -1, 0, 1, 4, 15])
    axes[2].set_xticklabels(["−4", "−1", "0", "1", "4", "15"])
    axes[0].set_yticks(range(nv))
    axes[0].set_yticklabels([lab for _, lab in UM_VARIANTS][::-1], fontsize=6.5)
    axes[0].set_ylim(-0.6, nv - 0.4)
    for i, ax in enumerate(axes):
        panel_label(ax, "abc"[i])
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=6, frameon=False, handlelength=1.0, columnspacing=0.9,
               bbox_to_anchor=(0.5, -0.01), fontsize=6.3)
    fig.tight_layout(w_pad=0.5, rect=(0, 0.07, 1, 1))
    save(fig, "fig_user_model")


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
            ax.axhline(0.10, color="#CC0000", lw=0.7, ls="--")
            ax.text(0.69, 0.115, "β = 0.10", fontsize=6, color="#CC0000", ha="right", va="bottom")
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


# ---------------------------------------------------------------- Fig: null-input audit
def fig_null() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 2.0), gridspec_kw={"width_ratios": [4, 5, 5]})
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
    fig_deploy()
    fig_risk()
    fig_crc()
    fig_user_model()
    fig_null()
    fig_ece()
    # fig_ewpm() and fig_meg_cer() are no longer in the paper (v1): Table 4 and Table 3 carry their numbers.
    # fig_drift() was removed in v2 (its offline baseline reused fit data); the clean-drift table carries the numbers.
