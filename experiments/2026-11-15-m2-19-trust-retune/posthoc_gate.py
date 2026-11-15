"""M2-19 POST HOC (not in plan.md): the re-tuned dedicated_0 LTT config plus the M2-18 commit gate
(min_chars 1, min_words 0, max_guard_risk 1.0) on val_eval (streaming frames route + batch) and on the
uniform / frame-shuffled controls (same 300-trial draw as run.py controls). A gate only removes commits,
so the LTT guarantee still holds. Writes results/posthoc-gate.json (aggregates only)."""
import json
import sys
from pathlib import Path

import numpy as np

sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as R  # noqa: E402

ctx = R.Ctx()
items, _ = ctx.items("dedicated_0", "val_eval")
base = R.FrozenTrustConfig.load(R.cfg_path("dedicated_0", "ltt"))
fz = base.with_commit_gate(1, 0, 1.0)
out = {"base_config_id": base.config_id, "gated_config_id": fz.config_id, "commit_gate": fz.commit_gate}
r, _ = R.evaluate(ctx, fz, items)
out["val_eval"] = r
rng = np.random.default_rng(R.SEED)
idx = sorted(rng.choice(len(items), 300, replace=False).tolist())
sub = [items[i] for i in idx]
variants = {"real": [it.stream(0) for it in sub],
            "frame_shuffled": [R.shuffle_stream(it.stream(0), rng) for it in sub],
            "uniform": [R.uniform_stream(it.stream(0), rng, 0.05) for it in sub]}
out["controls"] = {}
for name, streams in variants.items():
    for tag, cfg in (("base", base), ("gated", fz)):
        recs = ctx.pipe_from(cfg).run_items([R.Item(s, it.text, stream_text=it.stream_text) for s, it in zip(streams, sub)])
        com = [x for x in recs if x.actions[-1:] == ["COMMIT"]]
        out["controls"][f"{name}/{tag}"] = {"n": len(recs), "n_commit": len(com),
                                            "n_commit_empty": sum((x.committed_text or "").strip() == "" for x in com),
                                            "commit_cp95_upper": R.cp(len(com), len(recs))[1]}
        R.log(f"posthoc gate controls {name}/{tag}: commits {len(com)}/300")
R.log(f"posthoc gate val_eval: commit {r['n_commit']} wrong {r['n_wrong_commit']} eWPM {r['ewpm']:.2f} stream==batch {r['stream_equals_batch']}")
ctx.save()
R.T.dump(out, R.OUT / "posthoc-gate.json")
