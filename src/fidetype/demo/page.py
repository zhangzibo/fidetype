"""The static demo page: one self-contained HTML file, no server, no network.

:func:`render` turns a decision log (:func:`fidetype.demo.run_session`)
into HTML. The page shows every final decision without JavaScript. With
JavaScript, "Play" replays the session on a timeline: the signal
evidence, the provisional previews and then the final decision of each
phrase, at the speed you select.
"""

from __future__ import annotations

import html
import json
from typing import Any

_ACTION_CLASS = {"COMMIT": "commit", "OFFER": "offer", "OFFER_WORDS": "offer", "ASK": "ask", "ABSTAIN": "abstain"}
_OUTCOME = {
    "commit-correct": ("typed, correct", "ok"),
    "commit-wrong": ("typed, wrong", "bad"),
    "offer-hit": ("offered; the intended text is in the offer", "ok"),
    "offer-miss": ("offered; the user rejects it", "muted"),
    "abstain": ("nothing typed", "muted"),
}

_CSS = """
:root{--bg:#fbfaf8;--fg:#1d1d1f;--muted:#5c5c66;--line:#dedbd5;--card:#ffffff;--accent:#2f5d8a;--ok:#2d7a3e;--bad:#a8322d;--head:#f1efea;
--commit:#2d7a3e;--offer:#9a6a00;--abstain:#a8322d;--ask:#2f5d8a;--spark:#2f5d8a;--sparkbg:#eef2f7}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#16171a;--fg:#e8e6e1;--muted:#a3a3ad;--line:#33353b;--card:#1d1f23;--accent:#8bb6e0;--ok:#7fc58d;--bad:#ef8a84;--head:#24262b;
--commit:#7fc58d;--offer:#e2b44f;--abstain:#ef8a84;--ask:#8bb6e0;--spark:#8bb6e0;--sparkbg:#23272e}}
:root[data-theme="dark"]{--bg:#16171a;--fg:#e8e6e1;--muted:#a3a3ad;--line:#33353b;--card:#1d1f23;--accent:#8bb6e0;--ok:#7fc58d;--bad:#ef8a84;--head:#24262b;
--commit:#7fc58d;--offer:#e2b44f;--abstain:#ef8a84;--ask:#8bb6e0;--spark:#8bb6e0;--sparkbg:#23272e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1080px;margin:0 auto;padding:24px 16px 48px}h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.2rem;margin:32px 0 6px}
p{margin:6px 0;color:var(--muted)}a{color:var(--accent)}code{font-size:12.5px}
.key{border:1px solid var(--line);border-left:4px solid var(--abstain);background:var(--card);border-radius:8px;padding:10px 14px;margin:14px 0}
.key b{color:var(--fg)}
.controls{position:sticky;top:0;z-index:2;background:var(--bg);padding:10px 0;display:flex;gap:8px;align-items:center;flex-wrap:wrap;border-bottom:1px solid var(--line)}
button,select{font:inherit;font-size:14px;padding:5px 12px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg);cursor:pointer}
button.primary{background:var(--accent);color:var(--bg);border-color:var(--accent)}
.clock{font-variant-numeric:tabular-nums;color:var(--muted);margin-left:auto}
.utt{border:1px solid var(--line);border-radius:8px;background:var(--card);padding:10px 14px;margin:10px 0;transition:opacity .2s}
.utt.pending{opacity:.35}.utt.active{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.uhead{display:flex;gap:10px;flex-wrap:wrap;align-items:baseline}.num{font-weight:600;font-variant-numeric:tabular-nums}
.cond{font-size:13px;padding:1px 8px;border-radius:10px;background:var(--head);color:var(--muted)}
.cond.null{color:var(--abstain)}.intended{color:var(--muted);font-size:14px}.intended q{color:var(--fg)}
svg.spark{display:block;width:100%;height:38px;margin:8px 0 4px;background:var(--sparkbg);border-radius:4px}
svg.spark polyline{fill:none;stroke:var(--spark);stroke-width:1.2;vector-effect:non-scaling-stroke}
svg.spark line{stroke:var(--fg);stroke-width:1.5;vector-effect:non-scaling-stroke;display:none}.utt.active svg.spark line{display:block}
.row{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;font-size:14px;margin:3px 0}
.lbl{width:118px;flex:none;color:var(--muted);font-size:13px}
.preview{display:none;color:var(--muted);font-style:italic}.utt.active .preview{display:flex}
.final{display:flex}.utt.pending .final,.utt.active .final,.utt.pending .base,.utt.active .base{visibility:hidden}
.badge{font-size:12px;font-weight:700;letter-spacing:.04em;padding:1px 8px;border-radius:4px;color:var(--bg)}
.badge.commit{background:var(--commit)}.badge.offer{background:var(--offer)}.badge.abstain{background:var(--abstain)}.badge.ask{background:var(--ask)}
.txt{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:13.5px;word-break:break-word}
.nums{color:var(--muted);font-size:12.5px;font-variant-numeric:tabular-nums}
.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}.muted{color:var(--muted)}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:var(--head);font-weight:600}td.n{font-variant-numeric:tabular-nums;white-space:nowrap}
ul{margin:6px 0 0 18px;color:var(--muted);font-size:14px}
@media (max-width:560px){.lbl{width:auto}.clock{margin-left:0;width:100%}}
"""

