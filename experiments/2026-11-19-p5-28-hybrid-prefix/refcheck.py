"""P5-28 post-hoc reference check 1 (after the run): the end-only hybrid (lam_mid = inf, lam_end = 0.94) vs the
P5-27 single-arm decisions, comparing commit / text / complete. run.py compared the action labels, and the single
arm labels a non-commit "offer" while the hybrid labels it "no-commit"; so run.py reported 465/701. Read only."""
import json, sys, math, pickle, collections
sys.path.insert(0, r"C:\Users\zhang\OneDrive\Documents\GitHub\stealth-project\src")
import fidetype.trust as ft
from fidetype.trust import hybrid_commit as H
from fidetype.trust.commit_score import LearnedCommitScore
D=r"C:\Users\zhang\bci-data\derived\p5-27"
E=r"C:\Users\zhang\OneDrive\Documents\GitHub\stealth-project\experiments\2026-11-18-p5-27-streaming-prefix\results"
single=json.load(open(D+r"\decisions-single.json"))
print(collections.Counter(r["action"] for r in single))
base=ft.load(E+r"\guard-p5-27-base.json", decode_fn=lambda lp: [])
mid=LearnedCommitScore.from_dict(json.load(open(E+r"\guard-p5-27-stream.json"))["score"])
views=[]
for j in range(15):
    views+=pickle.load(open(D+rf"\views\eval-{j:03d}.pkl","rb"))
one=H.HybridPrefixGuard(base, mid, 6, math.inf, 0.94)
n=same=0
for v,s in zip(views,single):
    r=one.decide_views(v)
    a=(r.n_commits>0, r.text, r.complete)
    b=(s["action"]=="commit", s["text"] if s["action"]=="commit" else None, s["complete"] if s["action"]=="commit" else None)
    same+= a==b
print("commit/text/complete equal:", same, len(single))
