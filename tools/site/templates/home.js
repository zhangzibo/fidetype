(function(){
'use strict';
var RM = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function $(id){return document.getElementById(id)}
function el(tag,cls,html){var e=document.createElement(tag);if(cls)e.className=cls;if(html!=null)e.innerHTML=html;return e}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}

/* =====================================================================
   1. HERO ANIMATION (made-up values; illustrates the idea only)
   ===================================================================== */
var SCENES=[
  {q:'strong',amp:1,cands:[['i need help',0.93],['i need hell',0.04],['i feed help',0.02]],act:'commit',text:'i need help',
   cap:'Strong signal. One guess has a high score. The guard commits, and the text types.'},
  {q:'weak',amp:0.45,cands:[['open the window',0.48],['open the door',0.39],['close the window',0.09]],act:'offer',
   cap:'Weak signal. Two guesses are close. The guard offers a short list, and the user picks one.'},
  {q:'none',amp:0,cands:[['thank you so much',0.34],['good morning',0.33],['no thanks',0.33]],act:'withhold',
   cap:'No signal. The language model still writes fluent text. The guard sees no support for it, and types nothing.'}
];
var cur=0,playing=!RM,timers=[],cycleT=null;
var cv=$('wave'),cx=cv.getContext('2d'),amp=1,tAmp=1,phase=0,raf=null,heroVisible=true;
function sizeCanvas(){var r=cv.getBoundingClientRect(),d=window.devicePixelRatio||1;cv.width=Math.max(1,r.width*d);cv.height=Math.max(1,r.height*d);cx.setTransform(d,0,0,d,0,0)}
function sigColor(){return '#46c7e0'}
function drawWave(){
  var w=cv.width/(window.devicePixelRatio||1),h=cv.height/(window.devicePixelRatio||1);
  cx.clearRect(0,0,w,h);
  // baseline grid
  cx.strokeStyle='rgba(167,174,196,.15)';cx.lineWidth=1;cx.beginPath();cx.moveTo(0,h/2);cx.lineTo(w,h/2);cx.stroke();
  cx.strokeStyle=sigColor();cx.lineWidth=1.8;cx.beginPath();
  for(var x=0;x<=w;x+=2){
    var t=(x+phase)/w*6;
    var burst=Math.exp(-Math.pow(((x+phase*0.7)%260)-130,2)/900);
    var s=Math.sin(t*5.1)*0.35+Math.sin(t*11.3+1)*0.25+Math.sin(t*23.7)*0.12+burst*Math.sin(t*31)*0.9;
    var n=(Math.sin(x*12.9898+phase*0.37)*43758.5453)%1*0.18;
    var y=h/2-(s*amp+n*(0.4+0.6*(1-amp)))*h*0.42;
    if(x===0)cx.moveTo(x,y);else cx.lineTo(x,y);
  }
  cx.stroke();
}
function loop(){amp+= (tAmp-amp)*0.06;phase+=2.2;drawWave();raf=(playing&&heroVisible)?requestAnimationFrame(loop):null}
function startLoop(){if(!raf&&playing&&heroVisible)raf=requestAnimationFrame(loop)}

function clearTimers(){timers.forEach(clearTimeout);timers=[];clearTimeout(cycleT)}
function later(fn,ms){timers.push(setTimeout(fn,ms))}
function show(i,instant){
  clearTimers();cur=i;var s=SCENES[i];
  document.querySelectorAll('.scenes [data-scene]').forEach(function(b){b.setAttribute('aria-pressed',String(+b.dataset.scene===i))});
  var q=$('sigq');q.textContent=s.q==='none'?'no signal':s.q;q.className='sigq'+(s.q==='none'?' none':'');
  tAmp=s.amp;if(instant){amp=s.amp;drawWave()}
  var box=$('cands');box.innerHTML='';
  s.cands.forEach(function(c){var r=el('div','cand');r.innerHTML='<span class="t">'+esc(c[0])+'</span><span class="b"><i></i></span><span class="v">'+c[1].toFixed(2)+'</span>';box.appendChild(r)});
  ['commit','offer','withhold'].forEach(function(a){$('s-'+a).classList.remove('on')});
  var scr=$('screen');scr.innerHTML='<span class="caret"></span>';$('without').hidden=true;$('stage-cap').textContent='';
  ['l2','l3','l4'].forEach(function(l){$(l).classList.remove('flow')});
  var D=instant?0:1;
  later(function(){$('l2').classList.add('flow');[].forEach.call(box.children,function(r,k){r.classList.add('on');r.querySelector('i').style.width=(s.cands[k][1]*100)+'%'})},900*D);
  later(function(){$('l3').classList.add('flow');$('s-'+s.act).classList.add('on')},1900*D);
  later(function(){$('l4').classList.add('flow');renderScreen(s,instant)},2500*D);
  later(function(){$('stage-cap').textContent=s.cap},2600*D);
  if(playing&&!instant)cycleT=setTimeout(function(){show((cur+1)%SCENES.length)},7600);
}
function renderScreen(s,instant){
  var scr=$('screen');
  if(s.act==='commit'){
    var span=el('span');scr.insertBefore(span,scr.firstChild);
    if(instant){span.textContent=s.text;return}
    var k=0;(function type(){span.textContent=s.text.slice(0,++k);if(k<s.text.length)later(type,70)})();
  }else if(s.act==='offer'){
    scr.innerHTML='';
    s.cands.slice(0,3).forEach(function(c,k){var o=el('span','opt-chip');o.textContent=c[0];scr.appendChild(o);if(k===0)later(function(){o.classList.add('pick')},instant?0:1500)});
  }else{
    scr.innerHTML='<span class="nothing">nothing typed</span><span class="caret"></span>';
    var w=$('without');w.hidden=false;w.innerHTML='Without a trust layer, an app would type: <s>"'+esc(s.cands[0][0])+'"</s>';
  }
}
document.querySelector('.scenes').addEventListener('click',function(e){
  var b=e.target.closest('[data-scene]');if(b){show(+b.dataset.scene,!playing);return}
  if(e.target.closest('#pp')){playing=!playing;var p=$('pp');p.textContent=playing?'❚❚':'▶';p.setAttribute('aria-label',playing?'Pause animation':'Play animation');
    if(playing){startLoop();show(cur)}else{clearTimeout(cycleT)}}
});
if(RM){var p=$('pp');p.textContent='▶';p.setAttribute('aria-label','Play animation')}
sizeCanvas();window.addEventListener('resize',function(){sizeCanvas();drawWave()});
if('IntersectionObserver' in window){new IntersectionObserver(function(es){heroVisible=es[0].isIntersecting;startLoop()}).observe($('wave'))}
drawWave();show(0,RM);startLoop();

/* =====================================================================
   2. TOY SIMULATION (fake decoder, simplified guard)
   ===================================================================== */
function rngFrom(seed){return function(){seed|=0;seed=seed+0x6D2B79F5|0;var t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
function kum(u,a,b){return Math.pow(1-Math.pow(1-u,1/b),1/a)} // Kumaraswamy: a simple bounded score
var st={alpha:0.05,q:'strong',live:'signal',over:false,seed:7};
var OFFER_FLOOR=0.30,NCAL=400,NNULL=100,NLIVE=100;
function draw(rng,kind){ // p: top score; right: top guess is right; sq: evidence of signal (used by the offer gate)
  var p,right,sq;
  if(kind==='null'){p=st.over?kum(rng(),4,1.6):kum(rng(),1.3,4);right=false;sq=0.45*rng()}
  else{p=st.q==='strong'?kum(rng(),3.2,0.9):kum(rng(),1.8,1.6);right=rng()<p;sq=st.q==='strong'?0.6+0.4*rng():0.3+0.7*rng()}
  return {p:p,right:right,sq:sq};
}
function simulate(){
  var rng=rngFrom(st.seed);
  var cal=[],nul=[],live=[],i;
  for(i=0;i<NCAL;i++)cal.push(draw(rng,'sig'));
  for(i=0;i<NNULL;i++)nul.push(draw(rng,'null'));
  for(i=0;i<NLIVE;i++)live.push(draw(rng,st.live==='none'?'null':'sig'));
  // Fixed-sequence scan: lambda from 1.00 down; stop at the first lambda whose wrong-commit rate > alpha.
  var lam=1.01;
  for(var L=100;L>=0;L--){var l=L/100,wrong=0;for(i=0;i<NCAL;i++)if(cal[i].p>=l&&!cal[i].right)wrong++;
    if(wrong/NCAL<=st.alpha)lam=l;else break;}
  var nullCommits=0;nul.forEach(function(d){if(d.p>=lam)nullCommits++});
  var limit=Math.floor(st.alpha*NNULL);
  var refused=nullCommits>limit;
  var out=live.map(function(d){var a=d.p>=lam?(d.right?'c':'w'):(d.p>=OFFER_FLOOR&&d.sq>=0.5?'o':'h');return a});
  var baseWrong=live.filter(function(d){return !d.right}).length;
  return {lam:lam,nullCommits:nullCommits,limit:limit,refused:refused,out:out,baseWrong:baseWrong};
}
var cells=$('cells');for(var k=0;k<NLIVE;k++)cells.appendChild(el('div','cell h'));
var GL={c:'✓',w:'✗',o:'…',h:'–'};
function render(){
  var r=simulate();
  $('alpha-out').textContent=st.alpha.toFixed(2);
  var cnt={c:0,w:0,o:0,h:0};
  r.out.forEach(function(a,i){cnt[a]++;var c=cells.children[i];if(c.dataset.a!==a){c.className='cell '+a+(RM?'':' pop');c.textContent=GL[a];c.dataset.a=a;if(!RM)setTimeout(function(){c.classList.remove('pop')},260+i*3)}});
  cells.classList.toggle('dim',r.refused);
  cells.setAttribute('aria-label','Decisions for 100 simulated sentences: '+cnt.c+' right commits, '+cnt.w+' wrong commits, '+cnt.o+' offers, '+cnt.h+' withholds.');
  var ref=$('refused');
  if(r.refused){ref.className='refused show';ref.innerHTML='<b>Guard refused.</b> On 100 no-signal inputs, this guard committed '+r.nullCommits+' times. The limit at this alpha is '+r.limit+'. Fidetype returns no guard. The grid shows what the refused guard would do.'}
  else{ref.className='refused';ref.innerHTML=''}
  var wr=cnt.w/NLIVE;
  $('stats').innerHTML=
    '<div class="stat"><b style="color:var(--commit)">'+cnt.c+'</b><span>right commits</span></div>'+
    '<div class="stat"><b style="color:var(--wrong)">'+cnt.w+'</b><span>wrong commits</span></div>'+
    '<div class="stat"><b style="color:var(--offer)">'+cnt.o+'</b><span>offers</span></div>'+
    '<div class="stat"><b>'+cnt.h+'</b><span>withholds</span></div>';
  $('m-guard').style.width=(wr*100)+'%';$('n-guard').textContent=cnt.w+' / 100';
  $('m-base').style.width=(r.baseWrong)+'%';$('n-base').textContent=r.baseWrong+' / 100';
  $('m-a1').style.left=(st.alpha*100)+'%';$('m-a1').setAttribute('data-l','alpha '+st.alpha.toFixed(2));
  $('m-a2').style.left=(st.alpha*100)+'%';
  var v;
  if(r.refused)v='The no-signal check caught a guard that types text the signal does not support.';
  else if(r.lam>1)v='No commit threshold meets this alpha. The guard never commits. It only offers or withholds.';
  else if(st.live==='none')v='No signal: always-commit types '+r.baseWrong+' wrong sentences. The guard commits '+(cnt.c+cnt.w)+' times.';
  else v='The guard commits when the top score is at least '+r.lam.toFixed(2)+'. Wrong commits: '+cnt.w+' of 100 (target: at most '+Math.round(st.alpha*100)+'). '+(cnt.w>st.alpha*100?'This draw is above the target. The rate is a bound over many sentences, not over one small set.':'');
  $('verdict').textContent=v;
}
$('alpha').addEventListener('input',function(e){st.alpha=+e.target.value;render()});
function segBind(attr,key){document.querySelectorAll('[data-'+attr+']').forEach(function(b){b.addEventListener('click',function(){
  st[key]=b.dataset[attr];document.querySelectorAll('[data-'+attr+']').forEach(function(x){x.setAttribute('aria-pressed',String(x===b))});render()})})}
segBind('q','q');segBind('in','live');
$('overconf').addEventListener('change',function(e){st.over=e.target.checked;render()});
$('redo').addEventListener('click',function(){st.seed=Math.floor(Math.random()*1e9);render()});
render();

/* =====================================================================
   3. SCROLL PIPELINE
   ===================================================================== */
var STEPS=[
  {t:'Signal',d:'A device records a body signal: EEG, MEG, EMG or an implant. A replay file works too.',ic:'M14 26h6l3-8 5 16 4-12 3 4h5'},
  {t:'Your decoder',d:'Your model turns the signal into ranked guesses with scores. You keep your model.',ic:'M18 16h16v20H18zM22 22h8M22 28h5M14 22h4M14 30h4M34 22h4M34 30h4'},
  {t:'SDK writes NTS',d:'The SDK writes the guesses as NTS, one open format. Python, TypeScript or Rust.',ic:'M20 18l-6 8 6 8M32 18l6 8-6 8M28 16l-4 20'},
  {t:'Collector',d:'One service reads NTS from files, WebSocket or LSL. It runs processors and sends the results on.',ic:'M14 20h8v12h-8zM30 20h8v12h-8zM22 26h8'},
  {t:'Trust layer',d:'For each sentence it decides: commit, offer or withhold. It writes each decision to an audit log.',ic:'M26 14l10 4v8c0 6-4 10-10 12-6-2-10-6-10-12v-8zM21 26l4 4 7-8'},
  {t:'Apps and benchmark',d:'Apps act only on final decisions. The benchmark scores safe WPM on public datasets.',ic:'M16 16h20v14H16zM22 36h8M26 30v6'}
];
var pn=$('pnodes'),pl=$('plinks'),NS='http://www.w3.org/2000/svg',Y0=50,DY=120;
function sv(tag,attrs){var e=document.createElementNS(NS,tag);for(var a in attrs)e.setAttribute(a,attrs[a]);return e}
STEPS.forEach(function(s,i){
  var y=Y0+i*DY;
  if(i>0)pl.appendChild(sv('line',{class:'plink',x1:210,y1:y-DY+32,x2:210,y2:y-32,id:'pl'+i}));
  var g=sv('g',{class:'pnode',id:'pn'+i});
  g.appendChild(sv('rect',{x:60,y:y-32,width:300,height:64,rx:16}));
  var ig=sv('g',{transform:'translate('+(78)+','+(y-26)+')'});ig.appendChild(sv('path',{class:'ic',d:s.ic}));g.appendChild(ig);
  var tx=sv('text',{x:140,y:y+5});tx.textContent=s.t;g.appendChild(tx);
  pn.appendChild(g);
  var li=el('li','step');li.dataset.i=i;
  li.innerHTML='<svg class="mini" viewBox="0 0 52 52" aria-hidden="true"><path d="'+s.ic+'" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="n">STEP '+(i+1)+' / 6</span><h3>'+esc(s.t)+'</h3><p>'+esc(s.d)+'</p>';
  $('steps').appendChild(li);
});
var dot=$('pdot'),dotY=Y0,dotT=Y0,dotRaf=null;
function animDot(){dotY+=(dotT-dotY)*(RM?1:0.12);dot.setAttribute('cy',dotY.toFixed(1));if(Math.abs(dotT-dotY)>0.5)dotRaf=requestAnimationFrame(animDot);else{dot.setAttribute('cy',dotT);dotRaf=null}}
function activate(i){
  document.querySelectorAll('.step').forEach(function(s){s.classList.toggle('on',+s.dataset.i===i)});
  STEPS.forEach(function(_,k){var n=$('pn'+k);n.classList.toggle('on',k===i);n.classList.toggle('done',k<i);var l=$('pl'+k);if(l)l.classList.toggle('on',k<=i)});
  dotT=Y0+i*DY-32-8;if(!dotRaf)dotRaf=requestAnimationFrame(animDot);
}
dotY=dotT=Y0-40;dot.setAttribute('cy',dotY);
if('IntersectionObserver' in window){var sio=new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting)activate(+x.target.dataset.i)})},{rootMargin:'-45% 0px -45% 0px'});
  document.querySelectorAll('.step').forEach(function(s){sio.observe(s)})}
