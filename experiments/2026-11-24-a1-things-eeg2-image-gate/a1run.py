r"""A1 runner (P16-07, gap 207): THINGS-EEG2 zero-shot image identification with the trust gate (plan.md).

Our own code, Apache-2.0. Stages (``all`` runs them in order per subject; finished parts are skipped):

  convert     stream the pickled EEG (a1data.LazyUnpickler) -> float32 .npy in --out/sub-XX/      (CPU)
  s0          S0 session-reconstruction check on the test EEG (data only, no decoder)          (CPU)
  train       ATM-S re-implementation, 40 epochs, checkpoint every epoch, resume, val top-1    (GPU)
  scorecal    best-val epoch -> embeddings of val and cal units                                 (GPU / CPU)
  gate        temperature (val), precision LTT + conformal (cal), R2 cluster gates -> gate.json
              (also copied to results/gate_sub-XX.json; COMMIT IT before scoretest)
  scoretest   needs results/gate_sub-XX.json committed and on origin/main (plan stop rule);
              embeddings of test units, 80-trial means, nulls N1-N3, R1 session units
  evaluate    rules (i)-(iii), V1, V2, R1, R2 -> --out/sub-XX/eval.json
  summary     both subjects -> results/summary.json (aggregates only)

Run (repo root, GPU venv), after the GPU is free:
  C:\venvs\fidetype-rocm\Scripts\python.exe experiments\2026-11-24-a1-things-eeg2-image-gate\a1run.py all
A file ``pause`` or ``stop`` in --out stops after the current epoch (exit code 3). Exit code 4 = the gate files
wait for a commit + push. Derived outputs only go to --out (default C:/Users/zhang/bci-data/derived/a1-things-eeg2).
``--dry-run`` uses a few real trials, the CPU, 2 short epochs and never scores test units.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))

import a1data as D  # noqa: E402
import a1gate as G  # noqa: E402

RAW = Path(r"C:\Users\zhang\bci-data\raw\things-eeg2")
OUT = Path(r"C:\Users\zhang\bci-data\derived\a1-things-eeg2")
RESULTS = HERE / "results"
CFG = {"lr": 3e-4, "batch": 1024, "epochs": 40, "weight_decay": 0.01, "seed": 0, "w_img": 0.99}
LICENCE = {
    "eeg": "THINGS-EEG2 (Gifford et al. 2022), CC BY 4.0, OSF 3jk45; 250 Hz 63-ch re-preprocessing from HF "
           "LidongYang/EEG_Image_decode (CC BY 4.0), commit dbe34bb",
    "features": "CLIP ViT-H-14 features from the same HF dataset (CC BY 4.0)",
    "images": "THINGS images: research use only; not used, not copied",
    "code": "our own (Apache-2.0); model re-implements ATM-S (MIT, (c) 2023 DongyangLi)",
}


class Stop(Exception):
    pass


def log(out: Path, msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(out / "a1.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def sub_dir(out: Path, s: int) -> Path:
    d = out / f"sub-{s:02d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_json(p: Path, obj) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


# --- context -------------------------------------------------------------------------------------------------------

class Ctx:
    """Metadata, features, split and (memory-mapped) EEG of one subject."""

    def __init__(self, raw: Path, out: Path, s: int, dry: bool, eeg_dir: Path | None = None):
        self.raw, self.out, self.s, self.dry = raw, out, s, dry
        self.dir = sub_dir(out, s)
        self.eeg_dir = self.dir if eeg_dir is None else Path(eeg_dir) / f"sub-{s:02d}"
        meta = D.safe_load(raw / "osf" / "image_metadata.npy")
        self.train_concepts = list(meta["train_img_concepts"])
        self.test_concepts = list(meta["test_img_concepts"])
        self.split = D.make_split(self.train_concepts, self.test_concepts)
        self.img_tr, self.txt_tr = D.load_features(raw / "hf" / "ViT-H-14_features_train.pt")
        self.img_te, _ = D.load_features(raw / "hf" / "ViT-H-14_features_test.pt")
        self.cid = D.concept_ids(self.train_concepts)  # text feature row of each training image
        self.idx = {k: D.image_indices(self.train_concepts, getattr(self.split, k))
                    for k in ("val", "fit", "order", "certify")}
        if dry:  # a few real trials only
            self.idx = {k: v[: {"fit": 64, "val": 200, "order": 200, "certify": 200}[k]] for k, v in self.idx.items()}

    def eeg(self, part: str) -> np.ndarray:
        return np.load(self.eeg_dir / f"{part}.npy", mmap_mode="r", allow_pickle=False)


# --- stages --------------------------------------------------------------------------------------------------------

def st_convert(c: Ctx) -> None:
    for part, src, shape in (("test", "preprocessed_eeg_test.npy", D.TEST_SHAPE),
                             ("train", "preprocessed_eeg_training.npy", D.TRAIN_SHAPE)):
        if (c.eeg_dir / f"{part}_meta.json").exists():
            continue
        log(c.out, f"sub-{c.s:02d} convert {part}")
        meta = D.convert_eeg(c.raw / "hf" / f"sub-{c.s:02d}" / src, c.eeg_dir, part, shape)
        log(c.out, f"sub-{c.s:02d} {part}: shape {meta['shape']} from {meta['src_dtype']}, "
                   f"{len(meta['times'])} times {meta['times'][0]:.3f}..{meta['times'][-1]:.3f}")
    write_json(c.dir / "licence.json", LICENCE)


def st_s0(c: Ctx) -> dict:
    p = c.dir / "s0.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    r = D.s0_session_check(c.eeg("test"), max_images=20 if c.dry else None)
    write_json(p, r)
    log(c.out, f"sub-{c.s:02d} S0 {r}")
    return r


def _device(name: str):
    import torch

    # MIOpen's BatchNorm kernel does not compile on this ROCm build (miopenStatusUnknownError, run 2026-11-27);
    # the native PyTorch kernels compute the same model (project precedent: T12 train_decoder.py).
    torch.backends.cudnn.enabled = False
    return torch.device(name)


def embed(model, x: np.ndarray, subject: int, device, bs: int = 512) -> np.ndarray:
    import torch

    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(x), bs):
            xb = torch.from_numpy(np.ascontiguousarray(x[i:i + bs], dtype=np.float32)).to(device)
            sb = torch.full((len(xb),), subject, dtype=torch.long, device=device)
            out.append(model(xb, sb).float().cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, 1024), np.float32)


def val_units(c: Ctx) -> tuple[np.ndarray, np.ndarray]:
    """Val units and their per-unit galleries (true image in column 0)."""
    tr = c.eeg("train")
    vi = c.idx["val"]
    pool = D.image_indices(c.train_concepts, c.split.val)
    gal = D.make_galleries(vi, c.cid, pool, c.s)
    return D.train_units(tr, vi), gal


def st_train(c: Ctx, device_name: str, cfg: dict) -> None:
    import torch

    import a1model as M

    d = c.dir
    if (d / "train_done.json").exists():
        return
    device = _device(device_name)
    torch.manual_seed(cfg["seed"])
    model = M.ATMS().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    state = {"epoch": 0, "best_val": -1.0, "best_epoch": 0, "history": []}
    if (d / "latest.pt").exists():
        ck = torch.load(d / "latest.pt", map_location=device, weights_only=False)  # our own file
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        state = ck["state"]
        log(c.out, f"sub-{c.s:02d} resume after epoch {state['epoch']}")
    tr = c.eeg("train")
    fit = c.idx["fit"]
    x_fit = torch.from_numpy(np.ascontiguousarray(tr[fit], dtype=np.float32))  # [n, 4, 63, 250] in RAM
    img_t = torch.from_numpy(c.img_tr)
    txt_t = torch.from_numpy(c.txt_tr)
    vu, vgal = val_units(c)
    pairs = np.stack(np.meshgrid(np.arange(len(fit)), np.arange(4), indexing="ij"), -1).reshape(-1, 2)
    max_steps = 3 if c.dry else None
    t0 = time.time()
    while state["epoch"] < cfg["epochs"]:
        ep = state["epoch"] + 1
        model.train()
        order = np.random.default_rng([cfg["seed"], ep]).permutation(len(pairs))
        tot, nb = 0.0, 0
        for b in range(0, len(order), cfg["batch"]):
            pr = pairs[order[b:b + cfg["batch"]]]
            if len(pr) < 2:
                continue
            xb = x_fit[pr[:, 0], pr[:, 1]].to(device, non_blocking=True)
            gi = fit[pr[:, 0]]
            ib, tb = img_t[gi].to(device), txt_t[c.cid[gi]].to(device)
            sb = torch.full((len(xb),), c.s, dtype=torch.long, device=device)
            loss = M.atm_loss(model, model(xb, sb), ib, tb, cfg["w_img"])
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            tot += float(loss.detach())
            nb += 1
            if max_steps and nb >= max_steps:
                break
        emb = embed(model, vu, c.s, device)
        sim = G.cosine_per_unit(emb, c.img_tr, vgal)
        top1 = G.topk_acc(sim, np.zeros(len(sim), dtype=np.int64), 1)
        state["epoch"] = ep
        state["history"].append({"epoch": ep, "train_loss": tot / max(nb, 1), "val_top1": top1,
                                 "minutes": (time.time() - t0) / 60})
        if top1 > state["best_val"]:
            state["best_val"], state["best_epoch"] = top1, ep
            torch.save({"model": model.state_dict(), "epoch": ep}, d / "best.pt.tmp")
            Path(d / "best.pt.tmp").replace(d / "best.pt")
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "state": state}, d / "latest.pt.tmp")
        Path(d / "latest.pt.tmp").replace(d / "latest.pt")
        log(c.out, f"sub-{c.s:02d} epoch {ep} loss {tot / max(nb, 1):.4f} val_top1 {top1:.4f} "
                   f"best {state['best_val']:.4f}@{state['best_epoch']}")
        for f in ("pause", "stop"):
            if (c.out / f).exists():
                raise Stop(f)
    write_json(d / "train_done.json", {"best_epoch": state["best_epoch"], "best_val_top1": state["best_val"],
                                       "history": state["history"], "config": cfg})


def load_best(c: Ctx, device_name: str):
    import torch

    import a1model as M

    model = M.ATMS().to(_device(device_name))
    ck = torch.load(c.dir / "best.pt", map_location=device_name, weights_only=True)
    model.load_state_dict(ck["model"])
    return model


def st_scorecal(c: Ctx, device_name: str) -> None:
    p = c.dir / "scores_cal.npz"
    if p.exists():
        return
    model = load_best(c, device_name)
    dev = _device(device_name)
    tr = c.eeg("train")
    vu, vgal = val_units(c)
    out = {"val_sim": G.cosine_per_unit(embed(model, vu, c.s, dev), c.img_tr, vgal)}
    cal_pool = D.image_indices(c.train_concepts, c.split.cal)
    for k in ("order", "certify"):
        ii = c.idx[k]
        gal = D.make_galleries(ii, c.cid, cal_pool, c.s)
        out[f"{k}_sim"] = G.cosine_per_unit(embed(model, D.train_units(tr, ii), c.s, dev), c.img_tr, gal)
        out[f"{k}_img"] = ii
    np.savez(p, **out)
    log(c.out, f"sub-{c.s:02d} scorecal: " + ", ".join(f"{k} {v.shape}" for k, v in out.items()))


def concept_clusters(c: Ctx) -> tuple[np.ndarray, np.ndarray]:
    """R2: k-means cluster of every training concept (by image) and every test image."""
    _, txt_te = D.load_features(c.raw / "hf" / "ViT-H-14_features_test.pt")
    lab = G.kmeans(np.concatenate([c.txt_tr, txt_te]), k=8, seed=0)
    return lab[: len(c.txt_tr)][c.cid], lab[len(c.txt_tr):]


def st_gate(c: Ctx) -> dict:
    p = c.dir / "gate.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    sc = np.load(c.dir / "scores_cal.npz")
    zero = lambda a: np.zeros(len(a), dtype=np.int64)  # noqa: E731 (true image is column 0)
    T = G.fit_temperature(sc["val_sim"], zero(sc["val_sim"]))
    gate = G.fit_gate(sc["order_sim"], zero(sc["order_sim"]), sc["certify_sim"], zero(sc["certify_sim"]), T)
    cl_tr, _ = concept_clusters(c)
    r2 = {}
    for k in range(8):
        mo = cl_tr[sc["order_img"]] != k
        mc = cl_tr[sc["certify_img"]] != k
        gk = G.fit_gate(sc["order_sim"][mo], zero(sc["order_sim"][mo]), sc["certify_sim"][mc],
                        zero(sc["certify_sim"][mc]), T)
        r2[str(k)] = gk.to_dict()
    obj = {"subject": c.s, "dry_run": c.dry, "gate": gate.to_dict(), "r2_gates": r2,
           "best_epoch": json.loads((c.dir / "train_done.json").read_text(encoding="utf-8"))["best_epoch"]}
    write_json(p, obj)
    if not c.dry:
        RESULTS.mkdir(exist_ok=True)
        write_json(RESULTS / f"gate_sub-{c.s:02d}.json", obj)
    log(c.out, f"sub-{c.s:02d} gate: T {T:.4f} commit_p {gate.commit_p} conf_q {gate.conf_q:.4f}")
    return obj


def gate_committed(s: int) -> bool:
    """results/gate_sub-XX.json is committed, unchanged in the work tree, and on origin/main."""
    rel = f"experiments/{HERE.name}/results/gate_sub-{s:02d}.json"
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)  # noqa: E731
    if git("diff", "--quiet", "HEAD", "--", rel).returncode != 0:
        return False
    if not git("ls-files", "--error-unmatch", rel).stdout.strip():
        return False
    git("fetch", "-q", "origin", "main")
    return bool(git("log", "-1", "--format=%H", "origin/main", "--", rel).stdout.strip())


def st_scoretest(c: Ctx, device_name: str) -> None:
    p = c.dir / "scores_test.npz"
    if p.exists():
        return
    if c.dry:
        raise RuntimeError("dry run never scores test units")
    if not gate_committed(c.s):
        raise SystemExit(4)
    model = load_best(c, device_name)
    dev = _device(device_name)
    te = c.eeg("test")
    units, img = D.test_units(te)
    out = {"test_img": img, "test_sim": G.cosine_shared(embed(model, units, c.s, dev), c.img_te)}
    mean80 = np.asarray(te, dtype=np.float32).mean(axis=1)
    out["avg80_sim"] = G.cosine_shared(embed(model, mean80, c.s, dev), c.img_te)
    for k, v in G.make_nulls(units, c.s).items():
        out[f"{k}_sim"] = G.cosine_shared(embed(model, v, c.s, dev), c.img_te)
    for name, ses in (("early", (0, 1)), ("late", (2, 3))):
        u, im = D.session_units(te, ses)
        out[f"{name}_sim"] = G.cosine_shared(embed(model, u, c.s, dev), c.img_te)
        out[f"{name}_img"] = im
    np.savez(p, **out)
    log(c.out, f"sub-{c.s:02d} scoretest done")


def st_evaluate(c: Ctx) -> dict:
    sc = np.load(c.dir / "scores_test.npz")
    gobj = json.loads((c.dir / "gate.json").read_text(encoding="utf-8"))
    gate = G.Gate.from_dict(gobj["gate"])
    img = sc["test_img"]
    dec = gate.decide(sc["test_sim"])
    real = G.gate_metrics(dec, img, img)
    nulls, null_dec = {}, {}
    for k in ("N1", "N2", "N3"):
        null_dec[k] = gate.decide(sc[f"{k}_sim"])
        nulls[k] = G.gate_metrics(null_dec[k], None, img)
    sets = G.set_size_test(dec["set_size"], null_dec["N1"]["set_size"], img)
    avg80 = {"top1": G.topk_acc(sc["avg80_sim"], np.arange(200), 1), "top5": G.topk_acc(sc["avg80_sim"], np.arange(200), 5)}
    unit_acc = {"top1": G.topk_acc(sc["test_sim"], img, 1), "top5": G.topk_acc(sc["test_sim"], img, 5)}
    verdict = G.subject_verdict(avg80["top1"], real, nulls, sets)
    s0 = st_s0(c)
    r1 = None
    if s0["pass"]:
        e = G.gate_metrics(gate.decide(sc["early_sim"]), sc["early_img"], sc["early_img"])
        lt = G.gate_metrics(gate.decide(sc["late_sim"]), sc["late_img"], sc["late_img"])
        r1 = {"early": e, "late": lt, "pass": G.rule_drift(e, lt)}
    _, cl_te = concept_clusters(c)
    per = []
    for k, gd in gobj["r2_gates"].items():
        m = cl_te[img] == int(k)
        if m.any():
            per.append(G.gate_metrics(G.Gate.from_dict(gd).decide(sc["test_sim"][m]), img[m], img[m], n_boot=200))
    pooled = G.pooled_counts(per)
    r2 = {"pooled": pooled, "pass": G.rule_cluster(pooled), "per_cluster": per}
    cal = np.load(c.dir / "scores_cal.npz")
    z = lambda a: np.zeros(len(a), dtype=np.int64)  # noqa: E731
    g05 = G.fit_gate(cal["order_sim"], z(cal["order_sim"]), cal["certify_sim"], z(cal["certify_sim"]),
                     gate.temperature, alpha=0.05)
    alpha05 = G.gate_metrics(g05.decide(sc["test_sim"]), img, img)  # descriptive row (plan.md)
    res = {"subject": c.s, "real": real, "nulls": nulls, "sets": sets, "avg80": avg80, "unit_acc": unit_acc,
           "margin_mean": float(G.margin(sc["test_sim"]).mean()), "verdict": verdict, "S0": s0,
           "R1": r1 if r1 else "not run (session order unknown)", "R2": r2,
           "alpha_0.05_descriptive": {"commit_p": g05.commit_p, "real": alpha05}}
    write_json(c.dir / "eval.json", res)
    return res


def st_summary(out: Path, subjects) -> dict:
    per = {}
    for s in subjects:
        p = out / f"sub-{s:02d}" / "eval.json"
        if p.exists():
            e = json.loads(p.read_text(encoding="utf-8"))
            e["R2"].pop("per_cluster", None)
            per[f"sub-{s:02d}"] = e
    summ = {"outcome": G.overall_outcome({k: v["verdict"] for k, v in per.items()}), "subjects": per,
            "alpha": G.ALPHA, "delta": G.DELTA}
    RESULTS.mkdir(exist_ok=True)
    write_json(RESULTS / "summary.json", summ)
    return summ


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["convert", "s0", "train", "scorecal", "gate", "scoretest", "evaluate",
                                      "summary", "all"])
    ap.add_argument("--subjects", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--raw", type=Path, default=RAW)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--eeg-dir", type=Path, default=None, help="read converted EEG from here (default: --out)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--epochs", type=int, default=None, help="dry run only")
    a = ap.parse_args(argv)
    cfg = dict(CFG)
    if a.dry_run:
        cfg["epochs"] = a.epochs or 2
        cfg["batch"] = 32
    elif a.epochs is not None:
        ap.error("--epochs is for --dry-run only (plan: 40 epochs)")
    a.out.mkdir(parents=True, exist_ok=True)
    order = ["convert", "s0", "train", "scorecal", "gate", "scoretest", "evaluate"]
    stages = order if a.stage == "all" else ([] if a.stage == "summary" else [a.stage])
    if a.dry_run:
        stages = [s for s in stages if s not in ("scoretest", "evaluate")]
    try:
        for s in a.subjects:
            c = Ctx(a.raw, a.out, s, a.dry_run, a.eeg_dir)
            for st in stages:
                if st == "convert":
                    st_convert(c)
                elif st == "s0":
                    st_s0(c)
                elif st == "train":
                    st_train(c, a.device, cfg)
                elif st == "scorecal":
                    st_scorecal(c, a.device)
                elif st == "gate":
                    st_gate(c)
                elif st == "scoretest":
                    st_scoretest(c, a.device)
                elif st == "evaluate":
                    st_evaluate(c)
        if a.stage in ("all", "summary") and not a.dry_run:
            st_summary(a.out, a.subjects)
    except Stop as e:
        log(a.out, f"stopped by {e} file")
        return 3
    return 0


def _run_and_exit() -> None:
    """Log the exit code to a1.log, then end with TerminateProcess (ROCm/Windows exit hang, train.hard_exit)."""
    from fidetype.decoders.train import hard_exit

    try:
        code = main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    except BaseException:
        import traceback

        traceback.print_exc()
        code = 1
    if "--dry-run" not in sys.argv:
        OUT.mkdir(parents=True, exist_ok=True)
        log(OUT, f"exit code {code}")
    hard_exit(code)


if __name__ == "__main__":
    _run_and_exit()
