r"""P3-12 post-hoc check (written after the pre-registered C1 check failed as written): is the streaming CRT exact?

It runs the batch model (`_forward`) and the streaming model (`CRTStream`) in float32 (as shipped) and in float64
(the same code with float32 swapped for float64), on 12 windows of 1,000 frames (6 sessions x 2 starts; u0
weights of P11-07, read only). Output: max probability differences and argmax agreements (printed; copied into
results.md). CPU, 1 thread, about 1 min.

    .venv\Scripts\python.exe -I experiments/2026-11-20-p3-12-emg-latency-budget/f64_check.py
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys, json, numpy
sys.path.insert(0, "C:/Users/zhang/OneDrive/Documents/GitHub/stealth-project/src")
import fidetype.pretrained._crt as C
D="C:/Users/zhang/bci-data/derived/p11-07/"
g=json.load(open(D+"modellat-gpu.json")); mc=g["model_cfg"]
z=numpy.load(D+"modellat-params-u0.npz"); p={k:numpy.asarray(z[k]) for k in z.files}
kw=dict(ring_k=mc["ring_k"],kernel=mc["kernel"],dilations=tuple(mc["dilations"]))
import glob
files=sorted(glob.glob("C:/Users/zhang/bci-data/derived/p11-01-emg-decoder/sessions/*.feat.npy"))[:6]
class NP:
    float32 = numpy.float64
    def __getattr__(self, k): return getattr(numpy, k)
def run(f, dt64):
    C.np = NP() if dt64 else numpy
    ref = C._forward(p, f, **kw).astype(numpy.float64)
    s = C.CRTStream(p, **kw)
    out = numpy.concatenate([s.push(f[a:a+4]) for a in range(0, len(f), 4)]).astype(numpy.float64)
    C.np = numpy
    return ref, out
rows=[]
for fn in files:
    feat=numpy.load(fn, mmap_mode="r")
    for a0 in (3000, 20000):
        f=numpy.asarray(feat[a0:a0+1000], numpy.float32)
        b32, s32 = run(f, False); b64, s64 = run(f, True)
        P=lambda x: numpy.exp(x)
        rows.append((numpy.abs(P(b32)-P(b64)).max(), numpy.abs(P(s32)-P(b64)).max(), numpy.abs(P(s64)-P(b64)).max(), numpy.abs(P(s32)-P(b32)).max(), (s32.argmax(1)==b64.argmax(1)).mean(), (b32.argmax(1)==b64.argmax(1)).mean()))
r=numpy.array(rows)
print("max over 12 windows of 1000 frames: batch32 vs f64 %.2e | stream32 vs f64 %.2e | stream64 vs batch64 %.2e | stream32 vs batch32 %.2e | argmax agree s32/b32 vs f64 min %.4f %.4f" % (r[:,0].max(), r[:,1].max(), r[:,2].max(), r[:,3].max(), r[:,4].min(), r[:,5].min()))
