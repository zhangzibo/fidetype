# M1-15 full-r1 / r3 leakage + like-for-like analysis (2026-11-10). CPU only. Run in order: leak.py, analyse.py, extra.py (repo .venv).
from pathlib import Path as _P; _OUT = _P(__file__).resolve().parent
import json,sys,difflib
import numpy as np
from collections import defaultdict,Counter
sys.path.insert(0,"C:/Users/zhang/OneDrive/Documents/GitHub/stealth-project/src")
from fidetype.streams.vocab import normalize_text
from fidetype.eval.metrics import cer
S="C:/Users/zhang/bci-data/streams/"
def load(run,head,dec,sp):
    p=S+f"m1-15-sentence-context-{run}{'_head-conv' if head=='conv' else ''}/per_sentence_{dec}_{sp}.jsonl"
    return {(r["file"]):r for r in map(json.loads,open(p,encoding="utf-8")) if r}
out={}
def boot(diff,n=10000,seed=0):
    rng=np.random.default_rng(seed); d=np.asarray(diff); idx=rng.integers(0,len(d),(n,len(d)))
    m=d[idx].mean(1); return float(d.mean()),float(np.percentile(m,2.5)),float(np.percentile(m,97.5))
def summ(rows):
    c=[r["cer_target"] for r in rows]; byp=defaultdict(list)
    for r in rows: byp[r["participant"]].append(r["cer_target"])
    return dict(n=len(c),sent=float(np.mean(c)),part=float(np.mean([np.mean(v) for v in byp.values()])))
# 1 like-for-like
print("== like-for-like on r2 test/val instances")
ll={}
for sp in ["test","val"]:
  for head in ["final","conv"]:
    for dec in ["greedy","beam_lm"]:
        r2=load("r2",head,dec,sp); f1=load("full-r1",head,dec,sp); r3=load("r3",head,dec,sp)
        keys=sorted(r2); missing=[k for k in keys if k not in f1]
        assert not missing, missing[:5]
        assert all(r2[k]["target_text"]==f1[k]["target_text"] for k in keys)
        a=summ([r2[k] for k in keys]); b=summ([f1[k] for k in keys]); c=summ([r3[k] for k in keys])
        rest=summ([f1[k] for k in f1 if k not in r2])
        d=boot([f1[k]["cer_target"]-r2[k]["cer_target"] for k in keys])
        d3=boot([r3[k]["cer_target"]-r2[k]["cer_target"] for k in keys])
        ll[f"{sp}/{head}/{dec}"]=dict(r2=a,full_r1_on_r2=b,full_r1_other=rest,r3=c,diff_full_minus_r2=d,diff_r3_minus_r2=d3)
        print(sp,head,dec,"r2",a,"| full-r1 same inst",b,"| full-r1 other inst",rest,"| full-r2 diff",[round(x,3) for x in d],"| r3-r2",[round(x,3) for x in d3])
out["like_for_like"]=ll
# 2 per participant full-r1 test
print("== per participant full-r1 test (final head)")
pp={}
g=load("full-r1","final","greedy","test"); bm=load("full-r1","final","beam_lm","test"); cg=load("full-r1","conv","greedy","test")
r2g=load("r2","final","greedy","test")
byp=defaultdict(lambda: defaultdict(list)); subs=defaultdict(set)
for k in g:
    p=g[k]["participant"]; subs[p].add(g[k]["subject"])
    byp[p]["g"].append(g[k]["cer_target"]); byp[p]["b"].append(bm[k]["cer_target"]); byp[p]["c"].append(cg[k]["cer_target"])
    byp[p]["in_r2"].append(k in r2g)
for p in sorted(byp):
    v=byp[p]; pp[p]=dict(subjects=sorted(subs[p]),n=len(v["g"]),n_in_r2_set=int(sum(v["in_r2"])),greedy=float(np.mean(v["g"])),beam_lm=float(np.mean(v["b"])),conv_greedy=float(np.mean(v["c"])))
    print(p,pp[p])
out["per_participant_full_r1_test"]=pp
# 3 per unique sentence + near-variant
sp_=json.load(open(_OUT / "splits.json",encoding="utf-8"))
# train non-practice targets actually used: from cache
import glob
train_used=set()
for f in glob.glob("C:/Users/zhang/bci-data/cache/spanishbcbl/v1/S*/*.json"):
    for s in json.load(open(f,encoding="utf-8"))["segments"]:
        if s["split"]=="train" and not s.get("is_training"): train_used.add(normalize_text(s["target_text"]))
