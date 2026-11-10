"""Run the M2-14 OFFER_WORDS real-MEG harness (part_real) on the M1-15 r1 streams.

CPU only, about 4 min. Output: results/ewpm/real.json. Run with the repo .venv:
    .venv/Scripts/python.exe experiments/2026-11-09-m1-15-sentence-context/ewpm_check.py
"""
import importlib.util, json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
spec = importlib.util.spec_from_file_location("m2ow", REPO / "experiments/2026-11-08-m2-offer-words/run.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from fidetype.streams.spec import NeuralTextStream
ROOT = Path("C:/Users/zhang/bci-data/streams/m1-15-sentence-context-r1")
m.OUT = Path(__file__).resolve().parent / "results" / "ewpm"; m.OUT.mkdir(parents=True, exist_ok=True)
def load_split(split):
    rows = [json.loads(x) for x in (ROOT / split / "labels.jsonl").read_text(encoding="utf-8").splitlines() if x]
    return [(NeuralTextStream.from_npz(ROOT / split / r["file"]), r) for r in rows]
m.load_split = load_split
res = m.part_real(quick=False)
print(json.dumps({k: {kk: v.get(kk) for kk in ("ewpm", "wrong_commit_rate", "silent_error_rate", "cer", "wer", "system_word_accuracy", "rate_commit", "rate_offer")} for k, v in res["policies"].items()}, indent=1))
print("diffs", json.dumps({k: v for k, v in res["bootstrap_sentences"].get("diffs", {}).items() if k.endswith(":ewpm")}, indent=1, default=str))
print("seconds", res.get("seconds"))
