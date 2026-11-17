"""F2 reruns (plan: plan.md): P15-05 and P15-06 on the M4-13 T15 decoder, and the pre-registered P15-06 variant
"V-single" (one LTT test set with a fixed order) on M4-13 T15 and on T12 v2. CPU only. Our own code.

The method code is imported, not changed: experiments/2026-11-16-f2-e3-llm-grounding/run.py (P15-05) and
experiments/2026-11-16-p15-06-halluc-bound/run.py (P15-06). This file only points them at new inputs and new
output folders, and adds the variant (``<arm>@single``).

    run.py p15-05            P15-05 prep + 8 arms on M4-13 (val_select -> val_eval)
    run.py p15-06            P15-06 primary arms + secondary arms + V-single arms on M4-13 (P15-05 outputs above)
    run.py p15-06-t12        V-single arms on T12 v2 (P15-05 / P15-06 T12 caches, read only; copies in our folder)

Dry run (plumbing only): TRUST_RERUN_DRY=1 TRUST_RERUN_SOURCE=m4-12 [TRUST_RERUN_STUB_LLM=1] run.py ...
Per-trial outputs and caches: C:/Users/zhang/bci-data/derived/f2-reruns-m4-13/ only. Repo: aggregates only.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
import zlib
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "2026-11-17-trust-reruns-m4-13"))
import common as K  # noqa: E402

DRY = K.is_dry()
SRC_NAME = K.source_name()
STUB = os.environ.get("TRUST_RERUN_STUB_LLM", "0") == "1"
if not DRY:
    assert SRC_NAME == "m4-13" and not STUB, "a real run uses the M4-13 outputs and the real LLM"
OUT = HERE / ("results/dryrun-" + SRC_NAME if DRY else "results")
OUT.mkdir(parents=True, exist_ok=True)
DER = K.DER
VARIANT = "single"
DRY_ARMS = ["A0_ngram", "B1_rescore_G"]


class StubLLM:
    """Dry runs only: a deterministic fake LLM (no model load; keeps the dry run under the RAM limit)."""

    def score(self, texts):
        return [-2.5 * max(1, len(t.split())) - (zlib.crc32(t.encode()) % 100) / 50.0 for t in texts]

    def rewrite(self, nbest_texts, constrained=True):
        return nbest_texts[0] if nbest_texts else ""


# ---------------------------------------------------------------------------
# P15-05 on M4-13
# ---------------------------------------------------------------------------


def run_p15_05() -> None:
    F = K.load_module("f2e3_run", REPO / "experiments/2026-11-16-f2-e3-llm-grounding/run.py")
    own = K.own("p15-05", DRY)
    F.OWN_ROOT = own
    F.OUT = OUT
    F.LOGF = OUT / "run-p15-05.log"
    seed_cache = DER / "f2-e3-llm-grounding" / "llm-cache.sqlite"  # text -> LLM score / rewrite (same model, seed)
    if not STUB and not (own / "llm-cache.sqlite").exists() and seed_cache.exists():
        shutil.copy2(seed_cache, own / "llm-cache.sqlite")  # the P15-05 cache stays untouched

    def data_t15():
        cal, held = K.load_t15(SRC_NAME, norm_text=True)
        dec, _ = K.word_decoder()
        return cal, held, dec

    F.data_t15 = data_t15
    if STUB:
        from fidetype.lm.llm import CachedRewriter, CachedScorer

        def make_llm():
            return (CachedScorer(StubLLM(), F.DiskDict(F.OWN / "llm-cache.sqlite", "scores")),
                    CachedRewriter(StubLLM(), F.DiskDict(F.OWN / "llm-cache.sqlite", "rewrites")))

        F.make_llm = make_llm
    if DRY:
        F.NULL_TRIALS = 20
        os.environ.setdefault("F2E3_ARMS", ",".join(DRY_ARMS))
    os.environ["F2E3_LIMIT"] = "0"
    sys.argv = ["run.py", "t15", "prep", "arms"]
    F.log(f"P15-05 rerun: source {SRC_NAME}, dry {DRY}, stub LLM {STUB}, provenance {json.dumps(K.provenance(SRC_NAME))}")
    F.main()


# ---------------------------------------------------------------------------
# P15-06 on M4-13 (and T12) with the V-single variant
# ---------------------------------------------------------------------------


def variant_guard(H6, guard, grounding):
    """V-single (pre-registered, plan.md): the joint LTT with NO ordering split. The configurations are tested in a
    fixed, data-independent order (``halluc_bound._strictness``: higher commit_p first, then smaller tau_commit, then
    smaller tau_word) on ALL non-fit items (policy-grid + LTT items). Selection rule: fewest_halluc (primary).
    The fit part, the base guard, the grid, alpha, alpha_h and delta_h are those of the primary run."""
    from fidetype.trust import halluc_bound as H
    from fidetype.trust.dropin import TrustGuard

    items = guard.halluc_items
    pool = list(items["order"]) + list(items["test"])
    h = guard.sheet.halluc
    g = H6.CFG["halluc"]
    configs = H.grid(*([math.inf if v == "inf" else v for v in g["grid"][k]] for k in ("commit_p", "tau_commit", "tau_word")))
    if grounding is None:
        configs = [c for c in configs if math.isinf(c.gate.tau_commit) and math.isinf(c.gate.tau_word)]
    c0 = H._fj(h["base_commit_p"])
    res = H.joint_ltt([], pool, configs, alpha=float(guard.alpha), alpha_h=float(h["alpha_h"]),
                      delta=float(h["delta_h"]), min_commit_p=c0, select="fewest_halluc")
    sel = res.selected if res.selected is not None else H.Config(math.inf, H.HallucGate())
    info = dict(h)
    info.update({k: v for k, v in res.to_dict().items() if k not in ("alpha", "alpha_h", "delta")})
    info["selected"] = sel.to_dict()
    info["select"] = "fewest_halluc"
    info["variant"] = ("V-single: no ordering split; fixed order = halluc_bound._strictness; test = all "
                       f"{len(pool)} non-fit items (primary: {len(items['order'])} order + {len(items['test'])} test)")
    info["primary"] = {"selected": h.get("selected"), "feasible": h.get("feasible"), "n_test": h.get("n_test"),
                       "config_id": guard.config_id}
    recipe = dict(guard.config.recipe)
    recipe["halluc_bound"] = {**recipe.get("halluc_bound", {}), "selected": info["selected"], "variant": info["variant"]}
    final = replace(guard.config.with_policy(commit_p=sel.commit_p), recipe=recipe)
    gate = None if sel.gate.is_off or grounding is None else sel.gate
    new = TrustGuard(final, guard._codec, None, guard._user_decode, guard.audit_text, halluc_gate=gate,
                     grounding=grounding if gate is not None else None)
    warnings = list(guard.sheet.warnings)
    if res.selected is None:
        warnings.append("hallucination bound (V-single): no configuration certified, so the guard never commits.")
    new.sheet = replace(guard.sheet, config_id=final.config_id, commit_threshold=float(sel.commit_p), halluc=info,
                        warnings=tuple(warnings))
    new.halluc_items = items
    return new


def patch_p15_06(H6, set_name: str, src: Path, own: Path, p5res: Path, log_name: str) -> None:
    def set_data(name: str) -> None:
        H6.SET = set_name
        H6.SRC, H6.OWN = src, own
        H6.LOGF = OUT / log_name
        H6.P5RES = json.loads(p5res.read_text(encoding="utf-8"))

    H6.set_data = set_data
    H6.OUT = OUT
    orig = H6.calibrate_arm

    def calibrate_arm(pipe, arm_name, arm, cal, explore=False, select=None):
        if select != VARIANT:
            return orig(pipe, arm_name, arm, cal, explore=explore, select=select)
        guard, sec = orig(pipe, arm_name, arm, cal, explore=explore, select="fewest_halluc")
        return variant_guard(H6, guard, H6.make_grounding(pipe)), sec

    H6.calibrate_arm = calibrate_arm
    if STUB:
        H6.LazyLLM = StubLLM
        StubLLM.loaded = False


def run_p15_06() -> None:
    H6 = K.load_module("p1506_run", REPO / "experiments/2026-11-16-p15-06-halluc-bound/run.py")
    src, own = K.own("p15-05", DRY), K.own("p15-06", DRY)
    p5res = OUT / "results-t15.json"  # written by run_p15_05 (F.OUT = OUT)
    assert p5res.exists(), "run p15-05 first"
    patch_p15_06(H6, "t15", src, own, p5res, "run-p15-06.log")

    def data_t15():
        cal, held = K.load_t15(SRC_NAME, norm_text=True)
        dec, _ = K.word_decoder()
        return cal, held, dec

    H6.data_t15 = data_t15
    H6.CFG["p15_05_results"] = str(p5res)
    arms = (H6.CFG["arms_primary"] + H6.CFG["arms_secondary"]
            + [f"{a}@{VARIANT}" for a in H6.CFG["arms_primary"]])
    if DRY:
        arms = [a for a in arms if a.split("@")[0] in DRY_ARMS]
        H6.P5["null_trials"] = 20
    _main_p15_06(H6, "t15", arms, "results-p15-06.json")


def run_p15_06_t12() -> None:
    """V-single on T12 v2 (the decoder P15-06 T12 could not certify). Inputs: P15-05 T12 caches (read only)."""
    H6 = K.load_module("p1506_run", REPO / "experiments/2026-11-16-p15-06-halluc-bound/run.py")
    src = DER / "f2-e3-llm-grounding" / "t12"  # READ ONLY
    own = K.own("p15-06-t12", DRY)
    for f in ("llm-cache.sqlite", "base-nbest-extra.pkl"):  # copies of the P15-06 T12 caches (results do not change)
        s = DER / "p15-06-halluc-bound" / "t12" / f
        if s.exists() and not (own / f).exists() and not STUB:
            shutil.copy2(s, own / f)
    p5res = REPO / "experiments/2026-11-16-f2-e3-llm-grounding/results/results-t12.json"
    patch_p15_06(H6, "t12", src, own, p5res, "run-p15-06-t12.log")
    if DRY:
        orig = H6.data_t12
        nc, nh = K.dry_limits()

        def data_t12():
            cal, held, dec = orig()
            return tuple(v[:nc] for v in cal), tuple(v[:nh] for v in held), dec

        H6.data_t12 = data_t12
        H6.P5["null_trials"] = 20
        orig_nb = H6.Pipeline.base_nbest

        def base_nbest(self, x):
            # dry run only: a cache miss gives an empty n-best (no 3.5 GB T12 decoder load; the RAM limit)
            k = H6.xkey(x)
            if k not in self.base and k not in self.extra:
                return []
            return orig_nb(self, x)

        H6.Pipeline.base_nbest = base_nbest
    arms = [f"{a}@{VARIANT}" for a in H6.CFG["arms_primary"]]
    if DRY:
        arms = [a for a in arms if a.split("@")[0] in DRY_ARMS]
    _main_p15_06(H6, "t12", arms, "results-p15-06-t12.json")


def _main_p15_06(H6, set_name: str, arms: list[str], out_name: str) -> None:
    """H6.main with our result file name and arm list (same steps: caches, data, pipeline, run_arm per arm)."""
    H6.set_data(set_name)
    db = H6.OWN / "llm-cache.sqlite"
    if not db.exists():
        shutil.copy2(H6.SRC / "llm-cache.sqlite", db)  # the source cache stays untouched
    llm = H6.LazyLLM()
    sc = H6.CachedScorer(llm, H6.DiskDict(db, "scores"))
    rw = H6.CachedRewriter(llm, H6.DiskDict(db, "rewrites"))
    H6.log(f"start {set_name} {arms} (fidetype {H6.FT_VERSION}); source {SRC_NAME}, dry {DRY}, stub {STUB}")
    cal, held, dec = {"t15": H6.data_t15, "t12": H6.data_t12}[set_name]()
    H6.log(f"{set_name} data: {len(cal[0])} calibration, {len(held[0])} held-out trials")
    pipe = H6.Pipeline(dec, sc, rw)
    path = OUT / out_name
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr.update(fidetype_version=H6.FT_VERSION, config=H6.CFG, dry_run=DRY, source=SRC_NAME)
    if set_name == "t15":
        allr["provenance"] = K.provenance(SRC_NAME)
    allr.setdefault("arms", {})
    for a in arms:
        if a in allr["arms"]:
            H6.log(f"{a}: done before, skip")
            continue
        H6.log(f"{a}: start")
        row = H6.run_arm(pipe, a, cal, held)
        allr["arms"][a] = row
        path.write_text(json.dumps(allr, indent=1, default=str), encoding="utf-8")
        keys = ("status", "wer", "n_commit", "n_wrong_commit", "fluent_wrong_commits", "halluc_gate_blocked",
                "controls_held_out", "seconds")
        H6.log(f"{a}: done {json.dumps({k: row.get(k) for k in keys}, default=str)}")
    H6.log(f"all done; decoder loaded {getattr(dec, 'loaded', None)}, LLM loaded {getattr(llm, 'loaded', None)}")


def main() -> None:
    what = sys.argv[1]
    {"p15-05": run_p15_05, "p15-06": run_p15_06, "p15-06-t12": run_p15_06_t12}[what]()


if __name__ == "__main__":
    main()
