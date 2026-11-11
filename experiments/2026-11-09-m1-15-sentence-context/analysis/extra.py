# M1-15 full-r1 / r3 leakage + like-for-like analysis (2026-11-10). CPU only. Run in order: leak.py, analyse.py, extra.py (repo .venv).
from pathlib import Path as _P; _OUT = _P(__file__).resolve().parent
import json,sys,glob
import numpy as np
from collections import Counter,defaultdict
sys.path.insert(0,"C:/Users/zhang/OneDrive/Documents/GitHub/stealth-project/src")
from fidetype.streams.vocab import normalize_text
from fidetype.eval.metrics import cer
A=json.load(open(_OUT / "analysis.json",encoding="utf-8"))
close={r["sentence"] for r in A["per_test_sentence_full_r1"] if r["cer_nearest_train_vs_target"]<=0.25}
S="C:/Users/zhang/bci-data/streams/"
res={}
for run in ["full-r1","r2","r3"]:
  for head in ["final","conv"]:
    for dec in ["greedy","beam_lm"]:
      p=S+f"m1-15-sentence-context-{run}{'_head-conv' if head=='conv' else ''}/per_sentence_{dec}_test.jsonl"
      rows=[json.loads(x) for x in open(p,encoding="utf-8") if x.strip()]
      c=[r["cer_target"] for r in rows if normalize_text(r["target_text"]) in close]; f=[r["cer_target"] for r in rows if normalize_text(r["target_text"]) not in close]
      res[f"{run}/{head}/{dec}"]=dict(close=float(np.mean(c)),far=float(np.mean(f)),gap=float(np.mean(f)-np.mean(c)),n_close=len(c),n_far=len(f))
      print(run,head,dec,res[f"{run}/{head}/{dec}"])
# fair constant-sentence baseline: pick on train instances (leave-own-sentence-out), score on test
train_inst=[];val_inst=[]
for fn in glob.glob("C:/Users/zhang/bci-data/cache/spanishbcbl/v1/S*/*.json"):
    for s in json.load(open(fn,encoding="utf-8"))["segments"]:
        if s.get("is_training"): continue
        t=normalize_text(s["target_text"])
        if s["split"]=="train": train_inst.append(t)
        elif s["split"]=="val": val_inst.append(t)
cnt=Counter(train_inst); uniq=list(cnt)
def score(c,pool): 
    tot=sum(n*cer(t,c) for t,n in pool.items() if t!=c); N=sum(n for t,n in pool.items() if t!=c); return tot/N
best=min(uniq,key=lambda c: score(c,cnt))
g=[json.loads(x) for x in open(S+"m1-15-sentence-context-full-r1/per_sentence_greedy_test.jsonl",encoding="utf-8") if x.strip()]
tests=[normalize_text(r["target_text"]) for r in g]
res["constant_sentence_picked_on_train"]=dict(sentence=best,train_cer=score(best,cnt),test_cer=float(np.mean([cer(t,best) for t in tests])))
print(res["constant_sentence_picked_on_train"])
# shuffled control: share of derangement partners with same text (full-r1 test order = labels order)
lab=[json.loads(x) for x in open(S+"m1-15-sentence-context-full-r1/test/labels.jsonl",encoding="utf-8") if x.strip()]
n=len(lab); perm=np.random.default_rng(0).permutation(n); perm=np.where(perm==np.arange(n),(np.arange(n)+1)%n,perm)
same=sum(normalize_text(lab[i]["target_text"])==normalize_text(lab[perm[i]]["target_text"]) for i in range(n))
res["shuffled_same_text_partners_full_r1_test"]=[int(same),n]
print("shuffled partners with same text (assumes dataset order == labels order):",same,n)
A["near_variant_by_run"]=res
json.dump(A,open(_OUT / "analysis.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
