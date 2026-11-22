"""P4-22 run: the text-nbest readers on the real decoder output files of convert.py (checks C1-C5 of plan.md).

Reads ``<bci-data>/derived/p4-22`` (written by convert.py) and the original sources. Writes the
streams to ``<bci-data>/derived/p4-22/streams`` and aggregate results (counts, hashes, checks; no
text) to ``results/results.json`` in this folder.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-22-p4-22-nbest-readers/run.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

import convert as C  # noqa: E402
from fidetype.adapters import text_nbest as TN  # noqa: E402

KEYS = ("text", "score", "logp_acoustic", "logp_lm", "char_confidences")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def same_utts(a: list, b: list) -> bool:
    return [(u.id, u.nbest, u.t_start, u.t_end, u.is_final) for u in a] == \
           [(u.id, u.nbest, u.t_start, u.t_end, u.is_final) for u in b]


def compare(utts: list, src: list[tuple[str, list[dict]]], keys: tuple[str, ...]) -> dict:
    """src: (id, items) per utterance. Count utterances whose id and every item key match exactly."""
    ok_id = ok_all = 0
    n_items = sum(len(u.nbest) for u in utts)
    for u, (sid, items) in zip(utts, src):
        ok_id += u.id == sid
        good = len(u.nbest) == len(items)
        for it, s in zip(u.nbest, items):
            for k in keys:
                if k in s or k in ("text", "score"):
                    sv = s.get(k, 0.0)
                    good &= (it.get(k) == (float(sv) if k == "score" else sv))
        ok_all += good
    return {"utterances": len(utts), "source_utterances": len(src), "items": n_items,
            "source_items": sum(len(i) for _, i in src), "id_order_equal": ok_id, "exact_equal": ok_all}


def main() -> None:
    out = C.OUT
    sdir = out / "streams"
    sdir.mkdir(parents=True, exist_ok=True)
    r1 = [(i, [{"text": t}]) for i, t in C.r1_rows()]
    recs = C.r2_records()
    r2 = [(r["id"], r["nbest"]) for r in recs]
    r2_text_score = [(i, [{"text": it["text"], "score": it["score"]} for it in items]) for i, items in r2]
    head = json.loads((C.HYP / "trial-0105.jsonl").read_text(encoding="utf-8").splitlines()[0])["meta"]

    dec_r1 = TN.TextDecoderInfo(modality="intracortical", name="card2024-online-rnn", version="t15-copytask-online",
                                lm_name="unspecified", extra={"data.derived": True})
    dec_r2 = TN.TextDecoderInfo(modality="intracortical", name=head["decoder.name"] + "+m4-06-beam",
                                version=head["decoder.version"], causal=bool(head["decoder.causal"]),
                                lm_name=head["lm.name"], extra={"data.derived": True})
    jobs = [
        ("r1-online-1best.csv", TN.read_csv, {}, r1, ("text", "score"), dec_r1),
        ("r1-online-1best.jsonl", TN.read_jsonl, {}, r1, ("text", "score"), dec_r1),
        ("r2-ours-nbest.csv", TN.read_csv, {"score_col": "score"}, r2_text_score, ("text", "score"), dec_r2),
        ("r2-ours-nbest.jsonl", TN.read_jsonl, {}, r2, KEYS, dec_r2),
    ]
    res: dict = {"inputs": {}, "checks": {}}
    for name, reader, kw, src, keys, dec in jobs:
        p = out / name
        utts = reader(p, **kw)
        cmp = compare(utts, src, keys)
        cmp["read_nbest_same"] = same_utts(utts, TN.read_nbest(p, **kw))
        sp = sdir / (p.stem + "." + p.suffix.lstrip(".") + ".nts.jsonl")
        TN.write_stream(utts, dec, sp, score_semantics="none")
        fails = TN.check_stream_file(sp)
        cmp["stream_check_failures"] = len(fails)
        cmp["stream_check_failure_ids"] = sorted({f.split(":")[0] for f in fails})
        if name == "r2-ours-nbest.jsonl":
            evs = [json.loads(line) for line in sp.read_text(encoding="utf-8").splitlines()]
            hy = [e for e in evs if e["type"] == "hypothesis"]
            cmp["stream_nbest_equal_source"] = sum(e["nbest"] == items for e, (_, items) in zip(hy, r2))
            cmp["stream_hypotheses"] = len(hy)
        texts = [it["text"] for _, items in src for it in items]
        res["inputs"][name] = {"bytes": p.stat().st_size, "sha256": sha(p), "stream_sha256": sha(sp),
                               "texts_with_comma": sum("," in t for t in texts),
                               "texts_with_quote": sum('"' in t for t in texts),
                               "texts_with_edge_space": sum(t != t.strip() for t in texts),
                               "empty_texts": sum(t == "" for t in texts)}
        res["checks"][name] = cmp
    exp = {"r1-online-1best.csv": (1718, 1718), "r1-online-1best.jsonl": (1718, 1718),
           "r2-ours-nbest.csv": (816, 8158), "r2-ours-nbest.jsonl": (816, 8158)}
    verdict = {}
    for name, c in res["checks"].items():
        nu, ni = exp[name]
        verdict[name] = {
            "C1": c["utterances"] == nu and c["items"] == ni,
            "C2": c["id_order_equal"] == nu and c["exact_equal"] == nu,
            "C3": c["read_nbest_same"],
            "C4": c["stream_check_failures"] == 0,
        }
        if "stream_nbest_equal_source" in c:
            verdict[name]["C5"] = c["stream_nbest_equal_source"] == nu == c["stream_hypotheses"]
    res["verdict"] = verdict
    res["all_pass"] = all(all(v.values()) for v in verdict.values())
    res["note"] = "aggregate counts and hashes only; the derived files and texts stay outside the repo"
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "results.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