print("train unique used (non-practice):",len(train_used))
def nearest(t):
    b=min(train_used,key=lambda x: cer(t,x)); return b,cer(t,b)
print("== per unique test sentence (full-r1 final head)")
bys=defaultdict(lambda: defaultdict(list))
for k in g:
    t=normalize_text(g[k]["target_text"]); bys[t]["g"].append(g[k]["cer_target"]); bys[t]["b"].append(bm[k]["cer_target"])
    bys[t]["hyp_b"].append(normalize_text(bm[k]["hyp"]))
ps=[]
for t in sorted(bys):
    nb,nc=nearest(t)
    hyps=bys[t]["hyp_b"]
    hyp_is_train=sum(h in train_used for h in hyps)
    hyp_closer_to_nb=sum(cer(nb,h)<cer(t,h) for h in hyps)
    row=dict(sentence=t,n=len(bys[t]["g"]),greedy=float(np.mean(bys[t]["g"])),beam_lm=float(np.mean(bys[t]["b"])),nearest_train=nb,cer_nearest_train_vs_target=nc,beam_hyp_equals_train_sentence=hyp_is_train,beam_hyp_closer_to_nearest_train=hyp_closer_to_nb)
    ps.append(row); print(json.dumps(row,ensure_ascii=False))
out["per_test_sentence_full_r1"]=ps
close=[r for r in ps if r["cer_nearest_train_vs_target"]<=0.25]; far=[r for r in ps if r["cer_nearest_train_vs_target"]>0.25]
def wmean(rs,k): return float(sum(r[k]*r["n"] for r in rs)/sum(r["n"] for r in rs))
out["near_variant_split"]=dict(threshold_cer=0.25,close=dict(n_sent=len(close),n_inst=sum(r["n"] for r in close),greedy=wmean(close,"greedy"),beam_lm=wmean(close,"beam_lm")),far=dict(n_sent=len(far),n_inst=sum(r["n"] for r in far),greedy=wmean(far,"greedy"),beam_lm=wmean(far,"beam_lm")))
print("near-variant split",out["near_variant_split"])
# all hyps that are exactly a train sentence, all runs
for run in ["r2","full-r1","r3"]:
    for dec in ["greedy","beam_lm"]:
        rr=load(run,"final",dec,"test"); n=sum(normalize_text(r["hyp"]) in train_used for r in rr.values())
        print("hyp == a train sentence",run,dec,n,"/",len(rr))
        out.setdefault("hyp_equals_train",{})[f"{run}/{dec}"]=[n,len(rr)]
# 4 prior baselines for zeros
tests=[normalize_text(r["target_text"]) for r in g.values()]
# positional prior from train targets (instance-weighted from cache)
train_inst=[]
for f in glob.glob("C:/Users/zhang/bci-data/cache/spanishbcbl/v1/S*/*.json"):
    for s in json.load(open(f,encoding="utf-8"))["segments"]:
        if s["split"]=="train" and not s.get("is_training"): train_inst.append(normalize_text(s["target_text"]))
L=max(map(len,train_inst)); pos=[Counter() for _ in range(80)]
for t in train_inst:
    for i,ch in enumerate(t[:80]): pos[i][ch]+=1
posprior="".join(pos[i].most_common(1)[0][0] if pos[i] else "e" for i in range(80))
# length = typed length (oracle key count ~ typed); approximate with target length
def base(fn): return float(np.mean([cer(t,fn(t)) for t in tests]))
bl=dict(all_e=base(lambda t:"e"*len(t)), all_space=base(lambda t:" "*len(t)), positional_prior=base(lambda t: posprior[:len(t)]),
        empty=base(lambda t:""), best_constant_train_sentence=min((float(np.mean([cer(t,c) for t in tests])),c) for c in train_used))
print("prior baselines (test, full-r1 instances, CER vs target):",bl, "posprior:",posprior[:50])
out["prior_baselines_test_full_r1"]=bl; out["positional_prior_string"]=posprior[:50]
json.dump(out,open(_OUT / "analysis.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