_JS = """
(function(){
const log=JSON.parse(document.getElementById('log').textContent);
const U=log.utterances, cards=[...document.querySelectorAll('.utt')];
const end=U.length?U[U.length-1].t0+U[U.length-1].duration:0;
let t=end, playing=false, last=0;
const clock=document.getElementById('clock'), play=document.getElementById('play'), speed=document.getElementById('speed');
function fmt(x){return x.toFixed(1)+' s / '+end.toFixed(1)+' s';}
function render(){
  U.forEach((u,i)=>{
    const c=cards[i], loc=t-u.t0;
    const st=loc<0?'pending':(loc<u.duration?'active':'done');
    c.classList.toggle('pending',st==='pending');c.classList.toggle('active',st==='active');
    if(st==='active'){
      const x=Math.max(0,Math.min(1,loc/u.duration))*1000;
      const ln=c.querySelector('svg.spark line');ln.setAttribute('x1',x);ln.setAttribute('x2',x);
      let pv=null;for(const p of u.previews){if(p.t<=loc)pv=p;else break;}
      const el=c.querySelector('.preview .txt'), nm=c.querySelector('.preview .nums');
      if(pv){const tx=pv.top1||'(empty)';el.textContent=tx.length>80?tx.slice(0,79)+'\u2026':tx;nm.textContent='provisional '+pv.action+' \\u00b7 p '+pv.p_top1.toFixed(2)+' \\u00b7 guard risk '+pv.guard_risk.toFixed(2);}
      else{el.textContent='(listening)';nm.textContent='';}
    }
  });
  clock.textContent=fmt(Math.min(t,end));
}
function frame(now){
  if(!playing)return;
  const dt=(now-last)/1000;last=now;t+=dt*parseFloat(speed.value);
  const a=document.querySelector('.utt.active');
  render();
  const b=document.querySelector('.utt.active');
  if(b&&b!==a){b.scrollIntoView({block:'nearest',behavior:'smooth'});}
  if(t>=end){playing=false;play.textContent='Play';t=end;render();return;}
  requestAnimationFrame(frame);
}
play.addEventListener('click',()=>{
  if(playing){playing=false;play.textContent='Play';return;}
  if(t>=end)t=0;
  playing=true;play.textContent='Pause';last=performance.now();requestAnimationFrame(frame);
});
document.getElementById('reset').addEventListener('click',()=>{playing=false;play.textContent='Play';t=0;render();window.scrollTo({top:0});});
document.getElementById('all').addEventListener('click',()=>{playing=false;play.textContent='Play';t=end;render();});
const m=/^#t=([0-9.]+)$/.exec(location.hash);if(m){t=Math.min(end,parseFloat(m[1]));}
render();
})();
"""


def _e(x: Any) -> str:
    return html.escape(str(x), quote=True)


def _clip(text: str, n: int = 80) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _spark(evidence: list[float]) -> str:
    n = max(1, len(evidence) - 1)
    pts = " ".join(f"{1000 * i / n:.1f},{38 - 34 * float(v):.1f}" for i, v in enumerate(evidence))
    return (f'<svg class="spark" viewBox="0 0 1000 38" preserveAspectRatio="none" role="img" '
            f'aria-label="signal evidence per frame (1 - p(blank))"><polyline points="{pts}"/>'
            f'<line x1="0" x2="0" y1="0" y2="38"/></svg>')


def _card(u: dict[str, Any]) -> str:
    f, b = u["final"], u["baseline"]
    null = u["truth"] is None
    intended = ("no intended text: the user is not typing" if null else f'intended: <q>{_e(u["truth"])}</q>')
    shown = " | ".join(f["shown"]) if f["shown"] else "(nothing)"
    otext, ocls = _OUTCOME[f["outcome"]]
    btext, bcls = ("correct", "ok") if b["outcome"] == "commit-correct" else ("wrong", "bad")
    return f"""<div class="utt" data-k="{u['k']}">
<div class="uhead"><span class="num">#{u['k'] + 1}</span><span class="cond{' null' if null else ''}">{_e(u['label'])}</span><span class="intended">{intended}</span></div>
{_spark(u['evidence'])}
<div class="row preview"><span class="lbl">decoder now</span><span class="txt">(listening)</span><span class="nums"></span></div>
<div class="row final"><span class="lbl">trust layer</span><span class="badge {_ACTION_CLASS.get(f['action'], 'ask')}">{_e(f['action'])}</span><span class="txt">{_e(shown)}</span><span class="nums">p {f['p_top1']:.2f} &middot; guard risk {f['guard_risk']:.2f} &middot; {_e(f['reason'])}</span><span class="{ocls}">{_e(otext)}</span></div>
<div class="row base"><span class="lbl">always commit</span><span class="txt" title="{_e(b['text'])}">{_e(_clip(b['text']) or '(empty)')}</span><span class="{bcls}">{btext}</span></div>
</div>"""