activate(0);

/* =====================================================================
   4. NUMBERS CHART (values from the build: tools/site/numbers.json)
   ===================================================================== */
// Rows come from tools/site/numbers.json. The build checks each number against its source file.
var ROWS=JSON.parse(document.getElementById('numbers-data').textContent);
function drawChart(){
  var box=$('chart'),narrow=box.clientWidth<560;
  var W=narrow?380:760,LW=narrow?14:250,RH=narrow?112:92,TOP=narrow?8:16,H=TOP+ROWS.length*RH+34,X0=LW,X1=W-16,MAX=10;
  function X(v){return X0+(X1-X0)*v/MAX}
  var s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-labelledby="ch-t ch-d"><title id="ch-t">Safe WPM with the trust layer against a no-BCI baseline</title><desc id="ch-d">'+ROWS.map(function(r){return r.l+': '+r.v.toFixed(2)+' safe WPM, '+r.ci+' interval '+r.lo.toFixed(2)+' to '+r.hi.toFixed(2)+', baseline '+r.b.toFixed(2)+'. '+r.verdict+'.'}).join(' ')+'</desc><g class="grid">';
  for(var t=0;t<=MAX;t+=2)s+='<line x1="'+X(t)+'" x2="'+X(t)+'" y1="'+TOP+'" y2="'+(H-30)+'"/><text class="ax" x="'+X(t)+'" y="'+(H-12)+'" text-anchor="middle">'+t+'</text>';
  s+='<text class="ax" x="'+X1+'" y="'+(H+8)+'" text-anchor="end">words per minute</text></g>';
  ROWS.forEach(function(r,i){
    var y=narrow?TOP+i*RH+66:TOP+i*RH+RH/2-10, lx=narrow?0:0, ly=narrow?y-46:y-6;
    s+='<g class="row" tabindex="0" data-tip="'+esc(r.l+': '+r.v.toFixed(2)+' ['+r.lo.toFixed(2)+', '+r.hi.toFixed(2)+'] safe WPM. Baseline '+r.b.toFixed(2)+'. '+r.verdict+'.')+'">'+
      '<rect x="0" y="'+(narrow?y-62:y-34)+'" width="'+W+'" height="'+RH+'" fill="transparent"/>'+
      '<text class="rl" x="'+lx+'" y="'+ly+'">'+esc(r.l)+'</text><text class="rs" x="'+lx+'" y="'+(ly+17)+'">'+esc(narrow?r.verdict:r.s)+'</text>'+
      (narrow?'':'<text class="rs" x="0" y="'+(ly+34)+'" style="font-weight:600">'+esc(r.verdict.split(':')[0])+'</text>')+
      '<line class="ci" x1="'+X(r.lo)+'" x2="'+X(r.hi)+'" y1="'+y+'" y2="'+y+'"/>'+
      '<line class="ci" x1="'+X(r.lo)+'" x2="'+X(r.lo)+'" y1="'+(y-6)+'" y2="'+(y+6)+'"/><line class="ci" x1="'+X(r.hi)+'" x2="'+X(r.hi)+'" y1="'+(y-6)+'" y2="'+(y+6)+'"/>'+
      '<rect class="base" x="'+(X(r.b)-5.5)+'" y="'+(y-5.5)+'" width="11" height="11" transform="rotate(45 '+X(r.b)+' '+y+')"/>'+
      '<circle class="est" cx="'+X(r.v)+'" cy="'+y+'" r="7"/>'+
      '<text class="vl" x="'+X(r.v)+'" y="'+(narrow?y+22:y-14)+'" text-anchor="middle">'+r.v.toFixed(2)+'</text>'+
      '<text class="vd" x="'+X(r.b)+'" y="'+(y+22)+'" text-anchor="middle">'+r.b.toFixed(2)+'</text></g>';
  });
  s+='</svg>';box.innerHTML=s;
  document.querySelectorAll('.chart g.row').forEach(function(g){
    g.addEventListener('mousemove',function(e){showTip(g,e.clientX,e.clientY)});
    g.addEventListener('mouseleave',function(){tip.style.opacity=0});
    g.addEventListener('focus',function(){var b=g.getBoundingClientRect();showTip(g,b.left+b.width/3,b.top+b.height/2)});
    g.addEventListener('blur',function(){tip.style.opacity=0});
  });
}
var tip=$('tip');
function showTip(g,x,y){tip.textContent=g.getAttribute('data-tip');tip.style.left=Math.max(8,Math.min(x+14,window.innerWidth-270))+'px';tip.style.top=(y+14)+'px';tip.style.opacity=1}
drawChart();var lastNarrow=$('chart').clientWidth<560;
window.addEventListener('resize',function(){var n=$('chart').clientWidth<560;if(n!==lastNarrow){lastNarrow=n;drawChart()}});
$('num-table').innerHTML='<thead><tr><th>Setup</th><th>Safe WPM ['+esc(ROWS[0].ci)+' interval]</th><th>No-BCI baseline</th><th>Result</th></tr></thead><tbody>'+
  ROWS.map(function(r){return '<tr><td>'+esc(r.l)+' <span style="color:var(--muted)">('+esc(r.s)+')</span></td><td>'+r.v.toFixed(2)+' ['+r.lo.toFixed(2)+', '+r.hi.toFixed(2)+']</td><td>'+r.b.toFixed(2)+'</td><td>'+esc(r.verdict)+'</td></tr>'}).join('')+'</tbody>';

/* =====================================================================
   5. INSTALL TABS (arrow keys move between tabs)
   ===================================================================== */
var tabs=[].slice.call(document.querySelectorAll('[role=tab]'));
function sel(t){tabs.forEach(function(x){var on=x===t;x.setAttribute('aria-selected',String(on));x.tabIndex=on?0:-1;$(x.getAttribute('aria-controls')).hidden=!on});t.focus()}
tabs.forEach(function(t,i){t.addEventListener('click',function(){sel(t)});t.addEventListener('keydown',function(e){
  if(e.key==='ArrowRight'){e.preventDefault();sel(tabs[(i+1)%tabs.length])}
  if(e.key==='ArrowLeft'){e.preventDefault();sel(tabs[(i+tabs.length-1)%tabs.length])}})});
})();
