# M1-15 full-r1 / r3 leakage + like-for-like analysis (2026-11-10). CPU only. Run in order: leak.py, analyse.py, extra.py (repo .venv).
from pathlib import Path as _P; _OUT = _P(__file__).resolve().parent
import json,glob,sys,bz2,os
from collections import defaultdict, Counter
sys.path.insert(0,"C:/Users/zhang/OneDrive/Documents/GitHub/stealth-project/src")
from fidetype.data.preprocess import assign_split
from fidetype.streams.vocab import normalize_text
root="C:/Users/zhang/bci-data/cache/spanishbcbl/v1"
sents=defaultdict(set); inst=Counter(); mism=0; blocks=0
istrain=Counter()
for f in glob.glob(root+"/S*/*.json"):
    d=json.load(open(f,encoding="utf-8")); blocks+=1
    for s in d["segments"]:
        n=normalize_text(s["target_text"]); sp=s["split"]
        if assign_split(s["target_text"])!=sp: mism+=1
        sents[sp].add(n); inst[sp]+=1; istrain[(sp,s.get("is_training"))]+=1
print("blocks",blocks,"instances",dict(inst),"unique",{k:len(v) for k,v in sents.items()},"split/hash mismatches",mism)
print("is_training x split", dict(istrain))
tr,va,te=sents["train"],sents["val"],sents["test"]
print("exact overlap test&train",len(te&tr),"val&train",len(va&tr),"test&val",len(te&va))
# near duplicates: word-level containment / shared word n-grams
def wng(s,n): w=s.split(); return {tuple(w[i:i+n]) for i in range(len(w)-n+1)}
def sim(a,b):
    import difflib; return difflib.SequenceMatcher(None,a,b).ratio()
print("\n-- test sentences: closest train sentence")
rows=[]
for split,S in (("test",te),("val",va)):
  for t in sorted(S):
    best=max(tr,key=lambda x: sim(t,x)); r=sim(t,best)
    contained=[x for x in tr if x in t or t in x]
    sh4=max(len(wng(t,4)&wng(x,4)) for x in tr)
    sh3=max(len(wng(t,3)&wng(x,3)) for x in tr)
    rows.append((split,t,best,round(r,3),len(contained),sh3,sh4))
    print(split,"|",t,"|",best,"| ratio",round(r,3),"| train contained/containing",len(contained),"| max shared word 3-grams",sh3,"4-grams",sh4)
json.dump({"train":sorted(tr),"val":sorted(va),"test":sorted(te)},open(_OUT / "splits.json","w",encoding="utf-8"),ensure_ascii=False,indent=0)
# LM corpus
bl=set(x for x in open("C:/Users/zhang/bci-data/lm/spanishbcbl_blocklist.txt",encoding="utf-8").read().splitlines() if x)
print("\nblocklist size",len(bl),"test in blocklist",len(te&bl),"/",len(te),"val in blocklist",len(va&bl),"train in blocklist",len(tr&bl),"/",len(tr))
seen=set(); corpus=[]
with bz2.open("C:/Users/zhang/bci-data/corpora/tatoeba/spa_sentences.tsv.bz2","rt",encoding="utf-8") as f:
    for line in f:
        p=line.rstrip("\n").split("\t")
        if len(p)<3: continue
        s=normalize_text(p[2])
        if s and s not in seen: seen.add(s); corpus.append(s)
print("tatoeba spa unique",len(corpus))
allt=te|va|tr
print("raw Tatoeba exact matches: test",len(te&seen),"val",len(va&seen),"train",len(tr&seen), [x for x in allt if x in seen])
cont={t:[c for c in corpus if t in c] for t in te|va}
print("raw Tatoeba sentences containing a test/val sentence:",{t:len(v) for t,v in cont.items() if v})
# after build exclusion (exact + containment of long targets): replicate
long_block=[b for b in bl if len(b)>=15]
kept=[s for s in corpus if s not in bl and not any(b in s for b in long_block) and not (len(s)>=15 and any(s in b for b in long_block))]
print("kept (LM train+heldout pool)",len(kept),"removed",len(corpus)-len(kept))
ks=set(kept)
print("post-exclusion exact matches test",len(te&ks),"val",len(va&ks))
print("post-exclusion containing test/val:",sum(1 for s in kept for t in (te|va) if t in s))
# word 4-gram overlap of test sentences with LM corpus
lm4=set()
for s in kept:
    lm4|=wng(s,4)
for t in sorted(te):
    g=wng(t,4); print("test 4-gram coverage in LM corpus",t,f"{len(g&lm4)}/{len(g)}")