def _totals(totals: dict[str, Any]) -> str:
    if not totals:
        return "<p>No totals in this log (run <code>fidetype demo --totals 40 --html FILE</code>).</p>"
    rows = []
    for v in totals.values():
        c = v["trust"]
        rows.append(f"<tr><td>{_e(v['label'])}</td><td class=n>{v['n']}</td><td class=n>{c['commit-correct']}</td>"
                    f"<td class=n>{c['commit-wrong']}</td><td class=n>{c['offer-hit']}</td><td class=n>{c['offer-miss']}</td>"
                    f"<td class=n>{c['abstain']}</td><td class=n><b>{v['trust_wrong_commit_rate']:.3f}</b></td>"
                    f"<td class=n>{v['always_commit_wrong_commit_rate']:.3f}</td></tr>")
    return ("<div class=wrap><table><thead><tr><th>Condition</th><th>Phrases</th><th>COMMIT correct</th><th>COMMIT wrong</th>"
            "<th>OFFER, text in offer</th><th>OFFER, rejected</th><th>ABSTAIN</th><th>Trust: wrong-commit rate</th>"
            "<th>Always commit: wrong-commit rate</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


def render(log: dict[str, Any]) -> str:
    """Return the demo page (HTML) for a decision log."""
    pol, rc = log["policy"], log.get("risk_control", {})
    ns = log.get("totals", {}).get("no-signal")
    key = ""
    if ns:
        typed = ns["trust"]["commit-correct"] + ns["trust"]["commit-wrong"]
        key = (f'<div class="key"><b>No signal, no text.</b> On {ns["n"]} flat (no-signal) streams, the decoder\'s '
               f'language model still writes text made of real words. "Always commit" types it every time '
               f'({round(ns["always_commit_wrong_commit_rate"] * ns["n"])}/{ns["n"]}). The trust layer typed '
               f'{typed}/{ns["n"]}: the hallucination guard sees that the characters have no neural evidence and '
               f'abstains. Paper 1 reports the same result on real data: no text committed from null input.</div>')
    data = json.dumps(log, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    cards = "\n".join(_card(u) for u in log["utterances"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fidetype Trust Demo</title><style>{_CSS}</style></head><body><main>
<h1>Fidetype trust layer: live demo</h1>
<p>A simulated neural decoder sends NeuralTextStream frames. The streaming trust layer reads them and decides for each phrase:
<b>COMMIT</b> (type the text), <b>OFFER</b> (show the text; the user confirms or rejects it) or <b>ABSTAIN</b> (type nothing).
Grey previews are provisional decisions while the signal arrives; a consumer never types them.
All data on this page is synthetic. Nothing is sent over a network.</p>
{key}
<div class="controls"><button id="play" class="primary">Play</button><button id="reset">Reset</button><button id="all">Show all</button>
<label>speed <select id="speed"><option value="1">1&times;</option><option value="2">2&times;</option><option value="4" selected>4&times;</option><option value="8">8&times;</option></select></label>
<span id="clock" class="clock"></span></div>
<h2>Session: {len(log['utterances'])} phrases</h2>
<p>The order of conditions is fixed in advance; no phrase was selected by its outcome. The blue line is the signal evidence per frame (1 &minus; p(blank)).</p>
{cards}
<h2>Totals</h2>
<p>Other phrases, final decisions only. Wrong-commit rate = wrong commits / phrases. On null input every typed text is wrong.</p>
{_totals(log.get('totals', {}))}
<h2>Set-up</h2>
<ul>
<li>Decoder: {_e(log['decoder'])}, fitted on other synthetic phrases. Frames at {1 / log['frame_period']:.0f} Hz; a provisional decision every {_e(log.get('partial_every_frames'))} frames.</li>
<li>Signal levels: simulator target CER 0.05 (strong), 0.17 (good), 0.28 (medium), 0.41 (weak); confidence temperature 0.5 (over-confident, as real decoders). Null inputs: a flat (near-uniform) stream and a frame-shuffled stream.</li>
<li>Trust configuration <code>{_e(log['config_id'])}</code> (frozen, Paper 1 recipe, fitted on synthetic data): COMMIT if p &ge; {pol['commit_p']} and guard risk &le; {pol['commit_max_risk']}; ABSTAIN if guard risk &ge; {pol['abstain_risk']}; else OFFER the top {pol['offer_max_k']}. Commit threshold from {_e(rc.get('method'))} (alpha {_e(rc.get('alpha'))}, delta {_e(rc.get('delta'))}, n = {_e(rc.get('n'))}). One attempt per phrase, so the layer never asks for a repeat.</li>
<li>Synthetic results show how the layer behaves. They are not a measurement of a real device. Real results: Paper 1 and the open benchmark.</li>
<li>Reproduce: install Fidetype from the repository (<code>pip install .</code>), then <code>fidetype demo --html demo.html</code>. Fidetype {_e(log.get('fidetype_version', ''))}; generated by <code>fidetype demo</code>, do not edit by hand.</li>
</ul>
</main>
<script type="application/json" id="log">{data}</script>
<script>{_JS}</script>
</body></html>
"""
